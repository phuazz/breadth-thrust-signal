"""Fire-path tests for the weekly-refresh guard layer.

Every guard must demonstrably FIRE on the failure it exists to catch (the
sentiment-composite register-39 lesson: a guard whose firing path is untested
is scaffolding, not a guard). The NYSE lag function is injected so no test
touches the network or the market calendar.

Dates: Python datetime months are 1-indexed. Roster-age arithmetic gets the
two mandatory edge cases — one month boundary, one year boundary.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from weekly_refresh import ROSTER_MAX_AGE_DAYS, check_payload, validate_roster  # noqa: E402

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
ROSTER_FRESH = "2026-08-07"


def good_payload():
    return {
        "survivorship_bias": False,
        "current": {"as_of": "2026-08-12", "valid_count": 500},
        "study": {"window": {"end": "2026-08-12"}},
        "data_quality": {"min_valid_constituents": 350},
    }


def lag0(asof, now):
    return 0


def test_clean_payload_passes():
    assert check_payload(good_payload(), NOW, ROSTER_FRESH, lag_fn=lag0) == []


def test_fires_on_stale_asof():
    fails = check_payload(good_payload(), NOW, ROSTER_FRESH, lag_fn=lambda a, n: 5)
    assert any("lags 5" in f for f in fails)


def test_fires_on_frozen_window():
    p = good_payload()
    p["study"]["window"]["end"] = "2026-05-29"  # fresh prices, frozen study window
    fails = check_payload(p, NOW, ROSTER_FRESH, lag_fn=lag0)
    assert any("did not extend" in f for f in fails)


def test_fires_on_survivorship_flag():
    p = good_payload()
    p["survivorship_bias"] = True
    fails = check_payload(p, NOW, ROSTER_FRESH, lag_fn=lag0)
    assert any("survivorship" in f for f in fails)


def test_fires_on_thin_panel():
    p = good_payload()
    p["current"]["valid_count"] = 100
    fails = check_payload(p, NOW, ROSTER_FRESH, lag_fn=lag0)
    assert any("below floor" in f for f in fails)


def test_fires_on_old_roster():
    fails = check_payload(good_payload(), NOW, "2026-06-01", lag_fn=lag0)
    assert any("roster" in f for f in fails)


def test_roster_age_month_boundary_no_fire():
    # 2026-01-31 -> 2026-03-01 is 29 days (2026 is not a leap year): inside 45.
    now = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    p = good_payload()
    p["current"]["as_of"] = "2026-02-27"
    p["study"]["window"]["end"] = "2026-02-27"
    assert check_payload(p, now, "2026-01-31", lag_fn=lag0) == []


def test_roster_age_year_boundary_fires():
    # 2026-11-01 -> 2027-01-02 is 62 days: crosses the year and must fire.
    now = datetime(2027, 1, 2, 12, 0, tzinfo=timezone.utc)
    p = good_payload()
    p["current"]["as_of"] = "2026-12-31"
    p["study"]["window"]["end"] = "2026-12-31"
    fails = check_payload(p, now, "2026-11-01", lag_fn=lag0)
    assert any(str(ROSTER_MAX_AGE_DAYS) in f for f in fails)


def _roster(dates):
    return {"snapshots": {d: {"tickers": ["A", "B"]} for d in dates}}


def test_validate_roster_accepts_superset():
    ok, _ = validate_roster(_roster(["2026-05-29", "2026-08-07"]), _roster(["2026-05-29"]))
    assert ok


def test_validate_roster_rejects_shrink():
    ok, why = validate_roster(_roster(["2026-08-07"]), _roster(["2026-05-22", "2026-05-29"]))
    assert not ok and "fewer" in why


def test_validate_roster_rejects_backdated():
    ok, why = validate_roster(
        _roster(["2026-04-03", "2026-04-10"]), _roster(["2026-05-22", "2026-05-29"])
    )
    assert not ok


def test_validate_roster_rejects_empty_snapshot():
    src = _roster(["2026-05-29", "2026-08-07"])
    src["snapshots"]["2026-08-07"]["tickers"] = []
    ok, why = validate_roster(src, _roster(["2026-05-29"]))
    assert not ok and "no tickers" in why
