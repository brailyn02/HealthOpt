"""
merge_prep_foods.py
--------------------
Merges Food_Source preparation entries (Juice, Sauce, etc.) into their
parent whole-food entry when the parent already exists.

Changes:
  - Interactions  : child food ID redirected to parent food ID
  - Master        : child entry removed; parent entry kept unchanged
  - IDs stay as-is (gaps are acceptable; full renumber happens at freeze time)

Writes:
  generated/unified_food_master_typed.txt   (updated in-place)
  generated/unified_train_interactions_clean.txt  (updated in-place)
  generated/prep_merge_report.txt
"""

import re
from collections import defaultdict

GENERATED = r"d:\23AIBox-DFinder\generated"
MASTER    = f"{GENERATED}/unified_food_master_typed.txt"
INTER     = f"{GENERATED}/unified_train_interactions_clean.txt"
REPORT    = f"{GENERATED}/prep_merge_report.txt"

# ── load master ───────────────────────────────────────────────────────────────
with open(MASTER, encoding="utf-8") as fh:
    master = {int(l.split("\t")[0]): l.rstrip().split("\t") for l in fh if l.strip()}

food_sources = {e[1].strip().lower(): fid for fid, e in master.items()
                if e[2] == "Food_Source"}

PREP_SUFFIXES = re.compile(
    r"\s+(juice(?:s)?|sauce|broth|stock|peel|rind|pulp|flesh|dried|powder|vinegar|fermented)\s*$",
    re.IGNORECASE,
)

# ── detect merges ─────────────────────────────────────────────────────────────
merges: dict[int, int] = {}   # child_id → parent_id
for fid, e in sorted(master.items()):
    name, typ = e[1], e[2]
    if typ != "Food_Source":
        continue
    stripped = PREP_SUFFIXES.sub("", name.strip().lower())
    if stripped == name.strip().lower():
        continue
    if stripped in food_sources and food_sources[stripped] != fid:
        merges[fid] = food_sources[stripped]

print(f"Merges to apply: {len(merges)}")
for child_id, parent_id in sorted(merges.items()):
    print(f"  [{child_id}] {master[child_id][1]}  →  [{parent_id}] {master[parent_id][1]}")

# ── rewrite interactions ──────────────────────────────────────────────────────
total_before = total_after = redirected = 0
drug_to_foods: dict[int, set] = {}

with open(INTER, encoding="utf-8") as fh:
    for line in fh:
        tokens = line.strip().split()
        if not tokens:
            continue
        did = int(tokens[0])
        food_ids = list(map(int, tokens[1:]))
        total_before += len(food_ids)
        new_set = set()
        for fid in food_ids:
            new_fid = merges.get(fid, fid)   # redirect or keep
            if new_fid != fid:
                redirected += 1
            new_set.add(new_fid)
        drug_to_foods[did] = new_set
        total_after += len(new_set)

with open(INTER, "w", encoding="utf-8") as fh:
    for did in sorted(drug_to_foods):
        fh.write(f"{did} " + " ".join(str(f) for f in sorted(drug_to_foods[did])) + "\n")

print(f"\nInteractions: {total_before} → {total_after} pairs "
      f"({redirected} redirected, {total_before - total_after} collapsed duplicates)")

# ── remove child entries from master ─────────────────────────────────────────
removed_ids = set(merges.keys())
kept = {fid: e for fid, e in master.items() if fid not in removed_ids}

with open(MASTER, "w", encoding="utf-8") as fh:
    for fid in sorted(kept):
        e = kept[fid]
        fh.write(f"{e[0]}\t{e[1]}\t{e[2]}\n")

print(f"Master: {len(master)} → {len(kept)} entries ({len(removed_ids)} removed)")

# ── report ────────────────────────────────────────────────────────────────────
lines = ["=== Preparation Food Merge Report ===\n\n"]
for child_id, parent_id in sorted(merges.items()):
    inter_count = sum(1 for foods in drug_to_foods.values() if parent_id in foods)
    lines.append(f"  [{child_id}] {master[child_id][1]:<40s}  merged into  "
                 f"[{parent_id}] {master[parent_id][1]}  "
                 f"(parent now in {inter_count} drug interactions)\n")
lines.append(f"\nInteractions: {total_before} → {total_after}\n")
lines.append(f"Master entries: {len(master)} → {len(kept)}\n")

with open(REPORT, "w", encoding="utf-8") as fh:
    fh.writelines(lines)

print(f"Report: {REPORT}")
