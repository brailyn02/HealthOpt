import os
import csv
from multiprocessing import Pool, cpu_count
from pathlib import Path
import pandas as pd

UNSEEN = Path('validation_splits/validation_unseen.csv')
OUT = Path('validation_splits/phase5_fusion_results_exact.csv')
CHUNKSIZE = 4

rows_df = pd.read_csv(UNSEEN)
rows = rows_df.to_dict('records')
TOTAL = len(rows)

n_workers = min(4, max(1, cpu_count() - 1))
print('Loaded', TOTAL, 'pairs; using', n_workers, 'workers')

# initializer: load heavy models once per worker
def init_worker():
    global DF
    from predict import DFinder
    # verbose=False to reduce logging and LLM augmentation cost
    DF = DFinder(verbose=False)
    print('Worker', os.getpid(), 'initialized')


def worker(row):
    try:
        drug = str(row.get('drug_name') or row.get('drug') or row.get('drug_id'))
        food = str(row.get('food_name') or row.get('food') or row.get('food_id'))
        r = DF.predict(drug, food)
        out = {
            'drug': r.get('drug'),
            'food': r.get('food'),
            'fusion_score': r.get('fusion_score'),
            'confidence': r.get('confidence'),
            'flags': '|'.join(r.get('flags') or []),
            'graph_found': r.get('graph_found'),
            'graph_score': r.get('graph_score'),
            'graph_enzymes': ','.join(r.get('graph_enzymes') or []),
            'kge_found': r.get('kge_found'),
            'kge_score': r.get('kge_score'),
            'kge_enzymes': ','.join(r.get('kge_enzymes') or []),
            'lgn_score': r.get('lgn_score'),
            'norm_graph': r.get('norm_graph'),
            'norm_kge': r.get('norm_kge'),
            'norm_lgn': r.get('norm_lgn'),
            'mechanistic_support': r.get('mechanistic_support'),
            'mechanistic_support_details': r.get('mechanistic_support_details'),
            'physicochemical_warnings': '|'.join(r.get('physicochemical_warnings') or []),
            'explanation': (r.get('explanation') or '').replace('\n', ' '),
        }
        return out
    except Exception as e:
        return {'drug': row.get('drug_name'), 'food': row.get('food_name'), 'error': str(e)}

# Write header if not exists
fieldnames = [
    'drug','food','fusion_score','confidence','flags',
    'graph_found','graph_score','graph_enzymes',
    'kge_found','kge_score','kge_enzymes','lgn_score',
    'norm_graph','norm_kge','norm_lgn','mechanistic_support',
    'mechanistic_support_details','physicochemical_warnings','explanation','error'
]

# Remove existing OUT to start fresh
if OUT.exists():
    OUT.unlink()

with Pool(processes=n_workers, initializer=init_worker) as p:
    it = p.imap(worker, rows, chunksize=CHUNKSIZE)
    with OUT.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, res in enumerate(it, 1):
            # normalize keys: ensure all fieldnames present
            row = {k: res.get(k) if isinstance(res, dict) else None for k in fieldnames}
            writer.writerow(row)
            if i % 20 == 0 or i == TOTAL:
                print(f'WROTE {i}/{TOTAL} rows')

print('Completed. Output:', OUT)
