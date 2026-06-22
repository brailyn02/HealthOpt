import json
from pathlib import Path

base = Path(r"d:/23AIBox-DFinder")
cache_file = base / 'smiles_name_cache.json'
foods_file = base / 'pomelo_foods.txt'
drugs_file = base / 'pomelo_drugs.txt'
out_foods = base / 'pomelo_foods_named.txt'
out_drugs = base / 'pomelo_drugs_named.txt'

with cache_file.open('r', encoding='utf-8') as f:
    cache = json.load(f)

missing = 0

def process(infile, outfile):
    global missing
    lines = []
    with infile.open('r', encoding='utf-8') as f:
        for raw in f:
            line = raw.rstrip('\n')
            if not line.strip():
                continue
            # expect tab-separated: id \t smiles or id \t smiles \t label
            parts = line.split('\t')
            if len(parts) < 2:
                # keep as-is
                lines.append(line)
                continue
            idd = parts[0]
            smiles = parts[1]
            name = cache.get(smiles, '')
            if not name:
                name = cache.get(smiles.strip(), '')
            if not name:
                missing += 1
            # write id \t smiles \t name
            lines.append(f"{idd}\t{smiles}\t{name}")
    with outfile.open('w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

process(foods_file, out_foods)
process(drugs_file, out_drugs)
print('Wrote', out_foods.name, 'and', out_drugs.name)
print('Missing names (unmapped SMILES):', missing)
print('Total cache entries:', len(cache))
