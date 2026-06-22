# NutriHack — Simulator vs. Optimierer

**Zweck dieses Dokuments:** Die beiden Komponenten formal trennen, damit sie
in Code, Architektur und Praesentation nie vermischt werden. Fuer Scope 1
wird der **Simulator vollstaendig** gebaut; der **Optimierer** ist als
Konzept dokumentiert (Roadmap), nicht als Implementierung.

---

## Die Kernunterscheidung in einem Satz

> Der **Simulator** beantwortet *"Was passiert mit meinem Score, wenn ich
> X aendere?"* (vorwaerts, Mensch entscheidet).
> Der **Optimierer** beantwortet *"Welche Aenderung bringt mich am
> guenstigsten zu Ziel-Score Y?"* (rueckwaerts, Maschine empfiehlt).

| Dimension            | Simulator (A)                    | Optimierer (B)                          |
|----------------------|----------------------------------|-----------------------------------------|
| Richtung             | Vorwaerts: Input -> Score        | Rueckwaerts: Ziel-Score -> Input        |
| Wer entscheidet      | Mensch dreht den Regler          | Maschine sucht die Loesung              |
| Frage                | "Was, wenn...?"                   | "Wie erreiche ich...?"                  |
| Output               | EIN neuer Score                  | EINE empfohlene Aenderungskombination   |
| Rechenlast           | Trivial (1 Funktionsaufruf)      | Hoch (Suche ueber Loesungsraum)         |
| In Tableau baubar?   | Ja (Parameter + Calculated Field)| Nein/kaum (gehoert nach Python)         |
| Scope                | **Scope 1 — wird geliefert**     | **Roadmap — Konzept only**              |

---

## (A) Der Simulator — vollstaendige Spezifikation (Scope 1)

### Funktionsprinzip
Der Simulator ist mechanisch nichts anderes als die Scoring-Engine, die
mit veraenderten Eingabewerten erneut aufgerufen wird. Es gibt keine
Suchlogik — der Nutzer setzt die Werte, die Engine rechnet.

```
def simulate(basis_produkt: dict, aenderungen: dict) -> dict:
    """
    Vorwaertsfunktion.
    basis_produkt : Original-Naehrwerte (pro 100 g)
    aenderungen   : z.B. {"sugar_100g": -8.0}  (relativ oder absolut)
    Rueckgabe     : neuer Score + Differenz zum Original
    """
    neu = basis_produkt.copy()
    for feld, delta in aenderungen.items():
        neu[feld] = max(0.0, neu[feld] + delta)   # nie negativ
    score_alt = scoring_engine(basis_produkt)
    score_neu = scoring_engine(neu)
    return {
        "score_alt": score_alt,     # z.B. ("D", 17)
        "score_neu": score_neu,     # z.B. ("C", 11)
        "klasse_gewechselt": score_alt.letter != score_neu.letter,
    }
```

### Umsetzung in Tableau (die eigentliche Demo)
- **Parameter** = die Regler (z.B. "Zucker-Reduktion %", "Salz-Reduktion %",
  "Protein-Erhoehung g").
- **Calculated Fields** bilden die Punkte-Logik in Tableaus Formelsprache
  nach (dieselben Schwellen wie in Python, 1:1 gespiegelt).
- Nutzer zieht den Regler -> Calculated Field rechnet Punkte neu ->
  finaler Score + Ampelfarbe aktualisieren sich live.

### Was der Simulator demonstriert
Live am Regler: "8 g Zucker weniger pro 100 g hebt das Produkt von D auf C"
-> sichtbarer Farbwechsel im Regal -> Business-Argument. Das ist die
Praesentations-Demo.

---

## (B) Der Optimierer — Konzept-Dokument (Roadmap, NICHT Scope 1)

