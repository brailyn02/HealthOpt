#!/usr/bin/env python
"""Direct test of predict.py to verify manual keys are added."""

from predict import DFinder

# Create instance
df = DFinder(verbose=False)

# Make a test prediction
result = df.predict("Warfarin", "Grapefruit")

print("=" * 60)
print("TEST RESULT")
print("=" * 60)
print(f"Has simple_view: {'simple_view' in result}")
print(f"Has technical_view: {'technical_view' in result}")

if 'simple_view' in result:
    print(f"simple_view.metaphor: {result['simple_view'].get('metaphor')}")
    
if 'technical_view' in result:
    print(f"technical_view.raw_mechanism: {result['technical_view'].get('raw_mechanism')}")

print(f"\nTotal keys in result: {len(result)}")
print(f"\nKey names: {', '.join(sorted(result.keys()))}")
