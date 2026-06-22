"""
Check if Content.csv has any compound entries by sampling more rows.
"""
import pandas as pd

print("=" * 60)
print("CHECKING FOR COMPOUND ENTRIES IN CONTENT.CSV")
print("=" * 60)

# Read larger sample to find compound entries
df = pd.read_csv("Content.csv", nrows=10000)

print(f"\nTotal rows (sample): {len(df)}")
print(f"Source types in sample:")
print(df['source_type'].value_counts())

print(f"\n--- CHECKING FOR COMPOUND IN SOURCE TYPE ---")
if 'Compound' in df['source_type'].values:
    print(f"Found {len(df[df['source_type'] == 'Compound'])} compound entries")
    print(df[df['source_type'] == 'Compound'].head())
else:
    print("No Compound source_type found in first 10,000 rows")

print(f"\n--- CHECKING ORIG_SOURCE_NAME FOR COMPOUND-LIKE VALUES ---")
unique_sources = df['orig_source_name'].dropna().unique()
print(f"Unique orig_source_name values (first 50):")
for i, val in enumerate(unique_sources[:50]):
    print(f"  {i+1}. {val}")

print(f"\n--- CHECKING IF COMPOUND MIGHT BE IN A DIFFERENT COLUMN ---")
print(f"Columns that might contain compound info:")
for col in df.columns:
    if 'source' in col.lower() or 'compound' in col.lower():
        print(f"  {col}")
