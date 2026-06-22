"""
modal_train.py — DFinder KGE Training on Modal.com
====================================================
Runs train_kge.py on an A100-80GB GPU using a persistent Modal Volume for
data, checkpoints, and outputs.  Resumes automatically from periodic.pt
(epoch 50 already uploaded).

SETUP (one-time, run locally):
    pip install modal
    modal token new          # opens browser to authenticate

UPLOAD DATA + CHECKPOINT:
    modal run modal_train.py::upload

RUN TRAINING:
    modal run modal_train.py

PULL RESULTS (anytime while running or after):
    modal run modal_train.py::pull

Or use the PowerShell wrapper:
    powershell -ExecutionPolicy Bypass -File run_on_modal.ps1 -Upload
    powershell -ExecutionPolicy Bypass -File run_on_modal.ps1 -Run
    powershell -ExecutionPolicy Bypass -File run_on_modal.ps1 -Pull
"""

import os
from pathlib import Path

import modal

# ── App & Persistent Volume ───────────────────────────────────────────────────
app = modal.App("dfinder-kge")

# Volume persists across runs — data, checkpoints, metrics all live here
vol = modal.Volume.from_name("dfinder-vol", create_if_missing=True)

VOLUME_PATH = "/data"
DATA_DIR    = f"{VOLUME_PATH}/kge_input"
OUTPUT_DIR  = f"{VOLUME_PATH}/kge_rotate"

# ── Docker Image: PyTorch 2.5.1 + CUDA 12.1 + PyKEEN ─────────────────────────
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.5.1",
        extra_index_url="https://download.pytorch.org/whl/cu121",
    )
    .pip_install(
        "pykeen>=1.10.2",
        "numpy",
        "pandas",
        "tqdm",
        "click",
    )
)

