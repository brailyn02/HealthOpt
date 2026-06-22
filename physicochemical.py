"""
Phase 9 — Rule-Based Physicochemical Layer 0
=============================================
Deterministic warning engine that fires BEFORE the LightGCN/KGE fusion.
Operates on raw drug name + food name + optional LLM-sourced compound list.

Five rules:
  CHELATION_RISK        — multivalent cation (Ca2+/Fe2+/Mg2+/Zn2+) chelation
  VITAMIN_K_ANTAGONISM  — dietary Vitamin K1 reverses VKA anticoagulant effect
  TYRAMINE_CRISIS       — tyramine-containing food triggers hypertensive crisis in MAOI patients
  POTASSIUM_OVERLOAD    — high-potassium food + potassium-sparing drug → hyperkalaemia
  ACID_ABSORPTION_RISK  — food that raises gastric pH impairs acid-dependent drug absorption

Returns a list of warning dicts (empty if no rules fire).
Does NOT modify the fusion score — purely additive metadata.

Usage:
    from physicochemical import PhysicochemicalEngine
    engine = PhysicochemicalEngine()
    warnings = engine.check("Warfarin", "Spinach", llm_compounds=["Vitamin K1"])
"""

import os
import re
import pandas as pd
from pathlib import Path
from typing import Optional

ROOT        = Path(__file__).resolve().parent
DRUG_TABLE  = ROOT / "data" / "drug_sensitivity_table.csv"
FOOD_TABLE  = ROOT / "data" / "food_content_table.csv"

# ── LLM compound signals ──────────────────────────────────────────────────────
# If the LLM-decomposed compound list contains these keywords, treat as a signal
# even when the food isn't in our USDA table.
LLM_CATION_SIGNALS = {
    "calcium", "iron", "magnesium", "zinc", "manganese",
    "ca2+", "fe2+", "mg2+", "zn2+", "fe3+",
    "phytic acid", "phytate",   # chelation agent itself
    "oxalic acid", "oxalate",   # binds Ca/Fe
    "tannin", "tannic acid",    # chelates Fe/Zn
}
LLM_VITK_SIGNALS = {
    "vitamin k", "vitamin k1", "phylloquinone", "menaquinone",
    "vitamin k2", "mk-4", "mk-7",
}
LLM_TYRAMINE_SIGNALS = {
    "tyramine", "beta-phenylethylamine",
}
LLM_POTASSIUM_SIGNALS = {
    "potassium",
}
LLM_ACID_SIGNALS = {
    "bicarbonate", "calcium carbonate", "antacid",
    "milk protein", "casein",
}
LLM_ACIDIC_SIGNALS = {
    "citric acid", "ascorbic acid", "malic acid", "tartaric acid", "acetic acid",
}

# Common clinical aliases used by users vs canonical DrugBank names in table.
DRUG_ALIASES = {
    "aspirin": "acetylsalicylic acid",
    "asa": "acetylsalicylic acid",
}

# ── Tier rank helper ─────────────────────────────────────────────────────────
def _tier_rank(t: str) -> int:
    return {"HIGH": 2, "MEDIUM": 1}.get(str(t).upper(), 0)


def _llm_hit(compounds: list[str], signal_set: set[str]) -> Optional[str]:
    """Return the first matching compound name from the LLM list, or None."""
    for c in compounds:
        if any(sig in c.lower() for sig in signal_set):
            return c
    return None


def _source_from_signal(food_signal: str) -> str:
    if str(food_signal or "").startswith("LLM:"):
        return "LLM_COMPOUND"
    if str(food_signal or "").startswith("acid_tier_"):
        return "FOOD_TIER"
    if str(food_signal or "") in {"potassium_high", "potassium_medium"}:
        return "FOOD_TIER"
    if "_high" in str(food_signal or "") or "_medium" in str(food_signal or ""):
        return "FOOD_TIER"
    return "FOOD_NAME_KEYWORD"


