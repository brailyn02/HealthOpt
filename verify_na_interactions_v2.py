"""
verify_na_interactions_v2.py
Parse the COMPACT SUMMARY TABLE from north_african_food_drug_interactions.txt
(lines starting "# | Whole Food |...") and cross-check every
(bioactive compound, drug) pair against all workspace interaction databases.
"""

import re, json, csv, pathlib

ROOT    = pathlib.Path(r"d:\23AIBox-DFinder")
NA_FILE = ROOT / "north_african_food_drug_interactions.txt"
REPORT  = ROOT / "na_interaction_verification_v2.txt"

# ─── Bioactive → food-level aliases (what appears in DBs) ────────────────────
B2F = {
    "allicin":            ["garlic"],
    "ajoene":             ["garlic"],
    "quercetin":          ["quercetin","onion","parsley","apple","garlic"],
    "apigenin":           ["apigenin","parsley","chamomile","celery"],
    "kaempferol":         ["kaempferol","parsley","onion"],
    "luteolin":           ["luteolin","parsley","celery"],
    "curcumin":           ["curcumin","turmeric"],
    "piperine":           ["piperine","black pepper","pepper"],
    "gingerol":           ["ginger","gingerol"],
    "6-gingerol":         ["ginger","gingerol"],
    "capsaicin":          ["capsaicin","chili","pepper","capsicum"],
    "cinnamaldehyde":     ["cinnamon"],
    "coumarin":           ["cinnamon"],
    "eugenol":            ["eugenol","clove","cinnamon"],
    "linalool":           ["linalool","lavender","coriander"],
    "geraniol":           ["geraniol"],
    "limonene":           ["limonene","lemon","orange"],
    "carvone":            ["carvone","caraway","spearmint"],
    "cuminaldehyde":      ["cumin"],
    "safranal":           ["saffron"],
    "lycopene":           ["lycopene","tomato"],
    "beta-carotene":      ["beta-carotene","carrot","tomato"],
    "phytic acid":        ["phytic acid","phytate","soy","legume","wheat","bran"],
    "ip6":                ["phytic acid","phytate"],
    "sesamin":            ["sesame","sesamin"],
    "sesamolin":          ["sesame"],
    "resveratrol":        ["resveratrol","grape","wine","peanut"],
    "purine":             ["purine","meat","organ meat"],
    "uric acid":          ["purine","meat"],
    "hypoxanthine":       ["purine","meat"],
    "caffeine":           ["caffeine","coffee","tea"],
    "egcg":               ["green tea","tea","egcg","epigallocatechin"],
    "epigallocatechin":   ["green tea","tea","egcg","epigallocatechin"],
    "tannin":             ["tea","tannin","wine"],
    "tyramine":           ["tyramine","fermented","aged cheese"],
    "folate":             ["folate","folic acid","lentil","spinach"],
    "folic acid":         ["folic acid","folate","lentil"],
    "magnesium":          ["magnesium","nuts","legume"],
    "potassium":          ["potassium","banana","legume"],
    "calcium":            ["calcium","dairy","milk"],
    "iron":               ["iron"],
    "oleic acid":         ["olive oil","oleic acid"],
    "linoleic acid":      ["linoleic acid","omega-6","sunflower"],
    "ala":                ["alpha-linolenic","ala","flaxseed","omega-3"],
    "alpha-linolenic":    ["alpha-linolenic","ala","flaxseed","omega-3"],
    "epa":                ["epa","fish oil","omega-3","fish"],
    "eicosapentaenoic":   ["epa","fish oil","omega-3","fish"],
    "dha":                ["dha","fish oil","omega-3","fish"],
    "butyric acid":       ["butyrate","butter","dairy"],
    "butyrate":           ["butyrate","butter","dairy"],
    "palmitic acid":      ["palm","saturated fat","fat"],
    "vitamin k":          ["vitamin k","parsley","leafy green","spinach"],
    "vitamin c":          ["vitamin c","ascorbic acid","citrus"],
    "ascorbic acid":      ["ascorbic acid","vitamin c","citrus","lemon"],
    "citric acid":        ["citric acid","lemon","citrus"],
    "l-arginine":         ["arginine","nut","peanut","walnut"],
    "arginine":           ["arginine","nut","walnut"],
    "lecithin":           ["lecithin","egg","soy"],
    "choline":            ["choline","egg","lecithin"],
    "solanine":           ["solanine","potato"],
    "amygdalin":          ["amygdalin","almond","apricot","bitter almond"],
    "acrylamide":         ["acrylamide","fried","potato"],
    "benzo[a]pyrene":     ["benzo[a]pyrene","smoked","charred meat","barbecue"],
    "4-hne":              ["4-hne","oxidized fat","fried"],
    "rosmarinic acid":    ["rosemary","rosmarinic"],
    "cynarin":            ["artichoke","cynarin"],
    "silymarin":          ["silymarin","milk thistle"],
    "i3c":                ["broccoli","cauliflower","indole","crucifer"],
    "indole-3-carbinol":  ["broccoli","cauliflower","crucifer","indole"],
    "sulforaphane":       ["broccoli","sulforaphane","cauliflower"],
    "nasunin":            ["eggplant","aubergine"],
    "betaine":            ["beet","betaine"],
    "sucrose":            ["sucrose","sugar","honey"],
    "fructose":           ["fructose","sugar","fruit","honey"],
    "glucose":            ["glucose","sugar","carbohydrate"],
    "maltose":            ["maltose","malt"],
    "saponin":            ["saponin","legume","chickpea"],
    "pectin":             ["pectin","apple","citrus"],
    "inositol":           ["inositol"],
    "non-heme fe":        ["iron","non-heme"],
    "heme iron":          ["iron","red meat","heme"],
    "saturated fat":      ["saturated fat","fatty acid","butter","palm"],
    "sat.fats":           ["saturated fat","fatty acid","butter"],
    "omega-3":            ["omega-3","fish oil","epa","dha","ala","flaxseed"],
    "k+":                 ["potassium","banana","legume"],
    "na+":                ["sodium","salt"],
    "ages":               ["advanced glycation","age","maillard"],
    "tyramine":           ["tyramine","fermented"],
    "amylopectin":        ["starch","carbohydrate","bread","cereal"],
    "amylose":            ["starch","carbohydrate","rice","legume"],
    "beta-glucan":        ["oat","barley","beta-glucan"],
    "resistant starch":   ["starch","rye","barley"],
    "ferulic acid":       ["ferulic acid","wheat","bran","rice"],
    "tripalmitin":        ["palm oil","saturated fat","fat"],
    "bicarbonate":        ["baking soda","sodium bicarbonate"],
    "benzaldehyde":       ["almond","cherry","bitter almond"],
}

