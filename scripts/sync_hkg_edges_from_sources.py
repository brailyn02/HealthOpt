"""
sync_hkg_edges_from_sources.py
==============================
Backfill current HKG edge files with all available DrugBank and ChEMBL/FooDB edges
already present in local source files, then rebuild hkg_triplets.tsv as a clean union.

This avoids running the heavy full ChEMBL extraction path and is safe for quick sync.

Usage:
    cd D:/23AIBox-DFinder
    python scripts/sync_hkg_edges_from_sources.py
"""

from pathlib import Path
import pandas as pd

ROOT = Path("D:/23AIBox-DFinder")
PROC = ROOT / "data" / "processed_hkg"

DRUGBANK_ENZ = ROOT / "generated" / "drugbank_dfi_enzymes.csv"
STEP1 = PROC / "hkg_compound_cyp_edges.csv"
STEP2 = PROC / "hkg_food_compound_edges.csv"
STEP3 = PROC / "hkg_drug_cyp_edges.csv"
TRIPLETS = PROC / "hkg_triplets.tsv"

ACTION_TO_RELATION = {
    "inhibitor": "inhibits",
    "substrate": "substrate_of",
    "inducer": "induces",
    "agonist": "activates",
    "activator": "activates",
    "antagonist": "inhibits",
    "binder": "binds",
    "ligand": "binds",
    "regulator": "binds",
    "modulator": "modulates",
}


def relations_from_actions(action_value: str) -> list[str]:
    action = str(action_value or "").lower().strip()
    if not action or action == "nan":
        return ["binds"]

    relations: list[str] = []

    exact = ACTION_TO_RELATION.get(action)
    if exact:
        relations.append(exact)

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

    if not relations:
        relations.append("binds")

    out = []
    seen = set()
    for rel in relations:
        if rel not in seen:
            seen.add(rel)
            out.append(rel)
    return out


def rebuild_step3_from_drugbank() -> pd.DataFrame:
    df = pd.read_csv(DRUGBANK_ENZ)
    rows = []
    for _, r in df.iterrows():
        drug = str(r.get("drug_name", "")).strip()
        gene = str(r.get("gene_name", "")).strip()
        if not drug or not gene or gene.lower() == "nan":
            continue
        for rel in relations_from_actions(r.get("actions", "")):
            rows.append(
                {
                    "head": drug,
                    "relation": rel,
                    "tail": gene,
                    "weight": 1.0,
                    "source": "drugbank",
                    "head_type": "DRUG",
                    "tail_type": "TARGET",
                }
            )

    out = pd.DataFrame(rows)
    out = out.drop_duplicates(subset=["head", "relation", "tail"]).reset_index(drop=True)
    out.to_csv(STEP3, index=False)
    return out


def main() -> None:
    if not STEP1.exists() or not STEP2.exists() or not DRUGBANK_ENZ.exists():
        raise FileNotFoundError("Required source files missing for HKG sync")

    step1 = pd.read_csv(STEP1)
    step2 = pd.read_csv(STEP2)
    step3 = rebuild_step3_from_drugbank()

    all_edges = pd.concat([step1, step2, step3], ignore_index=True)
    all_edges = all_edges.drop_duplicates(subset=["head", "relation", "tail"]).reset_index(drop=True)
    all_edges.to_csv(TRIPLETS, sep="\t", index=False)

    print(f"[OK] Step3 rebuilt from DrugBank: {len(step3):,} edges")
    print(f"[OK] HKG triplets rebuilt (union Step1+Step2+Step3): {len(all_edges):,} edges")

    warfarin = step3[step3["head"].astype(str).str.lower() == "warfarin"]
    if len(warfarin) > 0:
        print("[INFO] Warfarin edges in step3:")
        for _, row in warfarin.sort_values(["tail", "relation"]).iterrows():
            print(f"  Warfarin,{row['relation']},{row['tail']}")


if __name__ == "__main__":
    main()
