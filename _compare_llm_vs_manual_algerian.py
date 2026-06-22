"""
Compare LLM output for Algerian dishes against manual curation.
Check which manual compounds LLM generates independently (without NA seed).
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NA_FILE = ROOT / "data" / "na_dish_compounds.json"
LLM_CACHE = ROOT / "data" / "llm_food_cache.json"

def norm_compound_name(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"\([^)]*\)", "", s)
    s = s.replace("/", " ")
    s = s.replace("+", " ")
    s = s.replace("_", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

print("=" * 60)
print("LLM vs MANUAL CURATION FOR ALGERIAN DISHES")
print("=" * 60)

# Load manual curation
with open(NA_FILE, encoding="utf-8") as f:
    manual_dishes = json.load(f)

# Load LLM cache
with open(LLM_CACHE, encoding="utf-8") as f:
    llm_cache = json.load(f)

print(f"\nManual dishes: {len(manual_dishes)}")
print(f"LLM cache entries: {len(llm_cache)}")

# Compare each dish
dish_comparison = []
for dish, manual_compounds in manual_dishes.items():
    dish_key = dish.lower()
    
    # Manual compounds (normalized)
    manual_set = set(norm_compound_name(c) for c in manual_compounds)
    
    # LLM output (without NA seed - what LLM actually generated)
    llm_output = llm_cache.get(dish_key, [])
    llm_set = set(norm_compound_name(c) for c in llm_output)
    
    # Calculate overlap
    overlap = manual_set & llm_set
    manual_only = manual_set - llm_set
    llm_only = llm_set - manual_set
    
    dish_comparison.append({
        "dish": dish,
        "manual_count": len(manual_set),
        "llm_count": len(llm_set),
        "overlap": len(overlap),
        "manual_only": len(manual_only),
        "llm_only": len(llm_only),
        "overlap_pct": len(overlap)/len(manual_set)*100 if manual_set else 0,
        "overlap_compounds": list(overlap),
        "manual_only_compounds": list(manual_only),
        "llm_only_compounds": list(llm_only)
    })

# Sort by overlap percentage
dish_comparison.sort(key=lambda x: x["overlap_pct"])

print(f"\n--- DISHES WITH LOWEST LLM-MANUAL OVERLAP ---")
for dc in dish_comparison[:10]:
    print(f"\n{dc['dish']}: {dc['overlap']}/{dc['manual_count']} overlap ({dc['overlap_pct']:.0f}%)")
    print(f"  Manual only: {', '.join(dc['manual_only_compounds'][:5])}")
    print(f"  LLM only: {', '.join(dc['llm_only_compounds'][:5])}")

print(f"\n--- DISHES WITH HIGHEST LLM-MANUAL OVERLAP ---")
for dc in dish_comparison[-10:]:
    print(f"\n{dc['dish']}: {dc['overlap']}/{dc['manual_count']} overlap ({dc['overlap_pct']:.0f}%)")

# Overall stats
total_manual = sum(dc["manual_count"] for dc in dish_comparison)
total_llm = sum(dc["llm_count"] for dc in dish_comparison)
total_overlap = sum(dc["overlap"] for dc in dish_comparison)

print(f"\n--- OVERALL STATS ---")
print(f"Total manual compounds: {total_manual}")
print(f"Total LLM compounds: {total_llm}")
print(f"Total overlap: {total_overlap}")
print(f"LLM recall vs manual: {total_overlap/total_manual*100:.1f}%")
print(f"LLM precision vs manual: {total_overlap/total_llm*100 if total_llm > 0 else 0:.1f}%")

# Show dishes where LLM generated manual compounds
print(f"\n--- DISHES WHERE LLM GENERATED MANUAL COMPOUNDS ---")
for dc in dish_comparison:
    if dc["overlap"] > 0:
        print(f"{dc['dish']}: {', '.join(dc['overlap_compounds'][:5])}")
