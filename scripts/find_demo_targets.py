"""
find_demo_targets.py
====================
Scan products_scored.csv for real, branded products currently at Nutri-Score
D or E where a SINGLE, realistic reformulation lever (sugar OR salt reduction)
flips the grade to C or B. These are the live "drag-the-slider" demo cases.

"Realistic" guardrails:
  - product must be branded + have a sane name (no blank/junk)
  - macros in plausible ranges (data-quality filter)
  - the required reduction is <= MAX_REL_CUT of the current value AND leaves a
    non-negative result (you cannot reformulate below 0 g)
  - we report the MINIMUM reduction that achieves the flip (crisp boundary)
"""
import sys, os
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
from nutriscore import score_general_food

SCORED = ROOT / "data" / "clean" / "products_scored.csv"
MAX_REL_CUT = 0.55          # max realistic relative reduction of one nutrient
GRADE_ORDER = dict(A=0, B=1, C=2, D=3, E=4)

NUTRIENT_KEYS = dict(energy_kj="energy_kj", sugar_g="sugars_g", sat_fat_g="sat_fat_g",
                     salt_g="salt_g", fibre_g="fibre_g", protein_g="proteins_g",
                     fvl_percent="fvl_pct")


def macros(row):
    return {k: float(row[col]) for k, col in NUTRIENT_KEYS.items()}


def grade_of(m):
    return score_general_food(**m).letter


def min_cut_to_target(m, lever, target_grades=("C", "B", "A"), step=0.1):
    """Smallest reduction of `lever` (g) that reaches a target grade. None if not
    reachable within MAX_REL_CUT."""
    cur = m[lever]
    if cur <= 0:
        return None
    limit = cur * MAX_REL_CUT
    reduced = 0.0
    while reduced <= limit + 1e-9:
        trial = dict(m)
        trial[lever] = max(0.0, cur - reduced)
        if grade_of(trial) in target_grades:
            new_g = grade_of(trial)
            return dict(grams_cut=round(reduced, 1),
                        pct_cut=round(reduced / cur * 100, 1),
                        new_value=round(trial[lever], 2),
                        new_grade=new_g)
        reduced += step
    return None


def plausible(row, m):
    name = str(row.get("product_name", "")).strip()
    brand = str(row.get("brands", "")).strip()
    if len(name) < 3 or name.lower() in ("nan", "none"):
        return False
    if not brand or brand.lower() in ("nan", "none"):
        return False
    if not (0 <= m["sugar_g"] <= 100 and 0 <= m["salt_g"] <= 15
            and 0 < m["energy_kj"] <= 4000 and 0 <= m["protein_g"] <= 100):
        return False
    return True


def run():
    df = pd.read_csv(SCORED, dtype={"barcode": str})
    de = df[df["ns_letter"].isin(["D", "E"])].copy()
    print(f"D/E products to scan: {len(de):,}")

    found = []
    for _, row in de.iterrows():
        m = macros(row)
        if not plausible(row, m):
            continue
        sugar = min_cut_to_target(m, "sugar_g")
        salt = min_cut_to_target(m, "salt_g")
        best = None
        for lever, res in (("sugar", sugar), ("salt", salt)):
            if res is None:
                continue
            # prefer the smaller relative effort
            if best is None or res["pct_cut"] < best[1]["pct_cut"]:
                best = (lever, res)
        if best is None:
            continue
        lever, res = best
        found.append(dict(
            name=str(row["product_name"]).strip(),
            brand=str(row["brands"]).strip(),
            type=row["product_type"],
            cur_grade=row["ns_letter"],
            cur_score=int(row["ns_score"]),
            protein_counted=bool(row["ns_protein_counted"]),
            lever=lever,
            **{f"lever_{k}": v for k, v in res.items()},
            energy_kj=round(m["energy_kj"], 0), sugar_g=round(m["sugar_g"], 1),
            sat_fat_g=round(m["sat_fat_g"], 1), salt_g=round(m["salt_g"], 2),
            fibre_g=round(m["fibre_g"], 1), protein_g=round(m["protein_g"], 1),
        ))

    res_df = pd.DataFrame(found)
    out = ROOT / "data" / "processed" / "demo_target_candidates.csv"
    res_df.sort_values("lever_pct_cut").to_csv(out, index=False, encoding="utf-8")
    print(f"flippable branded D/E products found: {len(res_df):,}  -> {out.relative_to(ROOT)}")

    def _min_lever_g(lever):
        return 5.0 if lever == "sugar" else 0.30   # meaningful, visible cut

    # --- GROUP A: intuitive stage demo -------------------------------------
    # Solidly D (score >= 13, NOT the 11-point knife-edge) + a clearly visible
    # single-lever cut. This is the believable "drag the slider, watch D->C".
    intuitive = res_df[(res_df["cur_score"] >= 13)
                       & (res_df.apply(lambda r: r["lever_grams_cut"] >= _min_lever_g(r["lever"]), axis=1))]
    # diversify a little: prefer a spread of magnitudes, recognizable single brand
    intuitive = intuitive.sort_values(["lever_pct_cut", "cur_score"]).head(8)

    # --- GROUP B: the smart "protein-cap unlock" story ---------------------
    capcases = res_df[(res_df["protein_counted"] == False)
                      & (res_df["protein_g"] >= 25)].sort_values("protein_g", ascending=False).head(4)

    def show(r, tag=""):
        cap = "  [PROTEIN-CAP: protein currently NOT counted -> wasted]" if not r["protein_counted"] else ""
        src = r['sugar_g'] if r['lever'] == 'sugar' else r['salt_g']
        print(f"\n* {r['name']}  —  {r['brand']}  ({r['type']}){tag}")
        print(f"    now: Nutri-Score {r['cur_grade']} (raw score {r['cur_score']}){cap}")
        print(f"    macros/100g: energy {r['energy_kj']:.0f}kJ | sugar {r['sugar_g']}g | "
              f"sat-fat {r['sat_fat_g']}g | salt {r['salt_g']}g | fibre {r['fibre_g']}g | protein {r['protein_g']}g")
        print(f"    LEVER: cut {r['lever']} {src}g -> {r['lever_new_value']}g "
              f"(-{r['lever_grams_cut']}g, -{r['lever_pct_cut']:.0f}%)  =>  flips D->{r['lever_new_grade']}")

    print("\n" + "=" * 78)
    print("GROUP A — INTUITIVE STAGE DEMO (solidly-D, visible single-lever flip)")
    print("=" * 78)
    for _, r in intuitive.iterrows():
        show(r)

    print("\n" + "=" * 78)
    print("GROUP B — SMART 'PROTEIN-CAP UNLOCK' STORY (tiny cut frees wasted protein)")
    print("=" * 78)
    for _, r in capcases.iterrows():
        show(r, tag="  <- bonus narrative")


if __name__ == "__main__":
    run()
