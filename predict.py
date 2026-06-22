"""
Phase 5 — DFinder Fusion Predictor
Combines all three inference layers to score a drug-food interaction:

  Layer 1 — Graph Query   (graph_query.py)         : deterministic HKG enzyme overlap
  Layer 2 — Mechanistic   (mech_kge_inference.py)   : RotatE pathway scoring
  Layer 3 — Collaborative (lightgcn_inference.py)   : LightGCN latent similarity

Fusion Strategy
    Piecewise confidence hand-off:
        if LGN >= 0.98: trust LGN directly (no mechanistic downscale)
        elif LGN >= 0.90: 0.80*LGN + 0.20*Mechanistic
        elif LGN >= 0.70: 0.70*LGN + 0.30*Mechanistic
        else            : 0.35*LGN + 0.65*Mechanistic

    Mechanistic support combines HKG + KGE + clinical-safety-gate signals using
    bounded noisy-or aggregation, with small bonuses for cross-layer agreement.

Confidence Tiers
  HIGH         : fusion_score >= 0.70  OR  (graph + kge both found)
  MEDIUM       : fusion_score >= 0.45  OR  any mechanistic evidence + lgn >= 0.5
  LOW          : fusion_score >= 0.20  OR  any layer has a signal
  INSUFFICIENT : no layer provided a signal

Flags
  ALL_LAYERS_AGREE  — all three layers indicate likely interaction
  HIDDEN_MECHANISM  — LGN high (>=0.80) but no mechanistic path found
  THEORETICAL_RISK  — mechanistic evidence but LGN low (< 0.40)
  EXPERT_REVIEW     — LGN very high (>=0.90) with any mechanistic signal

Usage:
    from predict import DFinder
    df = DFinder()
    result = df.predict("Warfarin", "Grapefruit")
    print(result["verdict"])

    # batch
    results = df.batch_predict([("Warfarin","Grapefruit"), ("Metformin","Green Tea")])

    # CLI
    python predict.py --drug Warfarin --food Grapefruit
    python predict.py --validate          # run on all 889 unseen pairs
"""

import argparse
import json
import os
import re
import numpy as np
import pandas as pd
from pathlib import Path

# ── Import translator for dual-view architecture ──────────────────────────────
from translator import create_dual_view, format_compounds

# ── Paths ───────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parent
VAL_DIR     = ROOT / "validation_splits"
UNSEEN      = VAL_DIR / "validation_unseen.csv"
FOOD_ID_MAP = ROOT / "DFinder-main/data/unified-DFI/id_maps/food_id_map.csv"

# ── Piecewise fusion config ─────────────────────────────────────────────────
LGN_STRONG_CONFIRM = 0.98
LGN_BAND_2         = 0.90
LGN_BAND_3         = 0.70

# Compound-level aggregation limit for noisy-or
MECH_TOP_K_COMPOUNDS = 5

# Small mechanism reinforcement bonuses
BONUS_COMPOUND_CONCORDANCE = 0.03  # same compound appears in Graph + KGE
BONUS_ENZYME_CONVERGENCE   = 0.02  # different compounds converge on same enzyme

# Option 2b: HKG-priority mechanistic weighting (physicochemical remains outside)
MECH_HKG_WEIGHT = 0.65
MECH_KGE_WEIGHT = 0.35

# Normalization denominators (empirical from Phase validation runs)
GRAPH_MAX  = 120.0   # graph_query weighted scores rarely exceed ~100
KGE_MAX    = 115.0   # mech kge max observed 111.42; add headroom
LGN_SCALE  = 1.0     # LGN returns sigmoid [0,1]

# Fusion score thresholds (used for confidence tiers)
# HIGH: >= 0.70, MEDIUM: >= 0.45, LOW: >= 0.20
TH_MEDIUM = 0.45
TH_LOW    = 0.20

def get_confidence_tier(score, layer0_fired=False):
    """
    Maps a fusion score to a discrete confidence tier based on corrected, consistent thresholds.
    The physicochemical gate (layer0_fired) is the only override.
    """
    if layer0_fired:
        return "HIGH"
    if score >= 0.70:
        return "HIGH"
    if score >= 0.45:
        return "MEDIUM"
    if score >= 0.20:
        return "LOW"
    return "INSUFFICIENT"

# LGN-specific confidence thresholds
LGN_HIGH_CONF_TH = 0.90  # Strong learned signal even when HKG/KGE are silent
LGN_MEDIUM_CONF_TH = 0.65  # Useful prediction signal without mechanistic proof

# LGN flags
LGN_HIDDEN_TH         = 0.80   # LGN >= 0.80 with no mechanistic evidence → HIDDEN_MECHANISM
LGN_THEORETICAL_UPPER = 0.40   # If mechanistic evidence but LGN < 0.40 → THEORETICAL_RISK
LGN_EXPERT_TH         = 0.90   # LGN >= 0.90 + any mech evidence → EXPERT_REVIEW
MECHANISM_ASSEMBLY_ENABLED = os.getenv("MECHANISM_ASSEMBLY_ENABLED", "1") != "0"


def _kge_confidence_from_score(score: float) -> str:
    if score < 70.0:
        return "TENTATIVE"
    if score < 85.0:
        return "MODERATE"
    return "HIGH"


def _confidence_weight(level: str) -> float:
    mapping = {
        "HIGH": 0.9,
        "MODERATE": 0.6,
        "TENTATIVE": 0.2,
    }
    return mapping.get(level, 0.2)


def _downgrade_confidence(level: str) -> str:
    if level == "HIGH":
        return "MODERATE"
    if level == "MODERATE":
        return "TENTATIVE"
    return "TENTATIVE"


def _noisy_or(scores: list[float]) -> float:
    vals = [float(np.clip(s, 0.0, 1.0)) for s in scores if s is not None]
    if not vals:
        return 0.0
    prod = 1.0
    for v in vals:
        prod *= (1.0 - v)
    return float(np.clip(1.0 - prod, 0.0, 1.0))


def _normalize_token(t: str) -> str:
    tok = str(t or "").strip().lower()
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        tok = tok[:-1]
    return tok


