"""
Find likely duplicate drug/food entries in the unified masters:
 - Known abbreviation→full mappings
 - Entries that share the same interactions (same food set = likely same drug)
"""
from pathlib import Path
from collections import defaultdict

root = Path(r'd:/23AIBox-DFinder/generated')

drugs = {}
with (root/'unified_drug_master.txt').open(encoding='utf-8') as f:
    for line in f:
        p = line.strip().split('\t', 1)
        if len(p) == 2:
            drugs[int(p[0])] = p[1]

foods = {}
with (root/'unified_food_master.txt').open(encoding='utf-8') as f:
    for line in f:
        p = line.strip().split('\t', 1)
        if len(p) == 2:
            foods[int(p[0])] = p[1]

# Load interactions
drug_to_foods = {}
with (root/'unified_train_interactions.txt').open(encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split()
        if parts:
            drug_to_foods[int(parts[0])] = frozenset(int(x) for x in parts[1:])

# ── 1. Known abbreviations / synonyms to flag ──────────────────────────────
known_aliases = [
    ("mms",                         "methyl methanesulfonate"),
    ("azt",                         "3'-deoxy-3'-azidothymidine"),
    ("5-fu",                         "5-fluorouracil"),
    ("5-flu",                        "5-fluorouracil"),
    ("asa",                          "aspirin"),
    ("apap",                         "acetaminophen"),
    ("acm",                          "acetaminophen"),
    ("ach",                          "acetylcholine"),
    ("ache",                         "acetylcholinesterase"),
    ("bche",                         "butyrylcholinesterase"),
    ("ang ii",                       "angiotensin ii"),
    ("agii",                         "angiotensin ii"),
    ("angiotensin i",                 "angiotensin ii"),   # different but worth checking
    ("alt",                          "alanine aminotransferase"),
    ("ast",                          "aspartate aminotransferase"),
    ("alp",                          "alkaline phosphatase"),
    ("adriamycin",                   "doxorubicin"),
    ("amb",                          "amphotericin b"),
    ("amp b",                        "amphotericin b"),
    ("blm",                          "bleomycin"),
    ("cis-diamminedichloroplatinum",  "cisplatin"),
    ("abts",                         "2'-azinobis-3-ethylbenzothiazoline-6-sulfonic acid"),
    ("5-hiaa",                       "5-hydroxyindole acetic acid"),
    ("6beta-hydroxycortisol",        "6ß-hydroxycortisol"),
    ("dmba",                         "7,12-dimethylbenz[α]anthracene"),
]

name2id = {name.lower(): i for i, name in drugs.items()}

print("=" * 60)
print("KNOWN ALIAS PAIRS FOUND IN DRUG MASTER")
print("=" * 60)
found_pairs = []
for abbr, full in known_aliases:
    aid = name2id.get(abbr.lower())
    fid = name2id.get(full.lower())
    if aid is not None and fid is not None:
        a_foods = drug_to_foods.get(aid, frozenset())
        f_foods = drug_to_foods.get(fid, frozenset())
        shared = a_foods & f_foods
        print(f"\n  '{drugs[aid]}' (id={aid}, {len(a_foods)} interactions)")
        print(f"  '{drugs[fid]}' (id={fid}, {len(f_foods)} interactions)")
        print(f"  Shared food interactions: {len(shared)}")
        found_pairs.append((aid, fid, drugs[aid], drugs[fid]))
    elif aid is not None:
        print(f"\n  '{abbr}' found as id={aid}, but '{full}' NOT in master")
    elif fid is not None:
        print(f"\n  '{full}' found as id={fid}, but '{abbr}' NOT in master")

# ── 2. Drugs with identical interaction sets (strong dedup candidates) ─────
print("\n\n" + "=" * 60)
print("DRUGS WITH IDENTICAL FOOD INTERACTION SETS")
print("=" * 60)
sets_seen = defaultdict(list)
for did, fset in drug_to_foods.items():
    if len(fset) >= 2:  # skip trivial single interactions
        sets_seen[fset].append(did)
for fset, dids in sets_seen.items():
    if len(dids) > 1:
        names = [drugs[d] for d in dids]
        print(f"\n  Shared foods: {sorted(foods[f] for f in fset)}")
        for d, n in zip(dids, names):
            print(f"    id={d}: {n}")
