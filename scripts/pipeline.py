"""Breadth-thrust-signal pipeline — fetch, compute, study, render.

Canonical build entry point (per vault convention: pipeline.py, not build.py):

    python scripts/pipeline.py                 # full run, render dashboard
    python scripts/pipeline.py --no-fetch      # recompute from cached panel only
    python scripts/pipeline.py --self-test     # synthetic end-to-end smoke test

Stages
------
1. Resolve membership (point-in-time CSP1 snapshots if present, else current-list
   fallback with a loud survivorship flag).
2. Fetch / update the constituent price+volume panel (cached).
3. Build breadth panels -> grouped/weighted composite (compute_breadth).
4. Conditional forward-return study with bootstrap baseline (forward_returns).
5. Emit data/signals.json and inject it into template.html -> docs/index.html.

The heavy constituent fetch is network-bound; run it locally. CI can run with
--no-fetch against a committed panel cache, matching breadth-thrust-etf.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import compute_breadth as cb  # noqa: E402
import forward_returns as fr  # noqa: E402
import membership as mb  # noqa: E402
from data_providers import PanelCache  # noqa: E402

DATA = ROOT / "data"
DOCS = ROOT / "docs"
TEMPLATE = ROOT / "template.html"

BENCHMARK = "^GSPC"           # SPX level for the forward-return study
START = "1999-01-01"          # burn-in for 252-day lookbacks
PIT_SNAPSHOTS = DATA / "constituents_csp1.json"   # optional point-in-time source

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("pipeline")


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------


def resolve_membership(adj, vol):
    """Return (adj, vol, survivorship_bias_flag). Prefer point-in-time."""
    if PIT_SNAPSHOTS.exists():
        log.info("Using point-in-time membership: %s", PIT_SNAPSHOTS.name)
        mask = mb.load_pit_snapshots(str(PIT_SNAPSHOTS))
        adj_m, vol_m = mb.apply_membership(adj, vol, mask)
        return adj_m, vol_m, False
    log.warning(
        "No point-in-time snapshot found (%s). Falling back to whatever is in "
        "the panel cache as a STATIC universe — survivorship bias is present.",
        PIT_SNAPSHOTS.name,
    )
    return adj, vol, True


# ---------------------------------------------------------------------------
# Study assembly
# ---------------------------------------------------------------------------


def valid_window(composite: pd.DataFrame):
    """First and last dates where breadth data is trustworthy (data_ok).

    Conditional thrust events can only occur inside this window — outside it the
    constituent panel is too thin (e.g. pre-2018 under point-in-time membership,
    where the mask has no members). Returned as (lo, hi) Timestamps, or
    (None, None) if no day is valid.
    """
    ok = composite.index[composite["data_ok"]]
    if len(ok) == 0:
        return None, None
    return ok.min(), ok.max()


def run_study(composite: pd.DataFrame, spx: pd.Series) -> dict:
    # GUARD 3 (period-matching) — the bootstrap baseline must be drawn from the
    # SAME era the conditional events can occur in. Conditional events live only
    # in the valid-breadth window; bootstrapping the baseline over a longer span
    # (e.g. 1999-2026 including the dot-com and GFC crashes when the panel has no
    # members) would make the lift apples-to-oranges and silently overstate it.
    # Restrict BOTH the conditional sample and the baseline to that window.
    lo, hi = valid_window(composite)
    if lo is not None:
        in_win = (spx.index >= lo) & (spx.index <= hi)
        spx = spx[in_win]
        composite = composite.loc[(composite.index >= lo) & (composite.index <= hi)]

    cond = fr.conditional_table(composite, spx, thresholds=(1, 2, 3, 4), events_only=True)
    base = fr.unconditional_baseline(spx)
    lift = fr.lift_table(cond, base)
    return {
        "window": {
            "start": lo.strftime("%Y-%m-%d") if lo is not None else None,
            "end": hi.strftime("%Y-%m-%d") if hi is not None else None,
            "trading_days": int(len(spx)),
            "note": (
                "Conditional sample and bootstrap baseline are both restricted "
                "to the valid-breadth window (data_ok days) so the lift is "
                "period-matched, not measured against a different era."
            ),
        },
        "conditional": cond.to_dict(orient="records"),
        "baseline": base.to_dict(orient="records"),
        "lift": lift.replace({np.nan: None}).to_dict(orient="records"),
    }


def current_status(composite: pd.DataFrame) -> dict:
    last = composite.iloc[-1]
    dims = {}
    for d, label in [
        ("d1", "Advance/Decline thrust"),
        ("d2", "% above 50d MA thrust"),
        ("d3", "New-high / new-low thrust"),
        ("d4", "Up-volume thrust"),
    ]:
        dims[d] = {"label": label, "on": bool(last[f"{d}_on"])}
    return {
        "as_of": composite.index[-1].strftime("%Y-%m-%d"),
        "n_dimensions": int(last["n_dimensions"]),
        "score": float(last["score"]),
        "dimensions": dims,
        "data_ok": bool(last["data_ok"]),
        "valid_count": int(last["valid_count"]) if last["valid_count"] == last["valid_count"] else None,
    }


def timeline(composite: pd.DataFrame, spx: pd.Series) -> dict:
    """Compact arrays for the dashboard charts.

    Restricted to the valid-breadth window so the chart does not paint the
    no-data pre-window era (all-zero by construction) as 18 years of measured
    zero conviction.
    """
    lo, hi = valid_window(composite)
    if lo is not None:
        composite = composite.loc[(composite.index >= lo) & (composite.index <= hi)]
    idx = composite.index
    spx_aligned = spx.reindex(idx)
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in idx],
        "spx": [None if x != x else round(float(x), 2) for x in spx_aligned.to_numpy()],
        "n_dimensions": [int(x) for x in composite["n_dimensions"].to_numpy()],
        "d1_on": [bool(x) for x in composite["d1_on"]],
        "d2_on": [bool(x) for x in composite["d2_on"]],
        "d3_on": [bool(x) for x in composite["d3_on"]],
        "d4_on": [bool(x) for x in composite["d4_on"]],
        "event": [bool(x) for x in composite["event"]],
    }


def last_signal_block(composite: pd.DataFrame, spx: pd.Series) -> dict:
    """Track the most recent thrust event against its own historical projection.

    Finds the last fresh event in the valid-breadth window, anchors at the
    session AFTER it (the no-lookahead convention the study uses), and reports
    the realised SPX path since, plus this event's realised forward return at
    each horizon. The projected median and range come from the conditional
    study (study.conditional, joined by threshold/horizon in the dashboard).
    """
    lo, hi = valid_window(composite)
    if lo is None:
        return {}
    comp = composite.loc[(composite.index >= lo) & (composite.index <= hi)]
    px = spx[(spx.index >= lo) & (spx.index <= hi)].sort_index()
    # Align scores onto the price index.
    nd = comp["n_dimensions"].reindex(px.index)
    ev = comp["event"].reindex(px.index).fillna(False).astype(bool)

    ev_positions = [i for i, e in enumerate(ev.to_numpy()) if e and nd.iloc[i] >= 1]
    if not ev_positions:
        return {}
    e = ev_positions[-1]
    anchor = e + 1  # forward window starts the next session (matches the study)
    if anchor >= len(px):
        return {}

    vals = px.to_numpy(dtype=float)
    base = vals[anchor]
    last = len(px) - 1
    days_since = int(last - anchor)
    score = int(nd.iloc[e])

    realized_by_h = {}
    for label, h in fr.HORIZONS.items():
        j = anchor + h
        realized_by_h[label] = (float(vals[j] / base - 1.0) if j <= last else None)

    path_days = list(range(0, days_since + 1))
    path_ret = [float(vals[anchor + k] / base - 1.0) for k in path_days]

    return {
        "date": px.index[e].strftime("%Y-%m-%d"),
        "anchor_date": px.index[anchor].strftime("%Y-%m-%d"),
        "score": score,
        "days_since": days_since,
        "spx_at_anchor": round(float(base), 2),
        "spx_now": round(float(vals[last]), 2),
        "realized_to_now": float(vals[last] / base - 1.0),
        "realized_by_horizon": realized_by_h,
        "horizons": fr.HORIZONS,
        "path_days": path_days,
        "path_ret": [round(r, 5) for r in path_ret],
    }


def formation_block(composite: pd.DataFrame, panels) -> dict:
    """Live per-dimension breakdown for the dashboard's "how it is formed" view.

    For each of the four dimensions: whether it is currently on (within the
    memory window), why its sub-conditions are grouped, and a gauge per raw
    reading showing where it sits relative to its canonical trigger(s). Reading
    values come from cb.latest_readings; sub-condition fire states and the
    dimension on-state come from the composite's last row.
    """
    r = cb.latest_readings(panels)
    last = composite.iloc[-1]

    def pct(x):
        return "—" if x is None else f"{x * 100:.0f}%"

    def num(x, d=2):
        return "—" if x is None else f"{x:.{d}f}"

    def gauge(label, value, scale_min, scale_max, markers, fired, display, hint):
        return {
            "label": label,
            "value": value,
            "display": display,
            "scale": {"min": scale_min, "max": scale_max},
            "markers": markers,
            "fired": bool(fired),
            "hint": hint,
        }

    dims = [
        {
            "key": "d1", "label": "Advance / Decline", "on": bool(last["d1_on"]),
            "why": ("Zweig, the 10-day A/D ratio and the McClellan Oscillator all "
                    "derive from one advance/decline series, so they are OR-ed and "
                    "counted once."),
            "gauges": [
                gauge("Zweig EMA(10) of advancers' share", r["zweig_ema"], 0, 1,
                      [{"at": 0.40, "label": "0.40"}, {"at": 0.615, "label": "0.615 trigger"}],
                      last["zweig"], pct(r["zweig_ema"]),
                      "Thrust: compress below 0.40, then cross above 0.615 within 10 sessions."),
                gauge("10-day cumulative A/D ratio", r["ad_ratio_10d"], 0, 3,
                      [{"at": 1.90, "label": "1.90 trigger"}],
                      last["ad_ratio_deemer"], num(r["ad_ratio_10d"]),
                      "Deemer breakaway momentum: above 1.90."),
                gauge("McClellan Oscillator", r["mcclellan_osc"], -150, 150,
                      [{"at": -50, "label": "−50"}, {"at": 0, "label": "0 trigger"}],
                      last["mcclellan"], num(r["mcclellan_osc"], 0),
                      "Thrust: dip below −50, then recross 0 within 20 sessions."),
            ],
        },
        {
            "key": "d2", "label": "% above 50-day MA", "on": bool(last["d2_on"]),
            "why": "Share of members trading above their own 50-day moving average.",
            "gauges": [
                gauge("% of members above 50-day MA", r["pct_above_50dma"], 0, 1,
                      [{"at": 0.25, "label": "25%"}, {"at": 0.75, "label": "75% trigger"}],
                      last["pct_above_50dma"], pct(r["pct_above_50dma"]),
                      "Thrust: surge from below 25% to above 75% within 15 sessions."),
            ],
        },
        {
            "key": "d3", "label": "New highs / new lows", "on": bool(last["d3_on"]),
            "why": "52-week new highs versus new lows, in two expressions that are OR-ed.",
            "gauges": [
                gauge("New highs / (highs + lows)", r["nhnl_ratio"], 0, 1,
                      [{"at": 0.10, "label": "10%"}, {"at": 0.50, "label": "50% trigger"}],
                      last["nhnl_ratio"], pct(r["nhnl_ratio"]),
                      "Thrust: surge from below 10% to above 50% within 10 sessions."),
                gauge("Net new highs (highs − lows)", r["net_new_highs"], -100, 100,
                      [{"at": 0, "label": "0"}, {"at": 20, "label": "+20 trigger"}],
                      last["net_new_highs"], num(r["net_new_highs"], 0),
                      "Thrust: rise from negative to above +20 within 10 sessions."),
            ],
        },
        {
            "key": "d4", "label": "Up-volume", "on": bool(last["d4_on"]),
            "why": "Volume of advancing names as a share of total (raw, unadjusted volume).",
            "gauges": [
                gauge("Up-volume ratio (best of trailing 5)", r["up_volume_trailing5_max"], 0, 1,
                      [{"at": 0.90, "label": "0.90 trigger"}],
                      last["up_volume"], pct(r["up_volume_trailing5_max"]),
                      "Thrust: above 0.90 on any of the last 5 sessions."),
            ],
        },
    ]
    return {"memory_days": cb.DEFAULT_MEMORY_DAYS, "dimensions": dims}


def build_payload(composite, spx, survivorship_bias, data_quality=None, panels=None) -> dict:
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "survivorship_bias": survivorship_bias,
        "data_quality": data_quality or {},
        "config": {
            "memory_days": cb.DEFAULT_MEMORY_DAYS,
            "dimensions": ["d1", "d2", "d3", "d4"],
            "note": (
                "Grouped/weighted score. The four dimensions are independent "
                "breadth facts; the A/D family (Zweig, McClellan, 10d A/D) is "
                "collapsed into d1 to avoid double counting. Summation Index "
                "deliberately excluded (would require an in-sample threshold)."
            ),
        },
        "current": current_status(composite),
        "formation": formation_block(composite, panels) if panels is not None else {},
        "last_signal": last_signal_block(composite, spx),
        "study": run_study(composite, spx),
        "timeline": timeline(composite, spx),
    }


def render(payload: dict) -> None:
    DOCS.mkdir(exist_ok=True)
    blob = json.dumps(payload, separators=(",", ":"))
    if TEMPLATE.exists():
        html = TEMPLATE.read_text(encoding="utf-8")
        # Replace ONLY the first occurrence — the data-island placeholder. The
        # token also appears a second time as the sentinel in the JS fetch-
        # fallback check (`if (raw === "__SIGNALS_JSON__")`); injecting the blob
        # there too would splice JSON into a string literal and break the whole
        # inline script. count=1 leaves the sentinel intact.
        html = html.replace("__SIGNALS_JSON__", blob, 1)
        (DOCS / "index.html").write_text(html, encoding="utf-8")
        log.info("Wrote %s", DOCS / "index.html")
    (DATA / "signals.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log.info("Wrote %s", DATA / "signals.json")


# ---------------------------------------------------------------------------
# Self-test (synthetic, no network) — proves the pipeline wires together.
# ---------------------------------------------------------------------------


def synthetic_run() -> dict:
    rng = np.random.default_rng(7)
    n_days, n_tickers = 1500, 480
    dates = pd.bdate_range(start=datetime(2018, 1, 2), periods=n_days)
    cols = [f"T{i:03d}" for i in range(n_tickers)]
    steps = rng.normal(0.0003, 0.012, size=(n_days, n_tickers))
    # Plant two synchronised breadth surges (post-drawdown rallies).
    for s in (300, 900):
        steps[s : s + 12, :] += 0.02
        steps[s - 40 : s, :] -= 0.01
    prices = 100 * np.exp(np.cumsum(steps, axis=0))
    adj = pd.DataFrame(prices, index=dates, columns=cols)
    vol = pd.DataFrame(rng.integers(1000, 9000, size=(n_days, n_tickers)), index=dates, columns=cols)
    panels = cb.build_panels(adj, vol)
    comp = cb.compute_composite(panels)
    spx = adj.mean(axis=1)
    payload = build_payload(comp, spx, survivorship_bias=True, panels=panels)
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-fetch", action="store_true", help="recompute from cache only")
    ap.add_argument("--self-test", action="store_true", help="synthetic end-to-end run")
    ap.add_argument("--tickers", default=str(DATA / "universe.json"),
                    help="JSON list of tickers for the fallback static universe")
    args = ap.parse_args()

    if args.self_test:
        payload = synthetic_run()
        render(payload)
        c = payload["current"]
        log.info("Self-test OK — as of %s, %d/4 dimensions on", c["as_of"], c["n_dimensions"])
        return 0

    # Resolve universe for fetch.
    universe_path = Path(args.tickers)
    if universe_path.exists():
        universe = mb.current_members_from_list(json.loads(universe_path.read_text()))
    elif PIT_SNAPSHOTS.exists():
        snaps = json.loads(PIT_SNAPSHOTS.read_text())["snapshots"]
        universe = sorted({t for s in snaps.values() for t in s["tickers"]})
    else:
        log.error("No universe.json and no constituents_csp1.json — nothing to fetch.")
        return 1

    cache = PanelCache(str(DATA / "panel_cache.json"))
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not args.no_fetch:
        cache.update(universe + [BENCHMARK], START, end)

    adj, vol = cache.to_frames()
    if BENCHMARK not in adj.columns:
        log.error("Benchmark %s not in panel — fetch it first.", BENCHMARK)
        return 1
    spx = adj[BENCHMARK].dropna()
    adj = adj.drop(columns=[BENCHMARK])
    vol = vol.drop(columns=[c for c in [BENCHMARK] if c in vol.columns])

    n_fetched = adj.shape[1]   # constituents with any price data in the panel

    adj, vol, survivorship = resolve_membership(adj, vol)
    n_used = adj.shape[1]      # constituents matched to the membership universe
    panels = cb.build_panels(adj, vol)
    comp = cb.compute_composite(panels)

    # Residual data-layer leak (distinct from survivorship of the MEMBERSHIP
    # universe, which the PIT mask fixes): delisted / renamed former members
    # that Yahoo no longer serves cannot be fetched, so they silently drop out
    # of the historical breadth count. Disclose the magnitude. Delisted names
    # skew weak, so their absence mildly understates past declines.
    ever_members = None
    if PIT_SNAPSHOTS.exists():
        snaps = json.loads(PIT_SNAPSHOTS.read_text())["snapshots"]
        ever_members = len({t for s in snaps.values() for t in s["tickers"]})
    data_quality = {
        "ever_members": ever_members,
        "fetched_constituents": int(n_fetched),
        "used_constituents": int(n_used),
        "unfetchable_members": (int(ever_members - n_used) if ever_members else None),
        "min_valid_constituents": cb.MIN_VALID_CONSTITUENTS,
        "note": (
            "Membership is point-in-time (survivorship-correct). Residual leak: "
            "former members delisted/renamed beyond Yahoo's reach cannot be "
            "fetched and drop from historical breadth. Days below "
            "min_valid_constituents are flagged data_ok=false and excluded from "
            "the study window."
        ),
    }

    # Data-integrity guard (vault rule): flag thin breadth days.
    thin = (~comp["data_ok"]).sum()
    if thin:
        log.warning("%d trading days have < %d valid constituents.", thin, cb.MIN_VALID_CONSTITUENTS)

    payload = build_payload(comp, spx.reindex(comp.index), survivorship, data_quality, panels)
    render(payload)
    c = payload["current"]
    log.info("Done — as of %s, %d/4 dimensions on (score %.1f)", c["as_of"], c["n_dimensions"], c["score"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
