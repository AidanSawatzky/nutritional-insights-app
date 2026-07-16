import glob
import os
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# ----------------------------------------------------------------------
# Paths (resolved relative to this script, so it runs from anywhere)
# ----------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

run_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(f"Run started: {run_time}")

# Grab the first CSV in the data folder
csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
if not csv_files:
    raise FileNotFoundError(f"No CSV found in {DATA_DIR}")
csv_path = csv_files[0]
print(f"Loading: {csv_path}\n")

# ----------------------------------------------------------------------
# Load and inspect
# ----------------------------------------------------------------------
df = pd.read_csv(csv_path)
print("Columns:", list(df.columns))
print("Shape:", df.shape)
print("\nMissing values per column:")
print(df.isnull().sum())

MACROS = ["Protein(g)", "Carbs(g)", "Fat(g)"]
CUISINE_COL = "Cuisine_type" if "Cuisine_type" in df.columns else "Cuisine"

# ----------------------------------------------------------------------
# Clean: fill missing macro values with the column mean
# ----------------------------------------------------------------------
for col in MACROS:
    df[col] = pd.to_numeric(df[col], errors="coerce")
    df[col] = df[col].fillna(df[col].mean())

print("\nMissing values after cleaning:")
print(df[MACROS].isnull().sum())

# ----------------------------------------------------------------------
# 1. Average macronutrient content per diet type
# ----------------------------------------------------------------------
avg_macros = df.groupby("Diet_type")[MACROS].mean().round(2)
print("\n=== Average macronutrients by diet type ===")
print(avg_macros)

# ----------------------------------------------------------------------
# 2. Top 5 protein-rich recipes per diet type
# ----------------------------------------------------------------------
top_protein = (
    df.sort_values("Protein(g)", ascending=False)
    .groupby("Diet_type")
    .head(5)
    .sort_values(["Diet_type", "Protein(g)"], ascending=[True, False])
)
print("\n=== Top 5 protein recipes per diet type ===")
print(top_protein[["Diet_type", "Recipe_name", CUISINE_COL, "Protein(g)"]])

# ----------------------------------------------------------------------
# 3. Diet type with the highest protein
# ----------------------------------------------------------------------
highest_avg_diet = avg_macros["Protein(g)"].idxmax()
print(f"\nDiet type with highest AVERAGE protein: {highest_avg_diet} "
      f"({avg_macros.loc[highest_avg_diet, 'Protein(g)']} g)")

single_best = df.loc[df["Protein(g)"].idxmax()]
print(f"Single highest-protein recipe: {single_best['Recipe_name']} "
      f"({single_best['Diet_type']}, {single_best['Protein(g)']} g)")

# ----------------------------------------------------------------------
# 4. Most common cuisine per diet type
# ----------------------------------------------------------------------
common_cuisine = (
    df.groupby("Diet_type")[CUISINE_COL]
    .agg(lambda x: x.mode().iloc[0])
)
print("\n=== Most common cuisine per diet type ===")
print(common_cuisine)

# ----------------------------------------------------------------------
# 5. New metrics: protein-to-carbs and carbs-to-fat ratios
#    Replace 0 denominators with NaN to avoid inf
# ----------------------------------------------------------------------
df["Protein_to_Carbs_ratio"] = (
    (df["Protein(g)"] / df["Carbs(g)"])
    .replace([np.inf, -np.inf], np.nan)
    .round(3)
)
df["Carbs_to_Fat_ratio"] = (
    (df["Carbs(g)"] / df["Fat(g)"])
    .replace([np.inf, -np.inf], np.nan)
    .round(3)
)

# Save the enriched dataset
cleaned_path = os.path.join(OUTPUT_DIR, "cleaned_with_ratios.csv")
df.to_csv(cleaned_path, index=False)
print(f"\nSaved cleaned dataset with ratios to: {cleaned_path}")

# ======================================================================
# VISUALIZATIONS
# ======================================================================
sns.set_theme(style="whitegrid")

# --- Bar chart: average macronutrients per diet type (grouped) ---
plot_df = avg_macros.reset_index().melt(
    id_vars="Diet_type", value_vars=MACROS,
    var_name="Macronutrient", value_name="Grams"
)
plt.figure(figsize=(11, 6))
sns.barplot(data=plot_df, x="Diet_type", y="Grams", hue="Macronutrient")
plt.title(f"Average Macronutrients by Diet Type  ({run_time})")
plt.xlabel("Diet Type")
plt.ylabel("Average Grams")
plt.xticks(rotation=30)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "bar_avg_macros.png"), dpi=120)

# --- Heatmap: macronutrient content vs diet type ---
plt.figure(figsize=(8, 5))
sns.heatmap(avg_macros, annot=True, fmt=".1f", cmap="YlOrRd")
plt.title(f"Macronutrient Heatmap by Diet Type  ({run_time})")
plt.ylabel("Diet Type")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "heatmap_macros.png"), dpi=120)

# --- Scatter: top 5 protein recipes by cuisine ---
plt.figure(figsize=(11, 6))
sns.scatterplot(
    data=top_protein, x=CUISINE_COL, y="Protein(g)",
    hue="Diet_type", s=120
)
plt.title(f"Top 5 Protein Recipes per Diet Type by Cuisine  ({run_time})")
plt.xlabel("Cuisine")
plt.ylabel("Protein (g)")
plt.xticks(rotation=45, ha="right")
plt.legend(bbox_to_anchor=(1.02, 1), loc="upper left")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "scatter_top_protein.png"), dpi=120)

print("\nAll figures saved to the output folder. Opening windows now...")
plt.show()