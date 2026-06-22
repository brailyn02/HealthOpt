import torch, numpy as np, json, os, sys
from pykeen.triples import TriplesFactory
from pykeen.models import RotatE

ckp_path = "/data/kge_rotate/checkpoints/periodic.pt"
out_dir   = "/data/kge_rotate/deploy"
os.makedirs(out_dir, exist_ok=True)

if not os.path.exists(ckp_path):
    print("[export] no checkpoint yet"); sys.exit(0)

try:
    ckp = torch.load(ckp_path, map_location="cpu", weights_only=False)
    state = ckp.get("model_state_dict") or ckp.get("state_dict")
    if state is None:
        print("[export] unexpected checkpoint format:", list(ckp.keys())); sys.exit(0)
    torch.save(state, os.path.join(out_dir, "model_state_dict.pt"))

    all_keys = list(state.keys())
    print(f"[export] state dict keys ({len(all_keys)} total): {all_keys[:10]}")

    # PyKEEN RotatE stores as entity_representations.0._embeddings.weight
    ent_key = [k for k in state if "entity" in k and "weight" in k]
    rel_key = [k for k in state if "relation" in k and "weight" in k]

    if ent_key:
        np.save(os.path.join(out_dir, "entity_embeddings.npy"), state[ent_key[0]].cpu().numpy())
        print(f"[export] entity embeddings saved from key: {ent_key[0]}")
    else:
        print(f"[export] WARNING: no entity key found. All keys: {all_keys}")

    if rel_key:
        np.save(os.path.join(out_dir, "relation_embeddings.npy"), state[rel_key[0]].cpu().numpy())
        print(f"[export] relation embeddings saved from key: {rel_key[0]}")
    else:
        print(f"[export] WARNING: no relation key found.")

    epoch = ckp.get("epoch", "?")
    print(f"[export] saved deploy snapshot at epoch {epoch} → {out_dir}")
except Exception as e:
    print(f"[export] warning: {e}")
