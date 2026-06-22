"""
Drug-Food Interaction Database Cleaner
=======================================
Cleans and deduplicates food and drug lists from a DFI database.

Usage:
    python clean_dfi_lists.py --foods food_list.csv --drugs drug_list.csv

Outputs:
    cleaned_foods.csv   - deduplicated food list with canonical names and aliases
    cleaned_drugs.csv   - drug list with category and dual-role flags
    cleaning_report.txt - summary of all changes made
"""

import csv
import re
import argparse
from collections import defaultdict

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

# Entries to remove entirely (NLP artifacts, non-food terms)
ARTIFACT_ENTRIES = {
    "drug", "intervention", "supplementation", "supplemented", "treatments",
    "treatment", "treated groups", "they", "it", "compounds", "compound",
    "extract", "fractions", "all fractions", "all plant extracts",
    "plant crude extract", "the oil", "lipids", "protein", "legume",
    "juices", "fruit juices", "vegetable", "essential", "essential oil",
    "methanol extracts", "cooking oils", "emulsifiers", "grain legumes",
    "flavonoid", "flavonoids", "polyphenol", "phenolic acids", "saponin",
    "infant weaning foods", "vegetable food", "vegetable infant weaning food",
    "refined-grain", "whole-grain", "whole-grain cereal", "multivitamin",
    "supplementation", "fractions", "s.", "k", "as", "it", "they",
    "intervention", "drug", "roxb.", "rossa", "extract of ginkgo biloba",
}

