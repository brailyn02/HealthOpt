"""
Comprehensive food master cleaning (v2):
  - Removes ALL pharmaceutical drug names (huge block from Pomelo DDI data)
  - Removes remaining vague labels (intervention, they, treatments, etc.)
  - Removes remaining abbreviations (Bae, Ph.Aq, Mmc, etc.)
  - Removes research chemicals (Paraquat, Oxythiamine, etc.)
  - Merges aliases (Resv->Resveratrol, Res->Resveratrol, etc.)
  - Oils are KEPT (user confirmed ok)
  - Rebuilds food master and interactions with clean contiguous IDs
"""
from pathlib import Path
import re

root = Path(r'd:/23AIBox-DFinder/generated')

# Load
foods = {}
with (root/'unified_food_master.txt').open(encoding='utf-8') as f:
    for line in f:
        p = line.strip().split('\t', 1)
        if len(p) == 2:
            foods[int(p[0])] = p[1]

drug_to_foods = {}
with (root/'unified_train_interactions.txt').open(encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split()
        if parts:
            drug_to_foods[int(parts[0])] = set(int(x) for x in parts[1:])

# 1. Vague / non-food labels
REMOVE_EXACT = {
    'anticoagulant','anticoagulants','antiplatelet','antidepressants',
    'anti-malarial','antibiotic','antibiotics','anticholinestrase',
    'aminoglycosides','benzodiazepines','fluoroquinolones','carbapenems',
    'activators','both drugs','na',
    'herbs','supplements','supplementation','supplemented','treatment',
    'treatments','treated groups','drug','drugs','medication','compound',
    'compounds','the oil','extract','fractions','all fractions','plant crude extract',
    'all plant extracts','flavonoids','phenolic acids','flavonoid',
    'polyphenol','saponin','lipids','emulsifiers','juices','essential',
    'vegetable','vegetable food','vegetable infant weaning food',
    'infant weaning foods','grain legumes','cooking oils',
    'intervention','they','garlic preparations',
    'ggt mixture','ggx mixture','polyherbal premix',
    'essential oil','n-3 pufa',
    'ph.aq','ph.chf','ph.cr','ph.etac','ph.hex','ph.sp',
}

REMOVE_CONTAINS = [
    'crude extract','methanol extract','methanolic extract',
    'hydroalcoholic','hydromethanolic','ethanolic extract',
    ' fractions','methanol extracts',
]

# 2. Pharmaceutical drugs to remove
PHARMA_DRUGS = {
    'calcitonin','paraquat','n-acetylcysteine','oxythiamine',
    'pcpa','phenylalanine methyl ester hydrochloride',
    'da-9801','ws 1442',
    # drugs that appear in pomelo food list directly
    'warfarin','aspirin','metformin','morphine','acetaminophen',
    'nicardipine','dexamethasone','cyclophosphamide','paclitaxel',
    'tetracycline','isoniazid','doxorubicin','piracetam',
    'ibuprofen, (+-)-','ibuprofen',
    'entrectinib','clorazepate','dihydrocodeine','vardenafil','venlafaxine',
    'voriconazole','duloxetine','temazepam','furosemide','tetrahydrocannabinol',
    'milnacipran','bromocriptine','colchicine','amobarbital','floctafenine',
    'amprenavir','bosutinib','irbesartan','theophylline','cobimetinib',
    'tamsulosin','erythrityl tetranitrate','diphenhydramine','desipramine',
    'procarbazine','avapritinib','metronidazole','hydroxyzine','regorafenib',
    'normethadone','trandolapril','disopyramide','nicotinic acid',
    'allopurinol','amantadine','atazanavir','efavirenz',
    'flavin mononucleotide','ketazolam','cyproheptadine','mecamylamine',
    'cenobamate','aripiprazole','modafinil','clobazam','dutasteride',
    'tiaprofenic acid','vinorelbine','dextromethorphan','brigatinib',
    'diphenoxylate','atorvastatin','pazopanib','meloxicam','erlotinib',
    'heroin','larotrectinib','melatonin','trimethadione','vandetanib',
    'terfenadine','cannabidiol','codeine','lenvatinib','estrone',
    'elbasvir','oxprenolol','suvorexant','olanzapine','probenecid',
    'ketoprofen','spirapril','diltiazem','alprazolam','paliperidone',
    'dexmethylphenidate','midostaurin','cabozantinib','rupatadine',
    'alendronic acid','clemastine','ziprasidone','indomethacin',
    'isocarboxazid','mefenamic acid','sumatriptan','ranolazine',
    'nelfinavir','clonidine','repaglinide','dabrafenib','buprenorphine',
    'encorafenib','allopregnanolone','azathioprine','oxycodone','bosentan',
    'dicoumarol','sparfloxacin','pindolol','indinavir','haloperidol',
    'digitoxin','quinagolide','methylergometrine','cabazitaxel','darunavir',
    'fluoxetine','prilosec','vindesine','cyclizine','dasatinib','metyrapone',
    'dexchlorpheniramine maleate','trimethylpsoralen','trabectedin',
    'phenprocoumon','lopinavir','triethylenetetramine','pregabalin',
    'hexachlorocyclohexane','anagrelide','tiagabine','meclofenamic acid',
    'vincristine','ferrous gluconate','tiludronic acid','clopidogrel',
    'flurbiprofen','phenylbutazone','gabapentin','desmethylsertraline',
    'dronedarone','difenoxin','vemurafenib','fluindione','brompheniramine',
    'dihydroergotamine','miconazole','nafarelin','zanubrutinib','fosamprenavir',
    'hydrochlorothiazide','ethinylestradiol','methsuximide','gliclazide',
    '4-methylpyrazole','idelalisib','cabergoline','dabigatran etexilate',
    'picosulfuric acid','clonazepam','glibenclamide','butabarbital',
    'metamizole','guanfacine','saxagliptin','prochlorperazine','lasmiditan',
    'acenocoumarol','etonogestrel','pargyline','brivaracetam','lapatinib',
    'diazepam','safinamide','bromazepam','ethosuximide','meperidine',
    'chlorothiazide','doxazosin','ziconotide','diflunisal','imipramine',
    'tasimelteon','oxilofrine','thioridazine','azatadine','fluconazole',
    'flecainide','estradiol','praziquantel','teniposide','dofetilide',
    'tyramine','isavuconazole','estramustine','chlorcyclizine','perindopril',
    'isavuconazonium','ticlopidine','biperiden','loxapine','fexofenadine',
    'cisapride','indinavir sulfate','8-methoxypsoralen','dipyridamole',
    'remifentanil','prazepam','methoxyflurane','moexipril','clozapine',
    'erythromycin','phenindamine','edoxaban','methohexital','zafirlukast',
    'butalbital','meprobamate','hydrocodone','diclofenac','sildenafil',
    'apixaban','valdecoxib','estradiol cypionate','methylphenidate',
    'donepezil','etravirine','palbociclib','nitrazepam',
    'flavin adenine dinucleotide','pimozide','clarithromycin',
    'prednisolone acetate','lomitapide','nilutamide','progesterone',
    'deutetrabenazine','calcium carbonate','acetohexamide','crizotinib',
    'phenindione','lercanidipine hydrochloride','zonisamide','carbinoxamine',
    'dichloralphenazone','gilteritinib','gemfibrozil','pentyl nitrite',
    'amiloride','linagliptin','fosphenytoin','hydromorphone','pipotiazine',
    'losartan','zolpidem','ticagrelor','ergotamine','elexacaftor',
    'piroxicam','nilotinib','prednisone','levonorgestrel','spironolactone',
    'procainamide','topiramate','ertugliflozin','captopril','lorlatinib',
    'triflusal','molindone','ciprofloxacin','zopiclone','glutethimide',
    'sodium fluoride','triamterene','linezolid','canagliflozin','abacavir',
    'lithium carbonate','chlophedianol','celecoxib','betrixaban',
    'itraconazole','salsalate','cyclobenzaprine','orphenadrine',
    'felodipine','remimazolam','potassium bicarbonate','cetirizine',
    'brimonidine','verapamil','nifedipine','nisoldipine','aminophylline',
    'nateglinide','asunaprevir','vortioxetine','zinc gluconate',
    'nitroglycerin','mifepristone','desvenlafaxine','sufentanil',
    'lovastatin','bepridil','levorphanol','dimenhydrinate','tofacitinib',
    'gefitinib','esketamine','olaparib','oxybutynin','netupitant',
    'insulin pork','copanlisib','rucaparib','ethylenediaminetetraacetic acid',
    'dextroamphetamine','lorazepam','nefazodone','doxylamine','oxazepam',
    'flunitrazepam','daclatasvir','thiotepa','quazepam','griseofulvin',
    'ritonavir','pentazocine','sodium oxybate','saquinavir','rasagiline',
    'eplerenone','bivalirudin','cortisol','prasugrel','quetiapine',
    'pantoprazole','methadone','pretomanid','ribociclib','fluphenazine',
    'gestodene','estazolam','pexidartinib','dexbrompheniramine','etoposide',
    'secnidazole','polythiazide','pyrilamine','nabumetone','ceritinib',
    'nebivolol','pramlintide','fludrocortisone','pimavanserin','desitin',
    'eluxadoline','fentanyl','didanosine','propafenone','perphenazine',
    'rivaroxaban','tolazamide','chlorpropamide','ibrutinib','tolvaptan',
    'secobarbital','demeclocycline','methyldopa','busulfan','thalidomide',
    'eltrombopag','dicyclomine','flibanserin','desogestrel',
    'cyproterone acetate','amlodipine','lofexidine','glipizide',
    'butorphanol','cefotetan','ruxolitinib','levocetirizine','dienogest',
    'tadalafil','tetrabenazine','baclofen','abemaciclib','metyrosine',
    'eszopiclone','simvastatin','methotrexate','lithium','nortriptyline',
    'docetaxel','promethazine','ketamine','citalopram','disulfiram',
    'sertraline','metaxalone','trazodone','ponatinib','dapagliflozin',
    'methylprednisolone','chloroquine','nalbuphine','amitriptyline',
    'felbamate','chloral hydrate','buspirone','trimipramine','phenobarbital',
    'ivabradine','ifosfamide','vilazodone','practolol','armodafinil',
    'terramycin','clidinium','methocarbamol','magaldrate','argatroban',
    'chlorzoxazone','aliskiren','clomipramine','tizanidine','voxelotor',
    'imatinib','vinblastine','erdafitinib','nevirapine','raloxifene',
    'sonidegib','lumateperone','trifluoperazine','enasidenib',
    'atorvastatin calcium','oxymorphone','mefloquine','5-fluorouracil',
    'midazolam','estradiol acetate','fosaprepitant','amoxapine','quinapril',
    'quinidine','fedratinib','bisacodyl','metoprolol','cimetidine',
    'bortezomib','propranolol','primidone','propoxyphene','tolbutamide',
    'risperidone','enalapril','azelastine','ribavirin','ramelteon',
    'estradiol valerate','zaleplon','nabilone','nimodipine','meclizine',
    'nitrendipine','amiodarone','prazosin','carbamazepine','reboxetine',
    'tolmetin','nadolol','acetohydroxamic acid','carisoprodol',
    'ivosidenib','bupropion','cangrelor','acalabrutinib','stavudine',
    'paroxetine','phenelzine','levomilnacipran','sorafenib',
    'metoclopramide','azelaic acid','indapamide','digoxin','reserpine',
    'valproic acid','tramadol','moclobemide','alectinib','lithium citrate',
    'periciazine','mirtazapine','flurazepam','liotrix','prednisolone',
    'fenoprofen','venetoclax','triazolam','antipyrine','chlorpromazine',
    'trimethobenzamide','selegiline','apomorphine','cilostazol',
    'oxcarbazepine','lisinopril','etodolac','deflazacort','thyroxine',
    'tinidazole','pemigatinib','ethylene glycol','bilastine','phenytoin',
    'dihydralazine','artemether',
    'heparin pentasaccharide','zinc acetate','zinc protoporphyrin-ix',
    'zinc sulfate','zinc gluconate',
    'cid 25200315','cid 118984461',
}

# 3. Alias map: food abbreviation (lower) -> canonical food name (lower)
#    None means remove entirely
FOOD_ALIASES = {
    'resv': 'resveratrol',
    'res': 'resveratrol',
    '3,4,5-trihydroxystilbene': 'resveratrol',
    "3,4',5-trihydroxystilbene": 'resveratrol',
    'isorhapontigenin': 'resveratrol',
    'egb761': 'ginkgo biloba extract',
    'extract of ginkgo biloba': 'ginkgo biloba extract',
    'g. biloba extract': 'ginkgo biloba extract',
    'ginkgo biloba leaf extract': 'ginkgo biloba extract',
    'ginkgo biloba extracts': 'ginkgo biloba extract',
    'ginko': 'ginkgo biloba',
    'g. biloba': 'ginkgo biloba',
    'silymarine': 'silymarin',
    'silybum marianum': 'silymarin',
    'quercitin': 'quercetin',
    'g. glabra': 'glycyrrhiza',
    'g. uralensis': 'glycyrrhiza',
    'glycyrrhiza glabra fabaceae': 'glycyrrhiza',
    'licorice root': 'licorice',
    'licorice extract': 'licorice',
    'aqueous licorice extract': 'licorice',
    'liquorice': 'licorice',
    'glycyrrhizin': 'glycyrrhizic acid',
    'glycerrhitinic acid': 'glycyrrhetinic acid',
    'grape fruit': 'grapefruit',
    'nigella': 'nigella sativa',
    'n. sativa oil': 'nigella sativa oil',
    'blackseed': 'nigella sativa',
    'black seed': 'nigella sativa',
    'panax': 'panax ginseng',
    'panax ginseng c.a. meyer': 'panax ginseng',
    'american ginseng': 'panax quinquefolius',
    'korean red ginseng': 'korean red ginseng total extract',
    'h. perforatum': 'hypericum perforatum extract',
    'hypericum extract formulation': 'hypericum perforatum extract',
    'hypericum perforatum': 'hypericum perforatum extract',
    "st john's wort": "st. john's wort",
    'h. sabdariffa': 'hibiscus sabdariffa',
    'roselle': 'hibiscus sabdariffa',
    'r. officinalis': 'rosemary',
    'rosmarinus officinalis l.': 'rosemary',
    'rosmarinus officinalis': 'rosemary',
    'rosemary tea': 'rosemary',
    'mentha spicata': 'mentha',
    'm. spicata': 'mentha',
    'zingiber': 'ginger',
    'zingiber officinale': 'ginger',
    'ginger rhizome': 'ginger',
    'curcuma longa': 'turmeric',
    'curcuma longa linn': 'turmeric',
    'haridra': 'turmeric',
    'zingiberaceae': 'ginger',
    'curcuminoids': 'curcumin',
    'curcuminoid': 'curcumin',
    'curcumin i': 'curcumin',
    'turmeric rhizome powder suspension': 'turmeric',
    'morinda citrifolia linn': 'morinda citrifolia',
    'morinda citrifolia linn.': 'morinda citrifolia',
    'noni': 'morinda citrifolia',
    'm. charantia extract': 'momordica charantia',
    'bitter melon leaf extract': 'momordica charantia',
    'bitter gourd': 'momordica charantia',
    'faba bean': 'fava beans',
    'vicia faba': 'fava beans',
    'broad bean': 'fava beans',
    'foeniculum vulgare': 'fennel',
    'fennel oil': 'foeniculum vulgare (fennel) essential oil',
    'oil of foeniculum vulgare mill': 'foeniculum vulgare (fennel) essential oil',
    'chamomile essential oi': 'chamomile',
    'g.mangostana': 'garcinia mangostana',
    'p. granatum': 'punica granatum',
    'a. officinalis': 'asparagus officinalis',
    'a. tricolor': 'amaranthus tricolor',
    'a. indica': 'azadirachta indica',
    'a.atroviolaceum extract': 'allium atroviolaceum',
    'p. oleracea': 'portulaca oleracea',
    'portulaca oleracea l.': 'portulaca oleracea',
    'uvae ursi': 'arctostaphylos uva-ursi',
    'bearberry leaf': 'arctostaphylos uva-ursi',
    'cranberries': 'cranberry',
    'soyabeans': 'soybean',
    'panax notoginseng ledeb': 'panax notoginseng',
    't. belerica': 'terminalia belerica',
    't. foenum-graecum': 'trigonella foenum-graecum',
    't. foenum-graecum aqueous extract': 'trigonella foenum-graecum',
    'vit.b6': 'vitamin b6',
    'vit. b6': 'vitamin b6',
    'vit.c': 'vitamin c',
    'ascorbic acid': 'vitamin c',
    'vitamin k1': 'vitamin k',
    'vitamin k3': 'vitamin k',
    'vitamins k2': 'vitamin k',
    'p. guineense': 'piper guineense',
    'piper longum l.': 'piper longum',
    'c-pc': 'spirulina platensis',
    'polysaccharide of spirulina platensis': 'spirulina platensis',
    'garlic bulb': 'garlic',
    'rutabaga sprout': 'rutabaga',
    'rutabaga sprouts': 'rutabaga',
    'brassica napus l. var. napobrassica': 'rutabaga',
    'rossa': 'rosa damascena',
    'san chi': 'panax notoginseng',
    'dengzhan shengmai formula': 'dengzhan shengmai',
    'naoxintong formula': 'naoxintong',
    'fufang danshen dripping pill': 'danshen',
    'shexiang baoxin formula': 'shexiang baoxin',
    'coq10': 'coenzyme q10',
    'soy lecithin': 'lecithin',
    'pistacia lentiscus oil': 'pistacia lentiscus',
    'mandarin juice': 'mandarin',
    'pomelo extract': 'pomelo',
    'sweetie juice': 'pomelo',
    'cnidium monnier (l.) cuss': 'cnidium',
    'fructus cnidii': 'cnidium',
    'barberry extract': 'berberis vulgaris',
    'berberine chloride': 'berberine',
    'barberry ethanolic extract': 'berberis vulgaris',
    'notoginsenoside': 'panax notoginseng saponins',
    'ginsenoside rg2': 'ginsenosides',
    'protopanaxadiol (pd) ginsenosides': 'ginsenosides',
    'protopanaxatriol (pt) ginsenosides': 'ginsenosides',
    # explicit remove (None)
    'lml': None, 'mmc': None, 'e-cs': None, 'roxb.': None, 'hre-1': None,
    'vbfw': None, 'vlp': None, 'dfl': None, 'fpo': None, 'feo': None,
    'sbt': None, 'sce': None, 'scg': None, 'smi': None, 'sipe': None,
    'swh': None, 'pso': None, 'psp': None, 'pop': None, 'pno': None,
    'plo': None, 'plme': None, 'rhpo': None, 'rhvo': None, 'rgap': None,
    'qps': None, 'ops': None, 'oise': None, 'nif\u2081': None, 'nura': None,
    'nisha': None, 'mpme': None, 'mps': None, 'lgc': None,
    'haela': None, 'haepd': None, 'gkb': None, 'hecl': None,
    'bwpe': None, 'bmle': None, 'beo': None, 'bae': None, 'appd': None,
    'amfe': None, 'csp': None, 'cle': None,
    'zxc': None, 'enna complex': None, 'sama': None,
    'nisha amalaki': None,
    # vague research codes
    'same': None, 'lisosan g complex': None, 'lisosan g': None,
    'ggt mixture': None,
}

REAL_FOODS = {
    'ale','beer','cola','kiwi','lime','oat','oats','sage','wine','fig',
    'rye','tea','rum','gin','oil','fat','cod','egg','ham','pea','yam',
    'dill','corn','milk','rice','salt','rubi','vco','wpi','n-3 pufa',
    's.limbata',
}

def is_abbreviation(name):
    n = name.strip()
    nl = n.lower()
    if nl in REAL_FOODS:
        return False
    if len(n) <= 2:
        return True
    if re.fullmatch(r'[A-Z]{2,6}', n):
        return True
    if re.fullmatch(r'[A-Z][a-z]{0,1}\.[A-Za-z]+', n):
        return True
    # only flag 3-4 char TitleCase if not a known food word
    if re.fullmatch(r'[A-Z][a-z]{1,3}', n) and nl not in REAL_FOODS:
        return True
    if re.fullmatch(r'[A-Z]{1,3}[a-z]?\d+', n):
        return True
    if re.match(r'[A-Z][A-Za-z0-9\-]*\d', n) and len(n) <= 8:
        return True
    return False

# Build name_lower -> first food_id map
name_lower2id = {}
for fid, name in foods.items():
    nl = name.lower().strip()
    alias_target = FOOD_ALIASES.get(nl)
    if alias_target is None and nl in FOOD_ALIASES:
        continue
    canonical_lower = alias_target if alias_target else nl
    if canonical_lower not in name_lower2id:
        name_lower2id[canonical_lower] = fid

remove_log = []
keep_ids = set()
old2canonical = {}
canonical_id2name = {}

for fid, name in foods.items():
    nl = name.lower().strip()

    # Explicit alias None -> remove
    if nl in FOOD_ALIASES and FOOD_ALIASES[nl] is None:
        old2canonical[fid] = None
        remove_log.append((fid, name, 'alias_none'))
        continue

    # Vague exact
    if nl in REMOVE_EXACT:
        old2canonical[fid] = None
        remove_log.append((fid, name, 'vague'))
        continue

    # Vague substring
    bad_sub = next((p for p in REMOVE_CONTAINS if p in nl), None)
    if bad_sub:
        old2canonical[fid] = None
        remove_log.append((fid, name, f'vague_contains'))
        continue

    # Pharma drugs
    if nl in PHARMA_DRUGS:
        old2canonical[fid] = None
        remove_log.append((fid, name, 'pharma_drug'))
        continue

    # IUPAC/chemical formula heuristic
    if (re.search(r'\d', name) and len(name) > 40 and
            re.search(r'[(){}\[\]]', name) and
            'extract' not in nl and 'polysaccharide' not in nl):
        old2canonical[fid] = None
        remove_log.append((fid, name, 'iupac_chemical'))
        continue

    # Resolve alias
    alias_target = FOOD_ALIASES.get(nl)
    canonical_lower = alias_target if alias_target else nl
    canon_fid = name_lower2id.get(canonical_lower, fid)
    if canon_fid not in foods:
        canon_fid = fid

    old2canonical[fid] = canon_fid
    keep_ids.add(canon_fid)

    if canon_fid not in canonical_id2name:
        # If alias_target is set, use that as the display name
        display = alias_target if alias_target else foods.get(canon_fid, name)
        canonical_id2name[canon_fid] = display
    else:
        # Only upgrade if the current name is an abbreviation and the new one isn't
        current = canonical_id2name[canon_fid]
        candidate = alias_target if alias_target else foods.get(fid, name)
        if is_abbreviation(current) and not is_abbreviation(candidate):
            canonical_id2name[canon_fid] = candidate

# Remove lone abbreviations
abbr_removed = []
for fid in list(keep_ids):
    name = foods.get(fid, '')
    if is_abbreviation(name) and old2canonical.get(fid) == fid:
        has_partner = any(v == fid and k != fid for k, v in old2canonical.items())
        if not has_partner:
            old2canonical[fid] = None
            keep_ids.discard(fid)
            abbr_removed.append((fid, name))

# Rebuild interactions
merged_drug_to_foods = {}
for did, fset in drug_to_foods.items():
    new_fset = set()
    for old_fid in fset:
        canon_fid = old2canonical.get(old_fid)
        if canon_fid is not None:
            new_fset.add(canon_fid)
    if new_fset:
        merged_drug_to_foods[did] = new_fset

# Assign new contiguous IDs
sorted_keep = sorted(keep_ids)
new_food_id = {old: new for new, old in enumerate(sorted_keep)}

final_drug_to_foods = {}
for did, fset in merged_drug_to_foods.items():
    new_fset = {new_food_id[f] for f in fset if f in new_food_id}
    if new_fset:
        final_drug_to_foods[did] = new_fset

# Write food master
food_out = root / 'unified_food_master.txt'
with food_out.open('w', encoding='utf-8') as f:
    for new_id, old_canon_id in enumerate(sorted_keep):
        name = canonical_id2name.get(old_canon_id, foods.get(old_canon_id, f'food_{old_canon_id}'))
        f.write(f"{new_id}\t{name}\n")

# Write interactions
inter_out = root / 'unified_train_interactions.txt'
with inter_out.open('w', encoding='utf-8') as f:
    for did in sorted(final_drug_to_foods.keys()):
        fids = sorted(final_drug_to_foods[did])
        if fids:
            f.write(' '.join([str(did)] + [str(x) for x in fids]) + '\n')

# Summary
total_pairs = sum(len(v) for v in final_drug_to_foods.values())
print(f"Original food entries   : {len(foods)}")
print(f"Removed (vague)         : {sum(1 for x in remove_log if 'vague' in x[2])}")
print(f"Removed (pharma drugs)  : {sum(1 for x in remove_log if x[2]=='pharma_drug')}")
print(f"Removed (IUPAC chem)    : {sum(1 for x in remove_log if x[2]=='iupac_chemical')}")
print(f"Removed (alias None)    : {sum(1 for x in remove_log if x[2]=='alias_none')}")
print(f"Removed (abbreviations) : {len(abbr_removed)}")
print(f"Final unique foods      : {len(sorted_keep)}")
print(f"Interaction lines       : {len(final_drug_to_foods)}")
print(f"Total positive pairs    : {total_pairs}")
print(f"\nWritten: {food_out}")
print(f"Written: {inter_out}")

print("\n--- Sample removed [vague] ---")
for fid, name, r in [x for x in remove_log if 'vague' in x[2]][:20]:
    print(f"  {fid}: {name}")

print("\n--- Sample removed [pharma_drug] first 20 ---")
for fid, name, r in [x for x in remove_log if x[2]=='pharma_drug'][:20]:
    print(f"  {fid}: {name}")

print(f"\n  ... and {sum(1 for x in remove_log if x[2]=='pharma_drug')-20} more pharma drugs removed")

print("\n--- Removed [iupac/alias_none] ---")
for fid, name, r in [x for x in remove_log if x[2] in ('iupac_chemical','alias_none')][:20]:
    print(f"  [{r}] {fid}: {name}")

print("\n--- Removed abbreviations ---")
for fid, name in abbr_removed[:20]:
    print(f"  {fid}: {name}")
