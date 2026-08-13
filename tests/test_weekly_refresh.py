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

from weekly_refresh import (  # noqa: E402
    NDU_MAX_AGE_DAYS,
    NORGATE_MIN_DELISTED_DB,
    ROSTER_MAX_AGE_DAYS,
    check_depth,
    check_payload,
    ndu_age_days,
    validate_roster,
)

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


# --- norgate provider mode ---------------------------------------------------


def norgate_payload():
    return {
        "survivorship_bias": False,
        "current": {"as_of": "2026-08-12", "valid_count": 503},
        "study": {"window": {"start": "1990-12-28", "end": "2026-08-12"}},
        "data_quality": {"min_valid_constituents": 400, "provider": "norgate-pit"},
    }


def test_norgate_clean_payload_passes_without_roster():
    assert check_payload(norgate_payload(), NOW, None, lag_fn=lag0, provider="norgate") == []


def test_norgate_fires_on_wrong_provider_tag():
    p = norgate_payload()
    p["data_quality"]["provider"] = "csp1-yahoo"
    fails = check_payload(p, NOW, None, lag_fn=lag0, provider="norgate")
    assert any("wrong layer" in f for f in fails)


def test_norgate_fires_on_shortened_history():
    p = norgate_payload()
    p["study"]["window"]["start"] = "1994-03-01"
    fails = check_payload(p, NOW, None, lag_fn=lag0, provider="norgate")
    assert any("silently shortened" in f for f in fails)


def test_norgate_mode_ignores_roster_age():
    # No roster is involved post-cutover; an ancient date must not fire.
    assert check_payload(norgate_payload(), NOW, "2020-01-01", lag_fn=lag0, provider="norgate") == []


def good_probe():
    return {"ready": True, "ndu_age_days": 1, "spx_first": "1950-01-03",
            "delisted_db_count": 21104}


def test_depth_clean_passes():
    assert check_depth(good_probe()) == []


def test_depth_fires_on_ndu_down():
    fails = check_depth({"ready": False, "ready_detail": "NDU not running"})
    assert fails and "not ready" in fails[0]


def test_depth_fires_on_stale_store():
    p = good_probe()
    p["ndu_age_days"] = NDU_MAX_AGE_DAYS + 5
    fails = check_depth(p)
    assert any("days old" in f for f in fails)


def test_depth_fires_on_lost_reach():
    p = good_probe()
    p["spx_first"] = "1994-06-01"
    fails = check_depth(p)
    assert any("reach lost" in f for f in fails)


def test_depth_fires_on_thin_delisted_archive():
    p = good_probe()
    p["delisted_db_count"] = 1371  # the trial-tier count — survivorship returned
    fails = check_depth(p)
    assert any("survivorship" in f for f in fails)
    assert str(NORGATE_MIN_DELISTED_DB) in fails[0]


def test_ndu_age_month_boundary():
    # 2026-01-31 23:00 SGT is 15:00 UTC; to 2026-02-02 00:00 UTC is 33h -> 1 day.
    assert ndu_age_days("2026-01-31 23:00:00+08:00",
                        datetime(2026, 2, 2, 0, 0, tzinfo=timezone.utc)) == 1


def test_ndu_age_year_boundary():
    # 2026-12-30 08:00 SGT is 00:00 UTC Dec 30; to 2027-01-03 00:00 UTC is 4 days.
    assert ndu_age_days("2026-12-30 08:00:00+08:00",
                        datetime(2027, 1, 3, 0, 0, tzinfo=timezone.utc)) == 4


def test_ndu_age_naive_stamp_read_as_sgt():
    # A naive NDU stamp is machine-local (SGT): 22:00 -> 14:00 UTC; +26h -> 1 day.
    assert ndu_age_days("2026-08-12 22:00:00",
                        datetime(2026, 8, 13, 16, 0, tzinfo=timezone.utc)) == 1


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
