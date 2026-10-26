"""WS10 thrust-subconditions: the study engine (frozen registration, built from PROMPT_RUN_ws10.md).

Implements the contract API stated in the module docstring of ``tests/test_ws10_contract.py`` for the
registration ``PREREG_thrust-subconditions.md`` (frozen 2026-10-01 at the tag ``prereg-freeze``). Every
constant is read from ``spec/ws10_prereg_spec.json`` through ``get()``, which raises ``FreezeViolation`` on
a missing key and never supplies a default. Where the words leave room, the reference implementation in
``tests/make_ws10_fixture.py`` is the semantics; the null sampler, the power routine and the self-drill
reproduce it draw for draw.

The three ways this study could be silently wrong (PREREG section 6), and where each guard lives here:

1. A definition mismatch on the member condition. ``candidate_share`` uses the close-based window of the
   spec including today, at-or-above for the 20-session high and strictly above for the 10-session
   average, the share as 100 * count / members with the multiplication first, and a denominator of names
   with both the close and the rolling statistic defined (no forward fill, no padding).
2. Double counting. ``cofire_share`` reads a window in EITHER direction; ``composite_with_members`` ORs a
   candidate into its own dimension (never a new dimension) and leaves the 60-session memory and the
   event rule of ``compute_breadth.compute_composite`` unchanged; H-M is gated on the ADDED events only.
3. A comparator that is not like-for-like. ``null_sets`` is the pinned SEQUENTIAL, count-matched,
   cluster-structured sampler with the complete-window rule (lag included) on the return series for both
   the treatment and the null; ``self_drill`` checks the null's centring against an independent
   unconditional reference; ``CandidateRegistry.assert_comparator`` refuses a candidate or added set as a
   comparator and ``before_set`` takes no candidate argument.

The three engine modules (compute_breadth, forward_returns, norgate_provider) are imported read-only and
never modified. Python months are 1-indexed (January == 1). Date arithmetic goes through pandas only.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
SPEC_PATH = ROOT / "spec" / "ws10_prereg_spec.json"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import compute_breadth as cb  # noqa: E402  (read-only)
import forward_returns as fr  # noqa: E402  (read-only)


# ---------------------------------------------------------------- exceptions

class FreezeViolation(KeyError):
    """A value the engine needs is absent from the frozen spec; never defaulted."""


class BurnInRefusal(RuntimeError):
    """A computation was requested inside the burn-in or on a panel with no data_ok session."""


class NonSessionDate(ValueError):
    """A date argument is not a session on the panel calendar."""


class ComparatorMisuse(RuntimeError):
    """A candidate or added event set was offered as a comparator."""


# ---------------------------------------------------------------- the spec

def load_spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


_SPEC_CACHE: dict | None = None


def _sp() -> dict:
    global _SPEC_CACHE
    if _SPEC_CACHE is None:
        _SPEC_CACHE = load_spec()
    return _SPEC_CACHE


def get(spec: dict, dotted: str):
    """Value at a dotted path of the spec; a missing key raises FreezeViolation, never a default."""
    node = spec
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise FreezeViolation(f"spec key missing: {dotted}")
        node = node[part]
    return node


def spec_hash() -> str:
    return hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest()


# ---------------------------------------------------------------- sessions

def resolve_session(date, sessions) -> pd.Timestamp:
    d = pd.Timestamp(date)
    if d not in pd.DatetimeIndex(sessions):
        raise NonSessionDate(f"{d.date()} is not a session on the panel calendar")
    return d


def forward_window_end(sessions, start, horizon_sessions: int) -> pd.Timestamp:
    cal = pd.DatetimeIndex(sessions)
    d = resolve_session(start, cal)
    i = cal.get_loc(d) + int(horizon_sessions)
    if i > len(cal) - 1:
        raise NonSessionDate(f"{d.date()} + {horizon_sessions} sessions runs beyond the panel calendar")
    return cal[i]


# ---------------------------------------------------------------- candidate shares and events

def candidate_share(close: pd.DataFrame, member: str) -> pd.Series:
    """Per cent of members at the member condition: 100 * count / members, the multiplication first.
    A name counts only when its close and its rolling statistic are both defined (no forward fill, no
    padding); NaN where fewer than shared.share_nan_below_members names qualify."""
    sp = _sp()
    w = int(get(sp, f"candidates.{member}.window_sessions"))
    floor = int(get(sp, "candidates.shared.share_nan_below_members"))
    if member == "S-D3":
        stat = close.rolling(w, min_periods=w).max()
        hit = close >= stat
    elif member == "S-D2":
        stat = close.rolling(w, min_periods=w).mean()
        hit = close > stat
    else:
        raise FreezeViolation(f"unknown candidate: {member}")
    valid = close.notna() & stat.notna()
    num = (hit & valid).sum(axis=1).astype(float)
    den = valid.sum(axis=1).astype(float)
    share = 100.0 * num / den.replace(0.0, np.nan)
    share[den < floor] = np.nan
    share.name = member
    return share


def daily_fire(share: pd.Series, threshold: float) -> pd.Series:
    out = (share >= threshold).fillna(False).astype(bool)
    out.name = share.name
    return out


def _data_ok(comp: pd.DataFrame, index: pd.DatetimeIndex) -> pd.Series:
    return comp["data_ok"].reindex(index).fillna(False).astype(bool)


def fresh_events(share: pd.Series, threshold: float, comp: pd.DataFrame) -> pd.DatetimeIndex:
    """First session at or above the threshold after shared.below_sessions consecutive DEFINED sessions
    strictly below; admitted on data_ok sessions at or after the first data_ok session only."""
    below_n = int(get(_sp(), "candidates.shared.below_sessions"))
    ok_all = comp["data_ok"].astype(bool)
    if not ok_all.any():
        raise BurnInRefusal("no data_ok session on this panel")
    first_ok = ok_all.index[ok_all.to_numpy()][0]
    ok = _data_ok(comp, share.index).to_numpy()
    vals = share.to_numpy(dtype=float)
    below = np.isfinite(vals) & (vals < threshold)
    at_or_above = np.isfinite(vals) & (vals >= threshold)
    out, run = [], 0
    for i, d in enumerate(share.index):
        if at_or_above[i]:
            if run >= below_n and d >= first_ok and ok[i]:
                out.append(d)
            run = 0
        elif below[i]:
            run += 1
        else:
            run = 0
    return pd.DatetimeIndex(out)


def candidate_events(close: pd.DataFrame, member: str, comp: pd.DataFrame,
                     threshold: float | None = None) -> pd.DatetimeIndex:
    """candidate_share then fresh_events at the registered threshold (or a declared sensitivity level).
    Refuses a panel shorter than the burn-in plus the member's own window."""
    sp = _sp()
    need = int(get(sp, "engine.constants.HL_LOOKBACK")) + int(get(sp, f"candidates.{member}.window_sessions"))
    if len(close) < need:
        raise BurnInRefusal(f"{len(close)} sessions is shorter than the burn-in plus the {member} window ({need})")
    thr = float(get(sp, f"candidates.{member}.threshold_pct")) if threshold is None else float(threshold)
    return fresh_events(candidate_share(close, member), thr, comp)


