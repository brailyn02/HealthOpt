"""
verify_smiles_v2.py
Cross-checks each SMILES against its label name using PubChem CID lookup.
Logic:
  - Extract (label, smiles) pairs from the file
  - Lookup SMILES in PubChem → get CID_smiles + canonical name
  - Lookup label text in PubChem → get CID_name
  - MATCH if CID_smiles == CID_name
  - MISMATCH if CIDs differ (wrong compound)
  - INVALID if SMILES not parseable by PubChem
  - NOT_FOUND if label name not found in PubChem (skip name check, report manually)
"""

import re
import time
import requests
import json

FILE = r"d:\23AIBox-DFinder\north_african_food_drug_interactions.txt"
REPORT = r"d:\23AIBox-DFinder\smiles_verification_v2_report.txt"
DELAY = 0.4  # seconds between PubChem calls

# ── extraction ───────────────────────────────────────────────────────────────

LABEL_RE = re.compile(r'SMILES\s*\(([^)]+)\)\s*:', re.IGNORECASE)
FORMULA_RE = re.compile(r'^[A-Z][a-z]?\d*([A-Z][a-z]?\d*)*[+\-]?\d*$')

def is_smiles(s):
    if not s or len(s) < 2:
        return False
    if FORMULA_RE.match(s) and '(' not in s and '=' not in s and '#' not in s:
        return False
    if s.endswith('...'):
        return False
    # must contain at least one SMILES character
    if not re.search(r'[=#@\[\]/\\+\-]|[a-z]|C|N|O|S|P|F|Cl|Br|I', s):
        return False
    return True

def extract_pairs(filepath):
    """Returns list of (line_no, label, smiles)"""
    pairs = []
    with open(filepath, encoding='utf-8') as f:
        lines = f.readlines()

    current_label = None
    current_label_line = None

    for i, raw in enumerate(lines, 1):
        # strip table borders
        inner = raw.strip().lstrip('|').rstrip('|').strip()

        # look for a label line
        m = LABEL_RE.search(inner)
        if m:
            current_label = m.group(1).strip()
            current_label_line = i
            continue

        if current_label:
            # next non-empty line after a label line is the SMILES
            candidate = inner.split('|')[0].strip()  # only col before any extra pipe
            if candidate and is_smiles(candidate):
                pairs.append((i, current_label, candidate))
                current_label = None
                current_label_line = None
            elif candidate:
                # not a smiles — reset
                current_label = None

    return pairs

# ── PubChem lookups ───────────────────────────────────────────────────────────

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

def cid_from_smiles(smiles):
    """Returns (cid, iupac_name, canonical_smiles) or raises."""
    url = f"{BASE}/compound/smiles/property/IUPACName,MolecularFormula,IsomericSMILES/JSON"
    try:
        r = requests.post(url, data={"smiles": smiles}, timeout=15)
        if r.status_code == 404:
            return None, None, None
        r.raise_for_status()
        props = r.json()["PropertyTable"]["Properties"][0]
        cid = props.get("CID")
        name = props.get("IUPACName", "")
        csmi = props.get("IsomericSMILES", "")
        return cid, name, csmi
    except Exception as e:
        return "ERROR", str(e), ""

def cid_from_name(name):
    """Returns first CID for a compound name, or None."""
    url = f"{BASE}/compound/name/{requests.utils.quote(name)}/cids/JSON"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        cids = r.json()["IdentifierList"]["CIDs"]
        return cids[0] if cids else None
    except Exception as e:
        return "ERROR"

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("Extracting (label, SMILES) pairs...")
    pairs = extract_pairs(FILE)
    print(f"  Found {len(pairs)} labeled SMILES entries.")

    # deduplicate by (label, smiles)
    seen = {}
    unique = []
    for line_no, label, smiles in pairs:
        key = (label.lower(), smiles)
        if key not in seen:
            seen[key] = line_no
            unique.append((line_no, label, smiles))
    print(f"  {len(unique)} unique (label, SMILES) pairs after dedup.")

    results = []
    total = len(unique)

    for idx, (line_no, label, smiles) in enumerate(unique, 1):
        print(f"  [{idx}/{total}] L{line_no} ({label}) ...", end=" ", flush=True)

        # 1. SMILES → CID
        cid_s, iupac, canon = cid_from_smiles(smiles)
        time.sleep(DELAY)

        if cid_s == "ERROR":
            status = "ERROR"
            note = iupac  # error message stored in iupac field
            results.append((line_no, label, smiles, status, cid_s, None, iupac, ""))
            print(f"ERROR: {note}")
            continue

        if cid_s is None:
            status = "INVALID"
            results.append((line_no, label, smiles, status, None, None, "", ""))
            print("INVALID (PubChem can't parse SMILES)")
            continue

        # 2. Name → CID
        cid_n = cid_from_name(label)
        time.sleep(DELAY)

        if cid_n == "ERROR":
            # can't check name; report smiles-only
            status = "SMILES_OK_NAME_LOOKUP_FAILED"
            note = f"CID_smiles={cid_s} ({iupac})"
            results.append((line_no, label, smiles, status, cid_s, None, iupac, ""))
            print(f"SMILES OK (CID={cid_s}) but name lookup failed")
            continue

        if cid_n is None:
            # label name not in PubChem (e.g. "K⁺", "Gelatinised Starch")
            status = "SMILES_OK_NAME_NOT_IN_PUBCHEM"
            results.append((line_no, label, smiles, status, cid_s, None, iupac, ""))
            print(f"SMILES OK (CID={cid_s} {iupac[:40]}) | name '{label}' not in PubChem")
            continue

        # 3. Compare CIDs
        if cid_s == cid_n:
            status = "MATCH"
        else:
            status = "MISMATCH"

        results.append((line_no, label, smiles, status, cid_s, cid_n, iupac, canon))
        icon = "✓" if status == "MATCH" else "✗ MISMATCH"
        print(f"{icon} CID_smiles={cid_s} CID_name={cid_n} | {iupac[:50]}")

    # ── write report ──────────────────────────────────────────────────────────
    counts = {}
    for r in results:
        counts[r[3]] = counts.get(r[3], 0) + 1

    with open(REPORT, 'w', encoding='utf-8') as out:
        out.write("SMILES Verification Report v2 — Name vs SMILES cross-check\n")
        out.write("=" * 70 + "\n\n")
        out.write("SUMMARY\n")
        for k, v in sorted(counts.items()):
            out.write(f"  {k:<40} {v}\n")
        out.write(f"  {'TOTAL':<40} {len(results)}\n\n")

        for status_filter in ["MISMATCH", "INVALID", "ERROR",
                               "SMILES_OK_NAME_NOT_IN_PUBCHEM",
                               "SMILES_OK_NAME_LOOKUP_FAILED", "MATCH"]:
            section = [r for r in results if r[3] == status_filter]
            if not section:
                continue
            out.write("=" * 70 + "\n")
            out.write(f"  {status_filter}  ({len(section)} entries)\n")
            out.write("=" * 70 + "\n")
            for line_no, label, smiles, status, cid_s, cid_n, iupac, canon in section:
                out.write(f"\n  Line   : {line_no}\n")
                out.write(f"  Label  : {label}\n")
                out.write(f"  SMILES : {smiles}\n")
                if cid_s:
                    out.write(f"  CID(S) : {cid_s}  →  {iupac}\n")
                if cid_n:
                    out.write(f"  CID(N) : {cid_n}\n")
                if canon:
                    out.write(f"  Canon  : {canon}\n")
                out.write("\n")

    print(f"\nDone. Report → {REPORT}")
    print("Summary:", counts)

if __name__ == "__main__":
    main()
