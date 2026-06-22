"""
Phase 4 — Mechanistic KGE Inference
Scores drug-food pairs through the RotatE model trained on the mechanistic HKG.

Lookup strategy:
  1. If food_name is directly a KGE entity (bioactive compound: Quercetin, Caffeine...) 
     → score it directly as compound head
  2. If food_name is a whole-food HKG node (Grapefruit, Ginger...)
     → food→contains→compounds (HKG), filter to KGE entities, score each compound
  3. Drug → drug_rosetta → KGE entity → score against all enzymes

RotatE score(h, r, e) = gamma - ||rot(h, r) - e||
Shared enzymes between compound-side and drug-side form the mechanistic evidence.

Usage as module:
    from mech_kge_inference import MechKGEInference
    kge = MechKGEInference()
    result = kge.score_by_name("Warfarin", "Quercetin")

Usage as script (validates on 889 unseen pairs):
    python mech_kge_inference.py
"""

import math
import numpy as np
import torch
import pandas as pd
from pathlib import Path
from collections import defaultdict

# ── Paths ───────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent
MECH_DIR   = ROOT / "data/mechanistic_kge"
HKG_DIR    = ROOT / "data/processed_hkg"
VAL_DIR    = ROOT / "validation_splits"

CKPT_PATH  = MECH_DIR / "mech_best.pt"
ENT2ID     = MECH_DIR / "mech_entity2id.txt"
REL2ID     = MECH_DIR / "mech_relation2id.txt"
TRIPLETS   = MECH_DIR / "mech_triplets.tsv"
ROSETTA    = MECH_DIR / "drug_rosetta.csv"
FOOD_COMP  = HKG_DIR  / "hkg_food_compound_edges.csv"
UNSEEN     = VAL_DIR  / "validation_unseen.csv"

# ── RotatE constants (must match train_mech_kge.py) ─────────────────────────
GAMMA     = 12.0
EMB_DIM   = 128   # complex dim (emb stored as 2*128 = 256 floats)

# Relation risk weights for final scoring
REL_RISK = {
    "inhibits"    : 1.5,
    "substrate_of": 1.2,
    "induces"     : 1.3,
    "binds"       : 1.0,
    "activates"   : 1.1,
    "modulates"   : 1.0,
}

# Enzyme importance weights (tiered clinical weighting)
ENZYME_WEIGHTS = {
    # Tier 1: high-stakes pathways
    "CYP3A4": 10,
    "VKORC1": 10,
    "CYP2C9": 9,
    "CYP2D6": 9,
    "ABCB1": 9,
    "CYP2C19": 8,

    # Tier 2: moderate clinical risk
    "UGT1A1": 5,
    "SLCO1B1": 5,
    "CYP1A2": 4,
    "CYP2B6": 4,
    "CYP2C8": 3,
    "CYP2E1": 3,
    "CYP2A6": 2,
    "ABCB11": 2,
}


