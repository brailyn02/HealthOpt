"""
Analyze specificity and False Positive Rate.

Note: The current validation set (889 pairs) contains only POSITIVE examples
(confirmed interactions). There are no negative/non-interaction pairs.

This means we cannot calculate true specificity or FPR without negative samples.
However, we can analyze:
1. How many positive pairs are classified as INSUFFICIENT (false negatives)
2. Score distribution to understand model behavior
3. Suggest approach for proper specificity evaluation
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VAL_DIR = ROOT / "validation_splits"
RESULTS = VAL_DIR / "phase5_fusion_results.csv"

print("=" * 80)
print("SPECIFICITY ANALYSIS")
print("=" * 80)

# Load results
df = pd.read_csv(RESULTS)
print(f"\nLoaded {len(df)} validation pairs")
print(f"Note: All pairs are POSITIVE (confirmed interactions)")
print(f"Verdict distribution: {df['truth'].value_counts().to_dict()}")

# Tier distribution
tier_counts = df['confidence'].value_counts()
print(f"\nTier distribution:")
for tier in ['HIGH', 'MEDIUM', 'LOW', 'INSUFFICIENT']:
    count = tier_counts.get(tier, 0)
    pct = count / len(df) * 100
    print(f"  {tier:12s}: {count:4d} ({pct:5.1f}%)")

# Score distribution
print(f"\nFusion score distribution:")
print(f"  Mean: {df['fusion_score'].mean():.4f}")
print(f"  Median: {df['fusion_score'].median():.4f}")
print(f"  Std: {df['fusion_score'].std():.4f}")
print(f"  Min: {df['fusion_score'].min():.4f}")
print(f"  Max: {df['fusion_score'].max():.4f}")

# Analyze INSUFFICIENT cases (false negatives in positive-only set)
insufficient = df[df['confidence'] == 'INSUFFICIENT']
print(f"\nINSUFFICIENT cases (false negatives): {len(insufficient)}")
print(f"Percentage of positive set: {len(insufficient)/len(df)*100:.1f}%")

print(f"\nSample INSUFFICIENT cases (should be interactions but flagged as safe):")
print(insufficient[['drug', 'food', 'fusion_score', 'lgn_score', 'truth']].head(10).to_string(index=False))

# Score threshold analysis
print(f"\n" + "=" * 80)
print("SCORE THRESHOLD ANALYSIS")
print("=" * 80)

thresholds = [0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80]
for thresh in thresholds:
    above = (df['fusion_score'] >= thresh).sum()
    below = (df['fusion_score'] < thresh).sum()
    print(f"Threshold {thresh:.2f}: {above:4d} above ({above/len(df)*100:5.1f}%), {below:4d} below ({below/len(df)*100:5.1f}%)")

print(f"\n" + "=" * 80)
print("LIMITATION AND RECOMMENDATION")
print("=" * 80)
print(f"\nCurrent limitation:")
print(f"  - Validation set contains only POSITIVE examples (n={len(df)})")
print(f"  - No negative/non-interaction pairs available")
print(f"  - Cannot calculate true specificity or FPR")
print(f"\nWhat we CAN say:")
print(f"  - Model correctly identifies {len(df) - len(insufficient)} of {len(df)} positive pairs as actionable ({(len(df)-len(insufficient))/len(df)*100:.1f}%)")
print(f"  - Model misses {len(insufficient)} positive pairs as INSUFFICIENT ({len(insufficient)/len(df)*100:.1f}% false negative rate)")
print(f"  - Score distribution shows model is not simply flagging everything (range: {df['fusion_score'].min():.3f} to {df['fusion_score'].max():.3f})")
print(f"\nRecommendation for proper specificity evaluation:")
print(f"  1. Create negative sample set: known safe drug-food pairs")
print(f"  2. Sources: DrugBank 'no interaction' annotations, clinical trial exclusion criteria")
print(f"  3. Calculate: Specificity = TN / (TN + FP), FPR = FP / (FP + TN)")
print(f"  4. This would demonstrate model doesn't flag safe pairs as dangerous")
