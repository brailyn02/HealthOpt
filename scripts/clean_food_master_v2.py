"""
clean_food_master_v2.py
========================
Comprehensive cleaning pipeline for unified_food_master.txt.

Exposes the public function:
    clean_food_data(raw_list) -> list[dict]

Which is called automatically when this script is run directly to:
  1. Filter irrelevant entries (noble gases, heavy metals, industrial chemicals,
     pharmaceutical-only drugs, false-positive alkaloids).
  2. Deduplicate stereoisomers (group (+)/(-)/R/S variants under parent name).
  3. Normalise common-name vs. scientific-name duplicates.
  4. Flag endogenous metabolites and dietary bioactives with a 'type' tag.
  5. Write:
       generated/unified_food_master_clean.txt   — cleaned master
       generated/food_id_remap.csv              — old_id -> new_canonical_id
       generated/food_cleaning_report.txt       — full audit report

Interactions file is also rewritten with remapped food IDs.

RDKit is used (if installed) to canonicalise SMILES when a foodb_food_smiles.csv
sidecar is present, ensuring cross-reference accuracy.
PubChemPy is used (if installed) to resolve ambiguous scientific names; results
are cached so only one network call per unique name is made.
"""

import re
import csv
import os
from collections import defaultdict

# ── optional heavy imports ────────────────────────────────────────────────────
try:
    from rdkit import Chem
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False

try:
    import pubchempy as pcp
    PUBCHEM_AVAILABLE = True
except ImportError:
    PUBCHEM_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════════════════════
#  REFERENCE LISTS
# ═══════════════════════════════════════════════════════════════════════════════

# ── 1. Hard-remove sets ───────────────────────────────────────────────────────

NOBLE_GASES = {
    "argon", "helium", "neon", "krypton", "xenon", "radon",
}

# Elemental metals and non-food elements.
# Note: nutritionally relevant minerals (calcium, iron, zinc, magnesium,
# potassium, sodium, selenium, iodine) are EXCLUDED from this block-list.
IRRELEVANT_ELEMENTS = {
    "silver", "gold", "platinum", "barium", "aluminum", "aluminium",
    "ruthenium", "thallium", "uranium", "iridium", "palladium",
    "cerium", "scandium", "samarium", "gallium", "germanium", "rhenium",
    "tin", "bismuth", "antimony", "beryllium", "strontium",
    "chromium",   # toxic hexavalent form; trivalent is trace mineral but too ambiguous
    "lithium",    # pharmaceutical, not dietary
    "cobalt",     # only relevant as B12 core; the bare element is not dietary
    "sulfur",     # elemental S is not a food compound (sulphur compounds are fine)
    "fluorine", "flourine",   # elemental F is toxic
    "hydrogen",   # H2 gas
    "oxygen",     # O2 gas
    "carbon dioxide",
    "hydrogen cyanide",
}

INDUSTRIAL_CHEMICALS = {
    # polymers & surfactants
    "polyacrylamide", "polyethylene glycol", "polysorbate 20", "polysorbate 80",
    # industrial solvents / reagents
    "tetrahydrofuran", "n,n-dimethylformamide", "acetone", "ether",
    "pentane", "dimethyl fumarate", "diazinon", "acrylamide", "acrylic acid",
    "thiodiacetic acid", "piperazine", "thiourea",
    "2,2,2-trichloroethanol", "2,4-dichlorophenol",
    "sulfuric acid", "potassium permanganate",
    "ammonium sulfate", "ammonium bicarbonate",
    "ethylenediaminetetraacetic acid", "edta",
    "dimethyl disulfide",   # odorant, not dietary
    "n,n-dimethylaniline",
    "diphenylamine",        # fungicide
    "dioctyl phthalate",    # plasticiser
    "3-phenoxybenzoic acid",# pyrethroid metabolite marker
    "1-hydroxypyrene",      # PAH metabolite — pollutant marker
    "anthracene",           # PAH
    "naphthalene",          # PAH
    "potassium oxide",      # not a food compound
    "calcium peroxide",     # industrial bleach
    "sulfuric acid",
    "propylene glycol",     # food additive but primarily industrial solvent
    "triacetin",            # food-grade but marginal
}

