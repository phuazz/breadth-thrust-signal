# ESCALATION — WS10 thrust-subconditions, Step 0 (2026-10-25)

**Status: OWNER RULING RECEIVED; implementation updated, awaiting the authorised run.**

The owner authorised separate tied counts, retention and explicit labelling of the legacy WS7 half-boundary
convention, and permission for independently constructed empty SEEN comparators. Frozen files remain unchanged.
The three-key `cofire_split` excludes ties; the runner reports `tied` beside each pooled and per-half split.
Before + same + after + tied therefore equals the number of co-firing candidate events. Co-fire shares,
G2, P1 and verdict rules are unchanged. Empty non-SEEN comparators retain the existing refusal behaviour.

The runner now files Step 0 failures from ordinary exceptions and persists Step 0 before outcome computation.
A private, exclusively created `data_local/ws10_full.started.json` marker is flushed before the full run and
retained after success, failure or interruption. It must not be deleted to retry without owner review.
A Step 0 STOP does not create that marker or the full-results sentinel. Exported WS7 baseline rows are limited
to the registered horizons; the pinned bootstrap calculation and its random stream are preserved.

The following records the original STOP and the options presented before the ruling. The full run has
not been executed and no candidate-conditional forward return, win rate, median, lift or percentile has been
computed. `results/ws10_results.json` has not been written. The study is not STOP_STEP0 on the data. Every data
probe that ran passed, and this STOP is an unanswered implementation question that only an owner ruling can
settle.

## What ran

Step 0 on real data at commit `928de20` (engine `4644178`, runner `aaab769`, High transport `928de20`), spec sha256
`b805afaf…3f33`, tag `prereg-freeze` reachable, battery 162 passed with none skipped. The live meter's cache was read
without refresh: last refreshed against NDU 2026-10-17 07:25 SGT, $SPX last session 2026-10-16. The live NDU database
is 2026-10-25 17:59 SGT, a drift of 8 days, inside the 10-day warning. The realised window end is therefore
2026-10-16.

| Probe | Result |
|---|---|
| P0-5 hashes, tree, tag | pass |
| P0-1 panel | pass: 1,304 ever-members; mask count 498 / 500 / 507 on the 9,015 data_ok sessions; first data_ok 1990-12-28; the event-set guard reproduced exactly (98; 46 in 41 clusters; 2025-05-05) |
| P0-4 $SPX and half bounds | pass: no gap; early 1990-12-28 → 2017-12-29, late 2018-01-02 → 2026-10-16 |
| P0-2 computability | pass: both shares defined on every data_ok session |
| P0-3 signal-side counts | **STOP**, see below |
| P0-6, P0-7 | not reached |
| P0-8 | High cache pulled (1,304 series, 0 failures, smoke check pass); not yet evaluated by the runner |

## The question

PREREG §10 and spec `redundancy.lead_lag_split_reported` require every co-fire to be classed as the member fire
BEFORE, on the SAME session as, or AFTER the candidate event, and the three counts reported beside each share. The
contract API (`cofire_split`) classes a co-firing candidate event "by whether the nearest fire is before, on, or
after the candidate's session". Neither the spec nor the reference implementation says how to class a candidate
event whose two nearest member fires are equally near on opposite sides, for example one fire at minus 3 sessions and
one at plus 3.

On the real panel this occurs **twice, both in S-D2's D1 split** (zero ties in S-D3's splits and in S-D2's own-dimension
and D4 splits). The D1 share is reported and never gated (spec `redundancy.d1_share`). The split is descriptive and
enters no gate, no status and no verdict. The co-fire shares themselves, the G2 statuses and P1 do not depend on it.

## Options for the owner (a pre-results implementation pin; the tie counts are signal-side, not a look)

1. **Recommended: report the ties as their own count.** `cofire_split` keeps its three keys and leaves a tied event
   out of all three, and the runner reports a `tied` count beside them, so before + same + after + tied equals the
   co-firing events. This assigns nothing by convention and stays compatible with the frozen contract test, whose
   known case has no tie.
2. Class a tie as BEFORE, giving the earlier fire precedence.
3. Class a tie as AFTER.

Whichever is ruled, the runner is re-run from Step 0 (`python scripts/ws10_run.py --step0`, then `--full` once). No
frozen file changes: the ruling touches only `scripts/ws10_subconditions.py` and `scripts/ws10_run.py`, and lands in its
own commit that cites this file.
