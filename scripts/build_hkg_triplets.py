"""
build_hkg_triplets.py
=====================
Builds the master Heterogeneous Knowledge Graph (HKG) triplet file for Phase 2
(Mechanism-Aware DFinder). Runs on the mechanism-hkg git branch only.

Output: data/processed_hkg/hkg_triplets.tsv
Columns: head | relation | tail | weight | source | head_type | tail_type

Node types : [FOOD] [COMPOUND] [TARGET] [DRUG]
Relations  : contains | inhibits | induces | substrate_of | metabolizes

Steps:
  1. Compound --> CYP/Transporter  (ChEMBL 36 SQLite, InChIKey match)
  2. Food --> Compound             (FooDB Content.csv, concentration weight)
  3. Drug --> CYP/Transporter     (DrugBank extracted enzymes CSV)
  4. Merge --> hkg_triplets.tsv

Usage:
    cd D:/23AIBox-DFinder
    python scripts/build_hkg_triplets.py
"""

import sqlite3
import csv
import os
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict

# ── RDKit: optional, not required ────────────────────────────────────────────
# FooDB Compound.csv moldb_smiles column already contains InChIKeys (confirmed).
# RDKit is only used as a fallback to recompute InChIKeys from SMILES if needed.
# On Windows with Application Control policies, RDKit DLLs may be blocked —
# we detect this and fall back to the FooDB InChIKey column gracefully.
try:
    from rdkit import Chem
    from rdkit import RDLogger
    # Test actual functionality, not just import
    _test = Chem.MolFromSmiles('C')
    if _test is None:
        raise ImportError("RDKit functional test failed")
    RDLogger.DisableLog('rdApp.*')
    HAS_RDKIT = True
    print("[OK] RDKit available — will recompute InChIKeys from SMILES for accuracy")
except Exception as e:
    HAS_RDKIT = False
    print(f"[INFO] RDKit not usable ({e})")
    print("[INFO] Using FooDB moldb_smiles column (pre-computed InChIKeys) — no RDKit needed")

# ── Paths ───────────────────────────────────────────────────────────────────────
ROOT       = Path("D:/23AIBox-DFinder")
OUT_DIR    = ROOT / "data" / "processed_hkg"
OUT_DIR.mkdir(parents=True, exist_ok=True)

COMPOUND_CSV  = ROOT / "Compound.csv"
CONTENT_CSV   = ROOT / "Content.csv"
FOOD_CSV      = ROOT / "Food.csv"
ENZYMES_CSV   = ROOT / "generated" / "drugbank_dfi_enzymes.csv"
CHEMBL_DB     = ROOT / "chembl_36_sqlite" / "chembl_36" / "chembl_36_sqlite" / "chembl_36.db"

OUT_TRIPLETS  = OUT_DIR / "hkg_triplets.tsv"
OUT_STEP1     = OUT_DIR / "hkg_compound_cyp_edges.csv"
OUT_STEP2     = OUT_DIR / "hkg_food_compound_edges.csv"
OUT_STEP3     = OUT_DIR / "hkg_drug_cyp_edges.csv"
OUT_STATS     = OUT_DIR / "hkg_build_stats.txt"

# ── Config ─────────────────────────────────────────────────────────────────────
IC50_THRESHOLD_NM  = 10_000   # 10 µM — standard pharmacological threshold
MIN_CONTENT_MG     = 0.0      # min mg/100g to include food→compound edge (0 = all)

# Human CYP / transporter targets to keep (ChEMBL preferred names, partial match)
TARGET_KEYWORDS = [
    "Cytochrome P450 3A4", "Cytochrome P450 2D6", "Cytochrome P450 1A2",
    "Cytochrome P450 2C9", "Cytochrome P450 2C19", "Cytochrome P450 2C8",
    "Cytochrome P450 2B6", "Cytochrome P450 1A1", "Cytochrome P450 1B1",
    "Cytochrome P450 3A5",
    "ATP-dependent translocase ABCB1",   # P-glycoprotein
    "Breast cancer resistance protein",  # ABCG2
    "Multidrug resistance-associated protein 2",  # MRP2
    "Solute carrier organic anion transporter family member 1B1",  # OATP1B1
    "Solute carrier organic anion transporter family member 1B3",  # OATP1B3
]

