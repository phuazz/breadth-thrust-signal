"""Weekly Norgate parallel run — the soak harness that gated the live-meter cutover.

STATUS 2026-09-02: the cutover is DONE and this script is RETIRED from
run_weekly_refresh.bat. Three clean runs discharged the gate (2026-08-22 —
record CLEAN, harness crashed on the summary print; 2026-08-27 manual after
that fix; 2026-08-29 scheduled, 10 of 10 edge sessions, task result 0) and the
wrapper flipped to ``--provider norgate``. From then on the deployed
data/signals.json IS the Norgate layer, so an edge comparison against it would
test the candidate against itself and read CLEAN by construction — a guard
that cannot fire is scaffolding, not a guard. ``assert_cross_layer`` refuses
that comparison outright (exit 1, no record written). Re-arm the script only
for a genuine cross-layer soak, e.g. a future re-cutover from the CSP1 fallback.

Original purpose, kept for the record. It ran AFTER the Saturday csp1 refresh
had published (wired in run_weekly_refresh.bat, gated on the refresh
succeeding). Alert-only: it changed nothing deployed and wrote aggregate
statistics only, to git-ignored data_local/ (vendor series values never leave
the cache).

What one run proves, per the 2026-08-13 scope memo:
  1. The Norgate candidate BUILDS end to end this week (depth gate, panel,
     composite, full payload) — the cutover path exercised for real.
  2. The candidate would have PASSED the cutover guard set
     (weekly_refresh.check_payload in norgate mode: as-of lag, window-extends,
     survivorship False, valid floor, provider tag, 1990-12-28 window pin).
  3. The candidate AGREES with the just-published CSP1 build on the last
     EDGE_DAYS common sessions' dimension flags and score. The two layers
     legitimately diverge in deep history (that is what WS7 measured); at the
     live edge both hold ~the same members and prices, so an edge mismatch
     means an implementation or data fault, not a layer difference.

Exit codes: 0 clean, 2 ALERT (any guard failure or edge mismatch — toast
fires), 1 operational error. The cutover session reads data_local/
parallel_last.json and the ALERT history; the soak bar is 1-2 consecutive
clean Saturdays.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import compute_breadth as cb  # noqa: E402
import pipeline as pl  # noqa: E402
import weekly_refresh as wr  # noqa: E402

OUT = ROOT / "data_local" / "parallel_last.json"
EDGE_DAYS = 10  # sessions compared at the live edge (vendor-guard convention)
CANDIDATE_PROVIDER = "norgate-pit"  # the layer this harness builds as the candidate


def assert_cross_layer(deployed: dict, candidate_provider: str = CANDIDATE_PROVIDER) -> str:
    """Refuse a same-layer comparison; return the deployed provider tag otherwise.

    The comparator's evidence is that two INDEPENDENT layers agree at the live
    edge. Once the deployed payload carries the candidate's own provider tag
    the two sides share every input, the mismatch count is zero by
    construction, and a CLEAN verdict would certify nothing. Raise, so that no
    record is written and the wrapper cannot mistake a tautology for a soak.
    """
    dep = (deployed.get("data_quality") or {}).get("provider")
    if dep == candidate_provider:
        raise ValueError(
            f"deployed payload already carries provider {dep!r} — a parallel run "
            f"would compare the {candidate_provider} candidate against itself; "
            f"nothing to soak (cutover done 2026-09-02)"
        )
    return dep

# Windows consoles default to cp1252, which cannot encode the arrow and dash
# this script's own summary line carries. Without this, a run whose verdict was
# CLEAN raised UnicodeEncodeError inside the final print() and exited non-zero.
#
# That is not cosmetic. The record is written BEFORE the summary is logged, so
# the soak produced a clean parallel_last.json and then reported failure — and
# run_weekly_refresh.bat chains on the exit code. The 2026-08-22 soak run sat
# that way until 2026-08-27: verdict CLEAN, zero alerts, ten of ten sessions
# agreeing, and read as a failed soak by anything looking at the exit code.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def log(msg: str) -> None:
    """Print a progress line. NEVER raises.

    Belt and braces over the reconfigure above: this is an unattended job whose
    exit code decides whether the wrapper treats the run as usable, so a
    progress message must not be able to fail it. If the stream still cannot
    encode a character, the line degrades to ASCII rather than taking the run
    down with it.
    """
    line = f"[parallel] {msg}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        print(line.encode(enc, errors="replace").decode(enc, errors="replace"), flush=True)


def compare_edge(timeline: dict, cand: pd.DataFrame, days: int = EDGE_DAYS) -> dict:
    """Pure edge comparison: deployed timeline dict vs candidate composite.

    Compares d1_on..d4_on and n_dimensions on the last ``days`` common
    sessions. Insufficient overlap is itself an alert condition — two live
    layers that cannot find ``days`` common sessions are misaligned.
    """
    dep = pd.DataFrame(
        {k: timeline[k] for k in ("n_dimensions", "d1_on", "d2_on", "d3_on", "d4_on")},
        index=pd.to_datetime(timeline["dates"]),
    )
    common = dep.index.intersection(cand.index)
    out: dict = {
        "days_requested": days,
        "days_compared": int(min(days, len(common))),
        "deployed_last": str(dep.index.max().date()) if len(dep) else None,
        "candidate_last": str(cand.index.max().date()) if len(cand) else None,
        "mismatches": [],
    }
    if len(common) < days:
        out["insufficient_overlap"] = True
        return out
    tail = common.sort_values()[-days:]
    for d in tail:
        for col in ("d1_on", "d2_on", "d3_on", "d4_on", "n_dimensions"):
            dv, cv = dep.loc[d, col], cand.loc[d, col]
            differs = (int(dv) != int(cv)) if col == "n_dimensions" else (bool(dv) != bool(cv))
            if differs:
                out["mismatches"].append(
                    {"date": str(d.date()), "field": col,
                     "deployed": int(dv), "candidate": int(cv)}
                )
    out["mismatch_days"] = len({m["date"] for m in out["mismatches"]})
    return out


def main() -> int:
    now = datetime.now(timezone.utc)
    alerts: list[str] = []
    try:
        # Cheapest check first, before the depth probe and the panel build: a
        # deployed payload on the candidate's own layer means there is nothing
        # to soak, and the refusal must land before any record could be written.
        deployed = json.loads((ROOT / "data" / "signals.json").read_text(encoding="utf-8"))
        assert_cross_layer(deployed)

        depth_fails = wr.check_depth(wr.collect_depth_probe(now))
        if depth_fails:
            alerts.extend(f"depth: {f}" for f in depth_fails)
            raise StopIteration  # skip the build; depth alone is the alert

        import norgate_provider as npv
        adj, vol, spx, dq = npv.live_panel(refresh_cache=True)
        dq["min_valid_constituents"] = cb.MIN_VALID_CONSTITUENTS
        panels = cb.build_panels(adj, vol)
        comp = cb.compute_composite(panels)
        payload = pl.build_payload(comp, spx.reindex(comp.index), False, dq, panels)

        guard_fails = wr.check_payload(payload, now, None, provider="norgate")
        alerts.extend(f"guard: {f}" for f in guard_fails)

        edge = compare_edge(deployed["timeline"], comp)
        if edge.get("insufficient_overlap"):
            alerts.append(f"edge: only {edge['days_compared']} common sessions")
        elif edge["mismatch_days"]:
            alerts.append(
                f"edge: {edge['mismatch_days']} of last {EDGE_DAYS} sessions disagree "
                + "; ".join(f"{m['date']} {m['field']}" for m in edge["mismatches"][:6])
            )
        record = {
            "run_utc": now.isoformat(),
            "verdict": "ALERT" if alerts else "CLEAN",
            "alerts": alerts,
            "candidate": {
                "as_of": payload["current"]["as_of"],
                "score": payload["current"]["score"],
                "valid_count": payload["current"]["valid_count"],
                "window": payload["study"]["window"],
                "members_per_day": dq.get("members_per_day"),
                "unfetchable_members": dq.get("unfetchable_members"),
            },
            "deployed_as_of": deployed.get("current", {}).get("as_of"),
            "edge": edge,
        }
    except StopIteration:
        record = {"run_utc": now.isoformat(), "verdict": "ALERT", "alerts": alerts}
    except Exception as e:  # noqa: BLE001 — operational failure, fail loudly
        log(f"ERROR: {e}")
        wr.toast("breadth-thrust-signal parallel run ERROR", str(e)[:180])
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2), encoding="utf-8")
    log(f"{record['verdict']}"
        + (f" — {' | '.join(alerts)}" if alerts else
           f" — edge agrees on {record['edge']['days_compared']} sessions, "
           f"window {record['candidate']['window']['start']} → "
           f"{record['candidate']['window']['end']}"))
    if alerts:
        wr.toast("breadth-thrust-signal parallel run ALERT", " | ".join(alerts)[:180])
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
