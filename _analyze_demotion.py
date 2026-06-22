import pandas as pd

p = 'validation_splits/phase5_fusion_results.csv'
df = pd.read_csv(p)

def tier(s):
    if s >= 0.70: return 'HIGH'
    if s >= 0.45: return 'MEDIUM'
    if s > 0:     return 'LOW'
    return 'INSUFFICIENT'

df['lgn_tier']    = df['lgn_score'].map(tier)
df['fusion_tier'] = df['fusion_score'].map(tier)

high_lgn = df[df['lgn_tier'] == 'HIGH']
no_mech  = high_lgn[(~high_lgn['graph_found']) & (~high_lgn['kge_found'])]
hid      = df[df['flags'].fillna('').str.contains('HIDDEN_MECHANISM')]

print(f"Total rows          : {len(df)}")
print(f"LGN HIGH (>=0.70)   : {len(high_lgn)}")
print(f"\nLGN HIGH -> fusion tier distribution:")
print(high_lgn['fusion_tier'].value_counts().to_string())
print(f"\nLGN HIGH, no graph, no KGE: {len(no_mech)}")
print(f"  -> fusion tier distribution:")
print(no_mech['fusion_tier'].value_counts().to_string())
print(f"\nHIDDEN_MECHANISM flag count : {len(hid)}")
print(f"HIDDEN_MECHANISM fusion tier:")
print(hid['fusion_tier'].value_counts().to_string())
print(f"\nDemotion: LGN HIGH but fusion NOT HIGH (no mech path): {len(no_mech[no_mech['fusion_tier'] != 'HIGH'])}")
print(f"\nSample demotion cases (lgn>=0.70, no mech, fusion < HIGH):")
demoted = no_mech[no_mech['fusion_tier'] != 'HIGH'][['drug','food','lgn_score','fusion_score','confidence']].head(15)
print(demoted.to_string(index=False))

# Verify the ratio
print(f"\n--- ABLATION CROSS-CHECK ---")
print(f"_piecewise_fusion when mech=0: fusion = lgn*(0.70*lgn)/(0.70*lgn) = lgn  [if lgn<LGN_STRONG_CONFIRM]")
print(f"So fusion_score should equal lgn_score for no-mech pairs (not halved)")
sample = no_mech[['lgn_score','fusion_score']].head(5)
sample['ratio'] = sample['fusion_score'] / sample['lgn_score']
print(sample.to_string(index=False))
