import csv
import sys
import re
import unicodedata

def norm(s):
    if s is None:
        return ''
    s = str(s)
    s = s.strip()
    # remove surrounding quotes
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    # normalize unicode accents
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    # replace non-alphanumeric with space, collapse spaces
    s = re.sub(r"[^a-z0-9]+", ' ', s)
    s = re.sub(r"\s+", ' ', s).strip()
    return s

def read_names_dict(path, key='drug_name'):
    names = set()
    with open(path, encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for r in reader:
            if key in r and r[key] is not None:
                names.add(norm(r[key]))
            else:
                # fallback: first value in the row
                vals = list(r.values())
                if vals:
                    names.add(norm(vals[0]))
    return names


if __name__ == '__main__':
    path_a = 'd:\\23AIBox-DFinder\\drugs_cleaned.csv'
    path_b = 'd:\\23AIBox-DFinder\\drugs_cleaned_with_categories.csv'

    a = read_names_dict(path_a, 'drug_name')
    b = read_names_dict(path_b, 'drug_name')

    missing = sorted(x for x in a if x not in b)

    print(f"drugs in {path_a}: {len(a)}\n")
    print(f"drugs in {path_b}: {len(b)}\n")
    print(f"missing from {path_b}: {len(missing)}\n")
    if missing:
        for m in missing:
            print(m)
    sys.exit(0)
