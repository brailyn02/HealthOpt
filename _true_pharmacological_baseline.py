"""
Calculate true recall on pharmacologically meaningful baseline:
Manual compounds that exist in FooDB/HKG OR PubChem (independent validation)
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

def load_runtime_output():
    with open(NA_FILE, encoding="utf-8") as f:
        na_dishes = json.load(f)
    with open(LLM_CACHE, encoding="utf-8") as f:
        cache = json.load(f)
    runtime_output = set()
    for dish, na_compounds in na_dishes.items():
        key = dish.lower()
        for c in na_compounds:
            runtime_output.add(norm_compound_name(c))
        llm_part = cache.get(key, [])
        for c in llm_part:
            runtime_output.add(norm_compound_name(c))
    return runtime_output

def load_pubchem_results():
    with open(PUBCHEM_RESULTS, encoding="utf-8") as f:
        return json.load(f)

print("=" * 60)
print("TRUE PHARMACOLOGICAL BASELINE (FooDB/HKG + PubChem)")
print("=" * 60)

manual = load_manual_compounds()
fooddb = load_fooddb_vocab()
hkg = load_hkg_vocab()
runtime = load_runtime_output()
pubchem_data = load_pubchem_results()

combined_vocab = fooddb | hkg

# Build PubChem found set
pubchem_found = set()
for item in pubchem_data:
    if item["pubchem_found"]:
        pubchem_found.add(item["normalized"])

# Categorize manual compounds
manual_in_fooddb_hkg = []
manual_in_pubchem_only = []
manual_true_artifacts = []

for dish, compound in manual:
    norm = norm_compound_name(compound)
    if norm in combined_vocab:
        manual_in_fooddb_hkg.append((dish, compound, norm))
    elif norm in pubchem_found:
        manual_in_pubchem_only.append((dish, compound, norm))
    else:
        manual_true_artifacts.append((dish, compound, norm))

print(f"\n--- MANUAL COMPOUND CATEGORIZATION ---")
print(f"In FooDB/HKG: {len(manual_in_fooddb_hkg)}")
print(f"In PubChem only (not FooDB/HKG): {len(manual_in_pubchem_only)}")
print(f"True artifacts (not in any database): {len(manual_true_artifacts)}")

# True pharmacological baseline
true_baseline = manual_in_fooddb_hkg + manual_in_pubchem_only
print(f"\nTRUE PHARMACOLOGICAL BASELINE: {len(true_baseline)} compounds")

# Calculate recall on true baseline
true_baseline_recovered = []
true_baseline_missed = []

for dish, compound, norm in true_baseline:
    if norm in runtime:
        true_baseline_recovered.append((dish, compound, norm))
    else:
        true_baseline_missed.append((dish, compound, norm))

print(f"\n--- RECALL ON TRUE PHARMACOLOGICAL BASELINE ---")
print(f"Recovered: {len(true_baseline_recovered)}")
print(f"Missed: {len(true_baseline_missed)}")
print(f"Recall: {len(true_baseline_recovered)/len(true_baseline)*100:.1f}%")

print(f"\n--- MISSED PHARMACOLOGICAL COMPOUNDS ---")
for dish, compound, norm in true_baseline_missed:
    source = "PubChem only" if norm in pubchem_found else "FooDB/HKG"
    print(f"  [{dish}] {compound} ({source})")

print(f"\n--- SUMMARY ---")
print(f"Original manual count (with duplicates): {len(manual)}")
print(f"True pharmacological baseline: {len(true_baseline)}")
print(f"True artifacts excluded: {len(manual_true_artifacts)}")
print(f"Recall on true baseline: {len(true_baseline_recovered)/len(true_baseline)*100:.1f}%")
