import os
import pandas as pd

print("=== SEARCHING FOR LAYER 0 / RULE ENGINE FILES ===")
found_files = []
for root, dirs, files in os.walk('.'):
    for f in files:
        if any(x in f.lower() for x in ['layer0', 'rule', 'physicochemical', 'chelation']):
            found_files.append(os.path.join(root, f))
            print(os.path.join(root, f))

if not found_files:
    print("No Layer 0 specific files found.")

print("\n=== CHECKING FUSION RESULTS FOR LAYER 0 COLUMN ===")
df = pd.read_csv('validation_splits/phase5_fusion_results.csv')

layer0_cols = [col for col in df.columns if 'layer0' in col.lower() or 'rule' in col.lower() or 'physicochemical' in col.lower()]

if layer0_cols:
    print(f"Found Layer 0 columns: {layer0_cols}")
    print(df[['drug','food'] + layer0_cols].head())
else:
    print("No Layer 0 column found in fusion results")
    print(f"\nAll available columns:\n{df.columns.tolist()}")