def member_fresh_fires(boolean: pd.Series, comp: pd.DataFrame) -> pd.DatetimeIndex:
    """First session a member's daily boolean is True after at least below_sessions consecutive sessions
    False, restricted to data_ok sessions (existing_member_fresh_fire.rule)."""
    below_n = int(get(_sp(), "existing_member_fresh_fire.below_sessions"))
    b = boolean.fillna(False).astype(bool).to_numpy()
    ok = _data_ok(comp, boolean.index).to_numpy()
    out, run = [], 0
    for i, d in enumerate(boolean.index):
        if b[i]:
            if run >= below_n and ok[i]:
                out.append(d)
            run = 0
        else:
            run += 1
    return pd.DatetimeIndex(out)


# ---------------------------------------------------------------- redundancy (G2)

def _positions(dates, sessions) -> np.ndarray:
    cal = pd.DatetimeIndex(sessions)
    pos = {d: i for i, d in enumerate(cal)}
    return np.array([pos[resolve_session(d, cal)] for d in dates], dtype=int)


def cofire_share(cand_events, fire_dates, sessions) -> float:
    """Per cent of candidate events with a member fire at most redundancy.window_sessions away, in EITHER
    direction; NaN for an empty candidate set."""
    if len(cand_events) == 0:
        return float("nan")
    win = int(get(_sp(), "redundancy.window_sessions"))
    cpos = _positions(cand_events, sessions)
    fpos = np.sort(_positions(fire_dates, sessions))
    hits = 0
    for i in cpos:
        if len(fpos) and np.any(np.abs(fpos - i) <= win):
            hits += 1
    return 100.0 * hits / len(cand_events)


