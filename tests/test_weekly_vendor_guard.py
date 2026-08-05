"""Unit tests for the weekly vendor guard's pure comparators (no NDU)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import compute_breadth as cb  # noqa: E402
from weekly_vendor_guard import (deemer_flags, flag_mismatches,  # noqa: E402
                                 one_sided_events, zweig_line,
                                 events_from_flags)


def _idx(n):
    return pd.bdate_range("2024-01-02", periods=n)


def test_deemer_flags_match_manual_ratio_of_sums():
    idx = _idx(30)
    adv = pd.Series(300.0, index=idx)
    dec = pd.Series(150.0, index=idx)  # 10d ratio-of-sums = 2.0 > 1.90
    f = deemer_flags(adv, dec)
    assert not f.iloc[: cb.AD_RATIO_WINDOW - 1].any()  # burn-in never flags
    assert f.iloc[cb.AD_RATIO_WINDOW:].all()


def test_zweig_line_is_ema_not_sma():
    idx = _idx(60)
    rng = np.random.default_rng(7)
    adv = pd.Series(rng.uniform(100, 400, len(idx)), index=idx)
    dec = pd.Series(rng.uniform(100, 400, len(idx)), index=idx)
    z = zweig_line(adv, dec)
    ratio = adv / (adv + dec)
    manual_ema = ratio.ewm(span=cb.ZWEIG_WINDOW, adjust=False).mean()
    sma = ratio.rolling(cb.ZWEIG_WINDOW).mean()
    assert float((z - manual_ema).abs().max()) < 1e-12
    assert float((z.dropna() - sma.reindex(z.index)).abs().max()) > 1e-4


def test_flag_mismatch_only_reports_recent_window():
    idx = _idx(40)
    a = pd.Series(False, index=idx)
    b = pd.Series(False, index=idx)
    b.iloc[5] = True    # old mismatch — outside last 10
    b.iloc[-2] = True   # recent mismatch — must be caught
    bad = flag_mismatches(a, b, last_n=10)
    assert bad == [str(idx[-2].date())]


def test_one_sided_events_pending_edge_not_alerted():
    idx = _idx(50)
    matched_a, matched_b = idx[10], idx[12]        # within +/-5 td: matched
    lone_old = idx[25]                             # one-sided: alert
    lone_edge = idx[-2]                            # within 5 td of end: pending
    res = one_sided_events([matched_a, lone_old, lone_edge],
                           [matched_b], idx)
    sides = {(e["side"], e["date"]) for e in res["one_sided"]}
    assert ("self", str(lone_old.date())) in sides
    assert all(e["date"] != str(lone_edge.date())
               for e in res["one_sided"])
    assert any(e["date"] == str(lone_edge.date())
               for e in res["pending"])


def test_events_from_flags_takes_episode_starts_only():
    idx = _idx(10)
    f = pd.Series([False, True, True, False, True, False, False, True,
                   True, True], index=idx)
    ev = events_from_flags(f)
    assert ev == [idx[1], idx[4], idx[7]]
