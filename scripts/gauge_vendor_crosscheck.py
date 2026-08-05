"""Tier-2 #4 — vendor-series cross-check audit. REVIEW-AND-PROPOSE: this
script changes NOTHING deployed; it measures whether Norgate's precomputed
S&P 500 internals can serve as a GUARD (cross-check alarm) for the WS7
self-computed panel. The WS7 layer itself STANDS — definition-controlled,
point-in-time membership, survivorship-free — and is not up for
replacement here (that would surrender exactly the control WS7 bought).

Pairs (self-computed vs vendor):
  P1  Zweig line: EMA(10) of adv/(adv+dec)          vs  #SPXZWBT
  P2  McClellan osc: EMA19−EMA39 of RAW net adv     vs  #SPXMCOSC
      (vendor may be ratio-adjusted — scale detected, never assumed)
  P3  daily advances / declines counts              vs  #SPXADV / #SPXDEC
      + the 10d Deemer ratio-of-sums > 1.90 day-flags derived from each
  P4  % above 50d MA                                vs  #SPX%MA50
      + the 25→75-within-15 thrust events from each
  P5  52W new highs / new lows counts               vs  #SPX52WHI / #SPX52WLO
      + the NH/(NH+NL) ratio thrust events from each
  P6  up-volume ratio: NO vendor SPX equivalent — reported as a finding.

Event detection uses the DEPLOYED machinery imported from compute_breadth
(_crossed_up_within + the frozen threshold constants) — never
re-implemented. Panel construction replicates ws7_extension.build()
line-for-line (cache root, universe, collision/basis asserts, membership
mask). Licence: vendor pulls are runtime-only; the committed output holds
statistics and event DATES only.

Three ways this audit could be silently wrong, defended:
  1. DEFINITIONAL MISMATCH PAPERED OVER AS EQUIVALENCE — each pair reports
     units, basis and a detected scale ratio; event comparisons run ONLY
     where units match (P2 events are skipped if the scale ratio says
     ratio-adjusted); nothing is rescaled toward agreement beyond the
     declared percent-vs-fraction convention.
  2. MEMBERSHIP-TIMING CONFLATION — the self panel uses the WS7
     point-in-time mask, the vendor uses official membership; differences
     are REPORTED (level + day-change correlations separately) as
     findings, not smoothed away.
  3. LOOK-ALIKE EVENTS AT DIFFERENT DATES COUNTED AS AGREEMENT — thrust
     events are matched within a ±5-trading-day window (the repo's own
     anchor convention) and unmatched events are listed by date on both
     sides, never netted.

Output: data/gauge_vendor_crosscheck.json (stats + event dates only)
Run:    python scripts/gauge_vendor_crosscheck.py
"""
from __future__ import annotations

import datetime as dt  # Python datetime: months are 1-indexed
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import compute_breadth as cb  # noqa: E402
import norgate_provider as npv  # noqa: E402

MATCH_TDAYS = 5  # repo anchor convention (validate_d1 / ws7)


def vendor(symbol: str) -> pd.Series:
    import norgatedata as nd
    df = nd.price_timeseries(
        symbol,
        stock_price_adjustment_setting=nd.StockPriceAdjustmentType.TOTALRETURN,
        padding_setting=nd.PaddingType.NONE,
        timeseriesformat="pandas-dataframe",
    )
    return df["Close"].rename(symbol)


def pair_stats(self_s: pd.Series, vend_s: pd.Series, unit_note: str) -> dict:
    j = pd.concat([self_s.rename("self"), vend_s.rename("vendor")],
                  axis=1, join="inner").dropna()
    if len(j) < 250:
        return {"n": int(len(j)), "note": "overlap too short"}
    d = j["vendor"] - j["self"]
    med_self = float(j["self"].abs().median()) or np.nan
    med_vend = float(j["vendor"].abs().median()) or np.nan
    return {
        "n": int(len(j)),
        "start": str(j.index[0].date()), "end": str(j.index[-1].date()),
        "unit_note": unit_note,
        "corr_levels": round(float(j["self"].corr(j["vendor"])), 4),
        "corr_daily_changes": round(float(
            j["self"].diff().corr(j["vendor"].diff())), 4),
        "median_signed_diff": round(float(d.median()), 4),
        "p95_abs_diff": round(float(d.abs().quantile(0.95)), 4),
        "scale_ratio_vendor_over_self": round(med_vend / med_self, 4)
        if med_self == med_self and med_self != 0 else None,
    }


