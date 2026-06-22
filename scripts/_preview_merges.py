import re

with open(r'd:\23AIBox-DFinder\generated\unified_food_master_typed.txt', encoding='utf-8') as f:
    master = {int(l.split('\t')[0]): l.rstrip().split('\t') for l in f if l.strip()}

food_sources = {e[1].strip().lower(): fid for fid, e in master.items() if e[2] == 'Food_Source'}

PREP_SUFFIXES = re.compile(
    r'\s+(juice(?:s)?|sauce|broth|stock|peel|rind|pulp|flesh|dried|powder|vinegar|fermented)\s*$',
    re.IGNORECASE
)

candidates = []
for fid, e in sorted(master.items()):
    name, typ = e[1], e[2]
    if typ != 'Food_Source':
        continue
    stripped = PREP_SUFFIXES.sub('', name.strip().lower())
    if stripped == name.strip().lower():
        continue
    if stripped in food_sources and food_sources[stripped] != fid:
        parent_id = food_sources[stripped]
        parent_name = master[parent_id][1]
        candidates.append((fid, name, parent_id, parent_name))
        print(f'  ID {fid:<5} "{name}"  ->  ID {parent_id:<5} "{parent_name}"')

print(f'\nTotal candidates: {len(candidates)}')