def _nearest_offsets(cand_events, fire_dates, sessions) -> list[tuple[int, bool]]:
    """For each co-firing candidate event: (signed offset of the nearest fire, tie flag). A negative offset
    means the member fire came BEFORE the candidate session. The tie flag marks two fires equally near on
    opposite sides."""
    win = int(get(_sp(), "redundancy.window_sessions"))
    cpos = _positions(cand_events, sessions)
    fpos = np.sort(_positions(fire_dates, sessions))
    out = []
    for i in cpos:
        if not len(fpos):
            continue
        diff = fpos - i
        near = diff[np.abs(diff) <= win]
        if not len(near):
            continue
        m = np.abs(near).min()
        sides = set(np.sign(near[np.abs(near) == m]).tolist())
        out.append((int(near[np.abs(near) == m][0]), len(sides) > 1))
    return out


def cofire_split(cand_events, fire_dates, sessions) -> dict:
    """Counts of co-firing candidate events by whether the nearest member fire is before, on, or after the
    candidate's session. A tie between two fires equally near on opposite sides is counted by
    ``cofire_ties`` separately and excluded from these three counts, per the owner ruling in
    ESCALATION_ws10.md. The runner reports the tied count beside this partition."""
    split = {"before": 0, "same": 0, "after": 0}
    for off, tie in _nearest_offsets(cand_events, fire_dates, sessions):
        if tie:
            continue
        split["same" if off == 0 else ("before" if off < 0 else "after")] += 1
    return split


def cofire_ties(cand_events, fire_dates, sessions) -> int:
    return int(sum(tie for _off, tie in _nearest_offsets(cand_events, fire_dates, sessions)))


def redundancy(cand_events, fires_by_dim: dict, own_dimension: str, sessions) -> dict:
    sp = _sp()
    above = float(get(sp, "redundancy.redundant_if_own_dimension_share_pct_above"))
    thin_below = int(get(sp, "redundancy.thin_suffix_below_events"))
    n = int(len(cand_events))
    out = {"own": cofire_share(cand_events, fires_by_dim[own_dimension], sessions),
           "d1": cofire_share(cand_events, fires_by_dim["d1"], sessions),
           "d4": cofire_share(cand_events, fires_by_dim["d4"], sessions),
           "n_events": n, "thin": bool(n < thin_below)}
    if n == 0:
        out["status"] = "NO_EVENTS"
    elif out["d4"] > out["own"]:
        out["status"] = "MISPLACED"
    elif out["own"] > above:
        out["status"] = "REDUNDANT"
    else:
        out["status"] = "DISTINCT"
    return out


# ---------------------------------------------------------------- H-M: the composite with members

def composite_with_members(panels, extra: dict, config=None) -> pd.DataFrame:
    """compute_breadth.compute_composite with each candidate daily boolean OR-ed into its dimension; the
    60-session memory and the event rule (a session on which n_dimensions increases) apply unchanged.
    Equal to compute_composite(panels) on every engine column when every extra boolean is False."""
    config = config or cb.CompositeConfig()
    mem = config.memory_days
    dims = pd.concat([cb.d1_advance_decline(panels), cb.d2_pct_above_ma(panels),
                      cb.d3_new_high_low(panels), cb.d4_up_volume(panels)], axis=1)
    for dim, boolean in extra.items():
        b = boolean.reindex(dims.index).fillna(False).astype(bool)
        dims[f"{dim}_member_{boolean.name or 'candidate'}"] = b
        dims[dim] = dims[dim] | b
    df = dims.copy()
    on_cols = []
    for d in ("d1", "d2", "d3", "d4"):
        df[f"{d}_on"] = dims[d].rolling(mem, min_periods=1).max().astype(bool)
        on_cols.append(f"{d}_on")
    w = config.weights
    df["n_dimensions"] = df[on_cols].sum(axis=1).astype(int)
    df["score"] = (df["d1_on"].astype(float) * w["d1"] + df["d2_on"].astype(float) * w["d2"]
                   + df["d3_on"].astype(float) * w["d3"] + df["d4_on"].astype(float) * w["d4"])
    df["event"] = (df["n_dimensions"] > df["n_dimensions"].shift(1).fillna(0)).astype(bool)
    df["valid_count"] = panels.valid_count
    computable = ((panels.ma_valid_count >= cb.MIN_VALID_CONSTITUENTS)
                  & (panels.hl_valid_count >= cb.MIN_VALID_CONSTITUENTS))
    df["burn_in"] = ~computable
    df["data_ok"] = (panels.valid_count >= cb.MIN_VALID_CONSTITUENTS) & computable
    return df


