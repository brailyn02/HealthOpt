"""
Check if FooDB has food-to-compound mappings via Content.csv or alternative.
Since Content.csv is in .gitignore, check for alternative mapping files.
"""
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FOOD_FILE = ROOT / "Food.csv"
COMPOUND_FILE = ROOT / "Compound.csv"
FOOD_CONTENT_TABLE = ROOT / "data" / "food_content_table.csv"

print("=" * 60)
print("CHECKING FOODB FOOD-TO-COMPOUND MAPPINGS")
print("=" * 60)

# Check Food.csv
print(f"\n--- FOOD.CSV ---")
food_df = pd.read_csv(FOOD_FILE)
print(f"Total foods: {len(food_df)}")
print(f"Columns: {list(food_df.columns)}")
print(f"Sample foods: {list(food_df['name'].head(10))}")

# Check Compound.csv
print(f"\n--- COMPOUND.CSV ---")
compound_df = pd.read_csv(COMPOUND_FILE)
print(f"Total compounds: {len(compound_df)}")
print(f"Columns: {list(compound_df.columns)}")

# Check food_content_table.csv
print(f"\n--- FOOD_CONTENT_TABLE.CSV ---")
content_df = pd.read_csv(FOOD_CONTENT_TABLE)
print(f"Total food entries: {len(content_df)}")
print(f"Columns: {list(content_df.columns)}")
print(f"Sample foods: {list(content_df['food_name'].head(10))}")

# Check if there's a direct food-to-compound mapping
print(f"\n--- MAPPING ANALYSIS ---")
print(f"Food.csv has food names and IDs")
print(f"Compound.csv has compound names and IDs")
print(f"food_content_table.csv has nutrient tiers (not compound mappings)")
print(f"\nContent.csv (food-to-compound mapping) is in .gitignore and inaccessible")
print(f"This means direct FooDB food-to-compound mappings are not available")
print(f"in the current repository structure.")

print(f"\n--- RECOMMENDATION ---")
print(f"To implement FooDB food-to-compound lookup:")
print(f"1. Download Content.csv from FooDB (if available)")
print(f"2. Or use FooDB API to query food-to-compound relationships")
print(f"3. Current priority order remains:")
print(f"   1. Algerian manual curation (56 dishes)")
print(f"   2. LLM decomposer (fallback for unknown foods)")
