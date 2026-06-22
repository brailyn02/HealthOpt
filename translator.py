"""
Dual-View Translator
====================
Converts technical model flags and mechanisms into human-friendly explanations
and actionable advice for non-expert users.

Maps technical terms to:
1. Simple metaphor/analogy
2. Plain-language explanation
3. Actionable advice

Uses Phase 7 LLM (OpenRouter Qwen3-235B) to generate personalized, warm narratives.
Supports multi-language translation of LLM narratives to French and Arabic.
"""

import os
import re
from llm_decompose import llm_friendly_narrative, llm_decompose

# ── Technical Flag → Human Translation Mapping ───────────────────────────────
TECHNICAL_TO_HUMAN = {
    "CHELATION_RISK": {
        "metaphor": "Mineral Magnet",
        "explanation": "The food acts like a magnet, grabbing your medicine and stopping it from working.",
        "advice": "Wait 2–3 hours after taking your medication before eating this food, or take it 2 hours before.",
        "risk_level_high": "This is a strong interaction. Timing is important.",
        "risk_level_medium": "This could reduce how well your medication works. Consider adjusting timing.",
        "risk_level_low": "Minor concern. Spacing meals and medication might help.",
    },
    "CYP3A4_INHIBITION": {
        "metaphor": "Liver Traffic Jam",
        "explanation": "This food slows down your liver's ability to break down your medicine, making it stay in your body too long.",
        "advice": "Avoid eating large amounts of this food while taking this medication. Talk to your doctor about alternatives.",
        "risk_level_high": "Your medicine could build up to unsafe levels. Contact your doctor.",
        "risk_level_medium": "Your medicine might stay in your body longer than expected. Monitor for side effects.",
        "risk_level_low": "Minor effect on how your liver processes this medication.",
    },
    "CYP3A4_INDUCTION": {
        "metaphor": "Liver Speed Boost",
        "explanation": "This food speeds up your liver's ability to break down your medicine, making it less effective faster.",
        "advice": "Your medication may not work as well. Talk to your doctor—you might need a higher dose.",
        "risk_level_high": "Your medicine could stop working. Consult your doctor immediately.",
        "risk_level_medium": "Your medication might be less effective. Contact your doctor.",
        "risk_level_low": "Slight reduction in medication effectiveness.",
    },
    "VITAMIN_K_ANTAGONISM": {
        "metaphor": "Clotting Clash",
        "explanation": "This food contains Vitamin K, which does the exact opposite of your blood-thinning medicine.",
        "advice": "Eat consistent amounts of this food. Don't suddenly eat a lot more or stop eating it.",
        "risk_level_high": "Your blood clotting can become unpredictable. Contact your doctor.",
        "risk_level_medium": "Your blood-thinning medication's effectiveness may change. Keep amounts consistent.",
        "risk_level_low": "Minor effect on your blood-thinning medication.",
    },
    "MAOI_INTERACTION": {
        "metaphor": "Chemical Clash",
        "explanation": "This food can dangerously interact with your depression medication, potentially causing high blood pressure.",
        "advice": "Avoid this food completely while taking this medication.",
        "risk_level_high": "This is a serious, potentially dangerous interaction. Avoid this food.",
        "risk_level_medium": "This interaction could cause side effects. Best to avoid.",
        "risk_level_low": "Unlikely to cause problems, but check with your doctor.",
    },
    "POTASSIUM_SPARING": {
        "metaphor": "Potassium Pile-Up",
        "explanation": "This food is high in potassium. Your medication also keeps potassium in your body, so levels could get dangerously high.",
        "advice": "Limit high-potassium foods (bananas, spinach, nuts). Your doctor may want to check your potassium levels.",
        "risk_level_high": "High potassium levels could harm your heart. Contact your doctor.",
        "risk_level_medium": "Your potassium levels could get too high. Limit this food.",
        "risk_level_low": "Minor concern about potassium buildup.",
    },
    "POTASSIUM_OVERLOAD": {
        "metaphor": "Potassium Pile-Up",
        "explanation": "This food is high in potassium. Your medication also keeps potassium in your body, so levels could get dangerously high.",
        "advice": "Limit high-potassium foods (bananas, spinach, nuts). Your doctor may want to check your potassium levels.",
        "risk_level_high": "High potassium levels could harm your heart. Contact your doctor.",
        "risk_level_medium": "Your potassium levels could get too high. Limit this food.",
        "risk_level_low": "Minor concern about potassium buildup.",
    },
    "IRON_ABSORPTION": {
        "metaphor": "Iron Lock",
        "explanation": "This food contains compounds that block your body from absorbing iron, making your iron supplement or medication less effective.",
        "advice": "Wait 1–2 hours after taking iron before eating this food, or vice versa.",
        "risk_level_high": "Iron absorption could be severely reduced. Timing is critical.",
        "risk_level_medium": "Iron absorption may be reduced. Separate meals and medication by 1–2 hours.",
        "risk_level_low": "Minor reduction in iron absorption.",
    },
    "CALCIUM_BINDING": {
        "metaphor": "Calcium Lockup",
        "explanation": "This food is high in calcium, which can trap your medication before your body absorbs it.",
        "advice": "Take this medication at least 2 hours away from high-calcium foods or supplements.",
        "risk_level_high": "Medication absorption could be very low. Strict timing needed.",
        "risk_level_medium": "Medication absorption may be reduced. Space out meals and medication.",
        "risk_level_low": "Minor effect on medication absorption.",
    },
    "QT_PROLONGATION": {
        "metaphor": "Heart Rhythm Risk",
        "explanation": "This food-drug combination could affect your heart's electrical rhythm.",
        "advice": "Talk to your doctor or pharmacist before combining these.",
        "risk_level_high": "This could be dangerous for your heart. Contact your doctor immediately.",
        "risk_level_medium": "Potential heart rhythm effects. Consult your doctor.",
        "risk_level_low": "Small risk to heart rhythm.",
    },
    "HYPERTENSION_RISK": {
        "metaphor": "Blood Pressure Spike",
        "explanation": "This combination could raise your blood pressure.",
        "advice": "Monitor your blood pressure. Talk to your doctor if it rises.",
        "risk_level_high": "Significant blood pressure increase possible. Contact your doctor.",
        "risk_level_medium": "Blood pressure could increase. Monitor it closely.",
        "risk_level_low": "Mild blood pressure effect.",
    },
    "HYPOGLYCEMIA_RISK": {
        "metaphor": "Blood Sugar Dip",
        "explanation": "This food-drug combination could cause your blood sugar to drop too low.",
        "advice": "Eat regular meals. Carry a fast-acting carb (juice, candy) just in case.",
        "risk_level_high": "Risk of dangerously low blood sugar. Contact your doctor.",
        "risk_level_medium": "Blood sugar could drop too low. Watch for dizziness or shakiness.",
        "risk_level_low": "Minor blood sugar effect.",
    },
    "ACID_ABSORPTION_RISK": {
        "metaphor": "Stomach Stress",
        "explanation": "This food-drug pair can irritate your stomach or change how the medicine dissolves.",
        "advice": "Take the medication with water and avoid acidic foods close to dosing when possible.",
        "risk_level_high": "High chance of stomach irritation or poor absorption. Contact your doctor.",
        "risk_level_medium": "Possible stomach irritation. Use food and timing carefully.",
        "risk_level_low": "Minor stomach/absorption effect.",
    },
}

