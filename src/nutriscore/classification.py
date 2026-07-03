"""
NutriHack — Klassifizierungs-Layer (vorgelagert vor der Scoring-Engine).

ZWECK
-----
Der Nutri-Score-2024-Algorithmus verwendet je nach Produkttyp ZWEI
unterschiedliche Regelwerke (eigene Punkte-Tabellen, eigener Süßstoff-Malus):

  - "general_foods"  -> feste Lebensmittel (Pulver, Riegel, ...)
  - "beverages"      -> TRINKBARE Produkte (Shakes, RTD, Milch- & Pflanzendrinks)

Diese Funktion entscheidet, WELCHES Regelwerk gilt. Die Engine ruft DANACH die
kategoriespezifische Tabelle auf.

      Produkt -> [classify_product] -> Kategorie -> [scoring_engine]

ARCHITEKTUR-REGEL (kritisch, Anweisung 5)
-----------------------------------------
Der physikalische Aggregatzustand (solid/liquid) ist das PRIMÄRE und
entscheidende Signal — nicht ein optionales Beiwerk:

  1. solid   -> IMMER general_foods. dairy/plant-Flags werden IGNORIERT.
  2. liquid  -> beverages (Süßstoff-Malus gilt; nur Wasser kann A erreichen).
  3. unknown -> NICHT raten. Default general_foods, aber needs_review=True.
                Eine eindeutige Getränke-FORM im Namen (z.B. "drink", "RTD")
                darf als beverages vorgeschlagen werden — ebenfalls needs_review.

WARUM dairy/plant ALLEIN NIEMALS nach beverages routen darf
-----------------------------------------------------------
Die Flags `is_dairy_based`/`is_plant_drink` beschreiben die ZUTATENBASIS, nicht
die FORM. Magermilch- und Caseinpulver sind dairy, aber FEST -> general_foods.
Die offizielle Regel ("milk DRINKS, plant DRINKS sind Getränke") bezieht sich
auf trinkbare Produkte; selbst kakaohaltiges Milchpulver wird laut SpF nicht als
Pulver, sondern als zubereitetes Getränk bewertet — das Pulver in der Dose bleibt
fest. Ein früherer Layer setzte dairy==Getränk und klassifizierte Caseinpulver
falsch als beverages (Haftungsfall). Dieser Layer schließt das aus:
Zutatenbasis-Flags wirken NUR in Kombination mit liquid.

QUELLE DER REGELN
-----------------
Die Zuordnungsregeln folgen den offiziellen Nutri-Score-2024-Definitionen
(Santé publique France FAQ / Eurofins-Zusammenfassung). Die numerischen
SCHWELLENWERTE sind NICHT Teil dieses Layers — sie liegen in
nutriscore.thresholds mit Zellbezug zum offiziellen Workbook.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ClassificationResult:
    category: str                  # "general_foods" oder "beverages"
    is_water: bool                 # True nur für reines Wasser (Sonderfall A)
    reason: str                    # auditierbare Begründung
    sweetener_malus_applies: bool  # True nur bei beverages (Reform 2024)
    needs_review: bool = False     # True, wenn Aggregatzustand unbekannt war
                                   # und angenommen werden musste -> manuell prüfen


# Eindeutige Getränke-FORM-Indikatoren (beschreiben die Darreichung, nicht die
# Zutat). Bewusst OHNE mehrdeutige Begriffe wie "milk"/"milch"/"shake", die auch
# in festen Produkten vorkommen ("milk powder", "milk protein", "shake powder").
_LIQUID_FORM_KEYWORDS = (
    "drink", "beverage", "getränk", "getraenk", "rtd",
    "ready-to-drink", "ready to drink", "smoothie", "juice", "saft",
    "lemonade", "limonade", "soda", "cola", "nectar",
    "plant-based drink", "pflanzendrink", "pflanzlicher drink",
)

# Suppen/Gazpacho bleiben general_foods, obwohl flüssig (offizielle Ausnahme).
_GENERAL_FOOD_EXCEPTIONS = (
    "soup", "suppe", "gazpacho", "broth", "brühe", "bruehe",
)

# Reines Wasser -> einziger Getränke-Sonderfall, der A erreichen kann.
_WATER_KEYWORDS = (
    "mineral water", "spring water", "mineralwasser", "quellwasser",
    "still water", "sparkling water", "tafelwasser",
)


def _matches_any(text: str, keywords) -> bool:
    return any(k in text for k in keywords)


def _matches_word(text: str, keywords) -> bool:
    """Whole-word keyword match (no \\w on either side of the keyword).

    Used for the liquid-form keywords, which include short tokens like "cola"
    and "soda". A plain substring test mis-fires badly here: "cola" is inside
    "choCOLAte"/"chocolat"/"cioccolate", so substring matching routed ~1,400
    chocolate protein bars/powders to 'beverages'. Word boundaries fix that
    while still matching the keyword as a standalone word.
    """
    return any(re.search(rf"(?<!\w){re.escape(k)}(?!\w)", text) for k in keywords)


def classify_product(
    product_name: Optional[str] = None,
    category: Optional[str] = None,
    physical_state: Optional[str] = None,
    is_dairy_based: bool = False,
    is_plant_drink: bool = False,
    *,
    force_scope1_general_foods: bool = True,  # akzeptiert für Rückwärtskompatibilität
) -> ClassificationResult:
    """
    Ordnet ein Produkt dem Regelwerk "general_foods" oder "beverages" zu.

    physical_state ("solid"/"liquid") ist das entscheidende Signal. Fehlt es,
    wird NICHT geraten: Default general_foods mit needs_review=True (außer eine
    eindeutige Getränke-Form steckt im Namen). is_dairy_based/is_plant_drink
    wirken ausschließlich zusammen mit liquid — eine dairy/plant-Flag allein
    macht aus einem festen Pulver KEIN Getränk.
    """
    name = (product_name or "").lower().strip()
    cat = (category or "").lower().strip()
    state = (physical_state or "").lower().strip()
    haystack = f"{name} {cat}"

    # 1) Harte Ausnahme: Suppe/Gazpacho -> general_foods, egal wie flüssig.
    if _matches_any(haystack, _GENERAL_FOOD_EXCEPTIONS):
        return ClassificationResult(
            category="general_foods", is_water=False,
            reason="Ausnahmeregel: Suppe/Gazpacho zählt als general_foods.",
            sweetener_malus_applies=False,
        )

    # 2) PRIMÄR: physikalischer Zustand.
    if state == "solid":
        # dairy/plant werden bewusst ignoriert: festes Milchpulver = general_foods.
        return ClassificationResult(
            category="general_foods", is_water=False,
            reason="Aggregatzustand 'solid' -> general_foods "
                   "(dairy/plant-Flag bei festem Produkt ohne Belang).",
            sweetener_malus_applies=False,
        )
    if state == "liquid":
        is_water = _matches_any(haystack, _WATER_KEYWORDS)
        return ClassificationResult(
            category="beverages", is_water=is_water,
            reason=f"Aggregatzustand 'liquid' -> beverages "
                   f"(dairy={is_dairy_based}, plant={is_plant_drink}, water={is_water}).",
            sweetener_malus_applies=True,
        )

    # 3) Zustand UNBEKANNT -> nicht raten.
    #    Nur eine eindeutige Getränke-FORM im Namen darf beverages vorschlagen.
    #    Wortgenauer Abgleich: "cola"/"soda" dürfen NICHT in "chocolate" greifen.
    if _matches_word(haystack, _LIQUID_FORM_KEYWORDS):
        is_water = _matches_any(haystack, _WATER_KEYWORDS)
        return ClassificationResult(
            category="beverages", is_water=is_water,
            reason="Getränke-Form aus dem Namen erschlossen; physical_state "
                   "unbekannt -> bitte Aggregatzustand bestätigen.",
            sweetener_malus_applies=True,
            needs_review=True,
        )

    # dairy/plant-Flag ALLEIN (ohne liquid, ohne Getränke-Keyword) -> KEIN Getränk.
    return ClassificationResult(
        category="general_foods", is_water=False,
        reason="physical_state unbekannt, keine Getränke-Form erkannt -> als "
               "general_foods angenommen (Scope 1). dairy/plant-Flag allein "
               "impliziert kein Getränk. Bitte Aggregatzustand nachtragen.",
        sweetener_malus_applies=False,
        needs_review=True,
    )


# ---------------------------------------------------------------------
# Selbsttest inkl. Regressionsfälle für den früheren Casein-Bug.
#   python -m nutriscore.classification   (oder direkt ausführen)
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # (label, kwargs, erwartete_kategorie)
    cases = [
        ("Whey Vanilla (solid)",        dict(product_name="Whey Vanilla", physical_state="solid"), "general_foods"),
        ("Protein Bar (solid)",         dict(product_name="Crunchy Protein Bar", physical_state="solid"), "general_foods"),
        # Regression: dairy ohne state darf NICHT nach beverages
        ("Casein Pulver (dairy,kein state)", dict(product_name="Micellar Casein", is_dairy_based=True), "general_foods"),
        ("Magermilchpulver (dairy,kein state)", dict(product_name="Skim Milk Powder", is_dairy_based=True), "general_foods"),
        ("Casein (dairy+solid)",        dict(product_name="Micellar Casein", is_dairy_based=True, physical_state="solid"), "general_foods"),
        # echte Getränke
        ("Vegan Shake RTD (liquid)",    dict(product_name="Vegan Protein Shake RTD", physical_state="liquid"), "beverages"),
        ("Oat Drink (liquid+plant)",    dict(product_name="Oat Drink Barista", is_plant_drink=True, physical_state="liquid"), "beverages"),
        ("Protein Drink (kein state)",  dict(product_name="Protein Drink Choco"), "beverages"),  # aus Form-Keyword
        ("Suppe (liquid)",              dict(product_name="Protein Soup Tomato", physical_state="liquid"), "general_foods"),
        ("Mineralwasser (liquid)",      dict(product_name="Mineral Water Still", physical_state="liquid"), "beverages"),
    ]
    print(f"{'Fall':<38}{'Kategorie':<15}{'Malus':<7}{'Review':<7}OK")
    print("-" * 80)
    allok = True
    for label, kw, expected in cases:
        r = classify_product(**kw)
        ok = r.category == expected
        allok &= ok
        print(f"{label:<38}{r.category:<15}{str(r.sweetener_malus_applies):<7}"
              f"{str(r.needs_review):<7}{'OK' if ok else 'FAIL <<<'}")
    print("\nRESULT:", "PASS" if allok else "FAIL")
    # Gating: ein FAIL muss den Build brechen, nicht nur gedruckt werden.
    import sys
    sys.exit(0 if allok else 1)
