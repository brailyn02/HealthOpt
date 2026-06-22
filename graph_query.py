"""
Phase 2 — Graph Query Engine
Deterministic lookup: food → contains → compounds → [relation] → enzyme ← [relation] ← drug
No model, no probabilities — pure HKG traversal.

Usage as module:
    from graph_query import GraphQueryEngine
    gq = GraphQueryEngine()
    result = gq.query("Warfarin", "Grapefruit")

Usage as script (validates on 889 unseen pairs):
    python graph_query.py
"""

import re, json, csv
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parent
HKG_DIR     = ROOT / "data/processed_hkg"
MECH_DIR    = ROOT / "data/mechanistic_kge"
VAL_DIR     = ROOT / "validation_splits"

FOOD_COMP   = HKG_DIR / "hkg_food_compound_edges.csv"
COMP_ENZ    = HKG_DIR / "hkg_compound_cyp_edges.csv"
DRUG_ENZ    = HKG_DIR / "hkg_drug_cyp_edges.csv"
DRUG_ROSETTA = MECH_DIR / "drug_rosetta.csv"
UNSEEN_VAL  = VAL_DIR / "validation_unseen.csv"

# ── Enzyme importance weights ─────────────────────────────────────────────────
# Tiered clinical weighting: high-stakes pathways are prioritized, while
# enzymes not listed here fall back to DEFAULT_ENZ_WEIGHT.
ENZYME_WEIGHTS = {
    # Tier 1: high-stakes pathways
    "CYP3A4"  : 10,
    "VKORC1"  : 10,
    "CYP2C9"  : 9,
    "CYP2D6"  : 9,
    "ABCB1"   : 9,    # P-glycoprotein
    "CYP2C19" : 8,

    # Tier 2: moderate clinical risk
    "UGT1A1"  : 5,
    "SLCO1B1" : 5,
    "CYP1A2"  : 4,
    "CYP2B6"  : 4,
    "CYP2C8"  : 3,
    "CYP2E1"  : 3,
    "CYP2A6"  : 2,
    "ABCB11"  : 2,    # BSEP
}
DEFAULT_ENZ_WEIGHT = 1

# Relation risk multipliers: inhibiting or being substrate of same enzyme = higher risk
RELATION_RISK = {
    "inhibits"    : 1.5,
    "substrate_of": 1.2,
    "induces"     : 1.3,
    "binds"       : 1.0,
    "activates"   : 1.1,
    "modulates"   : 1.0,
}

# ── Name normalization ────────────────────────────────────────────────────────
def _normalize_enzyme(name: str) -> str:
    """Convert long ChEMBL enzyme names to short canonical form used in drug side."""
    if not isinstance(name, str):
        return ""
    # Cytochrome P450 3A4  →  CYP3A4
    m = re.match(r"Cytochrome P450\s+(\S+)", name, re.IGNORECASE)
    if m:
        suffix = m.group(1).replace(",", "").strip()
        return f"CYP{suffix}"
    # ATP-dependent translocase ABCB1  →  ABCB1
    m = re.search(r"\b(ABCB\d+|ABCC\d+|SLCO\w+|UGT\w+)\b", name)
    if m:
        return m.group(1)
    # P-glycoprotein 1  →  ABCB1
    if "P-glycoprotein" in name or "P-gp" in name:
        return "ABCB1"
    return name.strip()

def _normalize_name(name: str) -> str:
    """Lowercase + strip for fuzzy matching."""
    return name.strip().lower() if isinstance(name, str) else ""

