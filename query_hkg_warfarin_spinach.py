import pandas as pd
from pathlib import Path

# Load HKG triplets
hkg = pd.read_csv('data/processed_hkg/hkg_triplets.tsv', sep='\t')

# Find Warfarin edges (drug to enzyme)
warfarin_edges = hkg[(hkg['head'].str.lower() == 'warfarin') & (hkg['relation'] != 'contains')]
print('=' * 80)
print('HKG: WARFARIN -> ENZYMES/PROTEINS')
print('=' * 80)
print(warfarin_edges[['head','relation','tail']].to_string(index=False))
print(f'\nTotal: {len(warfarin_edges)} edges\n')

# Find Spinach edges (food to compounds)
spinach_edges = hkg[(hkg['head'].str.lower() == 'spinach') & (hkg['relation'] == 'contains')]
print('=' * 80)
print('HKG: SPINACH -> COMPOUNDS')
print('=' * 80)
print(spinach_edges[['head','tail']].to_string(index=False))
print(f'\nTotal: {len(spinach_edges)} compounds\n')

# Find compound->enzyme interactions for spinach compounds
if len(spinach_edges) > 0:
    spinach_compounds = set(spinach_edges['tail'].unique())
    print(f'Spinach compounds ({len(spinach_compounds)} total):\n{sorted(spinach_compounds)}\n')
    
    compound_enzyme = hkg[(hkg['head'].isin(spinach_compounds)) & (hkg['relation'] != 'contains')]
    print('=' * 80)
    print('HKG: SPINACH COMPOUNDS -> ENZYMES/PROTEINS')
    print('=' * 80)
    if len(compound_enzyme) > 0:
        print(compound_enzyme[['head','relation','tail']].to_string(index=False))
        print(f'\nTotal: {len(compound_enzyme)} edges')
        
        # Show intersection with warfarin targets
        warfarin_targets = set(warfarin_edges['tail'].unique())
        print(f'\nWarfarin targets: {sorted(warfarin_targets)}')
        print(f'\nSpinach compounds target enzymes: {set(compound_enzyme["tail"].unique())}')
        
        overlap_targets = compound_enzyme[compound_enzyme['tail'].isin(warfarin_targets)]
        if len(overlap_targets) > 0:
            print(f'\n' + '=' * 80)
            print(f'OVERLAP: SPINACH COMPOUNDS -> WARFARIN TARGETS ({len(overlap_targets)} edges)')
            print('=' * 80)
            print(overlap_targets[['head','relation','tail']].to_string(index=False))
    else:
        print('No compound->enzyme edges found in HKG')
