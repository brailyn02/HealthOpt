"""
Check if pipeline foods actually have compound mappings in the KKG graph.
Determine if foods in food_id_map.csv have corresponding compound connections.
"""
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FOOD_ID_MAP = ROOT / "DFinder-main" / "data" / "unified-DFI" / "id_maps" / "food_id_map.csv"
HKG_EDGES = ROOT / "data" / "processed_hkg" / "hkg_food_compound_edges.csv"

print("=" * 60)
print("CHECKING PIPELINE FOOD COMPOUND COVERAGE")
print("=" * 60)

# Load pipeline foods
food_map = pd.read_csv(FOOD_ID_MAP)
pipeline_foods = set(food_map['name'].str.lower().unique())
print(f"\nPipeline foods: {len(pipeline_foods)}")

# Load HKG food-compound edges
try:
    hkg_edges = pd.read_csv(HKG_EDGES)
    hkg_foods = set(hkg_edges['head'].str.lower().unique())
    print(f"HKG foods with compound edges: {len(hkg_foods)}")
    
    # Check overlap
    overlap = pipeline_foods & hkg_foods
    pipeline_without_compounds = pipeline_foods - hkg_foods
    
    print(f"\n--- COVERAGE ANALYSIS ---")
    print(f"Pipeline foods with compound edges: {len(overlap)}")
    print(f"Pipeline foods WITHOUT compound edges: {len(pipeline_without_compounds)}")
    print(f"Coverage: {len(overlap)/len(pipeline_foods)*100:.1f}%")
    
    if len(pipeline_without_compounds) > 0:
        print(f"\n--- PIPELINE FOODS WITHOUT COMPOUND EDGES (sample) ---")
        for food in sorted(list(pipeline_without_compounds))[:20]:
            print(f"  - {food}")
    
except Exception as e:
    print(f"Error loading HKG edges: {e}")
