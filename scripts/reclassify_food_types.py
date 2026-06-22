"""
reclassify_food_types.py
=========================
Re-tags each entry in unified_food_master_clean.txt with one of five types:

  Food_Source          - whole food, ingredient, plant/animal source, preparation
  Compound_Group       - a class of compounds (flavonoids, tannins, extracts, …)
  Food Bioactive       - a specific isolated molecule with a defined structure
  Dietary Nutrient     - vitamins, minerals, macro-nutrients  [preserved]
  Dietary Amino Acid   - amino acids                         [preserved]
  Dietary Lipid        - fatty acids                         [preserved]
  Endogenous Metabolite- body intermediates, hormones        [preserved]

Priority order (higher beats lower):
  Endogenous Metabolite > Dietary Nutrient > Dietary Amino Acid > Dietary Lipid
  > Compound_Group > Food_Source > Food Bioactive

Outputs:
  generated/unified_food_master_typed.txt   – retyped master
  generated/food_retype_report.txt          – per-type summary + changed entries
"""

import re

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — TYPES TO PRESERVE (never reclassify)
# ══════════════════════════════════════════════════════════════════════════════

PRESERVE_TYPES = {
    "Endogenous Metabolite",
    "Dietary Nutrient",
    "Dietary Amino Acid",
    "Dietary Lipid",
}

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — COMPOUND_GROUP patterns
#  Matches names that are *classes* of compounds, not individual molecules.
# ══════════════════════════════════════════════════════════════════════════════

