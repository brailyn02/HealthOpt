"""
Step 9.2 — Build data/food_content_table.csv
Uses USDA FoodData Central foundation foods to extract per-food nutrient tiers
for: Calcium, Vitamin K (phylloquinone), Iron, Potassium, Magnesium, Zinc
Tyramine is NOT in USDA — handled via manual annotation dict for known high-tyramine foods.

Output columns:
  food_name, calcium_tier, vitk_tier, iron_tier, potassium_tier,
    magnesium_tier, zinc_tier, tyramine_tier, acid_tier
Tiers: HIGH / MEDIUM / LOW / UNKNOWN
"""

import os
import pandas as pd

USDA_DIR = "D:/23AIBox-DFinder/FoodData_Central_foundation_food_csv_2025-04-24"
OUT_PATH  = "D:/23AIBox-DFinder/data/food_content_table.csv"

# ── Nutrient IDs of interest ──────────────────────────────────────────────────
NUTRIENT_IDS = {
    "calcium":    [1087, 1237, 1239],   # total + added + intrinsic
    "vitk":       [1185, 1183, 1184],   # phylloquinone + MK-4 + dihydro
    "iron":       [1089, 1141, 1142, 1238, 1240],
    "potassium":  [1092],
    "magnesium":  [1090],
    "zinc":       [1095],
}

# Reverse lookup: nutrient_id → nutrient_key
ID_MAP: dict[int, str] = {}
for key, ids in NUTRIENT_IDS.items():
    for nid in ids:
        ID_MAP[nid] = key

ALL_IDS = set(ID_MAP.keys())

# ── Clinical thresholds (per 100 g) ──────────────────────────────────────────
# Based on DRI reference values and interaction literature
THRESHOLDS = {
    #         (MEDIUM_min, HIGH_min)
    "calcium":   (100,  300),   # mg — dairy ~120, fortified tofu ~350
    "vitk":      ( 20,  100),   # µg — broccoli ~100, spinach ~480
    "iron":      (  1,    3),   # mg — legumes ~3, liver ~6
    "potassium": (200,  400),   # mg — banana ~358, potato ~421
    "magnesium": ( 20,   60),   # mg — nuts ~150, leafy greens ~80
    "zinc":      (  1,    3),   # mg — meat ~3, oysters ~78
}

# ── Manual tyramine annotation ────────────────────────────────────────────────
# USDA doesn't measure tyramine; this is from published food-tyramine tables
# (McCabe 1986, Shulman 1989, Morales-Gutierrez 2020)
# Keys are lowercase substrings that trigger the tier
TYRAMINE_HIGH = [
    "aged cheese", "blue cheese", "camembert", "cheddar", "brie",
    "parmesan", "gruyere", "emmental", "stilton", "gouda",
    "chianti", "red wine", "miso", "soy sauce", "tamari",
    "fermented", "salami", "pepperoni", "chorizo", "anchov",
    "sauerkraut", "kimchi", "vegemite", "marmite",
    "broad bean", "fava bean",
]
TYRAMINE_MEDIUM = [
    "wine", "beer", "avocado", "banana", "raspberry", "pineapple",
    "overripe", "tofu", "tempeh", "cottage cheese", "yogurt",
    "chicken liver", "canned fish", "sardine", "herring",
]

# ── Manual acid-risk annotation (class-based) ───────────────────────────────
# Class labels used by physicochemical rule engine; this avoids one-off food
# patches by assigning family-level acid-risk tiers.
ACID_HIGH = [
    "lemon", "lime", "grapefruit", "pomelo", "citron", "vinegar",
    "pickled", "sauerkraut", "kimchi", "kombucha",
]
ACID_MEDIUM = [
    "orange", "mandarin", "clementine", "tangerine", "citrus",
    "tomato", "pineapple", "berry", "soda", "cola", "carbonated",
    "fruit juice",
]

# ── Manual Vitamin K overrides (µg per 100g, from USDA SR Legacy / literature) ─
# Used when USDA foundation foods lack VitK measurement
VITK_OVERRIDES_HIGH = [
    # >100 µg/100g
    "kale", "spinach", "collard", "swiss chard", "beet green",
    "turnip green", "mustard green", "dandelion green",
    "parsley", "cilantro", "basil", "sage", "thyme",
    "broccoli", "brussels sprout", "green onion", "scallion",
    "endive", "arugula", "watercress",
    "soybean oil", "canola oil", "olive oil",
    "natto",
]
VITK_OVERRIDES_MEDIUM = [
    # 20–100 µg/100g
    "lettuce", "cabbage", "asparagus", "cucumber", "pea",
    "green bean", "edamame", "avocado", "mango", "blueberry",
    "pomegranate", "grapes", "plum", "kiwi",
    "pine nut", "cashew", "pistachio",
    "olive", "soybean",
]

def vitk_tier_override(name_lower: str, usda_tier: str) -> str:
    """Apply manual VitK tier if USDA data is missing."""
    if usda_tier != "UNKNOWN":
        return usda_tier
    for kw in VITK_OVERRIDES_HIGH:
        if kw in name_lower:
            return "HIGH"
    for kw in VITK_OVERRIDES_MEDIUM:
        if kw in name_lower:
            return "MEDIUM"
    return "LOW"   # default: foods without VitK data are unlikely to be significant