# Map DrugBank action strings → relation names
ACTION_TO_RELATION = {
    "inhibitor":          "inhibits",
    "substrate":          "substrate_of",
    "inducer":            "induces",
    "substrate, inhibitor": "inhibits",   # primary action
    "substrate, inducer": "induces",
    "agonist":            "activates",
    "antagonist":         "inhibits",
    "binder":             "binds",
    "modulator":          "modulates",
}


def _relations_from_actions(action_value: str) -> list[str]:
    """Map raw DrugBank action text into one or more canonical relations."""
    action = str(action_value or "").lower().strip()
    if not action or action == "nan":
        return ["binds"]

    relations: list[str] = []

    # First keep exact known mappings for stability.
    exact = ACTION_TO_RELATION.get(action)
    if exact:
        relations.append(exact)

    # Then parse multi-action tokens to preserve directionality (victim/perpetrator).
    for token in [t.strip() for t in action.replace(";", ",").split(",") if t.strip()]:
        if token in ACTION_TO_RELATION:
            relations.append(ACTION_TO_RELATION[token])
            continue
        if "inhibit" in token or "antagon" in token:
            relations.append("inhibits")
        elif "induc" in token:
            relations.append("induces")
        elif "substrate" in token:
            relations.append("substrate_of")
        elif "agonist" in token or "activat" in token:
            relations.append("activates")
        elif "modulat" in token:
            relations.append("modulates")
        elif "bind" in token or "ligand" in token or "regulator" in token:
            relations.append("binds")

    # Fallback if nothing matched.
    if not relations:
        relations.append("binds")

    # Deduplicate while preserving order.
    out: list[str] = []
    seen = set()
    for rel in relations:
        if rel not in seen:
            seen.add(rel)
            out.append(rel)
    return out

stats = {}

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Compound → CYP edges (ChEMBL)
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("STEP 1: Compound → CYP/Transporter edges (ChEMBL 36)")
print("="*70)

# Load FooDB compounds
print("  Loading FooDB Compound.csv...")
compound_df = pd.read_csv(COMPOUND_CSV,
    usecols=["id", "name", "cas_number", "moldb_smiles"],
    dtype=str, low_memory=False)
compound_df.columns = ["foodb_id", "name", "smiles", "inchikey_raw"]
compound_df["foodb_id"] = compound_df["foodb_id"].str.strip()
compound_df["name"]     = compound_df["name"].str.strip()
compound_df["smiles"]   = compound_df["smiles"].str.strip()
# CONFIRMED: FooDB column shift — moldb_smiles column holds InChIKey, not SMILES
# Verified with Caffeine: moldb_smiles = 'RYYVLZVUVIJVGH-UHFFFAOYSA-N' (InChIKey)
#                         cas_number   = 'CN1C=NC2=C1C(=O)N(C)C(=O)N2C' (SMILES)
compound_df["foodb_inchikey"] = compound_df["inchikey_raw"].str.strip()

print(f"  FooDB compounds loaded: {len(compound_df):,}")

# Use FooDB InChIKey column directly (primary method — no RDKit required)
# The foodb_inchikey column is reliable: 70,413 / 70,477 compounds have it.
# If RDKit is available, recompute from SMILES for compounds missing InChIKey.
compound_df["match_inchikey"] = compound_df["foodb_inchikey"].where(
    compound_df["foodb_inchikey"].str.len() == 27, other=None
)  # Valid InChIKeys are exactly 27 chars

if HAS_RDKIT:
    missing_mask = compound_df["match_inchikey"].isna() & compound_df["smiles"].notna()
    n_missing = missing_mask.sum()
    if n_missing > 0:
        print(f"  RDKit: recomputing InChIKeys for {n_missing:,} compounds missing them...")
        def smiles_to_inchikey(smi):
            try:
                mol = Chem.MolFromSmiles(smi)
                if mol is None:
                    return None
                return Chem.inchi.MolToInchiKey(Chem.inchi.MolToInchi(mol))
            except Exception:
                return None
        compound_df.loc[missing_mask, "match_inchikey"] = \
            compound_df.loc[missing_mask, "smiles"].apply(smiles_to_inchikey)

