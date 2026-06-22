"""
Check full Content.csv for compound entries by reading more rows.
"""
import pandas as pd

print("=" * 60)
print("CHECKING FULL CONTENT.CSV FOR COMPOUND ENTRIES")
print("=" * 60)

# Read in chunks to find compound entries
chunk_size = 50000
compound_count = 0
nutrient_count = 0
total_rows = 0

for chunk in pd.read_csv("Content.csv", chunksize=chunk_size):
    total_rows += len(chunk)
    compound_count += len(chunk[chunk['source_type'] == 'Compound'])
    nutrient_count += len(chunk[chunk['source_type'] == 'Nutrient'])
    
    if compound_count > 0:
        print(f"Found compound entries in chunk ending at row {total_rows}")
        print(f"Sample compound entries:")
        print(chunk[chunk['source_type'] == 'Compound'].head())
        break
    
    if total_rows > 500000:  # Check first 500k rows
        print(f"Checked {total_rows} rows, no compound entries found yet")
        break

print(f"\n--- FINAL COUNTS ---")
print(f"Total rows checked: {total_rows}")
print(f"Compound entries: {compound_count}")
print(f"Nutrient entries: {nutrient_count}")

if compound_count > 0:
    print(f"\n✓ Content.csv DOES contain food-to-compound mappings")
else:
    print(f"\n✗ Content.csv appears to only contain nutrient data")
