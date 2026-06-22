"""
Check coverage of drugs extracted from dfi_interactions_from_keysentences.csv
against drugs_cleaned_final.csv and drugs_cleaned_with_categories.csv.
Outputs a detailed report.
"""
import csv
from pathlib import Path

root = Path(r'd:/23AIBox-DFinder')
out_dir = root / 'generated'
out_dir.mkdir(exist_ok=True)
report_path = out_dir / 'drug_coverage_report.txt'

def load_col_set(path, col):
    names = set()
    with path.open(encoding='utf-8', errors='ignore') as f:
        for row in csv.DictReader(f):
            v = (row.get(col) or '').strip().lower()
            if v:
                names.add(v)
    return names

def load_first_col_set(path):
    """Read drugs_cleaned_final where drug name is in first column (drug_id)."""
    names = set()
    with path.open(encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if row:
                v = row[0].strip().lower()
                if v:
                    names.add(v)
    return names, header

# ── Load sets ──────────────────────────────────────────────────────────────
# 1. All unique drug names mentioned in DFI key-sentences (source of truth)
dfi_drugs = load_col_set(root / 'dfi_interactions_from_keysentences.csv', 'drug')

# 2. drugs_cleaned_final (first column is the drug name)
cleaned_final_set, cleaned_final_header = load_first_col_set(root / 'drugs_cleaned_final.csv')

# 3. drugs_cleaned_with_categories (drug_name column, numeric drug_id)
with_cats_set = load_col_set(root / 'drugs_cleaned_with_categories.csv', 'drug_name')

# ── Comparisons ────────────────────────────────────────────────────────────
# a) DFI drugs vs drugs_cleaned_final
dfi_in_final     = dfi_drugs & cleaned_final_set
dfi_not_in_final = dfi_drugs - cleaned_final_set

# b) drugs_cleaned_final vs drugs_cleaned_with_categories
final_in_wcats    = cleaned_final_set & with_cats_set
final_not_in_wcats = cleaned_final_set - with_cats_set

# c) DFI drugs directly vs drugs_cleaned_with_categories
dfi_in_wcats     = dfi_drugs & with_cats_set
dfi_not_in_wcats = dfi_drugs - with_cats_set

# ── Write report ───────────────────────────────────────────────────────────
lines = []
def h(title): lines.append(f"\n{'='*60}\n{title}\n{'='*60}")

h("DATASET SIZES")
lines.append(f"  DFI key-sentences unique drugs    : {len(dfi_drugs)}")
lines.append(f"  drugs_cleaned_final unique entries : {len(cleaned_final_set)}  (header: {cleaned_final_header})")
lines.append(f"  drugs_cleaned_with_categories      : {len(with_cats_set)}")

h("A) DFI drugs vs drugs_cleaned_final")
lines.append(f"  DFI drugs present in cleaned_final  : {len(dfi_in_final)}")
lines.append(f"  DFI drugs MISSING from cleaned_final: {len(dfi_not_in_final)}")
if dfi_not_in_final:
    lines.append("  Missing list (first 100):")
    for n in sorted(dfi_not_in_final)[:100]:
        lines.append(f"    {n}")

h("B) drugs_cleaned_final vs drugs_cleaned_with_categories")
lines.append(f"  cleaned_final present in with_categories  : {len(final_in_wcats)}")
lines.append(f"  cleaned_final MISSING from with_categories: {len(final_not_in_wcats)}")
if final_not_in_wcats:
    lines.append("  Missing list (first 100):")
    for n in sorted(final_not_in_wcats)[:100]:
        lines.append(f"    {n}")

h("C) DFI drugs directly vs drugs_cleaned_with_categories")
lines.append(f"  DFI drugs present in with_categories  : {len(dfi_in_wcats)}")
lines.append(f"  DFI drugs MISSING from with_categories: {len(dfi_not_in_wcats)}")
if dfi_not_in_wcats:
    lines.append("  Missing list (first 100):")
    for n in sorted(dfi_not_in_wcats)[:100]:
        lines.append(f"    {n}")

h("SUMMARY")
lines.append(f"  DFI unique drugs: {len(dfi_drugs)}")
lines.append(f"  Covered by drugs_cleaned_with_categories: {len(dfi_in_wcats)} ({100*len(dfi_in_wcats)/len(dfi_drugs):.1f}%)")
lines.append(f"  NOT covered (these would be missing from training): {len(dfi_not_in_wcats)}")

report_text = "\n".join(lines)
report_path.write_text(report_text, encoding='utf-8')
print(report_text)
print(f"\nFull report saved to: {report_path}")
