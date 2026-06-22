"""
Per-relation evaluation of the saved RotatE model (Run 1, epoch ~257).
Computes MRR, Hits@1, Hits@3, Hits@10 for EACH relation separately.
Uses numpy-only scoring (no PyKEEN dependency needed locally).
"""

import numpy as np
from pathlib import Path
from collections import Counter

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE        = Path(__file__).parent
BACKUP      = BASE / "checkpoints_backup"
KGE_DIR     = BASE / "data" / "processed_hkg" / "kge_input"

ENT_EMB     = BACKUP / "deploy_entity_embeddings.npy"
REL_EMB     = BACKUP / "deploy_relation_embeddings.npy"
ENTITY2ID   = KGE_DIR / "entity2id.txt"
RELATION2ID = KGE_DIR / "relation2id.txt"
TEST_FILE   = KGE_DIR / "test.txt"
TRAIN_FILE  = KGE_DIR / "train.txt"
VALID_FILE  = KGE_DIR / "valid.txt"

# ── Load embeddings ────────────────────────────────────────────────────────────
print("Loading embeddings...")
ent = np.load(str(ENT_EMB)).astype(np.float32)   # [n_ent, 2*dim]
rel = np.load(str(REL_EMB)).astype(np.float32)   # [n_rel, dim] (phases)
n_ent, ent_dim = ent.shape
n_rel, rel_dim = rel.shape
embed_dim = ent_dim // 2
print(f"  entity embeddings : {ent.shape}  (embedding_dim={embed_dim})")
print(f"  relation embeddings: {rel.shape}")

# ── Load ID maps ───────────────────────────────────────────────────────────────
def load_id_map(path):
    m = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) == 2:
                m[parts[0]] = int(parts[1])
    return m

entity2id   = load_id_map(ENTITY2ID)
relation2id = load_id_map(RELATION2ID)
id2relation = {v: k for k, v in relation2id.items()}
print(f"\n  {len(entity2id):,} entities  |  {len(relation2id)} relations: {list(relation2id.keys())}")

# ── Load triplets ──────────────────────────────────────────────────────────────
def load_triplets(path):
    trips = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) == 3:
                try:
                    trips.append([int(parts[0]), int(parts[1]), int(parts[2])])
                except ValueError:
                    pass
    return np.array(trips, dtype=np.int64) if trips else np.zeros((0, 3), dtype=np.int64)

print("\nLoading triplets...")
test_np  = load_triplets(TEST_FILE)
train_np = load_triplets(TRAIN_FILE)
valid_np = load_triplets(VALID_FILE)
all_np   = np.concatenate([train_np, valid_np, test_np], axis=0)

print(f"  train: {len(train_np):,}  valid: {len(valid_np):,}  test: {len(test_np):,}")
print(f"  relation dist in test: {Counter(test_np[:,1].tolist())}")

# ── RotatE scoring ─────────────────────────────────────────────────────────────
# entity_emb[e] = [re_0..re_{d-1}, im_0..im_{d-1}]  (stacked halves)
# relation_emb[r] = phases [phi_0..phi_{d-1}]
# score(h,r,t) = -||h∘r - t||  in complex space

# ── Build filtered-ranking lookup: (h,r) → set of all true tails ─────────────
print("\nBuilding filtered-ranking lookup...")
from collections import defaultdict
hr_to_true_tails = defaultdict(set)
for h, r, t in all_np.tolist():
    hr_to_true_tails[(h, r)].add(t)
print(f"  {len(hr_to_true_tails):,} (h,r) pairs indexed")

