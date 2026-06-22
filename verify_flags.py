import pandas as pd

# Load the final fusion results and the Layer 0 results
try:
    fusion_df = pd.read_csv("validation_splits/phase5_fusion_results.csv")
    layer0_df = pd.read_csv("ablation_results/layer0_retrofitted.csv")
except FileNotFoundError:
    print("Error: Please run `predict.py --validate` and `ablation_study.py` first to generate necessary files.")
    exit()

# Rename columns in fusion_df to be consistent for the merge
fusion_df.rename(columns={"drug": "drug_name", "food": "food_name"}, inplace=True)

# Merge the two dataframes
df = pd.merge(fusion_df, layer0_df.drop_duplicates(subset=['drug_name', 'food_name']), on=['drug_name', 'food_name'], how='left')
df['layer0_fired'] = df['layer0_fired'].fillna(False)

# --- Define Flags based on the logic in predict.py ---

# LGN thresholds from predict.py
LGN_EXPERT_TH = 0.90
LGN_HIDDEN_TH = 0.80
LGN_THEORETICAL_UPPER = 0.40

# --- Calculate Flags ---

# ALL_LAYERS_AGREE: graph_found, kge_found, and lgn_score > 0
df['flag_all_layers_agree'] = (df['graph_found']) & (df['kge_found']) & (df['lgn_score'] > 0)

# HIDDEN_MECHANISM: LGN score is high, but no mechanistic path was found (neither graph nor KGE)
df['flag_hidden_mechanism'] = (df['lgn_score'] >= LGN_HIDDEN_TH) & (~df['graph_found']) & (~df['kge_found'])

# EXPERT_REVIEW: LGN score is very high AND there is some mechanistic confirmation (either graph or KGE)
df['flag_expert_review'] = (df['lgn_score'] >= LGN_EXPERT_TH) & (df['graph_found'] | df['kge_found'])

# THEORETICAL_RISK: A mechanistic path exists (graph or KGE), but the LGN signal is weak
df['flag_theoretical_risk'] = (df['graph_found'] | df['kge_found']) & (df['lgn_score'] < LGN_THEORETICAL_UPPER)

# CLINICAL_RULE_CONFIRMED: The Layer 0 safety gate fired
df['flag_clinical_rule_confirmed'] = df['layer0_fired']

# --- Report Counts ---
counts = {
    "ALL_LAYERS_AGREE": df['flag_all_layers_agree'].sum(),
    "HIDDEN_MECHANISM": df['flag_hidden_mechanism'].sum(),
    "EXPERT_REVIEW": df['flag_expert_review'].sum(),
    "THEORETICAL_RISK": df['flag_theoretical_risk'].sum(),
    "CLINICAL_RULE_CONFIRMED": df['flag_clinical_rule_confirmed'].sum()
}

print("--- Corrected Explainability Flag Counts (N=889) ---")
for flag, count in counts.items():
    print(f"— {flag}: {count}/889")

# Save the results to a file for inspection
df.to_csv("explainability_flags_verification.csv", index=False)
print("\nDetailed results saved to explainability_flags_verification.csv")
