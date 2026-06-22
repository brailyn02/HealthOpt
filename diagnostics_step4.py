import pandas as pd
df = pd.read_csv('validation_splits/phase5_fusion_results.csv')

print("=== CHECKING TABLE 3.9 TEST CASE DRUGS ===")
test_pairs = ['warfarin', 'phenelzine', 'ketoconazole', 'digoxin', 'ferrous']
for drug in test_pairs:
    matches = df[df['drug'].str.lower().str.contains(drug, na=False)]
    if len(matches):
        print(f"\n✓ FOUND: {drug.upper()}")
        print(matches[['drug','food','fusion_score', 'confidence', 'lgn_score', 'graph_found', 'kge_found']].to_string())
    else:
        print(f"\n✗ NOT FOUND: {drug}")

print("\n\n=== CHECKING FOR RULE-RELATED FLAGS IN EXPLANATION ===")
rule_keywords = ['chelation', 'warfarin', 'vitamin k', 'tyramine', 'acid', 'potassium', 'absorption', 'interaction']
for keyword in rule_keywords:
    matching_rows = df[df['explanation'].str.lower().str.contains(keyword, na=False)]
    if len(matching_rows) > 0:
        print(f"\nKeyword '{keyword}': {len(matching_rows)} matches")
        print(matching_rows[['drug', 'food', 'explanation']].head(2).to_string())
