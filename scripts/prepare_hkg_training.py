"""
prepare_hkg_training.py
=======================
Phase B Part 1: Convert hkg_triplets.tsv into integer-indexed KGE training files.

Steps:
  1. Load hkg_triplets.tsv
  2. Prefix every node with its type tag  (FOOD: / CPD: / ENZ: / DRUG:)
     → prevents name collisions across node types
  3. Build entity2id.txt and relation2id.txt mappings
  4. Split into train / valid / test  (90 / 5 / 5  by default)
  5. Write clean 3-column integer TSVs for PyKEEN / LibKGE / OpenKE

Output layout (data/processed_hkg/kge_input/):
  entity2id.txt   — entity_name \t id
  relation2id.txt — relation_name \t id
  train.txt       — head_id \t relation_id \t tail_id
  valid.txt
  test.txt
  kge_stats.txt   — summary

Usage:
    cd D:/23AIBox-DFinder
    python scripts/prepare_hkg_training.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT     = Path("D:/23AIBox-DFinder")
IN_FILE  = ROOT / "data" / "processed_hkg" / "hkg_triplets.tsv"
OUT_DIR  = ROOT / "data" / "processed_hkg" / "kge_input"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Config ───────────────────────────────────────────────────────────────────
TRAIN_RATIO = 0.90
VALID_RATIO = 0.05
# TEST_RATIO  = 1 - TRAIN - VALID = 0.05
SEED        = 42

# Type prefix map — keeps node types distinguishable in the embedding space
TYPE_PREFIX = {
    "FOOD":     "FOOD:",
    "COMPOUND": "CPD:",
    "TARGET":   "ENZ:",
    "DRUG":     "DRUG:",
}

print("=" * 60)
print("Phase B Part 1: HKG Training Data Preparation")
print("=" * 60)

# ── Load triplets ─────────────────────────────────────────────────────────────
print(f"\nLoading {IN_FILE.name}...")
df = pd.read_csv(IN_FILE, sep="\t", dtype=str, low_memory=False)
print(f"  Raw triplets loaded: {len(df):,}")
print(f"  Columns: {list(df.columns)}")

# Drop any rows with missing head/relation/tail
df = df.dropna(subset=["head", "relation", "tail"])
print(f"  After dropping nulls: {len(df):,}")

# ── Apply type prefixes ───────────────────────────────────────────────────────
print("\nApplying node type prefixes...")
df["head_prefixed"] = df.apply(
    lambda r: TYPE_PREFIX.get(r["head_type"], "") + r["head"].strip(), axis=1
)
df["tail_prefixed"] = df.apply(
    lambda r: TYPE_PREFIX.get(r["tail_type"], "") + r["tail"].strip(), axis=1
)

# Quick sanity check — show one of each type
print("  Sample prefixed nodes:")
for t, prefix in TYPE_PREFIX.items():
    sample = df[df["head_type"] == t]["head_prefixed"].iloc[0] if (df["head_type"] == t).any() else "(none)"
    print(f"    [{t:8s}] → {sample}")

# ── Deduplicate (same head-relation-tail may appear from multiple sources) ────
before = len(df)
df = df.drop_duplicates(subset=["head_prefixed", "relation", "tail_prefixed"])
after  = len(df)
print(f"\nDeduplication: {before:,} → {after:,} triplets ({before-after:,} removed)")

# ── Build entity & relation vocabularies ─────────────────────────────────────
print("\nBuilding entity vocabulary...")
all_entities = pd.concat([df["head_prefixed"], df["tail_prefixed"]]).unique()
all_entities.sort()
entity2id = {ent: i for i, ent in enumerate(all_entities)}
print(f"  Total unique entities: {len(entity2id):,}")

# Break down by type prefix
for t, prefix in TYPE_PREFIX.items():
    count = sum(1 for e in all_entities if e.startswith(prefix))
    print(f"    {t:10s}: {count:,}")

print("\nBuilding relation vocabulary...")
all_relations = sorted(df["relation"].unique())
relation2id = {rel: i for i, rel in enumerate(all_relations)}
print(f"  Total unique relations: {len(relation2id):,}")
for rel in all_relations:
    cnt = (df["relation"] == rel).sum()
    print(f"    [{relation2id[rel]:2d}] {rel:25s} — {cnt:,} triplets")

# ── Convert triplets to integer triples ───────────────────────────────────────
print("\nConverting to integer IDs...")
df["h_id"] = df["head_prefixed"].map(entity2id)
df["r_id"] = df["relation"].map(relation2id)
df["t_id"] = df["tail_prefixed"].map(entity2id)

# Verify no NaN IDs
assert df["h_id"].notna().all() and df["r_id"].notna().all() and df["t_id"].notna().all(), \
    "ERROR: Some entities/relations failed to map to IDs"
print("  All IDs mapped successfully")

# ── Train / valid / test split ────────────────────────────────────────────────
print(f"\nSplitting: {TRAIN_RATIO*100:.0f}% / {VALID_RATIO*100:.0f}% / {(1-TRAIN_RATIO-VALID_RATIO)*100:.0f}%")
rng = np.random.default_rng(SEED)
idx = rng.permutation(len(df))

n_train = int(len(df) * TRAIN_RATIO)
n_valid = int(len(df) * VALID_RATIO)

train_idx = idx[:n_train]
valid_idx = idx[n_train:n_train + n_valid]
test_idx  = idx[n_train + n_valid:]

train_df = df.iloc[train_idx][["h_id", "r_id", "t_id"]]
valid_df = df.iloc[valid_idx][["h_id", "r_id", "t_id"]]
test_df  = df.iloc[test_idx ][["h_id", "r_id", "t_id"]]

print(f"  Train: {len(train_df):,}")
print(f"  Valid: {len(valid_df):,}")
print(f"  Test:  {len(test_df):,}")

# ── Write output files ────────────────────────────────────────────────────────
print("\nWriting output files...")

# entity2id.txt
e2id_path = OUT_DIR / "entity2id.txt"
with open(e2id_path, "w", encoding="utf-8") as f:
    f.write(f"{len(entity2id)}\n")
    for ent, eid in sorted(entity2id.items(), key=lambda x: x[1]):
        f.write(f"{ent}\t{eid}\n")
print(f"  entity2id.txt — {len(entity2id):,} entities")

# relation2id.txt
r2id_path = OUT_DIR / "relation2id.txt"
with open(r2id_path, "w", encoding="utf-8") as f:
    f.write(f"{len(relation2id)}\n")
    for rel, rid in sorted(relation2id.items(), key=lambda x: x[1]):
        f.write(f"{rel}\t{rid}\n")
print(f"  relation2id.txt — {len(relation2id):,} relations")

# train / valid / test
for name, split_df in [("train", train_df), ("valid", valid_df), ("test", test_df)]:
    path = OUT_DIR / f"{name}.txt"
    with open(path, "w") as f:
        f.write(f"{len(split_df)}\n")
        split_df.to_csv(f, sep="\t", header=False, index=False)
    size_kb = path.stat().st_size / 1024
    print(f"  {name}.txt — {len(split_df):,} triplets ({size_kb:,.0f} KB)")

# ── Stats summary ─────────────────────────────────────────────────────────────
stats_path = OUT_DIR / "kge_stats.txt"
with open(stats_path, "w") as f:
    f.write("KGE Training Data Stats\n")
    f.write("=" * 45 + "\n")
    f.write(f"  total_triplets   : {len(df):,}\n")
    f.write(f"  total_entities   : {len(entity2id):,}\n")
    f.write(f"  total_relations  : {len(relation2id):,}\n")
    f.write(f"  train_triplets   : {len(train_df):,}\n")
    f.write(f"  valid_triplets   : {len(valid_df):,}\n")
    f.write(f"  test_triplets    : {len(test_df):,}\n")
    f.write("\nEntity breakdown:\n")
    for t, prefix in TYPE_PREFIX.items():
        count = sum(1 for e in all_entities if e.startswith(prefix))
        f.write(f"  {t:10s} : {count:,}\n")
    f.write("\nRelation breakdown:\n")
    for rel in all_relations:
        cnt = (df["relation"] == rel).sum()
        f.write(f"  {rel:25s} : {cnt:,}\n")

print(f"\n{'='*60}")
print("✓ Phase B Part 1 COMPLETE")
print(f"  Output directory: {OUT_DIR}")
print(f"  Entities: {len(entity2id):,} | Relations: {len(relation2id):,}")
print(f"  Ready for PyKEEN / RotatE training")
print(f"{'='*60}")
