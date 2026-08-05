"""Weekly vendor gauge guard — ALERT-ONLY cross-check of the deployed
self-computed breadth panel against Norgate vendor counts. Built from the
Tier-2 #4 audit (reviews/2026-08-05_gauge-vendor-crosscheck.md, "Proposal");
owner approved 2026-08-05. This layer makes NO decisions and changes NO
deployed behaviour: it recomputes three guard series from vendor inputs and
raises an alert when they disagree with the panel — the guard layer the
house rule requires for unattended pipelines.

Guard constructions (per the audit's verdicts):
  G1  Deemer 10d A/D ratio > 1.90 day-flags   from #SPXADV / #SPXDEC
  G2  %-above-50d-MA 25→75 thrust events      from #SPX%MA50
  G3  Zweig line = EMA10 of adv/(adv+dec)     from #SPXADV / #SPXDEC
      (NEVER the packaged #SPXZWBT — it is an SMA10; audit P1b)
Excluded from alerting per the audit: McClellan (ratio-adjusted vendor
units) and NH/NL (price-vs-TR basis) — loose agreement only, alerts would
false-positive.

Alert calibration (alert-only; revisit at the first false positive):
  - G1: any day-flag mismatch in the last 10 trading days.
  - G2: any thrust event on exactly one side within the trailing 90
    trading days, matched at ±5 trading days; events within 5 days of the
    panel end are PENDING, not alerted (the other side may still fire).
  - G3: |self − vendor| > 0.02 on any of the last 10 trading days
    (audit context: level corr 0.9987; 0.02 ≈ 4× the typical gap).
Staleness: comparisons only run when BOTH sides' actual last bars are
within 9 calendar days (actual-last-bar rule — never last_quoted_date).

Exit codes: 0 = ok · 1 = stale/skip (no comparison) · 2 = ALERT.
The scheduled wrapper appends stdout to data_local/guard.log; a snapshot
of derived statistics goes to data_local/guard_last.json (git-ignored;
this repo is PUBLIC and vendor values never enter it — the log and
snapshot carry derived flags, dates and diffs only).

Run:    python scripts/weekly_vendor_guard.py [--no-refresh]
Task:   "breadth-thrust-signal weekly vendor guard", Sat 08:00 SGT.
"""
from __future__ import annotations

import argparse
import datetime as dt  # Python datetime: months are 1-indexed
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_LOCAL = ROOT / "data_local"
sys.path.insert(0, str(ROOT / "scripts"))

import compute_breadth as cb  # noqa: E402
import norgate_provider as npv  # noqa: E402

MATCH_TDAYS = 5
ALERT_LAST_N = 10
EVENT_WINDOW_TDAYS = 90
ZWEIG_TOL = 0.02
STALE_CAL_DAYS = 9


# ---------------------------------------------------------------------------
# Pure comparators (unit-tested; no I/O, no NDU)
# ---------------------------------------------------------------------------

def deemer_flags(adv: pd.Series, dec: pd.Series) -> pd.Series:
    ratio = (adv.rolling(cb.AD_RATIO_WINDOW,
                         min_periods=cb.AD_RATIO_WINDOW).sum()
             / dec.rolling(cb.AD_RATIO_WINDOW,
                           min_periods=cb.AD_RATIO_WINDOW).sum()
             .replace(0, np.nan))
    return (ratio > cb.AD_RATIO_THRESHOLD).fillna(False)


def zweig_line(adv: pd.Series, dec: pd.Series) -> pd.Series:
    return (adv / (adv + dec).replace(0, np.nan)).ewm(
        span=cb.ZWEIG_WINDOW, adjust=False).mean()


def flag_mismatches(self_f: pd.Series, vend_f: pd.Series,
                    last_n: int) -> list[str]:
    j = pd.concat([self_f.rename("s"), vend_f.rename("v")], axis=1,
                  join="inner").dropna().tail(last_n)
    bad = j.index[j["s"].astype(bool) != j["v"].astype(bool)]
    return [str(d.date()) for d in bad]


def one_sided_events(self_ev: list[pd.Timestamp],
                     vend_ev: list[pd.Timestamp],
                     idx: pd.DatetimeIndex,
                     match_td: int = MATCH_TDAYS) -> dict:
    """Match events across sides; events within match_td of the index end
    are PENDING (excluded from the one-sided alert)."""
    pos = {d: i for i, d in enumerate(idx)}
    end = len(idx) - 1
    used = set()
    one_sided, pending = [], []

    def classify(d: pd.Timestamp, other: list[pd.Timestamp],
                 other_used: set, side: str):
        best, best_d = None, None
        for k, o in enumerate(other):
            if k in other_used or d not in pos or o not in pos:
                continue
            dd = abs(pos[o] - pos[d])
            if best is None or dd < best_d:
                best, best_d = k, dd
        if best is not None and best_d <= match_td:
            other_used.add(best)
            return
        if d in pos and end - pos[d] <= match_td:
            pending.append({"side": side, "date": str(d.date())})
        else:
            one_sided.append({"side": side, "date": str(d.date())})

    for d in self_ev:
        classify(d, vend_ev, used, "self")
    vend_used_by_self = used
    used2: set = set()
    for k, o in enumerate(vend_ev):
        if k in vend_used_by_self:
            continue
        classify(o, self_ev, used2, "vendor")
    return {"one_sided": one_sided, "pending": pending}


