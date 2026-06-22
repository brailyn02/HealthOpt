"""
Phase 0 — Data Preparation for Hybrid Pipeline
Produces all inputs needed for Phases 1-6.
NEVER modifies original HKG files or LightGCN files.
All outputs go to data/mechanistic_kge/ and validation_splits/.
"""

import os, sys, random
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

random.seed(42)
np.random.seed(42)

# ── Paths ───────────────────────────────────────────────────────────────────
ROOT         = Path("D:/23AIBox-DFinder")
HKG_TRIPLETS = ROOT / "data/processed_hkg/hkg_triplets.tsv"
LGN_DRUG_MAP = ROOT / "DFinder-main/data/unified-DFI/id_maps/drug_id_map.csv"
LGN_FOOD_MAP = ROOT / "DFinder-main/data/unified-DFI/id_maps/food_id_map.csv"
LGN_FOOD_FEAT= ROOT / "DFinder-main/data/unified-DFI/feature_extra/unified_food_feature_extra.npy"
LGN_TRAIN    = ROOT / "DFinder-main/data/unified-DFI/train.txt.bak"
LGN_TEST     = ROOT / "DFinder-main/data/unified-DFI/test.txt"
CONFIRMED    = ROOT / "confirmed_pairs_final.csv"

MECH_DIR     = ROOT / "data/mechanistic_kge"
VAL_DIR      = ROOT / "validation_splits"
MECH_DIR.mkdir(parents=True, exist_ok=True)
VAL_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("PHASE 0 — DATA PREPARATION")
print("=" * 60)


# ════════════════════════════════════════════════════════════════
# 0.1  Extract mechanistic subgraph (all relations except contains)
# ════════════════════════════════════════════════════════════════
print("\n[0.1] Loading HKG triplets...")
df = pd.read_csv(HKG_TRIPLETS, sep="\t", low_memory=False)
mech = df[df["relation"] != "contains"].copy()
mech = mech.dropna(subset=["head", "relation", "tail"])
mech["head"] = mech["head"].astype(str)
mech["tail"] = mech["tail"].astype(str)
print(f"  Total HKG triplets  : {len(df):,}")
print(f"  Mechanistic triplets: {len(mech):,}")
print(f"  Relation counts:\n{mech['relation'].value_counts().to_string()}")

mech_out = MECH_DIR / "mech_triplets.tsv"
mech[["head","relation","tail"]].to_csv(mech_out, sep="\t", index=False)
print(f"  Saved → {mech_out}")


# ════════════════════════════════════════════════════════════════
# 0.2  Build entity2id and relation2id for mechanistic subgraph
# ════════════════════════════════════════════════════════════════
print("\n[0.2] Building entity/relation ID maps...")
all_entities = sorted(set(mech["head"].tolist() + mech["tail"].tolist()))
all_relations = sorted(mech["relation"].unique().tolist())

entity2id  = {e: i for i, e in enumerate(all_entities)}
relation2id = {r: i for i, r in enumerate(all_relations)}

e2id_path = MECH_DIR / "mech_entity2id.txt"
r2id_path = MECH_DIR / "mech_relation2id.txt"

with open(e2id_path, "w") as f:
    f.write(f"{len(entity2id)}\n")
    for e, i in entity2id.items():
        f.write(f"{e}\t{i}\n")

with open(r2id_path, "w") as f:
    f.write(f"{len(relation2id)}\n")
    for r, i in relation2id.items():
        f.write(f"{r}\t{i}\n")

print(f"  Unique entities  : {len(entity2id):,}")
print(f"  Unique relations : {len(relation2id)}")

# Breakdown by entity type
drugs_in_mech     = mech[mech["head_type"]=="DRUG"]["head"].nunique()
compounds_in_mech = mech[mech["head_type"]=="COMPOUND"]["head"].nunique()
enzymes_in_mech   = mech["tail"].nunique()
print(f"  Drugs    : {drugs_in_mech}")
print(f"  Compounds: {compounds_in_mech}")
print(f"  Enzymes  : {enzymes_in_mech}")
print(f"  Saved → {e2id_path}, {r2id_path}")


