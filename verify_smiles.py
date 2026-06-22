"""
verify_smiles.py
Extracts every SMILES string from north_african_food_drug_interactions.txt
and verifies each against PubChem REST API.

File format (4-column pipe-delimited table):
  | dish_name | col2_bioactive/SMILES | col3_drugs |

SMILES appear in col2 as:
  PATTERN A (label + value on separate lines):
    | SMILES (Label):              | interaction text |
    | CC(C)/C=C/CCCCC              | more text        |
    | (=O)NCC1=CC(=C(C=C1)O)OC    |                  |  <- optional continuation

  PATTERN B (label + value inline in col2):
    | SMILES (Pectin rep.): OC1OC  | interaction text |
    | (C(=O)O)CC(O)C1O             |                  |

  PATTERN C (bare label, no parens):
    | SMILES: CC(C)/C=C/CCCCC      | text             |

PubChem endpoint:
  POST https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/property/
       IUPACName,MolecularFormula,MolecularWeight,IsomericSMILES/JSON

Results written to: smiles_verification_report.txt
"""

import re
import time
import requests
from pathlib import Path

INFILE  = Path(r"d:\23AIBox-DFinder\north_african_food_drug_interactions.txt")
OUTFILE = Path(r"d:\23AIBox-DFinder\smiles_verification_report.txt")
PUBCHEM_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/property/IUPACName,MolecularFormula,MolecularWeight,IsomericSMILES/JSON"

# Valid SMILES characters only
SMILES_CHARS = re.compile(r'^[A-Za-z0-9@\[\]()=#/\\+\-\.\%\*\:]+$')
SMILES_START = re.compile(r'^[A-Za-z0-9@\[\(CBcno]')  # plausible SMILES start

def get_col2(line):
    """
    Split a pipe-delimited table line and return the stripped content of column 2
    (0-indexed: | col0 | col1 | col2 | col3 |).
    Returns empty string if not enough columns.
    """
    parts = line.split('|')
    # parts[0] = leading whitespace, parts[1]=col1, parts[2]=col2, parts[3]=col3...
    if len(parts) >= 4:
        return parts[2].strip()
    return ''

def is_smiles_fragment(s):
    """Heuristic: does this string look like a SMILES fragment?"""
    if len(s) < 3:
        return False
    # Reject molecular formula patterns like C31H37O15+ or C12H22O11
    if re.match(r'^C\d+H\d+', s):
        return False
    # Reject strings with parenthetical text appended e.g. (DelGlu)
    if re.search(r'\([A-Z][a-z]{2,}\)', s):
        return False
    # Must have mostly SMILES chars; allow short words like 'O', 'N', 'C' etc.
    non_smiles = re.sub(r'[A-Za-z0-9@\[\]()=#/\\+\-\.%\*:]', '', s)
    if len(non_smiles) > 2:
        return False
    # Must start with a plausible atom/bracket
    return bool(SMILES_START.match(s))

def is_new_node(s):
    """Does this look like a new component node header (not a SMILES continuation)?"""
    if not s:
        return True
    # Separator line
    if re.match(r'^-{5,}', s):
        return True
    # Starts with typical node descriptors (capital letter followed by more capitals/words)
    if re.match(r'^[A-Z][a-z].*\(', s):          # "Butyric Acid (…)"
        return True
    if re.match(r'^SMILES', s):                    # new SMILES entry
        return True
    if re.match(r'^Interaction|^Source|^GCN|^#', s):
        return True
    return False

# ---------------------------------------------------------------------------
# 1. Extract all SMILES entries from file
# ---------------------------------------------------------------------------
def extract_smiles(filepath):
    """
    Walk the file line by line. When col2 contains a SMILES label, extract
    the SMILES value from col2 of the label line and up to 3 continuation lines.
    Returns list of dicts: {label, smiles, line_no}
    """
    lines = filepath.read_text(encoding='utf-8').splitlines()
    entries = []
    i = 0

    while i < len(lines):
        col2 = get_col2(lines[i])

        # ── PATTERN A/B: SMILES (Label): [optional_inline_value]
        m = re.match(r'SMILES\s*\(([^)]+)\)\s*:?\s*(.*)', col2)
        # ── PATTERN C: SMILES: value  (no parentheses)
        m_bare = re.match(r'SMILES\s*:\s*(.*)', col2) if not m else None

        if m or m_bare:
            if m:
                label     = m.group(1).strip()
                inline    = m.group(2).strip()
            else:
                label     = 'bare'
                inline    = m_bare.group(1).strip()

            smiles_parts = []

            # If there is an inline value on the label line, take it
            if inline and is_smiles_fragment(inline):
                smiles_parts.append(inline)

            # Collect continuation lines (col2 only) — up to 4 more lines
            j = i + 1
            while j < min(i + 5, len(lines)):
                c2 = get_col2(lines[j])
                if is_new_node(c2):
                    break
                if c2 and is_smiles_fragment(c2):
                    smiles_parts.append(c2)
                elif c2 == '':
                    pass   # blank col2 — stop collecting
                else:
                    break  # looks like a new node description, stop
                j += 1

            combined = ''.join(smiles_parts).replace(' ', '')

            # Filter: remove truncated placeholders
            if combined.endswith('...') or combined.endswith('…'):
                combined = ''

            # Only keep if it has >= 4 chars and looks like real SMILES
            if len(combined) >= 4 and is_smiles_fragment(combined):
                entries.append({
                    'label':   label,
                    'smiles':  combined,
                    'line_no': i + 1
                })

        i += 1

    return entries


