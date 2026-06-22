import pandas as pd
df = pd.read_csv('validation_splits/phase5_fusion_results.csv')
print("=== FUSION RESULTS COLUMNS ===")
print(df.columns.tolist())
print("\n=== FIRST 3 ROWS ===")
print(df.head(3))
print(f"\n=== TOTAL ROWS: {len(df)} ===")
