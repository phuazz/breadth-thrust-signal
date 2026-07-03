"""WS4 breadth stress-test — H1 level-vs-change, H2 level-quartile contrast,
H3 narrowness replication.

Pre-registered spec: C:/dev/KICKOFF_ws4-breadth-stresstest.md. This script
runs the three tests that live in this repo. H2 REUSES the Phase 0 thrust
study results verbatim from data/signals.json (study subtree) and adds only
the level-conditioned contrast, computed with the same forward_returns.py
machinery, the same one-day lag guard, and the same moving-block bootstrap
baseline.

Level series guard (spec section 2, silent-wrong #2): the breadth LEVEL is
taken raw from breadth-thrust-etf/data/breadth_csp1.json (series.ma_breadth,
share of CSP1 constituents above their 50-day MA). It is never derived from
the thrust pipeline's 60-day memory state.

Output: reviews/2026-07-03_ws4_results.json plus a printed summary.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from forward_returns import (  # noqa: E402
    HORIZONS,
    forward_returns,
    unconditional_baseline,
)

ROOT = Path(__file__).resolve().parent.parent
BTS_SIGNALS = ROOT / "data" / "signals.json"
BREADTH_CSP1 = Path("C:/dev/breadth-thrust-etf/data/breadth_csp1.json")
OUT_JSON = ROOT / "reviews" / "2026-07-03_ws4_results.json"

N_BOOT = 2000
BLOCK = 21
SEED = 42
DECLUSTER_DAYS = 21  # implementation detail fixed at spec time


def load_joint_frame() -> pd.DataFrame:
    """Join the Phase 0 SPX series with the raw CSP1 breadth level."""
    s = json.loads(BTS_SIGNALS.read_text(encoding="utf-8"))
    tl = s["timeline"]
    spx = pd.Series(tl["spx"], index=pd.to_datetime(tl["dates"]), name="spx")

    b = json.loads(BREADTH_CSP1.read_text(encoding="utf-8"))
    series = b["series"]
    if "ma_breadth" not in series:
        raise KeyError(f"ma_breadth not in breadth_csp1 series; keys={list(series.keys())}")
    lvl = pd.Series(series["ma_breadth"], index=pd.to_datetime(series["dates"]),
                    name="level").astype(float)

    df = pd.concat([spx, lvl], axis=1, join="inner").dropna()
    return df.sort_index()


def block_bootstrap_slope(x: np.ndarray, y: np.ndarray, n_boot=N_BOOT,
                          block=BLOCK, seed=SEED) -> dict:
    """Moving-block bootstrap CI for a standardised OLS slope."""
    rng = np.random.default_rng(seed)
    n = len(x)
    n_blocks = max(1, n // block)
    slopes = np.empty(n_boot)
    for i in range(n_boot):
        starts = rng.integers(0, max(1, n - block), size=n_blocks)
        idx = np.concatenate([np.arange(s, s + block) for s in starts])
        xs, ys = x[idx], y[idx]
        xs = (xs - xs.mean()) / (xs.std() or 1.0)
        slopes[i] = np.polyfit(xs, ys, 1)[0]
    return {"slope_boot_median": float(np.median(slopes)),
            "slope_lo5": float(np.percentile(slopes, 5)),
            "slope_hi95": float(np.percentile(slopes, 95))}


def h1_regressions(df: pd.DataFrame) -> list[dict]:
    """Forward returns on breadth LEVEL vs 21d CHANGE, lagged one day."""
    out = []
    level = df["level"]
    change = df["level"] - df["level"].shift(21)
    for label, h in HORIZONS.items():
        if label == "1w":
            continue  # spec horizons are 1m/3m/6m/12m
        fwd = forward_returns(df["spx"], h)
        for name, series in (("level", level), ("change_21d", change)):
            x_all = series.shift(1)  # one-day lag guard
            m = x_all.notna() & fwd.notna()
            x, y = x_all[m].to_numpy(), fwd[m].to_numpy()
            xz = (x - x.mean()) / x.std()
            slope, intercept = np.polyfit(xz, y, 1)
            r2 = float(np.corrcoef(xz, y)[0, 1] ** 2)
            # non-overlapping subsample (every h days, offset 0)
            xs, ys = xz[::h], y[::h]
            if len(xs) > 3 and xs.std() > 0:
                s_no = float(np.polyfit((xs - xs.mean()) / xs.std(), ys, 1)[0])
                n_no = int(len(xs))
            else:
                s_no, n_no = float("nan"), int(len(xs))
            boot = block_bootstrap_slope(x, y)
            sig = (boot["slope_lo5"] > 0) or (boot["slope_hi95"] < 0)
            out.append({"horizon": label, "predictor": name, "n": int(m.sum()),
                        "slope_std": float(slope), "r2": r2,
                        "slope_nonoverlap": s_no, "n_nonoverlap": n_no,
                        **boot, "boot_ci_excludes_zero": bool(sig)})
    return out


def quartile_events(level: pd.Series, q_lo: float, q_hi: float) -> dict:
    """Fresh entries into bottom/top quartile, de-clustered."""
    ev = {"washout_entry": [], "strength_entry": []}
    lo, hi = level.quantile(0.25), level.quantile(0.75)
    last = {"washout_entry": -10**9, "strength_entry": -10**9}
    vals = level.to_numpy()
    for i in range(1, len(vals)):
        if vals[i] < lo <= vals[i - 1] and i - last["washout_entry"] > DECLUSTER_DAYS:
            ev["washout_entry"].append(i)
            last["washout_entry"] = i
        if vals[i] > hi >= vals[i - 1] and i - last["strength_entry"] > DECLUSTER_DAYS:
            ev["strength_entry"].append(i)
            last["strength_entry"] = i
    return {"lo": float(lo), "hi": float(hi), "events": ev}


def h2_level_contrast(df: pd.DataFrame, study: dict) -> dict:
    """Level-conditioned forward returns vs the Phase 0 thrust study."""
    qe = quartile_events(df["level"], 0.25, 0.75)
    base = unconditional_baseline(df["spx"], n_boot=N_BOOT, block=BLOCK, seed=SEED)
    rows = []
    for kind, idxs in qe["events"].items():
        # one-day lag guard: forward window starts the day after the event
        entry_pos = [i + 1 for i in idxs if i + 1 < len(df)]
        dates = df.index[entry_pos]
        for label, h in HORIZONS.items():
            fwd = forward_returns(df["spx"], h)
            vals = fwd.loc[dates].dropna()
            b = base[base["horizon"] == label].iloc[0]
            rows.append({
                "condition": kind, "horizon": label, "n": int(len(vals)),
                "win_rate": float((vals > 0).mean()) if len(vals) else float("nan"),
                "median_ret": float(vals.median()) if len(vals) else float("nan"),
                "base_win_rate": float(b["base_win_rate"]),
                "base_win_hi": float(b["base_win_hi"]),
                "base_median_ret": float(b["base_median_ret"]),
                "win_lift": float((vals > 0).mean() - b["base_win_rate"]) if len(vals) else float("nan"),
                "win_beyond_noise": bool(len(vals) and (vals > 0).mean() > b["base_win_hi"]),
            })
    return {"quartiles": {"lo": qe["lo"], "hi": qe["hi"]},
            "n_events": {k: len(v) for k, v in qe["events"].items()},
            "event_dates": {k: [str(df.index[i].date()) for i in v]
                            for k, v in qe["events"].items()},
            "level_conditional": rows,
            "thrust_study_reused": {  # verbatim from Phase 0; not recomputed
                "window": study["window"],
                "conditional": study["conditional"],
                "baseline": study["baseline"]}}


def h3_narrowness(thresholds=(0.0, 2.0, 5.0)) -> dict:
    """Mega-cap-led months (SPY minus RSP trailing 12m TR) vs forward 12m."""
    import yfinance as yf

    def closes(sym):
        d = yf.download(sym, period="max", progress=False, auto_adjust=True,
                        threads=False)
        c = d["Close"][sym] if hasattr(d.columns, "levels") else d["Close"]
        return c.dropna()

    spy, rsp = closes("SPY"), closes("RSP")
    df = pd.concat([spy.rename("spy"), rsp.rename("rsp")], axis=1).dropna()
    m = df.resample("ME").last()
    t12_spy = m["spy"] / m["spy"].shift(12) - 1
    t12_rsp = m["rsp"] / m["rsp"].shift(12) - 1
    diff = (t12_spy - t12_rsp) * 100
    fwd12 = m["spy"].shift(-12) / m["spy"] - 1
    valid = diff.notna() & fwd12.notna()
    uncond = float((fwd12[valid] > 0).mean())
    out = {"window": [str(m.index[valid][0].date()), str(m.index[valid][-1].date())],
           "n_months": int(valid.sum()), "unconditional_pos_share": uncond,
           "thresholds": []}
    for th in thresholds:
        flag = valid & (diff > th)
        pos = float((fwd12[flag] > 0).mean()) if flag.any() else float("nan")
        # contiguous flagged episodes with the episode-average forward return
        episodes, cur = [], None
        for dt in m.index[valid]:
            if flag.loc[dt]:
                if cur is None:
                    cur = {"start": dt, "end": dt, "rets": []}
                cur["end"] = dt
                cur["rets"].append(float(fwd12.loc[dt]))
            elif cur is not None:
                episodes.append(cur)
                cur = None
        if cur is not None:
            episodes.append(cur)
        out["thresholds"].append({
            "threshold_ppt": th, "n_flagged_months": int(flag.sum()),
            "subsequent_12m_pos_share": pos,
            "independent_years_approx": round(int(flag.sum()) / 12, 1),
            "episodes": [{"start": str(e["start"].date()), "end": str(e["end"].date()),
                          "months": len(e["rets"]),
                          "mean_fwd12": round(float(np.mean(e["rets"])), 4),
                          "share_pos": round(float(np.mean([r > 0 for r in e["rets"]])), 3)}
                         for e in episodes]})
    return out


def main():
    df = load_joint_frame()
    s = json.loads(BTS_SIGNALS.read_text(encoding="utf-8"))
    print(f"Joint frame: {len(df)} days {df.index[0].date()} -> {df.index[-1].date()}")

    h1 = h1_regressions(df)
    h2 = h2_level_contrast(df, s["study"])
    h3 = h3_narrowness()

    results = {"spec": "KICKOFF_ws4-breadth-stresstest.md",
               "generated": "2026-07-03",
               "inputs": {"bts_signals_generated_utc": s.get("generated_utc"),
                          "breadth_csp1": str(BREADTH_CSP1),
                          "joint_days": len(df),
                          "joint_window": [str(df.index[0].date()), str(df.index[-1].date())]},
               "h1_level_vs_change": h1,
               "h2_level_quartile_contrast": h2,
               "h3_narrowness_replication": h3}
    OUT_JSON.parent.mkdir(exist_ok=True)
    OUT_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("\n== H1: standardised slopes (fwd return per 1sd of predictor) ==")
    for r in h1:
        print(f"  {r['horizon']:>3} {r['predictor']:<10} slope={r['slope_std']:+.4f} "
              f"r2={r['r2']:.3f} boot90=[{r['slope_lo5']:+.4f},{r['slope_hi95']:+.4f}] "
              f"{'SIG' if r['boot_ci_excludes_zero'] else 'ns '} n={r['n']}")
    print("\n== H2: level-quartile events vs baseline ==")
    print(f"  quartiles lo={h2['quartiles']['lo']:.3f} hi={h2['quartiles']['hi']:.3f} "
          f"events={h2['n_events']}")
    for r in h2["level_conditional"]:
        if r["horizon"] in ("1m", "6m", "12m"):
            print(f"  {r['condition']:<15} {r['horizon']:>3} n={r['n']:<3} "
                  f"win={r['win_rate']:.2f} base={r['base_win_rate']:.2f} "
                  f"lift={r['win_lift']:+.2f} beyond_noise={r['win_beyond_noise']}")
    print("\n== H3: mega-cap-led months -> subsequent 12m SPY ==")
    print(f"  window {h3['window']} n={h3['n_months']} uncond_pos={h3['unconditional_pos_share']:.2f}")
    for t in h3["thresholds"]:
        print(f"  >+{t['threshold_ppt']:.0f}ppt: n={t['n_flagged_months']} "
              f"pos_share={t['subsequent_12m_pos_share']:.2f} "
              f"(~{t['independent_years_approx']}y indep) episodes={len(t['episodes'])}")
    print(f"\nWrote {OUT_JSON}")


if __name__ == "__main__":
    main()
