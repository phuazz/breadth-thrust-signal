"""WS7 record charts. Reads reviews/2026-08-01_ws7_results.json and writes the
PNGs embedded in reviews/2026-08-01_ws7_norgate-history-extension.docx.
Committed so the record is reproducible. White theme, navy primary, per report
conventions."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
R = json.loads((ROOT / "reviews" / "2026-08-01_ws7_results.json").read_text(encoding="utf-8"))
OUT = ROOT / "reviews" / "charts"
OUT.mkdir(exist_ok=True)

NAVY, RED, TEAL, BAND, GREY = "#1e3a8a", "#dc2626", "#0891b2", "#dcfce7", "#9ca3af"
plt.rcParams.update({"font.family": "sans-serif", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})


def rows(block):
    return {(r["threshold"], r["horizon"]): r for r in R[block]["lift"]}


ho, pooled = rows("h1_held_out"), rows("h2_pooled")

# ── Chart 1: the pre-registered decision. Both legs at >=3, 6m, against the
#    bootstrap band. The win leg fails; the median leg passes.
fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.6, 3.6))
labels = ["Held-out\n1990–2017", "Pooled\n1990–2026"]
src = [ho[(3, "6m")], pooled[(3, "6m")]]

# Dots-and-bands, not bars: the action sits in a narrow range (74–78% on the
# win leg) and a bar chart would have to be truncated to show it, which
# misrepresents magnitudes. A dot against its own band reads honestly at any
# zoom.
for ax, key, hi_key, base_key, ylab, title, lo, hi in (
    (a1, "win_rate", "base_win_hi", "base_win_rate",
     "Share of positive 6m returns (%)", "Win-rate leg: FAILS", 70, 82),
    (a2, "median_ret", "base_ret_hi", "base_median_ret",
     "Median 6m return (%)", "Median leg: passes", 4, 9),
):
    for i, r in enumerate(src):
        base, band_hi = r[base_key] * 100, r[hi_key] * 100
        ax.fill_between([i - 0.30, i + 0.30], base, band_hi, color=BAND,
                        alpha=0.95, zorder=0)
        ax.plot([i - 0.30, i + 0.30], [band_hi] * 2, color="#374151", lw=1.3,
                ls="--", zorder=1)
        ax.plot([i - 0.30, i + 0.30], [base] * 2, color=GREY, lw=1.0, zorder=1)
        v = r[key] * 100
        clears = v > band_hi
        ax.plot([i], [v], "o", ms=11, color=NAVY if clears else RED, zorder=3)
        ax.annotate(f"{v:.1f}", (i, v), textcoords="offset points",
                    xytext=(16, -3), fontsize=9.5,
                    color=NAVY if clears else RED, fontweight="bold")
    ax.set_xticks(range(len(labels)), labels, fontsize=9)
    ax.set_xlim(-0.6, len(labels) - 0.4)
    ax.set_ylim(lo, hi)
    ax.set_ylabel(ylab)
    ax.set_title(title, fontsize=10)

fig.suptitle("Score >= 3, six-month horizon. Dashed line is the 95th percentile of the bootstrap "
             "baseline;\ngreen band spans baseline to that line. A dot must sit ABOVE the dashed "
             "line to clear.", fontsize=8.8)
fig.tight_layout(rect=(0, 0, 1, 0.86))
fig.savefig(OUT / "ws7_decision.png", dpi=160)
plt.close(fig)

# ── Chart 2: conviction monotonicity. Phase 0's backwards ordering against the
#    held-out and pooled windows.
FILED = {1: 0.885, 2: 0.864, 3: 0.786, 4: 0.500}
FILED_BASE = 0.748
thr = [1, 2, 3, 4]
fig, ax = plt.subplots(figsize=(8.6, 3.5))
ax.axhline(0, color="#374151", lw=0.8)
ax.plot(thr, [(FILED[t] - FILED_BASE) * 100 for t in thr], "o--", color=RED,
        label="Filed Phase 0, 2018–2026 (the inversion)")
ax.plot(thr, [ho[(t, "6m")]["win_lift"] * 100 for t in thr], "o-", color=NAVY,
        label="Held-out 1990–2017 (rho +0.40)")
ax.plot(thr, [pooled[(t, "6m")]["win_lift"] * 100 for t in thr], "o-", color=TEAL,
        label="Pooled 1990–2026 (rho +0.20)")
for t in thr:
    ax.annotate(f"n={ho[(t,'6m')]['n']}", (t, ho[(t, "6m")]["win_lift"] * 100),
                textcoords="offset points", xytext=(0, -14), ha="center",
                fontsize=8, color="#6b7280")
ax.set_xticks(thr, [f">= {t}" for t in thr])
ax.set_xlabel("Conviction threshold (dimensions on)")
ax.set_ylabel("6m win-rate lift over baseline (pp)")
ax.set_ylim(-30, 22)
ax.set_title("The conviction inversion does not reproduce out of sample", fontsize=10)
# Below the axis, not over the red line it would otherwise be struck through by.
ax.legend(frameon=False, fontsize=8.5, ncol=3, loc="upper center",
          bbox_to_anchor=(0.5, -0.20))
fig.tight_layout(rect=(0, 0.06, 1, 1))
fig.savefig(OUT / "ws7_monotonicity.png", dpi=160)
plt.close(fig)

# ── Chart 3: H4. How much of the filed event set survives the layer change.
h4 = R["h4_reconciliation"]
fig, ax = plt.subplots(figsize=(8.6, 2.4))
shared, filed_only, norg_only = 16, 10, 12
# Labels sit inside the segments; a legend below the axis collided with the
# x-label and made the exhibit unreadable at A4 width.
for left, width, colour, label in (
    (0, shared, NAVY, f"Shared\n{shared}"),
    (shared, filed_only, RED, f"Filed only\n{filed_only}"),
    (shared + filed_only, norg_only, GREY, f"Norgate only\n{norg_only}"),
):
    ax.barh([0], [width], left=[left], color=colour, height=0.55)
    ax.text(left + width / 2, 0, label, ha="center", va="center",
            fontsize=9.5, color="white", fontweight="bold")
ax.set_yticks([])
ax.set_ylim(-0.5, 0.5)
ax.set_xlim(0, shared + filed_only + norg_only)
ax.set_xlabel("Thrust events in the filed window, 2018-01-08 to 2026-05-29")
ax.set_title("Only 16 of 26 filed events survive daily point-in-time membership "
             "with delisted names restored", fontsize=10)
fig.tight_layout()
fig.savefig(OUT / "ws7_h4_overlap.png", dpi=160)
plt.close(fig)

# ── Chart 4: scope graphic — rigour plus restraint.
fig, ax = plt.subplots(figsize=(8.6, 2.8))
cats = ["H1 held-out grid", "H2 pooled grid", "H4 reconciliation",
        "H3 anchors", "H1b / H3b"]
counts = [20, 20, 24, 8, 2]
ax.barh(range(len(cats))[::-1], counts, color=NAVY, alpha=0.9)
for i, c in enumerate(counts):
    ax.text(c + 0.4, len(cats) - 1 - i, str(c), va="center", fontsize=9)
ax.set_yticks(range(len(cats))[::-1], cats, fontsize=9)
ax.set_xlabel("Configurations evaluated")
ax.set_xlim(0, 28)
ax.set_title("74 configurations evaluated  →  0 parameters tuned  →  1 component rejected, "
             "1 flagged", fontsize=10)
fig.tight_layout()
fig.savefig(OUT / "ws7_scope.png", dpi=160)
plt.close(fig)

for f in ("ws7_decision", "ws7_monotonicity", "ws7_h4_overlap", "ws7_scope"):
    print("wrote", OUT / f"{f}.png")
