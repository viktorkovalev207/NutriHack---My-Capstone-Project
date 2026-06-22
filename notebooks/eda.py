# %% [markdown]
# # NutriHack — Explorative Datenanalyse (EDA)
# **Capstone · Viktor Kovalev · 2026**
#
# **Business Question:**
# *Wie schneiden Protein-Pulver und Protein-Riegel im Nutri-Score 2024 ab,
# und welche Reformulierungs-Hebel bringen den grössten Vorteil?*

# %%
import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT / "src"))

df = pd.read_csv(ROOT / "data" / "clean" / "products_scored.csv", dtype={"barcode": str})
print(f"Dataset: {len(df):,} products  |  columns: {df.shape[1]}")
df[["product_type","ns_letter","ns_score"]].head(10)

# %% [markdown]
# ## 1 · Nutri-Score Verteilung — Gesamt

# %%
COLORS = {"A": "#1a7a4a", "B": "#85bb2f", "C": "#f8c417", "D": "#e27622", "E": "#e63312"}

counts = df["ns_letter"].value_counts().sort_index()
fig, ax = plt.subplots(figsize=(7, 4))
bars = ax.bar(counts.index, counts.values,
              color=[COLORS[l] for l in counts.index], width=0.6, edgecolor="white")
ax.bar_label(bars, fmt="{:,.0f}", padding=4, fontsize=10)
ax.set_title("Nutri-Score Verteilung — alle Produkte (n=9.893)", fontsize=13, pad=10)
ax.set_xlabel("Nutri-Score"); ax.set_ylabel("Anzahl Produkte")
ax.set_ylim(0, counts.max() * 1.15)
ax.spines[["top","right"]].set_visible(False)
plt.tight_layout()
plt.savefig(ROOT / "visualizations" / "01_score_distribution_all.png", dpi=150)
plt.show()
print("Saved: 01_score_distribution_all.png")

# %% [markdown]
# ## 2 · Verteilung nach Produkttyp

# %%
pivot = (df.groupby(["product_type","ns_letter"]).size()
           .unstack(fill_value=0)
           .reindex(columns=["A","B","C","D","E"]))

fig, axes = plt.subplots(1, 2, figsize=(12, 4), sharey=False)
for ax, (ptype, row) in zip(axes, pivot.iterrows()):
    label = "Protein-Pulver" if ptype == "protein_powder" else "Protein-Riegel"
    bars = ax.bar(row.index, row.values,
                  color=[COLORS[l] for l in row.index], width=0.6, edgecolor="white")
    ax.bar_label(bars, fmt="{:,.0f}", padding=4, fontsize=9)
    ax.set_title(label, fontsize=12)
    ax.set_xlabel("Nutri-Score"); ax.set_ylabel("Anzahl Produkte")
    ax.set_ylim(0, row.max() * 1.18)
    ax.spines[["top","right"]].set_visible(False)

plt.suptitle("Nutri-Score nach Produktkategorie", fontsize=13, y=1.02)
plt.tight_layout()
plt.savefig(ROOT / "visualizations" / "02_score_by_type.png", dpi=150, bbox_inches="tight")
plt.show()
print("Saved: 02_score_by_type.png")

# %% [markdown]
# ## 3 · Rohpunkte-Analyse: Was treibt schlechte Scores?

# %%
neg_cols = ["ns_energy_pts","ns_sugar_pts","ns_sat_fat_pts","ns_salt_pts"]
means = df.groupby("ns_letter")[neg_cols].mean()

fig, ax = plt.subplots(figsize=(9, 4))
x = range(len(means))
width = 0.2
labels = ["Energie","Zucker","Ges. Fett","Salz"]
offsets = [-1.5, -0.5, 0.5, 1.5]
for i, (col, label) in enumerate(zip(neg_cols, labels)):
    ax.bar([xi + offsets[i]*width for xi in x], means[col],
           width=width, label=label)

ax.set_xticks(list(x)); ax.set_xticklabels(means.index)
ax.set_xlabel("Nutri-Score"); ax.set_ylabel("Ø Negativpunkte")
ax.set_title("Negativpunkte nach Score-Klasse", fontsize=12)
ax.legend(); ax.spines[["top","right"]].set_visible(False)
plt.tight_layout()
plt.savefig(ROOT / "visualizations" / "03_negative_pts_breakdown.png", dpi=150)
plt.show()
print("Saved: 03_negative_pts_breakdown.png")

# %% [markdown]
# ## 4 · Simulator: Welcher Hebel bringt am meisten?

# %%
scenarios = {
    "Zucker -5g":    "sim_sugar_minus5_improved",
    "Zucker -10g":   "sim_sugar_minus10_improved",
    "Protein +5g":   "sim_protein_plus5_improved",
    "Protein +10g":  "sim_protein_plus10_improved",
    "Salz -0.3g":    "sim_salt_minus03_improved",
    "Ballaststoffe +3g": "sim_fibre_plus3_improved",
}

tableau = pd.read_csv(ROOT / "visualizations" / "nutriscore_tableau.csv", dtype={"barcode":str})
pcts = {label: tableau[col].mean()*100 for label, col in scenarios.items()}

fig, ax = plt.subplots(figsize=(8, 4))
bars = ax.barh(list(pcts.keys()), list(pcts.values()),
               color=["#2196F3"]*len(pcts), edgecolor="white")
ax.bar_label(bars, fmt="{:.1f}%", padding=4, fontsize=10)
ax.set_xlim(0, max(pcts.values()) * 1.25)
ax.set_xlabel("Anteil Produkte, die eine bessere Note erreichen (%)")
ax.set_title("Simulator: Welche Rezeptur-Änderung hilft am meisten?", fontsize=12)
ax.spines[["top","right"]].set_visible(False)
plt.tight_layout()
plt.savefig(ROOT / "visualizations" / "04_simulator_impact.png", dpi=150)
plt.show()
print("Saved: 04_simulator_impact.png")

# %% [markdown]
# ## 5 · Key Insights (Zusammenfassung)

# %%
total = len(df)
pct_ab = (df["ns_letter"].isin(["A","B"])).mean() * 100
pct_de = (df["ns_letter"].isin(["D","E"])).mean() * 100

powder = df[df["product_type"]=="protein_powder"]
bars_  = df[df["product_type"]=="protein_bar"]
pct_powder_ab = (powder["ns_letter"].isin(["A","B"])).mean() * 100
pct_bars_de   = (bars_["ns_letter"].isin(["D","E"])).mean() * 100

best_lever_pct = max(pcts.values())
best_lever     = max(pcts, key=pcts.get)

print("=" * 55)
print("KEY INSIGHTS — NutriHack Capstone")
print("=" * 55)
print(f"  Gesamt:               {total:,} Produkte analysiert")
print(f"  Gut bewertet (A/B):   {pct_ab:.1f}% aller Produkte")
print(f"  Schlecht (D/E):       {pct_de:.1f}% aller Produkte")
print()
print(f"  Protein-Pulver A/B:   {pct_powder_ab:.1f}%  (eher protein-reich, niedriger Zucker)")
print(f"  Protein-Riegel D/E:   {pct_bars_de:.1f}%  (oft hoher Zucker & Salz)")
print()
print(f"  Stärkster Hebel:      '{best_lever}' verbessert {best_lever_pct:.1f}%")
print("=" * 55)
