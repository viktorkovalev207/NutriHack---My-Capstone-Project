"""
verify_ladder_semantics.py — brute-force the point functions against a literal
re-implementation of the workbook IF-ladders over fine value grids, including
exact boundary values. Pure Python (no workbook/xlsx needed) — runs on a fresh
clone. GATING: exits 1 on any mismatch.
"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))
from nutriscore import thresholds as T
from nutriscore.engine import _ladder, _fvl_points

ok = True


def py_points(v, table):
    return _ladder(v, table)


def workbook_ladder(v, bounds):
    # nested IF(v<=b0,0,IF(v<=b1,1,...,len(bounds)))
    for i, b in enumerate(bounds):
        if v <= b:
            return i
    return len(bounds)


def sweep(name, bounds, values):
    global ok
    fails = [(v, workbook_ladder(v, bounds), py_points(v, bounds))
             for v in values if workbook_ladder(v, bounds) != py_points(v, bounds)]
    ok &= not fails
    print(f"{name:8} ladder mismatches: {len(fails)} {fails[:5]}")


sweep("SUGAR",   T.SUGAR_G,   [x / 10 for x in range(0, 700)])
sweep("SALT",    T.SALT_G,    [x / 100 for x in range(0, 500)])
sweep("FIBRE",   T.FIBRE_G,   [x / 100 for x in range(0, 1000)])
sweep("PROTEIN", T.PROTEIN_G, [x / 100 for x in range(0, 2500)])
sweep("ENERGY",  T.ENERGY_KJ, list(range(0, 4000, 7)))

# FVL: non-linear 0/1/2/5 ladder — sweep incl. exact bounds and epsilon-above.
def workbook_fvl(v):
    if v <= 40: return 0
    if v <= 60: return 1
    if v <= 80: return 2
    return 5

fvl_values = [x / 10 for x in range(0, 1001)] + [40.0001, 60.0001, 80.0001]
fvl_fails = [(v, workbook_fvl(v), _fvl_points(v)) for v in fvl_values
             if workbook_fvl(v) != _fvl_points(v)]
ok &= not fvl_fails
print(f"{'FVL':8} ladder mismatches: {len(fvl_fails)} {fvl_fails[:5]}")

# Letter map: workbook AE3 = <1 A, <3 B, <11 C, <19 D, else E — over all raw scores.
def workbook_letter(score):
    if score < 1: return "A"
    if score < 3: return "B"
    if score < 11: return "C"
    if score < 19: return "D"
    return "E"

def py_letter(score):
    for bound, lt in T.LETTER_BOUNDS:
        if score < bound:
            return lt
    return "E"

letter_fails = [(s, workbook_letter(s), py_letter(s)) for s in range(-20, 45)
                if workbook_letter(s) != py_letter(s)]
ok &= not letter_fails
print(f"{'LETTERS':8} map mismatches:    {len(letter_fails)} {letter_fails[:5]}")

# Boundary spot checks (documentation value)
print("\nspot: sugar 3.4 ->", py_points(3.4, T.SUGAR_G), "(exp 0) | 3.41 ->",
      py_points(3.41, T.SUGAR_G), "(exp 1)")

print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
