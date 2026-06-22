import json
import traceback
import sys
from pathlib import Path

# ensure repo root is on sys.path so `from predict import DFinder` works
sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from predict import DFinder
except Exception as e:
    print('IMPORT_ERROR', e)
    traceback.print_exc()
    raise


def main():
    csvp = Path('validation_splits/validation_unseen.csv')
    if not csvp.exists():
        print('MISSING_CSV', csvp)
        return
    import csv
    with csvp.open() as f:
        reader = csv.DictReader(f)
        row = next(reader, None)
    if not row:
        print('CSV_EMPTY')
        return
    drug = row.get('drug_name') or row.get('drug') or row.get('drug_name')
    food = row.get('food_name') or row.get('food')
    print('Testing pair:', drug, '|', food)
    try:
        df = DFinder(verbose=False)
        res = df.predict(drug, food)
        print(json.dumps(res, default=str, indent=2))
    except Exception as e:
        print('PREDICT_ERROR', e)
        traceback.print_exc()


if __name__ == '__main__':
    main()
