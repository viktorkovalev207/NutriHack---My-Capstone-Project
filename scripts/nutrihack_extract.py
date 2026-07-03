"""
nutrihack_extract.py
====================
Stage 1 — Data Extraction
NutriHack Capstone · Viktor Kovalev · 2026

Pulls protein powders and protein bars from the Open Food Facts API.
Output: data/raw/products_raw.csv

Usage:
    python scripts/nutrihack_extract.py

Features:
- Pagination through all available results
- Retry logic with exponential back-off (max 3 attempts)
- Field filtering to only the columns we need
- Barcode-based deduplication (OFF has duplicates across page boundaries)
"""

import csv
import json
import os
import time
import requests
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CATEGORIES = {
    "protein-powders": "protein_powder",
    "protein-bars":    "protein_bar",
}

# Only these fields per product (per 100g)
FIELDS = [
    "code", "product_name", "brands", "categories",
    "nutriments.energy-kj_100g",
    "nutriments.sugars_100g",
    "nutriments.saturated-fat_100g",
    "nutriments.salt_100g",
    "nutriments.fiber_100g",
    "nutriments.proteins_100g",
    "nutriments.fat_100g",
    "nutriments.carbohydrates_100g",
    "nutriments.fruits-vegetables-legumes-estimate-from-ingredients_100g",
    "nutriscore_grade",
    "nutriscore_score",
    "countries_tags",
    "quantity",
]

PAGE_SIZE   = 100   # OFF API caps at ~100 in practice
MAX_RETRIES = 5
RETRY_DELAY = 3     # seconds, doubles on each retry
OUT_PATH    = Path(__file__).parent.parent / "data" / "raw" / "products_raw.csv"

# Flat column names for the CSV (maps API path -> column header)
COL_MAP = {
    "code":                    "barcode",
    "product_name":            "product_name",
    "brands":                  "brands",
    "categories":              "categories",
    "nutriments.energy-kj_100g":                                   "energy_kj",
    "nutriments.sugars_100g":                                       "sugars_g",
    "nutriments.saturated-fat_100g":                               "sat_fat_g",
    "nutriments.salt_100g":                                        "salt_g",
    "nutriments.fiber_100g":                                       "fibre_g",
    "nutriments.proteins_100g":                                    "proteins_g",
    "nutriments.fat_100g":                                         "fat_g",
    "nutriments.carbohydrates_100g":                               "carbs_g",
    "nutriments.fruits-vegetables-legumes-estimate-from-ingredients_100g": "fvl_pct",
    "nutriscore_grade":        "off_nutriscore_grade",
    "nutriscore_score":        "off_nutriscore_score",
    "countries_tags":          "countries",
    "quantity":                "quantity",
}


def _get_field(product: dict, path: str):
    """Extract a (possibly nested) field from a product dict."""
    if "." in path:
        top, rest = path.split(".", 1)
        return _get_field(product.get(top, {}), rest)
    val = product.get(path)
    if isinstance(val, list):
        return ", ".join(str(x) for x in val)
    return val


def _fetch_page(category: str, page: int, session: requests.Session) -> dict:
    url = (
        f"https://world.openfoodfacts.org/cgi/search.pl"
        f"?action=process"
        f"&tagtype_0=categories"
        f"&tag_contains_0=contains"
        f"&tag_0={category}"
        f"&json=1"
        f"&page={page}"
        f"&page_size={PAGE_SIZE}"
        f"&fields={','.join(FIELDS)}"
    )
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, json.JSONDecodeError) as exc:
            wait = RETRY_DELAY * (2 ** (attempt - 1))
            print(f"    Retry {attempt}/{MAX_RETRIES} after {wait}s ({exc.__class__.__name__})")
            time.sleep(wait)
    return None  # signal caller to skip this page


def extract():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    seen_barcodes = set()
    rows = []

    session = requests.Session()
    session.headers["User-Agent"] = "NutriHack-Capstone/1.0 (viktor.kovalev96@gmail.com)"

    for category_slug, product_type in CATEGORIES.items():
        print(f"\n--- Fetching category: {category_slug} ---")
        page = 1
        consecutive_failures = 0
        while True:
            print(f"  page {page} ...", end=" ", flush=True)
            data = _fetch_page(category_slug, page, session)
            if data is None:
                consecutive_failures += 1
                print(f"SKIPPED (all retries failed, {consecutive_failures}/3)")
                if consecutive_failures >= 3:
                    # API is down, not a transient page glitch — a bare
                    # `page += 1; continue` would loop forever here.
                    print(f"  Aborting category '{category_slug}' after 3 "
                          f"consecutive failed pages.")
                    break
                page += 1
                time.sleep(5)
                continue
            consecutive_failures = 0
            products = data.get("products", [])
            print(f"{len(products)} products")

            if not products:
                break  # no more pages

            for p in products:
                barcode = str(p.get("code", "")).strip()
                if not barcode or barcode in seen_barcodes:
                    continue
                seen_barcodes.add(barcode)

                row = {"product_type": product_type}
                for api_key, col_name in COL_MAP.items():
                    row[col_name] = _get_field(p, api_key)
                rows.append(row)

            # OFF returns total count; stop when no more products
            if len(products) < PAGE_SIZE:
                break   # last partial page
            total = data.get("count", 0)
            if total and page * PAGE_SIZE >= total:
                break
            page += 1
            time.sleep(1.0)  # polite rate limit

    # Write CSV
    if not rows:
        print("\nNo products fetched. Check network or category names.")
        return

    fieldnames = ["product_type"] + list(COL_MAP.values())
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. {len(rows)} unique products written to:\n  {OUT_PATH}")


if __name__ == "__main__":
    extract()