### Das Problem, das er loest
Der Simulator zeigt das Ergebnis EINER vom Menschen gewaehlten Aenderung.
Aber der Hersteller will eigentlich das Inverse wissen: *"Ich will Score B.
Was ist der GUENSTIGSTE Weg dorthin?"* Es gibt typischerweise viele
Kombinationen (Zucker runter / Salz runter / Protein rauf / Ballaststoffe
rauf), die dasselbe Ziel erreichen — aber sie unterscheiden sich massiv in
Kosten, Geschmack und Machbarkeit. Diese Suche ist der eigentliche
Geschaeftswert.

### Prinzipieller Ansatz: Brute-Force ueber diskrete Schritte
Fuer einen ersten Wurf reicht eine erschoepfende Suche ueber ein diskretes
Raster — kein ausgefeilter Optimierungsalgorithmus noetig.

```
ZIEL: finde guenstigste Aenderungskombination, die Ziel-Score erreicht.

1. Definiere pro Stellschraube diskrete Schritte UND Kosten pro Schritt:
   zucker_schritte   = [0, -2, -4, -6, -8, -10]   g/100g
   salz_schritte     = [0, -0.1, -0.2, -0.3]      g/100g
   protein_schritte  = [0, +1, +2, +3]            g/100g
   ballast_schritte  = [0, +1, +2, +3]            g/100g
   (Kostenfunktion: z.B. EUR pro -1 g Zucker via Suessstoff-Matrix etc.)

2. Bilde das kartesische Produkt aller Schritt-Kombinationen
   (im Beispiel 6 x 4 x 4 x 4 = 384 Kombinationen — winzig).

3. Fuer jede Kombination:
   - wende Aenderungen auf das Basis-Produkt an
   - rufe scoring_engine() auf  (der Simulator als Baustein!)
   - pruefe: erreicht sie den Ziel-Score?
   - wenn ja: berechne Gesamtkosten der Kombination

4. Aus allen treffenden Kombinationen:
   gib die mit den MINIMALEN Kosten zurueck
   (optional: Top-3 als Alternativen mit Trade-off-Hinweisen).
```

```
def optimize(basis_produkt, ziel_letter, schritt_raster, kosten_fn):
    treffer = []
    for kombi in kartesisches_produkt(schritt_raster):
        score = scoring_engine(apply(basis_produkt, kombi))
        if besser_oder_gleich(score.letter, ziel_letter):
            treffer.append((kosten_fn(kombi), kombi, score))
    return sorted(treffer)[:3]     # guenstigste 3 Wege
```

### Warum NICHT in Scope 1 / nicht in Tableau
- Tableau-Parameter sind fuer Vorwaertsrechnung gemacht; eine Suche ueber
  hunderte Kombinationen mit Kostenminimierung ist dort kuenstlich und
  fragil. Das gehoert in Python.
- Es ist genau die Zusatzkomplexitaet, die den Solo-Scope sprengen wuerde.
- Der Simulator nutzt die Engine 1x; der Optimierer nutzt sie als
  Sub-Routine in einer Schleife. Der Optimierer SETZT den fertigen
  Simulator/Engine also voraus — er ist der natuerliche naechste Schritt,
  nicht ein paralleler.

### Wie man ihn in der Praesentation positioniert
Als Visions-Ausblick, sauber abgegrenzt:
> "Der gelieferte Simulator zeigt dem Hersteller die Wirkung einer
> Rezepturaenderung. Der logische naechste Entwicklungsschritt ist der
> Optimierer: Er kehrt die Frage um und schlaegt automatisch den
> kostenguenstigsten Reformulierungspfad zu einem Ziel-Score vor."

Das zeigt strategische Weitsicht — ohne dass etwas davon gebaut werden muss.

---

## Sprachregelung fuer Stand-Ups & Abschlusspraesentation

- **Simulator** = geliefertes Deliverable. Immer so nennen, wenn die
  Live-Demo gemeint ist.
- **Optimierer** = Roadmap / "naechster Schritt". Nie als bereits gebaut
  darstellen.
- Die beiden Begriffe in derselben Folie nur dann gemeinsam nennen, wenn
  die Trennung explizit das Thema ist (Deliverable vs. Vision).
