"""
Sample 10-15 extra runtime compounds (in runtime but not in manual baseline)
for manual food verification against food science literature.
"""
import json
import pandas as pd
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
NA_FILE = ROOT / "data" / "na_dish_compounds.json"
FOODB_FILE = ROOT / "Compound.csv"
HKG_FILE = ROOT / "data" / "processed_hkg" / "hkg_food_compound_edges.csv"
LLM_CACHE = ROOT / "data" / "llm_food_cache.json"
PUBCHEM_RESULTS = ROOT / "ablation_results" / "pubchem_excluded_validation.json"

def norm_compound_name(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"\([^)]*\)", "", s)
    s = s.replace("/", " ")
    s = s.replace("+", " ")
    s = s.replace("_", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def load_manual_compounds():
    with open(NA_FILE, encoding="utf-8") as f:
        data = json.load(f)
    all_manual = set()
    for dish, compounds in data.items():
        for c in compounds:
            all_manual.add(norm_compound_name(c))
    return all_manual

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

def load_runtime_output_per_dish():
    with open(NA_FILE, encoding="utf-8") as f:
        na_dishes = json.load(f)
    with open(LLM_CACHE, encoding="utf-8") as f:
        cache = json.load(f)
    
    runtime_by_dish = {}
    for dish, na_compounds in na_dishes.items():
        key = dish.lower()
        dish_output = set()
        for c in na_compounds:
            dish_output.add(norm_compound_name(c))
        llm_part = cache.get(key, [])
        for c in llm_part:
            dish_output.add(norm_compound_name(c))
        runtime_by_dish[dish] = dish_output
    
    return runtime_by_dish

print("=" * 60)
print("SAMPLING EXTRA RUNTIME COMPOUNDS FOR MANUAL VERIFICATION")
print("=" * 60)

manual = load_manual_compounds()
fooddb = load_fooddb_vocab()
hkg = load_hkg_vocab()
runtime_by_dish = load_runtime_output_per_dish()

combined_vocab = fooddb | hkg

# Find extra compounds (in runtime but not in manual)
extra_compounds = []
for dish, compounds in runtime_by_dish.items():
    for compound in compounds:
        if compound not in manual:
            source = "FooDB" if compound in fooddb else "HKG" if compound in hkg else "Neither"
            extra_compounds.append((dish, compound, source))

print(f"\nTotal extra runtime compounds: {len(extra_compounds)}")

# Sample 15 for manual verification
import random
random.seed(42)
sampled = random.sample(extra_compounds, min(15, len(extra_compounds)))

print(f"\n--- SAMPLED COMPOUNDS FOR MANUAL VERIFICATION ---")
print("Format: [Dish] Compound (Source: FooDB/HKG)")
print("Please verify using food science literature whether these compounds")
print("are genuinely present in the specified Algerian dishes.\n")

for i, (dish, compound, source) in enumerate(sampled, 1):
    print(f"{i}. [{dish}] {compound} (Source: {source})")

print(f"\n--- FULL LIST OF EXTRA COMPOUNDS ---")
print(f"Total: {len(extra_compounds)}")
print(f"Writing to file...")

with open(ROOT / "ablation_results" / "extra_runtime_compounds_for_verification.txt", "w", encoding="utf-8") as f:
    f.write("EXTRA RUNTIME COMPOUNDS (not in manual baseline)\n")
    f.write("=" * 60 + "\n\n")
    f.write(f"Total: {len(extra_compounds)}\n\n")
    f.write("Format: [Dish] Compound (Source)\n\n")
    for dish, compound, source in sorted(extra_compounds):
        f.write(f"[{dish}] {compound} ({source})\n")

print(f"Saved to: ablation_results/extra_runtime_compounds_for_verification.txt")
