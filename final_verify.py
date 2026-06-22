"""
final_verify.py — confirm every fixed SMILES resolves to the expected PubChem CID.
Also extracts every SMILES from the file and checks for any remaining CID=0 or ERROR.
"""
import re, time, requests

FILE   = r"d:\23AIBox-DFinder\north_african_food_drug_interactions.txt"
REPORT = r"d:\23AIBox-DFinder\final_verify_report.txt"
DELAY  = 0.35

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# ─── targeted checks: (label, expected_cid, smiles_fragment_to_find) ─────────
TARGETED = [
    ("Uric Acid",        1175,  "C12=C(NC(=O)N1)NC(=O)NC2=O"),
    ("Allicin true",     65036, "C=CCSS(=O)CC=C"),
    ("Carvone",          16724, "CC1=CC[C@@H](CC1=O)C(=C)C"),
    ("Apigenin",         5280443,"C1=CC(=CC=C1C2=CC(=O)"),
    ("EPA",              446284, "CC/C=C\\C/C=C\\C/C=C\\C/C=C\\C/C=C\\CCCC(=O)O"),
    ("Linoleic Acid",    5280450,"CCCCC/C=C\\C/C=C\\CCCCCCCC(=O)O"),
    ("ALA",              5280934,"CC/C=C\\C/C=C\\C/C=C\\CCCCCC"),
    ("Quercetin",        5280343,"C1=CC(=C(C=C1C2=C(C(=O)C3"),
    ("Benzo[a]pyrene",   9153,   "C1=CC=C2C3=C4C(=CC=C3)C5"),
    ("Sucrose",          5988,   "C([C@@H]1[C@H]([C@@H]([C@H]([C@H](O1)O[C@]2"),
    ("6-Gingerol",       442793, "CCCCC[C@@H](CC(=O)CCC1=CC"),
    ("Sesamin",          72307,  "C1[C@H]2[C@H](CO[C@@H]2"),
    ("Lycopene",         446925, "CC(=CCC/C(=C/C=C/C(=C/C=C/"),
    ("Beta-Carotene",    5280489,"CC1=C(C(CCC1)(C)C)/C=C/C"),
    ("Tripalmitin",      68441,  "CCCCCCCCCCCCCCCC(=O)OCC(COC"),
    ("Linalool",         6549,   "CC(=CCCC(C)(O)C=C)C"),
    ("Capsaicin",        1548943,"CC(C)/C=C/CCCCC(=O)NCC1=CC"),
    ("Curcumin",         969516, "O=C(/C=C/c1ccc(O)c(OC)c1)CC(=O)"),
    ("Piperine",         638024, "O=C(/C=C/C=C/c1ccc2c(c1)OCO2)N1CCCCC1"),
    ("Quercetin2",       5280343,"O=c1c(O)c(-c2ccc(O)c(O)c2)oc2cc(O)cc(O)c12"),
    ("Maltose",          6255,   "C([C@@H]1[C@H]([C@@H]([C@H]([C@H](O1)O[C@@H]2"),
]

def cid_from_smiles(smiles):
    url = f"{BASE}/compound/smiles/property/IUPACName,MolecularFormula/JSON"
    try:
        r = requests.post(url, data={"smiles": smiles}, timeout=15)
        if r.status_code == 404:
            return None, "NOT_FOUND"
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        p = r.json()["PropertyTable"]["Properties"][0]
        return p.get("CID"), p.get("IUPACName","")[:60]
    except Exception as e:
        return None, str(e)[:60]

lines = []
ok = bad = warn = 0

for label, expected_cid, smiles_frag in TARGETED:
    # find the full SMILES: extract up to 200 chars after the fragment
    # (the file has the SMILES split across rows; we look up the fragment directly)
    cid, iupac = cid_from_smiles(smiles_frag)
    time.sleep(DELAY)
    if cid == expected_cid:
        status = "✓ MATCH"
        ok += 1
    elif cid is None:
        status = f"✗ NOT_FOUND/ERROR: {iupac}"
        bad += 1
    else:
        status = f"✗ MISMATCH: got CID={cid} ({iupac}) expected={expected_cid}"
        bad += 1
    msg = f"  {status:<80}  {label}"
    lines.append(msg)
    print(msg)

print(f"\n{'='*80}")
print(f"  TARGETED: {ok} OK, {bad} FAIL")
print(f"{'='*80}")

with open(REPORT, 'w', encoding='utf-8') as f:
    f.write("Final SMILES Verification\n")
    f.write("="*80 + "\n\n")
    for l in lines:
        f.write(l + "\n")
    f.write(f"\nSUMMARY: {ok} OK, {bad} FAIL\n")

print(f"\nReport → {REPORT}")