def fresh_at(comp: pd.DataFrame, threshold: int) -> pd.DatetimeIndex:
    sel = comp["event"].astype(bool) & (comp["n_dimensions"] >= threshold) & comp["data_ok"].astype(bool)
    return pd.DatetimeIndex(comp.index[sel])


def before_set(comp: pd.DataFrame, threshold: int) -> pd.DatetimeIndex:
    """The SEEN four-dimension fresh-event set; it takes no candidate argument by construction."""
    return fresh_at(comp, threshold)


def added_events(before: pd.DataFrame, after: pd.DataFrame, threshold: int) -> pd.DatetimeIndex:
    b = set(fresh_at(before, threshold))
    return pd.DatetimeIndex([d for d in fresh_at(after, threshold) if d not in b])


def removed_events(before: pd.DataFrame, after: pd.DataFrame, threshold: int) -> pd.DatetimeIndex:
    a = set(fresh_at(after, threshold))
    return pd.DatetimeIndex([d for d in fresh_at(before, threshold) if d not in a])


def memory_window_share(added, before: pd.DataFrame) -> float:
    """Per cent of ADDED dates on which the before composite already had a dimension on (n_dimensions >= 1)."""
    return 100.0 * float((before["n_dimensions"].reindex(pd.DatetimeIndex(added)) >= 1).mean())


class CandidateRegistry:
    """Every candidate and added event set is registered here; a registered set offered as a comparator
    raises ComparatorMisuse. The checks made are kept for the manifest."""

    def __init__(self) -> None:
        self._sets: dict[str, frozenset] = {}
        self.checks: list[dict] = []

    def register(self, name: str, events) -> None:
        self._sets[name] = frozenset(pd.DatetimeIndex(events))

    def assert_comparator(self, events, label: str = "", *, seen: bool = False) -> None:
        s = frozenset(pd.DatetimeIndex(events))
        # Owner ruling: an independently constructed empty SEEN set is admissible;
        # an empty candidate passed without that provenance remains prohibited.
        if seen and not s:
            self.checks.append({"comparator": label, "n": 0, "admitted": True,
                                "reason": "empty SEEN comparator: owner ruling",
                                "registered_sets_checked": sorted(self._sets)})
            return
        for name, reg in self._sets.items():
            if s == reg:
                self.checks.append({"comparator": label, "n": len(s), "refused_as": name})
                raise ComparatorMisuse(f"comparator {label or '(unnamed)'} equals the registered set {name}")
        self.checks.append({"comparator": label, "n": len(s), "admitted": True,
                            "registered_sets_checked": sorted(self._sets)})


# ---------------------------------------------------------------- forward returns, windows, clusters

def _horizon_label(h: int) -> str:
    for label, n in fr.HORIZONS.items():
        if n == int(h):
            return label
    raise FreezeViolation(f"no forward_returns horizon of {h} sessions")


def forward_stats(events, index_series: pd.Series, horizon_sessions: int) -> dict:
    """Lagged one session through forward_returns.conditional_table: signal close T, window from the close
    of T+1; events whose lagged window is incomplete are dropped."""
    spx = index_series.sort_index()
    ev = pd.DatetimeIndex(events)
    comp = pd.DataFrame({"n_dimensions": 0, "event": False}, index=spx.index)
    comp.loc[ev.intersection(spx.index), ["n_dimensions", "event"]] = [1, True]
    tab = fr.conditional_table(comp, spx, thresholds=(1,), events_only=True)
    row = tab[(tab["threshold"] == 1) & (tab["horizon"] == _horizon_label(horizon_sessions))].iloc[0]
    n = int(row["n"])
    return {"n": n, "win_rate": float(row["win_rate"]) if n else float("nan"),
            "median": float(row["median_ret"]) if n else float("nan")}


