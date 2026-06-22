"""
reclassify_endogenous_subsets.py
---------------------------------
Reclassifies three subsets of Endogenous Metabolite entries that have clear
dietary / drug-interaction relevance:

  GROUP 1 — Pressor Amines         → Dietary Amine
      Dopamine, Serotonin, Epinephrine, N-Acetyldopamine, 5-Hydroxydopamine
      Rationale: present in food; cause hypertensive crises with MAOIs.

  GROUP 2 — Eicosanoids / Oxylipins → Food Bioactive
      Prostaglandins, Leukotrienes, HETEs, HPETEs, KETEs, Lipoxin
      Rationale: exogenous intake is a data point for NSAID / blood-thinner
      interactions in clinical DFI modelling.

  GROUP 3 — Purines & Nucleotide Cofactors → Food Bioactive
      ATP, ADP, AMP, GDP, NAD(P)(H), FAD, FMN, UTP, UDP, CTP,
      DCMP, DUMP, DTMP, DTTP, DGTP, cyclic-AMP, ADP-Ribose,
      Phosphoribosyl-ATP
      Rationale: dietary purines break down to uric acid; relevant for
      Allopurinol interactions and gout management.

All other Endogenous Metabolite entries (pure signalling proteins, steroid
hormones with no dietary source, etc.) are left unchanged.

Writes:
  generated/unified_food_master_typed.txt  (updated in-place)
  generated/endogenous_reclassify_report.txt
"""

MASTER = r"d:\23AIBox-DFinder\generated\unified_food_master_typed.txt"
REPORT = r"d:\23AIBox-DFinder\generated\endogenous_reclassify_report.txt"

# ── reclassification targets (lowercased canonical names) ─────────────────────

PRESSOR_AMINES = {
    "dopamine",
    "serotonin",
    "epinephrine",
    "n-acetyldopamine",
    "5-hydroxydopamine",
    # tyramine and histamine are already Food Bioactive — correctly typed
}

EICOSANOIDS = {
    "prostaglandin f2a",
    "prostaglandin h2",
    "leukotriene d4",
    "12(s)-leukotriene b4",
    "lipoxin b4",
    "5-hete",
    "12(s)-hpete",
    "15-kete",
    "15-hete",
}

PURINES_NUCLEOTIDES = {
    # adenine nucleotides
    "atp",
    "adp",
    "amp",
    "cyclic-amp",
    "adp-ribose",
    "phosphoribosyl-atp",
    # guanine nucleotides
    "gdp",
    # pyrimidine nucleotides (all dietary purine / cofactor relevance)
    "utp",
    "udp",
    "ctp",
    "dcmp",
    "dump",
    "dtmp",
    "dttp",
    "dgtp",
    # nicotinamide / flavin cofactors derived from dietary B-vitamins
    "nad",
    "nad+",
    "nadp+",
    "fad",
    "fmn",
    # coenzyme a — derived from pantothenate (Vitamin B5), dietary
    "coenzyme a",
    "cob(i)alamin",   # reduced cobalamin, derived from dietary B12
}

# ── load master ───────────────────────────────────────────────────────────────
rows = []
with open(MASTER, encoding="utf-8") as fh:
    for line in fh:
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 3:
            rows.append(parts)

# ── apply reclassification ────────────────────────────────────────────────────
changes = []

for row in rows:
    if row[2] != "Endogenous Metabolite":
        continue
    nl = row[1].strip().lower()
    if nl in PRESSOR_AMINES:
        new_type = "Dietary Amine"
    elif nl in EICOSANOIDS:
        new_type = "Food Bioactive"
    elif nl in PURINES_NUCLEOTIDES:
        new_type = "Food Bioactive"
    else:
        continue
    changes.append((int(row[0]), row[1], row[2], new_type))
    row[2] = new_type

# ── write updated master ──────────────────────────────────────────────────────
with open(MASTER, "w", encoding="utf-8") as fh:
    for row in rows:
        fh.write("\t".join(row) + "\n")

# ── report ────────────────────────────────────────────────────────────────────
from collections import defaultdict, Counter
by_new = defaultdict(list)
for fid, name, old, new in changes:
    by_new[new].append((fid, name))

final_types = Counter(r[2] for r in rows)

report_lines = [
    "=== Endogenous Metabolite Subset Reclassification ===\n\n",
    f"Total entries changed: {len(changes)}\n\n",
]
for new_type, items in sorted(by_new.items()):
    report_lines.append(f"--- → {new_type} ({len(items)}) ---\n")
    for fid, name in sorted(items, key=lambda x: x[0]):
        report_lines.append(f"  [{fid}] {name}\n")
    report_lines.append("\n")

report_lines.append("--- Final type distribution ---\n")
for t, c in sorted(final_types.items()):
    report_lines.append(f"  {t:<40s} {c:>5}\n")

with open(REPORT, "w", encoding="utf-8") as fh:
    fh.writelines(report_lines)

print(f"Changed: {len(changes)} entries")
for new_type, items in sorted(by_new.items()):
    print(f"  → {new_type}: {len(items)}")
print("\nFinal type distribution:")
for t, c in sorted(final_types.items()):
    print(f"  {t:<40s} {c:>5}")
print(f"\nReport: {REPORT}")
