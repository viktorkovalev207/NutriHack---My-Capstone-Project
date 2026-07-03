"""
nutrihack_tableau_export.py
============================
Stage 4 — Tableau Export with What-If Simulation
NutriHack Capstone · Viktor Kovalev · 2026

Builds the final CSV for Tableau that includes:
  - Base scored data
  - Pre-computed What-If scenario columns (Simulator)

Why pre-compute in Python and not in Tableau?
  Tableau Calculated Fields can replicate the ladder logic, but it would require
  15+ nested IFs per nutrient. Pre-computing here keeps Tableau clean and fast,
  and demonstrates the Simulator component of the architecture.

The 6 What-If scenarios (per product):
  A) sugar   -5 g/100g   (e.g. reformulation with sweetener)
  B) sugar   -10 g/100g  (stronger reformulation)
  C) protein +5 g/100g   (protein enrichment)
  D) protein +10 g/100g  (heavy protein enrichment)
  E) salt    -0.3 g/100g (sodium reduction)
  F) fibre   +3 g/100g   (fibre fortification)

Output:
  visualizations/nutriscore_tableau.csv
"""

import sys
import pandas as pd
from pathlib import Path

ROOT        = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nutriscore import simulate

SCORED_CSV  = ROOT / "data"          / "clean" / "products_scored.csv"
TABLEAU_CSV = ROOT / "visualizations" / "nutriscore_tableau.csv"

SCENARIOS = {
    "sim_sugar_minus5":   {"sugar_g":   -5.0},
    "sim_sugar_minus10":  {"sugar_g":  -10.0},
    "sim_protein_plus5":  {"protein_g": +5.0},
    "sim_protein_plus10": {"protein_g": +10.0},
    "sim_salt_minus03":   {"salt_g":    -0.3},
    "sim_fibre_plus3":    {"fibre_g":   +3.0},
}


def build_base(row):
    return {
        "energy_kj":  float(row["energy_kj"]),
        "sugar_g":    float(row["sugars_g"]),
        "sat_fat_g":  float(row["sat_fat_g"]),
        "salt_g":     float(row["salt_g"]),
        "fibre_g":    float(row["fibre_g"]),
        "protein_g":  float(row["proteins_g"]),
        "fvl_percent":float(row["fvl_pct"]),
    }


def add_simulations(df):
    for col_prefix, changes in SCENARIOS.items():
        scores  = []
        letters = []
        deltas  = []
        improved = []
        for _, row in df.iterrows():
            # Skip products the engine did not score (beverages -> REVIEW_REQUIRED):
            # running solid-food what-ifs on them would emit misleading grades.
            if pd.isna(row.get("ns_score")):
                scores.append(None); letters.append(None)
                deltas.append(None); improved.append(None)
                continue
            base = build_base(row)
            r = simulate(base, changes)
            scores.append(r.score_after)
            letters.append(r.letter_after)
            deltas.append(r.score_delta)
            improved.append(r.grade_changed and r.score_delta < 0)
        df[f"{col_prefix}_score"]    = scores
        df[f"{col_prefix}_letter"]   = letters
        df[f"{col_prefix}_delta"]    = deltas
        df[f"{col_prefix}_improved"] = improved
    return df


def tableau_cols(df):
    """Select and rename columns for clean Tableau experience."""
    keep = [
        # Identifiers
        "barcode", "product_name", "brands", "product_type",
        # Raw nutrients (for Tableau parameter sliders)
        "energy_kj", "sugars_g", "sat_fat_g", "salt_g",
        "fibre_g", "proteins_g", "fat_g", "carbs_g", "fvl_pct",
        # Scored result
        "ns_score", "ns_letter",
        "ns_negative_pts", "ns_positive_pts",
        "ns_energy_pts", "ns_sugar_pts", "ns_sat_fat_pts", "ns_salt_pts",
        "ns_protein_pts", "ns_fibre_pts", "ns_protein_counted",
        # What-If simulations
        "sim_sugar_minus5_score",    "sim_sugar_minus5_letter",
        "sim_sugar_minus5_delta",    "sim_sugar_minus5_improved",
        "sim_sugar_minus10_score",   "sim_sugar_minus10_letter",
        "sim_sugar_minus10_delta",   "sim_sugar_minus10_improved",
        "sim_protein_plus5_score",   "sim_protein_plus5_letter",
        "sim_protein_plus5_delta",   "sim_protein_plus5_improved",
        "sim_protein_plus10_score",  "sim_protein_plus10_letter",
        "sim_protein_plus10_delta",  "sim_protein_plus10_improved",
        "sim_salt_minus03_score",    "sim_salt_minus03_letter",
        "sim_salt_minus03_delta",    "sim_salt_minus03_improved",
        "sim_fibre_plus3_score",     "sim_fibre_plus3_letter",
        "sim_fibre_plus3_delta",     "sim_fibre_plus3_improved",
        # Data provenance (honesty layer: which scores rest on guessed values)
        "data_basis", "imputed_any", "fvl_assumed_zero",
        "imp_energy_kj", "imp_sugars_g", "imp_sat_fat_g",
        "imp_salt_g", "imp_fibre_g", "imp_proteins_g",
        # Meta
        "countries",
    ]
    existing = [c for c in keep if c in df.columns]
    return df[existing]


def run():
    TABLEAU_CSV.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(SCORED_CSV, dtype={"barcode": str})
    print(f"Loaded {len(df):,} scored products")

    print(f"Computing What-If scenarios (6 x {len(df):,} rows) ...")
    df = add_simulations(df)

    df_out = tableau_cols(df)
    df_out.to_csv(TABLEAU_CSV, index=False, encoding="utf-8")
    # The live Tableau workbook reads the XLSX twin (Tableau's CSV parser mangled
    # this file's headers). Emit it here so CSV and XLSX can never diverge.
    xlsx = TABLEAU_CSV.parent / "nutriscore_tableau_new.xlsx"
    df_out.to_excel(xlsx, index=False, sheet_name="data")
    print(f"Tableau export written to:\n  {TABLEAU_CSV}\n  {xlsx}")

    # Quick Simulator insight
    print("\n=== SIMULATOR INSIGHTS ===")
    for prefix, changes in SCENARIOS.items():
        improved_count = df[f"{prefix}_improved"].sum()
        grade_up_pct   = improved_count / len(df) * 100
        change_desc    = ", ".join(f"{k}={v:+g}" for k, v in changes.items())
        print(f"  {change_desc:25s} -> {improved_count:>4} products improve grade  ({grade_up_pct:.1f}%)")


if __name__ == "__main__":
    run()
