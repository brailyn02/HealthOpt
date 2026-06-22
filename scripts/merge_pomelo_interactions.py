"""
merge_pomelo_interactions.py

Merges pomelo_fideo_interactions.txt into the unified dataset:
  1. Resolves drug/food names from pomelo_foods_named.txt / pomelo_drugs_named.txt
  2. Adds missing drug names to unified_drug_master.txt
  3. Adds missing food compounds to unified_food_master.txt
  4. Saves SMILES for new food compounds to generated/pomelo_food_smiles.csv
  5. Saves SMILES for new/existing drugs to generated/pomelo_drug_smiles.csv
  6. Merges missing (drug,food) pairs into unified_train_interactions.txt

pomelo file layout:
  pomelo_foods_named.txt  — ID 0..622   = DRUGS  (id\tSMILES\tName)
  pomelo_drugs_named.txt  — ID 623..940 = FOODS  (id\tSMILES\tName)
  pomelo_fideo_interactions.txt — drug_id food_id1 food_id2 ...
"""

import csv, re
from collections import defaultdict
from pathlib import Path

ROOT      = Path(r'd:\23AIBox-DFinder')
GENERATED = ROOT / 'generated'

DRUG_MASTER  = GENERATED / 'unified_drug_master.txt'
FOOD_MASTER  = GENERATED / 'unified_food_master.txt'
TRAIN_FILE   = GENERATED / 'unified_train_interactions.txt'

POMELO_DRUGS_FILE = ROOT / 'pomelo_foods_named.txt'   # actually drugs
POMELO_FOODS_FILE = ROOT / 'pomelo_drugs_named.txt'   # actually food compounds
POMELO_INTER_FILE = ROOT / 'pomelo_fideo_interactions.txt'


def norm(s: str) -> str:
    return re.sub(r'\s+', ' ', str(s).strip().lower())


