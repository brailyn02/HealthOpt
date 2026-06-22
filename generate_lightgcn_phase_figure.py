from pathlib import Path

import matplotlib.pyplot as plt


OUT_DIR = Path(__file__).resolve().parent / "thesis_figures"
OUT_DIR.mkdir(exist_ok=True)


phase8 = {
    "AUC": 0.9035,
    "AUPR": 0.2418,
    "Recall@20": 0.4052,
    "NDCG@20": 0.3060,
    "Precision@20": 0.0757,
}

phase9_start = {
    "AUC": 0.8972,
    "AUPR": 0.2205,
    "Recall@20": 0.3892,
    "NDCG@20": 0.2860,
    "Precision@20": 0.0734,
}

phase9_end = {
    "AUC": 0.9012,
    "AUPR": 0.2338,
    "Recall@20": 0.4005,
    "NDCG@20": 0.2996,
    "Precision@20": 0.0757,
}


plt.style.use("seaborn-v0_8-whitegrid")
fig, axes = plt.subplots(1, 2, figsize=(15, 6), dpi=220)
fig.patch.set_facecolor("white")

phase_labels = ["Phase 8\nPre-training", "Phase 9\nStart", "Phase 9\nEnd"]
x = range(len(phase_labels))

# Left panel: core ranking metrics progression.
ax = axes[0]
auc_values = [phase8["AUC"], phase9_start["AUC"], phase9_end["AUC"]]
aupr_values = [phase8["AUPR"], phase9_start["AUPR"], phase9_end["AUPR"]]

ax.plot(x, auc_values, marker="o", linewidth=2.5, color="#1f77b4", label="AUC")
ax.plot(x, aupr_values, marker="o", linewidth=2.5, color="#ff7f0e", label="AUPR")
ax.scatter([1], [phase9_start["AUC"]], color="#1f77b4", s=60, facecolors="white", zorder=4)
ax.scatter([1], [phase9_start["AUPR"]], color="#ff7f0e", s=60, facecolors="white", zorder=4)
ax.set_xticks(list(x), phase_labels)
ax.set_ylabel("Score")
ax.set_title("Phase-Level Performance Trend")
ax.set_ylim(0.20, 0.93)
ax.legend(frameon=True, loc="lower right")
ax.annotate(
    "Phase 9 starts from the pretrained checkpoint\nand improves after North African fine-tuning.",
    xy=(1, phase9_start["AUC"]),
    xytext=(0.20, 0.86),
    textcoords="axes fraction",
    fontsize=9,
    bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#cccccc"),
)

# Right panel: retrieval metrics progression.
ax = axes[1]
categories = ["Recall@20", "NDCG@20", "Precision@20"]
phase8_vals = [phase8[c] for c in categories]
phase9_start_vals = [phase9_start[c] for c in categories]
phase9_end_vals = [phase9_end[c] for c in categories]

offsets = [0, 1, 2]
ax.plot(offsets, phase8_vals, marker="o", linewidth=2.5, color="#2ca02c", label="Phase 8 final")
ax.plot(offsets, phase9_start_vals, marker="o", linewidth=2.5, linestyle="--", color="#7f7f7f", label="Phase 9 start")
ax.plot(offsets, phase9_end_vals, marker="o", linewidth=2.5, color="#d62728", label="Phase 9 end")
ax.set_xticks(offsets, categories)
ax.set_ylabel("Score")
ax.set_title("Retrieval Metrics Across Training Stages")
ax.set_ylim(0.05, 0.46)
ax.legend(frameon=True, loc="lower right")

for axis, values in zip(axes, [auc_values, phase8_vals]):
    for idx, value in enumerate(values):
        axis.annotate(f"{value:.4f}", (idx, value), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8)

fig.suptitle(
    "LightGCN Training Performance: Phase 8 Pre-training and Phase 9 North African Fine-tuning",
    fontsize=15,
    fontweight="bold",
    y=0.98,
)
fig.text(
    0.5,
    0.01,
    "Note: the workspace stores final checkpoint metrics and fine-tuning baseline/final summaries, not a full epoch-by-epoch log.\nThis figure therefore presents a thesis-ready phase progression plot based on recorded benchmark values.",
    ha="center",
    va="bottom",
    fontsize=9,
    color="#555555",
)

fig.tight_layout(rect=[0, 0.06, 1, 0.94])

png_path = OUT_DIR / "figure_3_1_lightgcn_phase_training.png"
svg_path = OUT_DIR / "figure_3_1_lightgcn_phase_training.svg"
fig.savefig(png_path, bbox_inches="tight")
fig.savefig(svg_path, bbox_inches="tight")

print(png_path)
print(svg_path)