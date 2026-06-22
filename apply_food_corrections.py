"""
apply_food_corrections.py
Applies all scientific corrections from the audit to confirmed_pairs_exploded.csv
→ outputs confirmed_pairs_final.csv with correct food_id and canonical food_name
"""

import csv, sys
from pathlib import Path

BASE   = Path(r"d:\23AIBox-DFinder")
IN_CSV = BASE / "confirmed_pairs_exploded.csv"
OUT    = BASE / "confirmed_pairs_final.csv"

# ─────────────────────────────────────────────────────────────────────────────
# FINAL REMAP TABLE  food_name_lower → (canonical_name, food_id)
# Sources: DFinder food_id_map.csv + scientific audit decisions
# ─────────────────────────────────────────────────────────────────────────────
REMAP = {
    # ── Qualifier strips (keep same node, clean name) ─────────────────────
    "acetic acid (vinegar)":                ("Acetic Acid",             33),
    "carvone (caraway/karouiya)":           ("Carvone",                 32),
    "potassium (date paste — high load)":   ("Potassium",               22),
    "phytic acid (reduced — fermented)":    ("Phytic Acid",             762),
    "soluble fiber (pectin)":               ("Soluble Fiber",           10),
    "glucose/fructose (honey / sugar syrup)":("Glucose",               509),
    "triglycerides (dietary fat)":          ("Fat",                     9),
    "double-fried lecithin (almond paste)": ("Soy Lecithin",            189),
    "butter emulsion":                      ("Fat",                     9),
    "high-fat meal — saturated fats":       ("Fat",                     9),

    # ── Merge duplicates ──────────────────────────────────────────────────
    "larginine":          ("Arginine",           512),
    "l-arginine":         ("Arginine",           512),
    "omega3":             ("Alpha-Linolenic Acid",1049),
    "omega-3":            ("Alpha-Linolenic Acid",1049),
    "walnutala":          ("Alpha-Linolenic Acid",1049),  # WalnutALA proxy
    "solfiber":           ("Soluble Fiber",       10),
    "beta-glucan":        ("Soluble Fiber",       10),
    "soluble fiber":      ("Soluble Fiber",       10),
    "insoluble fiber":    ("Fiber",               10),
    "sat.fats":           ("Fat",                 9),
    "saturated fats":     ("Fat",                 9),
    "saturated lipids":   ("Fat",                 9),
    "lipid":              ("Fat",                 9),
    "lipsponge":          ("Fat",                 9),
    "lipidsponge":        ("Fat",                 9),
    "nonhemeiron":        ("Iron",               18),
    "non-heme iron":      ("Iron",               18),
    "heme iron":          ("Iron",               18),
    "mg2":                ("Magnesium",           20),
    "na":                 ("Na+",                 795),  # merge Sodium→Na+ ionic node
    "na+":                ("Na+",                 795),  # sodium ion — use exact Na+ food node
    "sodium":             ("Na+",                 795),  # merge Sodium→Na+ ionic node
    "fructoseglucose":    ("Glucose",             509),
    "sucrose / glucose":  ("Sucrose",             340),
    "sucrose / icing sugar": ("Sucrose",          340),
    "icing sugar":        ("Sucrose",             340),
    "amylose/amylopectin":("Starch",              831),

    # ── Internal keys → merge to parent node ─────────────────────────────
    "allicin-lateadd":              ("Allicin",      1011),
    "lipidcoatedstarch":            ("Starch",       831),
    "lipidsponge":                  ("Fat",          9),
    "w: amylopectin":               ("Amylopectin",  1801),
    "honey synergy":                ("Honey",        177),
    "grain starch":                 ("Starch",       831),
    "gelatinised starch":           ("Starch",       831),
    "pyrodextrins+insolfiber":      ("Fiber",        10),

    # ── Scientific proxy assignments ──────────────────────────────────────
    "albumin":            ("Protein",             23),    # Reject Arbutin fuzzy
    "amylose":            ("Starch",              831),   # Reject Maltose fuzzy
    "tyramine":           ("Tyramine-Containing Foods", 496),  # Reject Thymine
    "tannins":            ("Gallic Acid",         160),   # Reject Betanin
    "maillard":           ("Acrylamide",          None),  # proxy via name (no exact ID)
    "large neutral amino acids": ("L-Leucine",    511),   # BBB LAT1 proxy
    "plant protein":      ("Protein",             23),
    "scfas":              ("Butyric Acid",         679),  # most representative SCFA

    # ── Canonical / DFinder name fixes ───────────────────────────────────
    "folate":             ("Folic Acid",           11),
    "ascorbic acid":      ("Vitamin C",            27),
    "butter":             ("Fat",                  9),    # Reject Sheabutter
    "lecithin":           ("Soy Lecithin",         189),
    "beta-carotene":      ("Carotene",             718),
    "fructose":           ("D-Fructose",           514),
    "glucobrassicin":     ("Glucobrassicin",       644),  # accept 4-Methoxy close enough
    "gingerol":           ("Ginger",               13),   # closest food source node
    "leucine":            ("L-Leucine",            511),
    "resveratrol":        ("Trans-Resveratrol",    872),
    "inositol":           ("Myo-Inositol",         219),
    "purines":            ("Purine",               799),
    "sodium bicarbonate": ("Sodium Bicarbonate",   1663), # keep (Sodium Carbonate close enough for sodium load)
    "sesamin":            ("Sesame",               322),  # Sesamin not in DB, use food source
    "sesamolin":          ("Sesame",               322),  # same
    "nasunin":            ("Anthocyanins",         47),   # Anthocyanin class node, reject Casuarinin
    "cumin aldehyde":     ("Cuminaldehyde",        1503),
    "cuminaldeyhde":      ("Cuminaldehyde",        1503),
    "cuminaldehyde":      ("Cuminaldehyde",        1503),  # normalise CuminAldehyde variant
}

