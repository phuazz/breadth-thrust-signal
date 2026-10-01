"""WS10 (thrust-subconditions): the fixture must be able to FAIL.

These tests run WITHOUT the study engine. They regenerate the planted panel from the committed
generator, check it against the committed hash and expected values, run the committed wrong engine
(``tests/mutants/ws10_wrong.py``) and assert that the expectations reject every mutation, then
assert that the reference implementation (``tests/make_ws10_fixture.py``) passes. If a future fixture
change lets any mutation pass, the fixture has gone blind and the change is refused. The raw sha256
of the frozen spec is pinned here as well, so the pin holds before the engine exists.

Python months are 1-indexed. Date arithmetic goes through pandas only.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
FIX = TESTS / "fixtures" / "ws10"
SPEC = ROOT / "spec" / "ws10_prereg_spec.json"
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(ROOT / "scripts"))

import make_ws10_fixture as ref  # noqa: E402
import compute_breadth as cb  # noqa: E402
import forward_returns as fr  # noqa: E402

FROZEN_SPEC_SHA256 = "fb5b61ac9d0b3fb5c907b188a5fc3a293658d3ae0ac5e722df091c901a97aafb"

EXACT_THRESHOLD_DATES = {"S-D3": "2020-04-07", "S-D2": "2021-02-10"}   # 220 of 400 = 55.0; 360 of 400 = 90.0


def _load_mutant():
    spec = importlib.util.spec_from_file_location("ws10_wrong", TESTS / "mutants" / "ws10_wrong.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def fx():
    close, volume = ref.planted()
    expected = json.loads((FIX / "expected.json").read_text(encoding="utf-8"))
    panels = cb.build_panels(close, volume)
    before = cb.compute_composite(panels)
    return close, volume, panels, before, expected


def _dates(xs) -> list[str]:
    return [str(pd.Timestamp(x).date()) for x in xs]


# ---------------------------------------------------------------- the frozen spec and the fixture

def test_spec_hash_matches_frozen_value():
    assert hashlib.sha256(SPEC.read_bytes()).hexdigest() == FROZEN_SPEC_SHA256
    assert b"\r\n" not in SPEC.read_bytes(), "the spec must stay LF so its hash is stable across checkouts"


def test_fixture_regenerates_from_the_committed_generator(fx):
    close, volume, panels, before, expected = fx
    assert ref.panel_sha256(close) == expected["panel_sha256"]
    assert close.shape == (expected["n_sessions"], expected["n_names"])
    assert not close.isna().any().any(), "the planted panel carries no missing close"
    fresh = ref.expected(close, volume)
    assert fresh == expected, "expected.json is stale: regenerate with python tests/make_ws10_fixture.py"


def test_reference_values_are_the_planted_ones(fx):
    close, volume, panels, before, expected = fx
    sp = ref.spec()
    below = int(sp["candidates"]["shared"]["below_sessions"])
    for member in ("S-D3", "S-D2"):
        share = ref.share_share = ref.ref_share(close, member, sp)
        thr = float(sp["candidates"][member]["threshold_pct"])
        d = EXACT_THRESHOLD_DATES[member]
        assert share.loc[pd.Timestamp(d)] == thr, f"{member} must sit EXACTLY on {thr} at {d}"
        assert expected["shares"][member][d] == thr
        ev = ref.ref_fresh_events(share, thr, before["data_ok"], below)
        assert _dates(ev) == expected["fresh_events"][member]
        assert d in expected["fresh_events"][member]
    # the burn-in episode crosses 55 and is refused
    assert expected["shares"]["S-D3"]["2019-04-10"] == 60.0
    assert "2019-04-10" not in expected["fresh_events"]["S-D3"]
    assert pd.Timestamp("2019-04-10") < pd.Timestamp(expected["first_data_ok_session"])


# ---------------------------------------------------------------- share mutants

@pytest.mark.parametrize("member, fn_name", [
    ("S-D3", "share_sd3_window19"),
    ("S-D3", "share_sd3_strict_new_high"),
    ("S-D2", "share_sd2_sma11"),
    ("S-D2", "share_sd2_exclude_today"),
])
def test_share_mutants_change_a_fresh_event_date(fx, member, fn_name):
    close, volume, panels, before, expected = fx
    wrong = _load_mutant()
    sp = ref.spec()
    thr = float(sp["candidates"][member]["threshold_pct"])
    below = int(sp["candidates"]["shared"]["below_sessions"])
    share = getattr(wrong, fn_name)(close)
    ev = ref.ref_fresh_events(share, thr, before["data_ok"], below)
    assert _dates(ev) != expected["fresh_events"][member], f"fixture is blind to {fn_name}"


def test_division_first_share_misses_an_exact_threshold(fx):
    # 220 / 400 * 100 is 55.00000000000001 while 100 * 220 / 400 is 55.0; at 360 / 400 the two forms happen
    # to coincide, so the drill requires rejection at at least one planted exact-threshold date.
    close, volume, panels, before, expected = fx
    wrong = _load_mutant()
    rejected = []
    for member, d in EXACT_THRESHOLD_DATES.items():
        got = float(wrong.share_division_first(close, member).loc[pd.Timestamp(d)])
        if got != expected["shares"][member][d]:
            rejected.append((member, got))
    assert rejected, "the division-first share reproduces every planted exact threshold value"


# ---------------------------------------------------------------- fresh-event mutants

@pytest.mark.parametrize("member, kwargs", [
    ("S-D3", {"below_sessions": 5}),
    ("S-D2", {"below_sessions": 5}),
    ("S-D3", {"below_sessions": 19}),
    ("S-D3", {"admit_burn_in": True}),
    ("S-D3", {"strict": True}),
    ("S-D2", {"strict": True}),
])
def test_fresh_event_mutants_are_rejected(fx, member, kwargs):
    close, volume, panels, before, expected = fx
    wrong = _load_mutant()
    sp = ref.spec()
    thr = float(sp["candidates"][member]["threshold_pct"])
    share = ref.ref_share(close, member, sp)
    ev = wrong.fresh_events_wrong(share, thr, before["data_ok"], **kwargs)
    assert _dates(ev) != expected["fresh_events"][member], f"fixture is blind to {kwargs} on {member}"


def test_exactly_twenty_below_fires_and_nineteen_does_not():
    cal = pd.bdate_range("2021-01-04", periods=60)
    ok = pd.Series(True, index=cal)
    sp = ref.spec()
    below = int(sp["candidates"]["shared"]["below_sessions"])
    twenty = pd.Series([60.0] * 5 + [50.0] * 20 + [60.0] + [50.0] * 34, index=cal)
    nineteen = pd.Series([60.0] * 5 + [50.0] * 19 + [60.0] + [50.0] * 35, index=cal)
    broken = twenty.copy()
    broken.iloc[10] = np.nan
    assert _dates(ref.ref_fresh_events(twenty, 55.0, ok, below)) == [str(cal[25].date())]
    assert _dates(ref.ref_fresh_events(nineteen, 55.0, ok, below)) == []
    assert _dates(ref.ref_fresh_events(broken, 55.0, ok, below)) == [], "a NaN inside the run must break it"
    wrong = _load_mutant()
    assert _dates(wrong.fresh_events_wrong(nineteen, 55.0, ok, below_sessions=19)) != []


# ---------------------------------------------------------------- composite mutants (H-M)

def test_composite_mutants_change_the_added_set(fx):
    close, volume, panels, before, expected = fx
    wrong = _load_mutant()
    sp = ref.spec()
    extras = {}
    for member in ("S-D3", "S-D2"):
        c = sp["candidates"][member]
        fire = ref.ref_daily_fire(ref.ref_share(close, member, sp), float(c["threshold_pct"]))
        fire.name = member
        extras[c["dimension"]] = fire
    after_ref = ref.ref_composite_with_members(panels, extras, cb=cb)
    assert _dates(ref.ref_added_events(before, after_ref, 2)) == expected["h_m"]["ge2"]["added"]
    want_counts = expected["h_m"]["after_dim_true_counts"]
    assert {d: int(after_ref[d].sum()) for d in want_counts} == want_counts
    assert {d: int(before[d].sum()) for d in want_counts} == expected["h_m"]["before_dim_true_counts"]
    blind = []
    for label, kw in (("replace", {"replace": True}), ("memory1", {"memory": 1})):
        after = wrong.composite_wrong(panels, extras, cb, **kw)
        same_events = (_dates(ref.ref_added_events(before, after, 2)) == expected["h_m"]["ge2"]["added"]
                       and _dates(ref.ref_fresh_at(after, 2)) == expected["h_m"]["ge2"]["after"])
        same_dims = {d: int(after[d].sum()) for d in want_counts} == want_counts
        if same_events and same_dims:
            blind.append(label)
    assert not blind, f"fixture is blind to these composite mutations: {blind}"


def test_reference_composite_equals_the_engine_when_nothing_is_admitted(fx):
    close, volume, panels, before, expected = fx
    off = pd.Series(False, index=close.index, name="off")
    same = ref.ref_composite_with_members(panels, {"d2": off, "d3": off}, cb=cb)
    pd.testing.assert_frame_equal(same[before.columns], before)


# ---------------------------------------------------------------- redundancy, clusters, lag, null

def _cofire_unit():
    cal = pd.bdate_range("2020-01-02", periods=200)
    fires = pd.DatetimeIndex([cal[50], cal[100], cal[150]])
    cand = pd.DatetimeIndex([cal[50], cal[53], cal[55], cal[106], cal[180]])   # offsets 0, 3, 5, 6, 30
    return cal, fires, cand


def test_cofire_window_mutants_are_rejected():
    cal, fires, cand = _cofire_unit()
    assert ref.ref_cofire_share(cand, fires, cal, 5) == 60.0
    wrong = _load_mutant()
    assert wrong.cofire_share_wrong(cand, fires, cal, 4) != 60.0
    assert wrong.cofire_share_wrong(cand, fires, cal, 6) != 60.0


def test_cluster_gap_mutant_is_rejected(fx):
    close, volume, panels, before, expected = fx
    kc = expected["cluster_known_case"]
    assert ref.ref_cluster_ids(pd.to_datetime(kc["dates"]), 63) == kc["ids"] == [0, 0, 1]
    assert ref.ref_cluster_ids(pd.to_datetime(kc["dates_b"]), 63) == kc["ids_b"] == [0, 0, 0]
    wrong = _load_mutant()
    assert wrong.cluster_ids_gap62(pd.to_datetime(kc["dates_b"])) != kc["ids_b"], "a 63-day gap must not split"


def test_unlagged_forward_join_is_rejected():
    cal = pd.bdate_range("2019-01-02", periods=60)
    spx = pd.Series(100.0 + np.arange(60), index=cal)
    k, h = 30, fr.HORIZONS["1w"]
    honest = spx.iloc[k + 1 + h] / spx.iloc[k + 1] - 1.0
    comp = pd.DataFrame({"n_dimensions": 0, "event": False}, index=cal)
    comp.loc[cal[k], ["n_dimensions", "event"]] = [1, True]
    row = fr.conditional_table(comp, spx, thresholds=(1,), events_only=True)
    row = row[(row["threshold"] == 1) & (row["horizon"] == "1w")].iloc[0]
    assert abs(row["median_ret"] - honest) < 1e-12
    wrong = _load_mutant()
    assert abs(wrong.forward_stats_lag0(pd.DatetimeIndex([cal[k]]), spx, h)["median"] - honest) > 1e-9


def test_null_count_mutant_is_rejected():
    cal = pd.bdate_range("2019-01-02", periods=600)
    events = pd.DatetimeIndex([cal[300], cal[306], cal[314], cal[450]])
    wrong = _load_mutant()
    sets = wrong.null_sets_count_minus_one(events, cal[251:], 20, [19901228, 0])
    assert all(len(s) != len(events) for s in sets), "the count mutant must not be count-matched"
