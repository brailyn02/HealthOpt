"""
Count runtime compounds from the validation CSV to match thesis's 194
"""
import pandas as pd

csv_file = "ablation_results/wrapper_b_runtime_vs_manual_compound_level.csv"
df = pd.read_csv(csv_file)

runtime_rows = df[df['source'] == 'runtime']
print(f"Runtime rows in CSV: {len(runtime_rows)}")

# Count unique compounds
unique_runtime = runtime_rows['compound'].nunique()
print(f"Unique runtime compounds: {unique_runtime}")

# Count with duplicates per dish
runtime_with_dups = len(runtime_rows)
print(f"Runtime compounds with duplicates per dish: {runtime_with_dups}")

# Check which matches thesis 194
print(f"\nThesis claims 194 runtime compounds")
print(f"Closest match: {'unique' if abs(unique_runtime - 194) < abs(runtime_with_dups - 194) else 'with duplicates'}")
