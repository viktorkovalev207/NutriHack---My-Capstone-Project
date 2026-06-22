"""
Nutri-Score 2023/2024 threshold tables — GENERAL FOODS category.

PROVENANCE — NOT a single number is from a third party.
All values extracted programmatically from the official, 7-country-validated
calculation workbook:

    file : va_nutri-score_calculation_tool_updated_algorithm.xlsx
    src  : https://www.health.belgium.be/en/tools/nutri-score-calculation-tool
           (FPS Public Health, Belgium — validated by FR/BE/DE/ES/LU/NL/CH)
    got  : 2026-06-22, last updated by publisher 2025-10-24

The workbook contains SEVERAL alternative scenarios (Sugar I/Ia/Ib/II,
Protein II/V, ...). The scenario actually wired into the General-foods
"Updated algorithm" was determined by reading the live cell FORMULAS on the
"General foods" sheet (row 3), not by guessing. Each table below names the
exact source cells so any value can be re-checked against the file.

Threshold convention: a list ``T`` maps a nutrient value ``v`` to points
``= sum(1 for t in T if v > t)``. I.e. points = how many thresholds ``v``
strictly exceeds. This reproduces the nested ``IF(v<=t, p, ...)`` ladders
in the workbook exactly (verified: see tests/validate_against_workbook.py).
"""

# --- NEGATIVE components (raise the score = worse) ---------------------------

# Energy (kJ/100g). Source: General foods!K3 (inline ladder, 335 kJ steps).
ENERGY_KJ = [335, 670, 1005, 1340, 1675, 2010, 2345, 2680, 3015, 3350]  # >last -> 10

# Saturated fat (g/100g). Source: General foods!M3 (inline ladder, 1 g steps).
SAT_FAT_G = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # >last -> 10

# Sugar (g/100g). Source: Scenario!AA3,AA5:AA18  ("Sugar scenario Ib").
SUGAR_G = [3.4, 6.8, 10, 14, 17, 20, 24, 27, 31, 34, 37, 41, 44, 48, 51]  # >last -> 15

# Salt (g/100g). Source: Scenario!O3,O5:O23  ("Salt scenario I", 0.2 g steps).
SALT_G = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0,
          2.2, 2.4, 2.6, 2.8, 3.0, 3.2, 3.4, 3.6, 3.8, 4.0]  # >last -> 20

# --- POSITIVE components (lower the score = better) --------------------------

# Fibre (g/100g, AOAC). Source: Scenario!C3,C5:C8  ("Fibre scenario II").
FIBRE_G = [3.0, 4.1, 5.2, 6.3, 7.4]  # >last -> 5

# Protein (g/100g). Source: Scenario!G3,G5:G10  ("Protein scenario II").
PROTEIN_G = [2.4, 4.8, 7.2, 9.6, 12, 14, 17]  # >last -> 7

# Fruit/Veg/Legumes (%). Source: General foods!W3 (inline; uses column H = FVL%,
# NOT column G which includes oils). Non-linear jump 0,1,2,5 -> handled in engine.
FVL_PCT = [(40, 0), (60, 1), (80, 2)]  # else -> 5

# --- Letter mapping. Source: General foods!AE3 ------------------------------
# score < 1 -> A, < 3 -> B, < 11 -> C, < 19 -> D, else E
LETTER_BOUNDS = [(1, "A"), (3, "B"), (11, "C"), (19, "D")]  # else "E"