# DROP these entirely — no pharmacological relevance
DROP = {
    "braidedlattice+3mm",
    "hydrationmatrix",
    "shortcrust-friablematrix",
    "densematrix",
    "co₂",
    "co2",
    "minerals",           # too vague — no single node
    "phthalides",         # not in DB and no clean proxy
    "walnутаlа",          # already handled as walnutala above
}

# ─────────────────────────────────────────────────────────────────────────────
# Apply corrections
# ─────────────────────────────────────────────────────────────────────────────
rows_in = []
with open(IN_CSV, encoding="utf-8") as f:
    rows_in = list(csv.DictReader(f))

print(f"Input rows: {len(rows_in)}")

rows_out = []
dropped = 0
remapped = 0
ok = 0
seen = set()

for row in rows_in:
    food_name = row["food_name"].strip()
    lower = food_name.lower()

    # Check DROP
    if lower in DROP:
        dropped += 1
        continue

    # Check REMAP
    if lower in REMAP:
        canonical, fid = REMAP[lower]
        if fid is None:
            # Acrylamide etc — look up dynamically
            # For Maillard/Acrylamide, just drop since not in DB
            dropped += 1
            continue
        row["food_name"] = canonical
        row["food_id"]   = fid
        remapped += 1
    else:
        ok += 1

    # Deduplicate on (food_id, drug_id)
    key = (str(row["food_id"]), str(row["drug_id"]))
    if key in seen:
        continue
    seen.add(key)

    rows_out.append(row)

with open(OUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["food_name","food_id","drug_name","drug_id","verdict"])
    writer.writeheader()
    writer.writerows(rows_out)

print(f"  Remapped        : {remapped}")
print(f"  OK (unchanged)  : {ok}")
print(f"  Dropped         : {dropped}")
print(f"  Output rows     : {len(rows_out)}")
print(f"  Unique food IDs : {len(set(r['food_id'] for r in rows_out))}")
print(f"  Unique drug IDs : {len(set(r['drug_id'] for r in rows_out))}")
print(f"\nOutput → {OUT}")

# Verify no bad fuzzy matches remain
bad = [r for r in rows_out if r["food_name"] in
       {"Arbutin","Maltose","Thymine","Betanin","Sheabutter","Casuarinin","An Inositol"}]
if bad:
    print(f"\n⚠ {len(bad)} bad fuzzy matches still present!")
else:
    print("\n✓ No bad fuzzy matches in output.")
