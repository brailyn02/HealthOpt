"""
ablation_study.py
Run this from d:/23AIBox-DFinder/

Produces:
  ablation_results/layer0_retrofitted.csv   — Layer 0 firing on all 889 pairs
  ablation_results/ablation_table.csv       — 4-config ablation metrics
  ablation_results/layer0_upgrade_cases.csv — pairs where Layer 0 changes tier
  ablation_results/ablation_summary.txt     — paste-ready numbers for LaTeX
"""

import os
import sys
from pathlib import Path

import pandas as pd

os.makedirs("ablation_results", exist_ok=True)

# -- 1. Load data -------------------------------------------------------------
fusion = pd.read_csv("validation_splits/phase5_fusion_results.csv")
cohort = pd.read_csv("validation_splits/validation_unseen.csv")

print(f"Fusion rows  : {len(fusion)}")
print(f"Cohort rows  : {len(cohort)}")
print(f"Fusion cols  : {fusion.columns.tolist()}")

# fusion already has drug/food columns used in validation output
# rename to align naming downstream
df = fusion.copy()
df.rename(columns={"drug": "drug_name", "food": "food_name"}, inplace=True)

# -- 2-4. Layer 0 retroactive data ------------------------------------------
# Load cached layer0_retrofitted.csv if it exists (avoids importing
# physicochemical / predict which triggers heavy model loading).
_L0_CACHE = Path("ablation_results/layer0_retrofitted.csv")
if _L0_CACHE.exists():
    print(f"\nLoading cached Layer 0 results from {_L0_CACHE}")
    l0_df = pd.read_csv(_L0_CACHE)
else:
    print("\nNo cached Layer 0 results — applying manual rule mapping")
    known_layer0 = {
        ("warfarin", "spinach"): "VITAMIN_K_ANTAGONISM",
        ("warfarin", "vitamin k"): "VITAMIN_K_ANTAGONISM",
        ("acenocoumarol", "spinach"): "VITAMIN_K_ANTAGONISM",
        ("phenelzine", "cheese"): "TYRAMINE_CRISIS",
        ("phenelzine", "tyramine"): "TYRAMINE_CRISIS",
        ("tranylcypromine", "cheese"): "TYRAMINE_CRISIS",
        ("ciprofloxacin", "milk"): "CHELATION_RISK",
        ("ciprofloxacin", "yogurt"): "CHELATION_RISK",
        ("ferrous", "phytic"): "CHELATION_RISK",
        ("ferrous", "magnesium"): "CHELATION_RISK",
        ("tetracycline", "milk"): "CHELATION_RISK",
        ("ketoconazole", "antacid"): "ACID_ABSORPTION_RISK",
        ("ketoconazole", "milk"): "ACID_ABSORPTION_RISK",
        ("digoxin", "banana"): "POTASSIUM_OVERLOAD",
        ("digoxin", "avocado"): "POTASSIUM_OVERLOAD",
        ("lisinopril", "avocado"): "POTASSIUM_OVERLOAD",
        ("spironolactone", "avocado"): "POTASSIUM_OVERLOAD",
    }
    layer0_results = []
    for _, row in df.iterrows():
        drug_l = str(row["drug_name"]).lower()
        food_l = str(row["food_name"]).lower()
        fired, rule = False, ""
        for (d_frag, f_frag), r in known_layer0.items():
            if d_frag in drug_l and f_frag in food_l:
                fired, rule = True, r
                break
        layer0_results.append({
            "drug_name": row["drug_name"],
            "food_name": row["food_name"],
            "layer0_fired": fired,
            "layer0_rule": rule,
            "layer0_severity": "HIGH" if fired else "",
        })
    l0_df = pd.DataFrame(layer0_results)
    l0_df = l0_df.drop_duplicates(subset=["drug_name", "food_name"], keep="first")
    l0_df.to_csv(_L0_CACHE, index=False)

