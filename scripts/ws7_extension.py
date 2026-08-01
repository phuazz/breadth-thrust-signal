"""WS7 — Norgate point-in-time history extension: the pre-registered run.

Executes the tests fixed in ``C:\\dev\\KICKOFF_ws7-norgate-history-extension.md``
(sign-off 2026-08-01). Nothing here tunes a parameter; every threshold, window
and band was frozen before this file existed.

  H1   held-out out-of-sample test of the frozen Phase 0 spec, 1990 -> 2017
  H1b  conviction monotonicity, pre-registered as a falsification test
  H2   pooled full-window estimate (reported after H1, not as confirmation)
  H3   anchor validation over the extended window
  H3b  the 1990-2003 silent-period negative test on our own implementation
  H4   overlap reconciliation against the filed Phase 0 record

Run:  python scripts/ws7_extension.py [--refresh]
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
import forward_returns as fr  # noqa: E402
import norgate_provider as npv  # noqa: E402

log = logging.getLogger("ws7")

OUT = ROOT / "reviews" / "2026-08-01_ws7_results.json"
FILED = ROOT / "data" / "signals.json"

# --- pre-registered windows ------------------------------------------------
HELD_OUT_END = pd.Timestamp("2017-12-31")     # H1: never looked at before
FILED_START = pd.Timestamp("2018-01-08")      # H4: the filed Phase 0 window
FILED_END = pd.Timestamp("2026-05-29")
SILENT_START = pd.Timestamp("1990-12-28")     # H3b: literature reports no ZBT
SILENT_END = pd.Timestamp("2003-12-31")       #      between Aug 1984 and Mar 2009

# --- pre-registered anchors (Aspray, Forbes, 2023-04-09; see spec section 3) -
# Month-only anchors are matched against the whole calendar month. No anchor is
# invented to finer precision than its source gives.
ANCHORS_MONTH = [
    ("2004-05", "contested — omitted by a Morris list that could not be verified"),
    ("2009-03", "corroborated"),
    ("2011-10", "corroborated"),
    ("2013-10", "corroborated"),
    ("2015-10", "contested — omitted by the same Morris list"),
]
ANCHORS_DAY = [
    ("2019-01-10", "Aspray"),
    ("2019-01-04", "existing repo anchor; reported separately, never merged"),
    ("2023-11-03", "existing repo anchor"),
]
ANCHOR_DAY_WINDOW = 5     # calendar days, as validate_d1.py already uses
DECLUSTER_DAYS = 21       # H3b episode de-duplication, the WS4 convention


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------


def build(refresh: bool):
    root = npv.default_cache_root()
    r = npv.readiness()
    if not r.ok:
        raise SystemExit(f"Norgate not ready: {r.detail}")
    log.info("NDU ready: %s", r.detail.get("US Equities"))

    syms = npv.resolve_universe()
    npv.assert_no_base_ticker_collision(syms)

    if refresh:
        npv.refresh(root, syms + [npv.BENCHMARK])
    npv.assert_basis_integrity(root, syms)
    stale = npv.check_staleness(root, syms)

    close, volume = npv.build_panel(root, syms)
    mask = npv.membership_mask(syms, close.index)
    panels = cb.build_panels(close.where(mask), volume.where(mask))
    comp = cb.compute_composite(panels)
    spx = npv.benchmark_series(root).reindex(comp.index).ffill()

    log.info(
        "panel %s -> %s, %d days, %d data_ok, %d burn-in excluded",
        comp.index.min().date(), comp.index.max().date(), len(comp),
        int(comp["data_ok"].sum()), int(comp["burn_in"].sum()),
    )
    return comp, spx, panels, mask, stale


# ---------------------------------------------------------------------------
# Study over an arbitrary window (period-matched, exactly as Phase 0)
# ---------------------------------------------------------------------------


def study(comp: pd.DataFrame, spx: pd.Series, lo=None, hi=None) -> dict:
    """Conditional table + bootstrap baseline + lift, both restricted to the
    valid-breadth window so the lift is period-matched and not measured against
    a different era."""
    ok = comp.index[comp["data_ok"]]
    if len(ok) == 0:
        return {"error": "no valid-breadth days"}
    w_lo = max(ok.min(), pd.Timestamp(lo)) if lo is not None else ok.min()
    w_hi = min(ok.max(), pd.Timestamp(hi)) if hi is not None else ok.max()

    c = comp.loc[(comp.index >= w_lo) & (comp.index <= w_hi)]
    s = spx.loc[(spx.index >= w_lo) & (spx.index <= w_hi)]

    cond = fr.conditional_table(c, s, thresholds=(1, 2, 3, 4), events_only=True)
    base = fr.unconditional_baseline(s)
    lift = fr.lift_table(cond, base)

    # Spec section 4.3: report distinct episodes alongside every raw event
    # count. Thrusts cluster after bear markets, so n is not a count of
    # independent observations and a binomial SE computed on it overstates
    # precision exactly where the study wants to claim it.
    score_lag = c["n_dimensions"].shift(1)
    ev_lag = c["event"].astype(bool).shift(1).fillna(False)
    clusters = {}
    for thr in (1, 2, 3, 4):
        sel = c.index[ev_lag & (score_lag >= thr)]
        clusters[thr] = cluster_count(sel)
    lift["clusters"] = lift["threshold"].map(clusters)

    return {
        "window": {
            "start": str(w_lo.date()),
            "end": str(w_hi.date()),
            "trading_days": int(len(s)),
            "events": int(c["event"].astype(bool).sum()),
        },
        "clusters_by_threshold": {int(k): int(v) for k, v in clusters.items()},
        "lift": lift.to_dict(orient="records"),
    }


def _row(res: dict, thr: int, hz: str) -> dict | None:
    for r in res.get("lift", []):
        if r["threshold"] == thr and r["horizon"] == hz:
            return r
    return None


def decision(res: dict) -> dict:
    """The pre-registered H1 rule: score >= 3, 6-month horizon. BOTH legs must
    clear the 95th percentile of their bootstrap band."""
    r = _row(res, 3, "6m")
    if r is None:
        return {"verdict": "NO DATA"}
    win_pass = bool(r["win_beyond_noise"])
    med_pass = bool(r["ret_beyond_noise"])
    clusters = int(r.get("clusters", 0))
    out = {
        "n": int(r["n"]), "clusters": clusters,
        "win_rate": r["win_rate"], "base_win_hi": r["base_win_hi"],
        "win_leg": "PASS" if win_pass else "FAIL",
        "median_ret": r["median_ret"], "base_ret_hi": r["base_ret_hi"],
        "median_leg": "PASS" if med_pass else "FAIL",
        "verdict": "PASS" if (win_pass and med_pass) else "FAIL",
    }
    # Spec section 4.3: no beyond-noise call on single-digit cluster counts,
    # whatever the raw n.
    if clusters < 10 and (win_pass or med_pass):
        out["cluster_caveat"] = (
            f"{clusters} distinct episodes — below the pre-registered "
            f"double-digit floor, so any beyond-noise leg here is reported "
            f"but NOT treated as established"
        )
    return out


def monotonicity(res: dict, hz: str = "6m") -> dict:
    """H1b. Spearman rank correlation between conviction threshold and win-rate
    lift. Phase 0 found this running backwards; a negative value here means the
    inversion reproduces out of sample."""
    rows = [_row(res, t, hz) for t in (1, 2, 3, 4)]
    rows = [r for r in rows if r is not None and r["n"] > 0]
    if len(rows) < 3:
        return {"note": "too few populated thresholds", "n_thresholds": len(rows)}
    thr = pd.Series([r["threshold"] for r in rows], dtype=float)
    lifts = pd.Series([r["win_lift"] for r in rows], dtype=float)
    rho = float(thr.corr(lifts, method="spearman"))
    return {
        "horizon": hz,
        "thresholds": [int(r["threshold"]) for r in rows],
        "n_events": [int(r["n"]) for r in rows],
        "clusters": [int(r.get("clusters", 0)) for r in rows],
        "win_lift": [float(r["win_lift"]) for r in rows],
        "spearman_rho": rho,
        "reading": (
            "inversion reproduces (lift falls as conviction rises)" if rho < 0
            else "inversion does NOT reproduce" if rho > 0
            else "flat"
        ),
    }


def cluster_count(dates: pd.DatetimeIndex, gap_days: int = 63) -> int:
    """Distinct episodes, not raw events. Spec section 4.3: a win-rate lift is
    not called beyond-noise on single-digit cluster counts whatever the raw n."""
    if len(dates) == 0:
        return 0
    d = pd.DatetimeIndex(sorted(dates))
    return 1 + int((d.to_series().diff().dt.days.fillna(0) > gap_days).sum())


# ---------------------------------------------------------------------------
# H3 / H3b — anchors
# ---------------------------------------------------------------------------


def anchors(comp: pd.DataFrame, panels) -> dict:
    d1 = cb.d1_advance_decline(panels)
    ok = comp["data_ok"]
    out = {"month_anchors": [], "day_anchors": [], "fire_counts": {}}

    for col in ("zweig", "mcclellan", "ad_ratio_deemer", "d1"):
        out["fire_counts"][col] = int((d1[col] & ok).sum())

    fires = {c: d1.index[d1[c] & ok] for c in ("zweig", "mcclellan", "ad_ratio_deemer", "d1")}

    for month, note in ANCHORS_MONTH:
        per = pd.Period(month, freq="M")
        hits = {
            c: [str(d.date()) for d in f
                if d.to_period("M") == per]
            for c, f in fires.items()
        }
        hits = {c: v for c, v in hits.items() if v}
        out["month_anchors"].append({
            "anchor": month, "source_note": note,
            "match": bool(hits), "hits": hits,
        })

    for day, note in ANCHORS_DAY:
        a = pd.Timestamp(day)
        lo, hi = a - pd.Timedelta(days=ANCHOR_DAY_WINDOW), a + pd.Timedelta(days=ANCHOR_DAY_WINDOW)
        hits = {c: [str(d.date()) for d in f if lo <= d <= hi] for c, f in fires.items()}
        hits = {c: v for c, v in hits.items() if v}
        out["day_anchors"].append({
            "anchor": day, "source_note": note,
            "match": bool(hits), "hits": hits,
        })

    # H3b — the silent period.
    z = fires["zweig"]
    silent = pd.DatetimeIndex([d for d in z if SILENT_START <= d <= SILENT_END])
    episodes = cluster_count(silent, gap_days=DECLUSTER_DAYS)
    out["h3b_silent_period"] = {
        "window": [str(SILENT_START.date()), str(SILENT_END.date())],
        "raw_zweig_fire_days": int(len(silent)),
        "declustered_episodes": episodes,
        "dates": [str(d.date()) for d in silent],
        "expectation": "single digits after de-duplication",
        "verdict": (
            "CONSISTENT with the literature's silent period" if episodes < 10
            else "LOOSER than canonical — our EMA(10) / large-cap proxy fires "
                 "where the literature reports silence; a finding about the "
                 "implementation, not the market"
        ),
    }
    return out


# ---------------------------------------------------------------------------
# H4 — reconciliation against the filed record
# ---------------------------------------------------------------------------


def filed_record() -> pd.DataFrame:
    p = json.loads(FILED.read_text(encoding="utf-8"))
    t = p["timeline"]
    return pd.DataFrame(
        {k: t[k] for k in ("spx", "n_dimensions", "d1_on", "d2_on", "d3_on", "d4_on", "event")},
        index=pd.to_datetime(t["dates"]),
    )


def reconcile(comp: pd.DataFrame, spx: pd.Series) -> dict:
    """Compare the filed Phase 0 window three ways, so the burn-in effect and
    the data-layer effect are decomposed rather than conflated."""
    filed = filed_record()
    fspx = filed["spx"].astype(float)

    # (a) filed, as published
    a = fr.lift_table(
        fr.conditional_table(filed, fspx, events_only=True),
        fr.unconditional_baseline(fspx),
    )
    # (b) filed, burn-in events removed (the defect found at WS7 build)
    burn_end = filed.index[cb.HL_LOOKBACK - 1]
    filed_clean = filed.copy()
    filed_clean.loc[filed_clean.index <= burn_end, "event"] = False
    b = fr.lift_table(
        fr.conditional_table(filed_clean, fspx, events_only=True),
        fr.unconditional_baseline(fspx),
    )
    # (c) Norgate layer, same calendar window, fully warmed by prior history
    c = study(comp, spx, FILED_START, FILED_END)

    def pick(tbl, thr, hz):
        if isinstance(tbl, dict):
            return _row(tbl, thr, hz)
        r = tbl[(tbl["threshold"] == thr) & (tbl["horizon"] == hz)]
        return r.iloc[0].to_dict() if len(r) else None

    rows = []
    for thr in (1, 2, 3, 4):
        for hz in ("6m", "12m"):
            ra, rb, rc = pick(a, thr, hz), pick(b, thr, hz), pick(c, thr, hz)
            if not (ra and rc):
                continue
            rows.append({
                "threshold": thr, "horizon": hz,
                "filed_n": int(ra["n"]), "filed_win": ra["win_rate"], "filed_med": ra["median_ret"],
                "filed_exburn_n": int(rb["n"]) if rb else None,
                "filed_exburn_win": rb["win_rate"] if rb else None,
                "norgate_n": int(rc["n"]), "norgate_win": rc["win_rate"], "norgate_med": rc["median_ret"],
                "burn_in_effect_pp": (rb["win_rate"] - ra["win_rate"]) * 100 if rb else None,
                "data_layer_effect_pp": (rc["win_rate"] - rb["win_rate"]) * 100 if rb else None,
                "total_win_delta_pp": (rc["win_rate"] - ra["win_rate"]) * 100,
                "total_med_delta_pp": (rc["median_ret"] - ra["median_ret"]) * 100,
            })
    tbl = pd.DataFrame(rows)

    # Pre-registered erratum trigger.
    trig = tbl[(tbl["total_win_delta_pp"].abs() > 2.0)
               | (tbl["total_med_delta_pp"].abs() > 1.0)
               | ((tbl["norgate_n"] - tbl["filed_n"]).abs() > 2)]
    return {
        "burn_in_boundary": str(burn_end.date()),
        "rows": tbl.to_dict(orient="records"),
        "erratum_triggered": bool(len(trig) > 0),
        "erratum_rows": trig.to_dict(orient="records"),
        "rule": ("erratum if any headline figure moves >2pp on a win rate, "
                 ">1pp on a median, or event count differs by >2"),
    }


# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh", action="store_true", help="re-pull the Norgate cache")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    comp, spx, panels, mask, stale = build(args.refresh)

    log.info("\n--- H1 held-out out-of-sample 1990 -> 2017 ---")
    h1 = study(comp, spx, None, HELD_OUT_END)
    h1_dec = decision(h1)
    h1_mono = monotonicity(h1)
    ev_ho = comp.loc[(comp.index <= HELD_OUT_END) & comp["data_ok"] & comp["event"].astype(bool)].index
    h1["clusters"] = cluster_count(ev_ho)
    log.info("  window %s, %d events, %d clusters",
             h1["window"], h1["window"]["events"], h1["clusters"])
    log.info("  DECISION (>=3, 6m): %s", h1_dec)
    log.info("  H1b monotonicity: %s", h1_mono)

    log.info("\n--- H2 pooled full window ---")
    h2 = study(comp, spx)
    ev_all = comp.loc[comp["data_ok"] & comp["event"].astype(bool)].index
    h2["clusters"] = cluster_count(ev_all)
    h2_dec, h2_mono = decision(h2), monotonicity(h2)
    log.info("  window %s, %d events, %d clusters",
             h2["window"], h2["window"]["events"], h2["clusters"])
    log.info("  pooled (>=3, 6m): %s", h2_dec)
    log.info("  pooled monotonicity: %s", h2_mono)

    log.info("\n--- H3 / H3b anchors ---")
    anc = anchors(comp, panels)
    for a in anc["month_anchors"] + anc["day_anchors"]:
        log.info("  %s: %s", a["anchor"], "MATCH" if a["match"] else "MISS")
    log.info("  H3b: %s", anc["h3b_silent_period"]["verdict"])
    log.info("       %d raw fire-days, %d episodes",
             anc["h3b_silent_period"]["raw_zweig_fire_days"],
             anc["h3b_silent_period"]["declustered_episodes"])

    log.info("\n--- H4 reconciliation vs filed Phase 0 ---")
    h4 = reconcile(comp, spx)
    log.info("  erratum triggered: %s", h4["erratum_triggered"])

    payload = {
        "workstream": "WS7 — Norgate point-in-time history extension",
        "spec": "C:/dev/KICKOFF_ws7-norgate-history-extension.md",
        "run_utc": pd.Timestamp.now("UTC").isoformat(),
        "data_layer": {
            "source": "Norgate Data, S&P 500 Current & Past",
            "symbols": int(mask.shape[1]),
            "panel_days": int(len(comp)),
            "data_ok_days": int(comp["data_ok"].sum()),
            "burn_in_days_excluded": int(comp["burn_in"].sum()),
            "members_per_day": {
                "min": int(mask.sum(axis=1).min()),
                "median": int(mask.sum(axis=1).median()),
                "max": int(mask.sum(axis=1).max()),
            },
            "staleness": stale,
            "survivorship_bias": False,
        },
        "h1_held_out": h1, "h1_decision": h1_dec, "h1b_monotonicity": h1_mono,
        "h2_pooled": h2, "h2_decision": h2_dec, "h2b_monotonicity": h2_mono,
        "h3_anchors": anc,
        "h4_reconciliation": h4,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    log.info("\nWrote %s", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