# ── Nutrient-Specific Interactions ──────────────────────────────────────────
NUTRIENT_INTERACTIONS = {
    "Iron Deficiency + Tannins": {
        "metaphor": "Iron Trap",
        "explanation": "Tannins in tea or coffee bind to iron, preventing your body from absorbing it. This is especially important if you have low iron.",
        "advice": "Take iron supplements 1–2 hours before or after drinking tea/coffee.",
    },
    "Low Vitamin D + Low-Fat Meal": {
        "metaphor": "Fat-Free Fail",
        "explanation": "Vitamin D is fat-soluble, meaning it needs fat to be absorbed. Eating it with a fat-free meal reduces absorption.",
        "advice": "Take Vitamin D with a meal containing healthy fat (olive oil, nuts, avocado).",
    },
}

# ── Confidence Tier Descriptions ────────────────────────────────────────────
CONFIDENCE_DESCRIPTIONS = {
    "HIGH": {
        "color": "red",
        "emoji": "🔴",
        "title": "High Risk",
        "description": "Strong evidence from multiple layers. This interaction is well-documented.",
    },
    "MEDIUM": {
        "color": "orange",
        "emoji": "🟠",
        "title": "Medium Risk",
        "description": "Moderate evidence. The interaction exists but may depend on amounts and timing.",
    },
    "LOW": {
        "color": "yellow",
        "emoji": "🟡",
        "title": "Low Risk",
        "description": "Minor interaction. Usually not a concern with normal consumption.",
    },
    "INFO": {
        "color": "blue",
        "emoji": "🔵",
        "title": "Good to Know",
        "description": "Interesting nutrition insight relevant to your health.",
    },
    "INSUFFICIENT": {
        "color": "gray",
        "emoji": "⚪",
        "title": "No Data",
        "description": "We don't have enough information about this combination.",
    },
}


