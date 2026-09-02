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

## Build addendum — same day (2026-08-13, Thursday; owner "go ahead")

Shipped in three commits: `b60727a` (`pipeline.py --provider norgate` wires
`norgate_provider.live_panel` — readiness gate, 5% unfetchable ceiling, basis
integrity; `--preview` renders real-data rehearsals into gitignored dirs),
`17c46e3` (`weekly_refresh.py --provider norgate` swaps the roster sync for
the depth gate — NDU age ≤ 7 days, $SPX reach, delisted floor 15,000 — and
pins the provider tag plus the 1990-12-28 window start; `parallel_run.py`
rides the Saturday wrapper after a successful publish, alert-only, data_local
only; 16 new fire-path tests, suite at 51), `9c599f2` (provider-aware scope
banner with the restatement disclosure, dormant under csp1; README; docs
rebuilt). No new scheduled task — the parallel run rides the existing
"breadth-thrust-signal weekly refresh" heartbeat, so fleet-watch coverage is
unchanged.

Evidence banked today: the rehearsal reproduced WS7 exactly (window
1990-12-28 → 2026-08-12, 8,969 days, members/day 498–507, 98 events, 1,300 of
1,300 symbols, 0 refresh failures) and matched the deployed edge on every
dimension; the first parallel run returned **CLEAN** (10 of 10 edge sessions
agree). Rendered checks: static check 0 fail; deployed page measured clean at
390/844/768/1280 px (clientWidth read back 390/829/753/1265, zero uncontained
overflow, minimum font 11.0 px, zero console errors); the Norgate preview
page renders the 1990→ window and provenance note, clean at 390 px (one
resize-without-reload measurement artefact identified and eliminated).

**Nothing deployed changed today** — the page still publishes the CSP1 layer.
Cutover after one-to-two clean Saturdays (2026-08-15, 2026-08-22, both
weekday-verified): flip the wrapper to `--provider norgate`, re-render, full
mobile check on the restated page, ledger and record amendment.

## Cutover addendum — 2026-09-02 (Wednesday; weekday verified with Python `datetime`)

