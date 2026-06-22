import csv

train_edges = set()
with open(r'D:\23AIBox-DFinder\DFinder-main\data\unified-DFI\train.txt') as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        food_id = parts[0]
        for drug_id in parts[1:]:
            train_edges.add((food_id, drug_id))

print(f'Train edges total: {len(train_edges)}')

with open(r'D:\23AIBox-DFinder\confirmed_pairs_final.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

already = []
novel = []
for row in rows:
    key = (str(row['food_id']), str(row['drug_id']))
    if key in train_edges:
        already.append(row)
    else:
        novel.append(row)

print(f'Total pairs      : {len(rows)}')
print(f'Already in train : {len(already)} ({100*len(already)//len(rows)}%)')
print(f'Novel (new edges): {len(novel)} ({100*len(novel)//len(rows)}%)')
print(f'Unique food IDs in novel : {len(set(r["food_id"] for r in novel))}')
print(f'Unique drug IDs in novel : {len(set(r["drug_id"] for r in novel))}')

# Show breakdown by verdict
from collections import Counter
verdict_counts = Counter(r['verdict'] for r in novel)
print('\nNovel pairs by verdict:')
for v, c in verdict_counts.most_common():
    print(f'  {v:<25} {c}')
