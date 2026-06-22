"""
Check unverified LLM compounds against PubChem to see if they're real compounds
not in FooDB/HKG (database gap) vs hallucinations.
"""
import json
import re
import urllib.request
import urllib.parse
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
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

def is_valid_food_name(name: str) -> bool:
    name = name.lower()
    if "_unknown_" in name or "_medium_" in name or "_high_" in name:
        return False
    if "interaction" in name or "signal" in name or "detected" in name:
        return False
    if "narrative" in name or "v16" in name:
        return False
    if re.match(r"^[a-z]+_[a-z]+_(low|medium|high)_", name):
        return False
    return True

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

def check_pubchem(compound_name: str) -> dict:
    try:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{urllib.parse.quote(compound_name)}/cids/JSON"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if "IdentifierList" in data and "CID" in data["IdentifierList"]:
                cid = data["IdentifierList"]["CID"][0]
                return {"found": True, "cid": cid}
    except Exception as e:
        pass
    return {"found": False, "cid": None}

print("=" * 60)
print("PUBCHEM VERIFICATION OF UNVERIFIED LLM COMPOUNDS")
print("=" * 60)

fooddb = load_fooddb_vocab()
hkg = load_hkg_vocab()
combined_vocab = fooddb | hkg

with open(LLM_CACHE, encoding="utf-8") as f:
    llm_cache = json.load(f)

valid_cache = {k: v for k, v in llm_cache.items() if is_valid_food_name(k) and not k.endswith(":tiers")}

# Collect unverified compounds
unverified_compounds = set()
for food, compounds in valid_cache.items():
    for c in compounds:
        norm = norm_compound_name(c)
        if norm not in combined_vocab:
            unverified_compounds.add((food, c, norm))

print(f"\nUnverified compounds (not in FooDB/HKG): {len(unverified_compounds)}")

# Check against PubChem
pubchem_found = []
pubchem_not_found = []

for i, (food, original, norm) in enumerate(sorted(unverified_compounds, key=lambda x: x[2]), 1):
    print(f"[{i}/{len(unverified_compounds)}] Checking: {original}")
    result = check_pubchem(norm)
    if result["found"]:
        pubchem_found.append((food, original, norm, result["cid"]))
        print(f"  ✓ Found in PubChem (CID: {result['cid']})")
    else:
        pubchem_not_found.append((food, original, norm))
        print(f"  ✗ Not found in PubChem")
    time.sleep(0.1)

print(f"\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Total unverified compounds: {len(unverified_compounds)}")
print(f"Found in PubChem (real compounds, database gap): {len(pubchem_found)}")
print(f"Not found in PubChem (likely hallucinations): {len(pubchem_not_found)}")

print(f"\n--- REAL COMPOUNDS (DATABASE GAP) ---")
for food, original, norm, cid in pubchem_found:
    print(f"  [{food}] {original} -> CID: {cid}")

print(f"\n--- LIKELY HALLUCINATIONS ---")
for food, original, norm in pubchem_not_found:
    print(f"  [{food}] {original}")
