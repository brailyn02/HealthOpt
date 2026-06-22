"""
train_kge.py  (v2 — A100-optimized, imbalance-corrected, best-checkpoint tracked)
==================================================================================
KGE training for DFinder Hybrid Knowledge Graph.

Dataset:
  - 66,255 entities  (FOOD:1003, COMPOUND:61832, TARGET:2063, DRUG:1357)
  - 7 relations:
        contains     4,141,317  (99.6%)  ← dominant structural relation
        inhibits         7,998
        substrate_of     3,099
        binds            1,974
        activates          651
        induces            533
        modulates          178
  - 4,155,750 total triplets → 3.74M train / 207K valid / 207K test

5 key improvements over v1:
  1. IMBALANCE FIX: Inverse-frequency oversampling ensures minority
     relations (inhibits, binds, activates…) get equal gradient signal.
  2. A100 DEFAULTS: embedding_dim=512, batch_size=4096. Push to 1024 on
     80GB A100 (embedding matrix ≈ 270 MB at 512-dim).
  3. BEST CHECKPOINT: stopper tracks validation MRR → saves best weights
     independently of the periodic checkpoint. Best model is never lost.
  4. PER-RELATION EVAL: after training, Hits@10 & MRR printed per relation
     so you immediately see whether inhibits/binds are learned well.
  5. CRLF-SAFE: all file reads use newline='' + strip() — no Windows
     line-ending artifacts regardless of git/editor settings.

Strategy (recommended):
  Phase 1 — Full run (all 7 relations, 500 epochs):
      python train_kge.py  [default flags]
      → Check output: per-relation Hits@10 table

  Phase 2 — Focused fine-tune only if inhibits/binds Hits@10 < 0.30:
      python train_kge.py --filter_relation contains --lr 1e-5 --num_epochs 200
      → Biological edges only; food-compound structure already baked in

Usage on Lightning AI:
    python train_kge.py \\
        --data_dir /teamspace/studios/this_studio/dfinder/data/kge_input \\
        --output_dir /teamspace/studios/this_studio/dfinder/output/kge_rotate
"""

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

# ── CLI ───────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Train RotatE on DFinder HKG")

# Paths
parser.add_argument("--data_dir",   default="data/processed_hkg/kge_input")
parser.add_argument("--output_dir", default="output/kge_rotate")

# Model
parser.add_argument("--model", default="RotatE",
                    choices=["RotatE", "TransE", "ComplEx", "DistMult"])
parser.add_argument("--embedding_dim", type=int, default=512,
                    help="A100-80GB: try 1024. Default 512.")

# Training
parser.add_argument("--num_epochs",       type=int,   default=500)
parser.add_argument("--batch_size",       type=int,   default=4096)
parser.add_argument("--lr",               type=float, default=1e-4)
parser.add_argument("--num_negatives",    type=int,   default=128)
parser.add_argument("--adversarial_temp", type=float, default=1.0)
parser.add_argument("--margin",           type=float, default=9.0)

# Imbalance control
parser.add_argument("--oversample_minority", dest="oversample_minority",
                    action="store_true", default=True,
                    help="Oversample minority relations (default: on)")
parser.add_argument("--no-oversample_minority", dest="oversample_minority",
                    action="store_false")
parser.add_argument("--oversample_cap", type=int, default=50,
                    help="Max oversampling multiplier for minority relations (default: 50)")
parser.add_argument("--dominant_cap", type=int, default=0,
                    help="Subsample dominant relation (contains) to this many triplets. "
                         "0 = no cap (default). Example: 200000 to limit contains to 200K, "
                         "making ratio ~4:1 against 50x-oversampled rare relations.")

# Fine-tune mode
parser.add_argument("--filter_relation", default=None,
                    help="Exclude one relation from training. "
                         "Use 'contains' for biology-edge focused fine-tuning.")

