"""Norgate point-in-time data layer for the breadth-thrust engine (WS7).

Replaces the Yahoo + weekly-CSP1-snapshot path with Norgate Data, which serves
daily survivorship-free S&P 500 membership from 1990-01-02 together with full
price history for delisted members. Specified in
``C:\\dev\\KICKOFF_ws7-norgate-history-extension.md`` (sign-off 2026-08-01).

Two adjustment bases are pulled per symbol, and the split matters:

  - ``TOTALRETURN`` close -> direction, moving averages, 52-week highs/lows
  - ``NONE`` volume       -> the up-volume ratio

Norgate adjusts volume on the TOTALRETURN basis (it matches raw on 0.6% of
AAPL rows), so the project rule "volume is unadjusted" is only satisfied by
pulling the second basis explicitly. Mixing them is silent-wrongness #2 in the
spec and ``assert_basis_integrity`` exists to catch it.

Symbols are keyed on the FULL Norgate symbol throughout, never the base
ticker. 44 base tickers in the ever-member universe map to more than one
Norgate symbol -- ``C`` is Citigroup but ``C-199811`` is Chrysler, ``BAC`` vs
``BAC-199809``, ``AAL`` vs ``AAL-199702``. Keying on the base ticker splices
two unrelated companies into one series with no exception raised. That is
silent-wrongness #1 and ``assert_no_base_ticker_collision`` guards it.

Cache layout deliberately mirrors ``KICKOFF_norgate-store.md`` so it migrates
into the shared store without rework:

    <root>/basis=<BASIS>/<SYMBOL>.parquet

with provenance in the parquet footer rather than a sidecar, so it is written
atomically with the data and cannot desync from it.

**The cache lives outside this repository by default.** This repo is public
and the Norgate licence is personal-use-only, so vendor series values must
never be committed anywhere. The default root sits under ``C:\\dev\\`` where the
vault ``.gitignore`` (``/*``) already makes it structurally uncommittable —
that is a stronger guarantee than a ``.gitignore`` entry, which ``git add -f``
overrides. Override with ``BREADTH_NORGATE_CACHE`` if needed.

Refresh is always full-replace, never watermark-append. An adjusted series is
restated whenever a new distribution occurs -- back-adjustment rescales the
entire prior history -- so appending only a new tail would splice two
adjustment bases at an invisible seam.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

# Outside the repo by design — see the module docstring on licence scope.
DEFAULT_CACHE_ROOT = Path(r"C:\dev\.norgate-store\breadth-thrust-signal")


def default_cache_root() -> Path:
    return Path(os.environ.get("BREADTH_NORGATE_CACHE", DEFAULT_CACHE_ROOT))


def cache_root_for(universe: "Universe") -> Path:
    """Per-universe cache root.

    The S&P 500 keeps the original location so the filed WS7 run continues to
    resolve without moving 275MB of vendor data; additional universes get
    siblings. All of them sit under ``C:\\dev\\`` where the vault ignore rule
    makes them structurally uncommittable.
    """
    base = default_cache_root()
    return base if universe.slug == SP500.slug else base.parent / f"breadth-{universe.slug}"

INDEX_NAME = "S&P 500"
WATCHLIST = "S&P 500 Current & Past"
BENCHMARK = "$SPX"


@dataclass(frozen=True)
class Universe:
    """An index whose point-in-time breadth can be rebuilt independently.

    WS8 uses the non-S&P-500 entries for cross-sectional replication: the S&P
    500 window is spent, so a genuinely fresh test of the thrust mechanism has
    to come from a different cross-section. Breadth measured on a universe
    trades that universe's own index, so the test is of the mechanism rather
    than of a cross-market signal.
    """

    slug: str
    index_name: str
    watchlist: str
    benchmark: str
    note: str = ""


SP500 = Universe("sp500", "S&P 500", "S&P 500 Current & Past", "$SPX")
R2000 = Universe(
    "r2000", "Russell 2000", "Russell 2000 Current & Past", "$RUT",
    "Independent small-cap breadth; ~11k ever-members.",
)
SP600 = Universe(
    "sp600", "S&P SmallCap 600", "S&P SmallCap 600 Current & Past", "$SML",
    "Second small-cap read. $SML starts 1993-12-31, so the effective window "
    "opens ~1995 after the 252-day burn-in — shorter than the others.",
)
UNIVERSES = {u.slug: u for u in (SP500, R2000, SP600)}

CLOSE_BASIS = "TOTALRETURN"   # direction, MAs, 52-week high/low
VOLUME_BASIS = "NONE"         # up-volume ratio (raw, unadjusted)

# NDU is a local store; a cache built against a materially older database than
# the one now installed is a silent-staleness risk (spec 2, lifted from
# breadth-thrust-etf). Warn beyond this many days of drift.
STALENESS_WARN_DAYS = 10

_UNSAFE = re.compile(r'[<>:"/\\|?*]')


def _safe(symbol: str) -> str:
    """Windows-safe filename for a Norgate symbol ($SPX, BRK.B, AAL-199702)."""
    return _UNSAFE.sub("_", symbol)


def base_ticker(symbol: str) -> str:
    """Strip Norgate's delisting suffix: 'AAL-199702' -> 'AAL', 'AAL' -> 'AAL'."""
    head, _, tail = symbol.rpartition("-")
    return head if head and tail.isdigit() else symbol


