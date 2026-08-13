"""Weekly Norgate parallel run — the soak harness gating the live-meter cutover.

Runs AFTER the Saturday csp1 refresh has published (wired in
run_weekly_refresh.bat, gated on the refresh succeeding). Alert-only: it
changes nothing deployed and writes aggregate statistics only, to git-ignored
data_local/ (vendor series values never leave the cache).

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


def log(msg: str) -> None:
    print(f"[parallel] {msg}", flush=True)


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

        deployed = json.loads((ROOT / "data" / "signals.json").read_text(encoding="utf-8"))
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
