"""
prepare_dfinder_data.py
=======================
Converts the unified DFI dataset into DFinder-compatible training files.

Outputs (written to DFinder-main/data/unified-DFI/):
  data/
    train.txt          — 80% positive interactions (per-drug grouped)
    test.txt           — 20% positive interactions
    train_neg.txt      — negative interactions (same size as train)
  feature_extra/
    unified_drug_feature_extra.txt   — N_drugs × FEAT_DIM feature matrix
    unified_food_feature_extra.txt   — N_foods × FEAT_DIM feature matrix
  id_maps/
    drug_id_map.csv    — original_id, new_id, name
    food_id_map.csv    — original_id, new_id, name, type

Input files (relative to D:/23AIBox-DFinder/generated/):
  unified_train_interactions_clean.txt
  unified_drug_master.txt
  unified_food_master_typed.txt
  drugbank_drug_smiles.csv
  pomelo_food_smiles.csv
  FooDB/Compound.csv  (large, optional; set FOODB_PATH accordingly)

Feature encoding:
  Morgan fingerprint (radius=2, 2048-bit) from SMILES where available.
  Zero-vector for entities without SMILES.
  FEAT_DIM = 2048
"""

import os, sys, random, csv
from pathlib import Path
from collections import defaultdict

import numpy as np

# ── Optional RDKit import ──────────────────────────────────────────────────────
try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    HAS_RDKIT = True
    print("[OK] RDKit available — will generate Morgan fingerprints")
except ImportError:
    HAS_RDKIT = False
    print("[WARN] RDKit not installed — all features will be zero-vectors")
    print("       Install with: pip install rdkit-pypi")

# ── Configuration ──────────────────────────────────────────────────────────────
BASE_DIR    = Path("D:/23AIBox-DFinder")
GEN_DIR     = BASE_DIR / "generated"
FOODB_PATH  = BASE_DIR / "FooDB" / "Compound.csv"   # large file, optional

OUT_DIR     = BASE_DIR / "DFinder-main" / "data" / "unified-DFI"
DATA_DIR    = OUT_DIR               # train.txt, test.txt, train_neg.txt go here directly
FEAT_DIR    = OUT_DIR / "feature_extra"
MAP_DIR     = OUT_DIR / "id_maps"

FEAT_DIM    = 2048
TRAIN_RATIO = 0.80
NEG_RATIO   = 1.0   # negatives per positive (per drug)
SEED        = 42

random.seed(SEED)
np.random.seed(SEED)

