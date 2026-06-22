"""
Generate Train Mapping from Categorized Foods and Cleaned Drugs
================================================================
Creates DFinder train.txt by remapping interactions to new food/drug IDs
from the categorized foods and cleaned drugs lists.

Input:
    train_keysentences_dedup.txt  - Current interaction file with deduplicated IDs
    foods_keysentences_final.csv  - Foods before categorization
    foods_categorized.csv         - Foods with categories and updated IDs
    drugs_cleaned_final.csv       - Cleaned drugs list

Output:
    train_final.txt               - DFinder format: drug_id food_id1 food_id2 ...
"""

import csv
import sys
from collections import defaultdict

def normalize(name):
    """Lowercase, strip, collapse whitespace."""
    return name.strip().lower()

def read_categorized_foods(filepath):
    """Read categorized foods, return mapping of canonical_name -> new_food_id"""
    foods = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name_norm = normalize(row['canonical_name'])
            foods[name_norm] = int(row['food_id'])
    return foods

def read_original_foods(filepath):
    """Read original foods before categorization, return canonical_name -> old_food_id"""
    foods = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name_norm = normalize(row['canonical_name'])
            foods[name_norm] = int(row['food_id'])
    return foods

def read_cleaned_drugs(filepath):
    """Read cleaned drugs, return drug_id (int index) -> drug_name"""
    drugs = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            drug_id = int(row['drug_id'])
            drugs[drug_id] = row['drug_name']
    return drugs

def read_interactions(filepath):
    """
    Read interaction file in format: drug_id food_id1 food_id2 ...
    Returns dict: drug_id -> list of food_ids
    """
    interactions = defaultdict(list)
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 1:
                continue
            try:
                drug_id = int(parts[0])
                food_ids = [int(fid) for fid in parts[1:]]
                interactions[drug_id] = food_ids
            except ValueError as e:
                print(f"Warning: Line {line_num} has invalid format: {line}")
                print(f"  Error: {e}")
                continue
    return interactions

def main():
    print("=" * 70)
    print("GENERATING TRAIN MAPPING")
    print("=" * 70)
    
    # Read all input files
    print("\n1. Reading input files...")
    
    print("   - Reading categorized foods...")
    categorized_foods = read_categorized_foods('foods_categorized.csv')
    print(f"     Found {len(categorized_foods)} foods")
    
    print("   - Reading original foods (before categorization)...")
    original_foods = read_original_foods('foods_keysentences_final.csv')
    print(f"     Found {len(original_foods)} foods")
    
    print("   - Reading cleaned drugs...")
    cleaned_drugs = read_cleaned_drugs('drugs_keysentences.csv')
    print(f"     Found {len(cleaned_drugs)} drugs")
    
    print("   - Reading current interactions...")
    interactions = read_interactions('train_keysentences_dedup.txt')
    print(f"     Found {len(interactions)} drugs with interactions")
    
    # Build mapping: old food ID -> new food ID
    print("\n2. Building ID mapping...")
    
    # Create canonical name to old ID mapping
    old_id_to_canonical = {v: k for k, v in original_foods.items()}
    
    # Create ID remap: old_food_id -> new_food_id
    id_remap = {}
    unmapped_count = 0
    
    for old_id, canonical_name_norm in old_id_to_canonical.items():
        if canonical_name_norm in categorized_foods:
            new_id = categorized_foods[canonical_name_norm]
            id_remap[old_id] = new_id
        else:
            unmapped_count += 1
    
    print(f"   - Successfully mapped: {len(id_remap)} food IDs")
    if unmapped_count > 0:
        print(f"   ⚠ Warning: {unmapped_count} food IDs not in categorized list (removed as artifacts)")
    
    # Remap interactions
    print("\n3. Remapping interactions...")
    
    remapped_interactions = {}
    skipped_interactions = 0
    total_food_pairs = 0
    
    for drug_id, food_ids in interactions.items():
        new_food_ids = []
        
        for old_food_id in food_ids:
            if old_food_id in id_remap:
                new_food_ids.append(id_remap[old_food_id])
            else:
                # This food was removed (artifact)
                skipped_interactions += 1
        
        if new_food_ids:  # Only keep if drug still has at least one food
            remapped_interactions[drug_id] = sorted(set(new_food_ids))  # Remove dups, sort
            total_food_pairs += len(new_food_ids)
    
    print(f"   - Remapped {len(remapped_interactions)} drugs")
    print(f"   - Total food associations: {total_food_pairs}")
    if skipped_interactions > 0:
        print(f"   - Skipped {skipped_interactions} food associations (removed artifacts)")
    
    # Write output
    print("\n4. Writing output...")
    
    with open('train_final.txt', 'w', encoding='utf-8') as f:
        for drug_id in sorted(remapped_interactions.keys()):
            food_ids = remapped_interactions[drug_id]
            line = f"{drug_id} " + " ".join(str(fid) for fid in food_ids)
            f.write(line + "\n")
    
    print("   ✓ Wrote train_final.txt")
    
    # Generate summary report
    print("\n5. Generating report...")
    
    report = []
    report.append("=" * 70)
    report.append("TRAIN MAPPING SUMMARY")
    report.append("=" * 70)
    report.append("")
    report.append("INPUT STATISTICS:")
    report.append(f"  Original drugs:              {len(interactions)}")
    report.append(f"  Original food entries:       {len(original_foods)}")
    report.append(f"  Categorized food entries:    {len(categorized_foods)}")
    report.append(f"  Foods removed as artifacts:  {unmapped_count}")
    report.append("")
    report.append("OUTPUT STATISTICS:")
    report.append(f"  Final drugs in mapping:      {len(remapped_interactions)}")
    report.append(f"  Final food associations:     {total_food_pairs}")
    report.append(f"  Food pairs skipped:          {skipped_interactions}")
    report.append("")
    report.append("INTERACTION STATISTICS:")
    
    if remapped_interactions:
        food_counts = [len(fids) for fids in remapped_interactions.values()]
        report.append(f"  Min foods per drug:          {min(food_counts)}")
        report.append(f"  Max foods per drug:          {max(food_counts)}")
        report.append(f"  Avg foods per drug:          {sum(food_counts) / len(food_counts):.2f}")
    
    report.append("")
    report.append("FILES WRITTEN:")
    report.append("  train_final.txt              - DFinder format interactions")
    report.append("  train_mapping_report.txt     - This report")
    report.append("=" * 70)
    
    with open('train_mapping_report.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    
    print('\n'.join(report))

if __name__ == '__main__':
    main()