n_ik = compound_df["match_inchikey"].notna().sum()
print(f"  InChIKeys ready for matching: {n_ik:,} / {len(compound_df):,} compounds")

# Connect to ChEMBL with performance optimizations
print(f"  Connecting to ChEMBL DB ({CHEMBL_DB.name})...")
conn = sqlite3.connect(str(CHEMBL_DB), check_same_thread=False)
conn.row_factory = sqlite3.Row
cur_init = conn.cursor()
# Performance pragmas — critical for large SQLite files:
#   cache_size: -524288 = 512 MB page cache (default is only ~2 MB)
#   mmap_size: 4 GB memory-mapped I/O (avoids repeated disk seeks)
#   journal_mode=OFF: skip journaling for read-only workload
#   synchronous=OFF: no fsync needed for reads
cur_init.execute("PRAGMA cache_size = -524288")       # 512 MB SQLite page cache
cur_init.execute("PRAGMA mmap_size = 4294967296")     # 4 GB memory map
cur_init.execute("PRAGMA journal_mode = OFF")
cur_init.execute("PRAGMA synchronous = OFF")
cur_init.execute("PRAGMA temp_store = MEMORY")
print("  SQLite pragmas set: 512MB cache, 4GB mmap, temp in memory")

# Build InChIKey → molregno map from ChEMBL compound_structures
# Memory estimate: 2.85M rows × (27 char key + 4 byte int) ≈ ~180 MB — safe on 12 GB RAM.
# We store FULL key AND 14-char connectivity prefix for fuzzy fallback matching.
print("  Loading ChEMBL compound_structures InChIKey map (~30s, ~180 MB RAM)...")
cur = conn.cursor()
ik_to_molregno = {}   # full 27-char InChIKey → molregno
ik14_to_molregno = {} # 14-char connectivity layer → molregno (fallback)
for row in cur.execute(
    "SELECT molregno, standard_inchi_key FROM compound_structures "
    "WHERE standard_inchi_key IS NOT NULL"
):
    ik = row[1]
    ik_to_molregno[ik] = row[0]
    ik14 = ik[:14]
    if ik14 not in ik14_to_molregno:   # keep first match only for prefix
        ik14_to_molregno[ik14] = row[0]
print(f"  ChEMBL full InChIKeys: {len(ik_to_molregno):,}")
print(f"  ChEMBL 14-char prefix keys: {len(ik14_to_molregno):,}")

# Match FooDB compounds to ChEMBL molregnos
# Try exact 27-char match first, then 14-char connectivity prefix fallback
foodb_to_molregno = {}
full_matches = 0
prefix_matches = 0
for _, row in compound_df.iterrows():
    ik = row["match_inchikey"]
    if pd.isna(ik) or not ik or len(ik) < 14:
        continue
    molregno = ik_to_molregno.get(ik)
    if molregno:
        full_matches += 1
    else:
        molregno = ik14_to_molregno.get(ik[:14])
        if molregno:
            prefix_matches += 1
    if molregno:
        foodb_to_molregno[row["foodb_id"]] = (molregno, row["name"])
print(f"  Exact InChIKey matches: {full_matches:,}")
print(f"  Prefix (14-char) matches: {prefix_matches:,}")

print(f"  FooDB compounds matched to ChEMBL: {len(foodb_to_molregno):,}")
stats["step1_foodb_matched_to_chembl"] = len(foodb_to_molregno)

# Get human CYP/transporter targets from ChEMBL
print("  Querying target_dictionary for CYP/transporter targets...")
target_conditions = " OR ".join(
    [f"pref_name LIKE '%{kw}%'" for kw in TARGET_KEYWORDS]
)
target_rows = cur.execute(f"""
    SELECT tid, chembl_id, pref_name
    FROM target_dictionary
    WHERE organism = 'Homo sapiens'
      AND target_type = 'SINGLE PROTEIN'
      AND ({target_conditions})
""").fetchall()

