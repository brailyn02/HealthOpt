"""
Phase 3 — LightGCN Inference Wrapper
Standalone: no world.py, no dataloader.py, no Procedure.py dependencies.

Architecture recap:
  - LightGCN: 3-layer message passing on bipartite drug-food graph
  - DNN: 2048→1024→512→256→64  (Morgan fingerprint projection)
  - Final embedding: cat(GCN_64, DNN_64) = 128-dim
  - Score: sigmoid(dot(drug_emb, food_emb))

Usage as module:
    from lightgcn_inference import LightGCNInference
    lgn = LightGCNInference()
    score = lgn.score_by_name("Warfarin", "Grapefruit")
    scores = lgn.batch_score([("Warfarin","Grapefruit"), ("Digoxin","Caffeine")])

Usage as script (validates on 889 unseen pairs):
    python lightgcn_inference.py
"""

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import scipy.sparse as sp
import pandas as pd
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).resolve().parent
LGN_DIR   = ROOT / "DFinder-main"
DATA_DIR  = LGN_DIR / "data/unified-DFI"
FEAT_DIR  = DATA_DIR / "feature_extra"
ID_DIR    = DATA_DIR / "id_maps"
CKPT_PATH = LGN_DIR / "code/checkpoints/lgn-unified-DFI-3-64.pth.tar"
ADJ_PATH  = DATA_DIR / "s_pre_adj_mat.npz"
VAL_DIR   = ROOT / "validation_splits"
UNSEEN    = VAL_DIR / "validation_unseen.csv"

# Use filled food features (16 zero-rows filled in Phase 0)
DRUG_FEAT = FEAT_DIR / "unified_drug_feature_extra.npy"
FOOD_FEAT = FEAT_DIR / "unified_food_feature_extra_filled.npy"

# ── DNN (standalone, no world.py) ─────────────────────────────────────────────
class _DNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.dense1 = nn.Linear(2048, 1024)
        self.dense2 = nn.Linear(1024,  512)
        self.dense3 = nn.Linear( 512,  256)
        self.dense4 = nn.Linear( 256,   64)

    def forward(self, x):
        x = F.relu(self.dense1(x))
        x = F.relu(self.dense2(x))
        x = F.relu(self.dense3(x))
        return self.dense4(x)


