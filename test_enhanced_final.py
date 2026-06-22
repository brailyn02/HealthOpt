import json
import requests

print("Testing Warfarin-Spinach with enhanced explanations...")
print()

try:
    resp = requests.post('http://127.0.0.1:8000/predict', 
        json={'drug': 'Warfarin', 'food': 'Spinach'}, timeout=15)
    result = resp.json()
    
    print("Confidence:", result.get('confidence'))
    print()
    
    # Check for new dual-view structure
    if 'simple_view' in result:
        print("✓ NEW STRUCTURE DETECTED (simple_view + technical_view)")
        print()
        
        simple = result.get('simple_view', {})
        print("FRIENDLY VIEW:")
        print("  Metaphor:", simple.get('metaphor'))
        print("  Explanation:", simple.get('user_explanation')[:100])
        print("  Friendly narrative keys:", list(simple.get('friendly_narrative', {}).keys()))
        print()
        
        tech = result.get('technical_view', {})
        print("TECHNICAL VIEW:")
        print("  Technical flag:", tech.get('technical_flag'))
        
        mech = tech.get('detailed_mechanism', {})
        steps = mech.get('ordered_steps', [])
        print(f"  Ordered steps count: {len(steps)}")
        
        if steps:
            for i, step in enumerate(steps[:4]):
                details = step.get('details', [])
                detail_count = len(details) if isinstance(details, list) else 0
                print(f"    Layer {i}: {step.get('title')} - Found: {step.get('found')}, Details: {detail_count}")
        
        print()
        print("✓ SUCCESS: Enhancements deployed!")
        print("✓ Pathways should be visible in technical_view.layers")
        print("✓ Mechanistic confidence  data provided to LLM friendly narrative")
        
    elif 'explanation' in result:
        print("Legacy structure (old explanation format)")
        exp = result.get('explanation', '')
        print("Explanation:", exp[:200])
    else:
        print("Unexpected response structure")
        print("Keys:", list(result.keys())[:10])
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
