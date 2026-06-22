"""
Phase 7 - LLM Food Decomposer

Uses OpenRouter (Qwen3-235B) to decompose any food name into its pharmacologically
active bioactive compounds. Results are cached to disk so each food is only queried once.

Covers all 6 drug-food interaction mechanism classes:
  1. CYP enzyme inhibition/induction  (CYP3A4, CYP2D6, CYP2C9, CYP1A2, …)
  2. P-glycoprotein / OATP transport  (ABCB1/MDR1, OATP1B1, OATP2B1)
  3. Divalent cation chelation        (Ca²⁺, Mg²⁺, Zn²⁺, Fe²⁺ binding)
  4. Gastric pH alteration            (drug dissolution/absorption at GI level)
  5. Plasma protein binding           (albumin displacement)
  6. Pharmacodynamic synergy/antag.   (Vitamin K vs anticoagulants, serotonin, etc.)

Primary provider : OpenRouter / Qwen3-235B-A22B (free tier, no quota issues)
Fallback provider: Google Gemini 2.0 Flash (if OpenRouter unavailable)

Usage:
    from llm_decompose import llm_decompose

    llm_decompose("Harissa")
    # -> ["Capsaicin", "Allicin", "Cuminaldehyde"]

    llm_decompose("Grapefruit")
    # -> ["Naringenin", "Bergamottin", "6,7-Dihydroxybergamottin"]

    llm_decompose("Spinach")
    # -> ["Vitamin K1", "Calcium", "Magnesium"]

    llm_decompose("Plain White Rice")
    # -> []
"""

import json
import os
import re
import urllib.request
from pathlib import Path

import pandas as pd

try:
    import redis
except Exception:
    redis = None

# ── Config ────────────────────────────────────────────────────────────────────
# Primary: OpenRouter (Qwen3-235B, free tier, 262K context)
OPENROUTER_API_KEY = "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"
OPENROUTER_MODEL   = "qwen/qwen3-235b-a22b"
OPENROUTER_URL     = "https://openrouter.ai/api/v1/chat/completions"

# Fallback: Google Gemini 2.0 Flash
GEMINI_API_KEY = "AIzaSyCS5yuUUF7Ha5pv7zdmhEXW3Qtg_9rjw8c"
GEMINI_MODEL   = "gemini-2.0-flash"

ROOT       = Path(__file__).resolve().parent
CACHE_FILE = ROOT / "data" / "llm_food_cache.json"
REDIS_URL = os.getenv("LLM_CACHE_REDIS_URL", "")
REDIS_TTL_SECONDS = int(os.getenv("LLM_CACHE_TTL_SECONDS", "604800"))

# ── NA dish compounds lookup (bypasses LLM for known Algerian dishes) ─────────
_NA_DISH_FILE = ROOT / "data" / "na_dish_compounds.json"
_FOODB_COMPOUND_FILE = ROOT / "Compound.csv"
_HKG_FOOD_COMPOUND_FILE = ROOT / "data" / "processed_hkg" / "hkg_food_compound_edges.csv"

def _load_na_dish_compounds() -> dict:
    if _NA_DISH_FILE.exists():
        import json as _json
        with open(_NA_DISH_FILE, encoding="utf-8") as _f:
            return _json.load(_f)
    return {}

NA_DISH_COMPOUNDS: dict = _load_na_dish_compounds()


