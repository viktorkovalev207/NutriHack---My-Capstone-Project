"""
Nutri-Score 2023/2024 scoring engine — GENERAL FOODS.

Forward function only (this is the SIMULATOR core, per simulator_vs_optimierer.md).
Given nutrient values per 100 g, returns the points breakdown, raw score and letter.

The scoring rule — including the protein-cap — is transcribed EXACTLY from the
live formula on the workbook's "General foods" sheet:

    Points A (negative) = sugar + salt + energy + sat_fat          [cell AB3]
    Points C (positive) = protein + fvl + fibre                    [cell AC3]
    Score = IF(A < 11, A - C, A - fibre - fvl)                     [cell AD3]

i.e. when negative points reach 11, PROTEIN points stop counting (fibre and FVL
still count). This is the single most important rule for protein products.

VERIFICATION (see tests/oracle_validation.py): this engine reproduces the
workbook's own formula output on 620 boundary-focused grid cases with ZERO
mismatches — 534 of them in the protein-cap region. The oracle is an independent
code path (the `formulas` engine evaluating the workbook's verbatim formulas),
so a match proves the transcription of both thresholds and the cap rule is
faithful. (The workbook itself ships only 3 worked example products, far too few
to trust on their own — hence the synthetic-grid oracle.)
"""
from dataclasses import dataclass, asdict
from . import thresholds as T


def _ladder(value, table):
    """points = how many thresholds `value` strictly exceeds (see thresholds.py)."""
    return sum(1 for t in table if value > t)


def _fvl_points(fvl_pct):
    for upper, pts in T.FVL_PCT:
        if fvl_pct <= upper:
            return pts
    return 5


@dataclass
class ScoreResult:
    energy_pts: int
    sat_fat_pts: int
    sugar_pts: int
    salt_pts: int
    negative_pts: int          # "Points A"
    protein_pts: int
    fibre_pts: int
    fvl_pts: int
    positive_pts: int          # "Points C"
    protein_counted: bool      # False when capped by the >=11 rule
    score: int                 # raw numeric score
    letter: str                # A..E

    def as_dict(self):
        return asdict(self)


def score_general_food(
    energy_kj: float,
    sugar_g: float,
    sat_fat_g: float,
    salt_g: float,
    fibre_g: float,
    protein_g: float,
    fvl_percent: float = 0.0,
) -> ScoreResult:
    """Score a SOLID/general food. All nutrients per 100 g; salt in g (not sodium)."""
    energy_pts = _ladder(energy_kj, T.ENERGY_KJ)
    sat_fat_pts = _ladder(sat_fat_g, T.SAT_FAT_G)
    sugar_pts = _ladder(sugar_g, T.SUGAR_G)
    salt_pts = _ladder(salt_g, T.SALT_G)
    fibre_pts = _ladder(fibre_g, T.FIBRE_G)
    protein_pts = _ladder(protein_g, T.PROTEIN_G)
    fvl_pts = _fvl_points(fvl_percent)

    negative = sugar_pts + salt_pts + energy_pts + sat_fat_pts
    positive = protein_pts + fvl_pts + fibre_pts

    # Protein-cap rule (workbook General foods!AD3)
    if negative < 11:
        score = negative - positive
        protein_counted = True
    else:
        score = negative - fibre_pts - fvl_pts   # protein dropped
        protein_counted = False

    letter = "E"
    for bound, lt in T.LETTER_BOUNDS:
        if score < bound:
            letter = lt
            break

    return ScoreResult(
        energy_pts=energy_pts, sat_fat_pts=sat_fat_pts, sugar_pts=sugar_pts,
        salt_pts=salt_pts, negative_pts=negative,
        protein_pts=protein_pts, fibre_pts=fibre_pts, fvl_pts=fvl_pts,
        positive_pts=positive, protein_counted=protein_counted,
        score=score, letter=letter,
    )


@dataclass
class SimulateResult:
    score_before:  int
    letter_before: str
    score_after:   int
    letter_after:  str
    score_delta:   int    # negative = improved
    grade_changed: bool


def simulate(
    base_product: dict,
    changes: dict,
) -> SimulateResult:
    """
    Forward what-if simulation (Simulator core, see simulator_vs_optimierer.md).

    base_product : nutrient dict with keys matching score_general_food params
                   (energy_kj, sugar_g, sat_fat_g, salt_g, fibre_g, protein_g,
                    fvl_percent)
    changes      : delta dict, e.g. {"sugar_g": -8.0} or {"protein_g": +5}
                   Values are ADDED to the base; result is clamped to >= 0.

    Example
    -------
    >>> r = simulate(
    ...     {"energy_kj": 1600, "sugar_g": 12, "sat_fat_g": 3,
    ...      "salt_g": 0.5, "fibre_g": 3, "protein_g": 70, "fvl_percent": 0},
    ...     {"sugar_g": -8}
    ... )
    >>> r.grade_changed
    True
    """
    PARAM_KEYS = ("energy_kj", "sugar_g", "sat_fat_g", "salt_g",
                  "fibre_g", "protein_g", "fvl_percent")

    def _call(values):
        return score_general_food(
            energy_kj=values.get("energy_kj", 0),
            sugar_g=values.get("sugar_g", 0),
            sat_fat_g=values.get("sat_fat_g", 0),
            salt_g=values.get("salt_g", 0),
            fibre_g=values.get("fibre_g", 0),
            protein_g=values.get("protein_g", 0),
            fvl_percent=values.get("fvl_percent", 0),
        )

    before = _call(base_product)

    modified = dict(base_product)
    for key, delta in changes.items():
        modified[key] = max(0.0, modified.get(key, 0) + delta)

    after = _call(modified)

    return SimulateResult(
        score_before=before.score,
        letter_before=before.letter,
        score_after=after.score,
        letter_after=after.letter,
        score_delta=after.score - before.score,
        grade_changed=before.letter != after.letter,
    )
