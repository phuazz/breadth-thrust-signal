"""WS10 thrust-subconditions: the study-only High transport (spec data.high_basis_study_cache).

The frozen ``norgate_provider`` pulls Close and Volume only, so the labelled intraday-high sensitivity of S-D3
reads the ``High`` field from a separate, study-only cache written here: ``price_timeseries`` on the
TOTALRETURN basis, ``PaddingType.NONE``, no ``start_date`` (passing one silently truncates history), the High
column kept beside Close (Close only for the smoke check), full-symbol keys, and parquet footer provenance in
the same form as the live cache. The cache sits under ``C:/dev/.norgate-store/breadth-thrust-signal-ws10``,
outside the repository and never under the live meter's root; this module refuses to write anywhere else.
Descriptive use only (P0-8): a shortfall records the sensitivity NOT_RUN and does not stop the run.

    python scripts/ws10_high_cache.py --pull     pull every ever-member, then the smoke check

Python months are 1-indexed (January == 1). Date arithmetic goes through pandas only.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import norgate_provider as npv  # noqa: E402  (read-only)
import ws10_subconditions as ws  # noqa: E402

log = logging.getLogger("ws10.high")

FIELD = "High"


def study_root() -> Path:
    sp = ws.load_spec()
    root = Path(ws.get(sp, "data.high_basis_study_cache.cache_root"))
    live = Path(ws.get(sp, "data.cache_root"))
    if root.resolve() == live.resolve() or live.resolve() in root.resolve().parents:
        raise RuntimeError(f"the study-only High cache {root} must not sit under the live meter's root {live}")
    return root


def basis() -> str:
    b = ws.get(ws.load_spec(), "data.high_basis_study_cache.basis")
    if b != npv.CLOSE_BASIS:
        raise RuntimeError(f"High basis {b} is not the panel's close basis {npv.CLOSE_BASIS}")
    return b


def _path(root: Path, symbol: str) -> Path:
    return root / f"basis={basis()}" / f"{npv._safe(symbol)}.parquet"


def _pull(symbol: str) -> pd.DataFrame:
    import norgatedata as nd

    df = nd.price_timeseries(
        symbol,
        stock_price_adjustment_setting=getattr(nd.StockPriceAdjustmentType, basis()),
        padding_setting=nd.PaddingType.NONE,
        timeseriesformat="pandas-dataframe",
    )
    return df[[FIELD, "Close"]]


def _write(path: Path, df: pd.DataFrame, symbol: str, ndu_time: str) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df.reset_index(), preserve_index=False)
    meta = {
        b"symbol": symbol.encode(),
        b"basis": basis().encode(),
        b"field": FIELD.encode(),
        b"rows": str(len(df)).encode(),
        b"first_date": str(df.index.min().date()).encode(),
        b"last_date": str(df.index.max().date()).encode(),
        b"pulled_at_utc": datetime.now(timezone.utc).isoformat().encode(),
        b"ndu_last_database_update_time": ndu_time.encode(),
        b"purpose": b"WS10 study-only cache; the labelled intraday-high sensitivity of S-D3; descriptive only",
    }
    table = table.replace_schema_metadata({**(table.schema.metadata or {}), **meta})
    pq.write_table(table, path, compression="snappy")


def _read(path: Path) -> tuple[pd.DataFrame, dict]:
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(path)
    meta = {k.decode(): v.decode() for k, v in (pf.schema_arrow.metadata or {}).items() if k != b"pandas"}
    if meta.get("basis") != basis() or meta.get("field") != FIELD:
        raise ValueError(f"footer mismatch in {path}: basis {meta.get('basis')!r}, field {meta.get('field')!r}")
    df = pf.read().to_pandas()
    date_col = df.columns[0]
    return df.set_index(pd.DatetimeIndex(df[date_col])).drop(columns=[date_col]), meta


def pull(symbols: list[str]) -> dict:
    root = study_root()
    ndu_time = npv.ndu_update_time()
    stats = {"pulled": 0, "failed": []}
    for i, sym in enumerate(symbols):
        try:
            df = _pull(sym)
        except Exception as e:  # noqa: BLE001
            stats["failed"].append((sym, str(e)))
            continue
        if df.empty:
            stats["failed"].append((sym, "empty"))
            continue
        _write(_path(root, sym), df, sym, ndu_time)
        stats["pulled"] += 1
        if (i + 1) % 200 == 0:
            log.info("  %d of %d pulled", i + 1, len(symbols))
    log.info("pulled %d High series (%d failures) into %s", stats["pulled"], len(stats["failed"]), root)
    return stats


def smoke(symbol: str) -> dict:
    """One symbol's High is at or above its Close on every session it carries."""
    df, meta = _read(_path(study_root(), symbol))
    d = df.dropna()
    bad = int((d[FIELD] < d["Close"]).sum())
    return {"symbol": symbol, "sessions": int(len(d)), "high_below_close_sessions": bad, "pass": bad == 0,
            "footer_basis": meta.get("basis"), "footer_field": meta.get("field")}


def load_high_panel(symbols: list[str]) -> tuple[pd.DataFrame | None, dict]:
    """The High panel (dates x full symbols) from the study-only cache, with the P0-8 facts."""
    root = study_root()
    cols, stamps, missing = {}, set(), []
    for sym in symbols:
        p = _path(root, sym)
        if not p.exists():
            missing.append(sym)
            continue
        df, meta = _read(p)
        cols[sym] = df[FIELD]
        stamps.add(meta.get("ndu_last_database_update_time", ""))
    note = {"cache_root": str(root), "basis": basis(), "field": FIELD, "symbols": len(cols),
            "missing": len(missing), "ndu_times": sorted(stamps)}
    if not cols:
        note["smoke_pass"] = False
        return None, note
    first = next(iter(cols))
    sm = smoke(first)
    note["smoke"] = sm
    note["smoke_pass"] = bool(sm["pass"])
    return pd.DataFrame(cols).sort_index(), note


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull", action="store_true", required=True)
    ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    r = npv.readiness()
    if not r.ok:
        raise SystemExit(f"Norgate not ready: {r.detail}")
    syms = npv.resolve_universe()
    npv.assert_no_base_ticker_collision(syms)
    stats = pull(syms)
    sm = smoke(syms[0]) if stats["pulled"] else {"pass": False}
    log.info("smoke check: %s", sm)
    for sym, err in stats["failed"][:20]:
        log.warning("  failed %s: %s", sym, err)
    return 0 if sm.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