def load_pomelo_named(path: Path) -> dict[int, tuple[str, str]]:
    """Returns {id: (smiles, name)}. Name may be empty for unnamed entries."""
    result = {}
    with path.open(encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line:
                continue
            parts = line.split('\t')
            idx = int(parts[0])
            smiles = parts[1].strip() if len(parts) >= 2 else ''
            name   = parts[2].strip() if len(parts) >= 3 else ''
            # If no name column but there is a 2nd column that looks like a name
            # (no stereochemistry chars), handle gracefully
            result[idx] = (smiles, name)
    return result


def load_pomelo_interactions(path: Path) -> dict[int, set[int]]:
    result: dict[int, set[int]] = defaultdict(set)
    with path.open(encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if not parts:
                continue
            drug_id = int(parts[0])
            for fid in parts[1:]:
                result[drug_id].add(int(fid))
    return result


def load_master(path: Path) -> tuple[dict[int,str], dict[str,int], int]:
    id_to_name: dict[int,str] = {}
    norm_to_id: dict[str,int] = {}
    with path.open(encoding='utf-8') as f:
        for line in f:
            if '\t' not in line:
                continue
            idx_s, name = line.rstrip('\n').split('\t', 1)
            idx = int(idx_s)
            id_to_name[idx] = name
            norm_to_id[norm(name)] = idx
    max_id = max(id_to_name) if id_to_name else -1
    return id_to_name, norm_to_id, max_id


def load_interactions(path: Path) -> dict[int, set[int]]:
    result: dict[int, set[int]] = defaultdict(set)
    with path.open(encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if not parts:
                continue
            drug_id = int(parts[0])
            for fid in parts[1:]:
                result[drug_id].add(int(fid))
    return result


def write_master(path: Path, id_to_name: dict) -> None:
    lines = [f"{idx}\t{name}" for idx, name in sorted(id_to_name.items())]
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def write_interactions(path: Path, interactions: dict[int, set[int]]) -> None:
    lines = []
    for drug_id in sorted(interactions):
        food_ids = sorted(interactions[drug_id])
        lines.append(f"{drug_id} " + " ".join(str(f) for f in food_ids))
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    # ── Load sources ─────────────────────────────────────────────────────────
    pomelo_drug_map  = load_pomelo_named(POMELO_DRUGS_FILE)   # {id: (smiles,name)} — actual drugs
    pomelo_food_map  = load_pomelo_named(POMELO_FOODS_FILE)   # {id: (smiles,name)} — actual foods
    pomelo_inter     = load_pomelo_interactions(POMELO_INTER_FILE)

    drug_id_to_name, drug_norm_to_id, drug_max_id = load_master(DRUG_MASTER)
    food_id_to_name, food_norm_to_id, food_max_id = load_master(FOOD_MASTER)
    interactions = load_interactions(TRAIN_FILE)

    existing_pairs = sum(len(v) for v in interactions.values())

    # ── Track additions ───────────────────────────────────────────────────────
    new_drugs:  list[tuple[int,str,str]] = []   # (id, name, smiles)
    new_foods:  list[tuple[int,str,str]] = []
    new_pairs   = 0
    skip_pairs  = 0
    skip_noname = 0

    # ── Process each pomelo interaction ──────────────────────────────────────
    for pomelo_drug_id, pomelo_food_ids in pomelo_inter.items():
        drug_smiles, drug_name = pomelo_drug_map.get(pomelo_drug_id, ('', ''))
        if not drug_name:
            skip_noname += len(pomelo_food_ids)
            continue

        dn = norm(drug_name)

        # Resolve or add drug
        if dn in drug_norm_to_id:
            drug_id = drug_norm_to_id[dn]
        else:
            drug_max_id += 1
            drug_id = drug_max_id
            drug_id_to_name[drug_id] = drug_name
            drug_norm_to_id[dn] = drug_id
            new_drugs.append((drug_id, drug_name, drug_smiles))

        for pomelo_food_id in pomelo_food_ids:
            food_smiles, food_name = pomelo_food_map.get(pomelo_food_id, ('', ''))
            if not food_name:
                skip_noname += 1
                continue

            fn = norm(food_name)

            # Resolve or add food
            if fn in food_norm_to_id:
                food_id = food_norm_to_id[fn]
            else:
                food_max_id += 1
                food_id = food_max_id
                food_id_to_name[food_id] = food_name
                food_norm_to_id[fn] = food_id
                new_foods.append((food_id, food_name, food_smiles))

            # Add interaction if missing
            if food_id in interactions[drug_id]:
                skip_pairs += 1
            else:
                interactions[drug_id].add(food_id)
                new_pairs += 1

    total_pairs = sum(len(v) for v in interactions.values())

    # ── Write updated masters + interactions ─────────────────────────────────
    write_master(DRUG_MASTER, drug_id_to_name)
    write_master(FOOD_MASTER, food_id_to_name)
    write_interactions(TRAIN_FILE, interactions)

    # ── Write SMILES sidecar files ────────────────────────────────────────────
    food_smiles_path = GENERATED / 'pomelo_food_smiles.csv'
    with food_smiles_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['food_id', 'food_name', 'smiles'])
        for fid, fname, fsmi in sorted(new_foods, key=lambda x: x[0]):
            w.writerow([fid, fname, fsmi])

    drug_smiles_path = GENERATED / 'pomelo_drug_smiles.csv'
    with drug_smiles_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['drug_id', 'drug_name', 'smiles'])
        for did, dname, dsmi in sorted(new_drugs, key=lambda x: x[0]):
            w.writerow([did, dname, dsmi])

    # ── Report ────────────────────────────────────────────────────────────────
    print("=" * 62)
    print("POMELO MERGE REPORT")
    print("=" * 62)
    print(f"Pomelo unique drug-food pairs (raw)  : {sum(len(v) for v in pomelo_inter.values()):,}")
    print(f"  Skipped (no name resolved)         : {skip_noname:,}")
    print(f"  Already in unified                 : {skip_pairs:,}")
    print(f"  New pairs added                    : {new_pairs:,}")
    print()
    print(f"Pairs before merge : {existing_pairs:,}")
    print(f"Pairs after merge  : {total_pairs:,}")
    print()
    print(f"New drugs added    : {len(new_drugs)}")
    for did, dname, _ in sorted(new_drugs, key=lambda x: x[1]):
        print(f"  [{did}] {dname}")
    print()
    print(f"New foods added    : {len(new_foods)}")
    for fid, fname, fsmi in sorted(new_foods, key=lambda x: x[1]):
        smiles_preview = fsmi[:50] + '…' if len(fsmi) > 50 else fsmi
        print(f"  [{fid}] {fname}  |  {smiles_preview}")
    print()
    print(f"Drug master size   : {len(drug_id_to_name):,}")
    print(f"Food master size   : {len(food_id_to_name):,}")
    print(f"Interaction lines  : {len(interactions):,} drugs")
    print()
    print(f"SMILES saved → {food_smiles_path.name}  ({len(new_foods)} foods)")
    print(f"SMILES saved → {drug_smiles_path.name}  ({len(new_drugs)} drugs)")


if __name__ == '__main__':
    main()
