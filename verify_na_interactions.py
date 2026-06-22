"""
verify_na_interactions.py
Cross-checks every (bioactive compound → drug) pair documented in
north_african_food_drug_interactions.txt against all interaction databases
in the workspace.

Sources used:
  A) generated/drugbank_drug_food_named.csv         (drug ↔ food name)
  B) Drug to Food interactions Dataset.json          (DrugBank text)
  C) dfi_interactions_from_keysentences.csv          (PubMed NLP pairs)
  D) DFinder-main/data/unified-DFI/id_maps/*         (canonical ID maps)
"""

import re, json, csv, pathlib

ROOT = pathlib.Path(r"d:\23AIBox-DFinder")
NA_FILE = ROOT / "north_african_food_drug_interactions.txt"
REPORT  = ROOT / "na_interaction_verification_report.txt"

# ─── 1. Bioactive → canonical food-source mapping ────────────────────────────
# Keys are lowercase bioactive names (substrings OK); values are food-level terms
# that appear in the interaction databases.
BIOACTIVE_TO_FOOD = {
    "allicin":           ["garlic"],
    "ajoene":            ["garlic"],
    "alliin":            ["garlic"],
    "quercetin":         ["quercetin", "onion", "garlic", "parsley", "apple"],
    "apigenin":          ["apigenin", "parsley", "chamomile", "celery"],
    "kaempferol":        ["kaempferol", "parsley", "onion"],
    "luteolin":          ["luteolin", "parsley", "celery"],
    "curcumin":          ["curcumin", "turmeric"],
    "piperine":          ["piperine", "black pepper", "pepper"],
    "6-gingerol":        ["ginger", "gingerol"],
    "gingerol":          ["ginger", "gingerol"],
    "shogaol":           ["ginger"],
    "capsaicin":         ["capsaicin", "chili", "pepper", "capsicum"],
    "cinnamaldehyde":    ["cinnamon", "cinnamaldehyde"],
    "coumarin":          ["cinnamon"],
    "eugenol":           ["eugenol", "clove", "cinnamon"],
    "linalool":          ["linalool", "lavender", "coriander"],
    "geraniol":          ["geraniol"],
    "limonene":          ["limonene", "lemon", "orange"],
    "carvone":           ["carvone", "caraway", "spearmint"],
    "cuminaldehyde":     ["cumin"],
    "safranal":          ["saffron"],
    "lycopene":          ["lycopene", "tomato"],
    "beta-carotene":     ["beta-carotene", "carrot", "tomato"],
    "phytic acid":       ["phytic acid", "phytate", "soy", "legume", "wheat", "bran"],
    "ip6":               ["phytic acid", "phytate"],
    "sesamin":           ["sesame", "sesamin"],
    "sesamolin":         ["sesame"],
    "resveratrol":       ["resveratrol", "grape", "wine", "peanut"],
    "uric acid":         ["purine", "meat", "organ meat", "red meat"],
    "purine":            ["purine", "meat"],
    "hypoxanthine":      ["purine", "meat"],
    "caffeine":          ["caffeine", "coffee", "tea"],
    "egcg":              ["green tea", "tea", "egcg", "epigallocatechin"],
    "tannin":            ["tea", "tannin", "wine"],
    "tyramine":          ["tyramine", "fermented", "aged cheese"],
    "folate":            ["folate", "folic acid", "lentil"],
    "folic acid":        ["folic acid", "folate", "lentil"],
    "magnesium":         ["magnesium", "nuts", "legume"],
    "potassium":         ["potassium", "banana", "legume"],
    "calcium":           ["calcium", "dairy", "milk"],
    "iron":              ["iron"],
    "oleic acid":        ["olive oil", "oleic acid"],
    "linoleic acid":     ["linoleic acid", "omega-6"],
    "ala":               ["alpha-linolenic", "ala", "flaxseed", "omega-3"],
    "alpha-linolenic":   ["alpha-linolenic", "ala", "flaxseed", "omega-3"],
    "epa":               ["epa", "fish oil", "omega-3"],
    "eicosapentaenoic":  ["epa", "fish oil", "omega-3"],
    "dha":               ["dha", "fish oil", "omega-3"],
    "butyric acid":      ["butyrate", "butter", "dairy"],
    "butyrate":          ["butyrate", "butter", "dairy"],
    "palmitic acid":     ["palm", "saturated fat"],
    "stearic acid":      ["saturated fat"],
    "vitamin k":         ["vitamin k", "parsley", "leafy green"],
    "vitamin c":         ["vitamin c", "ascorbic acid", "citrus"],
    "ascorbic acid":     ["ascorbic acid", "vitamin c", "citrus"],
    "citric acid":       ["citric acid", "lemon", "citrus"],
    "l-arginine":        ["arginine", "nut", "peanut", "walnut"],
    "arginine":          ["arginine", "nut"],
    "lecithin":          ["lecithin", "egg", "soy"],
    "choline":           ["choline", "egg"],
    "solanine":          ["solanine", "potato"],
    "amygdalin":         ["amygdalin", "almond", "apricot", "bitter almond"],
    "acrylamide":        ["acrylamide", "fried", "potato"],
    "benzo[a]pyrene":    ["benzo[a]pyrene", "smoked", "charred meat"],
    "4-hne":             ["4-hne", "oxidized fat", "fried"],
    "rosmarinic acid":   ["rosemary", "rosmarinic"],
    "cynarin":           ["artichoke", "cynarin"],
    "silymarin":         ["silymarin", "milk thistle"],
    "indole-3-carbinol": ["broccoli", "cauliflower", "crucifer"],
    "i3c":               ["broccoli", "cauliflower", "indole"],
    "sulforaphane":      ["broccoli", "sulforaphane", "cauliflower"],
    "nasunin":           ["eggplant", "aubergine"],
    "betaine":           ["beet", "betaine"],
    "sodium":            ["sodium", "salt"],
    "bicarbonate":       ["baking soda"],
    "sucrose":           ["sucrose", "sugar"],
    "fructose":          ["fructose", "sugar", "fruit"],
    "glucose":           ["glucose", "sugar", "carbohydrate"],
    "maltose":           ["maltose", "malt"],
    "saponin":           ["saponin", "legume", "chickpea"],
    "pectin":            ["pectin", "apple", "citrus"],
    "inositol":          ["inositol"],
    "tripalmitin":       ["palm oil", "saturated fat"],
    "piperidine":        ["pepper"],
    "benzaldehyde":      ["almond", "cherry"],
    "lemon":             ["lemon", "citrus"],
}

