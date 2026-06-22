"""
Builds algerian_brand_map.csv from the official Algerian drug registry.

Input : algerian_drugs.csv  (Nomenclature Nationale des Produits Pharmaceutiques)
Output: algerian_brand_map.csv

Mapping chain:
    NOM DE MARQUE (brand) → DENOMINATION COMMUNE INTERNATIONALE (INN)
                          → pipeline drug name  (from drug_id_map.csv)

Match types (in priority order):
    exact  — INN lowercased == pipeline drug name lowercased (direct hit)
    prefix — pipeline drug name is the first word(s) of the INN
             e.g. "Metformine chlorhydrate" → "Metformin" won't exact-match
             but "metformin" is a prefix of "metformine"  → accepted
    fuzzy  — difflib ratio >= 0.82 between INN and pipeline name

All rows are kept, including those with no pipeline match (pipeline_drug = "").
You can review and manually fix the no-match rows before deploying.
"""

import re
import csv
import difflib
import unicodedata
import pandas as pd
from pathlib import Path

ROOT         = Path("D:/23AIBox-DFinder")
ALG_CSV      = ROOT / "algerian_drugs.csv"
DRUG_ID_MAP  = ROOT / "DFinder-main/data/unified-DFI/id_maps/drug_id_map.csv"
OUT_CSV      = ROOT / "algerian_brand_map.csv"

FUZZY_THRESHOLD = 0.82


def normalize(s: str) -> str:
    """Lowercase, remove accents, strip salt/form suffixes, collapse whitespace."""
    s = str(s).strip().lower()
    # Remove accents (é→e, è→e, etc.)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    # Strip common salt/form suffixes that appear in Algerian INN but not pipeline
    for suffix in [
        " chlorhydrate", " hydrochloride", " sulfate", " sodium", " potassium",
        " calcium", " acetate", " phosphate", " fumarate", " maleate",
        " tartrate", " mesylate", " besylate", " succinate", " citrate",
        " monohydrate", " dihydrate", " anhydrous",
        " exprime en ", " experime en ",  # Algerian-specific notation
    ]:
        if suffix in s:
            s = s[:s.index(suffix)]
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def match_inn_to_pipeline(inn_norm: str, pipeline_norms: list[str],
                           pipeline_originals: list[str],
                           prefix4_index: dict) -> tuple[str, str]:
    """
    Try exact → prefix → fuzzy match.
    Returns (pipeline_drug_original_case, match_type) or ("", "none").
    Fuzzy is pre-filtered to candidates sharing the first 4 characters.
    """
    # 1. Exact match
    for norm, orig in zip(pipeline_norms, pipeline_originals):
        if inn_norm == norm:
            return orig, "exact"

    # 2. Prefix match — INN starts with the pipeline name (or vice versa)
    for norm, orig in zip(pipeline_norms, pipeline_originals):
        if inn_norm.startswith(norm) or norm.startswith(inn_norm):
            if abs(len(inn_norm) - len(norm)) <= 8:
                return orig, "prefix"

    # 3. Fuzzy match — only against candidates sharing first 4 chars
    prefix = inn_norm[:4]
    candidates = prefix4_index.get(prefix, [])
    best_ratio = 0.0
    best_orig  = ""
    for idx in candidates:
        ratio = difflib.SequenceMatcher(None, inn_norm, pipeline_norms[idx]).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_orig  = pipeline_originals[idx]
    if best_ratio >= FUZZY_THRESHOLD:
        return best_orig, f"fuzzy({best_ratio:.2f})"

    return "", "none"


def main():
    # ── Load Algerian registry ────────────────────────────────────────────────
    alg = pd.read_csv(ALG_CSV, skiprows=7, header=0,
                      encoding="latin-1", on_bad_lines="skip")
    inn_col   = [c for c in alg.columns if "INTERNATIONALE" in str(c)][0]
    brand_col = [c for c in alg.columns if "MARQUE"         in str(c)][0]

    alg = alg[[brand_col, inn_col]].dropna(subset=[brand_col, inn_col]).copy()
    alg.columns = ["brand_raw", "inn_raw"]
    alg["brand_raw"] = alg["brand_raw"].str.strip()
    alg["inn_raw"]   = alg["inn_raw"].str.strip()

    # Deduplicate by brand (keep any row — we just need brand→INN)
    alg = alg.drop_duplicates(subset=["brand_raw"])
    print(f"Algerian registry rows (unique brands): {len(alg)}")

    # ── Load pipeline drug names ──────────────────────────────────────────────
    drug_map          = pd.read_csv(DRUG_ID_MAP)
    pipeline_originals = drug_map["name"].dropna().str.strip().tolist()
    pipeline_norms     = [normalize(n) for n in pipeline_originals]
    print(f"Pipeline drugs: {len(pipeline_originals)}")

    # Build prefix-4 index for fast fuzzy pre-filtering
    from collections import defaultdict
    prefix4_index: dict = defaultdict(list)
    for idx, norm in enumerate(pipeline_norms):
        prefix4_index[norm[:4]].append(idx)

    # ── Map each brand → INN → pipeline ──────────────────────────────────────
    rows = []
    stats = {"exact": 0, "prefix": 0, "fuzzy": 0, "none": 0}

    for _, row in alg.iterrows():
        brand     = row["brand_raw"]
        inn_raw   = row["inn_raw"]
        inn_norm  = normalize(inn_raw)

        pipeline_drug, match_type = match_inn_to_pipeline(
            inn_norm, pipeline_norms, pipeline_originals, prefix4_index
        )

        mtype_key = match_type.split("(")[0]  # strip fuzzy ratio for counter
        stats[mtype_key] = stats.get(mtype_key, 0) + 1

        rows.append({
            "brand_name"    : brand,
            "inn_raw"       : inn_raw,
            "inn_normalized": inn_norm,
            "pipeline_drug" : pipeline_drug,
            "match_type"    : match_type,
        })

    # ── Write output ─────────────────────────────────────────────────────────
    out_df = pd.DataFrame(rows).sort_values("brand_name")
    out_df.to_csv(OUT_CSV, index=False, encoding="utf-8")

    # ── Report ───────────────────────────────────────────────────────────────
    matched   = out_df[out_df["pipeline_drug"] != ""]
    unmatched = out_df[out_df["pipeline_drug"] == ""]

    print(f"\n=== Build Report ===")
    print(f"Total brand entries   : {len(out_df)}")
    print(f"Matched to pipeline   : {len(matched)} ({100*len(matched)/len(out_df):.1f}%)")
    print(f"  - exact             : {stats['exact']}")
    print(f"  - prefix            : {stats['prefix']}")
    print(f"  - fuzzy             : {stats.get('fuzzy', 0)}")
    print(f"Unmatched (no pipeline): {len(unmatched)} ({100*len(unmatched)/len(out_df):.1f}%)")
    print(f"\nSaved → {OUT_CSV}")

    print(f"\n--- Sample matched rows ---")
    for _, r in matched.head(15).iterrows():
        print(f"  {r['brand_name']:20s} → {r['inn_raw'][:35]:35s} → {r['pipeline_drug']} [{r['match_type']}]")

    print(f"\n--- Sample unmatched rows (INN not in pipeline) ---")
    for _, r in unmatched.head(10).iterrows():
        print(f"  {r['brand_name']:20s} → {r['inn_raw'][:40]}")


if __name__ == "__main__":
    main()