# Manual synonym groups: each tuple = (canonical_name, [list of aliases])
# Lower-case for matching; canonical will be title-cased in output
MANUAL_SYNONYMS = [
    ("Resveratrol",             ["rsv", "rv", "rvl", "res", "resv", "3,4',5-trihydroxystilbene",
                                  "3,4,5-trihydroxystilbene", "isorhapontigenin"]),
    ("Ginkgo Biloba",           ["ginkgo", "ginko", "ginkgo biloba extract", "ginkgo biloba extracts",
                                  "ginkgo biloba leaf extract", "g. biloba", "g. biloba extract",
                                  "egb761", "gbe", "extract of ginkgo biloba", "e-cs"]),
    ("Ginseng",                 ["panax", "panax ginseng", "panax ginseng c.a. meyer",
                                  "american ginseng", "panax quinquefolius", "red ginseng",
                                  "korean red ginseng", "korean red ginseng total extract",
                                  "krge", "ginseng", "rg"]),
    ("Panax Notoginseng",       ["panax notoginseng ledeb", "panax notoginseng saponins",
                                  "san chi", "notoginsenoside", "xuesaitong", "pns"]),
    ("Saffron",                 ["crocus sativus", "crocin"]),
    ("Curcumin",                ["curcuma longa", "curcuma longa linn", "turmeric",
                                  "turmeric rhizome powder suspension", "haridra",
                                  "curcuminoids", "curcuminoid", "curcumin i"]),
    ("Grapefruit",              ["grapefruit juice", "gfj", "grape fruit", "sweetie juice",
                                  "pomelo", "pomelo extract"]),
    ("Green Tea",               ["green tea extract", "gte", "camellia sinensis", "tea",
                                  "black tea"]),
    ("Licorice",                ["glycyrrhiza", "glycyrrhiza glabra fabaceae", "g. glabra",
                                  "g. uralensis", "glycyrrhizin", "glycyrrhizic acid",
                                  "glycyrrhetinic acid", "glycerrhitinic acid",
                                  "aqueous licorice extract", "licorice extract", "licorice root",
                                  "liquorice", "methanolic extract of g. glabra",
                                  "methanolic extract of glycyrrhiza glabra"]),
    ("Silymarin",               ["silybum marianum", "milk thistle", "silybin", "silychristin",
                                  "silydianin", "silymarine", "isosilybin"]),
    ("Nigella Sativa",          ["nigella", "black seed", "blackseed", "n. sativa oil",
                                  "nigella sativa oil", "nso", "ns", "thymoquinone"]),
    ("St. John's Wort",         ["hypericum perforatum", "hypericum perforatum extract",
                                  "h. perforatum", "sjw", "st john's wort"]),
    ("Vitamin B6",              ["vit. b6", "vit.b6", "vitamin b6"]),
    ("Vitamin C",               ["ascorbic acid", "vit.c", "vitamin c"]),
    ("Vitamin K",               ["vitamin k1", "vitamin k2", "vitamin k3", "vitamins k2"]),
    ("Coenzyme Q10",            ["coq10", "ubidecarenone"]),
    ("Berberine",               ["berberis vulgaris", "berberis crude extract",
                                  "barberry extract", "barberry crude extract",
                                  "barberry ethanolic extract", "berberine chloride", "bbr"]),
    ("Garlic",                  ["garlic bulb", "garlic preparations", "allium atroviolaceum",
                                  "a.atroviolaceum extract"]),
    ("Ginger",                  ["zingiber", "zingiber officinale", "zingiberaceae",
                                  "ginger rhizome", "10-gingerol"]),
    ("Fenugreek",               ["trigonella foenum-graecum", "t. foenum-graecum",
                                  "t. foenum-graecum aqueous extract", "fenugreek"]),
    ("Pomegranate",             ["punica granatum", "p. granatum", "pomegranate juice",
                                  "pomegranate seeds oil"]),
    ("Quercetin",               ["quercitin"]),
    ("Fava Bean",               ["faba bean", "vicia faba", "broad bean", "fava beans"]),
    ("Cranberry",               ["vaccinium macrocarpon", "cranberries", "cranberry juice"]),
    ("Olive Oil",               ["olive", "olive oil"]),
    ("Rosemary",                ["rosmarinus officinalis", "rosmarinus officinalis l.",
                                  "r. officinalis", "rosemary tea"]),
    ("Soybean",                 ["soyabeans", "soybean extract", "soybean oil", "soy lecithin"]),
    ("Hibiscus Sabdariffa",     ["roselle", "h. sabdariffa"]),
    ("Arctostaphylos Uva-Ursi", ["bearberry leaf", "uvae ursi", "arbutin"]),
    ("Danshen",                 ["salvia miltiorrhiza", "salvia", "fufang danshen dripping pill"]),
    ("Piperine",                ["piper longum", "piper longum l."]),
    ("Morinda Citrifolia",      ["morinda citrifolia linn", "morinda citrifolia linn.", "noni"]),
    ("Momordica Charantia",     ["bitter gourd", "bitter melon leaf extract",
                                  "m. charantia extract", "methanolic extract of momordica charantia l",
                                  "mc"]),
    ("Portulaca Oleracea",      ["portulaca oleracea l.", "p. oleracea"]),
    ("Rhodiola Rosea",          ["rhodiola"]),
    ("Schisandra Chinensis",    ["schisandra"]),
    ("Dehydroepiandrosterone",  ["dhea"]),
    ("Citrus Reticulate",       ["citrus unshiu", "mandarin", "mandarin juice"]),
    ("Grape Seed",              ["grape seed proanthocyanidin extract", "gspe", "vitis vinifera",
                                  "vitis vinifera leaves polyphenolic", "grapes", "grape juice"]),
    ("Mangosteen",              ["garcinia mangostana", "g.mangostana", "gamma-mangostin"]),
    ("Thyme",                   ["thymus vulgaris", "thyme (thymus vulgaris) leaf aqueous extract"]),
    ("Chamomile",               ["chamomile essential oi"]),   # typo in original
    ("Mentha Piperita",         ["mentha", "mentha spicata", "m. spicata"]),
    ("Cnidium",                 ["cnidium monnier (l.) cuss", "fructus cnidii"]),
    ("Fennel",                  ["foeniculum vulgare", "foeniculum vulgare (fennel) essential oil",
                                  "oil of foeniculum vulgare mill", "fennel oil"]),
    ("Rutabaga",                ["rutabaga sprout", "rutabaga sprouts",
                                  "brassica napus l. var. napobrassica"]),
    ("Kiwi",                    ["kiwifruit"]),
    ("Cherries",                ["cherry"]),
    ("Spirulina",               ["spirulina platensis", "polysaccharide of spirulina platensis"]),
    ("Cocoa",                   ["theobroma cacao", "t. cacao", "chocolate", "cocoa powder"]),
    ("Terminalia Belerica",     ["t. belerica"]),
    ("Azadirachta Indica",      ["a. indica"]),
    ("Asparagus Officinalis",   ["a. officinalis"]),
    ("Amaranthus Tricolor",     ["a. tricolor", "red spinach"]),
    ("Rosa Damascena",          ["rosa damascena extract"]),
    ("Hypericum Perforatum",    ["h. perforatum"]),
]

