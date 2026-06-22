"""
Extract the 122 excluded compounds and check them against independent sources
to distinguish genuine database gaps from annotation artifacts.
"""
import json
import pandas as pd
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
NA_FILE = ROOT / "data" / "na_dish_compounds.json"
FOODB_FILE = ROOT / "Compound.csv"
HKG_FILE = ROOT / "data" / "processed_hkg" / "hkg_food_compound_edges.csv"

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
            all_manual.append((dish, c))  # Keep dish context
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

manual = load_manual_compounds()
fooddb = load_fooddb_vocab()
hkg = load_hkg_vocab()
combined_vocab = fooddb | hkg

# Separate excluded compounds
excluded = []
for dish, compound in manual:
    norm = norm_compound_name(compound)
    if norm not in combined_vocab:
        excluded.append((dish, compound, norm))

print(f"Total excluded compounds: {len(excluded)}")
print(f"\n--- EXCLUDED COMPOUNDS WITH DISH CONTEXT ---")
for dish, original, norm in sorted(excluded, key=lambda x: x[2]):
    print(f"  [{dish}] {original} -> {norm}")

# Categorize by pattern
print(f"\n--- PATTERN ANALYSIS ---")
patterns = {
    "descriptive": [],
    "measurement": [],
    "chemical_formula": [],
    "plausible_compound": []
}

for dish, original, norm in excluded:
    if any(x in norm for x in ["emulsion", "lattice", "matrix", "sponge", "friable", "coated", "laminated", "gelatinised", "braided"]):
        patterns["descriptive"].append((dish, original))
    elif any(x in norm for x in ["mm", "co2", "na", "mg2", "co", "co2"]):
        patterns["measurement"].append((dish, original))
    elif re.match(r"^[a-z]+\s+[a-z]+$", norm) and len(norm.split()) == 2:
        patterns["plausible_compound"].append((dish, original))
    else:
        patterns["chemical_formula"].append((dish, original))

for category, items in patterns.items():
    print(f"\n{category.upper()} ({len(items)}):")
    for dish, original in items[:10]:
        print(f"  [{dish}] {original}")
    if len(items) > 10:
        print(f"  ... and {len(items) - 10} more")
