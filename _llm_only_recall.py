"""
Calculate non-circular recall using LLM-ONLY output (no NA seed).
This tests whether the LLM independently generates the baseline compounds.
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

def load_llm_only_output():
    """Load LLM-ONLY output (no NA seed) - what the LLM actually generated"""
    with open(NA_FILE, encoding="utf-8") as f:
        na_dishes = json.load(f)
    with open(LLM_CACHE, encoding="utf-8") as f:
        cache = json.load(f)
    
    llm_only_by_dish = {}
    for dish in na_dishes.keys():
        key = dish.lower()
        llm_part = cache.get(key, [])
        llm_only_by_dish[dish] = set(norm_compound_name(c) for c in llm_part)
    
    return llm_only_by_dish

def load_pubchem_results():
    with open(PUBCHEM_RESULTS, encoding="utf-8") as f:
        return json.load(f)

print("=" * 60)
print("NON-CIRCULAR RECALL (LLM-ONLY OUTPUT)")
print("=" * 60)

manual = load_manual_compounds()
fooddb = load_fooddb_vocab()
hkg = load_hkg_vocab()
llm_only_by_dish = load_llm_only_output()
pubchem_data = load_pubchem_results()

combined_vocab = fooddb | hkg

# Build PubChem found set
pubchem_found = set()
for item in pubchem_data:
    if item["pubchem_found"]:
        pubchem_found.add(item["normalized"])

# Identify baseline compounds (with dish context)
baseline_compounds = []
for dish, compound in manual:
    norm = norm_compound_name(compound)
    if norm in combined_vocab or norm in pubchem_found:
        baseline_compounds.append((dish, compound, norm))

print(f"\n--- BASELINE (pharmacologically canonicalized) ---")
print(f"Total baseline compounds: {len(baseline_compounds)}")

# Check which baseline compounds are recovered by LLM-ONLY output
recovered = []
missed = []

for dish, original, norm in baseline_compounds:
    if norm in llm_only_by_dish.get(dish, set()):
        recovered.append((dish, original, norm))
    else:
        missed.append((dish, original, norm))

print(f"\n--- LLM-ONLY RECALL ---")
print(f"Recovered by LLM (no NA seed): {len(recovered)}")
print(f"Missed by LLM: {len(missed)}")
print(f"LLM-only recall: {len(recovered)/len(baseline_compounds)*100:.1f}%")

print(f"\n--- MISSED BY LLM (but in baseline) ---")
for dish, original, norm in missed[:20]:
    source = "PubChem only" if norm in pubchem_found else "FooDB/HKG"
    print(f"  [{dish}] {original} ({source})")
if len(missed) > 20:
    print(f"  ... and {len(missed) - 20} more")

# Count LLM-only output
llm_only_with_dups = sum(len(compounds) for compounds in llm_only_by_dish.values())
llm_only_unique = len(set(c for compounds in llm_only_by_dish.values() for c in compounds))

print(f"\n--- LLM-ONLY OUTPUT ---")
print(f"LLM-only compounds (with duplicates per dish): {llm_only_with_dups}")
print(f"LLM-only unique compounds: {llm_only_unique}")