l0_df = l0_df.drop_duplicates(subset=["drug_name", "food_name"], keep="first")
df = df.merge(l0_df, on=["drug_name", "food_name"], how="left")
df["layer0_fired"] = df["layer0_fired"].fillna(False)
df["layer0_rule"] = df["layer0_rule"].fillna("")
df["layer0_severity"] = df["layer0_severity"].fillna("")

n_layer0_fired = int(df["layer0_fired"].sum())
print(f"Layer 0 fired on {n_layer0_fired} / {len(df)} pairs")

# -- 5. Tier assignment helper ------------------------------------------------
# -- Live fusion constants (mirrored from predict.py) -------------------------
_LGN_STRONG_CONFIRM = 0.98   # pass-through ceiling — LGN is authoritative
_LGN_HIGH_CONF_TH   = 0.90   # lgn alone → HIGH (HKG absence must not demote)
_LGN_MEDIUM_CONF_TH = 0.65   # lgn alone → MEDIUM
_GRAPH_MAX          = 30.0
_KGE_MAX            = 115.0
_MECH_HKG_W         = 0.65
_MECH_KGE_W         = 0.35
_TH_MEDIUM          = 0.45
_TH_LOW             = 0.20


def _mech_support(graph_score_raw, kge_score_raw):
    """Simplified mechanistic support score (no compound-level detail needed for ablation)."""
    ng = min(float(graph_score_raw or 0.0) / _GRAPH_MAX, 1.0)
    nk = min(float(kge_score_raw  or 0.0) / _KGE_MAX,   1.0)
    return min(_MECH_HKG_W * ng + _MECH_KGE_W * nk, 1.0)


def _piecewise_fusion(norm_lgn, mech_support_val):
    """Exact replica of predict.py DFinder._piecewise_fusion — no model loading."""
    l = max(0.0, min(float(norm_lgn),          1.0))
    m = max(0.0, min(float(mech_support_val),  1.0))
    if l >= _LGN_STRONG_CONFIRM:
        return l
    signals = []
    if l > 0.0:
        signals.append((l, 0.70))
    if m > 0.0:
        signals.append((m, 0.30))
    if not signals:
        return 0.0
    weighted_sum = sum(s * w * s for s, w in signals)
    weight_sum   = sum(w * s     for s, w in signals)
    return max(0.0, min(weighted_sum / weight_sum, 1.0)) if weight_sum > 0 else 0.0


def assign_tier(fusion_score, graph_found, kge_found, norm_lgn, layer0_fired=False):
    """
    Thesis Table 2.8 exact tier logic (Section 2.7):
      HIGH        : Sfusion >= 0.70  (or Layer 0 override)
      MEDIUM      : 0.45 <= Sfusion < 0.70
      LOW         : 0 < Sfusion < 0.45
      INSUFFICIENT: Sfusion = 0 exactly
    Layer 0 forces HIGH regardless of fusion score (thesis footnote †).
    """
    if layer0_fired:
        return "HIGH"
    f = float(fusion_score)
    if f >= 0.70:
        return "HIGH"
    if f >= 0.45:
        return "MEDIUM"
    if f > 0.0:
        return "LOW"
    return "INSUFFICIENT"


def compute_metrics(tier_series, label):
    total = len(tier_series)
    detected = (tier_series != "INSUFFICIENT").sum()
    high = (tier_series == "HIGH").sum()
    medium = (tier_series == "MEDIUM").sum()
    low = (tier_series == "LOW").sum()
    insuf = (tier_series == "INSUFFICIENT").sum()
    action = high + medium
    recall = detected / total * 100
    act_pct = action / total * 100

    print(f"\n{label}")
    print(f"  Recall@any : {detected}/{total} = {recall:.1f}%")
    print(f"  Actionable : {action}/{total}  = {act_pct:.1f}%")
    print(f"  HIGH={high}  MEDIUM={medium}  LOW={low}  INSUF={insuf}")

    return {
        "config": label,
        "recall_n": int(detected),
        "recall_pct": round(recall, 1),
        "actionable_n": int(action),
        "actionable_pct": round(act_pct, 1),
        "HIGH": int(high),
        "MEDIUM": int(medium),
        "LOW": int(low),
        "INSUFFICIENT": int(insuf),
    }


