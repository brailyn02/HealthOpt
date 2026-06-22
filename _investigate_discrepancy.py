"""
Investigate 305 vs 194 runtime discrepancy by comparing:
1. LLM cache state vs validation CSV
2. Check if cache was modified after validation
3. Re-run validate_wrapper_b.py to see current output
"""
import json
import pandas as pd
from pathlib import Path
import os
from datetime import datetime

ROOT = Path(__file__).resolve().parent
LLM_CACHE = ROOT / "data" / "llm_food_cache.json"
VALIDATION_CSV = ROOT / "ablation_results" / "wrapper_b_runtime_vs_manual_compound_level.csv"
VALIDATION_SUMMARY = ROOT / "ablation_results" / "wrapper_b_runtime_validation_summary.txt"

print("=" * 60)
print("INVESTIGATING 305 vs 194 DISCREPANCY")
print("=" * 60)

# Check file modification times
if LLM_CACHE.exists():
    cache_mtime = datetime.fromtimestamp(LLM_CACHE.stat().st_mtime)
    print(f"\nLLM cache file: {LLM_CACHE}")
    print(f"Last modified: {cache_mtime}")
    
    with open(LLM_CACHE, encoding="utf-8") as f:
        cache = json.load(f)
    print(f"Cache entries: {len(cache)}")
    
    # Count total compounds in cache
    cache_compounds = 0
    for dish, compounds in cache.items():
        cache_compounds += len(compounds)
    print(f"Total compounds in cache: {cache_compounds}")
else:
    print(f"\nLLM cache file not found: {LLM_CACHE}")

if VALIDATION_CSV.exists():
    csv_mtime = datetime.fromtimestamp(VALIDATION_CSV.stat().st_mtime)
    print(f"\nValidation CSV: {VALIDATION_CSV}")
    print(f"Last modified: {csv_mtime}")
    
    df = pd.read_csv(VALIDATION_CSV)
    runtime_rows = df[df['source'] == 'runtime']
    print(f"Runtime rows in CSV: {len(runtime_rows)}")
    print(f"Unique runtime compounds in CSV: {runtime_rows['compound'].nunique()}")
else:
    print(f"\nValidation CSV not found: {VALIDATION_CSV}")

if VALIDATION_SUMMARY.exists():
    summary_mtime = datetime.fromtimestamp(VALIDATION_SUMMARY.stat().st_mtime)
    print(f"\nValidation summary: {VALIDATION_SUMMARY}")
    print(f"Last modified: {summary_mtime}")
    print(f"\n--- SUMMARY CONTENT ---")
    with open(VALIDATION_SUMMARY, encoding="utf-8") as f:
        print(f.read())

# Compare timestamps
if LLM_CACHE.exists() and VALIDATION_CSV.exists():
    if cache_mtime > csv_mtime:
        print(f"\n⚠️  LLM cache was modified AFTER validation CSV was created")
        print(f"    This explains the discrepancy - cache has been updated since validation")
    else:
        print(f"\n✓ LLM cache was modified BEFORE validation CSV was created")
        print(f"    Discrepancy must be due to other factors")
