"""
extract_confirmed_pairs.py
Step 1: Parse na_interaction_verification_v3.txt → extract all ✓ CONFIRMED pairs
Step 2: Map food/drug names to DFinder unified-DFI integer IDs
        → output confirmed_pairs.csv + na_finetune_train.txt (DFinder format)
"""

import re, csv, sys
from pathlib import Path
from collections import defaultdict

# Import shared tables from v3 script (safe — guarded by if __name__ == "__main__")
sys.path.insert(0, str(Path(r"d:\23AIBox-DFinder")))
from verify_na_interactions_v3 import (
    FOOD_EXPAND, DRUG_EXPAND, DISPLAY_NAMES,
    expand_food, expand_drug, parse_line,
    recheck_novel, load_dbs, check_literature
)

BASE       = Path(r"d:\23AIBox-DFinder")
DATA_DIR   = BASE / "DFinder-main" / "data" / "unified-DFI"
ID_DIR     = DATA_DIR / "id_maps"
V2_PATH    = BASE / "na_interaction_verification_v2.txt"
OUT_CSV       = BASE / "confirmed_pairs.csv"
OUT_CSV_CLEAN = BASE / "confirmed_pairs_clean.csv"
OUT_TRAIN     = BASE / "na_finetune_train.txt"

# ─────────────────────────────────────────────────────────────────────────────
# Load ID maps
# ─────────────────────────────────────────────────────────────────────────────
def load_id_map(path):
    """Returns {name_lower: int_id}"""
    m = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            m[row["name"].strip().lower()] = int(row["new_id"])
    return m

food_id_map = load_id_map(ID_DIR / "food_id_map.csv")
drug_id_map = load_id_map(ID_DIR / "drug_id_map.csv")

print(f"Loaded {len(food_id_map)} food nodes, {len(drug_id_map)} drug nodes")

# ─────────────────────────────────────────────────────────────────────────────
# Resolve food_raw → food_id
# ─────────────────────────────────────────────────────────────────────────────
def resolve_food(food_raw):
    aliases = expand_food(food_raw)
    for alias in aliases:
        a = alias.lower().strip()
        if a in food_id_map:
            return food_id_map[a], a
        # Partial substring match (e.g. "omega-3 fatty acids" in key)
        for key, fid in food_id_map.items():
            if a and (a in key or key in a):
                return fid, key
    return None, None

# ─────────────────────────────────────────────────────────────────────────────
# Resolve drug_raw → drug_id(s)
# ─────────────────────────────────────────────────────────────────────────────
def resolve_drug(drug_raw):
    aliases = expand_drug(drug_raw)
    results = []
    seen = set()
    for alias in aliases:
        a = alias.lower().strip()
        if a in drug_id_map:
            did = drug_id_map[a]
            if did not in seen:
                results.append((did, a))
                seen.add(did)
            continue
        # Partial match
        for key, did in drug_id_map.items():
            if a and len(a) > 4 and (a in key or key in a):
                if did not in seen:
                    results.append((did, key))
                    seen.add(did)
                break
    return results  # list of (drug_id, matched_name)

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Parse v2.txt, apply v3 verdict logic, collect confirmed pairs
# ─────────────────────────────────────────────────────────────────────────────
dbs = load_dbs()

confirmed_pairs = []  # list of (food_raw, drug_raw, verdict_tag)

with open(V2_PATH, encoding="utf-8") as f:
    lines = f.readlines()

skip_summary = False
for line in lines:
    # Skip v2 summary block
    if "VERIFICATION SUMMARY" in line:
        skip_summary = True
    if skip_summary:
        continue

    parsed = parse_line(line)
    if parsed is None:
        continue

    orig_verdict, food_raw, drug_raw = parsed

    if orig_verdict.startswith("✓"):
        # Already confirmed in v2 — keep
        verdict_tag = orig_verdict[2:].strip()
        confirmed_pairs.append((food_raw, drug_raw, verdict_tag))

    elif orig_verdict.startswith("?"):
        # Attempt upgrade
        new_verdict, _ = recheck_novel(food_raw, drug_raw, dbs)
        if new_verdict.startswith("✓"):
            verdict_tag = new_verdict[2:].strip()
            confirmed_pairs.append((food_raw, drug_raw, verdict_tag))

    elif orig_verdict.startswith("~"):
        # Check literature for node-only pairs
        lit_verdict, _ = check_literature(food_raw, drug_raw)
        if lit_verdict and lit_verdict.startswith("✓"):
            verdict_tag = lit_verdict[2:].strip()
            confirmed_pairs.append((food_raw, drug_raw, verdict_tag))

print(f"\nStep 1 — Confirmed (food_raw, drug_raw) pairs extracted: {len(confirmed_pairs)}")

# Deduplicate
confirmed_pairs = list(dict.fromkeys(confirmed_pairs))
print(f"           After deduplication                         : {len(confirmed_pairs)}")

