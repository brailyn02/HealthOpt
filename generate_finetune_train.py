"""
Generate fine-tuned train.txt by merging confirmed_pairs_final.csv
(novel North African food-drug pairs) into the existing unified-DFI train.txt.

Strategy:
  - Load original train.txt as dict {food_id: set(drug_ids)}
  - Load confirmed_pairs_final.csv, add only novel edges
  - Write merged train.txt (backup original first)
  - Delete s_pre_adj_mat.npz so the dataloader rebuilds the adjacency matrix
"""
import csv
import os
import shutil
from collections import defaultdict

TRAIN_TXT     = r"D:\23AIBox-DFinder\DFinder-main\data\unified-DFI\train.txt"
PAIRS_CSV     = r"D:\23AIBox-DFinder\confirmed_pairs_final.csv"
ADJ_CACHE     = r"D:\23AIBox-DFinder\DFinder-main\data\unified-DFI\s_pre_adj_mat.npz"
BACKUP        = TRAIN_TXT + ".bak"

# Checkpoint was trained with drug IDs 0–1893 and food IDs 0–4999.
# Any pair with IDs outside these ranges would resize the embedding matrices
# and break --load 1 (checkpoint size mismatch). Filter or remap them.
MAX_DRUG_ID   = 1893
MAX_FOOD_ID   = 4999

# Drug synonym remaps: out-of-range ID → correct in-range ID
# paracetamol (1923) == Acetaminophen (15), same molecule, two names
DRUG_REMAP = {
    1923: 15,    # paracetamol → Acetaminophen (same molecule)
    2647: 766,   # Magnesium hydroxide → Magnesium oxide (both antacids, same acid-base mechanism)
}

# ── 1. Load original train.txt ─────────────────────────────────────────────
train = defaultdict(set)   # food_id (int) → set of drug_ids (int)
with open(TRAIN_TXT) as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        fid = int(parts[0])
        for did in parts[1:]:
            train[fid].add(int(did))

original_edge_count = sum(len(v) for v in train.values())
print(f"Original train.txt  : {len(train)} food nodes, {original_edge_count} edges")

# ── 2. Load new pairs ──────────────────────────────────────────────────────
new_edges = 0
already   = 0
skipped   = 0
remapped_drugs = 0
with open(PAIRS_CSV, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        fid = int(row["food_id"])
        did = int(row["drug_id"])
        # Apply drug synonym remap before range check
        if did in DRUG_REMAP:
            did = DRUG_REMAP[did]
            remapped_drugs += 1
        if fid > MAX_FOOD_ID or did > MAX_DRUG_ID:
            skipped += 1
            continue
        if did in train[fid]:
            already += 1
        else:
            train[fid].add(did)
            new_edges += 1

print(f"New pairs CSV       : {new_edges} novel edges added, {already} already present, {skipped} skipped (out of range), {remapped_drugs} drug synonyms remapped")
print(f"Merged total        : {sum(len(v) for v in train.values())} edges")

# ── 3. Backup original & write merged train.txt ────────────────────────────
if not os.path.exists(BACKUP):
    shutil.copy2(TRAIN_TXT, BACKUP)
    print(f"Backup saved        : {BACKUP}")
else:
    print(f"Backup already exists: {BACKUP}")

with open(TRAIN_TXT, "w") as f:
    for fid in sorted(train.keys()):
        drug_ids = sorted(train[fid])
        f.write(str(fid) + " " + " ".join(str(d) for d in drug_ids) + "\n")

print(f"Written             : {TRAIN_TXT}")

# ── 4. Delete cached adjacency matrix so dataloader rebuilds it ───────────
if os.path.exists(ADJ_CACHE):
    os.remove(ADJ_CACHE)
    print(f"Deleted adj cache   : {ADJ_CACHE}")
else:
    print("Adj cache not found (already clean)")

print("\n✓ Fine-tune data ready. Run training with:")
print("  cd D:\\23AIBox-DFinder\\DFinder-main\\code")
print("  python main.py --load 1 --epochs 200 --lr 0.0001 --comment finetune-na --tensorboard 0")
