"""
export_testcases_tableau.py
===========================
Builds a SEPARATE, Tableau-ready CSV containing only our curated test cases:
  - 6 real-world Gustavo Gusto pizzas (general-foods engine sanity cases)
  - 3 banger demo targets (Lifefood x2, MyProtein) — all real, verified macros

Same column schema as visualizations/nutriscore_tableau.csv, so it imports
identically — but isolated, so the demo can spotlight these without scrolling
through ~10k market rows. A `case_group` column lets Tableau filter pizza_test
vs demo_target.

Output: visualizations/nutriscore_tableau_testcases.csv
        + the XLSX twin the live Tableau workbook actually reads
"""
import sys
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from nutrihack_score import score_row
from nutrihack_tableau_export import add_simulations, tableau_cols

PIZZA_CSV = ROOT / "gustavo_pizza_tests.csv"
OUT_CSV = ROOT / "visualizations" / "nutriscore_tableau_testcases.csv"

# Clean-schema columns the scoring/export pipeline expects.
CLEAN_COLS = ["product_type", "barcode", "product_name", "brands", "categories",
              "energy_kj", "sugars_g", "sat_fat_g", "salt_g", "fibre_g",
              "proteins_g", "fat_g", "carbs_g", "fvl_pct", "countries"]


def load_pizzas():
    p = pd.read_csv(PIZZA_CSV)
    rows = []
    for i, r in p.iterrows():
        rows.append(dict(
            product_type="pizza_test", barcode=f"TEST-PIZZA-{i+1:02d}",
            product_name=r["product_name"], brands="Gustavo Gusto",
            categories="pizzas",
            energy_kj=r["energy_100g"], sugars_g=r["sugars_100g"],
            sat_fat_g=r["saturated_fat_100g"], salt_g=r["salt_100g"],
            fibre_g=r["fiber_100g"], proteins_g=r["proteins_100g"],
            fat_g="", carbs_g="", fvl_pct=0.0, countries="test",
        ))
    return rows


def demo_targets():
    # exact macros confirmed against the scored market dataset
    return [
        dict(product_type="demo_target", barcode="TEST-DEMO-01",
             product_name="Life Bar Oat Snack", brands="Lifefood",
             categories="protein-bars", energy_kj=1942, sugars_g=19.0,
             sat_fat_g=4.0, salt_g=0.52, fibre_g=6.0, proteins_g=17.0,
             fat_g="", carbs_g="", fvl_pct=0.0, countries="test"),
        dict(product_type="demo_target", barcode="TEST-DEMO-02",
             product_name="Life Bar High Protein", brands="Lifefood",
             categories="protein-bars", energy_kj=1366, sugars_g=43.0,
             sat_fat_g=1.0, salt_g=0.56, fibre_g=8.2, proteins_g=17.0,
             fat_g="", carbs_g="", fvl_pct=0.0, countries="test"),
        dict(product_type="demo_target", barcode="TEST-DEMO-03",
             product_name="Impact Vegan Protein", brands="MyProtein",
             categories="protein-powders", energy_kj=1446, sugars_g=0.0,
             sat_fat_g=0.9, salt_g=3.0, fibre_g=12.0, proteins_g=66.0,
             fat_g="", carbs_g="", fvl_pct=0.0, countries="test"),
    ]


def run():
    df = pd.DataFrame(load_pizzas() + demo_targets(), columns=CLEAN_COLS)
    print(f"Test cases: {len(df)} ({(df.product_type=='pizza_test').sum()} pizzas, "
          f"{(df.product_type=='demo_target').sum()} demo targets)")

    # Provenance: every test-case macro is a verified label value — nothing is
    # imputed. Set the flags explicitly so the schema matches the market export.
    for col in ("energy_kj", "sugars_g", "sat_fat_g", "salt_g", "fibre_g", "proteins_g"):
        df[f"imp_{col}"] = False
    df["imputed_any"] = False
    df["fvl_assumed_zero"] = False
    df["data_basis"] = "measured"

    # 1) score (adds ns_* columns)
    score_cols = df.apply(score_row, axis=1, result_type="expand")
    df = pd.concat([df, score_cols], axis=1)
    # 2) what-if scenarios (adds sim_* columns)
    df = add_simulations(df)
    # 3) select Tableau schema, keep a filter column for isolated views
    out = tableau_cols(df).copy()
    out.insert(0, "case_group", df["product_type"].values)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False, encoding="utf-8")
    # XLSX twin: the live Tableau workbook reads this file (Tableau's CSV parser
    # mangled the numeric headers of this CSV). Keep both in sync automatically.
    xlsx = OUT_CSV.parent / "nutriscore_tableau_testcases_new.xlsx"
    out.to_excel(xlsx, index=False, sheet_name="data")
    print(f"Wrote {len(out)} rows -> {OUT_CSV.relative_to(ROOT)} + {xlsx.name}")

    print("\n=== Test-case scores (base -> best single lever) ===")
    for _, r in out.iterrows():
        sims = {"sugar-5": r["sim_sugar_minus5_letter"], "sugar-10": r["sim_sugar_minus10_letter"],
                "salt-0.3": r["sim_salt_minus03_letter"], "fibre+3": r["sim_fibre_plus3_letter"],
                "prot+5": r["sim_protein_plus5_letter"], "prot+10": r["sim_protein_plus10_letter"]}
        best = min(sims.items(), key=lambda kv: "ABCDE".index(kv[1]))
        print(f"  {r['product_name'][:34]:34} [{r['case_group']:11}] "
              f"base {r['ns_letter']}  ->  best {best[1]} via {best[0]}")


if __name__ == "__main__":
    run()