def complete_window_events(events, index_series: pd.Series, horizon_sessions: int) -> pd.DatetimeIndex:
    """Events at return-series position i with i + 1 + h at most the last index (complete_window_rule)."""
    idx = index_series.sort_index().index
    pos = {d: i for i, d in enumerate(idx)}
    last = len(idx) - 1
    h = int(horizon_sessions)
    return pd.DatetimeIndex([d for d in sorted(pd.DatetimeIndex(events)) if d in pos and pos[d] + 1 + h <= last])


def cluster_ids(dates, gap_days: int) -> list[int]:
    d = pd.DatetimeIndex(sorted(pd.DatetimeIndex(dates)))
    ids, cur = [], 0
    for i in range(len(d)):
        if i > 0 and (d[i] - d[i - 1]).days > gap_days:
            cur += 1
        ids.append(cur)
    return ids


def cluster_count(dates, gap_days: int) -> int:
    ids = cluster_ids(dates, gap_days)
    return len(set(ids))


# ---------------------------------------------------------------- the comparator

def _lagged_return_lookup(index_series: pd.Series, h: int):
    """Position map and the lagged forward return px[i+1+h] / px[i+1] - 1 at every position i whose window
    is complete (NaN elsewhere): the same expression as the reference, so values agree bit for bit."""
    s = index_series.sort_index()
    idx = s.index
    px = s.to_numpy(dtype=float)
    n = len(px)
    lag = np.full(n, np.nan)
    k = np.arange(n)
    ok = k + 1 + h <= n - 1
    lag[ok] = px[k[ok] + 1 + h] / px[k[ok] + 1] - 1.0
    return idx, {d: i for i, d in enumerate(idx)}, lag


def null_sets(events, valid_sessions, index_series: pd.Series, horizon_sessions: int, draws: int,
              seed_key) -> list[pd.DatetimeIndex]:
    """The pinned SEQUENTIAL sampler (spec null.placement and null.restart), identical to the reference
    ref_null_sets draw for draw: clusters of the complete-window treatment events are placed in
    chronological order; each start is drawn by one rng.integers(len(admissible)) call over the ascending
    admissible positions of valid_sessions (the whole cluster fits, every event is complete at the horizon
    on the return series, every event is more than the cluster gap from every event already placed); a
    cluster with no admissible position restarts the whole draw; max_restarts restarts is a STOP."""
    sp = _sp()
    gap_days = int(get(sp, "clusters.gap_calendar_days"))
    max_restarts = int(get(sp, "null.max_restarts"))
    h = int(horizon_sessions)
    idx = index_series.sort_index().index
    ipos = {d: i for i, d in enumerate(idx)}
    v = pd.DatetimeIndex(sorted(pd.DatetimeIndex(valid_sessions)))
    vpos = {d: j for j, d in enumerate(v)}
    treat = complete_window_events(events, index_series, h)
    if len(treat) == 0:
        return [pd.DatetimeIndex([]) for _ in range(draws)]
    for d in treat:
        if d not in vpos:
            raise NonSessionDate(f"treatment event {d.date()} is not among the valid sessions")
    ids = cluster_ids(treat, gap_days)
    clusters = []
    for k in sorted(set(ids)):
        members = [d for d, i in zip(sorted(treat), ids) if i == k]
        base = vpos[members[0]]
        clusters.append([vpos[d] - base for d in members])
    last = len(idx) - 1
    complete = np.array([ipos[d] + 1 + h <= last for d in v], dtype=bool)
    vdays = (v - v[0]).days.to_numpy()
    rng = np.random.default_rng(seed_key)
    out = []
    for _ in range(draws):
        for restart in range(max_restarts + 1):
            if restart == max_restarts:
                raise RuntimeError("Stop: a null draw could not be placed in max_restarts restarts")
            # blocked[k] is True when valid session k lies within gap_days calendar days of an event already
            # placed in this draw; "more than gap_days from every placed event" is then ~blocked at the
            # session each offset lands on, the same admissible set as the reference's pairwise distances
            blocked = np.zeros(len(v), dtype=bool)
            placed_dates: list[pd.Timestamp] = []
            ok = True
            for offs in clusters:
                omax = offs[-1]
                n = len(v) - omax
                if n <= 0:
                    ok = False
                    break
                adm = np.ones(n, dtype=bool)
                for o in offs:
                    adm &= complete[o:o + n] & ~blocked[o:o + n]
                cand = np.flatnonzero(adm)
                if len(cand) == 0:
                    ok = False
                    break
                j = int(cand[rng.integers(len(cand))])
                for o in offs:
                    day = vdays[j + o]
                    lo = np.searchsorted(vdays, day - gap_days, side="left")
                    hi = np.searchsorted(vdays, day + gap_days, side="right")
                    blocked[lo:hi] = True
                    placed_dates.append(v[j + o])
            if ok:
                break
        out.append(pd.DatetimeIndex(sorted(placed_dates)))
    return out


