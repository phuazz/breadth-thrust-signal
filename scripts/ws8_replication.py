"""WS8 section 4b — cross-sectional replication.

The S&P 500 window is spent, so the only genuinely fresh test of the thrust
mechanism comes from a different cross-section. Rebuild D1-D4 unchanged on
Russell 2000 and S&P SmallCap 600 point-in-time breadth, and ask the
pre-registered question of the one cell that survived WS7:

    fresh event, score >= 3, one month forward -- is the median lift positive?

Breadth measured on a universe trades that universe's own index, so this tests
the mechanism rather than a cross-market signal.

Pre-registered gate: failure in BOTH universes closes WS8 negative regardless
of the S&P 500 backtest.

Run:  python scripts/ws8_replication.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import compute_breadth as cb  # noqa: E402
import forward_returns as fr  # noqa: E402
import norgate_provider as npv  # noqa: E402
import ws8_tilt as tilt_mod  # noqa: E402

log = logging.getLogger("ws8_rep")
OUT = ROOT / "reviews" / "2026-08-01_ws8_replication.json"

CELL_THRESHOLD = 3
CELL_HORIZON = "1m"


def cluster_count(dates, gap_days: int = 63) -> int:
    if len(dates) == 0:
        return 0
    d = pd.DatetimeIndex(sorted(dates))
    return 1 + int((d.to_series().diff().dt.days.fillna(0) > gap_days).sum())


CALIBRATION_SIZE = 500.0   # the universe the frozen thresholds were set on


def study_universe(u, scale_mode: str = "sized") -> dict:
    """scale_mode: 'literal' keeps the frozen numeric thresholds; 'sized'
    rescales the two COUNT-based ones by universe size.

    DEVIATION FROM SPEC, logged: the pre-registration said "rebuild D1-D4 on
    each, unchanged". Taken literally that is unfaithful, because the McClellan
    floor (-50 net advances) and the net-new-highs threshold (>20) are counts,
    not ratios. On a ~2,000-name Russell 2000 they represent a quarter of the
    fraction they do on the S&P 500, so the literal reading makes the signal
    substantially looser rather than the same. Both runs are reported so the
    effect of the choice is visible; 'sized' is the headline.
    """
    root = npv.cache_root_for(u)
    syms = npv.resolve_universe(u)
    close, volume = npv.build_panel(root, syms)
    mask = npv.membership_mask(syms, close.index, u)
    panels = cb.build_panels(close.where(mask), volume.where(mask))
    members = mask.sum(axis=1)
    scale = 1.0 if scale_mode == "literal" else float(members.median()) / CALIBRATION_SIZE

    comp = cb.compute_composite(panels, scale=scale)
    comp = comp[comp["data_ok"]]
    px = npv.benchmark_series(root, u).reindex(comp.index).ffill()
    log.info("%s [%s, scale=%.2f, median members %d]: %s -> %s, %d valid days",
             u.index_name, scale_mode, scale, int(members.median()),
             comp.index.min().date(), comp.index.max().date(), len(comp))

    cond = fr.conditional_table(comp, px, thresholds=(1, 2, 3, 4), events_only=True)
    base = fr.unconditional_baseline(px)
    lift = fr.lift_table(cond, base)

    ev = comp["event"].astype(bool).shift(1).fillna(False)
    sc = comp["n_dimensions"].shift(1)
    clusters = {t: cluster_count(comp.index[ev & (sc >= t)]) for t in (1, 2, 3, 4)}
    lift["clusters"] = lift["threshold"].map(clusters)

    row = lift[(lift["threshold"] == CELL_THRESHOLD)
               & (lift["horizon"] == CELL_HORIZON)].iloc[0].to_dict()

    # Same headline tilt backtest, driven by this universe's own breadth.
    import norgatedata as nd
    y = nd.price_timeseries("%10YTCM",
                            stock_price_adjustment_setting=nd.StockPriceAdjustmentType.NONE,
                            padding_setting=nd.PaddingType.NONE,
                            timeseriesformat="pandas-dataframe")["Close"]
    bond = tilt_mod.constant_maturity_total_return(y.reindex(px.index).ffill())
    t = tilt_mod.tilt_series(ev, sc, "V1", tilt_mod.DELTA_HEADLINE, tilt_mod.HOLD_HEADLINE)
    sig = tilt_mod.metrics(tilt_mod.backtest(px, bond, t))
    bse = tilt_mod.metrics(tilt_mod.backtest(px, bond, pd.Series(0.0, index=px.index)))

    return {
        "universe": u.slug,
        "index": u.index_name,
        "note": u.note,
        "scale_mode": scale_mode,
        "threshold_scale": scale,
        "median_members": int(members.median()),
        "window": [str(comp.index.min().date()), str(comp.index.max().date())],
        "valid_days": int(len(comp)),
        "ever_members": len(syms),
        "cell": {
            "threshold": CELL_THRESHOLD, "horizon": CELL_HORIZON,
            "n": int(row["n"]), "clusters": int(row["clusters"]),
            "win_rate": row["win_rate"], "base_win_rate": row["base_win_rate"],
            "base_win_hi": row["base_win_hi"], "win_beyond_noise": bool(row["win_beyond_noise"]),
            "median_ret": row["median_ret"], "base_median_ret": row["base_median_ret"],
            "base_ret_hi": row["base_ret_hi"], "ret_beyond_noise": bool(row["ret_beyond_noise"]),
            "median_lift_pp": float((row["median_ret"] - row["base_median_ret"]) * 100),
            "replicates": bool(row["median_ret"] > row["base_median_ret"]),
        },
        "tilt_backtest": {"signal": sig, "base": bse,
                          "sharpe_delta": sig["sharpe"] - bse["sharpe"],
                          "n_tilts": int(((t > 0) & (t.shift(1).fillna(0) == 0)).sum())},
        "full_grid": lift.to_dict(orient="records"),
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    out = {}
    for u in (npv.R2000, npv.SP600):
        for mode in ("sized", "literal"):
            key = u.slug if mode == "sized" else f"{u.slug}_literal"
            try:
                out[key] = study_universe(u, mode)
            except Exception as e:  # noqa: BLE001
                log.error("  %s FAILED: %s: %s", key, type(e).__name__, e)
                out[key] = {"error": f"{type(e).__name__}: {e}"}
                continue
            c = out[key]["cell"]
            log.info("  %s cell >=3 / 1m: n=%d clusters=%d median %+.2f%% vs base "
                     "%+.2f%% (lift %+.2fpp) -> %s", key, c["n"], c["clusters"],
                     c["median_ret"] * 100, c["base_median_ret"] * 100,
                     c["median_lift_pp"],
                     "REPLICATES" if c["replicates"] else "DOES NOT REPLICATE")
            b = out[key]["tilt_backtest"]
            log.info("     tilt: signal sharpe %.4f vs base %.4f (%+.4f), %d tilts",
                     b["signal"]["sharpe"], b["base"]["sharpe"], b["sharpe_delta"],
                     b["n_tilts"])
    for key in list(out):
        c = out[key].get("cell")
        if not c:
            continue
    # Gate is judged on the headline (size-adjusted) runs only.
    good = [k for k, v in out.items()
            if "cell" in v and v["cell"]["replicates"] and not k.endswith("_literal")]
    out["_gate"] = {
        "rule": ("pre-registered: the 1m >=3 cell must show a positive median lift in "
                 "at least ONE universe for the mechanism to be called replicated"),
        "replicated_in": good,
        "verdict": "REPLICATED" if good else "NOT REPLICATED",
    }
    log.info("\nGATE: %s (%s)", out["_gate"]["verdict"], good or "neither universe")
    OUT.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    log.info("wrote %s", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
