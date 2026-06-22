"""
Analyze Content.csv to understand its structure and whether it has food-to-compound mappings.
"""
import pandas as pd

print("=" * 60)
print("ANALYZING CONTENT.CSV")
print("=" * 60)

# Read sample to understand structure
df = pd.read_csv("Content.csv", nrows=1000)

print(f"\nTotal rows (sample): {len(df)}")
print(f"Columns: {list(df.columns)}")

print(f"\n--- SOURCE TYPES ---")
print(df['source_type'].value_counts())

print(f"\n--- SAMPLE NUTRIENT ENTRIES ---")
print(df[df['source_type'] == 'Nutrient'].head())

print(f"\n--- SAMPLE COMPOUND ENTRIES ---")
if 'Compound' in df['source_type'].values:
    print(df[df['source_type'] == 'Compound'].head())
else:
    print("No Compound source_type found in sample")

print(f"\n--- CHECKING FOR COMPOUND COLUMN ---")
if 'orig_source_name' in df.columns:
    print(f"orig_source_name sample values:")
    print(df['orig_source_name'].dropna().head(20))
