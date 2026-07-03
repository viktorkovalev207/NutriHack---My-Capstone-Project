"""
test_classification.py — hard-asserting tests for the classification layer and
the beverage REVIEW_REQUIRED gate.

Pins the two liability regressions:
  1. dairy-without-state (casein/milk powder) must NEVER route to beverages
  2. word-boundary matching: "cola" inside "chocolate" must NOT make a bar a
     beverage (the substring bug once mis-routed ~1,400 products)
plus the scoring gate: a beverage must never receive an A-E letter from the
general-foods engine.

Run:  python tests/test_classification.py   (or pytest)
"""
import sys, os

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from nutriscore import classify_product


def test_solid_products_are_general_foods():
    for name in ("Whey Vanilla", "Crunchy Protein Bar"):
        r = classify_product(product_name=name, physical_state="solid")
        assert r.category == "general_foods" and r.sweetener_malus_applies is False


def test_dairy_without_state_regression():
    """The original Haftungsfall: dairy flag alone must not imply 'beverage'."""
    for name in ("Micellar Casein", "Skim Milk Powder"):
        r = classify_product(product_name=name, is_dairy_based=True)
        assert r.category == "general_foods", (name, r.category)
        assert r.sweetener_malus_applies is False
        assert r.needs_review is True   # state unknown -> flagged, not guessed


def test_chocolate_is_not_a_beverage():
    """Word-boundary regression: 'cola' inside 'chocolate' must not match."""
    for name in ("Chocolate Protein Powder", "Schokolade Riegel",
                 "Chocolat protéiné", "Barretta al cioccolato"):
        r = classify_product(product_name=name)
        assert r.category == "general_foods", (name, r.category)


def test_real_drinks_are_beverages():
    assert classify_product(product_name="Cola Zero").category == "beverages"
    r = classify_product(product_name="Protein Drink Choco")
    assert r.category == "beverages" and r.needs_review is True
    r = classify_product(product_name="Vegan Protein Shake RTD",
                         physical_state="liquid")
    assert r.category == "beverages" and r.sweetener_malus_applies is True
    assert r.needs_review is False   # explicit liquid -> no guess involved


def test_soup_exception_and_water():
    r = classify_product(product_name="Protein Soup Tomato", physical_state="liquid")
    assert r.category == "general_foods"
    r = classify_product(product_name="Mineral Water Still", physical_state="liquid")
    assert r.category == "beverages" and r.is_water is True


def test_beverage_rows_get_no_letter():
    """The score_row gate: beverages -> REVIEW_REQUIRED, all numerics None."""
    from nutrihack_score import score_row, NS_NUMERIC_COLS
    solid = dict(product_name="Whey Vanilla", categories="protein-powders",
                 energy_kj=1600, sugars_g=5, sat_fat_g=1, salt_g=0.5,
                 fibre_g=2, proteins_g=75, fvl_pct=0)
    out = score_row(solid)
    assert out["ns_letter"] in "ABCDE" and out["ns_score"] is not None

    liquid = dict(solid, product_name="Vegan Protein Drink RTD",
                  categories="protein-drinks")
    out = score_row(liquid)
    assert out["ns_letter"] == "REVIEW_REQUIRED"
    assert all(out[c] is None for c in NS_NUMERIC_COLS), "numerics must be None"


def test_dataset_invariant_no_graded_beverages():
    """On the shipped dataset: no beverage row carries an A-E letter.
    Skipped silently when the (gitignored) CSV is absent (fresh clone)."""
    csv = os.path.join(ROOT, "data", "clean", "products_scored.csv")
    if not os.path.isfile(csv):
        print("    (dataset invariant skipped — products_scored.csv absent)")
        return
    import pandas as pd
    df = pd.read_csv(csv, low_memory=False)
    bev = df[df["ns_category"] == "beverages"]
    assert set(bev["ns_letter"].unique()) <= {"REVIEW_REQUIRED"}, \
        bev["ns_letter"].value_counts().to_dict()
    assert bev["ns_score"].isna().all()


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted({k: v for k, v in globals().items()
                            if k.startswith("test_") and callable(v)}.items()):
        try:
            fn()
            print(f"  OK    {name}")
        except Exception as e:
            fails += 1
            print(f"  FAIL  {name}: {e}")
    print("\nRESULT:", "PASS" if fails == 0 else f"FAIL ({fails})")
    sys.exit(0 if fails == 0 else 1)
