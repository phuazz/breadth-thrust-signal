"""A deliberately WRONG WS10 engine, committed so the fixture can be proved able to fail.

Every function here implements a near-miss of a frozen rule in ``spec/ws10_prereg_spec.json``:
a 19-session window, a strict new-high test, an 11-session or exclude-today average, a share
divided before it is scaled, a 5- or 19-session below-run, events admitted inside the burn-in, a
strict threshold, a dimension replaced instead of OR-ed, a one-session memory, a 4- or 6-session
co-fire window, a 62-day cluster gap, an unlagged forward join and a null that drops one event.
``tests/test_ws10_mutants.py`` asserts that the fixture's expectations reject each of them while the
reference in ``tests/make_ws10_fixture.py`` passes. Never import this module from the engine.

Python months are 1-indexed. Date arithmetic goes through pandas only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _share_from(hit: pd.DataFrame, valid: pd.DataFrame, floor: int = 400, division_first: bool = False) -> pd.Series:
    num = (hit & valid).sum(axis=1).astype(float)
    den = valid.sum(axis=1).astype(float)
    if division_first:
        share = num / den.replace(0.0, np.nan) * 100.0
    else:
        share = 100.0 * num / den.replace(0.0, np.nan)
    share[den < floor] = np.nan
    return share


def share_sd3_window19(close: pd.DataFrame) -> pd.Series:
    stat = close.rolling(19, min_periods=19).max()
    return _share_from(close >= stat, close.notna() & stat.notna())


def share_sd3_strict_new_high(close: pd.DataFrame) -> pd.Series:
    """close strictly above the maximum of the PREVIOUS 19 closes (today excluded)."""
    stat = close.shift(1).rolling(19, min_periods=19).max()
    return _share_from(close > stat, close.notna() & stat.notna())


def share_sd2_sma11(close: pd.DataFrame) -> pd.Series:
    stat = close.rolling(11, min_periods=11).mean()
    return _share_from(close > stat, close.notna() & stat.notna())


def share_sd2_exclude_today(close: pd.DataFrame) -> pd.Series:
    stat = close.shift(1).rolling(10, min_periods=10).mean()
    return _share_from(close > stat, close.notna() & stat.notna())


def share_division_first(close: pd.DataFrame, member: str) -> pd.Series:
    if member == "S-D3":
        stat = close.rolling(20, min_periods=20).max()
        hit = close >= stat
    else:
        stat = close.rolling(10, min_periods=10).mean()
        hit = close > stat
    return _share_from(hit, close.notna() & stat.notna(), division_first=True)


def fresh_events_wrong(share: pd.Series, threshold: float, data_ok: pd.Series, below_sessions: int = 20,
                       admit_burn_in: bool = False, strict: bool = False) -> pd.DatetimeIndex:
    ok_idx = data_ok.index[data_ok.astype(bool)]
    first_ok = ok_idx[0] if len(ok_idx) else share.index[0]
    vals = share.to_numpy(dtype=float)
    fin = np.isfinite(vals)
    hit = fin & ((vals > threshold) if strict else (vals >= threshold))
    below = fin & ~hit
    out, run = [], 0
    for i, d in enumerate(share.index):
        if hit[i]:
            if run >= below_sessions and (admit_burn_in or (d >= first_ok and bool(data_ok.loc[d]))):
                out.append(d)
            run = 0
        elif below[i]:
            run += 1
        else:
            run = 0
    return pd.DatetimeIndex(out)


def composite_wrong(panels, extra: dict, cb, replace: bool = False, memory: int | None = None) -> pd.DataFrame:
    """compute_composite with the candidate REPLACING its dimension (replace=True) or with a wrong memory."""
    config = cb.CompositeConfig()
    mem = memory or config.memory_days
    dims = pd.concat([cb.d1_advance_decline(panels), cb.d2_pct_above_ma(panels),
                      cb.d3_new_high_low(panels), cb.d4_up_volume(panels)], axis=1)
    for dim, boolean in extra.items():
        b = boolean.reindex(dims.index).fillna(False).astype(bool)
        dims[dim] = b if replace else (dims[dim] | b)
    df = dims.copy()
    on_cols = []
    for d in ("d1", "d2", "d3", "d4"):
        df[f"{d}_on"] = dims[d].rolling(mem, min_periods=1).max().astype(bool)
        on_cols.append(f"{d}_on")
    df["n_dimensions"] = df[on_cols].sum(axis=1).astype(int)
    df["event"] = (df["n_dimensions"] > df["n_dimensions"].shift(1).fillna(0)).astype(bool)
    computable = (panels.ma_valid_count >= cb.MIN_VALID_CONSTITUENTS) & (panels.hl_valid_count >= cb.MIN_VALID_CONSTITUENTS)
    df["burn_in"] = ~computable
    df["data_ok"] = (panels.valid_count >= cb.MIN_VALID_CONSTITUENTS) & computable
    return df


def cofire_share_wrong(cand: pd.DatetimeIndex, fires: pd.DatetimeIndex, sessions: pd.DatetimeIndex, window: int) -> float:
    """The reference's co-fire share with a caller-chosen window (4 or 6 in the drill)."""
    if len(cand) == 0:
        return float("nan")
    pos = {d: i for i, d in enumerate(sessions)}
    fire_pos = np.array(sorted(pos[d] for d in fires), dtype=int)
    hits = sum(1 for d in cand if len(fire_pos) and np.any(np.abs(fire_pos - pos[d]) <= window))
    return 100.0 * hits / len(cand)


def cluster_ids_gap62(dates: pd.DatetimeIndex) -> list[int]:
    d = pd.DatetimeIndex(sorted(dates))
    ids, cur = [], 0
    for i in range(len(d)):
        if i > 0 and (d[i] - d[i - 1]).days > 62:
            cur += 1
        ids.append(cur)
    return ids


def forward_stats_lag0(events: pd.DatetimeIndex, index_series: pd.Series, h: int) -> dict:
    """Forward return measured from the signal close itself: the look-ahead the engine's lag prevents."""
    s = index_series.sort_index()
    fwd = s.shift(-h) / s - 1.0
    vals = fwd.reindex(events).dropna()
    return {"n": int(len(vals)), "win_rate": float((vals > 0).mean()) if len(vals) else float("nan"),
            "median": float(vals.median()) if len(vals) else float("nan")}


def null_sets_count_minus_one(events: pd.DatetimeIndex, valid_sessions: pd.DatetimeIndex, draws: int, seed_key) -> list:
    """Random sets with ONE FEWER event than the treatment, placed anywhere: not count-matched."""
    rng = np.random.default_rng(seed_key)
    n = max(len(events) - 1, 0)
    out = []
    for _ in range(draws):
        pos = np.sort(rng.choice(len(valid_sessions), size=n, replace=False))
        out.append(pd.DatetimeIndex(valid_sessions[pos]))
    return out
