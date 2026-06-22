"""
add_na_food_triplets.py
=======================
Augments hkg_triplets.tsv with:
  1. 55 new FOOD: entities (Algerian dishes not yet in HKG)
  2. 3 new CPD: entities with known enzyme edges:
       - Acrylamide        → substrate_of → CYP2E1
       - Indole-3-carbinol → activates    → CYP1A2, CYP3A4
       - Butyric Acid      → inhibits     → HDAC1, HDAC2
  3. FOOD→contains→COMPOUND triplets for each dish
     (only for compounds that already exist in entity2id.txt - no orphan nodes)

After running this script, re-run:
    python scripts/prepare_hkg_training.py
to rebuild entity2id.txt and train/valid/test integer files.
"""

import re
import csv
from collections import defaultdict
from pathlib import Path

ROOT       = Path("D:/23AIBox-DFinder")
VERIFY_TXT = ROOT / "na_interaction_verification_v3.txt"
TRIPLETS   = ROOT / "data/processed_hkg/hkg_triplets.tsv"
ENTITY2ID  = ROOT / "data/processed_hkg/kge_input/entity2id.txt"

# ── 1. Load existing CPD entity names from entity2id.txt ─────────────────────
print("Loading existing CPD entities from entity2id.txt...")
cpd_lower_to_canonical = {}   # lowercase → exact name as in TSV (without CPD: prefix)
with open(ENTITY2ID, encoding="utf-8") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if parts[0].startswith("CPD:"):
            name = parts[0][4:]
            cpd_lower_to_canonical[name.lower()] = name

print(f"  {len(cpd_lower_to_canonical):,} CPD entities loaded")

# ── 2. New compounds to add (with enzyme edges) ───────────────────────────────
# Name → list of (relation, target_enzyme_TSV_name)
NEW_COMPOUNDS = {
    "Acrylamide": [
        ("substrate_of", "CYP2E1"),
    ],
    "Indole-3-carbinol": [
        ("activates", "CYP1A2"),
        ("activates", "CYP3A4"),
    ],
    "Butyric Acid": [
        ("inhibits", "HDAC1"),
        ("inhibits", "HDAC2"),
    ],
}

# Register new compounds so dish→compound lookup finds them
for name in NEW_COMPOUNDS:
    cpd_lower_to_canonical[name.lower()] = name

# ── 3. Parse dishes and their compounds ──────────────────────────────────────
print("\nParsing na_interaction_verification_v3.txt...")

# Non-chemical structural labels we always skip
SKIP_LABELS = {
    "densematrix", "hydrationmatrix", "lipidcoatedstarch", "lipidsponge",
    "shortcrust-friablematrix", "shortcrustfriablematrix", "zerofermentation",
    "gelatinisedflour", "butter emulsion", "oxidised lipids",
    "allicin-lateadd", "sat.fats", "saturated lipids", "plant protein",
    "non-heme fe", "nonhemeiron", "pyrodextrins", "braidedlattice+3mm",
    "sha'ra-strands", "sha\u2019ra-strands",
}

dishes = defaultdict(set)   # dish_name → set of TSV compound names (canonicalized)
current_dish = None

with open(VERIFY_TXT, encoding="utf-8") as f:
    for line in f:
        m = re.match(r'^Dish \d+: (.+)', line.strip())
        if m:
            current_dish = m.group(1).strip()
            continue

        m = re.match(r'^\s+[✓~?].+?\s{2,}(.+?)\s{2,}→', line)
        if m and current_dish:
            cpd_raw = m.group(1).strip()
            # Strip trailing parenthetical qualifiers (e.g. "Lycopene (Tomato)")
            cpd_clean = re.sub(r'\s*\(.*?\)\s*$', '', cpd_raw).strip()

            # Skip combos and non-chemical labels
            if ('+' in cpd_clean or '/' in cpd_clean or '\u2014' in cpd_clean
                    or ':' in cpd_clean or cpd_clean.lower() in SKIP_LABELS):
                continue

            # Map to canonical TSV name (must exist in entity2id CPD set)
            canonical = cpd_lower_to_canonical.get(cpd_clean.lower())

            # Also try I3C → Indole-3-carbinol
            if canonical is None and cpd_clean.upper() == "I3C":
                canonical = cpd_lower_to_canonical.get("indole-3-carbinol")

            if canonical:
                dishes[current_dish].add(canonical)

print(f"  {len(dishes)} dishes parsed")
total_pairs = sum(len(v) for v in dishes.values())
print(f"  {total_pairs} dish→compound pairs resolved")

# ── 4. Summary before writing ─────────────────────────────────────────────────
print("\nDish→compound breakdown:")
for dish in sorted(dishes):
    cpds = sorted(dishes[dish])
    new_flag = " [NEW FOOD]" if dish.lower() != "couscous" else ""
    print(f"  {dish}{new_flag}:")
    for c in cpds:
        new_cpd = " [NEW CPD]" if c in NEW_COMPOUNDS else ""
        print(f"    → {c}{new_cpd}")

# ── 5. Append new triplets to hkg_triplets.tsv ────────────────────────────────
print(f"\nAppending new triplets to {TRIPLETS.name}...")

new_rows = []

# 5a. Compound→enzyme edges for 3 new compounds
for cpd_name, enz_edges in NEW_COMPOUNDS.items():
    for relation, enz in enz_edges:
        new_rows.append({
            "head": cpd_name,
            "relation": relation,
            "tail": enz,
            "weight": "1.0",
            "source": "na_verified",
            "head_type": "COMPOUND",
            "tail_type": "TARGET",
        })

# 5b. FOOD→contains→COMPOUND edges
for dish, cpd_set in sorted(dishes.items()):
    for cpd in sorted(cpd_set):
        new_rows.append({
            "head": dish,
            "relation": "contains",
            "tail": cpd,
            "weight": "1.0",
            "source": "na_verified",
            "head_type": "FOOD",
            "tail_type": "COMPOUND",
        })

print(f"  New triplets to append: {len(new_rows)}")
print(f"    Compound→enzyme edges:  {sum(1 for r in new_rows if r['head_type']=='COMPOUND')}")
print(f"    Food→compound edges:    {sum(1 for r in new_rows if r['head_type']=='FOOD')}")

# Note: prepare_hkg_training.py already deduplicates on (head, relation, tail)
# so we don't need to scan the full 290MB TSV here.
new_rows_deduped = new_rows
print(f"  (Dedup will be handled by prepare_hkg_training.py)")

# Append to TSV
fieldnames = ["head", "relation", "tail", "weight", "source", "head_type", "tail_type"]
with open(TRIPLETS, "a", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
    for row in new_rows_deduped:
        writer.writerow(row)

print(f"\n✓ Done — {len(new_rows_deduped)} new triplets appended to {TRIPLETS.name}")
print("\nNext step: run  python scripts/prepare_hkg_training.py  to rebuild KGE files.")

# Cleanup temp files
import os
for tmp in ["_tmp_check_enz.py", "_tmp_check_cpd_names.py"]:
    p = ROOT / "scripts" / tmp
    if p.exists():
        os.remove(p)
