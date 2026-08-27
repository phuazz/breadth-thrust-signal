"""Tests for scripts/emit_state.py — the STATE_CONTRACT emission.

IMPORTANT: this repo runs `pytest tests/ -q` inside the weekly guarded refresh,
BEFORE it publishes. A failure here withholds the meter. Everything below is
therefore pure and synthetic: no filesystem reads of real data, no network, no
dependence on the date the suite happens to run.

What is guarded, given the emission is a copy:

  1. It must not emit a guess. A renamed or null key stops the emission.
  2. It must not emit a score and a dimension list that disagree. Those are two
     views of the same fact, and a mismatch means a wrong meter reading would be
     published with a plausible description attached.
  3. emit() must NEVER raise. The five sibling emitters each get their isolation
     from running in a separate workflow; this repo has none, so weekly_refresh
     calls emit() directly and the guarantee has to live in the function. A
     convenience must not be able to withhold the product.
  4. It must not churn the repo with a no-op.

Python datetime months are 1-indexed (January = 1).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import emit_state  # noqa: E402

REQUIRED = {"as_of", "state", "value", "zone", "role", "horizon",
            "evidence_grade", "licence", "action_hint", "source_file"}
OPTIONAL = {"computed_at", "cadence"}
SIGNAL = "conviction_meter"


def _dims(on=("d3",)):
    labels = {"d1": "Advance/Decline thrust", "d2": "% above 50d MA thrust",
              "d3": "New-high / new-low thrust", "d4": "Up-volume thrust"}
    return {k: {"label": v, "on": k in on} for k, v in labels.items()}


def _signals(score=1.0, on=("d3",), as_of="2026-08-20",
             generated="2026-08-21T23:01:43.218791+00:00"):
    return {
        "generated_utc": generated,
        "current": {"as_of": as_of, "n_dimensions": 4, "score": score,
                    "dimensions": _dims(on), "data_ok": True, "valid_count": 503},
        "last_signal": {"date": "2025-05-05", "score": 3, "days_since": 324},
    }


@pytest.fixture
def store(monkeypatch):
    box = {"d": _signals()}
    monkeypatch.setattr(emit_state, "load_signals", lambda: box["d"])
    return box


# --- the score and its dimensions must agree --------------------------------

@pytest.mark.parametrize("score,on,zone", [
    (0.0, (), "dimensions on: none"),
    (1.0, ("d3",), "dimensions on: d3"),
    (2.0, ("d1", "d3"), "dimensions on: d1, d3"),
    (4.0, ("d1", "d2", "d3", "d4"), "dimensions on: d1, d2, d3, d4"),
])
def test_the_state_is_the_count_and_the_zone_lists_them(store, score, on, zone):
    store["d"] = _signals(score=score, on=on)
    s = emit_state.build()["signals"][SIGNAL]
    assert s["state"] == str(int(score))
    assert s["zone"] == zone
    assert s["value"] == score


def test_a_score_disagreeing_with_its_dimensions_is_refused(store):
    """Two views of the same fact. A mismatch means a wrong meter reading would
    be published with a plausible description attached."""
    store["d"] = _signals(score=3.0, on=("d3",))
    with pytest.raises(emit_state.EmitError, match="disagree"):
        emit_state.build()


def test_the_dimension_list_is_sorted_not_dict_ordered(store):
    """An unordered list would churn the emission between runs and show on the
    consumer as a divergence that is not one."""
    store["d"] = _signals(score=2.0, on=("d4", "d1"))
    assert emit_state.build()["signals"][SIGNAL]["zone"] == "dimensions on: d1, d4"


def test_an_empty_dimension_block_is_refused(store):
    store["d"]["current"]["dimensions"] = {}
    with pytest.raises(emit_state.EmitError, match="empty"):
        emit_state.build()


# --- the score itself -------------------------------------------------------

def test_a_fractional_score_is_refused_not_truncated(store):
    """The score COUNTS confirmed dimensions, so 1.5 is not a rounding question
    — it means the pipeline produced something this does not understand.
    Truncating would publish a plausible integer over a broken input."""
    store["d"] = _signals(score=1.5, on=("d3",))
    with pytest.raises(emit_state.EmitError, match="fractional"):
        emit_state.build()


def test_a_score_above_the_meter_range_is_refused(store):
    store["d"] = _signals(score=5.0, on=("d1", "d2", "d3", "d4"))
    with pytest.raises(emit_state.EmitError, match="range"):
        emit_state.build()


def test_a_boolean_score_is_refused(store):
    """bool subclasses int, so True would otherwise pass a numeric check and
    emit as the state '1'."""
    store["d"] = _signals(score=True, on=("d3",))
    with pytest.raises(emit_state.EmitError, match="expected a number"):
        emit_state.build()


def test_a_zero_score_emits_rather_than_being_treated_as_missing(store):
    """0 is falsy. A truthiness check anywhere in the chain would drop the most
    common reading the meter has."""
    store["d"] = _signals(score=0.0, on=())
    assert emit_state.build()["signals"][SIGNAL]["state"] == "0"


# --- shape ------------------------------------------------------------------

def test_emits_exactly_the_one_signal(store):
    assert set(emit_state.build()["signals"]) == {SIGNAL}


def test_the_block_carries_the_required_fields_and_nothing_unknown(store):
    block = emit_state.build()["signals"][SIGNAL]
    assert REQUIRED <= set(block), f"missing {REQUIRED - set(block)}"
    assert set(block) <= REQUIRED | OPTIONAL, f"unknown {set(block) - REQUIRED - OPTIONAL}"


def test_cadence_is_manual(store):
    """This repo has no CI. The consumer badges the row MANUAL and shows its
    measured age rather than a freshness tick it has not earned; the emission
    repeats that so the consumer does not have to know why."""
    assert emit_state.build()["signals"][SIGNAL]["cadence"] == "manual"


def test_no_score_or_weight_field_is_emitted(store):
    banned = {"score", "weight", "composite", "rank"}
    assert not (banned & set(emit_state.build()["signals"][SIGNAL]))


def test_the_envelope_names_its_version_and_source(store):
    p = emit_state.build()
    assert p["contract_version"] == "1"
    assert p["emitted_by"] == "breadth-thrust-signal"


@pytest.mark.parametrize("pointer", ["as_of", "score", "dimensions"])
def test_a_missing_current_key_stops_the_emission(store, pointer):
    del store["d"]["current"][pointer]
    with pytest.raises(emit_state.EmitError, match=pointer):
        emit_state.build()


def test_a_missing_generated_utc_stops_the_emission(store):
    del store["d"]["generated_utc"]
    with pytest.raises(emit_state.EmitError, match="generated_utc"):
        emit_state.build()


def test_a_null_as_of_is_refused(store):
    store["d"]["current"]["as_of"] = None
    with pytest.raises(emit_state.EmitError, match="null"):
        emit_state.build()


# --- emit() must never raise ------------------------------------------------

def test_emit_returns_false_rather_than_raising_on_bad_data(store, monkeypatch, tmp_path):
    """weekly_refresh calls this directly, with no separate process to absorb a
    failure. It must degrade, not raise."""
    monkeypatch.setattr(emit_state, "OUT", tmp_path / "state.json")
    store["d"] = _signals(score=9.0, on=())
    lines = []
    assert emit_state.emit(log=lines.append) is False
    assert any("FAILED" in line for line in lines)


def test_emit_returns_false_rather_than_raising_on_an_unexpected_error(monkeypatch, tmp_path):
    """Not just EmitError: anything at all."""
    monkeypatch.setattr(emit_state, "OUT", tmp_path / "state.json")
    monkeypatch.setattr(emit_state, "load_signals",
                        lambda: (_ for _ in ()).throw(RuntimeError("disk on fire")))
    lines = []
    assert emit_state.emit(log=lines.append) is False
    assert any("disk on fire" in line for line in lines)


def test_emit_returns_false_rather_than_raising_when_the_write_fails(store, monkeypatch, tmp_path):
    """A read-only or missing directory must not take the refresh down."""
    monkeypatch.setattr(emit_state, "OUT", tmp_path / "no-such-dir" / "state.json")
    lines = []
    assert emit_state.emit(log=lines.append) is False
    assert any("could not write" in line for line in lines)


def test_a_failed_emit_leaves_the_previous_file_untouched(store, monkeypatch, tmp_path):
    out = tmp_path / "state.json"
    out.write_text('{"previous": "emission"}', encoding="utf-8")
    monkeypatch.setattr(emit_state, "OUT", out)
    store["d"] = _signals(score=9.0, on=())
    assert emit_state.emit(log=lambda _: None) is False
    assert json.loads(out.read_text(encoding="utf-8")) == {"previous": "emission"}


def test_emit_succeeds_and_writes(store, monkeypatch, tmp_path):
    out = tmp_path / "state.json"
    monkeypatch.setattr(emit_state, "OUT", out)
    assert emit_state.emit(log=lambda _: None) is True
    assert json.loads(out.read_text(encoding="utf-8"))["signals"][SIGNAL]["state"] == "1"


def test_an_unchanged_state_is_not_rewritten(store, monkeypatch, tmp_path):
    out = tmp_path / "state.json"
    monkeypatch.setattr(emit_state, "OUT", out)
    assert emit_state.emit(log=lambda _: None) is True
    first = out.read_text(encoding="utf-8")
    assert emit_state.emit(log=lambda _: None) is True
    assert out.read_text(encoding="utf-8") == first, "unchanged state was rewritten"


def test_a_changed_state_IS_rewritten(store, monkeypatch, tmp_path):
    out = tmp_path / "state.json"
    monkeypatch.setattr(emit_state, "OUT", out)
    assert emit_state.emit(log=lambda _: None) is True
    store["d"] = _signals(score=2.0, on=("d1", "d3"))
    assert emit_state.emit(log=lambda _: None) is True
    assert json.loads(out.read_text(encoding="utf-8"))["signals"][SIGNAL]["state"] == "2"