def _set_returns(dates, ipos: dict, lag: np.ndarray) -> np.ndarray:
    r = lag[[ipos[d] for d in sorted(dates)]] if len(dates) else np.array([], dtype=float)
    return r[np.isfinite(r)]


def _stats(r: np.ndarray) -> tuple[float, float]:
    if len(r) == 0:
        return float("nan"), float("nan")
    return float((r > 0).mean()), float(np.median(r))


def null_draws(events, valid_sessions, index_series: pd.Series, horizon_sessions: int, draws: int,
               seed_key) -> np.ndarray:
    """(draws, 2): win rate and median of each drawn set's lagged forward returns."""
    sets = null_sets(events, valid_sessions, index_series, horizon_sessions, draws, seed_key)
    _idx, ipos, lag = _lagged_return_lookup(index_series, int(horizon_sessions))
    return np.array([list(_stats(_set_returns(s, ipos, lag))) for s in sets], dtype=float)


def mc_p(observed: float, draw_values) -> float:
    """(1 + count of draws at or beyond the observed) / (1 + draws)."""
    vals = np.asarray(draw_values, dtype=float)
    return (1.0 + float(np.sum(vals >= observed))) / (1.0 + len(vals))


def per_horizon_p(p_win: float, p_med: float) -> float:
    return max(p_win, p_med)


def holm(pvals: dict, alpha: float) -> dict:
    """Holm step-down: the k-th smallest of m p-values is tested at alpha / (m - k + 1); rejection stops at
    the first failure. A missing (NaN) p never rejects and sorts last."""
    names = list(pvals)
    m = len(names)
    order = sorted(names, key=lambda k: (not np.isfinite(pvals[k]), pvals[k] if np.isfinite(pvals[k]) else 0.0))
    reject = {k: False for k in names}
    steps = []
    going = True
    for k, name in enumerate(order, start=1):
        thr = alpha / (m - k + 1)
        p = pvals[name]
        rej = bool(going and np.isfinite(p) and p <= thr)
        if not rej:
            going = False
        reject[name] = rej
        steps.append({"name": name, "p": (float(p) if np.isfinite(p) else None), "threshold": thr, "reject": rej})
    return {"reject": reject, "steps": steps}


def _power_from_sets(sets, ipos, lag, delta_pp: float, null_values: np.ndarray, bar: float) -> float:
    hits = 0
    for s in sets:
        r = _set_returns(s, ipos, lag) + delta_pp / 100.0
        p = max(mc_p(float((r > 0).mean()), null_values[:, 0]), mc_p(float(np.median(r)), null_values[:, 1]))
        hits += int(p <= bar)
    return hits / len(sets)


def power(events, valid_sessions, index_series: pd.Series, horizon_sessions: int, delta_pp: float,
          null_values: np.ndarray, draws: int, seed_key, alpha: float, family_size: int) -> float:
    """Share of sets drawn by the pinned sampler on seed_key whose max(p_win, p_med), after +delta_pp / 100
    is added to every lagged return, is at or below alpha / family_size against null_values."""
    if len(complete_window_events(events, index_series, horizon_sessions)) == 0:
        return 0.0
    sets = null_sets(events, valid_sessions, index_series, horizon_sessions, draws, seed_key)
    _idx, ipos, lag = _lagged_return_lookup(index_series, int(horizon_sessions))
    return _power_from_sets(sets, ipos, lag, float(delta_pp), null_values, alpha / family_size)