# ---------------------------------------------------------------------------
# Readiness gate
# ---------------------------------------------------------------------------


@dataclass
class Readiness:
    ok: bool
    detail: dict


def readiness() -> Readiness:
    """Feed readiness: NDU up, both equity databases present and current."""
    import norgatedata as nd

    detail: dict = {"norgatedata_version": nd.__version__}
    if not nd.status():
        return Readiness(False, {**detail, "error": "NDU not running"})

    dbs = nd.databases()
    for required in ("US Equities", "US Equities Delisted"):
        if required not in dbs:
            return Readiness(False, {**detail, "error": f"missing database: {required}"})
        detail[required] = str(nd.last_database_update_time(required))

    # Delisted must be non-empty, else survivorship silently returns.
    n_delisted = sum(
        1 for s in nd.watchlist_symbols(WATCHLIST) if base_ticker(s) != s
    )
    detail["delisted_members"] = n_delisted
    if n_delisted == 0:
        return Readiness(False, {**detail, "error": "no delisted members resolved"})

    return Readiness(True, detail)


def ndu_update_time() -> str:
    import norgatedata as nd

    return str(nd.last_database_update_time("US Equities"))


# ---------------------------------------------------------------------------
# Universe and membership
# ---------------------------------------------------------------------------


def resolve_universe(universe: "Universe" = None) -> list[str]:
    """Every symbol that has ever been a member, full Norgate keys."""
    import norgatedata as nd

    u = universe or SP500
    return list(nd.watchlist_symbols(u.watchlist))


def membership_mask(
    symbols: list[str], calendar: pd.DatetimeIndex, universe: "Universe" = None
) -> pd.DataFrame:
    """Daily point-in-time membership, dates x symbols, True where a member.

    Norgate's flag transitions on the EFFECTIVE date, not the announcement date
    -- verified at build step 0 of WS7 against TSLA (2020-12-21), META
    (2013-12-23) and BRK.B (2010-02-16), all three landing on the documented
    effective date, corroborated by the 35%/39% Monday clustering of adds and
    drops that an effective-date convention produces. So no shift is applied
    here; applying one would introduce the look-ahead it was meant to remove.
    """
    import norgatedata as nd

    u = universe or SP500
    cols = {}
    for sym in symbols:
        try:
            ser = nd.index_constituent_timeseries(
                sym, u.index_name, timeseriesformat="pandas-dataframe"
            )
        except Exception as e:  # noqa: BLE001
            log.warning("  membership unavailable for %s: %s", sym, e)
            continue
        cols[sym] = ser.iloc[:, 0].astype(bool)
    mask = pd.DataFrame(cols).reindex(calendar).fillna(False).astype(bool)
    return mask


