"""
Build unified drug master, food master, and interactions file from all sources:
  1. train(kaggle).txt         -> Kaggle drug/food IDs → names via kaggle CSVs
  2. train_final.txt           -> drugs_cleaned_with_categories + foods_categorized IDs
  3. dfi_interactions_from_keysentences.csv  -> raw drug/food name columns
  4. Pomelo SMILES interactions -> pomelo_drugs_named.txt / pomelo_foods_named.txt

Output format (per DFinder): drug_id food_id1 food_id2 ...
"""
import csv
from pathlib import Path
from collections import defaultdict

root = Path(r'd:/23AIBox-DFinder')
out_dir = root / 'generated'
out_dir.mkdir(exist_ok=True)

# ── Helper ─────────────────────────────────────────────────────────────────
def normalise(s):
    return s.strip().lower()

# ── 1. Load source ID→name maps ────────────────────────────────────────────

# Kaggle drug id → name
kaggle_drug_id2name = {}
with (root / 'drugs_id_names(kaggle).csv').open(encoding='utf-8') as f:
    for row in csv.DictReader(f):
        kaggle_drug_id2name[int(row['drug_id'])] = row['drug_name'].strip()

# Kaggle food id → name
kaggle_food_id2name = {}
with (root / 'foods_id_names(kaggle).csv').open(encoding='utf-8') as f:
    for row in csv.DictReader(f):
        kaggle_food_id2name[int(row['food_id'])] = row['food_name'].strip()

# drugs_cleaned_with_categories drug_id → name
dcwc_drug_id2name = {}
with (root / 'drugs_cleaned_with_categories.csv').open(encoding='utf-8') as f:
    for row in csv.DictReader(f):
        dcwc_drug_id2name[int(row['drug_id'])] = row['drug_name'].strip()

# foods_categorized food_id → canonical_name
foods_cat_id2name = {}
with (root / 'foods_categorized.csv').open(encoding='utf-8') as f:
    for row in csv.DictReader(f):
        foods_cat_id2name[int(row['food_id'])] = row['canonical_name'].strip()

# drugs_cleaned_final: first column is drug name (no numeric id)
dcf_names = set()
with (root / 'drugs_cleaned_final.csv').open(encoding='utf-8', errors='ignore') as f:
    reader = csv.reader(f)
    next(reader)  # skip header
    for row in reader:
        if row:
            name = row[0].strip()
            if name:
                dcf_names.add(name)

# Pomelo SMILES → name
smi2drugname = {}
with (root / 'pomelo_drugs_named.txt').open(encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) >= 3 and parts[2].strip():
            smi2drugname[parts[1].strip()] = parts[2].strip()

smi2foodname = {}
with (root / 'pomelo_foods_named.txt').open(encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) >= 3 and parts[2].strip():
            smi2foodname[parts[1].strip()] = parts[2].strip()

# ── 2. Collect ALL unique drug names and food names across every source ────
all_drug_names_ordered = []   # preserve insertion order, case-normalised dedup
drug_norm2canonical = {}      # normalised → first-seen canonical form

def add_drug(name):
    n = normalise(name)
    if n and n not in drug_norm2canonical:
        drug_norm2canonical[n] = name
        all_drug_names_ordered.append(name)

def add_food(name):
    n = normalise(name)
    if n and n not in food_norm2canonical:
        food_norm2canonical[n] = name
        all_food_names_ordered.append(name)

all_food_names_ordered = []
food_norm2canonical = {}

# Kaggle drugs
for name in kaggle_drug_id2name.values():
    add_drug(name)
# drugs_cleaned_with_categories
for name in dcwc_drug_id2name.values():
    add_drug(name)
# drugs_cleaned_final
for name in dcf_names:
    add_drug(name)
# Pomelo drug names
for name in smi2drugname.values():
    add_drug(name)
# DFI raw drug names
with (root / 'dfi_interactions_from_keysentences.csv').open(encoding='utf-8') as f:
    for row in csv.DictReader(f):
        add_drug(row['drug'].strip())

# Kaggle foods
for name in kaggle_food_id2name.values():
    add_food(name)
# foods_categorized
for name in foods_cat_id2name.values():
    add_food(name)
# Pomelo food names
for name in smi2foodname.values():
    add_food(name)
# DFI raw food names
with (root / 'dfi_interactions_from_keysentences.csv').open(encoding='utf-8') as f:
    for row in csv.DictReader(f):
        add_food(row['food'].strip())