# Pharmaceutical-only drugs — confirmed not normally present in food
PHARMACEUTICAL_DRUGS = {
    "verapamil", "warfarin", "isoniazid", "ampicillin", "gabapentin",
    "diazepam", "metoprolol", "celecoxib", "dexamethasone", "loratadine",
    "lincomycin", "tetracycline", "clotrimazole", "oxytetracycline",
    "aminopterin", "furazolidone", "bacitracin", "diazinon",
    "sulfaquinoxaline",     # veterinary antibiotic
    "ethoxyquin",           # synthetic antioxidant (banned in EU for human food)
    "pancreatin",           # digestive enzyme blend — pharmaceutical
}

# False-positive alkaloids and pollutant markers
FALSE_POSITIVES = {
    "ecgonine methyl ester",  # cocaine metabolite — soil contamination artefact
    "nornicotine",            # tobacco alkaloid metabolite — MS cross-reactivity
    "ecgonine",               # cocaine metabolite
    "cotinine",               # nicotine metabolite — smoking marker not food
    "norcocaine",
    "domoic acid",            # marine toxin / HAB marker — not a dietary compound
}

# ── 2. Endogenous metabolite / bio-intermediate flagging ─────────────────────

ENDOGENOUS_KEYWORDS = {
    # neurotransmitters & hormones
    "dopamine", "serotonin", "cortisol", "cortisone", "testosterone",
    "estrogen", "estradiol", "aldosterone", "vasopressin", "bilirubin",
    "adrenaline", "epinephrine", "noradrenaline", "norepinephrine",
    "melatonin", "oxytocin", "insulin", "glucagon",
    "angiotensin", "angiotensin iii",
    # intermediary metabolites
    "uric acid", "creatinine", "pyruvate", "oxaloacetate",
    "malonyl-coa", "methylmalonyl-coa", "succinyl-coa", "coenzyme a",
    "5-hydroxydopamine", "n-acetyldopamine",
    "indoxyl sulfate",          # uremic toxin
    "hypotaurine",
    "3-phospho-d-glycerate", "2-phosphoglycerate",
    "fructose 1-phosphate", "fructose 6-phosphate",
    "mannose 6-phosphate", "sorbitol 6-phosphate",
    "dihydroxyacetone phosphate",
    "phosphoribosyl pyrophosphate", "phosphoribosyl-atp",
    "d-erythrose 4-phosphate",
    "1-deoxy-d-xylulose 5-phosphate",
    "glycerylphosphoinositol",
    "sn-glycerol-3-phosphate",
    "myo-inositol 1-phosphate",
    "phosphatidylinositol-3,4,5-trisphosphate",
    "inositol 1,3,4,5,6-pentakisphosphate",
    "glutaric acid",
    "3-hydroxyglutaric acid",
    "l-saccharopine",
    "alpha-ketoglutarate",
    "shikimate",    # plant intermediate (borderline)
    "calmodulin",   # signalling protein
    # cofactors and nucleotides flagged as bio-intermediates
    "nadp+", "nad+", "fad", "fmn",
    "atp", "adp", "amp", "cyclic-amp", "udp", "ctp", "gtp", "itp",
    "dcmp", "damp", "dgtp", "dttp", "dtmp", "dump",
    "coenzyme a", "cob(i)alamin",
    "adf-ribose", "adp-ribose",
    "triphosphoric acid",
    "cdp-ethanolamine",
    "s-nitrosoglutathione",
    "leukotriene d4", "12(s)-leukotriene b4",
    "prostaglandin f2a", "prostaglandin h2",
    "lipoxin b4", "12(s)-hpete", "5-hete", "15-hete", "15-kete",
    "superoxide",
    "o-quinone",
    # steroid intermediates
    "pregnenolone", "allopregnanolone", "androsterone glucuronide",
    "16alpha-hydroxyestrone", "2-methoxyestradiol", "27-hydroxycholesterol",
    "25-hydroxycholesterol", "18-hydroxycorticosterone",
    "dynorphin a", "dynorphin b",
    "8-hydroxyguanosine", "8-hydroxy-deoxyguanosine",
    "thymidine glycol",
    "erythrose",
    "sepiapterin",
    "dihydropteridine",
    "pterin",
}

