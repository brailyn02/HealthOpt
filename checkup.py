import pandas as pd

# Check mechanistic triplet counts
df = pd.read_csv('D:/23AIBox-DFinder/data/processed_hkg/hkg_triplets.tsv', sep='\t', header=None, names=['h','r','t'])
print('=== RELATION COUNTS ===')
print(df['r'].value_counts())
print()

# Mechanistic only
mech = df[df['r'] != 'contains']
print('=== MECHANISTIC TRIPLETS ===')
print(f'Total: {len(mech)}')
print(f'Unique heads: {mech["h"].nunique()}')
print(f'Unique tails: {mech["t"].nunique()}')
print(f'Unique entities: {pd.concat([mech["h"], mech["t"]]).nunique()}')

# Sample some entities to understand naming convention
print()
print('=== SAMPLE MECHANISTIC ENTITIES (heads) ===')
print(mech['h'].unique()[:20])
print()
print('=== SAMPLE MECHANISTIC ENTITIES (tails) ===')
print(mech['t'].unique()[:20])

# Check drug_id_map in LightGCN
print()
print('=== LIGHTGCN DRUG ID MAP (first 10) ===')
lgn_drugs = pd.read_csv('D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/id_maps/drug_id_map.csv')
print(lgn_drugs.head(10))
print(f'Total LightGCN drugs: {len(lgn_drugs)}')

print()
print('=== LIGHTGCN FOOD ID MAP (first 10) ===')
lgn_foods = pd.read_csv('D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/id_maps/food_id_map.csv')
print(lgn_foods.head(10))
print(f'Total LightGCN foods: {len(lgn_foods)}')

# Check HKG entity2id
print()
print('=== HKG ENTITY2ID SAMPLE ===')
e2id = pd.read_csv('D:/23AIBox-DFinder/data/processed_hkg/kge_input/entity2id.txt', sep='\t', header=None, names=['entity','id'])
print(e2id.head(10))
print(f'Total HKG entities: {len(e2id)}')
# How many are drugs vs compounds vs enzymes?
print()
print('Entity prefix counts:')
e2id['prefix'] = e2id['entity'].str.split(':').str[0]
print(e2id['prefix'].value_counts())
