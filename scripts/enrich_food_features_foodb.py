"""
enrich_food_features_foodb.py

Uses local FooDB tables (Compound.csv, Content.csv, Food.csv) to:

1. Fill in fingerprints for Food Bioactives that PubChem missed
   - Looks up each not-found bioactive name in Compound.csv → moldb_smiles

2. Build average-compound fingerprints for Food_Source entries (whole foods)
   - Food.csv:    food name → food_id
   - Content.csv: food_id  → compound source_ids
   - Compound.csv: compound id → moldb_smiles
   - Average the fingerprints of all valid compounds → one vector per food

Updates unified_food_feature_extra.npy in place.

Usage:
    python scripts/enrich_food_features_foodb.py
"""

import os
import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

# ── paths ────────────────────────────────────────────────────────────────────
ROOT       = "D:/23AIBox-DFinder"
COMPOUND   = f"{ROOT}/Compound.csv"
CONTENT    = f"{ROOT}/Content.csv"
FOOD       = f"{ROOT}/Food.csv"
FOOD_MAP   = f"{ROOT}/DFinder-main/data/unified-DFI/id_maps/food_id_map.csv"
FEAT_NPY   = f"{ROOT}/DFinder-main/data/unified-DFI/feature_extra/unified_food_feature_extra.npy"
PUBCHEM_CACHE = f"{ROOT}/scripts/food_smiles_cache.csv"

MORGAN_RADIUS = 2
MORGAN_BITS   = 2048

SMILES_ELIGIBLE_TYPES = {
    "Food Bioactive", "Endogenous Metabolite", "Dietary Amino Acid",
    "Dietary Lipid", "Dietary Amine", "Dietary Nutrient",
}

# ── helpers ──────────────────────────────────────────────────────────────────

def smiles_to_fp(smiles: str):
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, MORGAN_RADIUS, nBits=MORGAN_BITS)
        return np.array(fp, dtype=np.float32)
    except Exception:
        return None


# ── load data ────────────────────────────────────────────────────────────────

print("Loading FooDB tables...")
# NOTE: FooDB Compound.csv has a column shift — actual SMILES are in 'cas_number'
compound_df = pd.read_csv(COMPOUND, usecols=['id', 'name', 'cas_number'],
                          dtype={'id': int, 'name': str, 'cas_number': str})
compound_df = compound_df.rename(columns={'cas_number': 'smiles'})
compound_df['smiles'] = compound_df['smiles'].replace('nan', np.nan)

# Build compound lookup by name (lowercase)
comp_by_name = compound_df.dropna(subset=['smiles'])
comp_by_name = comp_by_name.drop_duplicates('name')
comp_by_name_idx = comp_by_name.set_index(comp_by_name['name'].str.lower().str.strip())

# Build compound lookup by id
comp_by_id = compound_df.dropna(subset=['smiles']).set_index('id')

print(f"  Compound.csv: {len(compound_df):,} rows, {comp_by_name_idx.shape[0]:,} with SMILES")

print("Loading Content.csv (large)...")
content_df = pd.read_csv(CONTENT, usecols=['source_id', 'source_type', 'food_id'])
content_df = content_df[content_df['source_type'] == 'Compound']
print(f"  Content.csv: {len(content_df):,} compound-food links")

print("Loading Food.csv...")
food_df = pd.read_csv(FOOD, usecols=['id', 'name'])
food_by_name = food_df.drop_duplicates('name')
food_by_name_idx = food_by_name.set_index(food_df['name'].str.lower().str.strip())
print(f"  Food.csv: {len(food_df):,} foods")

food_map  = pd.read_csv(FOOD_MAP)
features  = np.load(FEAT_NPY)
n_foods   = len(features)
zero_mask = features.sum(axis=1) == 0

print(f"\nFeature file: {n_foods} entries, {zero_mask.sum()} zero vectors\n")

# ── Part 1: Fill missing bioactives from Compound.csv ────────────────────────

