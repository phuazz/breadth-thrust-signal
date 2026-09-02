"""Fire-path tests for the parallel-run edge comparator (pure, no NDU).

The comparator gates the live-meter cutover: it must demonstrably fire on a
flipped dimension flag and on calendar misalignment, and stay silent on
agreement. Deep-history divergence between the layers is EXPECTED (WS7
measured it) and deliberately outside what this comparator alerts on.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from parallel_run import EDGE_DAYS, assert_cross_layer, compare_edge  # noqa: E402


# ---------------------------------------------------------------------------
# Post-cutover: the harness must refuse to compare the candidate against itself
# ---------------------------------------------------------------------------

def test_same_layer_comparison_is_refused():
    """After the 2026-09-02 cutover the deployed payload carries the candidate's
    own provider tag. An edge comparison would then agree by construction and a
    CLEAN verdict would certify nothing, so the harness must raise before any
    record can be written."""
    deployed = {"data_quality": {"provider": "norgate-pit"}, "timeline": {}}
    with pytest.raises(ValueError, match="against itself"):
        assert_cross_layer(deployed)


def test_cross_layer_comparison_is_allowed():
    assert assert_cross_layer({"data_quality": {"provider": "csp1-yahoo"}}) == "csp1-yahoo"


def test_missing_provider_tag_is_not_treated_as_same_layer():
    # A payload with no provenance is an older csp1 build; it is a legitimate
    # (if poorly labelled) other side, not a self-comparison.
    assert assert_cross_layer({"data_quality": {}}) is None


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


# ---------------------------------------------------------------------------
# The 2026-08-22 soak that reported failure while its verdict was CLEAN
# ---------------------------------------------------------------------------

def test_log_never_raises_on_a_console_that_cannot_encode(monkeypatch, capsys):
    """parallel_run.log() must survive a stream that cannot encode its message.

    The 2026-08-22 soak wrote verdict CLEAN, zero alerts, ten of ten sessions
    agreeing — and then raised UnicodeEncodeError printing the summary line's
    arrow to a cp1252 console, exiting non-zero. The record is written BEFORE
    the summary, so the evidence was good and the exit code said otherwise;
    run_weekly_refresh.bat chains on that exit code. It sat unnoticed from
    2026-08-22 to 2026-08-27.

    A progress message must never be able to fail an unattended run.
    """
    import io
    import sys as _sys
    import parallel_run

    class Cp1252Stream(io.StringIO):
        encoding = "cp1252"

        def write(self, s):
            s.encode("cp1252")   # raises on the arrow, exactly as the console did
            return super().write(s)

    stream = Cp1252Stream()
    monkeypatch.setattr(_sys, "stdout", stream)

    parallel_run.log("CLEAN — window 1990-12-28 \u2192 2026-08-21")   # must not raise

    monkeypatch.undo()
    assert "CLEAN" in stream.getvalue(), "the line was dropped entirely"


def test_log_passes_plain_ascii_through_unchanged(monkeypatch, capsys):
    import parallel_run
    parallel_run.log("CLEAN - plain")
    assert "[parallel] CLEAN - plain" in capsys.readouterr().out
