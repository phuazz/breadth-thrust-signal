from __future__ import annotations
import sys
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import compute_breadth as cb
import forward_returns as fr

def _make_panel(n_days, n_tickers, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=datetime(2015, 1, 2), periods=n_days)
    steps = rng.normal(0, 0.01, size=(n_days, n_tickers))
    prices = 100 * np.exp(np.cumsum(steps, axis=0))
    cols = [f"T{i:03d}" for i in range(n_tickers)]
    adj = pd.DataFrame(prices, index=dates, columns=cols)
    vol = pd.DataFrame(rng.integers(1000, 10000, size=(n_days, n_tickers)), index=dates, columns=cols)
    return adj, vol

def test_panels_shapes_and_validity():
    adj, vol = _make_panel(400, 450)
    p = cb.build_panels(adj, vol)
    assert len(p.advances) == 400
    assert (p.advances + p.declines <= 450).all()
    uv = p.up_volume_ratio.dropna()
    assert (uv >= 0).all() and (uv <= 1).all()

def test_pct_above_ma_thrust_fires_on_planted_surge():
    n_days, n_tickers = 300, 450
    dates = pd.bdate_range(start=datetime(2015, 1, 2), periods=n_days)
    cols = [f"T{i:03d}" for i in range(n_tickers)]
    path = np.concatenate([np.linspace(100, 80, 200), np.linspace(80, 140, 100)])
    adj = pd.DataFrame(np.tile(path[:, None], (1, n_tickers)), index=dates, columns=cols)
    adj += np.random.default_rng(1).normal(0, 0.05, adj.shape)
    vol = pd.DataFrame(1000, index=dates, columns=cols)
    p = cb.build_panels(adj, vol)
    assert cb.d2_pct_above_ma(p)["d2"].any()

def test_score_bounded_and_or_within_dimension():
    adj, vol = _make_panel(400, 450)
    p = cb.build_panels(adj, vol)
    comp = cb.compute_composite(p)
    assert comp["n_dimensions"].between(0, 4).all()
    assert np.allclose(comp["score"], comp["n_dimensions"])
    d1 = cb.d1_advance_decline(p)
    assert (d1["d1"] == d1[["zweig", "ad_ratio_deemer", "mcclellan"]].any(axis=1)).all()

def test_no_lookahead_signal_is_lagged():
    dates = pd.bdate_range(start=datetime(2019, 1, 2), periods=60)
    spx = pd.Series(100.0 + np.arange(60), index=dates)
    comp = pd.DataFrame({"n_dimensions": 0, "event": False}, index=dates)
    k = 30
    comp.loc[dates[k], "n_dimensions"] = 2
    comp.loc[dates[k], "event"] = True
    h = fr.HORIZONS["1w"]
    tbl = fr.conditional_table(comp, spx, thresholds=(1,), events_only=True)
    row = tbl[(tbl["threshold"] == 1) & (tbl["horizon"] == "1w")].iloc[0]
    assert row["n"] == 1
    honest_val = spx.iloc[k + 1 + h] / spx.iloc[k + 1] - 1.0
    leaked_val = spx.iloc[k + h] / spx.iloc[k] - 1.0
    assert abs(row["median_ret"] - honest_val) < 1e-9
    assert abs(row["median_ret"] - leaked_val) > 1e-9

def test_forward_returns_align():
    spx = pd.Series(np.arange(1, 101, dtype=float), index=pd.bdate_range(start=datetime(2019, 1, 1), periods=100))
    f5 = fr.forward_returns(spx, 5)
    assert abs(f5.iloc[0] - 5.0) < 1e-9
    assert f5.iloc[-5:].isna().all()

def test_date_edge_month_and_year_boundary():
    d_month = datetime(2021, 1, 31) + relativedelta(months=1)
    assert (d_month.year, d_month.month, d_month.day) == (2021, 2, 28)
    d_year = datetime(2020, 2, 29) + relativedelta(years=1)
    assert (d_year.year, d_year.month, d_year.day) == (2021, 2, 28)
    rng = pd.bdate_range(start=datetime(2020, 12, 29), end=datetime(2021, 1, 4))
    assert pd.Timestamp(2021, 1, 1) in rng
    assert pd.Timestamp(2021, 1, 2) not in rng
