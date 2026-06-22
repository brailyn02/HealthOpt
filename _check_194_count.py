"""
Check if thesis's 194 runtime compounds is counting with duplicates per dish
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NA_FILE = ROOT / "data" / "na_dish_compounds.json"
LLM_CACHE = ROOT / "data" / "llm_food_cache.json"

def norm_compound_name(s: str) -> str:
    import re
    s = str(s).strip().lower()
    s = re.sub(r"\([^)]*\)", "", s)
    s = s.replace("/", " ")
    s = s.replace("+", " ")
    s = s.replace("_", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

with open(NA_FILE, encoding="utf-8") as f:
    na_dishes = json.load(f)

with open(LLM_CACHE, encoding="utf-8") as f:
    cache = json.load(f)

# Count with duplicates per dish (thesis methodology)
runtime_with_dups = 0
runtime_unique = set()

for dish, na_compounds in na_dishes.items():
    key = dish.lower()
    dish_output = set()
    
    # NA seed
    for c in na_compounds:
        dish_output.add(norm_compound_name(c))
    
    # LLM part
    llm_part = cache.get(key, [])
    for c in llm_part:
        dish_output.add(norm_compound_name(c))
    
    runtime_with_dups += len(dish_output)
    runtime_unique.update(dish_output)

print(f"Runtime compounds (with duplicates per dish): {runtime_with_dups}")
print(f"Runtime compounds (unique): {len(runtime_unique)}")
print(f"\nThesis validation likely used: {runtime_with_dups}")
