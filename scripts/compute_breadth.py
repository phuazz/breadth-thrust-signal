"""Breadth-thrust signal engine — grouped / weighted conviction score.

Design rationale (2026-06-01)
-----------------------------
The canonical "8 breadth thrust signals" are NOT 8 independent facts. Four of
them — Zweig, McClellan Oscillator, 10-day A/D ratio, McClellan Summation —
all derive from the same advance/decline series. The Summation Index is
literally the running sum of the Oscillator. A naive 0-8 sum therefore
overstates corroboration: "6 of 8 firing" can be two or three underlying
readings wearing six hats.

This engine collapses the indicators into FOUR independent breadth
dimensions and scores conviction as the number of dimensions currently
thrusting (0-4), with optional per-dimension weights:

  D1  Advance/Decline thrust   (OR of Zweig, 10d A/D ratio, McClellan Osc)
  D2  % above 50-day MA thrust
  D3  New-high / new-low thrust (OR of NH/NL ratio surge, net-new-high surge)
  D4  Up-volume thrust

Within a dimension we take the logical OR of its sub-conditions, because the
sub-conditions share the same raw data and are alternative expressions of one
breadth fact. Across dimensions we sum (optionally weighted), because the
dimensions are genuinely independent measurements.

Inputs are pandas DataFrames indexed by date (rows) with one column per
constituent ticker. This keeps the engine pure and unit-testable with synthetic
data — no network, no file IO.

Conventions
-----------
- Direction (advance/decline, new highs) uses ADJUSTED close, so splits do not
  manufacture spurious declines. Dividend-driven moves are negligible for
  direction counting.
- Up-volume uses RAW (unadjusted) volume — volume is unadjusted by nature
  (per vault data-integrity rule).
- All thresholds are canonical (Zweig 0.40 / 0.615, etc.) and are NOT optimised
  in-sample. Signal 7 (Summation Index) is deliberately EXCLUDED rather than
  fitted to an empirical threshold, because deriving its threshold from the
  same data would be exactly the in-sample overfit the brief warns against.
- Python datetime months are 1-indexed (Jan == 1). Stated explicitly because
  JavaScript Date months are 0-indexed; we are in Python here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Canonical thrust parameters (do NOT optimise in-sample)
# ---------------------------------------------------------------------------

# D1 — Advance/Decline family
ZWEIG_LOW = 0.40            # Zweig: EMA(10) of A/(A+D) starts below this ...
ZWEIG_HIGH = 0.615          #   ... and crosses above this ...
ZWEIG_WINDOW = 10           #   ... within this many sessions.
AD_RATIO_WINDOW = 10        # Deemer breakaway momentum lookback
AD_RATIO_THRESHOLD = 1.90   # 10-day cumulative advances / declines
MCC_FAST = 19               # McClellan Oscillator fast EMA span
MCC_SLOW = 39               # McClellan Oscillator slow EMA span
MCC_OVERSOLD = -50.0        # Oscillator must dip below this ...
MCC_RECOVER_WINDOW = 20     #   ... then cross back above zero within N sessions.

# D2 — % above 50-day MA
PCT50_MA_WINDOW = 50
PCT50_LOW = 0.25            # surge from below 25% ...
PCT50_HIGH = 0.75          #   ... to above 75% ...
PCT50_THRUST_WINDOW = 15    #   ... within this many sessions.

# D3 — New high / new low
HL_LOOKBACK = 252           # 52-week window for new highs / lows
NHNL_LOW = 0.10             # NH/(NH+NL) surge from below 10% ...
NHNL_HIGH = 0.50           #   ... to above 50% ...
NHNL_THRUST_WINDOW = 10     #   ... within this many sessions.
NET_NH_THRESHOLD = 20       # net new highs must exceed this ...
NET_NH_THRUST_WINDOW = 10   #   ... rising from net-negative within N sessions.

# D4 — Up volume
UPVOL_RATIO = 0.90          # up-volume / total volume must exceed this ...
UPVOL_TRAILING = 5          #   ... on at least one day in the trailing N sessions.

# Conviction memory: a fired dimension stays "on" for this many trading days,
# so that several thrusts clustering within weeks register as high conviction.
DEFAULT_MEMORY_DAYS = 60

# Minimum valid constituents required on a day for breadth to be trustworthy.
MIN_VALID_CONSTITUENTS = 400


# ---------------------------------------------------------------------------
# Raw breadth panels
# ---------------------------------------------------------------------------


@dataclass
class BreadthPanels:
    """Daily breadth aggregates, all indexed by trading date."""

    advances: pd.Series          # count of constituents up vs prior close
    declines: pd.Series          # count down vs prior close
    valid_count: pd.Series       # constituents with valid data that day
    pct_above_50dma: pd.Series   # fraction in [0, 1]
    new_highs: pd.Series         # count at 252-day high
    new_lows: pd.Series          # count at 252-day low
    up_volume_ratio: pd.Series   # up-volume / total volume in [0, 1]


def build_panels(adj_close: pd.DataFrame, volume: pd.DataFrame) -> BreadthPanels:
    """Aggregate a constituent price/volume panel into daily breadth series.

    Parameters
    ----------
    adj_close : DataFrame
        Adjusted close, dates x tickers. NaN where a constituent is not a
        member / has no data on that date.
    volume : DataFrame
        Raw (unadjusted) volume, same shape and alignment as ``adj_close``.

    Returns
    -------
    BreadthPanels
    """
    adj_close = adj_close.sort_index()
    volume = volume.reindex_like(adj_close)

    prev = adj_close.shift(1)
    up = adj_close > prev
    down = adj_close < prev
    valid = adj_close.notna() & prev.notna()

    advances = (up & valid).sum(axis=1).astype(float)
    declines = (down & valid).sum(axis=1).astype(float)
    valid_count = valid.sum(axis=1).astype(float)

    # % above 50-day moving average (per constituent, then cross-sectional share)
    ma50 = adj_close.rolling(PCT50_MA_WINDOW, min_periods=PCT50_MA_WINDOW).mean()
    above = adj_close > ma50
    ma_valid = adj_close.notna() & ma50.notna()
    pct_above = (above & ma_valid).sum(axis=1) / ma_valid.sum(axis=1).replace(0, np.nan)

    # 52-week new highs / lows
    roll_max = adj_close.rolling(HL_LOOKBACK, min_periods=HL_LOOKBACK).max()
    roll_min = adj_close.rolling(HL_LOOKBACK, min_periods=HL_LOOKBACK).min()
    hl_valid = adj_close.notna() & roll_max.notna()
    new_highs = ((adj_close >= roll_max) & hl_valid).sum(axis=1).astype(float)
    new_lows = ((adj_close <= roll_min) & hl_valid).sum(axis=1).astype(float)

    # Up-volume ratio: volume of up names / total volume
    up_vol = (volume.where(up, 0.0)).sum(axis=1)
    tot_vol = volume.where(valid, 0.0).sum(axis=1)
    up_volume_ratio = up_vol / tot_vol.replace(0, np.nan)

    return BreadthPanels(
        advances=advances,
        declines=declines,
        valid_count=valid_count,
        pct_above_50dma=pct_above,
        new_highs=new_highs,
        new_lows=new_lows,
        up_volume_ratio=up_volume_ratio,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _crossed_up_within(
    series: pd.Series, low: float, high: float, window: int
) -> pd.Series:
    """True on days where ``series`` is above ``high`` today AND was below
    ``low`` at some point in the trailing ``window`` sessions (inclusive of
    today's bar back ``window`` steps). Classic thrust shape: compressed, then
    released, inside a short window.
    """
    above_high = series > high
    # Was the series below `low` at any point in the trailing window?
    below_low = series < low
    was_low = below_low.rolling(window, min_periods=1).max().astype(bool)
    return (above_high & was_low).fillna(False)


# ---------------------------------------------------------------------------
# Dimension thrust detectors
# ---------------------------------------------------------------------------


def d1_advance_decline(panels: BreadthPanels) -> pd.DataFrame:
    """Advance/Decline thrust dimension.

    Returns a DataFrame with one boolean column per sub-condition plus a
    ``d1`` column that is the logical OR. The sub-conditions are reported for
    transparency but contribute to conviction only once (as ``d1``), because
    they all derive from the same advance/decline series.
    """
    adv = panels.advances
    dec = panels.declines
    net = adv - dec
    ad_ratio_daily = adv / (adv + dec).replace(0, np.nan)

    # Zweig: EMA(10) of advance ratio, compressed-then-released
    zweig_line = ad_ratio_daily.ewm(span=ZWEIG_WINDOW, adjust=False).mean()
    zweig = _crossed_up_within(zweig_line, ZWEIG_LOW, ZWEIG_HIGH, ZWEIG_WINDOW)

    # 10-day cumulative A/D ratio > 1.90 (Deemer breakaway momentum)
    cum_adv = adv.rolling(AD_RATIO_WINDOW, min_periods=AD_RATIO_WINDOW).sum()
    cum_dec = dec.rolling(AD_RATIO_WINDOW, min_periods=AD_RATIO_WINDOW).sum()
    ad_ratio = cum_adv / cum_dec.replace(0, np.nan)
    deemer = (ad_ratio > AD_RATIO_THRESHOLD).fillna(False)

    # McClellan Oscillator: EMA(19) - EMA(39) of net advances; dip < -50 then
    # cross back above 0 within MCC_RECOVER_WINDOW sessions.
    mcc = (
        net.ewm(span=MCC_FAST, adjust=False).mean()
        - net.ewm(span=MCC_SLOW, adjust=False).mean()
    )
    was_oversold = (mcc < MCC_OVERSOLD).rolling(
        MCC_RECOVER_WINDOW, min_periods=1
    ).max().astype(bool)
    mcc_thrust = ((mcc > 0) & was_oversold).fillna(False)

    out = pd.DataFrame(
        {
            "zweig": zweig,
            "ad_ratio_deemer": deemer,
            "mcclellan": mcc_thrust,
        }
    )
    out["d1"] = out.any(axis=1)
    return out


def d2_pct_above_ma(panels: BreadthPanels) -> pd.DataFrame:
    """% above 50-day MA thrust: surge from < 25% to > 75% within 15 sessions."""
    pct = panels.pct_above_50dma
    thrust = _crossed_up_within(pct, PCT50_LOW, PCT50_HIGH, PCT50_THRUST_WINDOW)
    return pd.DataFrame({"pct_above_50dma": thrust, "d2": thrust})


def d3_new_high_low(panels: BreadthPanels) -> pd.DataFrame:
    """New-high / new-low thrust dimension (OR of two NH/NL expressions)."""
    nh = panels.new_highs
    nl = panels.new_lows
    nhnl_ratio = nh / (nh + nl).replace(0, np.nan)
    ratio_thrust = _crossed_up_within(
        nhnl_ratio, NHNL_LOW, NHNL_HIGH, NHNL_THRUST_WINDOW
    )

    net_nh = nh - nl
    # Rose from net-negative (within window) to net > threshold today.
    was_negative = (net_nh < 0).rolling(
        NET_NH_THRUST_WINDOW, min_periods=1
    ).max().astype(bool)
    net_thrust = ((net_nh > NET_NH_THRESHOLD) & was_negative).fillna(False)

    out = pd.DataFrame({"nhnl_ratio": ratio_thrust, "net_new_highs": net_thrust})
    out["d3"] = out.any(axis=1)
    return out


def d4_up_volume(panels: BreadthPanels) -> pd.DataFrame:
    """Up-volume thrust: ratio > 0.90 on at least one day in trailing 5."""
    ratio = panels.up_volume_ratio
    hit = (ratio > UPVOL_RATIO).fillna(False)
    thrust = hit.rolling(UPVOL_TRAILING, min_periods=1).max().astype(bool)
    return pd.DataFrame({"up_volume": thrust, "d4": thrust})


# ---------------------------------------------------------------------------
# Composite conviction score
# ---------------------------------------------------------------------------


@dataclass
class CompositeConfig:
    memory_days: int = DEFAULT_MEMORY_DAYS
    # Per-dimension weights. Default equal — each independent breadth dimension
    # counts once. Override to up-weight more reliable dimensions.
    weights: dict = field(
        default_factory=lambda: {"d1": 1.0, "d2": 1.0, "d3": 1.0, "d4": 1.0}
    )


def compute_composite(
    panels: BreadthPanels, config: CompositeConfig | None = None
) -> pd.DataFrame:
    """Assemble the grouped/weighted conviction score.

    For each dimension we (a) detect fresh thrust EVENTS (the day it fires),
    then (b) hold the dimension "on" for ``memory_days`` trading days so that
    clustered thrusts register together. Conviction is the weighted count of
    dimensions currently on.

    Returns a DataFrame indexed by date with:
      - sub-condition booleans (zweig, mcclellan, ...)
      - d1..d4 (raw daily dimension fire)
      - d1_on..d4_on (dimension held on within memory window)
      - n_dimensions (0-4 integer, dimensions currently on)
      - score (weighted, == n_dimensions under equal weights)
      - event (True on a day where any NEW dimension switches on — the clean
        sampling point for the forward-return study)
      - valid_count, data_ok
    """
    config = config or CompositeConfig()
    mem = config.memory_days

    dims = pd.concat(
        [
            d1_advance_decline(panels),
            d2_pct_above_ma(panels),
            d3_new_high_low(panels),
            d4_up_volume(panels),
        ],
        axis=1,
    )

    df = dims.copy()
    on_cols = []
    for d in ("d1", "d2", "d3", "d4"):
        on = dims[d].rolling(mem, min_periods=1).max().astype(bool)
        df[f"{d}_on"] = on
        on_cols.append(f"{d}_on")

    w = config.weights
    df["n_dimensions"] = df[on_cols].sum(axis=1).astype(int)
    df["score"] = (
        df["d1_on"].astype(float) * w["d1"]
        + df["d2_on"].astype(float) * w["d2"]
        + df["d3_on"].astype(float) * w["d3"]
        + df["d4_on"].astype(float) * w["d4"]
    )

    # An "event" is a day where the count of active dimensions increases —
    # i.e. a new breadth fact just arrived. This is the de-duplicated sampling
    # point for the conditional forward-return study (avoids counting every day
    # of a 60-day memory window as a fresh observation).
    df["event"] = (df["n_dimensions"] > df["n_dimensions"].shift(1).fillna(0)).astype(bool)

    df["valid_count"] = panels.valid_count
    df["data_ok"] = panels.valid_count >= MIN_VALID_CONSTITUENTS

    return df


def latest_readings(panels: BreadthPanels) -> dict:
    """Current values of the raw breadth lines the D1-D4 detectors threshold.

    For the dashboard's "how the signal is formed" view. Mirrors the formulas in
    the detectors above and uses the SAME canonical constants, so a span/window
    change there flows through here. Display only — the signal itself comes from
    the detector booleans, never from these scalars.
    """
    adv, dec = panels.advances, panels.declines
    ad_ratio_daily = adv / (adv + dec).replace(0, np.nan)
    zweig_line = ad_ratio_daily.ewm(span=ZWEIG_WINDOW, adjust=False).mean()

    cum_adv = adv.rolling(AD_RATIO_WINDOW, min_periods=AD_RATIO_WINDOW).sum()
    cum_dec = dec.rolling(AD_RATIO_WINDOW, min_periods=AD_RATIO_WINDOW).sum()
    ad_ratio_10d = cum_adv / cum_dec.replace(0, np.nan)

    net = adv - dec
    mcc = (
        net.ewm(span=MCC_FAST, adjust=False).mean()
        - net.ewm(span=MCC_SLOW, adjust=False).mean()
    )

    nh, nl = panels.new_highs, panels.new_lows
    nhnl_ratio = nh / (nh + nl).replace(0, np.nan)
    net_nh = nh - nl

    upvol_trailing_max = panels.up_volume_ratio.rolling(
        UPVOL_TRAILING, min_periods=1
    ).max()

    def last(s):
        v = s.iloc[-1] if len(s) else np.nan
        return None if v != v else float(v)

    return {
        "advance_ratio": last(ad_ratio_daily),
        "zweig_ema": last(zweig_line),
        "ad_ratio_10d": last(ad_ratio_10d),
        "mcclellan_osc": last(mcc),
        "pct_above_50dma": last(panels.pct_above_50dma),
        "nhnl_ratio": last(nhnl_ratio),
        "net_new_highs": last(net_nh),
        "up_volume_ratio": last(panels.up_volume_ratio),
        "up_volume_trailing5_max": last(upvol_trailing_max),
    }
