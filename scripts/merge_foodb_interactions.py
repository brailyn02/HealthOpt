"""
merge_foodb_interactions.py
----------------------------
Merges food_drug_pairs.csv (143,729 pre-cleaned rows) into the unified dataset.

Strategy:
  - Food resolution: unified_food_master first, then FooDB Compound.csv by name
  - Drug resolution: unified_drug_master first, then DrugBank drug SMILES CSV by name
  - Unresolvable entities → skipped (logged)
  - Interactions format: "drug_id food_id1 food_id2 ...\n" (one line per drug)

Outputs (all in generated/):
  - unified_food_master.txt      (updated)
  - unified_drug_master.txt      (updated)
  - unified_train_interactions.txt (updated)
  - foodb_food_smiles.csv        (new food compounds added, with SMILES)
  - foodb_drug_smiles.csv        (new drugs added via this merge, with SMILES)
  - merge_foodb_report.txt       (stats report)
"""

import re
import pandas as pd
from collections import defaultdict

GENERATED = r'd:\23AIBox-DFinder\generated'
BASE      = r'd:\23AIBox-DFinder'

# ── helpers ───────────────────────────────────────────────────────────────────
def norm(name: str) -> str:
    """Lowercase, strip, collapse internal whitespace."""
    return re.sub(r'\s+', ' ', str(name).lower().strip())


# ── 1. Load existing masters ──────────────────────────────────────────────────
print("Loading existing masters …")

food_id_to_name = {}   # int → str
food_norm_to_id = {}   # norm_str → int

with open(f'{GENERATED}/unified_food_master.txt', encoding='utf-8') as fh:
    for line in fh:
        parts = line.rstrip('\n').split('\t', 1)
        fid, fname = int(parts[0]), parts[1]
        food_id_to_name[fid] = fname
        food_norm_to_id[norm(fname)] = fid

drug_id_to_name = {}
drug_norm_to_id = {}

with open(f'{GENERATED}/unified_drug_master.txt', encoding='utf-8') as fh:
    for line in fh:
        parts = line.rstrip('\n').split('\t', 1)
        did, dname = int(parts[0]), parts[1]
        drug_id_to_name[did] = dname
        drug_norm_to_id[norm(dname)] = did

print(f"  Foods loaded:  {len(food_id_to_name)}")
print(f"  Drugs loaded:  {len(drug_id_to_name)}")

# ── 2. Load existing interactions ─────────────────────────────────────────────
print("Loading existing interactions …")
drug_to_foods = defaultdict(set)   # drug_id → set of food_ids

with open(f'{GENERATED}/unified_train_interactions.txt', encoding='utf-8') as fh:
    for line in fh:
        tokens = line.strip().split()
        if not tokens:
            continue
        d = int(tokens[0])
        for t in tokens[1:]:
            drug_to_foods[d].add(int(t))

existing_pairs = sum(len(v) for v in drug_to_foods.values())
print(f"  Existing (drug,food) pairs: {existing_pairs}")

# ── 3. Build FooDB Compound lookup ────────────────────────────────────────────
print("Loading FooDB Compound.csv …")
comp_df = pd.read_csv(f'{BASE}/Compound.csv', usecols=['name', 'moldb_iupac', 'moldb_smiles'],
                      low_memory=False)

compound_smiles = {}   # norm_name → (canonical_name, smiles)
for _, row in comp_df.iterrows():
    smiles = row['moldb_smiles']
    if pd.isna(smiles) or not str(smiles).strip():
        smiles = None
    name_val = row['name']
    if pd.notna(name_val):
        compound_smiles[norm(str(name_val))] = (str(name_val), smiles)
    iupac_val = row['moldb_iupac']
    if pd.notna(iupac_val):
        n = norm(str(iupac_val))
        if n not in compound_smiles:
            compound_smiles[n] = (str(iupac_val), smiles)

print(f"  FooDB compound entries (incl. IUPAC aliases): {len(compound_smiles)}")

# ── 4. Build DrugBank drug name whitelist (for new drug resolution) ───────────
print("Loading DrugBank drug SMILES …")
db_drug_df = pd.read_csv(f'{GENERATED}/drugbank_drug_smiles.csv', low_memory=False)
db_drug_smiles = {}   # norm_name → (canonical_name, smiles)
for _, row in db_drug_df.iterrows():
    dname = row['drug_name']
    smiles = row['smiles'] if pd.notna(row['smiles']) else None
    db_drug_smiles[norm(str(dname))] = (str(dname), smiles)

