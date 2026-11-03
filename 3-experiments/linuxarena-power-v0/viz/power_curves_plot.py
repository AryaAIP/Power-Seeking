"""POWER_H against the budget H for the three states (before, after A, after B), from power_horizons.py's JSON, as a
static figure for the report. Each line is the midpoint of the lower and upper bounds between scored horizons, shaded
between them (no confidence interval). Run with matplotlib, e.g. in WSL:
  uv run --with matplotlib python viz/power_curves_plot.py findings/power-horizons-v4.json viz/nov3-power-curves-pair1.png "pair 1"
"""

import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

src, out, name = sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ""
r = json.load(open(src))
curves = r["power_curve"]
STATES = [("before", "initial environment state"), ("A", "after the control trajectory"), ("B", "after the power-seeking trajectory")]
COLOR = {"before": "#2a78d6", "A": "#eb6834", "B": "#1baf7a"}  # categorical slots 1-3, fixed order
SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#6b6b68", "#e6e5e1"

fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=200)
fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
for st, label in STATES:
    if st not in curves:
        continue
    lo, hi = curves[st]["low"], curves[st]["high"]
    mid = lo  # strict POWER_H (Arya, Nov 3): a test case counts at H only if seen passing at a scored step at or before H
    hs = list(range(len(mid)))
    ax.plot(hs, mid, color=COLOR[st], linewidth=2, label=label, solid_capstyle="round")
    pass  # lines only (Arya, Nov 3): no shaded range
ax.set_xlim(0, len(mid) - 1); ax.set_ylim(0, 1)
ax.set_xlabel("step budget H", fontsize=9, color=INK)
ax.set_ylabel("POWER_H (mean share of test cases passed by step H)", fontsize=9, color=INK)
ax.grid(axis="y", color=GRID, linewidth=0.8); ax.set_axisbelow(True)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color(GRID)
ax.tick_params(colors=MUTED, labelsize=8)
ax.legend(frameon=False, fontsize=8, loc="lower right", labelcolor=INK)
ax.set_title(f"POWER_H by step budget H (undiscounted), mean over {len(r['tasks'])} follow-up tasks", fontsize=11, color=INK, loc="left")
fig.text(0.01, 0.01, "A test case counts at step H if it passes at the last scored step at or before H; one that breaks stops counting."
         + (" One answer corrected (findings/score-corrections.json)." if r.get("score_corrections") else ""),
         fontsize=7, color=MUTED)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(out, facecolor=SURFACE)
print("wrote", out)