def get_simple_explanation(mechanism: str, tier: str) -> dict:
    """
    Convert technical mechanism and confidence tier into human-friendly explanation.
    
    Args:
        mechanism: Technical explanation from model (e.g., "CHELATION_RISK [HIGH]")
        tier: Confidence tier (HIGH, MEDIUM, LOW, INFO, INSUFFICIENT)
    
    Returns:
        dict with keys: metaphor, explanation, advice, risk_level_description
    """
    # Extract flag name from mechanism
    flag_key = None
    for key in TECHNICAL_TO_HUMAN.keys():
        if key in mechanism.upper():
            flag_key = key
            break
    
    if not flag_key:
        # Heuristic inference for mechanisms that do not include canonical flag labels.
        mech = (mechanism or "").upper()
        if "CHELATION" in mech or "CATION-SENSITIVE" in mech or "CATION" in mech:
            flag_key = "CHELATION_RISK"
        elif "CYP3A4" in mech or "CYP450" in mech or "CYP" in mech:
            if "INDUCE" in mech:
                flag_key = "CYP3A4_INDUCTION"
            else:
                flag_key = "CYP3A4_INHIBITION"
        elif "VITAMIN K" in mech or "WARFARIN" in mech:
            flag_key = "VITAMIN_K_ANTAGONISM"
        elif "TYRAMINE" in mech or "MAOI" in mech:
            flag_key = "MAOI_INTERACTION"
        elif "POTASSIUM" in mech:
            flag_key = "POTASSIUM_SPARING"

    if not flag_key:
        # Fallback for truly unmapped mechanisms
        return {
            "metaphor": "Interaction Detected",
            "explanation": mechanism[:100],  # First 100 chars of technical explanation
            "advice": "Consult your pharmacist or doctor.",
            "risk_level_description": f"{tier.lower().capitalize()} interaction.",
            "technical_flag": "UNKNOWN",
        }
    
    translation = TECHNICAL_TO_HUMAN[flag_key]
    risk_key = f"risk_level_{tier.lower()}"
    
    return {
        "metaphor": translation["metaphor"],
        "explanation": translation["explanation"],
        "advice": translation.get(risk_key, translation["advice"]),
        "risk_level_description": translation["advice"],
        "technical_flag": flag_key,
    }


def get_confidence_badge(tier: str) -> dict:
    """Get visual and text representation for confidence tier."""
    return CONFIDENCE_DESCRIPTIONS.get(
        tier.upper(),
        CONFIDENCE_DESCRIPTIONS["INSUFFICIENT"]
    )


def _severity_rank(sev: str) -> int:
    order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
    return order.get(str(sev or "").upper(), 0)


def _select_dominant_flag(result: dict, default_flag: str) -> tuple[str, list[str]]:
    """
    Choose primary mechanism for friendly narration using all pipeline signals.
    Returns (primary_flag, secondary_flags).
    """
    mechanism = str(result.get("explanation", "") or "")
    mechanism_upper = mechanism.upper()
    flags = [str(f).upper() for f in (result.get("flags", []) or [])]
    kge_enzymes = [str(e).upper() for e in (result.get("kge_enzymes", []) or [])]
    phys_warnings = result.get("physicochemical_warnings", []) or []

    candidates: list[str] = []

    # Candidate 1: direct parse from mechanism text.
    if "CHELATION_RISK" in mechanism_upper:
        candidates.append("CHELATION_RISK")
    if "VITAMIN_K" in mechanism_upper or "WARFARIN" in mechanism_upper:
        candidates.append("VITAMIN_K_ANTAGONISM")
    if "MAOI" in mechanism_upper or "TYRAMINE" in mechanism_upper:
        candidates.append("MAOI_INTERACTION")
    if "POTASSIUM" in mechanism_upper:
        candidates.append("POTASSIUM_OVERLOAD")
    if "ACID_ABSORPTION_RISK" in mechanism_upper or "GASTRIC" in mechanism_upper:
        candidates.append("ACID_ABSORPTION_RISK")

    has_cyp = any(e.startswith("CYP") for e in kge_enzymes) or "CYP" in mechanism_upper
    if has_cyp:
        if "INDUCE" in mechanism_upper:
            candidates.append("CYP3A4_INDUCTION")
        else:
            candidates.append("CYP3A4_INHIBITION")

    # Candidate 2: rule-derived from physicochemical warnings.
    max_phys_sev = 0
    for w in phys_warnings:
        if not isinstance(w, dict):
            continue
        rule = str(w.get("rule", "")).upper()
        if rule:
            # Normalize rule aliases to one user-facing mechanism namespace.
            if rule == "POTASSIUM_SPARING":
                rule = "POTASSIUM_OVERLOAD"
            elif rule == "TYRAMINE_CRISIS":
                rule = "MAOI_INTERACTION"
            candidates.append(rule)
        max_phys_sev = max(max_phys_sev, _severity_rank(str(w.get("severity", ""))))

    # Candidate 3: ensure default stays as fallback.
    if default_flag:
        candidates.append(default_flag)

    # De-duplicate preserve order
    seen = set()
    ordered = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            ordered.append(c)

    if not ordered:
        return default_flag or "UNKNOWN", []

    # Requested clinical hierarchy for user-facing explanation:
    # 1) Antagonism (Tug-of-War)  2) Chelation (Mineral Magnet)  3) Enzyme/Path (Traffic Jam/Speed Boost)
    hierarchy = {
        "VITAMIN_K_ANTAGONISM": 1,
        "MAOI_INTERACTION": 1,
        "POTASSIUM_OVERLOAD": 1,
        "POTASSIUM_SPARING": 1,
        "ACID_ABSORPTION_RISK": 1,
        "CHELATION_RISK": 2,
        "CYP3A4_INHIBITION": 3,
        "CYP3A4_INDUCTION": 3,
    }

    def _rank(flag: str) -> tuple[int, int]:
        # primary sort: hierarchy rank (lower is higher priority),
        # secondary sort: keep original appearance order for deterministic behavior.
        return (hierarchy.get(flag, 99), ordered.index(flag) if flag in ordered else 999)

    ranked = sorted(ordered, key=_rank)
    primary = ranked[0]
    secondary = [f for f in ranked[1:] if f != primary]
    return primary, secondary


