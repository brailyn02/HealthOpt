import pandas as pd

# Load HKG triplets
hkg = pd.read_csv('data/processed_hkg/hkg_triplets.tsv', sep='\t')

# Find Warfarin edges (drug to enzyme)
warfarin_edges = hkg[(hkg['head'].str.lower() == 'warfarin') & (hkg['relation'] != 'contains')]

# Find Spinach edges (food to compounds)
spinach_edges = hkg[(hkg['head'].str.lower() == 'spinach') & (hkg['relation'] == 'contains')]

# Find compound->enzyme interactions for spinach compounds
spinach_compounds = set(spinach_edges['tail'].unique())
compound_enzyme = hkg[(hkg['head'].isin(spinach_compounds)) & (hkg['relation'] != 'contains')]

# Get overlap
warfarin_targets = set(warfarin_edges['tail'].unique())
overlap_targets = compound_enzyme[compound_enzyme['tail'].isin(warfarin_targets)]

print('=' * 100)
print('SUMMARY: WARFARIN-SPINACH INTERACTION ANALYSIS (HKG LAYER)')
print('=' * 100)
print(f'\nWarfarin targets in HKG: {len(warfarin_targets)}')
print('Targets:', sorted(warfarin_targets))

print(f'\nSpinach compounds in HKG: {len(spinach_compounds)}')

print(f'\nSpinach compounds found in HKG that interact with any enzyme/protein: {len(set(compound_enzyme["head"].unique()))}')

print(f'\nSpinach compounds that target SAME enzymes as Warfarin: {len(set(overlap_targets["head"].unique()))}')
print('Overlapping compounds:', sorted(set(overlap_targets["head"].unique())))

print(f'\nTotal HKG edges where spinach compounds target warfarin enzymes: {len(overlap_targets)}')

# Group by relation
print('\nBreakdown by relation type:')
for rel in sorted(overlap_targets['relation'].unique()):
    sub = overlap_targets[overlap_targets['relation'] == rel]
    print(f'  {rel}: {len(sub)} edges')

print('\n' + '=' * 100)
print('OVERLAPPING INTERACTIONS (Spinach compounds → Warfarin targets)')
print('=' * 100)
for rel in sorted(overlap_targets['relation'].unique()):
    sub = overlap_targets[overlap_targets['relation'] == rel]
    print(f'\n{rel.upper()}:')
    for _, row in sub.iterrows():
        print(f'  {row["head"]} {row["relation"]} {row["tail"]}')
