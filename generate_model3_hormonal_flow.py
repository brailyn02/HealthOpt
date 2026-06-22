from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


OUT_DIR = Path(__file__).resolve().parent / "thesis_figures"
OUT_DIR.mkdir(exist_ok=True)


def add_box(ax, xy, w, h, text, fc, ec="#2c3e50", text_color="#111111", fontsize=11):
    x, y = xy
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.04",
        linewidth=1.6,
        edgecolor=ec,
        facecolor=fc,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        color=text_color,
        fontweight="semibold",
        wrap=True,
    )
    return patch


def arrow(ax, start, end, color="#34495e", text=None, text_offset=(0, 0.03)):
    arr = FancyArrowPatch(
        start,
        end,
        arrowstyle="->",
        mutation_scale=16,
        linewidth=1.8,
        color=color,
    )
    ax.add_patch(arr)
    if text:
        ax.text(
            (start[0] + end[0]) / 2 + text_offset[0],
            (start[1] + end[1]) / 2 + text_offset[1],
            text,
            ha="center",
            va="center",
            fontsize=9,
            color=color,
            bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="none", alpha=0.92),
        )


plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
})

fig, ax = plt.subplots(figsize=(13, 6.5), dpi=220)
fig.patch.set_facecolor("white")
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")

# Title
ax.text(
    0.5,
    0.96,
    "Figure 3.1 - Model 3 Hormonal Pharmacokinetic Adjustment Flow",
    ha="center",
    va="top",
    fontsize=16,
    fontweight="bold",
    color="#1f2d3d",
)

# Main flow boxes
add_box(
    ax,
    (0.05, 0.62),
    0.17,
    0.16,
    "Input\nCycle start date\n+ cycle length",
    fc="#d6eaf8",
    ec="#1f77b4",
)
add_box(
    ax,
    (0.27, 0.62),
    0.19,
    0.16,
    "Cycle phase detection\nMenstruation\nFollicular\nOvulation\nLuteal",
    fc="#e8f6f3",
    ec="#2ecc71",
)
add_box(
    ax,
    (0.51, 0.62),
    0.18,
    0.16,
    "CYP450 enzyme\nmodifier lookup\n(CYP3A4, CYP2D6,\nCYP2C9, CYP1A2, ABCB1)",
    fc="#f4ecf7",
    ec="#8e44ad",
)
add_box(
    ax,
    (0.74, 0.62),
    0.18,
    0.16,
    "Weighted cycle score\n$M_{cycle}$\ncombined modifier",
    fc="#fef5e7",
    ec="#f39c12",
)

arrow(ax, (0.22, 0.70), (0.27, 0.70))
arrow(ax, (0.46, 0.70), (0.51, 0.70))
arrow(ax, (0.69, 0.70), (0.74, 0.70))

# Lower policy / explanation branch
add_box(
    ax,
    (0.26, 0.25),
    0.22,
    0.15,
    "Tier adjustment policy\nOriginal tier -> adjusted tier\n(keep, raise, or confirm)",
    fc="#fdebd0",
    ec="#d35400",
)
add_box(
    ax,
    (0.57, 0.25),
    0.24,
    0.15,
    "Explanation generation\nUser note + technical note\nphase-aware wording policy",
    fc="#eaf2f8",
    ec="#2471a3",
)

arrow(ax, (0.83, 0.62), (0.83, 0.40), color="#7f8c8d")
arrow(ax, (0.48, 0.32), (0.57, 0.32), color="#7f8c8d", text="output")

# Side annotation: enzymes and phase modifiers
note = (
    "Phase-specific modifiers are applied to the detected enzyme set.\n"
    "Example policy: CYP3A4 is up-weighted most strongly during ovulation,\n"
    "then aggregated into a combined modifier used for the final tier decision."
)
ax.text(
    0.05,
    0.15,
    note,
    ha="left",
    va="top",
    fontsize=9.5,
    color="#3b3b3b",
    bbox=dict(boxstyle="round,pad=0.35", fc="#f8f9f9", ec="#d0d3d4"),
)

# Legend
legend_text = (
    "Legend: blue = input stage | green = phase detection | purple = enzyme modifiers | orange = scoring/policy | "
    "gray arrow = downstream adjustment"
)
ax.text(0.98, 0.06, legend_text, ha="right", va="bottom", fontsize=8.5, color="#5f6d7a")

fig.tight_layout(rect=[0, 0.03, 1, 0.95])

png_path = OUT_DIR / "fig9_model3_hormonal_flow.png"
svg_path = OUT_DIR / "fig9_model3_hormonal_flow.svg"
fig.savefig(png_path, bbox_inches="tight")
fig.savefig(svg_path, bbox_inches="tight")

print(png_path)
print(svg_path)