# -- 6. Four ablation configurations -----------------------------------------
print("\n==========================================")
print("  ABLATION CONFIGURATIONS")
print("==========================================")

ablation_rows = []

# Config 1: Layer 3 only (LGN) — no mechanistic signal fed to fusion
df["fusion_C1"] = df["lgn_score"].apply(lambda l: _piecewise_fusion(l, 0.0))
df["tier_L3_only"] = df.apply(
    lambda r: assign_tier(r["fusion_C1"], False, False, r["lgn_score"], False), axis=1
)
ablation_rows.append(compute_metrics(df["tier_L3_only"], "Config 1: Layer 3 only (LGN)"))


# Config 2: Layers 2+3 (LGN + KGE) — graph excluded
df["fusion_C2"] = df.apply(
    lambda r: _piecewise_fusion(r["lgn_score"], _mech_support(0.0, r["kge_score"])), axis=1
)
df["tier_L2_L3"] = df.apply(
    lambda r: assign_tier(r["fusion_C2"], False, r["kge_found"], r["lgn_score"], False), axis=1
)
ablation_rows.append(compute_metrics(df["tier_L2_L3"], "Config 2: Layers 2+3 (LGN + KGE)"))


# Config 3: Layers 1+2+3 (full probabilistic, no Layer 0)
df["fusion_C3"] = df.apply(
    lambda r: _piecewise_fusion(r["lgn_score"], _mech_support(r["graph_score"], r["kge_score"])), axis=1
)
df["tier_L1_L2_L3"] = df.apply(
    lambda r: assign_tier(r["fusion_C3"], r["graph_found"], r["kge_found"], r["lgn_score"], False), axis=1
)
ablation_rows.append(
    compute_metrics(df["tier_L1_L2_L3"], "Config 3: Layers 1+2+3 (full probabilistic)")
)


# Config 4: Full system (Layer 0 + full probabilistic)
df["tier_full"] = df.apply(
    lambda r: assign_tier(r["fusion_C3"], r["graph_found"], r["kge_found"], r["lgn_score"], r["layer0_fired"]), axis=1
)
ablation_rows.append(compute_metrics(df["tier_full"], "Config 4: Full system (all layers)"))

ablation_df = pd.DataFrame(ablation_rows)
ablation_df.to_csv("ablation_results/ablation_table.csv", index=False)

# -- 7. Layer 0 upgrade cases -------------------------------------------------
upgrades = df[(df["layer0_fired"] == True) & (df["tier_L1_L2_L3"] != "HIGH")][
    [
        "drug_name",
        "food_name",
        "lgn_score",
        "fusion_C3",
        "tier_L1_L2_L3",
        "layer0_rule",
        "tier_full",
    ]
].copy()

upgrades.rename(columns={"fusion_C3": "fusion_score_corrected", "tier_L1_L2_L3": "prob_tier", "tier_full": "layer0_tier"}, inplace=True)

print("\n-- Layer 0 UPGRADE cases (prob != HIGH, Layer 0 fires to HIGH) --")
if len(upgrades):
    print(upgrades.to_string(index=False))
else:
    print("(none)")

upgrades.to_csv("ablation_results/layer0_upgrade_cases.csv", index=False)

# -- 8. Evidence-layer contribution breakdown ---------------------------------
lgn_only = ((df["graph_found"] == False) & (df["kge_found"] == False)).sum()
lgn_kge = ((df["graph_found"] == False) & (df["kge_found"] == True)).sum()
lgn_graph = ((df["graph_found"] == True) & (df["kge_found"] == False)).sum()
all_three = ((df["graph_found"] == True) & (df["kge_found"] == True)).sum()

print("\n-- Evidence layer coverage on 889 pairs --")
print(f"  LGN only (no graph, no KGE) : {lgn_only}")
print(f"  LGN + KGE only              : {lgn_kge}")
print(f"  LGN + Graph only            : {lgn_graph}")
print(f"  LGN + Graph + KGE           : {all_three}")

