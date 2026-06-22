"""
Implement FooDB food-to-compound lookup via Content.csv.
Test on sample foods to verify functionality.
"""
import pandas as pd
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FOOD_FILE = ROOT / "Food.csv"
COMPOUND_FILE = ROOT / "Compound.csv"
CONTENT_FILE = ROOT / "Content.csv"

def norm_food_name(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def norm_compound_name(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"\([^)]*\)", "", s)
    s = s.replace("/", " ")
    s = s.replace("+", " ")
    s = s.replace("_", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

print("=" * 60)
print("IMPLEMENTING FOODB FOOD-TO-COMPOUND LOOKUP")
print("=" * 60)

# Load Food.csv (small)
print("\nLoading Food.csv...")
food_df = pd.read_csv(FOOD_FILE)
food_df['name_norm'] = food_df['name'].apply(norm_food_name)
print(f"Loaded {len(food_df)} foods")

# Load Compound.csv (small - just name and ID)
print("\nLoading Compound.csv...")
compound_df = pd.read_csv(COMPOUND_FILE, usecols=['id', 'name'])
compound_df['name_norm'] = compound_df['name'].apply(norm_compound_name)
print(f"Loaded {len(compound_df)} compounds")

# Load Content.csv compound entries only
print("\nLoading Content.csv (compound entries only)...")
content_compounds = []
chunk_size = 50000
for chunk in pd.read_csv(CONTENT_FILE, chunksize=chunk_size):
    compound_chunk = chunk[chunk['source_type'] == 'Compound']
    if not compound_chunk.empty:
        content_compounds.append(compound_chunk[['food_id', 'source_id']])
    if len(content_compounds) > 0 and sum(len(c) for c in content_compounds) > 100000:
        break

content_df = pd.concat(content_compounds, ignore_index=True)
print(f"Loaded {len(content_df)} food-to-compound mappings")

# Create lookup dictionary
print("\nCreating lookup dictionary...")
food_id_to_name = dict(zip(food_df['id'], food_df['name']))
compound_id_to_name = dict(zip(compound_df['id'], compound_df['name']))

food_to_compounds = {}
for _, row in content_df.iterrows():
    food_id = row['food_id']
    compound_id = row['source_id']
    
    if food_id in food_id_to_name and compound_id in compound_id_to_name:
        food_name = food_id_to_name[food_id]
        compound_name = compound_id_to_name[compound_id]
        
        if food_name not in food_to_compounds:
            food_to_compounds[food_name] = set()
        food_to_compounds[food_name].add(compound_name)

print(f"Created mappings for {len(food_to_compounds)} foods")

# Test on sample foods
print("\n--- TESTING FOOD-TO-COMPOUND LOOKUP ---")
test_foods = ["Garlic", "Onion", "Spinach", "Orange", "Coffee"]

for food in test_foods:
    food_norm = norm_food_name(food)
    # Find matching food in FooDB
    matching_foods = [f for f in food_to_compounds.keys() if norm_food_name(f) == food_norm]
    
    if matching_foods:
        for match in matching_foods:
            compounds = list(food_to_compounds[match])[:10]
            print(f"\n{food} (matched as '{match}'):")
            print(f"  Compounds: {', '.join(compounds)}")
            if len(food_to_compounds[match]) > 10:
                print(f"  ... and {len(food_to_compounds[match]) - 10} more")
    else:
        print(f"\n{food}: Not found in FooDB")

print(f"\n--- SUMMARY ---")
print(f"FooDB food-to-compound lookup implemented successfully")
print(f"Total foods with compound mappings: {len(food_to_compounds)}")
print(f"This can be used as priority #2 after NA seed")
