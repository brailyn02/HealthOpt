"""
Cross-check NA dish compounds from na_interaction_verification_v3.txt
against CPD: entities in KGE entity2id.txt
"""
import re

# --- Load KGE CPD entity names (lowercase) ---
cpd_names = set()
with open(r'D:\23AIBox-DFinder\data\processed_hkg\kge_input\entity2id.txt', encoding='utf-8') as f:
    for line in f:
        parts = line.rstrip('\n').split('\t')
        if parts[0].startswith('CPD:'):
            cpd_names.add(parts[0][4:].lower())

print(f'Total CPD entities in KGE: {len(cpd_names)}')

# --- Parse dishes + compounds from verification file ---
dishes = {}
current_dish = None

with open(r'D:\23AIBox-DFinder\na_interaction_verification_v3.txt', encoding='utf-8') as f:
    for line in f:
        m = re.match(r'^Dish \d+: (.+)', line.strip())
        if m:
            current_dish = m.group(1).strip()
            dishes[current_dish] = set()
            continue
        m = re.match(r'^\s+[✓~?].+?\s{2,}(.+?)\s{2,}→', line)
        if m and current_dish:
            cpd_raw = m.group(1).strip()
            cpd_clean = re.sub(r'\s*\(.*?\)\s*$', '', cpd_raw).strip()
            # Skip combos and non-chemical labels
            if ('+' not in cpd_clean and '/' not in cpd_clean and
                    '\u2014' not in cpd_clean and ':' not in cpd_clean):
                dishes[current_dish].add(cpd_clean)

# Non-chemical structural labels to skip
NOT_CHEMICALS = {
    'DenseMatrix', 'HydrationMatrix', 'LipidCoatedStarch', 'LipidSponge',
    'ShortcrustFriableMatrix', 'Shortcrust-FriableMatrix', 'ZeroFermentation',
    'GelatinisedFlour', 'Butter Emulsion', 'Oxidised Lipids',
    'Allicin-LateAdd', 'Sat.Fats', 'Saturated Lipids', 'Plant Protein',
    'Non-Heme Fe', 'NonHemeIron', 'Pyrodextrins', 'BraidedLattice+3mm',
}

# Alias map for fuzzy matching
ALIASES = {
    'Beta-Carotene':          ['beta-carotene', 'beta carotene', 'carotene'],
    'Amylopectin':            ['amylopectin'],
    'Purines':                ['purine'],
    'Tannins':                ['tannin'],
    'Saponins':               ['saponin'],
    'Soluble Fiber':          ['soluble fiber', 'soluble dietary fiber', 'pectin'],
    'I3C':                    ['indole-3-carbinol'],
    'Limonene':               ['limonene', 'd-limonene'],
    'Cucurbitacin':           ['cucurbitacin'],
    'Cuminaldehyde':          ['cuminaldehyde', '4-isopropylbenzaldehyde', 'p-isopropylbenzaldehyde'],
    'Heme Iron':              ['heme iron', 'hemoglobin'],
    'Vitamin K':              ['vitamin k', 'phylloquinone', 'menaquinone'],
    'Tyramine':               ['tyramine'],
    'Solanine':               ['solanine', 'alpha-solanine'],
    'CO2':                    ['carbon dioxide'],
    'Sodium Bicarbonate':     ['sodium bicarbonate'],
    'Resveratrol':            ['resveratrol', 'trans-resveratrol'],
    'Honey':                  ['honey'],
    'Olive Oil':              ['olive oil'],
    'Calcium':                ['calcium'],
    'Potassium':              ['potassium'],
    'Large Neutral Amino Acids': ['leucine', 'phenylalanine', 'valine', 'isoleucine'],
    'AGEs':                   ['advanced glycation end-product', 'methylglyoxal'],
    'Saturated Fats':         ['palmitic acid', 'stearic acid', 'saturated fat'],
}

# Collect all unique compounds
all_compounds = set()
for cpds in dishes.values():
    all_compounds.update(cpds)

found = []
not_found = []
skipped = []

for cpd in sorted(all_compounds):
    if cpd in NOT_CHEMICALS or any(x in cpd for x in ['Matrix', 'Emulsion',
            'Strands', 'Sponge', 'Coated', 'Dense', 'Hydration', 'Fermentation',
            'Flour', 'LateAdd', 'Lipids\n']):
        skipped.append(cpd)
        continue

    direct = cpd.lower()

    # 1. Exact match
    if direct in cpd_names:
        found.append((cpd, cpd))
        continue

    # 2. Alias match
    hit = None
    for alias in ALIASES.get(cpd, []):
        al = alias.lower()
        if al in cpd_names:
            hit = alias
            break
        for name in cpd_names:
            if name.startswith(al):
                hit = name
                break
        if hit:
            break

    # 3. Prefix match
    if not hit:
        for name in cpd_names:
            if name == direct or name.startswith(direct + ' ') or name.startswith(direct + ','):
                hit = name
                break

    if hit:
        found.append((cpd, hit))
    else:
        not_found.append(cpd)

# --- Print results ---
print(f'\n{"="*60}')
print(f'  IN KGE entity2id — {len(found)} compounds')
print(f'{"="*60}')
for cpd, match in found:
    note = '' if cpd.lower() == match.lower() else f'  → CPD:{match}'
    print(f'  ✓  {cpd}{note}')

print(f'\n{"="*60}')
print(f'  NOT in KGE entity2id — {len(not_found)} compounds')
print(f'{"="*60}')
for cpd in not_found:
    print(f'  ✗  {cpd}')

print(f'\n{"="*60}')
print(f'  Non-chemical labels skipped — {len(skipped)}')
print(f'{"="*60}')
for cpd in sorted(skipped):
    print(f'  –  {cpd}')

# --- Per-dish breakdown ---
print(f'\n{"="*60}')
print(f'  Per-dish compound coverage')
print(f'{"="*60}')
found_set = {cpd.lower() for cpd, _ in found}

for dish, cpds in sorted(dishes.items()):
    real = [c for c in sorted(cpds) if c not in NOT_CHEMICALS and
            not any(x in c for x in ['Matrix','Emulsion','Strands','Sponge',
                                      'Coated','Dense','Hydration','Fermentation',
                                      'Flour','LateAdd'])]
    in_kge  = [c for c in real if c.lower() in found_set]
    missing = [c for c in real if c.lower() not in found_set]
    print(f'\n  {dish}')
    for c in in_kge:
        print(f'    ✓ {c}')
    for c in missing:
        print(f'    ✗ {c}  [NEW]')