# ════════════════════════════════════════════════════════════════
# 0.3  Stratified 80/10/10 train/val/test split by relation
# ════════════════════════════════════════════════════════════════
print("\n[0.3] Creating stratified 80/10/10 train/val/test split...")
train_rows, val_rows, test_rows = [], [], []

for rel, group in mech.groupby("relation"):
    rows = group[["head","relation","tail"]].values.tolist()
    random.shuffle(rows)
    n = len(rows)
    n_val  = max(1, int(n * 0.10))
    n_test = max(1, int(n * 0.10))
    test_rows  += rows[:n_test]
    val_rows   += rows[n_test:n_test + n_val]
    train_rows += rows[n_test + n_val:]

def save_split(rows, path):
    with open(path, "w") as f:
        for h, r, t in rows:
            f.write(f"{entity2id[h]}\t{relation2id[r]}\t{entity2id[t]}\n")

save_split(train_rows, MECH_DIR / "mech_train.txt")
save_split(val_rows,   MECH_DIR / "mech_valid.txt")
save_split(test_rows,  MECH_DIR / "mech_test.txt")

print(f"  Train: {len(train_rows):,}")
print(f"  Valid: {len(val_rows):,}")
print(f"  Test : {len(test_rows):,}")

# Also save human-readable TSV splits (for debugging)
pd.DataFrame(train_rows, columns=["head","relation","tail"]).to_csv(MECH_DIR / "mech_train.tsv", sep="\t", index=False)
pd.DataFrame(val_rows,   columns=["head","relation","tail"]).to_csv(MECH_DIR / "mech_valid.tsv", sep="\t", index=False)
pd.DataFrame(test_rows,  columns=["head","relation","tail"]).to_csv(MECH_DIR / "mech_test.tsv",  sep="\t", index=False)

# Relation coverage check
print("  Relation coverage in each split:")
for split_name, split in [("train", train_rows), ("valid", val_rows), ("test", test_rows)]:
    rels = set(r for _, r, _ in split)
    print(f"    {split_name}: {sorted(rels)}")


# ════════════════════════════════════════════════════════════════
# 0.4  Drug Rosetta Stone + Validation Splits
# ════════════════════════════════════════════════════════════════
print("\n[0.4] Building Drug Rosetta Stone and validation splits...")

lgn_drugs = pd.read_csv(LGN_DRUG_MAP).dropna(subset=["name"])
lgn_foods = pd.read_csv(LGN_FOOD_MAP).dropna(subset=["name"])

drug_id_map  = {r["name"].lower(): int(r["new_id"]) for _, r in lgn_drugs.iterrows()}
food_id_map  = {r["name"].lower(): int(r["new_id"]) for _, r in lgn_foods.iterrows()}
hkg_drug_set = set(mech[mech["head_type"]=="DRUG"]["head"].str.lower().unique())

# Drug Rosetta Stone
rosetta_rows = []
for _, row in lgn_drugs.iterrows():
    name_lower = row["name"].lower()
    in_mech = name_lower in hkg_drug_set
    rosetta_rows.append({
        "lgn_id"      : int(row["new_id"]),
        "lgn_name"    : row["name"],
        "hkg_name"    : row["name"] if in_mech else None,
        "in_mech_kge" : in_mech
    })
rosetta_df = pd.DataFrame(rosetta_rows)
rosetta_df.to_csv(MECH_DIR / "drug_rosetta.csv", index=False)
matched = rosetta_df["in_mech_kge"].sum()
print(f"  Drug Rosetta Stone: {matched}/{len(rosetta_df)} LightGCN drugs have KGE embeddings")

# Load base train and test pairs
train_pairs = set()
with open(LGN_TRAIN) as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) > 1:
            uid = int(parts[0])
            for iid in parts[1:]:
                train_pairs.add((uid, int(iid)))