# ─────────────────────────────────────────────────────────────────────────────
# Helper: clean food display name
# ─────────────────────────────────────────────────────────────────────────────
def clean_food_name(food_raw):
    """Return a human-readable food name, stripping quantity suffixes."""
    # Strip measurement suffixes (250g, 1.5kg, 200ml, etc.)
    base = re.sub(r'\d+(\.\d+)?(g|kg|ml|l|mg|L)\b', '', food_raw).strip()
    base = re.sub(r'[-_]+$', '', base).strip()
    # Try DISPLAY_NAMES first on original, then stripped
    if food_raw in DISPLAY_NAMES:
        return DISPLAY_NAMES[food_raw]
    if base in DISPLAY_NAMES:
        return DISPLAY_NAMES[base]
    # Fall back to stripped base
    return base if base else food_raw


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Map to DFinder IDs → build train dict + CSV
# ─────────────────────────────────────────────────────────────────────────────
csv_rows = []
train_dict = defaultdict(set)   # food_id → set of drug_ids
unmatched_food = set()
unmatched_drug = set()

for food_raw, drug_raw, verdict_tag in confirmed_pairs:
    food_id, food_matched = resolve_food(food_raw)
    drug_results          = resolve_drug(drug_raw)

    if food_id is None:
        unmatched_food.add(food_raw)

    if not drug_results:
        unmatched_drug.add(drug_raw)

    for drug_id, drug_matched in drug_results:
        if food_id is not None:
            train_dict[food_id].add(drug_id)
        csv_rows.append({
            "food_raw":      food_raw,
            "food_name":     clean_food_name(food_raw),
            "food_matched":  food_matched or "UNMATCHED",
            "food_id":       food_id if food_id is not None else "—",
            "drug_raw":      drug_raw,
            "drug_name":     drug_matched,
            "drug_id":       drug_id,
            "verdict":       verdict_tag,
        })

    if not drug_results:
        csv_rows.append({
            "food_raw":      food_raw,
            "food_name":     clean_food_name(food_raw),
            "food_matched":  food_matched or "UNMATCHED",
            "food_id":       food_id if food_id is not None else "—",
            "drug_raw":      drug_raw,
            "drug_name":     "UNMATCHED",
            "drug_id":       "—",
            "verdict":       verdict_tag,
        })

# Write confirmed_pairs.csv (full, with raws for debugging)
with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "food_raw", "food_name", "food_matched", "food_id",
        "drug_raw", "drug_name", "drug_id", "verdict"
    ])
    writer.writeheader()
    writer.writerows(csv_rows)

print(f"\nStep 2 — confirmed_pairs.csv written: {len(csv_rows)} rows → {OUT_CSV}")

# Write confirmed_pairs_clean.csv — one-to-one, matched only, clean names
clean_rows = [
    r for r in csv_rows
    if r["food_id"] != "—" and r["drug_id"] != "—"
]
# Deduplicate
clean_seen = set()
clean_dedup = []
for r in clean_rows:
    key = (r["food_id"], r["drug_id"])
    if key not in clean_seen:
        clean_seen.add(key)
        clean_dedup.append(r)

with open(OUT_CSV_CLEAN, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "food_name", "food_id", "drug_name", "drug_id", "verdict"
    ])
    writer.writeheader()
    for r in clean_dedup:
        writer.writerow({
            "food_name": r["food_name"],
            "food_id":   r["food_id"],
            "drug_name": r["drug_name"],
            "drug_id":   r["drug_id"],
            "verdict":   r["verdict"],
        })

print(f"           confirmed_pairs_clean.csv written: {len(clean_dedup)} pairs → {OUT_CSV_CLEAN}")

# Write na_finetune_train.txt  (DFinder format: food_id drug_id1 drug_id2 ...)
mapped_foods  = len(train_dict)
mapped_pairs  = sum(len(v) for v in train_dict.values())

with open(OUT_TRAIN, "w", encoding="utf-8") as f:
    for food_id in sorted(train_dict):
        drug_ids = sorted(train_dict[food_id])
        f.write(str(food_id) + " " + " ".join(str(d) for d in drug_ids) + "\n")

print(f"           na_finetune_train.txt written : {mapped_foods} food nodes, {mapped_pairs} (food,drug) pairs → {OUT_TRAIN}")

# Report unmatched
if unmatched_food:
    print(f"\n  ⚠ Food keys with NO id_map match ({len(unmatched_food)}):")
    for x in sorted(unmatched_food)[:20]:
        print(f"      {x}")

if unmatched_drug:
    print(f"\n  ⚠ Drug keys with NO id_map match ({len(unmatched_drug)}):")
    for x in sorted(unmatched_drug)[:20]:
        print(f"      {x}")

print("\nDone.")
