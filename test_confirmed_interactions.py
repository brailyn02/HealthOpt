"""
Test confirmed (known) interactions to see layer scores and final tier
"""
import pandas as pd
from predict import DFinder
import json

# Load confirmed test pairs
test_pairs = pd.read_csv('validation_splits/validation_test_split.csv')

# Sample confirmed pairs (limit to first 20 for speed)
sample_pairs = test_pairs.head(20)

print('=' * 120)
print(f'TESTING {len(sample_pairs)} CONFIRMED INTERACTIONS')
print('=' * 120)

df_finder = DFinder()

results = []

for idx, row in sample_pairs.iterrows():
    drug = row['drug_name']
    food = row['food_name']
    source = row['verdict']
    
    try:
        result = df_finder.predict(drug, food)
        
        # Extract scores
        graph_score = float(result.get('graph_score', 0) or 0)
        kge_score = float(result.get('kge_score', 0) or 0)
        lgn_score = float(result.get('lgn_score', 0) or 0)
        fusion_score = float(result.get('fusion_score', result.get('score', 0)) or 0)
        tier = result.get('tier', result.get('confidence', 'UNKNOWN'))
        
        results.append({
            'drug': drug,
            'food': food,
            'source': source,
            'graph': graph_score,
            'kge': kge_score,
            'lgn': lgn_score,
            'fusion': fusion_score,
            'tier': tier,
        })
        
        print(f"\n{idx+1}. {drug:20s} × {food:20s} [{source}]")
        print(f"   Graph: {graph_score:6.2f} | KGE: {kge_score:6.2f} | LGN: {lgn_score:6.3f} | Fusion: {fusion_score:6.4f}")
        print(f"   TIER: {tier}")
        
    except Exception as e:
        print(f"\n{idx+1}. {drug:20s} × {food:20s} - ERROR: {str(e)[:60]}")

# Summary statistics
df_results = pd.DataFrame(results)

print('\n' + '=' * 120)
print('SUMMARY STATISTICS: CONFIRMED INTERACTION SCORING')
print('=' * 120)

print(f'\nTotal tested: {len(df_results)}')
print(f'\nTier distribution:')
for tier in sorted(df_results['tier'].unique()):
    count = len(df_results[df_results['tier'] == tier])
    pct = 100 * count / len(df_results)
    print(f'  {tier:15s}: {count:2d} ({pct:5.1f}%)')

print(f'\nScore statistics (normalized to [0,1]):')
print(f'  Graph:  mean={df_results["graph"].mean()/120:.3f}  min={df_results["graph"].min()/120:.3f}  max={df_results["graph"].max()/120:.3f}')
print(f'  KGE:    mean={df_results["kge"].mean()/115:.3f}  min={df_results["kge"].min()/115:.3f}  max={df_results["kge"].max()/115:.3f}')
print(f'  LGN:    mean={df_results["lgn"].mean():.3f}  min={df_results["lgn"].min():.3f}  max={df_results["lgn"].max():.3f}')
print(f'  Fusion: mean={df_results["fusion"].mean():.3f}  min={df_results["fusion"].min():.3f}  max={df_results["fusion"].max():.3f}')

print(f'\nHow many confirmed pairs score in each layer:')
graph_found = len(df_results[df_results['graph'] > 0])
kge_found = len(df_results[df_results['kge'] > 0])
lgn_found = len(df_results[df_results['lgn'] > 0])
print(f'  Graph found signal:  {graph_found}/{len(df_results)} ({100*graph_found/len(df_results):.1f}%)')
print(f'  KGE found signal:    {kge_found}/{len(df_results)} ({100*kge_found/len(df_results):.1f}%)')
print(f'  LGN found signal:    {lgn_found}/{len(df_results)} ({100*lgn_found/len(df_results):.1f}%)')

# Find "weak" confirmed pairs (ones scoring LOW when they should be HIGH)
low_tier_confirmed = df_results[df_results['tier'] == 'LOW']
if len(low_tier_confirmed) > 0:
    print(f'\n⚠️  WARNING: {len(low_tier_confirmed)} confirmed pairs scored only LOW tier:')
    for _, row in low_tier_confirmed.iterrows():
        print(f'   {row["drug"]:20s} × {row["food"]:20s}: G={row["graph"]:.1f} K={row["kge"]:.1f} L={row["lgn"]:.3f} F={row["fusion"]:.3f}')

# Find "insufficient" confirmed pairs (should never happen)
insuff_confirmed = df_results[df_results['tier'] == 'INSUFFICIENT']
if len(insuff_confirmed) > 0:
    print(f'\n❌ CRITICAL: {len(insuff_confirmed)} confirmed pairs scored INSUFFICIENT tier:')
    for _, row in insuff_confirmed.iterrows():
        print(f'   {row["drug"]:20s} × {row["food"]:20s}: G={row["graph"]:.1f} K={row["kge"]:.1f} L={row["lgn"]:.3f} F={row["fusion"]:.3f}')