# ── 3. Assign unified IDs ───────────────────────────────────────────────────
drug_norm2uid = {n: i for i, n in enumerate(normalise(c) for c in all_drug_names_ordered)}
food_norm2uid = {n: i for i, n in enumerate(normalise(c) for c in all_food_names_ordered)}

def drug_uid(name):
    return drug_norm2uid.get(normalise(name))

def food_uid(name):
    return food_norm2uid.get(normalise(name))

# ── 4. Collect all positive (drug_uid, food_uid) pairs ─────────────────────
interactions = defaultdict(set)  # drug_uid → set of food_uids

def add_pair(dname, fname):
    d = drug_uid(dname)
    f = food_uid(fname)
    if d is not None and f is not None:
        interactions[d].add(f)

# Source A: train(kaggle).txt
with (root / 'train(kaggle).txt').open(encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split()
        if not parts:
            continue
        dname = kaggle_drug_id2name.get(int(parts[0]))
        if not dname:
            continue
        for fid_str in parts[1:]:
            fname = kaggle_food_id2name.get(int(fid_str))
            if fname:
                add_pair(dname, fname)

# Source B: train_final.txt
with (root / 'train_final.txt').open(encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split()
        if not parts:
            continue
        dname = dcwc_drug_id2name.get(int(parts[0]))
        if not dname:
            continue
        for fid_str in parts[1:]:
            fname = foods_cat_id2name.get(int(fid_str))
            if fname:
                add_pair(dname, fname)

# Source C: dfi_interactions_from_keysentences.csv
with (root / 'dfi_interactions_from_keysentences.csv').open(encoding='utf-8') as f:
    for row in csv.DictReader(f):
        add_pair(row['drug'].strip(), row['food'].strip())

# Source D: Pomelo SMILES interactions
with (root / 'pomelo_interactions_mapped.txt').open(encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) < 3:
            continue
        food_smi = parts[1].strip()
        drug_smiles = [d.strip() for d in parts[2].split(',') if d.strip()]
        fname = smi2foodname.get(food_smi)
        if not fname:
            continue
        for dsmi in drug_smiles:
            dname = smi2drugname.get(dsmi)
            if dname:
                add_pair(dname, fname)

# ── 5. Write outputs ────────────────────────────────────────────────────────

# Unified drug master
drug_master = out_dir / 'unified_drug_master.txt'
with drug_master.open('w', encoding='utf-8') as f:
    for i, canonical in enumerate(all_drug_names_ordered):
        f.write(f"{i}\t{canonical}\n")

# Unified food master
food_master = out_dir / 'unified_food_master.txt'
with food_master.open('w', encoding='utf-8') as f:
    for i, canonical in enumerate(all_food_names_ordered):
        f.write(f"{i}\t{canonical}\n")

# Unified interactions (drug_id food_id1 food_id2 ...)
inter_file = out_dir / 'unified_train_interactions.txt'
with inter_file.open('w', encoding='utf-8') as f:
    for duid in sorted(interactions.keys()):
        fuids = sorted(interactions[duid])
        if fuids:
            f.write(' '.join([str(duid)] + [str(x) for x in fuids]) + '\n')

# ── 6. Summary ──────────────────────────────────────────────────────────────
total_pairs = sum(len(v) for v in interactions.values())
print(f"Unified drug master  : {len(all_drug_names_ordered)} entries  → {drug_master}")
print(f"Unified food master  : {len(all_food_names_ordered)} entries  → {food_master}")
print(f"Interaction lines    : {len(interactions)} drugs with food pairs")
print(f"Total positive pairs : {total_pairs}")
print(f"Interactions file    : {inter_file}")
print()
print("Sources breakdown:")
print(f"  Kaggle drug ID map    : {len(kaggle_drug_id2name)} drugs")
print(f"  Kaggle food ID map    : {len(kaggle_food_id2name)} foods")
print(f"  drugs_cleaned_w_cats  : {len(dcwc_drug_id2name)} drugs")
print(f"  drugs_cleaned_final   : {len(dcf_names)} drug names")
print(f"  Pomelo named drugs    : {len(smi2drugname)} drugs")
print(f"  Pomelo named foods    : {len(smi2foodname)} foods")
print(f"  foods_categorized     : {len(foods_cat_id2name)} foods")
