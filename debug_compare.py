import csv

def norm(s):
    if s is None:
        return ''
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    return s.strip().lower()

def read_dict_names(path, key='drug_name'):
    names = set()
    with open(path, encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for r in reader:
            if key in r:
                names.add(norm(r[key]))
            else:
                # fallback to first column
                first = list(r.values())[0] if r else ''
                names.add(norm(first))
    return names

A = read_dict_names('d:\\23AIBox-DFinder\\drugs_cleaned.csv','drug_name')
B = read_dict_names('d:\\23AIBox-DFinder\\drugs_cleaned_with_categories.csv','drug_name')

print('A count', len(A))
print('B count', len(B))
print('amoxicillin in A?', 'amoxicillin' in A)
print('amoxicillin in B?', 'amoxicillin' in B)

common = sorted(x for x in A if x in B)
print('common count', len(common))
print('common sample:', common[:20])

# show raw repr for amoxicillin entries if present
for s in list(A)[:5]:
    if 'amoxicillin' in s:
        print('A sample repr:', repr(s))
for s in list(B)[:20]:
    if 'amoxicillin' in s:
        print('B sample repr:', repr(s))
