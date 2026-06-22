"""
Targeted fixes to unified_food_master.txt and unified_train_interactions.txt:
  1. Rename "Bergamot Essential Oil" → "bergamot"
  2. Rename "Foeniculum vulgare (fennel) essential oil" → "fennel"
  3. Merge "Pinus Halepensis Essential Oil" (280) into "Pinus Halepensis" (279), remove 280
  4. Remove "alcohol" (0)
  5. Re-index food IDs to be contiguous after removals
"""
from pathlib import Path

root = Path(r'd:/23AIBox-DFinder/generated')

# Load food master (id -> name)
foods = {}
with (root/'unified_food_master.txt').open(encoding='utf-8') as f:
    for line in f:
        p = line.strip().split('\t', 1)
        if len(p) == 2:
            foods[int(p[0])] = p[1]

# Load interactions
drug_to_foods = {}
with (root/'unified_train_interactions.txt').open(encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split()
        if parts:
            drug_to_foods[int(parts[0])] = list(int(x) for x in parts[1:])

# Find IDs dynamically by name
def find_id(name_lower):
    for fid, n in foods.items():
        if n.lower() == name_lower:
            return fid
    return None

id_alcohol   = find_id('alcohol')
id_bergamot_oil = find_id('bergamot essential oil')
id_fennel_oil   = find_id('foeniculum vulgare (fennel) essential oil')
id_pinus_oil    = find_id('pinus halepensis essential oil')
id_pinus        = find_id('pinus halepensis')

print(f"alcohol id            : {id_alcohol}")
print(f"bergamot essential oil: {id_bergamot_oil}")
print(f"fennel essential oil  : {id_fennel_oil}")
print(f"pinus halepensis oil  : {id_pinus_oil}")
print(f"pinus halepensis      : {id_pinus}")

# 1. Rename bergamot essential oil → bergamot
if id_bergamot_oil is not None:
    foods[id_bergamot_oil] = 'bergamot'
    print(f"Renamed {id_bergamot_oil}: bergamot")

# 2. Rename fennel essential oil → fennel
if id_fennel_oil is not None:
    foods[id_fennel_oil] = 'fennel'
    print(f"Renamed {id_fennel_oil}: fennel")

# 3. Merge pinus essential oil → pinus
to_remove = set()
if id_pinus_oil is not None and id_pinus is not None:
    # Replace all occurrences of id_pinus_oil with id_pinus in interactions
    for did in drug_to_foods:
        drug_to_foods[did] = [
            id_pinus if fid == id_pinus_oil else fid
            for fid in drug_to_foods[did]
        ]
        # deduplicate while preserving order
        seen = set()
        drug_to_foods[did] = [x for x in drug_to_foods[did] if not (x in seen or seen.add(x))]
    to_remove.add(id_pinus_oil)
    del foods[id_pinus_oil]
    print(f"Merged {id_pinus_oil} (pinus oil) → {id_pinus} (pinus halepensis)")

# 4. Remove alcohol
if id_alcohol is not None:
    for did in drug_to_foods:
        drug_to_foods[did] = [fid for fid in drug_to_foods[did] if fid != id_alcohol]
    to_remove.add(id_alcohol)
    del foods[id_alcohol]
    print(f"Removed {id_alcohol} (alcohol)")

# 5. Re-index food IDs contiguously
sorted_ids = sorted(foods.keys())
old_to_new = {old: new for new, old in enumerate(sorted_ids)}
new_foods = {old_to_new[old]: name for old, name in foods.items()}

new_drug_to_foods = {}
for did, fids in drug_to_foods.items():
    new_fids = sorted({old_to_new[f] for f in fids if f in old_to_new})
    if new_fids:
        new_drug_to_foods[did] = new_fids

# Write food master
food_out = root / 'unified_food_master.txt'
with food_out.open('w', encoding='utf-8') as f:
    for new_id in sorted(new_foods.keys()):
        f.write(f"{new_id}\t{new_foods[new_id]}\n")

# Write interactions
inter_out = root / 'unified_train_interactions.txt'
with inter_out.open('w', encoding='utf-8') as f:
    for did in sorted(new_drug_to_foods.keys()):
        fids = new_drug_to_foods[did]
        f.write(' '.join([str(did)] + [str(x) for x in fids]) + '\n')

total_pairs = sum(len(v) for v in new_drug_to_foods.values())
print(f"\nFinal foods: {len(new_foods)}")
print(f"Interaction lines: {len(new_drug_to_foods)}")
print(f"Total positive pairs: {total_pairs}")
print(f"\nVerify chamomile, bergamot, fennel, pinus:")
for nid, name in new_foods.items():
    if any(k in name.lower() for k in ['chamomile','bergamot','fennel','pinus','nigella']):
        print(f"  {nid}: {name}")