# Radiopharmaceuticals and other unlikely DFI drug categories
RADIOPHARMACEUTICAL_KEYWORDS = [
    "technetium", "iodide i-", "iodide i ", "choline c-11", "fluorodopa",
    "fludeoxyglucose", "radium ra", "indium in-", "ioflupane", "tetrofosmin",
    "iothalamic", "ioxaglic", "copper oxodotreotide"
]

BIOLOGICAL_KEYWORDS = [
    "interferon", "insulin", "erythropoietin", "darbepoetin", "alteplase",
    "anistreplase", "streptokinase", "urokinase", "reteplase", "tenecteplase",
    "desmoteplase", "monteplase", "amediplase", "saruplase", "ancrod",
    "antithrombin", "protein c", "protein s", "brentuximab", "polatuzumab",
    "trastuzumab", "obinutuzumab", "ibritumomab", "denosumab", "canakinumab",
    "mepolizumab", "avelumab", "dulaglutide", "liraglutide", "semaglutide",
    "exenatide", "pramlintide", "mecasermin", "taliglucerase", "fidanacogene",
    "valoctocogene", "fecal microbiota", "vibrio cholerae"
]

# Substances appearing in both food and drug lists
DUAL_ROLE_SUBSTANCES = {
    "zinc", "vitamin e", "vitamin d", "vitamin d3", "ascorbic acid", "vitamin c",
    "lutein", "coenzyme q10", "niacin", "riboflavin", "thiamine", "biotin",
    "melatonin", "chromium", "magnesium", "iron", "calcium", "selenium",
    "dehydroepiandrosterone", "dhea", "ginkgo biloba", "ginseng", "berberine",
    "resveratrol", "curcumin", "quercetin", "piperine", "silymarin",
    "echinacea", "valerian", "st. john's wort", "garlic", "ginger",
    "cranberry", "green tea", "saffron"
}

# ─────────────────────────────────────────────
# FOOD CLEANING
# ─────────────────────────────────────────────

def normalize(name):
    """Lowercase, strip, collapse whitespace."""
    return re.sub(r'\s+', ' ', name.strip().lower())

def build_synonym_map():
    """Build a dict: normalized_alias -> canonical_name"""
    syn_map = {}
    for canonical, aliases in MANUAL_SYNONYMS:
        canon_norm = normalize(canonical)
        syn_map[canon_norm] = canonical
        for alias in aliases:
            syn_map[normalize(alias)] = canonical
    return syn_map

def clean_foods(input_rows):
    """
    Takes list of dicts with 'food_name' key.
    Returns (cleaned_rows, report_lines).
    """
    syn_map = build_synonym_map()
    
    # Group by canonical name
    canonical_groups = defaultdict(set)  # canonical -> set of original names seen
    removed = []
    
    for row in input_rows:
        name = row.get('food_name') or row.get('canonical_name', '')
        name = name.strip()
        norm = normalize(name)
        
        # Skip empty
        if not norm:
            continue
        
        # Remove artifacts
        if norm in ARTIFACT_ENTRIES:
            removed.append(name)
            continue
        
        # Skip pure abbreviation noise (1-3 uppercase letters alone, or single chars)
        if re.fullmatch(r'[A-Z]{1,3}', name) or re.fullmatch(r'[a-z]', name):
            removed.append(f"{name} (uninformative abbreviation)")
            continue
        
        # Check synonym map
        if norm in syn_map:
            canonical = syn_map[norm]
        else:
            # Title-case the name as canonical
            canonical = name.title()
        
        canonical_groups[canonical].add(name)
    
    # Build output rows
    cleaned = []
    for food_id, (canonical, originals) in enumerate(sorted(canonical_groups.items())):
        aliases = sorted(o for o in originals if normalize(o) != normalize(canonical))
        dual = "yes" if normalize(canonical) in DUAL_ROLE_SUBSTANCES else ""
        cleaned.append({
            "food_id": food_id,
            "canonical_name": canonical,
            "aliases": "; ".join(aliases),
            "dual_role": dual,
        })
    
    report = []
    report.append(f"FOOD CLEANING SUMMARY")
    report.append(f"  Input entries:   {len(input_rows)}")
    report.append(f"  After cleaning:  {len(cleaned)}")
    report.append(f"  Removed ({len(removed)} entries):")
    for r in sorted(set(removed)):
        report.append(f"    - {r}")
    
    return cleaned, report