if os.path.exists(PUBCHEM_CACHE):
    cache_df = pd.read_csv(PUBCHEM_CACHE)
    not_found_names_set = set(
        cache_df[cache_df['smiles'].isna() | (cache_df['smiles'].astype(str).isin(['', 'nan']))]
        ['name'].str.lower().str.strip().tolist()
    )
else:
    # Fall back: all eligible zero-vector entries
    eligible = food_map[food_map['type'].isin(SMILES_ELIGIBLE_TYPES)]
    not_found_names_set = set(
        eligible[eligible['new_id'].apply(lambda i: zero_mask[i])]['name']
        .str.lower().str.strip().tolist()
    )

print(f"Part 1: Looking up {len(not_found_names_set)} PubChem-not-found bioactives in FooDB Compound.csv...")

part1_found = 0
for _, row in food_map.iterrows():
    name_key = str(row['name']).lower().strip()
    if name_key not in not_found_names_set:
        continue
    food_id = int(row['new_id'])
    if features[food_id].sum() != 0:
        continue  # already has a fingerprint
    if name_key in comp_by_name_idx.index:
        smiles = comp_by_name_idx.loc[name_key, 'smiles']
        if isinstance(smiles, pd.Series):
            smiles = smiles.iloc[0]
        fp = smiles_to_fp(str(smiles))
        if fp is not None:
            features[food_id] = fp
            part1_found += 1
            print(f"  [{food_id:4d}] {str(row['name']):<40s} ✓")

print(f"\n  Part 1 result: {part1_found} bioactives filled from FooDB Compound.csv")
# Save after Part 1 so progress isn't lost if Part 2 is interrupted
np.save(FEAT_NPY, features)
print(f"  [saved]\n")

# ── Part 2: Average fingerprint for Food_Source entries ──────────────────────

food_sources = food_map[food_map['type'] == 'Food_Source']
# Only process ones that are still zero
food_sources = food_sources[food_sources['new_id'].apply(lambda i: features[i].sum() == 0)]

print(f"Part 2: Building average fingerprints for {len(food_sources)} whole Food_Source entries...")

# Build food_id → compound_ids map from Content
food_to_compounds = content_df.groupby('food_id')['source_id'].apply(list).to_dict()

part2_found = 0
part2_empty = 0

for _, row in food_sources.iterrows():
    food_id  = int(row['new_id'])
    name_key = str(row['name']).lower().strip()

    # Match food name → FooDB food_id
    if name_key not in food_by_name_idx.index:
        continue
    foodb_food_id = int(food_by_name_idx.loc[name_key, 'id'])
    if isinstance(foodb_food_id, pd.Series):
        foodb_food_id = int(foodb_food_id.iloc[0])

    # Get compound ids for this food
    compound_ids = food_to_compounds.get(foodb_food_id, [])
    if not compound_ids:
        continue

    # Compute fingerprints for all valid compounds
    fps = []
    for cid in compound_ids:
        if cid in comp_by_id.index:
            smiles = comp_by_id.loc[cid, 'smiles']
            if isinstance(smiles, pd.Series):
                smiles = smiles.iloc[0]
            fp = smiles_to_fp(str(smiles))
            if fp is not None:
                fps.append(fp)

    if fps:
        avg_fp = np.mean(fps, axis=0).astype(np.float32)
        features[food_id] = avg_fp
        part2_found += 1
        print(f"  [{food_id:4d}] {row['name']:<35s} ✓  ({len(fps)} compounds averaged)")
        if part2_found % 5 == 0:
            np.save(FEAT_NPY, features)
    else:
        part2_empty += 1

print(f"\n  Part 2 result: {part2_found} whole foods enriched, {part2_empty} had no compound data\n")

# ── Save ─────────────────────────────────────────────────────────────────────

np.save(FEAT_NPY, features)
total_nz = (features.sum(axis=1) != 0).sum()

print("=" * 55)
print("Done.")
print(f"  Bioactives from FooDB Compound : {part1_found}")
print(f"  Whole foods avg fingerprint    : {part2_found}")
print(f"  Total non-zero features        : {total_nz}/{n_foods}  ({100*total_nz/n_foods:.1f}%)")
print(f"  Feature file saved             : {FEAT_NPY}")