def _extract_food_context(food: str) -> dict:
    text = str(food or "").strip().lower()
    has_modifiers = bool(re.search(r"\b(without|no|sans|only)\b", text))

    base = re.split(r"\b(?:without|no|sans)\b", text, maxsplit=1)[0].strip(" ,+-/")
    if not base:
        base = text

    excluded: set[str] = set()
    for m in re.finditer(r"\b(?:without|no|sans)\s+([a-z0-9][a-z0-9\s,+/&-]*)", text):
        chunk = m.group(1)
        chunk = re.split(r"\b(?:but|except)\b", chunk, maxsplit=1)[0]
        for part in re.split(r",|/|\+|&|\band\b", chunk):
            for w in re.findall(r"[a-z0-9]+", part):
                nw = _normalize_token(w)
                if nw and nw not in {"without", "no", "sans"}:
                    excluded.add(nw)

    only_tokens: set[str] = set()
    for m in re.finditer(r"\b([a-z0-9]+)\s+only\b", text):
        only_tokens.add(_normalize_token(m.group(1)))

    return {
        "raw": text,
        "base_food": base,
        "has_modifiers": has_modifiers,
        "excluded_ingredients": sorted(x for x in excluded if x),
        "only_ingredients": sorted(x for x in only_tokens if x),
    }


def _apply_contextual_overrides(food_context: dict, llm_compounds: list[dict], llm_tiers: dict) -> tuple[list[dict], dict]:
    compounds = list(llm_compounds or [])
    tiers = dict(llm_tiers or {})
    excluded = set(food_context.get("excluded_ingredients") or [])
    only_tokens = set(food_context.get("only_ingredients") or [])

    dairy_words = {"cheese", "mozzarella", "dairy", "milk", "cream", "yogurt", "fromage"}
    meat_words = {"meat", "beef", "lamb", "mutton", "chicken", "turkey", "veal", "steak", "ham", "sausage"}
    tomato_words = {"tomato", "tomatoes", "sauce"}

    suppress_terms: set[str] = set()

    if excluded & dairy_words:
        suppress_terms.update({"calcium", "ca2+", "magnesium", "tyramine", "casein", "milk protein"})
        tiers["calcium"] = "LOW"
        tiers["tyramine"] = "LOW"

    if excluded & meat_words:
        suppress_terms.update({"iron", "fe2+", "fe3+", "zinc", "tyramine"})
        tiers["iron"] = "LOW"
        tiers["tyramine"] = "LOW"

    # Tomato-only phrases should not inherit dairy/meat assumptions from generic dishes.
    if only_tokens and (only_tokens & tomato_words):
        suppress_terms.update({"calcium", "ca2+", "magnesium", "iron", "fe2+", "fe3+", "tyramine", "zinc"})
        tiers["calcium"] = "LOW"
        tiers["iron"] = "LOW"
        tiers["tyramine"] = "LOW"

    if suppress_terms:
        filtered: list[dict] = []
        for c in compounds:
            name = str(c.get("name") or "").strip().lower()
            if any(term in name for term in suppress_terms):
                continue
            filtered.append(c)
        compounds = filtered

    return compounds, tiers


def _warning_blocked_by_context(warning: dict, food_context: dict) -> bool:
    excluded = set(food_context.get("excluded_ingredients") or [])
    only_tokens = set(food_context.get("only_ingredients") or [])
    if not excluded and not only_tokens:
        return False

    comp = str(warning.get("trigger_compound") or "").lower()
    sig = str(warning.get("food_signal") or "").lower()

    dairy_words = {"cheese", "mozzarella", "dairy", "milk", "cream", "yogurt", "fromage"}
    meat_words = {"meat", "beef", "lamb", "mutton", "chicken", "turkey", "veal", "steak", "ham", "sausage"}

    if excluded & dairy_words:
        if any(k in comp for k in ("calcium", "ca2+", "magnesium", "tyramine", "casein")):
            return True
        if "calcium_" in sig:
            return True

    if excluded & meat_words:
        if any(k in comp for k in ("iron", "fe2+", "fe3+", "zinc", "tyramine")):
            return True
        if "iron_" in sig:
            return True

    if only_tokens and (only_tokens & {"tomato", "tomatoes", "sauce"}):
        if any(k in comp for k in ("calcium", "ca2+", "magnesium", "iron", "fe2+", "fe3+", "zinc", "tyramine")):
            return True
        if any(k in sig for k in ("calcium_", "iron_", "tyramine_")):
            return True

    return False


