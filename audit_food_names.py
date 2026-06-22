"""
audit_food_names.py
For every unique food_name in confirmed_pairs_exploded.csv:
  1. Check if it has a direct match in DFinder food_id_map
  2. If not, find the closest match (fuzzy) in food_id_map
  3. Check Compound.csv (FooDB) for IUPAC/canonical name
  4. Flag: duplicates, internal-key leaks, non-canonical names
  5. Output audit_food_names.csv with recommended canonical name + action
"""

import csv, re, sys
from pathlib import Path
from difflib import get_close_matches

BASE    = Path(r"d:\23AIBox-DFinder")
ID_DIR  = BASE / "DFinder-main" / "data" / "unified-DFI" / "id_maps"

# ── Load DFinder food_id_map ──────────────────────────────────────────────────
dfinder_foods = {}   # lower_name → (id, canonical_name)
with open(ID_DIR / "food_id_map.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        dfinder_foods[row["name"].strip().lower()] = (int(row["new_id"]), row["name"].strip())

# ── Load FooDB Compound names ─────────────────────────────────────────────────
foodb_compounds = set()
with open(BASE / "Compound.csv", encoding="utf-8", errors="ignore") as f:
    for row in csv.DictReader(f):
        n = row.get("name", "").strip()
        if n:
            foodb_compounds.add(n.lower())

# ── Load foodrugs food names ──────────────────────────────────────────────────
foodrugs_foods = set()
try:
    with open(BASE / "foodrugs_interactions.csv", encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            for col in ("food", "food_name", "Food", "Food_Name", "bioactive", "Bioactive"):
                v = row.get(col, "").strip()
                if v:
                    foodrugs_foods.add(v.lower())
except:
    pass

# ── Internal-key patterns (should not appear as display names) ────────────────
INTERNAL_PATTERNS = [
    r'^[A-Z][a-z]?:',          # prefix like "W: Amylopectin"
    r'Matrix$',                 # DenseMatrix, HydrationMatrix, LipidSponge
    r'Sponge$',
    r'LipidCoated',
    r'Shortcrust',
    r'BraidedLattice',
    r'FractoseGlucose',
    r'LateAdd',
    r'InsolFiber$',
    r'Pyrodextrin',
]

# ── Known renames/merges ──────────────────────────────────────────────────────
KNOWN_REMAP = {
    "larginine":            ("L-Arginine",          "merge duplicate"),
    "larg":                 ("L-Arginine",          "merge duplicate"),
    "l-arginine":           ("L-Arginine",          "canonical"),
    "omega3":               ("Omega-3 Fatty Acids", "merge duplicate"),
    "omega-3":              ("Omega-3 Fatty Acids", "merge duplicate"),
    "cuminaldehyde":        ("Cuminaldehyde",       "canonical"),
    "cuminaldeyhde":        ("Cuminaldehyde",       "typo fix"),
    "nonhemeiron":          ("Non-Heme Iron",       "merge duplicate"),
    "non-heme iron":        ("Non-Heme Iron",       "canonical"),
    "non-heme fe":          ("Non-Heme Iron",       "merge duplicate"),
    "solfiber":             ("Soluble Fiber",       "merge duplicate"),
    "beta-glucan":          ("Soluble Fiber",       "merge — beta-glucan is soluble fiber"),
    "mg2":                  ("Magnesium",           "merge duplicate"),
    "mg2+":                 ("Magnesium",           "merge duplicate"),
    "na":                   ("Sodium",              "merge — Na = sodium"),
    "sat.fats":             ("Saturated Fats",      "merge duplicate"),
    "saturated lipids":     ("Saturated Fats",      "merge duplicate"),
    "lipid":                ("Fat",                 "use DFinder canonical node"),
    "lipsponge":            ("Fat",                 "internal key — use Fat"),
    "high-fat meal — saturated fats": ("Saturated Fats", "simplify"),
    "fructoseglucose":      ("Fructose",            "split — already expanded"),
    "honey synergy":        ("Honey",               "internal key — use Honey"),
    "denseMatrix":          (None,                  "internal structural key — drop"),
    "hydrationmatrix":      (None,                  "internal structural key — drop"),
    "lipidcoatedstarch":    ("Starch",              "internal key — use Starch"),
    "shortcrust-friablematrix": (None,              "internal structural key — drop"),
    "w: amylopectin":       ("Amylopectin",         "internal prefix — strip W:"),
    "grain starch":         ("Starch",              "use canonical Starch node"),
    "gelatinised starch":   ("Starch",              "gelatinised starch → Starch node"),
    "lipidsponge":          ("Fat",                 "internal key"),
    "ascorbic acid":        ("Vitamin C",           "Vitamin C = Ascorbic Acid (DrugBank name)"),
    "folate":               ("Folic Acid",          "DFinder uses Folic Acid"),
    "fructoseglucose":      ("Glucose",             "use Glucose node"),
    "niacin":               ("Niacin",              "canonical — check DFinder"),
    "allicin-lateadd":      ("Allicin",             "cooking-stage tag — merge to Allicin"),
    "braidedlattice+3mm":   (None,                  "structural descriptor — drop"),
    "double-fried lecithin (almond paste)": ("Lecithin", "use Lecithin node"),
    "butter emulsion":      ("Butter",              "use Butter node"),
    "acetic acid (vinegar)": ("Acetic Acid",        "strip qualifier — use Acetic Acid node"),
    "carvone (caraway/karouiya)": ("Carvone",       "strip qualifier — use Carvone node"),
    "potassium (date paste — high load)": ("Potassium", "strip qualifier — use Potassium node"),
    "soluble fiber (pectin)": ("Soluble Fiber",     "use Soluble Fiber node"),
    "phytic acid (reduced — fermented)": ("Phytic Acid", "use Phytic Acid node"),
    "glucose/fructose (honey / sugar syrup)": ("Glucose", "use Glucose node (honey = glucose+fructose)"),
    "triglycerides (dietary fat)": ("Fat",          "use Fat node"),
    "insoluble fiber":      ("Fiber",               "DFinder uses Fiber node"),
    "fatty acids":          ("Fat",                 "use Fat node"),
}

# ── Get all unique food names ─────────────────────────────────────────────────
food_names = set()
with open(BASE / "confirmed_pairs_exploded.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        food_names.add(row["food_name"].strip())

dfinder_name_list = list(dfinder_foods.keys())

rows_out = []

for name in sorted(food_names):
    lower = name.lower().strip()
    issues = []
    action = ""
    canonical = name
    dfinder_id = ""
    dfinder_name = ""

    # Check internal key patterns
    for pat in INTERNAL_PATTERNS:
        if re.search(pat, name, re.IGNORECASE):
            issues.append("INTERNAL-KEY")
            break

    # Check known remap table
    remap = KNOWN_REMAP.get(lower)
    if remap:
        canonical, action = remap
        if canonical is None:
            canonical = ""
            issues.append("DROP")

    # Check exact match in DFinder
    if lower in dfinder_foods:
        did, dname = dfinder_foods[lower]
        dfinder_id = did
        dfinder_name = dname
        if not action:
            action = "OK — exact match in DFinder"
    else:
        # Try canonical
        if canonical and canonical.lower() in dfinder_foods:
            did, dname = dfinder_foods[canonical.lower()]
            dfinder_id = did
            dfinder_name = dname
            if not action:
                action = f"REMAP → {dname}"
        else:
            # Fuzzy match
            matches = get_close_matches(lower, dfinder_name_list, n=1, cutoff=0.7)
            if matches:
                did, dname = dfinder_foods[matches[0]]
                if not action:
                    action = f"FUZZY → {dname}"
                dfinder_id = did
                dfinder_name = dname
                issues.append("FUZZY-MATCH")
            else:
                if not action:
                    action = "NOT IN DFINDER — review needed"
                issues.append("MISSING")

    # Check FooDB
    in_foodb = "YES" if lower in foodb_compounds else ""

    rows_out.append({
        "food_name":     name,
        "canonical":     canonical,
        "dfinder_id":    dfinder_id,
        "dfinder_name":  dfinder_name,
        "in_foodb":      in_foodb,
        "issues":        "|".join(issues) if issues else "OK",
        "action":        action,
    })

OUT = BASE / "audit_food_names.csv"
with open(OUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "food_name", "canonical", "dfinder_id", "dfinder_name", "in_foodb", "issues", "action"
    ])
    writer.writeheader()
    writer.writerows(rows_out)

print(f"Audited {len(rows_out)} unique food names → {OUT}")

# Summary
ok      = sum(1 for r in rows_out if r["issues"] == "OK")
drops   = sum(1 for r in rows_out if "DROP" in r["issues"])
missing = sum(1 for r in rows_out if "MISSING" in r["issues"])
fuzzy   = sum(1 for r in rows_out if "FUZZY" in r["issues"])
internal= sum(1 for r in rows_out if "INTERNAL" in r["issues"])

print(f"  OK (exact DFinder match) : {ok}")
print(f"  REMAP (known better name): {len(rows_out) - ok - drops - missing - fuzzy}")
print(f"  FUZZY match              : {fuzzy}")
print(f"  INTERNAL KEY (drop/fix)  : {internal}")
print(f"  DROP                     : {drops}")
print(f"  MISSING from all DBs     : {missing}")