print(f"  DrugBank drug entries: {len(db_drug_smiles)}")

# ── 5. Load food_drug_pairs.csv and deduplicate ───────────────────────────────
print("Loading food_drug_pairs.csv …")
pairs_df = pd.read_csv(f'{BASE}/food_drug_pairs.csv', usecols=['food', 'drug'],
                       low_memory=False)
pairs_df['food_n'] = pairs_df['food'].apply(lambda x: norm(str(x)))
pairs_df['drug_n'] = pairs_df['drug'].apply(lambda x: norm(str(x)))
pairs_df.drop_duplicates(subset=['food_n', 'drug_n'], inplace=True)
print(f"  Unique (food, drug) pairs: {len(pairs_df)}")

# representative canonical form: first occurrence per normed key
food_canonical = {}   # norm → original string
drug_canonical = {}   
for _, row in pairs_df.iterrows():
    fn, dn = row['food_n'], row['drug_n']
    if fn not in food_canonical:
        food_canonical[fn] = str(row['food'])
    if dn not in drug_canonical:
        drug_canonical[dn] = str(row['drug'])

# ── 6. Resolve entities, extend masters ──────────────────────────────────────
print("Resolving entities …")

next_food_id = max(food_id_to_name) + 1
next_drug_id = max(drug_id_to_name) + 1

new_foods = {}    # norm → food_id  (only newly added in this run)
new_drugs = {}    # norm → drug_id
new_food_smiles = []   # rows for foodb_food_smiles.csv
new_drug_smiles = []   # rows for foodb_drug_smiles.csv


def resolve_food(fn: str) -> int | None:
    """Return food_id for normed name, extending master if needed. None if unresolvable."""
    global next_food_id
    if fn in food_norm_to_id:
        return food_norm_to_id[fn]
    if fn in new_foods:
        return new_foods[fn]
    if fn in compound_smiles:
        canonical, smiles = compound_smiles[fn]
        fid = next_food_id
        next_food_id += 1
        food_id_to_name[fid] = canonical
        food_norm_to_id[fn]  = fid
        new_foods[fn]        = fid
        new_food_smiles.append({'food_id': fid, 'food_name': canonical,
                                'smiles': smiles, 'source': 'FooDB_Compound'})
        return fid
    return None


def resolve_drug(dn: str) -> int | None:
    """Return drug_id for normed name, extending master if needed. None if unresolvable."""
    global next_drug_id
    if dn in drug_norm_to_id:
        return drug_norm_to_id[dn]
    if dn in new_drugs:
        return new_drugs[dn]
    if dn in db_drug_smiles:
        canonical, smiles = db_drug_smiles[dn]
        did = next_drug_id
        next_drug_id += 1
        drug_id_to_name[did] = canonical
        drug_norm_to_id[dn]  = did
        new_drugs[dn]        = did
        new_drug_smiles.append({'drug_id': did, 'drug_name': canonical,
                                'smiles': smiles, 'source': 'DrugBank'})
        return did
    return None


# Pass 1: collect all unique normed names
unique_foods = pairs_df['food_n'].unique()
unique_drugs = pairs_df['drug_n'].unique()

# Resolve foods
food_resolve = {}      # norm → food_id or None
for fn in unique_foods:
    food_resolve[fn] = resolve_food(fn)

# Resolve drugs
drug_resolve = {}
for dn in unique_drugs:
    drug_resolve[dn] = resolve_drug(dn)

# Pass 2: map pairs and add to interactions
pairs_df['fid'] = pairs_df['food_n'].map(food_resolve)
pairs_df['did'] = pairs_df['drug_n'].map(drug_resolve)

# Track unresolved
skip_food = set(pairs_df.loc[pairs_df['fid'].isna(), 'food_n'])
skip_drug = set(pairs_df.loc[pairs_df['did'].isna(), 'drug_n'])

# Keep only fully resolved pairs
resolved = pairs_df.dropna(subset=['fid', 'did']).copy()
resolved['fid'] = resolved['fid'].astype(int)
resolved['did'] = resolved['did'].astype(int)