tid_to_name = {r["tid"]: r["pref_name"] for r in target_rows}
print(f"  Human CYP/transporter targets found: {len(tid_to_name)}")
for tid, name in tid_to_name.items():
    print(f"    [{tid}] {name}")

# Now fetch activities for matched compounds
# Performance improvements over first attempt:
#   1. SQLite pragmas: 512MB cache + 4GB mmap (set at connection time above)
#   2. Temp table for target TIDs (avoids IN-list re-parse each query)
#   3. Batch size 500 is fine now that cache is in memory
#   4. Iterate cursor row-by-row instead of .fetchall() (lower peak RAM)
#   5. Print progress every batch for real-time visibility
print("\n  Creating temp table of target TIDs...")
cur.execute("CREATE TEMP TABLE target_tids (tid INTEGER PRIMARY KEY)")
cur.executemany("INSERT INTO target_tids VALUES (?)",
                [(t,) for t in tid_to_name.keys()])
conn.commit()
print(f"  Temp table created with {len(tid_to_name)} TIDs")

print(f"\n  Querying ChEMBL activities (batched, 500 compounds/query)...")
matched_molregnos = list({mr for mr, _ in foodb_to_molregno.values()})
molregno_to_foodb = defaultdict(list)
for fid, (mr, name) in foodb_to_molregno.items():
    molregno_to_foodb[mr].append((fid, name))

print(f"  Total unique molregnos to query: {len(matched_molregnos):,}")

step1_rows = []
BATCH = 500
n_batches = (len(matched_molregnos) + BATCH - 1) // BATCH
import time as _time
t0 = _time.time()

for bi, i in enumerate(range(0, len(matched_molregnos), BATCH)):
    batch = matched_molregnos[i:i+BATCH]
    placeholders = ",".join("?" * len(batch))
    query = f"""
        SELECT a.molregno, a.standard_type,
               a.standard_value, a.standard_units, a.action_type,
               ass.tid
        FROM activities a
        JOIN assays ass ON a.assay_id = ass.assay_id
        JOIN target_tids tt ON ass.tid = tt.tid
        WHERE a.molregno IN ({placeholders})
          AND a.standard_type IN ('IC50','Ki','Inhibition','pIC50','pKi','Potency')
          AND a.standard_value IS NOT NULL
    """
    # Iterate cursor row-by-row — avoids loading all results into memory at once
    t_batch = _time.time()
    for r in cur.execute(query, batch):
        target_name = tid_to_name.get(r["tid"], "Unknown")
        val   = r["standard_value"]
        units = r["standard_units"] or ""
        stype = r["standard_type"]
        relation = None

        if stype in ("IC50", "Ki", "Potency") and val is not None:
            val_nm = val
            if "uM" in units or "µM" in units:
                val_nm = val * 1000
            elif "mM" in units:
                val_nm = val * 1_000_000
            if val_nm <= IC50_THRESHOLD_NM:
                relation = "inhibits"
        elif stype in ("pIC50", "pKi") and val is not None:
            if val >= 5.0:
                relation = "inhibits"
        elif stype == "Inhibition" and val is not None:
            if val >= 50:
                relation = "inhibits"

        if r["action_type"]:
            at = r["action_type"].lower()
            if "inducer" in at and not relation:
                relation = "induces"
            elif "substrate" in at and not relation:
                relation = "substrate_of"

        if not relation:
            continue

        for foodb_id, cmp_name in molregno_to_foodb[r["molregno"]]:
            step1_rows.append({
                "head":      cmp_name,
                "relation":  relation,
                "tail":      target_name,
                "weight":    1.0,
                "source":    "chembl36",
                "head_type": "COMPOUND",
                "tail_type": "TARGET",
            })

    elapsed = _time.time() - t0
    batch_sec = _time.time() - t_batch
    done_compounds = min(i + BATCH, len(matched_molregnos))
    pct = 100 * done_compounds / len(matched_molregnos)
    eta = (elapsed / (bi+1)) * (n_batches - bi - 1)
    print(f"    [{pct:5.1f}%] batch {bi+1:3d}/{n_batches} | "
          f"{done_compounds:,}/{len(matched_molregnos):,} compounds | "
          f"{len(step1_rows):,} triplets | "
          f"{batch_sec:.1f}s/batch | ETA {eta/60:.0f}min")

