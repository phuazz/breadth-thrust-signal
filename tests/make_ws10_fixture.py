"""Planted synthetic fixture for the WS10 (thrust-subconditions) contract tests.

Deterministic, no market data, no random number generator and no transcendental function: every
price is a cumulative PRODUCT of planted daily factors (IEEE multiplication is exactly rounded, so
the panel is bit-identical on every platform). The expected values come from a plain reference
implementation of the frozen rules in ``spec/ws10_prereg_spec.json``; ``tests/test_ws10_mutants.py``
proves that the committed wrong engine in ``tests/mutants/ws10_wrong.py`` FAILS these expectations
while this reference passes them. Regenerate with ``python tests/make_ws10_fixture.py``; the
contract tests rebuild the panel in memory and compare it with the committed hash.

Panel: 400 names in 20 groups of 20, 572 sessions on a business-day calendar from 2019-01-02
(Python months are 1-indexed, January == 1; every date operation goes through pandas). Group paths:
a slow decline by default (-0.355 per cent a session), planted rises (+0.4 per cent a session) and
planted steps (+1 per cent on one session, then exactly flat). The rates are chosen so that, after a
V-turn, a name reaches its 20-session closing high on the 10th up close under the frozen window and
on the 9th under a 19-session window, and so that a step followed by a flat plateau sits strictly
above its 10-session average for exactly nine sessions under the frozen inclusive window and for ten
under an 11-session or exclude-today variant. Exact-threshold shares are planted: 11 groups at a
20-session high is 220 of 400 = 55.0 per cent; 18 groups above their 10-session average is 360 of
400 = 90.0 per cent.

Planted episodes (session indices; the composite's burn-in ends at index 251, the 252nd session; the
dates and values the reference produces are the ones pinned in fixtures/ws10/expected.json and listed
in WS10_FIXTURE.md):
  A  sessions 60..110   groups 0-11 rise: the S-D3 share crosses 55 INSIDE the burn-in (refused)
  B  sessions 300..359  groups 0-11 rise, group g turning at 300 + 2g: the S-D3 share climbs in 5-point
                        steps and reaches exactly 55.0 (11 groups) on the first session the frozen rule
                        fires; a 19-session window fires one session earlier, a strict ">" rule two later
  C  sessions 360..364  decline, then rise from 365: the share re-crosses after 9 sessions below (no event)
  C2 sessions 400..419  decline, then rise from 420: about 29 sessions below, fresh event at the re-cross
  D1 session 470        17 groups step and plateau to 480; groups 17-18 step at 479 and plateau to 489: the
                        S-D2 share is 10.0 at 479 under the frozen rule and 95.0 under an 11-session or
                        exclude-today average
  D2 session 500        19 groups step (95.0 per cent): fresh S-D2 event; the S-D3 share re-crosses after
                        19 sessions below, so no S-D3 event
  D3 session 520        19 groups step after 11 sessions below: no fresh S-D2 event
  D4 session 550        18 groups step after 21 sessions below: exactly 90.0, fresh S-D2 event
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
N_GROUPS = 20
PER_GROUP = 20
N_NAMES = N_GROUPS * PER_GROUP
# ln(1 + RISE) = 0.003992; -ln(1 + DECLINE) = 0.003685; the ratio 0.480 puts the frozen 20-session
# window's first closing high on the 10th up close and a 19-session window's on the 9th (see the docstring).
DECLINE = -0.003678
RISE = 0.004
STEP = 0.10            # a step must clear the window's prior (higher) closes after a decline: 10 per cent does
VOLUME = 1_000_000.0

# Episode table: (groups, kind, start, end) with end inclusive; "rise" sets the daily factor to RISE on
# start..end; "step" sets STEP on start and 0.0 (exactly flat) on start+1..end.
EPISODES = [
    (range(0, 12), "rise", 60, 110),                        # A, inside the burn-in
    *[(range(g, g + 1), "rise", 300 + 2 * g, 359) for g in range(12)],   # B, staggered turns
    (range(0, 12), "rise", 365, 399),                       # C, after 5 sessions of decline
    (range(0, 12), "rise", 420, 469),                       # C2, after 20 sessions of decline
    (range(0, 17), "step", 470, 480),                       # D1a, 17 groups
    (range(17, 19), "step", 479, 489),                      # D1b, 2 groups
    (range(0, 19), "step", 500, 510),                       # D2, 19 groups
    (range(0, 19), "step", 520, 530),                       # D3, 19 groups, 11 sessions below
    (range(0, 18), "step", 550, 560),                       # D4, 18 groups = exactly 90.0
]

CHECK_SESSIONS = [70, 251, 310, 327, 328, 329, 331, 360, 369, 400, 428, 429, 470, 478, 479, 480, 481,
                  490, 500, 508, 509, 519, 520, 529, 549, 550, 560]


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
    volume = pd.DataFrame(VOLUME, index=cal, columns=close.columns)
    return close, volume


def panel_sha256(close: pd.DataFrame) -> str:
    return hashlib.sha256(np.ascontiguousarray(close.to_numpy(dtype="float64")).tobytes()).hexdigest()


# ---------------------------------------------------------------- reference implementation

def spec() -> dict:
    return json.loads(SPEC.read_text(encoding="utf-8"))


def ref_share(close: pd.DataFrame, member: str, sp: dict | None = None) -> pd.Series:
    """Candidate share in per cent: 100 * count / members, multiplication first (spec shared.share_formula)."""
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
    return share


def ref_daily_fire(share: pd.Series, threshold: float) -> pd.Series:
    return (share >= threshold).fillna(False).astype(bool)


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


def ref_composite_with_members(panels, extra: dict, config=None, cb=None) -> pd.DataFrame:
    """compute_composite with candidate daily booleans OR-ed into their dimensions; identical to the engine's
    function when every extra boolean is False."""
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


def ref_cluster_ids(dates: pd.DatetimeIndex, gap_days: int) -> list[int]:
    d = pd.DatetimeIndex(sorted(dates))
    ids, cur = [], 0
    for i in range(len(d)):
        if i > 0 and (d[i] - d[i - 1]).days > gap_days:
            cur += 1
        ids.append(cur)
    return ids


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
    first_ok = cal[int(np.argmax(data_ok.to_numpy()))]
    below = int(sp["candidates"]["shared"]["below_sessions"])

    out = {"panel_sha256": panel_sha256(close), "n_sessions": int(len(cal)), "n_names": int(close.shape[1]),
           "first_session": str(cal[0].date()), "last_session": str(cal[-1].date()),
           "first_data_ok_session": str(first_ok.date()), "first_data_ok_index": int(np.argmax(data_ok.to_numpy())),
           "shares": {}, "fresh_events": {}, "daily_fire_counts": {}}
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
        fire.name = member
        out["daily_fire_counts"][member] = int(fire.sum())
        extras[c["dimension"]] = fire
        # the first session on which the share is defined at all
        out.setdefault("first_defined", {})[member] = str(share.first_valid_index().date())
    after = ref_composite_with_members(panels, extras, cb=cb)
    out["h_m"] = {
        # the OR itself, pinned directly: the 60-session memory can absorb a dimension REPLACED by its
        # candidate, so n_dimensions and the event set alone would not reject that mutation
        "after_dim_true_counts": {dim: int(after[dim].sum()) for dim in ("d1", "d2", "d3", "d4")},
        "before_dim_true_counts": {dim: int(before[dim].sum()) for dim in ("d1", "d2", "d3", "d4")},
    }
    for thr in (2, 3):
        out["h_m"][f"ge{thr}"] = {
            "before": [str(d.date()) for d in ref_fresh_at(before, thr)],
            "after": [str(d.date()) for d in ref_fresh_at(after, thr)],
            "added": [str(d.date()) for d in ref_added_events(before, after, thr)],
        }
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
    return out


def main() -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    close, volume = planted()
    exp = expected(close, volume)
    (FIX / "expected.json").write_bytes((json.dumps(exp, indent=1) + "\n").encode("utf-8"))
    lines = ["# WS10 FIXTURE — planted panel and expected values", "",
             "Synthetic, deterministic, no market data, no random numbers. Regenerate with",
             "`python tests/make_ws10_fixture.py`; `tests/test_ws10_contract.py` compares the engine with",
             "`tests/fixtures/ws10/expected.json`; `tests/test_ws10_mutants.py` proves the committed wrong engine",
             "fails these expectations while the reference passes.", "",
             f"Panel sha256 `{exp['panel_sha256']}`; {exp['n_sessions']} sessions {exp['first_session']} to",
             f"{exp['last_session']}, {exp['n_names']} names; first data_ok session {exp['first_data_ok_session']}",
             f"(index {exp['first_data_ok_index']}). Episodes are documented in the generator's docstring.", "",
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
        lines.append(f"- {k}: before {v['before']}; after {v['after']}; ADDED {v['added']}")
    lines.append(f"- dimension booleans True (all sessions), before {exp['h_m']['before_dim_true_counts']} and after "
                 f"{exp['h_m']['after_dim_true_counts']}: the OR pinned directly, because the 60-session memory can hide "
                 f"a dimension replaced by its candidate")
    lines += ["", f"Redundancy shares (per cent, window {spec()['redundancy']['window_sessions']} sessions): {exp['redundancy']}", "",
              f"Member fresh fires: { {k: len(v) for k, v in exp['member_fresh_fires'].items()} }", "",
              f"Calendar boundaries, 21 sessions on (fixture calendar): {exp['boundaries_1m']}", ""]
    (HERE / "WS10_FIXTURE.md").write_bytes(("\n".join(lines)).encode("utf-8"))
    print("fixture written:", sorted(p.name for p in FIX.iterdir()))
    print(json.dumps({k: exp[k] for k in ("panel_sha256", "first_data_ok_session", "fresh_events", "h_m", "redundancy", "boundaries_1m", "first_defined")}, indent=1))
    print("shares at check sessions:")
    for i in CHECK_SESSIONS:
        d = str(cal[i].date())
        print(i, d, exp["shares"]["S-D3"][d], exp["shares"]["S-D2"][d])


if __name__ == "__main__":
    main()
