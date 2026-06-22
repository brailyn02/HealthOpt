"""
Phase 9 - Step 1: Parse DrugBank XML → drug_sensitivity_table.csv

Streams the 1.85 GB full database.xml using iterparse with start+end events.
Memory-safe: only keeps the current main drug element in memory; everything
outside is cleared as it ends.

Output columns:
    drugbank_id, name, cation_sensitive, vka, maoi, k_sparing, acid_dependent,
    food_interaction_texts
"""

import csv
import xml.etree.ElementTree as ET
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
NS      = 'http://www.drugbank.ca'
XML_IN  = Path('D:/23AIBox-DFinder/full database.xml')
CSV_OUT = Path('D:/23AIBox-DFinder/data/drug_sensitivity_table.csv')

# ── Keyword sets per flag ─────────────────────────────────────────────────────
# Anchored to <food-interactions> text only (except vka/maoi which also use moa)
CATION_KEYWORDS = {
    'calcium', 'dairy', 'milk', 'antacid', 'multivalent', 'magnesium',
    'iron', 'zinc', 'insoluble complex', 'chelat', 'mineral', 'supplement',
    'fortified juice', 'feed', 'divalent'
}
VKA_KEYWORDS_FI  = {'vitamin k', 'leafy vegetable', 'anticoagul', 'coagulation'}
VKA_KEYWORDS_MOA = {'vitamin k epoxide reductase', 'vkor', 'vitamin k antagonist'}
MAOI_KEYWORDS_FI  = {'tyramine', 'fermented', 'aged cheese', 'monoamine oxidase',
                      'maoi', 'mao inhibitor'}
MAOI_KEYWORDS_CAT = {'monoamine oxidase inhibitor'}
K_KEYWORDS_FI     = {'potassium', 'hyperkalem', 'k+ retention', 'potassium-rich',
                      'potassium supplement'}
K_KEYWORDS_MOA    = {'potassium-sparing', 'aldosterone', 'epithelial sodium channel',
                     'enac', 'angiotensin-converting enzyme inhibitor',
                     'angiotensin receptor'}
ACID_KEYWORDS_FI  = {'gastric ph', 'acidic environment', 'acidic drink',
                     'proton pump', 'ppi', 'antacid', 'low ph', 'gastric acid',
                     'gastric acidity', 'dissolution'}

# Extra: check absorption tag for acid-dependent absorption signals
ACID_KEYWORDS_ABSORPTION = {
    'gastric ph', 'acidic environment', 'low ph', 'gastric acid',
    'ph-dependent', 'requires acid', 'elevated ph', 'reduced at higher ph'
}

# Category-based class checks (catches whole drug classes DrugBank food-interactions misses)
CATION_CATEGORIES = {'fluoroquinolones', 'quinolone antibiotics', 'tetracyclines',
                     'bisphosphonates', 'thyroid drugs'}

def _text(elem, tag):
    """Get text of a direct child element, or empty string."""
    child = elem.find(f'{{{NS}}}{tag}')
    return (child.text or '').strip() if child is not None else ''

def _matches(text_lower, keywords):
    return any(kw in text_lower for kw in keywords)

def _get_categories(elem):
    cats = elem.find(f'{{{NS}}}categories')
    if cats is None:
        return ''
    return ' | '.join(
        (c.find(f'{{{NS}}}category').text or '').lower()
        for c in cats
        if c.find(f'{{{NS}}}category') is not None
    )

def classify_drug(elem):
    """Extract flags and evidence text from a main <drug> element."""
    db_id = ''
    for id_el in elem.findall(f'{{{NS}}}drugbank-id'):
        if id_el.get('primary') == 'true':
            db_id = id_el.text or ''
            break
    if not db_id:
        id_el = elem.find(f'{{{NS}}}drugbank-id')
        db_id = (id_el.text or '') if id_el is not None else ''

    name       = _text(elem, 'name')
    moa        = _text(elem, 'mechanism-of-action').lower()
    absorption = _text(elem, 'absorption').lower()
    cats       = _get_categories(elem)

    # Collect all food-interaction strings
    fi_block = elem.find(f'{{{NS}}}food-interactions')
    fi_texts = []
    if fi_block is not None:
        fi_texts = [
            (c.text or '').strip()
            for c in fi_block
            if c.text and c.text.strip()
        ]
    fi_combined = ' | '.join(fi_texts).lower()

    # ── Flag rules ────────────────────────────────────────────────────────────
    cation    = int(_matches(fi_combined, CATION_KEYWORDS) or
                    any(kw in cats for kw in CATION_CATEGORIES))
    vka       = int(_matches(fi_combined, VKA_KEYWORDS_FI) or
                    _matches(moa, VKA_KEYWORDS_MOA))
    maoi      = int(_matches(fi_combined, MAOI_KEYWORDS_FI) or
                    any(kw in cats for kw in MAOI_KEYWORDS_CAT))
    k_sparing = int(_matches(fi_combined, K_KEYWORDS_FI) or
                    _matches(moa, K_KEYWORDS_MOA))
    acid      = int(_matches(fi_combined, ACID_KEYWORDS_FI) or
                    _matches(absorption, ACID_KEYWORDS_ABSORPTION))

    flagged = any([cation, vka, maoi, k_sparing, acid])

    return {
        'drugbank_id':             db_id,
        'name':                    name,
        'cation_sensitive':        cation,
        'vka':                     vka,
        'maoi':                    maoi,
        'k_sparing':               k_sparing,
        'acid_dependent':          acid,
        'food_interaction_texts':  ' | '.join(fi_texts),
        'flagged':                 int(flagged),
    }

# ── Main streaming parse ──────────────────────────────────────────────────────
def main():
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)

    FIELDS = ['drugbank_id', 'name', 'cation_sensitive', 'vka', 'maoi',
              'k_sparing', 'acid_dependent', 'food_interaction_texts']

    context = ET.iterparse(str(XML_IN), events=('start', 'end'))
    inside_main_drug = False   # True while we're inside a top-level <drug type="...">
    drug_depth        = 0       # nesting counter for <drug> tags
    total             = 0
    flagged_count     = 0

    with open(CSV_OUT, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()

        for event, elem in context:
            tag = elem.tag

            if event == 'start':
                if tag == f'{{{NS}}}drug':
                    if not inside_main_drug and 'type' in elem.attrib:
                        # Entering a top-level drug entry
                        inside_main_drug = True
                        drug_depth = 1
                    elif inside_main_drug:
                        drug_depth += 1   # nested <drug> inside drug-interactions

            elif event == 'end':
                if tag == f'{{{NS}}}drug' and inside_main_drug:
                    drug_depth -= 1
                    if drug_depth == 0:
                        # Completed a full top-level drug element — process it
                        row = classify_drug(elem)
                        total += 1
                        if row['flagged']:
                            flagged_count += 1
                            writer.writerow({k: row[k] for k in FIELDS})

                        elem.clear()
                        inside_main_drug = False

                        if total % 1000 == 0:
                            print(f'  Processed {total} drugs, {flagged_count} flagged...')

                elif not inside_main_drug:
                    # Outside any main drug block — safe to clear immediately
                    elem.clear()

    print(f'\nDone. Total drugs: {total} | Flagged: {flagged_count}')
    print(f'Output: {CSV_OUT}')

if __name__ == '__main__':
    main()
