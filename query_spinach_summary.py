import pandas as pd

# Load HKG triplets
hkg = pd.read_csv('data/processed_hkg/hkg_triplets.tsv', sep='\t')

# Get all spinach compounds
spinach_edges = hkg[(hkg['head'].str.lower() == 'spinach') & (hkg['relation'] == 'contains')]
spinach_compounds = set(spinach_edges['tail'].unique())

# Get all spinach compound interactions
spinach_interactions = hkg[(hkg['head'].isin(spinach_compounds)) & (hkg['relation'] != 'contains')]

print('=' * 100)
print('SPINACH COMPOUNDS SUMMARY')
print('=' * 100)
print(f'\nTotal spinach compounds in HKG: {len(spinach_compounds)}')

compounds_with_interactions = set(spinach_interactions['head'].unique())
print(f'Compounds with drug/enzyme interactions: {len(compounds_with_interactions)}')
print(f'Compounds without interactions: {len(spinach_compounds) - len(compounds_with_interactions)}')
print(f'\nTotal interaction edges: {len(spinach_interactions)}')

print('\n' + '=' * 100)
print('INTERACTION TYPES')
print('=' * 100)
for rel in sorted(spinach_interactions['relation'].unique()):
    count = len(spinach_interactions[spinach_interactions['relation'] == rel])
    print(f'{rel}: {count} edges')

print('\n' + '=' * 100)
print('TOP 20 MOST CONNECTED SPINACH COMPOUNDS')
print('=' * 100)
compound_edge_counts = spinach_interactions.groupby('head').size().sort_values(ascending=False)
for i, (cpd, count) in enumerate(compound_edge_counts.head(20).items(), 1):
    print(f'{i:2d}. {cpd:50s} {count:3d} edges')
    # Show what it interacts with
    for rel in sorted(spinach_interactions[spinach_interactions['head']==cpd]['relation'].unique()):
        targets = spinach_interactions[(spinach_interactions['head']==cpd) & (spinach_interactions['relation']==rel)]['tail'].unique()
        print(f'        {rel}: {len(targets)} targets')

print('\n' + '=' * 100)
print('CLINICALLY RELEVANT SPINACH COMPOUNDS (interact with warfarin targets)')
print('=' * 100)

warfarin_edges = hkg[(hkg['head'].str.lower() == 'warfarin') & (hkg['relation'] != 'contains')]
warfarin_targets = set(warfarin_edges['tail'].unique())

clinically_relevant = spinach_interactions[spinach_interactions['tail'].isin(warfarin_targets)]
relevant_compounds = sorted(clinically_relevant['head'].unique())

print(f'\nSpinach compounds that target warfarin enzymes/proteins: {len(relevant_compounds)}')
print()
for i, cpd in enumerate(relevant_compounds, 1):
    edges = clinically_relevant[clinically_relevant['head'] == cpd]
    print(f'{i}. {cpd}')
    for rel in sorted(edges['relation'].unique()):
        targets = sorted(edges[edges['relation'] == rel]['tail'].unique())
        for target in targets:
            print(f'   --[{rel}]--> {target}')