# ---------------------------------------------------------------------------
# Price cache
# ---------------------------------------------------------------------------


def _cache_path(root: Path, basis: str, symbol: str) -> Path:
    return root / f"basis={basis}" / f"{_safe(symbol)}.parquet"


def _pull(symbol: str, basis: str) -> pd.DataFrame:
    """Pull one symbol on one basis. No ``start_date`` -- passing one silently
    truncates history and reads as a subscription limit (the trap documented in
    ``em-rotation-lab/scripts/step0_coverage.py:27-28``). Store full depth,
    slice on read."""
    import norgatedata as nd

    df = nd.price_timeseries(
        symbol,
        stock_price_adjustment_setting=getattr(nd.StockPriceAdjustmentType, basis),
        padding_setting=nd.PaddingType.NONE,
        timeseriesformat="pandas-dataframe",
    )
    return df[["Close", "Volume"]]


def _write(path: Path, df: pd.DataFrame, symbol: str, basis: str, ndu_time: str) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df.reset_index(), preserve_index=False)
    meta = {
        b"symbol": symbol.encode(),
        b"basis": basis.encode(),
        b"rows": str(len(df)).encode(),
        b"first_date": str(df.index.min().date()).encode(),
        b"last_date": str(df.index.max().date()).encode(),
        b"pulled_at_utc": datetime.now(timezone.utc).isoformat().encode(),
        b"ndu_last_database_update_time": ndu_time.encode(),
    }
    table = table.replace_schema_metadata({**(table.schema.metadata or {}), **meta})
    pq.write_table(table, path, compression="snappy")


def _read(path: Path, basis: str) -> pd.DataFrame:
    """Read a cached series, asserting the footer basis matches the request.

    Raises rather than returns on mismatch -- serving TOTALRETURN prices to a
    caller that asked for NONE is exactly the failure this layer exists to
    prevent, and a wrong answer is worse than no answer.
    """
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(path)
    meta = pf.schema_arrow.metadata or {}
    got = meta.get(b"basis", b"").decode()
    if got != basis:
        raise ValueError(
            f"basis mismatch in {path}: footer says {got!r}, caller asked {basis!r}"
        )
    df = pf.read().to_pandas()
    date_col = df.columns[0]
    return df.set_index(pd.DatetimeIndex(df[date_col])).drop(columns=[date_col])


def refresh(root: Path, symbols: list[str], bases=(CLOSE_BASIS, VOLUME_BASIS)) -> dict:
    """Full-replace every symbol on every basis. Never appends -- see module
    docstring on restatement."""
    ndu_time = ndu_update_time()
    stats = {"pulled": 0, "failed": []}
    for basis in bases:
        for sym in symbols:
            try:
                df = _pull(sym, basis)
            except Exception as e:  # noqa: BLE001
                stats["failed"].append((sym, basis, str(e)))
                continue
            if df.empty:
                stats["failed"].append((sym, basis, "empty"))
                continue
            _write(_cache_path(root, basis, sym), df, sym, basis, ndu_time)
            stats["pulled"] += 1
    log.info("  refreshed %d series (%d failures)", stats["pulled"], len(stats["failed"]))
    return stats


# ---------------------------------------------------------------------------
# Panel assembly
# ---------------------------------------------------------------------------


