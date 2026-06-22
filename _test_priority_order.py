"""
Test the integrated priority order in predict.py.
Verify that foods are decomposed using NA seed -> FooDB -> LLM priority.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

print("=" * 60)
print("TESTING PRIORITY ORDER IN PREDICT.PY")
print("=" * 60)

# Test food decomposition
test_foods = [
    "chakhchoukha",  # Should use NA seed
    "Garlic",  # Should use FooDB
    "pizza",  # Should use FooDB
    "unknown_algerian_dish_xyz",  # Should use LLM or NOT_FOUND
]

print(f"\n--- TESTING FOOD DECOMPOSITION ---")

# Import and initialize
try:
    from predict import DFinder
    print("Initializing DFinder with priority order...")
    finder = DFinder(verbose=True)
    
    for food in test_foods:
        print(f"\n--- Testing: {food} ---")
        try:
            result = finder.predict("warfarin", food)
            
            # Check source of compounds
            if result.get("llm_compounds"):
                sources = [c.get("source", "UNKNOWN") for c in result["llm_compounds"]]
                unique_sources = list(set(sources))
                print(f"  Compound sources: {unique_sources}")
                print(f"  Number of compounds: {len(result['llm_compounds'])}")
                
                # Determine primary source
                if "NA_SEED" in unique_sources:
                    print(f"  ✓ Used NA seed (priority 1)")
                elif "FOODB" in unique_sources:
                    print(f"  ✓ Used FooDB (priority 2)")
                elif "LLM_SOURCED" in unique_sources:
                    print(f"  ✓ Used LLM (priority 3)")
                else:
                    print(f"  ? Unknown source")
            else:
                print(f"  ✗ No compounds found")
        except Exception as e:
            print(f"  Error: {e}")

except Exception as e:
    print(f"Error initializing DFinder: {e}")
    import traceback
    traceback.print_exc()

print(f"\n--- SUMMARY ---")
print(f"Priority order integration tested")
print(f"Expected behavior: NA seed → FooDB → LLM")
