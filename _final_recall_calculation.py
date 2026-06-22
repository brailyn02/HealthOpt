"""
Final recall calculation:
Baseline = manual compounds in FooDB/HKG + PubChem (203)
Runtime = NA seed + LLM output (305)
Recall = baseline compounds recovered in runtime / baseline total
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
    all_manual = []
    for dish, compounds in data.items():
        for c in compounds:
            all_manual.append((dish, c))
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
    """Return dict: dish -> set of compounds (NA seed + LLM)"""
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

def load_pubchem_results():
    with open(PUBCHEM_RESULTS, encoding="utf-8") as f:
        return json.load(f)

print("=" * 60)
print("FINAL RECALL CALCULATION")
print("=" * 60)

manual = load_manual_compounds()
fooddb = load_fooddb_vocab()
hkg = load_hkg_vocab()
runtime_by_dish = load_runtime_output_per_dish()
pubchem_data = load_pubchem_results()

combined_vocab = fooddb | hkg

# Build PubChem found set
pubchem_found = set()
for item in pubchem_data:
    if item["pubchem_found"]:
        pubchem_found.add(item["normalized"])

# Identify baseline compounds (with dish context)
baseline_compounds = []  # (dish, original, norm)
for dish, compound in manual:
    norm = norm_compound_name(compound)
    if norm in combined_vocab or norm in pubchem_found:
        baseline_compounds.append((dish, compound, norm))

print(f"\n--- BASELINE (pharmacologically canonicalized) ---")
print(f"Total baseline compounds: {len(baseline_compounds)}")

# Check which baseline compounds are recovered in runtime
recovered = []
missed = []

for dish, original, norm in baseline_compounds:
    if norm in runtime_by_dish.get(dish, set()):
        recovered.append((dish, original, norm))
    else:
        missed.append((dish, original, norm))

print(f"\n--- RECALL ---")
print(f"Recovered: {len(recovered)}")
print(f"Missed: {len(missed)}")
print(f"Recall: {len(recovered)/len(baseline_compounds)*100:.1f}%")

print(f"\n--- MISSED BASELINE COMPOUNDS ---")
for dish, original, norm in missed:
    source = "PubChem only" if norm in pubchem_found else "FooDB/HKG"
    print(f"  [{dish}] {original} ({source})")

# Count runtime output with duplicates
runtime_with_dups = sum(len(compounds) for compounds in runtime_by_dish.values())
print(f"\n--- RUNTIME OUTPUT ---")
print(f"Runtime compounds (with duplicates per dish): {runtime_with_dups}")
print(f"Runtime unique compounds: {len(set(c for compounds in runtime_by_dish.values() for c in compounds))}")
