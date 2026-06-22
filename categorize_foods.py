"""
Food Entry Categorization and Enhancement
===========================================
Adds semantic categories to food entries and handles special cases:
- Element symbols (Ag, Ba, K, Mn, Zn) → expand to full names
- Treatment/formulation codes → tag as "formulation"
- Mixture codes → tag as "multi-ingredient"  
- Author notation → tag as "unresolved_abbreviation"

Outputs:
    foods_categorized.csv - enhanced food list with category column
"""

import csv
import re
from collections import defaultdict

# ─────────────────────────────────────────────
# ELEMENT SYMBOLS (PERIODIC TABLE)
# ─────────────────────────────────────────────

ELEMENT_SYMBOLS = {
    "ag": ("Silver", "elemental"),
    "ba": ("Barium", "elemental"),
    "k": ("Potassium", "elemental"),
    "mn": ("Manganese", "elemental"),
    "zn": ("Zinc", "elemental"),
    "se": ("Selenium", "elemental"),
    "fe": ("Iron", "elemental"),
    "ca": ("Calcium", "elemental"),
    "mg": ("Magnesium", "elemental"),
    "cu": ("Copper", "elemental"),
    "cr": ("Chromium", "elemental"),
    "co": ("Cobalt", "elemental"),
    "ni": ("Nickel", "elemental"),
    "zp": ("Zinc", "elemental"),  # typo variant
}

# ─────────────────────────────────────────────
# PROPRIETARY FORMULATIONS
# ─────────────────────────────────────────────

FORMULATION_CODES = {
    "c-pc": "C-Phycocyanin Complex",
    "e-cs": "Extract Combination Study",
    "egb761": "Ginkgo Biloba Standardized Extract",
    "ws 1442": "Crataegi Standardized Extract",
    "da-9801": "Proprietary Korean Herbal Formula",
    "ggt mixture": "Ginger-Green Tea Mixture",
    "enna complex": "ENNA Complex",
    "naoxintong": "Naoxintong Formula",
    "shexiang baoxin": "Shexiang Baoxin Formula",
    "dengzhan shengmai": "Dengzhan Shengmai Formula",
    "fufang danshen dripping pill": "Fufang Danshen Dripping Pill",
    "lisosan g": "Lisosan G Complex",
    "hpe": "Harpagophytum Procumbens Extract",
    "hre-1": "Hypericum Extract Formulation",
    "krge": "Korean Red Ginseng Extract",
    "gbe": "Ginkgo Biloba Extract",
    "gte": "Green Tea Extract",
    "gfj": "Grapefruit Juice",
    "ws1442": "Crataegi Standardized Extract",
}

# ─────────────────────────────────────────────
# MULTI-INGREDIENT MIXTURES
# ─────────────────────────────────────────────

MULTI_INGREDIENT_KEYWORDS = [
    "mixture", "complex", "blend", "combination", "dripping pill", "formula",
    "herbal mixtures", "polyherbal", "extract extracts"  # "extracts" plural often means blend
]

# ─────────────────────────────────────────────
# AUTHOR NOTATION (unresolvable abbreviations)
# ─────────────────────────────────────────────

# Single/double letter author codes or study IDs
AUTHOR_NOTATION_PATTERNS = [
    r"^[a-z]\.[a-z]$",           # N.S., M.C., etc.
    r"^[a-z]{1,3}[0-9]+$",       # tf001, pa15, etc.
    r"^[a-z]{2}-[a-z]$",         # tf-d, cp-1, etc.
    r"^[a-z]{1,2}$",             # Single/double letters: tf, mo, pa, rg, sa, sbt
    r"^[a-z]{1,3}-only$",        # study-only, tf-only
]

KNOWN_AUTHOR_CODES = {
    "tf", "mo", "pa", "rg", "sa1", "sbt", "da", "mmc", "mps", "mpme",
    "plo", "qps", "sc", "rc", "vs", "ac", "pc", "bc", "cc", "cs", "hp",
    "hc", "kc", "lc", "nc", "oc", "tc", "uc", "wc", "yc", "zc"
}

# ─────────────────────────────────────────────
# CATEGORIZATION LOGIC
# ─────────────────────────────────────────────

def normalize(name):
    """Lowercase, strip, collapse whitespace."""
    return re.sub(r'\s+', ' ', name.strip().lower())

def categorize_food(canonical_name):
    """
    Determine semantic category and optionally return normalized canonical name.
    Returns: (category, updated_canonical_name)
    """
    norm = normalize(canonical_name)
    
    # 1. Check if it's an element symbol
    if norm in ELEMENT_SYMBOLS:
        element_name, category = ELEMENT_SYMBOLS[norm]
        return (category, element_name)
    
    # 2. Check if it's a known formulation code
    if norm in FORMULATION_CODES:
        expanded = FORMULATION_CODES[norm]
        return ("formulation", expanded)
    
    # 3. Check for multi-ingredient keywords
    if any(kw in norm for kw in MULTI_INGREDIENT_KEYWORDS):
        return ("multi-ingredient", canonical_name)
    
    # 4. Check if it's author notation
    if re.match(r'^[a-z]{1,3}$', norm) and norm in KNOWN_AUTHOR_CODES:
        return ("unresolved_abbreviation", canonical_name)
    
    for pattern in AUTHOR_NOTATION_PATTERNS:
        if re.match(pattern, norm):
            return ("unresolved_abbreviation", canonical_name)
    
    # 5. Default: plant/botanical
    return ("botanical", canonical_name)

