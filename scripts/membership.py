"""Point-in-time S&P 500 membership masking (survivorship-bias mitigation).

Two membership sources, in priority order:

1. A fetch_constituents.py-style snapshot JSON (the breadth-thrust-etf
   ``constituents_csp1.json`` schema): weekly Friday snapshots of iShares CSP1
   (S&P 500 UCITS) holdings. Clean point-in-time membership from 2018 onward.
   Run `python scripts/fetch_constituents.py --etf CSP1` in breadth-thrust-etf
   and copy the output into this project's data/ directory.

2. A flat current-membership list (fallback). This REINTRODUCES survivorship
   bias — every pre-today member that was later deleted is missing, and every
   current member is assumed to have always been in the index. The pipeline
   stamps a loud ``survivorship_bias: true`` flag on the output when this path
   is used, and the dashboard renders a warning banner. Use only for a quick
   first look, never for a published result.
"""

from __future__ import annotations

import json

import pandas as pd


def load_pit_snapshots(path: str) -> pd.DataFrame:
    """Load a constituents snapshot JSON into a boolean membership mask.

    Returns a DataFrame indexed by snapshot date (rows) x ticker (cols), True
    where the ticker was a member at that snapshot. The caller forward-fills
    this onto the trading calendar.
    """
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    snaps = payload["snapshots"]
    all_tickers = sorted({t for s in snaps.values() for t in s["tickers"]})
    rows = {}
    for date_str, snap in snaps.items():
        member = pd.Series(False, index=all_tickers)
        member[snap["tickers"]] = True
        rows[pd.Timestamp(date_str)] = member
    mask = pd.DataFrame(rows).T.sort_index()
    return mask


def apply_membership(
    adj_close: pd.DataFrame, volume: pd.DataFrame, mask: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Null out price/volume on dates where a ticker was not a member.

    The weekly snapshot mask is forward-filled onto the daily trading calendar
    (membership held static between snapshots — the same explicit assumption
    fetch_constituents.py documents).
    """
    # Restrict to tickers present in both the panel and the membership universe.
    common = [t for t in adj_close.columns if t in mask.columns]
    adj_close = adj_close[common]
    volume = volume[common]
    mask = mask[common]

    daily_mask = mask.reindex(adj_close.index, method="ffill").fillna(False).astype(bool)
    adj_masked = adj_close.where(daily_mask)
    vol_masked = volume.where(daily_mask)
    return adj_masked, vol_masked


def current_members_from_list(tickers: list[str]) -> list[str]:
    """Normalise a flat ticker list for the survivorship-biased fallback path
    (dot -> dash share-class fix, dedupe, drop blanks)."""
    seen, out = set(), []
    for t in tickers:
        t = t.strip().replace(".", "-")
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out
