"""
explode_compound_foods.py
Reads confirmed_pairs_clean.csv and splits compound food names (containing " + ")
into individual component rows, re-resolving food_id for each component.
Outputs confirmed_pairs_exploded.csv
"""

import csv, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(r"d:\23AIBox-DFinder")))
from extract_confirmed_pairs import load_id_map, resolve_food

BASE      = Path(r"d:\23AIBox-DFinder")
IN_CSV    = BASE / "confirmed_pairs_clean.csv"
OUT_CSV   = BASE / "confirmed_pairs_exploded.csv"
ID_DIR    = BASE / "DFinder-main" / "data" / "unified-DFI" / "id_maps"

food_id_map = load_id_map(ID_DIR / "food_id_map.csv")

# Chemical names that contain + but should NOT be split
# Chemical ions / single tokens that must NOT be split
NO_SPLIT = {
    "Na+", "K+", "Ca2+", "Mg2+", "Fe2+", "Fe3+", "H+", "OH-",
    "Glucose/Fructose (Honey / Sugar Syrup)",  # single honey concept
    "Carvone (Caraway/Karouiya)",              # / is food-source qualifier
    "BraidedLattice+3mm",                      # structural descriptor
    "Pyrodextrins+InsolFiber",                 # single resistant-starch concept
}

def split_compound(food_name):
    """
    Split compound food names on + or / that are NOT inside parentheses.
    Strips parenthetical qualifiers from each component.
    Returns list of clean component strings.
    """
    if food_name in NO_SPLIT:
        return [food_name]

    # Tokenise: split on + or / outside parentheses
    parts = []
    current = ""
    depth = 0
    i = 0
    while i < len(food_name):
        c = food_name[i]
        if c == '(':
            depth += 1
            current += c
        elif c == ')':
            depth -= 1
            current += c
        elif c in ('+', '/') and depth == 0:
            # absorb optional surrounding spaces
            token = current.strip()
            if token:
                parts.append(token)
            current = ""
            # skip surrounding spaces
            i += 1
            while i < len(food_name) and food_name[i] == ' ':
                i += 1
            continue
        else:
            current += c
        i += 1
    if current.strip():
        parts.append(current.strip())

    # If only one part, return as-is
    if len(parts) <= 1:
        return [food_name]

    cleaned = []
    for p in parts:
        # Remove parenthetical suffixes
        p = re.sub(r'\s*\(.*?\)', '', p).strip()
        p = re.sub(r'^[-_\s]+|[-_\s]+$', '', p).strip()
        # Skip noise tokens
        if p and len(p) > 1:
            cleaned.append(p)
    return cleaned if cleaned else [food_name]


rows_in  = []
with open(IN_CSV, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows_in.append(row)

print(f"Input rows: {len(rows_in)}")

rows_out = []
unmatched = set()
seen = set()

for row in rows_in:
    food_name = row["food_name"]
    components = split_compound(food_name)

    for comp in components:
        # Resolve ID for this component
        food_id, food_matched = resolve_food(comp)
        if food_id is None:
            # Try the original row's food_id if only one component
            if len(components) == 1:
                food_id = row["food_id"]
                food_matched = row["food_name"]
            else:
                unmatched.add(comp)

        key = (str(food_id), str(row["drug_id"]))
        if key in seen:
            continue
        seen.add(key)

        rows_out.append({
            "food_name": comp,
            "food_id":   food_id if food_id is not None else "—",
            "drug_name": row["drug_name"],
            "drug_id":   row["drug_id"],
            "verdict":   row["verdict"],
        })

# Write output
with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["food_name", "food_id", "drug_name", "drug_id", "verdict"])
    writer.writeheader()
    writer.writerows(rows_out)

matched_rows = [r for r in rows_out if r["food_id"] != "—"]
print(f"Output rows (exploded + deduped): {len(rows_out)}")
print(f"  With valid food_id            : {len(matched_rows)}")
print(f"Output → {OUT_CSV}")

if unmatched:
    print(f"\n⚠ Components with no id_map match ({len(unmatched)}):")
    for x in sorted(unmatched):
        print(f"    {x}")
