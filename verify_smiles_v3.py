"""
verify_smiles_v3.py
Robust extractor: handles SMILES that span multiple table rows.
Cross-checks each (label, smiles) via PubChem CID comparison:
  - CID from SMILES == CID from compound name  → MATCH
  - CIDs differ                               → MISMATCH (wrong compound)
  - SMILES not parseable                       → INVALID
  - Name not in PubChem                        → SMILES_OK; manual check
"""

import re
import time
import requests

FILE   = r"d:\23AIBox-DFinder\north_african_food_drug_interactions.txt"
REPORT = r"d:\23AIBox-DFinder\smiles_verification_v3_report.txt"
DELAY  = 0.4  # seconds between PubChem calls

# ── helpers ───────────────────────────────────────────────────────────────────

LABEL_RE = re.compile(r'SMILES\s*\(([^)]+)\)\s*:?\s*(.*)', re.IGNORECASE)

def looks_like_smiles_fragment(text):
    """
    A SMILES continuation line has NO spaces and contains at least one
    SMILES-specific character or organic element.
    """
    if not text or ' ' in text:
        return False
    if text == '|' or re.match(r'^[-|=]+$', text):
        return False
    # must have at least one atom or SMILES symbol
    return bool(re.search(r'[CNOSPFIcnos=#@\[\]\(\)/\\+\-]', text))

def extract_pairs(filepath):
    """
    Returns list of (first_line_no, label, full_smiles).
    Handles:
      - "SMILES (Label):" on its own line, SMILES on next line(s)
      - "SMILES (Label): <smiles>" all on one line, with continuation
    """
    # --- Step 1: pull column 2 from every table row ---
    col2_rows = []   # (line_no, col2_text)
    with open(filepath, encoding='utf-8') as f:
        for lineno, raw in enumerate(f, 1):
            parts = raw.split('|')
            if len(parts) >= 4:
                col2 = parts[2].strip()
                col2_rows.append((lineno, col2))

    # --- Step 2: scan for SMILES labels and collect continuations ---
    pairs = []
    i = 0
    while i < len(col2_rows):
        line_no, text = col2_rows[i]
        m = LABEL_RE.match(text)
        if m:
            label      = m.group(1).strip()
            smi_start  = m.group(2).strip()

            # collect any continuation lines (no spaces, SMILES chars)
            smi_parts  = [smi_start] if smi_start else []
            j = i + 1
            while j < len(col2_rows):
                _, nxt = col2_rows[j]
                if looks_like_smiles_fragment(nxt):
                    smi_parts.append(nxt)
                    j += 1
                else:
                    break

            full_smiles = ''.join(smi_parts).strip()
            if full_smiles:
                pairs.append((line_no, label, full_smiles))
            i = j
        else:
            i += 1

    return pairs

# ── PubChem ───────────────────────────────────────────────────────────────────

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

def cid_from_smiles(smiles):
    """Returns (cid, iupac_name) or (None,None) if invalid, ('ERROR',msg) on failure."""
    url = f"{BASE}/compound/smiles/property/IUPACName,MolecularFormula/JSON"
    try:
        r = requests.post(url, data={"smiles": smiles}, timeout=15)
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        props = r.json()["PropertyTable"]["Properties"][0]
        return props.get("CID"), props.get("IUPACName", "")
    except Exception as e:
        return "ERROR", str(e)

def cid_from_name(name):
    """Returns first CID for a name string, or None/('ERROR',msg)."""
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
    print("Extracting (label, SMILES) pairs from file...")
    raw_pairs = extract_pairs(FILE)
    print(f"  Found {len(raw_pairs)} raw pairs.")

    # deduplicate by (label_lower, smiles)
    seen = set()
    pairs = []
    for ln, lbl, smi in raw_pairs:
        key = (lbl.lower(), smi)
        if key not in seen:
            seen.add(key)
            pairs.append((ln, lbl, smi))
    print(f"  {len(pairs)} unique (label, SMILES) pairs.\n")

    # preview extracted pairs
    for ln, lbl, smi in pairs:
        print(f"    L{ln:5d}  {lbl:<30}  {smi[:60]}")
    print()

    results = []
    total = len(pairs)

    for idx, (line_no, label, smiles) in enumerate(pairs, 1):
        print(f"[{idx:2d}/{total}] L{line_no} ({label}) ...", end=" ", flush=True)

        # SMILES → CID
        cid_s, iupac = cid_from_smiles(smiles)
        time.sleep(DELAY)

        if cid_s == "ERROR":
            results.append((line_no, label, smiles, "ERROR", None, None, iupac))
            print(f"ERROR: {iupac[:80]}")
            continue

        if cid_s is None:
            results.append((line_no, label, smiles, "INVALID", None, None, ""))
            print("INVALID (PubChem can't parse)")
            continue

        # Name → CID
        cid_n = cid_from_name(label)
        time.sleep(DELAY)

        if cid_n == "ERROR":
            results.append((line_no, label, smiles, "SMILES_OK_NAME_LOOKUP_FAILED", cid_s, None, iupac))
            print(f"SMILES OK (CID={cid_s} | {iupac[:40]}) — name lookup error")
            continue

        if cid_n is None:
            results.append((line_no, label, smiles, "SMILES_OK_NAME_NOT_IN_PUBCHEM", cid_s, None, iupac))
            print(f"SMILES OK (CID={cid_s} | {iupac[:40]}) — name not in PubChem")
            continue

        # compare
        if cid_s == cid_n:
            status = "MATCH"
            icon   = "✓"
        else:
            status = "MISMATCH"
            icon   = "✗ MISMATCH"

        results.append((line_no, label, smiles, status, cid_s, cid_n, iupac))
        print(f"{icon}  CID_smiles={cid_s}  CID_name={cid_n}  {iupac[:50]}")

    # ── report ─────────────────────────────────────────────────────────────────
    counts = {}
    for r in results:
        counts[r[3]] = counts.get(r[3], 0) + 1

    order = ["MISMATCH", "INVALID", "ERROR",
             "SMILES_OK_NAME_NOT_IN_PUBCHEM", "SMILES_OK_NAME_LOOKUP_FAILED", "MATCH"]

    with open(REPORT, 'w', encoding='utf-8') as out:
        out.write("SMILES Verification Report v3 — name-vs-smiles CID cross-check\n")
        out.write("=" * 70 + "\n\n")
        out.write("SUMMARY\n")
        for k in order:
            if k in counts:
                out.write(f"  {k:<45} {counts[k]}\n")
        out.write(f"  {'TOTAL':<45} {len(results)}\n\n")

        for status_filter in order:
            section = [r for r in results if r[3] == status_filter]
            if not section:
                continue
            out.write("=" * 70 + "\n")
            out.write(f"  {status_filter}  ({len(section)})\n")
            out.write("=" * 70 + "\n")
            for line_no, label, smiles, status, cid_s, cid_n, iupac in section:
                out.write(f"\n  Line      : {line_no}\n")
                out.write(f"  Label     : {label}\n")
                out.write(f"  SMILES    : {smiles}\n")
                if cid_s and cid_s != "ERROR":
                    out.write(f"  CID(smiles): {cid_s}  → {iupac}\n")
                if cid_n:
                    out.write(f"  CID(name) : {cid_n}\n")
                out.write("\n")

    print(f"\nDone. Report → {REPORT}")
    print("Summary:", counts)

if __name__ == "__main__":
    main()
