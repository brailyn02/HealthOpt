"""
Extract drugs list from keysentences training file
====================================================
Creates a drug list from unique drug IDs in train_keysentences_dedup.txt
"""

import csv
import pandas as pd
from collections import Counter

# Read the interaction file to get unique drug IDs
train_interactions = {}
with open('train_keysentences_dedup.txt', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line:
            parts = line.split()
            if parts:
                drug_id = int(parts[0])
                train_interactions[drug_id] = True

# Get all unique drug IDs
drug_ids = sorted(train_interactions.keys())

print(f"Found {len(drug_ids)} unique drugs in train_keysentences_dedup.txt")
print(f"Drug ID range: {min(drug_ids)} - {max(drug_ids)}")

# Create a basic drug list with just IDs and placeholder names
drugs_list = []
for drug_id in drug_ids:
    drugs_list.append({
        'drug_id': drug_id,
        'drug_name': f'Drug_{drug_id}',  # Placeholder
        'category': 'pharmaceutical'
    })

# Write to CSV
with open('drugs_keysentences.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['drug_id', 'drug_name', 'category'])
    writer.writeheader()
    writer.writerows(drugs_list)

print(f"\nWrote {len(drugs_list)} drugs to drugs_keysentences.csv")
