"""
parse_food_interactions.py

Parses drugbank_food_pairs.csv → extracts specific named foods/substances
from each food_interaction_text.

Output: drugbank_drug_food_named.csv  (drug_name, food_name)  – deduplicated
"""

import re
import pandas as pd

INPUT  = r'd:\23AIBox-DFinder\generated\drugbank_food_pairs.csv'
OUTPUT = r'd:\23AIBox-DFinder\generated\drugbank_drug_food_named.csv'

# ── SKIP patterns ────────────────────────────────────────────────────────────
# Sentences that are purely generic administration instructions with no
# named food/substance – drop the WHOLE sentence if it matches.
SKIP_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'^take\s+(with|on|without|after)',
        r'^administer\s+vitamin\s+supplements?[\.\s]*$',   # bare "Administer vitamin supplements."
        r'^administer\s+calcium\s+supplements?[\.\s]*$',
        r'^administer\s+folic\s+acid\s+supplements?[\.\s]*$',
        r'^administer\s+iron\s+supplements?[\.\s]*$',
        r'^drink\s+plenty\s+of\s+fluids',
        r'^maintain\s+(adequate|good)\s+hydration',
        r'^ensure\s+adequate\s+hydration',
        r'^avoid\s+(food|foods)\s+and\s+drinks\s+that\s+are\s+high\s+in\s+(fat|calories)',
        r'^monitor\s+diet',
        r'^separate\s+(administration|dosing)',
        r'^administer\s+with\s+food',
        r'^food\s+does\s+not\s+affect',
        r'^no\s+(clinically\s+)?significant\s+(food|dietary)',
    ]
]