# ── MechKGEInference ─────────────────────────────────────────────────────────
class MechKGEInference:
    def __init__(self, verbose: bool = True, top_k_enzymes: int = 150):
        self.top_k = top_k_enzymes

        if verbose:
            print("Loading Mechanistic KGE model...")

        # ── Entity / relation maps ────────────────────────────────────────
        self.ent2id, self.id2ent = self._load_id_map(ENT2ID)
        self.rel2id, self.id2rel = self._load_id_map(REL2ID)
        self.n_ent = len(self.ent2id)
        self.n_rel = len(self.rel2id)
        if verbose:
            print(f"  Entities: {self.n_ent}  Relations: {self.n_rel}")

        # ── Load RotatE embeddings from checkpoint ────────────────────────
        ckpt = torch.load(CKPT_PATH, map_location="cpu")
        sd   = ckpt["model_state_dict"]
        # entity_emb: (N, 2*DIM)  — [re|im]
        self._ent_emb = sd["entity_emb.weight"].float()    # (4348, 256)
        # relation_emb: (R, DIM)  — phase angles
        self._rel_emb = sd["relation_emb.weight"].float()  # (6, 128)
        if verbose:
            print(f"  entity_emb: {tuple(self._ent_emb.shape)}  "
                  f"relation_emb: {tuple(self._rel_emb.shape)}")

        # ── Identify enzyme entity IDs (tail-only entities) ───────────────
        trips = pd.read_csv(TRIPLETS, sep="\t", header=None, names=["h","r","t"])
        head_set = set(trips["h"].unique())
        tail_set = set(trips["t"].unique())
        enzyme_names = tail_set - head_set          # targets never appear as head
        self._enzyme_ids  = torch.tensor(
            sorted(self.ent2id[e] for e in enzyme_names if e in self.ent2id),
            dtype=torch.long
        )                                           # (2063,)
        self._enzyme_emb  = self._ent_emb[self._enzyme_ids]  # (2063, 256)
        self._enzyme_names = [self.id2ent[i.item()] for i in self._enzyme_ids]
        if verbose:
            print(f"  Enzyme entities: {len(self._enzyme_ids)}")

        # ── Drug rosetta: lgn_name (lower) → KGE entity name ─────────────
        rosetta = pd.read_csv(ROSETTA)
        self._drug_to_kge: dict[str, str] = {}
        for _, row in rosetta.dropna(subset=["hkg_name"]).iterrows():
            if row.get("in_mech_kge"):
                self._drug_to_kge[str(row["lgn_name"]).strip().lower()] = str(row["hkg_name"])

        # ── Food→compound lookup (whole-food HKG nodes) ───────────────────
        fc = pd.read_csv(FOOD_COMP).dropna(subset=["head", "tail"])
        self._food_comps: dict[str, list[str]] = defaultdict(list)
        for h, t in zip(fc["head"].str.strip().str.lower(), fc["tail"].str.strip()):
            self._food_comps[h].append(t)

        if verbose:
            print(f"  Drug→KGE bridges: {len(self._drug_to_kge):,}")
            print(f"  Food→compound entries: {len(self._food_comps):,}")
            print("  Mechanistic KGE ready.")

    # ── RotatE scoring ────────────────────────────────────────────────────────
    def _rotate_score_vs_enzymes(self, head_id: int, rel_id: int) -> np.ndarray:
        """
        Score head entity against ALL enzyme entities for a given relation.
        Returns ndarray shape (n_enzymes,) with RotatE scores.
        """
        h_emb = self._ent_emb[head_id]                            # (256,)
        r_phase = self._rel_emb[rel_id]                           # (128,)
        t_emb = self._enzyme_emb                                   # (2063, 256)

        h_re = h_emb[:EMB_DIM].unsqueeze(0)    # (1, 128)
        h_im = h_emb[EMB_DIM:].unsqueeze(0)    # (1, 128)
        t_re = t_emb[:, :EMB_DIM]              # (2063, 128)
        t_im = t_emb[:, EMB_DIM:]              # (2063, 128)

        r_re = torch.cos(r_phase).unsqueeze(0) # (1, 128)
        r_im = torch.sin(r_phase).unsqueeze(0) # (1, 128)

        rot_re = h_re * r_re - h_im * r_im     # (1, 128)
        rot_im = h_re * r_im + h_im * r_re

        diff_re = rot_re - t_re                 # (2063, 128)
        diff_im = rot_im - t_im

        dist = torch.sqrt(diff_re**2 + diff_im**2 + 1e-12).sum(dim=-1)  # (2063,)
        scores = GAMMA - dist                                             # (2063,)
        return scores.detach().numpy()

    def _best_enzymes(self, head_id: int) -> dict[str, dict]:
        """
        Score head entity against all enzymes, all relations.
        Returns {enzyme_name: {"rank": 1-based rank, "rel": best_rel_name, "score": raw_score}}
        for the top-k enzymes by best-relation score (no absolute threshold).
        Rank 1 = highest scoring enzyme among the enzyme-only pool.
        """
        # Stack all relation scores: (n_rel, n_enzymes)
        rel_scores = np.stack([
            self._rotate_score_vs_enzymes(head_id, rel_id)
            for rel_id in range(self.n_rel)
        ], axis=0)

        # Best relation score per enzyme
        best_rel_idx   = rel_scores.argmax(axis=0)   # (n_enzymes,)
        best_rel_score = rel_scores.max(axis=0)      # (n_enzymes,)

        # Top-K by score (descending) — no absolute threshold
        order = np.argsort(best_rel_score)[::-1][:self.top_k]
        result = {}
        for rank, enz_local_idx in enumerate(order, start=1):
            rel_name = self.id2rel[int(best_rel_idx[enz_local_idx])]
            raw_score = float(best_rel_score[enz_local_idx])
            result[self._enzyme_names[enz_local_idx]] = {
                "rank" : rank,
                "rel"  : rel_name,
                "score": raw_score,
            }
        return result

    # ── Query ─────────────────────────────────────────────────────────────────
    def score_by_name(self, drug_name: str, food_name: str) -> dict:
        """
        Score a (drug, food) pair via RotatE.
        Returns dict with mechanistic path score and evidence.
        """
        d_key = drug_name.strip().lower()
        f_key = food_name.strip().lower()

        # ── Resolve drug to KGE entity ────────────────────────────────────
        kge_drug_name = self._drug_to_kge.get(d_key)
        if kge_drug_name is None:
            # Try direct lookup by name
            kge_drug_name = drug_name.strip() if drug_name.strip() in self.ent2id else None
        drug_id = self.ent2id.get(kge_drug_name) if kge_drug_name else None

        # ── Resolve food to KGE compound(s) ──────────────────────────────
        food_compounds: list[tuple[str, int]] = []

        # Strategy 1: food name itself is a KGE entity (bioactive compound)
        if food_name.strip() in self.ent2id:
            food_compounds.append((food_name.strip(), self.ent2id[food_name.strip()]))

        # Strategy 2: whole-food node → contains → filter to KGE entities
        hkg_comps = self._food_comps.get(f_key, [])
        for comp in hkg_comps:
            if comp in self.ent2id and (comp, self.ent2id[comp]) not in food_compounds:
                food_compounds.append((comp, self.ent2id[comp]))

        # ── Score drug vs enzymes ─────────────────────────────────────────
        drug_enzyme_scores: dict[str, dict] = {}
        if drug_id is not None:
            drug_enzyme_scores = self._best_enzymes(drug_id)

        # ── Score each food compound vs enzymes ───────────────────────────
        comp_enzyme_scores: dict[str, dict[str, dict]] = {}
        for comp_name, comp_id in food_compounds[:30]:   # cap at 30 compounds
            comp_enzyme_scores[comp_name] = self._best_enzymes(comp_id)

        # ── Find shared high-scoring enzymes (rank-based, no score threshold) ──
        # Rank 1 = highest RotatE score among enzyme pool (best predicted target)
        K = self.top_k
        shared_enzymes = []
        for comp_name, comp_enz in comp_enzyme_scores.items():
            for enz_name, comp_data in comp_enz.items():
                if enz_name in drug_enzyme_scores:
                    drug_data      = drug_enzyme_scores[enz_name]
                    comp_rank      = comp_data["rank"]
                    drug_rank      = drug_data["rank"]
                    comp_rel       = comp_data["rel"]
                    drug_rel       = drug_data["rel"]
                    # Normalized rank scores in (0, 1]: rank 1 → 1.0, rank K → 1/K
                    norm_comp      = (K - comp_rank + 1) / K
                    norm_drug      = (K - drug_rank + 1) / K
                    path_score     = (norm_comp + norm_drug) / 2.0
                    enz_weight     = ENZYME_WEIGHTS.get(enz_name, 1)
                    risk_mult      = REL_RISK.get(comp_rel, 1.0) * REL_RISK.get(drug_rel, 1.0)
                    weighted_score = path_score * enz_weight * risk_mult
                    shared_enzymes.append({
                        "enzyme"       : enz_name,
                        "compound"     : comp_name,
                        "comp_rel"     : comp_rel,
                        "comp_rank"    : comp_rank,
                        "drug_rel"     : drug_rel,
                        "drug_rank"    : drug_rank,
                        "path_score"   : round(path_score, 4),
                        "enz_weight"   : enz_weight,
                        "risk_mult"    : round(risk_mult, 2),
                        "weighted"     : round(weighted_score, 4),
                    })

        # Sort by weighted score
        shared_enzymes.sort(key=lambda x: -x["weighted"])
        # Deduplicate by enzyme (keep best compound per enzyme)
        seen_enz: set[str] = set()
        unique_shared = []
        for e in shared_enzymes:
            if e["enzyme"] not in seen_enz:
                seen_enz.add(e["enzyme"])
                unique_shared.append(e)

        # Aggregate score
        total_score = sum(e["weighted"] for e in unique_shared[:10])

        # Build explanation
        explanation = self._explain(drug_name, food_name, unique_shared[:3], food_compounds)

        return {
            "drug"             : drug_name,
            "food"             : food_name,
            "drug_in_kge"      : drug_id is not None,
            "food_compounds_kge": len(food_compounds),
            "n_shared_enzymes" : len(unique_shared),
            "kge_score"        : round(total_score, 4),
            "found"            : len(unique_shared) > 0,
            "shared_enzymes"   : unique_shared[:10],
            "explanation"      : explanation,
        }

    def _explain(self, drug, food, top3, food_compounds) -> str:
        if not top3:
            if not food_compounds:
                return f"No KGE entities found for '{food}'."
            if not any(True for _ in top3):
                return f"No shared enzyme targets in KGE between '{food}' compounds and '{drug}'."
        parts = []
        for e in top3:
            parts.append(
                f"{e['enzyme']} (w={e['enz_weight']}): "
                f"{e['compound']} {e['comp_rel']}s {e['enzyme']} [rank={e['comp_rank']}]; "
                f"{drug} {e['drug_rel']}s {e['enzyme']} [rank={e['drug_rank']}]"
            )
        return " | ".join(parts)

    def batch_score(self, pairs: list[tuple[str, str]]) -> list[dict]:
        return [self.score_by_name(d, f) for d, f in pairs]

    # ── Internal helpers ──────────────────────────────────────────────────────
    @staticmethod
    def _load_id_map(path: Path) -> tuple[dict, dict]:
        with open(path) as f:
            f.readline()  # skip count line
            fwd = {}
            for line in f:
                if "\t" in line:
                    parts = line.strip().split("\t")
                    fwd[parts[0]] = int(parts[1])
        rev = {v: k for k, v in fwd.items()}
        return fwd, rev


