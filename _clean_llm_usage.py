"""
Clean LLM cache analysis - filter out non-food entries and get accurate usage stats.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NA_FILE = ROOT / "data" / "na_dish_compounds.json"
FOOD_ID_MAP = ROOT / "DFinder-main" / "data" / "unified-DFI" / "id_maps" / "food_id_map.csv"
LLM_CACHE = ROOT / "data" / "llm_food_cache.json"

def is_valid_food_name(name: str) -> bool:
    """Filter out cache pollution (drug-food interaction results, etc.)"""
    name = name.lower()
    # Skip if contains interaction-specific patterns
    if "_unknown_" in name or "_medium_" in name or "_high_" in name:
        return False
    if "interaction" in name or "signal" in name or "detected" in name:
        return False
    if "narrative" in name or "v16" in name:
        return False
    # Skip if looks like drug-compound pair
    if re.match(r"^[a-z]+_[a-z]+_(low|medium|high)_", name):
        return False
    return True

print("=" * 60)
print("CLEAN LLM USAGE ANALYSIS")
print("=" * 60)

# Load NA seed
with open(NA_FILE, encoding="utf-8") as f:
    na_dishes = json.load(f)
print(f"\nNA seed dishes: {len(na_dishes)}")

# Load known pipeline foods
try:
    import pandas as pd
    food_map = pd.read_csv(FOOD_ID_MAP)
    known_foods = set(food_map['name'].str.lower().unique())
    print(f"Known pipeline foods: {len(known_foods)}")
except Exception as e:
    print(f"Error loading food_id_map: {e}")
    known_foods = set()

# Load and clean LLM cache
with open(LLM_CACHE, encoding="utf-8") as f:
    llm_cache = json.load(f)

# Filter valid food names
valid_cache = {k: v for k, v in llm_cache.items() if is_valid_food_name(k)}
print(f"\nOriginal cache entries: {len(llm_cache)}")
print(f"Valid food entries (filtered): {len(valid_cache)}")
print(f"Polluted entries removed: {len(llm_cache) - len(valid_cache)}")

# Categorize valid cache entries
llm_only_foods = []
na_seed_foods_in_cache = []
known_pipeline_foods_in_cache = []

for food in valid_cache.keys():
    food_norm = food.lower()
    if food_norm in [d.lower() for d in na_dishes.keys()]:
        na_seed_foods_in_cache.append(food)
    elif food_norm in known_foods:
        known_pipeline_foods_in_cache.append(food)
    else:
        llm_only_foods.append(food)

print(f"\n--- CLEAN LLM CACHE BREAKDOWN ---")
print(f"LLM-only foods (triggered LLM): {len(llm_only_foods)}")
print(f"NA seed foods in cache (shouldn't happen): {len(na_seed_foods_in_cache)}")
print(f"Known pipeline foods in cache (shouldn't happen): {len(known_pipeline_foods_in_cache)}")

print(f"\n--- LLM-ONLY FOODS (actual LLM usage) ---")
print(f"Total: {len(llm_only_foods)}")
print(f"Sample (first 30):")
for f in sorted(llm_only_foods)[:30]:
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
