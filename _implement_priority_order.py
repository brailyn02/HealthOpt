"""
Implement priority order: NA seed → FooDB → LLM
Create a unified food decomposer with proper fallback chain.
"""
import json
import re
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NA_FILE = ROOT / "data" / "na_dish_compounds.json"
FOOD_FILE = ROOT / "Food.csv"
COMPOUND_FILE = ROOT / "Compound.csv"
CONTENT_FILE = ROOT / "Content.csv"
LLM_CACHE = ROOT / "data" / "llm_food_cache.json"

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

class PriorityFoodDecomposer:
    def __init__(self):
        print("Initializing Priority Food Decomposer...")
        
        # Load NA seed
        with open(NA_FILE, encoding="utf-8") as f:
            self.na_seed = json.load(f)
        print(f"  Loaded NA seed: {len(self.na_seed)} dishes")
        
        # Load FooDB mappings
        print("  Loading FooDB mappings...")
        food_df = pd.read_csv(FOOD_FILE)
        food_df['name_norm'] = food_df['name'].apply(norm_food_name)
        
        compound_df = pd.read_csv(COMPOUND_FILE, usecols=['id', 'name'])
        compound_df['name_norm'] = compound_df['name'].apply(norm_compound_name)
        
        content_compounds = []
        for chunk in pd.read_csv(CONTENT_FILE, chunksize=50000):
            compound_chunk = chunk[chunk['source_type'] == 'Compound']
            if not compound_chunk.empty:
                content_compounds.append(compound_chunk[['food_id', 'source_id']])
        
        content_df = pd.concat(content_compounds, ignore_index=True)
        
        food_id_to_name = dict(zip(food_df['id'], food_df['name']))
        compound_id_to_name = dict(zip(compound_df['id'], compound_df['name']))
        
        self.foodb_foods = {}
        for _, row in content_df.iterrows():
            food_id = row['food_id']
            compound_id = row['source_id']
            if food_id in food_id_to_name and compound_id in compound_id_to_name:
                food_name = food_id_to_name[food_id]
                compound_name = compound_id_to_name[compound_id]
                if food_name not in self.foodb_foods:
                    self.foodb_foods[food_name] = set()
                self.foodb_foods[food_name].add(compound_name)
        
        print(f"  Loaded FooDB: {len(self.foodb_foods)} foods with compounds")
        
        # Load LLM cache
        with open(LLM_CACHE, encoding="utf-8") as f:
            self.llm_cache = json.load(f)
        print(f"  Loaded LLM cache: {len(self.llm_cache)} entries")
    
    def decompose(self, food_name: str) -> dict:
        """
        Decompose food into compounds using priority order:
        1. NA seed (Algerian manual curation)
        2. FooDB (food-to-compound mappings)
        3. LLM cache (fallback)
        """
        food_norm = norm_food_name(food_name)
        
        # Priority 1: NA seed
        for dish, compounds in self.na_seed.items():
            if norm_food_name(dish) == food_norm:
                return {
                    "food": food_name,
                    "source": "NA_SEED",
                    "compounds": list(compounds),
                    "count": len(compounds)
                }
        
        # Priority 2: FooDB
        for food in self.foodb_foods.keys():
            if norm_food_name(food) == food_norm:
                compounds = list(self.foodb_foods[food])
                return {
                    "food": food_name,
                    "source": "FOODB",
                    "compounds": compounds,
                    "count": len(compounds)
                }
        
        # Priority 3: LLM cache
        for food, compounds in self.llm_cache.items():
            if norm_food_name(food) == food_norm:
                return {
                    "food": food_name,
                    "source": "LLM_CACHE",
                    "compounds": compounds,
                    "count": len(compounds)
                }
        
        return {
            "food": food_name,
            "source": "NOT_FOUND",
            "compounds": [],
            "count": 0
        }

print("=" * 60)
print("PRIORITY FOOD DECOMPOSER")
print("=" * 60)

decomposer = PriorityFoodDecomposer()

# Test on various foods
test_foods = [
    "chakhchoukha",  # NA seed
    "Garlic",  # FooDB
    "pizza",  # LLM cache
    "unknown_food_xyz"  # Not found
]

print(f"\n--- TESTING PRIORITY ORDER ---")
for food in test_foods:
    result = decomposer.decompose(food)
    print(f"\n{food}:")
    print(f"  Source: {result['source']}")
    print(f"  Compounds: {result['count']}")
    if result['compounds']:
        print(f"  Sample: {', '.join(result['compounds'][:5])}")

print(f"\n--- SUMMARY ---")
print(f"Priority order implemented: NA seed → FooDB → LLM cache")
print(f"This provides the most accurate compound decomposition by using")
print(f"manual curation first, then database mappings, then LLM fallback.")
