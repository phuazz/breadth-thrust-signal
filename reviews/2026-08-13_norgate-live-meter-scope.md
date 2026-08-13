# Norgate point-in-time upgrade — scope memo (go/no-go)

**Date**: 2026-08-13 (Thursday — weekday verified with Python `datetime`).
**Scope**: scoping only, per the queue entry "Norgate Tier 2 / Tier 3
workstreams — scope and start" (`NEXT.md`, session 2026-08-08). No engine
change ships with this filing.
**Verdict**: **GO** — but the workstream is materially narrower than the
queue entry assumed. Effort: one build session plus an unattended one-to-two
week parallel run.

## 1. Tier check — this is not the study the queue implied

The Tier 2 / Tier 3 lists (enumerated 2026-07-03 in the "Tier 2 and Tier 3 to
Work on for Norgate" session) do not contain this item: Tier-2 #3 (feed
migration, breadth-thrust-etf) and #4 (gauge-vendor audit, this repo) are done
and filed; Tier 3 is factor-regime-lab and a small-cap lab. More important,
**WS7 (filed 2026-08-01) already closed the study-side question**: daily
survivorship-free S&P 500 membership resolves from 1990-01-02, the frozen spec
was re-run held-out on 1990–2017 (≥3/6m REJECTED; grouping vindicated;
thresholds KEEP), and Norgate was **adopted as the project data layer**. WS8
rejected the tilt. The window extension as research is spent ground.

**The open gap is the live meter.** Today's weekly refresh still builds from
CSP1 weekly snapshots + Yahoo prices: `signals.json` (generated 2026-08-13)
carries study window 2019-01-07 → 2026-08-12 (1,910 days) and 110 unfetchable
ever-members — the exact layer whose event set WS7-H4 showed is substantially
a data-layer artefact (16 of 26 filed events survive the layer change). The
published tables therefore sit on evidence the filed record has already
erratum'd, while the clean layer (`norgate_provider.py` + tests) sits in the
repo unused by the live path.

## 2. The three scope questions, answered with fresh probes (2026-08-13)

**D1–D4 pre-2018, point-in-time: all four compute.** Live-NDU probe today
(aggregate statistics only, no vendor values retained): 1,300/1,300 watchlist
symbols resolve `index_constituent_timeseries` with zero failures; membership
counts are exactly 500 (505 in 2016) on seven mid-year sample dates 1992–2016.
On 30 sampled *today-delisted* members per date: unadjusted (NONE-basis)
volume non-null and positive 30/30 in every era (D4), and ≥252 prior sessions
30/30 on every date (D3) except one 2016 recent index joiner still inside its
own 252-day burn-in — a per-name condition `hl_valid` already masks, not a
coverage gap. Basis discipline is already coded and tested (TOTALRETURN close
for direction/MA/ranges; NONE volume for up-volume; `assert_basis_integrity`).
The em-rotation-lab coverage gate was re-run first, per discipline:
**PASS_MIN** — measured reach 1993-01-29 against the 1995-06-30 bar (the known
SPY-inception probe artefact), delisted archive 21,104 symbols, deaths 1990-01
→ 2026-08, NDU current same-day.

**Thin-breadth guard: it stops clipping and reverts to a tripwire.** The
guard is `MIN_VALID_CONSTITUENTS = 400` plus per-dimension computability
(`data_ok`). Its Phase 0 role — excluding 1999–2017 because the CSP1 roster
was empty there — disappears on the Norgate layer (~500 members with complete
member-with-price coverage throughout). The effective start is set by the
252-day burn-in (1990-12-28), not by the guard. The 400 floor (~80% of
membership) stays right across the whole window and is not re-tuned. The
refresh guard layer changes shape: the roster-age guard becomes an NDU
readiness/staleness guard, and a cheap depth tripwire (history reach +
delisted count, step0-style) should be added because the Saturday 08:00
vendor gauge guard loses *source* independence after cutover — both sides
become Norgate (constituent DB vs precomputed internals), which still catches
roster and aggregation faults but not a vendor-wide one.

**Thresholds: frozen, and stay frozen.** WS7's decision table already records
KEEP (H3b: the engine is not looser than canonical — 7 Zweig fires in the
literature-silent 1990–2003; 5 of 6 anchors match), at `scale = 1.0` on the
S&P 500. The window extension is measurement on the same constants. Nothing
in this workstream touches a threshold, window, memory span or floor; the
12-month observation stays FLAGGED, no action, exactly as WS7 filed it.

## 3. Recommendation and effort

**GO — as a data-layer cutover of the live meter, not a new study.** Build
session (2–4 commits, ~half a day attended): pipeline provider path reusing
`ws7_extension.build()`'s panel assembly (weekly full-replace pull measured at
66 s), `weekly_refresh.py` guard swap (as-of lag, window-extends,
survivorship-False and valid-floor guards unchanged), page provenance and
README updates, tests. Then a one-to-two week unattended parallel run (CSP1
vs Norgate panel, signal-state divergence report, Tier-2 #3 pattern) before a
short cutover-and-file session. The published window becomes 1990-12-28 →
live; the page's tables restate to the WS7-layer numbers **with the
restatement disclosed on the page**. Licence containment is unchanged: vendor
prices stay outside the repo (`C:\dev\.norgate-store\`), the public surface
carries derived aggregates only. Dependency stated: the live meter becomes
NDU-dependent, which feeds the December 2026 renewal right-sizing; the
CSP1+Yahoo path is retained as the flagged fallback (survivorship banner
returns if it ever governs). Out of scope: any threshold re-tune (forbidden),
the Summation Index (stays excluded), the small-cap thread (own
pre-registration if ever).
