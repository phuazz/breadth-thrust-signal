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

FROZEN_SPEC_SHA256 = "b805afaf4f02988bf9d1e7b83d0f7ed4d41696a327b610371d8b78e936b13f33"

EXACT_THRESHOLD_DATES = {"S-D3": "2020-04-08", "S-D2": "2021-02-10"}   # 440 of 800 = 55.0; 720 of 800 = 90.0


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


@pytest.fixture(scope="module")
def unit():
    sp = ref.spec()
    ui = ref.unit_index()
    return sp, ui, ref.unit_valid(ui), ref.unit_events(ui)


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
    assert close[ref.LATE_ENTRANT].first_valid_index() == pd.Timestamp(expected["late_entrant"]["first_close_session"])
    gap = close[ref.INTERIOR_GAP]
    assert gap.loc[expected["interior_gap"]["sessions"][0]: expected["interior_gap"]["sessions"][1]].isna().all()
    fresh = ref.expected(close, volume)
    assert fresh == expected, "expected.json is stale: regenerate with python tests/make_ws10_fixture.py"


def test_reference_values_are_the_planted_ones(fx):
    close, volume, panels, before, expected = fx
    sp = ref.spec()
    below = int(sp["candidates"]["shared"]["below_sessions"])
    for member in ("S-D3", "S-D2"):
        share = ref.ref_share(close, member, sp)
        thr = float(sp["candidates"][member]["threshold_pct"])
        d = EXACT_THRESHOLD_DATES[member]
        assert share.loc[pd.Timestamp(d)] == thr, f"{member} must sit EXACTLY on {thr} at {d}"
        assert expected["shares"][member][d] == thr
        ev = ref.ref_fresh_events(share, thr, before["data_ok"], below)
        assert _dates(ev) == expected["fresh_events"][member]
        assert d in expected["fresh_events"][member]
    # the burn-in episode crosses both thresholds and is refused
    first_ok = pd.Timestamp(expected["first_data_ok_session"])
    assert expected["shares"]["S-D3"]["2019-03-27"] >= 55.0 and expected["shares"]["S-D2"]["2019-03-27"] >= 90.0
    assert pd.Timestamp("2019-03-27") < first_ok
    assert "2019-03-27" not in expected["fresh_events"]["S-D3"] + expected["fresh_events"]["S-D2"]
    # the planted gaps leave the name out of the denominator: 799 members on those sessions
    assert expected["shares"]["S-D3"]["2020-05-06"] == 100.0 * 480 / 799
    assert expected["shares"]["S-D3"]["2020-03-11"] == 100.0 * 40 / 799


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


@pytest.mark.parametrize("fn_name", ["share_ffill", "share_denominator_present"])
def test_gap_and_entrant_mutants_change_a_planted_share(fx, fn_name):
    close, volume, panels, before, expected = fx
    wrong = _load_mutant()
    for member in ("S-D3", "S-D2"):
        got = getattr(wrong, fn_name)(close, member)
        want = expected["shares"][member]
        differs = [d for d, v in want.items() if v is not None and not np.isclose(got.loc[pd.Timestamp(d)], v)]
        assert differs, f"fixture is blind to {fn_name} on {member}"


def test_division_first_share_misses_an_exact_threshold(fx):
    # 440 / 800 * 100 and 100 * 440 / 800 can differ in the last bit; the drill requires rejection at at
    # least one planted exact-threshold date, while the contract pins exact equality at both.
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
    ("S-D2", {"admit_burn_in": True}),
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

def _extras(close, sp):
    extras = {}
    for member in ("S-D3", "S-D2"):
        c = sp["candidates"][member]
        fire = ref.ref_daily_fire(ref.ref_share(close, member, sp), float(c["threshold_pct"]))
        extras[c["dimension"]] = fire
    return extras