def _food_tokens(text: str) -> set[str]:
    """Tokenize food names robustly across punctuation/plurals."""
    toks = set(re.findall(r"[a-z0-9]+", str(text).lower()))
    norm = set()
    for t in toks:
        # Simple singularization for common USDA plurals (bananas -> banana)
        if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            norm.add(t[:-1])
        norm.add(t)
    return norm


def _has_context_modifiers(text: str) -> bool:
    return bool(re.search(r"\b(without|no|sans|only)\b", str(text or "").lower()))


class PhysicochemicalEngine:
    """
    Loads drug sensitivity table and food content table once at init.
    `check()` method evaluates 5 rules and returns a list of warning dicts.
    """

    def __init__(self, verbose: bool = True):
        if verbose:
            print("[PhysicochemicalEngine] Loading tables...")

        # Drug table — index by lowercase drug name for fast lookup
        drug_df = pd.read_csv(DRUG_TABLE, dtype=str)
        # Boolean columns
        for col in ("cation_sensitive", "vka", "maoi", "k_sparing", "acid_dependent"):
            drug_df[col] = drug_df[col].fillna("0").astype(int).astype(bool)
        self._drug_table = drug_df.copy()
        self._drug_index = {
            row["name"].lower(): row
            for _, row in drug_df.iterrows()
        }

        # Food table — index by lowercase food name
        food_df = pd.read_csv(FOOD_TABLE, dtype=str)
        self._food_table = food_df.copy()
        self._food_index = {
            row["food_name"].lower(): row
            for _, row in food_df.iterrows()
        }

        if verbose:
            print(
                f"[PhysicochemicalEngine] Ready: "
                f"{len(self._drug_index):,} drugs, {len(self._food_index):,} foods"
            )

    # ── Public API ────────────────────────────────────────────────────────────

    def check(
        self,
        drug_name: str,
        food_name: str,
        llm_compounds: Optional[list[str]] = None,
        llm_tiers: Optional[dict] = None,
    ) -> list[dict]:
        """
        Run all 5 physicochemical rules for the (drug, food) pair.

        Parameters
        ----------
        drug_name     : generic drug name (post-resolver)
        food_name     : food name as entered
        llm_compounds : list of compound name strings from LLM decomposition
        llm_tiers     : dict of nutrient tiers from llm_food_tiers(), used when
                        food is absent from the USDA table.
                        keys: calcium, vitk, iron, potassium, tyramine
                        values: "HIGH" | "MEDIUM" | "LOW"

        Returns
        -------
        List of warning dicts.  Each dict has:
          rule          : str   — one of the 5 rule names
          severity      : str   — HIGH / MEDIUM
          mechanism     : str   — short clinical description
          evidence      : str   — what triggered the rule
          drug_flag     : str   — which sensitivity flag matched
          food_signal   : str   — what food-side signal triggered
        """
        if llm_compounds is None:
            llm_compounds = []
        if llm_tiers is None:
            llm_tiers = {}

        drug_row = self._lookup_drug(drug_name)
        food_row = self._lookup_food(food_name)

        warnings = []

        warnings += self._rule_chelation(drug_row, food_row, food_name, llm_compounds, llm_tiers)
        warnings += self._rule_vitk(drug_row, food_row, food_name, llm_compounds, llm_tiers)
        warnings += self._rule_tyramine(drug_row, food_row, food_name, llm_compounds, llm_tiers)
        warnings += self._rule_potassium(drug_row, food_row, food_name, llm_compounds, llm_tiers)
        warnings += self._rule_acid(drug_row, food_row, food_name, llm_compounds)

        return warnings

    # ── Lookup helpers ─────────────────────────────────────────────────────────

    def _lookup_drug(self, name: str) -> Optional[pd.Series]:
        key = name.strip().lower()
        key = DRUG_ALIASES.get(key, key)
        # Exact match first
        if key in self._drug_index:
            return self._drug_index[key]
        # Substring: drug table name contains the query (handles salts)
        for k, row in self._drug_index.items():
            if key in k or k in key:
                return row
        return None

    def _lookup_food(self, name: str) -> Optional[pd.Series]:
        key = name.strip().lower()
        if key in self._food_index:
            return self._food_index[key]

        # Contextual entries (e.g., "pizza without cheese") should not be
        # auto-mapped to a generic base dish row via fuzzy overlap.
        if _has_context_modifiers(key):
            return None

        # Token-overlap retrieval with quality tie-breaks.
        # Prefer rows that have richer tier coverage over sparse UNKNOWN rows.
        q_tokens = _food_tokens(key)
        best_key = None
        best_row = None
        best_tuple = (-1, -1, -1)  # (overlap, known_tiers, -name_len)

        tier_cols = (
            "calcium_tier", "vitk_tier", "iron_tier",
            "potassium_tier", "magnesium_tier", "zinc_tier", "tyramine_tier",
        )

        for k, row in self._food_index.items():
            k_tokens = _food_tokens(k)
            overlap = len(q_tokens & k_tokens)
            if overlap == 0:
                continue
            known_tiers = sum(str(row.get(c, "UNKNOWN")).upper() != "UNKNOWN" for c in tier_cols)
            score = (overlap, known_tiers, -len(k))
            if score > best_tuple:
                best_tuple = score
                best_key = k
                best_row = row

        if best_row is not None:
            return best_row

        # Fallback: substring with same quality tie-break to avoid last-match overwrite.
        best_tuple = (-1, -1)
        for k, row in self._food_index.items():
            if key in k or k in key:
                known_tiers = sum(
                    str(row.get(c, "UNKNOWN")).upper() != "UNKNOWN"
                    for c in ("calcium_tier", "vitk_tier", "iron_tier", "potassium_tier", "tyramine_tier")
                )
                score = (known_tiers, -len(k))
                if score > best_tuple:
                    best_tuple = score
                    best_key = k
                    best_row = row
        return best_row

    def _flag(self, row: Optional[pd.Series], col: str) -> bool:
        if row is None:
            return False
        return bool(row.get(col, False))

    def _tier(self, row: Optional[pd.Series], col: str) -> str:
        """Return tier string (HIGH/MEDIUM/LOW/UNKNOWN), or UNKNOWN if row missing."""
        if row is None:
            return "UNKNOWN"
        return str(row.get(col, "UNKNOWN")).upper()

    # ── Rule 1: CHELATION_RISK ────────────────────────────────────────────────
    def _rule_chelation(self, drug_row, food_row, food_name, llm_compounds, llm_tiers):
        # Safety guard: VKA anticoagulants should not emit cation chelation warnings.
        if self._flag(drug_row, "vka"):
            return []

        if not self._flag(drug_row, "cation_sensitive"):
            return []

        # Priority: USDA table > llm_tiers > LLM compound signals
        cation_tier = self._tier(food_row, "calcium_tier")
        iron_tier   = self._tier(food_row, "iron_tier")

        # llm_tiers fallback when USDA has no data
        if cation_tier == "UNKNOWN" and "calcium" in llm_tiers:
            cation_tier = llm_tiers["calcium"].upper()
        if iron_tier == "UNKNOWN" and "iron" in llm_tiers:
            iron_tier = llm_tiers["iron"].upper()

        llm_match = _llm_hit(llm_compounds, LLM_CATION_SIGNALS)

        food_signal = None
        if cation_tier in ("HIGH", "MEDIUM"):
            food_signal = f"calcium_{cation_tier.lower()}"
        if iron_tier in ("HIGH", "MEDIUM"):
            food_signal = food_signal or f"iron_{iron_tier.lower()}"
        if llm_match and food_signal is None:
            food_signal = f"LLM:{llm_match}"

        if food_signal is None:
            return []

        if food_signal.startswith("LLM:"):
            trigger_compound = llm_match or food_signal.split(":", 1)[-1]
        elif food_signal.startswith("calcium_"):
            trigger_compound = "Calcium"
        elif food_signal.startswith("iron_"):
            trigger_compound = "Iron"
        else:
            trigger_compound = "Unknown"
        trigger_source = _source_from_signal(food_signal)

        severity = "HIGH" if (cation_tier == "HIGH" or iron_tier == "HIGH") else "MEDIUM"

        return [{
            "rule"      : "CHELATION_RISK",
            "severity"  : severity,
            "mechanism" : (
                "Multivalent cations (Ca²⁺/Fe²⁺/Mg²⁺/Zn²⁺) in food form "
                "insoluble chelate complexes with the drug, drastically "
                "reducing oral bioavailability. Separate administration by ≥2h."
            ),
            "evidence"  : (
                f"Drug is cation-sensitive; food signal: {food_signal}; "
                f"trigger compound: {trigger_compound} (source: {trigger_source})."
            ),
            "drug_flag" : "cation_sensitive",
            "food_signal": food_signal,
            "trigger_compound": trigger_compound,
            "trigger_source": trigger_source,
        }]

    # ── Rule 2: VITAMIN_K_ANTAGONISM ─────────────────────────────────────────
    def _rule_vitk(self, drug_row, food_row, food_name, llm_compounds, llm_tiers):
        if not self._flag(drug_row, "vka"):
            return []

        vitk_tier = self._tier(food_row, "vitk_tier")
        if vitk_tier == "UNKNOWN" and "vitk" in llm_tiers:
            vitk_tier = llm_tiers["vitk"].upper()

        llm_match = _llm_hit(llm_compounds, LLM_VITK_SIGNALS)

        food_signal = None
        if vitk_tier in ("HIGH", "MEDIUM"):
            food_signal = f"vitk_{vitk_tier.lower()}"
        if llm_match:
            food_signal = food_signal or f"LLM:{llm_match}"

        if food_signal is None:
            return []

        trigger_compound = llm_match if food_signal.startswith("LLM:") else "Vitamin K1"
        trigger_source = _source_from_signal(food_signal)

        severity = "HIGH" if vitk_tier == "HIGH" else "MEDIUM"

        return [{
            "rule"      : "VITAMIN_K_ANTAGONISM",
            "severity"  : severity,
            "mechanism" : (
                "Dietary Vitamin K1 (phylloquinone) is a cofactor for "
                "clotting factors II, VII, IX, X. High intake reverses "
                "the effect of VKA anticoagulants (warfarin, acenocoumarol). "
                "Consistent daily intake is key — sudden large servings "
                "of leafy greens destabilise INR."
            ),
            "evidence"  : (
                f"Drug antagonises Vitamin K epoxide reductase; "
                f"food signal: {food_signal}; trigger compound: {trigger_compound} "
                f"(source: {trigger_source})."
            ),
            "drug_flag" : "vka",
            "food_signal": food_signal,
            "trigger_compound": trigger_compound,
            "trigger_source": trigger_source,
        }]

    # ── Rule 3: TYRAMINE_CRISIS ───────────────────────────────────────────────
    def _rule_tyramine(self, drug_row, food_row, food_name, llm_compounds, llm_tiers):
        if not self._flag(drug_row, "maoi"):
            return []

        tyr_tier  = self._tier(food_row, "tyramine_tier")
        if tyr_tier == "UNKNOWN" and "tyramine" in llm_tiers:
            tyr_tier = llm_tiers["tyramine"].upper()

        llm_match = _llm_hit(llm_compounds, LLM_TYRAMINE_SIGNALS)

        food_signal = None
        if tyr_tier in ("HIGH", "MEDIUM"):
            food_signal = f"tyramine_{tyr_tier.lower()}"
        if llm_match:
            food_signal = food_signal or f"LLM:{llm_match}"

        if food_signal is None:
            return []

        trigger_compound = llm_match if food_signal.startswith("LLM:") else "Tyramine"
        trigger_source = _source_from_signal(food_signal)

        # Tyramine + MAOI is always HIGH — hypertensive crisis is life-threatening
        return [{
            "rule"      : "TYRAMINE_CRISIS",
            "severity"  : "HIGH",
            "mechanism" : (
                "MAO inhibitors block the intestinal/hepatic metabolism of "
                "dietary tyramine. Unmetabolised tyramine displaces "
                "norepinephrine from sympathetic nerve terminals causing "
                "potentially fatal hypertensive crisis. "
                "Strict avoidance of aged/fermented foods is mandatory."
            ),
            "evidence"  : (
                f"Drug is a MAO inhibitor; food signal: {food_signal}; "
                f"trigger compound: {trigger_compound} (source: {trigger_source})."
            ),
            "drug_flag" : "maoi",
            "food_signal": food_signal,
            "trigger_compound": trigger_compound,
            "trigger_source": trigger_source,
        }]

    # ── Rule 4: POTASSIUM_OVERLOAD ────────────────────────────────────────────
    def _rule_potassium(self, drug_row, food_row, food_name, llm_compounds, llm_tiers):
        if not self._flag(drug_row, "k_sparing"):
            return []

        pota_tier = self._tier(food_row, "potassium_tier")
        if pota_tier == "UNKNOWN" and "potassium" in llm_tiers:
            pota_tier = llm_tiers["potassium"].upper()

        llm_match = _llm_hit(llm_compounds, LLM_POTASSIUM_SIGNALS)

        food_signal = None
        if pota_tier == "HIGH":
            food_signal = "potassium_high"
        elif pota_tier == "MEDIUM":
            food_signal = "potassium_medium"
        if llm_match:
            food_signal = food_signal or f"LLM:{llm_match}"

        if food_signal is None:
            return []

        trigger_compound = llm_match if food_signal.startswith("LLM:") else "Potassium"
        trigger_source = _source_from_signal(food_signal)

        severity = "HIGH" if pota_tier == "HIGH" else "MEDIUM"

        return [{
            "rule"      : "POTASSIUM_OVERLOAD",
            "severity"  : severity,
            "mechanism" : (
                "Potassium-sparing diuretics and ACE inhibitors/ARBs reduce "
                "renal potassium excretion. High dietary potassium intake "
                "combined with these drugs risks hyperkalaemia "
                "(cardiac arrhythmia, muscle weakness)."
            ),
            "evidence"  : (
                f"Drug is potassium-sparing; food signal: {food_signal}; "
                f"trigger compound: {trigger_compound} (source: {trigger_source})."
            ),
            "drug_flag" : "k_sparing",
            "food_signal": food_signal,
            "trigger_compound": trigger_compound,
            "trigger_source": trigger_source,
        }]

    # ── Rule 5: ACID_ABSORPTION_RISK ─────────────────────────────────────────
    def _rule_acid(self, drug_row, food_row, food_name, llm_compounds):
        if not self._flag(drug_row, "acid_dependent"):
            return []

        # Class-first signal from the food content table.
        acid_tier = self._tier(food_row, "acid_tier")

        # Path A: Foods known to raise gastric pH (alkalinising) can reduce
        # absorption of acid-dependent drugs.
        name_lower = food_name.lower()
        alkaline_keywords = [
            "milk", "cream", "dairy", "yogurt", "antacid",
            "bicarbonate", "soda", "alkaline water",
            "calcium carbonate", "magnesium hydroxide",
        ]
        # Path B: Highly acidic foods can worsen gastric irritation for
        # acid-sensitive/irritant medications (e.g., aspirin + lemon/citrus).
        acidic_keywords = [
            "lemon", "lime", "citrus", "orange", "grapefruit", "vinegar",
            "tomato", "acidic juice",
        ]

        food_is_alkaline = any(kw in name_lower for kw in alkaline_keywords)
        food_is_acidic = any(kw in name_lower for kw in acidic_keywords)

        llm_alkaline = _llm_hit(llm_compounds, LLM_ACID_SIGNALS)
        llm_acidic = _llm_hit(llm_compounds, LLM_ACIDIC_SIGNALS)

        if (
            acid_tier not in ("HIGH", "MEDIUM")
            and not food_is_alkaline
            and not food_is_acidic
            and llm_alkaline is None
            and llm_acidic is None
        ):
            return []

        if food_is_alkaline or llm_alkaline is not None:
            food_signal = (
                next((kw for kw in alkaline_keywords if kw in name_lower), None)
                or f"LLM:{llm_alkaline}"
            )
            trigger_compound = llm_alkaline if str(food_signal).startswith("LLM:") else food_signal
            trigger_source = _source_from_signal(food_signal)

            return [{
                "rule"      : "ACID_ABSORPTION_RISK",
                "severity"  : "MEDIUM",
                "mechanism" : (
                    "Drug requires an acidic gastric environment (pH < 3) for "
                    "dissolution and absorption. Foods or agents that raise "
                    "gastric pH (dairy, antacids) can reduce bioavailability "
                    "by 50-90%. Take drug on empty stomach or >=2h before dairy."
                ),
                "evidence"  : (
                    f"Drug is acid-dependent; food signal: {food_signal}; "
                    f"trigger compound: {trigger_compound} (source: {trigger_source})."
                ),
                "drug_flag" : "acid_dependent",
                "food_signal": food_signal,
                "trigger_compound": trigger_compound,
                "trigger_source": trigger_source,
            }]

        food_signal = (
            (f"acid_tier_{acid_tier.lower()}" if acid_tier in ("HIGH", "MEDIUM") else None)
            or next((kw for kw in acidic_keywords if kw in name_lower), None)
            or f"LLM:{llm_acidic}"
        )
        if str(food_signal).startswith("LLM:"):
            trigger_compound = llm_acidic
        elif str(food_signal).startswith("acid_tier_"):
            trigger_compound = "Acidic food load"
        else:
            trigger_compound = food_signal
        trigger_source = _source_from_signal(food_signal)

        return [{
            "rule"      : "ACID_ABSORPTION_RISK",
            "severity"  : "MEDIUM",
            "mechanism" : (
                "This combination can increase gastric irritation risk. "
                "Acidic foods can aggravate stomach lining stress from "
                "acid-sensitive drugs (for example aspirin), causing pain, "
                "heartburn, or GI discomfort."
            ),
            "evidence"  : (
                f"Drug is acid-dependent; food signal: {food_signal}; "
                f"trigger compound: {trigger_compound} (source: {trigger_source})."
            ),
            "drug_flag" : "acid_dependent",
            "food_signal": food_signal,
            "trigger_compound": trigger_compound,
            "trigger_source": trigger_source,
        }]


# ── CLI quick-test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    engine = PhysicochemicalEngine(verbose=True)
    print()

    test_cases = [
        ("Warfarin",       "Spinach",       []),
        ("Warfarin",       "Chicken",       ["Vitamin K1"]),
        ("Ciprofloxacin",  "Milk",          []),
        ("Ciprofloxacin",  "Dairy Milk",    ["Calcium"]),
        ("Phenelzine",     "Aged Cheese",   []),
        ("Phenelzine",     "Wine",          []),
        ("Spironolactone", "Banana",        []),
        ("Lisinopril",     "Potato",        []),
        ("Itraconazole",   "Milk",          []),
        ("Metformin",      "Grapefruit",    []),   # should be empty
    ]

    print(f"{'Drug':<20} {'Food':<20} {'Warnings':}")
    print("-" * 70)
    for drug, food, comps in test_cases:
        ws = engine.check(drug, food, llm_compounds=comps)
        if ws:
            for w in ws:
                print(
                    f"{drug:<20} {food:<20} "
                    f"[{w['rule']}] {w['severity']} — {w['food_signal']}"
                )
        else:
            print(f"{drug:<20} {food:<20} (no warnings)")
