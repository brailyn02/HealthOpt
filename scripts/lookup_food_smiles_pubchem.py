"""
lookup_food_smiles_pubchem.py

Queries PubChem by name for each food entity that should have a SMILES
(Food Bioactive, Endogenous Metabolite, Dietary Amino Acid, Dietary Lipid,
Dietary Amine, Dietary Nutrient), computes Morgan fingerprints (radius=2,
nBits=2048), and updates the food feature .npy file.

Progress is cached to 'food_smiles_cache.csv' so the script can be resumed
if interrupted (PubChem has rate limits; ~3-4 req/s is safe).

Usage:
    python scripts/lookup_food_smiles_pubchem.py
"""

import os
import time
import numpy as np
import pandas as pd
import pubchempy as pcp
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

# ── paths ────────────────────────────────────────────────────────────────────
ROOT        = "D:/23AIBox-DFinder"
FOOD_MAP    = f"{ROOT}/DFinder-main/data/unified-DFI/id_maps/food_id_map.csv"
FEAT_NPY    = f"{ROOT}/DFinder-main/data/unified-DFI/feature_extra/unified_food_feature_extra.npy"
CACHE_CSV   = f"{ROOT}/scripts/food_smiles_cache.csv"

# Types that can/should have a single SMILES (exclude whole Food_Source)
SMILES_ELIGIBLE_TYPES = {
    "Food Bioactive",
    "Endogenous Metabolite",
    "Dietary Amino Acid",
    "Dietary Lipid",
    "Dietary Amine",
    "Dietary Nutrient",   # vitamins etc.; minerals will simply fail PubChem lookup
}

MORGAN_RADIUS = 2
MORGAN_BITS   = 2048
REQUEST_DELAY = 0.4   # seconds between PubChem requests (~2.5 req/s, well under limit)

# ── helpers ──────────────────────────────────────────────────────────────────

def smiles_to_fp(smiles: str) -> np.ndarray | None:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, MORGAN_RADIUS, nBits=MORGAN_BITS)
    return np.array(fp, dtype=np.float32)


def pubchem_smiles(name: str) -> str | None:
    """Return canonical SMILES from PubChem by compound name, or None."""
    try:
        results = pcp.get_compounds(name, 'name')
        if results:
            return results[0].connectivity_smiles or results[0].isomeric_smiles
    except Exception:
        pass
    return None


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    food_map = pd.read_csv(FOOD_MAP)
    features = np.load(FEAT_NPY)          # (1894, 2048)
    n_foods  = len(features)

    print(f"Loaded {n_foods} food feature vectors")
    print(f"Currently non-zero: {(features.sum(axis=1) != 0).sum()}")

    # Load or initialise cache
    if os.path.exists(CACHE_CSV):
        cache = pd.read_csv(CACHE_CSV)
        print(f"Resuming from cache ({len(cache)} entries)")
    else:
        cache = pd.DataFrame(columns=["new_id", "name", "smiles"])

    already_done = set(cache["new_id"].tolist())

    # Select eligible entries that are still zero vectors
    eligible = food_map[food_map["type"].isin(SMILES_ELIGIBLE_TYPES)].copy()
    zero_mask = features.sum(axis=1) == 0
    eligible  = eligible[eligible["new_id"].apply(lambda i: zero_mask[i])]
    eligible  = eligible[~eligible["new_id"].isin(already_done)]

    print(f"\nEligible foods needing lookup: {len(eligible)}")
    print("Types breakdown:")
    print(eligible["type"].value_counts().to_string())
    print()

    new_rows = []
    found = 0
    not_found = 0

    for _, row in eligible.iterrows():
        food_id   = int(row["new_id"])
        food_name = str(row["name"])

        smiles = pubchem_smiles(food_name)
        status = "found" if smiles else "not_found"

        if smiles:
            fp = smiles_to_fp(smiles)
            if fp is not None:
                features[food_id] = fp
                found += 1
                print(f"  [{food_id:4d}] {food_name:<40s} ✓")
            else:
                smiles = None  # invalid SMILES
                not_found += 1
                print(f"  [{food_id:4d}] {food_name:<40s} ✗ (bad SMILES)")
        else:
            not_found += 1
            print(f"  [{food_id:4d}] {food_name:<40s} – not found")

        new_rows.append({"new_id": food_id, "name": food_name, "smiles": smiles or ""})
        time.sleep(REQUEST_DELAY)

        # Save cache every 50 entries
        if len(new_rows) % 50 == 0:
            cache = pd.concat([cache, pd.DataFrame(new_rows)], ignore_index=True)
            cache.to_csv(CACHE_CSV, index=False)
            np.save(FEAT_NPY, features)
            new_rows = []
            print(f"  [checkpoint] saved cache + features  (found={found}, not_found={not_found})")

    # Final save
    if new_rows:
        cache = pd.concat([cache, pd.DataFrame(new_rows)], ignore_index=True)
        cache.to_csv(CACHE_CSV, index=False)
    np.save(FEAT_NPY, features)

    total_nonzero = (features.sum(axis=1) != 0).sum()
    print(f"\n{'='*55}")
    print(f"Done.")
    print(f"  New fingerprints added : {found}")
    print(f"  Not found in PubChem   : {not_found}")
    print(f"  Total non-zero features: {total_nonzero}/{n_foods}  ({100*total_nonzero/n_foods:.1f}%)")
    print(f"  Feature file saved     : {FEAT_NPY}")
    print(f"  Cache saved            : {CACHE_CSV}")


if __name__ == "__main__":
    main()