class DFinder:
    """3-layer drug-food interaction predictor."""

    def __init__(self, verbose: bool = True):
        if verbose:
            print("=" * 60)
            print("  DFinder v1.0 — Initialising all layers")
            print("=" * 60)

        # Layer 1: Graph Query
        from graph_query import GraphQueryEngine
        self.graph = GraphQueryEngine(verbose=verbose)

        # Layer 2: Mechanistic KGE
        from mech_kge_inference import MechKGEInference
        self.kge = MechKGEInference(verbose=verbose)

        # Layer 3: LightGCN
        from lightgcn_inference import LightGCNInference
        self.lgn = LightGCNInference(verbose=verbose)

        # Phase 8: Algerian trade-name resolver
        from drug_resolver import DrugResolver
        self.resolver = DrugResolver(verbose=verbose)

        # Phase 7: LLM food bridge
        from compound_resolver import CompoundResolver
        self.compound_resolver = CompoundResolver(verbose=verbose)
        from llm_decompose import llm_decompose, llm_food_tiers
        self._llm_decompose  = llm_decompose
        self._llm_food_tiers = llm_food_tiers
        na_dish_file = ROOT / "data" / "na_dish_compounds.json"
        if na_dish_file.exists():
            with open(na_dish_file, encoding="utf-8") as f:
                self._na_dish_compounds = json.load(f)
        else:
            self._na_dish_compounds = {}
        # Build known-food set (foods already in the pipeline graph)
        _food_df = pd.read_csv(FOOD_ID_MAP)
        self._known_foods: set[str] = set(
            _food_df["name"].dropna().str.strip().str.lower()
        )
        # Initialize FooDB lookup (priority #2 after NA seed)
        from foodb_lookup import FooDBLookup
        self._foodb_lookup = FooDBLookup(verbose=verbose)

        if verbose:
            print(f"Phase 7 bridge ready: {len(self._known_foods):,} known foods")

        # Phase 9: Rule-based Deterministic Clinical Safety Gate (Layer 0)
        # (implemented in physicochemical.py but conceptually a deterministic
        # clinical safety gate for rule-based checks such as chelation risk)
        from physicochemical import PhysicochemicalEngine
        self.phys_engine = PhysicochemicalEngine(verbose=verbose)

        if verbose:
            print("\nAll layers ready. DFinder is up.")
            print("=" * 60)

    def _get_drug_profile_anchor(self, drug: str) -> dict:
        d = str(drug or "").strip().lower()

        # Minimal anchor table for Phase A shadow mode.
        if d in {"warfarin", "coumadin"}:
            return {
                "primary_enzyme": "CYP2C9",
                "secondary_enzymes": ["CYP3A4"],
                "dominant_mechanism_class": "PHARMACODYNAMIC",
                "drug_family": "VKA_ANTICOAGULANT",
            }

        return {
            "primary_enzyme": None,
            "secondary_enzymes": [],
            "dominant_mechanism_class": "ENZYMATIC",
            "drug_family": "UNKNOWN",
        }

    def _is_rule_eligible(self, rule_name: str, profile: dict) -> bool:
        rule = str(rule_name or "").upper()
        family = str(profile.get("drug_family") or "UNKNOWN").upper()

        if rule == "VITAMIN_K_ANTAGONISM":
            return family == "VKA_ANTICOAGULANT"

        # Phase A: conservative default to preserve current behavior while exposing suppression metadata.
        if rule == "CHELATION_RISK" and family == "VKA_ANTICOAGULANT":
            return False

        if rule in {"CHELATION_RISK", "TYRAMINE_CRISIS", "ACID_ABSORPTION_RISK", "POTASSIUM_OVERLOAD"}:
            return True

        return True

    def _build_mechanism_assembly_shadow(
        self,
        drug: str,
        food: str,
        graph_enzymes: list,
        kge_enzymes: list,
        kge_score_raw: float,
        norm_lgn: float,
        phys_warnings: list,
    ) -> dict:
        profile = self._get_drug_profile_anchor(drug)
        primary = str(profile.get("primary_enzyme") or "").upper()
        secondary = {str(e).upper() for e in profile.get("secondary_enzymes") or []}

        suppressed = []
        ranked = []

        kge_conf = _kge_confidence_from_score(float(kge_score_raw or 0.0))
        downgraded_kge_conf = kge_conf

        kge_top = kge_enzymes[0] if kge_enzymes else None
        kge_enzyme = str((kge_top or {}).get("enzyme") or "").upper()

        if primary and kge_enzyme and (kge_enzyme != primary) and (kge_enzyme not in secondary):
            downgraded_kge_conf = _downgrade_confidence(kge_conf)
            if downgraded_kge_conf == "TENTATIVE" and kge_conf == "TENTATIVE":
                suppressed.append({
                    "class": "KGE_PATHWAY",
                    "source": ["KGE"],
                    "reason": "profile_conflict_low_confidence",
                    "policy": "POLICY_1",
                })
            else:
                suppressed.append({
                    "class": "KGE_PATHWAY",
                    "source": ["KGE"],
                    "reason": "profile_conflict_downgraded",
                    "policy": "POLICY_1",
                    "from": kge_conf,
                    "to": downgraded_kge_conf,
                })

        if kge_top and not (kge_conf == "TENTATIVE" and downgraded_kge_conf == "TENTATIVE" and primary and kge_enzyme and (kge_enzyme != primary) and (kge_enzyme not in secondary)):
            model_signal = max(float(norm_lgn or 0.0), _confidence_weight(downgraded_kge_conf))
            ranked.append({
                "class": "KGE_PATHWAY",
                "source": ["KGE"],
                "confidence": downgraded_kge_conf,
                "final_score": round(0.2 + 0.3 * model_signal, 4),
                "user_visible": downgraded_kge_conf != "TENTATIVE",
                "text": f"{kge_top.get('compound', 'Pathway')} -> {kge_top.get('enzyme', 'enzyme')} ({downgraded_kge_conf})",
            })

        for w in phys_warnings or []:
            rule = str(w.get("rule") or "").upper()
            eligible = self._is_rule_eligible(rule, profile)
            if not eligible:
                suppressed.append({
                    "class": rule,
                    "source": ["LAYER0"],
                    "reason": "drug_not_eligible",
                    "policy": "POLICY_2",
                })
                continue

            clinical_prior = 1.0 if rule == "VITAMIN_K_ANTAGONISM" else 0.6
            model_signal = max(float(norm_lgn or 0.0), _confidence_weight(downgraded_kge_conf))
            final_score = 0.5 * clinical_prior + 0.3 * model_signal + 0.2 * 1.0
            ranked.append({
                "class": rule,
                "source": ["LAYER0"],
                "confidence": str(w.get("severity") or "MEDIUM").upper(),
                "final_score": round(final_score, 4),
                "user_visible": True,
                "text": str(w.get("mechanism") or ""),
                "trigger_compound": str(w.get("trigger_compound") or "").strip() or None,
                "trigger_source": str(w.get("trigger_source") or "").strip() or None,
                "food_signal": str(w.get("food_signal") or "").strip() or None,
            })

        ranked.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
        lead = ranked[0] if ranked else None

        hormonal_mode = "tier_confirmed"
        if profile.get("dominant_mechanism_class") == "PHARMACODYNAMIC":
            hormonal_mode = "secondary_modifier_only"

        return {
            "version": "v1-shadow",
            "lead_mechanism": lead,
            "ranked_mechanisms": ranked,
            "suppressed_mechanisms": suppressed,
            "dominant_mechanism_class": profile.get("dominant_mechanism_class"),
            "profile_anchor": {
                "primary_enzyme": profile.get("primary_enzyme"),
                "secondary_enzymes": profile.get("secondary_enzymes") or [],
                "mechanism_class": profile.get("dominant_mechanism_class"),
            },
            "hormonal_wording_policy": {
                "mode": hormonal_mode,
                "show_arrow": False,
                "show_numeric_in_user_text": False,
                "dominant_enzyme": profile.get("primary_enzyme"),
                "message_template": "Hormonal phase confirms current tier.",
            },
        }

    def _build_explanation_from_assembly(
        self,
        drug: str,
        food: str,
        assembly: dict,
        fusion_score: float,
        graph_score_raw: float,
        kge_score_raw: float,
        lgn_score: float,
        norm_graph: float,
        norm_kge: float,
        norm_lgn: float,
        graph_enzymes: list,
        kge_enzymes: list,
    ) -> str:
        ranked = list((assembly or {}).get("ranked_mechanisms") or [])
        user_mechanisms = [m for m in ranked if bool(m.get("user_visible", True))]
        lead = (assembly or {}).get("lead_mechanism")

        if not user_mechanisms and not lead:
            return f"No significant interaction signal detected for {drug} × {food}."

        lead_item = lead or user_mechanisms[0]
        lead_class = str(lead_item.get("class") or "MECHANISM")
        lead_conf = str(lead_item.get("confidence") or "MODERATE")

        # Compact user-facing phrasing in Phase B.
        if lead_class == "VITAMIN_K_ANTAGONISM":
            lead_text = f"Primary mechanism: pharmacodynamic antagonism (Vitamin K pathway) for {drug} × {food}."
        else:
            lead_text = f"Primary mechanism: {lead_class.replace('_', ' ').title()} ({lead_conf})."

        lead_sources = [str(s).upper() for s in (lead_item.get("source") or [])]
        if "LAYER0" in lead_sources:
            trig = str(lead_item.get("trigger_compound") or "").strip()
            trig_src = str(lead_item.get("trigger_source") or "").strip()
            trig_sig = str(lead_item.get("food_signal") or "").strip()
            if trig:
                lead_text += f" Layer 0 trigger compound: {trig}"
                if trig_src:
                    lead_text += f" ({trig_src})"
                if trig_sig:
                    lead_text += f" from signal {trig_sig}"
                lead_text += "."

        secondary = [m for m in user_mechanisms if m is not lead_item][:2]
        if secondary:
            sec_text = ", ".join(str(m.get("class") or "").replace("_", " ").title() for m in secondary)
            lead_text += f" Secondary supported mechanisms: {sec_text}."

        enzyme_evidence = []
        for e in (graph_enzymes or [])[:3]:
            enz = str((e or {}).get("enzyme") or "").strip()
            if enz:
                enzyme_evidence.append(enz)
        for enz in (kge_enzymes or [])[:3]:
            n = str((enz or {}).get("enzyme") or "").strip()
            if n:
                enzyme_evidence.append(n)
        enzyme_evidence = list(dict.fromkeys(enzyme_evidence))[:3]

        if enzyme_evidence:
            lead_text += f" Secondary enzymatic evidence: {', '.join(enzyme_evidence)}."

        lead_text += (
            f" Layer evidence: Graph {float(graph_score_raw or 0.0):.3f} "
            f"(norm {float(norm_graph or 0.0):.3f}), "
            f"KGE {float(kge_score_raw or 0.0):.3f} "
            f"(norm {float(norm_kge or 0.0):.3f}), "
            f"LightGCN {float(lgn_score or 0.0):.3f} "
            f"(norm {float(norm_lgn or 0.0):.3f}); "
            f"Fusion {float(fusion_score or 0.0):.4f}."
        )
        return lead_text

    def _build_mechanistic_support(
        self,
        graph_score_raw: float,
        kge_score_raw: float,
        graph_enzymes: list,
        kge_enzymes: list,
        phys_warnings: list,
    ) -> tuple[float, dict]:
        """
        Build a bounded mechanistic support score in [0,1].
                - Graph and KGE supports are combined with HKG-priority weighting.
        - Graph/KGE use top-k compound paths to prevent compound-count inflation.
        - Concordance/convergence bonuses are additive but capped.
        - Physicochemical rules are handled in the dedicated tier-override block,
          not inside mechanistic support (option 2).
        """
        norm_graph = float(np.clip(float(graph_score_raw or 0.0) / GRAPH_MAX, 0.0, 1.0))
        norm_kge   = float(np.clip(float(kge_score_raw or 0.0) / KGE_MAX, 0.0, 1.0))

        # Graph compound support (top-k compounds by strongest mapped path score)
        graph_compound_best: dict[str, float] = {}
        graph_enzyme_set: set[str] = set()
        for edge in (graph_enzymes or [])[:MECH_TOP_K_COMPOUNDS]:
            enz = str(edge.get("enzyme") or "").strip()
            if enz:
                graph_enzyme_set.add(enz)
            base_weight = float(edge.get("weight") or 1.0)
            # Map enzyme weight range roughly into [0,1].
            path_score = float(np.clip(base_weight / 10.0, 0.0, 1.0))
            compounds = edge.get("compounds") or []
            for c in compounds:
                cname = str(c).strip().lower()
                if not cname:
                    continue
                graph_compound_best[cname] = max(graph_compound_best.get(cname, 0.0), path_score)

        graph_compound_scores = sorted(graph_compound_best.values(), reverse=True)[:MECH_TOP_K_COMPOUNDS]
        graph_compound_support = _noisy_or(graph_compound_scores)
        graph_support = max(norm_graph, graph_compound_support)

        # KGE compound support (top-k compounds by strongest weighted path)
        kge_compound_best: dict[str, float] = {}
        kge_enzyme_set: set[str] = set()
        for edge in (kge_enzymes or [])[:MECH_TOP_K_COMPOUNDS * 2]:
            enz = str(edge.get("enzyme") or "").strip()
            if enz:
                kge_enzyme_set.add(enz)
            cname = str(edge.get("compound") or "").strip().lower()
            if not cname:
                continue
            # Weighted values vary by relation and enzyme importance; keep bounded.
            weighted = float(edge.get("weighted") or 0.0)
            path_score = float(np.clip(weighted / 10.0, 0.0, 1.0))
            kge_compound_best[cname] = max(kge_compound_best.get(cname, 0.0), path_score)

        kge_compound_scores = sorted(kge_compound_best.values(), reverse=True)[:MECH_TOP_K_COMPOUNDS]
        kge_compound_support = _noisy_or(kge_compound_scores)
        kge_support = max(norm_kge, kge_compound_support)

        # Option 2: keep physicochemical logic outside mechanistic support
        # to avoid double-counting with the tier-override path.
        # Option 2b: give explicit priority to HKG over KGE.
        base_support = float(np.clip(
            MECH_HKG_WEIGHT * graph_support + MECH_KGE_WEIGHT * kge_support,
            0.0,
            1.0,
        ))

        # Cross-layer reinforcement.
        graph_comp_set = set(graph_compound_best.keys())
        kge_comp_set = set(kge_compound_best.keys())
        same_compound = len(graph_comp_set.intersection(kge_comp_set)) > 0
        same_enzyme = len(graph_enzyme_set.intersection(kge_enzyme_set)) > 0

        bonus = 0.0
        if same_compound:
            bonus += BONUS_COMPOUND_CONCORDANCE
        if same_enzyme:
            bonus += BONUS_ENZYME_CONVERGENCE

        mech_support = float(np.clip(base_support + bonus, 0.0, 1.0))
        details = {
            "graph_support": round(graph_support, 4),
            "kge_support": round(kge_support, 4),
            "phys_support": 0.0,
            "phys_in_mech_support": False,
            "hkg_priority_weighting": {
                "hkg_weight": MECH_HKG_WEIGHT,
                "kge_weight": MECH_KGE_WEIGHT,
            },
            "base_support": round(base_support, 4),
            "bonus": round(bonus, 4),
            "same_compound": same_compound,
            "same_enzyme": same_enzyme,
        }
        return mech_support, details

    @staticmethod
    def _piecewise_fusion(norm_lgn: float, mech_support: float) -> float:
        # Certainty ceiling: LightGCN is authoritative at extreme confidence.
        l = float(np.clip(norm_lgn, 0.0, 1.0))
        m = float(np.clip(mech_support, 0.0, 1.0))
        if l >= LGN_STRONG_CONFIRM:
            return l

        # Bayesian-style self-weighted combination.
        # Each signal contributes proportionally to its own strength.
        signals: list[tuple[float, float]] = []
        if l > 0.0:
            signals.append((l, 0.70))
        if m > 0.0:
            signals.append((m, 0.30))

        weighted_sum = sum(s * w * s for s, w in signals)
        weight_sum = sum(w * s for s, w in signals)
        if weight_sum <= 0.0:
            return 0.0
        return float(np.clip(weighted_sum / weight_sum, 0.0, 1.0))

    # ── Core predict ─────────────────────────────────────────────────────────
    def predict(self, drug_name: str, food_name: str, language: str = "en") -> dict:
        """
        Predict the interaction risk for a (drug, food) pair.
        Returns a comprehensive result dict with dual-view (simple + technical explanations).
        Supports translation to 'en', 'fr', 'ar' (language='en' by default).
        """
        # ── Phase 8: Trade-name resolution ───────────────────────────────
        resolution   = self.resolver.resolve(drug_name)
        drug_input   = drug_name.strip()          # keep original for output
        drug         = resolution["pipeline_name"]  # generic name for pipeline

        food = food_name.strip()
        food_key = food.lower()
        food_context = _extract_food_context(food)
        force_contextual_inference = bool(food_context.get("has_modifiers"))

        # ── Phase 7: Food bridge (NA seed -> FooDB -> LLM) ─
        llm_compounds    = []   # resolved compound dicts
        llm_used         = False
        llm_tiers        = {}   # nutrient tiers from LLM (Phase 9 fallback)
        food_in_pipeline = food_key in self._known_foods
        local_na_seed    = self._na_dish_compounds.get(food_key, [])
        foodb_compounds  = self._foodb_lookup.get_compounds(food) if not force_contextual_inference else None

        # Priority 1: NA seed (Algerian manual curation)
        if local_na_seed and not force_contextual_inference:
            for cname in local_na_seed:
                resolved_c = self.compound_resolver.resolve(cname)
                if resolved_c["branch"] != "none":
                    resolved_c["source"] = "NA_SEED"
                    llm_compounds.append(resolved_c)
            llm_used = len(llm_compounds) > 0

        # Priority 2: FooDB (database-backed food-to-compound mappings)
        elif foodb_compounds and not force_contextual_inference:
            for cname in foodb_compounds:
                resolved_c = self.compound_resolver.resolve(cname)
                if resolved_c["branch"] != "none":
                    resolved_c["source"] = "FOODB"
                    llm_compounds.append(resolved_c)
            llm_used = len(llm_compounds) > 0

        # Priority 3: LLM (fallback for unknown foods)
        if force_contextual_inference or (not food_in_pipeline and not local_na_seed and not foodb_compounds):
            raw_names = self._llm_decompose(food)
            for cname in raw_names:
                resolved_c = self.compound_resolver.resolve(cname)
                if resolved_c["branch"] != "none":
                    resolved_c["source"] = "LLM_SOURCED"
                    llm_compounds.append(resolved_c)
            llm_used  = len(llm_compounds) > 0
            llm_tiers = self._llm_food_tiers(food)   # always fetch tiers for unknown foods

        llm_compounds, llm_tiers = _apply_contextual_overrides(food_context, llm_compounds, llm_tiers)

        # ── Phase 9: Layer 0 — Deterministic Clinical Safety Gate ──────
        llm_compound_names = [c["name"] for c in llm_compounds]
        phys_warnings = self.phys_engine.check(
            drug, food,
            llm_compounds=llm_compound_names,
            llm_tiers=llm_tiers,
        )

        if force_contextual_inference and phys_warnings:
            phys_warnings = [w for w in phys_warnings if not _warning_blocked_by_context(w, food_context)]

        # ── Layer 1: Graph Query ──────────────────────────────────────────
        g = self.graph.query(drug, food)
        graph_score_raw = float(g.get("score", 0.0))
        graph_found     = g.get("found", False)
        graph_enzymes   = g.get("shared_enzymes", g.get("enzymes", []))

        # ── Layer 2: Mechanistic KGE ──────────────────────────────────────
        k = self.kge.score_by_name(drug, food)
        kge_score_raw   = float(k.get("kge_score", 0.0))
        kge_found       = k.get("found", False)
        kge_enzymes     = k.get("shared_enzymes", [])

        # Phase 7 KGE augmentation: score each LLM compound individually
        # and take the best result if it beats the direct food score
        llm_kge_best    = {"score": 0.0, "found": False, "enzymes": [], "compound": None}
        for rc in llm_compounds:
            if rc["branch"] == "kge":
                ck = self.kge.score_by_name(drug, rc["name"])
                c_score = float(ck.get("kge_score", 0.0))
                if c_score > llm_kge_best["score"]:
                    llm_kge_best = {
                        "score"    : c_score,
                        "found"    : ck.get("found", False),
                        "enzymes"  : ck.get("shared_enzymes", []),
                        "compound" : rc["name"],
                    }
        # Use LLM-sourced KGE result if it beats the direct food score
        if llm_kge_best["found"] and llm_kge_best["score"] > kge_score_raw:
            kge_score_raw = llm_kge_best["score"]
            kge_found     = True
            kge_enzymes   = llm_kge_best["enzymes"]

        # ── Layer 3: LightGCN ─────────────────────────────────────────────
        lgn_result = self.lgn.score_by_name(drug, food)
        lgn_score = lgn_result.get("score") if lgn_result else None
        if lgn_score is None:
            lgn_score = 0.0
        lgn_score = float(lgn_score)

        # Phase 7 LGN augmentation: mirror KGE augmentation — score each LLM
        # compound in LGN and take the best if it beats the direct food score.
        # This handles novel foods (e.g. Pizza) whose compounds ARE in the LGN
        # food map even though the whole food is not.
        llm_lgn_best = {"score": 0.0, "compound": None}
        if lgn_score == 0.0 and llm_compounds:
            for rc in llm_compounds:
                cr = self.lgn.score_by_name(drug, rc["name"])
                c_score = float(cr.get("score") or 0.0)
                if cr.get("food_found") and c_score > llm_lgn_best["score"]:
                    llm_lgn_best = {"score": c_score, "compound": rc["name"]}
        if llm_lgn_best["compound"] and llm_lgn_best["score"] > lgn_score:
            lgn_score = llm_lgn_best["score"]

        # ── Normalise & piecewise fuse ────────────────────────────────────
        norm_graph = min(graph_score_raw / GRAPH_MAX, 1.0)
        norm_kge   = min(kge_score_raw   / KGE_MAX,   1.0)
        norm_lgn   = float(np.clip(lgn_score, 0.0, 1.0))

        mech_support, mech_details = self._build_mechanistic_support(
            graph_score_raw=graph_score_raw,
            kge_score_raw=kge_score_raw,
            graph_enzymes=graph_enzymes,
            kge_enzymes=kge_enzymes,
            phys_warnings=phys_warnings,
        )

        fusion_score = self._piecewise_fusion(norm_lgn, mech_support)
        fusion_score = round(float(fusion_score), 4)

        # ── Confidence tier ───────────────────────────────────────────────
        mech_found = graph_found or kge_found

        if (graph_found and kge_found) or norm_lgn >= LGN_HIGH_CONF_TH:
            tier = "HIGH"
        elif fusion_score >= TH_MEDIUM or (mech_found and norm_lgn >= 0.5) or norm_lgn >= LGN_MEDIUM_CONF_TH:
            tier = "MEDIUM"
        elif fusion_score >= TH_LOW or mech_found or norm_lgn >= 0.5:
            tier = "LOW"
        else:
            tier = "INSUFFICIENT"

        # ── Flags ─────────────────────────────────────────────────────────
        flags = []
        if graph_found and kge_found and norm_lgn >= 0.5:
            flags.append("ALL_LAYERS_AGREE")
        if norm_lgn >= LGN_HIDDEN_TH and not mech_found:
            flags.append("HIDDEN_MECHANISM")
        if mech_found and norm_lgn < LGN_THEORETICAL_UPPER:
            flags.append("THEORETICAL_RISK")
        if norm_lgn >= LGN_EXPERT_TH and mech_found:
            flags.append("EXPERT_REVIEW")

        # Phase 7: LLM evidence flags + confidence cap
        if llm_used:
            flags.append("LLM_SOURCED")
            # Cap tier: LLM-only KGE evidence cannot exceed MEDIUM.
            # Keep direct LGN confidence intact because it is a trained prediction signal.
            if tier == "HIGH" and not graph_found and not kge_found and norm_lgn < LGN_HIGH_CONF_TH:
                tier = "MEDIUM"

        # Phase 9: Layer 0 graduated upgrade
        # Layer 0 severity × LGN signal → clinical correction independent of
        # the 0.80 LGN threshold, because chelation/VKA/tyramine are gut events
        # that the statistical model cannot learn from enzyme-interaction data.
        if phys_warnings:
            max_phys_severity = "HIGH" if any(w["severity"] == "HIGH" for w in phys_warnings) else "MEDIUM"
            if max_phys_severity == "HIGH":
                # HIGH deterministic clinical safety gate risk (e.g. Pizza + Ca²⁺ chelation):
                # upgrade to HIGH if any LGN signal present, MEDIUM otherwise
                flags.append("CLINICAL_RULE_CONFIRMED")
                if norm_lgn > 0.0:
                    tier = "HIGH"
                elif tier not in ("HIGH", "MEDIUM"):
                    tier = "MEDIUM"
            else:
                # MEDIUM deterministic clinical safety gate risk (e.g. Hamburger + Mg competition):
                # upgrade to MEDIUM only if LGN also has a meaningful signal
                if norm_lgn >= 0.40 and tier not in ("HIGH", "MEDIUM"):
                    flags.append("CLINICAL_RULE_CONFIRMED")
                    tier = "MEDIUM"
                elif norm_lgn > 0.0 and tier == "INSUFFICIENT":
                    flags.append("CLINICAL_RULE_CONFIRMED")
                    tier = "LOW"

        # ── Explanation ───────────────────────────────────────────────────
        mechanism_assembly = self._build_mechanism_assembly_shadow(
            drug=drug,
            food=food,
            graph_enzymes=graph_enzymes,
            kge_enzymes=kge_enzymes,
            kge_score_raw=kge_score_raw,
            norm_lgn=norm_lgn,
            phys_warnings=phys_warnings,
        )

        legacy_explanation = self._build_explanation(
            drug, food,
            graph_found, graph_enzymes, graph_score_raw,
            kge_found, kge_enzymes, kge_score_raw,
            norm_lgn, tier, flags,
            phys_warnings=phys_warnings,
        )

        explanation = (
            self._build_explanation_from_assembly(
                drug,
                food,
                mechanism_assembly,
                fusion_score,
                graph_score_raw,
                kge_score_raw,
                norm_lgn,
                norm_graph,
                norm_kge,
                norm_lgn,
                graph_enzymes,
                kge_enzymes,
            )
            if MECHANISM_ASSEMBLY_ENABLED
            else legacy_explanation
        )

        if force_contextual_inference:
            excluded_text = ", ".join(food_context.get("excluded_ingredients") or []) or "none"
            only_text = ", ".join(food_context.get("only_ingredients") or []) or "none"
            explanation += f" Food context applied (excluded: {excluded_text}; only: {only_text})."
            if not phys_warnings:
                explanation += " Layer 0 found no trigger compounds after applying this context."

        result = {
            # Input
            "drug"             : drug,
            "food"             : food,
            # Layer raw outputs
            "graph_score"      : round(graph_score_raw, 4),
            "graph_found"      : graph_found,
            "graph_enzymes"    : [e["enzyme"] for e in graph_enzymes[:3]],
            "graph_path"       : [e["enzyme"] for e in graph_enzymes[:3]],  # Alias for technical view
            "graph_shared_enzymes": graph_enzymes[:5],
            "kge_score"        : round(kge_score_raw, 4),
            "kge_found"        : kge_found,
            "kge_enzymes"      : [e["enzyme"] for e in kge_enzymes[:3]],
            "kge_shared_enzymes": kge_enzymes[:5],
            "lgn_score"        : round(norm_lgn, 4),
            # Fusion
            "norm_graph"       : round(norm_graph, 4),
            "norm_kge"         : round(norm_kge, 4),
            "norm_lgn"         : round(norm_lgn, 4),
            "mechanistic_support": round(mech_support, 4),
            "mechanistic_support_details": mech_details,
            "fusion_score"     : fusion_score,
            "confidence"       : tier,
            "tier"             : tier,  # Alias for UI compatibility
            "score"            : fusion_score,  # Alias for UI compatibility
            "type"             : "DRUG_FOOD",  # For UI result card type
            "flags"            : flags,
            "explanation"      : explanation,
            "legacy_explanation": legacy_explanation,
            # Phase 8 resolution
            "drug_input"       : drug_input,
            "resolution_note"  : (
                f"{drug_input} \u2192 {drug} (Algerian trade name resolved)"
                if resolution["resolved"] and resolution["source"] == "brand"
                else None
            ),
            # Phase 7 LLM bridge
            "food_in_pipeline" : food_in_pipeline,
            "food_context"     : food_context,
            "llm_compounds"    : llm_compounds if llm_used else None,
            "llm_best_compound": llm_kge_best["compound"] if llm_used else None,
            "llm_lgn_compound" : llm_lgn_best["compound"] if llm_lgn_best["compound"] else None,
            # Phase 9 clinical safety gate warnings
            "physicochemical_warnings": phys_warnings,
            # Phase A shadow mode: structured assembly output (not used by UI yet)
            "mechanism_assembly": mechanism_assembly,
            "hormonal_wording_policy": mechanism_assembly.get("hormonal_wording_policy"),
        }
        
        # ── Dual-View Architecture: Add human-friendly explanations ─────────
        try:
            result = create_dual_view(result, language=language)
        except Exception as e:
            with open(ROOT / 'predict_called.log', 'a') as log:
                log.write(f"[ERROR] create_dual_view failed: {type(e).__name__}: {e}\n")
        
        return result

    # ── Batch predict ─────────────────────────────────────────────────────────
    def batch_predict(self, pairs: list[tuple[str, str]]) -> list[dict]:
        return [self.predict(d, f) for d, f in pairs]

    # ── Explanation builder ───────────────────────────────────────────────────
    def _build_explanation(
        self, drug, food,
        graph_found, graph_enzymes, graph_score,
        kge_found, kge_enzymes, kge_score,
        lgn_score, tier, flags,
        phys_warnings: list | None = None,
    ) -> str:
        parts = []

        if graph_found and graph_enzymes:
            enames = ", ".join(e["enzyme"] for e in graph_enzymes[:3])
            parts.append(
                f"Enzyme mechanistic path detected: {food} shares "
                f"{enames} with {drug} (graph score {graph_score:.1f})."
            )
            # User-friendly specific note for common enzymes
            if any(str(e.get("enzyme") or "").upper() == "CYP3A4" for e in graph_enzymes[:3]):
                parts.append("CYP3A4 activity is adjusted.")

        if kge_found and kge_enzymes:
            top = kge_enzymes[0]
            parts.append(
                f"RotatE mechanistic path: {top['compound']} ({food}) "
                f"{top['comp_rel']}s {top['enzyme']} "
                f"[rank={top['comp_rank']}]; "
                f"{drug} {top['drug_rel']}s {top['enzyme']} "
                f"[rank={top['drug_rank']}] (KGE score {kge_score:.1f})."
            )

        if lgn_score >= 0.5:
            parts.append(
                f"LightGCN collaborative signal: score {lgn_score:.3f} "
                f"(similar interaction profiles in training graph)."
            )

        if "HIDDEN_MECHANISM" in flags:
            parts.append(
                f"⚠ HIDDEN MECHANISM: LightGCN indicates similarity "
                f"({lgn_score:.3f}) but no deterministic pathway identified — "
                f"potential unknown interaction."
            )
        if "THEORETICAL_RISK" in flags:
            parts.append(
                f"⚠ THEORETICAL RISK: Mechanistic pathways found but LightGCN "
                f"score low ({lgn_score:.3f}) — limited empirical support."
            )
        if "EXPERT_REVIEW" in flags:
            parts.append(
                "★ EXPERT REVIEW RECOMMENDED: Strong multi-layer evidence."
            )

        # Phase 9: physicochemical warnings appended to explanation
        if phys_warnings:
            for w in phys_warnings:
                parts.append(
                    f"⚠ {w['rule']} [{w['severity']}]: {w['mechanism']} "
                    f"Trigger: {w.get('trigger_compound', 'unknown')} "
                    f"({w.get('trigger_source', 'unknown')}; signal {w.get('food_signal', 'n/a')})."
                )

        if not parts:
            parts.append(
                f"No significant interaction signal detected for {drug} × {food}. "
                f"LGN:{lgn_score:.3f}  Graph:{graph_score:.1f}  KGE:{kge_score:.1f}."
            )

        return " ".join(parts)


