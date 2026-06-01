"""Conditional forward-return study.

Answers the core question: when the breadth-thrust conviction score is >= N,
what are forward SPX returns, and crucially how much LIFT is that over the
unconditional base rate?

Three correctness guards, matching the vault's "state the three ways a backtest
could be silently wrong" rule:

1. Look-ahead: the conviction score is lagged one day (.shift(1)) before any
   forward return is measured. Signal observed at close T; the forward window
   starts at close T+1. See ``conditional_table`` and the no-lookahead test.

2. Meaningless-without-baseline: a bare "80% win rate" is worthless if the
   unconditional 6-month win rate is already ~75%. We therefore report the
   LIFT over an unconditional baseline computed on the SAME overlapping,
   autocorrelated windows, with a bootstrap confidence band so the reader can
   see whether the lift survives sampling noise.

3. Overlapping-window autocorrelation: forward windows overlap heavily, so
   naive sample counts overstate independence. The bootstrap resamples
   contiguous blocks (moving-block bootstrap) to preserve autocorrelation when
   building the baseline band.

All functions are pure (DataFrame in, dict/DataFrame out) and unit-testable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Forward horizons in trading days (approx): 1w, 1m, 3m, 6m, 12m
HORIZONS = {"1w": 5, "1m": 21, "3m": 63, "6m": 126, "12m": 252}


def forward_returns(spx: pd.Series, horizon_days: int) -> pd.Series:
    """Simple forward return over ``horizon_days`` trading days.

    ret_t = spx_{t+h} / spx_t - 1, indexed at t. NaN where the window runs off
    the end of the series.
    """
    spx = spx.sort_index()
    fwd = spx.shift(-horizon_days) / spx - 1.0
    return fwd


def forward_max_drawdown(spx: pd.Series, horizon_days: int) -> pd.Series:
    """Worst peak-to-trough drawdown within the forward ``horizon_days`` window,
    measured from each start date t. Returned as a negative fraction.
    """
    spx = spx.sort_index()
    vals = spx.to_numpy(dtype=float)
    n = len(vals)
    out = np.full(n, np.nan)
    for i in range(n):
        end = i + horizon_days
        if end >= n:
            break
        window = vals[i : end + 1]
        running_max = np.maximum.accumulate(window)
        dd = window / running_max - 1.0
        out[i] = dd.min()
    return pd.Series(out, index=spx.index)


def _win_rate(x: pd.Series) -> float:
    x = x.dropna()
    if len(x) == 0:
        return float("nan")
    return float((x > 0).mean())


def conditional_table(
    composite: pd.DataFrame,
    spx: pd.Series,
    thresholds=(1, 2, 3, 4),
    events_only: bool = True,
) -> pd.DataFrame:
    """Forward-return summary by conviction threshold and horizon.

    Parameters
    ----------
    composite : DataFrame
        Output of ``compute_breadth.compute_composite`` (has ``n_dimensions``
        and ``event``).
    spx : Series
        SPX (or SPY) level indexed by the same trading dates.
    thresholds : iterable of int
        Score thresholds N; rows report stats for days where score >= N.
    events_only : bool
        If True, condition only on fresh thrust EVENT days (de-duplicated),
        which is the honest sampling unit. If False, condition on every day the
        score is >= N (heavily autocorrelated; for diagnostics only).

    Returns
    -------
    DataFrame with columns: threshold, horizon, n, win_rate, median_ret,
    mean_ret, median_max_dd.
    """
    spx = spx.sort_index()
    # GUARD 1 — lag the signal one day before measuring forward returns.
    score = composite["n_dimensions"].reindex(spx.index).shift(1)
    event = (composite["event"].reindex(spx.index).shift(1) == True)  # noqa: E712

    rows = []
    for label, h in HORIZONS.items():
        fwd = forward_returns(spx, h)
        mdd = forward_max_drawdown(spx, h)
        for n in thresholds:
            cond = score >= n
            if events_only:
                cond = cond & event
            sel = cond & fwd.notna()
            vals = fwd[sel]
            has = bool(sel.any())

            def _pct(q):
                # Percentile of the conditional forward-return distribution —
                # this is the "range" a reader should expect around the median,
                # not a confidence interval on the median itself.
                return float(np.percentile(vals, q)) if has else float("nan")

            rows.append(
                {
                    "threshold": n,
                    "horizon": label,
                    "n": int(sel.sum()),
                    "win_rate": _win_rate(vals),
                    "median_ret": float(vals.median()) if has else float("nan"),
                    "mean_ret": float(vals.mean()) if has else float("nan"),
                    "p10_ret": _pct(10),
                    "p25_ret": _pct(25),
                    "p75_ret": _pct(75),
                    "p90_ret": _pct(90),
                    "median_max_dd": float(mdd[sel].median()) if has else float("nan"),
                }
            )
    return pd.DataFrame(rows)


def unconditional_baseline(
    spx: pd.Series, n_boot: int = 2000, block: int = 21, seed: int = 42
) -> pd.DataFrame:
    """Bootstrap the unconditional forward-return distribution per horizon.

    GUARD 2 / 3 — the baseline is what a randomly chosen date would have
    earned, sampled with a MOVING-BLOCK bootstrap (contiguous blocks of length
    ``block``) so autocorrelation in overlapping forward windows is preserved.
    Returns median win-rate and return per horizon with a 5-95% band, so the
    conditional numbers can be read as LIFT over this, not in isolation.
    """
    rng = np.random.default_rng(seed)
    spx = spx.sort_index()
    rows = []
    for label, h in HORIZONS.items():
        fwd = forward_returns(spx, h).dropna().to_numpy()
        if len(fwd) == 0:
            continue
        n = len(fwd)
        n_blocks = max(1, n // block)
        boot_win = np.empty(n_boot)
        boot_med = np.empty(n_boot)
        for b in range(n_boot):
            starts = rng.integers(0, max(1, n - block), size=n_blocks)
            sample = np.concatenate([fwd[s : s + block] for s in starts])
            boot_win[b] = (sample > 0).mean()
            boot_med[b] = np.median(sample)
        rows.append(
            {
                "horizon": label,
                "base_win_rate": float(np.median(boot_win)),
                "base_win_lo": float(np.percentile(boot_win, 5)),
                "base_win_hi": float(np.percentile(boot_win, 95)),
                "base_median_ret": float(np.median(boot_med)),
                "base_ret_lo": float(np.percentile(boot_med, 5)),
                "base_ret_hi": float(np.percentile(boot_med, 95)),
                "n_total": int(n),
            }
        )
    return pd.DataFrame(rows)


def lift_table(conditional: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    """Join conditional stats to the baseline and compute lift.

    ``win_lift`` = conditional win rate - baseline win rate.
    ``ret_lift``  = conditional median return - baseline median return.
    A signal is interesting only when the lift is positive AND large relative
    to the baseline bootstrap band (base_win_hi - base_win_rate).
    """
    merged = conditional.merge(baseline, on="horizon", how="left")
    merged["win_lift"] = merged["win_rate"] - merged["base_win_rate"]
    merged["ret_lift"] = merged["median_ret"] - merged["base_median_ret"]
    # Is the conditional win rate above the 95th-percentile of the baseline
    # band? A coarse "beyond noise" flag.
    merged["win_beyond_noise"] = merged["win_rate"] > merged["base_win_hi"]
    return merged
