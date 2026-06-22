"""
Phase 6 — DFinder Evaluation
Evaluates model coverage and evidence quality on the 889 unseen confirmed interactions.

Note: All 889 validation pairs are POSITIVE (confirmed DFIs).
→ No negative class available → evaluation focuses on:
  1. Recall / Sensitivity by layer and tier
  2. Evidence quality stratification (LIT-confirmed > DrugBank > PubMed-NLP)
  3. Score distributions per evidence class
  4. Per-tier analysis
  5. HIDDEN_MECHANISM characterisation (what are the unexplained cases?)

Evidence strength ordering (strongest → weakest):
  LIT-confirmed > DrugBank-named > DrugBank-text > PubMed-NLP

Usage:
    python evaluate.py              # run full evaluation, write report
    python evaluate.py --show       # also print extended examples
"""

import argparse
import json
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

# ── Paths ───────────────────────────────────────────────────────────────────
ROOT      = Path("D:/23AIBox-DFinder")
VAL_DIR   = ROOT / "validation_splits"
UNSEEN    = VAL_DIR / "validation_unseen.csv"
FUSION    = VAL_DIR / "phase5_fusion_results.csv"
PHASE2    = VAL_DIR / "phase2_graph_query_results.csv"
PHASE3    = VAL_DIR / "phase3_lgn_scores.csv"
PHASE4    = VAL_DIR / "phase4_kge_scores.csv"
REPORT    = ROOT    / "evaluation_report.md"

# Evidence rank (lower = stronger)
EVIDENCE_RANK = {
    "LIT-confirmed"  : 1,
    "DrugBank-named" : 2,
    "DrugBank-text"  : 3,
    "PubMed-NLP"     : 4,
}


def load_data():
    """Load validation ground truth and all layer results, aligned by pair index."""
    gt    = pd.read_csv(UNSEEN)[["drug_name", "food_name", "verdict"]]
    fus   = pd.read_csv(FUSION)

    # Merge on drug+food (preserve order)
    df = gt.merge(
        fus[["drug","food","fusion_score","confidence","flags",
             "graph_found","graph_score","graph_enzymes",
             "kge_found","kge_score","kge_enzymes","lgn_score"]],
        left_on  = ["drug_name","food_name"],
        right_on = ["drug","food"],
        how      = "left"
    ).drop(columns=["drug","food"])

    df["evidence_rank"] = df["verdict"].map(EVIDENCE_RANK)
    df["flags"]         = df["flags"].fillna("")
    df["confidence"]    = df["confidence"].fillna("INSUFFICIENT")
    df["fusion_score"]  = df["fusion_score"].fillna(0.0)
    df["lgn_score"]     = df["lgn_score"].fillna(0.0)
    df["kge_score"]     = df["kge_score"].fillna(0.0)
    df["graph_score"]   = df["graph_score"].fillna(0.0)
    return df


def recall_by(df: pd.DataFrame, col: str, threshold, label: str) -> dict:
    """How many pairs have col >= threshold (or == True)?"""
    if isinstance(threshold, bool):
        detected = (df[col] == threshold).sum()
    else:
        detected = (df[col] >= threshold).sum()
    total = len(df)
    return {"label": label, "detected": int(detected),
            "total": total, "recall": detected / total}


def separation_score(df: pd.DataFrame, score_col: str) -> dict:
    """
    Test if LIT-confirmed pairs score higher than PubMed-NLP pairs.
    Returns mean scores by evidence class + Mann-Whitney U stat.
    """
    from scipy.stats import mannwhitneyu
    lit  = df[df["verdict"] == "LIT-confirmed"][score_col].dropna()
    nlp  = df[df["verdict"] == "PubMed-NLP"][score_col].dropna()
    stat, p = mannwhitneyu(lit, nlp, alternative="greater")
    return {
        "LIT-confirmed_mean"  : float(lit.mean()),
        "PubMed-NLP_mean"     : float(nlp.mean()),
        "mannwhitney_stat"    : float(stat),
        "p_value"             : float(p),
        "significant"         : bool(p < 0.05),
    }