# ── Build lookup indexes ──────────────────────────────────────────────────────
class GraphQueryEngine:
    def __init__(self, verbose: bool = True):
        if verbose:
            print("Loading HKG edge files...")

        fc = pd.read_csv(FOOD_COMP).dropna(subset=["head", "tail"])
        ce = pd.read_csv(COMP_ENZ).dropna(subset=["head", "tail"])
        de = pd.read_csv(DRUG_ENZ).dropna(subset=["head", "tail"])
        rosetta = pd.read_csv(DRUG_ROSETTA)

        # food_name (lower) → set of compound names  (vectorized — fc is 4M+ rows)
        fc["_h"] = fc["head"].str.strip().str.lower()
        self._food_to_compounds: dict[str, set[str]] = defaultdict(set)
        for h, t in zip(fc["_h"].to_numpy(), fc["tail"].to_numpy()):
            self._food_to_compounds[h].add(t)

        # compound_name (lower) → list of (enzyme_short, relation)
        ce["_h"]   = ce["head"].str.strip().str.lower()
        ce["_enz"] = ce["tail"].apply(_normalize_enzyme)
        ce_filt    = ce[ce["_enz"] != ""]
        self._compound_to_enzymes: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for h, enz, rel in zip(ce_filt["_h"].to_numpy(),
                               ce_filt["_enz"].to_numpy(),
                               ce_filt["relation"].to_numpy()):
            self._compound_to_enzymes[h].append((enz, rel))

        # drug_name (lower) → list of (enzyme_short, relation)
        de["_h"] = de["head"].str.strip().str.lower()
        self._drug_to_enzymes: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for h, t, rel in zip(de["_h"].to_numpy(),
                             de["tail"].to_numpy(),
                             de["relation"].to_numpy()):
            self._drug_to_enzymes[h].append((str(t), rel))

        # Also index drugs by both lgn_name and hkg_name from rosetta
        self._lgn_to_hkg: dict[str, str] = {}
        for _, row in rosetta.dropna(subset=["hkg_name"]).iterrows():
            self._lgn_to_hkg[_normalize_name(row["lgn_name"])] = _normalize_name(row["hkg_name"])

        if verbose:
            print(f"  Foods indexed: {len(self._food_to_compounds):,}")
            print(f"  Compound->enzyme pairs: {sum(len(v) for v in self._compound_to_enzymes.values()):,}")
            print(f"  Drug->enzyme pairs: {sum(len(v) for v in self._drug_to_enzymes.values()):,}")

    # ── Core query ────────────────────────────────────────────────────────────
    def query(self, drug_name: str, food_name: str) -> dict:
        """
        Traverse food→compounds→enzymes ← drug.
        Returns a dict with:
          found          : bool (any shared enzyme)
          score          : float (weighted enzyme overlap)
          shared_enzymes : list of (enzyme, food_relation, drug_relation)
          food_compounds : list of compounds found for this food
          drug_enzymes   : list of (enzyme, relation) for drug
          explanation    : natural language chain
        """
        d_key = _normalize_name(drug_name)
        f_key = _normalize_name(food_name)

        # Resolve drug via rosetta if needed
        d_key_resolved = self._lgn_to_hkg.get(d_key, d_key)

        # Step 1: food → compounds
        food_compounds = self._food_to_compounds.get(f_key, set())

        # Step 2: compounds → enzymes
        comp_enzyme_map: dict[str, list[tuple[str, str]]] = {}  # enzyme → [(compound, rel)]
        for comp in food_compounds:
            for enz, rel in self._compound_to_enzymes.get(_normalize_name(comp), []):
                if enz not in comp_enzyme_map:
                    comp_enzyme_map[enz] = []
                comp_enzyme_map[enz].append((comp, rel))

        # Step 3: drug → enzymes
        drug_enz_list = self._drug_to_enzymes.get(d_key_resolved, [])
        if not drug_enz_list:
            drug_enz_list = self._drug_to_enzymes.get(d_key, [])
        drug_enz_dict: dict[str, list[str]] = defaultdict(list)  # enzyme → [relations]
        for enz, rel in drug_enz_list:
            drug_enz_dict[enz].append(rel)

        # Step 4: overlap
        shared = []  # (enzyme, food_rels, drug_rels, comps)
        for enz, comp_rels in comp_enzyme_map.items():
            if enz in drug_enz_dict:
                food_rels = list({r for _, r in comp_rels})
                comps     = list({c for c, _ in comp_rels})
                shared.append((enz, food_rels, drug_enz_dict[enz], comps))

        # Step 5: score
        score = 0.0
        for enz, food_rels, drug_rels, _ in shared:
            base    = ENZYME_WEIGHTS.get(enz, DEFAULT_ENZ_WEIGHT)
            f_mult  = max(RELATION_RISK.get(r, 1.0) for r in food_rels)
            d_mult  = max(RELATION_RISK.get(r, 1.0) for r in drug_rels)
            score  += base * f_mult * d_mult

        # Step 6: explanation
        explanation = self._explain(drug_name, food_name, shared, food_compounds)

        return {
            "drug"          : drug_name,
            "food"          : food_name,
            "found"         : len(shared) > 0,
            "score"         : round(score, 3),
            "shared_enzymes": [
                {
                    "enzyme"     : e,
                    "food_rels"  : fr,
                    "drug_rels"  : dr,
                    "compounds"  : cs,
                    "weight"     : ENZYME_WEIGHTS.get(e, DEFAULT_ENZ_WEIGHT),
                }
                for e, fr, dr, cs in sorted(shared,
                    key=lambda x: ENZYME_WEIGHTS.get(x[0], 1), reverse=True)
            ],
            "food_compounds_total": len(food_compounds),
            "food_in_hkg"   : len(food_compounds) > 0,
            "drug_in_hkg"   : len(drug_enz_list) > 0,
            "explanation"   : explanation,
        }

    def _explain(self, drug, food, shared, food_compounds) -> str:
        if not shared:
            if not food_compounds:
                return f"No compounds found for '{food}' in HKG."
            return f"No shared enzyme targets between '{food}' compounds and '{drug}'."
        top = sorted(shared, key=lambda x: ENZYME_WEIGHTS.get(x[0], 1), reverse=True)[:3]
        lines = []
        for enz, food_rels, drug_rels, comps in top:
            comp_str = ", ".join(comps[:3]) + ("..." if len(comps) > 3 else "")
            f_rel = food_rels[0] if food_rels else "affects"
            d_rel = drug_rels[0] if drug_rels else "affects"
            lines.append(
                f"{enz}: {food} [{comp_str}] {f_rel}s {enz}; "
                f"{drug} {d_rel}s {enz}"
            )
        return " | ".join(lines)

    # ── Batch query ───────────────────────────────────────────────────────────
    def batch_query(self, pairs: list[tuple[str, str]]) -> list[dict]:
        return [self.query(d, f) for d, f in pairs]