def test_composite_mutants_change_the_added_set_or_the_or(fx):
    close, volume, panels, before, expected = fx
    wrong = _load_mutant()
    sp = ref.spec()
    extras = _extras(close, sp)
    after_ref = ref.ref_composite_with_members(panels, extras, cb=cb)
    assert _dates(ref.ref_added_events(before, after_ref, 2)) == expected["h_m"]["ge2"]["added"]
    assert _dates(ref.ref_removed_events(before, after_ref, 2)) == expected["h_m"]["ge2"]["removed"]
    want_counts = expected["h_m"]["after_dim_true_counts"]
    assert {d: int(after_ref[d].sum()) for d in want_counts} == want_counts
    assert {d: int(before[d].sum()) for d in want_counts} == expected["h_m"]["before_dim_true_counts"]
    assert int(after_ref["event"].sum()) == expected["h_m"]["after_event_count_all_sessions"]
    blind = []
    for label, kw in (("replace", {"replace": True}), ("memory1", {"memory": 1}), ("newly_on", {"newly_on_rule": True})):
        after = wrong.composite_wrong(panels, extras, cb, **kw)
        same_events = (_dates(ref.ref_added_events(before, after, 2)) == expected["h_m"]["ge2"]["added"]
                       and _dates(ref.ref_fresh_at(after, 2)) == expected["h_m"]["ge2"]["after"])
        same_dims = {d: int(after[d].sum()) for d in want_counts} == want_counts
        same_event_count = int(after["event"].sum()) == expected["h_m"]["after_event_count_all_sessions"]
        if same_events and same_dims and same_event_count:
            blind.append(label)
    assert not blind, f"fixture is blind to these composite mutations: {blind}"


def test_newly_on_rule_disagrees_on_the_planted_coincidence(fx):
    close, volume, panels, before, expected = fx
    wrong = _load_mutant()
    sp = ref.spec()
    extras = _extras(close, sp)
    after = ref.ref_composite_with_members(panels, extras, cb=cb)
    newly = wrong.composite_wrong(panels, extras, cb, newly_on_rule=True)
    disagree = _dates(after.index[after["event"].astype(bool) != newly["event"].astype(bool)])
    assert disagree == expected["h_m"]["event_rule_discriminating_sessions"]
    d = pd.Timestamp(disagree[0])
    assert not after.loc[d, "event"] and newly.loc[d, "event"]
    assert after.loc[d, "n_dimensions"] <= after["n_dimensions"].shift(1).loc[d], "a memory expired as the member switched on"


def test_fresh_at_without_the_data_ok_clause_admits_a_burn_in_event(fx):
    close, volume, panels, before, expected = fx
    wrong = _load_mutant()
    assert _dates(ref.ref_fresh_at(before, 2)) == expected["h_m"]["ge2"]["before"]
    got = _dates(wrong.fresh_at_without_data_ok(before, 2))
    assert got != expected["h_m"]["ge2"]["before"]
    for d in expected["h_m"]["ge2_events_inside_burn_in"]:
        assert d in got and d not in expected["h_m"]["ge2"]["before"]


def test_reference_composite_equals_the_engine_when_nothing_is_admitted(fx):
    close, volume, panels, before, expected = fx
    off = pd.Series(False, index=close.index, name="off")
    same = ref.ref_composite_with_members(panels, {"d2": off, "d3": off}, cb=cb)
    pd.testing.assert_frame_equal(same[before.columns], before)


# ---------------------------------------------------------------- redundancy, clusters, lag

def _cofire_unit():
    cal = pd.bdate_range("2020-01-02", periods=200)
    fires = pd.DatetimeIndex([cal[50], cal[100], cal[150]])
    # offsets relative to a fire: -3 (leads), +3 (lags), -5 (leads), +6 (lags, outside), +30 (outside)
    cand = pd.DatetimeIndex([cal[47], cal[53], cal[95], cal[106], cal[180]])
    return cal, fires, cand


def test_cofire_window_and_direction_mutants_are_rejected():
    cal, fires, cand = _cofire_unit()
    assert ref.ref_cofire_share(cand, fires, cal, 5) == 60.0
    wrong = _load_mutant()
    assert wrong.cofire_share_wrong(cand, fires, cal, 4) != 60.0
    assert wrong.cofire_share_wrong(cand, fires, cal, 6) != 60.0
    assert wrong.cofire_share_wrong(cand, fires, cal, 5, backward_only=True) == 20.0, "the leading candidates are the ones lost"


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
    assert abs(ref.ref_forward_stats(pd.DatetimeIndex([cal[k]]), spx, h)["median"] - honest) < 1e-12
    wrong = _load_mutant()
    assert abs(wrong.forward_stats_lag0(pd.DatetimeIndex([cal[k]]), spx, h)["median"] - honest) > 1e-9


# ---------------------------------------------------------------- the comparator on the unit path

