"""
test_engine.py — workbook-independent unit tests for the engine's contracts.

Pins: the float-precision fix, simulate()'s key validation, the clamp-to-zero
rule, the documented docstring example, and the reject-invalid-input contract.
Pure Python — runs on a fresh clone with no data files.

Run:  python tests/test_engine.py   (or pytest tests/test_engine.py)
"""
import sys, os, math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from nutriscore import score_general_food, simulate

BASE = dict(energy_kj=1600, sugar_g=12, sat_fat_g=3, salt_g=0.5,
            fibre_g=3, protein_g=70, fvl_percent=0)


def test_simulate_float_regression():
    """8.4 - 5.0 == 3.4000000000000004 in IEEE754 — must score like exact 3.4."""
    base = dict(BASE, sugar_g=8.4)
    r = simulate(base, {"sugar_g": -5})
    exact = score_general_food(**{**base, "sugar_g": 3.4})
    assert r.score_after == exact.score, (r.score_after, exact.score)
    # same for salt: 3.0 - 0.3
    base = dict(BASE, salt_g=3.0)
    r = simulate(base, {"salt_g": -0.3})
    exact = score_general_food(**{**base, "salt_g": 2.7})
    assert r.score_after == exact.score, (r.score_after, exact.score)


def test_simulate_rejects_unknown_change_key():
    """A typo'd lever key must raise, not silently report 'no improvement'."""
    try:
        simulate(BASE, {"sugars_g": -8})   # typo: real key is sugar_g
    except ValueError as e:
        assert "sugars_g" in str(e)
    else:
        raise AssertionError("unknown changes key did not raise")


def test_simulate_rejects_unknown_base_key():
    """A typo'd base key would score the real nutrient as 0 g -> inflated grade."""
    bad = dict(BASE)
    bad["sugars_g"] = bad.pop("sugar_g")
    try:
        simulate(bad, {"sugar_g": -5})
    except ValueError as e:
        assert "sugars_g" in str(e)
    else:
        raise AssertionError("unknown base key did not raise")


def test_simulate_clamps_to_zero():
    base = dict(BASE, sugar_g=12)
    r = simulate(base, {"sugar_g": -99})
    exact = score_general_food(**{**base, "sugar_g": 0.0})
    assert r.score_after == exact.score


def test_simulate_docstring_case():
    """The documented example: sugar -8 on a high-protein base flips D -> B."""
    r = simulate(BASE, {"sugar_g": -8})
    assert r.letter_before == "D" and r.letter_after == "B", (r.letter_before, r.letter_after)
    assert r.grade_changed is True


def test_engine_rejects_negative_input():
    """Negative grams graded silently as 'A' was the old failure mode."""
    for field in ("energy_kj", "sugar_g", "sat_fat_g", "salt_g",
                  "fibre_g", "protein_g", "fvl_percent"):
        bad = dict(BASE)
        bad[field] = -1
        try:
            score_general_food(**bad)
        except ValueError as e:
            assert field in str(e)
        else:
            raise AssertionError(f"negative {field} did not raise")


def test_engine_rejects_nan_input():
    bad = dict(BASE, salt_g=float("nan"))
    try:
        score_general_food(**bad)
    except ValueError as e:
        assert "salt_g" in str(e)
    else:
        raise AssertionError("NaN salt_g did not raise")


def test_zero_inputs_are_valid():
    """All-zero is legitimate (e.g. water-based powder base) — must not raise."""
    r = score_general_food(0, 0, 0, 0, 0, 0, 0)
    assert r.letter == "A" and r.score == 0


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
