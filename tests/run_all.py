"""
run_all.py — one command, every gate.

Runs the full validation battery as subprocesses and fails (exit 1) if ANY
gate fails. Data-dependent suites are skipped with a warning when their inputs
(gitignored workbook / generated CSVs) are absent, so a fresh clone still gets
a meaningful, gating run of the pure-Python tests.

Usage:
    python tests/run_all.py          # everything except the slow oracle
    python tests/run_all.py --full   # includes oracle_validation (~1-2 min)
"""
import subprocess, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WB = os.path.join(ROOT, "data", "raw", "nutriscore_workbook.xlsx")
SCORED = os.path.join(ROOT, "data", "clean", "products_scored.csv")

# (script, needs, description)
SUITES = [
    ("tests/test_engine.py",             None,   "engine contracts (simulate, negatives, float)"),
    ("tests/test_boundaries.py",         None,   "letter bounds, protein-cap flip, FVL ladder"),
    ("tests/test_classification.py",     None,   "classification + beverage gate"),
    ("tests/test_clean_pipeline.py",     None,   "cleaning stages (energy guard, imputation)"),
    ("tests/verify_ladder_semantics.py", None,   "ladder semantics sweep"),
    ("src/nutriscore/classification.py", None,   "classification self-test (gating)"),
    ("tests/verify_thresholds.py",       WB,     "threshold fidelity vs workbook"),
    ("tests/validate_against_workbook.py", WB,   "3 official workbook examples"),
]
if "--full" in sys.argv:
    SUITES.append(("tests/oracle_validation.py", WB, "independent oracle, 620 grid cases"))

env = dict(os.environ, PYTHONIOENCODING="utf-8")
failed, skipped = [], []
for script, needs, desc in SUITES:
    if needs and not os.path.isfile(needs):
        skipped.append((script, os.path.relpath(needs, ROOT)))
        print(f"SKIP  {script:42} (missing {os.path.relpath(needs, ROOT)})")
        continue
    r = subprocess.run([sys.executable, os.path.join(ROOT, script)],
                       capture_output=True, text=True, env=env, cwd=ROOT)
    status = "PASS" if r.returncode == 0 else "FAIL"
    print(f"{status}  {script:42} {desc}")
    if r.returncode != 0:
        failed.append(script)
        tail = (r.stdout + r.stderr).strip().splitlines()[-12:]
        print("      " + "\n      ".join(tail))

print(f"\n{'='*60}")
print(f"suites: {len(SUITES)}  passed: {len(SUITES)-len(failed)-len(skipped)}  "
      f"failed: {len(failed)}  skipped: {len(skipped)}")
if skipped:
    print("skipped suites need the official workbook — fetch from the Belgian "
          "FPS mirror (see requirements/README).")
print("RESULT:", "PASS" if not failed else "FAIL")
sys.exit(0 if not failed else 1)
