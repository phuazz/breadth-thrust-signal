"""Fire-path tests for the parallel-run edge comparator (pure, no NDU).

The comparator gates the live-meter cutover: it must demonstrably fire on a
flipped dimension flag and on calendar misalignment, and stay silent on
agreement. Deep-history divergence between the layers is EXPECTED (WS7
measured it) and deliberately outside what this comparator alerts on.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from parallel_run import EDGE_DAYS, compare_edge  # noqa: E402


def make_sides(n=15):
    idx = pd.bdate_range("2026-07-21", periods=n)
    base = {
        "n_dimensions": [1] * n,
        "d1_on": [False] * n,
        "d2_on": [False] * n,
        "d3_on": [True] * n,
        "d4_on": [False] * n,
    }
    timeline = {"dates": [d.strftime("%Y-%m-%d") for d in idx], **base}
    cand = pd.DataFrame(base, index=idx)
    return timeline, cand


def test_identical_edges_clean():
    t, c = make_sides()
    out = compare_edge(t, c)
    assert out["mismatch_days"] == 0
    assert out["days_compared"] == EDGE_DAYS
    assert not out.get("insufficient_overlap")


def test_flipped_flag_fires_with_date_and_field():
    t, c = make_sides()
    c.iloc[-1, c.columns.get_loc("d3_on")] = False
    c.iloc[-1, c.columns.get_loc("n_dimensions")] = 0
    out = compare_edge(t, c)
    assert out["mismatch_days"] == 1
    fields = {m["field"] for m in out["mismatches"]}
    assert "d3_on" in fields and "n_dimensions" in fields
    assert all(m["date"] == c.index[-1].strftime("%Y-%m-%d") for m in out["mismatches"])


def test_mismatch_outside_edge_window_ignored():
    # Divergence deeper than the last EDGE_DAYS sessions is a layer property,
    # not an implementation fault — the comparator must not alert on it.
    t, c = make_sides()
    c.iloc[0, c.columns.get_loc("d1_on")] = True  # 15 sessions back, outside 10
    out = compare_edge(t, c)
    assert out["mismatch_days"] == 0


def test_insufficient_overlap_flagged():
    t, c = make_sides()
    out = compare_edge(t, c.iloc[-3:])  # only 3 common sessions
    assert out.get("insufficient_overlap") is True
    assert out["days_compared"] == 3
