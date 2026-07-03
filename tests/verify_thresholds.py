"""
verify_thresholds.py — threshold-fidelity check against the official workbook.

Re-extracts every General-foods threshold table from data/raw/nutriscore_workbook.xlsx
(the exact cells the row-3 formulas reference) and diffs them against the constants
in src/nutriscore/thresholds.py. GATING: exits 1 on any mismatch.

Requires the workbook (gitignored; fetch from the Belgian FPS mirror — see
memory/README notes) — exits 2 with a clear message if it is missing.
"""
import openpyxl, re
import sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))
from nutriscore import thresholds as T

_WB = os.path.join(ROOT, 'data', 'raw', 'nutriscore_workbook.xlsx')
if not os.path.isfile(_WB):
    print("SKIP/FAIL: workbook missing at data/raw/nutriscore_workbook.xlsx\n"
          "Fetch: https://www.health.belgium.be/sites/default/files/media/files/"
          "2025-10/va_nutri-score_calculation_tool_updated_algorithm.xlsx")
    sys.exit(2)

wb = openpyxl.load_workbook(_WB, data_only=True)
sc = wb['Scenario']
wbf = openpyxl.load_workbook(_WB, data_only=False)
gff = wbf['General foods']

ref_re = re.compile(r'Scenario!\$([A-Z]+)\$(\d+)')
ok = True


def check(label, match):
    global ok
    ok &= bool(match)
    print(f"{label}: {'MATCH' if match else 'MISMATCH  <<<'}")


def refs(cell):
    return ref_re.findall(gff[cell].value)


def vals(rs):
    return [sc[c + r].value for c, r in rs]


def inline_thresholds(cell):
    # numeric comparison constants from an inline IF ladder like X<=335
    nums = re.findall(r'<=(\d+(?:\.\d+)?)', gff[cell].value)
    return [float(x) if '.' in x else int(x) for x in nums]


check("SUGAR   (AA3 -> Scenario!AA)", vals(refs('AA3')) == T.SUGAR_G)
check("SALT    (Z3  -> Scenario!O)",  vals(refs('Z3')) == T.SALT_G)
check("FIBRE   (X3  -> Scenario!C)",  vals(refs('X3')) == T.FIBRE_G)
check("PROTEIN (Y3  -> Scenario!G)",  vals(refs('Y3')) == T.PROTEIN_G)
check("ENERGY  (K3 inline)",          inline_thresholds('K3') == T.ENERGY_KJ)
check("SAT_FAT (M3 inline)",          inline_thresholds('M3') == T.SAT_FAT_G)

# FVL: W3 = IF(H<=40,0,IF(H<=60,1,IF(H<=80,2,5))) — bounds+points must equal FVL_PCT,
# and the fall-through must be 5.
w3 = gff['W3'].value
fvl_pairs = [(float(b) if '.' in b else int(b), int(p))
             for b, p in re.findall(r'H3<=(\d+(?:\.\d+)?),(\d+)', w3)]
check("FVL     (W3 inline)", fvl_pairs == [(b, p) for b, p in T.FVL_PCT] and ',5)' in w3.replace(' ', ''))

# Letter map: AE3 = ... IF(AD3<1,"A",IF(AD3<3,"B",IF(AD3<11,"C",IF(AD3<19,"D","E"))))
ae3 = gff['AE3'].value
letter_pairs = [(int(b), l) for b, l in re.findall(r'AD3<(\d+),"Nutriscore_([A-D])"', ae3)]
check("LETTERS (AE3 inline)", letter_pairs == T.LETTER_BOUNDS and '"Nutriscore_E"' in ae3)

print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
