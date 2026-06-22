"""Check supplement availability as drugs in LightGCN and HKG train datasets."""
import csv
import re

# ── 1. Load LightGCN drug names ──────────────────────────────────────────────
lgcn_drugs = {}  # name.lower() -> name
with open(r"D:\23AIBox-DFinder\DFinder-main\data\unified-DFI\id_maps\drug_id_map.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        lgcn_drugs[row["name"].lower()] = row["name"]

# ── 2. Load HKG DRUG: entity names ───────────────────────────────────────────
hkg_drugs = {}  # name.lower() -> name
with open(r"D:\23AIBox-DFinder\data\processed_hkg\kge_input\entity2id.txt", encoding="utf-8") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if parts[0].startswith("DRUG:"):
            name = parts[0][5:]
            hkg_drugs[name.lower()] = name

print(f"LightGCN drug vocab: {len(lgcn_drugs):,}")
print(f"HKG DRUG vocab:      {len(hkg_drugs):,}")

# ── 3. Supplement list ────────────────────────────────────────────────────────
supplements = {
    "Iron Supplements": [
        "Ferrous Sulfate", "Ferrous Gluconate", "Ferrous Fumarate",
        "Ferrous Bisglycinate", "Carbonyl Iron", "Polysaccharide Iron Complex",
        "Heme Iron Polypeptide", "Sucrosomial Iron", "Ferric Maltol",
        "Ferric Citrate", "Iron Protein Succinylate", "Iron Sucrose",
        "Ferric Carboxymaltose", "Iron Dextran", "Ferumoxytol",
    ],
    "Vitamin B12": [
        "Cyanocobalamin", "Methylcobalamin", "Adenosylcobalamin", "Hydroxocobalamin",
    ],
    "Folate (B9)": [
        "Folic Acid", "5-Methyltetrahydrofolate", "L-Methylfolate",
        "Folinic Acid", "Leucovorin",
    ],
    "Vitamin D3": [
        "Cholecalciferol", "Calciol",
    ],
    "Zinc": [
        "Zinc Gluconate", "Zinc Sulfate", "Zinc Picolinate",
        "Zinc Bisglycinate", "Zinc Citrate", "Zinc Oxide",
    ],
    "Magnesium": [
        "Magnesium Glycinate", "Magnesium Citrate", "Magnesium Malate",
        "Magnesium Taurate", "Magnesium Orotate", "Magnesium Chloride",
        "Magnesium Oxide",
    ],
    "Vitamin C": [
        "Ascorbic Acid", "Calcium Ascorbate", "Sodium Ascorbate",
    ],
    "Vitamin K": [
        "Phylloquinone", "Phytonadione", "Menaquinone-4", "MK-4",
        "Menaquinone-7", "MK-7",
    ],
    "Copper & Trace Minerals": [
        "Copper Gluconate", "Cupric Oxide", "Copper Chelates", "Cupric Sulfate",
        "Selenomethionine", "Sodium Selenite",
    ],
    "B-Vitamins": [
        "Pyridoxine", "Pyridoxal-5-Phosphate", "Pyridoxine Hydrochloride",
        "Riboflavin", "Riboflavin-5-Phosphate",
        "Thiamine", "Benfotiamine",
        "Niacin", "Nicotinamide", "Nicotinic Acid",
        "Pantothenic Acid", "Pantethine",
        "Biotin",
    ],
    "Vitamins A & E": [
        "Retinol", "Retinyl Palmitate", "Beta-Carotene",
        "Alpha-Tocopherol", "Tocotrienols",
    ],
}

def find_match(name, vocab):
    """Exact match, then word-boundary prefix (must be >= 6 chars to avoid 'Fe', 'Ca' etc.)."""
    key = name.lower()
    if key in vocab:
        return vocab[key]
    # Prefix match only when name is long enough to avoid short false-positives
    if len(key) >= 7:
        for k, v in vocab.items():
            if k.startswith(key) or (key.startswith(k) and len(k) >= 7):
                return v
    return None

# ── 4. Check & print ─────────────────────────────────────────────────────────
print()
print("=" * 72)
print(f"{'Supplement':<35} {'LightGCN':^12} {'HKG':^12}")
print("=" * 72)

summary = {"both": [], "lgcn_only": [], "hkg_only": [], "neither": []}

for group, names in supplements.items():
    print(f"\n  ── {group} ──")
    for name in names:
        l = find_match(name, lgcn_drugs)
        h = find_match(name, hkg_drugs)
        l_str = f"✓ ({l[:18]})" if l else "✗"
        h_str = f"✓ ({h[:18]})" if h else "✗"
        print(f"  {name:<35} {l_str:<20} {h_str}")
        if l and h:     summary["both"].append(name)
        elif l:         summary["lgcn_only"].append(name)
        elif h:         summary["hkg_only"].append(name)
        else:           summary["neither"].append(name)

# ── 5. Summary ────────────────────────────────────────────────────────────────
print()
print("=" * 72)
print("SUMMARY")
print("=" * 72)
print(f"  In BOTH datasets:     {len(summary['both'])}")
print(f"  LightGCN only:        {len(summary['lgcn_only'])}")
print(f"  HKG only:             {len(summary['hkg_only'])}")
print(f"  Not in either:        {len(summary['neither'])}")

if summary["neither"]:
    print(f"\n  Missing from BOTH:")
    for n in summary["neither"]:
        print(f"    ✗ {n}")

if summary["lgcn_only"]:
    print(f"\n  LightGCN-only (not in HKG):")
    for n in summary["lgcn_only"]:
        print(f"    → {n}")

if summary["hkg_only"]:
    print(f"\n  HKG-only (not in LightGCN):")
    for n in summary["hkg_only"]:
        print(f"    → {n}")
