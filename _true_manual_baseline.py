"""
Calculate recall on cleaned manual baseline:
Only count manual compounds that exist in FooDB/HKG (pharmacologically canonicalized)
Exclude annotation artifacts like "butter emulsion", "braidedlattice", etc.
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

def norm_compound_name(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"\([^)]*\)", "", s)
    s = s.replace("/", " ")
    s = s.replace("+", " ")
    s = s.replace("_", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def load_manual_compounds():
    """Return list with duplicates (thesis methodology)"""
    with open(NA_FILE, encoding="utf-8") as f:
        data = json.load(f)
    all_manual = []
    for dish, compounds in data.items():
        for c in compounds:
            all_manual.append(norm_compound_name(c))
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
    """Load runtime output = NA seed + LLM cache (actual pipeline behavior)"""
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

print("=" * 60)
print("TRUE MANUAL BASELINE: DATABASE-COVERED COMPOUNDS ONLY")
print("=" * 60)

manual = load_manual_compounds()
fooddb = load_fooddb_vocab()
hkg = load_hkg_vocab()
runtime = load_runtime_output()

combined_vocab = fooddb | hkg

# Filter manual to only database-covered compounds
manual_cleaned = [c for c in manual if c in combined_vocab]
manual_artifacts = [c for c in manual if c not in combined_vocab]

print(f"\nOriginal manual compounds (with duplicates): {len(manual)}")
print(f"Manual compounds IN FooDB/HKG (cleaned baseline): {len(manual_cleaned)}")
print(f"Manual artifacts (not in databases): {len(manual_artifacts)}")

# Calculate recall on cleaned baseline
manual_cleaned_recovered = [c for c in manual_cleaned if c in runtime]
manual_cleaned_missed = [c for c in manual_cleaned if c not in runtime]

print(f"\n--- RECALL ON CLEANED BASELINE ---")
print(f"Manual database-covered compounds recovered: {len(manual_cleaned_recovered)}")
print(f"Manual database-covered compounds missed: {len(manual_cleaned_missed)}")
print(f"Recall on cleaned baseline: {len(manual_cleaned_recovered)/len(manual_cleaned)*100:.1f}%")

# Show examples
print(f"\n--- ARTIFACT EXAMPLES (excluded from baseline) ---")
for c in sorted(set(manual_artifacts))[:15]:
    print(f"  - {c}")

print(f"\n--- MISSED DATABASE-COVERED COMPOUNDS ---")
for c in sorted(set(manual_cleaned_missed))[:15]:
    print(f"  - {c}")