def test_reference_null_matches_the_pinned_draws_and_statistics(fx, unit):
    close, volume, panels, before, expected = fx
    sp, ui, uv, ue = unit
    nu = expected["null_unit"]
    gap = int(sp["clusters"]["gap_calendar_days"])
    h = int(sp["horizons"]["sessions"]["3m"])
    assert _dates(ue) == nu["events"]
    assert len(ref.ref_complete_window_events(ue, ui, h)) == nu["n_complete"]
    sets = ref.ref_null_sets(ue, uv, ui, h, 3, [19901228, 0], gap)
    assert [_dates(s) for s in sets] == nu["first_three_draws_seed_0"]
    null = ref.ref_null_draws(ue, uv, ui, h, 300, [19901228, 0], gap)
    assert abs(null[:, 0].mean() - nu["null300_mean_win_rate"]) < 1e-12
    assert abs(null[:, 1].mean() - nu["null300_mean_median"]) < 1e-12
    treat = ref.ref_forward_stats(ue, ui, h)
    assert ref.ref_mc_p(treat["win_rate"], null[:, 0]) == nu["p_win_treatment"]
    assert ref.ref_mc_p(treat["median"], null[:, 1]) == nu["p_med_treatment"]


def test_null_count_mutant_is_rejected(unit):
    sp, ui, uv, ue = unit
    wrong = _load_mutant()
    sets = wrong.null_sets_count_minus_one(ue, uv, 20, [19901228, 0])
    assert all(len(s) != len(ue) for s in sets), "the count mutant must not be count-matched"


def test_power_mutants_are_rejected(fx, unit):
    close, volume, panels, before, expected = fx
    sp, ui, uv, ue = unit
    nu = expected["null_unit"]
    gap = int(sp["clusters"]["gap_calendar_days"])
    h = int(sp["horizons"]["sessions"]["3m"])
    alpha = float(sp["holm"]["alpha"])
    null = ref.ref_null_draws(ue, uv, ui, h, 300, [19901228, 0], gap)
    want10, want50 = nu["power_by_delta_pp"]["10.0"], nu["power_by_delta_pp"]["50.0"]
    assert ref.ref_power(ue, uv, ui, h, 10.0, null, 100, [19901228, 1000], gap, alpha, 3) == want10
    assert ref.ref_power(ue, uv, ui, h, 50.0, null, 100, [19901228, 1000], gap, alpha, 3) == want50 == 1.0
    assert 0.05 < want10 < 0.95
    wrong = _load_mutant()
    at_alpha = wrong.power_wrong(ref, ue, uv, ui, h, 10.0, null, 100, [19901228, 1000], gap, alpha, 3, at_alpha=True)
    assert at_alpha != want10, "a power scored at alpha instead of alpha/3 must differ at the mid-range delta"
    units = wrong.power_wrong(ref, ue, uv, ui, h, 50.0, null, 100, [19901228, 1000], gap, alpha, 3, wrong_units=True)
    assert units != want50, "a delta read in the wrong units must not saturate"


def test_self_drill_centring_leg_rejects_a_shifted_null(fx, unit):
    close, volume, panels, before, expected = fx
    sp, ui, uv, ue = unit
    nu = expected["null_unit"]
    gap = int(sp["clusters"]["gap_calendar_days"])
    h = int(sp["horizons"]["sessions"]["3m"])
    alpha = float(sp["holm"]["alpha"])
    wb, mb = float(sp["self_drill"]["win_band"]), float(sp["self_drill"]["median_band_pp"])
    null = ref.ref_null_draws(ue, uv, ui, h, 300, [19901228, 0], gap)
    got = ref.ref_self_drill(ue, uv, ui, h, null, 100, [19901228, 2000], gap, alpha, wb, mb)
    assert got["centring_pass"] and got == nu["self_drill"]
    shifted = null.copy()
    shifted[:, 0] += 0.2                       # a null drawn from the bull years only would centre like this
    assert not ref.ref_self_drill(ue, uv, ui, h, shifted, 100, [19901228, 2000], gap, alpha, wb, mb)["centring_pass"]
    shifted = null.copy()
    shifted[:, 1] += 0.03
    assert not ref.ref_self_drill(ue, uv, ui, h, shifted, 100, [19901228, 2000], gap, alpha, wb, mb)["centring_pass"]
