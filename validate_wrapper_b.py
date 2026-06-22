"""
Validate Wrapper B decomposition quality and hallucination risk.

Outputs:
  ablation_results/wrapper_b_runtime_vs_manual_food_level.csv
  ablation_results/wrapper_b_runtime_vs_manual_compound_level.csv
  ablation_results/wrapper_b_runtime_validation_summary.txt

This script uses the live llm_decompose() pipeline (with NA seed + FooDB/HKG gating)
so results reflect real runtime behavior.
"""

import json
import re
from pathlib import Path

import pandas as pd

from llm_decompose import llm_decompose

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "ablation_results"
OUT.mkdir(exist_ok=True)

MANUAL_PATH = ROOT / "data" / "na_dish_compounds.json"
FOODB_PATH = ROOT / "Compound.csv"
HKG_PATH = ROOT / "data" / "processed_hkg" / "hkg_food_compound_edges.csv"


def norm(s: str) -> str:
    s = str(s).lower().strip()
    s = re.sub(r"\([^)]*\)", "", s)
    s = s.replace("/", " ").replace("+", " ").replace("_", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def load_vocab() -> tuple[set[str], set[str]]:
    foodb = pd.read_csv(FOODB_PATH, usecols=["name", "moldb_iupac"], low_memory=False)
    foodb_vocab = set(foodb["name"].dropna().map(norm)).union(
        set(foodb["moldb_iupac"].dropna().map(norm))
    )

    hkg = pd.read_csv(HKG_PATH, usecols=["tail"])
    hkg_vocab = set(hkg["tail"].dropna().map(norm))
    return foodb_vocab, hkg_vocab


def main() -> None:
    with open(MANUAL_PATH, "r", encoding="utf-8") as f:
        manual = json.load(f)

    foodb_vocab, hkg_vocab = load_vocab()

    food_rows = []
    compound_rows = []

    for dish in sorted(manual.keys()):
        manual_set = {norm(x) for x in manual.get(dish, []) if str(x).strip()}
        runtime_list = llm_decompose(dish, verbose=False)
        runtime_set = {norm(x) for x in runtime_list if str(x).strip()}

        overlap = manual_set & runtime_set
        manual_only = manual_set - runtime_set
        runtime_only = runtime_set - manual_set

        food_rows.append(
            {
                "dish": dish,
                "manual_n": len(manual_set),
                "runtime_n": len(runtime_set),
                "overlap_n": len(overlap),
                "manual_only_n": len(manual_only),
                "runtime_only_n": len(runtime_only),
                "manual_compounds": " | ".join(sorted(manual_set)),
                "runtime_compounds": " | ".join(sorted(runtime_set)),
                "overlap_compounds": " | ".join(sorted(overlap)),
            }
        )

        for c in sorted(runtime_set):
            compound_rows.append(
                {
                    "dish": dish,
                    "source": "runtime",
                    "compound": c,
                    "in_foodb": c in foodb_vocab,
                    "in_hkg": c in hkg_vocab,
                    "in_manual_for_dish": c in manual_set,
                }
            )
        for c in sorted(manual_set):
            compound_rows.append(
                {
                    "dish": dish,
                    "source": "manual",
                    "compound": c,
                    "in_foodb": c in foodb_vocab,
                    "in_hkg": c in hkg_vocab,
                    "in_runtime_for_dish": c in runtime_set,
                }
            )

    food_df = pd.DataFrame(food_rows)
    cmp_df = pd.DataFrame(compound_rows)

    food_df.to_csv(OUT / "wrapper_b_runtime_vs_manual_food_level.csv", index=False)
    cmp_df.to_csv(OUT / "wrapper_b_runtime_vs_manual_compound_level.csv", index=False)

    # Aggregate metrics
    manual_total = int(food_df["manual_n"].sum())
    runtime_total = int(food_df["runtime_n"].sum())
    overlap_total = int(food_df["overlap_n"].sum())

    manual_rows = cmp_df[cmp_df["source"] == "manual"]
    runtime_rows = cmp_df[cmp_df["source"] == "runtime"]

    runtime_foodb = int(runtime_rows["in_foodb"].sum())
    runtime_hkg = int(runtime_rows["in_hkg"].sum())
    runtime_unverified = int((~runtime_rows["in_foodb"] & ~runtime_rows["in_hkg"]).sum())

    foods_any_overlap = int((food_df["overlap_n"] > 0).sum())
    foods_exact = int(((food_df["manual_only_n"] == 0) & (food_df["runtime_only_n"] == 0)).sum())

    summary = f"""
WRAPPER B RUNTIME VALIDATION
============================
Manual dish source: {MANUAL_PATH}
Runtime decomposer: llm_decompose() with NA seed + FooDB/HKG gate

DISH-LEVEL AGREEMENT
- Dishes evaluated: {len(food_df)}
- Dishes with any overlap: {foods_any_overlap}/{len(food_df)} ({(foods_any_overlap/len(food_df)*100):.1f}%)
- Exact dish-level matches: {foods_exact}/{len(food_df)} ({(foods_exact/len(food_df)*100):.1f}%)

COMPOUND-LEVEL AGREEMENT
- Manual compounds total: {manual_total}
- Runtime compounds total: {runtime_total}
- Overlap total: {overlap_total}
- Recall vs manual: {(overlap_total/manual_total*100 if manual_total else 0):.1f}%
- Precision vs manual: {(overlap_total/runtime_total*100 if runtime_total else 0):.1f}%

HALLUCINATION/VERIFICATION CHECK (runtime compounds)
- In FooDB: {runtime_foodb}/{len(runtime_rows)} ({(runtime_foodb/len(runtime_rows)*100 if len(runtime_rows) else 0):.1f}%)
- In HKG: {runtime_hkg}/{len(runtime_rows)} ({(runtime_hkg/len(runtime_rows)*100 if len(runtime_rows) else 0):.1f}%)
- In neither FooDB nor HKG (suspected hallucinations): {runtime_unverified}/{len(runtime_rows)} ({(runtime_unverified/len(runtime_rows)*100 if len(runtime_rows) else 0):.1f}%)

FILES WRITTEN
- {OUT / 'wrapper_b_runtime_vs_manual_food_level.csv'}
- {OUT / 'wrapper_b_runtime_vs_manual_compound_level.csv'}
""".strip()

    (OUT / "wrapper_b_runtime_validation_summary.txt").write_text(summary + "\n", encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