def build_panel(root: Path, symbols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Assemble (adj_close, volume) as aligned dates x FULL-SYMBOL frames.

    ``adj_close`` is TOTALRETURN close; ``volume`` is NONE-basis raw volume.
    """
    close_cols, vol_cols = {}, {}
    for sym in symbols:
        cp = _cache_path(root, CLOSE_BASIS, sym)
        vp = _cache_path(root, VOLUME_BASIS, sym)
        if not cp.exists() or not vp.exists():
            continue
        close_cols[sym] = _read(cp, CLOSE_BASIS)["Close"]
        vol_cols[sym] = _read(vp, VOLUME_BASIS)["Volume"]

    close = pd.DataFrame(close_cols).sort_index()
    volume = pd.DataFrame(vol_cols).sort_index().reindex_like(close)
    return close, volume


def benchmark_series(root: Path, universe: "Universe" = None) -> pd.Series:
    """Index close on the unadjusted basis, for the forward-return study."""
    u = universe or SP500
    return _read(_cache_path(root, VOLUME_BASIS, u.benchmark), VOLUME_BASIS)["Close"]


# ---------------------------------------------------------------------------
# Integrity guards (spec section 4)
# ---------------------------------------------------------------------------


def assert_no_base_ticker_collision(symbols: list[str]) -> None:
    """Silent-wrongness #1: two companies sharing one base ticker.

    The panel is keyed on full Norgate symbols, so collisions are harmless --
    but only for as long as that holds. This asserts the invariant explicitly
    so that any future change to bare-ticker keying fails loudly here rather
    than quietly splicing Chrysler onto Citigroup.
    """
    if len(set(symbols)) != len(symbols):
        raise ValueError("duplicate full symbols in universe")
    seen: dict[str, list[str]] = {}
    for s in symbols:
        seen.setdefault(base_ticker(s), []).append(s)
    collisions = {b: v for b, v in seen.items() if len(v) > 1}
    log.info(
        "  base-ticker collisions: %d base tickers -> %d symbols (harmless "
        "while keyed on full symbols)",
        len(collisions),
        sum(len(v) for v in collisions.values()),
    )


def assert_basis_integrity(root: Path, symbols: list[str], sample: int = 50) -> None:
    """Silent-wrongness #2: close and volume drawn from different series.

    Checks the two bases carry identical date indices per symbol, so the join
    in ``build_panel`` aligns direction with the volume that actually traded
    that day.
    """
    checked = 0
    for sym in symbols:
        cp = _cache_path(root, CLOSE_BASIS, sym)
        vp = _cache_path(root, VOLUME_BASIS, sym)
        if not (cp.exists() and vp.exists()):
            continue
        ci = _read(cp, CLOSE_BASIS).index
        vi = _read(vp, VOLUME_BASIS).index
        if not ci.equals(vi):
            raise ValueError(
                f"{sym}: {CLOSE_BASIS} and {VOLUME_BASIS} date indices differ "
                f"({len(ci)} vs {len(vi)} rows) -- direction and volume would "
                f"be misaligned"
            )
        checked += 1
        if checked >= sample:
            break
    log.info("  basis integrity: %d symbols verified aligned", checked)


def check_staleness(root: Path, symbols: list[str]) -> dict:
    """Silent-wrongness (spec 2, staleness): cache built against an older NDU."""
    import pyarrow.parquet as pq

    live = ndu_update_time()
    stamps = set()
    for sym in symbols[:100]:
        p = _cache_path(root, CLOSE_BASIS, sym)
        if not p.exists():
            continue
        meta = pq.ParquetFile(p).schema_arrow.metadata or {}
        stamps.add(meta.get(b"ndu_last_database_update_time", b"").decode())
    out = {"live_ndu": live, "cache_ndu": sorted(stamps)}
    if stamps and live not in stamps:
        drift = (pd.Timestamp(live) - max(pd.Timestamp(s) for s in stamps if s)).days
        out["drift_days"] = drift
        if drift > STALENESS_WARN_DAYS:
            log.warning(
                "  CACHE IS STALE: built against NDU %s, live is %s (%d days)",
                max(stamps), live, drift,
            )
    return out
