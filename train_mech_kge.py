"""
Phase 1 — Train Mechanistic RotatE KGE
Pure PyTorch, CPU-friendly, no PyKEEN dependency.
Input : data/mechanistic_kge/  (from prepare_phase0.py)
Output: data/mechanistic_kge/  (embeddings + checkpoint)
"""

import os, math, random, time
import numpy as np
import torch
import torch.nn as nn
from torch.optim import Adam
from pathlib import Path
from collections import defaultdict

# ── Config ───────────────────────────────────────────────────────────────────
ROOT       = Path("D:/23AIBox-DFinder")
MECH_DIR   = ROOT / "data/mechanistic_kge"

EMB_DIM    = 128          # embedding dim (128 = real part; RotatE uses 128 complex)
EPOCHS     = 300
BATCH_SIZE = 256
LR         = 1e-3
NEG_RATIO  = 64           # negative samples per positive
ADV_TEMP   = 1.0          # adversarial temperature (0 = uniform negatives)
GAMMA      = 12.0         # margin (standard RotatE setting)
EVAL_EVERY = 10           # evaluate on validation set every N epochs
SAVE_EVERY = 50           # save checkpoint every N epochs
SEED       = 42

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

device = torch.device("cpu")
print(f"Device: {device}")

# ── Load ID maps ─────────────────────────────────────────────────────────────
def load_id_map(path):
    id_map = {}
    with open(path) as f:
        n = int(f.readline().strip())
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) == 2:
                id_map[parts[0]] = int(parts[1])
    return id_map

entity2id  = load_id_map(MECH_DIR / "mech_entity2id.txt")
relation2id = load_id_map(MECH_DIR / "mech_relation2id.txt")
id2entity  = {v: k for k, v in entity2id.items()}
id2relation = {v: k for k, v in relation2id.items()}

N_ENTITY   = len(entity2id)
N_RELATION = len(relation2id)
print(f"Entities: {N_ENTITY}, Relations: {N_RELATION}")

# ── Load triplets ─────────────────────────────────────────────────────────────
def load_split(path):
    triples = []
    with open(path) as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) == 3:
                triples.append((int(parts[0]), int(parts[1]), int(parts[2])))
    return np.array(triples, dtype=np.int64)

train_data = load_split(MECH_DIR / "mech_train.txt")
valid_data = load_split(MECH_DIR / "mech_valid.txt")
test_data  = load_split(MECH_DIR / "mech_test.txt")

print(f"Train: {len(train_data)}, Valid: {len(valid_data)}, Test: {len(test_data)}")

# Build true-tail lookup for filtered ranking
all_data = np.concatenate([train_data, valid_data, test_data], axis=0)
hr_to_true = defaultdict(set)
for h, r, t in all_data:
    hr_to_true[(h, r)].add(t)

# ── RotatE Model ─────────────────────────────────────────────────────────────
class RotatE(nn.Module):
    def __init__(self, n_entity, n_relation, emb_dim, gamma):
        super().__init__()
        self.emb_dim   = emb_dim
        self.gamma     = gamma
        self.eps       = 2.0
        self.emb_range = (gamma + self.eps) / emb_dim

        # Entity embeddings: [re_0..re_{d-1}, im_0..im_{d-1}]  → size 2*d
        self.entity_emb   = nn.Embedding(n_entity,   emb_dim * 2)
        # Relation embeddings: phase only  → size d
        self.relation_emb = nn.Embedding(n_relation, emb_dim)

        nn.init.uniform_(self.entity_emb.weight,   -self.emb_range, self.emb_range)
        nn.init.uniform_(self.relation_emb.weight, -self.emb_range, self.emb_range)

    def score(self, h_idx, r_idx, t_idx):
        """
        Returns negative distance (higher = more likely).
        h_idx, r_idx, t_idx: LongTensors of shape (B,) or (B, N_neg)
        """
        pi = math.pi

        # Entity embeddings → complex
        h_emb = self.entity_emb(h_idx)   # (B, 2d) or (B, N, 2d)
        t_emb = self.entity_emb(t_idx)
        h_re, h_im = h_emb[..., :self.emb_dim], h_emb[..., self.emb_dim:]
        t_re, t_im = t_emb[..., :self.emb_dim], t_emb[..., self.emb_dim:]

        # Relation → phase angle in [-pi, pi]
        r_phase = self.relation_emb(r_idx) / (self.emb_range / pi)
        r_re = torch.cos(r_phase)
        r_im = torch.sin(r_phase)

        # RotatE: h ∘ r = (h_re*r_re - h_im*r_im,  h_re*r_im + h_im*r_re)
        rot_re = h_re * r_re - h_im * r_im
        rot_im = h_re * r_im + h_im * r_re

        # Distance to t
        diff_re = rot_re - t_re
        diff_im = rot_im - t_im

        dist = torch.sqrt(diff_re ** 2 + diff_im ** 2 + 1e-8).sum(dim=-1)
        return self.gamma - dist   # higher = better

    def forward(self, pos_h, pos_r, pos_t, neg_h, neg_r, neg_t):
        """
        pos_*: (B,)
        neg_*: (B, NEG_RATIO)
        Returns BPR-style adversarial loss.
        """
        pos_score = self.score(pos_h, pos_r, pos_t)          # (B,)
        neg_score = self.score(neg_h, neg_r, neg_t)          # (B, NEG_RATIO)

        # Adversarial weighting
        if ADV_TEMP > 0:
            neg_weight = torch.softmax(neg_score * ADV_TEMP, dim=-1).detach()
        else:
            neg_weight = torch.ones_like(neg_score) / neg_score.shape[-1]

        pos_loss = -torch.log(torch.sigmoid( pos_score) + 1e-8).mean()
        neg_loss = -(neg_weight * torch.log(torch.sigmoid(-neg_score) + 1e-8)).sum(dim=-1).mean()

        return (pos_loss + neg_loss) / 2

