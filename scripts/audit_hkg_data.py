"""
Audit data availability for the Heterogeneous Knowledge Graph (HKG).
Checks matching between FooDB Compound.csv and DrugBank enzyme data.
"""
import pandas as pd

ROOT = r"D:/23AIBox-DFinder"

# ── 1. FooDB Compound.csv ─────────────────────────────────────────────────────
print("Loading FooDB Compound.csv...")
compound = pd.read_csv(f"{ROOT}/Compound.csv",
    usecols=['id','name','cas_number','moldb_smiles','kingdom','superklass','klass','subklass'],
    dtype=str, low_memory=False)
print(f"  Total compounds: {len(compound):,}")

# Verify column content (cas_number was previously found to hold SMILES)
caffeine = compound[compound['name'].str.lower() == 'caffeine']
print(f"\n  Caffeine check:")
print(caffeine[['name','cas_number','moldb_smiles']].to_string())

has_cas    = compound['cas_number'].notna() & (compound['cas_number'].str.strip() != '')
has_smiles = compound['moldb_smiles'].notna() & (compound['moldb_smiles'].str.strip() != '')
print(f"\n  cas_number  (SMILES col): {has_cas.sum():,}")
print(f"  moldb_smiles field:       {has_smiles.sum():,}")

# Chemical class coverage
print(f"\n  Subclass coverage: {compound['subklass'].notna().sum():,} / {len(compound):,}")
print(f"  Top subclasses:\n{compound['subklass'].value_counts().head(10).to_string()}")

# ── 2. DrugBank enzyme data ───────────────────────────────────────────────────
print("\n\nLoading DrugBank enzyme data...")
enz = pd.read_csv(f"{ROOT}/generated/drugbank_dfi_enzymes.csv")
print(f"  Total rows: {len(enz):,}")
print(f"  Unique drugs: {enz['drug_name'].nunique():,}")
print(f"  Unique gene targets: {enz['gene_name'].nunique():,}")

cyp_tp = enz[enz['gene_name'].str.contains('CYP|ABCB1|ABCG2|SLCO', na=False)]
print(f"  CYP/Transporter rows: {len(cyp_tp):,}")
print(f"  Unique CYP/TP targets: {cyp_tp['gene_name'].nunique():,}")

# ── 3. Name-based matching FooDB <-> DrugBank ─────────────────────────────────
print("\n\nName-match: FooDB compounds <-> DrugBank drugs...")
foodb_names = set(compound['name'].str.lower().str.strip().dropna())
db_names    = set(enz['drug_name'].str.lower().str.strip().dropna())
overlap     = foodb_names & db_names
print(f"  FooDB compound names: {len(foodb_names):,}")
print(f"  DrugBank drug names:  {len(db_names):,}")
print(f"  NAME OVERLAP:         {len(overlap):,} compounds")

# Show matched compounds with their enzyme actions
matched_enz = enz[enz['drug_name'].str.lower().str.strip().isin(overlap)]
print(f"\n  CYP/TP rows for matched compounds: {len(matched_enz[matched_enz['gene_name'].str.contains('CYP|ABCB1|ABCG2', na=False)]):,}")

print("\n  Sample matched compounds with CYP targets:")
sample = matched_enz[matched_enz['gene_name'].str.contains('CYP3A4|CYP2D6|CYP1A2|ABCB1', na=False)][
    ['drug_name','gene_name','actions']
].drop_duplicates().head(25)
print(sample.to_string(index=False))

# ── 4. FooDB Food.csv ─────────────────────────────────────────────────────────
print("\n\nLoading Food.csv...")
food = pd.read_csv(f"{ROOT}/Food.csv", usecols=['id','name','food_group','food_subgroup','food_type'], dtype=str)
print(f"  Total foods: {len(food):,}")
print(f"  food_type distribution:\n{food['food_type'].value_counts().to_string()}")
print(f"  food_group sample:\n{food['food_group'].value_counts().head(10).to_string()}")

# ── 5. Content.csv stats ──────────────────────────────────────────────────────
print("\n\nChecking Content.csv food-compound density...")
content = pd.read_csv(f"{ROOT}/Content.csv", usecols=['source_id','source_type','food_id'])
c = content[content['source_type'] == 'Compound']
per_food = c.groupby('food_id')['source_id'].nunique()
print(f"  Foods with compounds: {len(per_food):,}")
print(f"  Avg compounds/food:   {per_food.mean():.0f}")
print(f"  Max compounds/food:   {per_food.max():,}")
print(f"  Min compounds/food:   {per_food.min():,}")

# ── 6. Subclass-based inference coverage ─────────────────────────────────────
print("\n\nSubclass-based CYP inference (known from literature):")
CYP_CLASS_MAP = {
    'Flavonoids':           ['CYP3A4','CYP1A2','CYP2C9'],
    'Isoflavonoids':        ['CYP3A4','CYP1A2'],
    'Furanocoumarins':      ['CYP3A4'],
    'Prenol lipids':        ['CYP3A4','CYP2C9'],
    'Alkaloids':            ['CYP2D6','CYP3A4'],
    'Stilbenes':            ['CYP1A2','CYP3A4'],
    'Anthocyanins':         ['CYP3A4'],
    'Terpene lactones':     ['CYP3A4'],
    'Hydroxycinnamic acids':['CYP1A2'],
}
for cls, cyps in CYP_CLASS_MAP.items():
    n = compound[compound['klass'] == cls].shape[0]
    if n > 0:
        print(f"  {cls:40s}: {n:5,} compounds -> {', '.join(cyps)}")

print("\n✓ Audit complete.")
