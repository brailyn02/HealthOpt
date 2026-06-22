import csv
from collections import defaultdict

with open(r'D:\23AIBox-DFinder\audit_food_names.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

groups = defaultdict(list)
for r in rows:
    groups[r['issues']].append(r)

for issue, rlist in sorted(groups.items()):
    print(f'\n=== {issue} ({len(rlist)}) ===')
    for r in rlist:
        print(f"  {r['food_name']:<40} id={r['dfinder_id']:<6} action={r['action']}")