test_pairs = set()
with open(LGN_TEST) as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) > 1:
            uid = int(parts[0])
            for iid in parts[1:]:
                test_pairs.add((uid, int(iid)))

# Categorise confirmed pairs
pairs = pd.read_csv(CONFIRMED)
unseen, test_split, contaminated, no_id = [], [], [], []

for _, row in pairs.iterrows():
    d = str(row["drug_name"]).lower()
    fo = str(row["food_name"]).lower()
    did = drug_id_map.get(d)
    fid = food_id_map.get(fo)
    rec = row.to_dict()
    if did is None or fid is None:
        no_id.append(rec)
        continue
    pair = (did, fid)
    if pair in train_pairs:
        contaminated.append(rec)
    elif pair in test_pairs:
        test_split.append(rec)
    else:
        unseen.append(rec)

pd.DataFrame(unseen).to_csv(      VAL_DIR / "validation_unseen.csv",          index=False)
pd.DataFrame(test_split).to_csv(  VAL_DIR / "validation_test_split.csv",       index=False)
pd.DataFrame(contaminated).to_csv(VAL_DIR / "excluded_train_contaminated.csv", index=False)
pd.DataFrame(no_id).to_csv(       VAL_DIR / "no_lgn_id.csv",                  index=False)

print(f"  Validation splits saved to {VAL_DIR}/")
print(f"    validation_unseen.csv          : {len(unseen)} pairs  ← PRIMARY EVAL")
print(f"    validation_test_split.csv      : {len(test_split)} pairs")
print(f"    excluded_train_contaminated.csv: {len(contaminated)} pairs")
print(f"    no_lgn_id.csv                  : {len(no_id)} pairs")


# ════════════════════════════════════════════════════════════════
# 0.5  Food → Representative Compound Map
# ════════════════════════════════════════════════════════════════
print("\n[0.5] Building food → representative compound map...")

# For each LightGCN food with zero fingerprint:
# pick the compound from HKG contains edges that has the most
# outgoing mechanistic edges (argmax mechanistic edge count)
contains = df[df["relation"] == "contains"].copy()
contains = contains.dropna(subset=["head", "tail"])
contains["head"] = contains["head"].astype(str)
contains["tail"] = contains["tail"].astype(str)

# Mechanistic compound set with edge count
mech_compound_counts = (
    mech[mech["head_type"] == "COMPOUND"]
    .groupby("head").size()
    .reset_index(name="mech_count")
)
mech_compound_counts["head_lower"] = mech_compound_counts["head"].str.lower()
mech_count_map = dict(zip(mech_compound_counts["head_lower"], mech_compound_counts["mech_count"]))

food_feat = np.load(LGN_FOOD_FEAT)

# Pre-build food_lower → list of compounds dict (much faster than per-food filtering)
print("  Pre-building food→compound lookup dict...")
food_to_compounds = defaultdict(list)
for _, row in contains[["head","tail"]].iterrows():
    food_to_compounds[row["head"].lower()].append(row["tail"])
print(f"  Lookup dict built: {len(food_to_compounds)} unique foods")

# Helper: find best representative from HKG contains
def best_hkg_compound(food_name_lower):
    candidates = food_to_compounds.get(food_name_lower, [])
    if not candidates:
        return None, 0
    scored = [(c, mech_count_map.get(c.lower(), 0)) for c in candidates]
    scored.sort(key=lambda x: -x[1])
    return scored[0]