# ── LightGCN Inference Engine ─────────────────────────────────────────────────
class LightGCNInference:
    """
    Fully standalone LightGCN inference.
    Loads once, scores any (drug, food) pair by name or ID.
    """

    N_DRUGS   = 5000
    N_FOODS   = 1894
    LATENT    = 64
    N_LAYERS  = 3

    def __init__(self, verbose: bool = True):
        self.device = torch.device("cpu")

        if verbose:
            print("Loading LightGCN model...")

        # ── ID maps ──────────────────────────────────────────────────────────
        dm = pd.read_csv(ID_DIR / "drug_id_map.csv")
        fm = pd.read_csv(ID_DIR / "food_id_map.csv")

        # name (lower) → lgn_id
        self._drug_name2id: dict[str, int] = {
            str(row["name"]).strip().lower(): int(row["new_id"])
            for _, row in dm.iterrows()
        }
        self._food_name2id: dict[str, int] = {
            str(row["name"]).strip().lower(): int(row["new_id"])
            for _, row in fm.iterrows()
        }
        # lgn_id → name (for display)
        self._drug_id2name = {int(r["new_id"]): str(r["name"]) for _, r in dm.iterrows()}
        self._food_id2name = {int(r["new_id"]): str(r["name"]) for _, r in fm.iterrows()}

        if verbose:
            print(f"  Drugs: {len(self._drug_name2id):,}  Foods: {len(self._food_name2id):,}")

        # ── Load checkpoint ───────────────────────────────────────────────────
        state = torch.load(CKPT_PATH, map_location="cpu")

        self._emb_drug = state["embedding_user.weight"]   # (5000, 64)
        self._emb_food = state["embedding_item.weight"]   # (1894, 64)

        self._dnn = _DNN()
        dnn_state = {k.replace("DNN.", ""): v
                     for k, v in state.items() if k.startswith("DNN.")}
        self._dnn.load_state_dict(dnn_state)
        self._dnn.eval()

        if verbose:
            print(f"  Checkpoint loaded: drug_emb={tuple(self._emb_drug.shape)}, "
                  f"food_emb={tuple(self._emb_food.shape)}")

        # ── Load adjacency matrix ─────────────────────────────────────────────
        adj_sp = sp.load_npz(ADJ_PATH).astype(np.float32)        # (6894, 6894)
        adj_dense = torch.tensor(adj_sp.toarray(), dtype=torch.float32)
        if verbose:
            print(f"  Adj matrix: {adj_dense.shape}  nnz={adj_sp.nnz:,}")

        # ── Load features ─────────────────────────────────────────────────────
        # Use mmap to reduce peak memory during array load on constrained instances.
        drug_feat_np = np.load(DRUG_FEAT, mmap_mode="r")
        food_feat_np = np.load(FOOD_FEAT, mmap_mode="r")
        drug_feat = torch.from_numpy(np.asarray(drug_feat_np, dtype=np.float32))  # (5000, 2048)
        food_feat = torch.from_numpy(np.asarray(food_feat_np, dtype=np.float32))  # (1894, 2048)
        if verbose:
            print(f"  Drug features: {tuple(drug_feat.shape)}")
            print(f"  Food features: {tuple(food_feat.shape)}")

        # ── Pre-compute full embeddings (done once at init, ~1s on CPU) ───────
        if verbose:
            print("  Computing full embeddings (GCN propagation)...")
        with torch.no_grad():
            # GCN propagation
            all_emb = torch.cat([self._emb_drug, self._emb_food], dim=0)  # (6894, 64)
            embs = [all_emb]
            cur  = all_emb
            for _ in range(self.N_LAYERS):
                cur = torch.mm(adj_dense, cur)
                embs.append(cur)
            light_out = torch.stack(embs, dim=1).mean(dim=1)              # (6894, 64)

            gcn_drugs = light_out[:self.N_DRUGS]                           # (5000, 64)
            gcn_foods = light_out[self.N_DRUGS:]                           # (1894, 64)

            # DNN projection
            dnn_drugs = self._dnn(drug_feat)   # (5000, 64)
            dnn_foods = self._dnn(food_feat)   # (1894, 64)

            # Final embeddings: cat(GCN, DNN) → 128-dim
            self._drug_emb_final = torch.cat([gcn_drugs, dnn_drugs], dim=1)  # (5000, 128)
            self._food_emb_final = torch.cat([gcn_foods, dnn_foods], dim=1)  # (1894, 128)

        if verbose:
            print(f"  Drug final emb: {tuple(self._drug_emb_final.shape)}")
            print(f"  Food final emb: {tuple(self._food_emb_final.shape)}")
            print("  LightGCN ready.")

    # ── Public API ────────────────────────────────────────────────────────────
    def score_by_id(self, drug_id: int, food_id: int) -> float:
        """Return sigmoid score for a (drug_id, food_id) pair. Returns None if OOB."""
        if drug_id < 0 or drug_id >= self.N_DRUGS:
            return None
        if food_id < 0 or food_id >= self.N_FOODS:
            return None
        with torch.no_grad():
            d = self._drug_emb_final[drug_id]
            f = self._food_emb_final[food_id]
            return float(torch.sigmoid(torch.dot(d, f)))

    def resolve_drug(self, name: str) -> int | None:
        """Name → LGN drug ID (None if not found)."""
        return self._drug_name2id.get(name.strip().lower())

    def resolve_food(self, name: str) -> int | None:
        """Name → LGN food ID (None if not found)."""
        return self._food_name2id.get(name.strip().lower())

    def score_by_name(self, drug_name: str, food_name: str) -> dict:
        """
        Score a (drug, food) pair by name.
        Returns dict with keys: score, drug_id, food_id, drug_found, food_found.
        """
        d_id = self.resolve_drug(drug_name)
        f_id = self.resolve_food(food_name)
        score = self.score_by_id(d_id, f_id) if (d_id is not None and f_id is not None) else None
        return {
            "drug"       : drug_name,
            "food"       : food_name,
            "drug_id"    : d_id,
            "food_id"    : f_id,
            "drug_found" : d_id is not None,
            "food_found" : f_id is not None,
            "score"      : score,
        }

    def batch_score(self, pairs: list[tuple[str, str]]) -> list[dict]:
        """Score a list of (drug_name, food_name) pairs. Returns list of dicts."""
        return [self.score_by_name(d, f) for d, f in pairs]

    def score_all_foods_for_drug(self, drug_name: str) -> np.ndarray | None:
        """
        Return sigmoid scores for drug vs ALL 1894 foods at once.
        Returns ndarray shape (1894,) or None if drug not found.
        """
        d_id = self.resolve_drug(drug_name)
        if d_id is None:
            return None
        with torch.no_grad():
            d = self._drug_emb_final[d_id]                # (128,)
            scores = torch.sigmoid(self._food_emb_final @ d)  # (1894,)
        return scores.numpy()

    def top_k_foods(self, drug_name: str, k: int = 20) -> list[dict]:
        """Return top-k foods for a drug by LightGCN score."""
        scores = self.score_all_foods_for_drug(drug_name)
        if scores is None:
            return []
        idx = np.argsort(scores)[::-1][:k]
        return [
            {"rank": i+1, "food": self._food_id2name.get(int(j), f"id_{j}"),
             "food_id": int(j), "score": float(scores[j])}
            for i, j in enumerate(idx)
        ]