# ── Validation on 889 unseen pairs ───────────────────────────────────────────
if __name__ == "__main__":
    kge = MechKGEInference(verbose=True)

    print("\n=== Validating on 889 unseen pairs ===")
    val = pd.read_csv(UNSEEN)
    print(f"Loaded {len(val)} pairs")

    results = []
    for i, row in val.iterrows():
        r = kge.score_by_name(str(row["drug_name"]), str(row["food_name"]))
        results.append(r)
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(val)} done...")

    found      = [r for r in results if r["found"]]
    d_miss     = [r for r in results if not r["drug_in_kge"]]
    f_miss     = [r for r in results if r["food_compounds_kge"] == 0]

    print(f"\n--- Coverage ---")
    print(f"  Pairs with shared enzyme (found) : {len(found):4d} / {len(results)} ({100*len(found)/len(results):.1f}%)")
    print(f"  Drug not in KGE                  : {len(d_miss):4d} / {len(results)} ({100*len(d_miss)/len(results):.1f}%)")
    print(f"  Food has no KGE compounds        : {len(f_miss):4d} / {len(results)} ({100*len(f_miss)/len(results):.1f}%)")

    scores_arr = np.array([r["kge_score"] for r in results])
    print(f"\n--- KGE score distribution (all 889) ---")
    for q in [0, 25, 50, 75, 90, 100]:
        print(f"  p{q:3d}: {np.percentile(scores_arr, q):.4f}")

    print(f"\n--- Pairs above threshold ---")
    for thr in [1, 5, 10, 20, 50]:
        n = int((scores_arr >= thr).sum())
        print(f"  kge_score >= {thr:3d} : {n:4d} / {len(results)} ({100*n/len(results):.1f}%)")

    # Top hits
    print(f"\n--- Top 15 highest-scoring pairs ---")
    top15 = sorted(results, key=lambda x: -x["kge_score"])[:15]
    for r in top15:
        top_enz = r["shared_enzymes"][0]["enzyme"] if r["shared_enzymes"] else "—"
        top_comp = r["shared_enzymes"][0]["compound"] if r["shared_enzymes"] else "—"
        print(f"  [{r['kge_score']:8.2f}] {r['drug'][:30]:30s} × {r['food'][:20]:20s}"
              f"  via {top_comp} → {top_enz}")

    # Shared enzyme frequency
    from collections import Counter
    enz_counter: Counter = Counter()
    for r in results:
        for e in r["shared_enzymes"]:
            enz_counter[e["enzyme"]] += 1
    print(f"\n--- Top 15 most-triggered enzymes ---")
    for enz, cnt in enz_counter.most_common(15):
        w = ENZYME_WEIGHTS.get(enz, 1)
        print(f"  {enz:25s}  count={cnt:4d}  weight={w}")

    # Save
    out_path = VAL_DIR / "phase4_kge_scores.csv"
    rows = []
    for r in results:
        top_e = r["shared_enzymes"][:3]
        rows.append({
            "drug"              : r["drug"],
            "food"              : r["food"],
            "drug_in_kge"       : r["drug_in_kge"],
            "food_compounds_kge": r["food_compounds_kge"],
            "n_shared_enzymes"  : r["n_shared_enzymes"],
            "kge_score"         : r["kge_score"],
            "found"             : r["found"],
            "top_enzyme_1"      : top_e[0]["enzyme"] if len(top_e) > 0 else "",
            "top_enz1_comp_rank": top_e[0]["comp_rank"] if len(top_e) > 0 else "",
            "top_enz1_drug_rank": top_e[0]["drug_rank"] if len(top_e) > 0 else "",
            "top_enzyme_2"      : top_e[1]["enzyme"] if len(top_e) > 1 else "",
            "top_enzyme_3"      : top_e[2]["enzyme"] if len(top_e) > 2 else "",
            "explanation"       : r["explanation"],
        })
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"\nResults saved → {out_path}")
    print("\nPhase 4 complete.")
