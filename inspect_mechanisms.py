import pandas as pd

dfi = pd.read_csv('D:/23AIBox-DFinder/dfi_interactions_from_keysentences.csv')
print(f"Total rows: {len(dfi)}")
print(f"Columns: {list(dfi.columns)}\n")

# ── Distribution checks ─────────────────────────────────────────────────────
print("=== drug_metabolizer value counts ===")
print(dfi['drug_metabolizer'].dropna().value_counts().head(20))

print("\n=== drug_transporter value counts ===")
print(dfi['drug_transporter'].dropna().value_counts().head(20))

print("\n=== well_known_target top 30 ===")
print(dfi['well_known_target'].dropna().value_counts().head(30))

print("\n=== modality value counts ===")
print(dfi['modality'].dropna().value_counts())

# ── Non-CYP mechanism search ─────────────────────────────────────────────────
combined = (
    dfi['interaction_sentence'].fillna('') + ' ' +
    dfi['well_known_target'].fillna('') + ' ' +
    dfi['drug_transporter'].fillna('') + ' ' +
    dfi['drug_metabolizer'].fillna('')
)

keywords = {
    'Vitamin K / Warfarin': r'vitamin k|warfarin|anticoagul',
    'Chelation / Cation':   r'chelat|divalent|dmt1',
    'Calcium absorption':   r'calcium.*absorpt|absorpt.*calcium|dairy',
    'P-gp transport':       r'p-glycoprotein|abcb1|p-gp\b|pgp|efflux pump',
    'pH / Gastric':         r'\bph\b|gastric acid|antacid|dissolution rate',
    'Protein binding':      r'protein bind|albumin|plasma protein|displacement',
    'Pharmacodynamic':      r'pharmacodynamic|pd effect|additive.*effect|synerg|antagonis',
}

for label, pattern in keywords.items():
    mask = combined.str.contains(pattern, case=False, regex=True)
    hits = dfi[mask][['drug','food','interaction_sentence','well_known_target','drug_transporter']].drop_duplicates()
    print(f"\n=== {label}: {len(hits)} pairs ===")
    for _, row in hits.head(3).iterrows():
        print(f"  DRUG: {row['drug']}  |  FOOD: {row['food']}")
        print(f"  target: {row['well_known_target']}  transporter: {row['drug_transporter']}")
        print(f"  sentence: {str(row['interaction_sentence'])[:130]}")
        print()
