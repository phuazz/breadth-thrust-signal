"""WS8 record charts. Reads the two WS8 results JSONs and writes the PNGs
embedded in reviews/2026-08-01_ws8_thrust-tilt-deployability.docx. Committed so
the record is reproducible. White theme, navy primary, per report conventions."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
R = json.loads((ROOT / "reviews" / "2026-08-01_ws8_results.json").read_text(encoding="utf-8"))["sp500"]
REP = json.loads((ROOT / "reviews" / "2026-08-01_ws8_replication.json").read_text(encoding="utf-8"))
OUT = ROOT / "reviews" / "charts"
OUT.mkdir(exist_ok=True)

NAVY, RED, TEAL, BAND, GREY = "#1e3a8a", "#dc2626", "#0891b2", "#dcfce7", "#9ca3af"
plt.rcParams.update({"font.family": "sans-serif", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})

# ── Chart 1: the decision. Signal against its own null, and against the base.
h = R["variants"]["V1_d20_h21"]
n = h["null"]
fig, ax = plt.subplots(figsize=(8.6, 3.0))
ax.fill_betweenx([-0.4, 0.4], n["sharpe_p05"], n["sharpe_p95"], color=BAND,
                 alpha=0.95, zorder=0, label="Random-entry null, 5th–95th percentile")
ax.plot([n["sharpe_p95"]] * 2, [-0.4, 0.4], color="#374151", lw=1.4, ls="--", zorder=1)
ax.plot([n["sharpe_p50"]] * 2, [-0.4, 0.4], color=GREY, lw=1.2, zorder=1)
ax.plot([R["base_60_40"]["sharpe"]] * 2, [-0.4, 0.4], color=TEAL, lw=1.6, zorder=2)
ax.plot([h["sharpe"]], [0], "o", ms=14, color=RED, zorder=3)
ax.annotate(f"signal {h['sharpe']:.3f}", (h["sharpe"], 0), textcoords="offset points",
            xytext=(0, -30), ha="center", fontsize=10, color=RED, fontweight="bold")
# base (0.743) and the null 95th (0.751) sit 0.008 apart, so their labels are
# staggered vertically and pushed to opposite sides or they overprint.
for x, lab, col, dy, ha in (
    (n["sharpe_p50"], f"null median {n['sharpe_p50']:.3f}", GREY, 20, "center"),
    (n["sharpe_p95"], f"null 95th {n['sharpe_p95']:.3f} — the bar", "#374151", 52, "right"),
    (R["base_60_40"]["sharpe"], f"untilted base {R['base_60_40']['sharpe']:.3f}", TEAL, -42, "right"),
):
    ax.annotate(lab, (x, 0), textcoords="offset points", xytext=(6 if ha == "right" else 0, dy),
                ha=ha, fontsize=8.5, color=col)
ax.set_ylim(-0.75, 0.95); ax.set_yticks([])
ax.set_xlim(0.655, 0.775)
ax.set_xlabel("Net Sharpe, 1990–2026")
ax.set_title("The pre-registered decision: the signal must clear the dashed line. It does not —\n"
             "and it sits below the null median, so the timing loses to randomly-placed tilts.",
             fontsize=9.5)
fig.tight_layout()
fig.savefig(OUT / "ws8_decision.png", dpi=160)
plt.close(fig)

# ── Chart 2: every variant, against the untilted base.
base = R["base_60_40"]["sharpe"]
keys = sorted(R["variants"], key=lambda k: -R["variants"][k]["sharpe"])
vals = [R["variants"][k]["sharpe"] - base for k in keys]
fig, ax = plt.subplots(figsize=(8.6, 4.0))
ax.barh(range(len(keys))[::-1], vals, color=[RED] * len(keys), alpha=0.9)
ax.axvline(0, color="#374151", lw=1.2)
ax.set_yticks(range(len(keys))[::-1],
              [k.replace("_", "  ").replace("d", "Δ").replace("h", "hold ") for k in keys],
              fontsize=8)
ax.set_xlabel("Net Sharpe minus untilted 60/40 base")
ax.set_title("All 18 variants underperform the untilted base — monotonically worse with\n"
             "larger tilts and longer holds. There is no corner of the grid that works.",
             fontsize=9.5)
fig.tight_layout()
fig.savefig(OUT / "ws8_variants.png", dpi=160)
plt.close(fig)

# ── Chart 3: mechanism replicates, strategy does not. Two panels.
unis = [("sp500", "S&P 500\n(WS7 cell)"), ("sp600", "S&P SmallCap 600"), ("r2000", "Russell 2000")]
lifts = [0.716, REP["sp600"]["cell"]["median_lift_pp"], REP["r2000"]["cell"]["median_lift_pp"]]
beyond = [True, REP["sp600"]["cell"]["ret_beyond_noise"], REP["r2000"]["cell"]["ret_beyond_noise"]]
sharpe_d = [h["sharpe"] - base,
            REP["sp600"]["tilt_backtest"]["sharpe_delta"],
            REP["r2000"]["tilt_backtest"]["sharpe_delta"]]

fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.6, 3.4))
a1.bar(range(3), lifts, 0.55, color=[NAVY if b else GREY for b in beyond])
a1.axhline(0, color="#374151", lw=1.0)
for i, (v, b) in enumerate(zip(lifts, beyond)):
    a1.text(i, v, f" {v:+.2f}" + ("\nbeyond noise" if b else "\nwithin noise"),
            ha="center", va="bottom", fontsize=8)
a1.set_xticks(range(3), [u[1] for u in unis], fontsize=8.5)
a1.set_ylim(0, 1.5)
a1.set_ylabel("1-month median lift (pp)")
a1.set_title("Mechanism: REPLICATES", fontsize=10, color=NAVY)

a2.bar(range(3), sharpe_d, 0.55, color=RED)
a2.axhline(0, color="#374151", lw=1.0)
for i, v in enumerate(sharpe_d):
    a2.text(i, v, f"{v:+.3f}", ha="center", va="top", fontsize=8.5)
a2.set_xticks(range(3), [u[1] for u in unis], fontsize=8.5)
a2.set_ylim(-0.06, 0.012)
a2.set_ylabel("Tilt net Sharpe minus base")
a2.set_title("Strategy: FAILS everywhere", fontsize=10, color=RED)
fig.suptitle("The breadth thrust is real and generalises across three independent cross-sections.\n"
             "It is still not convertible into portfolio value.", fontsize=9.5)
fig.tight_layout(rect=(0, 0, 1, 0.86))
fig.savefig(OUT / "ws8_replication.png", dpi=160)
plt.close(fig)

# ── Chart 4: what you actually buy — return up, risk up more.
labels = ["S&P 500", "S&P SmallCap 600", "Russell 2000"]
cagr_d = [(h["cagr"] - R["base_60_40"]["cagr"]) * 100,
          (REP["sp600"]["tilt_backtest"]["signal"]["cagr"] - REP["sp600"]["tilt_backtest"]["base"]["cagr"]) * 100,
          (REP["r2000"]["tilt_backtest"]["signal"]["cagr"] - REP["r2000"]["tilt_backtest"]["base"]["cagr"]) * 100]
dd_d = [(h["max_dd"] - R["base_60_40"]["max_dd"]) * 100,
        (REP["sp600"]["tilt_backtest"]["signal"]["max_dd"] - REP["sp600"]["tilt_backtest"]["base"]["max_dd"]) * 100,
        (REP["r2000"]["tilt_backtest"]["signal"]["max_dd"] - REP["r2000"]["tilt_backtest"]["base"]["max_dd"]) * 100]
x = np.arange(3); w = 0.36
fig, ax = plt.subplots(figsize=(8.6, 3.2))
ax.bar(x - w / 2, cagr_d, w, color=TEAL, label="Return added (CAGR, pp)")
ax.bar(x + w / 2, dd_d, w, color=RED, label="Drawdown added (MaxDD, pp)")
ax.axhline(0, color="#374151", lw=1.0)
for i, (c, d) in enumerate(zip(cagr_d, dd_d)):
    ax.text(i - w / 2, c, f"{c:+.2f}", ha="center", va="bottom", fontsize=8.5)
    ax.text(i + w / 2, d, f"{d:+.1f}", ha="center", va="top", fontsize=8.5)
ax.set_xticks(x, labels, fontsize=9)
ax.set_ylim(min(dd_d) * 1.35, max(cagr_d) * 2.6)
ax.set_ylabel("Change versus untilted base (pp)")
# Russell 2000 loses return outright, so "buys a little return" would be wrong
# for one of the three panels — the honest claim is the drawdown, which is
# consistent across all of them.
ax.set_title("What the tilt actually buys: at best a little return, and in the Russell none at all —\n"
             "paid for with 3 to 4 points of extra drawdown every time. Hence the Sharpe fall.",
             fontsize=9.5)
ax.legend(frameon=False, fontsize=8.5, loc="lower right", ncol=2)
fig.tight_layout()
fig.savefig(OUT / "ws8_tradeoff.png", dpi=160)
plt.close(fig)

for f in ("ws8_decision", "ws8_variants", "ws8_replication", "ws8_tradeoff"):
    print("wrote", OUT / f"{f}.png")
