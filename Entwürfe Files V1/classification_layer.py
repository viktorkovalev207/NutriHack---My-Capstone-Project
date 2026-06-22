"""
classification_layer.py
=======================================================================
NutriHack — Klassifizierungs-Layer (Stufe 3, vorgelagert)

ZWECK
-----
Der Nutri-Score-2024-Algorithmus verwendet je nach Produkttyp ZWEI
unterschiedliche Regelwerke mit unterschiedlichen Punkte-Tabellen und
Schwellenwerten:

  - "general_foods"  -> feste Lebensmittel (Pulver, Riegel, ...)
  - "beverages"      -> trinkbare Produkte (Shakes, RTD, Milchdrinks,
                        Pflanzendrinks, ...)

Diese Funktion entscheidet, WELCHES Regelwerk fuer ein Produkt gilt.
Die Scoring-Engine ruft DANACH die kategoriespezifische Punkte-Tabelle
auf. Die beiden Schritte sind bewusst getrennt:

      Produkt -> [classify_product] -> Kategorie -> [scoring_engine]

WARUM EIN EIGENER LAYER (auch wenn Scope 1 alles nach general_foods routet)
---------------------------------------------------------------------------
Im aktuellen Scope 1 betrachten wir ausschliesslich feste Produkte
(Proteinpulver, Proteinriegel). Fuer diese ist das Ergebnis IMMER
"general_foods". Trotzdem existiert dieser Layer als eigenstaendige,
dokumentierte Funktion, weil:

  1. Erweiterbarkeit: Sobald RTD-Shakes / Protein-Drinks aufgenommen
     werden, ist der Beverage-Pfad bereits vorgesehen. Es muss dann nur
     die Beverage-Punkte-Tabelle ergaenzt werden, nicht die Architektur
     umgebaut werden.
  2. Korrektheit der Reform 2024: Der Suessstoff-Malus gilt im
     2024-Algorithmus AUSSCHLIESSLICH fuer Getraenke. Ohne sauberen
     Klassifizierungs-Layer wuerde man diesen Malus faelschlich auf
     feste Produkte anwenden (oder umgekehrt vergessen).
  3. Nachvollziehbarkeit: Jede Klassifizierung gibt eine Begruendung
     zurueck -> auditierbar fuer den B2B-Use-Case.

WICHTIG — QUELLE DER REGELN
---------------------------
Die hier kodierten Zuordnungsregeln (was zaehlt als Getraenk?) folgen
den offiziellen Nutri-Score-2024-Definitionen. Die exakten numerischen
SCHWELLENWERTE der Punkte-Tabellen sind NICHT Teil dieses Layers — sie
kommen ausschliesslich aus dem offiziellen Santé-publique-France-Workbook
und werden in einem separaten Modul (scoring_tables) mit Zellbezug
hinterlegt.

Stand der offiziellen Sonderregeln (Reform 2024), die hier relevant sind:
  - Milch, Trinkjoghurt, aromatisierte Milchdrinks und Pflanzendrinks
    werden als "beverages" behandelt (unabhaengig vom Milchanteil).
  - Suppen und Gazpacho bleiben "general_foods".
  - Nur Wasser kann unter den Getraenken ein A erreichen.
Diese Regeln sollten vor finaler Abgabe nochmals 1:1 gegen das offizielle
Workbook / die offizielle FAQ verifiziert werden.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------
# Ergebnis-Objekt: nicht nur die Kategorie, sondern auch das WARUM.
# ---------------------------------------------------------------------
@dataclass
class ClassificationResult:
    category: str          # "general_foods" oder "beverages"
    is_water: bool         # True nur fuer reines Wasser (Sonderfall A)
    reason: str            # auditierbare Begruendung
    sweetener_malus_applies: bool  # True nur bei beverages (Reform 2024)


# ---------------------------------------------------------------------
# Schluesselwoerter zur Getraenke-Erkennung.
# Bewusst konservativ gehalten und gut kommentiert, damit die Liste
# spaeter leicht gegen die offizielle Definition geprueft werden kann.
# ---------------------------------------------------------------------
_BEVERAGE_KEYWORDS = (
    "drink", "beverage", "getränk", "getraenk", "shake", "smoothie",
    "juice", "saft", "milk", "milch", "rtd", "ready-to-drink",
    "ready to drink", "wasser", "water",
)

# Pflanzendrinks: laut Reform 2024 ebenfalls Getraenke.
_PLANT_DRINK_KEYWORDS = (
    "soy drink", "soja drink", "almond milk", "mandelmilch",
    "oat drink", "hafer drink", "rice drink", "reis drink",
    "plant-based drink", "pflanzendrink", "pflanzlicher drink",
)

# Ausnahmen, die trotz "fluessig-klingender" Begriffe FESTE Lebensmittel
# bleiben (laut offizieller Regel). Beispiel: Suppen, Gazpacho.
_GENERAL_FOOD_EXCEPTIONS = (
    "soup", "suppe", "gazpacho", "broth", "brühe", "bruehe",
)

# Reines Wasser -> einziger Getraenke-Sonderfall, der A erreichen kann.
_WATER_KEYWORDS = (
    "mineral water", "spring water", "mineralwasser", "quellwasser",
    "still water", "sparkling water", "tafelwasser",
)


def _matches_any(text: str, keywords) -> bool:
    """Hilfsfunktion: kommt eines der Schluesselwoerter im Text vor?"""
    return any(k in text for k in keywords)


def classify_product(
    product_name: Optional[str] = None,
    category: Optional[str] = None,
    physical_state: Optional[str] = None,
    is_dairy_based: bool = False,
    is_plant_drink: bool = False,
    *,
    force_scope1_general_foods: bool = True,
) -> ClassificationResult:
    """
    Ordnet ein Produkt dem Nutri-Score-Regelwerk "general_foods" oder
    "beverages" zu.

    Parameter
    ---------
    product_name : str, optional
        Produktname (z.B. "Whey Protein Vanilla").
    category : str, optional
        OFF-Kategorie-String (z.B. "protein-powders").
    physical_state : str, optional
        Falls bekannt: "solid" oder "liquid". Staerkstes Signal,
        wenn vorhanden.
    is_dairy_based : bool
        True, wenn Milchbasis bekannt ist (Milch zaehlt als Getraenk).
    is_plant_drink : bool
        True, wenn explizit als Pflanzendrink bekannt.
    force_scope1_general_foods : bool, keyword-only
        SCOPE-1-SCHALTER. Solange True (Default), wird jedes feste
        Produkt deterministisch nach "general_foods" geroutet und der
        Beverage-Pfad nur betreten, wenn ein Produkt eindeutig fluessig
        ist. Fuer eine spaetere Beverage-Erweiterung auf False setzen,
        um die volle Klassifizierungslogik zu aktivieren.

    Rueckgabe
    ---------
    ClassificationResult
        Mit Kategorie, Wasser-Flag, Begruendung und Suessstoff-Malus-Flag.
    """
    # Texte normalisieren (lowercase, None -> leer)
    name = (product_name or "").lower().strip()
    cat = (category or "").lower().strip()
    state = (physical_state or "").lower().strip()
    haystack = f"{name} {cat}"

    # -----------------------------------------------------------------
    # 1) Harte Ausnahmen zuerst: Suppe/Gazpacho bleiben general_foods,
    #    egal wie fluessig sie sind.
    # -----------------------------------------------------------------
    if _matches_any(haystack, _GENERAL_FOOD_EXCEPTIONS):
        return ClassificationResult(
            category="general_foods",
            is_water=False,
            reason="Ausnahmeregel: Suppe/Gazpacho zaehlt laut Reform 2024 "
                   "als general_foods, nicht als Getraenk.",
            sweetener_malus_applies=False,
        )

    # -----------------------------------------------------------------
    # 2) Eindeutiges physikalisches Signal hat Vorrang, falls vorhanden.
    # -----------------------------------------------------------------
    if state == "solid":
        return ClassificationResult(
            category="general_foods",
            is_water=False,
            reason="Physikalischer Zustand 'solid' -> general_foods.",
            sweetener_malus_applies=False,
        )

    explicit_liquid = (state == "liquid")

    # -----------------------------------------------------------------
    # 3) Getraenke-Erkennung ueber Flags + Schluesselwoerter.
    # -----------------------------------------------------------------
    looks_like_beverage = (
        explicit_liquid
        or is_dairy_based
        or is_plant_drink
        or _matches_any(haystack, _BEVERAGE_KEYWORDS)
        or _matches_any(haystack, _PLANT_DRINK_KEYWORDS)
    )

    # -----------------------------------------------------------------
    # 4) SCOPE-1-SCHALTER: solange aktiv und das Produkt nicht eindeutig
    #    fluessig ist, deterministisch nach general_foods routen.
    #    Das verhindert Fehlklassifikationen durch zufaellige
    #    Keyword-Treffer (z.B. "milk chocolate flavour" in einem Riegel).
    # -----------------------------------------------------------------
    if force_scope1_general_foods and not explicit_liquid \
            and not is_dairy_based and not is_plant_drink:
        return ClassificationResult(
            category="general_foods",
            is_water=False,
            reason="Scope-1-Routing: festes Fitness-Produkt "
                   "(Pulver/Riegel) -> general_foods.",
            sweetener_malus_applies=False,
        )

    # -----------------------------------------------------------------
    # 5) Beverage-Pfad (fuer spaetere Erweiterung bereits vollstaendig).
    # -----------------------------------------------------------------
    if looks_like_beverage:
        is_water = _matches_any(haystack, _WATER_KEYWORDS)
        return ClassificationResult(
            category="beverages",
            is_water=is_water,
            reason=("Als Getraenk klassifiziert "
                    f"(Milchbasis={is_dairy_based}, "
                    f"Pflanzendrink={is_plant_drink}, "
                    f"fluessig={explicit_liquid})."),
            # Reform 2024: Suessstoff-Malus gilt NUR fuer Getraenke.
            sweetener_malus_applies=True,
        )

    # -----------------------------------------------------------------
    # 6) Fallback: alles uebrige -> general_foods.
    # -----------------------------------------------------------------
    return ClassificationResult(
        category="general_foods",
        is_water=False,
        reason="Default-Fallback -> general_foods.",
        sweetener_malus_applies=False,
    )


# ---------------------------------------------------------------------
# Mini-Selbsttest: zeigt das Verhalten fuer typische Faelle.
# Ausfuehren mit:  python classification_layer.py
# ---------------------------------------------------------------------
if __name__ == "__main__":
    testfaelle = [
        # (name, category, state, dairy, plant)
        ("Whey Protein Vanilla",        "protein-powders", None,     False, False),
        ("Crunchy Protein Bar Caramel", "protein-bars",    None,     False, False),
        ("Vegan Protein Shake RTD",     "protein-drinks",  "liquid", False, False),
        ("Oat Drink Barista",           "plant-drinks",    "liquid", False, True),
        ("Protein Soup Tomato",         "soups",           None,     False, False),
        ("Mineral Water Still",         "waters",          "liquid", False, False),
    ]

    print(f"{'Produkt':<32} {'Kategorie':<15} {'Malus':<6} Begruendung")
    print("-" * 100)
    for name, cat, state, dairy, plant in testfaelle:
        r = classify_product(
            product_name=name, category=cat, physical_state=state,
            is_dairy_based=dairy, is_plant_drink=plant,
        )
        print(f"{name:<32} {r.category:<15} "
              f"{str(r.sweetener_malus_applies):<6} {r.reason}")
