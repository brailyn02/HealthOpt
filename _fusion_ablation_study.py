"""
Ablation study comparing different fusion strategies for combining layer outputs.

Compares:
1. Current self-weighted Bayesian fusion (s * w * s / (w * s))
2. Linear weighted average (w1 * s1 + w2 * s2)
3. Soft-voting (softmax-weighted average)
4. Max-pooling (max(s1, s2))
5. Attention mechanism (learnable weights)

Goal: Justify the chosen fusion strategy over simpler alternatives.
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VAL_DIR = ROOT / "validation_splits"
UNSEEN = VAL_DIR / "layer_scores_by_pair_norm.csv"  # Use pre-computed normalized layer scores
OUTPUT = ROOT / "ablation_results" / "fusion_ablation_results.csv"
OUTPUT.parent.mkdir(exist_ok=True)

# Load validation data with layer scores
print("Loading validation data with layer scores...")
df = pd.read_csv(UNSEEN)
print(f"Loaded {len(df)} validation pairs")
print(f"Columns: {df.columns.tolist()}")

# Constants from predict.py
LGN_STRONG_CONFIRM = 0.98
TH_MEDIUM = 0.45
TH_LOW = 0.20
LGN_HIGH_CONF_TH = 0.90
LGN_MEDIUM_CONF_TH = 0.65

def assign_tier(fusion_score, mech_found, norm_lgn):
    """Thesis tier logic."""
    f = float(fusion_score)
    if (mech_found and norm_lgn >= 0.5) or norm_lgn >= LGN_HIGH_CONF_TH:
        return "HIGH"
    elif f >= TH_MEDIUM or (mech_found and norm_lgn >= 0.5) or norm_lgn >= LGN_MEDIUM_CONF_TH:
        return "MEDIUM"
    elif f >= TH_LOW or mech_found or norm_lgn >= 0.5:
        return "LOW"
    else:
        return "INSUFFICIENT"

def compute_metrics(tier_series, config_name):
    """Compute recall and actionable rate for a tier series."""
    total = len(tier_series)
    tier_counts = tier_series.value_counts()
    
    high = tier_counts.get("HIGH", 0)
    medium = tier_counts.get("MEDIUM", 0)
    low = tier_counts.get("LOW", 0)
    insufficient = tier_counts.get("INSUFFICIENT", 0)
    
    actionable = high + medium
    actionable_rate = actionable / total if total > 0 else 0
    
    return {
        "config": config_name,
        "total": total,
        "high": high,
        "medium": medium,
        "low": low,
        "insufficient": insufficient,
        "actionable_rate": actionable_rate,
    }

# Fusion methods
def fusion_current(norm_lgn, mech_support):
    """Current self-weighted Bayesian fusion (s * w * s / (w * s))."""
    l = max(0.0, min(float(norm_lgn), 1.0))
    m = max(0.0, min(float(mech_support), 1.0))
    if l >= LGN_STRONG_CONFIRM:
        return l
    signals = []
    if l > 0.0:
        signals.append((l, 0.70))
    if m > 0.0:
        signals.append((m, 0.30))
    if not signals:
        return 0.0
    weighted_sum = sum(s * w * s for s, w in signals)
    weight_sum = sum(w * s for s, w in signals)
    return max(0.0, min(weighted_sum / weight_sum, 1.0)) if weight_sum > 0 else 0.0

def fusion_linear(norm_lgn, mech_support, w_lgn=0.70, w_mech=0.30):
    """Simple linear weighted average."""
    l = max(0.0, min(float(norm_lgn), 1.0))
    m = max(0.0, min(float(mech_support), 1.0))
    return w_lgn * l + w_mech * m

def fusion_soft_voting(norm_lgn, mech_support):
    """Softmax-weighted average (soft-voting)."""
    l = max(0.0, min(float(norm_lgn), 1.0))
    m = max(0.0, min(float(mech_support), 1.0))
    # Add small epsilon to avoid division by zero
    eps = 1e-8
    scores = np.array([l, m]) + eps
    weights = np.exp(scores) / np.sum(np.exp(scores))
    return weights[0] * l + weights[1] * m

def fusion_max_pooling(norm_lgn, mech_support):
    """Max-pooling (take the maximum signal)."""
    l = max(0.0, min(float(norm_lgn), 1.0))
    m = max(0.0, min(float(mech_support), 1.0))
    return max(l, m)

def fusion_attention(norm_lgn, mech_support):
    """Simple attention mechanism (signal-strength-weighted)."""
    l = max(0.0, min(float(norm_lgn), 1.0))
    m = max(0.0, min(float(mech_support), 1.0))
    # Attention weights based on signal strength
    total_strength = l + m + 1e-8
    w_lgn = l / total_strength
    w_mech = m / total_strength
    return w_lgn * l + w_mech * m

# Run ablation study
print("\n" + "=" * 80)
print("FUSION ABLATION STUDY")
print("=" * 80)

results = []

# Config 1: Current self-weighted Bayesian fusion
df["fusion_current"] = df.apply(
    lambda r: fusion_current(r["norm_lgn"], r["mech_support_approx"]), axis=1
)
df["tier_current"] = df.apply(
    lambda r: assign_tier(r["fusion_current"], r["graph_found"] or r["kge_found"], r["norm_lgn"]), axis=1
)
results.append(compute_metrics(df["tier_current"], "Current self-weighted Bayesian"))

# Config 2: Linear weighted average
df["fusion_linear"] = df.apply(
    lambda r: fusion_linear(r["norm_lgn"], r["mech_support_approx"]), axis=1
)
df["tier_linear"] = df.apply(
    lambda r: assign_tier(r["fusion_linear"], r["graph_found"] or r["kge_found"], r["norm_lgn"]), axis=1
)
results.append(compute_metrics(df["tier_linear"], "Linear weighted average"))

# Config 3: Soft-voting
df["fusion_soft_voting"] = df.apply(
    lambda r: fusion_soft_voting(r["norm_lgn"], r["mech_support_approx"]), axis=1
)
df["tier_soft_voting"] = df.apply(
    lambda r: assign_tier(r["fusion_soft_voting"], r["graph_found"] or r["kge_found"], r["norm_lgn"]), axis=1
)
results.append(compute_metrics(df["tier_soft_voting"], "Soft-voting (softmax)"))

# Config 4: Max-pooling
df["fusion_max"] = df.apply(
    lambda r: fusion_max_pooling(r["norm_lgn"], r["mech_support_approx"]), axis=1
)
df["tier_max"] = df.apply(
    lambda r: assign_tier(r["fusion_max"], r["graph_found"] or r["kge_found"], r["norm_lgn"]), axis=1
)
results.append(compute_metrics(df["tier_max"], "Max-pooling"))

# Config 5: Attention mechanism
df["fusion_attention"] = df.apply(
    lambda r: fusion_attention(r["norm_lgn"], r["mech_support_approx"]), axis=1
)
df["tier_attention"] = df.apply(
    lambda r: assign_tier(r["fusion_attention"], r["graph_found"] or r["kge_found"], r["norm_lgn"]), axis=1
)
results.append(compute_metrics(df["tier_attention"], "Attention mechanism"))

# Create results dataframe
results_df = pd.DataFrame(results)

# Save results
results_df.to_csv(OUTPUT, index=False)

# Print results
print("\n" + "=" * 80)
print("FUSION ABLATION RESULTS")
print("=" * 80)
print(results_df.to_string(index=False))

# Analysis
print("\n" + "=" * 80)
print("ANALYSIS")
print("=" * 80)

current_actionable = results_df[results_df["config"] == "Current self-weighted Bayesian"]["actionable_rate"].values[0]
best_actionable = results_df["actionable_rate"].max()
best_config = results_df.loc[results_df["actionable_rate"].idxmax(), "config"]

print(f"\nCurrent method actionable rate: {current_actionable:.4f}")
print(f"Best actionable rate: {best_actionable:.4f} ({best_config})")
print(f"Difference: {(best_actionable - current_actionable):.4f}")

if current_actionable >= best_actionable:
    print("\n✓ Current method performs as well as or better than alternatives")
else:
    print(f"\n⚠ {best_config} outperforms current method by {(best_actionable - current_actionable)*100:.2f}%")

print(f"\nResults saved to: {OUTPUT}")