def tyramine_tier(name_lower: str) -> str:
    for kw in TYRAMINE_HIGH:
        if kw in name_lower:
            return "HIGH"
    for kw in TYRAMINE_MEDIUM:
        if kw in name_lower:
            return "MEDIUM"
    return "LOW"


def acid_tier(name_lower: str) -> str:
    for kw in ACID_HIGH:
        if kw in name_lower:
            return "HIGH"
    for kw in ACID_MEDIUM:
        if kw in name_lower:
            return "MEDIUM"
    return "LOW"

def apply_tier(value: float, low_max: float, med_max: float) -> str:
    if pd.isna(value):
        return "UNKNOWN"
    if value >= med_max:
        return "HIGH"
    if value >= low_max:
        return "MEDIUM"
    return "LOW"

# ── Load data ─────────────────────────────────────────────────────────────────
print("Loading food.csv ...")
food_df = pd.read_csv(
    os.path.join(USDA_DIR, "food.csv"),
    usecols=["fdc_id", "description"],
    dtype={"fdc_id": int, "description": str},
)
print(f"  {len(food_df):,} food entries")

print("Loading food_nutrient.csv (filtering to target nutrients) ...")
fn_chunks = pd.read_csv(
    os.path.join(USDA_DIR, "food_nutrient.csv"),
    usecols=["fdc_id", "nutrient_id", "amount"],
    dtype={"fdc_id": int, "nutrient_id": int, "amount": float},
    chunksize=200_000,
)
rows = []
for chunk in fn_chunks:
    rows.append(chunk[chunk["nutrient_id"].isin(ALL_IDS)])
fn_df = pd.concat(rows, ignore_index=True)
print(f"  {len(fn_df):,} rows after filter")

# ── Map nutrient IDs to keys ──────────────────────────────────────────────────
fn_df["nutrient_key"] = fn_df["nutrient_id"].map(ID_MAP)

# Sum sub-nutrients per food per key (e.g., intrinsic + added calcium)
fn_agg = (
    fn_df.groupby(["fdc_id", "nutrient_key"])["amount"]
    .mean()  # mean over duplicate measurements of same nutrient
    .reset_index()
)

# Pivot to wide
pivot = fn_agg.pivot_table(
    index="fdc_id", columns="nutrient_key", values="amount", aggfunc="mean"
)
pivot.columns.name = None
pivot = pivot.reset_index()

# Join food names
pivot = pivot.merge(food_df, on="fdc_id", how="left")

# Average across duplicate descriptions (same food, multiple lab entries)
nut_cols = [c for c in pivot.columns if c in THRESHOLDS]
pivot = pivot.groupby("description")[nut_cols].mean().reset_index()
pivot.rename(columns={"description": "food_name"}, inplace=True)

print(f"  {len(pivot):,} unique food names after deduplication")

# ── Apply tiers ───────────────────────────────────────────────────────────────
for key, (med_min, high_min) in THRESHOLDS.items():
    col = f"{key}_tier"
    if key in pivot.columns:
        pivot[col] = pivot[key].apply(lambda v: apply_tier(v, med_min, high_min))
    else:
        pivot[col] = "UNKNOWN"

# Vitamin K override — supplement sparse USDA data with keyword-based tier
pivot["vitk_tier"] = pivot.apply(
    lambda r: vitk_tier_override(r["food_name"].lower(), r["vitk_tier"]), axis=1
)

# Tyramine tier (manual keyword)
pivot["tyramine_tier"] = pivot["food_name"].str.lower().apply(tyramine_tier)

# Acid tier (manual family-level keyword)
pivot["acid_tier"] = pivot["food_name"].str.lower().apply(acid_tier)

# ── Select output columns ─────────────────────────────────────────────────────
tier_cols = [
    "food_name",
    "calcium_tier", "vitk_tier", "iron_tier",
    "potassium_tier", "magnesium_tier", "zinc_tier",
    "tyramine_tier", "acid_tier",
]
# Also include raw values for debugging / future use
raw_cols = [c for c in nut_cols if c in pivot.columns]
out_df = pivot[tier_cols + raw_cols].copy()

# ── Save ─────────────────────────────────────────────────────────────────────
os.makedirs("D:/23AIBox-DFinder/data", exist_ok=True)
out_df.to_csv(OUT_PATH, index=False)
print(f"\nSaved → {OUT_PATH}  ({len(out_df):,} rows, {len(out_df.columns)} cols)")

# ── Spot-check ────────────────────────────────────────────────────────────────
print("\n── Spot-check (key foods) ──")
checks = ["spinach", "milk", "banana", "cheese", "broccoli", "chicken", "tofu",
          "soy sauce", "lentil", "potato", "oyster", "beef liver"]
for kw in checks:
    hits = out_df[out_df["food_name"].str.lower().str.contains(kw, na=False)]
    if hits.empty:
        print(f"  {kw:15s} → NOT FOUND")
    else:
        row = hits.iloc[0]
        tiers = " | ".join(
            f"{c.replace('_tier','')[:4]}:{row[c]}"
            for c in tier_cols[1:]
        )
        print(f"  {kw:15s} → {row['food_name'][:40]:<40} | {tiers}")

# Summary stats
print("\n── Tier distribution ──")
for col in tier_cols[1:]:
    counts = out_df[col].value_counts().to_dict()
    print(f"  {col}: {counts}")
