"""Planted synthetic fixture for the WS10 (thrust-subconditions) contract tests.

Deterministic, no market data, no random number generator in the PANEL and no transcendental
function: every price is a cumulative PRODUCT of planted daily factors (IEEE multiplication is
exactly rounded, so the panel is bit-identical on every platform). The expected values come from a
plain reference implementation of the frozen rules in ``spec/ws10_prereg_spec.json``, including the
null sampler, the power routine and the self-drill; ``tests/test_ws10_mutants.py`` proves that the
committed wrong engine in ``tests/mutants/ws10_wrong.py`` FAILS these expectations while this
reference passes them. Regenerate with ``python tests/make_ws10_fixture.py``; the contract tests
rebuild the panel in memory and compare it with the committed hash.

Panel: 800 names in 40 groups of 20, 572 sessions on a business-day calendar from 2019-01-02
(Python months are 1-indexed, January == 1; every date operation goes through pandas). Group paths:
a slow decline by default (-0.3678 per cent a session), planted rises (+0.4 per cent a session) and
planted steps (+10 per cent on one session, then exactly flat). The rates are chosen so that, after a
V-turn, a name reaches its 20-session closing high on the 10th up close under the frozen window and
on the 9th under a 19-session window, and so that a step followed by a flat plateau sits strictly
above its 10-session average for exactly nine sessions under the frozen inclusive window and for ten
under an 11-session or exclude-today variant. Exact-threshold shares are planted: 22 groups at a
20-session high is 440 of 800 = 55.0 per cent; 36 groups above their 10-session average is 720 of
800 = 90.0 per cent. Two names of the never-rising group 39 carry planted gaps (legitimate on a
padding-NONE panel): N798 enters late (no close before session 300) and N799 has an interior gap
(sessions 340 to 345), so a forward-filled statistic or a denominator that counts members without
the required history is caught; 798 names still clear the 400-member floor on every session.

Planted episodes (session indices; the composite's burn-in ends at index 251, the 252nd session; the
dates and values the reference produces are the ones pinned in fixtures/ws10/expected.json and listed
in WS10_FIXTURE.md):
  A  session 60         38 groups (95 per cent) step, then rise to 70: both shares cross INSIDE the burn-in
                        (refused as events), and D1, D2 and D4 all fire so the four-dimension composite
                        carries a >=2 event inside the burn-in (a fresh_at without the data_ok clause admits it)
  A2 sessions 125..140  24 groups rise: the S-D3 share reaches 60 on the session on which the memories D2 and
                        D4 opened by episode A expire, so "n_dimensions increases" (the frozen event rule) and
                        "any dimension newly on" (a near-miss) disagree there; the generator asserts it
  B  sessions 300..359  24 groups rise, group g turning at 300 + g: the share climbs 2.5 points a session and
                        reaches exactly 55.0 (22 groups) on the first session the frozen rule fires; a 19-session
                        window fires one session earlier, a strict ">" rule one later
  C  sessions 360..364  decline, then rise from 365: the share re-crosses after 9 sessions below (no event)
  C2 sessions 400..419  decline, then rise from 420: about 29 sessions below, fresh event at the re-cross
  D1 session 470        34 groups (85 per cent) step and plateau to 480; groups 34-35 step at 479 and plateau
                        to 489: the S-D2 share is 5.0 at 479 under the frozen rule and 90.0 under an 11-session
                        or exclude-today average (which would then fire)
  D2 session 500        38 groups step (95.0 per cent): fresh S-D2 event; the S-D3 share re-crosses after 19
                        sessions below, so no S-D3 event
  D3 session 520        38 groups step after 11 sessions below: no fresh S-D2 event
  D4 session 550        36 groups step after 21 sessions below: exactly 90.0, fresh S-D2 event
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "ws10"
ROOT = HERE.parent
SPEC = ROOT / "spec" / "ws10_prereg_spec.json"

N_SESSIONS = 572
N_GROUPS = 40
PER_GROUP = 20
N_NAMES = N_GROUPS * PER_GROUP
# ln(1 + RISE) = 0.003992; -ln(1 + DECLINE) = 0.003685; the ratio 0.480 puts the frozen 20-session
# window's first closing high on the 10th up close and a 19-session window's on the 9th (see the docstring).
DECLINE = -0.003678
RISE = 0.004
STEP = 0.10            # a step must clear the window's prior (higher) closes after a decline: 10 per cent does
VOLUME = 1_000_000.0
LATE_ENTRANT = "N798"  # no close before session 300
INTERIOR_GAP = "N799"  # no close on sessions 340..345
ENTRANT_FROM = 300
GAP_RANGE = (340, 345)

# Episode table: (groups, kind, start, end) with end inclusive; "rise" sets the daily factor to RISE on
# start..end; "step" sets STEP on start and 0.0 (exactly flat) on start+1..end.
EPISODES = [
    (range(0, 38), "step", 60, 60),                         # A, inside the burn-in: 95 per cent step ...
    (range(0, 38), "rise", 61, 70),                         # ... then ten sessions of rise
    (range(0, 24), "rise", 125, 140),                       # A2, the memory-expiry coincidence
    *[(range(g, g + 1), "rise", 300 + g, 359) for g in range(24)],   # B, staggered turns
    (range(0, 24), "rise", 365, 399),                       # C, after 5 sessions of decline
    (range(0, 24), "rise", 420, 469),                       # C2, after 20 sessions of decline
    (range(0, 34), "step", 470, 480),                       # D1a, 34 groups
    (range(34, 36), "step", 479, 489),                      # D1b, 2 groups
    (range(0, 38), "step", 500, 510),                       # D2, 38 groups
    (range(0, 38), "step", 520, 530),                       # D3, 38 groups, 11 sessions below
    (range(0, 36), "step", 550, 560),                       # D4, 36 groups = exactly 90.0
]

CHECK_SESSIONS = [60, 70, 134, 251, 310, 315, 328, 329, 330, 331, 350, 360, 369, 400, 428, 429, 470, 478,
                  479, 480, 481, 490, 500, 508, 509, 519, 520, 529, 549, 550, 560]


def calendar() -> pd.DatetimeIndex:
    # start + periods, never end-on-a-weekend + periods (pandas 3.0.0 returns one fewer there)
    return pd.bdate_range("2019-01-02", periods=N_SESSIONS)


def _group_factors(g: int) -> np.ndarray:
    r = np.full(N_SESSIONS, DECLINE)
    for groups, kind, start, end in EPISODES:
        if g not in groups:
            continue
        if kind == "rise":
            r[start:end + 1] = RISE
        elif kind == "step":
            r[start] = STEP
            r[start + 1:end + 1] = 0.0
    return 1.0 + r


def planted() -> tuple[pd.DataFrame, pd.DataFrame]:
    cal = calendar()
    cols = {}
    for g in range(N_GROUPS):
        path = 100.0 * np.cumprod(_group_factors(g))
        for i in range(PER_GROUP):
            name = g * PER_GROUP + i
            cols[f"N{name:03d}"] = path * (1.0 + name * 1e-6)   # cosmetic per-name scale
    close = pd.DataFrame(cols, index=cal)
    close.iloc[:ENTRANT_FROM, close.columns.get_loc(LATE_ENTRANT)] = np.nan
    close.iloc[GAP_RANGE[0]:GAP_RANGE[1] + 1, close.columns.get_loc(INTERIOR_GAP)] = np.nan
    volume = pd.DataFrame(VOLUME, index=cal, columns=close.columns)
    volume[close.isna()] = np.nan
    return close, volume


def panel_sha256(close: pd.DataFrame) -> str:
    arr = np.ascontiguousarray(close.to_numpy(dtype="float64"))
    arr = np.where(np.isnan(arr), -1.0, arr)          # NaN bytes are not unique; map them to a sentinel
    return hashlib.sha256(arr.tobytes()).hexdigest()


# ---------------------------------------------------------------- reference implementation: members and events

def spec() -> dict:
    return json.loads(SPEC.read_text(encoding="utf-8"))


def ref_share(close: pd.DataFrame, member: str, sp: dict | None = None) -> pd.Series:
    """Candidate share in per cent: 100 * count / members, multiplication first (spec shared.share_formula).
    A member counts only with the required history: a close inside a window of NaN gives a NaN statistic and
    the name leaves both numerator and denominator (no forward fill, no padding)."""
    sp = sp or spec()
    c = sp["candidates"][member]
    w = int(c["window_sessions"])
    floor = int(sp["candidates"]["shared"]["share_nan_below_members"])
    if member == "S-D3":
        stat = close.rolling(w, min_periods=w).max()
        hit = close >= stat
    elif member == "S-D2":
        stat = close.rolling(w, min_periods=w).mean()
        hit = close > stat
    else:
        raise ValueError(member)
    valid = close.notna() & stat.notna()
    num = (hit & valid).sum(axis=1).astype(float)
    den = valid.sum(axis=1).astype(float)
    share = 100.0 * num / den.replace(0.0, np.nan)
    share[den < floor] = np.nan
    share.name = member
    return share


def ref_daily_fire(share: pd.Series, threshold: float) -> pd.Series:
    out = (share >= threshold).fillna(False).astype(bool)
    out.name = share.name
    return out


def ref_fresh_events(share: pd.Series, threshold: float, data_ok: pd.Series, below_sessions: int) -> pd.DatetimeIndex:
    """First session at or above the threshold after `below_sessions` consecutive DEFINED sessions strictly
    below; admitted on data_ok sessions at or after the first data_ok session only."""
    ok_idx = data_ok.index[data_ok.astype(bool)]
    if len(ok_idx) == 0:
        raise RuntimeError("BurnInRefusal: no data_ok session on this panel")
    first_ok = ok_idx[0]
    vals = share.to_numpy(dtype=float)
    below = np.isfinite(vals) & (vals < threshold)
    at_or_above = np.isfinite(vals) & (vals >= threshold)
    out = []
    run = 0
    for i, d in enumerate(share.index):
        if at_or_above[i]:
            if run >= below_sessions and d >= first_ok and bool(data_ok.loc[d]):
                out.append(d)
            run = 0
        elif below[i]:
            run += 1
        else:
            run = 0
    return pd.DatetimeIndex(out)


def ref_member_fresh_fires(boolean: pd.Series, data_ok: pd.Series, below_sessions: int) -> pd.DatetimeIndex:
    """First session a member's daily boolean is True after `below_sessions` consecutive sessions False,
    restricted to data_ok sessions."""
    b = boolean.fillna(False).astype(bool).to_numpy()
    out, run = [], 0
    for i, d in enumerate(boolean.index):
        if b[i]:
            if run >= below_sessions and bool(data_ok.loc[d]):
                out.append(d)
            run = 0
        else:
            run += 1
    return pd.DatetimeIndex(out)


def ref_cofire_share(cand: pd.DatetimeIndex, fires: pd.DatetimeIndex, sessions: pd.DatetimeIndex, window: int) -> float:
    """Per cent of candidate events with a member fire at most `window` sessions away in EITHER direction."""
    if len(cand) == 0:
        return float("nan")
    pos = {d: i for i, d in enumerate(sessions)}
    fire_pos = np.array(sorted(pos[d] for d in fires), dtype=int)
    hits = 0
    for d in cand:
        i = pos[d]
        if len(fire_pos) and np.any(np.abs(fire_pos - i) <= window):
            hits += 1
    return 100.0 * hits / len(cand)


def ref_composite_with_members(panels, extra: dict, config=None, cb=None, newly_on_rule: bool = False) -> pd.DataFrame:
    """compute_composite with candidate daily booleans OR-ed into their dimensions; identical to the engine's
    function when every extra boolean is False. `newly_on_rule` is the near-miss event rule used only by the
    generator to assert that the planted coincidence discriminates it."""
    import compute_breadth as _cb
    cb = cb or _cb
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
    df["score"] = sum(df[f"{d}_on"].astype(float) * w[d] for d in ("d1", "d2", "d3", "d4"))
    if newly_on_rule:
        newly = pd.concat([df[c] & ~df[c].shift(1).fillna(False).astype(bool) for c in on_cols], axis=1).any(axis=1)
        df["event"] = newly.astype(bool)
    else:
        df["event"] = (df["n_dimensions"] > df["n_dimensions"].shift(1).fillna(0)).astype(bool)
    df["valid_count"] = panels.valid_count
    computable = (panels.ma_valid_count >= cb.MIN_VALID_CONSTITUENTS) & (panels.hl_valid_count >= cb.MIN_VALID_CONSTITUENTS)
    df["burn_in"] = ~computable
    df["data_ok"] = (panels.valid_count >= cb.MIN_VALID_CONSTITUENTS) & computable
    return df


def ref_fresh_at(comp: pd.DataFrame, thr: int) -> pd.DatetimeIndex:
    sel = comp["event"].astype(bool) & (comp["n_dimensions"] >= thr) & comp["data_ok"].astype(bool)
    return pd.DatetimeIndex(comp.index[sel])


def ref_added_events(before: pd.DataFrame, after: pd.DataFrame, thr: int) -> pd.DatetimeIndex:
    b = set(ref_fresh_at(before, thr))
    return pd.DatetimeIndex([d for d in ref_fresh_at(after, thr) if d not in b])


def ref_removed_events(before: pd.DataFrame, after: pd.DataFrame, thr: int) -> pd.DatetimeIndex:
    a = set(ref_fresh_at(after, thr))
    return pd.DatetimeIndex([d for d in ref_fresh_at(before, thr) if d not in a])


def ref_cluster_ids(dates: pd.DatetimeIndex, gap_days: int) -> list[int]:
    d = pd.DatetimeIndex(sorted(dates))
    ids, cur = [], 0
    for i in range(len(d)):
        if i > 0 and (d[i] - d[i - 1]).days > gap_days:
            cur += 1
        ids.append(cur)
    return ids


# ---------------------------------------------------------------- reference implementation: the comparator

def ref_complete_window_events(events: pd.DatetimeIndex, index_series: pd.Series, h: int) -> pd.DatetimeIndex:
    """Events whose LAGGED forward window is complete on the return series: position + 1 + h within the series."""
    idx = index_series.sort_index().index
    pos = {d: i for i, d in enumerate(idx)}
    last = len(idx) - 1
    return pd.DatetimeIndex([d for d in sorted(events) if d in pos and pos[d] + 1 + h <= last])


def ref_lagged_returns(events: pd.DatetimeIndex, index_series: pd.Series, h: int) -> np.ndarray:
    s = index_series.sort_index()
    idx = s.index
    px = s.to_numpy(dtype=float)
    pos = {d: i for i, d in enumerate(idx)}
    last = len(idx) - 1
    out = []
    for d in sorted(events):
        i = pos[d]
        if i + 1 + h <= last:
            out.append(px[i + 1 + h] / px[i + 1] - 1.0)
    return np.array(out, dtype=float)


def ref_forward_stats(events: pd.DatetimeIndex, index_series: pd.Series, h: int) -> dict:
    r = ref_lagged_returns(events, index_series, h)
    return {"n": int(len(r)), "win_rate": float((r > 0).mean()) if len(r) else float("nan"),
            "median": float(np.median(r)) if len(r) else float("nan")}


def ref_null_sets(events: pd.DatetimeIndex, valid_sessions: pd.DatetimeIndex, index_series: pd.Series, h: int,
                  draws: int, seed_key, gap_days: int, max_restarts: int = 10_000) -> list[pd.DatetimeIndex]:
    """The pinned sampler (spec null.placement). Clusters of the complete-window treatment events are placed
    SEQUENTIALLY in chronological order; each cluster's start is drawn uniformly over the positions of
    `valid_sessions` on which the whole cluster fits, every event's lagged window is complete on the return
    series, and every event is more than `gap_days` calendar days from every event already placed in the
    draw; a cluster with no admissible position restarts the whole draw; `max_restarts` restarts for one draw
    is a STOP. One rng.integers call per cluster placement, on numpy.random.default_rng(seed_key)."""
    idx = index_series.sort_index().index
    ipos = {d: i for i, d in enumerate(idx)}
    v = pd.DatetimeIndex(sorted(valid_sessions))
    vpos = {d: j for j, d in enumerate(v)}
    treat = ref_complete_window_events(events, index_series, h)
    if len(treat) == 0:
        return [pd.DatetimeIndex([]) for _ in range(draws)]
    for d in treat:
        if d not in vpos:
            raise RuntimeError("NonSessionDate: treatment event outside valid_sessions")
    ids = ref_cluster_ids(treat, gap_days)
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
                raise RuntimeError("Stop: null placement failed after max_restarts")
            placed_days: list[int] = []
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
                    adm &= complete[o:o + n]
                if placed_days:
                    pdays = np.array(placed_days)
                    for o in offs:
                        dist = np.abs(vdays[o:o + n][:, None] - pdays[None, :])
                        adm &= (dist > gap_days).all(axis=1)
                cand = np.flatnonzero(adm)
                if len(cand) == 0:
                    ok = False
                    break
                j = int(cand[rng.integers(len(cand))])
                for o in offs:
                    placed_days.append(int(vdays[j + o]))
                    placed_dates.append(v[j + o])
            if ok:
                break
        out.append(pd.DatetimeIndex(sorted(placed_dates)))
    return out


def ref_null_draws(events, valid_sessions, index_series, h, draws, seed_key, gap_days) -> np.ndarray:
    sets = ref_null_sets(events, valid_sessions, index_series, h, draws, seed_key, gap_days)
    rows = []
    for s in sets:
        st = ref_forward_stats(s, index_series, h)
        rows.append([st["win_rate"], st["median"]])
    return np.array(rows, dtype=float)


def ref_mc_p(observed: float, draw_values: np.ndarray) -> float:
    return (1.0 + float(np.sum(draw_values >= observed))) / (1.0 + len(draw_values))


def ref_power(events, valid_sessions, index_series, h, delta_pp: float, null_values: np.ndarray, draws: int,
              seed_key, gap_days: int, alpha: float, family_size: int) -> float:
    """Share of random sets with the treatment's structure whose max(p_win, p_med), after +delta_pp is added
    to every lagged forward return, is at or below alpha / family_size against `null_values`."""
    sets = ref_null_sets(events, valid_sessions, index_series, h, draws, seed_key, gap_days)
    bar = alpha / family_size
    hits = 0
    for s in sets:
        r = ref_lagged_returns(s, index_series, h) + delta_pp / 100.0
        p = max(ref_mc_p(float((r > 0).mean()), null_values[:, 0]), ref_mc_p(float(np.median(r)), null_values[:, 1]))
        hits += int(p <= bar)
    return hits / draws


def ref_self_drill(events, valid_sessions, index_series, h, null_values: np.ndarray, drill_draws: int, seed_key,
                   gap_days: int, alpha: float, win_band: float, median_band_pp: float) -> dict:
    """P0-6. Centring leg (the STOP): the null's mean per-draw win rate and median against the unconditional
    complete-window lagged figures over the valid sessions, an independent reference. Size leg (reported):
    the share of `drill_draws` random sets whose max(p_win, p_med) against the null is at or below alpha."""
    r = ref_lagged_returns(pd.DatetimeIndex(valid_sessions), index_series, h)
    unc_win = float((r > 0).mean())
    unc_med = float(np.median(r))
    null_win = float(null_values[:, 0].mean())
    null_med = float(null_values[:, 1].mean())
    sets = ref_null_sets(events, valid_sessions, index_series, h, drill_draws, seed_key, gap_days)
    small = 0
    for s in sets:
        st = ref_forward_stats(s, index_series, h)
        p = max(ref_mc_p(st["win_rate"], null_values[:, 0]), ref_mc_p(st["median"], null_values[:, 1]))
        small += int(p <= alpha)
    return {"unconditional_win_rate": unc_win, "unconditional_median": unc_med,
            "null_mean_win_rate": null_win, "null_mean_median": null_med,
            "centring_pass": bool(abs(null_win - unc_win) <= win_band and abs(null_med - unc_med) * 100.0 <= median_band_pp),
            "size_share_at_alpha": small / drill_draws}


# ---------------------------------------------------------------- the deterministic unit path for the comparator

UNIT_SESSIONS = 1200


def unit_index() -> pd.Series:
    """A zero-drift triangle path: +0.3 per cent a session for 150 sessions then -0.3 per cent for 150, repeated;
    cumulative products only, so bit-identical everywhere; 63-session forward returns are positive on about
    half the sessions and never exactly zero."""
    cal = pd.bdate_range("2010-01-04", periods=UNIT_SESSIONS)
    r = np.where((np.arange(UNIT_SESSIONS) // 150) % 2 == 0, 0.003, -0.003)
    return pd.Series(100.0 * np.cumprod(1.0 + r), index=cal, name="unit")


def unit_valid(index: pd.Series) -> pd.DatetimeIndex:
    return index.index[251:]


def unit_events(index: pd.Series) -> pd.DatetimeIndex:
    """Twelve clusters of two events (offsets 0 and 7 sessions), 70 sessions apart from 300."""
    cal = index.index
    return pd.DatetimeIndex(sorted([cal[300 + 70 * k] for k in range(12)] + [cal[307 + 70 * k] for k in range(12)]))


def many_clusters_events(index: pd.Series, n: int = 30) -> pd.DatetimeIndex:
    cal = index.index
    return pd.DatetimeIndex([cal[260 + 28 * k] for k in range(n)])


# ---------------------------------------------------------------- expected values

def expected(close: pd.DataFrame, volume: pd.DataFrame) -> dict:
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import compute_breadth as cb

    sp = spec()
    cal = close.index
    panels = cb.build_panels(close, volume)
    before = cb.compute_composite(panels)
    data_ok = before["data_ok"]
    first_ok_i = int(np.argmax(data_ok.to_numpy()))
    first_ok = cal[first_ok_i]
    below = int(sp["candidates"]["shared"]["below_sessions"])

    out = {"panel_sha256": panel_sha256(close), "n_sessions": int(len(cal)), "n_names": int(close.shape[1]),
           "first_session": str(cal[0].date()), "last_session": str(cal[-1].date()),
           "first_data_ok_session": str(first_ok.date()), "first_data_ok_index": first_ok_i,
           "late_entrant": {"name": LATE_ENTRANT, "first_close_session": str(cal[ENTRANT_FROM].date())},
           "interior_gap": {"name": INTERIOR_GAP, "sessions": [str(cal[GAP_RANGE[0]].date()), str(cal[GAP_RANGE[1]].date())]},
           "shares": {}, "fresh_events": {}, "daily_fire_counts": {}, "first_defined": {}}
    assert data_ok.iloc[first_ok_i:].all(), "the planted gaps must not blank data_ok after the burn-in"
    extras = {}
    for member in ("S-D3", "S-D2"):
        c = sp["candidates"][member]
        share = ref_share(close, member, sp)
        thr = float(c["threshold_pct"])
        out["shares"][member] = {str(cal[i].date()): (None if not np.isfinite(share.iloc[i]) else float(share.iloc[i]))
                                 for i in CHECK_SESSIONS}
        ev = ref_fresh_events(share, thr, data_ok, below)
        out["fresh_events"][member] = [str(d.date()) for d in ev]
        fire = ref_daily_fire(share, thr)
        out["daily_fire_counts"][member] = int(fire.sum())
        extras[c["dimension"]] = fire
        out["first_defined"][member] = str(share.first_valid_index().date())
    after = ref_composite_with_members(panels, extras, cb=cb)
    out["h_m"] = {
        # the OR itself, pinned directly: the 60-session memory can absorb a dimension REPLACED by its
        # candidate, so n_dimensions and the event set alone would not reject that mutation
        "after_dim_true_counts": {dim: int(after[dim].sum()) for dim in ("d1", "d2", "d3", "d4")},
        "before_dim_true_counts": {dim: int(before[dim].sum()) for dim in ("d1", "d2", "d3", "d4")},
        "after_event_count_all_sessions": int(after["event"].sum()),
        "before_event_count_all_sessions": int(before["event"].sum()),
    }
    for thr in (2, 3):
        out["h_m"][f"ge{thr}"] = {
            "before": [str(d.date()) for d in ref_fresh_at(before, thr)],
            "after": [str(d.date()) for d in ref_fresh_at(after, thr)],
            "added": [str(d.date()) for d in ref_added_events(before, after, thr)],
            "removed": [str(d.date()) for d in ref_removed_events(before, after, thr)],
        }
    # a >=2 event of the four-dimension composite INSIDE the burn-in, which fresh_at must refuse
    inside = before.index[before["event"].astype(bool) & (before["n_dimensions"] >= 2) & ~data_ok.astype(bool)]
    assert len(inside) > 0, "episode A must produce a >=2 composite event inside the burn-in"
    out["h_m"]["ge2_events_inside_burn_in"] = [str(d.date()) for d in inside]
    # the planted coincidence: the frozen event rule and the "any dimension newly on" rule disagree
    newly = ref_composite_with_members(panels, extras, cb=cb, newly_on_rule=True)
    disagree = after.index[after["event"].astype(bool) != newly["event"].astype(bool)]
    assert len(disagree) > 0, "the memory-expiry coincidence (episode A2) must be planted"
    out["h_m"]["event_rule_discriminating_sessions"] = [str(d.date()) for d in disagree]
    # member fresh fires and redundancy on the planted panel
    members = sp["engine"]["members"]
    fires = {}
    for dim, names in members.items():
        for m in names:
            fires[m] = [str(d.date()) for d in ref_member_fresh_fires(before[m], data_ok, below)]
    out["member_fresh_fires"] = fires
    win = int(sp["redundancy"]["window_sessions"])
    out["redundancy"] = {}
    for member in ("S-D3", "S-D2"):
        c = sp["candidates"][member]
        cand = pd.DatetimeIndex(pd.to_datetime(out["fresh_events"][member]))
        own = pd.DatetimeIndex(sorted({pd.Timestamp(x) for m in members[c["dimension"]] for x in fires[m]}))
        d1 = pd.DatetimeIndex(sorted({pd.Timestamp(x) for m in members["d1"] for x in fires[m]}))
        d4 = pd.DatetimeIndex(sorted({pd.Timestamp(x) for m in members["d4"] for x in fires[m]}))
        out["redundancy"][member] = {"own": ref_cofire_share(cand, own, cal, win),
                                     "d1": ref_cofire_share(cand, d1, cal, win),
                                     "d4": ref_cofire_share(cand, d4, cal, win)}
    # calendar boundaries on the fixture calendar: 21 sessions on from the last session of 2019 (year) and
    # from the last February 2020 session (month), stated so a defect is caught rather than a fixture rewritten
    h1m = int(sp["horizons"]["sessions"]["1m"])
    bounds = {}
    for start in ("2019-12-31", "2020-02-28"):
        i = cal.get_loc(pd.Timestamp(start))
        bounds[start] = str(cal[i + h1m].date())
    out["boundaries_1m"] = bounds
    out["cluster_known_case"] = {"dates": ["2020-01-02", "2020-02-03", "2020-04-10"], "ids": ref_cluster_ids(pd.to_datetime(["2020-01-02", "2020-02-03", "2020-04-10"]), 63),
                                 "dates_b": ["2020-01-02", "2020-02-03", "2020-04-06"], "ids_b": ref_cluster_ids(pd.to_datetime(["2020-01-02", "2020-02-03", "2020-04-06"]), 63)}
    # the comparator on the deterministic unit path: pinned draws, statistics, power and the self-drill
    gap = int(sp["clusters"]["gap_calendar_days"])
    h3m = int(sp["horizons"]["sessions"]["3m"])
    alpha = float(sp["holm"]["alpha"])
    fam = 3
    ui = unit_index()
    uv = unit_valid(ui)
    ue = unit_events(ui)
    sets3 = ref_null_sets(ue, uv, ui, h3m, 3, [19901228, 0], gap)
    null300 = ref_null_draws(ue, uv, ui, h3m, 300, [19901228, 0], gap)
    treat = ref_forward_stats(ue, ui, h3m)
    powers = {str(d): ref_power(ue, uv, ui, h3m, d, null300, 100, [19901228, 1000], gap, alpha, fam) for d in (0.0, 3.0, 10.0, 50.0)}
    drill = ref_self_drill(ue, uv, ui, h3m, null300, 100, [19901228, 2000], gap, alpha,
                           float(sp["self_drill"]["win_band"]), float(sp["self_drill"]["median_band_pp"]))
    many = ref_null_sets(many_clusters_events(ui), uv, ui, h3m, 2000, [19901228, 5], gap)
    out["null_unit"] = {
        "sessions": UNIT_SESSIONS, "first_session": str(ui.index[0].date()), "valid_from_index": 251,
        "events": [str(d.date()) for d in ue], "n_complete": int(len(ref_complete_window_events(ue, ui, h3m))),
        "treatment_3m": treat,
        "first_three_draws_seed_0": [[str(d.date()) for d in s] for s in sets3],
        "null300_mean_win_rate": float(null300[:, 0].mean()), "null300_mean_median": float(null300[:, 1].mean()),
        "null300_win_rate_p95": float(np.percentile(null300[:, 0], 95)), "null300_median_p95": float(np.percentile(null300[:, 1], 95)),
        "p_win_treatment": ref_mc_p(treat["win_rate"], null300[:, 0]), "p_med_treatment": ref_mc_p(treat["median"], null300[:, 1]),
        "power_by_delta_pp": powers, "self_drill": drill,
        "many_clusters": {"n_clusters": 30, "draws": 2000, "completed": len(many), "all_count_matched": bool(all(len(s) == 30 for s in many))},
    }
    assert powers["50.0"] == 1.0, "the saturation case must be attainable by a correct engine"
    assert 0.05 < powers["10.0"] < 0.95, "a mid-range power is needed to discriminate the alpha and unit mutants"
    assert drill["centring_pass"], "the self-drill's centring leg must pass on its own generator"
    return out


def main() -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    close, volume = planted()
    exp = expected(close, volume)
    (FIX / "expected.json").write_bytes((json.dumps(exp, indent=1) + "\n").encode("utf-8"))
    lines = ["# WS10 FIXTURE — planted panel and expected values", "",
             "Synthetic, deterministic, no market data, no random numbers in the panel. Regenerate with",
             "`python tests/make_ws10_fixture.py`; `tests/test_ws10_contract.py` compares the engine with",
             "`tests/fixtures/ws10/expected.json`; `tests/test_ws10_mutants.py` proves the committed wrong engine",
             "fails these expectations while the reference passes.", "",
             f"Panel sha256 `{exp['panel_sha256']}`; {exp['n_sessions']} sessions {exp['first_session']} to",
             f"{exp['last_session']}, {exp['n_names']} names; first data_ok session {exp['first_data_ok_session']}",
             f"(index {exp['first_data_ok_index']}); late entrant {exp['late_entrant']['name']} from",
             f"{exp['late_entrant']['first_close_session']}; interior gap {exp['interior_gap']['name']} on",
             f"{exp['interior_gap']['sessions'][0]} to {exp['interior_gap']['sessions'][1]}. Episodes are documented in",
             "the generator's docstring.", "",
             "| Candidate | first defined | fresh events | daily fire sessions |", "|---|---|---|---|"]
    for m in ("S-D3", "S-D2"):
        lines.append(f"| {m} | {exp['first_defined'][m]} | {', '.join(exp['fresh_events'][m])} | {exp['daily_fire_counts'][m]} |")
    lines += ["", "| Session | date | S-D3 share | S-D2 share |", "|---|---|---|---|"]
    cal = close.index
    for i in CHECK_SESSIONS:
        d = str(cal[i].date())
        lines.append(f"| {i} | {d} | {exp['shares']['S-D3'][d]} | {exp['shares']['S-D2'][d]} |")
    lines += ["", "H-M on the planted panel (fresh events at the threshold, data_ok sessions only):", ""]
    for k in ("ge2", "ge3"):
        v = exp["h_m"][k]
        lines.append(f"- {k}: before {v['before']}; after {v['after']}; ADDED {v['added']}; REMOVED {v['removed']}")
    lines.append(f"- dimension booleans True (all sessions), before {exp['h_m']['before_dim_true_counts']} and after "
                 f"{exp['h_m']['after_dim_true_counts']}: the OR pinned directly, because the 60-session memory can hide "
                 f"a dimension replaced by its candidate")
    lines.append(f"- composite event count over all sessions, before {exp['h_m']['before_event_count_all_sessions']} and after "
                 f"{exp['h_m']['after_event_count_all_sessions']}; >=2 events inside the burn-in (refused): "
                 f"{exp['h_m']['ge2_events_inside_burn_in']}; the frozen event rule and the newly-on near-miss disagree on "
                 f"{exp['h_m']['event_rule_discriminating_sessions']}")
    lines += ["", f"Redundancy shares (per cent, window {spec()['redundancy']['window_sessions']} sessions): {exp['redundancy']}", "",
              f"Member fresh fires: { {k: len(v) for k, v in exp['member_fresh_fires'].items()} }", "",
              f"Calendar boundaries, 21 sessions on (fixture calendar): {exp['boundaries_1m']}", "",
              "Comparator on the deterministic unit path (triangle, 1,200 sessions, 24 events in 12 clusters):", ""]
    nu = exp["null_unit"]
    lines += [f"- treatment 3m {nu['treatment_3m']}; complete-window events {nu['n_complete']}",
              f"- first three draws, seed key [19901228, 0]: {nu['first_three_draws_seed_0']}",
              f"- null (300 draws) mean win rate {nu['null300_mean_win_rate']:.6f}, mean median {nu['null300_mean_median']:.6f}; "
              f"p_win {nu['p_win_treatment']:.6f}, p_med {nu['p_med_treatment']:.6f}",
              f"- power at +0 / +3 / +10 / +50pp per 3 months (100 draws, alpha/3): {nu['power_by_delta_pp']}",
              f"- self-drill: {nu['self_drill']}",
              f"- thirty singleton clusters, 2,000 draws: completed {nu['many_clusters']['completed']}, count-matched {nu['many_clusters']['all_count_matched']}", ""]
    (HERE / "WS10_FIXTURE.md").write_bytes(("\n".join(lines)).encode("utf-8"))
    print("fixture written:", sorted(p.name for p in FIX.iterdir()))
    print(json.dumps({k: exp[k] for k in ("panel_sha256", "first_data_ok_session", "fresh_events", "redundancy", "boundaries_1m", "first_defined")}, indent=1))
    print(json.dumps({k: v for k, v in exp["h_m"].items()}, indent=1))
    print(json.dumps(exp["null_unit"], indent=1))
    print("shares at check sessions:")
    for i in CHECK_SESSIONS:
        d = str(cal[i].date())
        print(i, d, exp["shares"]["S-D3"][d], exp["shares"]["S-D2"][d])


if __name__ == "__main__":
    main()
