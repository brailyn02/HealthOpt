"""
add_nutrient_drug_enz_edges.py
==============================
Adds 10 supplement-as-DRUG → ENZ edges to hkg_triplets.tsv
for the blood-test deficiency → supplement interaction pipeline.

Summary of what this adds:
  New DRUG nodes (6): Copper, Folic acid, Pyridoxal, Cholecalciferol, Retinol, Phylloquinone
  New ENZ nodes  (6): Hemoglobin, Ceruloplasmin, Methionine Synthase, ALAS1, Hepcidin, ALAD
  Existing nodes (used as-is):
    DRUG: Iron(62462), Cyanocobalamin(62113), Zinc(63168), Ascorbic acid(61915)
    ENZ:  MTHFR(64225), SLC11A2(64684), VKORC1(65054)

10 edges:
  1. DRUG:Iron             → binds       → ENZ:Hemoglobin
  2. DRUG:Copper           → activates   → ENZ:Ceruloplasmin
  3. DRUG:Cyanocobalamin   → binds       → ENZ:Methionine Synthase
  4. DRUG:Folic acid       → substrate_of → ENZ:MTHFR
  5. DRUG:Pyridoxal        → activates   → ENZ:ALAS1
  6. DRUG:Cholecalciferol  → inhibits    → ENZ:Hepcidin
  7. DRUG:Zinc             → activates   → ENZ:ALAD
  8. DRUG:Retinol          → modulates   → ENZ:Hepcidin
  9. DRUG:Ascorbic acid    → activates   → ENZ:SLC11A2   (zero new nodes)
 10. DRUG:Phylloquinone    → substrate_of → ENZ:VKORC1

After running, re-run scripts/prepare_hkg_training.py to rebuild KGE files.
"""

import csv
from pathlib import Path

TRIPLETS = Path("D:/23AIBox-DFinder/data/processed_hkg/hkg_triplets.tsv")
FIELDNAMES = ["head", "relation", "tail", "weight", "source", "head_type", "tail_type"]

# 10 edges — (head, relation, tail, head_type, tail_type)
NEW_EDGES = [
    # Edge 1 — Iron (already DRUG) → Hemoglobin (new ENZ)
    ("Iron",            "binds",        "Hemoglobin",          "DRUG", "TARGET"),
    # Edge 2 — Copper (new DRUG) → Ceruloplasmin (new ENZ)
    ("Copper",          "activates",    "Ceruloplasmin",        "DRUG", "TARGET"),
    # Edge 3 — Cyanocobalamin (already DRUG) → Methionine Synthase (new ENZ)
    ("Cyanocobalamin",  "binds",        "Methionine Synthase",  "DRUG", "TARGET"),
    # Edge 4 — Folic acid (new DRUG) → MTHFR (existing ENZ)
    ("Folic acid",      "substrate_of", "MTHFR",                "DRUG", "TARGET"),
    # Edge 5 — Pyridoxal (new DRUG) → ALAS1 (new ENZ)
    ("Pyridoxal",       "activates",    "ALAS1",                "DRUG", "TARGET"),
    # Edge 6 — Cholecalciferol (new DRUG) → Hepcidin (new ENZ)
    ("Cholecalciferol", "inhibits",     "Hepcidin",             "DRUG", "TARGET"),
    # Edge 7 — Zinc (already DRUG) → ALAD (new ENZ)
    ("Zinc",            "activates",    "ALAD",                 "DRUG", "TARGET"),
    # Edge 8 — Retinol (new DRUG) → Hepcidin (shared new ENZ from edge 6)
    ("Retinol",         "modulates",    "Hepcidin",             "DRUG", "TARGET"),
    # Edge 9 — Ascorbic acid (already DRUG) → SLC11A2 (existing ENZ) — ZERO new nodes
    ("Ascorbic acid",   "activates",    "SLC11A2",              "DRUG", "TARGET"),
    # Edge 10 — Phylloquinone (new DRUG) → VKORC1 (existing ENZ)
    ("Phylloquinone",   "substrate_of", "VKORC1",               "DRUG", "TARGET"),
]

rows_to_write = []
for head, rel, tail, htype, ttype in NEW_EDGES:
    rows_to_write.append({
        "head":      head,
        "relation":  rel,
        "tail":      tail,
        "weight":    "1.0",
        "source":    "nutrient_deficiency_curated",
        "head_type": htype,
        "tail_type": ttype,
    })

# Print plan clearly
print("=" * 65)
print("Nutrient supplement DRUG→ENZ edges to add:")
print("=" * 65)
new_drugs = {"Copper","Folic acid","Pyridoxal","Cholecalciferol","Retinol","Phylloquinone"}
new_enzymes = {"Hemoglobin","Ceruloplasmin","Methionine Synthase","ALAS1","Hepcidin","ALAD"}

for r in rows_to_write:
    h_flag  = " [NEW DRUG]" if r["head"] in new_drugs else ""
    t_flag  = " [NEW ENZ]"  if r["tail"] in new_enzymes else ""
    print(f"  DRUG:{r['head']}{h_flag}  →  {r['relation']}  →  ENZ:{r['tail']}{t_flag}")

print(f"\nNew DRUG nodes: {sorted(new_drugs)}")
print(f"New ENZ nodes:  {sorted(new_enzymes)}")
print(f"Total edges:    {len(rows_to_write)}")

# Append to TSV
with open(TRIPLETS, "a", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter="\t", lineterminator="\n")
    for row in rows_to_write:
        writer.writerow(row)

print(f"\n✓ {len(rows_to_write)} edges appended to {TRIPLETS.name}")
print("\nNext: run  python scripts/prepare_hkg_training.py  to rebuild KGE files.")