# ── Training function (A100-80GB, up to 24 h) ─────────────────────────────────
@app.function(
    gpu="A100-80GB",
    timeout=86400,                   # 24-hour max
    volumes={VOLUME_PATH: vol},
    image=image,
    # Retry up to 2x automatically on preemption / transient failure
    retries=modal.Retries(max_retries=2, backoff_coefficient=1.0, initial_delay=10.0),
)
def train(
    num_epochs:       int = 500,
    embedding_dim:    int = 512,
    batch_size:       int = 4096,
    eval_every:       int = 25,
    checkpoint_every: int = 10,
    dominant_cap:     int = 200_000,   # subsample 'contains' to 200K → ~4:1 ratio vs rare relations
    oversample_cap:   int = 50,        # max multiplier for minority relations
):
    import subprocess
    import shutil
    import sys
    import time

    os.makedirs(f"{OUTPUT_DIR}/checkpoints", exist_ok=True)
    os.makedirs(f"{OUTPUT_DIR}/best",        exist_ok=True)

    script = f"{VOLUME_PATH}/train_kge.py"
    if not os.path.exists(script):
        raise FileNotFoundError(
            f"{script} not found on volume. "
            "Run: modal run modal_train.py::upload  first."
        )

    # Export script — extracts deployable files from periodic.pt after each commit
    export_script = f"""
import torch, numpy as np, json, os, sys
from pykeen.triples import TriplesFactory
from pykeen.models import RotatE

ckp_path = "{OUTPUT_DIR}/checkpoints/periodic.pt"
out_dir   = "{OUTPUT_DIR}/deploy"
os.makedirs(out_dir, exist_ok=True)

if not os.path.exists(ckp_path):
    print("[export] no checkpoint yet"); sys.exit(0)

try:
    ckp = torch.load(ckp_path, map_location="cpu", weights_only=False)
    # PyKEEN checkpoint stores model state under 'model_state_dict'
    state = ckp.get("model_state_dict") or ckp.get("state_dict")
    if state is None:
        print("[export] unexpected checkpoint format:", list(ckp.keys())); sys.exit(0)
    torch.save(state, os.path.join(out_dir, "model_state_dict.pt"))

    # Extract entity & relation embeddings directly from state dict
    # PyKEEN RotatE stores embeddings under entity_representations.0._embeddings.weight
    all_keys = list(state.keys())
    print(f"[export] state dict keys: {{all_keys[:10]}}")
    ent_key = [k for k in state if "entity" in k and "weight" in k]
    rel_key = [k for k in state if "relation" in k and "weight" in k]
    if ent_key:
        np.save(os.path.join(out_dir, "entity_embeddings.npy"), state[ent_key[0]].cpu().numpy())
        print(f"[export] entity embeddings from key: {{ent_key[0]}}")
    else:
        print(f"[export] WARNING: no entity embedding key found. All keys: {{all_keys}}")
    if rel_key:
        np.save(os.path.join(out_dir, "relation_embeddings.npy"), state[rel_key[0]].cpu().numpy())
        print(f"[export] relation embeddings from key: {{rel_key[0]}}")
    else:
        print(f"[export] WARNING: no relation embedding key found.")

    epoch = ckp.get("epoch", "?")
    print(f"[export] saved deploy snapshot at epoch {{epoch}} → {{out_dir}}")
except Exception as e:
    print(f"[export] warning: {{e}}")
"""
    export_script_path = f"{OUTPUT_DIR}/export_snapshot.py"
    with open(export_script_path, "w") as f:
        f.write(export_script)

    cmd = [
        sys.executable, script,
        "--data_dir",         DATA_DIR,
        "--output_dir",       OUTPUT_DIR,
        "--num_epochs",       str(num_epochs),
        "--embedding_dim",    str(embedding_dim),
        "--batch_size",       str(batch_size),
        "--eval_every",       str(eval_every),
        "--checkpoint_every", str(checkpoint_every),
        "--dominant_cap",     str(dominant_cap),
        "--oversample_cap",   str(oversample_cap),
        "--device",           "cuda",
    ]
    print("Launching:", " ".join(cmd))
    run_env = os.environ.copy()
    run_env["PYKEEN_HOME"] = f"{OUTPUT_DIR}/.pykeen"   # best-model → persistent volume

    # Use Popen so we can commit from the MAIN thread every 10 min.
    # Background threads cannot reliably call vol.commit() in Modal.
    proc = subprocess.Popen(cmd, env=run_env)
    last_commit = time.time()
    COMMIT_INTERVAL = 600  # every 10 minutes

    import signal

    def _do_commit(label: str):
        """Call vol.commit() with a 90-second timeout via SIGALRM."""
        def _alarm_handler(signum, frame):
            raise TimeoutError("vol.commit() timed out after 90s")
        signal.signal(signal.SIGALRM, _alarm_handler)
        signal.alarm(90)
        try:
            vol.commit()
            print(f"[volume] {label}", flush=True)
        finally:
            signal.alarm(0)  # always cancel alarm

    while proc.poll() is None:
        time.sleep(30)  # lightweight poll every 30 seconds
        if time.time() - last_commit >= COMMIT_INTERVAL:
            try:
                src = f"{OUTPUT_DIR}/metrics.csv"
                dst = f"{OUTPUT_DIR}/metrics_snapshot.csv"
                if os.path.exists(src):
                    shutil.copy2(src, dst)
                subprocess.run([sys.executable, export_script_path], capture_output=True)
                _do_commit("committed checkpoints to persistent storage")
            except TimeoutError as e:
                print(f"[volume] commit timed out (checkpoint write in progress), will retry next interval", flush=True)
            except Exception as e:
                print(f"[volume] commit warning: {e}", flush=True)
            finally:
                last_commit = time.time()  # always reset timer

    # Final flush after training process exits
    try:
        src = f"{OUTPUT_DIR}/metrics.csv"
        dst = f"{OUTPUT_DIR}/metrics_snapshot.csv"
        if os.path.exists(src):
            shutil.copy2(src, dst)
        subprocess.run([sys.executable, export_script_path], capture_output=True)
        _do_commit("final commit complete")
    except TimeoutError:
        print("[volume] final commit timed out — retrying once...", flush=True)
        try:
            time.sleep(15)
            _do_commit("final commit (retry) complete")
        except Exception as e:
            print(f"[volume] final commit retry failed: {e}", flush=True)
    except Exception as e:
        print(f"[volume] final commit warning: {e}", flush=True)
    print(f"\nTraining exited with code {proc.returncode}")


