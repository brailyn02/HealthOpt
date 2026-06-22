"""
final_verify_v2.py — extract complete SMILES from file, look up CIDs, report mismatches.
Handles multi-line SMILES rows in the table format used in the file.
"""
import re, time, requests

FILE   = r"d:\23AIBox-DFinder\north_african_food_drug_interactions.txt"
REPORT = r"d:\23AIBox-DFinder\final_verify_v2_report.txt"
DELAY  = 0.35

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# Expected (label_substring, expected_cid) for the 19 fixed compounds
EXPECTED = {
    "uric acid":      1175,
    "allicin":        65036,
    "carvone":        16724,
    "apigenin":       5280443,
    "eicosapentaenoic": 446284,   # EPA
    "linoleic acid":  5280450,
    "alpha-linolenic": 5280934,   # ALA
    "quercetin":      5280343,
    "benzo[a]pyrene": 9153,
    "sucrose":        5988,
    "6-gingerol":     442793,
    "sesamin":        72307,
    "lycopene":       446925,
    "beta-carotene":  5280489,
    "tripalmitin":    68441,
    "linalool":       6549,
    "capsaicin":      1548943,
    "curcumin":       969516,
    "piperine":       638024,
    "maltose":        6255,
}

# ─── parse file → {label: [smiles1, smiles2, ...]} ───────────────────────────
def looks_like_smiles(s):
    s = s.strip()
    if not s or ' ' in s:
        return False
    if '|' in s or '+' == s:
        return False
    if all(c in '-=+|' for c in s):
        return False
    frac = sum(1 for c in s if c in 'CONHSPFBrIcnosph()[]@\\/#%=1234567890.') / max(len(s),1)
    return frac > 0.75

def extract_label_smiles(path):
    """
    Returns list of (label, full_smiles) pairs from every | label | smiles | row.
    Joins continuation SMILES lines.
    """
    pairs = []
    with open(path, encoding='utf-8') as f:
        raw = f.readlines()

    i = 0
    while i < len(raw):
        line = raw[i].rstrip('\n')
        parts = [p.strip() for p in line.split('|')]
        # table row: | ... | label | smiles |
        if len(parts) >= 4:
            label = parts[1].strip()
            col2  = parts[2].strip() if len(parts) > 2 else ''
            # is col2 a SMILES?
            if looks_like_smiles(col2) and label and not looks_like_smiles(label):
                # possible continuation on next line(s) — same pattern but empty label
                full_smiles = col2
                while i+1 < len(raw):
                    nxt = raw[i+1].rstrip('\n')
                    nparts = [p.strip() for p in nxt.split('|')]
                    if len(nparts) >= 3:
                        nlabel = nparts[1].strip()
                        ncol2  = nparts[2].strip()
                        # continuation: empty first col, empty label, looks like smiles frag
                        if nlabel == '' and looks_like_smiles(ncol2):
                            full_smiles += ncol2
                            i += 1
                        else:
                            break
                    else:
                        break
                pairs.append((label, full_smiles))
        i += 1
    return pairs

def cid_from_smiles(smiles):
    url = f"{BASE}/compound/smiles/property/IUPACName,MolecularFormula/JSON"
    try:
        r = requests.post(url, data={"smiles": smiles}, timeout=20)
        if r.status_code == 404:
            return None, "NOT_FOUND", ""
        if r.status_code != 200:
            return None, f"HTTP_{r.status_code}", ""
        p = r.json()["PropertyTable"]["Properties"][0]
        return p.get("CID"), "OK", p.get("IUPACName","")[:70]
    except Exception as e:
        return None, "EXC", str(e)[:60]

# ─── main ─────────────────────────────────────────────────────────────────────
pairs = extract_label_smiles(FILE)
print(f"Extracted {len(pairs)} (label, SMILES) pairs from file.\n")

# deduplicate by (label, smiles)
seen = {}
for label, smi in pairs:
    key = (label.lower(), smi)
    seen[key] = (label, smi)
unique_pairs = list(seen.values())
print(f"Unique pairs: {len(unique_pairs)}\n")

results = []
ok = bad = skip = 0

for label, smi in sorted(unique_pairs, key=lambda x: x[0].lower()):
    label_lower = label.lower()
    expected_cid = None
    for kw, ecid in EXPECTED.items():
        if kw in label_lower:
            expected_cid = ecid
            break

    cid, status, iupac = cid_from_smiles(smi)
    time.sleep(DELAY)

    if expected_cid is not None:
        if cid == expected_cid:
            verdict = "✓ MATCH"
            ok += 1
        elif status != "OK" or cid is None:
            verdict = f"✗ LOOKUP_FAIL ({status})"
            bad += 1
        else:
            verdict = f"✗ MISMATCH got={cid}"
            bad += 1
    else:
        if status == "OK" and cid:
            verdict = f"  OK  CID={cid}"
        elif "NOT_FOUND" in status or "HTTP_4" in status:
            verdict = f"  INVALID/UNKNOWN ({status})"
            bad += 1
        else:
            verdict = f"  {status}"
        skip += 1

    line = f"{verdict:<35} {label:<40} CID={cid} | {iupac}"
    results.append(line)
    print(line)

summary = f"\nSUMMARY: {ok} targeted MATCH, {bad} FAIL/MISMATCH, {skip} untargeted"
print(summary)

with open(REPORT, 'w', encoding='utf-8') as f:
    f.write("Final SMILES Verification v2\n")
    f.write("="*100 + "\n\n")
    for l in results:
        f.write(l + "\n")
    f.write(summary + "\n")

print(f"\nReport → {REPORT}")
