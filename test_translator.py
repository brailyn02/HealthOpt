#!/usr/bin/env python
from translator import create_dual_view

test_result = {
    'drug': 'Warfarin',
    'food': 'Grapefruit',
    'confidence': 'HIGH',
    'explanation': 'Test mechanism',
    'fusion_score': 0.77,
    'score': 0.77,
    'flags': [],
    'llm_compounds': None,
    'kge_enzymes': ['CYP3A4'],
    'lgn_score': 0.9,
    'physicochemical_warnings': [],
}

try:
    print("Testing translator...")
    result = create_dual_view(test_result)
    print('SUCCESS: Translator worked')
    print('Keys in result:', sorted([k for k in result.keys() if k in ['simple_view', 'technical_view']]))
    if 'simple_view' in result:
        print('simple_view:', result['simple_view'])
    if 'technical_view' in result:
        print('technical_view:', result['technical_view'])
except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