# ── Validation: run on 889 unseen pairs ───────────────────────────────────────
if __name__ == "__main__":
    gq = GraphQueryEngine(verbose=True)

    print("\n=== Validating on unseen pairs ===")
    val = pd.read_csv(UNSEEN_VAL)
    print(f"Loaded {len(val)} unseen pairs")

    results = []
    for _, row in val.iterrows():
        r = gq.query(str(row["drug_name"]), str(row["food_name"]))
        results.append(r)

    found     = [r for r in results if r["found"]]
    not_found = [r for r in results if not r["found"]]
    drug_miss = [r for r in results if not r["drug_in_hkg"]]
    food_miss = [r for r in results if not r["food_in_hkg"]]

    print(f"\n--- Coverage ---")
    print(f"  Pairs with interaction found : {len(found):4d} / {len(results)} ({100*len(found)/len(results):.1f}%)")
    print(f"  Pairs with no shared enzyme  : {len(not_found):4d} / {len(results)} ({100*len(not_found)/len(results):.1f}%)")
    print(f"  Drugs missing from HKG       : {len(drug_miss):4d} / {len(results)} ({100*len(drug_miss)/len(results):.1f}%)")
    print(f"  Foods missing from HKG       : {len(food_miss):4d} / {len(results)} ({100*len(food_miss)/len(results):.1f}%)")

    # Score distribution
    scores = [r["score"] for r in results]
    scores_arr = np.array(scores)
    print(f"\n--- Score distribution ---")
    for thr in [0, 5, 10, 20, 50]:
        n = int((scores_arr > thr).sum())
        print(f"  score > {thr:3d} : {n:4d} pairs ({100*n/len(results):.1f}%)")

    # Top shared enzymes
    enz_counter: dict[str, int] = defaultdict(int)
    for r in results:
        for e in r["shared_enzymes"]:
            enz_counter[e["enzyme"]] += 1
    print(f"\n--- Top shared enzymes (across all found interactions) ---")
    for enz, cnt in sorted(enz_counter.items(), key=lambda x: -x[1])[:15]:
        w = ENZYME_WEIGHTS.get(enz, DEFAULT_ENZ_WEIGHT)
        print(f"  {enz:20s}  count={cnt:4d}  weight={w}")

    # Sample high-score results
    print(f"\n--- Top 10 highest-scoring pairs ---")
    top10 = sorted(results, key=lambda x: -x["score"])[:10]
    for r in top10:
        top_enz = r["shared_enzymes"][0]["enzyme"] if r["shared_enzymes"] else "—"
        print(f"  [{r['score']:6.1f}] {r['drug'][:30]:30s} × {r['food'][:20]:20s}  top_enz={top_enz}")

    # Save results
    out_path = VAL_DIR / "phase2_graph_query_results.csv"
    rows = []
    for r in results:
        top_enzymes = "|".join(e["enzyme"] for e in r["shared_enzymes"][:5])
        rows.append({
            "drug"          : r["drug"],
            "food"          : r["food"],
            "found"         : r["found"],
            "score"         : r["score"],
            "drug_in_hkg"   : r["drug_in_hkg"],
            "food_in_hkg"   : r["food_in_hkg"],
            "n_shared_enzymes": len(r["shared_enzymes"]),
            "top_enzymes"   : top_enzymes,
            "explanation"   : r["explanation"],
        })
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"\nResults saved → {out_path}")
    print("\nPhase 2 complete.")
