"""
Deduplicate unified drug master:
  - Cluster drugs with identical interaction sets → keep longest descriptive name
  - Apply manual alias map (abbreviation → canonical)
  - Auto-detect abbreviations: all-caps ≤6 chars, or single/two-letter codes
  - Rebuild unified_drug_master.txt, unified_train_interactions.txt with new contiguous IDs
"""
from pathlib import Path
from collections import defaultdict
import re

root = Path(r'd:/23AIBox-DFinder/generated')

# ── Load masters ────────────────────────────────────────────────────────────
drugs = {}   # id → name
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

# ── Load interactions ────────────────────────────────────────────────────────
drug_to_foods = {}
with (root/'unified_train_interactions.txt').open(encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split()
        if parts:
            drug_to_foods[int(parts[0])] = set(int(x) for x in parts[1:])

# ── Manual alias map: abbreviation/variant (lowercase) → canonical (lowercase) ─
# Maps the LESS preferred form → MORE preferred form
manual_aliases = {
    # Abbreviation → full name
    "mms":                                      "methyl methanesulfonate",
    "azt":                                      "3'-deoxy-3'-azidothymidine",
    "5-fu":                                     "5-fluorouracil",
    "5-flu":                                    "5-fluorouracil",
    "asa":                                      "aspirin",
    "apap":                                     "acetaminophen",
    "ach":                                      "acetylcholine",
    "ache":                                     "acetylcholinesterase",
    "bche":                                     "butyrylcholinesterase",
    "ang ii":                                   "angiotensin ii",
    "agii":                                     "angiotensin ii",
    "alt":                                      "alanine aminotransferase",
    "ast":                                      "aspartate aminotransferase",
    "alp":                                      "alkaline phosphatase",
    "adriamycin":                               "doxorubicin",
    "amb":                                      "amphotericin b",
    "amp b":                                    "amphotericin b",
    "blm":                                      "bleomycin",
    "cis-diamminedichloroplatinum":             "cisplatin",
    "abts":                                     "2'-azinobis-3-ethylbenzothiazoline-6-sulfonic acid",
    "5-hiaa":                                   "5-hydroxyindole acetic acid",
    "dmba":                                     "7,12-dimethylbenz[α]anthracene",
    "7,12-dimethylbenzaanthracene":             "7,12-dimethylbenz[α]anthracene",
    "ds":                                       "diclofenac sodium",
    "ft":                                       "diclofenac sodium",
    "diclofinac":                               "diclofenac sodium",
    "va":                                       "vitamin a",
    "naloxone methiodide":                      "naloxone hydrochloride",
    "bche":                                     "butyrylcholinesterase",
    "tp":                                       "testosterone propionate",
    "dht":                                      "dihydrotestosterone",
    "pge(2)":                                   "prostaglandin e(2)",
    "cb":                                       "anandamide",
    "cannabinoid":                              "anandamide",
    "ccl4":                                     "carbon tetrachloride",
    "va":                                       "vitamin a",
    "pc":                                       "protein carbonyl",
    "na+":                                      "sodium",
    "k+":                                       "potassium",
    "ca(2+)":                                   "calcium",
    "ca++":                                     "calcium",
    "l-name":                                   "n(g)-nitro-l-arginine methyl ester",
    "n(g)-nitro-l-arginine methyl ester (l-name)": "n(g)-nitro-l-arginine methyl ester",
    "as(iii)":                                  "arsenic",
    "as3+":                                     "arsenic",
    "arsenite":                                 "arsenic",
    "arsenicated":                              "arsenic",
    "al":                                       "aluminum",
    "aluminium chloride":                       "aluminum chloride",
    "alcl3":                                    "aluminum chloride",
    "ampt":                                     "alpha-methyl-para-tyrosine",
    "dxr":                                      "doxorubicin",
    "inh":                                      "isoniazid",
    "pl":                                       "pyridoxal",
    "ag":                                       "silver",
    "ag-nanoparticles":                         "silver nanoparticles",
    "am":                                       "amphotericin b",
    "amx":                                      "amoxicillin",
    "ifa":                                      "soy isoflavone aglycone",
    "hcy":                                      "homocysteine",
    "npsh":                                     "non-protein thiol",
    "reduced level of non-protein thiol":       "non-protein thiol",
}

# ── Build normalised name → canonical name map ───────────────────────────────
# Start from manual aliases, then auto-cluster by identical interactions

# Resolve chains: if A→B and B→C, A→C
def resolve(alias_map, key):
    seen = set()
    while key in alias_map and key not in seen:
        seen.add(key)
        key = alias_map[key]
    return key

# Build name_lower → canonical_lower from manual map
alias_lower = {k.lower(): v.lower() for k, v in manual_aliases.items()}
# resolve chains
alias_lower = {k: resolve(alias_lower, alias_lower[k]) if alias_lower[k] in alias_lower else alias_lower[k]
               for k in alias_lower}

# ── Auto-detect abbreviations ────────────────────────────────────────────────
def is_abbreviation(name):
    n = name.strip()
    # Single or two letters (e.g. "DS", "FT", "K", "Hcy", "Am")
    if len(n) <= 2:
        return True
    # All-uppercase word of length ≤ 6, not a known real drug-like word
    if re.fullmatch(r'[A-Z]{2,6}', n):
        return True
    # Pattern like "CCl4", "Na+", "Ca++", "As3+"
    if re.fullmatch(r'[A-Z][a-z]?[0-9+]+', n):
        return True
    # Greek-letter prefix abbreviations like "α-toc", "β-..." already in manual
    return False

# ── Step 1: Map each drug id to its canonical name (lowercase) ────────────────
# priority: manual alias > auto-detect (mark as abbreviation, drop later)

name_lower2id = {}  # first-seen drug_id for each lowercased canonical name
for did, name in drugs.items():
    nl = name.lower()
    # Apply manual alias
    canonical_lower = alias_lower.get(nl, nl)
    if canonical_lower not in name_lower2id:
        name_lower2id[canonical_lower] = did

# ── Step 2: Build mapping old_drug_id → canonical_drug_id ─────────────────────
old2canonical_id = {}   # old drug id → the drug id whose name is the canonical
canonical_id2name = {}  # canonical drug id → display name (preserve original casing)

for did, name in drugs.items():
    nl = name.lower()
    canonical_lower = alias_lower.get(nl, nl)
    canon_id = name_lower2id.get(canonical_lower, did)
    old2canonical_id[did] = canon_id
    # Pick display name: prefer the longer / non-abbreviated form
    if canon_id not in canonical_id2name:
        canonical_id2name[canon_id] = drugs.get(canon_id, name)
    else:
        # Keep the longer name as display
        current = canonical_id2name[canon_id]
        candidate = drugs.get(did, name)
        if not is_abbreviation(candidate) and (is_abbreviation(current) or len(candidate) > len(current)):
            canonical_id2name[canon_id] = candidate

# ── Step 3: Cluster identical-interaction-set duplicates ─────────────────────
# After alias resolution, merge interaction sets per canonical id
merged_interactions = defaultdict(set)   # canonical_id → merged food set
for did, fset in drug_to_foods.items():
    canon_id = old2canonical_id.get(did, did)
    merged_interactions[canon_id].update(fset)

# ── Step 4: Auto-remove pure abbreviations that have NO alias mapping ─────────
# (i.e., they stand alone with no canonical partner — likely noise)
abbreviation_only_ids = set()
for did, name in drugs.items():
    nl = name.lower()
    canonical_lower = alias_lower.get(nl, nl)
    canon_id = name_lower2id.get(canonical_lower, did)
    if canon_id == did and is_abbreviation(name):
        abbreviation_only_ids.add(did)

# Remove these from merged_interactions (keep if they have a manual alias pointing elsewhere)
for did in abbreviation_only_ids:
    if did in merged_interactions and old2canonical_id.get(did) == did:
        del merged_interactions[did]

# ── Step 5: Assign new contiguous IDs ─────────────────────────────────────────
# Sort by current canonical_id for determinism
sorted_canonical_ids = sorted(merged_interactions.keys())
new_drug_id = {old: new for new, old in enumerate(sorted_canonical_ids)}

# ── Step 6: Write new unified_drug_master.txt ─────────────────────────────────
drug_master_out = root / 'unified_drug_master.txt'
with drug_master_out.open('w', encoding='utf-8') as f:
    for new_id, old_canon_id in enumerate(sorted_canonical_ids):
        name = canonical_id2name.get(old_canon_id, drugs.get(old_canon_id, f'drug_{old_canon_id}'))
        f.write(f"{new_id}\t{name}\n")

# ── Step 7: Write new unified_train_interactions.txt ──────────────────────────
inter_out = root / 'unified_train_interactions.txt'
with inter_out.open('w', encoding='utf-8') as f:
    for new_id, old_canon_id in enumerate(sorted_canonical_ids):
        fids = sorted(merged_interactions[old_canon_id])
        if fids:
            f.write(' '.join([str(new_id)] + [str(x) for x in fids]) + '\n')

# ── Summary ────────────────────────────────────────────────────────────────────
total_old = len(drugs)
total_new = len(sorted_canonical_ids)
total_pairs = sum(len(v) for v in merged_interactions.values())
removed_abbr = len(abbreviation_only_ids)
alias_merged = sum(1 for old, canon in old2canonical_id.items() if old != canon)

print(f"Original drug entries     : {total_old}")
print(f"Removed pure abbreviations: {removed_abbr}")
print(f"Alias-merged duplicates   : {alias_merged}")
print(f"Final unique drug entries : {total_new}")
print(f"Total positive pairs      : {total_pairs}")
print(f"Interaction lines         : {len([v for v in merged_interactions.values() if v])}")
print(f"\nWritten: {drug_master_out}")
print(f"Written: {inter_out}")

# Show sample of what was merged
print("\n--- Sample merges applied ---")
shown = 0
for old_id, canon_id in sorted(old2canonical_id.items()):
    if old_id != canon_id and shown < 20:
        print(f"  '{drugs[old_id]}' → '{canonical_id2name.get(canon_id, drugs.get(canon_id))}'")
        shown += 1

print("\n--- Pure abbreviations removed (first 30) ---")
for did in sorted(abbreviation_only_ids)[:30]:
    print(f"  id={did}: '{drugs[did]}'")
