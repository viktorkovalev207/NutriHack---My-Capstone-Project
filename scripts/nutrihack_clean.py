"""
nutrihack_clean.py
==================
Stage 2 — Data Cleaning & Imputation
NutriHack Capstone · Viktor Kovalev · 2026

Input:  data/raw/products_raw.csv
Output: data/clean/products_clean.csv

Cleaning decisions (documented for Limitations & Bias section):
  1. Drop rows with no product_name
  2. Plausibility filter: per-100g values physically impossible if > hard caps
     (e.g. proteins > 100 g/100g) → flagged as data_error and dropped
  3. Energy imputation: if energy_kj is missing but macros are present,
     estimate via standard Atwater kJ factors:
       energy_kj ≈ 17·protein + 17·carbs + 37·fat  (ignores fibre for simplicity)
  4. fvl_pct: always 0 for protein powders/bars (no fruit/veg/legumes content
     expected; imputing 0 is conservative = worst-case for the score → safe)
  5. Remaining nutrient NaNs: impute with per-product_type median
     (median is robust to outliers; within-category imputation keeps
     the bias contained)
  6. After imputation, drop rows still missing any scoring-critical column
     (energy_kj, sugars_g, sat_fat_g, salt_g, proteins_g)
  7. fibre_g NaN: impute with category median (fibre is lowest-impact positive
     component; median imputation understates fibre → conservatively bad for score)
  8. PROVENANCE: every imputed value is flagged per row (imp_<col>, imputed_any,
     data_basis = measured|contains_estimates). A score based on guessed salt is
     not certification-grade; the flags make that visible downstream (Tableau)
     instead of hiding it. fvl_assumed_zero is tracked separately (structural
     conservative assumption, not a guess).
"""

import sys, os
import pandas as pd
import numpy as np
from pathlib import Path

ROOT     = Path(__file__).parent.parent
RAW_CSV  = ROOT / "data" / "raw"  / "products_raw.csv"
CLEAN_CSV = ROOT / "data" / "clean" / "products_clean.csv"

# --- Hard plausibility caps (values per 100 g) ----------------------------
# Anything above these is physically impossible and indicates a data entry error.
# Protein powder at 100 % protein would be max 100 g; fat max 100 g; etc.
# Energy: pure fat = 37 kJ/g × 100 g = 3700 kJ. We allow a small buffer.
CAPS = {
    "energy_kj":  4200,  # slightly above pure fat (37 kJ/g × ~113% — generous)
    "proteins_g":  100,
    "fat_g":       100,
    "carbs_g":     100,
    "sugars_g":    100,
    "sat_fat_g":   100,
    "fibre_g":     100,
    "salt_g":       30,  # extremely salty would be 10g; 30 gives real outlier room
    "fvl_pct":    100,
}

# Columns required for Nutri-Score scoring (engine cannot run without these)
SCORING_COLS = ["energy_kj", "sugars_g", "sat_fat_g", "salt_g", "proteins_g"]

# Score-relevant columns whose imputation is a GUESS (Atwater estimate or
# category median) and must therefore be flagged per row in the output.
# fvl_pct is deliberately NOT in this list: filling it with 0 is a structural
# assumption (protein powders/bars contain no fruit/veg; 0 is the worst case
# FOR the score, so it can never flatter a product) — it gets its own flag.
GUESS_COLS = ["energy_kj", "sugars_g", "sat_fat_g", "salt_g", "fibre_g", "proteins_g"]


def load(path):
    df = pd.read_csv(path, dtype={"barcode": str})
    print(f"Loaded {len(df):,} rows from {path.name}")
    return df


def step1_drop_no_name(df):
    before = len(df)
    df = df.dropna(subset=["product_name"])
    print(f"[1] Drop missing product_name:  {before - len(df):>4} removed → {len(df):,} remain")
    return df


