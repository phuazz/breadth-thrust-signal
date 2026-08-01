"""WS7 guards: the three ways the Norgate history extension could be silently
wrong (KICKOFF_ws7-norgate-history-extension.md section 4), plus the burn-in
gate the filed Phase 0 record was found to be missing.

These tests are pure — none of them touch NDU — so they run in CI and in any
sandbox. The live-feed checks live in ``norgate_provider.readiness()``.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import compute_breadth as cb  # noqa: E402
import norgate_provider as npv  # noqa: E402


# ---------------------------------------------------------------------------
# Silent-wrongness #1 — ticker reuse
# ---------------------------------------------------------------------------


def test_base_ticker_strips_only_delisting_suffix():
    # Real collisions from the ever-member universe: same base, different firm.
    assert npv.base_ticker("C-199811") == "C"        # Chrysler
    assert npv.base_ticker("C") == "C"               # Citigroup
    assert npv.base_ticker("AAL-199702") == "AAL"
    assert npv.base_ticker("BAC-199809") == "BAC"
    # A hyphen that is not a delisting stamp must survive intact, or share
    # classes get silently merged into their parent.
    assert npv.base_ticker("BRK-B") == "BRK-B"
    assert npv.base_ticker("BF-B") == "BF-B"


def test_collision_guard_accepts_full_symbols_and_rejects_duplicates():
    # Keyed on full Norgate symbols, Chrysler and Citigroup coexist safely.
    npv.assert_no_base_ticker_collision(["C", "C-199811", "AAL", "AAL-199702"])
    # Keyed on base tickers, they collapse to one column — this must never pass.
    with pytest.raises(ValueError):
        npv.assert_no_base_ticker_collision(["C", "C", "AAL"])


def test_panel_columns_are_unique_per_company():
    """A panel built from colliding symbols keeps them as separate series."""
    dates = pd.bdate_range(start=datetime(2000, 1, 3), periods=10)
    panel = pd.DataFrame(
        {"C": np.arange(10.0), "C-199811": np.arange(10.0) * 2},
        index=dates,
    )
    assert panel.shape[1] == 2
    assert not panel["C"].equals(panel["C-199811"])


# ---------------------------------------------------------------------------
# Silent-wrongness #2 — adjustment-basis conflation
# ---------------------------------------------------------------------------


def test_cache_path_is_keyed_on_basis():
    """The bug that detonates the moment a second basis appears: a cache path
    keyed on symbol alone serves TOTALRETURN prices to a NONE caller."""
    root = Path("/tmp/x")
    a = npv._cache_path(root, npv.CLOSE_BASIS, "AAPL")
    b = npv._cache_path(root, npv.VOLUME_BASIS, "AAPL")
    assert a != b
    assert npv.CLOSE_BASIS in str(a) and npv.VOLUME_BASIS in str(b)


def test_reader_raises_on_basis_mismatch(tmp_path):
    df = pd.DataFrame(
        {"Close": [1.0, 2.0], "Volume": [10, 20]},
        index=pd.DatetimeIndex(["2020-01-02", "2020-01-03"]),
    )
    p = npv._cache_path(tmp_path, npv.CLOSE_BASIS, "AAPL")
    npv._write(p, df, "AAPL", npv.CLOSE_BASIS, "2026-08-01 00:00:00+08:00")

    back = npv._read(p, npv.CLOSE_BASIS)
    assert list(back.columns) == ["Close", "Volume"]
    assert back.index.equals(df.index)

    # A wrong answer is worse than no answer: mismatch must raise, not return.
    with pytest.raises(ValueError, match="basis mismatch"):
        npv._read(p, npv.VOLUME_BASIS)


def test_footer_provenance_is_written_with_the_data(tmp_path):
    import pyarrow.parquet as pq

    df = pd.DataFrame(
        {"Close": [1.0], "Volume": [10]},
        index=pd.DatetimeIndex(["2020-01-02"]),
    )
    p = npv._cache_path(tmp_path, npv.VOLUME_BASIS, "$SPX")
    npv._write(p, df, "$SPX", npv.VOLUME_BASIS, "2026-08-01 00:00:00+08:00")
    meta = pq.ParquetFile(p).schema_arrow.metadata
    assert meta[b"symbol"] == b"$SPX"
    assert meta[b"basis"] == npv.VOLUME_BASIS.encode()
    assert meta[b"ndu_last_database_update_time"] == b"2026-08-01 00:00:00+08:00"
    assert meta[b"first_date"] == b"2020-01-02"


def test_basis_integrity_rejects_misaligned_dates(tmp_path):
    """Close and volume must share a date index, or direction is matched to the
    wrong day's volume."""
    close = pd.DataFrame(
        {"Close": [1.0, 2.0, 3.0], "Volume": [1, 2, 3]},
        index=pd.DatetimeIndex(["2020-01-02", "2020-01-03", "2020-01-06"]),
    )
    vol = close.iloc[:2]  # one row short
    npv._write(npv._cache_path(tmp_path, npv.CLOSE_BASIS, "X"), close, "X",
               npv.CLOSE_BASIS, "t")
    npv._write(npv._cache_path(tmp_path, npv.VOLUME_BASIS, "X"), vol, "X",
               npv.VOLUME_BASIS, "t")
    with pytest.raises(ValueError, match="date indices differ"):
        npv.assert_basis_integrity(tmp_path, ["X"])


