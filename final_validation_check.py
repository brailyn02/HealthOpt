import pandas as pd
import numpy as np

# Load the final, comprehensive data
try:
    df = pd.read_csv("explainability_flags_verification.csv")
except FileNotFoundError:
    print("Error: Please run `verify_flags.py` first to generate the necessary data file.")
    exit()

TOTAL_PAIRS = len(df)
print(f"--- Verification based on {TOTAL_PAIRS} pairs ---")

# --- 1. Verification for Layer-by-layer recall table (tab:recall_889) ---
print("\n1. Verifying Layer-by-layer recall (Table: tab:recall_889)...")

# Layer 1 - HKG Graph
hkg_detected = df['graph_found'].sum()
hkg_recall = (hkg_detected / TOTAL_PAIRS) * 100
print(f"  Layer 1 (HKG Graph) | path found: {hkg_detected}/{TOTAL_PAIRS} = {hkg_recall:.1f}% recall")

# Layer 2 - KGE
kge_detected = (df['kge_score'] > 0).sum()
kge_recall = (kge_detected / TOTAL_PAIRS) * 100
print(f"  Layer 2 (KGE)       | score > 0: {kge_detected}/{TOTAL_PAIRS} = {kge_recall:.1f}% recall")

# Layer 3 - LGN >= 0.50
lgn_detected_050 = (df['lgn_score'] >= 0.50).sum()
lgn_recall_050 = (lgn_detected_050 / TOTAL_PAIRS) * 100
print(f"  Layer 3 (LGN)       | >= 0.50: {lgn_detected_050}/{TOTAL_PAIRS} = {lgn_recall_050:.1f}% recall")

# Layer 3 - LGN >= 0.90
lgn_detected_090 = (df['lgn_score'] >= 0.90).sum()
lgn_recall_090 = (lgn_detected_090 / TOTAL_PAIRS) * 100
print(f"  Layer 3 (LGN)       | >= 0.90: {lgn_detected_090}/{TOTAL_PAIRS} = {lgn_recall_090:.1f}% recall")

# Fusion HIGH+MEDIUM (Actionable)
# Re-calculate tiers based on final logic to be certain
def assign_tier(row):
    if row['layer0_fired']: return "HIGH"
    if row['fusion_score'] >= 0.70: return "HIGH"
    if row['fusion_score'] >= 0.45: return "MEDIUM"
    if row['fusion_score'] > 0: return "LOW"
    return "INSUFFICIENT"
df['final_tier'] = df.apply(assign_tier, axis=1)

actionable_detected = df['final_tier'].isin(['HIGH', 'MEDIUM']).sum()
actionable_recall = (actionable_detected / TOTAL_PAIRS) * 100
print(f"  Fusion (Actionable) | HIGH+MEDIUM: {actionable_detected}/{TOTAL_PAIRS} = {actionable_recall:.1f}% recall")

# ANY signal
any_signal_detected = ((df['fusion_score'] > 0) | (df['layer0_fired'])).sum()
any_signal_recall = (any_signal_detected / TOTAL_PAIRS) * 100
print(f"  ANY signal (Full)   | > 0: {any_signal_detected}/{TOTAL_PAIRS} = {any_signal_recall:.1f}% recall")


# --- 2. Verification for Top Validated Predictions table (tab:top_pred) ---
print("\n2. Verifying Top Validated Predictions (Table: tab:top_pred)...")

# Check specific pairs mentioned in the table
pairs_to_check = [
    ("Tamoxifen", "Sesame"),
    ("Cyclosporine", "Ginger"),
    ("Simvastatin", "Ginger"),
    ("Amiodarone", "Honey"),
    ("Atorvastatin", "Grapefruit"),
    ("Warfarin", "Grapefruit"),
    ("Ferrous sulfate", "Pizza"),
    ("Ferrous sulfate", "Hamburger")
]

for drug, food in pairs_to_check:
    # Normalize names for matching
    drug_norm = drug.lower().strip()
    food_norm = food.lower().strip()
    
    pair_data = df[
        (df['drug_name'].str.lower().str.strip() == drug_norm) & 
        (df['food_name'].str.lower().str.strip() == food_norm)
    ]
    
    if not pair_data.empty:
        row = pair_data.iloc[0]
        flags = []
        if row['flag_all_layers_agree']: flags.append("ALL_LAYERS_AGREE")
        if row['flag_expert_review']: flags.append("EXPERT_REVIEW")
        if row['flag_clinical_rule_confirmed']: flags.append("CLINICAL_RULE_CONFIRMED")
        
        score_str = f"{row['fusion_score']:.3f}" if pd.notna(row['fusion_score']) else "---"
        if row['flag_clinical_rule_confirmed']:
            score_str = "---"

        print(f"  - {drug} | {food}")
        print(f"    Score: {score_str}, Tier: {row['final_tier']}, Flags: {', '.join(flags) or 'None'}")
    else:
        print(f"  - {drug} | {food}: NOT FOUND in validation data.")

# --- 3. Verification for Discussion section ---
print("\n3. Verifying numbers in Discussion section...")
lgn_recall_05_val = lgn_recall_050
hidden_mechanism_count = df['flag_hidden_mechanism'].sum()
layer0_fired_count = df['layer0_fired'].sum()

print(f"  LGN recall at 0.50: {lgn_recall_05_val:.1f}% (Thesis says 88.5%)")
print(f"  HIDDEN_MECHANISM count: {hidden_mechanism_count} (Thesis says 471)")
print(f"  Layer 0 fired count: {layer0_fired_count} (Ablation study implies 30 upgrades, previous script found 43 total)")

print("\n--- Verification Complete ---")