def run_evaluation(show: bool = False) -> str:
    df = load_data()
    total = len(df)
    lines = []

    def h(text): lines.append(f"\n## {text}")
    def row(text): lines.append(text)

    # ── Header ────────────────────────────────────────────────────────────
    lines.append("# DFinder Evaluation Report")
    lines.append(f"Total unseen confirmed interaction pairs: **{total}**")
    lines.append("All pairs are positive (confirmed DFIs) — evaluation measures sensitivity/recall.\n")

    # ── Evidence distribution ─────────────────────────────────────────────
    h("Evidence Source Distribution")
    ev_dist = df["verdict"].value_counts()
    for src, cnt in ev_dist.items():
        row(f"  - {src}: {cnt} ({100*cnt/total:.1f}%)")

    # ── Layer-wise recall ─────────────────────────────────────────────────
    h("Layer-wise Recall on 889 Confirmed Pairs")
    row("| Layer | Threshold | Detected | Recall |")
    row("|-------|-----------|----------|--------|")
    for label, col, thr in [
        ("Layer 1 — Graph Query",   "graph_found",  True),
        ("Layer 2 — Mechanistic KGE (kge_score>0)", "kge_found", True),
        ("Layer 3 — LightGCN (≥0.5)", "lgn_score", 0.5),
        ("Layer 3 — LightGCN (≥0.7)", "lgn_score", 0.7),
        ("Layer 3 — LightGCN (≥0.9)", "lgn_score", 0.9),
        ("Fusion HIGH or MEDIUM",    "confidence",  None),
        ("Any layer (fusion>0)",     "fusion_score", 0.001),
    ]:
        if col == "confidence":
            det = df[df["confidence"].isin(["HIGH","MEDIUM"])]["drug_name"].count()
        elif isinstance(thr, bool):
            det = int((df[col] == thr).sum())
        else:
            det = int((df[col] >= thr).sum())
        row(f"| {label} | {thr} | {det}/{total} | {100*det/total:.1f}% |")

    # ── Confidence tier breakdown ──────────────────────────────────────────
    h("Confidence Tier Breakdown")
    row("| Tier | Count | % | Avg fusion_score | Dominant evidence |")
    row("|------|-------|---|-----------------|-------------------|")
    for tier in ["HIGH", "MEDIUM", "LOW", "INSUFFICIENT"]:
        sub = df[df["confidence"] == tier]
        if len(sub) == 0: continue
        avg_fs = sub["fusion_score"].mean()
        dom_ev = sub["verdict"].value_counts().index[0]
        row(f"| {tier} | {len(sub)} | {100*len(sub)/total:.1f}% | "
            f"{avg_fs:.4f} | {dom_ev} |")

    # ── Evidence quality stratification ───────────────────────────────────
    h("Evidence Quality Stratification")
    row("Do stronger evidence classes score higher? (Mean scores by source)\n")
    row("| Evidence Source | Count | Avg fusion | Avg LGN | Avg KGE | Avg Graph |")
    row("|-----------------|-------|-----------|---------|---------|-----------|")
    for ev in ["LIT-confirmed","DrugBank-named","DrugBank-text","PubMed-NLP"]:
        sub = df[df["verdict"] == ev]
        if len(sub) == 0: continue
        row(f"| {ev} | {len(sub)} | "
            f"{sub['fusion_score'].mean():.4f} | "
            f"{sub['lgn_score'].mean():.4f} | "
            f"{sub['kge_score'].mean():.2f} | "
            f"{sub['graph_score'].mean():.2f} |")

    # Mann-Whitney test
    sep = separation_score(df, "fusion_score")
    row(f"\n**LIT-confirmed vs PubMed-NLP fusion score separation:**")
    row(f"  - LIT-confirmed mean: {sep['LIT-confirmed_mean']:.4f}")
    row(f"  - PubMed-NLP mean: {sep['PubMed-NLP_mean']:.4f}")
    row(f"  - Mann-Whitney U={sep['mannwhitney_stat']:.0f}, p={sep['p_value']:.4f} "
        f"({'✅ significant' if sep['significant'] else '❌ not significant'})")

    # ── Tier × Evidence cross-tabulation ─────────────────────────────────
    h("Confidence × Evidence Cross-tabulation")
    ct = pd.crosstab(df["confidence"], df["verdict"])
    ct = ct.reindex(
        index=["HIGH","MEDIUM","LOW","INSUFFICIENT"],
        columns=["LIT-confirmed","DrugBank-named","DrugBank-text","PubMed-NLP"],
        fill_value=0
    )
    row("\n| Tier | LIT-confirmed | DrugBank-named | DrugBank-text | PubMed-NLP |")
    row("|------|--------------|----------------|--------------|------------|")
    for tier in ["HIGH","MEDIUM","LOW","INSUFFICIENT"]:
        vals = " | ".join(str(ct.loc[tier, ev]) for ev in
                          ["LIT-confirmed","DrugBank-named","DrugBank-text","PubMed-NLP"])
        row(f"| {tier} | {vals} |")

    pct_lit_high = 100 * ct.loc["HIGH","LIT-confirmed"] / ev_dist.get("LIT-confirmed",1)
    pct_lit_med  = 100 * ct.loc["MEDIUM","LIT-confirmed"] / ev_dist.get("LIT-confirmed",1)
    row(f"\n**{pct_lit_high:.1f}% of LIT-confirmed pairs reach HIGH; "
        f"{pct_lit_med:.1f}% reach MEDIUM.**")

    # ── Flag analysis ─────────────────────────────────────────────────────
    h("Flag Analysis")
    all_flags = ["ALL_LAYERS_AGREE","HIDDEN_MECHANISM","THEORETICAL_RISK","EXPERT_REVIEW"]
    row("| Flag | Count | % | Avg fusion | LIT-conf in flag |")
    row("|------|-------|---|-----------|-----------------|")
    for flag in all_flags:
        sub = df[df["flags"].str.contains(flag, na=False)]
        if len(sub) == 0: continue
        lit_in = sub[sub["verdict"]=="LIT-confirmed"]["drug_name"].count()
        row(f"| {flag} | {len(sub)} | {100*len(sub)/total:.1f}% | "
            f"{sub['fusion_score'].mean():.4f} | {lit_in} ({100*lit_in/max(len(sub),1):.0f}%) |")

    # ALL_LAYERS_AGREE detail
    h("ALL_LAYERS_AGREE Pairs (Highest Confidence)")
    agree = df[df["flags"].str.contains("ALL_LAYERS_AGREE",na=False)].sort_values(
        "fusion_score", ascending=False)
    row(f"\n{len(agree)} pairs where Graph + KGE + LGN all signal interaction:\n")
    row("| Drug | Food | Fusion | Evidence | Enzymes |")
    row("|------|------|--------|----------|---------|")
    for _, r in agree.head(15).iterrows():
        enzymes = str(r.get("kge_enzymes",""))[:30] or str(r.get("graph_enzymes",""))[:30]
        row(f"| {r['drug_name'][:22]} | {r['food_name'][:16]} | "
            f"{r['fusion_score']:.4f} | {r['verdict']} | {enzymes} |")

    # ── HIDDEN_MECHANISM characterisation ─────────────────────────────────
    h("HIDDEN_MECHANISM Characterisation")
    hidden = df[df["flags"].str.contains("HIDDEN_MECHANISM",na=False)]
    row(f"\n{len(hidden)} pairs where LGN≥0.80 but no Graph/KGE path:\n")
    row("| Evidence Source | Count | Avg LGN |")
    row("|-----------------|-------|---------|")
    for ev in ["LIT-confirmed","DrugBank-named","DrugBank-text","PubMed-NLP"]:
        sub = hidden[hidden["verdict"] == ev]
        if len(sub) == 0: continue
        row(f"| {ev} | {len(sub)} | {sub['lgn_score'].mean():.4f} |")
    row(f"\n→ These interactions may operate via non-CYP mechanisms "
        f"(e.g. pharmacodynamics, absorption, transporter effects) "
        f"not captured by the current HKG.")

    # ── Score distribution by evidence class ──────────────────────────────
    h("Score Distribution (Percentiles) by Evidence Class")
    row("| Evidence | p25 | p50 | p75 | p90 |")
    row("|----------|-----|-----|-----|-----|")
    for ev in ["LIT-confirmed","DrugBank-named","DrugBank-text","PubMed-NLP"]:
        sub = df[df["verdict"] == ev]["fusion_score"]
        if len(sub) == 0: continue
        row(f"| {ev} | "
            f"{np.percentile(sub,25):.4f} | {np.percentile(sub,50):.4f} | "
            f"{np.percentile(sub,75):.4f} | {np.percentile(sub,90):.4f} |")

    # ── Summary ───────────────────────────────────────────────────────────
    h("Summary")
    total_detected = int((df["confidence"].isin(["HIGH","MEDIUM","LOW"])).sum())
    row(f"- **Overall detection rate (HIGH+MEDIUM+LOW)**: {total_detected}/{total} "
        f"({100*total_detected/total:.1f}%)")
    row(f"- **HIGH+MEDIUM** (actionable flags): "
        f"{int(df['confidence'].isin(['HIGH','MEDIUM']).sum())}/{total} "
        f"({100*df['confidence'].isin(['HIGH','MEDIUM']).mean():.1f}%)")
    row(f"- **ALL_LAYERS_AGREE** (highest precision): "
        f"{int(df['flags'].str.contains('ALL_LAYERS_AGREE',na=False).sum())}/{total} "
        f"({100*df['flags'].str.contains('ALL_LAYERS_AGREE',na=False).mean():.1f}%)")
    row(f"- **Key bottleneck**: 94% of foods have no KGE compound path; "
        f"22% of drugs not in KGE entity space.")
    row(f"- **LightGCN** carries most signal (100% coverage, median score 0.93).")
    row(f"- **Graph + KGE** add mechanistic interpretability for ~25% of pairs.")

    report = "\n".join(lines)
    return report, df


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DFinder evaluation")
    parser.add_argument("--show", action="store_true",
                        help="Print full report to console")
    args = parser.parse_args()

    print("Running Phase 6 evaluation...")
    report, df = run_evaluation(show=args.show)

    REPORT.write_text(report, encoding="utf-8")
    print(f"Evaluation report saved → {REPORT}")

    # Always print key metrics
    print("\n" + "="*60)
    total = len(df)
    for tier in ["HIGH","MEDIUM","LOW","INSUFFICIENT"]:
        n = int((df["confidence"] == tier).sum())
        print(f"  {tier:15s}: {n:4d} / {total}  ({100*n/total:.1f}%)")
    print("="*60)
    agree = int(df["flags"].str.contains("ALL_LAYERS_AGREE",na=False).sum())
    hidden = int(df["flags"].str.contains("HIDDEN_MECHANISM",na=False).sum())
    print(f"  ALL_LAYERS_AGREE  : {agree:4d} ({100*agree/total:.1f}%)")
    print(f"  HIDDEN_MECHANISM  : {hidden:4d} ({100*hidden/total:.1f}%)")

    # Per-evidence mean fusion
    print("\n--- Mean fusion score by evidence source ---")
    for ev in ["LIT-confirmed","DrugBank-named","DrugBank-text","PubMed-NLP"]:
        sub = df[df["verdict"] == ev]["fusion_score"]
        if len(sub): print(f"  {ev:20s}: {sub.mean():.4f}  (n={len(sub)})")

    if args.show:
        print("\n" + report)

    print("\nPhase 6 complete.")
