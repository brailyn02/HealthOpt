import pandas as pd

# Load HKG triplets
hkg = pd.read_csv('data/processed_hkg/hkg_triplets.tsv', sep='\t')

# Get all spinach compounds
spinach_edges = hkg[(hkg['head'].str.lower() == 'spinach') & (hkg['relation'] == 'contains')]
spinach_compounds = sorted(spinach_edges['tail'].unique())

print('=' * 100)
print(f'SPINACH COMPOUNDS IN HKG ({len(spinach_compounds)} total)')
print('=' * 100)

for i, compound in enumerate(spinach_compounds, 1):
    # Find what this compound interacts with
    interactions = hkg[(hkg['head'] == compound) & (hkg['relation'] != 'contains')]
    if len(interactions) > 0:
        print(f"\n{i}. {compound}")
        print(f"   Interactions: {len(interactions)} edges")
        for rel in sorted(interactions['relation'].unique()):
            rel_edges = interactions[interactions['relation'] == rel]
            targets = sorted(rel_edges['tail'].unique())
            print(f"     {rel}: {targets}")
    else:
        print(f"\n{i}. {compound} (no interactions in HKG)")

print('\n' + '=' * 100)
print('SUMMARY STATISTICS')
print('=' * 100)
print(f'Total spinach compounds: {len(spinach_compounds)}')

compounds_with_interactions = set()
for cpd in spinach_compounds:
    interactions = hkg[(hkg['head'] == cpd) & (hkg['relation'] != 'contains')]
    if len(interactions) > 0:
        compounds_with_interactions.add(cpd)

print(f'Compounds with interactions: {len(compounds_with_interactions)}')
print(f'Compounds without interactions: {len(spinach_compounds) - len(compounds_with_interactions)}')

# Interaction type breakdown
all_spinach_interactions = hkg[(hkg['head'].isin(spinach_compounds)) & (hkg['relation'] != 'contains')]
print(f'\nTotal interaction edges: {len(all_spinach_interactions)}')
print('\nBy relation type:')
for rel in sorted(all_spinach_interactions['relation'].unique()):
    count = len(all_spinach_interactions[all_spinach_interactions['relation'] == rel])
    print(f'  {rel}: {count}')

# Most connected compounds
print('\nMost connected spinach compounds:')
compound_edge_counts = all_spinach_interactions.groupby('head').size().sort_values(ascending=False)
for cpd, count in compound_edge_counts.head(15).items():
    print(f'  {cpd}: {count} edges')
