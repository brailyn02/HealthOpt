import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

INPUT_FOODS = Path('pomelo_foods.txt')
INPUT_DRUGS = Path('pomelo_drugs.txt')
CACHE_FILE = Path('smiles_name_cache.json')

def load_smiles_files():
    smiles = {}
    for p in (INPUT_FOODS, INPUT_DRUGS):
        with p.open(encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('\t', 1)
                if len(parts) < 2:
                    continue
                sid, smi = parts[0].strip(), parts[1].strip()
                smiles[smi] = smiles.get(smi, 0) + 1
    return sorted(smiles.keys(), key=lambda s: -smiles[s])

def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}

def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')

def query_pubchem_name(smiles):
    # Use PUG-REST: try to get 'Title' then 'IUPACName' then first synonym
    base = 'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/'
    q = urllib.parse.quote(smiles, safe='')
    props = 'IUPACName,Title'
    url = f"{base}{q}/property/{props}/JSON"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.load(resp)
            props = data.get('PropertyTable', {}).get('Properties', [{}])[0]
            title = props.get('Title')
            iupac = props.get('IUPACName')
            if title:
                return title
            if iupac:
                return iupac
    except Exception:
        pass
    # fallback to synonyms endpoint
    url2 = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{q}/synonyms/JSON"
    try:
        with urllib.request.urlopen(url2, timeout=30) as resp:
            data = json.load(resp)
            syns = data.get('InformationList', {}).get('Information', [{}])[0].get('Synonym', [])
            if syns:
                # prefer common-looking names (not raw SMILES)
                for s in syns:
                    if not any(ch in s for ch in '#/=\\[]()@'):
                        return s
                return syns[0]
    except Exception:
        pass
    return None

def map_all(limit=None, delay=0.2):
    smiles_list = load_smiles_files()
    cache = load_cache()
    total = len(smiles_list)
    to_process = [s for s in smiles_list if s not in cache]
    if limit:
        to_process = to_process[:limit]
    for idx, smi in enumerate(to_process, 1):
        name = query_pubchem_name(smi)
        cache[smi] = name if name else ''
        if idx % 10 == 0:
            save_cache(cache)
        time.sleep(delay)
    save_cache(cache)
    return cache

def apply_mapping(cache):
    def replace_file(inpath, outpath):
        with open(inpath, encoding='utf-8') as inf, open(outpath, 'w', encoding='utf-8') as outf:
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

    replace_file(INPUT_FOODS, Path('pomelo_foods_named.txt'))
    replace_file(INPUT_DRUGS, Path('pomelo_drugs_named.txt'))

def main():
    import sys
    limit = None
    delay = 0.15
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except Exception:
            limit = None
    if len(sys.argv) > 2:
        try:
            delay = float(sys.argv[2])
        except Exception:
            delay = 0.15

    print('Loading SMILES...')
    smi_count = len(load_smiles_files())
    print(f'Unique SMILES to consider: {smi_count}')
    cache = load_cache()
    print(f'Cached entries: {len(cache)}')
    cache = map_all(limit=limit, delay=delay)
    print(f'Cache size after run: {len(cache)}')
    apply_mapping(cache)
    print('Wrote pomelo_foods_named.txt and pomelo_drugs_named.txt')

if __name__ == '__main__':
    main()
