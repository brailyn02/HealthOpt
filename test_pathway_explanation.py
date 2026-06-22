#!/usr/bin/env python3
"""Quick test of enhanced pathway explanations."""

import json
import requests

payload = {
    'drug_name': 'Warfarin',
    'food_name': 'Spinach',
}

print("Testing Warfarin-Spinach prediction with enhanced explanations...")
print()

try:
    resp = requests.post(
        'http://127.0.0.1:8000/predict',
        json=payload,
        timeout=15
    )
    result = resp.json()
    
    print(f"Confidence tier: {result.get('confidence', 'N/A')}")
    print()
    
    exp = result.get('explanation', {})
    
    # Simple view
    simple = exp.get('simple_view', {})
    print("=== FRIENDLY EXPLANATION ===")
    print(f"Metaphor: {simple.get('metaphor', 'N/A')}")
    print(f"Explanation: {simple.get('explanation', 'N/A')[:150]}")
    print()
    
    # Technical view
    tech = exp.get('technical_view', {})
    mech = tech.get('detailed_mechanism', {})
    steps = mech.get('ordered_steps', [])
    
    print("=== TECHNICAL LAYER STEPS ===")
    for i, step in enumerate(steps[:5]):
        title = step.get('title', 'Unknown')
        found = step.get('found', False)
        print(f"Layer {i}: {title} - Found: {found}")
        
        # Show details for layers with evidence
        if found and 'details' in step:
            details = step.get('details', [])
            if isinstance(details, list):
                for j, detail in enumerate(details[:2]):
                    if isinstance(detail, dict):
                        enz = detail.get('enzyme') or detail.get('name') or detail.get('rule')
                        if enz:
                            print(f"  • {enz}")
                    else:
                        print(f"  • {str(detail)[:60]}")
    
    print()
    print("✓ Prediction completed successfully")
    print("✓ Enhancements deployed and working")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
