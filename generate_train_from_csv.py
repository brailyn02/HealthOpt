"""
Generate train_final.txt from interactions CSV using cleaned drugs and foods
===========================================================================
Maps drug and food names from dfi_interactions_from_keysentences.csv to their IDs
and generates DFinder format training file.

Input:
    dfi_interactions_from_keysentences.csv   - Raw interactions (drug, food columns)
    drugs_cleaned_with_categories.csv        - Drug names with IDs
    foods_categorized.csv                   - Food names with IDs

Output:
    train_final.txt                         - DFinder format: drug_id food_id1 food_id2 ...
"""

import csv
import re
from collections import defaultdict

def normalize(name):
    """Normalize name for matching: lowercase, strip whitespace, remove special chars"""
    return re.sub(r'\s+', ' ', name.strip().lower())

def read_drugs(filepath):
    """Read drug list, return mapping: normalized_name -> drug_id"""
    drug_map = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            drug_id = int(row['drug_id'])
            drug_name = row['drug_name'].strip()
            norm_name = normalize(drug_name)
            if norm_name:
                drug_map[norm_name] = drug_id
    return drug_map

def read_foods(filepath):
    """Read food list, return mapping: normalized_name -> food_id"""
    food_map = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            food_id = int(row['food_id'])
            canonical_name = row['canonical_name'].strip()
            norm_name = normalize(canonical_name)
            if norm_name:
                food_map[norm_name] = food_id
    return food_map

def read_interactions(filepath):
    """Read interactions CSV, return list of (drug_name, food_name) pairs"""
    interactions = []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            drug = row.get('drug', '').strip()
            food = row.get('food', '').strip()
            if drug and food:
                interactions.append((drug, food))
    return interactions

def main():
    print("=" * 80)
    print("GENERATING TRAIN_FINAL.TXT FROM INTERACTIONS CSV")
    print("=" * 80)
    
    # Read input files
    print("\n1. Reading input files...")
    
    print("   - Reading drugs...")
    drug_map = read_drugs('drugs_cleaned_with_categories.csv')
    print(f"     Found {len(drug_map)} unique drug names")
    
    print("   - Reading foods...")
    food_map = read_foods('foods_categorized.csv')
    print(f"     Found {len(food_map)} unique food names")
    
    print("   - Reading interactions...")
    interactions = read_interactions('dfi_interactions_from_keysentences.csv')
    print(f"     Found {len(interactions)} interaction records")
    
    # Map interactions
    print("\n2. Mapping interactions to IDs...")
    
    drug_to_foods = defaultdict(set)  # drug_id -> set of food_ids
    matched = 0
    unmatched_drugs = set()
    unmatched_foods = set()
    
    for drug_name, food_name in interactions:
        norm_drug = normalize(drug_name)
        norm_food = normalize(food_name)
        
        # Look up IDs
        if norm_drug not in drug_map:
            unmatched_drugs.add(drug_name)
            continue
        if norm_food not in food_map:
            unmatched_foods.add(food_name)
            continue
        
        drug_id = drug_map[norm_drug]
        food_id = food_map[norm_food]
        
        drug_to_foods[drug_id].add(food_id)
        matched += 1
    
    print(f"   - Successfully matched: {matched} interactions")
    print(f"   - Unmatched drugs: {len(unmatched_drugs)}")
    print(f"   - Unmatched foods: {len(unmatched_foods)}")
    
    if unmatched_drugs:
        print(f"\n   Sample unmatched drugs:")
        for drug in sorted(unmatched_drugs)[:10]:
            print(f"     - {drug}")
    
    if unmatched_foods:
        print(f"\n   Sample unmatched foods:")
        for food in sorted(unmatched_foods)[:10]:
            print(f"     - {food}")
    
    # Write output
    print("\n3. Writing train_final.txt...")
    
    with open('train_final.txt', 'w', encoding='utf-8') as f:
        for drug_id in sorted(drug_to_foods.keys()):
            food_ids = sorted(drug_to_foods[drug_id])
            line = f"{drug_id} " + " ".join(str(fid) for fid in food_ids)
            f.write(line + "\n")
    
    total_drugs = len(drug_to_foods)
    total_associations = sum(len(fids) for fids in drug_to_foods.values())
    
    print(f"   ✓ Wrote {total_drugs} drugs with interactions")
    print(f"   ✓ Total food associations: {total_associations}")
    
    # Statistics
    print("\n4. Statistics:")
    food_counts = [len(fids) for fids in drug_to_foods.values()]
    if food_counts:
        print(f"   - Min foods per drug: {min(food_counts)}")
        print(f"   - Max foods per drug: {max(food_counts)}")
        print(f"   - Avg foods per drug: {sum(food_counts) / len(food_counts):.2f}")
    
    # Generate report
    print("\n5. Generating report...")
    
    report = []
    report.append("=" * 80)
    report.append("TRAIN_FINAL.TXT GENERATION REPORT")
    report.append("=" * 80)
    report.append("")
    report.append("INPUT FILES:")
    report.append(f"  dfi_interactions_from_keysentences.csv")
    report.append(f"  drugs_cleaned_with_categories.csv")
    report.append(f"  foods_categorized.csv")
    report.append("")
    report.append("STATISTICS:")
    report.append(f"  Unique drugs in drug list:           {len(drug_map)}")
    report.append(f"  Unique foods in food list:           {len(food_map)}")
    report.append(f"  Total interaction records:           {len(interactions)}")
    report.append(f"  Successfully matched:                {matched}")
    report.append(f"  Unmatched drugs:                     {len(unmatched_drugs)}")
    report.append(f"  Unmatched foods:                     {len(unmatched_foods)}")
    report.append("")
    report.append("OUTPUT:")
    report.append(f"  Drugs with interactions:             {total_drugs}")
    report.append(f"  Total food associations:             {total_associations}")
    if food_counts:
        report.append(f"  Min foods per drug:                  {min(food_counts)}")
        report.append(f"  Max foods per drug:                  {max(food_counts)}")
        report.append(f"  Avg foods per drug:                  {sum(food_counts) / len(food_counts):.2f}")
    report.append("")
    report.append("=" * 80)
    
    with open('train_final_report.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    
    print('\n'.join(report))
    print(f"\nFiles written:")
    print(f"  train_final.txt")
    print(f"  train_final_report.txt")

if __name__ == '__main__':
    main()