model = RotatE(N_ENTITY, N_RELATION, EMB_DIM, GAMMA).to(device)
optimizer = Adam(model.parameters(), lr=LR)
total_params = sum(p.numel() for p in model.parameters())
print(f"Model parameters: {total_params:,}")

# ── Evaluation (MRR, H@1, H@3, H@10, per relation) ──────────────────────────
@torch.no_grad()
def evaluate(data, split_name="valid", max_per_rel=200):
    model.eval()
    rel_metrics = defaultdict(lambda: {"ranks": []})

    # Group by relation
    by_rel = defaultdict(list)
    for h, r, t in data:
        by_rel[r].append((h, r, t))

    for r_id, triples in by_rel.items():
        # Cap per relation to keep eval fast
        if len(triples) > max_per_rel:
            triples = random.sample(triples, max_per_rel)

        for h, r, t in triples:
            h_t = torch.tensor([h], device=device)
            r_t = torch.tensor([r], device=device)
            # Score against ALL entities as tail
            all_t = torch.arange(N_ENTITY, device=device)
            h_rep = h_t.expand(N_ENTITY)
            r_rep = r_t.expand(N_ENTITY)
            scores = model.score(h_rep, r_rep, all_t).cpu().numpy()

            # Filtered ranking: mask out other true tails
            true_tails = hr_to_true[(h, r)] - {t}
            for tt in true_tails:
                scores[tt] = -1e9

            rank = (scores > scores[t]).sum() + 1
            rel_metrics[r_id]["ranks"].append(int(rank))

    results = {}
    all_ranks = []
    for r_id, m in rel_metrics.items():
        ranks = np.array(m["ranks"])
        all_ranks.extend(ranks.tolist())
        results[id2relation[r_id]] = {
            "MRR"    : float(np.mean(1.0 / ranks)),
            "H@1"    : float(np.mean(ranks <= 1)),
            "H@3"    : float(np.mean(ranks <= 3)),
            "H@10"   : float(np.mean(ranks <= 10)),
            "Med_Rank": float(np.median(ranks)),
            "N"      : len(ranks)
        }

    all_ranks = np.array(all_ranks)
    results["__ALL__"] = {
        "MRR"    : float(np.mean(1.0 / all_ranks)),
        "H@1"    : float(np.mean(all_ranks <= 1)),
        "H@3"    : float(np.mean(all_ranks <= 3)),
        "H@10"   : float(np.mean(all_ranks <= 10)),
        "Med_Rank": float(np.median(all_ranks)),
        "N"      : len(all_ranks)
    }

    print(f"\n  [{split_name}] {'Relation':<20} {'MRR':>6} {'H@1':>6} {'H@3':>6} {'H@10':>6} {'MedRk':>7} N")
    print(f"  {'-'*65}")
    for rel, m in sorted(results.items()):
        print(f"  {rel:<20} {m['MRR']:>6.4f} {m['H@1']:>6.4f} {m['H@3']:>6.4f} {m['H@10']:>6.4f} {m['Med_Rank']:>7.0f} {m['N']}")
    model.train()
    return results["__ALL__"]["MRR"]