skip_pairs = len(pairs_df) - len(resolved)

for did_val, grp in resolved.groupby('did')['fid']:
    drug_to_foods[int(did_val)].update(grp.astype(int))

# Count truly new pairs
after_pairs = sum(len(v) for v in drug_to_foods.values())
added_pairs = after_pairs - existing_pairs

print(f"  New food entities added:  {len(new_foods)}")
print(f"  New drug entities added:  {len(new_drugs)}")
print(f"  New (drug,food) pairs:    {added_pairs}")
print(f"  Skipped (unresolved food): {len(skip_food)}")
print(f"  Skipped (unresolved drug): {len(skip_drug)}")
print(f"  Total skipped pair rows:  {skip_pairs}")

# ── 7. Write updated masters ──────────────────────────────────────────────────
print("Writing updated masters …")

with open(f'{GENERATED}/unified_food_master.txt', 'w', encoding='utf-8') as fh:
    for fid in sorted(food_id_to_name):
        fh.write(f"{fid}\t{food_id_to_name[fid]}\n")

with open(f'{GENERATED}/unified_drug_master.txt', 'w', encoding='utf-8') as fh:
    for did in sorted(drug_id_to_name):
        fh.write(f"{did}\t{drug_id_to_name[did]}\n")

print(f"  Food master: {len(food_id_to_name)} entries")
print(f"  Drug master: {len(drug_id_to_name)} entries")

# ── 8. Write updated interactions ─────────────────────────────────────────────
print("Writing updated interactions …")
total_pairs = sum(len(v) for v in drug_to_foods.values())
with open(f'{GENERATED}/unified_train_interactions.txt', 'w', encoding='utf-8') as fh:
    for did in sorted(drug_to_foods):
        foods = sorted(drug_to_foods[did])
        fh.write(f"{did} " + " ".join(str(f) for f in foods) + "\n")

print(f"  Total (drug,food) pairs written: {total_pairs}")

# ── 9. Write SMILES sidecars ──────────────────────────────────────────────────
pd.DataFrame(new_food_smiles).to_csv(f'{GENERATED}/foodb_food_smiles.csv', index=False)
pd.DataFrame(new_drug_smiles).to_csv(f'{GENERATED}/foodb_drug_smiles.csv', index=False)
print(f"  Saved foodb_food_smiles.csv ({len(new_food_smiles)} rows)")
print(f"  Saved foodb_drug_smiles.csv ({len(new_drug_smiles)} rows)")

# ── 10. Write report ──────────────────────────────────────────────────────────
report_lines = [
    "=== FooDB / food_drug_pairs Merge Report ===\n",
    f"Input pairs (unique after dedup): {len(pairs_df)}\n",
    f"\n--- Entity Resolution ---\n",
    f"New food entities:  {len(new_foods)}\n",
    f"  (existing)        {len(food_norm_to_id) - len(new_foods)}\n",
    f"New drug entities:  {len(new_drugs)}\n",
    f"  (existing)        {len(drug_norm_to_id) - len(new_drugs)}\n",
    f"\n--- Master Sizes After Merge ---\n",
    f"Food master total:  {len(food_id_to_name)}\n",
    f"Drug master total:  {len(drug_id_to_name)}\n",
    f"\n--- Interaction Pairs ---\n",
    f"Pre-merge pairs:    {existing_pairs}\n",
    f"Newly added pairs:  {added_pairs}\n",
    f"Total pairs now:    {total_pairs}\n",
    f"\n--- Skipped ---\n",
    f"Unresolved foods:   {len(skip_food)}  (not in master or FooDB Compound.csv)\n",
    f"Unresolved drugs:   {len(skip_drug)}  (not in master or DrugBank SMILES)\n",
    f"\nTop 30 unresolved foods:\n",
]
for fn in sorted(skip_food)[:30]:
    report_lines.append(f"  {food_canonical.get(fn, fn)}\n")
report_lines.append(f"\nTop 30 unresolved drugs:\n")
for dn in sorted(skip_drug)[:30]:
    report_lines.append(f"  {drug_canonical.get(dn, dn)}\n")

with open(f'{GENERATED}/merge_foodb_report.txt', 'w', encoding='utf-8') as fh:
    fh.writelines(report_lines)

print("\n=== Done. Report at generated/merge_foodb_report.txt ===")
