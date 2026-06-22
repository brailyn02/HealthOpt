"""
Analyze LLM decompose usage in the pipeline:
1. How many foods are in known pipeline (bypass LLM)
2. How many foods are in NA seed (bypass LLM)
3. What foods actually trigger LLM calls
4. Assess LLM utility for those foods
"""
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NA_FILE = ROOT / "data" / "na_dish_compounds.json"
FOOD_ID_MAP = ROOT / "DFinder-main" / "data" / "unified-DFI" / "id_maps" / "food_id_map.csv"
LLM_CACHE = ROOT / "data" / "llm_food_cache.json"

print("=" * 60)
print("LLM DECOMPOSE USAGE ANALYSIS")
print("=" * 60)

# Load NA seed
import json
with open(NA_FILE, encoding="utf-8") as f:
    na_dishes = json.load(f)
print(f"\nNA seed dishes: {len(na_dishes)}")

# Load known pipeline foods
try:
    food_map = pd.read_csv(FOOD_ID_MAP)
    known_foods = set(food_map['name'].str.lower().unique())
    print(f"Known pipeline foods: {len(known_foods)}")
except Exception as e:
    print(f"Error loading food_id_map: {e}")
    known_foods = set()

# Load LLM cache to see what foods actually triggered LLM calls
with open(LLM_CACHE, encoding="utf-8") as f:
    llm_cache = json.load(f)
print(f"LLM cache entries: {len(llm_cache)}")

# Categorize LLM cache entries
llm_only_foods = []
na_seed_foods_in_cache = []
known_pipeline_foods_in_cache = []

for food in llm_cache.keys():
    food_norm = food.lower()
    if food_norm in [d.lower() for d in na_dishes.keys()]:
        na_seed_foods_in_cache.append(food)
    elif food_norm in known_foods:
        known_pipeline_foods_in_cache.append(food)
    else:
        llm_only_foods.append(food)

print(f"\n--- LLM CACHE BREAKDOWN ---")
print(f"LLM-only foods (triggered LLM): {len(llm_only_foods)}")
print(f"NA seed foods in cache (shouldn't happen): {len(na_seed_foods_in_cache)}")
print(f"Known pipeline foods in cache (shouldn't happen): {len(known_pipeline_foods_in_cache)}")

if na_seed_foods_in_cache:
    print(f"\n⚠️  NA seed foods in cache (unexpected):")
    for f in na_seed_foods_in_cache[:10]:
        print(f"  - {f}")

if known_pipeline_foods_in_cache:
    print(f"\n⚠️  Known pipeline foods in cache (unexpected):")
    for f in known_pipeline_foods_in_cache[:10]:
        print(f"  - {f}")

print(f"\n--- LLM-ONLY FOODS (actual LLM usage) ---")
print(f"Total: {len(llm_only_foods)}")
print(f"Sample (first 20):")
for f in sorted(llm_only_foods)[:20]:
    print(f"  - {f}")

# Calculate coverage
total_coverage = len(known_foods) + len(na_dishes)
llm_coverage = len(llm_only_foods)
print(f"\n--- COVERAGE ANALYSIS ---")
print(f"Pipeline foods (bypass LLM): {len(known_foods)}")
print(f"NA seed dishes (bypass LLM): {len(na_dishes)}")
print(f"Total bypass coverage: {total_coverage}")
print(f"LLM-only foods (require LLM): {llm_coverage}")
print(f"LLM utility ratio: {llm_coverage/total_coverage*100:.1f}%")