# ── Negative Sampling ─────────────────────────────────────────────────────────
def corrupt_batch(batch_h, batch_r, batch_t):
    """
    For each positive, generate NEG_RATIO negatives by corrupting tail.
    Returns (neg_h, neg_r, neg_t) each of shape (B, NEG_RATIO).
    """
    B = batch_h.shape[0]
    neg_t = torch.randint(0, N_ENTITY, (B, NEG_RATIO), device=device)
    neg_h = batch_h.unsqueeze(1).expand(B, NEG_RATIO)
    neg_r = batch_r.unsqueeze(1).expand(B, NEG_RATIO)
    return neg_h, neg_r, neg_t

# ── Training Loop ─────────────────────────────────────────────────────────────
train_tensor = torch.tensor(train_data, dtype=torch.long, device=device)
best_mrr     = 0.0
best_epoch   = 0
metrics_log  = []

print(f"\nStarting training: {EPOCHS} epochs, batch={BATCH_SIZE}, neg={NEG_RATIO}, dim={EMB_DIM}")
print("=" * 65)

for epoch in range(1, EPOCHS + 1):
    model.train()
    t0 = time.time()

    # Shuffle
    perm = torch.randperm(len(train_tensor), device=device)
    train_shuffled = train_tensor[perm]

    total_loss = 0.0
    n_batches  = 0

    for i in range(0, len(train_shuffled), BATCH_SIZE):
        batch = train_shuffled[i: i + BATCH_SIZE]
        h = batch[:, 0]
        r = batch[:, 1]
        t = batch[:, 2]

        neg_h, neg_r, neg_t = corrupt_batch(h, r, t)

        optimizer.zero_grad()
        loss = model(h, r, t, neg_h, neg_r, neg_t)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        n_batches  += 1

    avg_loss = total_loss / n_batches
    elapsed  = time.time() - t0

    log_entry = {"epoch": epoch, "loss": avg_loss}

    # Evaluation
    if epoch % EVAL_EVERY == 0 or epoch == 1:
        mrr = evaluate(valid_data, split_name=f"valid ep{epoch}")
        log_entry["mrr"] = mrr
        if mrr > best_mrr:
            best_mrr   = mrr
            best_epoch = epoch
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "mrr": mrr,
            }, MECH_DIR / "mech_best.pt")
            print(f"  ★ New best MRR={mrr:.4f} at epoch {epoch} — saved")
        metrics_log.append(log_entry)
        print(f"  Epoch {epoch:4d}/{EPOCHS} | loss={avg_loss:.4f} | MRR={mrr:.4f} | best={best_mrr:.4f}@ep{best_epoch} | {elapsed:.1f}s")
    else:
        metrics_log.append(log_entry)
        if epoch % 10 == 0:
            print(f"  Epoch {epoch:4d}/{EPOCHS} | loss={avg_loss:.4f} | {elapsed:.1f}s")

    # Periodic checkpoint
    if epoch % SAVE_EVERY == 0:
        torch.save({
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
        }, MECH_DIR / f"mech_ep{epoch}.pt")
        print(f"  Checkpoint saved: mech_ep{epoch}.pt")

# ── Final Evaluation ──────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print(f"Training complete. Best validation MRR={best_mrr:.4f} at epoch {best_epoch}")
print("\nLoading best model for final TEST evaluation...")

ckpt = torch.load(MECH_DIR / "mech_best.pt", map_location=device)
model.load_state_dict(ckpt["model_state_dict"])

print("\nFINAL TEST SET RESULTS:")
evaluate(test_data, split_name="TEST", max_per_rel=500)

# ── Export Embeddings ─────────────────────────────────────────────────────────
print("\nExporting embeddings...")
model.eval()
with torch.no_grad():
    entity_emb   = model.entity_emb.weight.cpu().numpy()    # (N_entity, 2*dim)
    relation_emb = model.relation_emb.weight.cpu().numpy()  # (N_relation, dim)

np.save(MECH_DIR / "mech_entity_embeddings.npy",   entity_emb)
np.save(MECH_DIR / "mech_relation_embeddings.npy", relation_emb)
print(f"  mech_entity_embeddings.npy   shape: {entity_emb.shape}")
print(f"  mech_relation_embeddings.npy shape: {relation_emb.shape}")

# Save metrics log
import json
with open(MECH_DIR / "mech_training_log.json", "w") as f:
    json.dump(metrics_log, f, indent=2)
print(f"  mech_training_log.json saved")

print("\nPhase 1 complete. Ready for Phase 2 — Graph Query Engine.")
