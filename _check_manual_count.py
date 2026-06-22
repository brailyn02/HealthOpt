"""
Check why thesis says 292 manual compounds but we count 136 unique.
Possibility: thesis counted total compounds across all dishes (with duplicates)
"""
import json
from pathlib import Path

NA_FILE = Path(__file__).resolve().parent / "data" / "na_dish_compounds.json"

with open(NA_FILE, encoding="utf-8") as f:
    data = json.load(f)

unique_compounds = set()
total_with_duplicates = 0

for dish, compounds in data.items():
    total_with_duplicates += len(compounds)
    for c in compounds:
        unique_compounds.add(c.lower())

print(f"Dishes: {len(data)}")
print(f"Total compounds (with duplicates across dishes): {total_with_duplicates}")
print(f"Unique compounds (deduplicated): {len(unique_compounds)}")
print(f"\nThesis likely used the with-duplicates count: {total_with_duplicates}")
