"""
Recalculate both baseline and runtime using consistent methodology:
With duplicates per dish (thesis approach)
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

def load_runtime_output_with_dups():
    """Count runtime output WITH duplicates per dish (matching thesis methodology)"""
    with open(NA_FILE, encoding="utf-8") as f:
        na_dishes = json.load(f)
    with open(LLM_CACHE, encoding="utf-8") as f:
        cache = json.load(f)
    
    runtime_with_dups = 0
    for dish, na_compounds in na_dishes.items():
        key = dish.lower()
        dish_output = set()
        for c in na_compounds:
            dish_output.add(norm_compound_name(c))
        llm_part = cache.get(key, [])
        for c in llm_part:
            dish_output.add(norm_compound_name(c))
        runtime_with_dups += len(dish_output)
    
    return runtime_with_dups

def load_pubchem_results():
    with open(PUBCHEM_RESULTS, encoding="utf-8") as f:
        return json.load(f)

print("=" * 60)
print("CONSISTENT COUNTING (WITH DUPLICATES PER DISH)")
print("=" * 60)

manual = load_manual_compounds()
fooddb = load_fooddb_vocab()
hkg = load_hkg_vocab()
runtime_with_dups = load_runtime_output_with_dups()
pubchem_data = load_pubchem_results()

combined_vocab = fooddb | hkg

# Build PubChem found set
pubchem_found = set()
for item in pubchem_data:
    if item["pubchem_found"]:
        pubchem_found.add(item["normalized"])

# Categorize manual compounds (with duplicates)
manual_in_fooddb_hkg = 0
manual_in_pubchem_only = 0
manual_true_artifacts = 0

for dish, compound in manual:
    norm = norm_compound_name(compound)
    if norm in combined_vocab:
        manual_in_fooddb_hkg += 1
    elif norm in pubchem_found:
        manual_in_pubchem_only += 1
    else:
        manual_true_artifacts += 1

print(f"\n--- MANUAL COMPOUNDS (WITH DUPLICATES) ---")
print(f"Total: {len(manual)}")
print(f"In FooDB/HKG: {manual_in_fooddb_hkg}")
print(f"In PubChem only: {manual_in_pubchem_only}")
print(f"True artifacts: {manual_true_artifacts}")

true_baseline = manual_in_fooddb_hkg + manual_in_pubchem_only
print(f"\nTRUE PHARMACOLOGICAL BASELINE: {true_baseline}")

print(f"\n--- RUNTIME OUTPUT ---")
print(f"Runtime output (with duplicates per dish): {runtime_with_dups}")

print(f"\n--- COMPARISON ---")
print(f"Baseline: {true_baseline}")
print(f"Runtime: {runtime_with_dups}")
print(f"Difference: {runtime_with_dups - true_baseline}")
