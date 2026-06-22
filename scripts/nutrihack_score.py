"""
nutrihack_score.py
==================
Stage 3 — Batch Scoring
NutriHack Capstone · Viktor Kovalev · 2026

Runs every cleaned product through the Nutri-Score 2024 engine
and appends the result columns.

Input:  data/clean/products_clean.csv
Output: data/clean/products_scored.csv
"""

import sys, os
import pandas as pd
from pathlib import Path

ROOT      = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nutriscore import score_general_food, classify_product

CLEAN_CSV  = ROOT / "data" / "clean" / "products_clean.csv"
SCORED_CSV = ROOT / "data" / "clean" / "products_scored.csv"

# Result columns produced per product. Kept as a constant so the beverages
# bypass can emit the SAME schema (all-None numerics) without drifting.
NS_NUMERIC_COLS = [
    "ns_score", "ns_negative_pts", "ns_positive_pts", "ns_energy_pts",
    "ns_sugar_pts", "ns_sat_fat_pts", "ns_salt_pts", "ns_protein_pts",
    "ns_fibre_pts", "ns_fvl_pts", "ns_protein_counted",
]


def score_row(row):
    # Step 1: classify (all protein powders/bars are general_foods in Scope 1)
    cls = classify_product(
        product_name=row.get("product_name"),
        category=row.get("categories"),
    )

    # Step 2: beverages use a DIFFERENT Nutri-Score rule set (own point tables +
    # the 2024 sweetener malus). The general-foods engine would emit a wrong,
    # liability-grade letter, so we bypass it entirely and flag for manual
    # review instead of fabricating a score.
    if cls.category == "beverages":
        out = {col: None for col in NS_NUMERIC_COLS}
        out["ns_category"] = cls.category
        out["ns_letter"] = "REVIEW_REQUIRED"
        return out

    # Step 3: score (general foods)
    res = score_general_food(
        energy_kj  = float(row["energy_kj"]),
        sugar_g    = float(row["sugars_g"]),
        sat_fat_g  = float(row["sat_fat_g"]),
        salt_g     = float(row["salt_g"]),
        fibre_g    = float(row["fibre_g"]),
        protein_g  = float(row["proteins_g"]),
        fvl_percent= float(row["fvl_pct"]),
    )

    return {
        "ns_category":        cls.category,
        "ns_score":           res.score,
        "ns_letter":          res.letter,
        "ns_negative_pts":    res.negative_pts,
        "ns_positive_pts":    res.positive_pts,
        "ns_energy_pts":      res.energy_pts,
        "ns_sugar_pts":       res.sugar_pts,
        "ns_sat_fat_pts":     res.sat_fat_pts,
        "ns_salt_pts":        res.salt_pts,
        "ns_protein_pts":     res.protein_pts,
        "ns_fibre_pts":       res.fibre_pts,
        "ns_fvl_pts":         res.fvl_pts,
        "ns_protein_counted": res.protein_counted,
    }


def run():
    df = pd.read_csv(CLEAN_CSV, dtype={"barcode": str})
    print(f"Loaded {len(df):,} products")

    score_cols = df.apply(score_row, axis=1, result_type="expand")
    df = pd.concat([df, score_cols], axis=1)

    df.to_csv(SCORED_CSV, index=False, encoding="utf-8")
    print(f"Scored and saved {len(df):,} products to:\n  {SCORED_CSV}")

    print("\nNutri-Score distribution:")
    print(df["ns_letter"].value_counts().sort_index().to_string())

    print("\nBy product type:")
    print(df.groupby("product_type")["ns_letter"].value_counts()
            .unstack(fill_value=0)
            .reindex(columns=["A","B","C","D","E"])
            .to_string())


if __name__ == "__main__":
    run()