# ── Upload: push local files to the Modal volume ──────────────────────────────
@app.function(volumes={VOLUME_PATH: vol}, image=modal.Image.debian_slim())
def _upload_bytes(remote_path: str, data: bytes):
    """Write bytes to a path on the volume (called from local entrypoint)."""
    os.makedirs(os.path.dirname(remote_path), exist_ok=True)
    with open(remote_path, "wb") as f:
        f.write(data)
    vol.commit()
    print(f"  uploaded → {remote_path}  ({len(data)/1024/1024:.1f} MB)")


@app.local_entrypoint()
def upload():
    """
    Upload training script + KGE data + epoch-50 checkpoint to Modal volume.
    Run once before training, or whenever local files change.
    """
    base = Path(__file__).parent

    # 1. train_kge.py
    script_bytes = (base / "train_kge.py").read_bytes()
    _upload_bytes.remote(f"{VOLUME_PATH}/train_kge.py", script_bytes)

    # 2. KGE input files (entity2id, relation2id, train/valid/test .txt)
    kge_dir = base / "data" / "processed_hkg" / "kge_input"
    for fname in ["entity2id.txt", "relation2id.txt",
                  "train.txt", "valid.txt", "test.txt"]:
        fpath = kge_dir / fname
        if not fpath.exists():
            print(f"  WARNING: {fpath} not found — skipping")
            continue
        _upload_bytes.remote(f"{DATA_DIR}/{fname}", fpath.read_bytes())

    # 3. Checkpoint — only upload if NOT already on the volume (never overwrite)
    ckp = base / "checkpoints_backup" / "periodic.pt"
    if ckp.exists():
        import subprocess, sys
        remote_ckp = "kge_rotate/checkpoints/periodic.pt"
        r = subprocess.run([sys.executable, "-m", "modal", "volume", "put",
                            "dfinder-vol", str(ckp), remote_ckp],
                           capture_output=True)
        if r.returncode == 0:
            print("  checkpoint uploaded — PyKEEN will resume from saved epoch")
        else:
            # File already exists on volume — that's fine, keep the remote one
            print("  checkpoint already on volume — keeping remote version (will resume from there)")
    else:
        print("  No local periodic.pt — training starts/resumes from whatever is on the volume")

    print("\nUpload complete. Now run:  modal run modal_train.py")


# ── Pull: download latest checkpoints + metrics to local machine ──────────────
@app.function(volumes={VOLUME_PATH: vol}, image=modal.Image.debian_slim())
def _read_bytes(remote_path: str) -> bytes | None:
    if not os.path.exists(remote_path):
        return None
    with open(remote_path, "rb") as f:
        return f.read()


