"""WS10 thrust-subconditions: the runner (Step 0 with FAIL_STOP, then the full run ONCE).

Executes the frozen registration ``PREREG_thrust-subconditions.md`` through ``scripts/ws10_subconditions.py``.
Every constant comes from ``spec/ws10_prereg_spec.json``. The live meter's cache is read as it is and never
refreshed or written; ``data/signals.json``, ``docs/`` and ``template.html`` are never touched.

    python scripts/ws10_run.py --step0     Step 0 only: the probes, power and the self-drill (random entries
                                           only); no candidate-conditional statistic; writes ws10_step0.json
    python scripts/ws10_run.py --full      Step 0 again, then, if nothing stopped, every cell of
                                           null.cell_order; refuses to run when results/ws10_results.json exists

Outputs: results/ws10_results.json (declared cells), results/ws10_full.json, results/ws10_step0.json,
results/ws10_manifest.json and an appended line in data_local/ws10_runs_log.jsonl. The results files carry
shares, counts, dates and return statistics only, never a per-symbol price.

Python months are 1-indexed (January == 1). Date arithmetic goes through pandas only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import compute_breadth as cb  # noqa: E402  (read-only)
import forward_returns as fr  # noqa: E402  (read-only)
import ws10_subconditions as ws  # noqa: E402

log = logging.getLogger("ws10")

RESULTS = ROOT / "results"
DATA_LOCAL = ROOT / "data_local"
FROZEN_PATHS = ("PREREG_thrust-subconditions.md", "spec/", "tests/")
STUDY_GLOB = re.compile(r"^scripts/ws10_[^/]*\.py$")
TEST_FILES_WITH_PIN = ("tests/test_ws10_contract.py", "tests/test_ws10_mutants.py")


class Stop(RuntimeError):
    """The FAIL_STOP exception: the run ends and the reason is filed."""


# ---------------------------------------------------------------- hashes, tree and guards

def spec_hash_or_stop(frozen: str) -> str:
    got = ws.spec_hash()
    if got != frozen:
        raise Stop(f"spec sha256 {got} differs from the frozen value {frozen}")
    return got


def frozen_hashes_in_tests() -> dict:
    """FROZEN_SPEC_SHA256 as written in the two frozen test files."""
    out = {}
    for rel in TEST_FILES_WITH_PIN:
        m = re.search(r'^FROZEN_SPEC_SHA256 = "([0-9a-f]{64})"', (ROOT / rel).read_text(encoding="utf-8"), re.M)
        if not m:
            raise Stop(f"FROZEN_SPEC_SHA256 not found in {rel}")
        out[rel] = m.group(1)
    return out


def check_engine_modules(spec: dict) -> dict:
    pinned = ws.get(spec, "engine.modules_sha256")
    got = {}
    for name, want in pinned.items():
        h = hashlib.sha256((SCRIPTS / name).read_bytes()).hexdigest()
        if h != want:
            raise Stop(f"engine module {name} sha256 {h} differs from the pinned {want}")
        got[name] = h
    return got


def _porcelain_paths(line: str) -> list[str]:
    body = line[3:] if len(line) > 3 else ""
    parts = body.split(" -> ") if " -> " in body else [body]
    return [p.strip().strip('"') for p in parts]


def _is_frozen(path: str) -> bool:
    p = path.replace("\\", "/")
    return any(p == f or (f.endswith("/") and p.startswith(f)) for f in FROZEN_PATHS) or bool(STUDY_GLOB.match(p))


def check_frozen_tree_clean(status_lines) -> None:
    for line in status_lines:
        if not line.strip():
            continue
        for p in _porcelain_paths(line):
            if _is_frozen(p):
                raise Stop(f"frozen or study file not clean against HEAD: {line.strip()}")


def event_set_guard(observed: dict, expected: dict) -> None:
    for k, want in expected.items():
        if k in ("source", "on_miss"):
            continue
        if k not in observed or observed[k] != want:
            raise Stop(f"event-set guard: {k} observed {observed.get(k)!r}, filed {want!r}")


def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False).stdout


def tree_and_tag() -> dict:
    status = [ln for ln in _git("status", "--porcelain").splitlines() if ln.strip()]
    check_frozen_tree_clean(status)
    tag_commit = _git("rev-parse", "prereg-freeze^{commit}").strip()
    if not tag_commit:
        raise Stop("tag prereg-freeze not found")
    r = subprocess.run(["git", "merge-base", "--is-ancestor", "prereg-freeze", "HEAD"], cwd=ROOT, check=False)
    if r.returncode != 0:
        raise Stop("tag prereg-freeze is not reachable from HEAD")
    return {"head": _git("rev-parse", "HEAD").strip(), "tag": "prereg-freeze", "tag_commit": tag_commit,
            "status_lines_outside_frozen_set": status}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- the panel

@dataclass
class Context:
    spec: dict
    close: pd.DataFrame                  # membership-masked TOTALRETURN close
    comp: pd.DataFrame                   # four-dimension composite (the before composite)
    panels: object
    spx: pd.Series                       # $SPX, NONE basis, its own calendar (the return series)
    mask_count: pd.Series
    ever_members: int
    data_quality: dict = field(default_factory=dict)
    high: pd.DataFrame | None = None     # membership-masked TOTALRETURN High (study-only cache), or None
    high_note: dict = field(default_factory=dict)
    provider: str = "norgate-pit"


def load_real(spec: dict) -> Context:
    """The panel from the live meter's cache WITHOUT refresh (norgate_provider.build_panel and
    membership_mask on the full-symbol universe), as the WS7 build and live_panel assemble it."""
    import norgate_provider as npv  # read-only

    root = npv.default_cache_root()
    if Path(root).resolve() != Path(ws.get(spec, "data.cache_root")).resolve():
        raise Stop(f"cache root {root} is not the registered {ws.get(spec, 'data.cache_root')}")
    if ws.get(spec, "data.refresh_cache") is not False:
        raise Stop("the spec must declare refresh_cache false")
    r = npv.readiness()
    if not r.ok:
        raise Stop(f"Norgate not ready: {r.detail}")
    syms = npv.resolve_universe()
    npv.assert_no_base_ticker_collision(syms)
    npv.assert_basis_integrity(root, syms)
    stale = npv.check_staleness(root, syms)
    close, volume = npv.build_panel(root, syms)
    mask = npv.membership_mask(syms, close.index)
    adj_m = close.where(mask)
    vol_m = volume.where(mask)
    panels = cb.build_panels(adj_m, vol_m)
    comp = cb.compute_composite(panels)
    spx = npv.benchmark_series(root).sort_index()
    mask_count = mask.sum(axis=1)
    active = mask_count[mask_count > 0]
    dq = {"provider": "norgate-pit", "ever_members": len(syms), "fetched_constituents": int(close.shape[1]),
          "unfetchable_members": int(len(syms) - close.shape[1]),
          "members_per_day_all_sessions": {"min": int(active.min()), "median": int(active.median()),
                                           "max": int(active.max())},
          "ndu_last_database_update": npv.ndu_update_time(), "staleness": stale,
          "refreshed_by_this_run": False, "cache_root": str(root), "readiness": r.detail}
    spx_file = npv._cache_path(root, npv.VOLUME_BASIS, npv.BENCHMARK)
    try:
        import pyarrow.parquet as pq
        meta = pq.ParquetFile(spx_file).schema_arrow.metadata or {}
        dq["benchmark_cache_footer"] = {k.decode(): meta[k].decode() for k in
                                        (b"basis", b"pulled_at_utc", b"ndu_last_database_update_time", b"last_date")
                                        if k in meta}
    except Exception as e:  # noqa: BLE001
        dq["benchmark_cache_footer"] = {"error": str(e)}
    ctx = Context(spec=spec, close=adj_m, comp=comp, panels=panels, spx=spx, mask_count=mask_count,
                  ever_members=len(syms), data_quality=dq)
    # the study-only High cache for the intraday sensitivity (P0-8; a shortfall records NOT_RUN)
    try:
        import ws10_high_cache as hc
        high, note = hc.load_high_panel(list(close.columns))
        note["panel_symbols"] = int(close.shape[1])
        if high is not None and note.get("symbols") == int(close.shape[1]) and note.get("smoke_pass"):
            ctx.high = high.reindex(index=close.index, columns=close.columns).where(mask)
        ctx.high_note = note
    except Exception as e:  # noqa: BLE001
        ctx.high_note = {"error": str(e)}
    return ctx


# ---------------------------------------------------------------- helpers

def _d(x) -> str:
    return str(pd.Timestamp(x).date())


def _f(x):
    if x is None:
        return None
    x = float(x)
    return x if np.isfinite(x) else None


def halves(ctx: Context, window_end: pd.Timestamp) -> dict:
    h = ws.get(ctx.spec, "data.halves")
    cal = ctx.close.index
    out = {}
    for name in ("early", "late"):
        lo, hi = h[name]
        lo = ws.resolve_session(pd.Timestamp(lo), cal)
        hi = window_end if hi == "live" else ws.resolve_session(pd.Timestamp(hi), cal)
        out[name] = (lo, hi)
    return out


def in_half(dates, bounds) -> pd.DatetimeIndex:
    lo, hi = bounds
    d = pd.DatetimeIndex(dates)
    return d[(d >= lo) & (d <= hi)]


def valid_sessions(ctx: Context, bounds) -> pd.DatetimeIndex:
    ok = ctx.comp.index[ctx.comp["data_ok"].astype(bool).to_numpy()]
    return in_half(ok, bounds)


def fires_by_dim(ctx: Context) -> dict:
    members = ws.get(ctx.spec, "engine.members")
    out = {}
    for dim, names in members.items():
        out[dim] = pd.DatetimeIndex(sorted({d for m in names for d in ws.member_fresh_fires(ctx.comp[m], ctx.comp)}))
    return out


def candidate_sets(ctx: Context) -> dict:
    """Every treatment set of null.cell_order, keyed by its hypothesis label (signal side only)."""
    sp = ctx.spec
    out = {}
    for member in ("S-D3", "S-D2"):
        share = ws.candidate_share(ctx.close, member)
        out[member] = {"share": share,
                       "events": ws.candidate_events(ctx.close, member, ctx.comp)}
        for lvl in ws.get(sp, f"candidates.{member}.sensitivities_pct"):
            out[f"{member}.sens{int(lvl)}"] = {"events": ws.candidate_events(ctx.close, member, ctx.comp, threshold=lvl)}
    if ctx.high is not None:
        lvl = float(ws.get(sp, "candidates.S-D3.labelled_sensitivity.threshold_pct"))
        out["S-D3.intraday"] = {"events": ws.candidate_events(ctx.high, "S-D3", ctx.comp, threshold=lvl)}
    extras = {}
    for member in ("S-D3", "S-D2"):
        fire = ws.daily_fire(out[member]["share"], float(ws.get(sp, f"candidates.{member}.threshold_pct")))
        fire.name = member
        extras[ws.get(sp, f"candidates.{member}.dimension")] = fire
    after = ws.composite_with_members(ctx.panels, extras)
    out["after"] = after
    for thr in (int(ws.get(sp, "h_m.gated_threshold")), int(ws.get(sp, "h_m.reported_threshold"))):
        out[f"H-M.ge{thr}"] = {"events": ws.added_events(ctx.comp, after, thr),
                               "removed": ws.removed_events(ctx.comp, after, thr),
                               "before": ws.before_set(ctx.comp, thr), "after": ws.fresh_at(after, thr)}
    return out


def treatment_for(cell: str, sets: dict):
    parts = cell.split(".")
    hyp = parts[0]
    if hyp == "H-S1":
        key, half, hz = "S-D3", parts[1], parts[2]
    elif hyp == "H-S2":
        key, half, hz = "S-D2", parts[1], parts[2]
    elif hyp == "H-M":
        key, half, hz = f"H-M.{parts[1]}", parts[2], parts[3]
    else:                                         # S-D3.sens50.early.3m, S-D3.intraday.late.3m
        key, half, hz = f"{parts[0]}.{parts[1]}", parts[2], parts[3]
    if key not in sets:
        return None, half, hz, key
    return sets[key]["events"], half, hz, key


# ---------------------------------------------------------------- Step 0

def signal_side(ctx: Context, window_end, hv, sets, fires) -> dict:
    """P0-3: counts only (doctrine D1: counts are not looks)."""
    sp = ctx.spec
    gap = int(ws.get(sp, "clusters.gap_calendar_days"))
    cal = ctx.close.index
    out = {"candidates": {}, "h_m": {}}
    ties = {}
    for member in ("S-D3", "S-D2"):
        ev = sets[member]["events"]
        own = ws.get(sp, f"candidates.{member}.dimension")
        block = {"pooled": {"fresh_events": int(len(ev)), "clusters": ws.cluster_count(ev, gap)}}
        red = ws.redundancy(ev, fires, own, cal)
        block["redundancy_pooled"] = {**{k: _f(red[k]) for k in ("own", "d1", "d4")}, "n_events": red["n_events"],
                                      "status": red["status"], "thin_g2": red["thin"]}
        block["lead_lag_pooled"] = {k: ws.cofire_split(ev, fires[dk], cal)
                                    for k, dk in (("own", own), ("d1", "d1"), ("d4", "d4"))}
        ties[member] = {k: ws.cofire_ties(ev, fires[dk], cal) for k, dk in (("own", own), ("d1", "d1"), ("d4", "d4"))}
        for half, b in hv.items():
            e = in_half(ev, b)
            r = ws.redundancy(e, fires, own, cal)
            block[half] = {"fresh_events": int(len(e)), "clusters": ws.cluster_count(e, gap),
                           "dates": [_d(x) for x in e],
                           "redundancy": {**{k: _f(r[k]) for k in ("own", "d1", "d4")}, "n_events": r["n_events"]},
                           "lead_lag": {k: ws.cofire_split(e, fires[dk], cal)
                                        for k, dk in (("own", own), ("d1", "d1"), ("d4", "d4"))}}
        block["first_computable_session"] = _d(sets[member]["share"].first_valid_index())
        block["daily_fire_sessions_data_ok"] = int((ws.daily_fire(sets[member]["share"],
                                                                  float(ws.get(sp, f"candidates.{member}.threshold_pct")))
                                                    & ctx.comp["data_ok"].astype(bool)).sum())
        out["candidates"][member] = block
    for key in [k for k in sets if k.startswith("S-D") and "." in k]:
        ev = sets[key]["events"]
        out["candidates"].setdefault("sensitivities", {})[key] = {
            half: {"fresh_events": int(len(in_half(ev, b))), "clusters": ws.cluster_count(in_half(ev, b), gap)}
            for half, b in hv.items()}
    for thr_key in ("H-M.ge2", "H-M.ge3"):
        s = sets[thr_key]
        hb = {}
        for half, b in hv.items():
            add = in_half(s["events"], b)
            hb[half] = {"before": int(len(in_half(s["before"], b))), "after": int(len(in_half(s["after"], b))),
                        "added": int(len(add)), "added_clusters": ws.cluster_count(add, gap),
                        "removed": int(len(in_half(s["removed"], b))),
                        "added_dates": [_d(x) for x in add], "removed_dates": [_d(x) for x in in_half(s["removed"], b)]}
            if thr_key == "H-M.ge2":
                hb[half]["added_memory_window_share_pct"] = _f(ws.memory_window_share(add, ctx.comp)) if len(add) else None
        if thr_key == "H-M.ge2":
            hb["pooled_added_memory_window_share_pct"] = (_f(ws.memory_window_share(s["events"], ctx.comp))
                                                          if len(s["events"]) else None)
        out["h_m"][thr_key] = hb
    out["cofire_ties"] = ties
    return out


def comparator_step0(ctx: Context, hv, sets, nulls: dict) -> dict:
    """P0-6 and P0-7 per gate cell, from random entries only."""
    sp = ctx.spec
    order = ws.get(sp, "null.cell_order")
    seed = int(ws.get(sp, "null.seed"))
    draws = int(ws.get(sp, "null.draws"))
    alpha = float(ws.get(sp, "holm.alpha"))
    keyed = float(ws.get(sp, "power.delta_pp_3m_keyed"))
    deltas = [keyed] + [float(x) for x in ws.get(sp, "power.deltas_pp_3m_descriptive")]
    pdraws = int(ws.get(sp, "power.draws"))
    drill_n = int(ws.get(sp, "self_drill.drill_draws"))
    out = {}
    for cell in ws.get(sp, "null.gate_cells"):
        ci = order.index(cell)
        ev, half, hz, key = treatment_for(cell, sets)
        h = int(ws.get(sp, f"horizons.sessions.{hz}"))
        treat = in_half(ev, hv[half])
        vs = valid_sessions(ctx, hv[half])
        t0 = time.time()
        null = ws.null_draws(treat, vs, ctx.spx, h, draws, [seed, ci])
        nulls[cell] = null
        n_complete = len(ws.complete_window_events(treat, ctx.spx, h))
        if n_complete == 0:
            pw = {d: 0.0 for d in deltas}
            drill = None
        else:
            pw = ws.power_by_delta(treat, vs, ctx.spx, h, deltas, null, pdraws, [seed, 1000 + ci], alpha, 3)
            drill = ws.self_drill(treat, vs, ctx.spx, h, null, drill_n, [seed, 2000 + ci])
        out[cell] = {"cell_index": ci, "treatment_events_complete": int(n_complete),
                     "treatment_clusters": ws.cluster_count(ws.complete_window_events(treat, ctx.spx, h),
                                                            int(ws.get(sp, "clusters.gap_calendar_days"))),
                     "valid_sessions": int(len(vs)),
                     "power": {f"{d:+.1f}pp": pw[d] for d in deltas}, "power_keyed": pw[keyed],
                     "thin": bool(pw[keyed] < float(ws.get(sp, "power.thin_below"))),
                     "demoted": bool(pw[keyed] < float(ws.get(sp, "power.demotion_below"))),
                     "self_drill": drill,
                     "self_drill_size_leg_label": "smoke check, cannot fail by construction, not a STOP",
                     "seconds": round(time.time() - t0, 1)}
        log.info("  %s: n=%d power %s drill %s (%.0fs)", cell, n_complete, out[cell]["power"],
                 None if drill is None else drill["centring_pass"], time.time() - t0)
    clause = {}
    for hyp, cells in (("H-S1", ("H-S1.early.3m", "H-S1.late.3m")), ("H-S2", ("H-S2.early.3m", "H-S2.late.3m")),
                       ("H-M.ge2", ("H-M.ge2.early.3m", "H-M.ge2.late.3m"))):
        clause[hyp] = {k: out[cells[0]]["power"][k] * out[cells[1]]["power"][k] for k in out[cells[0]]["power"]}
    return {"cells": out, "clause_level_power": clause}


def step0(ctx: Context, nulls: dict) -> tuple[dict, dict | None]:
    """Every probe of spec step0_probes. Returns (block, signal sets) with block["stopped"] set on a STOP."""
    sp = ctx.spec
    block: dict = {"probes": {}, "stopped": False, "stop_reason": None}
    sets = None
    try:
        # P0-5 hashes and tree
        pins = frozen_hashes_in_tests()
        for rel, val in pins.items():
            spec_hash_or_stop(val)
        block["probes"]["P0-5"] = {"spec_sha256": ws.spec_hash(), "frozen_in_tests": pins,
                                   "modules": check_engine_modules(sp), "tree": tree_and_tag(),
                                   "study_modules_sha256": {p.name: _sha(p) for p in sorted(SCRIPTS.glob("ws10_*.py"))},
                                   "pass": True}
        # P0-1 panel
        exp = ws.get(sp, "data.expected_panel")
        ok = ctx.comp["data_ok"].astype(bool)
        ok_idx = ctx.comp.index[ok.to_numpy()]
        if ctx.provider != ws.get(sp, "data.provider"):
            raise Stop(f"provider {ctx.provider} is not {ws.get(sp, 'data.provider')}")
        if ctx.ever_members < int(exp["ever_members_min"]):
            raise Stop(f"ever-members {ctx.ever_members} below {exp['ever_members_min']}")
        first_ok = ok_idx[0]
        window_start = pd.Timestamp(ws.get(sp, "data.window_start"))
        if first_ok != window_start:
            raise Stop(f"first data_ok session {_d(first_ok)} is not the window start {_d(window_start)}")
        window_end = ok_idx[-1]
        mc = ctx.mask_count.reindex(ok_idx)
        lo, hi = exp["members_per_day_mask_range"]
        bad = mc[(mc < lo) | (mc > hi)]
        p01 = {"ever_members": ctx.ever_members, "first_data_ok": _d(first_ok), "window_end": _d(window_end),
               "data_ok_sessions": int(len(ok_idx)),
               "mask_count_on_data_ok": {"min": int(mc.min()), "median": int(mc.median()), "max": int(mc.max())},
               "mask_count_outside_range_sessions": int(len(bad))}
        block["window_end"] = _d(window_end)
        if len(bad):
            block["probes"]["P0-1"] = {**p01, "pass": False}
            raise Stop(f"membership-mask count outside [{lo}, {hi}] on {len(bad)} data_ok sessions, first {_d(bad.index[0])}")
        gap = int(ws.get(sp, "clusters.gap_calendar_days"))
        f1 = ws.fresh_at(ctx.comp, 1)
        f3 = ws.fresh_at(ctx.comp, 3)
        f1_sep = f1[f1 <= pd.Timestamp("2026-09-01")]
        f3_jul = f3[f3 <= pd.Timestamp("2026-07-31")]
        observed = {"fresh_events_ge1_on_or_before_2026-09-01": int(len(f1_sep)),
                    "fresh_events_ge3_on_or_before_2026-07-31": int(len(f3_jul)),
                    "clusters_ge3_on_or_before_2026-07-31": ws.cluster_count(f3_jul, gap),
                    "last_fresh_event_ge1_on_or_before_2026-09-01": _d(f1_sep[-1]) if len(f1_sep) else None}
        p01["event_set_guard_observed"] = observed
        block["probes"]["P0-1"] = {**p01, "pass": False}
        event_set_guard(observed, exp["event_set_guard"])
        block["probes"]["P0-1"]["pass"] = True
        # P0-4 benchmark and half bounds
        cal = ctx.close.index
        win_cal = cal[(cal >= window_start) & (cal <= window_end)]
        present = win_cal.isin(ctx.spx.dropna().index)
        longest, run = 0, 0
        for p in present:
            run = 0 if p else run + 1
            longest = max(longest, run)
        missing_ok = ok_idx[~ok_idx.isin(ctx.spx.dropna().index)]
        hv = halves(ctx, window_end)
        block["probes"]["P0-4"] = {"longest_spx_gap_sessions": int(longest),
                                   "panel_sessions_missing_from_spx": int((~present).sum()),
                                   "data_ok_sessions_missing_from_spx": int(len(missing_ok)),
                                   "spx_last_session": _d(ctx.spx.dropna().index[-1]),
                                   "halves": {k: [_d(a), _d(b)] for k, (a, b) in hv.items()}, "pass": False}
        if longest > 5:
            raise Stop(f"$SPX has a gap of {longest} sessions on the panel calendar")
        if len(missing_ok):
            raise Stop(f"{len(missing_ok)} data_ok sessions absent from the $SPX return series (first "
                       f"{_d(missing_ok[0])}): the sampler cannot place on them; the spec does not answer this")
        block["probes"]["P0-4"]["pass"] = True
        # P0-2 computability, and the signal sets
        sets = candidate_sets(ctx)
        p02 = {}
        for member in ("S-D3", "S-D2"):
            share = sets[member]["share"]
            undefined = share.reindex(ok_idx).isna()
            p02[member] = {"first_computable_session": _d(share.first_valid_index()),
                           "undefined_data_ok_sessions": int(undefined.sum())}
            if undefined.any():
                block["probes"]["P0-2"] = {**p02, "pass": False}
                raise Stop(f"{member} share undefined on {int(undefined.sum())} data_ok sessions, first "
                           f"{_d(undefined.index[undefined.to_numpy()][0])}")
        block["probes"]["P0-2"] = {**p02, "pass": True}
        # P0-3 signal-side counts
        fires = fires_by_dim(ctx)
        p03 = signal_side(ctx, window_end, hv, sets, fires)
        p03["member_fresh_fires_pooled"] = {k: int(len(v)) for k, v in fires.items()}
        block["probes"]["P0-3"] = {**p03, "pass": True}
        tie_total = sum(v for m in p03["cofire_ties"].values() for v in m.values())
        if tie_total:
            block["probes"]["P0-3"]["pass"] = False
            raise Stop(f"{tie_total} co-firing candidate events have two member fires equally near on opposite "
                       "sides; the spec does not say how the lead/lag split classes them")
        # P0-6 and P0-7
        comp0 = comparator_step0(ctx, hv, sets, nulls)
        block["probes"]["P0-7"] = {"cells": {c: {k: v[k] for k in ("cell_index", "treatment_events_complete",
                                                                   "treatment_clusters", "power", "power_keyed",
                                                                   "thin", "demoted")}
                                             for c, v in comp0["cells"].items()},
                                   "clause_level_power": comp0["clause_level_power"], "pass": True}
        block["probes"]["P0-6"] = {"cells": {c: {"self_drill": v["self_drill"],
                                                 "size_leg_label": v["self_drill_size_leg_label"]}
                                             for c, v in comp0["cells"].items()}, "pass": True}
        for c, v in comp0["cells"].items():
            if v["self_drill"] is not None and not v["self_drill"]["centring_pass"]:
                block["probes"]["P0-6"]["pass"] = False
                raise Stop(f"self-drill centring leg outside its bands on {c}")
        block["_comparator"] = comp0
        # P0-8 the study-only High cache (no STOP)
        note = dict(ctx.high_note)
        note["intraday_sensitivity"] = "RUN" if ctx.high is not None else "NOT_RUN"
        block["probes"]["P0-8"] = note
        block["hv"] = hv
    except Stop as e:
        block["stopped"] = True
        block["stop_reason"] = str(e)
        log.error("STOP: %s", e)
    return block, sets


# ---------------------------------------------------------------- the full run

def ws7_baselines(ctx: Context, hv) -> dict:
    sp = ctx.spec
    out = {}
    for half, (lo, hi) in hv.items():
        s = ctx.spx[(ctx.spx.index >= lo) & (ctx.spx.index <= hi)]
        out[half] = fr.unconditional_baseline(s, n_boot=int(ws.get(sp, "ws7_read.n_boot")),
                                              block=int(ws.get(sp, "ws7_read.block")),
                                              seed=int(ws.get(sp, "ws7_read.seed")))
    return out


def run_cell(ctx: Context, cell: str, ci: int, sets: dict, hv, nulls: dict, baselines: dict) -> dict:
    sp = ctx.spec
    gap = int(ws.get(sp, "clusters.gap_calendar_days"))
    ev, half, hz, key = treatment_for(cell, sets)
    if ev is None:
        return {"cell": cell, "cell_index": ci, "status": "NOT_RUN", "reason": ctx.high_note.get("error") or
                "the study-only High cache did not pass P0-8"}
    h = int(ws.get(sp, f"horizons.sessions.{hz}"))
    treat = in_half(ev, hv[half])
    vs = valid_sessions(ctx, hv[half])
    complete = ws.complete_window_events(treat, ctx.spx, h)
    if cell in nulls:
        null = nulls[cell]
    else:
        null = ws.null_draws(treat, vs, ctx.spx, h, int(ws.get(sp, "null.draws")), [int(ws.get(sp, "null.seed")), ci])
    obs = ws.forward_stats(treat, ctx.spx, h)
    row = {"cell": cell, "cell_index": ci, "treatment": key, "half": half, "horizon": hz,
           "half_bounds": [_d(hv[half][0]), _d(hv[half][1])],
           "events_in_half": int(len(treat)), "events_complete": int(len(complete)),
           "clusters_complete": ws.cluster_count(complete, gap),
           "observed": {"n": obs["n"], "win_rate": _f(obs["win_rate"]), "median": _f(obs["median"])}}
    if obs["n"] == 0:
        row.update({"p_win": None, "p_med": None, "p": None, "null": None, "ws7": None})
        return row
    p_win = ws.mc_p(obs["win_rate"], null[:, 0])
    p_med = ws.mc_p(obs["median"], null[:, 1])
    row.update({"p_win": p_win, "p_med": p_med, "p": ws.per_horizon_p(p_win, p_med),
                "null": {"draws": int(len(null)), "win_rate_p95": _f(np.percentile(null[:, 0], 95)),
                         "median_p95": _f(np.percentile(null[:, 1], 95)),
                         "win_rate_mean": _f(null[:, 0].mean()), "median_mean": _f(null[:, 1].mean())}})
    cond = pd.DataFrame([{"threshold": 1, "horizon": hz, "n": obs["n"], "win_rate": obs["win_rate"],
                          "median_ret": obs["median"]}])
    lt = fr.lift_table(cond, baselines[half]).iloc[0]
    row["ws7"] = {"label": "WS7 both-legs read, beside the primary, never a gate",
                  "base_win_rate": _f(lt["base_win_rate"]), "base_win_hi": _f(lt["base_win_hi"]),
                  "base_median_ret": _f(lt["base_median_ret"]), "base_ret_hi": _f(lt["base_ret_hi"]),
                  "win_lift": _f(lt["win_lift"]), "ret_lift": _f(lt["ret_lift"]),
                  "win_beyond_noise": bool(lt["win_beyond_noise"]), "ret_beyond_noise": bool(lt["ret_beyond_noise"])}
    return row


def full_run(ctx: Context, s0: dict, sets: dict, nulls: dict, registry: ws.CandidateRegistry) -> dict:
    sp = ctx.spec
    hv = s0["hv"]
    order = ws.get(sp, "null.cell_order")
    alpha = float(ws.get(sp, "holm.alpha"))
    for name in ("S-D3", "S-D2", "H-M.ge2", "H-M.ge3"):
        registry.register(name, sets[name]["events"])
    for k in [k for k in sets if k.startswith("S-D") and "." in k]:
        registry.register(k, sets[k]["events"])
    baselines = ws7_baselines(ctx, hv)
    cells = {}
    for ci, cell in enumerate(order):
        t0 = time.time()
        cells[cell] = run_cell(ctx, cell, ci, sets, hv, nulls, baselines)
        log.info("  cell %s done (%.0fs)", cell, time.time() - t0)
    # Holm per hypothesis per half across {1m, 3m, 6m}
    holm_res = {}
    for hyp in ("H-S1", "H-S2", "H-M.ge2"):
        for half in ("early", "late"):
            pv = {}
            for hz in ("1m", "3m", "6m"):
                p = cells[f"{hyp}.{half}.{hz}"]["p"]
                pv[hz] = float("nan") if p is None else p
            holm_res[f"{hyp}.{half}"] = ws.holm(pv, alpha)
    comp0 = s0["_comparator"]["cells"]
    gate = {}
    for cell in ws.get(sp, "null.gate_cells"):
        hyp_half = cell.rsplit(".", 1)[0]
        cleared = bool(holm_res[hyp_half]["reject"]["3m"])
        pk = comp0[cell]["power_keyed"] if cells[cell]["events_complete"] > 0 else 0.0
        gate[cell] = {"cleared": cleared, "power_keyed": pk, "status": ws.cell_status(cleared, pk)}
    g1 = {"S-D3": ws.clause_status(gate["H-S1.early.3m"]["status"], gate["H-S1.late.3m"]["status"]),
          "S-D2": ws.clause_status(gate["H-S2.early.3m"]["status"], gate["H-S2.late.3m"]["status"])}
    red = s0["probes"]["P0-3"]["candidates"]
    g2 = {m: red[m]["redundancy_pooled"]["status"] for m in ("S-D3", "S-D2")}
    g3 = ws.clause_status(gate["H-M.ge2.early.3m"]["status"], gate["H-M.ge2.late.3m"]["status"])
    thin = any(v["power_keyed"] < float(ws.get(sp, "power.thin_below")) for v in gate.values())
    verdict = ws.verdict(g1, g2, g3, stopped=False, thin=thin)
    # H-M: the SEEN before set (routed through the registry), the after set and the change, at 3m per half
    h3 = int(ws.get(sp, "horizons.sessions.3m"))
    hm = {}
    for thr in (2, 3):
        s = sets[f"H-M.ge{thr}"]
        for half, b in hv.items():
            bset = in_half(s["before"], b)
            registry.assert_comparator(bset, label=f"H-M.ge{thr}.before.{half}")
            bs = ws.forward_stats(bset, ctx.spx, h3)
            ast = ws.forward_stats(in_half(s["after"], b), ctx.spx, h3)
            hm[f"ge{thr}.{half}"] = {
                "before_SEEN": {"label": "SEEN: the four-dimension set, descriptive reference only, never a treatment "
                                         "or a null", "n": bs["n"], "win_rate": _f(bs["win_rate"]), "median": _f(bs["median"])},
                "after": {"n": ast["n"], "win_rate": _f(ast["win_rate"]), "median": _f(ast["median"])},
                "change_in_3m_lift": {"win_rate": _f(ast["win_rate"] - bs["win_rate"]) if ast["n"] and bs["n"] else None,
                                      "median": _f(ast["median"] - bs["median"]) if ast["n"] and bs["n"] else None,
                                      "note": "after minus before on the same half; the unconditional base cancels"}}
    p03 = s0["probes"]["P0-3"]
    sd2 = red["S-D2"]["redundancy_pooled"]
    p1 = any((sd2[k] is not None and sd2[k] > 70.0) for k in ("own", "d1", "d4"))
    p2 = gate["H-S1.early.3m"]["status"] == "PASS" and gate["H-S1.late.3m"]["status"] in ("FAIL", "UNRESOLVED")
    late_added = p03["h_m"]["H-M.ge2"]["late"]["added"]
    p3 = g3 != "PASS" and late_added < 15
    predictions = {
        "P1": {"claim": ws.get(sp, "predictions.P1.claim"), "p": ws.get(sp, "predictions.P1.p"), "right": bool(p1),
               "basis": {k: sd2[k] for k in ("own", "d1", "d4")}},
        "P2": {"claim": ws.get(sp, "predictions.P2.claim"), "p": ws.get(sp, "predictions.P2.p"), "right": bool(p2),
               "basis": {"early": gate["H-S1.early.3m"]["status"], "late": gate["H-S1.late.3m"]["status"]}},
        "P3": {"claim": ws.get(sp, "predictions.P3.claim"), "p": ws.get(sp, "predictions.P3.p"), "right": bool(p3),
               "basis": {"G3": g3, "added_ge2_late": late_added}}}
    return {"cells": cells, "holm": holm_res, "gate": gate, "g1": g1, "g2": g2, "g3": g3, "thin": thin,
            "verdict": verdict, "h_m": hm, "predictions": predictions, "baselines": {
                half: b.to_dict(orient="records") for half, b in baselines.items()}}


# ---------------------------------------------------------------- writers

def _dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(obj, indent=1, default=str) + "\n").encode("utf-8"))


def _clean_step0(s0: dict) -> dict:
    return {k: v for k, v in s0.items() if not k.startswith("_") and k != "hv"}


def manifest(ctx: Context, s0: dict, registry: ws.CandidateRegistry | None, mode: str) -> dict:
    p05 = s0["probes"].get("P0-5", {})
    return {"registration": ws.get(ctx.spec, "registration"), "mode": mode,
            "written_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_revision": _git("rev-parse", "HEAD").strip(), "tag": "prereg-freeze",
            "tag_commit": _git("rev-parse", "prereg-freeze^{commit}").strip(),
            "spec_sha256": ws.spec_hash(), "engine_modules_sha256": p05.get("modules"),
            "study_modules_sha256": {p.name: _sha(p) for p in sorted(SCRIPTS.glob("ws10_*.py"))},
            "ndu_database_time": ctx.data_quality.get("ndu_last_database_update"),
            "cache_vintage": {"staleness": ctx.data_quality.get("staleness"),
                              "benchmark_cache_footer": ctx.data_quality.get("benchmark_cache_footer")},
            "cache_refreshed_by_this_run": False,
            "window_end_realised": s0.get("window_end"),
            "high_cache": ctx.high_note,
            "comparator_checks": registry.checks if registry else [],
            "comparator_note": "every comparator the runner uses is routed through CandidateRegistry.assert_comparator; "
                               "the primary null is random sets from the pinned sampler; the WS7 read is the "
                               "unconditional block bootstrap; neither is a candidate or added set"}


def append_runs_log(entry: dict) -> None:
    p = ROOT / ws.get(ws.load_spec(), "outputs.runs_log")
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


def results_doc(ctx: Context, s0: dict, fr_: dict | None, man: dict) -> dict:
    sp = ctx.spec
    run = {k: man[k] for k in ("git_revision", "tag", "tag_commit", "spec_sha256", "engine_modules_sha256",
                               "ndu_database_time", "cache_vintage", "window_end_realised")}
    run["panel"] = {"ever_members": ctx.ever_members, **{k: v for k, v in ctx.data_quality.items()
                                                         if k in ("fetched_constituents", "unfetchable_members",
                                                                  "members_per_day_all_sessions")}}
    doc = {"registration": ws.get(sp, "registration"), "run": run,
           "step0": {"stopped": s0["stopped"], "stop_reason": s0["stop_reason"],
                     "probes_pass": {k: v.get("pass") for k, v in s0["probes"].items() if isinstance(v, dict)},
                     "P0-1": s0["probes"].get("P0-1"), "P0-2": s0["probes"].get("P0-2"),
                     "P0-4": s0["probes"].get("P0-4"), "P0-8": s0["probes"].get("P0-8")}}
    if fr_ is None:
        doc["verdict"] = "STOP_STEP0"
        return doc
    p03 = s0["probes"]["P0-3"]
    p07 = s0["probes"]["P0-7"]
    gate_cells = ws.get(sp, "null.gate_cells")
    cands = {}
    for member, hyp in (("S-D3", "H-S1"), ("S-D2", "H-S2")):
        c = p03["candidates"][member]
        cands[member] = {
            "hypothesis": hyp, "threshold_pct": ws.get(sp, f"candidates.{member}.threshold_pct"),
            "signal_side": {k: c[k] for k in ("pooled", "first_computable_session")} | {
                half: {k: c[half][k] for k in ("fresh_events", "clusters", "dates", "lead_lag", "redundancy")}
                for half in ("early", "late")},
            "cells": {cell: fr_["cells"][cell] for cell in ws.get(sp, "null.cell_order") if cell.startswith(hyp + ".")},
            "holm": {half: fr_["holm"][f"{hyp}.{half}"] for half in ("early", "late")},
            "power": {cell: p07["cells"][cell] for cell in gate_cells if cell.startswith(hyp + ".")},
            "clause_level_power": p07["clause_level_power"][hyp],
            "redundancy": {"pooled": c["redundancy_pooled"], "lead_lag_pooled": c["lead_lag_pooled"],
                           "suffix": "THIN_G2" if c["redundancy_pooled"]["thin_g2"] else ""},
            "G1": fr_["g1"][member], "G2": fr_["g2"][member]}
    hm_cells = {cell: fr_["cells"][cell] for cell in ws.get(sp, "null.cell_order") if cell.startswith("H-M.")}
    doc["candidates"] = cands
    doc["h_m"] = {"signal_side": p03["h_m"], "cells": hm_cells,
                  "holm": {half: fr_["holm"][f"H-M.ge2.{half}"] for half in ("early", "late")},
                  "power": {cell: p07["cells"][cell] for cell in gate_cells if cell.startswith("H-M.")},
                  "clause_level_power": p07["clause_level_power"]["H-M.ge2"],
                  "before_after_3m": fr_["h_m"], "ge3_label": "reported at 3m, never gated", "G3": fr_["g3"]}
    doc["sensitivities"] = {"label": "descriptive, never gated, in no family",
                            "cells": {cell: fr_["cells"][cell] for cell in ws.get(sp, "null.cell_order")
                                      if cell.startswith("S-D")}}
    doc["gate_table"] = {"cells": fr_["gate"], "G1": fr_["g1"], "G2": {m: fr_["g2"][m] + (
        "_THIN_G2" if p03["candidates"][m]["redundancy_pooled"]["thin_g2"] else "") for m in ("S-D3", "S-D2")},
        "G3": fr_["g3"], "thin_suffix": fr_["thin"],
        "conjunction_family_wise_rate_at_most": float(ws.get(sp, "holm.alpha")) ** 2}
    doc["verdict"] = fr_["verdict"]
    doc["predictions"] = fr_["predictions"]
    doc["note"] = "Mechanical output of the frozen registration; no interpretation. The verdict read, the prediction " \
                  "scoring review and the filing follow in a separate session."
    return doc


# ---------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--step0", action="store_true")
    g.add_argument("--full", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    spec = ws.load_spec()
    out_results = ROOT / ws.get(spec, "outputs.declared_cells")
    if args.full and out_results.exists():
        raise SystemExit(f"{out_results} exists: the full run is executed ONCE")
    t0 = time.time()
    try:
        ctx = load_real(spec)
    except Stop as e:
        s0 = {"probes": {}, "stopped": True, "stop_reason": str(e)}
        _dump(ROOT / ws.get(spec, "outputs.step0"), s0)
        append_runs_log({"at_utc": datetime.now(timezone.utc).isoformat(), "mode": "step0" if args.step0 else "full",
                         "stopped": True, "stop_reason": str(e)})
        log.error("STOP while loading: %s", e)
        return 2
    log.info("panel loaded (%.0fs): %s sessions x %s names", time.time() - t0, *ctx.close.shape)
    nulls: dict = {}
    s0, sets = step0(ctx, nulls)
    mode = "step0" if args.step0 else "full"
    registry = ws.CandidateRegistry()
    if args.step0 or s0["stopped"]:
        man = manifest(ctx, s0, registry, mode)
        _dump(ROOT / ws.get(spec, "outputs.step0"), _clean_step0(s0))
        _dump(ROOT / ws.get(spec, "outputs.manifest"), man)
        if s0["stopped"] and args.full:
            _dump(out_results, results_doc(ctx, s0, None, man))
        append_runs_log({"at_utc": man["written_at_utc"], "mode": mode, "git_revision": man["git_revision"],
                         "spec_sha256": man["spec_sha256"], "stopped": s0["stopped"], "stop_reason": s0["stop_reason"],
                         "window_end": s0.get("window_end"), "seconds": round(time.time() - t0)})
        log.info("Step 0 %s (%.0fs)", "STOPPED: " + str(s0["stop_reason"]) if s0["stopped"] else "clear", time.time() - t0)
        return 2 if s0["stopped"] else 0
    res = full_run(ctx, s0, sets, nulls, registry)
    man = manifest(ctx, s0, registry, mode)
    _dump(ROOT / ws.get(spec, "outputs.step0"), _clean_step0(s0))
    full = {"registration": ws.get(spec, "registration"), "step0": _clean_step0(s0),
            "self_drill": {c: v["self_drill"] for c, v in s0["_comparator"]["cells"].items()},
            **{k: v for k, v in res.items()}}
    _dump(ROOT / ws.get(spec, "outputs.full"), full)
    _dump(ROOT / ws.get(spec, "outputs.manifest"), man)
    _dump(out_results, results_doc(ctx, s0, res, man))
    append_runs_log({"at_utc": man["written_at_utc"], "mode": mode, "git_revision": man["git_revision"],
                     "spec_sha256": man["spec_sha256"], "stopped": False, "verdict": res["verdict"],
                     "window_end": s0.get("window_end"), "seconds": round(time.time() - t0)})
    log.info("full run done (%.0fs): verdict %s", time.time() - t0, res["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
