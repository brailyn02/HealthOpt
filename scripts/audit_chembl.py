"""Audit ChEMBL 36 SQLite and auxiliary files for HKG Layer 2 usefulness."""
import sqlite3, os, re

# ── 1. chemreps file ──────────────────────────────────────────────────────────
reps_path = r"D:/23AIBox-DFinder/chembl_36_chemreps.txt/chembl_36_chemreps.txt"
with open(reps_path) as f:
    lines = f.readlines()
print(f"chemreps lines: {len(lines):,}")
print(f"Header: {lines[0].strip()}")
print(f"Sample: {lines[1][:100]}")
print()

# ── 2. UniProt mapping ────────────────────────────────────────────────────────
uni_path = r"D:/23AIBox-DFinder/chembl_uniprot_mapping.txt"
with open(uni_path) as f:
    uni_lines = [l for l in f if not l.startswith("#")]
print(f"uniprot_mapping lines: {len(uni_lines):,}")

cyp_rows = [l for l in uni_lines if re.search(
    r"CYP|cytochrome|P-glyco|ABCB1|ABCG2|SLCO|UGT|transporter", l, re.I)]
print(f"CYP/transporter targets: {len(cyp_rows):,}")
print("Samples:")
for r in cyp_rows[:12]:
    print(" ", r.strip())
print()

# ── 3. SQLite tables ──────────────────────────────────────────────────────────
db_path = r"D:/23AIBox-DFinder/chembl_36_sqlite/chembl_36/chembl_36_sqlite/chembl_36.db"
print(f"DB size: {os.path.getsize(db_path)/1e9:.1f} GB")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

tables = cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()
print(f"Tables ({len(tables)}):")
for (t,) in tables:
    cnt = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t:45s}: {cnt:>10,}")

# ── 4. Key tables for Layer 2 ─────────────────────────────────────────────────
print("\n\n=== ACTIVITIES table (compound→assay→target) ===")
cols = [r[1] for r in cur.execute("PRAGMA table_info(activities)").fetchall()]
print("Columns:", cols)
sample = cur.execute("""
    SELECT a.molregno, a.assay_id, a.standard_type, a.standard_relation,
           a.standard_value, a.standard_units, a.activity_comment
    FROM activities a LIMIT 5
""").fetchall()
for row in sample:
    print(" ", row)

print("\n\n=== ASSAYS table ===")
cols = [r[1] for r in cur.execute("PRAGMA table_info(assays)").fetchall()]
print("Columns:", cols[:15])

print("\n\n=== TARGET_DICTIONARY ===")
cols = [r[1] for r in cur.execute("PRAGMA table_info(target_dictionary)").fetchall()]
print("Columns:", cols)
cyp_targets = cur.execute("""
    SELECT chembl_id, pref_name, target_type, organism
    FROM target_dictionary
    WHERE pref_name LIKE '%CYP%' OR pref_name LIKE '%cytochrome%'
       OR pref_name LIKE '%P-glycoprotein%' OR pref_name LIKE '%ABCB1%'
    LIMIT 20
""").fetchall()
print(f"CYP/P-gp targets: {len(cyp_targets)}")
for row in cyp_targets[:15]:
    print(" ", row)

# ── 5. Pipeline: compound SMILES → CYP IC50/Ki assays ────────────────────────
print("\n\n=== CYP3A4 inhibition assays count ===")
cyp3a4 = cur.execute("""
    SELECT COUNT(DISTINCT a.molregno)
    FROM activities a
    JOIN assays ass ON a.assay_id = ass.assay_id
    JOIN target_dictionary td ON ass.tid = td.tid
    WHERE (td.pref_name LIKE '%CYP3A4%' OR td.pref_name LIKE '%3A4%')
      AND a.standard_type IN ('IC50','Ki','Inhibition','pIC50','pKi')
      AND a.standard_value IS NOT NULL
""").fetchone()[0]
print(f"  Unique compounds with CYP3A4 inhibition data: {cyp3a4:,}")

cyp_all = cur.execute("""
    SELECT td.pref_name, COUNT(DISTINCT a.molregno) as n_compounds,
           COUNT(*) as n_assays
    FROM activities a
    JOIN assays ass ON a.assay_id = ass.assay_id
    JOIN target_dictionary td ON ass.tid = td.tid
    WHERE (td.pref_name LIKE '%CYP%' OR td.pref_name LIKE '%cytochrome P450%')
      AND a.standard_type IN ('IC50','Ki','Inhibition','pIC50','pKi','Potency')
      AND a.standard_value IS NOT NULL
      AND td.organism = 'Homo sapiens'
    GROUP BY td.pref_name
    ORDER BY n_compounds DESC
    LIMIT 15
""").fetchall()
print("\n  Human CYP targets with inhibition data:")
for row in cyp_all:
    print(f"    {row[0]:50s}: {row[1]:6,} compounds,  {row[2]:7,} assays")

# ── 6. Cross-match: FooDB SMILES vs ChEMBL chemreps ─────────────────────────
print("\n\n=== Cross-match FooDB compound names vs ChEMBL preferred names ===")
import pandas as pd
foodb = pd.read_csv(r"D:/23AIBox-DFinder/Compound.csv",
    usecols=["id","name","cas_number"], dtype=str, low_memory=False)
foodb_names = set(foodb["name"].str.lower().str.strip().dropna())

chembl_names = cur.execute(
    "SELECT molregno, chembl_id FROM molecule_dictionary WHERE pref_name IS NOT NULL"
).fetchall()
chembl_name_map = {}
for molregno, chembl_id in chembl_names:
    row = cur.execute(
        "SELECT pref_name FROM molecule_dictionary WHERE molregno=?", (molregno,)
    ).fetchone()
    if row:
        chembl_name_map[row[0].lower().strip()] = (molregno, chembl_id)

overlap = foodb_names & set(chembl_name_map.keys())
print(f"  FooDB compounds: {len(foodb_names):,}")
print(f"  ChEMBL molecules with names: {len(chembl_name_map):,}")
print(f"  NAME OVERLAP: {len(overlap):,} compounds")
print("  Examples:", list(overlap)[:20])

conn.close()
print("\n✓ Audit complete.")