# Suffix-based: name ends with any of these (word boundary, case-insensitive)
_CG_SUFFIX_RE = re.compile(
    r"""
    \b(
      tannins?          | polyphenols?      | flavonoids?       |
      anthocyanins?     | proanthocyanidins?| catechins         |
      isoflavones?      | carotenoids?      | stilbenes?        |
      curcuminoids?     | xanthones?        | chalcones?        |
      terpenoids?       | triterpenoids?    | diterpenoids?     |
      monoterpenoids?   | sesquiterpenoids? | phytosterols?     |
      sterols?          | glucosinolates?   | thiocyanates?     |
      saponins?         | alkaloids?        | glycosides?       |
      polysaccharides?  | oligosaccharides? | monosaccharides?  |
      phospholipids?    | glycolipids?      | sphingolipids?    |
      lipids?           | glycerides?       | triglycerides?    |
      peptides?         | oligopeptides?    | proteins?         |
      fibers?           | fibre?            | lignins?          |
      disulfides?       | glucans?          | fructans?         |
      pectins?          | gums?             | starches?         |
      terpenes?         | diterpenes?       | triterpenes?      |
      resins?           | ginkgolides?      | cardenolides?     |
      bufadienolides?   | withanolides?     | cucurbitacins?    |
      ginsenosides?     | ketones?          | aldehydes         |
      coumarins         | chromones?        | quinones?         |
      benzoquinones?    | naphthoquinones?  | anthraquinones?   |
      furanocoumarins?  | lignans?          | neolignans?       |
      sugars?           | salicylates?      | tocopherols?      |
      anthocyanidins?   | leucoanthocyanidins?
    )\s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Keyword-anywhere: name contains these words as whole tokens
_CG_KEYWORD_RE = re.compile(
    r"""
    \b(
      extract(?:ion)?   | fraction          | concentrate       |
      preparation       | complex           | standardized      |
      enriched          | formulation       | mixture           |
      formula           | supplement        | powder            |
      infusion          | decoction         | tincture          |
      isolate           | hydrolysate       | digest[ae]?       |
      crude\s+extract   | total\s+extract   | aqueous\s+extract |
      ethanolic         | methanolic        | hexane            |
      residue           | fraction
    )\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Explicit Compound_Group entries (canonical names that are clearly classes)
_CG_EXPLICIT = {
    "anthocyanins", "flavonoids", "isoflavones", "carotenoids",
    "polyphenols", "tannins", "saponins", "alkaloids", "terpenoids",
    "lignans", "stilbenes", "curcuminoids", "phytosterols",
    "glucosinolates", "catechins", "proanthocyanidins",
    "fiber", "protein", "proteins", "fat", "sugars",
    "carbohydrates", "lipids", "vitamins",
    "resveratrol analogs", "phenolic compounds",
    "polyphenolic compounds", "phenylpropanoids",
    "bile acids", "short-chain fatty acids", "medium-chain fatty acids",
    "long-chain fatty acids", "omega-3 fatty acids",
    "glycosides", "antioxidants",
    "c-phycocyanin",      # phycocyanin is a protein pigment class
    "chitosan",           # deacetylated chitin polymer
    "carrageenan",        # polysaccharide class
    "galactomannan",      # polysaccharide
    "arabinogalactan",    # polysaccharide
    "curcuminoids",
    "ginkgosides",
    "tocopherols",
    "anthocyanidins",
    "ginsenosides",       # class name
    # enriched-keyword compound names (from the data)
    "blueberry anthocyanins-enriched extract",
    "buckwheat protein extract",
    "protopanaxatriol (pt) ginsenosides",
    "polysaccharides extracted from the egyptian mango mangifera indica",
    "grape seed proanthocyanidin extract",
}

# Tannin-compound or Polyphenol-compound name patterns:
_CG_COMPOUND_CLASS_RE = re.compile(
    r"\b(?:condensed|hydrolysable|ellagic|gallic|total)[\s-]+(?:tannins?|polyphenols?|flavonoids?)\b",
    re.IGNORECASE,
)

# Specific compounds that share a root with class names — always Food Bioactive.
# e.g. "catechin" is the monomer; "catechins" is the class.
_ALWAYS_BIOACTIVE = {
    "catechin",            # flavan-3-ol monomer
    "coumarin",            # specific benzopyrone
    "chalcone",            # specific α,β-unsaturated ketone
    "chromone",            # 1,4-benzopyrone
    "saponin",             # single triterpenoid glycoside unit
    "methyl salicylate",   # specific methyl ester of salicylic acid
    "ethyl salicylate",
    "glutathione disulfide",  # GSSG — specific peptide dimer
    "coniferyl aldehyde",  # specific phenylpropanoid
    "betaine aldehyde",    # specific metabolite
    "cinnamaldehyde",
    "benzaldehyde",
    "vanillin",
    "hexanal",
    "nonanal",
    "furfural",
    "hydroxymethylfurfural",
    "geranial",
    "citronellal",
    "neral",
    "perillaldehyde",
    "cuminaldehyde",
    "phenylacetaldehyde",
    "5-hydroxymethyl-2-furancarboxaldehyde",
    "methyl salicylate",
    "invert sugar",        # a specific 50:50 glucose/fructose mixture
    "carbon disulfide",    # not a class — a specific small molecule
}

def is_compound_group(name: str) -> bool:
    n = name.strip()
    nl = n.lower()
    if nl in _CG_EXPLICIT:
        return True
    if _CG_SUFFIX_RE.search(n):
        return True
    if _CG_KEYWORD_RE.search(n):
        return True
    if _CG_COMPOUND_CLASS_RE.search(n):
        return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 3 — FOOD_SOURCE patterns
#  Whole foods, culinary ingredients, organisms used as food sources.
# ══════════════════════════════════════════════════════════════════════════════

# Exhaustive curated set of whole food names (lowercased canonical forms)
FOOD_SOURCE_NAMES = {
    # ── Fruits ────────────────────────────────────────────────────────────────
    "apple", "apple sauce", "apricot", "avocado", "banana", "bilberry",
    "blackberry", "blackcurrant", "blueberry", "boysenberry", "breadfruit",
    "cantaloupe", "cherry", "cherries", "clementine", "coconut", "cranberry",
    "cranberries", "currant", "damson", "date", "desert date", "durian",
    "elderberry", "fig", "gooseberry", "grape", "grapefruit", "guava",
    "honeydew", "jackfruit", "kiwi", "kiwifruit", "kumquat", "lemon",
    "lime", "lychee", "mandarin", "mango", "melon", "mulberry", "nectarine",
    "orange", "papaya", "passion fruit", "peach", "pear", "persimmon",
    "pineapple", "plum", "pomegranate", "quince", "raspberry", "redcurrant",
    "starfruit", "strawberry", "tamarind", "tangerine", "watermelon",
    "bael fruit", "indian gooseberry", "amlaki",
    # ── Vegetables ────────────────────────────────────────────────────────────
    "artichoke", "asparagus", "beetroot", "beet", "broccoli", "brussels sprouts",
    "cabbage", "carrot", "carrots", "cauliflower", "celery", "corn",
    "courgette", "cucumber", "daikon", "eggplant", "fennel", "garlic",
    "garlic bulb", "horseradish", "kale", "leek", "lettuce", "onion",
    "parsnip", "pea", "pepper", "pumpkin", "radish", "shallot", "spinach",
    "squash", "sweet potato", "tomato", "turnip", "yam", "zucchini",
    "amaranth", "araceae", "chicory", "garden cress", "fava bean",
    "kidney beans", "lotus root", "bitter gourd", "adzuki bean",
    "chinese parsley", "brassica sprout",
    # ── Herbs & Spices ────────────────────────────────────────────────────────
    "anise", "anise myrtle", "angelica dahurica", "angelica keiskei",
    "ashwagandha", "basil", "bergamot", "black pepper", "cardamom",
    "cayenne", "chamomile", "cinnamon", "clove", "cnidium", "coriander",
    "cumin", "curry leaf", "dill", "echinacea", "fennel seed",
    "fenugreek", "ginger", "ginkgo biloba", "ginseng", "holy basil",
    "lavender", "lemon balm", "lemon myrtle", "licorice", "marjoram",
    "mint", "neem", "nutmeg", "oregano", "parsley", "peppermint",
    "rosemary", "sage", "st. john's wort", "tarragon", "thyme", "turmeric",
    "valerian", "vanilla", "citrus reticulate", "danshen compound",
    "cordyceps", "shi chang pu", "agave",
    # ── Tree/plant sources (culinary) ─────────────────────────────────────────
    "acorn", "almond", "brazil nut", "cashew", "chestnut", "hazelnut",
    "macadamia", "peanut", "pecan", "pistachio", "walnut", "pine nut",
    "flaxseed", "hemp seed", "pumpkin seed", "sesame", "sunflower seed",
    "groundnut", "soybean", "linseed",
    # ── Grains & Cereals ──────────────────────────────────────────────────────
    "barley", "buckwheat", "corn", "millet", "oat", "oats", "quinoa",
    "rice", "rye", "sorghum", "spelt", "wheat", "amaranth grain",
    # ── Legumes ───────────────────────────────────────────────────────────────
    "bean", "black bean", "chickpea", "lentil", "lima bean", "mung bean",
    "navy bean", "soy", "soya", "tofu", "tempeh", "edamame", "pigeonpea",
    # ── Animal foods ──────────────────────────────────────────────────────────
    "beef", "chicken", "duck", "egg", "fish", "goat", "herring", "lamb",
    "liver", "lobster", "mackerel", "mussel", "oyster", "pork", "prawn",
    "salmon", "sardine", "shrimp", "squid", "tuna", "turkey", "veal",
    "venison", "alaska pollock", "codliver", "abalone", "anchovy",
    # ── Dairy & Eggs ──────────────────────────────────────────────────────────
    "butter", "cheese", "cream", "dairy", "dairy product",
    "dairy product fermented by lactobacilli", "milk", "semi-skimmed milk",
    "whey", "yoghurt", "yogurt",
    # ── Fungi ─────────────────────────────────────────────────────────────────
    "mushroom", "shiitake", "reishi", "maitake", "oyster mushroom",
    "truffle", "yeast",
    # ── Algae & Marine Plants ─────────────────────────────────────────────────
    "algae", "alga", "brown algae", "gracilaria seaweed", "kelp",
    "nori", "spirulina", "chlorella", "wakame", "laminaria hyperborea",
    # ── Beverages ─────────────────────────────────────────────────────────────
    "ale", "beer", "black tea", "coffee", "cola", "fortified wine",
    "green tea", "herbal tea", "orange juice", "red wine", "rosé wine",
    "tea", "white wine", "wine", "whisky", "sake",
    "grapefruit juice", "clementine juice",
    # ── Oils & Fats ───────────────────────────────────────────────────────────
    "beef tallow", "canola", "canola oil", "castor", "castor oil",
    "coconut oil", "corn oil", "cottonseed", "cottonseed oil",
    "fish oil", "flaxseed oil", "fortified oil", "fresh palm oil",
    "groundnut oil", "groundnut oils", "lard", "linseed oil",
    "olive oil", "palm oil", "pistacia lentiscus oil",
    "pomegranate seeds oil", "soybean oil", "sunflower oil",
    "virgin coconut oil", "vegetable oil",
    # ── Sweeteners / Preparations ─────────────────────────────────────────────
    "honey", "molasses", "sugar", "maple syrup", "agave syrup",
    "cocoa", "chocolate", "salt", "vinegar",
    # ── Fermented / Processed foods ───────────────────────────────────────────
    "kimchi", "miso", "natto", "sauerkraut", "sourdough",
    "budo-no-megumi", "fish flakes",
    # ── Herbal multi-ingredient or organ-level items ───────────────────────────
    "milk thistle", "horse chestnut", "equisetum arvense l", "kudzu",
    "hibiscus rosa sinensis", "hibiscus sabdariffa", "hippophae rhamnoides",
    "garcinia kola", "cuscutae", "dioscorea", "elderflower",
    "chuan lian", "danggui", "against", "against formula",
    "dengzhan shengmai formula", "urtica dioica",
    "combretaceae", "compositae",
    # ── Whole-food preparations ───────────────────────────────────────────────
    "fruit juice", "fruit juices", "vegetable juice", "citrus juices",
    "pomegranate juice", "cranberry juice", "grape juice", "wine vinegar",
    "ginger-green tea mixture",
    # ── Plants used as herbal sources ────────────────────────────────────────
    "neem", "bearberry", "black chokeberry", "fingerroot",
    "tartary buckwheat sprouts", "tasmannia pepper leaf", "lemon balm",
    "baobab", "artichoke leaf", "coenzyme q10",
    # misc short generic terms
    "calcium", "fat", "fiber",  # these are nutrients/generic — will be caught by preserve or compound_group
}

# Single-word patterns that are clearly whole organisms / food sources
# (genera names, binomials ending in a capital-started second name — culinary)
_FS_GENUS_CULINARY = re.compile(
    r"""^
    (?: [A-Z][a-z]+                   # Single genus name
      | [A-Z][a-z]+ \s [a-z]+         # Binomial: Daucus carota
    )
    (?:\s+(?:L\.|Linn\.|Thunb\.|Mill\.|\([A-Z]\.\)[\s\w]+))?   # optional authority
    \s*$
    """,
    re.VERBOSE,
)

# Whole-food prep patterns  (name includes these phrases — different from
# "extract" which signals Compound_Group)
_FS_PREP_SUFFIX_RE = re.compile(
    r"""
    \b(
      juice(?:s)?       | sauce           | broth        |
      flesh             | peel            | rind         |
      seed(?:s)?        | nut(?:s)?       | grain(?:s)?  |
      flour             | starch          | pulp         |
      vinegar           | fermented       | dried        |
      smoked            | roasted         | boiled       |
      raw               | whole           | fresh
    )\s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Common culinary/food-source keywords anywhere in the name
_FS_KEYWORD_RE = re.compile(
    r"\b(sativum|officinalis|vulgaris|nucifera|sinensis|japonica|indica)\b",
    re.IGNORECASE,
)

def is_food_source(name: str) -> bool:
    nl = name.strip().lower()
    if nl in FOOD_SOURCE_NAMES:
        return True
    # Bilingual: check if any known single food word is an exact match
    # (handles capitalised versions)
    # Prep suffixes
    if _FS_PREP_SUFFIX_RE.search(name):
        return True
    # Very short 1-word names that are plainly foods
    # (not chemical-looking  — no digits, no hyphens as stereo markers)
    if (re.match(r"^[A-Za-z][a-z]+$", name.strip())
            and not re.search(r"\d", name)
            and len(name.split()) == 1
            and len(name) <= 20
            and nl in FOOD_SOURCE_NAMES):
        return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 4 — FOOD_BIOACTIVE: specific-molecule markers
#  These countersign that something really IS a specific compound even if
#  the surface name looks generic.
# ══════════════════════════════════════════════════════════════════════════════

# Stereo / position markers in name
_BIOACTIVE_STEREO_RE = re.compile(
    r"[\(\[][\+\-±RS,\d]+[\)\]]|"
    r"\b(?:alpha|beta|gamma|delta|omega)[-\s]"
    r"|\b[0-9]+[-,]",
    re.IGNORECASE,
)

# Chemical suffix families for specific molecules
_BIOACTIVE_SUFFIX_RE = re.compile(
    r"""
    (?:
      \b\w+(?:
          yl\s+(?:ester|ether|alcohol|acid|glycoside)
        | glucuronide | galactoside | glucoside | rutinoside
        | rhamnoside  | furanoside  | pyranoside | arabinoside
        | glucopyranoside|galactopyranoside
      )\b
    |
      \b(?:
        quercetin | kaempferol | isorhamnetin | myricetin | fisetin |
        luteolin   | apigenin   | chrysin      | naringenin| hesperetin|
        hesperidin | naringin   | rutin        | diosmin   | diosmetin |
        butein     | phloretin  | phlorizin    | silymarin | catechin  |
        epicatechin| epigallocatechin | gallocatechin |
        cyanidin   | delphinidin | pelargonidin | petunidin | malvidin  |
        peonidin   | caffeic\s*acid | chlorogenic\s*acid | ferulic\s*acid |
        rosmarinic\s*acid | gallic\s*acid | ellagic\s*acid |
        ursolic\s*acid | oleanolic\s*acid | betulinic\s*acid |
        curcumin   | resveratrol | pterostilbene | oxyresveratrol |
        capsaicin  | piperine    | gingerol      | shogaol      |
        berberine  | coptisine   | palmatine     | jatrorrhizine |
        colchicine | vinblastine | vincristine   | taxol        |
        baicalein  | baicalin    | wogonin       | scutellarein |
        genistein  | daidzein    | formononetin  | biochanin    |
        thymol     | carvacrol   | eugenol       | isoeugenol   |
        menthol    | borneol     | camphor       | linalool     |
        geraniol   | citral      | nerolidol     | farnesol     |
        lycopene   | zeaxanthin  | lutein        | astaxanthin  |
        beta[-\s]?carotene | canthaxanthin | fucoxanthin  |
        quercetin  | fisetin     | morin         | galangin     |
        limonene   | carvone     | perillaldehyde| pulegone     |
        thujone    | fenchone    | menthone      |
        sulforaphane | glucoraphanin | sinigrin   | allicin      |
        alliin     | ajoene      | diallyl       |
        coumarin   | umbelliferone | esculetin   | scopoletin   |
        bergapten  | psoralen    | isopsoralen   | xanthotoxin  |
        artemisinin | arteannuin  | artabsin      |
        silibinin  | silydianin  | silychristin  |
        crocin     | crocetin    | safranal      |
        ginsenoside| panaxatriol | panaxadiol    |
        astragalin | astragaloside| astragalus   |
        chlorophyll| pheophytin  | pheophorbide  |
        lutein     | violaxanthin| neoxanthin    |
        anthocyanin(?:\s+-\d[-\w]+)   # specific glycoside: cyanidin 3-glucoside
      )\b
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)


def is_specific_molecule(name: str) -> bool:
    """True if the name looks like a specific molecular compound."""
    # Stereo / position prefix → almost always a specific compound
    if _BIOACTIVE_STEREO_RE.search(name):
        return True
    # Known specific molecule names
    if _BIOACTIVE_SUFFIX_RE.search(name):
        return True
    # IUPAC-like: contains digit-hyphen (3-hydroxy…, 4-methyl…, etc.)
    if re.search(r"\b\d+-[A-Za-z]", name):
        return True
    # Glycoside / ester / ether derivatives
    if re.search(r"\b\w{4,}(?:oside|uronide|glycoside|acetate|formate|benzoate|palmitate)\b", name, re.I):
        return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 5 — MAIN CLASSIFICATION FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def reclassify(food_id: int, name: str, current_type: str) -> str:
    """Return the new type for this entry."""
    # 1. Preserved types are never touched
    if current_type in PRESERVE_TYPES:
        return current_type

    # 2. Compound_Group check (highest priority among reclassifiable types)
    # But first: specific molecules that share a root with class names —
    # these are always individual bioactives regardless of suffix matches.
    _nl = name.strip().lower()
    if _nl in _ALWAYS_BIOACTIVE:
        return "Food Bioactive"
    if is_compound_group(name):
        return "Compound_Group"

    # 3. Food_Source check
    if is_food_source(name):
        return "Food_Source"

    # For entries currently labelled "Food / Whole-Food Preparation":
    # if they are NOT a compound group they must be Food_Source
    if current_type == "Food / Whole-Food Preparation":
        return "Food_Source"

    # 4. Default: Food Bioactive (specific molecule)
    return "Food Bioactive"


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 6 — ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from collections import defaultdict

    GENERATED = r"d:\23AIBox-DFinder\generated"
    IN_PATH   = f"{GENERATED}/unified_food_master_clean.txt"
    OUT_PATH  = f"{GENERATED}/unified_food_master_typed.txt"
    RPT_PATH  = f"{GENERATED}/food_retype_report.txt"

    # ── read ──────────────────────────────────────────────────────────────────
    entries = []
    with open(IN_PATH, encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            fid, fname, ftype = int(parts[0]), parts[1], parts[2]
            entries.append((fid, fname, ftype))

    print(f"Loaded {len(entries)} entries.")

    # ── reclassify ────────────────────────────────────────────────────────────
    results = []
    changed = []
    type_counts_before = defaultdict(int)
    type_counts_after  = defaultdict(int)

    for fid, fname, ftype in entries:
        type_counts_before[ftype] += 1
        new_type = reclassify(fid, fname, ftype)
        type_counts_after[new_type] += 1
        results.append((fid, fname, new_type))
        if new_type != ftype:
            changed.append((fid, fname, ftype, new_type))

    # ── write new master ──────────────────────────────────────────────────────
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        for fid, fname, new_type in results:
            fh.write(f"{fid}\t{fname}\t{new_type}\n")

    print(f"Written: {OUT_PATH}")
    print(f"Changed: {len(changed)} entries")

    # ── report ────────────────────────────────────────────────────────────────
    changed_by_transition: dict[str, list] = defaultdict(list)
    for fid, fname, old, new in changed:
        changed_by_transition[f"{old}  →  {new}"].append((fid, fname))

    report_lines = [
        "=== Food Type Reclassification Report ===\n\n",
        "--- Type counts BEFORE ---\n",
    ]
    for t, c in sorted(type_counts_before.items()):
        report_lines.append(f"  {t:<40s} {c:>5}\n")

    report_lines += ["\n--- Type counts AFTER ---\n"]
    for t, c in sorted(type_counts_after.items()):
        report_lines.append(f"  {t:<40s} {c:>5}\n")

    report_lines += [f"\n--- Changed entries ({len(changed)} total) ---\n"]
    for transition, items in sorted(changed_by_transition.items()):
        report_lines.append(f"\n  [{transition}]  ({len(items)})\n")
        for fid, fname in sorted(items, key=lambda x: x[0]):
            report_lines.append(f"    {fid:>5}  {fname}\n")

    with open(RPT_PATH, "w", encoding="utf-8") as fh:
        fh.writelines(report_lines)

    print(f"Report: {RPT_PATH}")
    print("\nType counts after reclassification:")
    for t, c in sorted(type_counts_after.items()):
        print(f"  {t:<40s} {c:>5}")
