"""
Drug Resolver — Algerian Trade Name → Pipeline Generic Name

Loads algerian_brand_map.csv and resolves any drug input (brand or generic)
to the name understood by the DFinder pipeline.

Resolution priority:
  1. Exact brand name match (case-insensitive)
  2. Exact INN match (case-insensitive) → pass through as-is
  3. No match → pass through as-is (pipeline handles unknown names gracefully)

Usage:
    from drug_resolver import DrugResolver
    resolver = DrugResolver()

    resolver.resolve("Tahor")
    # → {"pipeline_name": "Atorvastatin", "brand_name": "Tahor",
    #    "inn_raw": "Atorvastatine calcique", "resolved": True, "source": "brand"}

    resolver.resolve("Atorvastatin")
    # → {"pipeline_name": "Atorvastatin", "brand_name": None,
    #    "inn_raw": None, "resolved": True, "source": "passthrough"}

    resolver.resolve("SomeUnknown")
    # → {"pipeline_name": "SomeUnknown", "brand_name": None,
    #    "inn_raw": None, "resolved": False, "source": "passthrough"}
"""

import pandas as pd
from pathlib import Path

ROOT      = Path(__file__).resolve().parent
BRAND_MAP = ROOT / "algerian_brand_map.csv"
DRUG_ID_MAP = ROOT / "DFinder-main/data/unified-DFI/id_maps/drug_id_map.csv"

