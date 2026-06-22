import pandas as pd
df2 = pd.read_csv('validation_splits/validation_unseen.csv')
print("=== VALIDATION COHORT COLUMNS ===")
print(df2.columns.tolist())
print("\n=== FIRST 3 ROWS ===")
print(df2.head(3))
print(f"\n=== TOTAL ROWS: {len(df2)} ===")
