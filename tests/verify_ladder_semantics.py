import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))
from nutriscore import thresholds as T

# Replicate the workbook IF-ladder for sugar exactly using the Scenario AA cells
# in the SAME order the formula references them (AA3, AA5, AA6, ... AA18),
# then else->15.
sugar_bounds = [3.4, 6.8, 10, 14, 17, 20, 24, 27, 31, 34, 37, 41, 44, 48, 51]

def workbook_sugar(v):
    # nested IF(C<=b0,0,IF(C<=b1,1,...,15))
    for i, b in enumerate(sugar_bounds):
        if v <= b:
            return i
    return 15

def py_points(v, table):
    return sum(1 for t in table if v > t)

# test across fine grid including boundary values and the duplicated first boundary
import numpy as np
fails = []
for v in [x/10 for x in range(0, 700)]:
    a = workbook_sugar(v)
    b = py_points(v, T.SUGAR_G)
    if a != b:
        fails.append((v, a, b))
print("SUGAR ladder mismatches:", len(fails), fails[:10])

# Salt
salt_bounds = T.SALT_G
def workbook_salt(v):
    for i, b in enumerate(salt_bounds):
        if v <= b:
            return i
    return 20
fails = []
for v in [x/100 for x in range(0, 500)]:
    a = workbook_salt(v); b = py_points(v, T.SALT_G)
    if a != b: fails.append((v,a,b))
print("SALT ladder mismatches:", len(fails), fails[:10])

# Fibre
def workbook_fibre(v):
    for i,b in enumerate(T.FIBRE_G):
        if v <= b: return i
    return 5
fails=[]
for v in [x/100 for x in range(0,1000)]:
    a=workbook_fibre(v); b=py_points(v,T.FIBRE_G)
    if a!=b: fails.append((v,a,b))
print("FIBRE ladder mismatches:", len(fails), fails[:10])

# Protein
def workbook_prot(v):
    for i,b in enumerate(T.PROTEIN_G):
        if v <= b: return i
    return 7
fails=[]
for v in [x/100 for x in range(0,2500)]:
    a=workbook_prot(v); b=py_points(v,T.PROTEIN_G)
    if a!=b: fails.append((v,a,b))
print("PROTEIN ladder mismatches:", len(fails), fails[:10])

# Energy
def workbook_energy(v):
    for i,b in enumerate(T.ENERGY_KJ):
        if v <= b: return i
    return 10
fails=[]
for v in range(0,4000,7):
    a=workbook_energy(v); b=py_points(v,T.ENERGY_KJ)
    if a!=b: fails.append((v,a,b))
print("ENERGY ladder mismatches:", len(fails), fails[:10])

# Critical boundary test: at exactly v == boundary, workbook gives lower band (v<=b),
# python: v > t is False so doesn't count -> same band. Check v slightly above.
print()
print("Boundary semantics spot check (sugar=3.4):")
print("  workbook:", workbook_sugar(3.4), "py:", py_points(3.4, T.SUGAR_G), "(should be 0)")
print("Boundary semantics spot check (sugar=3.41):")
print("  workbook:", workbook_sugar(3.41), "py:", py_points(3.41, T.SUGAR_G), "(should be 1)")