def merge_zn_zinc(rows):
    """
    Merge Zn and Zinc entries, keeping Zinc as canonical.
    Returns updated rows and merge info.
    """
    # Find Zn and Zinc entries
    zn_idx = None
    zinc_idx = None
    
    for i, row in enumerate(rows):
        norm = normalize(row['canonical_name'])
        if norm == "zn":
            zn_idx = i
        elif norm == "zinc":
            zinc_idx = i
    
    merged_info = None
    
    if zn_idx is not None and zinc_idx is not None:
        # Merge Zn into Zinc
        zn_aliases = rows[zn_idx].get('aliases', '')
        zinc_aliases = rows[zinc_idx].get('aliases', '')
        
        # Combine aliases
        all_aliases = set()
        if zn_aliases:
            all_aliases.update(a.strip() for a in zn_aliases.split(';') if a.strip())
        if zinc_aliases:
            all_aliases.update(a.strip() for a in zinc_aliases.split(';') if a.strip())
        
        # Update Zinc entry
        rows[zinc_idx]['aliases'] = "; ".join(sorted(all_aliases))
        
        # Mark Zn for removal
        merged_info = (zn_idx, "Zn merged into Zinc")
        
        # Remove Zn row
        rows = [r for i, r in enumerate(rows) if i != zn_idx]
    
    return rows, merged_info

def process_foods(input_file):
    """
    Read cleaned foods CSV, categorize entries, merge duplicates,
    and return enhanced rows with report.
    """
    rows = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Merge Zn and Zinc
    rows, merge_info = merge_zn_zinc(rows)
    
    # Categorize each entry
    enhancements = defaultdict(int)  # category -> count
    updated_rows = []
    canon_updates = []
    
    for row in rows:
        category, updated_canonical = categorize_food(row['canonical_name'])
        
        row['category'] = category
        if updated_canonical != row['canonical_name']:
            canon_updates.append({
                'old': row['canonical_name'],
                'new': updated_canonical,
                'category': category
            })
            row['canonical_name'] = updated_canonical
        
        enhancements[category] += 1
        updated_rows.append(row)
    
    # Regenerate food_id after merge
    for i, row in enumerate(updated_rows):
        row['food_id'] = str(i)
    
    report = []
    report.append("=" * 60)
    report.append("FOOD CATEGORIZATION SUMMARY")
    report.append("=" * 60)
    report.append(f"\nInput entries:  {len(rows)}")
    report.append(f"After merge:    {len(updated_rows)}")
    if merge_info:
        report.append(f"Merges:         {merge_info[1]}")
    
    report.append(f"\nCategory Distribution:")
    for category in sorted(enhancements.keys()):
        count = enhancements[category]
        report.append(f"  {category:30s}: {count:3d}")
    
    if canon_updates:
        report.append(f"\nCanonical Name Updates ({len(canon_updates)}):")
        for update in canon_updates[:10]:  # Show first 10
            report.append(f"  {update['old']:40s} → {update['new']:30s} [{update['category']}]")
        if len(canon_updates) > 10:
            report.append(f"  ... and {len(canon_updates) - 10} more")
    
    report.append("\nElement Expansions:")
    elem_examples = []
    for row in updated_rows:
        if row['category'] == 'elemental':
            elem_examples.append(row['canonical_name'])
    if elem_examples:
        for elem in sorted(set(elem_examples))[:10]:
            report.append(f"  - {elem}")
    
    report.append("\nUnresolved Abbreviations (recommend manual review/exclusion):")
    unresolved = [r for r in updated_rows if r['category'] == 'unresolved_abbreviation']
    if unresolved:
        for row in sorted(unresolved, key=lambda x: x['canonical_name'])[:15]:
            report.append(f"  - {row['canonical_name']:30s} (ID: {row['food_id']})")
        if len(unresolved) > 15:
            report.append(f"  ... and {len(unresolved) - 15} more")
    else:
        report.append("  None found")
    
    report.append("\nFormulations (proprietary/study-specific):")
    formulations = [r for r in updated_rows if r['category'] == 'formulation']
    if formulations:
        for row in sorted(formulations, key=lambda x: x['canonical_name'])[:10]:
            report.append(f"  - {row['canonical_name']:50s} (ID: {row['food_id']})")
        if len(formulations) > 10:
            report.append(f"  ... and {len(formulations) - 10} more")
    else:
        report.append("  None found")
    
    report.append("\nMulti-Ingredient Mixtures:")
    mixtures = [r for r in updated_rows if r['category'] == 'multi-ingredient']
    if mixtures:
        for row in sorted(mixtures, key=lambda x: x['canonical_name'])[:10]:
            report.append(f"  - {row['canonical_name']:50s} (ID: {row['food_id']})")
        if len(mixtures) > 10:
            report.append(f"  ... and {len(mixtures) - 10} more")
    else:
        report.append("  None found")
    
    report.append("\n" + "=" * 60)
    
    return updated_rows, report

def write_output(rows, output_file, report_file):
    """Write categorized foods and report."""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['food_id', 'canonical_name', 'aliases', 'dual_role', 'category'])
        writer.writeheader()
        writer.writerows(rows)
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_file if isinstance(report_file, list) else [report_file]))

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    
    input_file = 'foods_cleaned_final.csv'
    output_file = 'foods_categorized.csv'
    report_file = 'categorization_report.txt'
    
    print(f"Reading {input_file}...")
    rows, report = process_foods(input_file)
    
    print(f"Writing {output_file}...")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['food_id', 'canonical_name', 'aliases', 'dual_role', 'category'])
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Writing {report_file}...")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    
    print('\n'.join(report))
    print(f"\nOutputs written to:")
    print(f"  {output_file}")
    print(f"  {report_file}")
