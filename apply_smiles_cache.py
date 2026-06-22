import json
from pathlib import Path

CACHE_FILE = Path('smiles_name_cache.json')
INPUT_FOODS = Path('pomelo_foods.txt')
INPUT_DRUGS = Path('pomelo_drugs.txt')

def load_cache():
    return json.loads(CACHE_FILE.read_text(encoding='utf-8'))

def apply_file(inp, out):
    cache = load_cache()
    with inp.open(encoding='utf-8') as inf, out.open('w', encoding='utf-8') as outf:
        for line in inf:
            parts = line.strip().split('\t', 1)
            if len(parts) < 2:
                continue
            id_, smi = parts[0], parts[1]
            name = cache.get(smi) or ''
            if name:
                outf.write(f"{id_}\t{name}\t{smi}\n")
            else:
                outf.write(f"{id_}\t{smi}\n")

def main():
    apply_file(INPUT_FOODS, Path('pomelo_foods_named.txt'))
    apply_file(INPUT_DRUGS, Path('pomelo_drugs_named.txt'))
    print('Wrote pomelo_foods_named.txt and pomelo_drugs_named.txt')

if __name__ == '__main__':
    main()
