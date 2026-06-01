"""Validate the engine's D1 advance/decline thrusts against published dates.

Per the vault rule "verify against at least two sources", this rebuilds the
breadth panels through the SAME point-in-time-masked code path the pipeline
uses, then prints the actual fire dates of each D1 sub-condition (Zweig,
McClellan Oscillator, 10-day Deemer A/D). It does NOT tune anything — it
reports matches and misses against the published anchors honestly.

Anchors (published Zweig Breadth Thrust / breadth-thrust triggers):
  - 2019-01-04  (the canonical post-Dec-2018 ZBT)
  - 2023-11-03  (the early-Nov-2023 breadth thrust)

Note on universe: published ZBT dates use NYSE all-issues breadth (incl. small
caps, preferreds, bonds). This engine uses S&P 500 large-cap constituents, a
proxy that converges with NYSE at the extremes but can differ by a day or two
on the exact trigger bar. Differences are expected and reported, not fitted.

Run:  python scripts/validate_d1.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import compute_breadth as cb  # noqa: E402
import membership as mb  # noqa: E402
from data_providers import PanelCache  # noqa: E402

DATA = ROOT / "data"
BENCHMARK = "^GSPC"
PIT = DATA / "constituents_csp1.json"

# Published anchors and the +/- window (trading days) we accept as a match,
# because a large-cap proxy can lead/lag NYSE all-issues by a bar or two.
ANCHORS = ["2019-01-04", "2023-11-03"]
MATCH_WINDOW_DAYS = 5


def _fires_near(fire_dates: pd.DatetimeIndex, anchor: pd.Timestamp, window: int):
    lo = anchor - pd.Timedelta(days=window)
    hi = anchor + pd.Timedelta(days=window)
    return [d for d in fire_dates if lo <= d <= hi]


def main() -> int:
    cache = PanelCache(str(DATA / "panel_cache.json"))
    adj, vol = cache.to_frames()
    if BENCHMARK in adj.columns:
        adj = adj.drop(columns=[BENCHMARK])
        vol = vol.drop(columns=[c for c in [BENCHMARK] if c in vol.columns])

    if PIT.exists():
        mask = mb.load_pit_snapshots(str(PIT))
        adj, vol = mb.apply_membership(adj, vol, mask)
        print(f"Point-in-time membership applied ({PIT.name}); survivorship-correct.")
    else:
        print("WARNING: no PIT snapshot — survivorship bias present.")

    panels = cb.build_panels(adj, vol)
    d1 = cb.d1_advance_decline(panels)
    valid = panels.valid_count

    # Only trust days with enough breadth (the engine's own data_ok gate).
    ok = valid >= cb.MIN_VALID_CONSTITUENTS
    print(
        f"Panel: {adj.index.min().date()} -> {adj.index.max().date()}, "
        f"{len(adj.index)} trading days, {adj.shape[1]} tickers ever.\n"
        f"Days with >= {cb.MIN_VALID_CONSTITUENTS} valid constituents: "
        f"{int(ok.sum())} / {len(ok)}.\n"
    )

    for col in ("zweig", "mcclellan", "ad_ratio_deemer", "d1"):
        fires = d1.index[d1[col] & ok]
        print(f"[{col}] {len(fires)} fire-days (within valid-breadth window):")
        for d in fires:
            print(f"    {d.date()}")
        print()

    print("=" * 60)
    print("Anchor cross-check (+/- %d calendar days):" % MATCH_WINDOW_DAYS)
    for a in ANCHORS:
        anchor = pd.Timestamp(a)
        hits = {}
        for col in ("zweig", "mcclellan", "ad_ratio_deemer", "d1"):
            fires = d1.index[d1[col] & ok]
            near = _fires_near(fires, anchor, MATCH_WINDOW_DAYS)
            if near:
                hits[col] = [d.date().isoformat() for d in near]
        if hits:
            print(f"  {a}: MATCH -> {hits}")
        else:
            print(f"  {a}: MISS  (no D1 sub-condition fired within window)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