def events_from_flags(flags: pd.Series) -> list[pd.Timestamp]:
    f = flags.fillna(False).astype(bool)
    starts = f & ~f.shift(1, fill_value=False)
    return list(f.index[starts])


# ---------------------------------------------------------------------------

def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-refresh", action="store_true",
                    help="skip the store refresh (manual fast run)")
    args = ap.parse_args()
    today = dt.date.today()
    print(f"[guard] run {today.isoformat()}")

    r = npv.readiness()
    if not r.ok:
        print(f"[guard] SKIP: Norgate not ready — {r.detail}")
        return 1
    root = npv.default_cache_root()
    syms = npv.resolve_universe()
    npv.assert_no_base_ticker_collision(syms)
    if not args.no_refresh:
        npv.refresh(root, syms)
    npv.assert_basis_integrity(root, syms)

    close, volume = npv.build_panel(root, syms)
    mask = npv.membership_mask(syms, close.index)
    panels = cb.build_panels(close.where(mask), volume.where(mask))
    panel_last = close.index[-1].date()

    import norgatedata as nd

    def vendor(sym: str) -> pd.Series:
        df = nd.price_timeseries(
            sym,
            stock_price_adjustment_setting=nd.StockPriceAdjustmentType.TOTALRETURN,
            padding_setting=nd.PaddingType.NONE,
            timeseriesformat="pandas-dataframe",
        )
        return df["Close"].rename(sym)

    v_adv, v_dec, v_ma50 = (vendor("#SPXADV"), vendor("#SPXDEC"),
                            vendor("#SPX%MA50"))
    vendor_last = v_adv.index[-1].date()

    if (today - panel_last).days > STALE_CAL_DAYS or \
            (today - vendor_last).days > STALE_CAL_DAYS:
        print(f"[guard] SKIP stale: panel last {panel_last}, vendor last "
              f"{vendor_last} (cap {STALE_CAL_DAYS} calendar days)")
        return 1

    # G1 — Deemer flags
    g1_self = deemer_flags(panels.advances, panels.declines)
    g1_vend = deemer_flags(v_adv, v_dec)
    g1_bad = flag_mismatches(g1_self, g1_vend, ALERT_LAST_N)

    # G2 — %MA50 thrust events over the trailing window
    pct_self = panels.pct_above_50dma
    pct_self = pct_self / (100.0 if pct_self.max() > 1.5 else 1.0)
    pct_vend = v_ma50 / (100.0 if v_ma50.max() > 1.5 else 1.0)
    lo = cb.PCT50_LOW / 100.0 if cb.PCT50_LOW > 1.5 else cb.PCT50_LOW
    hi = cb.PCT50_HIGH / 100.0 if cb.PCT50_HIGH > 1.5 else cb.PCT50_HIGH
    idx = pct_self.dropna().index.intersection(pct_vend.dropna().index)
    idx = idx[-EVENT_WINDOW_TDAYS:]
    e_self = events_from_flags(cb._crossed_up_within(
        pct_self.reindex(idx), lo, hi, cb.PCT50_THRUST_WINDOW))
    e_vend = events_from_flags(cb._crossed_up_within(
        pct_vend.reindex(idx), lo, hi, cb.PCT50_THRUST_WINDOW))
    g2 = one_sided_events(e_self, e_vend, idx)

    # G3 — Zweig line (from counts; never packaged #SPXZWBT)
    z_self = zweig_line(panels.advances, panels.declines)
    z_vend = zweig_line(v_adv, v_dec)
    zj = pd.concat([z_self.rename("s"), z_vend.rename("v")], axis=1,
                   join="inner").dropna().tail(ALERT_LAST_N)
    g3_bad = [str(d.date()) for d in
              zj.index[(zj["s"] - zj["v"]).abs() > ZWEIG_TOL]]

    alerts = []
    if g1_bad:
        alerts.append(f"G1 Deemer day-flag mismatch on {g1_bad}")
    if g2["one_sided"]:
        alerts.append(f"G2 one-sided %MA50 thrust: {g2['one_sided']}")
    if g3_bad:
        alerts.append(f"G3 Zweig divergence > {ZWEIG_TOL} on {g3_bad}")

    snapshot = {
        "run_date": today.isoformat(),
        "panel_last_bar": str(panel_last),
        "vendor_last_bar": str(vendor_last),
        "g1_mismatch_days": g1_bad,
        "g2_events": g2,
        "g3_divergence_days": g3_bad,
        "g3_last_abs_diff": round(float((zj["s"] - zj["v"]).abs().iloc[-1]),
                                  5) if len(zj) else None,
        "alerts": alerts,
    }
    DATA_LOCAL.mkdir(exist_ok=True)
    (DATA_LOCAL / "guard_last.json").write_text(
        json.dumps(snapshot, indent=1), encoding="utf-8")

    if alerts:
        for a in alerts:
            print(f"[guard] ALERT: {a}")
        return 2
    print(f"[guard] ok — panel {panel_last} vs vendor {vendor_last}; "
          f"G1 clean last {ALERT_LAST_N}d, G2 {len(g2['pending'])} pending "
          f"0 one-sided, G3 max|diff| "
          f"{float((zj['s'] - zj['v']).abs().max()):.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