# ── NAMED FOOD / SUBSTANCE RULES ────────────────────────────────────────────
# Each rule: (regex_pattern, canonical_food_name)
# Order matters for overlapping patterns – more specific first.
# A single sentence can yield MULTIPLE matches.
RULES = [
    # ── Grapefruit family ──────────────────────────────────────────────────
    (r'seville\s+orange',                          'seville orange'),
    (r'pomelo',                                    'pomelo'),
    (r'bitter\s+orange',                           'bitter orange'),
    (r'grapefruit',                                'grapefruit'),

    # ── Herbal supplements ─────────────────────────────────────────────────
    (r"st\.?\s*john'?s?\s*wort",                   "st. john's wort"),
    (r'\bechinacea\b',                             'echinacea'),
    (r'\bkava\b',                                  'kava'),
    (r'\bvalerian\b',                              'valerian'),
    (r'\bginkgo\b',                                'ginkgo biloba'),
    (r'\bginseng\b',                               'ginseng'),
    (r'\bgoldenseal\b',                            'goldenseal'),
    (r'\bephedra\b',                               'ephedra'),
    (r'\bblack\s+cohosh\b',                        'black cohosh'),
    (r'\bsaw\s+palmetto\b',                        'saw palmetto'),
    (r'\bmilk\s+thistle\b',                        'milk thistle'),
    (r'\bgarlic\s+(supplement|extract|herb)',       'garlic supplement'),
    (r'\bgarlic\b',                                'garlic'),
    (r'\bturmeric\b',                              'turmeric'),
    (r'\bcurcumin\b',                              'turmeric'),
    (r'\bchamomile\b',                             'chamomile'),
    (r'\blicorice\b',                              'natural licorice'),
    (r'\bnatural\s+licorice\b',                    'natural licorice'),

    # ── Anticoagulant / hypertensive / serotonergic herb categories ────────
    (r'herbs?\s+(and\s+supplements?\s+)?with\s+anticoagulant',
                                                   'anticoagulant herbs'),
    (r'herbs?\s+(or\s+supplements?\s+)?that\s+(may\s+)?increase\s+blood\s+pressure',
                                                   'hypertensive herbs'),
    (r'herbs?\s+(or\s+supplements?\s+)?with\s+hypotensive',
                                                   'hypotensive herbs'),
    (r'herbs?\s+that\s+(may\s+)?(lower|reduce)\s+blood\s+(pressure|sugar)',
                                                   'hypoglycemic herbs'),
    (r'serotonergic\s+herbs?',                     'serotonergic herbs'),

    # ── Alcohol ────────────────────────────────────────────────────────────
    (r'\balcohol\b',                               'alcohol'),
    (r'\bethanol\b',                               'alcohol'),
    (r'\bdrinking\b.*\bwine|beer|spirits\b',       'alcohol'),

    # ── Caffeine / stimulants ──────────────────────────────────────────────
    (r'\bxanthines?\b',                            'xanthines'),
    (r'\bcaffeine\b',                              'caffeine'),
    (r'\bcaffeinated\b',                           'caffeine'),
    (r'\bcoffee\b',                                'coffee'),
    (r'\bgreen\s+tea\b',                           'green tea'),
    (r'\btea\b',                                   'tea'),
    (r'\bcola\b',                                  'cola'),
    (r'\bcoca-?cola\b',                            'cola'),
    (r'\benergy\s+drinks?\b',                      'energy drinks'),
    (r'\bguarana\b',                               'guarana'),
    (r'\bmaté?\b',                                 'yerba mate'),
    (r'\byerba\s+mate\b',                          'yerba mate'),

    # ── Dairy / calcium foods ──────────────────────────────────────────────
    (r'\bdairy\b',                                 'dairy'),
    (r'\bmilk\b',                                  'milk'),
    (r'\bcheese\b',                                'cheese'),
    (r'\baged\s+cheese\b',                         'aged cheese'),
    (r'\byogurt\b',                                'yogurt'),
    (r'\bicecream|ice\s+cream\b',                  'ice cream'),
    (r'\bcalcium.?rich\s+foods?\b',                'calcium-rich foods'),
    (r'\bcalcium\s+in\s+(food|diet)',              'calcium-rich foods'),

    # ── Vitamin K / anticoagulation foods ──────────────────────────────────
    (r'\bvitamin\s+k[\-\s]?rich\b',               'vitamin K-rich foods'),
    (r'\bvitamin\s+k\s+in\s+(food|diet)',          'vitamin K-rich foods'),
    (r'\bvitamin\s+k\b',                           'vitamin K'),
    (r'\bgreen\s+leafy\s+vegetables?\b',           'green leafy vegetables'),
    (r'\bleafy\s+greens?\b',                       'green leafy vegetables'),
    (r'\bspinach\b',                               'spinach'),
    (r'\bkale\b',                                  'kale'),
    (r'\bbroccoli\b',                              'broccoli'),
    (r'\bbrussels\s+sprouts?\b',                   'brussels sprouts'),

    # ── Tyramine-containing foods ───────────────────────────────────────────
    (r'\btyramine[\-\s]?(?:rich|containing|laden)?\s*foods?\b',
                                                   'tyramine-containing foods'),
    (r'\btyramine\b',                              'tyramine-containing foods'),
    (r'\bfermented\s+(food|meat|product)',         'fermented foods'),
    (r'\baged\s+(meat|food|product)',              'aged/fermented foods'),
    (r'\bsauerkraut\b',                            'sauerkraut'),
    (r'\bmiso\b',                                  'miso'),
    (r'\bsoy\s+sauce\b',                           'soy sauce'),
    (r'\bfava\s+beans?\b',                         'fava beans'),
    (r'\bpickled\s+',                              'pickled foods'),
    (r'\bcured\s+meat',                            'cured/processed meats'),
    (r'\bprocessed\s+meat',                        'cured/processed meats'),
    (r'\bsmoked\s+(fish|meat|salmon)',             'smoked fish/meat'),
    (r'\borgan\s+meats?\b',                        'organ meats'),

    # ── Potassium-rich foods ────────────────────────────────────────────────
    (r'\bpotassium[\-\s]?(?:rich|containing)?\s*foods?\b',
                                                   'potassium-rich foods'),
    (r'\bpotassium\s+in\s+(food|diet)',            'potassium-rich foods'),
    (r'\bpotassium\b',                             'potassium-rich foods'),
    (r'\bbanana\b',                                'banana'),
    (r'\bavocado\b',                               'avocado'),

    # ── Fiber ──────────────────────────────────────────────────────────────
    (r'\bhigh[\-\s]fiber\s+(?:diet|foods?)\b',     'high-fiber foods'),
    (r'\bdietary\s+fiber\b',                       'high-fiber foods'),
    (r'\bfiber[\-\s]?rich\b',                      'high-fiber foods'),
    (r'\bbran\b',                                  'high-fiber foods'),
    (r'\bpsyllium\b',                              'psyllium/fiber'),

    # ── Vitamin C ──────────────────────────────────────────────────────────
    (r'\bvitamin\s+c[\-\s]?rich\b',               'vitamin C-rich foods'),
    (r'\bvitamin\s+c\b',                           'vitamin C'),
    (r'\bascorbic\s+acid\b',                       'vitamin C'),
    (r'\bcitrus\b',                                'citrus'),
    (r'\borange\s+juice\b',                        'orange juice'),

    # ── Other fruit juices ─────────────────────────────────────────────────
    (r'\bapple\s+juice\b',                         'apple juice'),
    (r'\bcranberry\s+juice\b',                     'cranberry juice'),
    (r'\bcranberry\b',                             'cranberry'),
    (r'\bpomegranate\s+juice\b',                   'pomegranate juice'),
    (r'\bfruit\s+(?:juice|drink)',                 'fruit juice'),

    # ── Iodine / goitrogenic ───────────────────────────────────────────────
    (r'\biodine[\-\s]?(?:rich|containing)?\s*foods?\b',
                                                   'iodine-containing foods'),
    (r'\biodine\b',                                'iodine'),
    (r'\bgoitrogenic\s+foods?\b',                  'goitrogenic foods'),
    (r'\bgoitrogen',                               'goitrogenic foods'),

    # ── Histamine ──────────────────────────────────────────────────────────
    (r'\bhistamine[\-\s]?(?:rich|containing)?\s*foods?\b',
                                                   'histamine-containing foods'),
    (r'\bhistamine\b',                             'histamine-containing foods'),

    # ── Furanocoumarins / flavonoids ────────────────────────────────────────
    (r'\bfurancoumarin',                           'furancoumarin-containing foods'),
    (r'\bflavonoid[\-\s]?(?:rich)?\s*foods?\b',    'flavonoid-rich foods'),
    (r'\bflavonoid',                               'flavonoid-rich foods'),
    (r'\bquercetin\b',                             'quercetin (flavonoid)'),
    (r'\bresveratrol\b',                           'resveratrol'),
    (r'\banthocyanin',                             'anthocyanin-rich foods'),

    # ── Soybeans / soy ─────────────────────────────────────────────────────
    (r'\bsoy(?:beans?)?\b',                        'soy/soybean'),
    (r'\btofu\b',                                  'tofu'),

    # ── High-fat / high-protein ────────────────────────────────────────────
    (r'\bhigh[\-\s]fat\s+(?:meal|diet|food)',      'high-fat foods'),
    (r'\bfatty\s+(meal|food)',                     'high-fat foods'),
    (r'\bhigh[\-\s]protein\s+(?:meal|diet|food)',  'high-protein foods'),

    # ── Salt / sodium ──────────────────────────────────────────────────────
    (r'\bhigh[\-\s]salt\b',                        'high-salt foods'),
    (r'\bsodium[\-\s]?rich\b',                     'high-salt foods'),
    (r'\bsalt\s+intake\b',                         'high-salt foods'),

    # ── Sugar / carbohydrates ──────────────────────────────────────────────
    (r'\bhigh[\-\s]sugar\b',                       'high-sugar foods'),
    (r'\bsugary\b',                                'high-sugar foods'),

    # ── Specific foods ─────────────────────────────────────────────────────
    (r'\bchocolate\b',                             'chocolate'),
    (r'\bcocoa\b',                                 'chocolate'),
    (r'\bpomelo\b',                                'pomelo'),
    (r'\bavidin\b',                                'avidin (raw egg white)'),
    (r'\braw\s+eggs?\b',                           'avidin (raw egg white)'),
    (r'\bblack\s+pepper\b',                        'black pepper'),
    (r'\bpiperine\b',                              'black pepper'),
    (r'\btannin',                                  'tannin-rich foods'),
    (r'\boxalic\s+acid\b',                         'oxalate-rich foods'),
    (r'\boxalate',                                 'oxalate-rich foods'),
    (r'\bphytic\s+acid\b',                         'phytate-rich foods'),
    (r'\bphytate',                                 'phytate-rich foods'),
    (r'\bphytochemical',                           'phytochemical-rich foods'),
    (r'\bgrape\s+(?!fruit)',                       'grapes'),
    (r'\bapple\b',                                 'apple'),
    (r'\btomato\b',                                'tomato'),
    (r'\bpapaya\b',                                'papaya'),
    (r'\bmango\b',                                 'mango'),
    (r'\bpineapple\b',                             'pineapple'),
    (r'\bwatermelon\b',                            'watermelon'),
    (r'\bbeets?\b',                                'beets'),
    (r'\bcelery\b',                                'celery'),
    (r'\bparsley\b',                               'parsley'),
    (r'\bcoriander\b',                             'coriander'),
    (r'\bgingerroot|ginger\s+root\b|\bginger\b',   'ginger'),

    # ── Iron ───────────────────────────────────────────────────────────────
    (r'\biron[\-\s]?(?:rich|containing)?\s*foods?\b',
                                                   'iron-rich foods'),
    (r'\biron\s+in\s+(food|diet)',                 'iron-rich foods'),
    (r'\biron\s+(supplement|preparation)',         'iron supplements'),
    (r'\biron\b',                                  'iron'),

    # ── Calcium supplements vs food ────────────────────────────────────────
    (r'\bcalcium\s+supplement',                    'calcium supplements'),
    (r'\bcalcium\b',                               'calcium-rich foods'),

    # ── Vitamins (supplement vs food) ──────────────────────────────────────
    (r'\bvitamin\s+a\s+supplement',               'vitamin A supplements'),
    (r'\bvitamin\s+a\b',                           'vitamin A'),
    (r'\bvitamin\s+b12\b',                         'vitamin B12'),
    (r'\bvitamin\s+b6\b',                          'vitamin B6 (pyridoxine)'),
    (r'\bpyridoxine\b',                            'vitamin B6 (pyridoxine)'),
    (r'\bvitamin\s+b3\b',                          'niacin (vitamin B3)'),
    (r'\bniacin\b',                                'niacin (vitamin B3)'),
    (r'\bvitamin\s+d\b',                           'vitamin D'),
    (r'\bvitamin\s+e\b',                           'vitamin E'),
    (r'\bfolate\b',                                'folic acid/folate'),
    (r'\bfolic\s+acid\b',                          'folic acid/folate'),
    (r'\bmelatonin\b',                             'melatonin'),
    (r'\bmagnesium\b',                             'magnesium'),
    (r'\bzinc\b',                                  'zinc'),
    (r'\bselenium\b',                              'selenium'),
    (r'\bomega[\-\s]3\b',                          'omega-3 fatty acids'),
    (r'\bfish\s+oil\b',                            'fish oil/omega-3'),
    (r'\bcoenzyme\s+q10\b|CoQ10',                  'CoQ10'),
    (r'\bchromium\b',                              'chromium'),
    (r'\bprobiotic',                               'probiotics'),
    (r'\bprebiotic',                               'prebiotics'),
]

