"""Weekly guarded refresh — keeps the live meter live, or fails loudly.

Owner decision 2026-08-13: the dashboard is a LIVE METER, not a static study
snapshot. This script is the refresh path plus the guard layer that the vault
session discipline requires of any unattended automation ("no unattended agent
without a guard layer"). It is scheduled by Task Scheduler as
"breadth-thrust-signal weekly refresh" (Saturday 07:00 SGT, before the 08:00
vendor gauge guard so that guard cross-checks a fresh panel), via
scripts/run_weekly_refresh.bat, logging to data_local/refresh.log.

Steps, in order — any failure stops the run BEFORE anything is committed:

1. Depth gate (norgate mode — the default since the 2026-09-02 cutover): NDU
   readiness, store age, $SPX reach and the delisted-archive floor
   (check_depth) — the ways the extended window could silently shorten or
   re-acquire survivorship bias. The output guards then additionally pin the
   payload provider tag and the 1990-12-28 window start.
   In --provider csp1 mode (the flagged fallback) this step is the ROSTER
   SYNC instead. Copy ../breadth-thrust-etf/data/constituents_csp1.json (the
   point-in-time CSP1 snapshots that repo's local refresh maintains) over our
   copy, but only after validating it: it must parse, carry at least as many
   snapshots as ours, and extend at least as far. A missing or invalid source
   is a warning, not a failure — the pipeline forward-fills the last roster —
   but a roster older than ROSTER_MAX_AGE_DAYS is a hard failure, because a
   long-static roster quietly reintroduces the survivorship drift the
   point-in-time design exists to remove.
2. Pipeline. python scripts/pipeline.py (full fetch + rebuild).
3. Output guards (check_payload): the rebuilt signals.json must be current to
   within MAX_SESSION_LAG completed NYSE sessions, the study window must have
   extended with the data (a frozen window with fresh prices is the failure
   mode a naive freshness check misses), survivorship_bias must still be
   False, and the valid-constituent count must clear the pipeline's own floor.
4. Tests. python -m pytest tests/ -q must pass.
5. Publish. Commit data/signals.json + docs/index.html +
   data/constituents_csp1.json as "Weekly refresh YYYY-MM-DD" and push, with
   a backlog-aware retry (an earlier failed push must not hide behind a later
   no-change week).

Failure semantics: exit 1, a Windows toast via ~/.claude/hooks/notify.ps1 if
present, and NO commit — the deployed page keeps its last good build, whose
own client-side staleness banner (template.html renderStaleness) turns amber
after 9 calendar days. fleet_watch.json carries the heartbeat row on the
"Weekly refresh" commit, so a silently dead schedule breaches within a week.

Dates: all calendar arithmetic goes through pandas_market_calendars / pandas.
Python datetime months are 1-indexed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ROSTER = DATA / "constituents_csp1.json"
SIGNALS = DATA / "signals.json"
DEFAULT_SOURCE_ROSTER = ROOT.parent / "breadth-thrust-etf" / "data" / "constituents_csp1.json"

MAX_SESSION_LAG = 3        # completed NYSE sessions the as-of may trail by
ROSTER_MAX_AGE_DAYS = 45   # hard stop: a roster this stale is survivorship drift
TRACKED_OUTPUTS = ["data/signals.json", "docs/index.html", "data/constituents_csp1.json",
                   "data/state.json"]

# --- Norgate provider mode (build 2026-08-13 per the scope memo; the schtask
# --- wrapper flipped to --provider norgate at the 2026-09-02 cutover and the
# --- CLI default followed the same day on owner instruction) ---------------
DEFAULT_PROVIDER = "norgate"         # csp1 stays selectable as the flagged fallback
NORGATE_WINDOW_START = "1990-12-28"  # deterministic: 252-session burn-in from
                                     # the 1990-01-02 membership start; drift
                                     # here means silent history loss
NDU_MAX_AGE_DAYS = 7                 # NDU updates daily when the machine is on
NORGATE_MIN_DELISTED_DB = 15000      # US Equities Delisted symbol floor
                                     # (measured 21,104 on 2026-08-13)
NORGATE_REACH = "1991-01-01"         # $SPX first bar must be on/before this


def log(msg: str) -> None:
    print(f"[refresh] {msg}", flush=True)


def toast(title: str, msg: str) -> None:
    ps = Path.home() / ".claude" / "hooks" / "notify.ps1"
    if not ps.exists():
        return
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps),
         "-Title", title, "-Message", msg],
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Step 1 — roster sync
# ---------------------------------------------------------------------------


def validate_roster(src: dict, cur: dict) -> tuple[bool, str]:
    """A replacement roster must be a superset in time: at least as many
    snapshots, extending at least as far, every snapshot non-empty."""
    try:
        s_snaps, c_snaps = src["snapshots"], cur["snapshots"]
    except (KeyError, TypeError):
        return False, "source has no snapshots key"
    if not isinstance(s_snaps, dict) or not s_snaps:
        return False, "source snapshots empty"
    if len(s_snaps) < len(c_snaps):
        return False, f"source has fewer snapshots ({len(s_snaps)} < {len(c_snaps)})"
    if max(s_snaps) < max(c_snaps):
        return False, f"source ends earlier ({max(s_snaps)} < {max(c_snaps)})"
    if any(not s.get("tickers") for s in s_snaps.values()):
        return False, "a source snapshot has no tickers"
    return True, "ok"


def sync_roster(source: Path) -> str:
    """Return the last snapshot date in force after the sync attempt."""
    cur = json.loads(ROSTER.read_text(encoding="utf-8"))
    if not source.exists():
        log(f"roster source missing ({source}) — keeping current roster")
        return max(cur["snapshots"])
    try:
        src = json.loads(source.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log(f"roster source unreadable ({e}) — keeping current roster")
        return max(cur["snapshots"])
    ok, why = validate_roster(src, cur)
    if not ok:
        log(f"roster source rejected: {why} — keeping current roster")
        return max(cur["snapshots"])
    if max(src["snapshots"]) > max(cur["snapshots"]) or len(src["snapshots"]) > len(cur["snapshots"]):
        shutil.copyfile(source, ROSTER)
        log(f"roster synced: {len(src['snapshots'])} snapshots to {max(src['snapshots'])}")
    else:
        log("roster already current")
    return max(json.loads(ROSTER.read_text(encoding='utf-8'))["snapshots"])


# ---------------------------------------------------------------------------
# Step 1 (norgate mode) — depth gate, replacing the roster sync
# ---------------------------------------------------------------------------


def ndu_age_days(ndu_time_str: str, now_utc: datetime) -> int:
    """Whole days between NDU's last database update and now (UTC).

    All arithmetic through pandas Timestamps — the NDU stamp carries a +08:00
    offset and hand-rolled offset maths is exactly the class of date bug the
    vault rules exist to prevent.
    """
    import pandas as pd

    ndu = pd.Timestamp(ndu_time_str)
    if ndu.tzinfo is None:
        ndu = ndu.tz_localize("Asia/Singapore")  # NDU stamps local machine time
    now = pd.Timestamp(now_utc)
    if now.tzinfo is None:
        now = now.tz_localize("UTC")
    return max(0, (now - ndu.tz_convert("UTC")).days)


def check_depth(probe: dict) -> list[str]:
    """Pure depth-gate verdict on a collected probe. Empty list = pass.

    Fires when NDU is down, the store is stale, the index history has lost
    reach, or the delisted archive has thinned — each a way the extended
    window could silently shorten or re-acquire survivorship bias.
    """
    fails: list[str] = []
    if not probe.get("ready"):
        fails.append(f"NDU not ready: {probe.get('ready_detail')}")
        return fails  # nothing below is meaningful without NDU
    age = probe.get("ndu_age_days")
    if age is None or age > NDU_MAX_AGE_DAYS:
        fails.append(f"NDU store is {age} days old (max {NDU_MAX_AGE_DAYS})")
    first = probe.get("spx_first")
    if not first or first > NORGATE_REACH:
        fails.append(f"$SPX history starts {first} — reach lost (bar {NORGATE_REACH})")
    n = probe.get("delisted_db_count") or 0
    if n < NORGATE_MIN_DELISTED_DB:
        fails.append(
            f"delisted archive holds {n} symbols (floor {NORGATE_MIN_DELISTED_DB}) "
            f"— survivorship would silently return"
        )
    return fails


def collect_depth_probe(now_utc: datetime) -> dict:
    """Live NDU probe feeding check_depth. Import-heavy, so isolated here."""
    import norgatedata as nd

    sys.path.insert(0, str(ROOT / "scripts"))
    import norgate_provider as npv

    r = npv.readiness()
    probe: dict = {"ready": r.ok, "ready_detail": r.detail if not r.ok else None}
    if not r.ok:
        return probe
    probe["ndu_age_days"] = ndu_age_days(npv.ndu_update_time(), now_utc)
    spx = nd.price_timeseries(
        "$SPX",
        stock_price_adjustment_setting=nd.StockPriceAdjustmentType.NONE,
        padding_setting=nd.PaddingType.NONE,
        timeseriesformat="pandas-dataframe",
    )
    probe["spx_first"] = str(spx.index.min().date())
    probe["delisted_db_count"] = len(nd.database_symbols("US Equities Delisted"))
    return probe


# ---------------------------------------------------------------------------
# Step 3 — output guards
# ---------------------------------------------------------------------------


def nyse_session_lag(asof: str, now_utc: datetime) -> int:
    """Completed NYSE sessions strictly after the as-of date, as of now."""
    import pandas_market_calendars as mcal
    nyse = mcal.get_calendar("NYSE")
    sched = nyse.schedule(start_date=asof, end_date=now_utc.date())
    completed = sched[sched["market_close"] <= now_utc]
    return max(0, len(completed.index) - 1)  # exclude the as-of session itself


def check_payload(payload: dict, now_utc: datetime, roster_last: str,
                  lag_fn=nyse_session_lag, provider: str = DEFAULT_PROVIDER) -> list[str]:
    """Return the list of guard failures (empty means publishable).

    norgate mode (deployed since 2026-09-02, and the default here so that a
    caller who omits the provider gets the stricter set and fails LOUD on a
    csp1 payload rather than passing it) swaps the roster-age check (no
    roster is involved) for two pins: the payload must self-identify as the
    norgate-pit layer, and the study window must open at NORGATE_WINDOW_START
    — a later start is silent history loss, the failure a naive freshness
    check cannot see. csp1 mode is the pre-cutover guard set, retained
    byte-for-byte for the fallback.
    """
    fails: list[str] = []
    cur = payload.get("current", {})
    asof = cur.get("as_of")
    if not asof:
        return ["payload has no current.as_of"]
    lag = lag_fn(asof, now_utc)
    if lag > MAX_SESSION_LAG:
        fails.append(f"as_of {asof} lags {lag} completed NYSE sessions (max {MAX_SESSION_LAG})")
    wend = (payload.get("study", {}).get("window", {}) or {}).get("end")
    if wend != asof:
        fails.append(f"study window end {wend} != as_of {asof} — window did not extend with the data")
    if payload.get("survivorship_bias") is not False:
        fails.append("survivorship_bias is not False — point-in-time membership was not applied")
    q = payload.get("data_quality", {}) or {}
    floor = q.get("min_valid_constituents")
    vc = cur.get("valid_count")
    if floor is not None and (vc is None or vc < floor):
        fails.append(f"valid_count {vc} below floor {floor}")
    if provider == "norgate":
        if q.get("provider") != "norgate-pit":
            fails.append(f"payload provider {q.get('provider')!r} is not 'norgate-pit' — wrong layer built")
        wstart = (payload.get("study", {}).get("window", {}) or {}).get("start")
        if wstart != NORGATE_WINDOW_START:
            fails.append(
                f"study window start {wstart} != {NORGATE_WINDOW_START} — history silently shortened"
            )
    else:
        roster_age = (now_utc.date() - datetime.strptime(roster_last, "%Y-%m-%d").date()).days
        if roster_age > ROSTER_MAX_AGE_DAYS:
            fails.append(f"roster last snapshot {roster_last} is {roster_age} days old (max {ROSTER_MAX_AGE_DAYS})")
    return fails


# ---------------------------------------------------------------------------
# Step 5 — publish
# ---------------------------------------------------------------------------


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=check)


def publish(today: str, no_push: bool) -> None:
    porcelain = git("status", "--porcelain", "--", *TRACKED_OUTPUTS).stdout.strip()
    if porcelain:
        git("add", "--", *TRACKED_OUTPUTS)
        git("commit", "-q", "-m", f"Weekly refresh {today}")
        log("committed")
    else:
        log("no output changes to commit")
    if no_push:
        log("push skipped (--no-push)")
        return
    # Backlog-aware: push whenever local is ahead, not only when this run
    # committed — an earlier failed push must not hide behind a quiet week.
    git("fetch", "-q", "origin", check=False)
    ahead = git("rev-list", "--count", "origin/master..HEAD", check=False).stdout.strip()
    if porcelain or (ahead.isdigit() and int(ahead) > 0):
        for attempt in range(3):
            r = git("push", "-q", "origin", "master", check=False)
            if r.returncode == 0:
                log("pushed")
                return
            log(f"push attempt {attempt + 1} failed: {r.stderr.strip()[:200]}")
            time.sleep(20)
        raise RuntimeError("git push failed after 3 attempts")


# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-roster", default=str(DEFAULT_SOURCE_ROSTER))
    ap.add_argument("--no-push", action="store_true", help="build and guard, do not push")
    ap.add_argument("--provider", choices=("csp1", "norgate"), default=DEFAULT_PROVIDER,
                    help="data layer for the rebuild: norgate (deployed since "
                         "2026-09-02, the default: depth gate + provider and "
                         "window-start pins) or csp1 (the flagged fallback: "
                         "roster sync + roster-age guard)")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    try:
        if args.provider == "norgate":
            depth_fails = check_depth(collect_depth_probe(now))
            if depth_fails:
                raise RuntimeError("depth gate failed: " + " | ".join(depth_fails))
            log("depth gate clean")
            roster_last = None
        else:
            roster_last = sync_roster(Path(args.source_roster))

        log("running pipeline")
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "pipeline.py"),
             "--provider", args.provider],
            cwd=ROOT,
        )
        if r.returncode != 0:
            raise RuntimeError(f"pipeline.py exited {r.returncode}")

        payload = json.loads(SIGNALS.read_text(encoding="utf-8"))
        fails = check_payload(payload, now, roster_last, provider=args.provider)
        if fails:
            raise RuntimeError("guards failed: " + " | ".join(fails))
        log(f"guards clean — as_of {payload['current']['as_of']}, "
            f"{payload['data_quality'].get('used_constituents')} constituents")

        log("running tests")
        t = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"], cwd=ROOT)
        if t.returncode != 0:
            raise RuntimeError("pytest failed — not publishing")

        # STATE_CONTRACT emission for the private consumer. Deliberately AFTER
        # the guards and tests, and deliberately unable to fail this run: the
        # meter is the product, the emission is a convenience for one private
        # reader, and a convenience must never be able to withhold the product.
        # emit_state.emit() never raises — see its module docstring for why the
        # isolation is written down here rather than provided by a separate
        # workflow, as it is for the five sibling emitters.
        # The import is inside the try as well: emit() cannot raise, but an
        # ImportError from a missing or broken module would otherwise fall into
        # the outer handler and withhold the publish — the precise failure this
        # whole block exists to prevent.
        try:
            import emit_state
            if not emit_state.emit(log=log):
                log("state emission failed — publishing the meter regardless")
        except Exception as exc:  # noqa: BLE001 — never let a convenience block the product
            log(f"state emission unavailable ({type(exc).__name__}: {exc}) — "
                "publishing the meter regardless")

        publish(today, args.no_push)
        log("done")
        return 0
    except Exception as e:  # noqa: BLE001 — one funnel: log, toast, fail loudly
        log(f"FAILED: {e}")
        toast("breadth-thrust-signal refresh FAILED", str(e)[:180])
        return 1


if __name__ == "__main__":
    sys.exit(main())