# Manual overrides for the 12 foods we already decided (9 + 3 missing)
# Strategy: if rep is already in LGN with a real FP → copy that row
# Otherwise → will compute Morgan fp from SMILES in step 0.6
manual_reps = {
    # food_name_lower        : (rep_name,           rep_smiles_if_not_in_lgn)
    "tyramine-containing foods" : ("Tyramine",           "NCCc1ccc(O)cc1"),
    "fat"                       : ("Oleic Acid",         None),   # in LGN id=754
    "saponins"                  : ("Glycyrrhizin",       "O=C(O)[C@@H]1CC[C@]2(C)[C@H]1CC[C@]1(C)[C@@H]2CC=C2[C@@H]3C(C)(C)CC[C@]3(CC[C@@]21C)C(=O)O"),
    "starch"                    : ("Amylopectin",        None),   # in LGN id=1801
    "protein"                   : ("L-Leucine",          None),   # in LGN id=511
    "anthocyanins"              : ("Cyanidin",           None),   # in LGN id=124
    "soy lecithin"              : ("Phosphatidylcholine",None),   # in LGN id=921
    "flavonoids"                : ("Quercetin",          None),   # in LGN id=279
    "fiber"                     : ("Pectin",             "OC(=O)[C@H]1OC(O)[C@@H](O)[C@H](O)[C@H]1O"),
    # 3 missing from LGN entirely
    "soluble fiber"             : ("Beta-glucan",        "OC[C@H]1O[C@@H](O[C@H]2[C@@H](O)[C@H](O)[C@@H](O)[C@H](O2)CO)[C@H](O)[C@@H](O)[C@@H]1O"),
    "glucobrassicin"            : ("Indole-3-carbinol",  "OCc1c[nH]c2ccccc12"),
    "sodium bicarbonate"        : ("Sodium Bicarbonate", "OC([O-])=O.[Na+]"),
}

lgn_food_lower = {r["name"].lower(): int(r["new_id"]) for _, r in lgn_foods.iterrows()}

rep_rows = []
for idx, row in lgn_foods.iterrows():
    name     = row["name"]
    food_id  = int(row["new_id"])
    fp       = food_feat[food_id]
    is_zero  = np.allclose(fp, 0)

    if not is_zero:
        rep_rows.append({
            "lgn_food_id"  : food_id,
            "food_name"    : name,
            "has_fp"       : True,
            "rep_compound" : None,
            "rep_smiles"   : None,
            "strategy"     : "original"
        })
        continue

    name_lower = name.lower()

    if name_lower in manual_reps:
        rep_name, rep_smiles = manual_reps[name_lower]
        # Check if rep is in LGN with a real FP
        rep_id = lgn_food_lower.get(rep_name.lower())
        if rep_id is not None and not np.allclose(food_feat[rep_id], 0):
            rep_smiles = None  # signal: copy from LGN row
            strategy   = f"copy_lgn:{rep_id}"
        else:
            strategy = "compute_smiles"
    else:
        # Auto: pick best from HKG contains
        best_cpd, best_cnt = best_hkg_compound(name_lower)
        if best_cpd and best_cnt > 0:
            rep_name   = best_cpd
            rep_smiles = None
            strategy   = f"hkg_best_compound(count={best_cnt})"
        else:
            rep_name   = None
            rep_smiles = None
            strategy   = "no_representative_found"

    rep_rows.append({
        "lgn_food_id"  : food_id,
        "food_name"    : name,
        "has_fp"       : False,
        "rep_compound" : rep_name,
        "rep_smiles"   : rep_smiles,
        "strategy"     : strategy
    })

rep_df = pd.DataFrame(rep_rows)
rep_df.to_csv(MECH_DIR / "food_representative_compound.csv", index=False)

n_original = (rep_df["strategy"] == "original").sum()
n_copy_lgn = rep_df["strategy"].str.startswith("copy_lgn").sum()
n_compute  = (rep_df["strategy"] == "compute_smiles").sum()
n_hkg_auto = rep_df["strategy"].str.startswith("hkg_best").sum()
n_none     = (rep_df["strategy"] == "no_representative_found").sum()

print(f"  Total LightGCN foods      : {len(rep_df)}")
print(f"  Already have fingerprint  : {n_original}")
print(f"  Copy from LGN row         : {n_copy_lgn}")
print(f"  Compute from SMILES       : {n_compute}")
print(f"  Auto-assigned from HKG    : {n_hkg_auto}")
print(f"  No representative found   : {n_none}  (will remain zero)")
print(f"  Saved → {MECH_DIR}/food_representative_compound.csv")


