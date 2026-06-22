import os

MAP_PATH = os.path.join('DFinder-main', 'data', 'POMELO_FIDEO-DFI', 'fideo_pomelo_input_map.txt')
INTERACTIONS_PATH = 'pomelo_fideo_interactions.txt'

def load_map(path):
    m = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t')
            # file contains repeating pairs: id \t label
            for i in range(0, len(parts)-1, 2):
                key = parts[i].strip()
                val = parts[i+1].strip()
                if not key:
                    continue
                try:
                    kid = int(key)
                except ValueError:
                    continue
                # prefer the last seen label for an id
                m[kid] = val
    return m

def parse_interactions(path):
    interactions = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            toks = line.split()
            try:
                food = int(toks[0])
            except Exception:
                continue
            drugs = []
            for t in toks[1:]:
                try:
                    drugs.append(int(t))
                except Exception:
                    continue
            interactions.append((food, drugs))
    return interactions

def main():
    mapping = load_map(MAP_PATH)
    interactions = parse_interactions(INTERACTIONS_PATH)

    foods = {}
    all_drug_ids = set()
    for food_id, drug_ids in interactions:
        food_name = mapping.get(food_id, str(food_id))
        mapped_drugs = [mapping.get(d, str(d)) for d in drug_ids]
        foods[food_id] = (food_name, mapped_drugs)
        all_drug_ids.update(drug_ids)

    # write unique food names
    with open('pomelo_foods.txt', 'w', encoding='utf-8') as f:
        for fid, (fname, _) in sorted(foods.items()):
            f.write(f"{fid}\t{fname}\n")

    # write unique drug names
    with open('pomelo_drugs.txt', 'w', encoding='utf-8') as f:
        for did in sorted(all_drug_ids):
            f.write(f"{did}\t{mapping.get(did, str(did))}\n")

    # write mapped interactions (food_name \t comma-separated drug names)
    with open('pomelo_interactions_mapped.txt', 'w', encoding='utf-8') as f:
        for fid, (fname, dlist) in sorted(foods.items()):
            f.write(f"{fid}\t{fname}\t{','.join(dlist)}\n")

    print('Wrote pomelo_foods.txt ({})'.format(len(foods)))
    print('Wrote pomelo_drugs.txt ({})'.format(len(all_drug_ids)))
    print('Wrote pomelo_interactions_mapped.txt ({})'.format(len(foods)))

if __name__ == '__main__':
    main()