# ── Validation runner ─────────────────────────────────────────────────────────
def run_validation(df: DFinder):
    val = pd.read_csv(UNSEEN)
    print(f"\n=== Running fusion on {len(val)} unseen pairs ===")

    results = []
    for i, row in val.iterrows():
        r = df.predict(str(row["drug_name"]), str(row["food_name"]))
        # Attach ground truth if available
        if "verdict" in row:
            r["truth"] = str(row["verdict"])
        results.append(r)
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(val)} done...")

    # ── Summary ───────────────────────────────────────────────────────────────
    total = len(results)
    tiers = pd.Series([r["confidence"] for r in results]).value_counts()
    print("\n--- Confidence tiers ---")
    for t in ["HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]:
        n = tiers.get(t, 0)
        print(f"  {t:15s}: {n:4d} ({100*n/total:.1f}%)")

    flag_counts: dict[str, int] = {}
    for r in results:
        for f in r["flags"]:
            flag_counts[f] = flag_counts.get(f, 0) + 1
    print("\n--- Flags ---")
    for flag, cnt in sorted(flag_counts.items(), key=lambda x: -x[1]):
        print(f"  {flag:25s}: {cnt:4d}")

    # Fusion score distribution
    fscores = np.array([r["fusion_score"] for r in results])
    print("\n--- Fusion score distribution ---")
    for q in [0, 25, 50, 75, 90, 95, 100]:
        print(f"  p{q:3d}: {np.percentile(fscores, q):.4f}")

    # Coverage per layer
    g_cov = sum(1 for r in results if r["graph_found"])
    k_cov = sum(1 for r in results if r["kge_found"])
    all_3 = sum(1 for r in results if r["graph_found"] and r["kge_found"] and r["lgn_score"] >= 0.5)
    print("\n--- Layer coverage ---")
    print(f"  Layer 1 (Graph)   : {g_cov:4d}/{total} ({100*g_cov/total:.1f}%)")
    print(f"  Layer 2 (KGE)     : {k_cov:4d}/{total} ({100*k_cov/total:.1f}%)")
    print(f"  Layer 3 (LGN≥0.5) : {sum(1 for r in results if r['lgn_score']>=0.5):4d}/{total}")
    print(f"  All 3 agree       : {all_3:4d}/{total} ({100*all_3/total:.1f}%)")

    # Sample HIGH confidence pairs
    high = sorted([r for r in results if r["confidence"] == "HIGH"],
                  key=lambda x: -x["fusion_score"])
    print(f"\n--- Top 10 HIGH confidence pairs ---")
    for r in high[:10]:
        flags_str = ",".join(r["flags"]) if r["flags"] else "—"
        print(f"  [{r['fusion_score']:.4f}] "
              f"{r['drug'][:28]:28s} × {r['food'][:18]:18s}  "
              f"flags={flags_str}")

    # Save results
    out_path = VAL_DIR / "phase5_fusion_results.csv"
    rows = []
    for r in results:
        rows.append({
            "drug"          : r["drug"],
            "food"          : r["food"],
            "fusion_score"  : r["fusion_score"],
            "confidence"    : r["confidence"],
            "flags"         : "|".join(r["flags"]),
            "graph_found"   : r["graph_found"],
            "graph_score"   : r["graph_score"],
            "graph_enzymes" : ",".join(r["graph_enzymes"]),
            "kge_found"     : r["kge_found"],
            "kge_score"     : r["kge_score"],
            "kge_enzymes"   : ",".join(r["kge_enzymes"]),
            "lgn_score"     : r["lgn_score"],
            "truth"         : r.get("truth", ""),
            "explanation"   : r["explanation"],
        })
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"\nResults saved → {out_path}")
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    parser = argparse.ArgumentParser(description="DFinder drug-food interaction predictor")
    parser.add_argument("--drug",     type=str, help="Drug name")
    parser.add_argument("--food",     type=str, help="Food name")
    parser.add_argument("--validate", action="store_true",
                        help="Run on all 889 unseen validation pairs")
    parser.add_argument("--json",     action="store_true",
                        help="Output result as JSON (single pair mode)")
    args = parser.parse_args()

    df = DFinder(verbose=True)

    if args.validate:
        run_validation(df)

    elif args.drug and args.food:
        result = df.predict(args.drug, args.food)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"  DRUG : {result['drug']}")
            print(f"  FOOD : {result['food']}")
            print(f"{'='*60}")
            print(f"  Fusion score  : {result['fusion_score']:.4f}")
            print(f"  Confidence    : {result['confidence']}")
            print(f"  Flags         : {', '.join(result['flags']) if result['flags'] else 'none'}")
            print(f"{'─'*60}")
            print(f"  Layer 1 Graph : {result['graph_score']:.2f}  found={result['graph_found']}",
                  f"  enzymes={result['graph_enzymes']}")
            print(f"  Layer 2 KGE   : {result['kge_score']:.2f}  found={result['kge_found']}",
                  f"  enzymes={result['kge_enzymes']}")
            print(f"  Layer 3 LGN   : {result['lgn_score']:.4f}")
            print(f"{'─'*60}")
            print(f"  {result['explanation']}")
            if result.get("physicochemical_warnings"):
                print(f"{'─'*60}")
                print(f"  DETERMINISTIC CLINICAL SAFETY GATE WARNINGS:")
                for w in result["physicochemical_warnings"]:
                    print(f"    [{w['severity']}] {w['rule']}: {w['evidence']}")
            print(f"{'='*60}")

    else:
        # Quick demo
        print("Running demo predictions...")
        df_inst = df
        demo_pairs = [
            ("Warfarin",     "Grapefruit"),
            ("Tacrolimus",   "Grapefruit"),
            ("Metformin",    "Green Tea"),
            ("Atorvastatin", "Grapefruit"),
            ("Midazolam",    "Ginger"),
            ("Cyclosporine", "St. John's Wort"),
        ]
        for drug, food in demo_pairs:
            r = df_inst.predict(drug, food)
            flags_str = f"  [{','.join(r['flags'])}]" if r["flags"] else ""
            print(f"  [{r['confidence']:12s}  {r['fusion_score']:.3f}]  "
                  f"{drug:20s} × {food:20s}{flags_str}")
