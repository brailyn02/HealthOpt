"""
Three-way breakdown of the NA dish compound gap:
1. Manual compounds that exist in FooDB/HKG
2. Of those, how many the LLM actually generated
3. This separates LLM misses from database coverage gaps
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
    """Return list with duplicates (thesis methodology: 292 total)"""
    with open(NA_FILE, encoding="utf-8") as f:
        data = json.load(f)
    all_manual = []  # List, not set - preserve duplicates
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

def load_llm_output():
    """Load runtime output = NA seed + LLM cache (actual pipeline behavior)"""
    with open(NA_FILE, encoding="utf-8") as f:
        na_dishes = json.load(f)
    
    with open(LLM_CACHE, encoding="utf-8") as f:
        cache = json.load(f)
    
    runtime_output = set()
    for dish, na_compounds in na_dishes.items():
        key = dish.lower()
        # NA seed compounds (always included)
        for c in na_compounds:
            runtime_output.add(norm_compound_name(c))
        # LLM-generated part (from cache)
        llm_part = cache.get(key, [])
        for c in llm_part:
            runtime_output.add(norm_compound_name(c))
    
    return runtime_output

print("=" * 60)
print("THREE-WAY BREAKDOWN OF NA DISH COMPOUND GAP")
print("=" * 60)

manual = load_manual_compounds()
fooddb = load_fooddb_vocab()
hkg = load_hkg_vocab()
llm = load_llm_output()

combined_vocab = fooddb | hkg

print(f"\nManual compounds (total with duplicates): {len(manual)}")
print(f"FooDB vocabulary size: {len(fooddb)}")
print(f"HKG vocabulary size: {len(hkg)}")
print(f"Combined vocab (FooDB ∪ HKG): {len(combined_vocab)}")
print(f"LLM generated compounds: {len(llm)}")

# Breakdown 1: Manual compounds in databases
manual_in_db = [c for c in manual if c in combined_vocab]
manual_not_in_db = [c for c in manual if c not in combined_vocab]

print(f"\n--- BREAKDOWN 1: DATABASE COVERAGE ---")
print(f"Manual compounds IN FooDB/HKG: {len(manual_in_db)} ({len(manual_in_db)/len(manual)*100:.1f}%)")
print(f"Manual compounds NOT in FooDB/HKG: {len(manual_not_in_db)} ({len(manual_not_in_db)/len(manual)*100:.1f}%)")

# Breakdown 2: Of manual compounds IN database, how many did LLM generate?
manual_in_db_and_llm = [c for c in manual_in_db if c in llm]
manual_in_db_not_llm = [c for c in manual_in_db if c not in llm]

print(f"\n--- BREAKDOWN 2: LLM RECALL ON DATABASE-COVERED COMPOUNDS ---")
print(f"Manual compounds IN database AND LLM generated: {len(manual_in_db_and_llm)}")
print(f"Manual compounds IN database BUT LLM missed: {len(manual_in_db_not_llm)}")
print(f"LLM recall on database-covered compounds: {len(manual_in_db_and_llm)/len(manual_in_db)*100:.1f}%")

# Breakdown 3: Manual compounds NOT in database (pure database gap)
print(f"\n--- BREAKDOWN 3: PURE DATABASE GAP ---")
print(f"Manual compounds NOT in any database: {len(manual_not_in_db)}")
print(f"These are 100% database coverage issues (LLM cannot be blamed)")

# Summary
print(f"\n--- SUMMARY ---")
print(f"Total manual compounds (with duplicates): {len(manual)}")
print(f"  - Database gap (not in FooDB/HKG): {len(manual_not_in_db)} ({len(manual_not_in_db)/len(manual)*100:.1f}%)")
print(f"  - LLM gap (in database but missed): {len(manual_in_db_not_llm)} ({len(manual_in_db_not_llm)/len(manual)*100:.1f}%)")
print(f"  - Successfully recovered: {len(manual_in_db_and_llm)} ({len(manual_in_db_and_llm)/len(manual)*100:.1f}%)")

# Show examples of compounds in each category
print(f"\n--- EXAMPLES ---")
print(f"Database gap examples (not in FooDB/HKG):")
for c in sorted(set(manual_not_in_db))[:10]:
    print(f"  - {c}")

print(f"\nLLM gap examples (in database but missed by LLM):")
for c in sorted(set(manual_in_db_not_llm))[:10]:
    print(f"  - {c}")