def step2_plausibility(df):
    """Remove rows outside physical bounds (upper caps AND negative values).

    Negative nutrient amounts are physically impossible; the scoring engine
    refuses them (ValueError), so they must never leave this stage. Exception:
    fvl_pct — OFF's "estimate-from-ingredients" occasionally yields small
    negative estimates; the rest of such a row is fine, so we clip to 0
    (the conservative floor for protein products) instead of dropping.
    """
    n_clip = int((df["fvl_pct"] < 0).sum()) if "fvl_pct" in df.columns else 0
    if n_clip:
        df.loc[df["fvl_pct"] < 0, "fvl_pct"] = 0.0
    flag = pd.Series(False, index=df.index)
    for col, cap in CAPS.items():
        if col in df.columns:
            bad = df[col].notna() & ((df[col] > cap) | (df[col] < 0))
            flag |= bad
    before = len(df)
    df = df[~flag].copy()
    print(f"[2] Drop implausible values:    {before - len(df):>4} removed, "
          f"{n_clip} negative fvl_pct clipped → {len(df):,} remain")
    return df


def step2b_energy_consistency(df):
    """Drop rows whose STATED energy is physically impossible vs their macros.

    A food cannot contain less energy than its macronutrients already hold.
    Atwater lower bound (kJ): energy_kj >= 0.8 * (17*protein + 17*carbs + 37*fat),
    where 0.8 leaves 20% slack for measurement/rounding noise. Applied ONLY where
    energy and all three macros are present, so rows awaiting energy imputation
    (step3) are untouched — and imputed energy is consistent by construction.
    Catches corrupt OFF entries such as a bar listing 620 kJ while its macros
    imply >=1400 kJ, which would otherwise score with a far-too-low energy point.

    Boundary semantics (pinned by tests/test_clean_pipeline.py): rows EXACTLY at
    the 0.8x bound are KEPT — the comparison is strict `<`. Changing it to `<=`
    silently changes which products get certified; do that only deliberately.
    """
    have = (df["energy_kj"].notna() & df["proteins_g"].notna()
            & df["carbs_g"].notna() & df["fat_g"].notna())
    lower = 0.8 * (17 * df["proteins_g"] + 17 * df["carbs_g"] + 37 * df["fat_g"])
    bad = have & (df["energy_kj"] < lower)
    before = len(df)
    df = df[~bad].copy()
    print(f"[2b] Drop impossible-low energy: {before - len(df):>4} removed → {len(df):,} remain")
    return df


def step3_impute_energy(df):
    """Estimate energy_kj from macros where kJ is missing but macros are present."""
    missing_energy = df["energy_kj"].isna()
    has_macros = df["proteins_g"].notna() & df["carbs_g"].notna() & df["fat_g"].notna()
    mask = missing_energy & has_macros
    df.loc[mask, "energy_kj"] = (
        17 * df.loc[mask, "proteins_g"]
        + 17 * df.loc[mask, "carbs_g"]
        + 37 * df.loc[mask, "fat_g"]
    ).round(1)
    print(f"[3] Impute energy from macros:  {mask.sum():>4} values filled")
    return df


def step4_fvl_zero(df):
    """FVL (fruit/veg/legumes): always 0 for protein powders/bars."""
    n = df["fvl_pct"].isna().sum()
    df["fvl_pct"] = df["fvl_pct"].fillna(0.0)
    print(f"[4] Fill fvl_pct → 0:          {n:>4} values filled")
    return df


def step5_median_impute(df):
    """Impute remaining NaNs with per-product_type median."""
    imputable = ["energy_kj", "sugars_g", "sat_fat_g", "salt_g",
                 "fibre_g", "proteins_g", "fat_g", "carbs_g"]
    total_filled = 0
    for col in imputable:
        medians = df.groupby("product_type")[col].transform("median")
        missing = df[col].isna()
        df.loc[missing, col] = medians[missing]
        total_filled += missing.sum()
    print(f"[5] Median impute by category:  {total_filled:>4} values filled")
    return df