@app.local_entrypoint()
def pull():
    """Download latest metrics.csv and embeddings from Modal volume via CLI (fast)."""
    import subprocess, sys
    base       = Path(__file__).parent
    backup_dir = base / "checkpoints_backup"
    backup_dir.mkdir(exist_ok=True)

    files = [
        (f"kge_rotate/metrics_snapshot.csv",           backup_dir / "metrics_modal.csv"),
        (f"kge_rotate/deploy/model_state_dict.pt",     backup_dir / "deploy_model_state_dict.pt"),
        (f"kge_rotate/deploy/entity_embeddings.npy",   backup_dir / "deploy_entity_embeddings.npy"),
        (f"kge_rotate/deploy/relation_embeddings.npy", backup_dir / "deploy_relation_embeddings.npy"),
    ]

    for remote, local in files:
        local.unlink(missing_ok=True)  # force overwrite — modal volume get won't replace existing files
        r = subprocess.run(
            [sys.executable, "-m", "modal", "volume", "get",
             "dfinder-vol", remote, str(local)],
            capture_output=True, text=True
        )
        if local.exists() and local.stat().st_size > 0:
            kb = local.stat().st_size / 1024
            print(f"  ✓ {local.name}  ({kb:.1f} KB)")
        else:
            print(f"  - {local.name}: not available yet  [stderr: {r.stderr.strip()[:120]}]")

    # If .npy files missing but state dict is available, extract locally
    state_dict_path = backup_dir / "deploy_model_state_dict.pt"
    ent_npy = backup_dir / "deploy_entity_embeddings.npy"
    rel_npy = backup_dir / "deploy_relation_embeddings.npy"
    if state_dict_path.exists() and (not ent_npy.exists() or not rel_npy.exists()):
        try:
            import torch, numpy as np
            state = torch.load(str(state_dict_path), map_location="cpu", weights_only=False)
            all_keys = list(state.keys())
            ent_keys = [k for k in state if "entity" in k and "weight" in k]
            rel_keys = [k for k in state if "relation" in k and "weight" in k]
            if ent_keys:
                np.save(str(ent_npy), state[ent_keys[0]].numpy())
                print(f"  ✓ Extracted entity_embeddings.npy locally from key: {ent_keys[0]}")
            if rel_keys:
                np.save(str(rel_npy), state[rel_keys[0]].numpy())
                print(f"  ✓ Extracted relation_embeddings.npy locally from key: {rel_keys[0]}")
            if not ent_keys and not rel_keys:
                print(f"  ✗ No embedding keys found. State dict keys: {all_keys[:15]}")
        except Exception as e:
            print(f"  ✗ Local extraction failed: {e}")

    # Print MRR summary
    metrics_path = backup_dir / "metrics_modal.csv"
    if metrics_path.exists() and metrics_path.stat().st_size > 0:
        print("\n  Latest MRR values:")
        for line in metrics_path.read_text(encoding="utf-8").splitlines():
            if "both.realistic.inverse_harmonic_mean_rank" in line:
                parts = line.split(",")
                print(f"    epoch {parts[1].strip():>4}  MRR = {parts[3].strip()}")


