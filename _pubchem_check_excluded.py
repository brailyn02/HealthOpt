"""
Check excluded compounds against PubChem API to identify real compounds vs artifacts.
PubChem PUG REST API: https://pubchem.ncbi.nlm.nih.gov/rest/pug/
"""
import json
import urllib.request
import urllib.parse
import time
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
            all_manual.append((dish, c))
    return all_manual

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
    """
    Query PubChem PUG REST for compound information.
    Returns dict with 'found' (bool), 'cid' (int if found), 'iupac_name' (str if found)
    """
    try:
        # Try name search first
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{urllib.parse.quote(compound_name)}/cids/JSON"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if "IdentifierList" in data and "CID" in data["IdentifierList"]:
                cid = data["IdentifierList"]["CID"][0]
                # Get IUPAC name for verification
                iupac = None
                try:
                    props_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/IUPACName/JSON"
                    req2 = urllib.request.Request(props_url, headers={"Accept": "application/json"})
                    with urllib.request.urlopen(req2, timeout=10) as resp2:
                        props = json.loads(resp2.read())
                        if "PropertyTable" in props and "Properties" in props["PropertyTable"] and len(props["PropertyTable"]["Properties"]) > 0:
                            iupac = props["PropertyTable"]["Properties"][0].get("IUPACName")
                except Exception:
                    pass
                return {"found": True, "cid": cid, "iupac_name": iupac}
    except Exception as e:
        pass
    return {"found": False, "cid": None, "iupac_name": None}

print("=" * 60)
print("PUBCHEM VALIDATION OF EXCLUDED COMPOUNDS")
print("=" * 60)

manual = load_manual_compounds()
fooddb = load_fooddb_vocab()
hkg = load_hkg_vocab()
combined_vocab = fooddb | hkg

# Get excluded compounds
excluded = []
for dish, compound in manual:
    norm = norm_compound_name(compound)
    if norm not in combined_vocab:
        excluded.append((dish, compound, norm))

print(f"Checking {len(excluded)} excluded compounds against PubChem...")
print("(This may take a minute due to API rate limiting)\n")

results = []
pubchem_found = []
pubchem_not_found = []

for i, (dish, original, norm) in enumerate(excluded, 1):
    print(f"[{i}/{len(excluded)}] Checking: {original}")
    pubchem_result = check_pubchem(norm)
    results.append({
        "dish": dish,
        "original": original,
        "normalized": norm,
        "pubchem_found": pubchem_result["found"],
        "pubchem_cid": pubchem_result["cid"],
        "pubchem_iupac": pubchem_result["iupac_name"]
    })
    
    if pubchem_result["found"]:
        pubchem_found.append((dish, original, norm, pubchem_result["cid"], pubchem_result["iupac_name"]))
        print(f"  ✓ Found in PubChem (CID: {pubchem_result['cid']}, IUPAC: {pubchem_result['iupac_name']})")
    else:
        pubchem_not_found.append((dish, original, norm))
        print(f"  ✗ Not found in PubChem")
    
    # Rate limiting
    time.sleep(0.1)

print(f"\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Total excluded compounds: {len(excluded)}")
print(f"Found in PubChem (real compounds): {len(pubchem_found)}")
print(f"Not found in PubChem (likely artifacts): {len(pubchem_not_found)}")

print(f"\n--- REAL COMPOUNDS FOUND IN PUBCHEM ---")
for dish, original, norm, cid, iupac in pubchem_found:
    print(f"  [{dish}] {original} -> CID: {cid}, IUPAC: {iupac}")

print(f"\n--- LIKELY ARTIFACTS (NOT IN PUBCHEM) ---")
for dish, original, norm in pubchem_not_found:
    print(f"  [{dish}] {original}")

# Save results
output_file = ROOT / "ablation_results" / "pubchem_excluded_validation.json"
output_file.parent.mkdir(exist_ok=True)
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\nResults saved to: {output_file}")
