"""WS8 — is the surviving breadth-thrust cell deployable net of costs?

Executes the tests fixed in ``C:\\dev\\KICKOFF_ws8-thrust-tilt-deployability.md``
(sign-off 2026-08-01). Nothing here tunes a parameter: the tilt size, hold
length, base weights, cost model and decision rule were all frozen before this
file existed.

The question is narrow. WS7 measured statistical lift and never ran a
net-of-cost backtest. One cell survived every cut -- fresh events at score >= 3,
one month forward -- and this asks whether it is deployable or merely
measurable.

Run:  python scripts/ws8_tilt.py
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import compute_breadth as cb  # noqa: E402
import norgate_provider as npv  # noqa: E402

log = logging.getLogger("ws8")
OUT = ROOT / "reviews" / "2026-08-01_ws8_results.json"

# --- frozen in the pre-registration -----------------------------------------
BASE_EQUITY = 0.60            # 60/40 reference frame, monthly rebalance
DELTA_HEADLINE = 0.20         # tilt size, 60/40 -> 80/20
DELTAS = (0.10, 0.20, 0.30)   # sensitivities, fixed here, not searched
HOLD_HEADLINE = 21            # trading days
HOLDS = (10, 21, 42)
TX_BPS = 10.0                 # per unit of allocation change (WS4 cost model)
N_NULL = 2000                 # random-entry draws
SEED = 42
ERAS = {"1990-2008": ("1990-01-01", "2008-12-31"),
        "2009-2026": ("2009-01-01", "2026-12-31")}


# ---------------------------------------------------------------------------
# Bond leg
# ---------------------------------------------------------------------------


def constant_maturity_total_return(yield_pct: pd.Series, maturity: float = 10.0,
                                   freq: int = 2) -> pd.Series:
    """Daily total return of a rolling constant-maturity par Treasury.

    DEVIATION FROM SPEC, logged: the pre-registration named IEF, but IEF begins
    2002-07-26 and the study window opens 1990. Splicing two series at 2002
    would put a seam in the middle of the sample. Instead the whole window uses
    one consistent methodology -- hold a par bond struck at yesterday's yield,
    reprice it today at today's yield one day closer to maturity, add the
    day's accrued coupon -- and ``validate_bond_proxy`` checks it against IEF
    over the overlap.

    The decision is near-insensitive to this choice in any case: the signal
    portfolio and its null share the same bond leg and the same tilt frequency,
    so the bond series moves the reported absolute Sharpe but very little of
    the signal-versus-null comparison the decision rests on.
    """
    y = (yield_pct / 100.0).astype(float)
    y_prev = y.shift(1)
    n = maturity * freq
    c = y_prev / freq                      # par coupon set at yesterday's yield
    dt = 1.0 / 252.0
    n_new = (maturity - dt) * freq         # one day closer to maturity
    r_new = y / freq

    # Price the (now slightly seasoned) par bond at today's yield.
    disc = np.power(1.0 + r_new, -n_new)
    ann = (1.0 - disc) / r_new.replace(0.0, np.nan)
    price = c * ann + disc                 # per 1.0 of face
    accrued = y_prev * dt
    ret = price - 1.0 + accrued
    return ret.fillna(0.0)


def validate_bond_proxy(proxy: pd.Series, root: Path) -> dict:
    """Guard for the deviation above: does the synthetic track IEF where IEF
    exists? If it does not, the pre-2002 bond leg is not trustworthy."""
    try:
        ief = npv._read(npv._cache_path(root, npv.CLOSE_BASIS, "IEF"), npv.CLOSE_BASIS)["Close"]
    except Exception as e:  # noqa: BLE001
        return {"available": False, "note": f"IEF not cached: {e}"}
    ief_ret = ief.pct_change().dropna()
    j = pd.concat([proxy.rename("proxy"), ief_ret.rename("ief")], axis=1).dropna()
    if len(j) < 250:
        return {"available": False, "note": "insufficient overlap"}
    ann = lambda s: (1 + s).prod() ** (252 / len(s)) - 1  # noqa: E731
    return {
        "available": True,
        "overlap_days": int(len(j)),
        "overlap_start": str(j.index.min().date()),
        "correlation": float(j["proxy"].corr(j["ief"])),
        "proxy_ann_return": float(ann(j["proxy"])),
        "ief_ann_return": float(ann(j["ief"])),
        "ann_return_gap_pp": float((ann(j["proxy"]) - ann(j["ief"])) * 100),
        "proxy_ann_vol": float(j["proxy"].std() * np.sqrt(252)),
        "ief_ann_vol": float(j["ief"].std() * np.sqrt(252)),
    }


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


def tilt_series(events: pd.Series, scores: pd.Series, variant: str,
                delta: float, hold: int) -> pd.Series:
    """Daily equity tilt above the base weight.

    V1 selective : fresh event with score >= 3 -> full delta for `hold` days.
    V2 graded    : any fresh event -> delta * score/4 for `hold` days.
    A new event during an active tilt restarts the clock; tilts never stack.
    """
    tilt = pd.Series(0.0, index=events.index)
    if variant == "V1":
        trig = events & (scores >= 3)
        size = pd.Series(delta, index=events.index)
    elif variant == "V2":
        trig = events & (scores >= 1)
        size = delta * (scores.clip(lower=0, upper=4) / 4.0)
    else:
        raise ValueError(variant)

    remaining, current = 0, 0.0
    idx = np.flatnonzero(trig.to_numpy())
    trig_set = set(idx.tolist())
    sz = size.to_numpy()
    out = np.zeros(len(tilt))
    for i in range(len(tilt)):
        if i in trig_set and not np.isnan(sz[i]):
            remaining, current = hold, float(sz[i])
        if remaining > 0:
            out[i] = current
            remaining -= 1
    return pd.Series(out, index=tilt.index)


def backtest(px: pd.Series, bond_ret: pd.Series, tilt: pd.Series,
             base: float = BASE_EQUITY, tx_bps: float = TX_BPS) -> pd.Series:
    """Equity curve for the tilted 60/40. Weights drift between trades; we
    trade to target monthly and whenever the tilt changes, paying cost on the
    actual weight moved."""
    px = px.astype(float)
    eq_ret = px.pct_change().fillna(0.0).to_numpy()
    bd_ret = bond_ret.reindex(px.index).fillna(0.0).to_numpy()
    target = (base + tilt.reindex(px.index).fillna(0.0)).clip(0.0, 1.0).to_numpy()
    month_end = px.index.to_period("M")
    is_rebal = np.zeros(len(px), dtype=bool)
    is_rebal[:-1] = month_end[:-1].to_numpy() != month_end[1:].to_numpy()

    w = target[0]
    equity = np.empty(len(px))
    equity[0] = 1.0
    turnover = 0.0
    for t in range(1, len(px)):
        port_r = w * eq_ret[t] + (1.0 - w) * bd_ret[t]
        # weight drifts with relative performance
        denom = 1.0 + port_r
        w_drift = (w * (1.0 + eq_ret[t]) / denom) if denom > 0 else w
        cost = 0.0
        if is_rebal[t] or target[t] != target[t - 1]:
            moved = abs(target[t] - w_drift)
            if moved > 1e-4:
                cost = moved * tx_bps / 10000.0
                turnover += moved
            w = target[t]
        else:
            w = w_drift
        equity[t] = equity[t - 1] * (1.0 + port_r - cost)
    s = pd.Series(equity, index=px.index)
    s.attrs["turnover"] = turnover
    return s


def metrics(equity: pd.Series) -> dict:
    r = equity.pct_change().dropna()
    if len(r) < 2:
        return {}
    yrs = len(r) / 252.0
    cagr = equity.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(252)
    dd = (equity / equity.cummax() - 1.0).min()
    return {
        "cagr": float(cagr),
        "vol": float(vol),
        "sharpe": float(cagr / vol) if vol > 0 else float("nan"),
        "max_dd": float(dd),
        "years": float(yrs),
        "turnover_per_yr": float(equity.attrs.get("turnover", 0.0) / yrs),
    }


# ---------------------------------------------------------------------------
# The null
# ---------------------------------------------------------------------------


def random_entry_null(px, bond_ret, tilt, n_draws=N_NULL, seed=SEED) -> dict:
    """Cost-matched random-entry control.

    Implemented as a random CIRCULAR ROTATION of the realised tilt series.
    This preserves the number of tilts, their sizes, their durations and their
    clustering EXACTLY, and destroys only the alignment with market state --
    which is precisely the thing under test. Independent block draws would
    have perturbed the clustering as well, making the null easier to beat.
    """
    rng = np.random.default_rng(seed)
    vals = tilt.to_numpy()
    n = len(vals)
    out = []
    for _ in range(n_draws):
        k = int(rng.integers(1, n))
        rot = pd.Series(np.roll(vals, k), index=tilt.index)
        out.append(metrics(backtest(px, bond_ret, rot)))
    sh = np.array([m["sharpe"] for m in out if m])
    cg = np.array([m["cagr"] for m in out if m])
    return {
        "n_draws": int(len(sh)),
        "sharpe_p50": float(np.median(sh)), "sharpe_p95": float(np.percentile(sh, 95)),
        "sharpe_p05": float(np.percentile(sh, 5)),
        "cagr_p50": float(np.median(cg)), "cagr_p95": float(np.percentile(cg, 95)),
    }


# ---------------------------------------------------------------------------


def load(universe=None):
    u = universe or npv.SP500
    root = npv.cache_root_for(u)
    syms = npv.resolve_universe(u)
    close, volume = npv.build_panel(root, syms)
    mask = npv.membership_mask(syms, close.index, u)
    comp = cb.compute_composite(cb.build_panels(close.where(mask), volume.where(mask)))
    comp = comp[comp["data_ok"]]
    px = npv.benchmark_series(root, u).reindex(comp.index).ffill()
    return comp, px, root


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--universe", default="sp500", choices=sorted(npv.UNIVERSES))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    u = npv.UNIVERSES[args.universe]
    comp, px, root = load(u)
    log.info("%s: %s -> %s, %d days", u.index_name,
             comp.index.min().date(), comp.index.max().date(), len(comp))

    import norgatedata as nd
    y = nd.price_timeseries("%10YTCM", stock_price_adjustment_setting=nd.StockPriceAdjustmentType.NONE,
                            padding_setting=nd.PaddingType.NONE,
                            timeseriesformat="pandas-dataframe")["Close"]
    bond = constant_maturity_total_return(y.reindex(px.index).ffill())
    proxy_check = validate_bond_proxy(bond, npv.cache_root_for(npv.SP500))
    log.info("bond proxy vs IEF: %s", proxy_check)

    events = comp["event"].astype(bool).shift(1).fillna(False)
    scores = comp["n_dimensions"].shift(1)

    results = {"universe": u.slug, "index": u.index_name,
               "window": [str(comp.index.min().date()), str(comp.index.max().date())],
               "bond_proxy_check": proxy_check, "variants": {}}

    base_curve = backtest(px, bond, pd.Series(0.0, index=px.index))
    results["base_60_40"] = metrics(base_curve)
    results["buy_and_hold"] = metrics(backtest(px, bond, pd.Series(1 - BASE_EQUITY, index=px.index)))
    log.info("base 60/40: %s", {k: round(v, 4) for k, v in results["base_60_40"].items()})

    for variant in ("V1", "V2"):
        for delta in DELTAS:
            for hold in HOLDS:
                tilt = tilt_series(events, scores, variant, delta, hold)
                curve = backtest(px, bond, tilt)
                m = metrics(curve)
                m["days_tilted"] = int((tilt > 0).sum())
                m["pct_tilted"] = float((tilt > 0).mean())
                m["n_tilts"] = int(((tilt > 0) & (tilt.shift(1).fillna(0) == 0)).sum())
                key = f"{variant}_d{int(delta*100)}_h{hold}"
                headline = (variant == "V1" and delta == DELTA_HEADLINE
                            and hold == HOLD_HEADLINE)
                m["headline"] = headline
                if headline:
                    m["null"] = random_entry_null(px, bond, tilt)
                    m["verdict"] = ("PASS" if m["sharpe"] > m["null"]["sharpe_p95"]
                                    else "FAIL")
                    log.info("HEADLINE %s: sharpe %.3f vs null p95 %.3f -> %s",
                             key, m["sharpe"], m["null"]["sharpe_p95"], m["verdict"])
                results["variants"][key] = m

    # Era split — mandatory, whatever the pooled result says.
    results["eras"] = {}
    tilt = tilt_series(events, scores, "V1", DELTA_HEADLINE, HOLD_HEADLINE)
    for era, (lo, hi) in ERAS.items():
        w = (px.index >= lo) & (px.index <= hi)
        if w.sum() < 500:
            continue
        p, b, t = px[w], bond[w], tilt[w]
        sig, base_e = metrics(backtest(p, b, t)), metrics(backtest(p, b, pd.Series(0.0, index=p.index)))
        results["eras"][era] = {
            "signal": sig, "base": base_e,
            "sharpe_delta": sig["sharpe"] - base_e["sharpe"],
            "n_tilts": int(((t > 0) & (t.shift(1).fillna(0) == 0)).sum()),
        }
        log.info("  era %s: signal sharpe %.3f vs base %.3f (%+.3f), %d tilts",
                 era, sig["sharpe"], base_e["sharpe"],
                 sig["sharpe"] - base_e["sharpe"], results["eras"][era]["n_tilts"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    prev[u.slug] = results
    OUT.write_text(json.dumps(prev, indent=2, default=str), encoding="utf-8")
    log.info("wrote %s", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