# Compile all patterns
COMPILED_RULES = [
    (re.compile(pattern, re.IGNORECASE), canonical)
    for pattern, canonical in RULES
]

# ── Deduplicate food_name labels ─────────────────────────────────────────────
# Some rules share the same canonical name via two patterns (e.g. grapefruit
# variants).  We rely on Python set deduplication per sentence below.

def extract_foods(text: str) -> list[str]:
    """Return the list of canonical food names matched in text (deduped, ordered)."""
    text = str(text)

    # Check if entire sentence should be skipped
    for skip_pat in SKIP_PATTERNS:
        if skip_pat.search(text):
            return []

    found = set()
    for pattern, canonical in COMPILED_RULES:
        if pattern.search(text):
            found.add(canonical)
    return sorted(found)


def main():
    df = pd.read_csv(INPUT)
    df['food_interaction_text'] = df['food_interaction_text'].fillna('').astype(str)

    rows = []
    for _, row in df.iterrows():
        drug = row['drug_name']
        text = row['food_interaction_text']
        foods = extract_foods(text)
        for food in foods:
            rows.append({'drug_name': drug, 'food_name': food})

    out = pd.DataFrame(rows, columns=['drug_name', 'food_name'])
    out = out.drop_duplicates()
    out = out.sort_values(['drug_name', 'food_name']).reset_index(drop=True)

    out.to_csv(OUTPUT, index=False)
    print(f"Saved {len(out):,} unique (drug, food) pairs → {OUTPUT}")

    # Stats
    print(f"Unique drugs:  {out['drug_name'].nunique():,}")
    print(f"Unique foods:  {out['food_name'].nunique():,}")
    print("\nTop 30 most-interacting foods:")
    print(out['food_name'].value_counts().head(30).to_string())
    print("\nSample rows:")
    print(out.head(20).to_string(index=False))


if __name__ == '__main__':
    main()
