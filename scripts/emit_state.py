"""emit_state.py — publish the conviction meter in the STATE_CONTRACT shape.

WHAT THIS IS FOR
----------------
A private consumer (the command centre) renders this meter beside signals from
seven other projects. Until now it did that by reaching INTO this repo and
reading exact JSON pointers out of data/signals.json from its own side. That
works, and it is guarded there, but it puts knowledge of THIS repo's field names
in somebody else's codebase: rename a key here and the break surfaces over
there, days later, in a file nobody was editing at the time.

This writes `data/state.json` beside the signals it describes.

WHY THE ISOLATION IS EXPLICIT HERE, NOT ARCHITECTURAL
------------------------------------------------------
The five sibling emitters each run in their own GitHub workflow, so a failure
there physically cannot hold up the pipeline it reads from. This repo has NO
workflows — it is refreshed by a local scheduled task running
scripts/weekly_refresh.py, which publishes nothing if any guard fails. There is
no separate process to hide behind, so the isolation has to be written down
instead: weekly_refresh calls this inside a try/except and treats any failure as
a logged warning, never as a reason to withhold the meter's own publish.

That asymmetry is deliberate. The meter is the product; the emission is a
convenience for one private reader. A convenience must never be able to suppress
the product.

CADENCE IS `manual`, AND THAT IS NOT A DEFECT
-----------------------------------------------
This repo has no CI. It refreshes when the Saturday task runs, or when someone
runs it by hand, so the consumer badges the row MANUAL and shows its measured
age rather than a freshness tick it has not earned. The emission repeats
`cadence: manual` so that stays true on the consumer's side without it having
to know why.

WHAT IT IS NOT
--------------
  * NOT a new signal and not a recomputation. Every value is copied from a file
    this repo already publishes. If this and signals.json ever disagree,
    signals.json is right and this is broken.
  * NOT load-bearing here. Nothing in this repo reads data/state.json.

Usage:
    python scripts/emit_state.py           # write data/state.json
    python scripts/emit_state.py --check   # validate and print, write nothing
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
SOURCE_JSON = ROOT / "data" / "signals.json"
OUT = ROOT / "data" / "state.json"

CONTRACT_VERSION = "1"
SOURCE = "breadth-thrust-signal"
SIGNAL = "conviction_meter"

# The meter is 0..4 dimensions confirmed. The consumer holds the same list
# frozen; a score outside it is a rejection there, and catching it here names
# the file it came from.
SCORES = ("0", "1", "2", "3", "4")


class EmitError(Exception):
    """A required input was missing or malformed. Never emit a guess."""


def require(obj, path: str, kind=None):
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise EmitError(f"missing key `{part}` at pointer `{path}`")
        cur = cur[part]
    if cur is None:
        raise EmitError(f"pointer `{path}` is null")
    if kind is not None and not isinstance(cur, kind):
        # `kind` is often a tuple of accepted types, which has no __name__.
        want = kind.__name__ if isinstance(kind, type) else "/".join(k.__name__ for k in kind)
        raise EmitError(f"pointer `{path}` is {type(cur).__name__}, expected {want}")
    return cur


def load_signals():
    if not SOURCE_JSON.exists():
        raise EmitError(f"source file not found: {SOURCE_JSON}")
    try:
        return json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EmitError(f"signals.json is not valid JSON: {exc}") from exc


def score_label(score) -> str:
    """The meter's score as the consumer's categorical state.

    The score is stored as a float (1.0). It is a COUNT of confirmed dimensions,
    so a fractional value is not a rounding question — it means the pipeline
    produced something this does not understand, and is refused rather than
    truncated into a plausible integer.
    """
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise EmitError(f"current.score is {score!r}, expected a number")
    if float(score) != int(score):
        raise EmitError(f"current.score {score!r} is fractional — the meter counts dimensions")
    label = str(int(score))
    if label not in SCORES:
        raise EmitError(f"current.score {score!r} outside the meter's range {SCORES}")
    return label


def build() -> dict:
    d = load_signals()

    score = require(d, "current.score", (int, float))
    as_of = require(d, "current.as_of", str)
    dims = require(d, "current.dimensions", dict)
    generated = require(d, "generated_utc", str)

    if not dims:
        raise EmitError("current.dimensions is empty — there is nothing to describe")

    # Sorted so the description is stable across runs: an unordered dict would
    # otherwise churn the emission and show as a divergence that is not one.
    on = [k for k, v in sorted(dims.items()) if isinstance(v, dict) and v.get("on")]

    label = score_label(score)
    if len(on) != int(score):
        raise EmitError(
            f"current.score is {int(score)} but {len(on)} dimension(s) are flagged on "
            f"({on}) — the score and its dimensions disagree"
        )

    return {
        "contract_version": CONTRACT_VERSION,
        "emitted_by": SOURCE,
        "emitted_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "signals": {
            SIGNAL: {
                "as_of": as_of,
                "state": label,
                "value": score,
                "zone": f"dimensions on: {', '.join(on) if on else 'none'}",
                "role": "view-only",
                "horizon": "6m",
                "evidence_grade": "informational",
                "licence": "public",
                "action_hint": "none",
                "source_file": "data/signals.json",
                "computed_at": generated,
                "cadence": "manual",
            }
        },
    }


def unchanged(payload: dict) -> bool:
    """Same emission as the one on disk, apart from the run's own timestamp?

    `generated_utc` moves on every rebuild, so `computed_at` changes whenever the
    pipeline runs and the emission genuinely differs then. What this suppresses
    is the pure no-op: a rerun against an unchanged signals.json, where only this
    script's own timestamp would have moved.
    """
    if not OUT.exists():
        return False
    try:
        prev = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    strip = lambda d: {k: v for k, v in d.items() if k != "emitted_at"}
    return strip(prev) == strip(payload)


def emit(log=print) -> bool:
    """Write the emission. Returns True on success, False on any failure.

    This is the entry point weekly_refresh.py calls. It NEVER raises: a failure
    here must not be able to withhold the meter's own publish, and there is no
    separate process to provide that isolation in this repo.
    """
    try:
        payload = build()
    except EmitError as exc:
        log(f"emit_state: FAILED — {exc}")
        log("emit_state: nothing written; the previous state.json is left as it was.")
        return False
    except Exception as exc:  # noqa: BLE001 — a convenience must never break the product
        log(f"emit_state: FAILED unexpectedly — {type(exc).__name__}: {exc}")
        return False

    try:
        if unchanged(payload):
            log("emit_state: state unchanged since the last emission — leaving it as it is.")
            return True
        OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    except OSError as exc:
        log(f"emit_state: could not write {OUT}: {exc}")
        return False

    s = payload["signals"][SIGNAL]
    log(f"emit_state: meter {s['state']} of 4 @ {s['as_of']} — {s['zone']}")
    return True


def main(argv: list[str]) -> int:
    if "--check" in argv:
        try:
            s = build()["signals"][SIGNAL]
        except EmitError as exc:
            print(f"emit_state: FAILED — {exc}", file=sys.stderr)
            return 1
        print(f"emit_state: meter {s['state']} of 4 @ {s['as_of']} — {s['zone']}")
        print("emit_state: --check, nothing written.")
        return 0
    return 0 if emit() else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
