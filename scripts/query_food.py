from pathlib import Path
root = Path(r'd:/23AIBox-DFinder/generated')
drugs = {}
with (root/'unified_drug_master.txt').open(encoding='utf-8') as f:
    for line in f:
        p = line.strip().split('\t', 1)
        if len(p)==2: drugs[int(p[0])] = p[1]
foods = {}
with (root/'unified_food_master.txt').open(encoding='utf-8') as f:
    for line in f:
        p = line.strip().split('\t', 1)
        if len(p)==2: foods[int(p[0])] = p[1]

# Find chamomile food id
chamomile_ids = {fid for fid,name in foods.items() if 'chamomile' in name.lower()}
print(f"Chamomile food IDs: {chamomile_ids}")
for fid in chamomile_ids:
    print(f"  {fid} -> {foods[fid]}")

# Find all drugs that interact with chamomile
print("\nDrugs that interact with chamomile:")
with (root/'unified_train_interactions.txt').open(encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split()
        if not parts: continue
        drug_id = int(parts[0])
        food_ids = [int(x) for x in parts[1:]]
        for cid in chamomile_ids:
            if cid in food_ids:
                print(f"  drug_id={drug_id} -> {drugs.get(drug_id)}")
                break
