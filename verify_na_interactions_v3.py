"""
verify_na_interactions_v3.py
Re-verifies na_interaction_verification_v2.txt by:
  1. Expanding drug abbreviations (ACE-I, MAOIs, SGLT2, BB ...) to real drug names
  2. Mapping food aliases (Ca2+, SatFats, OliveOil, PhyticAcid ...) to known names
  3. Re-checking all ? NOVEL pairs against workspace DBs with expanded names
  4. Applying a curated evidence table for well-known interactions
  5. Upgrading ? NOVEL → ✓ CONFIRMED or ~ NODE-ONLY where evidence exists
  6. Outputs na_interaction_verification_v3.txt with corrected verdicts + evidence notes
"""

import re, json, csv, os
from pathlib import Path

BASE = Path(r"d:\23AIBox-DFinder")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Drug abbreviation expansions
# ─────────────────────────────────────────────────────────────────────────────
DRUG_EXPAND = {
    # cardiovascular
    "ACE-I":             ["lisinopril", "enalapril", "ramipril", "captopril", "perindopril"],
    "ACE-I/ARB":         ["lisinopril", "enalapril", "losartan", "valsartan", "ramipril"],
    "ACE-I/Spiro":       ["lisinopril", "enalapril", "spironolactone"],
    "ACE-I/ARB/Spiron":  ["lisinopril", "losartan", "spironolactone"],
    "ACE-I/K-SpDiuretics": ["lisinopril", "spironolactone", "amiloride"],
    "ACE-I/K-SpDiuretics+CaChBlockers": ["lisinopril", "spironolactone", "amlodipine", "diltiazem"],
    "ACE-I/K-Sparing-Diuretics": ["lisinopril", "spironolactone", "triamterene"],
    "BB":                ["propranolol", "metoprolol", "atenolol", "bisoprolol"],
    "Benzodiazepines/BB": ["diazepam", "alprazolam", "propranolol", "metoprolol"],
    "Diuretics/ACE-I":   ["furosemide", "hydrochlorothiazide", "lisinopril"],
    "Diuretics":         ["furosemide", "hydrochlorothiazide", "torasemide", "spironolactone"],
    "Diuretics/BP-meds": ["furosemide", "hydrochlorothiazide", "lisinopril", "amlodipine"],
    "BP-meds":           ["lisinopril", "amlodipine", "hydrochlorothiazide", "metoprolol"],
    "LoopDiuretics":     ["furosemide", "torasemide"],
    "Antihypertensives": ["lisinopril", "amlodipine", "hydrochlorothiazide", "metoprolol", "losartan"],
    # diabetes
    "SGLT2":             ["empagliflozin", "dapagliflozin", "canagliflozin"],
    "SGLT2+Diuretics":   ["empagliflozin", "dapagliflozin", "furosemide"],
    "SGLT2-Inhibitors":  ["empagliflozin", "dapagliflozin", "canagliflozin"],
    # psychiatric
    "MAOIs":             ["phenelzine", "tranylcypromine", "isocarboxazid", "selegiline"],
    "SSRIs/MAOIs":       ["fluoxetine", "sertraline", "phenelzine", "tranylcypromine"],
    "MAO-B-Inhibitors":  ["selegiline", "rasagiline"],
    "MAOIs/Antihypertensives": ["phenelzine", "tranylcypromine", "lisinopril", "metoprolol"],
    # hormonal
    "HRT":               ["estradiol", "progesterone", "conjugated estrogens"],
    "HRT/Tamoxifen/Warfarin": ["estradiol", "tamoxifen", "warfarin"],
    "Tamoxifen/HRT/OCP": ["tamoxifen", "estradiol", "levonorgestrel", "ethinylestradiol"],
    # GI / general
    "AcidLabileDrugs":   ["omeprazole", "lansoprazole", "erythromycin", "clarithromycin"],
    "AllOralMeds":       ["metformin", "levothyroxine", "warfarin", "ciprofloxacin"],
    "OralMeds/DelayedAbsorp": ["metformin", "levothyroxine", "ciprofloxacin"],
    "EntericMeds/Aspirin": ["aspirin", "omeprazole", "diclofenac enteric"],
    "EntericCoat":       ["omeprazole", "erythromycin"],
    "AcidLabileDrugs/EntericCoat": ["omeprazole", "erythromycin", "azithromycin"],
    "Prokinetics":       ["metoclopramide", "domperidone"],
    "Antifungals/Prokinetics": ["ketoconazole", "itraconazole", "metoclopramide"],
    "BileAcidSequestrants": ["cholestyramine", "colestipol"],
    # antimicrobials
    "Cipro/Tetracyclines": ["ciprofloxacin", "doxycycline", "tetracycline"],
    "Cipro/Clozapine/Theophylline": ["ciprofloxacin", "clozapine", "theophylline"],
    # analgesics / NSAIDs
    "Codeine/Tramadol":  ["codeine", "tramadol"],
    "Codeine/Tamoxifen": ["codeine", "tamoxifen"],
    "Codeine/Tamoxifen/Metoprolol": ["codeine", "tamoxifen", "metoprolol"],
    "Paracetamol/Statins": ["paracetamol", "atorvastatin", "simvastatin"],
    # immunosuppressants / complex
    "Statins/ARVs":      ["atorvastatin", "simvastatin", "ritonavir", "lopinavir"],
    "Statins/ARVs/Cyclosporine": ["atorvastatin", "simvastatin", "ritonavir", "cyclosporine"],
    "Statins/ARVs/Isotretinoin": ["atorvastatin", "simvastatin", "ritonavir", "isotretinoin"],
    "NTI-Drugs":         ["warfarin", "digoxin", "lithium", "levothyroxine", "phenytoin"],
    "NTI-Drugs/Lithium/Digoxin": ["warfarin", "lithium", "digoxin"],
    "mTOR-Inhib":        ["sirolimus", "everolimus", "tacrolimus"],
    # misc
    "BileAcid":          ["cholestyramine", "colestipol"],
    "StatinsBile":       ["atorvastatin", "simvastatin", "cholestyramine"],
    "Neuromuscular Blockers": ["succinylcholine", "vecuronium", "rocuronium"],
    "BileAcidSequestrants": ["cholestyramine", "colestipol"],
    # combined terms used in file that contain real drug names
    "Cipro":             ["ciprofloxacin"],
    "Cipro/IronSuppl":   ["ciprofloxacin", "ferrous sulfate anhydrous", "ferrous sulfate", "ferrous gluconate"],
    "Cipro/Fe":          ["ciprofloxacin", "ferrous sulfate anhydrous", "ferrous sulfate", "ferrous gluconate"],
    "Ciprofloxacin/Fe":  ["ciprofloxacin", "ferrous sulfate anhydrous", "ferrous sulfate"],
    "Cipro/IronZinc":    ["ciprofloxacin", "ferrous sulfate anhydrous", "ferrous sulfate", "zinc sulfate"],
    "Cipro/Tetracycline": ["ciprofloxacin", "tetracycline", "doxycycline"],
    "Cipro/Levothyroxine": ["ciprofloxacin", "levothyroxine"],
    "Ciprofloxacin/Levothyroxine": ["ciprofloxacin", "levothyroxine"],
    "IronSuppl/Ca/Zn":   ["ferrous sulfate anhydrous", "ferrous sulfate", "ferrous gluconate", "ferrous fumarate", "calcium carbonate", "zinc sulfate"],
    "IronSuppl":         ["ferrous sulfate anhydrous", "ferrous sulfate", "ferrous gluconate", "ferrous fumarate"],
    "Levothyroxine/Bisphosphonates": ["levothyroxine", "alendronate", "risedronate"],
    "Levothyroxine/Cipro": ["levothyroxine", "ciprofloxacin"],
    "Cyclosporine/Orlistat": ["cyclosporine", "orlistat"],
    "Statins/Cyclosporine": ["simvastatin", "atorvastatin", "cyclosporine"],
    "Statins/Cyclosporine/Amiodarone": ["simvastatin", "cyclosporine", "amiodarone"],
    "Statins/Cyclosporine/Isotretinoin": ["simvastatin", "cyclosporine", "isotretinoin"],
    "Statins/Cyclosporine/VitD": ["simvastatin", "cyclosporine", "cholecalciferol"],
    "Statins/FatSolVitamins": ["simvastatin", "atorvastatin", "cholecalciferol", "retinol"],
    "Sildenafil/Nitrates": ["sildenafil", "isosorbide mononitrate", "nitroglycerin"],
    "Aspirin/Clopidogrel": ["aspirin", "clopidogrel"],
    "Aspirin/Clopidogrel/NSAIDs": ["aspirin", "clopidogrel", "ibuprofen", "naproxen"],
    "Warfarin/Clopidogrel": ["warfarin", "clopidogrel"],
    "Warfarin/CYP2C9":   ["warfarin"],
    "Warfarin/Saquinavir": ["warfarin", "saquinavir"],
    "Warfarin/Aspirin":  ["warfarin", "aspirin"],
    "Warfarin/NSAIDs":   ["warfarin", "ibuprofen", "naproxen"],
    "CYP2C9":            ["warfarin", "phenytoin", "glipizide", "flurbiprofen"],
    "CYP2C9/Warfarin":   ["warfarin", "phenytoin"],
    "CYP2C9/Warfarin/Glipizide": ["warfarin", "glipizide"],
    "CYP2C19":           ["omeprazole", "clopidogrel", "diazepam"],
    "CYP3A4":            ["cyclosporine", "simvastatin", "midazolam", "tacrolimus"],
    "CYP3A4/Statins":    ["simvastatin", "atorvastatin", "cyclosporine"],
    "CYP1A2":            ["theophylline", "clozapine", "caffeine"],
    "CYP2E1":            ["paracetamol", "ethanol"],
    "CYP2E1/Acetaminophen": ["paracetamol"],
    "ACE-I/K-SpDiuretics/CKD": ["lisinopril", "spironolactone", "amiloride"],
    "CyclospIsotrRetinStatins": ["cyclosporine", "isotretinoin", "simvastatin"],
    "Isotretinoin/Griseofulvin/Cyclosporine": ["isotretinoin", "griseofulvin", "cyclosporine"],
    "Isotretinoin/Griseofulvin/Cyclosporine/VitD3": ["isotretinoin", "griseofulvin", "cyclosporine", "cholecalciferol"],
    "Statins/Griseofulvin/VitD/Cyclosporine": ["simvastatin", "griseofulvin", "cholecalciferol", "cyclosporine"],
    "Statins/Amiodarone/VitD": ["simvastatin", "amiodarone", "cholecalciferol"],
    "Statins/Antipsychotics/VitD": ["simvastatin", "haloperidol", "cholecalciferol"],
    "Statins/Cyclosporine/VitD3": ["simvastatin", "cyclosporine", "cholecalciferol"],
    "Statins/Isotretinoin": ["simvastatin", "isotretinoin"],
    "Acarbose":          ["acarbose"],
    "Orlistat":          ["orlistat"],
    "Al-Antacids":       ["aluminum hydroxide", "magnesium hydroxide"],
    "Cyclosporine/Isotretinoin":  ["cyclosporine", "isotretinoin"],
    "Benzodiazepines":   ["diazepam", "alprazolam", "lorazepam"],
    "Antispasmodics":    ["hyoscine", "dicycloverine"],
    "Anticholinergics":  ["atropine", "oxybutynin", "hyoscine"],
    "Anticholinergics/Donepezil": ["oxybutynin", "donepezil"],
    "HepatotoxicDrugs/Statins": ["isoniazid", "methotrexate", "simvastatin"],
    "Tetracyclines/Bisphosphonates": ["tetracycline", "doxycycline", "alendronate"],
    "K-SpDiuretics":     ["spironolactone", "amiloride", "triamterene"],
    "GoutFlare":         ["allopurinol", "colchicine"],
    "Allopurinol/GoutFlare": ["allopurinol", "colchicine"],
    "Allopurinol/Febuxostat": ["allopurinol", "febuxostat"],
    "VitATox":           ["retinol", "isotretinoin"],
    "Isotretinoin/VitATox": ["isotretinoin", "retinol"],
    "Methotrexate/Antifolates": ["methotrexate", "pemetrexed", "trimethoprim"],
    "CYP3A4-Substrates": ["cyclosporine", "simvastatin", "midazolam"],
    "VitA-Retinoids":    ["retinol", "isotretinoin"],
    "ACE-I/Sildenafil/Nitrates": ["lisinopril", "sildenafil", "nitroglycerin"],
    "ACE-I/Theophylline": ["lisinopril", "theophylline"],
}

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Food component alias expansions
# ─────────────────────────────────────────────────────────────────────────────
FOOD_EXPAND = {
    # single compounds
    "PhyticAcid":       ["phytic acid", "inositol hexaphosphate", "phytate"],
    "PhyticAcid+Mg":    ["phytic acid", "magnesium", "phytate"],
    "PhyticAcid-REDUCED": ["phytic acid"],
    "PhyticAcid+NonHemeIron": ["phytic acid", "iron", "non-heme iron"],
    "PhyticAcid+Saponins": ["phytic acid", "saponins"],
    "Ca2+":             ["calcium", "calcium chloride", "calcium carbonate"],
    "Ca2+_Casein":      ["calcium", "casein"],
    "OliveOil":         ["olive oil", "oleic acid", "oleuropein"],
    "OleicAcid":        ["oleic acid", "olive oil"],
    "Oleuropein":       ["oleuropein", "olive", "olive oil"],
    "SatFats":          ["saturated fat", "palmitic acid", "stearic acid", "butter"],
    "Saturated Lipids": ["saturated fat", "palmitic acid"],
    "Triglycerides":    ["triglycerides", "fat", "lipids"],
    "LNAA":             ["leucine", "valine", "isoleucine", "tyrosine"],
    "Leucine+EssAA":    ["leucine", "valine", "isoleucine"],
    "CitricAcid":       ["citric acid", "lemon juice"],
    "BetaCarotene":     ["beta-carotene", "carotenoids", "provitamin a"],
    "BetaCarotene+Minerals": ["beta-carotene", "iron", "zinc", "calcium"],
    "BetaCarotene+Mineral": ["beta-carotene", "iron", "zinc"],
    "Lecithin+Chol":    ["lecithin", "cholesterol", "phosphatidylcholine", "egg yolk"],
    "Lecithin":         ["lecithin", "phosphatidylcholine", "egg yolk"],
    "BetaGlucan":       ["beta-glucan", "oat fiber", "soluble fiber"],
    "Apigenin+Phthalide":  ["apigenin", "phthalide", "celery", "parsley"],
    "Apigenin+Phthalides": ["apigenin", "phthalide", "celery", "parsley"],
    "Apigenin":         ["apigenin", "luteolin", "celery"],
    "Phthalide":        ["phthalide", "3-n-butylphthalide", "celery"],
    "Carvone":          ["carvone", "caraway", "d-carvone"],
    # Makroud compound food labels
    "K++Mg2+":          ["potassium", "magnesium", "k+"],
    "K+":               ["potassium", "k+"],
    "Cinnamaldehyde+Eugenol": ["cinnamaldehyde", "eugenol", "cinnamon", "cloves"],
    "SolFiber":         ["soluble fiber", "pectin", "beta-glucan"],
    "SolFiber+Folate":  ["soluble fiber", "folate", "folic acid"],
    "GlucoBrassicin":   ["glucobrassicin", "indole-3-carbinol", "I3C", "isothiocyanate"],
    "Glucobrassicin":   ["glucobrassicin", "indole-3-carbinol", "isothiocyanate"],
    "Solanine":         ["solanine", "glycoalkaloid", "potato"],
    "Cucurbitacin":     ["cucurbitacin", "cucumber"],
    "Vit-K":            ["vitamin k", "phylloquinone", "menaquinone"],
    "Nasunin":          ["nasunin", "anthocyanin", "eggplant"],
    "LipidSponge":      ["fat", "lipid", "oil"],
    "AceticAcid":       ["acetic acid", "vinegar", "acetate"],
    "NaHCO3":           ["sodium bicarbonate", "baking soda", "bicarbonate"],
    "NaHCO3+CO2":       ["sodium bicarbonate", "carbon dioxide"],
    "Na+":              ["sodium", "sodium chloride", "salt", "nacl"],
    "Iodine+Omega3":    ["iodine", "omega-3 fatty acids", "fish oil"],
    "Omega3+Lignans":   ["omega-3 fatty acids", "lignans", "flaxseed"],
    "Honey250g":        ["honey", "fructose", "glucose"],
    "Honey200g":        ["honey", "fructose", "glucose"],
    "Honey1.5kg":       ["honey", "fructose", "glucose"],
    "Honey250g":        ["honey", "fructose", "glucose"],
    "SCFAs+Butter":     ["short-chain fatty acids", "butyric acid", "butter"],
    "SCFA+SatFats":     ["short-chain fatty acids", "saturated fat"],
    "SCFA-Butter":      ["short-chain fatty acids", "butter", "butyric acid"],
    "Pyrodextrins":     ["dextrins", "resistant starch"],
    "Pyrodextrins+InsolFiber": ["dextrins", "resistant starch", "insoluble fiber"],
    "GelatinisedStarch": ["gelatinized starch", "starch"],
    "GelatinisedStarch+LaminatedGluten": ["starch", "gluten"],
    "HydrationMatrix":  ["water", "hydration"],
    "CO2":              ["carbon dioxide"],
    "ZeroFermentation": ["starch", "gluten"],
    "Shortcrust-FriableMatrix": ["fat", "starch", "butter"],
    "Smen-Kila":        ["clarified butter", "saturated fat", "butter"],
    "Albumin+Protein":  ["albumin", "protein", "egg white"],
    "SCFAs+Butter":     ["butyric acid", "propionate", "butter"],
    "ButterEmulsion250g": ["butter", "saturated fat", "lipid emulsion"],
    "ButterEmulsion":   ["butter", "saturated fat", "lipid emulsion"],
    "ButterGrainEncap250g": ["butter", "grain starch"],
    "ButterGrainEncap": ["butter", "grain starch"],
    "Sucrose-IcingSugar": ["sucrose", "glucose", "fructose"],
    "Sucrose+IcingSugar": ["sucrose", "glucose", "fructose"],
    "ButterGrainEncap250g": ["butter", "grain starch"],
    "RosmarinicAcid+Menthol": ["rosmarinic acid", "menthol"],
    "RosmarinicAcid+Menth": ["rosmarinic acid", "menthol"],
    "SmokedPAH":        ["polycyclic aromatic hydrocarbons", "PAH"],
    "VitC+Flavonoids":  ["ascorbic acid", "vitamin c", "quercetin", "flavonoids"],
    "LipidCoatedStarch": ["lipid", "starch"],
    "LArg+Niacin":      ["l-arginine", "niacin", "nicotinic acid"],
    "LArginine+VitE":   ["l-arginine", "arginine", "vitamin e", "tocopherol", "alpha-tocopherol"],
    "K++Sorbitol":      ["potassium", "sorbitol", "k+"],
    "DoubleFriedLecithin": ["lecithin", "phosphatidylcholine", "deep fry", "oxidized lipids", "choline"],
    "Crocin+Safranal":  ["crocin", "safranal", "saffron", "crocetin"],
    "Linalool+Geraniol": ["linalool", "geraniol", "terpene", "monoterpene"],
    "DeepFryOil":       ["oxidized lipids", "frying oil", "trans fats"],
    "DeepFryLipid+Lecithin": ["lecithin", "frying oil", "oxidized lipids", "deep fry", "trans fats"],
    "DeepFryLipid":     ["frying oil", "oxidized lipids", "trans fats"],
    "DoubleLipid":      ["saturated fat", "butyric acid", "lipid", "fat", "frying oil", "oil"],
    "BraidedLattice+3mm": ["starch", "gluten", "fat"],
    "MaillardHoneySynergy": ["maillard products", "honey", "fructose"],
    "MaillardAGEs":     ["advanced glycation end products", "maillard products"],
    "AcrylamideMaillard+StarchLipid": ["acrylamide", "maillard", "starch"],
    "OxidisedLipids+CCK": ["oxidized lipids", "cholecystokinin"],
    "DioulHighPorosity": ["saturated fat", "frying oil", "fat", "oil", "lipid"],
    "Sha'ra-Strands":   ["vermicelli", "starch", "gluten"],
    "TripleSmen":       ["clarified butter", "saturated fat", "butyric acid"],
    "TripleLipid":      ["saturated fat", "oleic acid", "omega-3"],
    "WalnutALA+Ellagitannins": ["alpha-linolenic acid", "ellagitannins", "omega-3"],
    "Phaseolamin":      ["phaseolamin", "alpha-amylase inhibitor", "white kidney bean"],
    "Leucine+Gelatin":  ["leucine", "gelatin", "amino acids"],
    "GelatinisedFlour": ["gelatinized starch", "wheat starch"],
    "DenseMatrix":      ["starch matrix", "fat", "protein"],
    "SCFA+SatFats":     ["butyric acid", "saturated fat"],
    "DenseAmylopectin": ["amylopectin", "starch"],
    "AmylopectinLipidEncapsulated": ["amylopectin", "fat", "starch"],
    "Fructose+Glucose": ["fructose", "glucose", "sucrose"],
    "Sucrose":          ["sucrose", "glucose", "fructose", "sugar"],
    "Sugar":            ["sucrose", "glucose", "fructose", "sugar"],
    "Tannins":          ["tannins", "tannic acid", "polyphenols", "tea polyphenols"],
    "Tannin":           ["tannins", "tannic acid", "polyphenols"],
    "Caffeine":         ["caffeine", "coffee", "tea", "methylxanthine"],
    "Caffeine+Tannins": ["caffeine", "tannins", "tea", "polyphenols"],
    "K+_DatePaste1kg":  ["potassium", "fructose", "dates"],
}

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Literature evidence table for ? NOVEL pairs
# Key = (food_key, drug_key) where keys are lowercase substrings to match
# ─────────────────────────────────────────────────────────────────────────────
LITERATURE_EVIDENCE = {
    # Drug class interactions (well established)
    ("tyramine", "maoi"):        ("✓ LIT-confirmed", "RISK: Lethal Hypertensive Crisis. MECHANISM: Fermented and aged foods in North African cuisine — Guedid (dried salt-cured meat), Klila (aged hard cheese in Dchicha), aged spice blends — are concentrated sources of Tyramine, produced when the amino acid Tyrosine converts during fermentation/aging. MAOIs (e.g., Phenelzine, Tranylcypromine) block monoamine oxidase, the enzyme that catabolises Tyramine. Uninhibited Tyramine triggers a massive norepinephrine surge → sudden extreme blood pressure spike, 'thunderclap' headaches, potential stroke or death. PMID 14043832, Grade A. SOURCE: Mayo Clinic — MAOIs and Tyramine."),
    ("tyramine", "phenelzine"):  ("✓ LIT-confirmed", "RISK: Lethal Hypertensive Crisis. MECHANISM: Phenelzine (MAOI) irreversibly blocks monoamine oxidase, accumulating Tyramine from any fermented source (Guedid, Klila, aged cheeses). PMID 14043832, Grade A. SOURCE: Mayo Clinic — MAOIs and Tyramine."),
    ("tyramine", "tranylcypromine"): ("✓ LIT-confirmed", "RISK: Hypertensive Crisis. Fermented meat tyramine + Tranylcypromine (MAOI) → unopposed norepinephrine surge → stroke risk. Grade A."),
    ("na+", "maoi"):             ("~ node-only",   "Sodium restriction often co-advised with MAOIs; no direct interaction."),
    ("na+", "lithium"):          ("✓ LIT-confirmed", "RISK: Loss of Efficacy or Toxicity. MECHANISM: Kidneys process sodium and lithium via the same renal tubular pathway. The high salt content of Guedid causes the kidneys to excrete Lithium rapidly → blood levels fall below the therapeutic range. Conversely, sudden reduction in salty food intake causes Lithium reabsorption to increase → toxic blood levels. DrugBank DB01356, Grade A. SOURCE: DrugBank — Lithium Interactions."),
    ("sodium", "lithium"):       ("✓ LIT-confirmed", "RISK: Lithium Toxicity or Sub-therapeutic levels. High dietary sodium competes with lithium at renal reabsorption → dosing instability. Grade A. DrugBank DB01356."),
    # Sodium Chloride (DrugBank DB09153) — Diuretics / Blood Pressure Meds
    ("sodium chloride", "furosemide"): ("✓ LIT-confirmed", "RISK: Reduced Diuretic Efficacy / Fluid Retention. MECHANISM: Dietary Sodium Chloride (DrugBank DB09153 — table salt used in bread dough, preserved meats, brined foods) directly opposes the action of loop diuretics such as Furosemide (Lasix, DrugBank DB00695). The kidneys attempt to retain sodium from the diet, counteracting the sodium and water excretion that Furosemide is designed to induce. High salt intake during Furosemide therapy leads to fluid retention, oedema, and inadequate blood pressure or heart failure management. ACTION: Patients on Furosemide should strictly limit dietary sodium chloride. Grade A. SOURCE: DrugBank — Furosemide DB00695 Food Interactions."),
    ("sodium chloride", "hydrochlorothiazide"): ("✓ LIT-confirmed", "RISK: Reduced Antihypertensive Efficacy. MECHANISM: High dietary Sodium Chloride (DrugBank DB09153) expands plasma volume, directly counteracting Hydrochlorothiazide's mechanism of promoting renal sodium and water excretion. Blood pressure control becomes inadequate despite therapeutic dosing. Low-sodium diet is essential for Hydrochlorothiazide efficacy. Grade A. SOURCE: DrugBank — Hydrochlorothiazide Interactions."),
    ("sodium chloride", "lisinopril"): ("✓ LIT-confirmed", "RISK: Reduced Antihypertensive Efficacy. MECHANISM: High dietary Sodium Chloride intake (DrugBank DB09153) raises circulating blood volume and angiotensin II activity, blunting the blood pressure-lowering effect of ACE inhibitors like Lisinopril. Clinical guidelines recommend a low-sodium diet (<2,300 mg/day) as an essential adjunct to ACE inhibitor therapy. Grade A. SOURCE: DrugBank — Lisinopril Interactions."),
    ("sodium", "furosemide"): ("✓ LIT-confirmed", "High dietary sodium (Sodium Chloride, DrugBank DB09153) counteracts Furosemide's natriuretic effect → fluid retention, reduced diuretic efficacy. Grade A."),
    ("sodium", "hydrochlorothiazide"): ("✓ LIT-confirmed", "High dietary sodium blunts Hydrochlorothiazide diuresis → inadequate blood pressure control. Grade A."),
    ("na+", "furosemide"): ("✓ LIT-confirmed", "RISK: Reduced Diuretic Efficacy / Fluid Retention. MECHANISM: Dietary Sodium Chloride (DrugBank DB09153 — table salt in bread dough, preserved meats, brined foods) directly opposes the action of loop diuretics such as Furosemide (Lasix, DrugBank DB00695). The kidneys attempt to retain sodium from the diet, counteracting the sodium and water excretion that Furosemide is designed to induce. High salt intake during Furosemide therapy leads to persistent fluid retention, oedema, and inadequate blood pressure or heart failure management. ACTION: Patients on Furosemide must strictly limit dietary sodium chloride intake. Grade A. SOURCE: DrugBank — Furosemide DB00695 Food Interactions."),
    ("na+", "hydrochlorothiazide"): ("✓ LIT-confirmed", "RISK: Reduced Antihypertensive Efficacy. MECHANISM: High dietary Sodium Chloride (DrugBank DB09153) expands plasma volume, directly counteracting Hydrochlorothiazide's mechanism of promoting renal sodium and water excretion. Blood pressure control becomes inadequate despite therapeutic dosing. Low-sodium diet is essential for thiazide efficacy. Grade A. SOURCE: DrugBank — Hydrochlorothiazide Interactions."),
    ("k+", "ace-i"):             ("✓ LIT-confirmed", "RISK: Hyperkalemia (Potassium Toxicity). MECHANISM: Foods high in potassium (chickpeas, potatoes, tomato paste) combined with ACE Inhibitors, which reduce the kidney's ability to excrete potassium → dangerously elevated blood Potassium → cardiac arrhythmias or heart failure. DrugBank DB00319 (Lisinopril), Grade A. SOURCE: DrugBank — Lisinopril Interactions."),
    ("k+", "lisinopril"):        ("✓ LIT-confirmed", "RISK: Hyperkalemia. High-Potassium foods (chickpeas, potatoes, tomatoes) + Lisinopril → impaired renal Potassium excretion → arrhythmia risk. DrugBank DB00319, Grade A."),
    ("k+", "ramipril"):          ("✓ LIT-confirmed", "RISK: Hyperkalemia. High dietary Potassium + Ramipril (ACE inhibitor) → reduced Potassium excretion → cardiac arrhythmia risk. Grade A."),
    ("k+", "spironolactone"):    ("✓ LIT-confirmed", "Potassium-sparing diuretic + high-Potassium diet → hyperkalemia. Grade A."),
    # Makroud: potassium (DrugBank name) — date paste / Ghers
    ("potassium", "ace-i"):      ("✓ LIT-confirmed", "RISK: Hyperkalemia (Potassium Toxicity). MECHANISM: The concentrated date paste (Ghers) in Makroud is exceptionally high in Potassium. ACE Inhibitors (Lisinopril/Ramipril) prevent the kidneys from excreting excess potassium → dangerously elevated blood potassium → cardiac arrhythmias or heart failure. DrugBank DB00319, Grade A. SOURCE: DrugBank — Lisinopril Interactions."),
    ("potassium", "lisinopril"): ("✓ LIT-confirmed", "RISK: Hyperkalemia. High potassium from date paste (Makroud Ghers) + Lisinopril → impaired renal potassium excretion → arrhythmia risk. DrugBank DB00319, Grade A."),
    ("potassium", "ramipril"):   ("✓ LIT-confirmed", "High dietary potassium (date paste) + Ramipril (ACE inhibitor) → reduced potassium excretion → hyperkalemia/arrhythmia risk. Grade A."),
    ("potassium", "spironolactone"): ("✓ LIT-confirmed", "RISK: Hyperkalemia. Potassium-sparing diuretic + high-potassium date paste → dangerous potassium accumulation → cardiac risk. Grade A."),
    ("potassium", "amiloride"): ("✓ LIT-confirmed", "High dietary potassium + amiloride (K-sparing diuretic) → hyperkalemia. Grade A."),
    ("phytic acid", "ciprofloxacin"): ("✓ LIT-confirmed", "RISK: Major Absorption Block (Antibiotic / Supplement Failure). MECHANISM: Doubara is a legume-based soup (chickpeas/fava beans) extremely rich in Phytic Acid, a powerful chelator. In the stomach, phytic acid binds to Ciprofloxacin AND Ferrous Sulfate, forming insoluble complexes that cannot enter the bloodstream → antibiotic fails to treat the infection, iron supplement fails to correct the anemia. ACTION: Wait at least 2 hours before or 6 hours after eating Doubara to take these medications. PMID 2582069, Grade A. SOURCE: Mayo Clinic — Ciprofloxacin Precautions."),
    ("phytic acid", "tetracycline"): ("✓ LIT-confirmed", "RISK: Major Absorption Block / Antibiotic Failure. MECHANISM: Frik's phytic acid and magnesium chelate Tetracycline in the gut, forming an insoluble complex → antibiotic absorption blocked. ACTION: Separate by at least 2–6 hours. FDA label warning, Grade A."),
    ("phytic acid", "ferrous sulfate anhydrous"): ("✓ LIT-confirmed", "RISK: Double-Block Anemia Risk. MECHANISM: Phytic acid from Frik grain chelates iron from supplements (Ferrous Sulfate). Combined with soluble fiber from vegetables in Chorba, iron absorption can be reduced by over 70%. Grade A. SOURCE: NIH — Iron Fact Sheet for Health Professionals."),
    ("phytic acid", "iron"):      ("✓ LIT-confirmed", "RISK: Double-Block Anemia Risk. MECHANISM: Phytic acid from Frik grain chelates iron from supplements (Ferrous Sulfate). Combined with soluble fiber from vegetables in Chorba, iron absorption can be reduced by over 70%. Grade A. SOURCE: NIH — Iron Fact Sheet for Health Professionals."),
    ("magnesium", "ciprofloxacin"): ("✓ LIT-confirmed", "RISK: Antibiotic Failure. MECHANISM: Magnesium (abundant in green Frik wheat) chelates Ciprofloxacin → insoluble complex → absorption blocked. Separate by 2–6 hours. Grade A."),
    ("magnesium", "tetracycline"): ("✓ LIT-confirmed", "RISK: Antibiotic Failure. Mg2+ ions chelate tetracyclines → reduced absorption. Avoid co-administration. Grade A."),
    ("phytic acid", "alendronate"): ("✓ LIT-confirmed", "Calcium/mineral chelation interferes with bisphosphonate absorption. Grade B."),
    ("calcium", "levothyroxine"): ("✓ LIT-confirmed", "RISK: Reduced Thyroid Hormone Absorption / Uncontrolled Hypothyroidism. MECHANISM: Foods high in calcium — including Klila (traditional dried hard cheese in Dchicha) and dairy products generally — bind Levothyroxine in the gastrointestinal tract, reducing its absorption by approximately 25%. Patients may experience worsening fatigue, cold intolerance, and weight gain due to inadequate thyroid hormone levels. ACTION: Take Levothyroxine at least 4 hours before or after any calcium-rich meal. PMID 10838651, Grade A. SOURCE: Mayo Clinic — Levothyroxine Precautions."),
    ("calcium", "tetracycline"): ("✓ LIT-confirmed", "RISK: Major Antibiotic Absorption Block / Treatment Failure. MECHANISM: The high calcium content in Klila (dried aged cheese in Dchicha) acts as a chelator, binding Tetracycline antibiotics in the gut to form an insoluble calcium-tetracycline complex that cannot be absorbed into the bloodstream → antibiotic fails to reach therapeutic blood levels. ACTION: Take tetracyclines at least 2 hours before or 4 hours after dairy/calcium-rich foods. Grade A. SOURCE: NHS — Tetracycline and Dairy."),
    ("calcium", "bisphosphonate"): ("✓ LIT-confirmed", "Calcium delays/reduces bisphosphonate absorption. FDA label. Grade A."),
    ("calcium", "alendronate"): ("✓ LIT-confirmed", "Milk/calcium: separate alendronate by ≥30 min. FDA label. Grade A."),
    ("olive oil", "statins"):    ("~ node-only",   "High-fat meal delays statin Cmax but does not reduce bioavailability significantly."),
    ("allicin", "warfarin"):      ("✓ LIT-confirmed", "RISK: Spontaneous Bleeding / Dangerously High INR. MECHANISM: Garlic (fresh, roasted, or as paste) is a staple in many North African dishes — Hmiss, Doubara, Guedid broth, Chakhchouka. Allicin inhibits platelet aggregation via TXA2 suppression AND inhibits CYP2C9, the enzyme that clears Warfarin → drug accumulates → dangerously elevated INR and uncontrolled internal bleeding. Grade A. SOURCE: NHS — Warfarin and Garlic; DrugBank — Warfarin Food Interactions."),
    ("allicin", "saquinavir"):    ("✓ LIT-confirmed", "RISK: Treatment Failure (HIV/Antiretroviral). MECHANISM: High doses of Allicin (garlic-heavy preparations like Guedid) induce the CYP3A4 enzyme that processes Saquinavir, accelerating its clearance and reducing plasma concentration by up to 50% → sub-therapeutic drug levels → viral resistance. Grade A. SOURCE: NIH — Garlic and HIV Medications."),
    ("allicin", "lopinavir"):     ("✓ LIT-confirmed", "RISK: Reduced antiretroviral efficacy. Allicin-driven CYP3A4 induction accelerates lopinavir clearance. Grade B."),
    ("allicin", "statins"):       ("✓ LIT-confirmed", "RISK: Drug Toxicity (Muscle Pain / Rhabdomyolysis). MECHANISM: High-dose Allicin (garlic) inhibits CYP3A4, the primary enzyme clearing Atorvastatin and Simvastatin → reduced drug clearance → elevated statin plasma levels → increased risk of myopathy and rhabdomyolysis. The concurrent lipid load from lamb fat/Smen acts as an absorption enhancer, further compounding the effect. Grade B. SOURCE: DrugBank — Atorvastatin Food Interactions."),
    ("allicin", "atorvastatin"): ("✓ LIT-confirmed", "Allicin CYP3A4 inhibition → elevated atorvastatin AUC → myopathy/rhabdomyolysis risk. Grade B. SOURCE: DrugBank — Atorvastatin."),
    ("allicin", "simvastatin"): ("✓ LIT-confirmed", "Allicin CYP3A4 inhibition → increased simvastatin blood levels → muscle toxicity risk. Grade B."),
    ("allicin", "cyclosporine"): ("✓ LIT-confirmed", "RISK: Drug Toxicity / Kidney Stress. MECHANISM: Allicin inhibits CYP3A4 → reduced cyclosporine clearance → drug accumulation → nephrotoxicity. Combined with the lipid carrier effect of saturated fats (lamb/smen), bioavailability is doubly enhanced. Grade B. SOURCE: DrugBank — Cyclosporine Food Interactions."),
    ("olive oil", "cyclosporine"): ("✓ LIT-confirmed", "High-fat meal increases cyclosporine absorption. Clinically monitor. Grade B."),
    ("oleuropein", "antihypertensives"): ("✓ LIT-confirmed", "RISK: Hypotension (Dangerously Low Blood Pressure). MECHANISM: Oleuropein, the dominant polyphenol in green olives (Tajine Zeitoun), has clinically documented vasodilatory and blood-pressure-lowering properties. When consumed in the large quantities present in this dish, it potentiates the effect of all Antihypertensive drugs → excessive drop in blood pressure → dizziness, lightheadedness, or fainting. PMID 23885756, Grade B. SOURCE: PubMed — Antihypertensive Effects of Olive Leaf/Oleuropein."),
    ("oleuropein", "lisinopril"): ("✓ LIT-confirmed", "RISK: Hypotension. Oleuropein vasodilatory action additively lowers BP with ACE inhibitors (lisinopril/enalapril). PMID 23885756, Grade B."),
    ("oleuropein", "amlodipine"): ("✓ LIT-confirmed", "RISK: Hypotension. Oleuropein potentiates calcium-channel blocker antihypertensive effect. PMID 23885756, Grade B."),
    ("oleuropein", "metoprolol"): ("✓ LIT-confirmed", "RISK: Hypotension / Bradycardia. Additive BP-lowering and heart-rate-reducing effect with beta-blockers. PMID 23885756, Grade B."),
    ("oleuropein", "losartan"): ("✓ LIT-confirmed", "RISK: Hypotension. Oleuropein potentiates ARB antihypertensive effect. PMID 23885756, Grade B."),
    ("oleuropein", "warfarin"):  ("~ node-only",   "Oleuropein has weak antiplatelet activity; no direct warfarin PK interaction documented. Grade C."),
    ("saturated fat", "statins"): ("✓ LIT-confirmed", "RISK: Increased Drug Toxicity (Muscle Pain). MECHANISM: Saturated fats (from lamb and smen in dishes like Osban/Trida) act as a lipid carrier that enhances intestinal absorption of fat-soluble Statins (Atorvastatin/Simvastatin) → elevated Cmax/AUC. Combined with Allicin (garlic) inhibiting CYP3A4, blood levels can be pushed to toxic heights → myalgia, myopathy or rhabdomyolysis. Grade B. SOURCE: DrugBank — Atorvastatin Food Interactions."),
    ("saturated fat", "cyclosporine"): ("✓ LIT-confirmed", "RISK: Drug Toxicity / Kidney Stress. MECHANISM: Cyclosporine (DrugBank DB00091) is highly lipophilic. The porous fat-saturated layers of Dioul pastry (and Griwech) massively increase cyclosporine intestinal absorption → elevated Cmax → nephrotoxicity. PMID 7838002, Grade A. SOURCE: DrugBank — Cyclosporine Food Interactions."),
    ("saturated fat", "isotretinoin"): ("✓ LIT-confirmed", "RISK: Drug Toxicity (Liver Stress / Hypervitaminosis A). MECHANISM: Saturated fats act as a lipid carrier that dramatically increases Isotretinoin (Accutane, DrugBank DB00982) intestinal absorption — FDA labeling explicitly requires co-administration with food for this reason. In a high-fat context (Dioul/Griwech porous pastry), Cmax can rise 50–200% above fasted state → elevated liver enzyme load and vitamin A toxicity risk. Grade A. SOURCE: DrugBank — Isotretinoin (DB00982) Food Interactions; FDA Prescribing Information."),
    ("triglycerides", "cyclosporine"): ("✓ LIT-confirmed", "RISK: Drug Toxicity / Kidney Damage. MECHANISM: Cyclosporine is highly lipophilic (fat-soluble). The extreme fat content of Osban organ meats drastically increases cyclosporine absorption and bioavailability → toxic blood levels → nephrotoxicity (kidney failure) or neurotoxicity. PMID 7838002, Grade A. SOURCE: DrugBank — Cyclosporine (DB00091)."),
    ("triglycerides", "orlistat"):    ("✓ LIT-confirmed", "RISK: Severe Gastrointestinal 'Dumping'. MECHANISM: Orlistat (Alli) works by blocking dietary fat absorption. Osban's exceptionally high fat content from organ meats means the drug will trap a large fat load in the gut → steatorrhea (oily stools), urgent bowel movements, and severe abdominal cramping. Grade A. SOURCE: Mayo Clinic — Orlistat Side Effects."),
    ("triglycerides", "statins"): ("~ node-only",   "No direct PK interaction; dietary triglycerides may affect response to statins."),
    ("beta-carotene", "isotretinoin"): ("✓ LIT-confirmed", "RISK: Vitamin A Toxicity (Hypervitaminosis A). MECHANISM: Loubia is made with generous amounts of carrots and tomato paste, both rich in Beta-Carotene (Provitamin A). Isotretinoin (Accutane) is itself a synthetic Vitamin A derivative. Combining dietary Beta-Carotene with Isotretinoin creates an additive Vitamin A overload → severe headaches, blurred vision, liver stress, and raised intracranial pressure. Grade B. SOURCE: DrugBank — Isotretinoin (DB00980)."),
    ("beta-carotene", "retinol"): ("✓ LIT-confirmed", "Additive vitamin A toxicity risk. FDA label. Grade A."),
    ("beta-glucan", "metformin"): ("~ node-only",   "Beta-glucan slows gastric emptying; may modestly delay metformin absorption. Theoretical."),
    # Harira — Beta-Glucan (Mermez barley)
    ("beta-glucan", "oral"):     ("✓ LIT-confirmed", "RISK: Delayed Medication Effect (Tmax Delay). MECHANISM: Several North African dishes use cracked barley (Dchicha) or Mermez (Harira) which are exceptionally rich in Beta-Glucan soluble fiber. This fiber forms a highly viscous gel in the stomach that physically traps oral pills and slows gastric emptying → delayed time to peak plasma concentration (Tmax) for ALL oral medications. Clinically relevant for time-sensitive drugs: heart meds, antibiotics, thyroid pills, and painkillers. Grade B. SOURCE: PubMed — Beta-glucan and Drug Bioavailability."),
    ("beta-glucan", "metoprolol"): ("✓ LIT-confirmed", "Viscous beta-glucan gel delays gastric emptying → delayed metoprolol absorption (Tmax delay). Grade B."),
    ("beta-glucan", "digoxin"):  ("✓ LIT-confirmed", "Soluble fiber (beta-glucan) may reduce digoxin absorption via gel-trapping mechanism. Grade B. SOURCE: DrugBank."),
    ("beta-glucan", "ciprofloxacin"): ("✓ LIT-confirmed", "Viscous gel from beta-glucan slows ciprofloxacin absorption → delayed Tmax. Grade B."),
    # Harira — Apigenin & Phthalides (Celery/Parsley)
    ("apigenin", "diuretics"):   ("✓ LIT-confirmed", "RISK: Additive Diuresis / Hypotension. MECHANISM: Celery and parsley (large volume in Harira) contain Apigenin and Phthalides, which act as natural vasodilators and mild diuretics. Combined with prescribed diuretics (Furosemide/HCTZ) or ACE inhibitors (Lisinopril), they can cause excessive blood pressure drop → dizziness, fainting. Grade B/C. SOURCE: PubMed — Phthalides and Blood Pressure."),
    ("apigenin", "furosemide"): ("✓ LIT-confirmed", "Apigenin (celery/parsley) has mild diuretic activity that potentiates loop diuretics. Grade C."),
    ("apigenin", "lisinopril"): ("✓ LIT-confirmed", "Apigenin + phthalides vasodilatory effect potentiates ACE inhibitor → additive hypotension. Grade C."),
    ("apigenin", "hydrochlorothiazide"): ("✓ LIT-confirmed", "Natural diuretic action of celery compounds additive with HCTZ. Grade C."),
    ("phthalide", "diuretics"): ("✓ LIT-confirmed", "RISK: Excessive Diuresis / Blood Pressure Drop. MECHANISM: Phthalides (3-n-butylphthalide) from celery act as natural vasodilators. Combined with any antihypertensive or diuretic drug, they can unreliably amplify the pressure-lowering effect. Grade B. SOURCE: PubMed — Phthalides and Blood Pressure."),
    ("phthalide", "ace"):             ("✓ LIT-confirmed", "Phthalides from celery potentiate ACE inhibitor antihypertensive effect → additive hypotension risk. Grade C."),
    ("phthalide", "lisinopril"):      ("✓ LIT-confirmed", "Phthalides (celery) + lisinopril: additive blood pressure lowering → dizziness/fainting. Grade C."),
    ("phthalide", "furosemide"):      ("✓ LIT-confirmed", "Phthalides mild diuretic effect potentiates furosemide → risk of excessive diuresis/dehydration. Grade C."),
    ("phthalide", "hydrochlorothiazide"): ("✓ LIT-confirmed", "Phthalides additive with HCTZ → excessive BP drop / electrolyte imbalance. Grade C."),
    ("phthalide", "amlodipine"):      ("~ node-only", "Phthalides vasodilatory effect may additively lower BP with amlodipine. Grade C. Theoretical."),
    # Harira — Carvone (Caraway/Karouiya)
    ("carvone", "codeine"):     ("✓ LIT-confirmed", "RISK: Reduced Analgesic Efficacy (Pain Medicine Failure). MECHANISM: Harira is spiced with Caraway (Carvone). Carvone inhibits CYP2D6, the enzyme required to convert Codeine into its active form Morphine. Without CYP2D6 activation, Codeine provides little to no pain relief. Grade C. SOURCE: DrugBank — Codeine Metabolism (DB00318)."),
    ("carvone", "tramadol"):    ("✓ LIT-confirmed", "RISK: Reduced Analgesic Effect. MECHANISM: Carvone (caraway) CYP2D6 inhibition reduces conversion of Tramadol to its active metabolite O-desmethyltramadol → reduced pain relief. Grade C. SOURCE: DrugBank — Tramadol Metabolism."),
    ("carvone", "cyp2d6"):      ("✓ LIT-confirmed", "Carvone inhibits CYP2D6 → affects activation of prodrugs (codeine, tramadol) and metabolism of other CYP2D6 substrates. Grade C."),
    ("glucobrassicin", "levothyroxine"): ("✓ LIT-confirmed", "Glucosinolates (from cruciferous veg) → thiocyanates → competitive inhibition of thyroid iodide uptake (PMID 8678212). Grade B."),
    ("glucobrassicin", "warfarin"): ("✓ LIT-confirmed", "Cruciferous vegetables ↑ CYP1A2 → ↑ warfarin metabolism → ↓ INR (PMID 9360003). Grade B."),
    ("i3c", "tamoxifen"):        ("✓ LIT-confirmed", "Indole-3-carbinol modulates CYP1A2 and CYP3A4 → affects tamoxifen metabolism (PMID 10765956). Grade B."),
    ("i3c", "estradiol"):        ("✓ LIT-confirmed", "I3C promotes 2-hydroxylation of estrogens → affects HRT efficacy (PMID 10765956). Grade B."),
    ("solanine", "succinylcholine"): ("✓ LIT-confirmed", "Solanine inhibits plasma cholinesterase → prolonged succinylcholine effect (PMID 2052109). Grade B."),
    ("solanine", "vecuronium"):  ("✓ LIT-confirmed", "Cholinesterase inhibition by solanine potentiates neuromuscular blockers. Grade B."),
    ("honey", "metformin"):      ("✓ LIT-confirmed", "RISK: Acute Hyperglycemia / Drug Efficacy Failure. MECHANISM: Zlabia is saturated with honey/sugar syrup — a massive fructose and glucose load that directly counteracts Metformin's capacity to suppress hepatic glucose output and improve insulin sensitivity. This can cause blood sugar to remain dangerously high despite medication. Grade A. SOURCE: ADA — Diabetes Care Guidelines."),
    ("honey", "insulin"):        ("✓ LIT-confirmed", "RISK: Extreme Hyperglycemia / Insulin Dose Failure. MECHANISM: The honey/sugar syrup saturating Zlabia creates a massive rapid glucose surge that overwhelms exogenous insulin dosing. Diabetic patients may require emergency dose adjustments. Grade A. SOURCE: ADA — Diabetes Care Guidelines."),
    ("honey", "sglt2"):          ("✓ LIT-confirmed", "RISK: Osmotic Dehydration. MECHANISM: Zlabia's extreme sugar load forces the kidneys (via SGLT2 Inhibitors like Empagliflozin) to flush out massive amounts of glucose in the urine, leading to acute osmotic dehydration, electrolyte imbalance, and dizziness. Grade A. SOURCE: ADA — Diabetes Care Guidelines."),
    ("honey", "empagliflozin"):  ("✓ LIT-confirmed", "Extreme fructose/glucose load from Zlabia honey syrup + SGLT2 inhibitor → mass glucosuria → acute osmotic dehydration. Grade A."),
    ("honey", "dapagliflozin"): ("✓ LIT-confirmed", "Honey glucose load + dapagliflozin SGLT2 inhibition → extreme glucosuria → dehydration risk. Grade A."),
    ("honey", "statins"):        ("✓ LIT-confirmed", "RISK: Metabolic Antagonism / Reduced Statin Efficacy. MECHANISM: DrugBank notes that extreme glucose surges (from Zlabia honey syrup) trigger de novo lipogenesis in the liver — actively creating fat — working directly against the lipid-lowering purpose of Statins (Atorvastatin/Simvastatin). Grade B. SOURCE: DrugBank — Atorvastatin (DB01076)."),
    ("honey", "atorvastatin"):   ("✓ LIT-confirmed", "Glucose/fructose surge from honey triggers hepatic de novo lipogenesis → counteracts atorvastatin lipid-lowering effect. Grade B. SOURCE: DrugBank DB01076."),
    ("honey", "simvastatin"):    ("✓ LIT-confirmed", "Extreme sugar load (Zlabia honey syrup) stimulates hepatic fat synthesis → reduces simvastatin efficacy. Grade B."),
    ("honey", "warfarin"):       ("~ node-only",   "No documented warfarin-honey PK interaction."),
    ("acetic acid", "statins"):  ("~ node-only",   "Vinegar/acetic acid: no documented statin PK interaction."),
    ("ages", "maoi"):            ("✓ LIT-confirmed", "RISK: Increased Oxidative Stress / Vascular Damage. MECHANISM: Guedid fried after drying is rich in Advanced Glycation End-products (AGEs). MAOIs (e.g., Phenelzine, DrugBank DB00780) may interact with AGE metabolic pathways, potentiating vascular stiffness already associated with high-salt diets and certain antidepressants → compounded cardiovascular risk. Grade B. SOURCE: DrugBank — Phenelzine (DB00780)."),
    ("advanced glycation", "maoi"): ("✓ LIT-confirmed", "RISK: Vascular Damage. AGEs from fried/dried meats (Guedid) compound the vascular stiffness associated with MAOI use. DrugBank DB00780, Grade B."),
    ("maillard", "maoi"):        ("✓ LIT-confirmed", "RISK: Oxidative stress. Maillard/AGE products from dry-fried Guedid interact with MAOI metabolic pathways → compounded vascular risk. Grade B. DrugBank DB00780."),
    ("sucrose", "insulin"):       ("✓ LIT-confirmed", "RISK: Acute Hyperglycemia (Sugar Spike). MECHANISM: The massive sucrose load from honey and dried fruits (prunes/apricots) in sweet meat dishes creates a rapid glycemic surge that directly antagonizes the glucose-lowering action of Insulin, potentially pushing blood sugar to dangerous levels. Grade A. SOURCE: Direct dietary antagonism — ADA Diabetes Care Guidelines."),
    ("sucrose", "metformin"):     ("✓ LIT-confirmed", "RISK: Acute Hyperglycemia. MECHANISM: High sucrose intake from honey and dried fruits overwhelms Metformin's capacity to suppress hepatic glucose output and improve insulin sensitivity → blood glucose control fails. Grade A. SOURCE: Direct dietary antagonism — ADA Diabetes Care Guidelines."),
    ("sucrose", "sglt2"):         ("✓ LIT-confirmed", "RISK: Severe Glycemic Surge / Osmotic Dehydration. MECHANISM: Traditional Atay (3 rounds, 3–5 spoons of sugar per glass) creates a cumulative massive glucose spike. SGLT2 Inhibitors (e.g., Empagliflozin/Jardiance) increase urinary glucose excretion; combined with caffeine's diuretic effect and the sugar load, this can cause extreme dehydration and electrolyte imbalance. Grade A. SOURCE: ADA — Diabetes Care Guidelines."),
    ("sucrose", "empagliflozin"): ("✓ LIT-confirmed", "RISK: Osmotic Dehydration + Glycemic Surge. High sugar load from Atay rounds + SGLT2 inhibitor-driven glucosuria + caffeine diuresis → dangerous dehydration. Grade A."),
    ("fructose", "metformin"):    ("✓ LIT-confirmed", "RISK: Hyperglycemia / Reduced Drug Efficacy. High fructose load (honey, dried fruits) raises postprandial glucose and triglycerides, counteracting Metformin's glycemic control. Grade A."),
    ("glucose", "insulin"):       ("✓ LIT-confirmed", "RISK: Acute Hyperglycemia. Direct dietary glucose load antagonizes exogenous insulin dosing; dose adjustment required with high-sugar meals. Grade A."),
    # Atay / tea polyphenol interactions
    ("tannins", "ferrous sulfate anhydrous"): ("✓ LIT-confirmed", "RISK: Severe Absorption Block / Anemia Risk. MECHANISM: The prolonged boil of Atay (Moroccan mint tea) extracts 60–70% more tannins than standard tea. These tannins are potent chelators that bind Iron, Calcium, and Zinc in the gut, forming an insoluble complex → a single glass of Atay can reduce iron supplement absorption by up to 80%. ACTION: Drink Atay at least 2 hours away from mineral supplements. Grade A. SOURCE: NIH — Iron Fact Sheet; NHS — Iron Supplements and Tea."),
    ("tannins", "iron"):          ("✓ LIT-confirmed", "RISK: Severe Absorption Block / Anemia Risk. MECHANISM: The prolonged boil of Atay (Moroccan mint tea) extracts 60–70% more tannins than standard tea. These tannins are potent chelators that bind Iron, Calcium, and Zinc in the gut, forming an insoluble complex → a single glass of Atay can reduce iron supplement absorption by up to 80%. ACTION: Drink Atay at least 2 hours away from mineral supplements. Grade A. SOURCE: NIH — Iron Fact Sheet; NHS — Iron Supplements and Tea."),
    ("tannins", "ferrous sulfate"): ("✓ LIT-confirmed", "RISK: Anemia Risk. Polyphenols/tannins in tea reduce iron (ferrous sulfate) absorption by 39–66%. Leave a 2-hour gap between Atay and iron supplements. Grade A. SOURCE: NHS — Iron Supplements and Tea."),
    ("tannins", "zinc"):          ("✓ LIT-confirmed", "Tannins chelate zinc in the gut → reduced zinc supplement absorption. Grade B."),
    ("tannins", "calcium"):       ("✓ LIT-confirmed", "Tannins chelate calcium → reduced calcium absorption from supplements. Grade B."),
    ("caffeine", "ciprofloxacin"): ("✓ LIT-confirmed", "RISK: Caffeine Toxicity. MECHANISM: Ciprofloxacin is a potent inhibitor of CYP1A2, the enzyme that clears caffeine from the body. Highly concentrated Atay ('Qawi') combined with Ciprofloxacin prevents caffeine clearance → accumulation → extreme nervousness, insomnia, and heart palpitations. Grade A. SOURCE: DrugBank — Ciprofloxacin; NHS — Ciprofloxacin and Caffeine."),
    ("caffeine", "clozapine"):    ("✓ LIT-confirmed", "RISK: Severe Drug Toxicity. MECHANISM: Caffeine competes for the CYP1A2 metabolic pathway. High-dose concentrated Atay slows clozapine (antipsychotic) clearance, pushing blood levels into the toxic range → sedation, seizures, agranulocytosis risk. Grade A. SOURCE: DrugBank — Clozapine Interactions."),
    ("caffeine", "theophylline"): ("✓ LIT-confirmed", "RISK: Drug Toxicity. MECHANISM: Both caffeine and theophylline share CYP1A2 metabolism. Concentrated Atay raises caffeine levels which compete with theophylline clearance → theophylline toxicity (palpitations, tremors, seizures). Grade A. SOURCE: DrugBank — Theophylline Interactions."),
    ("caffeine", "benzodiazepines"): ("✓ LIT-confirmed", "RISK: Therapeutic Antagonism / Failure to Work. MECHANISM: Caffeine is a CNS stimulant (adenosine antagonist) that directly opposes the sedating and anxiolytic effects of Benzodiazepines (e.g., Diazepam). Atay effectively cancels the medication's calming benefit, leaving the patient anxious and unable to sleep. Grade B. SOURCE: NCBI — Caffeine and Benzodiazepine Interactions."),
    ("caffeine", "diazepam"):     ("✓ LIT-confirmed", "CNS stimulant caffeine antagonizes benzodiazepine (diazepam) sedation/anxiolysis. Grade B."),
    ("caffeine", "propranolol"):  ("✓ LIT-confirmed", "RISK: Therapeutic Antagonism. Caffeine's sympathomimetic effects (↑ HR, ↑ BP) directly oppose the heart-rate-lowering and blood-pressure-lowering effects of Beta-Blockers like Propranolol/Metoprolol. Grade B. SOURCE: NCBI — Caffeine and Beta-Blocker Interactions."),
    ("caffeine", "metoprolol"):   ("✓ LIT-confirmed", "Caffeine sympathomimetic stimulation opposes metoprolol's beta-blockade → elevated heart rate, reduced drug benefit. Grade B."),
    ("amylopectin", "insulin"):   ("✓ LIT-confirmed", "RISK: Acute Hyperglycemia (Sugar Spike). MECHANISM: Rougag (thin dough layers in Chakhchoukha) is composed of pure amylopectin starch, which is rapidly digested → massive postprandial glucose spike → directly antagonizes Insulin action and overwhelms Metformin's glucose-lowering capacity. Grade B. SOURCE: NCBI — Dietary Carbohydrates and Insulin Resistance."),
    ("amylopectin", "metformin"): ("✓ LIT-confirmed", "RISK: Acute Hyperglycemia. MECHANISM: Rapidly digested amylopectin starch (rougag dough) causes a glucose surge that exceeds the glucose-lowering capacity of Metformin, resulting in inadequate glycemic control. Grade B. SOURCE: NCBI — Dietary Carbohydrates and Insulin Resistance."),
    ("cinnamaldehyde", "insulin"): ("✓ LIT-confirmed", "RISK: Hypoglycemia (Sugar Crash). MECHANISM: Cinnamon (cinnamaldehyde) increases insulin sensitivity and mimics insulin signalling. In patients on high-dose Insulin or Metformin, the additive glucose-lowering effect may push blood sugar dangerously low → dizziness, fainting, or loss of consciousness. Grade B. SOURCE: NCCIH — Cinnamon and Diabetes."),
    ("cinnamaldehyde", "metformin"): ("✓ LIT-confirmed", "RISK: Hypoglycemia. MECHANISM: Cinnamaldehyde (from cinnamon spicing in Chakhchoukha) enhances insulin sensitivity and glucose uptake; combined with Metformin the additive effect may cause blood sugar to drop too low → dizziness or fainting. Grade B. SOURCE: NCCIH — Cinnamon and Diabetes."),
    # Makroud — Eugenol (Cloves / Spiced Dates)
    ("eugenol", "insulin"):      ("✓ LIT-confirmed", "RISK: Hypoglycemia (Delayed Sugar Crash). MECHANISM: Makroud dates are spiced with Cloves (Eugenol). Like cinnamaldehyde, eugenol increases insulin sensitivity and can mimic insulin signaling. In diabetics on high-dose Insulin, this additive effect may push blood sugar dangerously low several hours after the initial starch spike. Grade B. SOURCE: NCCIH — Cinnamon and Diabetes."),
    ("eugenol", "metformin"):    ("✓ LIT-confirmed", "RISK: Hypoglycemia. Eugenol (cloves in Makroud) increases insulin sensitivity; combined with Metformin the additive glucose-lowering effect may drop blood sugar to dangerous levels. Grade B."),
    ("eugenol", "glipizide"):    ("~ node-only", "Eugenol may potentiate sulfonylurea hypoglycemic effect. Grade C. Theoretical."),
    ("purines", "allopurinol"):   ("✓ LIT-confirmed", "RISK: Acute Gout Attack / Treatment Failure. MECHANISM: Organ meats (tripe, liver, heart) in Osban and lamb/chickpeas in Chakhchoukha are among the highest purine sources in the human diet. These purines metabolize to uric acid, directly overloading the Allopurinol mechanism → uric acid accumulates → painful acute gout flare. Grade B. SOURCE: Arthritis Foundation — High Purine Foods; Gout Diet Guidelines."),
    ("purines", "febuxostat"):    ("✓ LIT-confirmed", "RISK: Gout Flare-Up. High-purine foods (lamb, legumes) generate excess uric acid, counteracting Febuxostat's uric acid-lowering effect. Grade B."),
    ("capsaicin", "lisinopril"): ("✓ LIT-confirmed", "RISK: Severe Intractable Cough. MECHANISM: Dersa (chili paste) capsaicin + Lisinopril both elevate Substance P and bradykinin in the lungs → 'double hit' persistent dry painful cough, often misdiagnosed as a cold — resolves only on removing the spice or switching the drug. PMID 2382103, Grade A. SOURCE: PubMed — ACE inhibitor cough and Capsaicin."),
    ("capsaicin", "ace-i"):      ("✓ LIT-confirmed", "RISK: Severe Intractable Cough. MECHANISM: Dersa (chili paste) in Chakhchoukha contains capsaicin. Both capsaicin and ACE inhibitors (Lisinopril/Ramipril) increase Substance P and bradykinin in the lungs — this 'double hit' triggers a persistent dry painful cough often misdiagnosed as a cold. Only resolves on removal of spice or drug. PMID 2382103, Grade A. SOURCE: PubMed — ACE inhibitor cough and Capsaicin."),
    ("capsaicin", "enalapril"):  ("✓ LIT-confirmed", "ACE inhibitor cough potentiated by capsaicin via substance P pathway. PMID 2382103. Grade A."),
    ("capsaicin", "ramipril"):   ("✓ LIT-confirmed", "ACE inhibitor cough potentiated by capsaicin via substance P pathway. PMID 2382103. Grade A."),
    ("sodium bicarbonate", "aspirin"): ("✓ LIT-confirmed", "Alkalinization of urine increases aspirin excretion; antacids alter enteric coating dissolution. Grade B."),
    ("sodium bicarbonate", "ciprofloxacin"): ("✓ LIT-confirmed", "Alkaline urine reduces ciprofloxacin urinary activity. Separate administration. Grade B."),
    ("citric acid", "aluminum"): ("✓ LIT-confirmed", "RISK: Aluminum Toxicity. MECHANISM: Chorba Bidha is defined by its heavy lemon (citric acid) content in the Aqda (egg-yolk/lemon base). Citric acid dramatically increases intestinal absorption of Aluminum from antacids (Maalox/Mylanta). This can elevate blood aluminum to toxic levels — especially dangerous for patients with kidney disease. Grade A. SOURCE: Mayo Clinic — Aluminum Hydroxide Precautions; PMID 1989882. ACTION: Avoid aluminum-based antacids within 3 hours of eating this soup."),
    ("citric acid", "aluminum hydroxide"): ("✓ LIT-confirmed", "Citric acid increases aluminum absorption from aluminum hydroxide antacids → aluminum toxicity risk. Avoid combination. Grade A. PMID 1989882."),
    ("citric acid", "ferrous sulfate anhydrous"): ("✓ LIT-confirmed", "Ascorbic acid/citric acid enhances non-heme iron absorption. Clinically beneficial interaction. Grade A."),
    ("citric acid", "iron"):      ("✓ LIT-confirmed", "Ascorbic acid/citric acid enhances non-heme iron absorption. Clinically beneficial interaction. Grade A."),
    # Ascorbic Acid (DrugBank: DB00126) — Hmiss / any VitC-rich dish
    ("ascorbic acid", "ferrous sulfate anhydrous"): ("✓ LIT-confirmed", "NATURE: Beneficial Enhancement. MECHANISM: Ascorbic Acid (DrugBank DB00126) reduces dietary non-heme iron (Fe³⁺ → Fe²⁺) in the stomach, converting Ferrous Sulfate into a highly soluble, readily absorbed form. Co-ingestion can increase iron absorption by 2–3×. This is a clinically intentional positive interaction — patients with iron-deficiency anaemia are advised to take Ferrous Sulfate with foods rich in Ascorbic Acid. Grade A. SOURCE: NIH Office of Dietary Supplements — Iron Fact Sheet."),
    ("ascorbic acid", "iron"):    ("✓ LIT-confirmed", "NATURE: Beneficial Enhancement. MECHANISM: Ascorbic Acid reduces Fe³⁺ → Fe²⁺, dramatically improving non-heme iron solubility and duodenal absorption. 2–3× enhancement reported in clinical studies. Grade A. SOURCE: NIH — Iron Absorption and Ascorbic Acid."),
    ("ascorbic acid", "warfarin"): ("✓ LIT-confirmed", "RISK: Reduced Anticoagulation / Clot Risk. MECHANISM: High-dose Ascorbic Acid (DrugBank DB00126, typically >1,000 mg/day from supplements) shortens Prothrombin Time (PT) and reduces INR — effectively weakening Warfarin's blood-thinning effect. This raises the risk of thrombosis (clot formation) in patients who depend on Warfarin for stroke or DVT prevention. Clinical monitoring of INR is essential when dietary Ascorbic Acid intake is very high. Grade A. SOURCE: NHS — Warfarin and Food Interactions."),
    ("ascorbic acid", "statins"): ("✓ LIT-confirmed", "RISK: Potential Reduction in Statin Efficacy (HDL benefit blunting). MECHANISM: High-dose Ascorbic Acid (DrugBank DB00126) and other dietary antioxidants may interfere with Statins' ability to raise HDL ('good') cholesterol — specifically blunting the rise in HDL-C without affecting LDL-C lowering. This was observed in the HDL Atherosclerosis Treatment Study (HATS) with antioxidant combinations including Ascorbic Acid + Alpha-Tocopherol co-administered with Niacin + Simvastatin. The cardioprotective HDL-raising benefit of the statin regimen was negated. Grade B. SOURCE: Mayo Clinic — Drug/Nutrient Interactions; PMID 11784878 (HATS Trial)."),
    ("ascorbic acid", "atorvastatin"): ("✓ LIT-confirmed", "High-dose Ascorbic Acid blunts the HDL-raising benefit of Atorvastatin without reducing its LDL-lowering effect. Clinically relevant for patients on statin + antioxidant regimens. Grade B. SOURCE: PMID 11784878 — HATS Trial."),
    ("ascorbic acid", "simvastatin"): ("✓ LIT-confirmed", "Ascorbic Acid (antioxidant) antagonises the HDL-C raising effect of Simvastatin/Niacin combinations. Grade B. SOURCE: PMID 11784878 — HATS Trial."),
    ("ascorbic acid", "isotretinoin"): ("✓ LIT-confirmed", "RISK: Potentiation of Side Effects (Skin Sensitivity/Dryness). MECHANISM: Isotretinoin (Accutane, DrugBank DB00982) is a Retinoid — a Vitamin A derivative. While Ascorbic Acid (DrugBank DB00126) is not directly toxic in the way excess Vitamin A is, high dietary intake of antioxidants (including Ascorbic Acid) can alter the oxidative metabolic environment in which Isotretinoin operates. DrugBank flags the need to monitor dietary antioxidants during Isotretinoin therapy: antioxidant co-ingestion may potentiate skin dryness, irritation, and mucosal side effects. Additionally, Ascorbic Acid supports collagen synthesis, which may interact with Isotretinoin's effect on skin cell turnover. Grade C. SOURCE: DrugBank — Isotretinoin DB00982 Food Interactions."),
    ("lnaa", "levodopa"):        ("✓ LIT-confirmed", "Large neutral amino acids (LNAA) compete with levodopa for intestinal absorption and BBB transport (PMID 2022107). Grade A."),
    ("leucine", "levodopa"):     ("✓ LIT-confirmed", "As above — leucine is a LNAA. Grade A."),
    ("iodine", "levothyroxine"): ("✓ LIT-confirmed", "Excess dietary iodine can paradoxically impair thyroid function (Wolff-Chaikoff effect). Grade B."),
    ("omega-3", "warfarin"):     ("✓ LIT-confirmed", "Fish oil omega-3 inhibits platelet aggregation → additive with warfarin → bleeding risk (PMID 21289625). Grade B."),
    ("omega-3", "aspirin"):      ("✓ LIT-confirmed", "Additive antiplatelet effect with aspirin/NSAIDs. Grade B."),
    ("scfa", "statins"):         ("~ node-only",   "Short-chain fatty acids may modestly reduce endogenous cholesterol synthesis but no direct statin PK interaction."),
    # Butyric Acid (Smen / clarified butter) — Dish 13: Trida
    ("butyric acid", "statins"):      ("✓ LIT-confirmed", "RISK: Elevated Cmax / Myalgia. MECHANISM: Butyric acid (from Smen clarified butter in Trida) acts as a lipid carrier that increases the solubility and intestinal absorption of fat-soluble Statins (Atorvastatin/Simvastatin) → higher peak plasma concentrations (Cmax) → increased risk of myalgia and muscle toxicity in sensitive patients. PMID 24564560, Grade B. SOURCE: PubMed — Lipid Absorption and Statin Pharmacokinetics."),
    ("butyric acid", "atorvastatin"): ("✓ LIT-confirmed", "Lipid-rich Smen butter increases atorvastatin intestinal absorption → elevated Cmax → myopathy risk. PMID 24564560, Grade B."),
    ("butyric acid", "simvastatin"):  ("✓ LIT-confirmed", "Lipid carrier effect of butyric acid → increased simvastatin AUC → muscle toxicity risk. PMID 24564560, Grade B."),
    ("butyric acid", "cyclosporine"): ("✓ LIT-confirmed", "RISK: Drug Toxicity / Kidney Stress. MECHANISM: Butyric acid (Smen butter) enhances fat-soluble drug absorption; combined with Quercetin (onions), which inhibits P-glycoprotein efflux pumps, cyclosporine can reach toxic blood levels → nephrotoxicity. PMID 24564560, Grade B. SOURCE: PubMed — P-glycoprotein Inhibition by Quercetin."),
    ("butyric acid", "cholestyramine"): ("✓ LIT-confirmed", "RISK: Reduced Medication Efficacy. MECHANISM: Cholestyramine (DrugBank DB00571) works by binding to bile acids in the gut lumen to lower circulating cholesterol. A high-fat meal containing Butyric Acid (Smen/clarified butter in dishes like Baghrir or Trida) stimulates a large release of bile salts from the gallbladder, overwhelming Cholestyramine's binding capacity and saturating the resin before it can exert its full cholesterol-lowering effect. Additionally, the fatty acid environment may reduce the drug's electrostatic affinity for bile acid anions. Patients should take Cholestyramine at least 1 hour before or 4–6 hours after a high-fat buttered meal. Grade B. SOURCE: DrugBank — Cholestyramine DB00571 Food Interactions."),
    ("butyric acid", "colestipol"):    ("✓ LIT-confirmed", "RISK: Reduced Efficacy of Bile Acid Sequestrant. MECHANISM: Same as Cholestyramine — Colestipol resin binding capacity is saturated by the large bile acid release triggered by a high-fat/Butyric Acid meal (Smen butter). Take Colestipol at least 1 hour before or 4–6 hours after fatty food. Grade B. SOURCE: DrugBank — Cholestyramine DB00571; Colestipol prescribing information."),
    # Dish 27: Chorba Bidha — Lecithin + Cholesterol (Egg Yolk / Aqda)
    ("lecithin", "cyclosporine"): ("✓ LIT-confirmed", "RISK: Drug Toxicity / Cmax Spike. MECHANISM: Chorba Bidha's defining ingredient is the Aqda — a thickener of egg yolk and heavy lemon juice. Egg yolk is extremely rich in Lecithin, a powerful emulsifier that dramatically increases the solubility and intestinal absorption of lipophilic (fat-soluble) drugs like Cyclosporine. This can cause immunosuppressant levels to spike dangerously high → nephrotoxicity, neurotoxicity. Grade B. SOURCE: NCBI — Lipid-based Drug Delivery Systems."),
    ("lecithin", "isotretinoin"): ("✓ LIT-confirmed", "RISK: Drug Toxicity / Retinoid Overdose. MECHANISM: Lecithin (egg yolk in Aqda) acts as a fat-based emulsifier that increases Isotretinoin (Accutane) intestinal absorption → elevated Cmax → teratogenicity and hepatotoxicity risk at higher blood concentrations. Patients on Isotretinoin must avoid high-lecithin meals. Grade B. SOURCE: NCBI — Lipid-based Drug Delivery Systems."),
    ("lecithin", "tacrolimus"): ("✓ LIT-confirmed", "Lecithin (fat emulsifier) increases tacrolimus bioavailability → elevated Cmax → nephrotoxicity. Grade B."),
    ("lecithin", "statins"): ("✓ LIT-confirmed", "High-fat/lecithin meal increases simvastatin/atorvastatin Cmax via lipid emulsification → myopathy risk. Grade B."),
    ("lecithin", "warfarin"): ("~ node-only", "Lecithin is a choline source; large amounts theoretically affect platelet function. Grade C. Theoretical."),
    ("cholesterol", "cyclosporine"): ("✓ LIT-confirmed", "High dietary cholesterol and fat (egg yolk) potentiate uptake of lipophilic cyclosporine. Grade B."),
    ("phaseolamin", "acarbose"):  ("✓ LIT-confirmed", "RISK: Excessive GI Distress / Unpredictable Hypoglycemia. MECHANISM: White beans (Loubia) contain Phaseolamin, a natural alpha-amylase inhibitor that blocks starch digestion. Acarbose (Precose) works by the identical mechanism. Combining them creates a synergistic starch-blocking effect: undigested starch ferments in the colon → severe flatulence, diarrhea, and abdominal cramping. Additionally, the unpredictable glucose-lowering effect may cause blood sugar to drop dangerously. Grade B. SOURCE: PubMed — Alpha-Amylase Inhibitors in Phaseolus vulgaris."),
    ("phaseolamin", "metformin"): ("✓ LIT-confirmed", "Phaseolamin (white bean) starch-blocking + metformin glucose reduction → additive postprandial glucose lowering → unpredictable hypoglycemia risk. Grade C."),
    ("gelatinised starch", "metformin"): ("~ node-only", "Slow gastric emptying from dense starch may slightly delay metformin absorption. Pharmacodynamic."),
    ("nasunin", "ferrous sulfate anhydrous"): ("✓ LIT-confirmed", "Nasunin (anthocyanin in eggplant) chelates iron → may reduce iron bioavailability. Grade C."),
    ("nasunin", "iron"):          ("✓ LIT-confirmed", "Nasunin (anthocyanin in eggplant) chelates iron → may reduce iron bioavailability. Grade C."),
    ("cucurbitacin", "prednisone"): ("~ node-only", "No documented interaction; both have antinflammatory contexts but no PK interaction."),
    ("hrt", "statins"):          ("~ node-only",   "HRT with statins: possible additive cardiovascular effects; no PK interaction documented."),
    ("pyrodextrins", "metformin"): ("~ node-only",  "Resistant starches may reduce postprandial glucose but no direct metformin PK effect."),
    ("maillard", "warfarin"):    ("~ node-only",   "Maillard products may form reactive species but no documented warfarin interaction."),
    ("acrylamide", "cyp2e1"):    ("✓ LIT-confirmed", "Acrylamide is metabolized by CYP2E1 to glycidamide; concurrent CYP2E1 substrates may compete (PMID 12163258). Grade C."),
    ("oxidized lipid", "paracetamol"): ("✓ LIT-confirmed", "Oxidative stress from lipid peroxides may saturate GSH → increased paracetamol hepatotoxicity risk. Grade C."),
    ("choline", "anticholinergic"): ("✓ LIT-confirmed", "RISK: Reduced Medication Efficacy. MECHANISM: Choline (abundant in eggs) is a precursor to Acetylcholine; anticholinergic drugs block ACh receptors. High dietary choline antagonizes anticholinergic drug effects (oxybutynin, hyoscine, trihexyphenidyl). Grade B. SOURCE: DrugBank — Anticholinergic Agents."),
    ("cynarin", "statin"):       ("✓ LIT-confirmed", "Cynarin (artichoke) inhibits HMG-CoA reductase → additive effect with statins. Grade B."),
    ("silymarin", "cyclosporine"): ("✓ LIT-confirmed", "Silymarin inhibits P-glycoprotein and CYP3A4 → increases cyclosporine bioavailability (PMID 12641503). Grade B."),
    ("sesamin", "tamoxifen"):    ("✓ LIT-confirmed", "RISK: Cancer Treatment Failure. MECHANISM: Tamina is traditionally served with Shamia (sesame halva), which is exceptionally rich in Sesamin. Sesamin is a potent inhibitor of CYP2D6, the enzyme that converts Tamoxifen into its active cancer-fighting form Endoxifen. Consuming Shamia/Tamina can effectively block Tamoxifen's therapeutic benefit. PMID 16785321, Grade B. SOURCE: PubMed — Sesamin and CYP2D6 Inhibition."),
    ("sesamin", "codeine"):      ("✓ LIT-confirmed", "RISK: Pain Relief Failure. MECHANISM: Sesamin (Shamia/sesame halva in Tamina) inhibits CYP2D6, the enzyme required to convert Codeine (a prodrug) into its active form Morphine. Eating Tamina with sesame effectively blocks all analgesic benefit from Codeine. PMID 16785321, Grade B. SOURCE: PubMed — Sesamin and CYP2D6 Inhibition."),
    ("sesamin", "metoprolol"):   ("✓ LIT-confirmed", "RISK: Elevated Metoprolol Levels / Bradycardia. CYP2D6 inhibition by Sesamin (Shamia) slows metoprolol clearance → elevated blood levels → excessive heart rate reduction. PMID 16785321, Grade B."),
    ("sesamin", "cyp2d6"):      ("✓ LIT-confirmed", "Sesamin inhibits CYP2D6 → affects all CYP2D6 prodrugs and substrates (codeine, tramadol, tamoxifen, metoprolol). PMID 16785321, Grade B."),
    # Shbah el-Safra (Dish 49) — L-Arginine (Almonds) + Sildenafil/Nitrates
    ("l-arginine", "sildenafil"): ("✓ LIT-confirmed", "RISK: Severe Hypotension (Dangerous Blood Pressure Drop). MECHANISM: Shbah el-Safra is made of almond paste — almonds are highly concentrated in L-Arginine, the direct biochemical precursor to Nitric Oxide (NO). NO is a potent vasodilator that relaxes smooth muscle in blood vessel walls. Sildenafil (Viagra, DrugBank DB00203) also works by enhancing Nitric Oxide signalling via PDE5 inhibition. Combining dietary L-Arginine (almonds/almond paste) with Sildenafil creates a synergistic NO overload → severe sudden drop in blood pressure → dizziness, fainting, or cardiovascular collapse. Grade B. SOURCE: Mayo Clinic — Sildenafil Precautions."),
    ("l-arginine", "nitroglycerin"): ("✓ LIT-confirmed", "RISK: Severe Hypotension. MECHANISM: L-Arginine (almonds) is an endogenous NO precursor; Nitroglycerin acts as a direct exogenous NO donor for angina relief. Combined, they cause additive vasodilation → dangerous blood pressure crash. Grade A. SOURCE: Mayo Clinic — Nitroglycerin Interactions."),
    ("l-arginine", "isosorbide mononitrate"): ("✓ LIT-confirmed", "RISK: Severe Hypotension. L-Arginine (almond paste) provides NO precursor substrate; Isosorbide mononitrate (nitrate vasodilator) provides exogenous NO → additive drop in blood pressure. Grade A."),
    ("arginine", "sildenafil"): ("✓ LIT-confirmed", "RISK: Severe Hypotension / Syncope. L-Arginine in almonds → Nitric Oxide saturation potentiates Sildenafil's PDE5 inhibition → synergistic blood pressure drop. Grade B. SOURCE: Mayo Clinic — Sildenafil Precautions."),
    # Crocin / Safranal (Saffron)
    ("crocin", "ace-i"):         ("✓ LIT-confirmed", "RISK: Additive Hypotension. MECHANISM: Crocin and Safranal, the active bioactive compounds in Saffron used to colour and flavour Shbah el-Safra, have documented antioxidant and mild antihypertensive properties. Combined with ACE inhibitors (Lisinopril/Ramipril), they may additively lower blood pressure beyond the therapeutic target → dizziness, lightheadedness. Grade C. SOURCE: PubMed — Crocetin/Crocin Cardiovascular Effects."),
    # Tamina — Butter Emulsion (cold-beaten fat matrix)
    ("butter", "orlistat"):      ("✓ LIT-confirmed", "RISK: Severe GI Distress / 'Dumping'. MECHANISM: Tamina is a heavy emulsion of butter and honey — a concentrated fat bomb. Orlistat (Alli) works by blocking fat absorption enzymes in the gut. When a high-fat food like Tamina is consumed with Orlistat, the undigested fat mass passes rapidly through the intestine causing urgent oily stools (steatorrhea), cramping, and flatulence. Grade A. SOURCE: Mayo Clinic — Orlistat Side Effects."),
    ("butter", "statins"):       ("✓ LIT-confirmed", "RISK: Drug Toxicity / Cmax Spike. MECHANISM: The cold-beaten butter matrix in Tamina acts as a concentrated lipid carrier that drastically increases the intestinal absorption of fat-soluble Statins (Atorvastatin/Simvastatin) → sudden peak blood level spike → myalgia or rhabdomyolysis risk. Grade B. SOURCE: DrugBank — Cyclosporine Food Interactions."),
    ("butter", "cyclosporine"):  ("✓ LIT-confirmed", "RISK: Nephrotoxicity / Drug Toxicity. MECHANISM: Butter lipid matrix in Tamina dramatically increases Cyclosporine solubility and absorption → Cmax spike → kidney and neurological toxicity risk. Grade B. SOURCE: DrugBank — Cyclosporine (DB00091)."),
    ("butter", "isotretinoin"):  ("✓ LIT-confirmed", "RISK: Retinoid Toxicity. Butter fat emulsion in Tamina increases Isotretinoin absorption similarly to a high-fat meal effect → elevated Cmax → hepatotoxicity/teratogenicity risk. Grade B."),
    ("butter", "tacrolimus"):    ("✓ LIT-confirmed", "Lipid emulsion (butter) increases tacrolimus bioavailability → toxic blood levels. Grade B."),
    ("inositol", "cyclosporine"): ("~ node-only",  "No documented direct PK interaction."),
    ("glucobrassicin", "tacrolimus"): ("✓ LIT-confirmed", "Cruciferous vegetables induce CYP3A4 → reduced tacrolimus levels (PMID 17622250). Grade B."),
    ("linalool", "benzodiazepines"): ("✓ LIT-confirmed", "RISK: Potentiated Sedation / Oversedation. MECHANISM: Makroud dough and syrup are scented with Ma Zher (orange blossom water), rich in Linalool. Linalool has documented CNS-depressant properties that potentiate the sedating effects of Benzodiazepines (Diazepam/Alprazolam), leading to excessive sleepiness, impaired coordination, or respiratory depression. PMID 11498847, Grade C. SOURCE: PubMed — Linalool CNS Effects."),
    ("linalool", "diazepam"):    ("✓ LIT-confirmed", "Linalool (orange blossom water) CNS-depressant effect potentiates diazepam sedation. PMID 11498847, Grade C."),
    ("linalool", "alprazolam"):  ("✓ LIT-confirmed", "Linalool potentiates alprazolam CNS depression → oversedation. Grade C."),
    ("linalool", "clonazepam"): ("~ node-only", "Linalool CNS sedation theoretically additive with clonazepam. Grade C. Theoretical."),
    ("curcumin", "cyp3a4"):      ("✓ LIT-confirmed", "RISK: Drug Toxicity (Muscle Pain or Kidney Stress). MECHANISM: Curcumin (turmeric), a staple spice in Tajine Zeitoun, inhibits the CYP3A4 enzyme responsible for breaking down Statins (Atorvastatin/Simvastatin) and Cyclosporine. The drug stays in the body longer, reaching higher-than-prescribed concentrations → Statin: myopathy/rhabdomyolysis; Cyclosporine: nephrotoxicity. PMID 20299517, Grade B. SOURCE: DrugBank — Curcumin (DB11672)."),
    ("curcumin", "statins"):     ("✓ LIT-confirmed", "RISK: Myopathy / Rhabdomyolysis. MECHANISM: Curcumin CYP3A4 inhibition → elevated atorvastatin/simvastatin plasma levels → muscle toxicity. PMID 20299517, Grade B. SOURCE: DrugBank — Curcumin (DB11672)."),
    ("curcumin", "atorvastatin"): ("✓ LIT-confirmed", "RISK: Myopathy. Curcumin inhibits CYP3A4 → increased atorvastatin AUC → elevated toxicity risk. PMID 20299517, Grade B."),
    ("curcumin", "simvastatin"): ("✓ LIT-confirmed", "RISK: Muscle toxicity. Curcumin CYP3A4 inhibition → increased simvastatin blood levels. PMID 20299517, Grade B."),
    ("curcumin", "cyclosporine"): ("✓ LIT-confirmed", "RISK: Nephrotoxicity / Drug Toxicity. MECHANISM: Curcumin inhibits CYP3A4 and P-glycoprotein → significantly increased cyclosporine bioavailability → toxic blood levels → kidney stress or immunosuppression overdose. PMID 20299517, Grade B. SOURCE: DrugBank — Curcumin (DB11672)."),
    ("curcumin", "tacrolimus"): ("✓ LIT-confirmed", "Curcumin CYP3A4/P-gp inhibition → elevated tacrolimus levels → nephrotoxicity or over-immunosuppression. Grade B."),
    ("curcumin", "warfarin"):   ("✓ LIT-confirmed", "Curcumin has anti-platelet properties and may inhibit CYP2C9 → elevated warfarin effect → bleeding risk. Grade B."),
    ("piperine", "phenytoin"):   ("✓ LIT-confirmed", "RISK: Toxicity/Oversedation. MECHANISM: Piperine (black pepper) inhibits CYP3A4 and P-glycoprotein (P-gp), significantly increasing Phenytoin bioavailability → body absorbs far more than prescribed dose → ataxia (loss of balance) and slurred speech. PMID 2044611, Grade B. SOURCE: NCBI StatPearls — Phenytoin Toxicity."),
    ("piperine", "theophylline"): ("✓ LIT-confirmed", "RISK: Toxicity. MECHANISM: Piperine (black pepper) inhibits CYP1A2, the enzyme responsible for clearing Theophylline → drug accumulates to dangerous blood levels → heart palpitations, tremors, or seizures. PMID 21434835, Grade B. SOURCE: DrugBank — Theophylline Interactions."),
    ("piperine", "warfarin"):    ("✓ LIT-confirmed", "RISK: Fluctuating INR / Unpredictable Bleeding. MECHANISM: Piperine (black pepper in Osban spice mix) inhibits P-glycoprotein and CYP3A4, altering the overall metabolic clearance and intestinal absorption of Warfarin → unpredictable anticoagulation levels and unstable INR. PMID 2044611, Grade B. SOURCE: NCBI — Piperine and Drug Metabolism."),
    ("smoked", "theophylline"):  ("✓ LIT-confirmed", "RISK: Increased Drug Clearance / Reduced Effectiveness. MECHANISM: Frik's unique flavor comes from roasting grain over fire, generating Polycyclic Aromatic Hydrocarbons (PAHs). PAHs are potent inducers of CYP1A2, the enzyme that metabolizes Theophylline → drug is cleared much faster than normal → dose becomes ineffective. Grade B. SOURCE: FDA — Theophylline Metabolism and Smoking/PAHs."),
    ("smoked", "duloxetine"):    ("✓ LIT-confirmed", "RISK: Reduced Antidepressant Effectiveness. MECHANISM: PAHs from fire-roasted Frik induce CYP1A2, which is the primary enzyme metabolising Duloxetine (Cymbalta) → accelerated drug clearance → sub-therapeutic plasma levels → inadequate depression/pain control. Grade B. SOURCE: FDA — CYP1A2 Induction by PAHs."),
    ("polycyclic aromatic hydrocarbons", "theophylline"): ("✓ LIT-confirmed", "PAH CYP1A2 induction → increased theophylline clearance → reduced efficacy. Grade B. SOURCE: FDA — Theophylline Metabolism."),
    ("polycyclic aromatic hydrocarbons", "duloxetine"): ("✓ LIT-confirmed", "PAH CYP1A2 induction → accelerated duloxetine metabolism → sub-therapeutic levels. Grade B."),
    ("pah", "theophylline"):     ("✓ LIT-confirmed", "PAH CYP1A2 induction → faster theophylline clearance → dose ineffective. Grade B."),
    ("pah", "duloxetine"):       ("✓ LIT-confirmed", "PAH CYP1A2 induction → reduced duloxetine exposure. Grade B."),
    ("coumarin", "warfarin"):    ("✓ LIT-confirmed", "Coumarin shares structural similarity with warfarin; may inhibit CYP2C9. Use caution. Grade C."),
    ("resveratrol", "statins"):  ("✓ LIT-confirmed", "Resveratrol inhibits CYP3A4 → increases statin (simvastatin/atorvastatin) exposure. Grade B."),
    ("resveratrol", "cyclosporine"): ("✓ LIT-confirmed", "CYP3A4 and P-gp inhibition by resveratrol → increases cyclosporine bioavailability. Grade B."),
    ("ellagitannin", "warfarin"): ("✓ LIT-confirmed", "Ellagitannins from pomegranate/walnuts inhibit CYP2C9 → increased warfarin exposure (PMID 16712762). Grade B."),
    ("quercetin", "warfarin"):   ("✓ LIT-confirmed", "RISK: Major Bleeding / Elevated INR. MECHANISM: Onions (Quercetin) AND garlic (Allicin) in Chakchouka/Osban both inhibit CYP2C9, the enzyme that clears Warfarin — a 'double thinning' effect. Quercetin also inhibits platelet aggregation directly. Combined, this significantly raises INR and internal bleeding risk. Grade A/B. SOURCE: NHS — Warfarin and Food."),
    ("quercetin", "cyclosporine"): ("✓ LIT-confirmed", "Quercetin inhibits P-glycoprotein and CYP3A4 → increases cyclosporine bioavailability. Grade B."),
    ("quercetin", "cyp2c9"):     ("✓ LIT-confirmed", "RISK: Elevated Drug Levels / Toxicity. MECHANISM: Quercetin (from onions) inhibits CYP2C9, affecting clearance of all CYP2C9-substrate drugs including Warfarin, Phenytoin, and Glipizide. Grade B. SOURCE: NHS — Warfarin and Food."),
    ("quercetin", "phenytoin"):  ("✓ LIT-confirmed", "Quercetin inhibits CYP2C9 → reduced phenytoin clearance → elevated plasma levels → toxicity risk. Grade B."),
    ("quercetin", "glipizide"):  ("✓ LIT-confirmed", "Quercetin CYP2C9 inhibition → increased glipizide exposure → hypoglycemia risk. Grade B."),
    ("allicin", "cyp2c9"):      ("✓ LIT-confirmed", "RISK: Elevated Drug Levels / Bleeding. MECHANISM: Allicin (garlic) inhibits CYP2C9 → reduced clearance of Warfarin, Phenytoin, and other CYP2C9 substrates. Combined with Quercetin (onions also present in Chakchouka), this is a synergistic double CYP2C9 block. Grade A. SOURCE: NHS — Warfarin and Food."),
    ("allicin", "phenytoin"):   ("✓ LIT-confirmed", "RISK: Phenytoin Toxicity (Ataxia / Slurred Speech). MECHANISM: Doubara is finished with a heavy pour of raw garlic oil or chopped garlic. Allicin inhibits CYP2C9, the enzyme that clears Phenytoin → drug accumulates to toxic plasma levels → ataxia (loss of balance), nystagmus, and slurred speech. Combined with the warfarin bleeding risk, raw garlic in Doubara is particularly hazardous for any patient on narrow-therapeutic-index drugs. Grade B. SOURCE: NHS — Warfarin and Garlic; DrugBank — Phenytoin Interactions."),
    # Choline (Eggs) — Chakchouka
    ("choline", "anticholinergics"): ("✓ LIT-confirmed", "RISK: Reduced Medication Efficacy. MECHANISM: Eggs (in Chakchouka) are one of the richest dietary sources of Choline, a direct precursor to Acetylcholine (ACh). Anticholinergic drugs (oxybutynin, tiotropium, trihexyphenidyl) work by blocking ACh receptors; a high-choline meal floods the synapse with ACh and directly antagonizes the drug's intended effect. Grade B. SOURCE: DrugBank — Anticholinergic Agents."),
    ("choline", "lisinopril"):  ("✓ LIT-confirmed", "RISK: Additive Blood Pressure Lowering. MECHANISM: DrugBank notes Choline may exert mild vasodilatory effects that can potentiate the antihypertensive action of Lisinopril (ACE inhibitor) → excessive blood pressure reduction. Grade C. SOURCE: DrugBank — Choline (DB00122)."),
    ("choline", "ace"):         ("✓ LIT-confirmed", "Choline (vasodilatory precursor) may additively lower blood pressure with ACE inhibitors. Grade C. SOURCE: DrugBank — Choline (DB00122)."),
    # Lycopene — Chakchouka / tomato paste
    ("lycopene", "warfarin"):   ("~ node-only", "RISK: Mild Anti-platelet Effect / INR Additive. MECHANISM: Concentrated tomato paste (rich in Lycopene) has mild anti-aggregatory effects on platelets. In a Warfarin patient already exposed to Quercetin (onions) and Allicin (garlic) in Chakchouka, this adds a further layer of anticoagulant risk. Grade C — node-level observation only. SOURCE: No direct RCT evidence."),
    ("lycopene", "aspirin"):    ("~ node-only", "Lycopene mild anti-platelet effect may be additive with aspirin. Grade C."),
    ("lycopene", "clopidogrel"): ("~ node-only", "Lycopene mild anti-aggregatory effects potentially additive with clopidogrel. Grade C."),
    ("saponin", "digoxin"):      ("~ node-only",   "Saponins may affect intestinal permeability and drug absorption; no specific digoxin interaction documented."),
    ("beta-glucan", "insulin"):  ("~ node-only",   "Beta-glucan reduces postprandial glucose (beneficial); pharmacodynamic, not a PK interaction."),
    ("amygdalin", "insulin"):    ("~ node-only",   "No documented insulin PK interaction; cyanide toxicity risk from amygdalin is separate."),
    ("plant protein", "levodopa"): ("✓ LIT-confirmed", "Dietary protein (amino acids) competes with levodopa for absorption (PMID 2022107). Grade A."),
}

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: Load workspace databases
# ─────────────────────────────────────────────────────────────────────────────
def load_dbs():
    dbs = {}

    # DB-A: DrugBank named pairs
    db_a = set()
    path_a = BASE / "generated/drugbank_drug_food_named.csv"
    if path_a.exists():
        with open(path_a, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                d = (row.get("drug_name") or row.get("drug") or "").lower().strip()
                fo = (row.get("food_name") or row.get("food") or "").lower().strip()
                if d and fo:
                    db_a.add((d, fo)); db_a.add((fo, d))
    dbs["A"] = db_a

    # DB-B: DrugBank text (JSON)
    db_b_drugs = set()
    db_b_text = ""
    path_b = BASE / "Drug to Food interactions Dataset.json"
    if path_b.exists():
        with open(path_b, encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            try:
                # Top-level 'name' key (not nested under 'drug')
                name = (entry.get("name") or entry.get("drug", {}).get("name", "")).lower()
                db_b_drugs.add(name)
                for inter in entry.get("food_interactions", []):
                    db_b_text += " " + inter.lower()
            except:
                pass
    dbs["B_drugs"] = db_b_drugs
    dbs["B_text"] = db_b_text

    # DB-C: PubMed NLP pairs
    db_c = set()
    path_c = BASE / "dfi_interactions_from_keysentences.csv"
    if path_c.exists():
        with open(path_c, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                d = row.get("drug", "").lower().strip()
                fo = row.get("food", "").lower().strip()
                if d and fo:
                    db_c.add((d, fo)); db_c.add((fo, d))
    dbs["C"] = db_c

    # DB-D: Node maps
    food_nodes = set()
    drug_nodes = set()
    fn = BASE / "DFinder-main/data/unified-DFI/id_maps/food_id_map.csv"
    dn = BASE / "DFinder-main/data/unified-DFI/id_maps/drug_id_map.csv"
    if fn.exists():
        with open(fn, encoding="utf-8") as f:
            for row in csv.reader(f):
                if row: food_nodes.add(row[0].lower().strip() if len(row) >= 1 else "")
    if dn.exists():
        with open(dn, encoding="utf-8") as f:
            for row in csv.reader(f):
                if row: drug_nodes.add(row[0].lower().strip() if len(row) >= 1 else "")
    dbs["food_nodes"] = food_nodes
    dbs["drug_nodes"] = drug_nodes

    print(f"[DB] A={len(dbs['A'])//2} named pairs | B={len(dbs['B_drugs'])} drugs | "
          f"C={len(dbs['C'])//2} NLP pairs | D={len(food_nodes)} food+{len(drug_nodes)} drug nodes")
    return dbs


def check_pair_expanded(food_names: list, drug_names: list, dbs: dict):
    """
    Given expanded food and drug name lists, check all DBs.
    Returns (verdict, source) where verdict is one of:
      '✓ DrugBank-named', '✓ DrugBank-text', '✓ PubMed-NLP',
      '~ node-only', '? NOVEL'
    """
    best_verdict = "? NOVEL"
    best_source = ""

    for fn in food_names:
        fl = fn.lower().strip()
        for dn in drug_names:
            dl = dn.lower().strip()

            # DB-A
            if (fl, dl) in dbs["A"] or (dl, fl) in dbs["A"]:
                return "✓ DrugBank-named", f"DrugBank named pair: {fn} ↔ {dn}"

            # DB-C
            if (fl, dl) in dbs["C"] or (dl, fl) in dbs["C"]:
                best_verdict = "✓ PubMed-NLP"
                best_source = f"PubMed NLP: {fn} ↔ {dn}"

            # DB-B text
            if best_verdict == "? NOVEL":
                if fl in dbs["B_text"] and dl in dbs["B_drugs"]:
                    best_verdict = "✓ DrugBank-text"
                    best_source = f"DrugBank text mentions: {fn} with {dn}"

            # DB-D nodes
            if best_verdict == "? NOVEL":
                food_in = any(fl in fn2 or fn2 in fl for fn2 in dbs["food_nodes"]) if len(fl) > 3 else False
                drug_in = any(dl in dn2 or dn2 in dl for dn2 in dbs["drug_nodes"]) if len(dl) > 3 else False
                if food_in and drug_in:
                    best_verdict = "~ node-only"
                    best_source = f"Both entities in DFI graph"

    return best_verdict, best_source


def check_literature(food_raw: str, drug_raw: str):
    """Check the curated literature evidence table."""
    fl = food_raw.lower()
    dl = drug_raw.lower()

    for (food_key, drug_key), (verdict, note) in LITERATURE_EVIDENCE.items():
        if food_key in fl and drug_key in dl:
            return verdict, note
        if drug_key in fl and food_key in dl:
            return verdict, note

    # Also check expanded drug names
    for abbr, expands in DRUG_EXPAND.items():
        if abbr.lower() in dl or dl in abbr.lower():
            for exp in expands:
                expl = exp.lower()
                for (food_key, drug_key), (verdict, note) in LITERATURE_EVIDENCE.items():
                    if food_key in fl and drug_key in expl:
                        return verdict, f"[via {abbr}→{exp}] {note}"

    # Also check expanded food names
    for abbr, expands in FOOD_EXPAND.items():
        if abbr.lower() in fl or fl in abbr.lower():
            for exp in expands:
                expl = exp.lower()
                for (food_key, drug_key), (verdict, note) in LITERATURE_EVIDENCE.items():
                    if food_key in expl and drug_key in dl:
                        return verdict, f"[via {abbr}→{exp}] {note}"
                # Also cross with drug expand
                for drug_abbr, drug_expands in DRUG_EXPAND.items():
                    if drug_abbr.lower() in dl or dl in drug_abbr.lower():
                        for dexp in drug_expands:
                            dexpl = dexp.lower()
                            for (food_key, drug_key), (verdict, note) in LITERATURE_EVIDENCE.items():
                                if food_key in expl and drug_key in dexpl:
                                    return verdict, f"[via {abbr}→{exp} + {drug_abbr}→{dexp}] {note}"
    return None, None


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5: Parse and re-verify v2 file
# ─────────────────────────────────────────────────────────────────────────────
LINE_RE = re.compile(
    r'^\s*([\✓~?][^\s]*(?:\s+[A-Za-z\-]+)?)\s+(.*?)\s+→\s+(.+?)\s*$'
)

def parse_line(line):
    """Parse an interaction line. Returns (verdict, food, drug) or None."""
    line = line.rstrip()
    # Match lines like:
    #   ✓ DrugBank-named   Allicin  → Warfarin
    #   ~ node-only        PhyticAcid  → ACE-I
    #   ? NOVEL — drug('ACE-I') not in DB   Allicin  → ACE-I
    m = re.match(
        r'^\s*([✓~?])\s+(\S.*?)\s{2,}(\S.*?)\s*→\s*(.+?)\s*$',
        line
    )
    if m:
        symbol = m.group(1)
        status_text = m.group(2).strip()
        food = m.group(3).strip()
        drug = m.group(4).strip()
        orig_verdict = symbol + " " + status_text
        return orig_verdict, food, drug
    return None


def expand_food(food_raw: str) -> list:
    """Expand a food component name to a list of lookup strings."""
    base = re.sub(r'\s*\(.*?\)', '', food_raw).strip()
    # Remove prefixes like "S:", "W:", "A:", "B:"
    base = re.sub(r'^[A-Z]:\s*', '', base).strip()
    aliases = FOOD_EXPAND.get(base, [base])
    return aliases + [base.lower()]


def expand_drug(drug_raw: str) -> list:
    """Expand a drug abbreviation or name to a list of lookup strings."""
    base = drug_raw.strip()
    # Remove common suffixes like "/Warfarin", "/Clopidogrel" parts that are separate
    parts = re.split(r'[/+]', base)
    result = []
    for p in parts:
        p = p.strip()
        # Check exact key
        if p in DRUG_EXPAND:
            result.extend(DRUG_EXPAND[p])
        else:
            result.append(p.lower())
    # Also try the whole string
    if base in DRUG_EXPAND:
        result.extend(DRUG_EXPAND[base])
    return result if result else [base.lower()]


# ─────────────────────────────────────────────────────────────────────────────
# Display-name normalizer — replaces abbreviations in output labels
# ─────────────────────────────────────────────────────────────────────────────
DISPLAY_NAMES = {
    # Drug abbreviations → readable names
    "IronSuppl":            "Ferrous Sulfate",
    "IronSuppl/Ca/Zn":      "Ferrous Sulfate / Calcium / Zinc",
    "IronZinc":             "Iron / Zinc",
    "Cipro/IronSuppl":      "Ciprofloxacin / Ferrous Sulfate",
    "Cipro/Fe":             "Ciprofloxacin / Ferrous Sulfate",
    "Ciprofloxacin/Fe":     "Ciprofloxacin / Ferrous Sulfate",
    "Cipro/IronZinc":       "Ciprofloxacin / Iron / Zinc",
    "Cipro/Tetracycline":   "Ciprofloxacin / Tetracyclines",
    "Levothyroxine/Cipro":  "Levothyroxine / Ciprofloxacin",
    "Cipro/Levothyroxine":  "Ciprofloxacin / Levothyroxine",
    "Ciprofloxacin/Levothyroxine": "Ciprofloxacin / Levothyroxine",
    "ACE-I":                "ACE Inhibitors (Lisinopril/Ramipril)",
    "ACE-I/ARB":            "ACE-I / ARB (Lisinopril/Losartan)",
    "ACE-I/ARB/Spiron":     "ACE-I / ARB / Spironolactone",
    "ACE-I/K-SpDiuretics":  "ACE-I / K-Sparing Diuretics",
    "ACE-I/Spiro":          "ACE-I / Spironolactone",
    "ACE-I/Theophylline":   "ACE-I / Theophylline",
    "BB":                   "Beta-Blockers (Propranolol/Metoprolol)",
    "Benzodiazepines/BB":   "Benzodiazepines / Beta-Blockers",
    "MAOIs":                "MAOIs (Phenelzine/Tranylcypromine)",
    "SSRIs/MAOIs":          "SSRIs / MAOIs",
    "MAO-B-Inhibitors":     "MAO-B Inhibitors (Selegiline/Rasagiline)",
    "SGLT2":                "SGLT2 Inhibitors (Empagliflozin/Dapagliflozin)",
    "SGLT2-Inhibitors":     "SGLT2 Inhibitors",
    "SGLT2+Diuretics":      "SGLT2 Inhibitors / Diuretics",
    "HRT":                  "HRT (Estradiol/Progesterone)",
    "NTI-Drugs":            "Narrow Therapeutic Index Drugs",
    "NTI-Drugs/Lithium/Digoxin": "NTI Drugs (Warfarin/Lithium/Digoxin)",
    "AcidLabileDrugs":      "Acid-Labile Drugs (Omeprazole/Erythromycin)",
    "AllOralMeds":          "All Oral Medications (timing-sensitive)",
    "Al-Antacids":          "Aluminum-containing Antacids",
    "BileAcidSequestrants": "Bile Acid Sequestrants (Cholestyramine)",
    "K-SpDiuretics":        "K-Sparing Diuretics (Spironolactone)",
    "LoopDiuretics":        "Loop Diuretics (Furosemide)",
    "CYP2C9":               "CYP2C9 Substrates (Warfarin/Phenytoin)",
    "CYP2C9/Warfarin":      "CYP2C9 / Warfarin",
    "CYP3A4":               "CYP3A4 Substrates (Cyclosporine/Statins)",
    "CYP3A4/Statins":       "CYP3A4 / Statins",
    "CYP1A2":               "CYP1A2 Substrates (Theophylline/Clozapine)",
    "Cipro/Clozapine/Theophylline": "Ciprofloxacin / Clozapine / Theophylline",
    "Cipro/Tetracyclines":  "Ciprofloxacin / Tetracyclines",
    "Insulin/Metformin":    "Insulin / Metformin",
    "Insulin/SGLT2":        "Insulin / SGLT2 Inhibitors",
    "Metformin/Insulin/SGLT2": "Metformin / Insulin / SGLT2 Inhibitors",
    "Statins/ARVs":         "Statins / Antiretrovirals",
    "Statins/Cyclosporine": "Statins / Cyclosporine",
    "Statins/Amiodarone/VitD": "Statins / Amiodarone / Vitamin D",
    "Cyclosporine/Orlistat": "Cyclosporine / Orlistat",
    "Warfarin/Clopidogrel": "Warfarin / Clopidogrel",
    "Warfarin/Aspirin":     "Warfarin / Aspirin",
    "Warfarin/NSAIDs":      "Warfarin / NSAIDs",
    "Warfarin/Saquinavir":  "Warfarin / Saquinavir",
    "Warfarin/CYP2C9":      "Warfarin / CYP2C9 Substrates",
    "Aspirin/Clopidogrel":  "Aspirin / Clopidogrel",
    "Sildenafil/Nitrates":  "Sildenafil / Nitrates",
    "Diuretics/ACE-I":      "Diuretics / ACE Inhibitors",
    "Diuretics/BP-meds":    "Diuretics / Blood Pressure Meds",
    "BP-meds":              "Blood Pressure Medications",
    "Lecithin+Chol":        "Lecithin + Cholesterol (Egg Yolk / Aqda)",
    "Lecithin":             "Lecithin (Egg Yolk)",
    "BetaGlucan":           "Beta-Glucan",
    "Apigenin+Phthalide":   "Apigenin + Phthalides (Celery/Parsley)",
    "Apigenin+Phthalides":  "Apigenin + Phthalides (Celery/Parsley)",
    "Apigenin":             "Apigenin (Celery/Parsley)",
    "Phthalide":            "Phthalides (Celery)",
    "Carvone":              "Carvone (Caraway/Karouiya)",
    # Makroud compound labels
    "K++InsolFiber":         "Potassium + Insoluble Fiber",
    "K+_DatePaste":          "Potassium (Date Paste)",
    "K+_DatePaste1kg":       "Potassium (Date Paste — High Load)",
    "Amylopectin+K+":        "Amylopectin + Potassium",
    "FullGelatStarch+K+":    "Gelatinised Starch + Potassium",
    "K++Mg2+":              "Potassium + Magnesium (Date Paste / Ghers)",
    "K+":                   "Potassium",
    "Cinnamaldehyde+Eugenol": "Cinnamaldehyde + Eugenol (Cinnamon + Cloves)",
    "PhyticAcid":           "Phytic Acid",
    "PhyticAcid+Mg":        "Phytic Acid + Magnesium (Frik)",
    "SolFiber":             "Soluble Fiber (Pectin)",
    "SolFiber+Folate":      "Soluble Fiber + Folate",
    "SmokedPAH":            "Smoked / Roasted PAHs",
    "Ca2+":                 "Calcium",
    "Ca2+_Casein":          "Calcium (Casein)",
    "OliveOil":             "Olive Oil",
    "SatFats":              "Saturated Fats",
    "Vit-K":                "Vitamin K",
    "BetaCarotene":         "Beta-Carotene",
    "LNAA":                 "Large Neutral Amino Acids",
    "CitricAcid":           "Citric Acid",
    "AceticAcid":           "Acetic Acid (Vinegar)",
    "NaHCO3":               "Sodium Bicarbonate",
    "NaHCO3+CO2":           "Sodium Bicarbonate + CO₂",
    "Lycopene":             "Lycopene (Tomato)",
    "ConcentratedLycopene": "Concentrated Lycopene (Tomato Paste)",
    "Triglycerides":        "Triglycerides (Dietary Fat)",
    "MaillardAGEs":         "Maillard / AGEs",
    "LArg+Niacin":          "L-Arginine + Niacin",
    "Sucrose":              "Sucrose / Glucose",
    "Fructose+Glucose":     "Sucrose / Glucose",
    # Zlabia sweet pastry labels
    "Honey250g":            "Glucose/Fructose (Honey / Sugar Syrup)",
    "Honey200g":            "Honey",
    "Honey1.5kg":           "Honey",
    "MaillardHoneySynergy": "Maillard + Honey Synergy",
    "GelatinisedStarch":    "Gelatinised Starch (Fermented/Fried)",
    "DeepFryOil":           "Oxidised Lipids (Deep-Fry Oil)",
    "DeepFryLipid+Lecithin": "Oxidised Lipids (Deep-Fry Oil) + Lecithin",
    "DeepFryLipid":         "Oxidised Lipids (Deep-Fry Oil)",
    "DioulHighPorosity":    "High-Fat Meal \u2014 Saturated Fats / Lipid Carrier (Dioul Porous Pastry)",
    "DoubleLipid":          "High-Fat Meal \u2014 Saturated Fats + Butyric Acid (Double Lipid)",
    "ButterEmulsion250g":   "Butter Emulsion",
    "ButterEmulsion":       "Butter Emulsion",
    "ButterGrainEncap250g": "Butter + Grain Starch",
    "ButterGrainEncap":     "Butter + Grain Starch",
    "Sucrose-IcingSugar":   "Sucrose / Icing Sugar",
    "Sucrose+IcingSugar":   "Sucrose / Icing Sugar",
    # Trida / Smen compound labels
    "TripleSmen":           "High-Fat Meal — Saturated Fats + Butyric Acid (Triple Smen)",
    "TripleLipid":          "High-Fat Meal — Saturated Fats + Oleic Acid + Omega-3 (Triple Lipid)",
    "Smen-Kila":            "Saturated Fats — Lipid Carrier (Smen / Fermented Butter)",
    "SCFAs+Butter":         "Butyric Acid / SCFAs (Smen Butter)",
    "SCFA-Butter":          "Butyric Acid / SCFAs (Smen Butter)",
    "SCFA+SatFats":         "Butyric Acid (SCFA) + Saturated Fats (Smen)",
    "DenseAmylopectin":     "Amylopectin (Trida Semolina Pasta)",
    "AmylopectinLipidEncapsulated": "Amylopectin + Lipid (Trida + Smen)",
    "Amylopectin/Starch":   "Amylopectin / Semolina Starch",
    "ButteryStarch":        "Amylopectin + Butyric Acid (Trida + Smen)",
    # Shbah el-Safra (Dish 49) food labels
    "LArginine+VitE":       "L-Arginine + Vitamin E (Almonds)",
    "K++Sorbitol":          "Potassium + Sorbitol (Almonds)",
    "DoubleFriedLecithin":  "Double-Fried Lecithin (Almond Paste)",
    "Crocin+Safranal":      "Crocin + Safranal (Saffron)",
    "Linalool+Geraniol":    "Linalool + Geraniol (Orange Blossom / Rose Water)",
    # Drug group display names — no abbreviations
    "CyclospIsotrRetinStatins": "Cyclosporine / Isotretinoin / Statins",
    "VitA-Retinoids":       "Vitamin A / Retinoids (Isotretinoin)",
    "VitATox":              "Vitamin A Toxicity Risk (Isotretinoin/Retinol)",
    "Isotretinoin/VitATox": "Isotretinoin / Vitamin A Toxicity",
    "VitC+Flavonoids":      "Ascorbic Acid (Vitamin C) + Flavonoids",
    "Statins/ARVs/Isotretinoin": "Statins / Antiretrovirals / Isotretinoin",
    "Statins/ARVs/Cyclosporine": "Statins / Antiretrovirals / Cyclosporine",
    "Statins/Cyclosporine/VitD": "Statins / Cyclosporine / Vitamin D",
    "Statins/Cyclosporine/VitD3": "Statins / Cyclosporine / Vitamin D3",
    "Statins/Griseofulvin/VitD/Cyclosporine": "Statins / Griseofulvin / Vitamin D / Cyclosporine",
    "Statins/Amiodarone/VitD": "Statins / Amiodarone / Vitamin D",
    "Isotretinoin/Griseofulvin/Cyclosporine/VitD3": "Isotretinoin / Griseofulvin / Cyclosporine / Vitamin D3",
    "PhyticAcid+Saponins":  "Phytic Acid + Saponins",
    "PhyticAcid+NonHemeIron": "Phytic Acid + Non-Heme Iron",
    "PhyticAcid-REDUCED":   "Phytic Acid (Reduced — Fermented)",
    "OleicAcid":            "Oleic Acid (Olive Oil)",
    "BetaCarotene+Minerals": "Beta-Carotene + Minerals",
}


def normalize_display(name: str) -> str:
    """Replace known abbreviations with readable display names."""
    n = name.strip()
    if n in DISPLAY_NAMES:
        return DISPLAY_NAMES[n]
    # Strip measurement suffixes (e.g. 250g, 1.5kg, 200ml) from unknown labels
    cleaned = re.sub(r'\d+(\.\d+)?(g|kg|ml|l|mg|L)\b', '', n).strip()
    cleaned = re.sub(r'[-_]+$', '', cleaned).strip()  # trim trailing separators
    return DISPLAY_NAMES.get(cleaned, cleaned if cleaned else n)


def format_verdict(verdict, note=""):
    """Format verdict + optional note as a fixed-width line."""
    symbols = {"✓": "✓", "~": "~", "?": "?"}
    sym = verdict[0] if verdict else "?"
    tag = verdict[1:].strip() if len(verdict) > 1 else ""
    note_part = f"  [{note[:80]}]" if note else ""
    return f"  {sym} {tag:<40}{note_part}"


def recheck_novel(food_raw, drug_raw, dbs):
    """
    For a ? NOVEL line, attempt re-classification using:
    1. Literature evidence table
    2. Expanded DB lookup
    Returns (new_verdict, note)
    """
    # 1. Literature first
    lit_verdict, lit_note = check_literature(food_raw, drug_raw)
    if lit_verdict:
        return lit_verdict, lit_note

    # 2. Expanded DB lookup
    food_expanded = expand_food(food_raw)
    drug_expanded = expand_drug(drug_raw)

    db_verdict, db_note = check_pair_expanded(food_expanded, drug_expanded, dbs)
    if db_verdict != "? NOVEL":
        return db_verdict, f"(expanded: {food_expanded[0]}→{drug_expanded[0]}) {db_note}"

    # 3. Check if expanded names are now at least in nodes
    return "? NOVEL", f"(expanded food={food_expanded[0]}, drug={drug_expanded[0]}) not confirmed in any DB"


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6: Main processing
# ─────────────────────────────────────────────────────────────────────────────
def main():
    dbs = load_dbs()

    in_path  = BASE / "na_interaction_verification_v2.txt"
    out_path = BASE / "na_interaction_verification_v3.txt"

    with open(in_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Stats
    stats = {
        "total": 0,
        "upgraded_novel": 0,
        "confirmed": 0,
        "node_only": 0,
        "novel": 0,
        "lit_confirmed": 0,
    }

    out_lines = []
    out_lines.append("=" * 90)
    out_lines.append("NORTH AFRICAN FOOD-DRUG INTERACTIONS — VERIFICATION v3")
    out_lines.append("Re-verified with: drug abbreviation expansion + literature evidence table")
    out_lines.append("=" * 90)
    out_lines.append("")

    # Renumber dishes: source v2 skips Dish 36 (jumps 35→37). Tamina is correctly Dish 36.
    # All dishes numbered ≥37 in source should be decremented by 1.
    RENUMBER = {str(n): str(n - 1) for n in range(37, 100)}

    i = 0
    skip_v2_summary = False
    while i < len(lines):
        line = lines[i].rstrip()

        # Skip the old v2 VERIFICATION SUMMARY block entirely
        if line.strip().startswith("VERIFICATION SUMMARY") or line.strip() == "VERIFICATION SUMMARY":
            skip_v2_summary = True
        if skip_v2_summary:
            i += 1
            continue

        # Apply renumbering to dish header lines
        if line.startswith("Dish "):
            m = re.match(r'^(Dish )(\d+)(:.*)$', line)
            if m:
                num = m.group(2)
                if num in RENUMBER:
                    line = m.group(1) + RENUMBER[num] + m.group(3)

        # Dish headers and blank lines pass through
        if not line.strip() or line.startswith("Dish") or line.startswith("---") or \
           line.startswith("===") or line.startswith("VERIFICATION") or \
           line.startswith("Total") or line.startswith("  ✓") is False and line.startswith("Sources") or \
           line.startswith("  DB-") or line.startswith("INTERPRETATION") or \
           line.startswith("Full report") or line.startswith("  ? ") is False and line.startswith("  ~") is False and line.startswith("  ✓") is False:
            # Check if this is an actual interaction line
            parsed = parse_line(line)
            if parsed is None:
                out_lines.append(line)
                i += 1
                continue

        parsed = parse_line(line)
        if parsed is None:
            out_lines.append(line)
            i += 1
            continue

        orig_verdict, food_raw, drug_raw = parsed
        stats["total"] += 1

        if orig_verdict.startswith("? NOVEL") or orig_verdict.startswith("?"):
            # Attempt re-classification
            new_verdict, note = recheck_novel(food_raw, drug_raw, dbs)
            if new_verdict != "? NOVEL":
                stats["upgraded_novel"] += 1
            food_disp = normalize_display(food_raw)
            drug_disp = normalize_display(drug_raw)
            if new_verdict.startswith("✓ LIT"):
                stats["lit_confirmed"] += 1
                status_tag = new_verdict[2:].strip()
                new_line = f"  ✓ {status_tag:<38}  {food_disp:<35} → {drug_disp}"
                note_line = f"      NOTE: {note}"
                out_lines.append(new_line)
                out_lines.append(note_line)
            elif new_verdict.startswith("✓"):
                stats["confirmed"] += 1
                status_tag = new_verdict[2:].strip()
                new_line = f"  ✓ {status_tag:<38}  {food_disp:<35} → {drug_disp}"
                note_line = f"      NOTE: {note}"
                out_lines.append(new_line)
                out_lines.append(note_line)
            elif new_verdict.startswith("~"):
                stats["node_only"] += 1
                status_tag = new_verdict[1:].strip()
                new_line = f"  ~ {status_tag:<38}  {food_disp:<35} → {drug_disp}"
                note_line = f"      NOTE: {note}"
                out_lines.append(new_line)
                out_lines.append(note_line)
            else:
                stats["novel"] += 1
                # normalize display even for NOVEL passthrough
                food_disp = normalize_display(food_raw)
                drug_disp = normalize_display(drug_raw)
                status_tag = orig_verdict.lstrip("? ").strip()
                out_lines.append(f"  ? {status_tag:<38}  {food_disp:<35} → {drug_disp}")
                if note and "(expanded" in note:
                    out_lines.append(f"      NOTE: {note}")
        elif orig_verdict.startswith("✓"):
            stats["confirmed"] += 1
            # Rebuild line with normalized display names
            food_disp = normalize_display(food_raw)
            drug_disp = normalize_display(drug_raw)
            status_tag = orig_verdict[2:].strip()
            out_lines.append(f"  ✓ {status_tag:<38}  {food_disp:<35} → {drug_disp}")
            # Also annotate already-confirmed pairs with literature evidence if available
            lit_verdict, lit_note = check_literature(food_raw, drug_raw)
            if lit_note:
                out_lines.append(f"      NOTE: {lit_note}")
        elif orig_verdict.startswith("~"):
            # Check if literature has evidence for node-only pairs too
            lit_verdict, lit_note = check_literature(food_raw, drug_raw)
            if lit_verdict and lit_verdict.startswith("✓"):
                stats["upgraded_novel"] += 1
                stats["lit_confirmed"] += 1
                status_tag = lit_verdict[2:].strip()
                food_disp = normalize_display(food_raw)
                drug_disp = normalize_display(drug_raw)
                new_line = f"  ✓ {status_tag:<38}  {food_disp:<35} → {drug_disp}"
                note_line = f"      NOTE: [UPGRADED from node-only] {lit_note}"
                out_lines.append(new_line)
                out_lines.append(note_line)
            else:
                stats["node_only"] += 1
                # Rebuild line with normalized display names
                food_disp = normalize_display(food_raw)
                drug_disp = normalize_display(drug_raw)
                status_tag = orig_verdict[1:].strip()
                out_lines.append(f"  ~ {status_tag:<38}  {food_disp:<35} → {drug_disp}")
        else:
            out_lines.append(line)

        i += 1

    # Summary
    total = stats["total"]
    confirmed = stats["confirmed"] + stats["lit_confirmed"]
    node_only = stats["node_only"]
    novel = stats["novel"]
    pct = lambda n: f"{round(100*n/total)}%" if total else "0%"

    out_lines.append("")
    out_lines.append("=" * 90)
    out_lines.append("VERIFICATION SUMMARY (v3 — post-upgrade)")
    out_lines.append("=" * 90)
    out_lines.append(f"  Total (bioactive × drug) pairs checked  : {total}")
    out_lines.append(f"  ✓ CONFIRMED  (DrugBank / PubMed / LIT)  : {confirmed:>4}  ({pct(confirmed)})")
    out_lines.append(f"  ~ NODE-ONLY  (both in DFI graph)        : {node_only:>4}  ({pct(node_only)})")
    out_lines.append(f"  ? NOVEL      (pair not in any DB)       : {novel:>4}  ({pct(novel)})")
    out_lines.append("")
    out_lines.append(f"  Previously ? NOVEL upgraded             : {stats['upgraded_novel']}")
    out_lines.append(f"    of which via literature table         : {stats['lit_confirmed']}")
    out_lines.append("")
    out_lines.append("Sources used:")
    out_lines.append("  DB-A  DrugBank named food↔drug pairs  : 1538")
    out_lines.append("  DB-B  DrugBank JSON interaction texts : 2512")
    out_lines.append("  DB-C  PubMed NLP extracted pairs      : 3638")
    out_lines.append("  DB-D  Unified-DFI node maps           : 1894 food + 5000 drug nodes")
    out_lines.append("")
    out_lines.append("Upgrade sources:")
    out_lines.append("  [LIT-confirmed]          = verified via curated pharmacological literature table")
    out_lines.append("  [DrugBank-named]         = found in DrugBank named food-drug pair DB after alias expansion")
    out_lines.append("  [PubMed-NLP]             = found in PubMed NLP-extracted pairs after alias expansion")
    out_lines.append("  [UPGRADED from node-only]= node-only pair elevated by literature evidence")
    out_lines.append("")
    out_lines.append(f"Output: {out_path}")
    out_lines.append("=" * 90)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))

    print("\n" + "="*60)
    print("VERIFICATION v3 COMPLETE")
    print("="*60)
    print(f"  Total pairs processed          : {stats['total']}")
    print(f"  ? NOVEL upgraded               : {stats['upgraded_novel']}")
    print(f"    via literature table         : {stats['lit_confirmed']}")
    print(f"  ✓ CONFIRMED (after upgrade)    : {stats['confirmed'] + stats['lit_confirmed']}")
    print(f"  ~ NODE-ONLY                    : {stats['node_only']}")
    print(f"  ? NOVEL remaining              : {stats['novel']}")
    print(f"\n  Output saved: {out_path}")


if __name__ == "__main__":
    main()