# ── Per-relation evaluation ────────────────────────────────────────────────────
def evaluate_relation(rel_id, triplets, max_triplets=500):
    """Filtered tail ranking for test triplets of this relation."""
    rel_name = id2relation[rel_id]
    mask = triplets[:, 1] == rel_id
    rel_trips = triplets[mask]
    if len(rel_trips) == 0:
        return None

    sampled = rel_trips
    note = ""
    if len(rel_trips) > max_triplets:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(rel_trips), size=max_triplets, replace=False)
        sampled = rel_trips[idx]
        note = f" (sampled {max_triplets}/{len(rel_trips)})"

    r_re   = rel[rel_id, :embed_dim]    # [d]  cos(φ) — already unit-normalized
    r_im   = rel[rel_id, embed_dim:]    # [d]  sin(φ)
    t_re_all = ent[:, :embed_dim]   # [n_ent, d]
    t_im_all = ent[:, embed_dim:]   # [n_ent, d]

    ranks = []
    for i, (h, r, t) in enumerate(sampled.tolist()):
        h_re = ent[h, :embed_dim]           # [d]
        h_im = ent[h, embed_dim:]           # [d]
        hr_re = h_re * r_re - h_im * r_im   # [d]
        hr_im = h_re * r_im + h_im * r_re   # [d]

        # score vs all entities: -||hr - t_all||  → [n_ent]
        diff_re = hr_re[None, :] - t_re_all  # [n_ent, d]
        diff_im = hr_im[None, :] - t_im_all  # [n_ent, d]
        scores  = -np.sqrt((diff_re**2 + diff_im**2).sum(-1))  # [n_ent]

        target_score = scores[t]
        # Filtered: mask other true tail answers for (h, r) using precomputed lookup
        other_trues = hr_to_true_tails[(h, r)] - {t}
        if other_trues:
            scores[np.array(list(other_trues), dtype=np.int64)] = -1e9

        rank = int((scores > target_score).sum()) + 1
        ranks.append(rank)
        if i % 50 == 0:
            print(f"    [{rel_name}] {i+1}/{len(sampled)}{note}", end="\r")

    ranks = np.array(ranks)
    mrr   = float((1.0 / ranks).mean())
    h1    = float((ranks <= 1).mean())
    h3    = float((ranks <= 3).mean())
    h10   = float((ranks <= 10).mean())
    med   = float(np.median(ranks))
    print(f"    [{rel_name}] done{note}                    ")
    return {"relation": rel_name, "n_eval": len(ranks), "n_total": len(rel_trips),
            "MRR": mrr, "H@1": h1, "H@3": h3, "H@10": h10, "median_rank": med}

# ── Run evaluation for all relations ──────────────────────────────────────────
print("\n" + "="*70)
print("Per-Relation Evaluation on TEST set (filtered tail ranking)")
print("Model: Run 1, epoch ~257, MRR_aggregate=0.1718")
print("="*70)

results = []
for rel_id in sorted(id2relation.keys()):
    rel_name = id2relation[rel_id]
    print(f"\n[{rel_name}] (rel_id={rel_id})")
    r = evaluate_relation(rel_id, test_np)
    if r:
        results.append(r)
        print(f"  n={r['n_eval']}/{r['n_total']}  MRR={r['MRR']:.4f}  H@1={r['H@1']:.4f}  "
              f"H@3={r['H@3']:.4f}  H@10={r['H@10']:.4f}  median_rank={r['median_rank']:.0f}")
    else:
        print(f"  no test triplets for this relation")

# ── Summary table ──────────────────────────────────────────────────────────────
print("\n\n" + "="*70)
print(f"{'Relation':<20} {'Eval/Total':>12}  {'MRR':>8}  {'H@1':>8}  {'H@3':>8}  {'H@10':>8}  {'Med.Rank':>10}")
print("-"*80)
for r in sorted(results, key=lambda x: -x["MRR"]):
    nt = f"{r['n_eval']}/{r['n_total']}"
    print(f"{r['relation']:<20} {nt:>12}  {r['MRR']:>8.4f}  {r['H@1']:>8.4f}  "
          f"{r['H@3']:>8.4f}  {r['H@10']:>8.4f}  {r['median_rank']:>10.0f}")

# Weighted aggregate (by n_total for fairness)
if results:
    total_eval = sum(r["n_eval"] for r in results)
    w_mrr = sum(r["MRR"] * r["n_eval"] for r in results) / total_eval
    w_h10 = sum(r["H@10"] * r["n_eval"] for r in results) / total_eval
    print("-"*80)
    print(f"{'WEIGHTED AGGREGATE':<20} {total_eval:>12}  {w_mrr:>8.4f}  {'':>8}  {'':>8}  {w_h10:>8.4f}")
print("="*80)
