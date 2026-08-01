"""WS8 section 4b: pull the cross-sectional replication universes.

Russell 2000 (~11k ever-members) and S&P SmallCap 600 (~2.6k). Full history,
both adjustment bases, cached outside the repository per the licence rule.
Run once; the backtest and replication scripts read from the cache.

Run:  python scripts/ws8_fetch_universes.py
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import norgate_provider as npv  # noqa: E402

log = logging.getLogger("ws8_fetch")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    r = npv.readiness()
    if not r.ok:
        raise SystemExit(f"Norgate not ready: {r.detail}")

    for u in (npv.R2000, npv.SP600):
        root = npv.cache_root_for(u)
        syms = npv.resolve_universe(u)
        npv.assert_no_base_ticker_collision(syms)
        log.info("%s: %d ever-members -> %s", u.index_name, len(syms), root)
        t0 = time.time()
        stats = npv.refresh(root, syms + [u.benchmark])
        log.info(
            "  %s done in %.0fs: %d series, %d failures",
            u.slug, time.time() - t0, stats["pulled"], len(stats["failed"]),
        )
        for f in stats["failed"][:5]:
            log.info("    FAIL %s", f)
        npv.assert_basis_integrity(root, syms[:50])
    return 0


if __name__ == "__main__":
    sys.exit(main())
