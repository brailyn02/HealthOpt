from pathlib import Path
import csv

root = Path(r"d:/23AIBox-DFinder")
# Inputs
drugs_csv = root / 'drugs_cleaned_with_categories.csv'
foods_csv = root / 'foods_categorized.csv'
train_kaggle = root / 'train(kaggle).txt'
train_final = root / 'train_final.txt'
pomelo_inter_mapped = root / 'pomelo_interactions_mapped.txt'
pomelo_foods_named = root / 'pomelo_foods_named.txt'
pomelo_drugs_named = root / 'pomelo_drugs_named.txt'

# Outputs
out_dir = root / 'generated'
out_dir.mkdir(exist_ok=True)
unified_drugs_file = out_dir / 'unified_drugs.tsv'
unified_foods_file = out_dir / 'unified_foods.tsv'
unified_interactions = out_dir / 'unified_interactions.txt'
missing_report = out_dir / 'missing_drugs_in_interactions.txt'

# Helpers
def load_drug_csv(path):
    id2name = {}
    name2id = {}
    with path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            did = row['drug_id'].strip()
            name = row['drug_name'].strip()
            id2name[int(did)] = name
            name2id[name.lower()] = int(did)
    return id2name, name2id

def load_food_csv(path):
    id2name = {}
    name2id = {}
    with path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            fid = int(row['food_id'])
            name = row['canonical_name'].strip()
            id2name[fid] = name
            name2id[name.lower()] = fid
    return id2name, name2id

# Load canonical lists
drug_id2name, drug_name2id = load_drug_csv(drugs_csv)
food_id2name, food_name2id = load_food_csv(foods_csv)

# Collect interactions as (food_name, drug_name)
inter_pairs = set()
found_drug_names = set()
found_food_names = set()

# Parse train(kaggle)
def parse_indexed_interactions(path, food_map, drug_map):
    pairs = set()
    with path.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            food_idx = parts[0]
            try:
                fidx = int(food_idx)
            except ValueError:
                continue
            food_name = food_map.get(fidx)
            if not food_name:
                continue
            for token in parts[1:]:
                try:
                    didx = int(token)
                except ValueError:
                    continue
                dname = drug_map.get(didx)
                if not dname:
                    continue
                pairs.add((food_name, dname))
    return pairs

pairs_kaggle = parse_indexed_interactions(train_kaggle, food_id2name, drug_id2name)
pairs_final = parse_indexed_interactions(train_final, food_id2name, drug_id2name)

for p in pairs_kaggle | pairs_final:
    inter_pairs.add(p)
    found_food_names.add(p[0].lower())
    found_drug_names.add(p[1].lower())

# Parse Pomelo: build SMILES->name maps from named files
smi2drugname = {}
smi2foodname = {}
if pomelo_drugs_named.exists():
    with pomelo_drugs_named.open(encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 3:
                # parts: idx, SMILES, name
                smi = parts[1].strip()
                name = parts[2].strip()
                if name:
                    smi2drugname[smi] = name
if pomelo_foods_named.exists():
    with pomelo_foods_named.open(encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 3:
                smi = parts[1].strip()
                name = parts[2].strip()
                if name:
                    smi2foodname[smi] = name
# parse pomelo interactions mapping (smiles)
if pomelo_inter_mapped.exists():
    with pomelo_inter_mapped.open(encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) < 3:
                continue
            food_smi = parts[1].strip()
            drug_smiles = [d.strip() for d in parts[2].split(',') if d.strip()]
            food_name = smi2foodname.get(food_smi)
            for d in drug_smiles:
                dname = smi2drugname.get(d)
                if food_name and dname:
                    inter_pairs.add((food_name, dname))
                    found_food_names.add(food_name.lower())
                    found_drug_names.add(dname.lower())

# Now check coverage: which drugs from drugs CSV are present
all_drug_names = {n.lower():did for did,n in drug_id2name.items()}
present = set()
for name_l in all_drug_names:
    if name_l in found_drug_names:
        present.add(name_l)
missing = set(all_drug_names.keys()) - present

# Write missing report (top 200)
with missing_report.open('w', encoding='utf-8') as out:
    out.write(f"Total drugs in drugs_cleaned_with_categories.csv: {len(all_drug_names)}\n")
    out.write(f"Drugs present in interactions: {len(present)}\n")
    out.write(f"Drugs missing from interactions: {len(missing)}\n\n")
    for i,name in enumerate(sorted(missing)):
        out.write(f"{i+1}\t{all_drug_names[name]}\t{name}\n")

# Build unified drug list: start with canonical drugs, append any found_drug_names not in canonical
unified_drug_names = []
lower_to_unified_id = {}
# add canonical in order of drug_id
for did in sorted(drug_id2name.keys()):
    name = drug_id2name[did]
    uid = len(unified_drug_names)
    unified_drug_names.append((uid, name))
    lower_to_unified_id[name.lower()] = uid
# append extra drugs from pomelo or interactions not in canonical
extra_drugs = sorted([n for n in found_drug_names if n not in lower_to_unified_id])
for n in extra_drugs:
    uid = len(unified_drug_names)
    unified_drug_names.append((uid, n))
    lower_to_unified_id[n] = uid

# Build unified food list similarly
unified_food_names = []
lower_food_to_unified_id = {}
# canonical foods first
for fid in sorted(food_id2name.keys()):
    name = food_id2name[fid]
    uid = len(unified_food_names)
    unified_food_names.append((uid, name))
    lower_food_to_unified_id[name.lower()] = uid
# append extra foods found
extra_foods = sorted([n for n in found_food_names if n not in lower_food_to_unified_id])
for n in extra_foods:
    uid = len(unified_food_names)
    unified_food_names.append((uid, n))
    lower_food_to_unified_id[n] = uid

# Build interactions mapping using unified ids
food_to_drugids = {}
for f_name,d_name in inter_pairs:
    fid = lower_food_to_unified_id.get(f_name.lower())
    did = lower_to_unified_id.get(d_name.lower())
    if fid is None or did is None:
        continue
    food_to_drugids.setdefault(fid, set()).add(did)

# Write unified files
with unified_drugs_file.open('w', encoding='utf-8') as f:
    for uid,name in unified_drug_names:
        f.write(f"{uid}\t{name}\n")
with unified_foods_file.open('w', encoding='utf-8') as f:
    for uid,name in unified_food_names:
        f.write(f"{uid}\t{name}\n")
with unified_interactions.open('w', encoding='utf-8') as f:
    for fid in sorted(food_to_drugids.keys()):
        drugs = sorted(food_to_drugids[fid])
        if not drugs:
            continue
        line = ' '.join([str(fid)] + [str(d) for d in drugs])
        f.write(line + '\n')

# Summary print
print(f"Wrote unified files to: {out_dir}")
print(f"Canonical drugs: {len(all_drug_names)}; present in interactions: {len(present)}; missing: {len(missing)}")
print(f"Canonical foods: {len(food_id2name)}; foods used in interactions: {len(found_food_names)}")
print(f"Unified drugs total: {len(unified_drug_names)}")
print(f"Unified foods total: {len(unified_food_names)}")
print(f"Unified interaction lines: {len(food_to_drugids)}")
print(f"Missing report: {missing_report}")
print('Done')