# Also pull from drug_mechanism (cleaner curated data)
print("\n  Querying ChEMBL drug_mechanism (curated)...")
mech_rows = cur.execute("""
    SELECT md.pref_name, dm.action_type, td.pref_name as target_name
    FROM drug_mechanism dm
    JOIN molecule_dictionary md ON dm.molregno = md.molregno
    JOIN target_dictionary td   ON dm.tid = td.tid
    WHERE td.organism = 'Homo sapiens'
      AND dm.molregno IN (SELECT DISTINCT molregno FROM compound_structures)
""").fetchall()

for r in mech_rows:
    if not r["pref_name"] or not r["target_name"]:
        continue
    at = (r["action_type"] or "").lower()
    relation = None
    if "inhibitor" in at or "antagonist" in at:
        relation = "inhibits"
    elif "inducer" in at:
        relation = "induces"
    elif "substrate" in at:
        relation = "substrate_of"
    if not relation:
        continue
    # Only keep CYP/transporter targets
    tname = r["target_name"]
    if not any(kw.split()[2] in tname for kw in TARGET_KEYWORDS if len(kw.split()) > 2):
        continue
    step1_rows.append({
        "head":      r["pref_name"],
        "relation":  relation,
        "tail":      tname,
        "weight":    1.0,
        "source":    "chembl36_mechanism",
        "head_type": "COMPOUND",
        "tail_type": "TARGET",
    })

conn.close()