# Manual overrides for common brands not in official registry
MANUAL_OVERRIDES: dict[str, str] = {
    "kardegic"     : "Aspirin",
    "aspegic"      : "Aspirin",
    "aspirine cardio": "Aspirin",
    "doliprane"    : "Paracetamol",
    "efferalgan"   : "Paracetamol",
    "dafalgan"     : "Paracetamol",
    "brufen"       : "Ibuprofen",
    "nurofen"      : "Ibuprofen",
    "tahor"        : "Atorvastatin",
    "crestor"      : "Rosuvastatin",
    "lovenox"      : "Enoxaparin",
    "clexane"      : "Enoxaparin",
    "sintrom"      : "Acenocoumarol",
    "previscan"    : "Fluindione",
    "coumadine"    : "Warfarin",
    "coumadin"     : "Warfarin",
    "glucophage"   : "Metformin",
    "stagid"       : "Metformin",
    "dianben"      : "Metformin",
    "diamicron"    : "Gliclazide",
    "amaryl"       : "Glimepiride",
    "lantus"       : "Insulin glargine",
    "novorapid"    : "Insulin aspart",
    "zestril"      : "Lisinopril",
    "renitec"      : "Enalapril",
    "lopril"       : "Captopril",
    "coveram"      : "Amlodipine",
    "norvasc"      : "Amlodipine",
    "amlor"        : "Amlodipine",
    "cordarone"    : "Amiodarone",
    "digoxine"     : "Digoxin",
    "lasilix"      : "Furosemide",
    "aldactone"    : "Spironolactone",
    "sectral"      : "Acebutolol",
    "tenormine"    : "Atenolol",
    "avlocardyl"   : "Propranolol",
    "seloken"      : "Metoprolol",
    "zocor"        : "Simvastatin",
    "lipitor"      : "Atorvastatin",
    "lescol"       : "Fluvastatin",
    "pravastatine" : "Pravastatin",
    "augmentin"    : "Amoxicillin",
    "clamoxyl"     : "Amoxicillin",
    "clavoxyl"     : "Amoxicillin",
    "ciflox"       : "Ciprofloxacin",
    "oflocet"      : "Ofloxacin",
    "tavanic"      : "Levofloxacin",
    "zithromax"    : "Azithromycin",
    "zinnat"       : "Cefuroxime",
    "rocephine"    : "Ceftriaxone",
    "diflucan"     : "Fluconazole",
    "triflucan"    : "Fluconazole",
    "zovirax"      : "Aciclovir",
    "inexium"      : "Esomeprazole",
    "mopral"       : "Omeprazole",
    "pantoloc"     : "Pantoprazole",
    "lanzor"       : "Lansoprazole",
    "zantac"       : "Ranitidine",
    "tagamet"      : "Cimetidine",
    "spasfon"      : "Phloroglucinol",
    "vogalene"     : "Metopimazine",
    "primpéran"    : "Metoclopramide",
    "primperam"    : "Metoclopramide",
    "gaviscon"     : "Alginic acid",
    "xarelto"      : "Rivaroxaban",
    "eliquis"      : "Apixaban",
    "pradaxa"      : "Dabigatran",
    "plavix"       : "Clopidogrel",
    "vastarel"     : "Trimetazidine",
    "ikorel"       : "Nicorandil",
    "isoptine"     : "Verapamil",
    "tildiem"      : "Diltiazem",
    "loxen"        : "Nicardipine",
    "mediator"     : "Benfluorex",
    "voltarene"    : "Diclofenac",
    "voltaren"     : "Diclofenac",
    "profenid"     : "Ketoprofen",
    "surgam"       : "Tiaprofenic acid",
    "celebrex"     : "Celecoxib",
    "cortancyl"    : "Prednisone",
    "solupred"     : "Prednisolone",
    "medrol"       : "Methylprednisolone",
    "kenacort"     : "Triamcinolone",
    "depakine"     : "Valproic acid",
    "tegretol"     : "Carbamazepine",
    "rivotril"     : "Clonazepam",
    "temesta"      : "Lorazepam",
    "lexomil"      : "Bromazepam",
    "urbanyl"      : "Clobazam",
    "stilnox"      : "Zolpidem",
    "imovane"      : "Zopiclone",
    "seresta"      : "Oxazepam",
    "xanax"        : "Alprazolam",
    "prozac"       : "Fluoxetine",
    "deroxat"      : "Paroxetine",
    "seroplex"     : "Escitalopram",
    "seropram"     : "Citalopram",
    "zoloft"       : "Sertraline",
    "effexor"      : "Venlafaxine",
    "cymbalta"     : "Duloxetine",
    "laroxyl"      : "Amitriptyline",
    "tofranil"     : "Imipramine",
    "haldol"       : "Haloperidol",
    "tercian"      : "Cyamemazine",
    "nozinan"      : "Levomepromazine",
    "zyprexa"      : "Olanzapine",
    "risperdal"    : "Risperidone",
    "abilify"      : "Aripiprazole",
    "xeplion"      : "Paliperidone",
    "leponex"      : "Clozapine",
    "levothyrox"   : "Levothyroxine",
    "euthyrox"     : "Levothyroxine",
    "neo-mercazole": "Carbimazole",
    "glucantime"   : "Meglumine antimoniate",
    "plaquenil"    : "Hydroxychloroquine",
    "aralen"       : "Chloroquine",
    "nolvadex"     : "Tamoxifen",
    "taxol"        : "Paclitaxel",
    "herceptin"    : "Trastuzumab",
    "mabthera"     : "Rituximab",
    "glivec"       : "Imatinib",
    "avastin"      : "Bevacizumab",
    "opdivo"       : "Nivolumab",
    "keytruda"     : "Pembrolizumab",
}