# ── Create output directories ──────────────────────────────────────────────────
for d in [DATA_DIR, FEAT_DIR, MAP_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# 1.  Load masters & build contiguous ID maps
# ══════════════════════════════════════════════════════════════════════════════
print("\n[1/6] Loading masters and building contiguous ID maps…")

# Drug master: id\tname
drug_orig_to_name = {}
with open(GEN_DIR / "unified_drug_master.txt", encoding="utf-8") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 2:
            drug_orig_to_name[int(parts[0])] = parts[1]

sorted_drug_ids = sorted(drug_orig_to_name)
drug_orig_to_new = {orig: new for new, orig in enumerate(sorted_drug_ids)}
N_DRUGS = len(sorted_drug_ids)

# Food master: id\tname\ttype
food_orig_to_info = {}
with open(GEN_DIR / "unified_food_master_typed.txt", encoding="utf-8") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 2:
            food_orig_to_info[int(parts[0])] = (parts[1], parts[2] if len(parts) > 2 else "")

sorted_food_ids = sorted(food_orig_to_info)
food_orig_to_new = {orig: new for new, orig in enumerate(sorted_food_ids)}
N_FOODS = len(sorted_food_ids)

print(f"  Drugs: {N_DRUGS}  (IDs 0–{N_DRUGS-1})")
print(f"  Foods: {N_FOODS}  (IDs 0–{N_FOODS-1})")

# Write ID maps
with open(MAP_DIR / "drug_id_map.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["original_id", "new_id", "name"])
    for orig, new in drug_orig_to_new.items():
        w.writerow([orig, new, drug_orig_to_name[orig]])

with open(MAP_DIR / "food_id_map.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["original_id", "new_id", "name", "type"])
    for orig, new in food_orig_to_new.items():
        name, ftype = food_orig_to_info[orig]
        w.writerow([orig, new, name, ftype])

print("  ID maps written.")

# ══════════════════════════════════════════════════════════════════════════════
# 2.  Load interactions & remap IDs
# ══════════════════════════════════════════════════════════════════════════════
print("\n[2/6] Loading interactions and remapping IDs…")

# drug_pos[new_drug_id] = set of new_food_ids
drug_pos = defaultdict(set)
skipped = 0

with open(GEN_DIR / "unified_train_interactions_clean.txt", encoding="utf-8") as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        orig_drug = int(parts[0])
        if orig_drug not in drug_orig_to_new:
            skipped += 1
            continue
        new_drug = drug_orig_to_new[orig_drug]
        for fp in parts[1:]:
            orig_food = int(fp)
            if orig_food in food_orig_to_new:
                drug_pos[new_drug].add(food_orig_to_new[orig_food])
            else:
                skipped += 1

total_pos = sum(len(v) for v in drug_pos.values())
print(f"  Loaded {total_pos:,} positive pairs across {len(drug_pos):,} drugs")
if skipped:
    print(f"  [WARN] {skipped} entries skipped (missing from master)")

# ══════════════════════════════════════════════════════════════════════════════
# 3.  Train / test split (80/20) & negative sampling
# ══════════════════════════════════════════════════════════════════════════════
print("\n[3/6] Splitting train/test (80/20) and generating negatives…")

all_food_ids = set(range(N_FOODS))
train_pos  = {}   # drug → list of food ids
test_pos   = {}
train_neg  = {}

for drug, foods in drug_pos.items():
    foods_list = list(foods)
    random.shuffle(foods_list)
    split = max(1, int(len(foods_list) * TRAIN_RATIO))
    train_pos[drug]  = foods_list[:split]
    test_pos[drug]   = foods_list[split:]

    # negative sampling from foods NOT in positive set for this drug
    neg_pool = list(all_food_ids - foods)
    n_neg = max(1, int(len(train_pos[drug]) * NEG_RATIO))
    if len(neg_pool) >= n_neg:
        train_neg[drug] = random.sample(neg_pool, n_neg)
    else:
        train_neg[drug] = neg_pool  # take all if fewer available

train_pairs = sum(len(v) for v in train_pos.values())
test_pairs  = sum(len(v) for v in test_pos.values())
neg_pairs   = sum(len(v) for v in train_neg.values())
print(f"  Train positives : {train_pairs:,}")
print(f"  Test  positives : {test_pairs:,}")
print(f"  Train negatives : {neg_pairs:,}")

# ── Helper to write DFinder-format file ──────────────────────────────────────
def write_interaction_file(path, data_dict):
    lines_written = 0
    with open(path, "w", encoding="utf-8") as f:
        for drug_id in sorted(data_dict):
            items = data_dict[drug_id]
            if items:
                f.write(str(drug_id) + " " + " ".join(map(str, items)) + "\n")
                lines_written += 1
    return lines_written

n = write_interaction_file(DATA_DIR / "train.txt",     train_pos)
print(f"  Wrote train.txt     ({n} lines)")
n = write_interaction_file(DATA_DIR / "test.txt",      test_pos)
print(f"  Wrote test.txt      ({n} lines)")
n = write_interaction_file(DATA_DIR / "train_neg.txt", train_neg)
print(f"  Wrote train_neg.txt ({n} lines)")

# ══════════════════════════════════════════════════════════════════════════════
# 4.  Collect SMILES (drugs and foods)
# ══════════════════════════════════════════════════════════════════════════════
print("\n[4/6] Collecting SMILES…")

# Drug SMILES: drugbank_drug_smiles.csv → {drug_name: smiles}
drug_name_to_smiles = {}
smiles_path = GEN_DIR / "drugbank_drug_smiles.csv"
if smiles_path.exists():
    with open(smiles_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name  = row.get("drug_name", "").strip()
            smiles = row.get("smiles", "").strip()
            if name and smiles:
                drug_name_to_smiles[name.lower()] = smiles
    print(f"  Drug SMILES loaded: {len(drug_name_to_smiles):,} entries")
else:
    print(f"  [WARN] {smiles_path} not found")

# Food SMILES: pomelo_food_smiles.csv then FooDB Compound.csv
food_name_to_smiles = {}

pomelo_path = GEN_DIR / "pomelo_food_smiles.csv"
if pomelo_path.exists():
    with open(pomelo_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name   = row.get("food_name", row.get("name", "")).strip()
            smiles = row.get("smiles", row.get("SMILES", "")).strip()
            if name and smiles:
                food_name_to_smiles[name.lower()] = smiles
    print(f"  Pomelo food SMILES loaded: {len(food_name_to_smiles):,} entries")

if FOODB_PATH.exists():
    print(f"  Loading FooDB Compound.csv (large, may take a moment)…")
    with open(FOODB_PATH, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name   = row.get("name", "").strip()
            smiles = row.get("moldb_smiles", row.get("smiles", "")).strip()
            if name and smiles and name.lower() not in food_name_to_smiles:
                food_name_to_smiles[name.lower()] = smiles
    print(f"  FooDB food SMILES total: {len(food_name_to_smiles):,} entries")
else:
    print(f"  [INFO] FooDB Compound.csv not found at {FOODB_PATH} — skipping")

# ══════════════════════════════════════════════════════════════════════════════
# 5.  Generate feature matrices
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n[5/6] Generating {FEAT_DIM}-bit Morgan fingerprint features…")

def smiles_to_fp(smiles, n_bits=FEAT_DIM):
    """Return numpy array of n_bits Morgan fingerprint, or None on failure."""
    if not HAS_RDKIT or not smiles:
        return None
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        try:
            # RDKit ≥ 2022.03: use MorganGenerator
            from rdkit.Chem.rdFingerprintGenerator import GetMorganGenerator
            gen = GetMorganGenerator(radius=2, fpSize=n_bits)
            fp = gen.GetFingerprint(mol)
        except ImportError:
            fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=n_bits)
        arr = np.zeros(n_bits, dtype=np.float32)
        from rdkit.DataStructs import ConvertToNumpyArray
        ConvertToNumpyArray(fp, arr)
        return arr
    except Exception:
        return None

# Drug features
drug_feat = np.zeros((N_DRUGS, FEAT_DIM), dtype=np.float32)
drug_smiles_hits = 0
for orig_id, new_id in drug_orig_to_new.items():
    name = drug_orig_to_name[orig_id].lower()
    smiles = drug_name_to_smiles.get(name)
    if smiles:
        fp = smiles_to_fp(smiles)
        if fp is not None:
            drug_feat[new_id] = fp
            drug_smiles_hits += 1

print(f"  Drugs with SMILES: {drug_smiles_hits:,} / {N_DRUGS:,}  ({100*drug_smiles_hits/N_DRUGS:.1f}%)")

# Food features
food_feat = np.zeros((N_FOODS, FEAT_DIM), dtype=np.float32)
food_smiles_hits = 0
for orig_id, new_id in food_orig_to_new.items():
    name = food_orig_to_info[orig_id][0].lower()
    smiles = food_name_to_smiles.get(name)
    if smiles:
        fp = smiles_to_fp(smiles)
        if fp is not None:
            food_feat[new_id] = fp
            food_smiles_hits += 1

print(f"  Foods with SMILES: {food_smiles_hits:,} / {N_FOODS:,}  ({100*food_smiles_hits/N_FOODS:.1f}%)")

# ── Write feature files ───────────────────────────────────────────────────────
def write_feature_file(path, matrix):
    # Save as numpy binary for fast loading
    npy_path = str(path).replace('.txt', '.npy')
    np.save(npy_path, matrix)
    print(f"  Wrote {Path(npy_path).name}  ({matrix.shape[0]}×{matrix.shape[1]})  [numpy binary]")
    # Also write text backup for compatibility
    with open(path, "w", encoding="utf-8") as f:
        for row in matrix:
            f.write(" ".join(f"{v:.6f}" for v in row) + "\n")
    print(f"  Wrote {path.name}  ({matrix.shape[0]}×{matrix.shape[1]})  [text backup]")

write_feature_file(FEAT_DIR / "unified_drug_feature_extra.txt", drug_feat)
write_feature_file(FEAT_DIR / "unified_food_feature_extra.txt", food_feat)

# ══════════════════════════════════════════════════════════════════════════════
# 6.  Print summary & patch instructions
# ══════════════════════════════════════════════════════════════════════════════
print("\n[6/6] Summary")
print("=" * 60)
print(f"  Output directory : {OUT_DIR}")
print(f"  Drugs            : {N_DRUGS}  (IDs 0–{N_DRUGS-1})")
print(f"  Foods            : {N_FOODS}  (IDs 0–{N_FOODS-1})")
print(f"  Total positives  : {total_pos:,}")
print(f"  Train / Test     : {train_pairs:,} / {test_pairs:,}")
print(f"  Train negatives  : {neg_pairs:,}")
print(f"  Feature dim      : {FEAT_DIM}")
print()
print("  Next: patch DFinder-main/code/model.py:")
print(f"    d_feat_extra shape : ({N_DRUGS}, {FEAT_DIM})")
print(f"    f_feat_extra shape : ({N_FOODS}, {FEAT_DIM})")
print(f"    feature file path  : ../data/unified-DFI/feature_extra/")
print()
print("  And DFinder-main/code/DNN.py:")
print(f"    Linear({FEAT_DIM}, 1024)  [was 2159]")
print()
print("  And DFinder-main/code/world.py:")
print(f"    ROOT_PATH  → D:/23AIBox-DFinder/DFinder-main/")
print(f"    dataset    → unified-DFI  (add to supported list)")
print()
print("  Then train:")
print("    cd DFinder-main/code")
print("    python main.py --dataset unified-DFI --model lgn --epochs 500")
print("=" * 60)
