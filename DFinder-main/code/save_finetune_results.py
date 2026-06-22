"""Evaluate the fine-tuned checkpoint and save results to finetune_results.txt."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import world
import utils
import dataloader
import model
import Procedure
import torch

world.tensorboard = False
world.config['test_u_batch_size'] = 332

dataset = dataloader.Loader(path=f"../data/{world.dataset}")

Recmodel = model.LightGCN(world.config, dataset)
Recmodel = Recmodel.to(world.device)

weight_file = utils.getFileName()
print(f"Loading: {weight_file}")
Recmodel.load_state_dict(torch.load(weight_file, map_location=world.device))
Recmodel.eval()

results = Procedure.Test(dataset, Recmodel, epoch=200, w=None, multicore=world.config['multicore'])

OUT = r"D:\23AIBox-DFinder\finetune_results.txt"
with open(OUT, "w", encoding="utf-8") as f:
    f.write("=" * 60 + "\n")
    f.write("  DFinder (LightGCN + DNN) — unified-DFI Dataset\n")
    f.write("  Fine-Tune Results — 200 Epochs (North African Food-Drug Pairs)\n")
    f.write("=" * 60 + "\n\n")

    f.write("Dataset\n")
    f.write("-------\n")
    f.write(f"  Training pairs  : {dataset.traindataSize:,}\n")
    f.write(f"  Test pairs      : {dataset.testDataSize:,}\n")
    f.write(f"  Total pairs     : {dataset.traindataSize + dataset.testDataSize:,}\n")
    f.write(f"  Drugs           : {dataset.m_items:,}\n")
    f.write(f"  Foods           : {dataset.n_user:,}\n")
    f.write(f"  New NA edges    : 1,183\n\n")

    f.write("Fine-Tune Config\n")
    f.write("----------------\n")
    f.write(f"  Architecture    : LightGCN (3 layers) + DNN (2048→1024→512→256→64)\n")
    f.write(f"  Embedding dim   : 64\n")
    f.write(f"  LR              : 0.0001  (pretrain LR was 0.001)\n")
    f.write(f"  Decay           : 1e-4\n")
    f.write(f"  BPR batch size  : 512\n")
    f.write(f"  Epochs          : 200\n\n")

    f.write("Evaluation Metrics (Test Set @ Epoch 200)\n")
    f.write("------------------------------------------\n")
    f.write(f"  AUC  (group-weighted)   : {results['auc']:.4f}\n")
    f.write(f"  AUPR (group-weighted)   : {results['aupr']:.4f}\n")
    f.write(f"  Recall@20               : {results['recall'][0]:.4f}\n")
    f.write(f"  NDCG@20                 : {results['ndcg'][0]:.4f}\n")
    f.write(f"  Precision@20            : {results['precision'][0]:.4f}\n\n")

    f.write("Baseline (pre-fine-tune @ Epoch 0)\n")
    f.write("-----------------------------------\n")
    f.write(f"  AUC  (group-weighted)   : 0.8972\n")
    f.write(f"  AUPR (group-weighted)   : 0.2205\n")
    f.write(f"  Recall@20               : 0.3892\n")
    f.write(f"  NDCG@20                 : 0.2860\n")
    f.write(f"  Precision@20            : 0.0734\n\n")

    f.write("Checkpoint\n")
    f.write("----------\n")
    f.write(f"  File : DFinder-main/code/checkpoints/lgn-unified-DFI-3-64.pth.tar\n")
    f.write(f"  Pre-train backup : lgn-unified-DFI-3-64.pretrain.pth.tar\n")
    f.write("=" * 60 + "\n")

print(f"\nResults saved to {OUT}")
