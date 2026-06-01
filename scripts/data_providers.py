"""Price + volume data layer for the breadth-thrust engine.

Unlike the equity-defense-dashboard provider (adjusted close only), this engine
needs THREE fields per constituent:

  - adjusted close  -> direction (advances/declines), 52-week highs/lows, MA
  - raw volume      -> up-volume ratio (volume is unadjusted by nature)

so we return a richer schema:

    {ticker: {"dates": [...], "adjClose": [...], "volume": [...]}}

A file-backed cache stores the full panel so daily runs fetch only the delta.
Network fetch (yfinance) is blocked in some sandboxes; run the heavy fetch
locally, exactly as the breadth-thrust-etf roster refresh already does.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def fetch_yahoo(tickers: list[str], start: str, end: str, batch_size: int = 40) -> dict:
    """Fetch adjusted close + raw volume from Yahoo via yfinance.

    Returns {ticker: {"dates", "adjClose", "volume"}}. Tickers that fail are
    silently omitted (the engine tolerates a varying member count per day).
    """
    import yfinance as yf

    out: dict[str, dict] = {}
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        log.info("  Yahoo batch %d: %s ...", i // batch_size + 1, batch[:4])
        try:
            df = yf.download(
                batch, start=start, end=end, auto_adjust=False,
                progress=False, threads=True,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("  batch error: %s", e)
            continue
        if df is None or df.empty:
            continue
        adj = df["Adj Close"]
        vol = df["Volume"]
        if len(batch) == 1:
            adj.columns, vol.columns = batch, batch
        for t in batch:
            if t not in adj.columns:
                continue
            a = adj[t]
            v = vol[t]
            mask = a.notna()
            if not mask.any():
                continue
            idx = a.index[mask]
            out[t] = {
                "dates": [d.strftime("%Y-%m-%d") for d in idx],
                "adjClose": [round(float(x), 4) for x in a[mask].to_numpy()],
                "volume": [int(x) if x == x else 0 for x in v.reindex(idx).fillna(0).to_numpy()],
            }
        time.sleep(0.5)  # be polite to the endpoint
    return out


class PanelCache:
    """File-backed cache of the constituent price/volume panel."""

    def __init__(self, path: str):
        self.path = path
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"tickers": {}, "last_updated": None}

    def save(self) -> None:
        self.data["last_updated"] = datetime.now(timezone.utc).isoformat()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, separators=(",", ":"))
        size_mb = os.path.getsize(self.path) / 1024 / 1024
        log.info("  panel cache saved: %s (%.1f MB)", self.path, size_mb)

    def update(self, tickers: list[str], start: str, end: str, fetcher=fetch_yahoo) -> None:
        """Fetch any tickers missing or stale relative to ``end`` and merge."""
        cached = self.data["tickers"]
        need = []
        for t in tickers:
            rec = cached.get(t)
            if not rec or not rec.get("dates") or rec["dates"][-1] < end:
                need.append(t)
        if not need:
            log.info("  panel up to date")
            return
        log.info("  fetching %d tickers ...", len(need))
        fresh = fetcher(need, start, end)
        for t, rec in fresh.items():
            if t in cached and cached[t].get("dates"):
                # Merge on date, replacing overlaps (adjustments drift over time).
                merged = dict(zip(cached[t]["dates"], zip(cached[t]["adjClose"], cached[t]["volume"])))
                merged.update(dict(zip(rec["dates"], zip(rec["adjClose"], rec["volume"]))))
                items = sorted(merged.items())
                cached[t] = {
                    "dates": [d for d, _ in items],
                    "adjClose": [v[0] for _, v in items],
                    "volume": [v[1] for _, v in items],
                }
            else:
                cached[t] = rec
        self.data["tickers"] = cached
        self.save()

    def to_frames(self):
        """Return (adj_close_df, volume_df) as aligned pandas DataFrames."""
        import pandas as pd

        adj_cols, vol_cols = {}, {}
        for t, rec in self.data["tickers"].items():
            idx = pd.to_datetime(rec["dates"])
            adj_cols[t] = pd.Series(rec["adjClose"], index=idx)
            vol_cols[t] = pd.Series(rec["volume"], index=idx)
        adj = pd.DataFrame(adj_cols).sort_index()
        vol = pd.DataFrame(vol_cols).sort_index()
        return adj, vol
