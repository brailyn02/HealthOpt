"""
List the 12 foods that are covered by FooDB but not by NA seed.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NA_FILE = ROOT / "data" / "na_dish_compounds.json"
LLM_CACHE = ROOT / "data" / "llm_food_cache.json"

def norm_food_name(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def is_valid_food_name(name: str) -> bool:
    name = name.lower()
    if "_unknown_" in name or "_medium_" in name or "_high_" in name:
        return False
    if "interaction" in name or "signal" in name or "detected" in name:
        return False
    if "narrative" in name or "v16" in name:
        return False
    if re.match(r"^[a-z]+_[a-z]+_(low|medium|high)_", name):
        return False
    return True

print("=" * 60)
print("FOODS COVERED BY FOODB BUT NOT BY NA SEED")
print("=" * 60)

# Load NA seed
with open(NA_FILE, encoding="utf-8") as f:
    na_dishes = json.load(f)
na_foods_norm = set(norm_food_name(d) for d in na_dishes.keys())

# Load LLM cache
with open(LLM_CACHE, encoding="utf-8") as f:
    llm_cache = json.load(f)

# Filter valid food names
valid_llm_foods = {k: v for k, v in llm_cache.items() if is_valid_food_name(k) and not k.endswith(":tiers")}

# Import FooDB lookup
from foodb_lookup import FooDBLookup
foodb = FooDBLookup(verbose=False)

# Find foods covered by FooDB but not NA seed
foodb_only = []
for food in valid_llm_foods.keys():
    food_norm = norm_food_name(food)
    
    if food_norm not in na_foods_norm and foodb.has_food(food):
        foodb_only.append(food)

print(f"\nTotal foods covered by FooDB but not NA seed: {len(foodb_only)}")
print(f"\nList of foods:")
for i, food in enumerate(sorted(foodb_only), 1):
    print(f"  {i}. {food}")