def snapshot_missing(df):
    """Pre-imputation NaN snapshot — the basis for the provenance flags.

    Call BEFORE steps 3-5 (the imputing steps). Returns (guess_na, fvl_na).
    """
    return df[GUESS_COLS].isna(), df["fvl_pct"].isna()


def step_provenance(df, guess_na, fvl_na):
    """Attach per-row imputation provenance so no estimated value can hide.

    A manufacturer-facing 'certification' tool must distinguish scores computed
    from measured label values from scores that rest on statistical guesses.
    Adds, per row:
      imp_<col>        True where <col> was NaN pre-imputation and is filled now
      imputed_any      True if ANY scoring-relevant value was guessed
      data_basis       'measured' | 'contains_estimates'  (Tableau-friendly)
      fvl_assumed_zero True where fvl_pct was filled with the structural 0
                       (tracked separately — a documented conservative
                        assumption, not a guess; it can only worsen the score)
    """
    for col in GUESS_COLS:
        df[f"imp_{col}"] = (guess_na.loc[df.index, col] & df[col].notna())
    df["fvl_assumed_zero"] = fvl_na.loc[df.index] & df["fvl_pct"].notna()
    imp_cols = [f"imp_{c}" for c in GUESS_COLS]
    df["imputed_any"] = df[imp_cols].any(axis=1)
    df["data_basis"] = df["imputed_any"].map(
        {True: "contains_estimates", False: "measured"})
    n = int(df["imputed_any"].sum())
    print(f"[7] Provenance: {n:,} of {len(df):,} rows contain >=1 imputed "
          f"scoring value ({n / len(df) * 100:.1f}%)")
    return df


def step6_drop_still_missing(df):
    """Drop rows that are still missing any scoring-critical value after imputation."""
    before = len(df)
    df = df.dropna(subset=SCORING_COLS)
    print(f"[6] Drop still-missing score cols: {before - len(df):>4} removed → {len(df):,} remain")
    return df


def step7_round_and_types(df):
    """Round numerics to reasonable precision and ensure types are consistent."""
    num_cols = ["energy_kj", "sugars_g", "sat_fat_g", "salt_g",
                "fibre_g", "proteins_g", "fat_g", "carbs_g", "fvl_pct"]
    for col in num_cols:
        if col in df.columns:
            df[col] = df[col].round(2)
    # Clean product_name and brands
    df["product_name"] = df["product_name"].str.strip()
    df["brands"]       = df["brands"].str.strip() if "brands" in df.columns else df.get("brands")
    return df


def print_summary(df):
    print()
    print("=== CLEAN DATASET SUMMARY ===")
    print(f"Total products:  {len(df):,}")
    print()
    print(df["product_type"].value_counts().to_string())
    print()
    print("Missing values remaining:")
    missing = df.isnull().sum()
    print(missing[missing > 0].to_string() if missing.any() else "  none in scoring columns")
    print()
    print("Numeric stats (scoring columns):")
    sc = ["energy_kj","sugars_g","sat_fat_g","salt_g","fibre_g","proteins_g"]
    print(df[sc].describe().round(2).to_string())


def clean():
    CLEAN_CSV.parent.mkdir(parents=True, exist_ok=True)

    df = load(RAW_CSV)
    df = step1_drop_no_name(df)
    df = step2_plausibility(df)
    df = step2b_energy_consistency(df)
    guess_na, fvl_na = snapshot_missing(df)   # provenance baseline (pre-impute)
    df = step3_impute_energy(df)
    df = step4_fvl_zero(df)
    df = step5_median_impute(df)
    df = step6_drop_still_missing(df)
    df = step_provenance(df, guess_na, fvl_na)
    df = step7_round_and_types(df)

    df.to_csv(CLEAN_CSV, index=False, encoding="utf-8")
    print_summary(df)
    print(f"\nClean data written to:\n  {CLEAN_CSV}")


if __name__ == "__main__":
    clean()
