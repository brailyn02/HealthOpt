import torch
import numpy as np
from pathlib import Path

# Load KGE model
mech_dir = Path('data/mechanistic_kge')
ckpt = torch.load(mech_dir / 'mech_best.pt', map_location='cpu')
model_state = ckpt['model_state_dict']

# Load entity/relation maps
entity2id = {}
with open(mech_dir / 'mech_entity2id.txt') as f:
    n = int(f.readline())
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 2:
            entity2id[parts[0]] = int(parts[1])

id2entity = {v: k for k, v in entity2id.items()}

relation2id = {}
with open(mech_dir / 'mech_relation2id.txt') as f:
    n = int(f.readline())
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) == 2:
            relation2id[parts[0]] = int(parts[1])

id2relation = {v: k for k, v in relation2id.items()}

print('=' * 80)
print('KGE MODEL METADATA')
print('=' * 80)
print(f'Total entities: {len(entity2id)}')
print(f'Total relations: {len(relation2id)}')
print(f'Relations: {sorted(relation2id.keys())}')
print(f'Model checkpoint epoch: {ckpt.get("epoch", "N/A")}')
print(f'Best validation MRR: {ckpt.get("best_mrr", "N/A")}\n')

# Check if Warfarin and common spinach compounds are in KGE
print('=' * 80)
print('KGE: ENTITY SEARCH')
print('=' * 80)

# Find warfarin-related entities
warfarin_entities = [e for e in entity2id.keys() if 'warfarin' in e.lower()]
print(f'\nWarfarin-related entities ({len(warfarin_entities)}):')
for e in warfarin_entities[:10]:
    print(f'  {e}')

# Find spinach-related entities
spinach_entities = [e for e in entity2id.keys() if 'spinach' in e.lower()]
print(f'\nSpinach-related entities ({len(spinach_entities)}):')
for e in spinach_entities[:10]:
    print(f'  {e}')

# Find vitamin K, Phylloquinone, etc
vitamin_entities = [e for e in entity2id.keys() if any(x in e.lower() for x in ['vitamin k', 'phyllo', 'tocopherol', 'lutein', 'neoxanthin'])]
print(f'\nVitamin K and spinach compound entities ({len(vitamin_entities)}):')
for e in vitamin_entities[:15]:
    print(f'  {e}')

# Load triplets to verify structure
triplets_file = mech_dir / 'mech_triplets.tsv'
if triplets_file.exists():
    triplets = []
    with open(triplets_file) as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) == 3:
                triplets.append(tuple(parts))
    print(f'\nTotal mechanistic triplets in KGE: {len(triplets)}')
    
    # Find warfarin triplets
    warfarin_triplets = [t for t in triplets if 'warfarin' in t[0].lower()]
    print(f'Warfarin triplets in KGE: {len(warfarin_triplets)}')
    if warfarin_triplets:
        print('Sample Warfarin triplets:')
        for t in warfarin_triplets[:10]:
            print(f'  {t[0]} --[{t[1]}]--> {t[2]}')
    
    # Find spinach triplets
    spinach_triplets = [t for t in triplets if 'spinach' in t[0].lower()]
    print(f'\nSpinach triplets in KGE: {len(spinach_triplets)}')
    if spinach_triplets:
        print('Sample Spinach triplets:')
        for t in spinach_triplets[:10]:
            print(f'  {t[0]} --[{t[1]}]--> {t[2]}')
    
    # Find connections between warfarin targets and spinach compounds
    warfarin_targets = set(t[2] for t in warfarin_triplets if t[1] != 'contains')
    spinach_compounds = set(t[2] for t in spinach_triplets if t[1] == 'contains')
    print(f'\nWarfarin enzyme/protein targets ({len(warfarin_targets)}):')
    for t in sorted(warfarin_targets)[:15]:
        print(f'  {t}')
    
    print(f'\nSpinach compounds ({len(spinach_compounds)}):')
    for t in sorted(spinach_compounds)[:15]:
        print(f'  {t}')
    
    # Find overlaps
    overlaps = [t for t in triplets if t[0] in spinach_compounds and t[2] in warfarin_targets and t[1] != 'contains']
    print(f'\nSpinach compounds interacting with Warfarin targets: {len(overlaps)}')
    if overlaps:
        print('Interactions:')
        for t in overlaps[:20]:
            print(f'  {t[0]} --[{t[1]}]--> {t[2]}')
