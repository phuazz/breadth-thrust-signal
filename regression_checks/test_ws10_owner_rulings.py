"""Post-freeze implementation checks; the frozen tests/ directory remains untouched.

Synthetic inputs only. Never invoke the runner entry point, load real data, or run a study.
Python months are 1-indexed. Date construction uses pandas; no manual date arithmetic.
"""

import ast
import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ws10_run as runner
import ws10_subconditions as ws


@pytest.mark.parametrize("start", ["2020-01-27", "2020-12-28"])
def test_ties_are_separate_and_partition_cofires_across_boundaries(start):
    cal = pd.bdate_range(start, periods=30)
    events = cal[[4, 12, 20, 27]]
    fires = cal[[2, 6, 12, 19, 29]]
    report = runner.cofire_report(events, fires, cal)
    assert report == {"before": 1, "same": 1, "after": 1, "tied": 1}
    assert sum(report.values()) == len(events)
    assert ws.cofire_share(events, fires, cal) == 100.0
    assert set(ws.cofire_split(events, fires, cal)) == {"before", "same", "after"}


def test_empty_seen_permission_does_not_admit_candidate_comparators():
    reg = ws.CandidateRegistry()
    empty = pd.DatetimeIndex([])
    nonempty = pd.DatetimeIndex([pd.Timestamp("2020-01-02")])
    reg.register("empty candidate", empty)
    reg.register("nonempty candidate", nonempty)
    reg.assert_comparator(empty, "before.early", seen=True)
    assert reg.checks[-1]["admitted"]
    with pytest.raises(ws.ComparatorMisuse):
        reg.assert_comparator(empty)
    with pytest.raises(ws.ComparatorMisuse):
        reg.assert_comparator(nonempty, seen=True)


@pytest.fixture
def isolated_runner(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "_git", lambda *args: "synthetic-revision")
    return ws.load_spec()


def test_start_claim_blocks_repeat_without_results(isolated_runner):
    spec = isolated_runner
    marker = runner.claim_full_run(spec)
    assert json.loads(marker.read_text())["state"] == "STARTED"
    assert not (runner.ROOT / spec["outputs"]["declared_cells"]).exists()
    with pytest.raises(runner.Stop):
        runner.claim_full_run(spec)


def test_exclusive_claim_blocks_a_race(isolated_runner, monkeypatch):
    spec = isolated_runner
    runner.claim_full_run(spec)
    # Simulate both invocations having passed the earlier existence check.
    monkeypatch.setattr(runner, "assert_full_not_started", lambda spec: None)
    with pytest.raises(runner.Stop, match="another full run"):
        runner.claim_full_run(spec)


def test_failed_marker_flush_still_blocks_retry(isolated_runner, monkeypatch):
    def fail_flush(_fd):
        raise OSError("synthetic flush failure")
    monkeypatch.setattr(runner.os, "fsync", fail_flush)
    with pytest.raises(OSError):
        runner.claim_full_run(isolated_runner)
    with pytest.raises(runner.Stop):
        runner.assert_full_not_started(isolated_runner)


@pytest.mark.parametrize("output", ["declared_cells", "full"])
def test_existing_outcome_output_blocks_without_marker(isolated_runner, output):
    path = runner.ROOT / isolated_runner["outputs"][output]
    path.parent.mkdir(parents=True)
    path.write_text("{}")
    with pytest.raises(runner.Stop):
        runner.assert_full_not_started(isolated_runner)


def test_step0_record_alone_does_not_consume_full_run(isolated_runner):
    runner._dump(runner.ROOT / isolated_runner["outputs"]["step0"], {"stopped": True})
    runner.assert_full_not_started(isolated_runner)
    assert not runner.full_start_marker(isolated_runner).exists()


@pytest.mark.parametrize("failure", [RuntimeError("placement exhausted"),
                                    ws.NonSessionDate("synthetic non-session bound"),
                                    IndexError("synthetic empty panel")])
def test_probe_exception_is_returned_as_a_stop(monkeypatch, failure):
    def fail():
        raise failure
    monkeypatch.setattr(runner, "frozen_hashes_in_tests", fail)
    stopped, sets = runner.step0(SimpleNamespace(spec=ws.load_spec()), {})
    assert stopped["stopped"]
    assert stopped["exception_type"] == type(failure).__name__
    assert stopped["stop_reason"] == str(failure)
    assert sets is None


def test_ws7_export_preserves_legacy_values_and_limits_horizons():
    spec = ws.load_spec()
    spec["ws7_read"]["n_boot"] = 9  # Synthetic regression only; never written to the frozen spec.
    cal = pd.bdate_range("2010-01-04", periods=700)
    px = pd.Series(100 * np.cumprod(1 + np.where(np.arange(700) % 2, .002, -.001)), index=cal)
    bounds = {"early": (cal[0], cal[349]), "late": (cal[350], cal[-1])}
    got = runner.ws7_baselines(SimpleNamespace(spec=spec, spx=px), bounds)
    for half, (lo, hi) in bounds.items():
        legacy = runner.fr.unconditional_baseline(px.loc[lo:hi], n_boot=9, block=21, seed=42)
        expected = legacy[legacy.horizon.isin(spec["horizons"]["sessions"])]
        pd.testing.assert_frame_equal(got[half], expected)
        assert set(got[half].horizon) == {"1m", "3m", "6m"}
    assert "truncated to the half" in runner.WS7_CONVENTION
    assert "never a gate" in runner.WS7_CONVENTION


def test_entrypoint_order_and_stop_branch_without_executing_it():
    tree = ast.parse(inspect.getsource(runner.main))
    calls = [(node.lineno, node.func.id) for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    first = lambda name: min(line for line, called in calls if called == name)
    assert first("assert_full_not_started") < first("load_real")
    assert first("_dump") < first("claim_full_run") < first("full_run")
    stop_branch = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                       and ast.unparse(node.test) == "args.step0 or s0['stopped']")
    assert isinstance(stop_branch.body[-1], ast.Return)
    text = ast.unparse(stop_branch)
    assert "out_results" not in text
    assert "claim_full_run" not in text
    assert "full_run(" not in text