# ── Validation on 889 unseen pairs ───────────────────────────────────────────
if __name__ == "__main__":
    lgn = LightGCNInference(verbose=True)

    print("\n=== Validating on 889 unseen pairs ===")
    val = pd.read_csv(UNSEEN)
    print(f"Loaded {len(val)} pairs")

    results = []
    for _, row in val.iterrows():
        r = lgn.score_by_name(str(row["drug_name"]), str(row["food_name"]))
        results.append(r)

    scored   = [r for r in results if r["score"] is not None]
    d_miss   = [r for r in results if not r["drug_found"]]
    f_miss   = [r for r in results if not r["food_found"]]
    both_miss = [r for r in results if not r["drug_found"] and not r["food_found"]]

    print(f"\n--- Coverage ---")
    print(f"  Pairs scored           : {len(scored):4d} / {len(results)} ({100*len(scored)/len(results):.1f}%)")
    print(f"  Drug not in LGN        : {len(d_miss):4d} / {len(results)} ({100*len(d_miss)/len(results):.1f}%)")
    print(f"  Food not in LGN        : {len(f_miss):4d} / {len(results)} ({100*len(f_miss)/len(results):.1f}%)")
    print(f"  Both missing           : {len(both_miss):4d} / {len(results)}")

    scores_arr = np.array([r["score"] for r in scored])
    print(f"\n--- Score distribution (scored pairs only) ---")
    for q in [0, 10, 25, 50, 75, 90, 100]:
        print(f"  p{q:3d}: {np.percentile(scores_arr, q):.4f}")

    # Threshold analysis
    print(f"\n--- Pairs above threshold ---")
    for thr in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        n = int((scores_arr >= thr).sum())
        print(f"  score >= {thr:.1f} : {n:4d} / {len(scored)} ({100*n/len(scored):.1f}%)")

    # Top 20 highest-scoring
    print(f"\n--- Top 20 highest-scoring pairs ---")
    top20 = sorted(scored, key=lambda x: -x["score"])[:20]
    for r in top20:
        print(f"  {r['score']:.4f}  {r['drug'][:35]:35s}  ×  {r['food']}")

    # Missing drug names (unique)
    missing_drugs = sorted({r["drug"] for r in d_miss})
    print(f"\n--- {len(missing_drugs)} unique drugs missing from LGN (first 20) ---")
    for n in missing_drugs[:20]:
        print(f"  {n}")

    missing_foods = sorted({r["food"] for r in f_miss})
    print(f"\n--- {len(missing_foods)} unique foods missing from LGN (first 20) ---")
    for n in missing_foods[:20]:
        print(f"  {n}")

    # Save results
    out_path = VAL_DIR / "phase3_lgn_scores.csv"
    pd.DataFrame(results).to_csv(out_path, index=False)
    print(f"\nResults saved → {out_path}")

    # Export full embedding matrices for Phase 4 use
    emb_out = VAL_DIR.parent / "data/mechanistic_kge"
    np.save(emb_out / "lgn_drug_embeddings.npy",  lgn._drug_emb_final.numpy())
    np.save(emb_out / "lgn_food_embeddings.npy",  lgn._food_emb_final.numpy())
    print(f"LGN embeddings exported:")
    print(f"  lgn_drug_embeddings.npy  {lgn._drug_emb_final.shape}")
    print(f"  lgn_food_embeddings.npy  {lgn._food_emb_final.shape}")

    print("\nPhase 3 complete.")