# ─── 2. Load all database interaction sources ─────────────────────────────────
print("Loading databases...")

# A) DrugBank named pairs
db_drugfood = []
with open(ROOT / "generated" / "drugbank_drug_food_named.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        db_drugfood.append((row["drug_name"].lower().strip(),
                            row["food_name"].lower().strip()))
print(f"  DrugBank named pairs: {len(db_drugfood)}")

# B) DrugBank JSON text
db_json_texts = []  # list of (drug_name_lower, interaction_text_lower)
with open(ROOT / "Drug to Food interactions Dataset.json", encoding="utf-8") as f:
    db_json = json.load(f)
for entry in db_json:
    drug = entry.get("name","").lower().strip()
    for fi in entry.get("food_interactions", []):
        db_json_texts.append((drug, str(fi).lower()))
print(f"  DrugBank JSON texts: {len(db_json_texts)}")

# C) PubMed NLP pairs
db_pubmed = []
with open(ROOT / "dfi_interactions_from_keysentences.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        d = row.get("drug","").lower().strip()
        fo = row.get("food","").lower().strip()
        if d and fo:
            db_pubmed.append((d, fo))
print(f"  PubMed NLP pairs: {len(db_pubmed)}")

# D) unified-DFI food_id_map
food_id_map = {}
with open(ROOT / "DFinder-main" / "data" / "unified-DFI" / "id_maps" / "food_id_map.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        food_id_map[row["name"].lower().strip()] = int(row["new_id"])
print(f"  Unified food entities: {len(food_id_map)}")
drug_id_map = {}
with open(ROOT / "DFinder-main" / "data" / "unified-DFI" / "id_maps" / "drug_id_map.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        drug_id_map[row["name"].lower().strip()] = int(row["new_id"])
print(f"  Unified drug entities: {len(drug_id_map)}")

# ─── 3. Parse north_african file: extract (dish, bioactive, drug) triples ────
print("\nParsing north_african_food_drug_interactions.txt...")

lines = open(NA_FILE, encoding="utf-8").readlines()

# Find dish headers and their bioactive→drug doc
dishes = []        # list of {num, name, pairs: [(bioactive, drug), ...]}
current_dish = None
current_num = 0

def extract_col(line, col_idx):
    parts = line.split("|")
    if len(parts) > col_idx + 1:
        return parts[col_idx + 1].strip()
    return ""

# We parse the table rows: col1=dish#, col2=bioactive, col3=drug
# Then interaction text for context
dish_pattern      = re.compile(r"^(\d+)\s*\|")
substance_terms   = set()  # collect all unique bioactives seen

for i, line in enumerate(lines):
    m = dish_pattern.match(line)
    if m:
        num = int(m.group(1))
        # col2 = dish name (if non-empty and not SMILES), col3 might be drug
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3:
            dish_name = parts[1].strip()
            col2 = parts[2].strip() if len(parts) > 2 else ""
            col3 = parts[3].strip() if len(parts) > 3 else ""
            current_dish = {"num": num, "name": dish_name, "pairs": [], "text": ""}
            dishes.append(current_dish)

    # table continuation row  "|   | bioactive | drug |"
    elif line.startswith("   |") and current_dish:
        parts = [p.strip() for p in line.split("|")]
        col2 = parts[2].strip() if len(parts) > 2 else ""
        col3 = parts[3].strip() if len(parts) > 3 else ""
        # skip separators, SMILES labels, empty
        if (col2 and col3
                and not col2.startswith("---")
                and not col2.startswith("SMILES")
                and not col2.startswith("Source")
                and "✓" not in col2
                and " " in col2   # bioactive names have spaces or "(...)":
                    or ("(" in col2 and "=" not in col2)):
            bioactive = re.sub(r"\[.*?\]", "", col2).strip()  # strip [✓]
            bioactive = re.sub(r"\s*\(.*?\)\s*$", "", bioactive).strip()
            if bioactive and col3:
                current_dish["pairs"].append((bioactive, col3))
                substance_terms.add(bioactive.lower())

    # capture interaction text lines for context
    elif line.startswith("   | Interaction") and current_dish:
        current_dish["text"] += line.strip() + " "

total_pairs = sum(len(d["pairs"]) for d in dishes)
print(f"  Dishes found: {len(dishes)}")
print(f"  Documented (bioactive, drug) pairs: {total_pairs}")

# ─── 4. Cross-check each pair against all DBs ─────────────────────────────────
print("\nCross-checking against databases...")

def check_databases(bioactive_lower, drug_lower):
    """Returns dict of {source: bool} and matched food/drug terms."""
    food_aliases = []
    for kw, aliases in BIOACTIVE_TO_FOOD.items():
        if kw in bioactive_lower or bioactive_lower in kw:
            food_aliases.extend(aliases)

    drug_variants = [drug_lower]
    # normalise common suffixes
    for suffix in [" (diabetes)", " (gout)", " substrates", " inhibitors",
                   " (anticoagulant)", " / ", "/"]:
        drug_variants.extend([p.strip() for p in drug_lower.split(suffix) if p.strip()])

    confirmed_a = confirmed_b = confirmed_c = confirmed_d = False
    matched_food = matched_drug = ""

    # Source A: DrugBank named pairs
    for db_drug, db_food in db_drugfood:
        drug_hit = any(dv in db_drug or db_drug in dv
                       for dv in drug_variants if len(dv) > 3)
        food_hit = any(fa in db_food or db_food in fa
                       for fa in food_aliases if len(fa) > 2)
        if drug_hit and food_hit:
            confirmed_a = True
            matched_food = db_food; matched_drug = db_drug
            break

    # Source B: DrugBank JSON text
    if not confirmed_a:
        for db_drug, text in db_json_texts:
            drug_hit = any(dv in db_drug or db_drug in dv
                           for dv in drug_variants if len(dv) > 3)
            food_hit = any(fa in text for fa in food_aliases if len(fa) > 3)
            if drug_hit and food_hit:
                confirmed_b = True
                matched_drug = db_drug
                break

    # Source C: PubMed NLP
    if not confirmed_a and not confirmed_b:
        for db_drug, db_food in db_pubmed:
            drug_hit = any(dv in db_drug or db_drug in dv
                           for dv in drug_variants if len(dv) > 3)
            food_hit = any(fa in db_food or db_food in fa
                           for fa in food_aliases if len(fa) > 2)
            if drug_hit and food_hit:
                confirmed_c = True
                matched_food = db_food; matched_drug = db_drug
                break

    # Source D: unified-DFI id presence (weaker - just checks if food exists)
    food_in_db = any(
        any(fa in fname or fname in fa for fa in food_aliases if len(fa) > 3)
        for fname in food_id_map
    )
    drug_in_db = any(
        any(dv in dname or dname in dv for dv in drug_variants if len(dv) > 3)
        for dname in drug_id_map
    )
    confirmed_d = food_in_db and drug_in_db

    sources = []
    if confirmed_a: sources.append("DrugBank-named")
    if confirmed_b: sources.append("DrugBank-text")
    if confirmed_c: sources.append("PubMed-NLP")
    if confirmed_d: sources.append("unified-DFI-nodes")

    return sources, food_aliases[:3], food_in_db, drug_in_db

# ─── 5. Build full report ──────────────────────────────────────────────────────
report_lines = []
stats = {"confirmed_strong": 0, "confirmed_node": 0, "novel": 0, "total": 0}

for dish in dishes:
    if not dish["pairs"]:
        continue
    report_lines.append(f"\n{'='*90}")
    report_lines.append(f"Dish {dish['num']:02d}: {dish['name']}")
    report_lines.append(f"{'='*90}")
    for bioactive, drug in dish["pairs"]:
        sources, food_aliases, food_in_db, drug_in_db = check_databases(
            bioactive.lower(), drug.lower()
        )
        stats["total"] += 1
        strong = [s for s in sources if s != "unified-DFI-nodes"]

        if strong:
            verdict = f"✓ CONFIRMED  [{', '.join(strong)}]"
            stats["confirmed_strong"] += 1
        elif sources:  # only unified-DFI node
            verdict = f"~ NODE-EXISTS  [both food+drug node in unified-DFI]"
            stats["confirmed_node"] += 1
        else:
            if not food_in_db and not drug_in_db:
                verdict = "? NOVEL  (neither food nor drug in any DB)"
            elif not food_in_db:
                verdict = f"? NOVEL-FOOD  (drug known, food '{food_aliases[:1]}' not in DB)"
            elif not drug_in_db:
                verdict = f"? NOVEL-DRUG  (food known, drug not in DB)"
            else:
                verdict = "? NOVEL-PAIR  (both exist singly, pair not confirmed)"
            stats["novel"] += 1

        line = f"  {verdict}"
        detail = f"    Bioactive: {bioactive:<30}  Drug: {drug[:55]}"
        if food_aliases:
            detail += f"\n    Food aliases tried: {', '.join(food_aliases[:4])}"
        report_lines.append(line)
        report_lines.append(detail)

# Summary
summary = f"""
{'='*90}
SUMMARY
{'='*90}
Total documented (bioactive → drug) pairs : {stats['total']}
  ✓ CONFIRMED (strong DB hit)              : {stats['confirmed_strong']}  ({100*stats['confirmed_strong']//max(stats['total'],1)}%)
  ~ NODE-EXISTS (food+drug in DFI graph)   : {stats['confirmed_node']}  ({100*stats['confirmed_node']//max(stats['total'],1)}%)
  ? NOVEL (not cross-confirmed)            : {stats['novel']}  ({100*stats['novel']//max(stats['total'],1)}%)

Databases checked:
  A) DrugBank named pairs        : {len(db_drugfood)} pairs
  B) DrugBank JSON food texts    : {len(db_json_texts)} entries
  C) PubMed NLP extracted pairs  : {len(db_pubmed)} pairs
  D) Unified-DFI node maps       : {len(food_id_map)} food nodes, {len(drug_id_map)} drug nodes
"""

all_lines = report_lines + [summary]
for l in all_lines:
    print(l)

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(all_lines))

print(f"\nFull report → {REPORT}")
