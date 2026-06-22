"""
final_verify_v3.py — correct extractor for the 'SMILES (Label):' / <smiles> format.
Extracts every SMILES entry, looks up CID on PubChem, reports anything that
is INVALID (400/404) or maps to wrong CID for the 19 fixed compounds.
"""
import re, time, requests

FILE   = r"d:\23AIBox-DFinder\north_african_food_drug_interactions.txt"
REPORT = r"d:\23AIBox-DFinder\final_verify_v3_report.txt"
DELAY  = 0.30

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# Expected (label_keyword_lower, expected_cid)
EXPECTED = {
    "uric acid":          1175,
    "allicin":            65036,
    "carvone":            16724,
    "apigenin":           5280443,
    "eicosapentaenoic":   446284,
    "linoleic acid":      5280450,
    "alpha-linolenic":    5280934,
    "quercetin":          5280343,
    "benzo[a]pyrene":     9153,
    "benzo(a)pyrene":     9153,
    "sucrose":            5988,
    "6-gingerol":         442793,
    "sesamin":            72307,
    "lycopene":           446925,
    "beta-carotene":      5280489,
    "tripalmitin":        68441,
    "linalool":           6549,
    "capsaicin":          1548943,
    "curcumin":           969516,
    "piperine":           638024,
    "maltose":            6255,
}

def looks_like_smiles(s):
    s = s.strip()
    if not s or len(s) < 3:
        return False
    if any(c in s for c in [' ', '\t']):
        return False
    # reject separator lines (all dashes or underscores)
    if re.match(r'^[-_=*]+$', s):
        return False
    # must start with a SMILES-characteristic character
    if not re.match(r'^[CONHSPFBrIcnosph\(\[\\/@#]', s):
        return False
    # must have at least some organic-chemistry chars
    frac = sum(1 for c in s if c in 'CONHSPFBrIcnosph()[]@\\/=#%1234567890.+') / len(s)
    return frac > 0.75

def extract_col2(line):
    """Extract content of second column (index 2 in split-by-pipe)."""
    parts = line.split('|')
    if len(parts) >= 3:
        return parts[2].strip()
    return ''

def extract_pairs(path):
    """
    Returns list of (label, full_smiles) by parsing:
        | ... | SMILES (Label): |
        | ... | <smiles>        |
        (possible continuation lines with more SMILES chars)
    """
    pairs = []
    with open(path, encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        col2 = extract_col2(lines[i])
        # detect "SMILES (something):" header
        m = re.match(r'SMILES\s*[\(\[]?([^\):]+?)[\)\]]?\s*:', col2, re.IGNORECASE)
        if m:
            label = m.group(1).strip()
            # next line should be the SMILES
            if i + 1 < len(lines):
                smi = extract_col2(lines[i+1])
                if looks_like_smiles(smi) or (len(smi) > 5 and not ' ' in smi):
                    full_smi = smi
                    j = i + 2
                    # continuation lines (same pattern, fragment continues)
                    while j < len(lines):
                        cont = extract_col2(lines[j])
                        # stop at separator / empty / label lines
                        if (not cont or re.match(r'^[-_=*]+$', cont) or
                                ' ' in cont or re.match(r'[A-Za-z].*:', cont)):
                            break
                        if looks_like_smiles(cont):
                            full_smi += cont
                            j += 1
                        else:
                            break
                    pairs.append((label, full_smi))
                    i = j
                    continue
        i += 1
    return pairs

def cid_from_smiles(smiles):
    url = f"{BASE}/compound/smiles/property/IUPACName,MolecularFormula/JSON"
    try:
        r = requests.post(url, data={"smiles": smiles}, timeout=20)
        if r.status_code == 404:
            return None, "NOT_FOUND", ""
        if r.status_code not in (200, 201):
            return None, f"HTTP_{r.status_code}", ""
        p = r.json()["PropertyTable"]["Properties"][0]
        return p.get("CID"), "OK", p.get("IUPACName", "")[:70]
    except Exception as e:
        return None, "EXC", str(e)[:60]

# ─── main ─────────────────────────────────────────────────────────────────────
pairs = extract_pairs(FILE)
print(f"Extracted {len(pairs)} (label, SMILES) pairs.\n")

# deduplicate
seen = {}
for lbl, smi in pairs:
    seen[(lbl.lower(), smi)] = (lbl, smi)
unique = sorted(seen.values(), key=lambda x: x[0].lower())
print(f"Unique: {len(unique)}\n")

results = []
ok = bad = other = 0

for label, smi in unique:
    ll = label.lower()
    expected_cid = None
    for kw, ecid in EXPECTED.items():
        if kw in ll:
            expected_cid = ecid
            break

    cid, status, iupac = cid_from_smiles(smi)
    time.sleep(DELAY)

    smi_short = smi[:55]

    if status != "OK" or cid is None:
        verdict = f"✗ INVALID ({status})"
        bad += 1
    elif expected_cid is not None:
        if cid == expected_cid:
            verdict = "✓ MATCH"
            ok += 1
        else:
            verdict = f"✗ MISMATCH got={cid} exp={expected_cid}"
            bad += 1
    else:
        verdict = f"  OK  CID={cid}"
        other += 1

    line = f"{verdict:<40} | {label:<35} | {smi_short}"
    results.append((verdict, label, cid, iupac, smi_short))
    print(line)

summary = (f"\nSUMMARY: {ok} targeted MATCH, {bad} FAIL/INVALID/MISMATCH, "
           f"{other} non-targeted OK\n"
           f"Total unique SMILES: {len(unique)}")
print(summary)

with open(REPORT, 'w', encoding='utf-8') as f:
    f.write("Final SMILES Verification v3\n")
    f.write("="*120 + "\n\n")
    f.write(f"{'Verdict':<40} | {'Label':<35} | {'CID':>8} | {'IUPAC Name':<70} | SMILES\n")
    f.write("-"*120 + "\n")
    for v, lbl, cid, iupac, smi in results:
        f.write(f"{v:<40} | {lbl:<35} | {str(cid or ''):>8} | {iupac:<70} | {smi}\n")
    f.write("\n" + summary + "\n")

print(f"\nReport → {REPORT}")