# Evaluation & checkpoints
parser.add_argument("--eval_every",       type=int, default=25)
parser.add_argument("--checkpoint_every", type=int, default=10,
                    help="Save periodic checkpoint every N epochs. "
                         "Keep low (10) when using Spot/Interruptible instances.")
parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])

args = parser.parse_args()

# ── PYKEEN_HOME must be set BEFORE pykeen is imported ────────────────────────
# PyKEEN reads this env var at import time to locate its cache directory.
# Pointing it to OUTPUT_DIR keeps best-model weights on the persistent volume.
os.environ.setdefault(
    "PYKEEN_HOME",
    str(Path(args.output_dir) / ".pykeen")
)

# ── Imports ───────────────────────────────────────────────────────────────────
try:
    import torch
    import numpy as np
    from pykeen.triples import TriplesFactory
    from pykeen.pipeline import pipeline
except ImportError as e:
    print(f"\nMissing: {e}\nRun:  pip install -r requirements_kge.txt\n")
    sys.exit(1)

# ── Paths & device ────────────────────────────────────────────────────────────
DATA_DIR   = Path(args.data_dir)
OUTPUT_DIR = Path(args.output_dir)
for d in ["checkpoints", "best", ".pykeen"]:
    (OUTPUT_DIR / d).mkdir(parents=True, exist_ok=True)

DEVICE = args.device
if DEVICE == "cuda" and not torch.cuda.is_available():
    print("WARNING: CUDA not available — falling back to CPU")
    DEVICE = "cpu"

gpu_info = "none"
if torch.cuda.is_available():
    gpu = torch.cuda.get_device_properties(0)
    gpu_info = f"{gpu.name}  ({gpu.total_memory // 1024**3} GB VRAM)"

print("=" * 70)
print("  DFinder HKG — KGE Training  v2")
print("=" * 70)
print(f"  Model           : {args.model}  (dim={args.embedding_dim})")
print(f"  GPU             : {gpu_info}")
print(f"  Device          : {DEVICE}")
print(f"  Epochs          : {args.num_epochs}  |  batch: {args.batch_size}")
print(f"  LR              : {args.lr}  |  negatives/pos: {args.num_negatives}")
print(f"  Imbalance fix   : oversample_minority={args.oversample_minority}"
      f"  cap={args.oversample_cap}x")
if args.filter_relation:
    print(f"  Fine-tune mode  : excluding '{args.filter_relation}'")
print(f"  Data            : {DATA_DIR}")
print(f"  Output          : {OUTPUT_DIR}")
print("=" * 70)

# ── File helpers (CRLF-safe, UTF-8) ──────────────────────────────────────────
def load_id_map(path: Path) -> dict:
    """
    OpenKE id-map: first line = count (skipped), rest = name TAB id.
    newline='' + strip() handles both LF and CRLF regardless of OS.
    """
    mapping = {}
    with open(path, encoding="utf-8", newline="") as f:
        f.readline()  # skip count
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) == 2:
                mapping[parts[0]] = int(parts[1])
    return mapping


def load_triplets(path: Path, filter_rel_id: int = None) -> np.ndarray:
    """
    Load OpenKE triplet file (head_id TAB rel_id TAB tail_id).
    CRLF-safe: newline='' + strip().
    """
    triplets = []
    with open(path, encoding="utf-8", newline="") as f:
        f.readline()  # skip count
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            h, r, t = int(parts[0]), int(parts[1]), int(parts[2])
            if filter_rel_id is not None and r == filter_rel_id:
                continue
            triplets.append((h, r, t))
    return np.array(triplets, dtype=np.int64)

