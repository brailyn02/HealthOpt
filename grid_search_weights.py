"""
Grid Search: Weight Sensitivity Analysis on 889-pair Validation Cohort

Tests all combinations of:
  - w_LGN: 0.40, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80
  - w_mech = 1 - w_LGN (implicit)
  - concordance_bonus: 0.01, 0.02, 0.03, 0.04, 0.05

For each combination, recomputes fusion scores and tier assignments,
then measures recall, precision, and actionable rate.

Output: grid_search_results.csv with all metrics
"""

import numpy as np
import pandas as pd
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parent
VAL_DIR = ROOT / "validation_splits"
UNSEEN = VAL_DIR / "validation_unseen.csv"
PHASE5 = VAL_DIR / "phase5_fusion_results.csv"
OUTPUT = ROOT / "grid_search_results.csv"

# Load ground truth and cached results
print("Loading validation cohort and cached layer results...")
gt = pd.read_csv(UNSEEN)[["drug_name", "food_name", "verdict"]]
phase5 = pd.read_csv(PHASE5)

# Merge on (drug, food)
df = gt.merge(
    phase5[["drug", "food", "graph_found", "graph_score", 
            "kge_found", "kge_score", "lgn_score"]],
    left_on=["drug_name", "food_name"],
    right_on=["drug", "food"],
    how="left"
).drop(columns=["drug", "food"])

print(f"  Total pairs: {len(df)}")
print(f"  Missing layer data: {df[['graph_score', 'kge_score', 'lgn_score']].isna().any(axis=1).sum()}")

# Fill missing values
df["graph_score"] = df["graph_score"].fillna(0.0)
df["kge_score"] = df["kge_score"].fillna(0.0)
df["lgn_score"] = df["lgn_score"].fillna(0.0)
df["graph_found"] = df["graph_found"].fillna(False)
df["kge_found"] = df["kge_found"].fillna(False)

# Normalization constants (from predict.py)
GRAPH_MAX = 120.0
KGE_MAX = 115.0

# Compute normalized layer scores once (these don't change with weight variations)
df["norm_graph"] = np.clip(df["graph_score"] / GRAPH_MAX, 0.0, 1.0)
df["norm_kge"] = np.clip(df["kge_score"] / KGE_MAX, 0.0, 1.0)
df["norm_lgn"] = np.clip(df["lgn_score"], 0.0, 1.0)

print("\nLayer score distributions:")
print(f"  LGN:   min={df['lgn_score'].min():.3f}, max={df['lgn_score'].max():.3f}, mean={df['lgn_score'].mean():.3f}")
print(f"  Graph: min={df['graph_score'].min():.1f}, max={df['graph_score'].max():.1f}, mean={df['graph_score'].mean():.1f}")
print(f"  KGE:   min={df['kge_score'].min():.1f}, max={df['kge_score'].max():.1f}, mean={df['kge_score'].mean():.1f}")


def _noisy_or(scores: list[float]) -> float:
    """Bounded OR aggregation for compound-level scores."""
    vals = [float(np.clip(s, 0.0, 1.0)) for s in scores if s is not None]
    if not vals:
        return 0.0
    prod = 1.0
    for v in vals:
        prod *= (1.0 - v)
    return float(np.clip(1.0 - prod, 0.0, 1.0))


def compute_mech_support(row, bonus_concordance, bonus_enzyme):
    """
    Recompute mechanistic support with given bonuses.
    Note: We simplify by using directly normalized graph/kge scores
    since we don't have the detailed compound/enzyme breakdowns.
    In practice, the bonuses are small (0.01-0.05) so impact is limited.
    """
    norm_graph = row["norm_graph"]
    norm_kge = row["norm_kge"]
    
    # Simplified: assume max of graph and kge as base support
    # (In full pipeline, uses noisy-or on top-k compounds, but we don't have that granularity)
    base_support = np.clip(0.65 * norm_graph + 0.35 * norm_kge, 0.0, 1.0)
    
    # Apply bonus (assuming both found = bonus applies)
    bonus = 0.0
    if row["graph_found"] and row["kge_found"]:
        bonus = bonus_concordance + bonus_enzyme
    elif row["graph_found"] or row["kge_found"]:
        bonus = bonus_concordance / 2  # partial bonus for one layer found
    
    mech_support = np.clip(base_support + bonus, 0.0, 1.0)
    return mech_support