# ── Fix checkpoint: compute correct checksum and inject it ───────────────────
@app.function(volumes={VOLUME_PATH: vol}, image=image, gpu="A100-80GB")
def fix_checkpoint():
    """
    Compute the correct PyKEEN checksum for the current training config,
    restore from pre-patch backup, inject the checksum, remove lr_scheduler
    state (which triggered the original mismatch), and save.
    """
    import torch, shutil, os, sys, json, hashlib
    import numpy as np

    os.environ["PYKEEN_HOME"] = f"{OUTPUT_DIR}/.pykeen"

    # ── load data (same as train_kge.py) ─────────────────────────────────────
    def load_id_map(path):
        m = {}
        with open(path) as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) == 2:
                    m[parts[0]] = int(parts[1])
        return m

    def load_triplets(path):
        trips = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) == 3:
                    trips.append([int(p) for p in parts])
        return np.array(trips, dtype=np.int64)

    from pykeen.triples import TriplesFactory
    from pykeen.training import SLCWATrainingLoop
    from pykeen.models import RotatE
    from pykeen.losses import NSSALoss
    from pykeen.sampling import BasicNegativeSampler
    import torch.optim as optim

    entity2id   = load_id_map(f"{DATA_DIR}/entity2id.txt")
    relation2id = load_id_map(f"{DATA_DIR}/relation2id.txt")
    id2relation = {v: k for k, v in relation2id.items()}

    train_np = load_triplets(f"{DATA_DIR}/train.txt")

    # oversample (same logic as train_kge.py)
    from collections import Counter
    rel_counts = Counter(train_np[:, 1].tolist())
    dominant = max(rel_counts.values())
    dom_rel  = max(rel_counts, key=rel_counts.get)
    parts = []
    for rel_id in sorted(rel_counts.keys()):
        cnt  = rel_counts[rel_id]
        mult = min(dominant // cnt, 50) if rel_id != dom_rel else 1
        mask = train_np[:, 1] == rel_id
        parts.append(np.tile(train_np[mask], (mult, 1)))
    balanced = np.concatenate(parts, axis=0)
    rng = np.random.default_rng(42)
    rng.shuffle(balanced)

    _common = dict(
        num_entities=len(entity2id),
        num_relations=len(relation2id),
        entity_to_id=entity2id,
        relation_to_id=relation2id,
    )
    train_tf = TriplesFactory(
        mapped_triples=torch.tensor(balanced, dtype=torch.long), **_common
    )

    # ── build model + training loop (mirrors pipeline internals) ─────────────
    device = torch.device("cuda")
    model = RotatE(triples_factory=train_tf, embedding_dim=512, random_seed=42).to(device)
    loss  = NSSALoss(margin=9.0, adversarial_temperature=1.0)
    model.loss = loss

    optimizer = optim.Adam(model.parameters(), lr=0.0001)

    neg_sampler = BasicNegativeSampler(
        mapped_triples=train_tf.mapped_triples,
        num_negs_per_pos=128,
        corruption_scheme=("head", "tail"),
    )

    training_loop = SLCWATrainingLoop(
        model=model,
        triples_factory=train_tf,
        optimizer=optimizer,
        negative_sampler=neg_sampler,
        automatic_memory_optimization=True,
    )

    # ── extract the checksum ─────────────────────────────────────────────────
    if hasattr(training_loop, "_checkpoint_hash"):
        checksum = training_loop._checkpoint_hash
    else:
        # Fallback: print all private attrs to diagnose
        attrs = [a for a in dir(training_loop) if "check" in a.lower() or "hash" in a.lower() or "sum" in a.lower()]
        print(f"No _checkpoint_hash found. Relevant attrs: {attrs}")
        # Try to compute it the same way PyKEEN does
        import hashlib, json
        # PyKEEN uses md5 of json-serialized config
        cfg = {}
        for attr in ["num_epochs", "batch_size"]:
            if hasattr(training_loop, attr):
                cfg[attr] = getattr(training_loop, attr)
        checksum = hashlib.md5(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
        print(f"Computed fallback checksum: {checksum}")
    print(f"Computed checksum: {checksum}")

    # ── restore from backup and patch ────────────────────────────────────────
    bak  = f"{OUTPUT_DIR}/checkpoints/periodic_pre_patch.pt"
    dest = f"{OUTPUT_DIR}/checkpoints/periodic.pt"

    if not os.path.exists(bak):
        print("No backup found! Using current periodic.pt"); bak = dest

    ckp = torch.load(bak, map_location="cpu", weights_only=False)
    print(f"Loaded backup checkpoint at epoch {ckp.get('epoch', '?')}")
    print(f"Old checksum: {ckp.get('checksum', 'MISSING')}")

    ckp.pop("lr_scheduler_state_dict", None)
    ckp["checksum"] = checksum
    ckp.pop("stopper_dict", None)        # let stopper restart cleanly

    torch.save(ckp, dest)
    vol.commit()
    print(f"Patched checkpoint saved. Epoch={ckp.get('epoch')}, checksum={checksum}")


# ── Default entrypoint: just run training ─────────────────────────────────────
@app.local_entrypoint()
def main():
    print("Starting DFinder KGE training on Modal A100-80GB...")
    print("Job runs fully detached — Ctrl+C will NOT stop it.")
    print("Pull checkpoints anytime with:")
    print("  modal run modal_train.py::pull\n")
    train.spawn()  # spawn = fire-and-forget, never killed by local interrupt
    print("Job submitted. Training is running on Modal servers.")
    print("Check progress: modal app list")
    print("Pull results:   modal run modal_train.py::pull")