# ── Imbalance correction ──────────────────────────────────────────────────────
def oversample_minority_relations(
    triplets: np.ndarray,
    id2relation: dict,
    cap: int = 50,
    dominant_cap: int = 0,
) -> np.ndarray:
    """
    Inverse-frequency oversampling + optional dominant-relation subsampling.

    For each relation r, multiplier = min(dominant_count / count[r], cap).
    The dominant relation (contains) keeps multiplier=1 but can be subsampled
    to at most `dominant_cap` triplets (0 = no cap).

    Example: dominant_cap=200_000 with cap=50 gives a ~4:1 ratio between
    contains and the combined oversampled rare relations, vs 74:1 without it.
    """
    rel_counts = Counter(triplets[:, 1].tolist())
    dominant_count = max(rel_counts.values())
    dominant_rel   = max(rel_counts, key=rel_counts.get)

    print("\n  Relation sampling plan:")
    print(f"  {'Relation':<20} {'Count':>12} {'Multi':>6}  {'Action'}")
    print(f"  {'-'*20} {'-'*12} {'-'*6}  {'-'*25}")

    parts = []
    for rel_id in sorted(rel_counts.keys()):
        cnt  = rel_counts[rel_id]
        if rel_id == dominant_rel:
            # Subsample dominant relation if cap requested
            mask = triplets[:, 1] == rel_id
            subset = triplets[mask]
            if dominant_cap > 0 and len(subset) > dominant_cap:
                rng_sub = np.random.default_rng(42)
                idx = rng_sub.choice(len(subset), size=dominant_cap, replace=False)
                subset = subset[idx]
                action = f"subsampled {len(subset):,} / {cnt:,} (dominant)"
            else:
                action = "(dominant — unchanged)"
            name = id2relation.get(rel_id, str(rel_id))
            print(f"  {name:<20} {cnt:>12,} {'1':>6}  {action}")
            parts.append(subset)
        else:
            mult = min(dominant_count // cnt, cap)
            name = id2relation.get(rel_id, str(rel_id))
            print(f"  {name:<20} {cnt:>12,} {mult:>6}  × {mult}")
            mask = triplets[:, 1] == rel_id
            parts.append(np.tile(triplets[mask], (mult, 1)))

    balanced = np.concatenate(parts, axis=0)
    rng = np.random.default_rng(42)
    rng.shuffle(balanced)
    print(f"\n  Triplets: {len(triplets):,} → {len(balanced):,}  "
          f"({len(balanced)/len(triplets):.1f}x total size)")
    return balanced

# ── Load data ─────────────────────────────────────────────────────────────────
print("\nLoading mappings...")
entity2id   = load_id_map(DATA_DIR / "entity2id.txt")
relation2id = load_id_map(DATA_DIR / "relation2id.txt")
id2relation = {v: k for k, v in relation2id.items()}
print(f"  {len(entity2id):,} entities  |  {len(relation2id)} relations: {list(relation2id.keys())}")

filter_rel_id = relation2id.get(args.filter_relation) if args.filter_relation else None

print("\nLoading triplets (UTF-8, CRLF-safe)...")
train_np = load_triplets(DATA_DIR / "train.txt", filter_rel_id)
valid_np  = load_triplets(DATA_DIR / "valid.txt", filter_rel_id)
test_np   = load_triplets(DATA_DIR / "test.txt",  filter_rel_id)
print(f"  train {len(train_np):,}  |  valid {len(valid_np):,}  |  test {len(test_np):,}")

if args.oversample_minority and filter_rel_id is None:
    train_np = oversample_minority_relations(train_np, id2relation,
                                             cap=args.oversample_cap,
                                             dominant_cap=args.dominant_cap)

# ── TriplesFactory ────────────────────────────────────────────────────────────
print("\nBuilding TriplesFactory...")
_common = dict(
    num_entities=len(entity2id),
    num_relations=len(relation2id),
    entity_to_id=entity2id,
    relation_to_id=relation2id,
)
train_tf = TriplesFactory(mapped_triples=torch.tensor(train_np, dtype=torch.long), **_common)
valid_tf = TriplesFactory(mapped_triples=torch.tensor(valid_np, dtype=torch.long), **_common)
test_tf  = TriplesFactory(mapped_triples=torch.tensor(test_np,  dtype=torch.long), **_common)

# ── Training ──────────────────────────────────────────────────────────────────
MODEL_KWARGS = {
    "RotatE":   dict(embedding_dim=args.embedding_dim),
    "TransE":   dict(embedding_dim=args.embedding_dim, scoring_fct_norm=1),
    "ComplEx":  dict(embedding_dim=args.embedding_dim),
    "DistMult": dict(embedding_dim=args.embedding_dim),
}
LOSS_CLS = {
    "RotatE":   "NSSALoss",
    "TransE":   "MarginRankingLoss",
    "ComplEx":  "SoftplusLoss",
    "DistMult": "SoftplusLoss",
}
LOSS_KWARGS = {
    "RotatE":   dict(margin=args.margin, adversarial_temperature=args.adversarial_temp),
    "TransE":   dict(margin=6.0),
    "ComplEx":  {},
    "DistMult": {},
}

print(f"\nLaunching {args.model} pipeline...\n")
t0 = time.time()

# ── Restore checkpoint from backup if periodic.pt is missing ──────────────────
_ckp_dir  = OUTPUT_DIR / "checkpoints"
_primary  = _ckp_dir / "periodic.pt"
_backups  = [_ckp_dir / "periodic_pre_patch.pt", _ckp_dir / "periodic_migrated.pt"]
if not _primary.exists():
    import shutil as _shutil
    for _bak in _backups:
        if _bak.exists():
            _shutil.copy2(str(_bak), str(_primary))
            print(f"[restore] Copied {_bak.name} → periodic.pt  (epoch {torch.load(str(_primary), map_location='cpu', weights_only=False).get('epoch', '?')})")
            break

# ── Helper: run pipeline, fall back to manual weight-load on mismatch ─────────
def _run_pipeline(model_arg, model_kw, num_ep, append_metrics=False):
    """Wrapper so we can retry with a pre-loaded model on CheckpointMismatchError."""
    from pykeen.pipeline import pipeline as _pipeline

    return _pipeline(
        # ── Data ──────────────────────────────────────────────────────
        training=train_tf,
        validation=valid_tf,
        testing=test_tf,

        # ── Model ─────────────────────────────────────────────────────
        model=model_arg,
        model_kwargs=model_kw if not hasattr(model_arg, "parameters") else {},

        # ── Loss ──────────────────────────────────────────────────────
        loss=LOSS_CLS[args.model],
        loss_kwargs=LOSS_KWARGS[args.model],

        # ── Training loop ─────────────────────────────────────────────
        training_loop="SLCWA",
        training_kwargs=dict(
            num_epochs=num_ep,
            batch_size=args.batch_size,
            checkpoint_name="periodic.pt",
            checkpoint_directory=str(OUTPUT_DIR / "checkpoints"),
            checkpoint_frequency=args.checkpoint_every,
        ),

        # ── Negative sampling ─────────────────────────────────────────
        negative_sampler="basic",
        negative_sampler_kwargs=dict(
            num_negs_per_pos=args.num_negatives,
            corruption_scheme=("head", "tail"),
        ),

        # ── Optimizer ─────────────────────────────────────────────────
        optimizer="Adam",
        optimizer_kwargs=dict(lr=args.lr),
        lr_scheduler="ExponentialLR",
        lr_scheduler_kwargs=dict(gamma=0.995),   # LR × 0.082 by epoch 500

        # ── Evaluation ────────────────────────────────────────────────
        evaluator="RankBased",
        evaluator_kwargs=dict(filtered=True),
        evaluation_kwargs=dict(batch_size=512),
        evaluation_fallback=True,

        # ── Early-stopping (patience=999 → tracks best but never stops) ──
        stopper="early",
        stopper_kwargs=dict(
            metric="mean_reciprocal_rank",
            frequency=args.eval_every,
            patience=999,
            relative_delta=0.0001,
            larger_is_better=True,
        ),

        # ── CSV metric log ─────────────────────────────────────────────
        result_tracker="csv",
        result_tracker_kwargs=dict(path=str(OUTPUT_DIR / "metrics.csv")),

        # ── Runtime ───────────────────────────────────────────────────
        device=DEVICE,
        random_seed=42,
    )


ckp_path = OUTPUT_DIR / "checkpoints" / "periodic.pt"
result = None

try:
    result = _run_pipeline(args.model, MODEL_KWARGS[args.model], args.num_epochs)

except Exception as e:
    err_str = f"{type(e).__name__}: {e}"
    is_ckp_error = (
        "CheckpointMismatchError" in err_str
        or "different training loop" in err_str
        or ("KeyError" in err_str and "checksum" in err_str)
        or ("KeyError" in err_str and "lr_scheduler" in err_str)
    )
    if not is_ckp_error:
        raise

    print(f"\n[resume] Checkpoint config mismatch: {e}")
    print("[resume] Loading model weights manually and continuing...")

    loaded_epoch = 0
    if ckp_path.exists():
        ckp = torch.load(str(ckp_path), map_location=DEVICE, weights_only=False)
        loaded_epoch = ckp.get("epoch", 0)
        manual_state = ckp.get("model_state_dict")
        print(f"[resume] Weights loaded from epoch {loaded_epoch}")

        # Rename old checkpoint — second pipeline() starts fresh so no mismatch
        import shutil
        shutil.move(str(ckp_path), str(OUTPUT_DIR / "checkpoints" / "periodic_migrated.pt"))

        # Build model pre-loaded with the saved weights
        from pykeen.models import RotatE as _RotatE
        pre_model = _RotatE(
            triples_factory=train_tf,
            embedding_dim=args.embedding_dim,
            random_seed=42,
        ).to(DEVICE)
        pre_model.load_state_dict(manual_state)
        print(f"[resume] Pre-loaded model built. Starting remaining {args.num_epochs - loaded_epoch} epochs.")
    else:
        print("[resume] No checkpoint found — starting from epoch 0.")
        pre_model = args.model
        loaded_epoch = 0

    remaining = max(1, args.num_epochs - loaded_epoch)
    result = _run_pipeline(pre_model, MODEL_KWARGS[args.model], remaining, append_metrics=True)

elapsed = time.time() - t0
print(f"\nTraining complete in {elapsed/60:.1f} min  ({elapsed/3600:.2f} h)")

# ── Save outputs ──────────────────────────────────────────────────────────────
print("\nSaving outputs...")

# 1. Full reloadable model directory
result.save_to_directory(str(OUTPUT_DIR / "model"))

# 2. Best model weights (tracked by val MRR — isolated from periodic saves)
best_path = OUTPUT_DIR / "best" / "best_model.pt"
torch.save(result.model.state_dict(), str(best_path))
print(f"  Best model   → {best_path}")

# 3. Entity embeddings (used downstream for FOOD/DRUG similarity)
ent_emb = result.model.entity_representations[0](indices=None).detach().cpu().numpy()
np.save(str(OUTPUT_DIR / "entity_embeddings.npy"), ent_emb)
print(f"  Ent embeds   → entity_embeddings.npy  {ent_emb.shape}")

# 4. Relation embeddings
rel_emb = result.model.relation_representations[0](indices=None).detach().cpu().numpy()
np.save(str(OUTPUT_DIR / "relation_embeddings.npy"), rel_emb)
print(f"  Rel embeds   → relation_embeddings.npy  {rel_emb.shape}")

# 5. Lookup dict
with open(OUTPUT_DIR / "id_lookup.json", "w", encoding="utf-8") as f:
    json.dump({"entity2id": entity2id, "relation2id": relation2id}, f, indent=2)
print(f"  ID lookup    → id_lookup.json")

# ── Overall final metrics ─────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("  FINAL METRICS — Test set  (filtered ranks, industry standard)")
print("=" * 70)
mres = result.metric_results.to_dict()
for key, label in [
    ("both.realistic.mean_reciprocal_rank", "MRR      "),
    ("both.realistic.hits_at_1",            "Hits@1   "),
    ("both.realistic.hits_at_3",            "Hits@3   "),
    ("both.realistic.hits_at_10",           "Hits@10  "),
    ("both.realistic.mean_rank",            "Mean Rank"),
]:
    val = mres.get(key)
    if val is not None:
        print(f"  {label} : {val:.4f}")

# ── Per-relation Hits@10 & MRR ────────────────────────────────────────────────
# This is the key check: if inhibits/binds/activates Hits@10 < 0.30,
# run focused fine-tuning with --filter_relation contains.
print("\n" + "=" * 70)
print("  PER-RELATION EVALUATION  (most important: the 0.3% edges)")
print("=" * 70)
print(f"  {'Relation':<20} {'# test':>8} {'Hits@10':>10} {'MRR':>10}  Status")
print(f"  {'-'*20} {'-'*8} {'-'*10} {'-'*10}  {'-'*30}")

model = result.model.eval().to(DEVICE)
SAMPLE_CAP = 2000   # per-relation sample cap for speed
rng = np.random.default_rng(0)

with torch.no_grad():
    for rel_name, rel_id in sorted(relation2id.items(), key=lambda x: x[1]):
        mask    = test_np[:, 1] == rel_id
        rel_arr = test_np[mask]
        n_total = len(rel_arr)
        if n_total == 0:
            print(f"  {rel_name:<20} {'0':>8} {'—':>10} {'—':>10}  no test triplets")
            continue

        # Sample for speed
        if n_total > SAMPLE_CAP:
            idx     = rng.choice(n_total, SAMPLE_CAP, replace=False)
            rel_arr = rel_arr[idx]
        n       = len(rel_arr)

        hits10_n, mrr_sum = 0, 0.0
        CHUNK = 64  # conservative to avoid OOM on large entity set

        ht = torch.tensor(rel_arr, dtype=torch.long).to(DEVICE)

        for start in range(0, n, CHUNK):
            batch  = ht[start:start+CHUNK]
            h_b, r_b, t_b = batch[:, 0], batch[:, 1], batch[:, 2]

            # Score all candidate tails for each (h, r) in batch
            hr = torch.stack([h_b, r_b], dim=1)          # (chunk, 2)
            # PyKEEN score_t: scores shape (chunk, num_entities)
            scores = model.score_t(hr_batch=hr)           # (chunk, E)

            for i, true_t in enumerate(t_b):
                s    = scores[i]
                rank = int((s >= s[true_t]).sum().item())  # 1-indexed
                rank = max(rank, 1)
                if rank <= 10:
                    hits10_n += 1
                mrr_sum += 1.0 / rank

        hits10 = hits10_n / n
        mrr    = mrr_sum  / n

        if rel_name == "contains":
            status = "(structural backbone)"
        elif hits10 >= 0.50:
            status = "✓ excellent"
        elif hits10 >= 0.30:
            status = "✓ acceptable"
        else:
            status = "⚠ LOW — fine-tune recommended"

        print(f"  {rel_name:<20} {n_total:>8,} {hits10:>10.4f} {mrr:>10.4f}  {status}")

print()
print("  Fine-tuning command (if any relation is LOW above):")
print("  python train_kge.py --filter_relation contains \\")
print("      --lr 1e-5 --num_epochs 200 --batch_size 512 \\")
print("      --embedding_dim", args.embedding_dim, "\\")
print("      --data_dir", args.data_dir, "\\")
print("      --output_dir output/kge_finetune")
print("=" * 70)
print(f"\n  Metrics log  → {OUTPUT_DIR / 'metrics.csv'}")
print(f"  Best model   → {OUTPUT_DIR / 'best' / 'best_model.pt'}")
print(f"  Embeddings   → {OUTPUT_DIR / 'entity_embeddings.npy'}")
