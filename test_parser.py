from verify_smiles import extract_smiles, deduplicate
from pathlib import Path

entries = extract_smiles(Path(r'd:\23AIBox-DFinder\north_african_food_drug_interactions.txt'))
uniq = deduplicate(entries)
print(f'Total: {len(entries)}  Unique: {len(uniq)}')
print()
for e in uniq:
    print(f'  L{e["line_no"]:>4}  {e["label"][:30]:<30}  {e["smiles"][:60]}')
