"""
test_boundaries.py — workbook-independent pins for the scoring boundaries.

Pins: exact letter-band edges (A/B/C/D/E), the protein-cap flip at negative
points 10 vs 11 (a +0.01 g salt difference that jumps a full letter), and the
non-linear FVL ladder incl. the 2 -> 5 jump. Pure Python, no data files.

Run:  python tests/test_boundaries.py   (or pytest)
"""
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from nutriscore import score_general_food
from nutriscore.engine import _fvl_points


def _score_of(energy=0, sugar=0, sat=0, salt=0, fibre=0, protein=0, fvl=0):
    return score_general_food(energy, sugar, sat, salt, fibre, protein, fvl)


def test_letter_bounds_exact():
    """Workbook AE3: <1 A, <3 B, <11 C, <19 D, else E — at the exact edges."""
    cases = [
        (_score_of(protein=3), -1, "A"),           # 1 protein pt -> score -1
        (_score_of(), 0, "A"),                      # all zero -> 0
        (_score_of(energy=336), 1, "B"),            # 1 energy pt
        (_score_of(energy=671), 2, "B"),
        (_score_of(energy=1006), 3, "C"),
        (_score_of(energy=3351), 10, "C"),          # 10 energy pts, neg<11
        (_score_of(energy=3351, sugar=3.5), 11, "D"),   # neg=11 (cap active)
        (_score_of(energy=3351, sugar=27.1), 18, "D"),  # 10+8
        (_score_of(energy=3351, sugar=31.1), 19, "E"),  # 10+9
    ]
    for res, want_score, want_letter in cases:
        assert res.score == want_score, (res.score, want_score)
        assert res.letter == want_letter, (res.score, res.letter, want_letter)


def test_protein_cap_flip_at_11():
    """+0.01 g salt flips negative pts 10 -> 11: protein stops counting and the
    grade jumps a full letter (C -> D). The sharpest cliff in the algorithm."""
    below = _score_of(sugar=34.1, salt=0.20, protein=30)   # neg = 10
    above = _score_of(sugar=34.1, salt=0.21, protein=30)   # neg = 11
    assert below.negative_pts == 10 and below.protein_counted is True
    assert below.score == 3 and below.letter == "C"
    assert above.negative_pts == 11 and above.protein_counted is False
    assert above.score == 11 and above.letter == "D"


def test_fvl_ladder_bounds_and_jump():
    """FVL is 0/1/2/5 (no 3, 4): bounds at 40/60/80, then the jump to 5."""
    expected = [(0, 0), (40, 0), (40.0001, 1), (60, 1), (60.0001, 2),
                (80, 2), (80.0001, 5), (100, 5)]
    for value, want in expected:
        got = _fvl_points(value)
        assert got == want, (value, got, want)


def test_protein_cap_keeps_fibre_and_fvl():
    """Above the cap, protein is dropped but fibre and FVL still count
    (workbook AD3: neg - fibre - fvl, NOT neg - all positives)."""
    r = _score_of(energy=3351, sugar=3.5, fibre=8, protein=30, fvl=90)
    assert r.negative_pts == 11 and r.protein_counted is False
    # score = 11 - fibre_pts(5) - fvl_pts(5) = 1, NOT 11 - 17
    assert r.fibre_pts == 5 and r.fvl_pts == 5
    assert r.score == 1, r.score


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted({k: v for k, v in globals().items()
                            if k.startswith("test_") and callable(v)}.items()):
        try:
            fn()
            print(f"  OK    {name}")
        except Exception as e:
            fails += 1
            print(f"  FAIL  {name}: {e}")
    print("\nRESULT:", "PASS" if fails == 0 else f"FAIL ({fails})")
    sys.exit(0 if fails == 0 else 1)