def _norm_compound_name(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"\([^)]*\)", "", s)
    s = s.replace("/", " ")
    s = s.replace("+", " ")
    s = s.replace("_", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _safe_split_compound(raw: str) -> list[str]:
    """Split coarse labels into candidate compound tokens."""
    text = str(raw).strip()
    if not text:
        return []

    # Remove simple leading label prefixes from manual notes.
    text = re.sub(r"^[a-z]\s*:\s*", "", text, flags=re.IGNORECASE)
    # Split on common compound separators.
    parts = re.split(r"\s*\+\s*|\s*/\s*|\s*,\s*", text)
    return [p.strip() for p in parts if p.strip()]


def _load_compound_vocab() -> dict[str, str]:
    """
    Build normalized-name -> canonical compound name map from:
      1) HKG food-compound edges (tail column)
      2) FooDB Compound.csv (name + moldb_iupac)
    """
    vocab: dict[str, str] = {}

    # HKG compounds (graph vocabulary)
    try:
        hkg = pd.read_csv(_HKG_FOOD_COMPOUND_FILE, usecols=["tail"])
        for tail in hkg["tail"].dropna().astype(str):
            n = _norm_compound_name(tail)
            if n and n not in vocab:
                vocab[n] = str(tail).strip()
    except Exception:
        pass

    # FooDB compounds (reference vocabulary)
    try:
        comp = pd.read_csv(_FOODB_COMPOUND_FILE, usecols=["name", "moldb_iupac"], low_memory=False)
        for col in ("name", "moldb_iupac"):
            for val in comp[col].dropna().astype(str):
                n = _norm_compound_name(val)
                if n and n not in vocab:
                    vocab[n] = str(val).strip()
    except Exception:
        pass

    # A minimal alias bridge for frequent manual labels.
    alias_to_norm = {
        "vitamin k": "vitamin k1",
        "vit k": "vitamin k1",
        "na": "sodium",
        "na ": "sodium",
        "na+": "sodium",
        "s allylcysteine": "s allylcysteine",
    }
    for alias, target in alias_to_norm.items():
        a = _norm_compound_name(alias)
        t = _norm_compound_name(target)
        if a and t and t in vocab:
            vocab[a] = vocab[t]

    return vocab


COMPOUND_CANONICAL: dict[str, str] = _load_compound_vocab()


def _canonicalize_and_gate(compounds: list[str], verbose: bool = False) -> list[str]:
    """Return deduped canonical compounds that exist in FooDB/HKG vocab."""
    kept: list[str] = []
    dropped: list[str] = []
    seen = set()

    for raw in compounds:
        for token in _safe_split_compound(raw):
            n = _norm_compound_name(token)
            if not n:
                continue
            if n in COMPOUND_CANONICAL:
                c = COMPOUND_CANONICAL[n]
                key = c.lower().strip()
                if key not in seen:
                    seen.add(key)
                    kept.append(c)
            else:
                dropped.append(token)

    if verbose and dropped:
        print(f"  [compound gate] dropped {len(dropped)} unverified tokens: {sorted(set(dropped))[:12]}")
    return kept

def _merge(a: list, b: list) -> list:
    """Return a + b deduplicated, preserving order, case-insensitive dedup."""
    seen = set()
    result = []
    for item in a + b:
        key = item.strip().lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a specialized pharmacognosy assistant. Your task is to decompose food names into their key bioactive chemical constituents that are relevant to drug-food interactions.

Include compounds that interact via ANY of these 6 mechanisms:

1. CYP ENZYME INHIBITION/INDUCTION
   Cytochrome P450 enzymes: CYP3A4, CYP2D6, CYP2C9, CYP2C19, CYP1A2, CYP2E1
   Example: Bergamottin (grapefruit) inhibits CYP3A4

2. P-GLYCOPROTEIN / OATP TRANSPORT
   P-gp (ABCB1/MDR1), OATP1B1, OATP2B1 efflux/uptake transporters
   Example: Naringenin inhibits P-gp and OATP2B1

3. DIVALENT CATION CHELATION
   Foods rich in Ca2+, Mg2+, Zn2+, Fe2+ that chelate drugs in the gut lumen.
   Include Calcium for dairy/leafy greens, Magnesium for nuts/legumes,
   Iron for red meat/legumes, Zinc for shellfish/meat.
   Example: Calcium in milk chelates fluoroquinolones, tetracyclines,
   levothyroxine, bisphosphonates, reducing absorption by up to 50%.

4. GASTRIC pH ALTERATION
   Components that change gastric acid affecting drug dissolution.
   Example: Carbonated or acidic drinks vs. enteric-coated drugs.

5. PLASMA PROTEIN BINDING DISPLACEMENT
   Compounds displacing drugs from albumin or other plasma proteins.
   Example: Free fatty acids displacing highly protein-bound drugs.

6. PHARMACODYNAMIC SYNERGY / ANTAGONISM
   Direct PD interactions (not metabolic):
   - Vitamin K1 (phylloquinone) in green vegetables antagonizes warfarin/acenocoumarol
   - Tyramine in fermented foods (aged cheese, wine, soy sauce) with MAO inhibitors
   - Potassium-rich foods with potassium-sparing diuretics or ACE inhibitors
   - Caffeine/xanthines synergizing with stimulants or antagonizing adenosine receptor drugs
   - Serotonin/dopamine precursors with SSRIs or MAOIs

INCLUSION RULES:
- DO include: specific named phytochemicals, Vitamin K1, minerals (Ca, Mg, Fe, Zn)
  when the food is a significant dietary source, tyramine, tannins, oxalates, caffeine
- DO NOT include: water, generic starch, non-bioactive fibre, trace minerals in
  insignificant amounts, vague terms like "antioxidants", "flavonoids" without specifics
- Include a mineral ONLY if the food is a major dietary source

Return ONLY a JSON object. No preamble. No explanations. No markdown.
Format: {"bioactives": ["CompoundName1", "CompoundName2"]}
If no pharmacologically relevant constituents exist, return: {"bioactives": []}

Examples:

User: Harissa Sauce
Assistant: {"bioactives": ["Capsaicin", "Allicin", "p-Cymene", "Carvacrol"]}

User: Grapefruit Juice
Assistant: {"bioactives": ["Naringenin", "Bergamottin", "6,7-Dihydroxybergamottin"]}

User: Spinach
Assistant: {"bioactives": ["Vitamin K1", "Calcium", "Magnesium", "Kaempferol", "Quercetin"]}

User: Kale
Assistant: {"bioactives": ["Vitamin K1", "Calcium", "Sulforaphane", "Kaempferol"]}

User: Dairy Milk
Assistant: {"bioactives": ["Calcium", "Magnesium"]}

User: Cheese (aged/fermented)
Assistant: {"bioactives": ["Calcium", "Tyramine", "Magnesium"]}

User: Banana
Assistant: {"bioactives": ["Potassium", "Dopamine", "Serotonin"]}

User: Green Tea
Assistant: {"bioactives": ["Epigallocatechin gallate", "Caffeine", "Theanine"]}

User: Mint Tea
Assistant: {"bioactives": ["Menthol", "Menthone", "Rosmarinic acid", "Luteolin"]}

User: Black Seed (Nigella sativa)
Assistant: {"bioactives": ["Thymoquinone", "Carvacrol", "p-Cymene"]}

User: Garlic
Assistant: {"bioactives": ["Allicin", "Diallyl sulfide", "Diallyl disulfide", "S-Allylcysteine"]}

User: Turmeric
Assistant: {"bioactives": ["Curcumin", "Bisdemethoxycurcumin", "Turmerone"]}

User: Red Wine
Assistant: {"bioactives": ["Resveratrol", "Quercetin", "Tyramine", "Ethanol", "Tannins"]}

User: Broccoli
Assistant: {"bioactives": ["Vitamin K1", "Sulforaphane", "Calcium", "Indole-3-carbinol"]}

User: Pizza (mozzarella + tomato + herbs)
Assistant: {"bioactives": ["Calcium", "Rosmarinic acid", "Carvacrol", "Luteolin", "Lycopene"]}

User: Plain White Rice
Assistant: {"bioactives": []}

User: Water
Assistant: {"bioactives": []}"""


# ── Cache helpers ─────────────────────────────────────────────────────────────
def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


_REDIS = None


def _get_redis_client():
    global _REDIS
    if _REDIS is not None:
        return _REDIS
    if not REDIS_URL or redis is None:
        return None
    try:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        _REDIS = client
        return _REDIS
    except Exception:
        return None


def _redis_key(food_key: str) -> str:
    return f"llm_food:{food_key}"


def _get_redis_cache(food_key: str) -> list[str] | None:
    client = _get_redis_client()
    if client is None:
        return None
    try:
        raw = client.get(_redis_key(food_key))
        if not raw:
            return None
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(c).strip() for c in data if str(c).strip()]
        return None
    except Exception:
        return None


def _set_redis_cache(food_key: str, compounds: list[str]) -> None:
    client = _get_redis_client()
    if client is None:
        return
    try:
        client.setex(_redis_key(food_key), REDIS_TTL_SECONDS, json.dumps(compounds, ensure_ascii=False))
    except Exception:
        return


# ── Module-level cache (loaded once) ─────────────────────────────────────────
_CACHE: dict | None = None


def _get_cache() -> dict:
    global _CACHE
    if _CACHE is None:
        _CACHE = _load_cache()
    return _CACHE


# ── OpenRouter call (primary) ─────────────────────────────────────────────────
def _call_openrouter(food_name: str) -> list[str]:
    payload = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": food_name},
        ],
        "temperature": 0.1,
        "max_tokens": 256,
    }).encode("utf-8")

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://dfinder.local",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data    = json.loads(resp.read())
        content = data["choices"][0]["message"]["content"].strip()
        # Strip <think>...</think> if model returns reasoning traces
        if "</think>" in content:
            content = content.split("</think>")[-1].strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = "\n".join(
                ln for ln in content.splitlines() if not ln.startswith("```")
            ).strip()
        data2 = json.loads(content)
        return [str(c).strip() for c in data2.get("bioactives", []) if str(c).strip()]


# ── Gemini call (fallback) ────────────────────────────────────────────────────
def _call_gemini(food_name: str) -> list[str]:
    from google import genai
    from google.genai import types
    client   = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=food_name,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.1,
            max_output_tokens=256,
        ),
    )
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = "\n".join(
            ln for ln in raw.splitlines() if not ln.startswith("```")
        ).strip()
    data = json.loads(raw)
    return [str(c).strip() for c in data.get("bioactives", []) if str(c).strip()]


# ── Core function ─────────────────────────────────────────────────────────────
def llm_decompose(food_name: str, verbose: bool = False) -> list[str]:
    """
    Returns a deduplicated list of CYP-relevant compound names for the given food.

    - If the food is a known Algerian dish (in NA_DISH_COMPOUNDS), those compounds
      are always included as a seed (from na_dish_compounds.json).
    - Then checks disk cache for any prior LLM result; if found, merges with seed.
    - Otherwise calls OpenRouter (Qwen3) → Gemini fallback; caches the LLM result.
    - Final output = merge(NA seed, LLM result), deduplicated, order-preserved.
    - Returns [] on any error so the pipeline falls through gracefully.

    Args:
        food_name: Human-readable food name, e.g. "Harissa", "Couscous", "Mint Tea"
        verbose:   Print debug info if True

    Returns:
        List of compound name strings, e.g. ["Phytic Acid", "Ferulic Acid", "Calcium"]
    """
    cache = _get_cache()
    key   = food_name.strip().lower()

    # NA dish seed compounds (always included when dish is known)
    na_raw = NA_DISH_COMPOUNDS.get(key, [])
    na_compounds = _canonicalize_and_gate(na_raw, verbose=verbose)
    if na_compounds and verbose:
        print(f"  [NA dish seed] {food_name} -> {na_compounds}")

    # Redis cache hit — fastest path in shared deployments
    redis_hit = _get_redis_cache(key)
    if redis_hit is not None:
        redis_hit = _canonicalize_and_gate(redis_hit, verbose=verbose)
        if verbose:
            print(f"  [LLM redis cache hit] {food_name} -> {redis_hit}")
        return _merge(na_compounds, redis_hit)

    # Cache hit — merge with NA seed and return
    if key in cache:
        llm_compounds = _canonicalize_and_gate(cache[key], verbose=verbose)
        if verbose:
            print(f"  [LLM cache hit] {food_name} -> {llm_compounds}")
        merged = _merge(na_compounds, llm_compounds)
        return merged

    # LLM call — try OpenRouter first, fall back to Gemini
    llm_compounds = []
    try:
        llm_compounds = _call_openrouter(food_name)
    except Exception as e:
        if verbose:
            print(f"  [OpenRouter error] {food_name}: {type(e).__name__}: {e}")
        try:
            llm_compounds = _call_gemini(food_name)
        except Exception as e2:
            if verbose:
                print(f"  [Gemini fallback error] {food_name}: {type(e2).__name__}: {e2}")
            llm_compounds = []

    llm_compounds = _canonicalize_and_gate(llm_compounds, verbose=verbose)

    # Cache only LLM part (NA seed is always re-applied at call time)
    cache[key] = llm_compounds
    _set_redis_cache(key, llm_compounds)
    _save_cache(cache)

    merged = _merge(na_compounds, llm_compounds)
    if verbose:
        print(f"  [LLM decompose] {food_name} -> {llm_compounds}  [merged] -> {merged}")

    return merged


# ── Tier system prompt ─────────────────────────────────────────────────────────
_TIER_SYSTEM_PROMPT = """You are a clinical dietitian assistant. For any food name given, return the approximate content tier for 5 clinically important nutrients as they relate to drug-food interactions.

Tiers are based on amount per typical 100g serving:
  Calcium  : HIGH >= 300mg  |  MEDIUM 100-299mg  |  LOW < 100mg
  Vitamin K: HIGH >= 100µg  |  MEDIUM 20-99µg    |  LOW < 20µg
  Iron     : HIGH >= 3mg    |  MEDIUM 1-2.9mg    |  LOW < 1mg
  Potassium: HIGH >= 400mg  |  MEDIUM 200-399mg  |  LOW < 200mg
  Tyramine : HIGH = aged/fermented foods (aged cheese, cured meat, wine, soy sauce, kimchi, miso)
             MEDIUM = partially fermented or ripened (yogurt, avocado, banana, overripe fruit)
             LOW = fresh/cooked standard foods

Return ONLY a JSON object with exactly these 5 keys: calcium, vitk, iron, potassium, tyramine.
Values must be exactly one of: "HIGH", "MEDIUM", "LOW".
No preamble. No explanations. No markdown.

Examples:
User: Spinach
{"calcium":"LOW","vitk":"HIGH","iron":"MEDIUM","potassium":"HIGH","tyramine":"LOW"}

User: Pizza (mozzarella and tomato)
{"calcium":"HIGH","vitk":"LOW","iron":"LOW","potassium":"LOW","tyramine":"LOW"}

User: Hamburger
{"calcium":"MEDIUM","vitk":"LOW","iron":"MEDIUM","potassium":"MEDIUM","tyramine":"MEDIUM"}

User: Aged Cheddar Cheese
{"calcium":"HIGH","vitk":"LOW","iron":"LOW","potassium":"LOW","tyramine":"HIGH"}

User: Banana
{"calcium":"LOW","vitk":"LOW","iron":"LOW","potassium":"HIGH","tyramine":"MEDIUM"}

User: Lentil Soup
{"calcium":"LOW","vitk":"LOW","iron":"HIGH","potassium":"HIGH","tyramine":"LOW"}

User: Plain White Rice
{"calcium":"LOW","vitk":"LOW","iron":"LOW","potassium":"LOW","tyramine":"LOW"}"""

_TIERS_CACHE_SUFFIX = ":tiers"


def _parse_tiers(content: str) -> dict:
    """Parse LLM tier JSON, returning a dict with all 5 keys defaulting to LOW."""
    defaults = {"calcium": "LOW", "vitk": "LOW", "iron": "LOW", "potassium": "LOW", "tyramine": "LOW"}
    if "</think>" in content:
        content = content.split("</think>")[-1].strip()
    if content.startswith("```"):
        content = "\n".join(ln for ln in content.splitlines() if not ln.startswith("```")).strip()
    try:
        data = json.loads(content)
        valid = {"HIGH", "MEDIUM", "LOW"}
        for k in defaults:
            if str(data.get(k, "")).upper() in valid:
                defaults[k] = str(data[k]).upper()
    except Exception:
        pass
    return defaults


def llm_food_tiers(food_name: str, verbose: bool = False) -> dict:
    """
    Returns a dict of 5 nutrient tiers for the given food:
      {"calcium": "HIGH"|"MEDIUM"|"LOW", "vitk": ..., "iron": ...,
       "potassium": ..., "tyramine": ...}

    Used by PhysicochemicalEngine when the food is not in the USDA table.
    Results cached under f"{key}:tiers".
    """
    cache = _get_cache()
    key   = food_name.strip().lower() + _TIERS_CACHE_SUFFIX

    if key in cache:
        if verbose:
            print(f"  [LLM tiers cache hit] {food_name} -> {cache[key]}")
        return cache[key]

    tiers = {"calcium": "LOW", "vitk": "LOW", "iron": "LOW", "potassium": "LOW", "tyramine": "LOW"}
    try:
        payload = json.dumps({
            "model": OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": _TIER_SYSTEM_PROMPT},
                {"role": "user",   "content": food_name},
            ],
            "temperature": 0.0,
            "max_tokens": 128,
        }).encode("utf-8")
        req = urllib.request.Request(
            OPENROUTER_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://dfinder.local",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data    = json.loads(resp.read())
            content = data["choices"][0]["message"]["content"].strip()
            tiers   = _parse_tiers(content)
    except Exception as e:
        if verbose:
            print(f"  [LLM tiers OpenRouter error] {food_name}: {e}")
        try:
            from google import genai
            from google.genai import types
            client   = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=food_name,
                config=types.GenerateContentConfig(
                    system_instruction=_TIER_SYSTEM_PROMPT,
                    temperature=0.0,
                    max_output_tokens=128,
                ),
            )
            tiers = _parse_tiers(response.text.strip())
        except Exception as e2:
            if verbose:
                print(f"  [LLM tiers Gemini error] {food_name}: {e2}")

    cache[key] = tiers
    _save_cache(cache)

    if verbose:
        print(f"  [LLM food tiers] {food_name} -> {tiers}")

    return tiers


# ── Friendly Narrative Generation (Phase 7b - Output Humanization) ────────────
_NARRATIVE_SYSTEM_PROMPT = """You are the HealthOpt Patient Communicator.

Input Context:

Medication: {medication_name}

Food: {food_name}

Identified Compounds: {compounds} (e.g., Calcium, Phytic Acid, or Naringin)

Mechanism Flag: {flag} (e.g., CHELATION_RISK or CYP3A4_INHIBITION)

Instructions for the Friendly Explanation:

1. Identify the Culprits:
Start by mentioning the specific ingredients in the food (like the compounds) that are causing the issue.

2. Apply the Mineral Magnet (Chelation):
If the flag is CHELATION_RISK, explain that the compounds are acting like a Mineral Magnet.
They claw onto the medication, forming a clump that your body cannot absorb.

3. Apply the Traffic Jam (Enzyme Block):
If the flag involves enzymes (CYP450/CYP3A4), explain that the food is causing a Traffic Jam in your liver.
This stops the liver from processing the medication, leading to buildup in your blood.

4. Apply the Tug-of-War (Antagonism):
If the food does the opposite of the drug (like Vitamin K vs. Warfarin), call it a Tug-of-War.

5. Direct Impact:
End by stating this makes the medication less effective for current health goals.

Strict Grounding Rules:
- Use only the provided input context and pipeline evidence.
- Do not add compounds, mechanisms, percentages, diagnoses, cycle phases, or outcomes not present in the provided context.
- If a detail is missing, say "Not available from current pipeline evidence." rather than inventing it.
- Do not mention LightGCN, model internals, layers, embeddings, or algorithm names in the friendly text.
- Do not include numeric model scores, confidence scores, or fusion numbers in user-facing prose.

No-interaction rule (mandatory):
- If risk is INSUFFICIENT/NONE or no actionable interaction exists, return:
    - what_is_happening: "No interaction detected."
    - why_it_matters: "No clinically meaningful interaction was identified from current evidence."
    - how_to_fix_it: ["No timing adjustment is needed based on current data."]
    - when_to_act: "LOW PRIORITY - no action needed unless symptoms change."

Return ONLY valid JSON (no markdown):
{
    "what_is_happening": "plain text",
    "why_it_matters": "plain text",
    "how_to_fix_it": ["plain text tip"],
    "when_to_act": "plain text urgency"
}
"""


def _clean_narrative_text(text: str) -> str:
    """Normalize LLM prose to keep it patient-friendly and non-repetitive."""
    if not isinstance(text, str):
        return ""
    cleaned = text.strip()
    for prefix in ("Medication:", "Food:", "Drug:", "Risk Level:"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    # Remove leading warning/info emojis when model still injects them in prose.
    while cleaned and cleaned[0] in "⚠️❗❓💙💡🕒✅⏰":
        cleaned = cleaned[1:].strip()
    return cleaned


def _format_compounds_for_prompt(food_name: str, bioactives: list[str] | None) -> str:
    """Create a specific compound context string for the explanation prompt."""
    if not bioactives:
        return "No specific compounds identified"

    tagged: list[str] = []

    # Keep compounds exactly as provided by pipeline evidence (no inferred ingredients).
    for c in bioactives:
        c_norm = str(c).strip()
        tagged.append(c_norm)

    # De-duplicate while preserving order
    seen = set()
    unique = []
    for t in tagged:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            unique.append(t)

    return ", ".join(unique)


def _has_direct_chemical_path(technical_flag: str, mechanism: str) -> bool:
    """Heuristic: whether we can explain via known chemical mechanism."""
    flag = (technical_flag or "").upper()
    mech = (mechanism or "").lower()
    if flag in {
        "CHELATION_RISK",
        "CYP3A4_INHIBITION",
        "CYP3A4_INDUCTION",
        "VITAMIN_K_ANTAGONISM",
        "MAOI_INTERACTION",
        "POTASSIUM_RISK",
        "ACID_ABSORPTION_RISK",
        "ACID_LABILE_RISK",
    }:
        return True
    return any(k in mech for k in ["chelat", "cyp", "vitamin k", "tyramine", "potassium", "acid", "bioavailability"])


def _extract_physchem_culprits(technical_flag: str, pipeline_evidence: dict | None) -> list[str]:
    """Extract culprit compounds/signals from physicochemical layer evidence."""
    if not isinstance(pipeline_evidence, dict):
        return []

    flag = (technical_flag or "").upper()
    warnings = pipeline_evidence.get("physicochemical_warnings", []) or []
    culprits: list[str] = []

    signal_map = {
        "calcium": "Calcium",
        "magnesium": "Magnesium",
        "zinc": "Zinc",
        "iron": "Iron",
        "vitamin_k": "Vitamin K1",
        "potassium": "Potassium",
        "tyramine": "Tyramine",
    }

    for w in warnings:
        if not isinstance(w, dict):
            continue
        rule = str(w.get("rule", "")).upper()
        if flag and rule and rule != flag:
            continue

        food_signal = str(w.get("food_signal", "")).lower()

        # 1) Strongest source: structured food signal (e.g., "calcium_high").
        for key, name in signal_map.items():
            if key in food_signal:
                culprits.append(name)

        # 2) Fallback only when signal is missing.
        if not food_signal:
            mechanism = str(w.get("mechanism", "")).lower()
            for token, name in [
                ("calcium", "Calcium"),
                ("magnesium", "Magnesium"),
                ("zinc", "Zinc"),
                ("iron", "Iron"),
                ("vitamin k", "Vitamin K1"),
                ("potassium", "Potassium"),
                ("tyramine", "Tyramine"),
            ]:
                if re.search(rf"\b{re.escape(token)}\b", mechanism):
                    culprits.append(name)

    seen = set()
    out = []
    for c in culprits:
        k = c.lower()
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out


def _build_confidence_driver_summary(pipeline_evidence: dict | None) -> str:
    """Create a compact summary of phase contributions to confidence."""
    if not isinstance(pipeline_evidence, dict):
        return "Not available from current pipeline evidence."

    parts = []
    flags = pipeline_evidence.get("flags", []) or []
    if flags:
        parts.append(f"flags={','.join(str(f) for f in flags)}")

    warnings = pipeline_evidence.get("physicochemical_warnings", []) or []
    if warnings:
        rules = [str(w.get("rule", "")) for w in warnings if isinstance(w, dict) and w.get("rule")]
        if rules:
            parts.append(f"physchem_rules={','.join(rules)}")

    for key in ["norm_graph", "norm_kge", "norm_lgn", "fusion_score", "lgn_score"]:
        val = pipeline_evidence.get(key)
        if isinstance(val, (int, float)):
            parts.append(f"{key}={val:.4f}")

    return "; ".join(parts) if parts else "Not available from current pipeline evidence."


def _extract_cyp_primary_culprit_from_mechanism(mechanism: str, food_name: str) -> str:
    """Extract the food-side CYP culprit from technical mechanism text (e.g., 'Retinol (yogurt) inhibits CYP3A4')."""
    text = str(mechanism or "")
    food = re.escape(str(food_name or "").strip())

    # Prefer explicit food-side pattern: "<Compound> (food) inhibits CYP..."
    if food:
        m = re.search(
            rf"([A-Za-z0-9\-\s]+?)\s*\({food}\)\s+inhibit\w*\s+CYP",
            text,
            flags=re.IGNORECASE,
        )
        if m:
            return m.group(1).strip()

    # Fallback: first inhibitor entity before CYP mention.
    m2 = re.search(r"([A-Za-z0-9\-\s]+?)\s+inhibit\w*\s+CYP", text, flags=re.IGNORECASE)
    if m2:
        return m2.group(1).strip()

    return ""


def _pick_primary_evidence_compounds(
    technical_flag: str,
    food_name: str,
    bioactives: list[str] | None,
    pipeline_evidence: dict | None = None,
) -> list[str]:
    """Pick mechanism-driving compounds so the narrative stays specific and clinically relevant."""
    flag = (technical_flag or "").upper()
    compounds = [str(c).strip() for c in (bioactives or []) if str(c).strip()]
    by_key = {c.lower(): c for c in compounds}

    primary: list[str] = []

    # Highest priority depends on mechanism family.
    if flag == "CHELATION_RISK":
        # For chelation, physicochemical layer is the authoritative culprit source.
        physchem = _extract_physchem_culprits(flag, pipeline_evidence)
        primary.extend(physchem)

    elif flag in {"CYP3A4_INHIBITION", "CYP3A4_INDUCTION"}:
        # For CYP interactions, prefer mechanism-derived food-side culprit (e.g., Retinol in yogurt).
        mech_text = ""
        if isinstance(pipeline_evidence, dict):
            mech_text = str(pipeline_evidence.get("technical_mechanism", "") or "")
        cyp_culprit = _extract_cyp_primary_culprit_from_mechanism(mech_text, food_name)
        if cyp_culprit:
            primary.append(cyp_culprit)

    if flag == "CHELATION_RISK":
        for k in ["calcium", "magnesium", "zinc", "iron", "phytic acid", "phytate", "oxalates", "fiber"]:
            if k in by_key:
                primary.append(by_key[k])

    elif flag in {"CYP3A4_INHIBITION", "CYP3A4_INDUCTION"}:
        for k in ["bergamottin", "6,7-dihydroxybergamottin", "naringenin", "naringin", "quercetin"]:
            if k in by_key:
                primary.append(by_key[k])

    elif flag == "VITAMIN_K_ANTAGONISM":
        for k in ["vitamin k1", "phylloquinone"]:
            if k in by_key:
                primary.append(by_key[k])

    if not primary:
        primary = compounds[:4]

    # de-duplicate
    seen = set()
    out = []
    for p in primary:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    # For chelation, keep the leading culprit dominant (usually from food_signal),
    # then include secondary contributors as context.
    if flag == "CHELATION_RISK" and out:
        lead = out[0]
        rest = [x for x in out[1:] if x.lower() != lead.lower()]
        return [lead] + rest
    return out


def _normalize_narrative_payload(narrative: dict, risk_level: str, food_name: str, metaphor: str, mechanism: str) -> dict:
    """Ensure output shape and clean text to avoid noisy/repetitive UI rendering."""
    if not isinstance(narrative, dict):
        narrative = {}

    tips = narrative.get("how_to_fix_it", [])
    if not isinstance(tips, list):
        tips = [str(tips)] if tips else []
    tips = [str(t).strip() for t in tips if str(t).strip()]

    if not tips:
        tips = [f"🕒 Keep at least 2 hours between {food_name} and your medication."]

    what_text = _clean_narrative_text(narrative.get("what_is_happening", f"{metaphor}: {mechanism}"))
    # Guardrail: avoid awkward singular phrasing in one-mechanism narratives.
    if "Mechanisms in order:" not in what_text and "2)" not in what_text:
        what_text = re.sub(r"\bcan also act as\b", "can act as", what_text, flags=re.IGNORECASE)
        what_text = re.sub(r"\bcan also cause\b", "can cause", what_text, flags=re.IGNORECASE)

    return {
        "what_is_happening": what_text,
        "why_it_matters": _clean_narrative_text(narrative.get("why_it_matters", "This interaction can change how well your medication works.")),
        "how_to_fix_it": tips,
        "when_to_act": _clean_narrative_text(narrative.get("when_to_act", f"{risk_level} RISK")),
    }


def _anchor_narrative_entities(
    narrative: dict,
    food_name: str,
    drug_name: str,
    primary_culprit: str,
    technical_flag: str,
) -> dict:
    """Force explicit food/drug naming and remove generic placeholders."""
    if not isinstance(narrative, dict):
        return narrative

    safe_food = (food_name or "this food").strip()
    safe_drug = (drug_name or "this medication").strip()
    culprit = (primary_culprit or "the key compound").strip()
    flag = (technical_flag or "").upper()

    def _rewrite(text: str) -> str:
        t = str(text or "")
        t = re.sub(r"\bUnknown\s+Food\b", safe_food, t, flags=re.IGNORECASE)
        t = re.sub(r"\bUnknown\s+Drug\b", safe_drug, t, flags=re.IGNORECASE)
        t = re.sub(r"\bthe food\b", safe_food, t, flags=re.IGNORECASE)
        t = re.sub(r"\bthis food\b", safe_food, t, flags=re.IGNORECASE)
        t = re.sub(r"\bthe medication\b", safe_drug, t, flags=re.IGNORECASE)
        t = re.sub(r"\bthis medication\b", safe_drug, t, flags=re.IGNORECASE)
        t = re.sub(r"\byour medication\b", safe_drug, t, flags=re.IGNORECASE)
        return t

    what = _rewrite(narrative.get("what_is_happening", ""))
    why = _rewrite(narrative.get("why_it_matters", ""))
    tips = [_rewrite(t) for t in (narrative.get("how_to_fix_it", []) or [])]
    when = _rewrite(narrative.get("when_to_act", ""))

    # Strict anchor: first line must name both entities.
    if safe_food.lower() not in what.lower() or safe_drug.lower() not in what.lower():
        if flag == "CHELATION_RISK":
            what = (
                f"{culprit} in {safe_food} acts like a Mineral Magnet and binds to {safe_drug}, "
                f"forming clumps that reduce absorption."
            )
        elif "CYP" in flag:
            what = (
                f"{safe_food} interferes with liver worker CYP3A4 needed to process {safe_drug}, "
                f"creating a Traffic Jam that slows metabolism."
            )
        else:
            what = f"{safe_food} is interacting with {safe_drug} and changing how your body handles the medication."

    narrative["what_is_happening"] = what
    narrative["why_it_matters"] = why
    narrative["how_to_fix_it"] = tips
    narrative["when_to_act"] = when
    return narrative


def _mechanism_phrase(flag: str, food_name: str, drug_name: str, is_primary: bool = True, num_total_mechanisms: int = 1) -> str:
    """
    Return a concise, user-facing mechanism sentence with required labels.
    
    Args:
        flag: Technical flag (CHELATION_RISK, etc.)
        food_name: Name of food
        drug_name: Name of drug
        is_primary: True if this is the primary/only mechanism (affects phrasing)
        num_total_mechanisms: Total count of mechanisms detected (for pluralization)
    """
    food = (food_name or "this food").strip()
    drug = (drug_name or "this medication").strip()
    f = (flag or "").upper()
    
    primary_or_single = (is_primary or num_total_mechanisms == 1)

    if f == "VITAMIN_K_ANTAGONISM":
        return f"{food} creates a Tug-of-War (Antagonism): Vitamin K in {food} counteracts the anticoagulant effect of {drug}."
    if f in {"MAOI_INTERACTION", "TYRAMINE_CRISIS"}:
        return f"{food} creates a Chemical Clash (MAOI/Tyramine Pathway), which can trigger dangerous blood pressure spikes with {drug}."
    if f in {"POTASSIUM_SPARING", "POTASSIUM_OVERLOAD"}:
        return f"{food} causes a Potassium Pile-Up (Electrolyte Pathway), raising potassium while {drug} also reduces potassium excretion."
    if f == "ACID_ABSORPTION_RISK":
        return f"{food} increases stomach irritation risk with {drug}, especially when taken close together."
    if f == "CHELATION_RISK":
        return (
            f"{food} acts as a Mineral Magnet (Chelation), physically binding {drug} and lowering absorption."
            if primary_or_single
            else f"{food} can also act as a Mineral Magnet (Chelation), physically binding {drug} and lowering absorption."
        )
    if f == "CYP3A4_INDUCTION":
        return (
            f"{food} causes a Liver Speed Boost (Enzyme Pathway), making CYP3A4 clear {drug} too quickly."
            if primary_or_single
            else f"{food} can also cause a Liver Speed Boost (Enzyme Pathway), making CYP3A4 clear {drug} too quickly."
        )
    if f == "CYP3A4_INHIBITION":
        return (
            f"{food} causes a Liver Traffic Jam (Enzyme Pathway), slowing CYP3A4 processing of {drug}."
            if primary_or_single
            else f"{food} can also cause a Liver Traffic Jam (Enzyme Pathway), slowing CYP3A4 processing of {drug}."
        )
    return ""


def _enrich_with_ordered_mechanisms(
    narrative: dict,
    pipeline_evidence: dict | None,
    technical_flag: str,
    food_name: str,
    drug_name: str,
) -> dict:
    """Ensure friendly narrative includes all detected mechanisms in ordered, labeled form."""
    if not isinstance(narrative, dict):
        return narrative

    primary = str((pipeline_evidence or {}).get("primary_flag", "") or technical_flag or "").upper()
    secondary = [str(x).upper() for x in ((pipeline_evidence or {}).get("secondary_flags", []) or [])]

    ordered_flags = [f for f in [primary, *secondary] if f]
    # de-duplicate preserving order
    seen = set()
    ordered_flags = [f for f in ordered_flags if not (f in seen or seen.add(f))]

    phrases = []
    num_mechanisms = len(ordered_flags)
    for idx, f in enumerate(ordered_flags):
        p = _mechanism_phrase(f, food_name, drug_name, is_primary=(idx == 0), num_total_mechanisms=num_mechanisms)
        if p:
            phrases.append(p)

    if not phrases:
        return narrative

    intro = "Mechanisms in order: "
    sequence_labels = []
    for f in ordered_flags:
        if f == "VITAMIN_K_ANTAGONISM":
            sequence_labels.append("Tug-of-War (Antagonism)")
        elif f in {"MAOI_INTERACTION", "TYRAMINE_CRISIS"}:
            sequence_labels.append("Chemical Clash (MAOI/Tyramine)")
        elif f in {"POTASSIUM_SPARING", "POTASSIUM_OVERLOAD"}:
            sequence_labels.append("Potassium Pile-Up (Electrolyte Pathway)")
        elif f == "ACID_ABSORPTION_RISK":
            sequence_labels.append("Stomach Stress (Acid/GI Pathway)")
        elif f == "CHELATION_RISK":
            sequence_labels.append("Mineral Magnet (Chelation)")
        elif f in {"CYP3A4_INHIBITION", "CYP3A4_INDUCTION"}:
            sequence_labels.append("Liver Traffic Jam/Speed Boost (Enzyme Pathway)")

    # de-duplicate human labels too
    seq_seen = set()
    sequence_labels = [x for x in sequence_labels if not (x in seq_seen or seq_seen.add(x))]

    kge_found = bool((pipeline_evidence or {}).get("kge_found", False))
    mech_conf = str((pipeline_evidence or {}).get("mechanistic_confidence", "")).lower()
    kge_shared = (pipeline_evidence or {}).get("kge_shared_enzymes", []) or []

    strong_mech_note = ""
    if kge_found and mech_conf == "high":
        traces = []
        for edge in kge_shared[:2]:
            if not isinstance(edge, dict):
                continue
            compound = str(edge.get("compound") or "").strip()
            comp_rel = str(edge.get("comp_rel") or edge.get("relation") or "interacts with").strip()
            enzyme = str(edge.get("enzyme") or edge.get("name") or "").strip()
            drug_rel = str(edge.get("drug_rel") or "interacts with").strip()
            if compound and enzyme:
                traces.append(f"{compound} {comp_rel}s {enzyme}; {drug_name} {drug_rel}s {enzyme}")
            elif enzyme:
                traces.append(enzyme)
        if traces:
            strong_mech_note = " Strong pathway evidence: " + " | ".join(traces) + "."

    if len(phrases) == 1:
        summary = f"Mechanism: {sequence_labels[0]}." if sequence_labels else ""
        narrative["what_is_happening"] = (
            "In simple terms: " + phrases[0] + (" " + summary if summary else "") + strong_mech_note
        ).strip()
        if "VITAMIN_K_ANTAGONISM" in ordered_flags:
            why = str(narrative.get("why_it_matters", "")).strip()
            vk_line = "Primary risk is Vitamin K antagonism, which can reduce anticoagulant effect and destabilize INR."
            if "vitamin k" not in why.lower() and "inr" not in why.lower():
                narrative["why_it_matters"] = (why + " " + vk_line).strip()
        return narrative

    numbered_steps = [f"{idx}) {text}" for idx, text in enumerate(phrases, start=1)]
    summary = intro + " -> ".join(sequence_labels) + "."
    narrative["what_is_happening"] = (
        "In simple terms: " + " ".join(numbered_steps) + " " + summary + strong_mech_note
    ).strip()
    if "VITAMIN_K_ANTAGONISM" in ordered_flags:
        why = str(narrative.get("why_it_matters", "")).strip()
        vk_line = "Primary risk is Vitamin K antagonism, which can reduce anticoagulant effect and destabilize INR."
        if "vitamin k" not in why.lower() and "inr" not in why.lower():
            narrative["why_it_matters"] = (why + " " + vk_line).strip()
    return narrative


def _call_openrouter_narrative(narrative_prompt: str) -> dict:
    """Call OpenRouter with narrative prompt, return parsed JSON dict."""
    payload = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": _NARRATIVE_SYSTEM_PROMPT},
            {"role": "user",   "content": narrative_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 512,
    }).encode("utf-8")

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://dfinder.local",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data    = json.loads(resp.read())
        content = data["choices"][0]["message"]["content"].strip()
        # Strip <think>...</think> if model returns reasoning
        if "</think>" in content:
            content = content.split("</think>")[-1].strip()
        # Strip markdown code fences
        if content.startswith("```"):
            content = "\n".join(
                ln for ln in content.splitlines() if not ln.startswith("```")
            ).strip()
        return json.loads(content)


def _call_gemini_narrative(narrative_prompt: str) -> dict:
    """Call Gemini with narrative prompt, return parsed JSON dict."""
    from google import genai
    from google.genai import types
    client   = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=narrative_prompt,
        config=types.GenerateContentConfig(
            system_instruction=_NARRATIVE_SYSTEM_PROMPT,
            temperature=0.7,
            max_output_tokens=512,
        ),
    )
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = "\n".join(ln for ln in raw.splitlines() if not ln.startswith("```")).strip()
    return json.loads(raw)


_NARRATIVE_CACHE_SUFFIX = ":narrative_v16"


def _format_pathway_evidence(pipeline_evidence: dict | None) -> str:
    """
    Extract and format HKG/KGE pathway evidence for inclusion in friendly explanation.
    
    Returns a human-readable summary of exact pathways found.
    """
    if not pipeline_evidence:
        return ""
    
    evidence_parts = []
    
    # Graph (HKG) evidence
    graph_found = pipeline_evidence.get("graph_found", False)
    graph_shared_enzymes = pipeline_evidence.get("graph_shared_enzymes", []) or []
    if graph_found and graph_shared_enzymes:
        enzyme_names = []
        for enz_dict in graph_shared_enzymes[:3]:  # Top 3 pathways
            if isinstance(enz_dict, dict):
                name = enz_dict.get("enzyme", "") or enz_dict.get("name", "")
            else:
                name = str(enz_dict)
            if name:
                enzyme_names.append(name)
        if enzyme_names:
            evidence_parts.append(f"Documented biological pathway: {', '.join(enzyme_names)}")
    
    # KGE (mechanistic) evidence
    kge_found = pipeline_evidence.get("kge_found", False)
    kge_shared_enzymes = pipeline_evidence.get("kge_shared_enzymes", []) or []
    mechanistic_conf = pipeline_evidence.get("mechanistic_confidence", "low")
    
    if kge_found and kge_shared_enzymes:
        enzyme_names = []
        for enz_dict in kge_shared_enzymes[:3]:  # Top 3 pathways
            if isinstance(enz_dict, dict):
                name = enz_dict.get("enzyme", "") or enz_dict.get("name", "")
            else:
                name = str(enz_dict)
            if name:
                enzyme_names.append(name)
        if enzyme_names:
            if mechanistic_conf == "high":
                evidence_parts.append(f"Strong mechanistic pathway evidence: {', '.join(enzyme_names)}")
            else:
                evidence_parts.append(f"Inferred mechanistic pathway: {', '.join(enzyme_names)}")
    
    return " | ".join(evidence_parts) if evidence_parts else ""


def llm_friendly_narrative(
    drug_name: str,
    food_name: str,
    mechanism: str,
    risk_level: str,
    metaphor: str,
    technical_flag: str = "UNKNOWN",
    bioactives: list[str] = None,
    pipeline_evidence: dict | None = None,
    verbose: bool = False
) -> dict:
    """
    Use the same LLM (Qwen3-235B via OpenRouter) to generate a friendly explanation
    of a drug-food interaction.

    Args:
        drug_name: e.g., "Ferrous Sulfate"
        food_name: e.g., "Pizza"
        mechanism: Technical mechanism, e.g., "Chelation of ferrous iron by calcium and fiber"
        risk_level: "HIGH", "MEDIUM", or "LOW"
        metaphor: Friendly metaphor, e.g., "Mineral Magnet"
        bioactives: List of active compounds in the food (optional, for context)
        verbose: Print debug info if True

    Returns:
        dict with keys:
        - what_is_happening: str
        - why_it_matters: str
        - how_to_fix_it: list[str]
        - when_to_act: str
    """
    risk_upper = str(risk_level or "").strip().upper()
    mechanism_text = str(mechanism or "").strip().lower()

    # Hard guardrail: never ask the LLM to invent an interaction when risk is insufficient.
    if risk_upper in {"INSUFFICIENT", "NONE", "NO_INTERACTION"} or mechanism_text in {"", "none", "no interaction", "no interaction detected"}:
        return {
            "what_is_happening": "No interaction detected.",
            "why_it_matters": "No clinically meaningful interaction was identified from current evidence.",
            "how_to_fix_it": ["No timing adjustment is needed based on current data."],
            "when_to_act": "LOW PRIORITY - no action needed unless symptoms change.",
        }

    cache = _get_cache()
    primary_sig = str((pipeline_evidence or {}).get("primary_flag", "")).upper()
    secondary_sig = "|".join(str(x).upper() for x in ((pipeline_evidence or {}).get("secondary_flags", []) or []))
    mech_sig = str(mechanism or "").strip().lower()[:120]
    cache_key = (
        f"{drug_name.lower()}_{food_name.lower()}_{risk_level.lower()}_"
        f"{technical_flag.lower()}_{primary_sig}_{secondary_sig}_{mech_sig}{_NARRATIVE_CACHE_SUFFIX}"
    )

    # Cache hit
    if cache_key in cache:
        if verbose:
            print(f"  [LLM narrative cache hit] {drug_name} × {food_name}")
        return cache[cache_key]

    # Build narrative prompt (feed technical data to LLM for humanization)
    compounds_context = _format_compounds_for_prompt(food_name, bioactives)
    primary_evidence = _pick_primary_evidence_compounds(technical_flag, food_name, bioactives, pipeline_evidence)
    primary_culprit = primary_evidence[0] if primary_evidence else "Not available from current pipeline evidence"
    secondary = ", ".join(primary_evidence[1:]) if len(primary_evidence) > 1 else "None"
    primary_evidence_str = ", ".join(primary_evidence) if primary_evidence else "No high-confidence primary compounds"
    has_direct_path = _has_direct_chemical_path(technical_flag, mechanism)
    evidence_text = json.dumps(pipeline_evidence or {}, ensure_ascii=False)
    confidence_drivers = _build_confidence_driver_summary(pipeline_evidence)
    
    # Extract pathway evidence (HKG/KGE details)
    pathway_evidence = _format_pathway_evidence(pipeline_evidence)
    mechanistic_conf = (pipeline_evidence or {}).get("mechanistic_confidence", "low")
    kge_found = (pipeline_evidence or {}).get("kge_found", False)
    norm_lgn = float((pipeline_evidence or {}).get("norm_lgn", 0) or 0)
    
    # Add mechanistic strength note when appropriate
    mechanistic_note = ""
    if kge_found and norm_lgn >= 0.70:
        mechanistic_note = "\n- MECHANISTIC STRENGTH: High confidence in mechanistic pathway evidence—include this strength in the explanation."
    
    narrative_prompt = f"""Input Context:

Medication: {drug_name}

Food: {food_name}

Identified Compounds: {compounds_context}

Primary Interaction Compounds: {primary_evidence_str}

Primary Culprit Compound: {primary_culprit}

Secondary Contributor Compounds: {secondary}

Mechanism Flag: {technical_flag}

Risk Level: {risk_level}

Technical Mechanism: {mechanism}

{f'Pathway Evidence (Exact biological mechanisms found):{chr(10)}{pathway_evidence}' if pathway_evidence else ''}

Pipeline Evidence (use only this; do not invent): {evidence_text}

Confidence Drivers (pipeline phases): {confidence_drivers}

Grounding Notes:
- {'A direct chemical path is present.' if has_direct_path else 'No direct chemical path is present; use only the provided statistical/pattern evidence text.'}
- Use the metaphor \"{metaphor}\" only when it matches the mechanism flag behavior.
- If Mechanism Flag is CHELATION_RISK, attribute interaction only to cation-related evidence compounds/signals (Calcium/Magnesium/Zinc/Iron) from pipeline evidence.
- Start with the Primary Culprit Compound. Mention secondary contributors only as secondary.
- If confidence drivers are provided, reference them faithfully without adding new factors.{mechanistic_note}
"""

    narrative = {}
    try:
        narrative = _call_openrouter_narrative(narrative_prompt)
    except Exception as e:
        if verbose:
            print(f"  [OpenRouter narrative error] {drug_name} × {food_name}: {e}")
        try:
            narrative = _call_gemini_narrative(narrative_prompt)
        except Exception as e2:
            if verbose:
                print(f"  [Gemini narrative error] {drug_name} × {food_name}: {e2}")
            # Deterministic fallback: simple wording that still includes all detected mechanisms.
            primary_flag = str((pipeline_evidence or {}).get("primary_flag", "") or technical_flag or "").upper()
            secondary_flags = [str(x).upper() for x in ((pipeline_evidence or {}).get("secondary_flags", []) or [])]
            ordered_flags = [f for f in [primary_flag, *secondary_flags] if f]

            seen_flags = set()
            ordered_flags = [f for f in ordered_flags if not (f in seen_flags or seen_flags.add(f))]

            steps = []
            num_mechanisms = len(ordered_flags)
            for idx, flag in enumerate(ordered_flags):
                phrase = _mechanism_phrase(flag, food_name, drug_name, is_primary=(idx == 0), num_total_mechanisms=num_mechanisms)
                if phrase:
                    steps.append(phrase)

            if not steps:
                steps = [f"{food_name} may change how your body handles {drug_name}."]

            flags_set = set(ordered_flags)
            why_text = "This interaction can change how safe or effective your medication is."
            if any(f in flags_set for f in {"POTASSIUM_OVERLOAD", "POTASSIUM_SPARING"}):
                why_text = "Potassium can rise too high, which may cause heart rhythm problems or muscle weakness."
            elif "ACID_ABSORPTION_RISK" in flags_set:
                why_text = "Stomach irritation risk may increase, with symptoms like heartburn or abdominal pain."
            elif any(f in flags_set for f in {"CYP3A4_INHIBITION", "CYP3A4_INDUCTION"}):
                why_text = "Your medication level may become too high or too low if liver processing changes."

            tips = []
            if any(f in flags_set for f in {"POTASSIUM_OVERLOAD", "POTASSIUM_SPARING"}):
                tips.append("Limit high-potassium portions and ask your clinician whether potassium monitoring is needed.")
            if "ACID_ABSORPTION_RISK" in flags_set:
                tips.append(f"Avoid acidic foods such as {food_name} close to dosing, and take {drug_name} with water.")
            if "CHELATION_RISK" in flags_set:
                tips.append(f"Keep at least 2-3 hours between {food_name} and {drug_name}.")
            if any(f in flags_set for f in {"CYP3A4_INHIBITION", "CYP3A4_INDUCTION"}):
                tips.append(f"Avoid large amounts of {food_name} while using {drug_name}, and watch for side effects.")
            if not tips:
                tips.append(f"Ask your pharmacist about safe timing with {food_name} and {drug_name}.")

            if len(steps) == 1:
                what_text = "In simple terms: " + steps[0]
            else:
                numbered = [f"{idx}) {s}" for idx, s in enumerate(steps, start=1)]
                what_text = "In simple terms: " + " ".join(numbered)

            narrative = {
                "what_is_happening": what_text,
                "why_it_matters": why_text,
                "how_to_fix_it": tips,
                "when_to_act": f"{risk_level} RISK"
            }

    narrative = _normalize_narrative_payload(narrative, risk_level, food_name, metaphor, mechanism)
    narrative = _anchor_narrative_entities(
        narrative=narrative,
        food_name=food_name,
        drug_name=drug_name,
        primary_culprit=primary_culprit,
        technical_flag=technical_flag,
    )
    narrative = _enrich_with_ordered_mechanisms(
        narrative=narrative,
        pipeline_evidence=pipeline_evidence,
        technical_flag=technical_flag,
        food_name=food_name,
        drug_name=drug_name,
    )

    # Cache result
    cache[cache_key] = narrative
    _save_cache(cache)

    if verbose:
        print(f"  [LLM friendly narrative] {drug_name} × {food_name}")

    return narrative


# ── CLI / quick test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_foods = [
        "Harissa",
        "Mint Tea",
        "Black Seed Oil",
        "Couscous",
        "Dates",
        "Olive Oil",
        "Grapefruit",
        "Plain White Rice",
    ]
    print(f"{'Food':<25}  Bioactives")
    print("-" * 80)
    for food in test_foods:
        bioactives = llm_decompose(food, verbose=False)
        print(f"{food:<25}  {bioactives if bioactives else '(none - no CYP interaction expected)'}")
