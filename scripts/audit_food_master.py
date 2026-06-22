"""
Audit unified_food_master.txt for:
1. Vague category labels (herbs, supplements, treatment, etc.)
2. Known drugs that ended up in food list
3. Abbreviations / single-letter codes
4. Other non-food entries
"""
from pathlib import Path
import re

root = Path(r'd:/23AIBox-DFinder/generated')

foods = {}
with (root/'unified_food_master.txt').open(encoding='utf-8') as f:
    for line in f:
        p = line.strip().split('\t', 1)
        if len(p) == 2:
            foods[int(p[0])] = p[1]

# ── Known drugs that appear as foods ──────────────────────────────────────
known_drugs_in_food = {
    'warfarin', 'aspirin', 'piracetam', 'nicardipine', 'cisplatin',
    'doxorubicin', 'bleomycin', 'rifampicin', 'bacitracin', 'metformin',
    'acetaminophen', 'acetylcholine', 'arachidonic acid', 'anandamide',
    'dexamethasone', 'cyclophosphamide', 'tamoxifen', 'paclitaxel',
    'morphine', 'ethanol', 'methanol', 'isoniazid', 'streptomycin',
    'tetracycline', 'penicillin', 'ampicillin', 'amoxicillin',
    'fluoroquinolone', 'fluoroquinolones', 'carbapenems', 'meropenem',
    'cefoxitin', 'leukotriene c4', 'prostaglandin', 'adenosine',
    'androgen', 'androgens', 'corticosterone', 'testosterone',
    'botulinum', 'interferon', 'interleukin',
}

# ── Vague category / non-food labels ─────────────────────────────────────
vague_labels = {
    'herbs', 'supplements', 'supplementation', 'treatment', 'both drugs',
    'anticoagulant', 'anticoagulants', 'antiplatelet', 'antidepressants',
    'anti-malarial', 'antibiotic', 'anticholinestrase', 'aminoglycosides',
    'benzodiazepines', 'activators', 'fractions', 'all fractions',
    'plant crude extract', 'flavonoids', 'phenolic acids',
    'drug', 'drugs', 'medication', 'compound', 'extract',
}

# ── Abbreviations (same logic as drug dedup) ─────────────────────────────
def is_abbreviation(name):
    n = name.strip()
    if len(n) <= 2:
        return True
    if re.fullmatch(r'[A-Z]{2,5}', n):
        return True
    if re.fullmatch(r'[A-Z][a-z]?[0-9+\-]+', n):
        return True
    return False

# ── Scan ──────────────────────────────────────────────────────────────────
categories = {'vague': [], 'drug_in_food': [], 'abbreviation': [], 'clean': []}

for fid, name in foods.items():
    nl = name.lower().strip()
    if nl in vague_labels or any(v in nl for v in ['fraction', 'extract', 'crude']):
        categories['vague'].append((fid, name))
    elif nl in known_drugs_in_food or any(d in nl for d in ['warfarin', 'piracetam', 'cisplatin', 'rifampicin']):
        categories['drug_in_food'].append((fid, name))
    elif is_abbreviation(name):
        categories['abbreviation'].append((fid, name))
    else:
        categories['clean'].append((fid, name))

print(f"Total food entries : {len(foods)}")
print(f"Clean              : {len(categories['clean'])}")
print(f"Vague labels       : {len(categories['vague'])}")
print(f"Drugs in food list : {len(categories['drug_in_food'])}")
print(f"Abbreviations      : {len(categories['abbreviation'])}")

print("\n=== VAGUE LABELS ===")
for fid, name in sorted(categories['vague'], key=lambda x: x[1]):
    print(f"  {fid}\t{name}")

print("\n=== DRUGS FOUND IN FOOD LIST ===")
for fid, name in sorted(categories['drug_in_food'], key=lambda x: x[1]):
    print(f"  {fid}\t{name}")

print("\n=== ABBREVIATIONS IN FOOD LIST ===")
for fid, name in sorted(categories['abbreviation'], key=lambda x: x[1]):
    print(f"  {fid}\t{name}")