# ─────────────────────────────────────────────
# DRUG CLEANING
# ─────────────────────────────────────────────

def categorize_drug(name):
    norm = name.lower()
    if any(kw in norm for kw in RADIOPHARMACEUTICAL_KEYWORDS):
        return "radiopharmaceutical"
    if any(kw in norm for kw in BIOLOGICAL_KEYWORDS):
        return "biological"
    return "pharmaceutical"

def find_enantiomer_groups(rows):
    """Find drugs that are enantiomers or salt/ester forms of each other."""
    # Simple heuristic: strip (R)-, (S)-, prefixes and match base names
    base_map = defaultdict(list)
    for row in rows:
        name = row['drug_name']
        base = re.sub(r'^\([RS]\)-', '', name, flags=re.IGNORECASE).strip()
        base_map[base.lower()].append(name)
    
    enantiomer_notes = {}
    for base, variants in base_map.items():
        if len(variants) > 1:
            for v in variants:
                others = [x for x in variants if x != v]
                enantiomer_notes[v] = f"Enantiomer/variant of: {', '.join(others)}"
    return enantiomer_notes

def clean_drugs(input_rows):
    """
    Takes list of dicts with 'drug_name' key.
    Returns (cleaned_rows, report_lines).
    """
    enantiomer_notes = find_enantiomer_groups(input_rows)
    
    cleaned = []
    radio_count = 0
    bio_count = 0
    dual_count = 0
    
    for row in input_rows:
        name = row['drug_name'].strip()
        drug_id = row['drug_id']
        
        category = categorize_drug(name)
        if category == "radiopharmaceutical":
            radio_count += 1
        elif category == "biological":
            bio_count += 1
        
        dual = "yes" if normalize(name) in DUAL_ROLE_SUBSTANCES else ""
        if dual:
            dual_count += 1
        
        notes = enantiomer_notes.get(name, "")
        
        cleaned.append({
            "drug_id": drug_id,
            "drug_name": name,
            "category": category,
            "dual_role": dual,
            "notes": notes,
        })
    
    report = []
    report.append(f"\nDRUG CLEANING SUMMARY")
    report.append(f"  Total drugs:          {len(cleaned)}")
    report.append(f"  Pharmaceuticals:      {len(cleaned) - radio_count - bio_count}")
    report.append(f"  Biologicals:          {bio_count}")
    report.append(f"  Radiopharmaceuticals: {radio_count}")
    report.append(f"  Dual-role (food+drug):{dual_count}")
    
    return cleaned, report

# ─────────────────────────────────────────────
# I/O HELPERS
# ─────────────────────────────────────────────

def read_csv(filepath):
    with open(filepath, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def write_csv(filepath, rows, fieldnames):
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def write_report(filepath, lines):
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Clean DFI food and drug lists.")
    parser.add_argument('--foods',  required=True, help='Input food CSV (food_id, food_name or canonical_name)')
    parser.add_argument('--drugs',  required=True, help='Input drug CSV (drug_id, drug_name)')
    parser.add_argument('--out-foods',  default='cleaned_foods.csv')
    parser.add_argument('--out-drugs',  default='cleaned_drugs.csv')
    parser.add_argument('--out-report', default='cleaning_report.txt')
    args = parser.parse_args()
    
    print("Reading input files...")
    food_rows = read_csv(args.foods)
    drug_rows = read_csv(args.drugs)
    
    print("Cleaning food list...")
    cleaned_foods, food_report = clean_foods(food_rows)
    
    print("Cleaning drug list...")
    cleaned_drugs, drug_report = clean_drugs(drug_rows)
    
    print("Writing outputs...")
    write_csv(args.out_foods, cleaned_foods,
              ['food_id', 'canonical_name', 'aliases', 'dual_role'])
    write_csv(args.out_drugs, cleaned_drugs,
              ['drug_id', 'drug_name', 'category', 'dual_role', 'notes'])
    
    all_report = food_report + drug_report
    write_report(args.out_report, all_report)
    
    print("\n" + "\n".join(all_report))
    print(f"\nOutputs written to:")
    print(f"  {args.out_foods}")
    print(f"  {args.out_drugs}")
    print(f"  {args.out_report}")

if __name__ == '__main__':
    main()