class DrugResolver:
    def __init__(self, verbose: bool = True):
        # ── Brand map from Algerian registry ──────────────────────────────
        df = pd.read_csv(BRAND_MAP, encoding="utf-8")
        df = df[df["pipeline_drug"].notna() & (df["pipeline_drug"] != "")]

        self._brand_map: dict[str, dict] = {}
        for _, row in df.iterrows():
            key = str(row["brand_name"]).strip().lower()
            self._brand_map[key] = {
                "pipeline_drug": str(row["pipeline_drug"]).strip(),
                "inn_raw"      : str(row["inn_raw"]).strip(),
                "match_type"   : str(row["match_type"]).strip(),
            }

        # ── Add manual overrides (brands not in official registry) ─────────
        for brand_lower, pipeline_name in MANUAL_OVERRIDES.items():
            if brand_lower not in self._brand_map:
                self._brand_map[brand_lower] = {
                    "pipeline_drug": pipeline_name,
                    "inn_raw"      : pipeline_name,
                    "match_type"   : "manual",
                }

        # ── Full pipeline drug list for passthrough validation ─────────────
        try:
            dm = pd.read_csv(DRUG_ID_MAP)
            self._pipeline_names: set[str] = set(
                dm["name"].dropna().str.strip().str.lower()
            )
        except FileNotFoundError:
            # Fallback: use drugs known from brand map
            self._pipeline_names = set(
                v["pipeline_drug"].lower() for v in self._brand_map.values()
            )
        # Canonical casing: lower → original
        self._pipeline_canonical: dict[str, str] = {}
        try:
            dm = pd.read_csv(DRUG_ID_MAP)
            for name in dm["name"].dropna():
                self._pipeline_canonical[name.strip().lower()] = name.strip()
        except FileNotFoundError:
            for v in self._brand_map.values():
                n = v["pipeline_drug"]
                self._pipeline_canonical[n.lower()] = n

        if verbose:
            print(f"DrugResolver loaded: {len(self._brand_map):,} brand entries "
                  f"({sum(1 for v in self._brand_map.values() if v['match_type']=='manual')} manual overrides) "
                  f"| {len(self._pipeline_names):,} pipeline drugs")

    def resolve(self, drug_input: str) -> dict:
        """
        Resolve a drug name to its pipeline-compatible generic name.

        Returns:
            pipeline_name : str   — name to pass to DFinder.predict()
            brand_name    : str | None — original brand name if resolved
            inn_raw       : str | None — raw INN from Algerian registry
            match_type    : str        — "exact"/"prefix"/"fuzzy(x.xx)"
            resolved      : bool       — True if brand→generic mapping was applied
            source        : str        — "brand" | "passthrough"
        """
        key = drug_input.strip().lower()

        # 1. Brand name match
        if key in self._brand_map:
            entry = self._brand_map[key]
            return {
                "pipeline_name": entry["pipeline_drug"],
                "brand_name"   : drug_input.strip(),
                "inn_raw"      : entry["inn_raw"],
                "match_type"   : entry["match_type"],
                "resolved"     : True,
                "source"       : "brand",
            }

        # 2. Already a known pipeline generic name → pass through cleanly
        if key in self._pipeline_names:
            canonical = self._pipeline_canonical.get(key, drug_input.strip())
            return {
                "pipeline_name": canonical,
                "brand_name"   : None,
                "inn_raw"      : None,
                "match_type"   : "passthrough",
                "resolved"     : True,
                "source"       : "passthrough",
            }

        # 3. Unknown — pass through as-is
        return {
            "pipeline_name": drug_input.strip(),
            "brand_name"   : None,
            "inn_raw"      : None,
            "match_type"   : "none",
            "resolved"     : False,
            "source"       : "passthrough",
        }

    def resolve_name(self, drug_input: str) -> str:
        """Shorthand — returns just the pipeline name string."""
        return self.resolve(drug_input)["pipeline_name"]

    def is_algerian_brand(self, drug_input: str) -> bool:
        """Returns True if the input is a known Algerian trade name."""
        return drug_input.strip().lower() in self._brand_map

    def suggest(self, drug_input: str, n: int = 5) -> list[str]:
        """
        Suggest closest brand names for a fuzzy-unmatched input.
        Useful for 'did you mean?' UI hints.
        """
        import difflib
        key = drug_input.strip().lower()
        matches = difflib.get_close_matches(key, self._brand_map.keys(),
                                            n=n, cutoff=0.6)
        return [self._brand_map[m]["pipeline_drug"] for m in matches]


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    resolver = DrugResolver(verbose=True)
    print()

    test_cases = [
        # Known Algerian brands
        "TAHOR", "Glucophage", "KARDEGIC", "Sintrom", "NOVAROL",
        "ABILIFY", "ABASAGLAR", "ACTEMRA", "ACETADOL",
        # Generic names (should pass through)
        "Atorvastatin", "Metformin", "Warfarin",
        # Unknown
        "SomeBrandNotInAlgeria", "Aspirin",
    ]

    print(f"{'Input':25s}  {'Pipeline name':25s}  {'Source':12s}  {'Match':20s}")
    print("-" * 90)
    for name in test_cases:
        r = resolver.resolve(name)
        flag = "⚠ UNRESOLVED" if not r["resolved"] else ""
        print(f"  {name:23s}  →  {r['pipeline_name']:23s}  [{r['source']:10s}]  "
              f"{r['match_type']:18s}  {flag}")
