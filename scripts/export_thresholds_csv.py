"""
Emit the auditable threshold table (Anweisung 2 deliverable).

One row per (component, points) step, each carrying the exact SOURCE CELL in the
official workbook so any value can be re-checked against the primary source.
Output: data/processed/general_foods_thresholds.csv
"""
import os, csv, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from nutriscore import thresholds as T

WB = "va_nutri-score_calculation_tool_updated_algorithm.xlsx (Belgium FPS Public Health, 7-country validated)"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "processed",
                   "general_foods_thresholds.csv")

rows = []

def add(component, unit, table, max_points, cells, direction):
    # points p applies for value <= table[p-1] cutoff; here we record the upper
    # bound of each band. Band p covers (prev, cutoff]; top band is "> last".
    for p in range(0, max_points + 1):
        if p < len(table):
            upper = table[p]
            bound = f"<= {upper}"
        else:
            upper = ""
            bound = f"> {table[-1]}"
        rows.append(dict(component=component, points=p, upper_bound=bound,
                         unit=unit, direction=direction, source_cells=cells,
                         workbook=WB))

# negative (more = worse)
add("energy", "kJ/100g", T.ENERGY_KJ, 10, "General foods!K3 (inline ladder)", "negative")
add("saturated_fat", "g/100g", T.SAT_FAT_G, 10, "General foods!M3 (inline ladder)", "negative")
add("sugar", "g/100g", T.SUGAR_G, 15, "Scenario!AA3,AA5:AA18 (Sugar scenario Ib)", "negative")
add("salt", "g/100g", T.SALT_G, 20, "Scenario!O3,O5:O23 (Salt scenario I)", "negative")
# positive (more = better)
add("fibre", "g/100g", T.FIBRE_G, 5, "Scenario!C3,C5:C8 (Fibre scenario II)", "positive")
add("protein", "g/100g", T.PROTEIN_G, 7, "Scenario!G3,G5:G10 (Protein scenario II)", "positive")
# FVL is a 3-step non-linear band
for upper, p in T.FVL_PCT:
    rows.append(dict(component="fvl_percent", points=p, upper_bound=f"<= {upper}",
                     unit="%", direction="positive",
                     source_cells="General foods!W3 (inline; uses column H)", workbook=WB))
rows.append(dict(component="fvl_percent", points=5, upper_bound="> 80", unit="%",
                 direction="positive", source_cells="General foods!W3 (inline; uses column H)",
                 workbook=WB))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["component", "points", "upper_bound",
                                      "unit", "direction", "source_cells", "workbook"])
    w.writeheader()
    w.writerows(rows)

print(f"wrote {len(rows)} threshold rows -> {os.path.relpath(OUT)}")