def events_from_flags(flags: pd.Series) -> list[pd.Timestamp]:
    f = flags.fillna(False).astype(bool)
    starts = f & ~f.shift(1, fill_value=False)
    return list(f.index[starts])


def match_events(a: list[pd.Timestamp], b: list[pd.Timestamp],
                 idx: pd.DatetimeIndex) -> dict:
    pos = {d: i for i, d in enumerate(idx)}
    used = set()
    pairs, un_a = [], []
    for da in a:
        best, best_d = None, None
        for k, db in enumerate(b):
            if k in used or da not in pos or db not in pos:
                continue
            dd = abs(pos[db] - pos[da])
            if best is None or dd < best_d:
                best, best_d = k, dd
        if best is not None and best_d <= MATCH_TDAYS:
            used.add(best)
            pairs.append({"self": str(da.date()), "vendor":
                          str(b[best].date()), "tday_delta": int(best_d)})
        else:
            un_a.append(str(da.date()))
    un_b = [str(db.date()) for k, db in enumerate(b) if k not in used]
    return {"n_self": len(a), "n_vendor": len(b), "matched": len(pairs),
            "pairs": pairs, "unmatched_self": un_a,
            "unmatched_vendor": un_b}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    # ---- self-computed panel, exactly as ws7_extension.build() ----------
    root = npv.default_cache_root()
    r = npv.readiness()
    if not r.ok:
        raise SystemExit(f"Norgate not ready: {r.detail}")
    syms = npv.resolve_universe()
    npv.assert_no_base_ticker_collision(syms)
    npv.assert_basis_integrity(root, syms)
    close, volume = npv.build_panel(root, syms)
    mask = npv.membership_mask(syms, close.index)
    panels = cb.build_panels(close.where(mask), volume.where(mask))
    print(f"self panel: {close.index.min().date()} -> "
          f"{close.index.max().date()}")

    adv, dec = panels.advances, panels.declines
    ad_ratio_daily = adv / (adv + dec).replace(0, np.nan)
    zweig_self = ad_ratio_daily.ewm(span=cb.ZWEIG_WINDOW,
                                    adjust=False).mean()
    mcc_self = (adv.sub(dec).ewm(span=cb.MCC_FAST, adjust=False).mean()
                - adv.sub(dec).ewm(span=cb.MCC_SLOW, adjust=False).mean())
    deemer_self_ratio = (
        adv.rolling(cb.AD_RATIO_WINDOW, min_periods=cb.AD_RATIO_WINDOW).sum()
        / dec.rolling(cb.AD_RATIO_WINDOW,
                      min_periods=cb.AD_RATIO_WINDOW).sum().replace(0, np.nan))
    pct50_self = panels.pct_above_50dma
    nh_self, nl_self = panels.new_highs, panels.new_lows
    nhnl_self = nh_self / (nh_self + nl_self).replace(0, np.nan)

    # ---- vendor series ---------------------------------------------------
    v_zwbt = vendor("#SPXZWBT")
    v_mcc = vendor("#SPXMCOSC")
    v_adv = vendor("#SPXADV")
    v_dec = vendor("#SPXDEC")
    v_ma50 = vendor("#SPX%MA50")
    v_nh = vendor("#SPX52WHI")
    v_nl = vendor("#SPX52WLO")

    zwbt_scale = 100.0 if v_zwbt.max() > 1.5 else 1.0
    v_zwbt_frac = v_zwbt / zwbt_scale
    ma50_scale = 100.0 if v_ma50.max() > 1.5 else 1.0
    v_ma50_frac = v_ma50 / ma50_scale
    pct50_self_frac = pct50_self / (100.0 if pct50_self.max() > 1.5 else 1.0)

    v_deemer_ratio = (
        v_adv.rolling(cb.AD_RATIO_WINDOW, min_periods=cb.AD_RATIO_WINDOW).sum()
        / v_dec.rolling(cb.AD_RATIO_WINDOW,
                        min_periods=cb.AD_RATIO_WINDOW).sum().replace(0,
                                                                      np.nan))
    v_nhnl = v_nh / (v_nh + v_nl).replace(0, np.nan)

    out: dict = {"pairs": {}}

    # P1 Zweig
    p1 = pair_stats(zweig_self, v_zwbt_frac,
                    "EMA10 advance ratio, fraction (vendor scale "
                    f"detected /{zwbt_scale:.0f})")
    idx1 = zweig_self.dropna().index.intersection(v_zwbt_frac.dropna().index)
    e_self = events_from_flags(cb._crossed_up_within(
        zweig_self.reindex(idx1), cb.ZWEIG_LOW, cb.ZWEIG_HIGH,
        cb.ZWEIG_WINDOW))
    e_vend = events_from_flags(cb._crossed_up_within(
        v_zwbt_frac.reindex(idx1), cb.ZWEIG_LOW, cb.ZWEIG_HIGH,
        cb.ZWEIG_WINDOW))
    p1["zweig_thrust_events"] = match_events(e_self, e_vend, idx1)
    out["pairs"]["P1_zweig"] = p1

    # P1b — decompose the P1 anomaly: is packaged #SPXZWBT the EMA10 of
    # the vendor's own counts, or a different formula? Two candidates are
    # built from vendor inputs (proven ≈ self inputs in P3), so whichever
    # correlates with #SPXZWBT reveals the vendor formula, and whichever
    # correlates with the self line shows the correct guard construction.
    v_unc = vendor("#SPXUNC")
    zw_counts = (v_adv / (v_adv + v_dec).replace(0, np.nan)).ewm(
        span=cb.ZWEIG_WINDOW, adjust=False).mean()
    zw_unch = (v_adv / (v_adv + v_dec + v_unc).replace(0, np.nan)).ewm(
        span=cb.ZWEIG_WINDOW, adjust=False).mean()
    jb = pd.concat([zweig_self.rename("self"),
                    v_zwbt_frac.rename("zwbt"),
                    zw_counts.rename("from_counts"),
                    zw_unch.rename("unch_incl")], axis=1,
                   join="inner").dropna()
    out["pairs"]["P1b_zweig_decomposition"] = {
        "corr_self_vs_from_counts": round(float(
            jb["self"].corr(jb["from_counts"])), 4),
        "corr_zwbt_vs_from_counts": round(float(
            jb["zwbt"].corr(jb["from_counts"])), 4),
        "corr_zwbt_vs_unch_incl": round(float(
            jb["zwbt"].corr(jb["unch_incl"])), 4),
        "median_zwbt_minus_from_counts": round(float(
            (jb["zwbt"] - jb["from_counts"]).median()), 4),
        "median_zwbt_minus_unch_incl": round(float(
            (jb["zwbt"] - jb["unch_incl"]).median()), 4),
        "note": ("if self≈from_counts but zwbt≉from_counts, the packaged "
                 "ZWBT uses a different formula and the correct vendor "
                 "guard for the Zweig leg is EMA10 of #SPXADV/#SPXDEC, "
                 "not #SPXZWBT"),
        "resolved": ("2026-08-05 probe: #SPXZWBT correlates 1.0000 with "
                     "the 10-day SIMPLE moving average of "
                     "#SPXADV/(#SPXADV+#SPXDEC) — the vendor packages an "
                     "SMA10, not the canonical EMA10. Never adopt "
                     "#SPXZWBT for the deployed EMA-based Zweig leg; "
                     "build any vendor guard from the raw counts."),
    }

    # P2 McClellan — scale decides whether events are comparable
    p2 = pair_stats(mcc_self, v_mcc, "self RAW net-advance EMA19-EMA39; "
                    "vendor basis detected via scale ratio")
    sr = p2.get("scale_ratio_vendor_over_self")
    p2["verdict_hint"] = (
        "units comparable" if sr is not None and 0.5 <= sr <= 2.0 else
        "DEFINITIONALLY DIFFERENT (probable ratio-adjusted vendor) — "
        "level guard unusable at the deployed -50 count threshold")
    out["pairs"]["P2_mcclellan"] = p2

    # P3 advances / declines + Deemer
    out["pairs"]["P3_advances"] = pair_stats(adv, v_adv, "daily count")
    out["pairs"]["P3_declines"] = pair_stats(dec, v_dec, "daily count")
    j3 = pd.concat([deemer_self_ratio.rename("self"),
                    v_deemer_ratio.rename("vendor")], axis=1,
                   join="inner").dropna()
    flags_s = j3["self"] > cb.AD_RATIO_THRESHOLD
    flags_v = j3["vendor"] > cb.AD_RATIO_THRESHOLD
    out["pairs"]["P3_deemer_1p90"] = {
        "day_flag_agreement": round(float((flags_s == flags_v).mean()), 4),
        "episodes": match_events(events_from_flags(flags_s),
                                 events_from_flags(flags_v), j3.index),
    }

    # P4 %MA50 + thrust events
    p4 = pair_stats(pct50_self_frac, v_ma50_frac,
                    "fraction above 50d MA (vendor scale detected "
                    f"/{ma50_scale:.0f}; self TR-close basis, vendor basis "
                    "per vendor)")
    idx4 = pct50_self_frac.dropna().index.intersection(
        v_ma50_frac.dropna().index)
    lo, hi = cb.PCT50_LOW, cb.PCT50_HIGH
    lo_f = lo / 100.0 if lo > 1.5 else lo
    hi_f = hi / 100.0 if hi > 1.5 else hi
    e4s = events_from_flags(cb._crossed_up_within(
        pct50_self_frac.reindex(idx4), lo_f, hi_f, cb.PCT50_THRUST_WINDOW))
    e4v = events_from_flags(cb._crossed_up_within(
        v_ma50_frac.reindex(idx4), lo_f, hi_f, cb.PCT50_THRUST_WINDOW))
    p4["pct50_thrust_events"] = match_events(e4s, e4v, idx4)
    out["pairs"]["P4_pct_above_50dma"] = p4

    # P5 NH/NL
    out["pairs"]["P5_new_highs"] = pair_stats(
        nh_self, v_nh, "52W new-high count (self TR-close basis)")
    out["pairs"]["P5_new_lows"] = pair_stats(
        nl_self, v_nl, "52W new-low count (self TR-close basis)")
    j5 = pd.concat([nhnl_self.rename("self"), v_nhnl.rename("vendor")],
                   axis=1, join="inner").dropna()
    nlo = cb.NHNL_LOW / 100.0 if cb.NHNL_LOW > 1.5 else cb.NHNL_LOW
    nhi = cb.NHNL_HIGH / 100.0 if cb.NHNL_HIGH > 1.5 else cb.NHNL_HIGH
    e5s = events_from_flags(cb._crossed_up_within(
        j5["self"], nlo, nhi, cb.NHNL_THRUST_WINDOW))
    e5v = events_from_flags(cb._crossed_up_within(
        j5["vendor"], nlo, nhi, cb.NHNL_THRUST_WINDOW))
    out["pairs"]["P5_nhnl_ratio_events"] = match_events(e5s, e5v, j5.index)

    # P6 finding
    out["pairs"]["P6_up_volume"] = {
        "finding": "no Norgate SPX up/down-volume series (only the "
                   "McClellan Volume Oscillator) — no vendor guard "
                   "possible for D4; self-computed stands alone"}

    out["computed_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(
        timespec="seconds")
    out["scope"] = ("guard-adoption audit only; the WS7 self-computed "
                    "layer is not up for replacement")
    (ROOT / "data" / "gauge_vendor_crosscheck.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")

    for k, v in out["pairs"].items():
        if "corr_levels" in v:
            print(f"{k}: n={v['n']} corr={v['corr_levels']} "
                  f"dcorr={v['corr_daily_changes']} "
                  f"scale={v.get('scale_ratio_vendor_over_self')}")
        elif "day_flag_agreement" in v:
            ep = v["episodes"]
            print(f"{k}: day-agree={v['day_flag_agreement']} episodes "
                  f"self/vendor/matched {ep['n_self']}/{ep['n_vendor']}"
                  f"/{ep['matched']}")
    for k in ("P1_zweig", "P4_pct_above_50dma"):
        ev_key = ("zweig_thrust_events" if k == "P1_zweig"
                  else "pct50_thrust_events")
        ep = out["pairs"][k][ev_key]
        print(f"{k} events: self/vendor/matched "
              f"{ep['n_self']}/{ep['n_vendor']}/{ep['matched']}")
    ep = out["pairs"]["P5_nhnl_ratio_events"]
    print(f"P5 events: self/vendor/matched {ep['n_self']}/{ep['n_vendor']}"
          f"/{ep['matched']}")
    print("wrote data/gauge_vendor_crosscheck.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
