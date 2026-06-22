"""
Investigate 3 gate-bypassing compounds: thymol, diallyl sulfide, diallyl disulfide
Check if they're in NA seed (bypasses gate) or LLM cache (should have been filtered)
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NA_FILE = ROOT / "data" / "na_dish_compounds.json"
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

def load_fooddb_vocab():
    import pandas as pd
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
    import pandas as pd
    vocab = set()
    try:
        df = pd.read_csv(HKG_FILE, usecols=["tail"])
        for tail in df["tail"].dropna().astype(str):
            vocab.add(norm_compound_name(tail))
    except Exception as e:
        print(f"Error loading HKG: {e}")
    return vocab

print("=" * 60)
print("INVESTIGATING GATE-BYPASSING COMPOUNDS")
print("=" * 60)

fooddb = load_fooddb_vocab()
hkg = load_hkg_vocab()
combined_vocab = fooddb | hkg

# Check the 3 compounds
suspicious_compounds = ["thymol", "diallyl sulfide", "diallyl disulfide"]

print(f"\n--- CHECKING IF COMPOUNDS ARE IN DATABASES ---")
for compound in suspicious_compounds:
    norm = norm_compound_name(compound)
    in_fooddb = norm in fooddb
    in_hkg = norm in hkg
    print(f"{compound:20s} -> FooDB: {in_fooddb}, HKG: {in_hkg}")

# Check if they're in NA seed
with open(NA_FILE, encoding="utf-8") as f:
    na_dishes = json.load(f)

print(f"\n--- CHECKING IF COMPOUNDS ARE IN NA SEED ---")
for compound in suspicious_compounds:
    norm = norm_compound_name(compound)
    found_in_dishes = []
    for dish, compounds in na_dishes.items():
        for c in compounds:
            if norm_compound_name(c) == norm:
                found_in_dishes.append(dish)
    if found_in_dishes:
        print(f"{compound:20s} -> IN NA SEED (dishes: {', '.join(found_in_dishes)})")
    else:
        print(f"{compound:20s} -> NOT in NA seed")

# Check if they're in LLM cache
with open(LLM_CACHE, encoding="utf-8") as f:
    llm_cache = json.load(f)

print(f"\n--- CHECKING IF COMPOUNDS ARE IN LLM CACHE ---")
for compound in suspicious_compounds:
    norm = norm_compound_name(compound)
    found_in_foods = []
    for food, compounds in llm_cache.items():
        for c in compounds:
            if norm_compound_name(c) == norm:
                found_in_foods.append(food)
    if found_in_foods:
        print(f"{compound:20s} -> IN LLM CACHE (foods: {', '.join(found_in_foods[:5])})")
    else:
        print(f"{compound:20s} -> NOT in LLM cache")

# Check chakhchoukha specifically (where they appeared)
print(f"\n--- CHECKING CHAKHCHOUKHA OUTPUT ---")
chakhchoukha_key = None
for key in na_dishes.keys():
    if "chakhchoukha" in key.lower():
        chakhchoukha_key = key
        break

if chakhchoukha_key:
    print(f"NA seed for {chakhchoukha_key}:")
    for c in na_dishes[chakhchoukha_key]:
        print(f"  - {c}")
    
    print(f"\nLLM cache for {chakhchoukha_key}:")
    cache_key = chakhchoukha_key.lower()
    if cache_key in llm_cache:
        for c in llm_cache[cache_key]:
            print(f"  - {c}")
    else:
        print(f"  (not in cache)")