# -- 9. Marginal contributions ------------------------------------------------
insuf_L3 = (df["tier_L3_only"] == "INSUFFICIENT").sum()
insuf_L2_L3 = (df["tier_L2_L3"] == "INSUFFICIENT").sum()
insuf_L1plus = (df["tier_L1_L2_L3"] == "INSUFFICIENT").sum()
insuf_full = (df["tier_full"] == "INSUFFICIENT").sum()

kge_marginal = insuf_L3 - insuf_L2_L3
graph_marginal = insuf_L2_L3 - insuf_L1plus
l0_marginal = insuf_L1plus - insuf_full

print("\n-- Marginal contributions (pairs rescued from INSUFFICIENT) --")
print(f"  KGE    rescued : {kge_marginal}")
print(f"  Graph  rescued : {graph_marginal}")
print(f"  Layer0 rescued : {l0_marginal}")
print(f"  Layer0 upgraded to HIGH from lower tier: {len(upgrades)}")

# -- 10. Write paste-ready summary -------------------------------------------
c1, c2, c3, c4 = ablation_rows

summary = f"""
============================================
  ABLATION STUDY - PASTE-READY NUMBERS
============================================

CONFIG 1 - Layer 3 only (LightGCN baseline)
  recall_any : {c1['recall_n']}/889 = {c1['recall_pct']}%
  actionable : {c1['actionable_n']}/889 = {c1['actionable_pct']}%
  HIGH={c1['HIGH']}  MEDIUM={c1['MEDIUM']}  LOW={c1['LOW']}  INSUF={c1['INSUFFICIENT']}

CONFIG 2 - Layers 2+3 (LGN + KGE)
  recall_any : {c2['recall_n']}/889 = {c2['recall_pct']}%
  actionable : {c2['actionable_n']}/889 = {c2['actionable_pct']}%
  HIGH={c2['HIGH']}  MEDIUM={c2['MEDIUM']}  LOW={c2['LOW']}  INSUF={c2['INSUFFICIENT']}
  KGE marginal gain (rescued from INSUF): {kge_marginal} pairs

CONFIG 3 - Layers 1+2+3 (full probabilistic, no Layer 0)
  recall_any : {c3['recall_n']}/889 = {c3['recall_pct']}%
  actionable : {c3['actionable_n']}/889 = {c3['actionable_pct']}%
  HIGH={c3['HIGH']}  MEDIUM={c3['MEDIUM']}  LOW={c3['LOW']}  INSUF={c3['INSUFFICIENT']}
  Graph marginal gain (rescued from INSUF): {graph_marginal} pairs

CONFIG 4 - Full system (all layers + Layer 0)
  recall_any : {c4['recall_n']}/889 = {c4['recall_pct']}%
  actionable : {c4['actionable_n']}/889 = {c4['actionable_pct']}%
  HIGH={c4['HIGH']}  MEDIUM={c4['MEDIUM']}  LOW={c4['LOW']}  INSUF={c4['INSUFFICIENT']}
  Layer 0 fired on : {n_layer0_fired} pairs
  Layer 0 upgrades (non-HIGH -> HIGH): {len(upgrades)} pairs

EVIDENCE LAYER COVERAGE:
  LGN only            : {lgn_only} pairs ({lgn_only / 889 * 100:.1f}%)
  LGN + KGE           : {lgn_kge} pairs ({lgn_kge / 889 * 100:.1f}%)
  LGN + Graph         : {lgn_graph} pairs ({lgn_graph / 889 * 100:.1f}%)
  All three           : {all_three} pairs ({all_three / 889 * 100:.1f}%)

LAYER 0 UPGRADE CASES:
{upgrades.to_string(index=False) if len(upgrades) else '  (none in 889-pair cohort - see Table 3.9 for validated examples)'}
============================================
"""

print(summary)
with open("ablation_results/ablation_summary.txt", "w", encoding="utf-8") as f:
    f.write(summary)

print("\nDone. Check ablation_results/ for all output files.")
print("Paste ablation_results/ablation_summary.txt numbers into your LaTeX.")
