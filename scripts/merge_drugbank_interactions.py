"""
merge_drugbank_interactions.py

Compares drugbank_drug_food_named.csv against unified_train_interactions.txt.
For each (drug, food) pair in DrugBank that is missing from unified:
  1. If drug name not in unified_drug_master  → add it with a new ID
  2. If food name not in unified_food_master  → add it with a new ID
  3. Add the new (drug_id food_id) pair to the interactions file

Matching is case-insensitive and strip-normalised.
"""

import csv, re
from collections import defaultdict
from pathlib import Path

GENERATED = Path(r'd:\23AIBox-DFinder\generated')

DRUG_MASTER  = GENERATED / 'unified_drug_master.txt'
FOOD_MASTER  = GENERATED / 'unified_food_master.txt'
TRAIN_FILE   = GENERATED / 'unified_train_interactions.txt'
DRUGBANK_CSV = GENERATED / 'drugbank_drug_food_named.csv'


# ── helpers ──────────────────────────────────────────────────────────────────

def normalise(s: str) -> str:
    """Lowercase, collapse whitespace, strip."""
    return re.sub(r'\s+', ' ', str(s).strip().lower())


def load_master(path: Path) -> tuple[dict, dict, int]:
    """
    Returns:
      id_to_name : {int_id: str_name}
      norm_to_id : {normalised_name: int_id}
      max_id     : int
    """
    id_to_name = {}
    norm_to_id = {}
    with path.open(encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line:
                continue
            parts = line.split('\t', 1)
            if len(parts) != 2:
                continue
            idx, name = int(parts[0]), parts[1]
            id_to_name[idx] = name
            norm_to_id[normalise(name)] = idx
    max_id = max(id_to_name) if id_to_name else -1
    return id_to_name, norm_to_id, max_id


def load_interactions(path: Path) -> dict[int, set[int]]:
    """Returns {drug_id: {food_id, ...}}"""
    interactions: dict[int, set[int]] = defaultdict(set)
    with path.open(encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if not parts:
                continue
            drug_id = int(parts[0])
            for fid in parts[1:]:
                interactions[drug_id].add(int(fid))
    return interactions


def write_master(path: Path, id_to_name: dict) -> None:
    lines = [f"{idx}\t{name}" for idx, name in sorted(id_to_name.items())]
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def write_interactions(path: Path, interactions: dict[int, set[int]]) -> None:
    lines = []
    for drug_id in sorted(interactions):
        food_ids = sorted(interactions[drug_id])
        lines.append(f"{drug_id} " + " ".join(str(f) for f in food_ids))
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    # Load existing masters
    drug_id_to_name, drug_norm_to_id, drug_max_id = load_master(DRUG_MASTER)
    food_id_to_name, food_norm_to_id, food_max_id = load_master(FOOD_MASTER)
    interactions = load_interactions(TRAIN_FILE)

    # Snapshot of existing pair count
    existing_pairs = sum(len(v) for v in interactions.values())

    new_drugs_added: list[tuple[int, str]] = []
    new_foods_added: list[tuple[int, str]] = []
    new_pairs_added = 0
    skipped_pairs   = 0

    with open(DRUGBANK_CSV, encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            drug_name = row['drug_name'].strip()
            food_name = row['food_name'].strip()

            dn = normalise(drug_name)
            fn = normalise(food_name)

            # ── Resolve drug ID ──────────────────────────────────────────────
            if dn in drug_norm_to_id:
                drug_id = drug_norm_to_id[dn]
            else:
                # New drug – assign next ID
                drug_max_id += 1
                drug_id = drug_max_id
                drug_id_to_name[drug_id] = drug_name
                drug_norm_to_id[dn] = drug_id
                new_drugs_added.append((drug_id, drug_name))

            # ── Resolve food ID ──────────────────────────────────────────────
            if fn in food_norm_to_id:
                food_id = food_norm_to_id[fn]
            else:
                # New food – assign next ID
                food_max_id += 1
                food_id = food_max_id
                food_id_to_name[food_id] = food_name
                food_norm_to_id[fn] = food_id
                new_foods_added.append((food_id, food_name))

            # ── Check if interaction is already known ────────────────────────
            if food_id in interactions[drug_id]:
                skipped_pairs += 1
                continue

            interactions[drug_id].add(food_id)
            new_pairs_added += 1

    total_pairs = sum(len(v) for v in interactions.values())

    # ── Write updated files ───────────────────────────────────────────────────
    write_master(DRUG_MASTER, drug_id_to_name)
    write_master(FOOD_MASTER, food_id_to_name)
    write_interactions(TRAIN_FILE, interactions)

    # ── Report ────────────────────────────────────────────────────────────────
    print("=" * 60)
    print("MERGE REPORT")
    print("=" * 60)
    print(f"Existing pairs before merge : {existing_pairs:,}")
    print(f"DrugBank pairs processed    : {existing_pairs + new_pairs_added + skipped_pairs:,}")
    print(f"  Already in unified        : {skipped_pairs:,}  (skipped)")
    print(f"  New pairs added           : {new_pairs_added:,}")
    print(f"Total pairs after merge     : {total_pairs:,}")
    print()
    print(f"New drugs added to drug master : {len(new_drugs_added)}")
    for did, dname in new_drugs_added:
        print(f"  [{did}] {dname}")
    print()
    print(f"New foods added to food master : {len(new_foods_added)}")
    for fid, fname in new_foods_added:
        print(f"  [{fid}] {fname}")
    print()
    print(f"Drug master size  : {len(drug_id_to_name):,}")
    print(f"Food master size  : {len(food_id_to_name):,}")
    print(f"Interaction lines : {len(interactions):,} drugs")

if __name__ == '__main__':
    main()
