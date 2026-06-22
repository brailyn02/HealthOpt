"""
Content-level lineage check:
Does train_final.txt actually feed into unified-DFI/train.txt?

Strategy:
  1. Load train_final.txt → decode drug/food IDs using dfi drugs/foods lists
  2. Load unified-DFI/train.txt → decode using drug_id_map + food_id_map
  3. Check intersection by name
"""
import csv
from collections import defaultdict
import os

# ── Load train_final IDs ─────────────────────────────────────────────────────
# train_final uses drugs_cleaned_with_categories and foods_categorized id spaces

tf_drug_map = {}  # id -> name
with open('D:/23AIBox-DFinder/drugs_cleaned_with_categories.csv', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        tf_drug_map[int(row['drug_id'])] = row['drug_name'].strip().lower()

tf_food_map = {}  # id -> name
with open('D:/23AIBox-DFinder/foods_categorized.csv', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        tf_food_map[int(row['food_id'])] = row['canonical_name'].strip().lower()

# Decode train_final.txt pairs
tf_pairs = set()
with open('D:/23AIBox-DFinder/train_final.txt', encoding='utf-8') as f:
    for line in f:
        toks = line.strip().split()
        if len(toks) < 2: continue
        drug_id = int(toks[0])
        drug_name = tf_drug_map.get(drug_id, f'unk_drug_{drug_id}')
        for food_tok in toks[1:]:
            food_name = tf_food_map.get(int(food_tok), f'unk_food_{food_tok}')
            tf_pairs.add((drug_name, food_name))

print(f"train_final.txt decoded pairs: {len(tf_pairs)}")
print("Sample:", list(tf_pairs)[:5])

# ── Load unified-DFI/train.txt ────────────────────────────────────────────────
uni_drug_map = {}  # id -> name
with open('D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/id_maps/drug_id_map.csv') as f:
    for row in csv.DictReader(f):
        uni_drug_map[int(row['new_id'])] = row['name'].strip().lower()

uni_food_map = {}  # id -> name
with open('D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/id_maps/food_id_map.csv') as f:
    for row in csv.DictReader(f):
        uni_food_map[int(row['new_id'])] = row['name'].strip().lower()

uni_pairs = set()
with open('D:/23AIBox-DFinder/DFinder-main/data/unified-DFI/train.txt', encoding='utf-8') as f:
    for line in f:
        toks = line.strip().split()
        if len(toks) < 2: continue
        drug_id = int(toks[0])
        drug_name = uni_drug_map.get(drug_id, f'unk_{drug_id}')
        for food_tok in toks[1:]:
            food_name = uni_food_map.get(int(food_tok), f'unk_{food_tok}')
            uni_pairs.add((drug_name, food_name))

print(f"\nunified-DFI/train.txt decoded pairs: {len(uni_pairs)}")

# ── Intersection ──────────────────────────────────────────────────────────────
common = tf_pairs & uni_pairs
print(f"\nPairs in BOTH train_final AND unified-DFI/train.txt: {len(common)}")
print(f"train_final coverage in unified-DFI/train.txt: {len(common)/len(tf_pairs)*100:.1f}%")

if common:
    print("\nMatching pairs (first 10):")
    for p in list(common)[:10]:
        print(f"  {p[0]}  x  {p[1]}")
else:
    print("\nNO OVERLAP — train_final pairs do NOT appear in unified-DFI/train.txt by name")
    print("\nSample train_final pairs (decoded):", list(tf_pairs)[:5])
    print("Sample unified pairs:", list(uni_pairs)[:5])
