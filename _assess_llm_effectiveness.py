"""
Assess LLM decompose effectiveness for real foods.
Sample foods from LLM cache and verify compound accuracy against known food chemistry.
"""
import json
import re
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FOODB_FILE = ROOT / "Compound.csv"
HKG_FILE = ROOT / "data" / "processed_hkg" / "hkg_food_compound_edges.csv"
LLM_CACHE = ROOT / "data" / "llm_food_cache.json"

def norm_compound_name(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"\([^)]*\)", "", s)
    s = s.replace("/", " ")
    s = s.replace("+", " ")
    s = s.replace("_", " ")
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

def load_fooddb_vocab():
    vocab = set()
    try:
        df = pd.read_csv(FOODB_FILE, usecols=["name", "moldb_iupac"], low_memory=False)
        for col in ("name", "moldb_iupac"):
            for val in df[col].dropna().astype(str):
                vocab.add(norm_compound_name(val))
    except Exception as e:
        print(f"Error loading FooDB: {e}")
    return vocab

def load_hkg_vocab():
    vocab = set()
    try:
        df = pd.read_csv(HKG_FILE, usecols=["tail"])
        for tail in df["tail"].dropna().astype(str):
            vocab.add(norm_compound_name(tail))
    except Exception as e:
        print(f"Error loading HKG: {e}")
    return vocab

print("=" * 60)
print("LLM DECOMPOSE EFFECTIVENESS ASSESSMENT")
print("=" * 60)

fooddb = load_fooddb_vocab()
hkg = load_hkg_vocab()
combined_vocab = fooddb | hkg

with open(LLM_CACHE, encoding="utf-8") as f:
    llm_cache = json.load(f)

# Filter valid food names (exclude :tiers and pollution)
valid_cache = {k: v for k, v in llm_cache.items() if is_valid_food_name(k) and not k.endswith(":tiers")}
print(f"\nValid LLM-decomposed foods: {len(valid_cache)}")

# Analyze each food
food_analysis = []
for food, compounds in valid_cache.items():
    if not compounds:
        continue
    
    verified = []
    unverified = []
    for c in compounds:
        norm = norm_compound_name(c)
        if norm in combined_vocab:
            verified.append(c)
        else:
            unverified.append(c)
    
    food_analysis.append({
        "food": food,
        "total": len(compounds),
        "verified": len(verified),
        "unverified": len(unverified),
        "verified_pct": len(verified)/len(compounds)*100 if compounds else 0,
        "compounds": compounds
    })

# Sort by number of compounds (most compounds first)
food_analysis.sort(key=lambda x: x["total"], reverse=True)

print(f"\n--- TOP 10 FOODS BY COMPOUND COUNT ---")
for fa in food_analysis[:10]:
    print(f"\n{fa['food']}: {fa['total']} compounds ({fa['verified_pct']:.0f}% verified)")
    print(f"  Compounds: {', '.join(fa['compounds'][:10])}")
    if len(fa['compounds']) > 10:
        print(f"  ... and {len(fa['compounds']) - 10} more")

# Overall stats
total_foods = len(food_analysis)
total_compounds = sum(fa["total"] for fa in food_analysis)
total_verified = sum(fa["verified"] for fa in food_analysis)
total_unverified = sum(fa["unverified"] for fa in food_analysis)

print(f"\n--- OVERALL EFFECTIVENESS ---")
print(f"Total foods analyzed: {total_foods}")
print(f"Total compounds generated: {total_compounds}")
print(f"Average compounds per food: {total_compounds/total_foods:.1f}")
print(f"Verified (in FooDB/HKG): {total_verified} ({total_verified/total_compounds*100:.1f}%)")
print(f"Unverified (not in databases): {total_unverified} ({total_unverified/total_compounds*100:.1f}%)")

# Check for common compound categories
print(f"\n--- COMMON COMPOUND CATEGORIES ---")
all_compounds = []
for fa in food_analysis:
    all_compounds.extend(fa["compounds"])

# Count compound occurrences
from collections import Counter
compound_counts = Counter(all_compounds)
print(f"Most common compounds:")
for compound, count in compound_counts.most_common(10):
    print(f"  {compound}: {count} foods")
