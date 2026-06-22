import pandas as pd

pairs = pd.read_csv('D:/23AIBox-DFinder/confirmed_pairs_final.csv')

lgn_drugs = pd.read_csv('D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/id_maps/drug_id_map.csv')
lgn_foods = pd.read_csv('D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/id_maps/food_id_map.csv')

lgn_drugs = lgn_drugs.dropna(subset=['name'])
lgn_foods = lgn_foods.dropna(subset=['name'])

drug_id_map = {r['name'].lower(): int(r['new_id']) for _, r in lgn_drugs.iterrows()}
food_id_map = {r['name'].lower(): int(r['new_id']) for _, r in lgn_foods.iterrows()}

# Load base train.txt
train_pairs = set()
with open('D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/train.txt') as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) > 1:
            uid = int(parts[0])
            for iid in parts[1:]:
                train_pairs.add((uid, int(iid)))

# Load train.txt.bak (original before fine-tune?)
train_bak_pairs = set()
with open('D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/train.txt.bak') as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) > 1:
            uid = int(parts[0])
            for iid in parts[1:]:
                train_bak_pairs.add((uid, int(iid)))

# Load test.txt
test_pairs = set()
with open('D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/test.txt') as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) > 1:
            uid = int(parts[0])
            for iid in parts[1:]:
                test_pairs.add((uid, int(iid)))

# Load train_neg.txt
neg_pairs = set()
with open('D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/train_neg.txt') as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) > 1:
            uid = int(parts[0])
            for iid in parts[1:]:
                neg_pairs.add((uid, int(iid)))

print(f'Current train.txt pairs:   {len(train_pairs)}')
print(f'train.txt.bak pairs:       {len(train_bak_pairs)}')
print(f'test.txt pairs:            {len(test_pairs)}')
print(f'train_neg.txt pairs:       {len(neg_pairs)}')
print()

# Pairs added by fine-tuning = in current train but not in bak
added_by_finetune = train_pairs - train_bak_pairs
removed_by_finetune = train_bak_pairs - train_pairs
print(f'Pairs ADDED by fine-tune:   {len(added_by_finetune)}')
print(f'Pairs REMOVED by fine-tune: {len(removed_by_finetune)}')
print()

in_train_current = 0
in_train_bak = 0
in_test = 0
not_in_any = 0
no_id = 0

for _, row in pairs.iterrows():
    d = str(row['drug_name']).lower()
    fo = str(row['food_name']).lower()
    did = drug_id_map.get(d)
    fid = food_id_map.get(fo)
    if did is None or fid is None:
        no_id += 1
        continue
    pair = (did, fid)
    if pair in train_pairs:
        in_train_current += 1
    if pair in train_bak_pairs:
        in_train_bak += 1
    if pair in test_pairs:
        in_test += 1
    if pair not in train_pairs and pair not in test_pairs:
        not_in_any += 1

print(f'Confirmed pairs in current train.txt:  {in_train_current}')
print(f'Confirmed pairs in train.txt.bak:      {in_train_bak}')
print(f'Confirmed pairs in test.txt:           {in_test}')
print(f'Confirmed pairs NOT in any split:      {not_in_any}')
print(f'Confirmed pairs with no LGN ID:        {no_id}')
