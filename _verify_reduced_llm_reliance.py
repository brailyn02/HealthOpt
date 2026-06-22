"""
Verify reduced LLM reliance by checking how many LLM cache foods
are now covered by FooDB or NA seed.
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

print("=" * 60)
print("VERIFYING REDUCED LLM RELIANCE")
print("=" * 60)

# Load NA seed
with open(NA_FILE, encoding="utf-8") as f:
    na_dishes = json.load(f)
na_foods_norm = set(norm_food_name(d) for d in na_dishes.keys())

# Load LLM cache
with open(LLM_CACHE, encoding="utf-8") as f:
    llm_cache = json.load(f)

# Filter valid food names (exclude pollution)
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

valid_llm_foods = {k: v for k, v in llm_cache.items() if is_valid_food_name(k) and not k.endswith(":tiers")}
print(f"\nValid LLM cache foods: {len(valid_llm_foods)}")

# Import FooDB lookup
from foodb_lookup import FooDBLookup
foodb = FooDBLookup(verbose=False)

# Analyze coverage
na_covered = []
foodb_covered = []
llm_only = []

for food in valid_llm_foods.keys():
    food_norm = norm_food_name(food)
    
    if food_norm in na_foods_norm:
        na_covered.append(food)
    elif foodb.has_food(food):
        foodb_covered.append(food)
    else:
        llm_only.append(food)

print(f"\n--- COVERAGE ANALYSIS ---")
print(f"Total LLM cache foods: {len(valid_llm_foods)}")
print(f"Covered by NA seed: {len(na_covered)} ({len(na_covered)/len(valid_llm_foods)*100:.1f}%)")
print(f"Covered by FooDB: {len(foodb_covered)} ({len(foodb_covered)/len(valid_llm_foods)*100:.1f}%)")
print(f"Still require LLM: {len(llm_only)} ({len(llm_only)/len(valid_llm_foods)*100:.1f}%)")

print(f"\n--- REDUCTION IN LLM RELIANCE ---")
print(f"Previous: All {len(valid_llm_foods)} foods would use LLM")
print(f"Now: Only {len(llm_only)} foods require LLM")
print(f"Reduction: {len(valid_llm_foods) - len(llm_only)} foods ({(len(valid_llm_foods) - len(llm_only))/len(valid_llm_foods)*100:.1f}%)")

print(f"\n--- FOODS NOW COVERED BY FOODB (sample) ---")
for food in sorted(foodb_covered)[:20]:
    print(f"  {food}")

print(f"\n--- FOODS STILL REQUIRING LLM ---")
for food in sorted(llm_only):
    print(f"  {food}")
