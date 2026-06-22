from pathlib import Path
root = Path(r'd:/23AIBox-DFinder/generated')
drugs = {}
with (root/'unified_drug_master.txt').open(encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split('\t', 1)
        if len(parts) == 2: drugs[int(parts[0])] = parts[1]
foods = {}
with (root/'unified_food_master.txt').open(encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split('\t', 1)
        if len(parts) == 2: foods[int(parts[0])] = parts[1]
with (root/'unified_train_interactions.txt').open(encoding='utf-8') as f:
    lines = []
    for _ in range(5):
        l = f.readline()
        if l.strip(): lines.append(l.strip().split())
print("=== First 5 interaction lines decoded ===")
for parts in lines:
    if not parts: continue
    drug_id = int(parts[0])
    food_ids = [int(x) for x in parts[1:]]
    print(f'\ndrug_id={drug_id} -> "{drugs.get(drug_id)}"')
    for fid in food_ids:
        print(f'  food_id={fid} -> "{foods.get(fid)}"')