# Drug name normalisation: strip parenthetical context
def norm_drug(d):
    # Remove parenthetical notes like "(Gout)", "(Diabetes)" etc.
    d = re.sub(r"\s*\(.*?\)", "", d)
    d = re.sub(r"\*", "", d)
    d = d.strip().lower()
    return d

def get_food_aliases(bioactive):
    bl = bioactive.lower().strip()
    aliases = set()
    for kw, flist in B2F.items():
        if kw in bl or bl in kw or bl.startswith(kw) or kw.startswith(bl):
            aliases.update(flist)
    return list(aliases)

# ─── Load databases ───────────────────────────────────────────────────────────
print("Loading databases...")

# A) DrugBank named pairs (drug_name, food_name)
db_A = []
with open(ROOT / "generated" / "drugbank_drug_food_named.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        db_A.append((r["drug_name"].lower().strip(), r["food_name"].lower().strip()))

# B) DrugBank JSON food interaction texts
db_B = []
with open(ROOT / "Drug to Food interactions Dataset.json", encoding="utf-8") as f:
    for entry in json.load(f):
        drug = entry.get("name","").lower().strip()
        for fi in entry.get("food_interactions", []):
            db_B.append((drug, str(fi).lower()))

# C) PubMed NLP pairs
db_C = []
with open(ROOT / "dfi_interactions_from_keysentences.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        d = r.get("drug","").lower().strip()
        fo = r.get("food","").lower().strip()
        if d and fo:
            db_C.append((d, fo))

# D) Unified-DFI node maps
food_nodes = set()
with open(ROOT / "DFinder-main" / "data" / "unified-DFI" / "id_maps" / "food_id_map.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        food_nodes.add(r["name"].lower().strip())

drug_nodes = set()
with open(ROOT / "DFinder-main" / "data" / "unified-DFI" / "id_maps" / "drug_id_map.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        drug_nodes.add(r["name"].lower().strip())

print(f"  DB-A (DrugBank named): {len(db_A)}")
print(f"  DB-B (DrugBank texts): {len(db_B)}")
print(f"  DB-C (PubMed NLP)    : {len(db_C)}")
print(f"  DB-D food nodes      : {len(food_nodes)}, drug nodes: {len(drug_nodes)}")

# ─── Parse compact summary table ─────────────────────────────────────────────
# Lines of format: "NN | Dish Name | bioactive1, bioactive2 | drug1, drug2"
# The table starts after the "# | Whole Food | ..." header line.

lines = open(NA_FILE, encoding="utf-8").readlines()
table_start = None
for i, ln in enumerate(lines):
    if re.match(r'^#\s*\|.*Whole Food', ln):
        table_start = i + 2   # skip header + separator
        break

dishes = []  # [{num, name, bioactives:[str], drugs:[str]}]
if table_start:
    for ln in lines[table_start:]:
        ln = ln.rstrip("\n")
        m = re.match(r'^(\d+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*$', ln)
        if m:
            num       = int(m.group(1))
            name      = m.group(2).strip()
            bio_raw   = m.group(3).strip()
            drug_raw  = m.group(4).strip()
            # split on commas but protect parenthesised content
            def split_items(s):
                # split on top-level commas
                items, depth, cur = [], 0, ""
                for ch in s:
                    if ch == "(": depth += 1
                    elif ch == ")": depth -= 1
                    if ch == "," and depth == 0:
                        if cur.strip(): items.append(cur.strip()); cur = ""
                    else:
                        cur += ch
                if cur.strip(): items.append(cur.strip())
                return items
            bioactives = [re.sub(r'\(\*\)|\[.*?\]','',b).strip() for b in split_items(bio_raw) if b.strip()]
            drugs      = [re.sub(r'\(\*\)|\[.*?\]','',d).strip() for d in split_items(drug_raw) if d.strip()]
            dishes.append({"num": num, "name": name, "bioactives": bioactives, "drugs": drugs})

print(f"\nDishes in compact table: {len(dishes)}")
total_bio = sum(len(d["bioactives"]) for d in dishes)
total_drug = sum(len(d["drugs"]) for d in dishes)
print(f"Total bioactives: {total_bio}, total drugs: {total_drug}")

# ─── Check each bioactive against each drug ──────────────────────────────────
def check_pair(bioactive, drug):
    """Returns (sources_list, food_in_nodes, drug_in_nodes)."""
    aliases = get_food_aliases(bioactive)
    drug_l  = norm_drug(drug)
    drug_variants = [drug_l]
    # also split on "/" for "Warfarin/Aspirin" style
    drug_variants += [x.strip() for x in re.split(r'[/,]', drug_l) if len(x.strip()) > 3]

    confirmed = []

    # A: DrugBank named
    for db_drug, db_food in db_A:
        dhit = any(dv in db_drug or db_drug in dv for dv in drug_variants if len(dv) > 3)
        fhit = any(fa in db_food or db_food in fa for fa in aliases if len(fa) > 2)
        if dhit and fhit:
            confirmed.append(("DrugBank-named", db_drug, db_food))
            break

    # B: DrugBank JSON text
    if not confirmed:
        for db_drug, text in db_B:
            dhit = any(dv in db_drug or db_drug in dv for dv in drug_variants if len(dv) > 3)
            fhit = any(fa in text for fa in aliases if len(fa) > 3)
            if dhit and fhit:
                confirmed.append(("DrugBank-text", db_drug, ""))
                break

    # C: PubMed NLP
    if not confirmed:
        for db_drug, db_food in db_C:
            dhit = any(dv in db_drug or db_drug in dv for dv in drug_variants if len(dv) > 3)
            fhit = any(fa in db_food or db_food in fa for fa in aliases if len(fa) > 2)
            if dhit and fhit:
                confirmed.append(("PubMed-NLP", db_drug, db_food))
                break

    # D: node existence
    food_in = any(any(fa in fn or fn in fa for fa in aliases if len(fa) > 2) for fn in food_nodes)
    drug_in = any(any(dv in dn or dn in dv for dv in drug_variants if len(dv) > 3) for dn in drug_nodes)

    return confirmed, food_in, drug_in

# ─── Build report ─────────────────────────────────────────────────────────────
stats = {"confirmed": 0, "node_only": 0, "novel": 0, "total": 0}
report = []

for dish in dishes:
    dish_lines = []
    for bio in dish["bioactives"]:
        bio_clean = re.sub(r'\(.*?\)', '', bio).strip()
        for drg in dish["drugs"]:
            drg_clean = re.sub(r'\(.*?\)', '', drg).strip()
            if not bio_clean or not drg_clean:
                continue
            confirmed, food_in, drug_in = check_pair(bio_clean, drg_clean)
            stats["total"] += 1

            if confirmed:
                src, m_drug, m_food = confirmed[0]
                verdict = f"✓ {src}"
                stats["confirmed"] += 1
            elif food_in and drug_in:
                verdict = "~ node-only"
                stats["node_only"] += 1
            else:
                parts = []
                if not food_in: parts.append(f"food('{bio_clean[:20]}') not in DB")
                if not drug_in: parts.append(f"drug('{drg_clean[:20]}') not in DB")
                verdict = "? NOVEL — " + "; ".join(parts)
                stats["novel"] += 1

            aliases = get_food_aliases(bio_clean)
            dish_lines.append(
                f"  {verdict:<40}  {bio_clean:<30} → {drg_clean[:45]}"
            )

    if dish_lines:
        report.append(f"\nDish {dish['num']:02d}: {dish['name']}")
        report.append("-" * 90)
        report.extend(dish_lines)

# Summary
total = max(stats["total"], 1)
summary = f"""
{'='*90}
VERIFICATION SUMMARY
{'='*90}
Total (bioactive × drug) pairs checked  : {stats['total']}
  ✓ CONFIRMED  (DrugBank / PubMed)      : {stats['confirmed']:4d}  ({100*stats['confirmed']//total}%)
  ~ NODE-ONLY  (both in DFI graph)      : {stats['node_only']:4d}  ({100*stats['node_only']//total}%)
  ? NOVEL      (pair not in any DB)     : {stats['novel']:4d}  ({100*stats['novel']//total}%)

Sources used:
  DB-A  DrugBank named food↔drug pairs  : {len(db_A)}
  DB-B  DrugBank JSON interaction texts : {len(db_B)}
  DB-C  PubMed NLP extracted pairs      : {len(db_C)}
  DB-D  Unified-DFI node maps           : {len(food_nodes)} food + {len(drug_nodes)} drug nodes

INTERPRETATION:
  ✓ CONFIRMED  = interaction is documented in at least one external DB → solid evidence
  ~ NODE-ONLY  = both food entity and drug exist in the graph but no direct edge confirmed
  ? NOVEL      = interaction not found in any DB → either genuinely new signal OR
                 the bioactive/drug label needs alias expansion

Full report → {REPORT}
"""

all_output = report + [summary]
for l in all_output:
    print(l)

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(all_output))