def _sanitize_for_friendly_text(text: str) -> str:
    """Remove model-score jargon from user-facing mechanism text."""
    cleaned = str(text or "")
    # Drop trailing layer score dump if present.
    cleaned = re.sub(r"\s*Layer evidence:.*$", "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()
    # Keep numbers that belong to medical values but remove explicit score phrases.
    cleaned = re.sub(r"\b(Graph|KGE|LightGCN|Fusion)\s+\d+(\.\d+)?\b", "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def _build_user_mechanism_summary(result: dict, mechanism_assembly: dict, phys_warnings: list) -> str:
    """Build plain-language cause/effect summary for friendly explanation input."""
    ranked = [m for m in (mechanism_assembly.get("ranked_mechanisms") or []) if isinstance(m, dict)]
    parts: list[str] = []

    if ranked:
        lead = ranked[0]
        lead_class = str(lead.get("class") or "interaction").replace("_", " ").lower()
        parts.append(f"Primary interaction driver: {lead_class}.")
        secondary = [str(m.get("class") or "").replace("_", " ").lower() for m in ranked[1:3] if m.get("class")]
        if secondary:
            parts.append(f"Secondary contributors: {', '.join(secondary)}.")

    if phys_warnings:
        top = []
        for w in phys_warnings[:3]:
            if not isinstance(w, dict):
                continue
            rule = str(w.get("rule") or "").replace("_", " ").lower()
            mech = str(w.get("mechanism") or "").strip()
            if rule:
                top.append(f"{rule}: {mech}" if mech else rule)
        if top:
            parts.append("Clinically relevant food-side factors: " + "; ".join(top) + ".")

    graph_enz = [str(e) for e in (result.get("graph_path", []) or []) if str(e).strip()]
    kge_enz = [str(e) for e in (result.get("kge_enzymes", []) or []) if str(e).strip()]
    enzyme_evidence = list(dict.fromkeys(graph_enz + kge_enz))[:4]
    if enzyme_evidence:
        parts.append("Shared biological pathways: " + ", ".join(enzyme_evidence) + ".")

    base = _sanitize_for_friendly_text(str(result.get("explanation", "") or ""))
    if base:
        parts.insert(0, base)

    if not parts:
        return "Interaction evidence is present from multiple pipeline checks."
    return " ".join(parts)


def _build_technical_layer_steps(result: dict, mechanism_assembly: dict, phys_warnings: list) -> list[dict]:
    """Create a strict layer-by-layer technical explanation payload."""
    steps: list[dict] = []

    # Layer 0: physicochemical
    layer0_found = len(phys_warnings or []) > 0
    steps.append({
        "layer": "layer0",
        "title": "Physicochemical Rules",
        "found": layer0_found,
        "details": phys_warnings if layer0_found else ["No rule-triggered physicochemical warning."],
    })

    # Layer 1: graph
    graph_shared = result.get("graph_shared_enzymes", []) or []
    steps.append({
        "layer": "layer1_graph",
        "title": "Graph Evidence (Documented Biology)",
        "found": bool(result.get("graph_found", False)),
        "score": float(result.get("graph_score", 0) or 0),
        "details": graph_shared if graph_shared else [{"note": "No direct documented overlap found."}],
    })

    # Layer 2: KGE
    kge_shared = result.get("kge_shared_enzymes", []) or []
    steps.append({
        "layer": "layer2_kge",
        "title": "Mechanistic Pathway Evidence",
        "found": bool(result.get("kge_found", False)),
        "score": float(result.get("kge_score", 0) or 0),
        "details": kge_shared if kge_shared else [{"note": "No inferred mechanistic bridge found."}],
    })

    # Layer 3: collaborative
    norm_lgn = float(result.get("norm_lgn", result.get("lgn_score", 0)) or 0)
    lgn_strength = "high" if norm_lgn >= 0.90 else ("medium" if norm_lgn >= 0.65 else ("low" if norm_lgn >= 0.50 else "weak"))
    steps.append({
        "layer": "layer3_collaborative",
        "title": "Pattern-Based Signal",
        "score": float(result.get("lgn_score", 0) or 0),
        "norm_score": norm_lgn,
        "signal_strength": lgn_strength,
        "details": [f"Collaborative pattern signal is {lgn_strength}."]
    })

    # Layer 4: fusion/tier logic
    steps.append({
        "layer": "layer4_fusion",
        "title": "Fusion Decision",
        "score": float(result.get("fusion_score", result.get("score", 0)) or 0),
        "confidence": result.get("confidence", result.get("tier", "INSUFFICIENT")),
        "logic_applied": {
            "high_if": [
                "graph_and_kge_both_found",
                "norm_lgn >= 0.90"
            ],
            "medium_if": [
                "fusion_score >= 0.45",
                "mechanistic_found_and_norm_lgn >= 0.5",
                "norm_lgn >= 0.65"
            ]
        },
    })

    return steps


def _format_hkg_full_paths(result: dict) -> list[dict]:
    """Format full HKG paths as compound -> enzyme evidence for technical output."""
    paths: list[dict] = []
    for edge in (result.get("graph_shared_enzymes", []) or []):
        if not isinstance(edge, dict):
            continue
        enzyme = str(edge.get("enzyme") or "").strip()
        if not enzyme:
            continue
        compounds = [str(c).strip() for c in (edge.get("compounds") or []) if str(c).strip()]
        food_rels = [str(r).strip() for r in (edge.get("food_rels") or []) if str(r).strip()]
        drug_rels = [str(r).strip() for r in (edge.get("drug_rels") or []) if str(r).strip()]
        paths.append({
            "enzyme": enzyme,
            "compounds": compounds,
            "food_relations": food_rels,
            "drug_relations": drug_rels,
            "weight": edge.get("weight"),
        })
    return paths


def _format_kge_full_paths(result: dict) -> list[dict]:
    """Format full KGE paths as compound -> enzyme -> drug evidence for technical output."""
    paths: list[dict] = []
    for edge in (result.get("kge_shared_enzymes", []) or []):
        if not isinstance(edge, dict):
            continue
        enzyme = str(edge.get("enzyme") or "").strip()
        compound = str(edge.get("compound") or "").strip()
        if not enzyme and not compound:
            continue
        paths.append({
            "enzyme": enzyme,
            "compound": compound,
            "compound_relation": str(edge.get("comp_rel") or "").strip(),
            "compound_rank": edge.get("comp_rank"),
            "drug_relation": str(edge.get("drug_rel") or "").strip(),
            "drug_rank": edge.get("drug_rank"),
            "path_score": edge.get("path_score"),
            "weighted": edge.get("weighted"),
            "enz_weight": edge.get("enz_weight"),
            "risk_mult": edge.get("risk_mult"),
        })
    return paths


def _format_exact_pathway_relations(result: dict) -> dict:
    """Build explicit HKG/KGE relation traces for technical diagnostics."""
    hkg_paths = _format_hkg_full_paths(result)
    kge_paths = _format_kge_full_paths(result)

    summary_parts = []
    if hkg_paths:
        hkg_summary = []
        for p in hkg_paths[:3]:
            compounds = ", ".join(p.get("compounds", [])[:3]) or "unknown compound"
            food_rels = ", ".join(p.get("food_relations", [])[:2]) or "affects"
            drug_rels = ", ".join(p.get("drug_relations", [])[:2]) or "affects"
            hkg_summary.append(f"{compounds} {food_rels} {p.get('enzyme')} ; drug {drug_rels} {p.get('enzyme')}")
        summary_parts.append("HKG: " + " | ".join(hkg_summary))
    if kge_paths:
        kge_summary = []
        for p in kge_paths[:3]:
            compound = p.get("compound") or "unknown compound"
            comp_rel = p.get("compound_relation") or "affects"
            drug_rel = p.get("drug_relation") or "affects"
            kge_summary.append(
                f"{compound} {comp_rel} {p.get('enzyme')} [rank {p.get('compound_rank')}]; "
                f"drug {drug_rel} {p.get('enzyme')} [rank {p.get('drug_rank')}]"
            )
        summary_parts.append("KGE: " + " | ".join(kge_summary))

    return {
        "hkg": hkg_paths,
        "kge": kge_paths,
        "summary": " || ".join(summary_parts),
    }


def format_compounds(llm_compounds: list) -> dict:
    """
    Format identified compounds for user display.
    
    Args:
        llm_compounds: List of dicts with 'name', 'branch', 'source' keys
    
    Returns:
        dict with 'bioactive' and 'nutritional' compound lists
    """
    bioactive = []
    nutritional = []
    
    for comp in llm_compounds:
        if comp.get("branch") == "kge":
            bioactive.append({
                "name": comp["name"],
                "source": comp.get("source", "LLM_SOURCED"),
                "type": "Bioactive Compound",
            })
        elif comp.get("branch") == "nutrient":
            nutritional.append({
                "name": comp["name"],
                "source": comp.get("source", "LLM_SOURCED"),
                "tier": comp.get("tier", "general"),
                "type": "Nutrient",
            })
    
    return {
        "bioactive": bioactive,
        "nutritional": nutritional,
        "summary": f"Found {len(bioactive)} bioactive compound(s) and {len(nutritional)} nutrient(s).",
    }


def _translate_narrative_to_language(narrative: dict, language: str) -> dict:
    """
    Translate LLM-generated narrative to target language using Gemini API.
    
    Args:
        narrative: Dict with 'what_is_happening', 'why_it_matters', 'how_to_fix_it', 'when_to_act'
        language: Target language code ('en', 'fr', 'ar')
    
    Returns:
        Dict with translated narrative (or original if language is 'en' or translation fails)
    """
    if language == "en" or not narrative:
        return narrative
    
    try:
        import google.generativeai as genai
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print(f"[WARN] GEMINI_API_KEY not set, skipping narrative translation to {language}")
            return narrative
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Map language codes to language names
        lang_names = {"fr": "French", "ar": "Arabic"}
        target_lang = lang_names.get(language, "English")
        
        # Build translation prompt
        translation_prompt = f"""Translate the following drug-food interaction explanation to {target_lang}.
Keep the tone warm, actionable, and easy to understand. Preserve any lists and formatting.

Original text:
- What is happening: {narrative.get('what_is_happening', '')}
- Why it matters: {narrative.get('why_it_matters', '')}
- How to fix it: {narrative.get('how_to_fix_it', [])}
- When to act: {narrative.get('when_to_act', '')}

Respond with valid JSON in this format:
{{
  "what_is_happening": "translated text",
  "why_it_matters": "translated text",
  "how_to_fix_it": ["item1", "item2"],
  "when_to_act": "translated text"
}}"""
        
        response = model.generate_content(translation_prompt)
        response_text = response.text
        
        # Extract JSON from response
        import json
        # Find JSON in response (it might be wrapped in markdown code blocks)
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            translated = json.loads(json_str)
            return {
                "what_is_happening": translated.get("what_is_happening", narrative.get("what_is_happening", "")),
                "why_it_matters": translated.get("why_it_matters", narrative.get("why_it_matters", "")),
                "how_to_fix_it": translated.get("how_to_fix_it", narrative.get("how_to_fix_it", [])),
                "when_to_act": translated.get("when_to_act", narrative.get("when_to_act", "")),
            }
    except Exception as e:
        print(f"[WARN] Translation to {language} failed: {type(e).__name__}: {e}")
        return narrative
    
    return narrative


def create_dual_view(result: dict, language: str = "en") -> dict:
    """
    Wrap a prediction result with both simple and technical views.
    
    Uses Phase 7 LLM (Qwen3-235B via OpenRouter) to generate warm, friendly 
    explanations of the drug-food interaction for the "simple_view".
    
    Args:
        result: Output from DFinder.predict()
        language: Target language for response ('en', 'fr', 'ar'). Defaults to 'en'.
    
    Returns:
        Enhanced result dict with 'simple_view' and 'technical_view' keys
    """
    tier = result.get("confidence", "INSUFFICIENT")
    mechanism = result.get("explanation", "")
    # Resolve names from all known backend fields before falling back.
    drug_name = (
        result.get("drug_name")
        or result.get("drug_input")
        or result.get("drug")
        or "Unknown Drug"
    )
    food_name = (
        result.get("food_name")
        or result.get("food")
        or "Unknown Food"
    )
    
    simple = get_simple_explanation(mechanism, tier)

    mechanism_assembly = result.get("mechanism_assembly") or {}
    suppressed_rules = {
        str(item.get("class") or "").upper()
        for item in (mechanism_assembly.get("suppressed_mechanisms") or [])
        if isinstance(item, dict)
    }

    # Filter suppressed rule warnings from user-facing narrative inputs.
    phys_warnings = [
        w for w in (result.get("physicochemical_warnings", []) or [])
        if str((w or {}).get("rule", "")).upper() not in suppressed_rules
    ]
    result["physicochemical_warnings"] = phys_warnings

    ranked = mechanism_assembly.get("ranked_mechanisms") or []
    user_ranked = [m for m in ranked if isinstance(m, dict) and bool(m.get("user_visible", True))]

    if user_ranked:
        lead_class = str((mechanism_assembly.get("lead_mechanism") or user_ranked[0]).get("class") or "UNKNOWN").upper()
        secondary_flags = [str(m.get("class") or "").upper() for m in user_ranked[1:3]]
        dominant_flag = lead_class if lead_class in TECHNICAL_TO_HUMAN else simple.get("technical_flag", "UNKNOWN")
    else:
        dominant_flag, secondary_flags = _select_dominant_flag(result, simple.get("technical_flag", "UNKNOWN"))

    if dominant_flag in TECHNICAL_TO_HUMAN:
        base = TECHNICAL_TO_HUMAN[dominant_flag]
        risk_key = f"risk_level_{str(tier).lower()}"
        simple = {
            **simple,
            "technical_flag": dominant_flag,
            "metaphor": base["metaphor"],
            "explanation": base["explanation"],
            "advice": base.get(risk_key, base["advice"]),
        }
    confidence_info = get_confidence_badge(tier)
    
    # Extract compounds from llm_compounds if available
    llm_compounds = result.get("llm_compounds", [])
    compounds_summary = format_compounds(llm_compounds) if llm_compounds else None
    
    # ── NEW: Generate LLM-based friendly narrative ──────────────────────────
    # Use already extracted Step-1 compounds when available; otherwise backfill via decomposer.
    food_bioactives = llm_compounds if llm_compounds else (llm_decompose(food_name, verbose=False) if food_name else [])
    
    user_mechanism = _build_user_mechanism_summary(result, mechanism_assembly, phys_warnings)

    # Call LLM to generate warm, actionable explanation
    # Enhance pipeline evidence with mechanistic confidence and pathway details
    norm_lgn = float(result.get("norm_lgn", result.get("lgn_score", 0)) or 0)
    kge_found = bool(result.get("kge_found", False))
    graph_found = bool(result.get("graph_found", False))
    
    friendly_narrative = llm_friendly_narrative(
        drug_name=drug_name,
        food_name=food_name,
        mechanism=user_mechanism,
        risk_level=tier,
        metaphor=simple["metaphor"],
        technical_flag=simple.get("technical_flag", "UNKNOWN"),
        bioactives=food_bioactives,
        pipeline_evidence={
            "confidence": tier,
            "flags": result.get("flags", []),
            "primary_flag": dominant_flag,
            "secondary_flags": secondary_flags,
            "physicochemical_warnings": phys_warnings,
            "graph_path": result.get("graph_path", []),
            "graph_shared_enzymes": result.get("graph_shared_enzymes", []),
            "graph_found": graph_found,
            "graph_score": float(result.get("graph_score", 0) or 0),
            "kge_enzymes": [] if str((mechanism_assembly.get("dominant_mechanism_class") or "")).upper() == "PHARMACODYNAMIC" else result.get("kge_enzymes", []),
            "kge_shared_enzymes": [] if str((mechanism_assembly.get("dominant_mechanism_class") or "")).upper() == "PHARMACODYNAMIC" else result.get("kge_shared_enzymes", []),
            "kge_found": kge_found,
            "kge_score": float(result.get("kge_score", 0) or 0),
            "mechanistic_confidence": "high" if kge_found and norm_lgn >= 0.70 else ("medium" if kge_found else "low"),
            "norm_lgn": norm_lgn,
            "resolution_note": result.get("resolution_note", ""),
            "llm_compounds": llm_compounds,
            "technical_mechanism": user_mechanism,
            "mechanism_assembly": mechanism_assembly,
        },
        verbose=False
    )
    
    # ── Translate friendly narrative if language != 'en' ──────────────────
    friendly_narrative_dict = {
        "what_is_happening": friendly_narrative.get("what_is_happening", ""),
        "why_it_matters": friendly_narrative.get("why_it_matters", ""),
        "how_to_fix_it": friendly_narrative.get("how_to_fix_it", []),
        "when_to_act": friendly_narrative.get("when_to_act", ""),
    }

    # Ensure high mechanistic confidence is reflected in friendly copy without model jargon.
    hkg_paths = _format_hkg_full_paths(result)
    if hkg_paths:
        lead_hkg = hkg_paths[0]
        compounds = lead_hkg.get("compounds", [])
        compound_text = ", ".join(compounds[:3]) if compounds else food_name
        hkg_line = f" HKG path: {compound_text} -> {lead_hkg.get('enzyme')} -> {drug_name}."
        current = str(friendly_narrative_dict.get("what_is_happening", "") or "")
        if "hkg path:" not in current.lower():
            friendly_narrative_dict["what_is_happening"] = (current + hkg_line).strip()

    if kge_found and norm_lgn >= 0.70:
        kge_edges = result.get("kge_shared_enzymes", []) or []
        enzymes = []
        for e in kge_edges[:2]:
            if isinstance(e, dict):
                enz = str(e.get("enzyme") or e.get("name") or "").strip()
                if enz:
                    enzymes.append(enz)
        if enzymes:
            add_line = f" We also found strong pathway evidence involving {', '.join(enzymes)}."
            current = str(friendly_narrative_dict.get("what_is_happening", "") or "")
            if "strong pathway evidence" not in current.lower():
                friendly_narrative_dict["what_is_happening"] = (current + add_line).strip()

    evidence_summary = (
        f"Graph score {float(result.get('graph_score', 0) or 0):.3f}; "
        f"KGE score {float(result.get('kge_score', 0) or 0):.3f}; "
        f"LightGCN score {float(result.get('lgn_score', 0) or 0):.3f}; "
        f"Fusion score {float(result.get('fusion_score', result.get('score', 0)) or 0):.3f}."
    )

    if language != "en":
        friendly_narrative_dict = _translate_narrative_to_language(friendly_narrative_dict, language)
    
    result["simple_view"] = {
        "metaphor": simple["metaphor"],
        "user_explanation": simple["explanation"],
        "what_to_do": simple["advice"],
        "explanation_notice": "Detailed layer-by-layer evidence is available in Technical Details.",
        "confidence_badge": confidence_info,
        "compounds_identified": compounds_summary,
        # NEW: LLM-generated friendly sections (translated if needed)
        "friendly_narrative": friendly_narrative_dict
    }

    technical_steps = _build_technical_layer_steps(result, mechanism_assembly, phys_warnings)
    exact_pathways = _format_exact_pathway_relations(result)
    raw_mechanism = mechanism
    if exact_pathways.get("summary"):
        raw_mechanism = (raw_mechanism + " Exact pathway trace: " + exact_pathways["summary"]).strip()
    
    result["technical_view"] = {
        "technical_flag": simple.get("technical_flag", "UNKNOWN"),
        "raw_mechanism": raw_mechanism,
        "fusion_score": result.get("score", 0),
        "evidence_summary": evidence_summary,
        "confidence": result.get("confidence", result.get("tier", "INSUFFICIENT")),
        "normalization": {
            "norm_graph": result.get("norm_graph", 0),
            "norm_kge": result.get("norm_kge", 0),
            "norm_lgn": result.get("norm_lgn", 0),
        },
        "scoring_policy": {
            "mechanistic_support": "HKG_PRIORITY_WEIGHTED",
            "hkg_weight": 0.65,
            "kge_weight": 0.35,
            "physicochemical_in_mechanistic_support": False,
        },
        "layers": {
            "layer0": {
                "found": len(result.get("physicochemical_warnings", []) or []) > 0,
                "score": max([
                    _severity_rank(str((w or {}).get("severity", "")))
                    for w in (result.get("physicochemical_warnings", []) or [])
                    if isinstance(w, dict)
                ] + [0]),
                "warnings": result.get("physicochemical_warnings", []),
            },
            "graph": {
                "found": result.get("graph_found", False),
                "score": result.get("graph_score", 0),
                "enzymes": result.get("graph_path", []),
                "shared_enzymes": result.get("graph_shared_enzymes", []),
            },
            "kge": {
                "found": result.get("kge_found", False),
                "score": result.get("kge_score", 0),
                "enzymes": result.get("kge_enzymes", []),
                "shared_enzymes": result.get("kge_shared_enzymes", []),
            },
            "lgn": {
                "score": result.get("lgn_score", 0),
            },
            "fusion": {
                "score": result.get("fusion_score", result.get("score", 0)),
                "confidence": result.get("confidence", result.get("tier", "INSUFFICIENT")),
            },
        },
        "detailed_mechanism": {
            "ordered_steps": technical_steps,
            "exact_pathways": exact_pathways,
            "hkg_full_paths": hkg_paths,
            "kge_full_paths": _format_kge_full_paths(result),
        },
        "flags": result.get("flags", []),
        "physicochemical_warnings": result.get("physicochemical_warnings", []),
    }
    
    return result


if __name__ == "__main__":
    # Test translations
    print("=" * 70)
    print("DUAL-VIEW TRANSLATOR TEST")
    print("=" * 70)
    
    test_cases = [
        ("CHELATION_RISK [HIGH] – Multivalent cations bind drug.", "HIGH"),
        ("CYP3A4_INHIBITION – Food slows liver metabolism.", "MEDIUM"),
        ("VITAMIN_K_ANTAGONISM – Vitamin K opposes anticoagulant.", "HIGH"),
    ]
    
    for mechanism, tier in test_cases:
        print(f"\n📋 Mechanism: {mechanism}")
        print(f"   Tier: {tier}")
        simple = get_simple_explanation(mechanism, tier)
        print(f"   🎭 Metaphor: {simple['metaphor']}")
        print(f"   💡 Explanation: {simple['explanation']}")
        print(f"   ✅ Advice: {simple['advice']}")
        
        badge = get_confidence_badge(tier)
        print(f"   {badge['emoji']} {badge['title']}: {badge['description']}")
