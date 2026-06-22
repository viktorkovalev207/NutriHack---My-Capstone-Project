import openpyxl, re
import sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))
from nutriscore import thresholds as T

_WB = os.path.join(ROOT, 'data', 'raw', 'nutriscore_workbook.xlsx')
wb = openpyxl.load_workbook(_WB, data_only=True)
sc = wb['Scenario']
wbf = openpyxl.load_workbook(_WB, data_only=False)
gff = wbf['General foods']

ref_re = re.compile(r'Scenario!\$([A-Z]+)\$(\d+)')

def refs(cell):
    return ref_re.findall(gff[cell].value)

def vals(rs):
    return [sc[c + r].value for c, r in rs]

def inline_thresholds(cell):
    # extract numeric comparison constants from inline IF ladder like X<=335
    f = gff[cell].value
    nums = re.findall(r'<=(\d+(?:\.\d+)?)', f)
    return [float(x) if '.' in x else int(x) for x in nums]

print("=== SUGAR (General foods!AA3 -> Scenario AA) ===")
sr = refs('AA3'); sv = vals(sr)
print("workbook order refs:", sr)
print("workbook band boundaries:", sv)
print("thresholds.py SUGAR_G   :", T.SUGAR_G)
print("MATCH:", sv == T.SUGAR_G)
print()

print("=== SALT (General foods!Z3 -> Scenario O) ===")
zr = refs('Z3'); zv = vals(zr)
print("workbook band boundaries:", zv)
print("thresholds.py SALT_G    :", T.SALT_G)
print("MATCH:", zv == T.SALT_G)
print()

print("=== FIBRE (General foods!X3 -> Scenario C) ===")
xr = refs('X3'); xv = vals(xr)
print("workbook band boundaries:", xv)
print("thresholds.py FIBRE_G   :", T.FIBRE_G)
print("MATCH:", xv == T.FIBRE_G)
print()

print("=== PROTEIN (General foods!Y3 -> Scenario G) ===")
yr = refs('Y3'); yv = vals(yr)
print("workbook band boundaries:", yv)
print("thresholds.py PROTEIN_G :", T.PROTEIN_G)
print("MATCH:", yv == T.PROTEIN_G)
print()

print("=== ENERGY (General foods!K3 inline) ===")
ek = inline_thresholds('K3')
print("workbook:", ek)
print("thresholds.py ENERGY_KJ:", T.ENERGY_KJ)
print("MATCH:", ek == T.ENERGY_KJ)
print()

print("=== SAT FAT (General foods!M3 inline) ===")
mk = inline_thresholds('M3')
print("workbook:", mk)
print("thresholds.py SAT_FAT_G:", T.SAT_FAT_G)
print("MATCH:", mk == T.SAT_FAT_G)
print()

print("=== FVL (General foods!W3 inline; uses column H) ===")
print("W3 formula:", gff['W3'].value)
print("thresholds.py FVL_PCT:", T.FVL_PCT)
print()

print("=== LETTER mapping (Updated algorithm AE3) ===")
print("AE3 formula:", gff['AE3'].value)
print("thresholds.py LETTER_BOUNDS:", T.LETTER_BOUNDS)
