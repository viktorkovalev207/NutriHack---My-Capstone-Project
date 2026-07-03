"""
test_clean_pipeline.py — in-memory DataFrame tests for the cleaning stages that
decide WHICH products get certified. No data files needed.

Pins: the step2b exact-0.8x boundary (strict `<` keeps the boundary row), the
skip-when-macros-missing rule, energy imputation, the negative-value guards
(drop core / clip fvl), and the per-category median imputation.

Run:  python tests/test_clean_pipeline.py   (or pytest)
"""
import sys, os
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from nutrihack_clean import (step2_plausibility, step2b_energy_consistency,
                             step3_impute_energy, step5_median_impute)


def test_step2b_exact_boundary_is_kept():
    """P/C/F = 10/10/10 -> Atwater min 710, bound 0.8x = 568.0.
    A row at EXACTLY the bound survives (strict <); just below is dropped."""
    df = pd.DataFrame({"energy_kj": [568.0, 567.9],
                       "proteins_g": [10.0] * 2, "carbs_g": [10.0] * 2,
                       "fat_g": [10.0] * 2})
    kept = step2b_energy_consistency(df)["energy_kj"].tolist()
    assert kept == [568.0], kept


def test_step2b_skips_rows_with_missing_macros():
    """Rows awaiting energy imputation must not be judged by the guard."""
    df = pd.DataFrame({"energy_kj": [100.0], "proteins_g": [10.0],
                       "carbs_g": [float("nan")], "fat_g": [10.0]})
    assert len(step2b_energy_consistency(df)) == 1


def test_step3_imputes_atwater_energy():
    df = pd.DataFrame({"energy_kj": [float("nan")], "proteins_g": [10.0],
                       "carbs_g": [10.0], "fat_g": [10.0]})
    out = step3_impute_energy(df)
    assert out["energy_kj"].tolist() == [710.0]
    # consistency by construction: the imputed row passes step2b
    assert len(step2b_energy_consistency(out)) == 1


def test_step2_drops_negative_core_and_clips_negative_fvl():
    df = pd.DataFrame({
        "product_name": ["neg sugar", "neg fvl", "clean"],
        "energy_kj": [1000.0, 1000.0, 1000.0],
        "sugars_g": [-1.0, 5.0, 5.0],
        "fvl_pct": [0.0, -3.0, 10.0],
    })
    out = step2_plausibility(df)
    assert out["product_name"].tolist() == ["neg fvl", "clean"]
    assert out["fvl_pct"].tolist() == [0.0, 10.0]   # -3 clipped to 0, 10 kept


def test_step2_upper_caps_still_enforced():
    df = pd.DataFrame({"product_name": ["impossible", "ok"],
                       "proteins_g": [120.0, 80.0], "fvl_pct": [0.0, 0.0]})
    out = step2_plausibility(df)
    assert out["product_name"].tolist() == ["ok"]


def test_step5_median_impute_per_category():
    df = pd.DataFrame({
        "product_type": ["bar", "bar", "bar", "powder", "powder"],
        "salt_g": [0.2, 0.4, float("nan"), 2.0, float("nan")],
        # remaining imputable columns present so the loop runs
        "energy_kj": [1.0] * 5, "sugars_g": [1.0] * 5, "sat_fat_g": [1.0] * 5,
        "fibre_g": [1.0] * 5, "proteins_g": [1.0] * 5, "fat_g": [1.0] * 5,
        "carbs_g": [1.0] * 5,
    })
    out = step5_median_impute(df)
    # bar median = 0.3 (of 0.2, 0.4); powder median = 2.0 — no cross-category
    # leak. Float tolerance: median(0.2, 0.4) is 0.30000000000000004 in IEEE754;
    # harmless downstream (step7 rounds to 2 dp, engine ladders round to 6 dp).
    assert abs(out.loc[2, "salt_g"] - 0.3) < 1e-9, out.loc[2, "salt_g"]
    assert out.loc[4, "salt_g"] == 2.0, out.loc[4, "salt_g"]


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
