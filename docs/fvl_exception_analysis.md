# Geklärt: Die FVL=5-Protein-Ausnahme wurde in der Reform 2023 entfernt

**Status: GESCHLOSSEN — Engine ist korrekt.** (Analyse vom 2026-07-03)

## Die Frage

Der klassische Nutri-Score (2017) kannte eine Ausnahme von der Protein-Cap-Regel:
Bei ≥ 11 Negativpunkten zählte Protein normalerweise nicht mehr — **außer** die
Obst/Gemüse/Hülsenfrüchte-Komponente (FVL) erreichte ihre Maximalpunktzahl 5.
Unsere Engine implementiert diese Ausnahme **nicht**. War das ein Bug?

## Der Beweis (Primärquelle)

Das offizielle, von 7 Ländern validierte Berechnungs-Workbook
(`va_nutri-score_calculation_tool_updated_algorithm.xlsx`, FPS Public Health
Belgien, Stand 2025-10) enthält **beide** Algorithmen nebeneinander auf dem
Blatt „General foods". Die Score-Formeln, wörtlich:

| Algorithmus | Zelle | Formel |
|---|---|---|
| **Alt (2017)** | `T3` | `=IF(AND(R3>=0,R3<11), R3-S3, IF(AND(R3>=11, O3=5), R3-S3, R3-O3-P3))` |
| **Neu (2023/24)** | `AD3` | `=IF(AB3<11, AB3-AC3, AB3-X3-W3)` |

`O3` = FVL-Punkte (alt). Die alte Formel enthält die Ausnahme **explizit**
(`AND(R3>=11, O3=5)` → alle Positivpunkte inkl. Protein zählen). Die neue
Formel enthält **keine** FVL-Bedingung: bei Negativpunkten ≥ 11 zählen nur noch
Ballaststoffe (`X3`) und FVL (`W3`), Protein nie.

**Schlussfolgerung:** Die Ausnahme wurde in der Reform bewusst entfernt. Unsere
Engine (`src/nutriscore/engine.py`, transkribiert AD3 wörtlich und ist per
unabhängigem Oracle gegen 620 Fälle mit 0 Abweichungen validiert —
`tests/oracle_validation.py`) implementiert die **aktuelle offizielle Regel
korrekt**. Sekundärbestätigung: die Beschreibung des Update-Algorithmus nennt
als Bedingung nur noch „Protein zählt bei N < 11" ohne FVL-Ausnahme
([Eurofins-Update-Übersicht](https://www.eurofins.de/food-analysis/food-news/food-testing-news/nutri-score-update/),
[Nature Food 2023-Update](https://www.nature.com/articles/s43016-024-00920-3)).

## Praktische Auswirkung im Marktdatensatz (9.861 Produkte)

10 Produkte haben Negativpunkte ≥ 11 **und** FVL-Punkte = 5 — alle 10 hätten
unter der alten Ausnahme einen besseren Score:

| Produkt | Neu (korrekt) | Score unter Alt-Regel |
|---|---|---|
| Kürbiskernprotein 60% Pulver | 4 / C | −3 (wäre **A**) |
| AB COMPLETE ORIGINAL | 8 / C | 1 (wäre B) |
| Protein Warrior Blend | 11 / D | 4 (wäre C) |
| Veganer Nougat & Himbeere Proteinriegel | 12 / D | 5 (wäre C) |
| … (insgesamt 10, siehe Analyse-Query unten) | | |

**Erzähl-Wert für die Präsentation:** Die Reform hat FVL-reiche Proteinprodukte
um bis zu **zwei Notenstufen** verschärft — ein weiterer Beleg, dass Hersteller
den reformierten Algorithmus neu durchrechnen müssen und Alt-Wissen („viel
Gemüseanteil rettet mein Protein") nicht mehr gilt.

## Reproduktion

```bash
# Formeln aus der Primärquelle ziehen:
python - <<'PY'
import openpyxl
ws = openpyxl.load_workbook('data/raw/nutriscore_workbook.xlsx', data_only=False)['General foods']
print('ALT :', ws['T3'].value)
print('NEU :', ws['AD3'].value)
PY
```
