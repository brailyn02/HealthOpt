from pathlib import Path

food_file = Path(r"d:\23AIBox-DFinder\pomelo_foods_named.txt")
drug_file = Path(r"d:\23AIBox-DFinder\pomelo_drugs_named.txt")
inter_file = Path(r"d:\23AIBox-DFinder\pomelo_interactions_mapped.txt")

def load_mapped(file_path):
    mapped = set()
    total = 0
    with file_path.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) < 3:
                continue
            total += 1
            smi = parts[1].strip()
            name = parts[2].strip()
            if name:
                mapped.add(smi)
    return mapped, total

food_mapped_set, food_total = load_mapped(food_file)
drug_mapped_set, drug_total = load_mapped(drug_file)

# Parse interactions and count
total_pairs = 0
mapped_pairs = 0
pairs_with_food_mapped = 0
pairs_with_drug_mapped = 0
lines_with_any_mapped_pair = 0
unique_mapped_foods_used = set()
unique_mapped_drugs_used = set()

with inter_file.open(encoding='utf-8') as f:
    for line in f:
        line = line.rstrip('\n')
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) < 3:
            continue
        food_smi = parts[1].strip()
        drugs_field = parts[2].strip()
        drug_smiles = [d.strip() for d in drugs_field.split(',') if d.strip()]
        any_mapped_in_line = False
        for d in drug_smiles:
            total_pairs += 1
            food_mapped = food_smi in food_mapped_set
            drug_mapped = d in drug_mapped_set
            if food_mapped:
                pairs_with_food_mapped += 1
            if drug_mapped:
                pairs_with_drug_mapped += 1
            if food_mapped and drug_mapped:
                mapped_pairs += 1
                any_mapped_in_line = True
                unique_mapped_foods_used.add(food_smi)
                unique_mapped_drugs_used.add(d)
        if any_mapped_in_line:
            lines_with_any_mapped_pair += 1

print(f"Mapped food entries (with name): {len(food_mapped_set)} / {food_total}")
print(f"Mapped drug entries (with name): {len(drug_mapped_set)} / {drug_total}")
print(f"Total candidate pairs in Pomelo interactions: {total_pairs}")
print(f"Pairs where both food+drug have names: {mapped_pairs}")
print(f"Pairs where food has name: {pairs_with_food_mapped}")
print(f"Pairs where drug has name: {pairs_with_drug_mapped}")
print(f"Interaction lines with >=1 fully-mapped pair: {lines_with_any_mapped_pair}")
print(f"Unique mapped food SMILES used in mapped pairs: {len(unique_mapped_foods_used)}")
print(f"Unique mapped drug SMILES used in mapped pairs: {len(unique_mapped_drugs_used)}")