**Owner decision: FLIP**, on three clean parallel runs: 2026-08-22 (record
CLEAN, harness crashed on the summary print; fixed 2026-08-27, `b42b32f`),
2026-08-27 (manual, after the fix) and 2026-08-29 (scheduled: CLEAN, 10 of 10
edge sessions, 503 valid, 0 unfetchable, window 1990-12-28 → 2026-08-28, task
result 0). Shipped as `06e814b` (wrapper flip, parallel-run refusal, page
provenance, README) and `4fc3e54` (the first Norgate-layer publish, "Weekly
refresh 2026-09-02", produced by `weekly_refresh.py --provider norgate
--no-push` end to end: depth gate clean, 2,604 series refreshed with 0
failures, output guards clean, 85 tests green, state emitted), plus this
addendum.

**Re-render path, and why.** The queue note proposed injecting the committed
`data/signals.json` through the template because the repo has no separate
docs-writing flag. That would have rendered the wrong layer: the committed
payload was the CSP1 build (`csp1-yahoo`, window 2019-01-07 → 2026-08-27, 110
unfetchable), and the restated page needs a Norgate payload that only the
provider path produces. There is no missing flag — `pipeline.render()` writes
`docs/index.html` on every non-preview run — so the re-render was the wrapper's
own command with NDU up (database stamp 2026-09-02 15:00:42 +08:00),
rehearsed first with `--preview` into the gitignored rehearsal directories.

**Three ways the restated page could be silently wrong, and the guard for
each.** (1) Right label, wrong layer: the norgate-mode output guards pin
`provider == norgate-pit` and window start 1990-12-28 on the published
payload, and the rendered page's data island read back `norgate-pit` /
1990-12-28 / as-of 2026-09-01 at every viewport. (2) Silent history loss or
survivorship re-acquisition inside the layer: depth gate (NDU ready and no
more than 7 days old, $SPX reach, 15,000 delisted floor), 5 % unfetchable
ceiling, 400-valid floor, survivorship flag False, and the like-for-like
reconciliation below. (3) Stale prose beside restated numbers: every
layer-specific sentence now reads the provider tag (usage bullets, verdict,
lift-table note, footer), the SPX log-axis ticks are chosen from the data
range, and the check was on the rendered DOM, not the template.

**Reconciliation, like-for-like: the filed WS7 record (pooled H2, window to
2026-07-31), the live page at cutover, and the pre-cutover page.**

| Figure | WS7 filed (Norgate, → 2026-07-31) | Live page at cutover (Norgate, → 2026-09-01) | Pre-cutover page (CSP1, 2019-01-07 → 2026-08-27) |
|---|---|---|---|
| Study window, sessions | 8,961 | 8,983 (+22 sessions, 2026-08-03 → 2026-09-01) | 1,921 |
| Fresh events / at ≥3 / at 4 | 98 / 46 / 10 | 98 / 46 / 10 (no event since 2025-05-05) | 22 / 14 / 2 |
| Members per day min / median / max | 498 / 500 / 507 | 498 / 500 / 507 (1,301 ever-members, 0 unfetchable) | 615 used of 725 ever-members, 110 unfetchable |
| ≥3, 6m win rate vs bootstrap 95th pct | 76.1 % vs 78.0 % (FAIL) | 76.1 % vs 78.1 % (inside band) | 78.6 % vs 77.7 % base (n = 14) |
| ≥3, 6m median vs 95th pct of baseline median | +7.69 % vs +6.37 % (PASS) | +7.69 % vs +6.41 % (clears) | +11.15 % vs +8.50 % base |
| ≥3, 1m median lift | +0.72pp (the WS8 input) | +0.71pp (+1.97 % vs +1.26 %) | +1.32pp |
| ≥3, 12m median | not tabulated in the memo (held-out H1: +13.49 %) | +13.49 % (n = 46) | +23.05 % (n = 14; the WS7-erratum figure) |
| 6m win-lift by threshold ≥1 / ≥2 / ≥3 / ≥4 | +3.6 / +1.7 / +1.1 / +5.1pp (ρ +0.20) | +3.5 / +1.5 / +1.0 / +4.9pp (not monotone) | +8.7 / +7.3 / +0.9 / −27.7pp (inverted) |

The conditional side reproduces the filed record exactly — same events, same
win rates, same medians; the bootstrap bands move by 0.04–0.10pp because the
baseline is re-drawn over 22 more sessions. Nothing was tuned: thresholds,
memory window, 400 floor and 252-day burn-in are the frozen constants. The
page verdict is unchanged in substance (win leg inside the band, median leg
clears) and now states the filed WS7 verdict beside the live cell: the cell
reports, it does not decide.

**Rendered checks (published `docs/index.html`, served locally, viewport
emulated and `clientWidth` read back before any other measurement).** Static
check 0 fail / 1 warn (no dark theme — light by design). 390 × 844: clientWidth
390, body h-scroll 0, uncontained overflow 0 (110 elements sit inside the two
`.tblwrap` scrollers — tables 429 and 556 px wide in a 358 px scroller, as
designed), smallest rendered font 11.0 px, 40–49 chars/line. 844 × 390:
clientWidth 829, 0 / 0, 11.0 px, 66–73 chars/line. 768: clientWidth 753,
0 / 0, 11.0 px, 66–73. 1280: clientWidth 1265, 0 / 0, 11.0 px, 66–73. Console
errors 0. Marks that actually printed: 36 score-3 triangles, 10 score-4 stars,
46 guide lines; ten y-axis ticks 300 → 7,000. Two defects were caught on the
rehearsal and fixed before publish: the fixed SPX tick list (2,500–7,000)
would have left 1990–2019 with no y tick, and running prose measured 37
chars/line for list items at 390 px and 107–147 at 844–1280 px (a 66ch cap
and a phone-padding trim are in `06e814b`).

**What changed operationally.** The wrapper propagates the refresh exit code
(`exit /b %errorlevel%`), so a failed refresh now shows as a non-zero Last
Result in Task Scheduler. The parallel run is retired from the wrapper: with
the Norgate layer deployed it would compare the candidate against itself and
read CLEAN by construction, so `parallel_run.py` refuses a same-layer
comparison (test pinned) and the wrapper line itself is pinned by a test. The
CSP1+Yahoo path stays as the flagged fallback (still the argparse default);
its survivorship and residual-leak banners are dormant, not deleted. The
Saturday 08:00 vendor gauge guard loses source independence as §2 anticipated;
the depth gate is the vendor-wide tripwire. Fleet row "breadth-signal weekly
refresh" is unchanged (grep "Weekly refresh", 168 h). First unattended firing
on the new layer: Sat 2026-09-05 07:00 SGT (weekday verified), as-of Fri
2026-09-04.

**Open, harvested to `NEXT.md`.** (a) `pipeline.py` and `weekly_refresh.py`
kept `csp1` as the argparse default at cutover, so a bare manual run would
have rebuilt the fallback over the live page — **RESOLVED the same day on
owner instruction**: both defaults flipped to `norgate`, `--provider csp1`
selects the fallback, and the guard function defaults to the norgate pins so
a fallback payload checked without an explicit provider fails loud (two tests
pin it; follow-up commit of 2026-09-02). (b) The fallback path is unexercised from here; its roster sync
and 45-day roster-age guard still work, but yfinance retracted closes on
2026-08-28 (breadth-thrust-etf), so a fallback publish would need its own
check first. (c) The December 2026 Norgate renewal is now load-bearing for the
live meter.
