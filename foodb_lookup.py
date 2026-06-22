"""
FooDB food-to-compound lookup module.
Provides fast lookup of compounds for foods from FooDB Content.csv.
"""
import re
import pandas as pd
from pathlib import Path
from typing import Set, Dict, Optional

ROOT = Path(__file__).resolve().parent
FOOD_FILE = ROOT / "Food.csv"
COMPOUND_FILE = ROOT / "Compound.csv"
CONTENT_FILE = ROOT / "Content.csv"


class FooDBLookup:
    """Fast food-to-compound lookup using FooDB Content.csv."""
    
    def __init__(self, verbose: bool = True):
        self._food_to_compounds: Dict[str, Set[str]] = {}
        self._loaded = False
        self._verbose = verbose
        
        if verbose:
            print("Initializing FooDB lookup...")
        
        self._load_mappings()
    
    def _norm_food_name(self, s: str) -> str:
        s = str(s).strip().lower()
        s = re.sub(r"[^a-z0-9 ]+", " ", s)
        return re.sub(r"\s+", " ", s).strip()
    
    def _norm_compound_name(self, s: str) -> str:
        s = str(s).strip().lower()
        s = re.sub(r"\([^)]*\)", "", s)
        s = s.replace("/", " ")
        s = s.replace("+", " ")
        s = s.replace("_", " ")
        s = re.sub(r"[^a-z0-9 ]+", " ", s)
        return re.sub(r"\s+", " ", s).strip()
    
    def _load_mappings(self):
        """Load food-to-compound mappings from FooDB files."""
        try:
            # Load Food.csv
            food_df = pd.read_csv(FOOD_FILE)
            food_df['name_norm'] = food_df['name'].apply(self._norm_food_name)
            
            # Load Compound.csv
            compound_df = pd.read_csv(COMPOUND_FILE, usecols=['id', 'name'])
            compound_df['name_norm'] = compound_df['name'].apply(self._norm_compound_name)
            
            # Load Content.csv compound entries
            content_compounds = []
            for chunk in pd.read_csv(CONTENT_FILE, chunksize=50000, low_memory=False):
                compound_chunk = chunk[chunk['source_type'] == 'Compound']
                if not compound_chunk.empty:
                    content_compounds.append(compound_chunk[['food_id', 'source_id']])
            
            content_df = pd.concat(content_compounds, ignore_index=True)
            
            # Build lookup dictionary
            food_id_to_name = dict(zip(food_df['id'], food_df['name']))
            compound_id_to_name = dict(zip(compound_df['id'], compound_df['name']))
            
            for _, row in content_df.iterrows():
                food_id = row['food_id']
                compound_id = row['source_id']
                
                if food_id in food_id_to_name and compound_id in compound_id_to_name:
                    food_name = food_id_to_name[food_id]
                    compound_name = compound_id_to_name[compound_id]
                    
                    if food_name not in self._food_to_compounds:
                        self._food_to_compounds[food_name] = set()
                    self._food_to_compounds[food_name].add(compound_name)
            
            self._loaded = True
            
            if self._verbose:
                print(f"  FooDB lookup ready: {len(self._food_to_compounds)} foods with compounds")
        
        except Exception as e:
            if self._verbose:
                print(f"  Error loading FooDB: {e}")
                print(f"  FooDB lookup will be disabled")
            self._food_to_compounds = {}
    
    def get_compounds(self, food_name: str) -> Optional[list[str]]:
        """
        Get compounds for a food from FooDB.
        
        Args:
            food_name: Name of the food to look up
            
        Returns:
            List of compound names if found, None otherwise
        """
        if not self._loaded:
            return None
        
        food_norm = self._norm_food_name(food_name)
        
        # Try exact match first
        for food in self._food_to_compounds.keys():
            if self._norm_food_name(food) == food_norm:
                return list(self._food_to_compounds[food])
        
        return None
    
    def has_food(self, food_name: str) -> bool:
        """Check if food exists in FooDB."""
        return self.get_compounds(food_name) is not None
    
    @property
    def num_foods(self) -> int:
        """Number of foods with compound mappings."""
        return len(self._food_to_compounds)