# ════════════════════════════════════════════════════════════════
# 0.6  Fill Zero Fingerprints → unified_food_feature_extra_filled.npy
# ════════════════════════════════════════════════════════════════
print("\n[0.6] Filling zero fingerprints...")

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    RDKIT_AVAILABLE = True
    print("  rdkit available — will compute Morgan fingerprints from SMILES")
except ImportError:
    RDKIT_AVAILABLE = False
    print("  WARNING: rdkit not available — SMILES-based fingerprints will be skipped")
    print("  Run: pip install rdkit  then re-run this script")

food_feat_filled = food_feat.copy()

copied      = 0
computed    = 0
hkg_auto_fp = 0
skipped     = 0

for _, row in rep_df.iterrows():
    fid      = int(row["lgn_food_id"])
    strategy = str(row["strategy"])

    if strategy == "original":
        continue  # already has real fingerprint

    if strategy.startswith("copy_lgn:"):
        src_id = int(strategy.split(":")[1])
        food_feat_filled[fid] = food_feat[src_id]
        copied += 1

    elif strategy == "compute_smiles" and row["rep_smiles"] is not None:
        if RDKIT_AVAILABLE:
            mol = Chem.MolFromSmiles(str(row["rep_smiles"]))
            if mol:
                fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048)
                food_feat_filled[fid] = np.array(fp, dtype=np.float32)
                computed += 1
            else:
                print(f"    WARNING: Invalid SMILES for {row['food_name']}: {row['rep_smiles']}")
                skipped += 1
        else:
            skipped += 1

    elif strategy.startswith("hkg_best_compound"):
        # rep_compound is a name — look it up in LGN
        rep_name = str(row["rep_compound"]) if row["rep_compound"] else None
        if rep_name:
            rep_id = lgn_food_lower.get(rep_name.lower())
            if rep_id is not None and not np.allclose(food_feat[rep_id], 0):
                food_feat_filled[fid] = food_feat[rep_id]
                hkg_auto_fp += 1
            else:
                skipped += 1
        else:
            skipped += 1

    elif strategy == "no_representative_found":
        skipped += 1

out_path = ROOT / "DFinder-main/data/unified-DFI/feature_extra/unified_food_feature_extra_filled.npy"
np.save(out_path, food_feat_filled)

# Verify
zeros_before = sum(1 for i in range(len(food_feat))      if np.allclose(food_feat[i], 0))
zeros_after  = sum(1 for i in range(len(food_feat_filled)) if np.allclose(food_feat_filled[i], 0))

print(f"  Zero rows before : {zeros_before}")
print(f"  Zero rows after  : {zeros_after}  ({zeros_before - zeros_after} filled)")
print(f"    Copied from LGN row        : {copied}")
print(f"    Computed from SMILES       : {computed}")
print(f"    Filled from HKG auto-match : {hkg_auto_fp}")
print(f"    Skipped (no data)          : {skipped}")
print(f"  Saved → {out_path}")


# ════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("PHASE 0 COMPLETE — Summary of outputs")
print("=" * 60)
print(f"\ndata/mechanistic_kge/")
for f in sorted(MECH_DIR.iterdir()):
    size = f.stat().st_size
    print(f"  {f.name:<45} {size:>10,} bytes")
print(f"\nvalidation_splits/")
for f in sorted(VAL_DIR.iterdir()):
    size = f.stat().st_size
    print(f"  {f.name:<45} {size:>10,} bytes")
print(f"\nDFinder-main/.../feature_extra/")
filled_path = ROOT / "DFinder-main/data/unified-DFI/feature_extra/unified_food_feature_extra_filled.npy"
print(f"  unified_food_feature_extra_filled.npy      {filled_path.stat().st_size:>10,} bytes")
print("\nOriginal files are UNTOUCHED.")
print("Ready for Phase 1 — Train Mechanistic KGE.")
