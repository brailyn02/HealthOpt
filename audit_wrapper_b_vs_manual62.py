import json
import re
from pathlib import Path

import pandas as pd

OUT_DIR = Path("ablation_results")
OUT_DIR.mkdir(exist_ok=True)

MANUAL_PATH = Path("data/na_dish_compounds.json")
CACHE_PATH = Path("data/llm_food_cache.json")
FOODB_COMPOUND_PATH = Path("Compound.csv")


def norm_text(s: str) -> str:
    s = str(s).lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def norm_key(s: str) -> str:
    s = norm_text(s)
    s = re.sub(r"\([^)]*\)", "", s)  # drop parenthetical notes
    s = s.replace("/", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def food_aliases(food_name: str) -> set[str]:
    raw = norm_text(food_name)
    aliases = {norm_key(raw)}

    # split slash variants
    parts = [p.strip() for p in raw.split("/") if p.strip()]
    for p in parts:
        aliases.add(norm_key(p))

    # split with dash variants
    for p in re.split(r"\s+-\s+", raw):
        p = p.strip()
        if p:
            aliases.add(norm_key(p))

    aliases.discard("")
    return aliases


def norm_compound(s: str) -> str:
    s = norm_text(s)
    s = s.replace("_", " ")
    s = re.sub(r"\([^)]*\)", "", s)
    s = s.replace("/", " ")
    s = re.sub(r"[^a-z0-9+ ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# 1) Load manual compounds for 62 Algerian foods
with MANUAL_PATH.open("r", encoding="utf-8") as f:
    manual = json.load(f)

manual_foods = list(manual.keys())

# 2) Load Wrapper B cache
with CACHE_PATH.open("r", encoding="utf-8") as f:
    cache = json.load(f)

cache_food_map = {}
for k, v in cache.items():
    if ":tiers" in str(k).lower():
        continue
    if isinstance(v, list):
        cache_food_map[str(k)] = v

# Build reverse index for cache foods by normalized aliases
cache_alias_to_foods = {}
for cache_food in cache_food_map:
    aliases = food_aliases(cache_food)
    for a in aliases:
        cache_alias_to_foods.setdefault(a, set()).add(cache_food)

# 3) Load direct FooDB compound vocabulary
foodb = pd.read_csv(
    FOODB_COMPOUND_PATH,
    usecols=["name", "moldb_iupac"],
    low_memory=False,
)

foodb_name_vocab = set(foodb["name"].dropna().map(norm_compound).unique())
foodb_iupac_vocab = set(foodb["moldb_iupac"].dropna().map(norm_compound).unique())
foodb_vocab = foodb_name_vocab | foodb_iupac_vocab

# 4) Per-food comparison manual vs Wrapper B
food_rows = []
compound_rows = []

for manual_food in manual_foods:
    m_aliases = food_aliases(manual_food)
    matched_cache_foods = set()
    for a in m_aliases:
        matched_cache_foods |= cache_alias_to_foods.get(a, set())

    manual_compounds_raw = manual.get(manual_food, []) or []
    manual_compounds = [norm_compound(x) for x in manual_compounds_raw if str(x).strip()]
    manual_set = {x for x in manual_compounds if x}

    llm_compounds_raw = []
    for cf in sorted(matched_cache_foods):
        llm_compounds_raw.extend(cache_food_map.get(cf, []))
    llm_compounds = [norm_compound(x) for x in llm_compounds_raw if str(x).strip()]
    llm_set = {x for x in llm_compounds if x}

    overlap = manual_set & llm_set
    manual_only = manual_set - llm_set
    llm_only = llm_set - manual_set

    # Food-level summary row
    food_rows.append(
        {
            "manual_food": manual_food,
            "manual_food_aliases": " | ".join(sorted(m_aliases)),
            "matched_cache_foods": " | ".join(sorted(matched_cache_foods)),
            "has_wrapper_b_result": len(matched_cache_foods) > 0,
            "manual_compound_count": len(manual_set),
            "llm_compound_count": len(llm_set),
            "overlap_count": len(overlap),
            "manual_only_count": len(manual_only),
            "llm_only_count": len(llm_only),
            "manual_compounds": " | ".join(sorted(manual_set)),
            "llm_compounds": " | ".join(sorted(llm_set)),
            "overlap_compounds": " | ".join(sorted(overlap)),
            "manual_only_compounds": " | ".join(sorted(manual_only)),
            "llm_only_compounds": " | ".join(sorted(llm_only)),
        }
    )

    # Compound-level rows for availability checks
    for c in sorted(manual_set):
        compound_rows.append(
            {
                "manual_food": manual_food,
                "source": "manual",
                "compound": c,
                "in_foodb_vocab": c in foodb_vocab,
                "in_wrapper_for_this_food": c in llm_set,
            }
        )
    for c in sorted(llm_set):
        compound_rows.append(
            {
                "manual_food": manual_food,
                "source": "wrapper_b",
                "compound": c,
                "in_foodb_vocab": c in foodb_vocab,
                "in_manual_for_this_food": c in manual_set,
            }
        )

food_df = pd.DataFrame(food_rows)
compound_df = pd.DataFrame(compound_rows)

# 5) Aggregate metrics
n_manual_foods = len(manual_foods)
n_foods_with_wrapper = int(food_df["has_wrapper_b_result"].sum())

manual_compound_mentions = compound_df[compound_df["source"] == "manual"]
llm_compound_mentions = compound_df[compound_df["source"] == "wrapper_b"]

manual_foodb_hits = int(manual_compound_mentions["in_foodb_vocab"].sum())
llm_foodb_hits = int(llm_compound_mentions["in_foodb_vocab"].sum())

manual_total = len(manual_compound_mentions)
llm_total = len(llm_compound_mentions)

# overlap across foods where wrapper exists
overlap_total = int(food_df["overlap_count"].sum())
manual_only_total = int(food_df["manual_only_count"].sum())
llm_only_total = int(food_df["llm_only_count"].sum())

# 6) Write outputs
food_df.to_csv(OUT_DIR / "wrapper_b_vs_manual62_food_level.csv", index=False)
compound_df.to_csv(OUT_DIR / "wrapper_b_vs_manual62_compound_level.csv", index=False)

# unverified lists
compound_df[(compound_df["source"] == "manual") & (compound_df["in_foodb_vocab"] == False)].to_csv(
    OUT_DIR / "manual62_compounds_not_in_foodb.csv", index=False
)
compound_df[(compound_df["source"] == "wrapper_b") & (compound_df["in_foodb_vocab"] == False)].to_csv(
    OUT_DIR / "wrapper_b_compounds_not_in_foodb.csv", index=False
)

summary = f"""
WRAPPER B vs MANUAL 62-FOOD COMPOUND AUDIT
==========================================
Manual source: {MANUAL_PATH}
Wrapper B cache: {CACHE_PATH}
FoodB compound source: {FOODB_COMPOUND_PATH} (columns: name, moldb_iupac)

FOOD COVERAGE
- Manual foods total: {n_manual_foods}
- Manual foods with a Wrapper B cache match: {n_foods_with_wrapper}/{n_manual_foods} ({(n_foods_with_wrapper/n_manual_foods*100):.1f}%)

MANUAL COMPOUNDS (for 62 foods)
- Compound mentions: {manual_total}
- In FoodB vocab: {manual_foodb_hits}/{manual_total} ({((manual_foodb_hits/manual_total*100) if manual_total else 0):.1f}%)

WRAPPER B COMPOUNDS (only for foods that matched cache)
- Compound mentions: {llm_total}
- In FoodB vocab: {llm_foodb_hits}/{llm_total} ({((llm_foodb_hits/llm_total*100) if llm_total else 0):.1f}%)

FOOD-WISE AGREEMENT (manual vs wrapper)
- Overlap compounds (sum across foods): {overlap_total}
- Manual-only compounds (sum across foods): {manual_only_total}
- Wrapper-only compounds (sum across foods): {llm_only_total}

FILES WRITTEN
- {OUT_DIR / 'wrapper_b_vs_manual62_food_level.csv'}
- {OUT_DIR / 'wrapper_b_vs_manual62_compound_level.csv'}
- {OUT_DIR / 'manual62_compounds_not_in_foodb.csv'}
- {OUT_DIR / 'wrapper_b_compounds_not_in_foodb.csv'}
""".strip()

with (OUT_DIR / "wrapper_b_vs_manual62_summary.txt").open("w", encoding="utf-8") as f:
    f.write(summary + "\n")

print(summary)
print("\nDone.")