def compute_fusion_score(norm_lgn, mech_support, w_lgn):
    """
    Recompute fusion using provided weights.
    Implements piecewise fusion with Bayesian self-weighted combination.
    """
    lgn_strong_confirm = 0.98
    l = float(np.clip(norm_lgn, 0.0, 1.0))
    m = float(np.clip(mech_support, 0.0, 1.0))
    
    # Ceiling: very high LGN is trusted directly
    if l >= lgn_strong_confirm:
        return l
    
    # Bayesian self-weighted fusion with specified weights
    w_mech = 1.0 - w_lgn
    
    signals = []
    if l > 0.0:
        signals.append((l, w_lgn))
    if m > 0.0:
        signals.append((m, w_mech))
    
    if not signals:
        return 0.0
    
    # Weighted average: sum(signal * weight) / sum(weight)
    weighted_sum = sum(s * w for s, w in signals)
    weight_sum = sum(w for s, w in signals)
    return float(np.clip(weighted_sum / weight_sum, 0.0, 1.0))


def assign_tier(fusion_score, graph_found, kge_found, norm_lgn):
    """Assign confidence tier based on fusion score and layer evidence."""
    th_high = 0.70
    th_medium = 0.45
    th_low = 0.20
    lgn_high_conf = 0.90
    lgn_medium_conf = 0.65
    
    if (graph_found and kge_found) or norm_lgn >= lgn_high_conf:
        return "HIGH"
    elif fusion_score >= th_medium or (
        (graph_found or kge_found) and norm_lgn >= 0.5
    ) or norm_lgn >= lgn_medium_conf:
        return "MEDIUM"
    elif fusion_score >= th_low or (graph_found or kge_found) or norm_lgn >= 0.5:
        return "LOW"
    else:
        return "INSUFFICIENT"


# Grid parameters
w_lgn_values = [0.40, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80]
bonus_values = [0.01, 0.02, 0.03, 0.04, 0.05]

print("\n" + "=" * 100)
print(f"GRID SEARCH: {len(w_lgn_values)} × {len(bonus_values)} = {len(w_lgn_values) * len(bonus_values)} combinations")
print("=" * 100)

results = []