# ---------------------------------------------------------------------------
# Burn-in gate — the defect found in the filed Phase 0 record
# ---------------------------------------------------------------------------


def _flat_panel(n_days, n_tickers=450, seed=3):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=datetime(1990, 1, 2), periods=n_days)
    steps = rng.normal(0, 0.01, size=(n_days, n_tickers))
    prices = 100 * np.exp(np.cumsum(steps, axis=0))
    cols = [f"T{i:03d}" for i in range(n_tickers)]
    adj = pd.DataFrame(prices, index=dates, columns=cols)
    vol = pd.DataFrame(rng.integers(1000, 10000, size=(n_days, n_tickers)),
                       index=dates, columns=cols)
    return adj, vol


def test_data_ok_is_false_through_the_burn_in():
    """For the first HL_LOOKBACK days D3 cannot fire and for the first
    PCT50_MA_WINDOW days D2 cannot, so the score is mechanically capped at 2.
    Those days must be excluded from the study, not scored."""
    adj, vol = _flat_panel(400)
    comp = cb.compute_composite(cb.build_panels(adj, vol))

    assert not comp["data_ok"].iloc[: cb.HL_LOOKBACK - 1].any(), (
        "days where 52-week highs/lows do not yet exist must not be data_ok"
    )
    assert comp["data_ok"].iloc[cb.HL_LOOKBACK:].any(), (
        "data_ok must switch on once every dimension is computable"
    )
    assert comp["burn_in"].iloc[0]
    assert not comp["burn_in"].iloc[-1]


def test_burn_in_days_cannot_reach_full_conviction():
    """The invariant that makes the gate necessary: a capped window can only
    ever produce low-conviction events."""
    adj, vol = _flat_panel(400)
    comp = cb.compute_composite(cb.build_panels(adj, vol))
    capped = comp[comp["burn_in"]]
    assert (capped["n_dimensions"] <= 2).all(), (
        "D2 and D3 are uncomputable during burn-in, so score > 2 is impossible "
        "there — if this fails the burn-in mask is wrong"
    )


def test_burn_in_gate_does_not_shorten_a_fully_warmed_panel():
    """Regression guard: the gate must not silently eat valid days at the end
    of a panel that has already warmed up."""
    adj, vol = _flat_panel(600)
    comp = cb.compute_composite(cb.build_panels(adj, vol))
    ok = comp["data_ok"]
    # Once on, it stays on for a panel with no membership gaps.
    first_on = ok.idxmax()
    assert ok.loc[first_on:].all()
