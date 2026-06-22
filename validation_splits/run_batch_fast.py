import csv
import json
import sys
import time
import traceback
from pathlib import Path
from multiprocessing import Pool, cpu_count

# Ensure repo root on path
sys.path.append(str(Path(__file__).resolve().parents[1]))

OUT = Path('validation_splits/phase5_fusion_results_exact.csv')
UNSEEN = Path('validation_splits/validation_unseen.csv')
ERR = Path('validation_splits/phase5_errors.log')

from predict import DFinder

FIELDNAMES = [
    'drug','food','fusion_score','confidence','flags',
    'graph_found','graph_score','graph_enzymes',
    'kge_found','kge_score','kge_enzymes',
    'lgn_score','norm_graph','norm_kge','norm_lgn',
    'mechanistic_support','mechanistic_support_details','physicochemical_warnings','explanation'
]


def init_worker():
    global DF
    DF = DFinder(verbose=False)


def worker(row):
    try:
        drug = row.get('drug_name') or row.get('drug') or row.get('drug_input')
        food = row.get('food_name') or row.get('food') or row.get('food_input')
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
            'mechanistic_support_details': json.dumps(r.get('mechanistic_support_details') or {}),
            'physicochemical_warnings': json.dumps(r.get('physicochemical_warnings') or []),
            'explanation': r.get('explanation') or ''
        }
        return out
    except Exception as e:
        return {'drug': row.get('drug_name'), 'food': row.get('food_name'), 'error': str(e), 'traceback': traceback.format_exc()}


def main():
    if not UNSEEN.exists():
        print('Missing input CSV:', UNSEEN)
        return
    with UNSEEN.open() as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    total = len(rows)
    n_workers = min(4, max(1, cpu_count()-1))
    print('Starting batch with', n_workers, 'workers for', total, 'pairs')

    # prepare output file
    if not OUT.exists():
        with OUT.open('w', newline='', encoding='utf-8') as outf:
            writer = csv.DictWriter(outf, fieldnames=FIELDNAMES)
            writer.writeheader()

    processed = 0
    start = time.time()
    with Pool(processes=n_workers, initializer=init_worker) as p:
        for res in p.imap_unordered(worker, rows, chunksize=4):
            processed += 1
            if 'error' in res:
                with ERR.open('a', encoding='utf-8') as ef:
                    ef.write(json.dumps(res) + '\n')
            else:
                with OUT.open('a', newline='', encoding='utf-8') as outf:
                    writer = csv.DictWriter(outf, fieldnames=FIELDNAMES)
                    writer.writerow(res)
            if processed % 20 == 0 or processed == total:
                elapsed = time.time() - start
                print(f'Progress: {processed}/{total} ({processed/total:.1%}) elapsed {elapsed:.0f}s')
    print('Batch completed. Wrote', OUT)


if __name__ == '__main__':
    main()
