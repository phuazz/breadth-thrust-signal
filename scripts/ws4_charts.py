"""WS4 record charts. Reads the two WS4 results JSONs and writes the PNGs
embedded in reviews/2026-07-03_ws4_breadth-stresstest.docx. Committed so the
record is reproducible. White theme, navy primary, per report conventions."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
RESULTS = json.loads((ROOT / "reviews" / "2026-07-03_ws4_results.json").read_text(encoding="utf-8"))
EDD = json.loads(Path("C:/dev/equity-defense-dashboard/reviews/2026-07-03_ws4_attribution.json").read_text(encoding="utf-8"))
OUT = ROOT / "reviews" / "charts"
OUT.mkdir(exist_ok=True)

NAVY, RED, TEAL, BAND = "#1e3a8a", "#dc2626", "#0891b2", "#dcfce7"
plt.rcParams.update({"font.family": "sans-serif", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})

# ── Chart 1: H2 win rates by horizon — washout vs strength vs thrust,
#    against the unconditional bootstrap band.
horizons = ["1m", "3m", "6m", "12m"]
lev = {(r["condition"], r["horizon"]): r for r in RESULTS["h2_level_quartile_contrast"]["level_conditional"]}
thr = {r["horizon"]: r for r in RESULTS["h2_level_quartile_contrast"]["thrust_study_reused"]["conditional"]
       if r["threshold"] == 2}
base = {r["horizon"]: r for r in RESULTS["h2_level_quartile_contrast"]["thrust_study_reused"]["baseline"]}

fig, ax = plt.subplots(figsize=(8.6, 3.6))
x = range(len(horizons))
w = 0.25
for j, (label, getter, colour) in enumerate([
        ("Washout entry (level < Q1)", lambda h: lev[("washout_entry", h)]["win_rate"], NAVY),
        ("Strength entry (level > Q3)", lambda h: lev[("strength_entry", h)]["win_rate"], TEAL),
        ("Thrust event (score >= 2, Phase 0)", lambda h: thr[h]["win_rate"], RED)]):
    ax.bar([i + (j - 1) * w for i in x], [getter(h) for h in horizons], w,
           label=label, color=colour, alpha=0.9)
for i, h in enumerate(horizons):
    b = base[h]
    ax.plot([i - 0.42, i + 0.42], [b["base_win_rate"]] * 2, color="#374151", lw=1.4)
    ax.fill_between([i - 0.42, i + 0.42], b["base_win_lo"], b["base_win_hi"],
                    color=BAND, alpha=0.9, zorder=0)
ax.set_xticks(list(x), horizons)
ax.set_ylim(0.4, 1.0)
ax.set_ylabel("Share of positive forward returns")
ax.set_title("Conditional win rates vs the unconditional bootstrap band (2018–2026)")
ax.legend(loc="lower right", frameon=False, fontsize=8.5)
fig.tight_layout()
fig.savefig(OUT / "ws4_h2_winrates.png", dpi=160)
plt.close(fig)

# ── Chart 2: H4 leave-one-out — Sharpe and MaxDD per variant (full window, IEF).
v = EDD["variants"]["full"]["ief"]
names = ["full", "minus_blowup", "minus_vix", "minus_ma200", "minus_mom12", "minus_sma10m"]
labels = ["Full composite", "minus Blowup", "minus VIX term", "minus 200d MA",
          "minus 12m momentum", "minus 10m SMA"]
sharpes = [v[n]["sharpe"] for n in names]
maxdds = [v[n]["maxdd"] * 100 for n in names]
colours = [NAVY] + [("#9ca3af" if abs(v[n]["sharpe"] - v["full"]["sharpe"]) <= 0.05 else RED)
                    for n in names[1:]]

fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.6, 3.4))
a1.barh(range(len(names))[::-1], sharpes, color=colours)
a1.set_yticks(range(len(names))[::-1], labels, fontsize=9)
a1.set_xlabel("Sharpe (net, 1998–2026)")
a1.set_xlim(0.6, 0.9)
a1.axvline(v["full"]["sharpe"], color="#374151", lw=0.8, ls="--")
a2.barh(range(len(names))[::-1], maxdds, color=colours)
a2.set_yticks(range(len(names))[::-1], ["" for _ in names])
a2.set_xlabel("Maximum drawdown (%)")
a2.set_xlim(-45, 0)
a2.axvline(v["full"]["maxdd"] * 100, color="#374151", lw=0.8, ls="--")
fig.suptitle("Removing one sub-signal from the defence composite: grey = within pre-registered noise bands, red = materially worse", fontsize=9.5)
fig.tight_layout(rect=(0, 0, 1, 0.93))
fig.savefig(OUT / "ws4_h4_loo.png", dpi=160)
plt.close(fig)

print("wrote", OUT / "ws4_h2_winrates.png")
print("wrote", OUT / "ws4_h4_loo.png")