# ---------------------------------------------------------------------------
# 2. Verify against PubChem
# ---------------------------------------------------------------------------
def verify_smiles_pubchem(smiles_str):
    """
    Query PubChem with a SMILES string.
    Returns dict with status and pubchem data.
    """
    try:
        resp = requests.post(
            PUBCHEM_URL,
            data={'smiles': smiles_str},
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            props = data.get('PropertyTable', {}).get('Properties', [{}])[0]
            return {
                'status':    'OK',
                'cid':       props.get('CID', '?'),
                'iupac':     props.get('IUPACName', '?'),
                'formula':   props.get('MolecularFormula', '?'),
                'mw':        props.get('MolecularWeight', '?'),
                'canonical': props.get('IsomericSMILES', '?')
            }
        elif resp.status_code == 404:
            return {'status': 'NOT_FOUND', 'detail': 'PubChem: no compound matched'}
        elif resp.status_code == 400:
            return {'status': 'INVALID', 'detail': f'PubChem rejected: {resp.text[:120]}'}
        else:
            return {'status': f'HTTP_{resp.status_code}', 'detail': resp.text[:120]}
    except requests.exceptions.Timeout:
        return {'status': 'TIMEOUT', 'detail': 'Request timed out'}
    except Exception as e:
        return {'status': 'ERROR', 'detail': str(e)}


# ---------------------------------------------------------------------------
# 3. Deduplicate by SMILES string (same molecule may appear many times)
# ---------------------------------------------------------------------------
def deduplicate(entries):
    """Keep first occurrence of each unique SMILES string."""
    seen = {}
    unique = []
    for e in entries:
        key = e['smiles']
        if key not in seen:
            seen[key] = True
            unique.append(e)
    return unique


# ---------------------------------------------------------------------------
# 4. Main
# ---------------------------------------------------------------------------
def main():
    print(f"Reading {INFILE} ...")
    all_entries = extract_smiles(INFILE)
    print(f"  Total SMILES entries found (with duplicates): {len(all_entries)}")

    unique_entries = deduplicate(all_entries)
    print(f"  Unique SMILES to verify: {len(unique_entries)}")

    results = []
    ok_count      = 0
    invalid_count = 0
    notfound_count = 0
    error_count   = 0

    for idx, entry in enumerate(unique_entries, 1):
        label   = entry['label']
        smiles  = entry['smiles']
        line_no = entry['line_no']

        print(f"[{idx:>3}/{len(unique_entries)}] L{line_no:>4}  {label[:30]:<30}  {smiles[:45]}", end=' ... ')
        result = verify_smiles_pubchem(smiles)
        status = result['status']

        if status == 'OK':
            ok_count += 1
            print(f"OK  CID={result['cid']}  {result['formula']}  {result['iupac'][:50]}")
        elif status == 'NOT_FOUND':
            notfound_count += 1
            print(f"NOT FOUND")
        elif status == 'INVALID':
            invalid_count += 1
            print(f"INVALID  {result.get('detail','')[:60]}")
        else:
            error_count += 1
            print(f"{status}  {result.get('detail','')[:60]}")

        results.append({**entry, **result})
        time.sleep(0.3)   # PubChem rate limit: max ~5 req/s

    # -----------------------------------------------------------------------
    # 5. Write report
    # -----------------------------------------------------------------------
    with OUTFILE.open('w', encoding='utf-8') as f:
        f.write("=" * 100 + "\n")
        f.write("SMILES VERIFICATION REPORT — north_african_food_drug_interactions.txt\n")
        f.write(f"Total unique SMILES verified: {len(unique_entries)}\n")
        f.write(f"OK: {ok_count}  |  INVALID: {invalid_count}  |  NOT_FOUND: {notfound_count}  |  ERRORS: {error_count}\n")
        f.write("=" * 100 + "\n\n")

        # --- INVALID / NOT FOUND first (action needed)
        f.write(">>> INVALID SMILES (need correction)\n")
        f.write("-" * 80 + "\n")
        for r in results:
            if r['status'] == 'INVALID':
                f.write(f"  Label : {r['label']}\n")
                f.write(f"  Line  : {r['line_no']}\n")
                f.write(f"  SMILES: {r['smiles']}\n")
                f.write(f"  Detail: {r.get('detail','')}\n\n")

        f.write("\n>>> NOT FOUND IN PUBCHEM (may be polymer/class/truncated)\n")
        f.write("-" * 80 + "\n")
        for r in results:
            if r['status'] == 'NOT_FOUND':
                f.write(f"  Label : {r['label']}\n")
                f.write(f"  Line  : {r['line_no']}\n")
                f.write(f"  SMILES: {r['smiles']}\n\n")

        f.write("\n>>> ERRORS / TIMEOUTS\n")
        f.write("-" * 80 + "\n")
        for r in results:
            if r['status'] not in ('OK', 'INVALID', 'NOT_FOUND'):
                f.write(f"  Label : {r['label']}\n")
                f.write(f"  Line  : {r['line_no']}\n")
                f.write(f"  SMILES: {r['smiles']}\n")
                f.write(f"  Status: {r['status']}  {r.get('detail','')}\n\n")

        # --- Full verified list
        f.write("\n>>> ALL VERIFIED OK\n")
        f.write("-" * 80 + "\n")
        for r in results:
            if r['status'] == 'OK':
                f.write(f"  [{r['cid']:>8}]  {r['label']:<35}  {r['formula']:<14}  MW={r['mw']:<8}  {r['iupac'][:55]}\n")
                f.write(f"             File SMILES : {r['smiles']}\n")
                f.write(f"             PubChem SMILES: {r['canonical']}\n\n")

    print(f"\nReport written to: {OUTFILE}")
    print(f"Summary — OK: {ok_count}  INVALID: {invalid_count}  NOT_FOUND: {notfound_count}  ERRORS: {error_count}")


if __name__ == "__main__":
    main()