step1_df = pd.DataFrame(step1_rows).drop_duplicates(subset=["head","relation","tail"])
step1_df.to_csv(OUT_STEP1, index=False)
stats["step1_compound_cyp_triplets"] = len(step1_df)
print(f"\n  ✓ Step 1 complete: {len(step1_df):,} Compound→CYP triplets")
print(f"    Saved to: {OUT_STEP1.name}")
print(f"    Relation breakdown:\n{step1_df['relation'].value_counts().to_string()}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Food → Compound edges (FooDB Content.csv)
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("STEP 2: Food → Compound edges (FooDB Content.csv)")
print("="*70)

print("  Loading Food.csv...")
food_df = pd.read_csv(FOOD_CSV,
    usecols=["id", "name", "food_group", "food_type"],
    dtype=str)
food_df["id"] = food_df["id"].str.strip()
food_id_to_name = dict(zip(food_df["id"], food_df["name"].str.strip()))
print(f"  Foods: {len(food_id_to_name):,}")

print("  Loading Compound.csv name map...")
compound_name_map = dict(zip(
    compound_df["foodb_id"].astype(str),
    compound_df["name"].str.strip()
))

print("  Streaming Content.csv (748 MB)...")
step2_rows = []
seen = set()
chunk_iter = pd.read_csv(CONTENT_CSV,
    usecols=["source_id", "source_type", "food_id", "standard_content"],
    dtype={"source_id": str, "food_id": str, "standard_content": str},
    chunksize=500_000)

rows_processed = 0
for chunk in chunk_iter:
    chunk = chunk[chunk["source_type"] == "Compound"]
    for _, row in chunk.iterrows():
        fid  = str(row["food_id"]).strip()
        cid  = str(row["source_id"]).strip()
        food_name = food_id_to_name.get(fid)
        cmp_name  = compound_name_map.get(cid)
        if not food_name or not cmp_name:
            continue

        # Concentration weight
        try:
            content = float(row["standard_content"])
        except (ValueError, TypeError):
            content = 0.0

        if content < MIN_CONTENT_MG:
            continue

        key = (food_name, cmp_name)
        if key in seen:
            continue
        seen.add(key)

        step2_rows.append({
            "head":      food_name,
            "relation":  "contains",
            "tail":      cmp_name,
            "weight":    round(content, 4),
            "source":    "foodb",
            "head_type": "FOOD",
            "tail_type": "COMPOUND",
        })
    rows_processed += len(chunk)
    print(f"    Processed {rows_processed:,} compound-food rows, {len(step2_rows):,} unique edges so far...")

step2_df = pd.DataFrame(step2_rows)
step2_df.to_csv(OUT_STEP2, index=False)
stats["step2_food_compound_triplets"] = len(step2_df)
print(f"\n  ✓ Step 2 complete: {len(step2_df):,} Food→Compound triplets")
print(f"    Unique foods:     {step2_df['head'].nunique():,}")
print(f"    Unique compounds: {step2_df['tail'].nunique():,}")
print(f"    Saved to: {OUT_STEP2.name}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Drug → CYP edges (DrugBank)
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("STEP 3: Drug → CYP/Transporter edges (DrugBank)")
print("="*70)

enz_df = pd.read_csv(ENZYMES_CSV)
print(f"  Loaded: {len(enz_df):,} rows, {enz_df['drug_name'].nunique():,} drugs")

step3_rows = []
for _, row in enz_df.iterrows():
    drug_name = str(row["drug_name"]).strip()
    gene_name = str(row["gene_name"]).strip()
    if not drug_name or not gene_name or gene_name.lower() == "nan":
        continue

    for relation in _relations_from_actions(row.get("actions", "")):
        step3_rows.append({
            "head":      drug_name,
            "relation":  relation,
            "tail":      gene_name,
            "weight":    1.0,
            "source":    "drugbank",
            "head_type": "DRUG",
            "tail_type": "TARGET",
        })

step3_df = pd.DataFrame(step3_rows).drop_duplicates(subset=["head","relation","tail"])
step3_df.to_csv(OUT_STEP3, index=False)
stats["step3_drug_cyp_triplets"] = len(step3_df)
print(f"\n  ✓ Step 3 complete: {len(step3_df):,} Drug→Target triplets")
print(f"    Relation breakdown:\n{step3_df['relation'].value_counts().to_string()}")
print(f"    Saved to: {OUT_STEP3.name}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Merge into master triplet file
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("STEP 4: Merge → master HKG triplet file")
print("="*70)

all_triplets = pd.concat([step1_df, step2_df, step3_df], ignore_index=True)
all_triplets = all_triplets.drop_duplicates(subset=["head","relation","tail"])
all_triplets.to_csv(OUT_TRIPLETS, sep="\t", index=False)

stats["total_triplets"]   = len(all_triplets)
stats["unique_heads"]     = all_triplets["head"].nunique()
stats["unique_tails"]     = all_triplets["tail"].nunique()
stats["unique_relations"] = all_triplets["relation"].nunique()

# Node type counts
for ntype in ["FOOD","COMPOUND","TARGET","DRUG"]:
    heads = all_triplets[all_triplets["head_type"]==ntype]["head"].nunique()
    tails = all_triplets[all_triplets["tail_type"]==ntype]["tail"].nunique()
    stats[f"nodes_{ntype}"] = max(heads, tails)

print(f"\n  ✓ Master triplet file: {OUT_TRIPLETS.name}")
print(f"    Total triplets   : {stats['total_triplets']:,}")
print(f"    Unique relations : {stats['unique_relations']}")
print(f"    Relations breakdown:")
print(all_triplets["relation"].value_counts().to_string())
print(f"\n  Node counts:")
for ntype in ["FOOD","COMPOUND","TARGET","DRUG"]:
    print(f"    [{ntype}]: {stats.get(f'nodes_{ntype}',0):,}")

# ── Write stats report ────────────────────────────────────────────────────────
with open(OUT_STATS, "w") as f:
    f.write("HKG Build Stats\n" + "="*40 + "\n")
    for k, v in stats.items():
        f.write(f"  {k:45s}: {v:,}\n" if isinstance(v, int) else f"  {k}: {v}\n")

print(f"\n  Stats saved to: {OUT_STATS.name}")
print("\n" + "="*70)
print("✓ HKG triplet file ready for Phase 2 (KG embedding & DFinder v2).")
print(f"  Next step: train RotatE/TransE on {OUT_TRIPLETS}")
print("="*70)