def power_by_delta(events, valid_sessions, index_series: pd.Series, horizon_sessions: int, deltas,
                   null_values: np.ndarray, draws: int, seed_key, alpha: float, family_size: int) -> dict:
    """``power`` at several deltas on one seed key. Each delta reuses the same drawn sets, which is what
    separate ``power`` calls on the same seed key would draw, so every value equals ``power``'s."""
    if len(complete_window_events(events, index_series, horizon_sessions)) == 0:
        return {float(d): 0.0 for d in deltas}
    sets = null_sets(events, valid_sessions, index_series, horizon_sessions, draws, seed_key)
    _idx, ipos, lag = _lagged_return_lookup(index_series, int(horizon_sessions))
    return {float(d): _power_from_sets(sets, ipos, lag, float(d), null_values, alpha / family_size) for d in deltas}


def self_drill(events, valid_sessions, index_series: pd.Series, horizon_sessions: int,
               null_values: np.ndarray, drill_draws: int, seed_key) -> dict:
    """P0-6. Centring leg (the STOP): the null's mean per-draw win rate and median against the unconditional
    complete-window lagged figures over the valid sessions, computed directly from the return series.
    Size leg (a labelled smoke check): the share of drill_draws random sets with max(p_win, p_med) <= alpha."""
    sp = _sp()
    alpha = float(get(sp, "holm.alpha"))
    win_band = float(get(sp, "self_drill.win_band"))
    median_band_pp = float(get(sp, "self_drill.median_band_pp"))
    h = int(horizon_sessions)
    _idx, ipos, lag = _lagged_return_lookup(index_series, h)
    r = _set_returns(pd.DatetimeIndex(valid_sessions), ipos, lag)
    unc_win, unc_med = float((r > 0).mean()), float(np.median(r))
    null_win, null_med = float(null_values[:, 0].mean()), float(null_values[:, 1].mean())
    sets = null_sets(events, valid_sessions, index_series, h, drill_draws, seed_key)
    small = 0
    for s in sets:
        w, m = _stats(_set_returns(s, ipos, lag))
        p = max(mc_p(w, null_values[:, 0]), mc_p(m, null_values[:, 1]))
        small += int(p <= alpha)
    return {"unconditional_win_rate": unc_win, "unconditional_median": unc_med,
            "null_mean_win_rate": null_win, "null_mean_median": null_med,
            "centring_pass": bool(abs(null_win - unc_win) <= win_band
                                  and abs(null_med - unc_med) * 100.0 <= median_band_pp),
            "size_share_at_alpha": small / drill_draws}


# ---------------------------------------------------------------- statuses and the verdict

def cell_status(cleared: bool, power_keyed: float) -> str:
    if cleared:
        return "PASS"
    if power_keyed >= float(get(_sp(), "power.demotion_below")):
        return "FAIL"
    return "UNRESOLVED"


def clause_status(early: str, late: str) -> str:
    if early == "PASS" and late == "PASS":
        return "PASS"
    if "FAIL" in (early, late):
        return "FAIL"
    return "UNRESOLVED"


def verdict(g1: dict, g2: dict, g3: str, stopped: bool = False, thin: bool = False) -> str:
    """verdict.rule_in_order, applied mechanically; _THIN appended when any gate cell's keyed power is
    below power.thin_below (the caller passes the flag)."""
    if stopped:
        return "STOP_STEP0"
    proposable = [c for c in g1 if g1[c] == "PASS" and g2.get(c) == "DISTINCT"]
    if g3 == "PASS" and len(proposable) == len(g1) and len(g1) > 0:
        out = "PROPOSE_ENGINE_CHANGE"
    elif g3 == "PASS" and len(proposable) == 1:
        out = "PROPOSE_CONDITIONAL"
    elif g3 == "FAIL" and len(proposable) >= 1:
        out = "ADDS_FIRES_WITHOUT_INFORMATION"
    elif any(s == "PASS" for s in g1.values()) and not proposable:
        out = "ALREADY_CARRIED"
    elif len(g1) > 0 and all(s == "FAIL" for s in g1.values()):
        out = "NO_INFORMATION"
    else:
        out = "UNRESOLVED"
    return out + "_THIN" if thin else out