# Nucleotide / CoA patterns (regex)
_BIO_INTERMEDIATE_RE = re.compile(
    r"""
    \b(A?[DU]?[TCGA]TP|A?[DU]?[TCGA]DP|A?[DU]?[TCGA]MP|
       [dD]?[NR]?[AGCTUacgtu]TP|[dD]?[NR]?[AGCTUacgtu]DP
      |CoA\b|-CoA\b|acyl-CoA\b
      |N[AH]D\+?P?\+?|FAD|FMN|cAMP|cyclic.AMP)\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

# ── 3. Scientific-name → common-name normalisation map ───────────────────────

SCI_TO_COMMON = {
    "zingiber officinale":      "ginger",
    "cinnamomum zeylanicum":    "cinnamon",
    "cinnamomum zeylaniucm":    "cinnamon",   # typo in source
    "asparagus officinalis":    "asparagus",
    "anetheum graveolens":      "dill",
    "azadirachta indica":       "neem",
    "cocos nucifera l":         "coconut",
    "citrullus vulgaris":       "watermelon",
    "arctostaphylos uva-ursi":  "bearberry",
    "aronia melanocarpa":       "black chokeberry",
    "balanites aegyptiaca":     "desert date",
    "aegle marmelos":           "bael fruit",
    "acorus gramineus":         "shi chang pu",
    "alga gracilaria caudata":  "gracilaria seaweed",
    "amaranthus tricolor":      "amaranth",
    "apios americana":          "groundnut",
    "arctostaphylos uva-ursi":  "bearberry",
    "boesenbergia rotunda rhizomes": "fingerroot",
    "brassica sprout":          "brassica sprout",
    "cajanus":                  "pigeonpea",
    "cichorium intybus":        "chicory",
    "cirsium chanroenicum":     "thistle",
    "cnidium monnier (l.) cuss":"cnidium",
    "fufang danshen dripping pill": "danshen compound",
}

# Typo / capitalisation corrections (normalised → corrected)
NAME_FIXES = {
    "grape fruit":              "grapefruit",
    "vitamins k2":              "vitamin k2",
    "ascorbic acid":            "vitamin c",  # unify with common alias
    "vitamin b":                "vitamin b complex",
    "aqueous licorice extract": "licorice extract",
    "berberine chloride":       "berberine",
    "c-phycocyanin complex":    "c-phycocyanin",
    "c. chanroenicum":          "cirsium chanroenicum",
    "c. zeylaniucm":            "cinnamon",
}

# ── 4. Known duplicates / consolidation map ───────────────────────────────────
# Maps any name (normed) → the canonical normed name to keep

EXPLICIT_MERGE = {
    # ginkgo variants
    "ginkgo":                   "ginkgo biloba",
    # grapefruit
    "grape fruit":              "grapefruit",
    "grapefruit juice":         "grapefruit",
    # vitamin c
    "ascorbic acid":            "vitamin c",
    # berberine
    "berberine chloride":       "berberine",
    # phycocyanin
    "c-phycocyanin complex":    "c-phycocyanin",
    # licorice
    "aqueous licorice extract": "licorice extract",
    # cinnamon
    "cinnamomum":               "cinnamon",
    "cinnamomum zeylanicum":    "cinnamon",
    "cinnamomum zeylaniucm":    "cinnamon",
    # cirsium
    "cirsium":                  "cirsium chanroenicum",
    "c. chanroenicum":          "cirsium chanroenicum",
    # cocos
    "cocos nucifera l":         "coconut",
    # pinene
    "(+)-alpha-pinene":         "alpha-pinene",
    "(-)-alpha-pinene":         "alpha-pinene",
    "pinene":                   "alpha-pinene",
    # fenchone
    "(+)-fenchone":             "fenchone",
    "(-)-fenchone":             "fenchone",
    # menthone
    "(±)-menthone":             "menthone",
    "(-)-menthone":             "menthone",
    # carvone
    "(-)-carvone":              "carvone",
    "(+)-carvone":              "carvone",
    # borneol
    "(-)-borneol":              "borneol",
    "(+)-borneol":              "borneol",
    # salicylate / salicylates
    "salicylate":               "salicylates",
    # gossypol
    "(-)-gossypol":             "gossypol",
    # matairesinol
    "(-)-matairesinol":         "matairesinol",
    # quinic acid
    "(-)-quinic acid":          "quinic acid",
    # vitamin c
    "l-ascorbic acid":          "vitamin c",
}

# ═══════════════════════════════════════════════════════════════════════════════
#  STEREO-STRIP REGEX
# ═══════════════════════════════════════════════════════════════════════════════

_STEREO_PREFIX = re.compile(
    r"""^
    (?:
      \([\+\-±RS,]\)[-\s]*     |  # (+)-, (-)-, (±)-, (R)-, (S)-
      \([+-]?\d*[RS,]+\)[-\s]* |  # (2R)-, (1S,2R)- etc.
      (?:cis|trans|endo|exo|syn|anti)- |
      (?:t|c)-                 |
      (?:(?:L|D)-(?=[A-Z]))    |  # L- D- before uppercase (amino acids)
      [\(]?(?:alpha|beta|gamma|delta|epsilon|omega)[\)]?-
    )+
    """,
    re.VERBOSE | re.IGNORECASE,
)

_STEREO_SUFFIX = re.compile(
    r"""(
      [,\s]+(?:d|l|dl)\s*$     |  # trailing D, L, DL
      \s*\([RS,\+\-±]+\)\s*$   |  # trailing (R), (S) etc.
      \s+\d+[RS]?\s*$          |  # trailing stereo number
      \s+(?:alpha|beta|gamma)\s*$
    )""",
    re.VERBOSE | re.IGNORECASE,
)


def _strip_stereo(name: str) -> str:
    """Remove stereochemistry prefixes/suffixes to get the parent compound name."""
    s = name.strip()
    s = _STEREO_PREFIX.sub("", s).strip()
    m = _STEREO_SUFFIX.search(s)
    if m:
        s = s[:m.start()].strip()
    return s


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _norm(name: str) -> str:
    """Lowercase, strip, collapse whitespace."""
    return re.sub(r"\s+", " ", str(name).lower().strip())


def _classify_type(name: str) -> str:
    """Return a semantic type tag for the entry."""
    n = _norm(name)
    # CoA / nucleotide pattern
    if _BIO_INTERMEDIATE_RE.search(name):
        return "Endogenous Metabolite"
    if n in ENDOGENOUS_KEYWORDS:
        return "Endogenous Metabolite"
    # Plant extracts / whole foods — keyword heuristics
    for kw in ("extract", "juice", "oil", "sprout", "seed", "root",
                "leaf", "bark", "fruit", "berry", "algae", "alga",
                "mushroom", "fungus", "herb", "spice", "tea", "milk"):
        if kw in n:
            return "Food / Whole-Food Preparation"
    # Glycosides, flavonoids, polyphenols
    for kw in ("glycoside", "flavonoid", "polyphenol", "anthocyan",
                "catechin", "quercetin", "kaempferol", "apigenin",
                "curcumin", "resveratrol", "ginsenoside"):
        if kw in n:
            return "Food Bioactive"
    # Fatty acids
    if re.search(r"\b(?:acid|ate)\b", n) and re.search(
        r"\b(?:fatty|oleic|linoleic|palmitic|stearic|eicosa|docosa|omega|butyric"
        r"|caprylic|capric|lauric|myristic|pentadec|heptadec|erucic|gadoleic)\b",
        n,
    ):
        return "Dietary Lipid"
    # Vitamins / minerals
    for kw in ("vitamin", "thiamine", "riboflavin", "niacin", "folate",
                "cobalamin", "tocopherol", "retinol", "calciferol",
                "calcium", "magnesium", "zinc", "iron", "potassium", "sodium"):
        if kw in n:
            return "Dietary Nutrient"
    # Amino acids
    if re.search(r"\b(?:L-|D-)?(?:alanine|arginine|asparagine|aspartate"
                 r"|cysteine|glutamine|glutamate|glycine|histidine"
                 r"|isoleucine|leucine|lysine|methionine|phenylalanine"
                 r"|proline|serine|threonine|tryptophan|tyrosine|valine"
                 r"|ornithine|citrulline|taurine)\b", n):
        return "Dietary Amino Acid"
    return "Food Bioactive"


def _filter_reason(n: str) -> str | None:
    """Return removal reason if name should be excluded, else None."""
    if n in NOBLE_GASES:
        return "noble gas"
    if n in IRRELEVANT_ELEMENTS:
        return "non-food element or gas"
    if n in INDUSTRIAL_CHEMICALS:
        return "industrial chemical / solvent"
    if n in PHARMACEUTICAL_DRUGS:
        return "pharmaceutical drug (not a food compound)"
    if n in FALSE_POSITIVES:
        return "false-positive (drug metabolite / contaminant marker)"
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def clean_food_data(raw_list: list[tuple[int, str]]) -> list[dict]:
    """
    Clean and classify a raw food master list.

    Parameters
    ----------
    raw_list : list of (food_id: int, food_name: str)

    Returns
    -------
    list of dicts, one per canonical food entry, with keys:
        food_id        : int   — canonical ID (lowest original ID in merged group)
        food_name      : str   — canonical display name
        original_ids   : list  — all original IDs merged into this entry
        original_names : list  — all original names merged into this entry
        type           : str   — semantic type tag
        removed        : bool
        removal_reason : str | None

    Notes
    -----
    RDKit (if installed) is used to canonicalise SMILES in the companion
    foodb_food_smiles.csv sidecar.  PubChemPy (if installed) is used to
    resolve ambiguous scientific names via the PubChem REST API (one call per
    unique name, results cached in memory for the session).
    """
    # ── pass 1: normalise names ────────────────────────────────────────────────
    entries = []  # (orig_id, orig_name, norm_name, canonical_name)
    for fid, fname in raw_list:
        n = _norm(fname)
        # scientific name → common name
        if n in SCI_TO_COMMON:
            canonical = SCI_TO_COMMON[n]
        # typo / capitalisation fix
        elif n in NAME_FIXES:
            canonical = NAME_FIXES[n]
        else:
            canonical = n
        entries.append((fid, fname, n, canonical))

    # optional: PubChem resolution for entries still holding a binomial name
    if PUBCHEM_AVAILABLE:
        _pubchem_resolve(entries)

    # ── pass 2: explicit merge map ─────────────────────────────────────────────
    # Apply EXPLICIT_MERGE on canonical names
    def apply_merge(c):
        return EXPLICIT_MERGE.get(c, c)

    entries = [(fid, fn, n, apply_merge(c)) for fid, fn, n, c in entries]

    # ── pass 3: stereoisomer deduplication ────────────────────────────────────
    # Group by stripped-stereo canonical name
    # Key = (stereo-stripped canonical name)
    stereo_groups: dict[str, list] = defaultdict(list)
    for fid, fn, n, c in entries:
        key = _norm(_strip_stereo(c))
        stereo_groups[key].append((fid, fn, n, c))

    # ── pass 4: build final output ────────────────────────────────────────────
    output = []
    for stripped_key, members in stereo_groups.items():
        # All members that are not filtered
        surviving = []
        removed_members = []
        for fid, fn, n, c in members:
            reason = _filter_reason(c) or _filter_reason(n)
            if reason:
                removed_members.append((fid, fn, reason))
            else:
                surviving.append((fid, fn, n, c))

        if not surviving:
            # Entire group is filtered — emit one removed record per original entry
            for fid, fn, r in removed_members:
                output.append({
                    "food_id":       fid,
                    "food_name":     fn,
                    "original_ids":  [fid],
                    "original_names":[fn],
                    "type":          "Removed",
                    "removed":       True,
                    "removal_reason": r,
                })
            continue

        # Canonical representative: prefer entry whose canonical form equals
        # stripped_key, otherwise alphabetically first
        surviving.sort(key=lambda x: x[0])  # sort by id to pick lowest
        canonical_name = surviving[0][3].title() if stripped_key else surviving[0][1]

        # Prefer an explicit canonical name if one of the merged names is
        # the un-decorated parent compound
        for _, _, _, c in surviving:
            if _norm(_strip_stereo(c)) == stripped_key and not re.search(
                r"[\(\)\+\-±]", c
            ):
                canonical_name = c.title()
                break

        all_ids   = sorted({e[0] for e in surviving} | {e[0] for e in removed_members})
        canonical_id = surviving[0][0]

        typ = _classify_type(canonical_name)

        output.append({
            "food_id":        canonical_id,
            "food_name":      canonical_name,
            "original_ids":   all_ids,
            "original_names": [e[1] for e in surviving] + [e[1] for e in removed_members],
            "type":           typ,
            "removed":        False,
            "removal_reason": None,
        })

    return output


# ═══════════════════════════════════════════════════════════════════════════════
#  OPTIONAL PUBCHEM RESOLVER
# ═══════════════════════════════════════════════════════════════════════════════

_BINOMIAL_RE = re.compile(r"^[A-Z][a-z]+ [a-z]+$")   # "Genus species"
_pubchem_cache: dict[str, str] = {}


def _pubchem_resolve(entries):
    """In-place: replace canonical name with PubChem preferred name for
    entries that look like a binomial scientific name and are not already in
    SCI_TO_COMMON."""
    import time
    for i, (fid, fn, n, c) in enumerate(entries):
        display = c.title()
        if not _BINOMIAL_RE.match(display):
            continue
        if display in _pubchem_cache:
            entries[i] = (fid, fn, n, _pubchem_cache[display])
            continue
        try:
            results = pcp.get_compounds(display, "name", as_dataframe=False)
            if results:
                preferred = results[0].iupac_name or results[0].synonyms[0] if results[0].synonyms else display
                preferred = _norm(preferred)
            else:
                preferred = c
        except Exception:
            preferred = c
        _pubchem_cache[display] = preferred
        entries[i] = (fid, fn, n, preferred)
        time.sleep(0.22)   # stay within PubChem rate limit (5 req/s)


# ═══════════════════════════════════════════════════════════════════════════════
#  RDKIT SMILES CANONICALISATION (companion sidecar)
# ═══════════════════════════════════════════════════════════════════════════════

def _canonicalise_smiles_sidecar(smiles_path: str, id_remap: dict[int, int]) -> None:
    """
    Rewrite foodb_food_smiles.csv (or any food SMILES sidecar) by:
      - remapping food_id via id_remap (old → canonical)
      - canonicalising SMILES via RDKit (if available)
    """
    if not os.path.exists(smiles_path) or os.path.getsize(smiles_path) == 0:
        return
    import pandas as pd
    try:
        df = pd.read_csv(smiles_path)
    except Exception:
        return   # empty or malformed file — skip silently
    if "food_id" not in df.columns:
        return
    df["food_id"] = df["food_id"].map(lambda x: id_remap.get(int(x), int(x)))
    if RDKIT_AVAILABLE and "smiles" in df.columns:
        def canon(s):
            if not isinstance(s, str):
                return s
            mol = Chem.MolFromSmiles(s)
            return Chem.MolToSmiles(mol) if mol else s
        df["smiles"] = df["smiles"].apply(canon)
    # Drop duplicates (two stereoisomers now share one id)
    df.drop_duplicates(subset=["food_id", "smiles"] if "smiles" in df.columns
                       else ["food_id"], keep="first", inplace=True)
    df.to_csv(smiles_path, index=False)
    print(f"  Updated SMILES sidecar: {smiles_path} ({len(df)} rows)")


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN — runs when executed directly
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    GENERATED = r"d:\23AIBox-DFinder\generated"
    MASTER_IN  = f"{GENERATED}/unified_food_master.txt"
    MASTER_OUT = f"{GENERATED}/unified_food_master_clean.txt"
    REMAP_OUT  = f"{GENERATED}/food_id_remap.csv"
    REPORT_OUT = f"{GENERATED}/food_cleaning_report.txt"
    INTER_IN   = f"{GENERATED}/unified_train_interactions.txt"
    INTER_OUT  = f"{GENERATED}/unified_train_interactions_clean.txt"

    # ── load raw master ────────────────────────────────────────────────────────
    raw_list = []
    with open(MASTER_IN, encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t", 1)
            if len(parts) == 2:
                raw_list.append((int(parts[0]), parts[1]))

    print(f"Loaded {len(raw_list)} entries from food master.")

    # ── run cleaning ───────────────────────────────────────────────────────────
    results = clean_food_data(raw_list)

    # ── assign new sequential IDs (skipping removed entries) ─────────────────
    kept     = [r for r in results if not r["removed"]]
    removed  = [r for r in results if r["removed"]]

    # Sort kept by the first original id to preserve approximate ordering
    kept.sort(key=lambda r: r["food_id"])
    for new_id, r in enumerate(kept):
        r["new_id"] = new_id

    # Build old_id → new_id remap
    id_remap: dict[int, int] = {}
    for r in kept:
        for old_id in r["original_ids"]:
            id_remap[old_id] = r["new_id"]
    # Removed entries' old IDs map to None (will drop pairs)
    for r in removed:
        for old_id in r["original_ids"]:
            id_remap.setdefault(old_id, -1)  # -1 = removed

    # ── write cleaned master ───────────────────────────────────────────────────
    with open(MASTER_OUT, "w", encoding="utf-8") as fh:
        for r in kept:
            fh.write(f"{r['new_id']}\t{r['food_name']}\t{r['type']}\n")

    print(f"Clean food master: {len(kept)} entries → {MASTER_OUT}")

    # ── write remap CSV ────────────────────────────────────────────────────────
    with open(REMAP_OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["old_id", "old_name", "new_id", "canonical_name", "type", "removal_reason"])
        for r in kept:
            for oid, oname in zip(r["original_ids"], r["original_names"]):
                w.writerow([oid, oname, r["new_id"], r["food_name"],
                            r["type"], ""])
        for r in removed:
            for oid, oname in zip(r["original_ids"], r["original_names"]):
                w.writerow([oid, oname, "REMOVED", r["food_name"],
                            r["type"], r["removal_reason"]])

    print(f"Remap CSV written: {REMAP_OUT}")

    # ── update interactions ────────────────────────────────────────────────────
    removed_ids = {old_id for r in removed for old_id in r["original_ids"]}
    total_pairs_before = 0
    total_pairs_after  = 0
    dropped_pairs      = 0

    with open(INTER_IN,  encoding="utf-8") as fi, \
         open(INTER_OUT, "w", encoding="utf-8") as fo:
        for line in fi:
            tokens = line.strip().split()
            if not tokens:
                continue
            drug_id = tokens[0]
            old_food_ids = list(map(int, tokens[1:]))
            total_pairs_before += len(old_food_ids)

            new_food_ids = set()
            for fid in old_food_ids:
                new_fid = id_remap.get(fid, -1)
                if new_fid >= 0:
                    new_food_ids.add(new_fid)
                else:
                    dropped_pairs += 1

            if new_food_ids:
                fo.write(f"{drug_id} " + " ".join(str(f) for f in sorted(new_food_ids)) + "\n")
                total_pairs_after += len(new_food_ids)

    print(f"Interactions: {total_pairs_before} → {total_pairs_after} pairs "
          f"({dropped_pairs} dropped for removed food nodes)")

    # ── update SMILES sidecars ─────────────────────────────────────────────────
    for sidecar in [
        f"{GENERATED}/foodb_food_smiles.csv",
        f"{GENERATED}/pomelo_food_smiles.csv",
    ]:
        _canonicalise_smiles_sidecar(sidecar, id_remap)

    # ── write report ───────────────────────────────────────────────────────────
    by_type: dict[str, list] = defaultdict(list)
    for r in kept:
        by_type[r["type"]].append(r["food_name"])

    removed_by_reason: dict[str, list] = defaultdict(list)
    for r in removed:
        removed_by_reason[r["removal_reason"]].append(r["food_name"])

    lines = [
        "=== Food Master Cleaning Report ===\n\n",
        f"Input entries:          {len(raw_list)}\n",
        f"Canonical entries kept: {len(kept)}\n",
        f"Entries removed:        {len(removed)}\n",
        f"  (merges / dedup reduced entries by {len(raw_list) - len(kept) - len(removed)} via consolidation)\n",
        f"\n--- Kept by Type ---\n",
    ]
    for typ, names in sorted(by_type.items()):
        lines.append(f"  {typ}: {len(names)}\n")

    lines.append(f"\n--- Removed by Reason ---\n")
    for reason, names in sorted(removed_by_reason.items()):
        lines.append(f"\n  [{reason}] ({len(names)} entries)\n")
        for n in sorted(names):
            lines.append(f"    - {n}\n")

    lines.append(f"\n--- Stereoisomers / Duplicates Merged ---\n")
    for r in kept:
        if len(r["original_ids"]) > 1:
            lines.append(
                f"  {r['food_name']}  ←  "
                + ", ".join(r["original_names"])
                + f"  (IDs {r['original_ids']} → {r['new_id']})\n"
            )

    lines.append(f"\n--- Endogenous Metabolites (kept but flagged) ---\n")
    for r in kept:
        if r["type"] == "Endogenous Metabolite":
            lines.append(f"  [{r['new_id']}] {r['food_name']}\n")

    lines.append(f"\n--- False Positives Removed ---\n")
    for r in removed:
        if "false-positive" in (r["removal_reason"] or ""):
            lines.append(f"  [{r['food_id']}] {r['food_name']}  — {r['removal_reason']}\n")

    lines.append(f"\n--- Interaction Impact ---\n")
    lines.append(f"  Pairs before:  {total_pairs_before}\n")
    lines.append(f"  Pairs after:   {total_pairs_after}\n")
    lines.append(f"  Pairs dropped: {dropped_pairs}\n")

    with open(REPORT_OUT, "w", encoding="utf-8") as fh:
        fh.writelines(lines)

    print(f"\nReport: {REPORT_OUT}")
    print("Done.")
