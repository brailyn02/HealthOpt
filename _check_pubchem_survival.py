"""
Check if the 33 PubChem-only compounds actually survive the vocabulary gate in runtime output.
If they're not in FooDB/HKG, the gate should drop them.
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
    """Load runtime output AFTER vocabulary gate (what actually flows through)"""
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
print("CHECKING PUBCHEM-ONLY COMPOUND SURVIVAL")
print("=" * 60)

fooddb = load_fooddb_vocab()
hkg = load_hkg_vocab()
runtime = load_runtime_output()
pubchem_data = load_pubchem_results()

combined_vocab = fooddb | hkg

# Get PubChem-only compounds
pubchem_only = set()
for item in pubchem_data:
    if item["pubchem_found"]:
        norm = item["normalized"]
        if norm not in combined_vocab:
            pubchem_only.add((item["dish"], item["original"], norm))

print(f"\nPubChem-only compounds (not in FooDB/HKG): {len(pubchem_only)}")

# Check which survive in runtime
survived = []
dropped = []

for dish, original, norm in pubchem_only:
    if norm in runtime:
        survived.append((dish, original, norm))
    else:
        dropped.append((dish, original, norm))

print(f"\n--- SURVIVAL AFTER VOCABULARY GATE ---")
print(f"Survived in runtime: {len(survived)}")
print(f"Dropped by gate: {len(dropped)}")

if survived:
    print(f"\n--- SURVIVED COMPOUNDS ---")
    for dish, original, norm in survived:
        print(f"  [{dish}] {original}")

if dropped:
    print(f"\n--- DROPPED COMPOUNDS ---")
    for dish, original, norm in dropped:
        print(f"  [{dish}] {original}")

print(f"\n--- CONCLUSION ---")
if len(survived) > 0:
    print(f"CRITICAL: {len(survived)} PubChem-only compounds survived the vocabulary gate.")
    print(f"This means they came from NA seed (bypassing gate) or the gate logic is not working as expected.")
else:
    print(f"All PubChem-only compounds were dropped by the vocabulary gate as expected.")
    print(f"This means my earlier 100% recall claim was circular - these compounds cannot be recovered.")