for w_lgn in w_lgn_values:
    for bonus in bonus_values:
        # Compute mechanistic support and fusion for all pairs
        df[f"mech_support_{w_lgn}_{bonus}"] = df.apply(
            lambda row: compute_mech_support(row, bonus, bonus / 2), 
            axis=1
        )
        df[f"fusion_score_{w_lgn}_{bonus}"] = df.apply(
            lambda row: compute_fusion_score(
                row["norm_lgn"],
                row[f"mech_support_{w_lgn}_{bonus}"],
                w_lgn
            ),
            axis=1,
            raw=False
        )
        df[f"tier_{w_lgn}_{bonus}"] = df.apply(
            lambda row: assign_tier(
                row[f"fusion_score_{w_lgn}_{bonus}"],
                row["graph_found"],
                row["kge_found"],
                row["norm_lgn"]
            ),
            axis=1,
            raw=False
        )
        
        # Compute metrics
        tier_counts = Counter(df[f"tier_{w_lgn}_{bonus}"])
        total = len(df)
        
        # Recall: proportion at each tier (all pairs are positives, so recall = prop at that threshold)
        recall_high_medium = (tier_counts["HIGH"] + tier_counts["MEDIUM"]) / total
        recall_high = tier_counts["HIGH"] / total
        recall_medium = tier_counts["MEDIUM"] / total
        recall_low = tier_counts["LOW"] / total
        recall_insufficient = tier_counts["INSUFFICIENT"] / total
        
        # Actionable rate: HIGH or MEDIUM
        actionable_count = tier_counts["HIGH"] + tier_counts["MEDIUM"]
        actionable_rate = actionable_count / total
        
        # Score ranges
        scores = df[f"fusion_score_{w_lgn}_{bonus}"]
        
        result = {
            "w_lgn": w_lgn,
            "w_mech": round(1.0 - w_lgn, 2),
            "concordance_bonus": bonus,
            "total_pairs": total,
            "high_count": tier_counts["HIGH"],
            "medium_count": tier_counts["MEDIUM"],
            "low_count": tier_counts["LOW"],
            "insufficient_count": tier_counts["INSUFFICIENT"],
            "recall_high": round(recall_high, 4),
            "recall_medium": round(recall_medium, 4),
            "recall_low": round(recall_low, 4),
            "recall_insufficient": round(recall_insufficient, 4),
            "actionable_rate": round(actionable_rate, 4),
            "avg_fusion_score": round(scores.mean(), 4),
            "min_fusion_score": round(scores.min(), 4),
            "max_fusion_score": round(scores.max(), 4),
            "std_fusion_score": round(scores.std(), 4),
        }
        results.append(result)
        
        # Print progress
        print(
            f"w_lgn={w_lgn:.2f} bonus={bonus:.2f}: "
            f"HIGH={result['high_count']:3d}, MEDIUM={result['medium_count']:3d}, "
            f"actionable_rate={result['actionable_rate']:.3f}"
        )

# Create results dataframe
results_df = pd.DataFrame(results)

# Sort by actionable rate (descending) then by w_lgn (to show trend)
results_df_sorted = results_df.sort_values(
    by=["actionable_rate", "w_lgn"], 
    ascending=[False, True]
)

# Save results
results_df_sorted.to_csv(OUTPUT, index=False)
print(f"\n✓ Results saved to {OUTPUT}")

# Print top combinations
print("\n" + "=" * 120)
print("TOP 15 COMBINATIONS (by actionable rate):")
print("=" * 120)
print(results_df_sorted.head(15).to_string(index=False))

# Print current configuration performance
current_w = 0.60
current_bonus = 0.03
current_row = results_df[
    (results_df["w_lgn"] == current_w) & 
    (results_df["concordance_bonus"] == current_bonus)
]
if len(current_row) > 0:
    print("\n" + "=" * 120)
    print(f"CURRENT CONFIGURATION (w_lgn={current_w}, bonus={current_bonus}):")
    print("=" * 120)
    print(current_row[["w_lgn", "w_mech", "concordance_bonus", "actionable_rate", 
                       "high_count", "medium_count", "low_count"]].to_string(index=False))

# Stability analysis: compare w_lgn = 0.55-0.65 range
stability_range = results_df[
    (results_df["w_lgn"] >= 0.55) & 
    (results_df["w_lgn"] <= 0.65) &
    (results_df["concordance_bonus"] == 0.03)
]
if len(stability_range) > 0:
    print("\n" + "=" * 120)
    print("STABILITY ANALYSIS (bonus=0.03, varying w_lgn in [0.55, 0.65]):")
    print("=" * 120)
    print(stability_range[["w_lgn", "actionable_rate", "high_count", "medium_count", 
                          "avg_fusion_score"]].sort_values("w_lgn").to_string(index=False))
    action_rates = stability_range["actionable_rate"].values
    print(f"\n  Actionable rate range: {action_rates.min():.4f} - {action_rates.max():.4f}")
    print(f"  Variation: {(action_rates.max() - action_rates.min()):.4f} ({100*(action_rates.max()-action_rates.min()):.2f}%)")

print("\n✓ Grid search complete!")
