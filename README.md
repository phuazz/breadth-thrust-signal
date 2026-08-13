# breadth-thrust-signal

A risk-on **breadth-thrust conviction meter** and conditional forward-return
study for the broad US market. It is the bullish mirror of the
`equity-defense-dashboard`: where that project detects when to go defensive,
this one quantifies how strongly market breadth is confirming a turn upward.

**Status:** Phase 0 — first real, survivorship-correct run completed
(2026-06-01). Point-in-time iShares CSP1 membership applied, so the effective
study window is **2018-01 to 2026-05 (~2,109 trading days)**: before the first
2018 CSP1 snapshot the membership mask has no members, so 1999–2017 carries no
breadth and is excluded by the thin-breadth guard. Both published breadth-thrust
anchors (2019-01-04, 2023-11-03) are detected without tuning. Headline verdict
is suggestive but not confirmed — see below.

Personal research artefact. Not investment advice. Not affiliated with any
regulated fund.

---

## What it measures

The canonical "eight breadth thrust signals" are not eight independent facts.
Four of them — Zweig, McClellan Oscillator, ten-day A/D ratio, McClellan
Summation — all derive from the same advance/decline series; the Summation
Index is literally the running sum of the Oscillator. A naive zero-to-eight sum
therefore overstates corroboration: "six of eight firing" can be two or three
underlying readings wearing six hats.

This engine collapses the indicators into **four independent breadth
dimensions** and scores conviction as the number of dimensions currently
thrusting, zero to four:

| Dimension | Fires when (logical OR of canonical sub-conditions) |
|---|---|
| **D1 Advance/Decline** | Zweig EMA(10) of A/(A+D) crosses 0.40 → 0.615 within 10 sessions, OR 10-day cumulative A/D ratio > 1.90 (Deemer), OR McClellan Oscillator dips below −50 then recrosses 0 within 20 sessions |
| **D2 % above 50d MA** | Share of constituents above their 50-day MA surges from < 25% to > 75% within 15 sessions |
| **D3 New-high / new-low** | NH/(NH+NL) surges from < 10% to > 50% within 10 sessions, OR net new highs rise from negative to > 20 within 10 sessions |
| **D4 Up-volume** | Up-volume / total volume exceeds 0.90 on at least one of the trailing 5 sessions |

Within a dimension the sub-conditions are OR-ed (they share the same raw data,
so they count once). Across dimensions the score is a weighted sum (default
equal weights), because the dimensions are genuinely independent measurements.
A fired dimension is held "on" for a 60-trading-day memory window so that
clustered thrusts register together.

The **McClellan Summation Index (canonical signal 7) is deliberately
excluded.** Its thrust threshold would have to be derived empirically from the
same data, which is exactly the in-sample overfit the source brief warns
against. Better to drop it than to fit it.

---

## The study

The core question is not "what are forward returns after a thrust" but **how
much lift that is over the unconditional base rate.** An 80% six-month win rate
is unimpressive if a randomly chosen date since 2000 already wins 78% of the
time. So the study reports, for each conviction threshold (≥1, ≥2, ≥3, ≥4) and
horizon (1w, 1m, 3m, 6m, 12m):

- conditional win rate and median forward return, measured only on **fresh
  thrust-event days** (de-duplicated, signal lagged one day);
- an **unconditional bootstrap baseline** built with a moving-block resample
  that preserves the autocorrelation of overlapping forward windows;
- the **lift** of the former over the latter, with a "beyond-noise" flag when
  the conditional win rate clears the 95th percentile of the baseline band.

### Three ways this study could be silently wrong (and the guards)

1. **Survivorship bias** inflating thrusts and forward returns. Mitigated by
   point-in-time membership (below). When point-in-time data is absent the
   output is stamped `survivorship_bias: true` and the dashboard shows a
   warning banner.
2. **Look-ahead** in the forward-return join. The conviction score is lagged
   one day (`.shift(1)`) before any forward return is measured; signal at close
   T, window starts T+1. Enforced by `test_no_lookahead_signal_is_lagged`.
3. **A meaningless comparison** — a bare win rate with no baseline. Mitigated by
   the bootstrap baseline and lift table; the dashboard never shows a
   conditional number without its baseline.

---

## Data

Breadth is computed from **S&P 500 constituent** adjusted close (for direction,
moving averages and 52-week highs/lows) and **raw volume** (for the up-volume
ratio; volume is unadjusted by nature). This is a large-cap proxy for true
NYSE breadth — the two converge at the extremes the thrust conditions care
about, and diverge at moderate readings we do not.

### Two data layers (`pipeline.py --provider`)

- **`csp1` (deployed default until cutover):** weekly iShares CSP1 snapshots +
  Yahoo prices. Point-in-time from 2018; carries the documented residual leak
  (delisted ever-members beyond Yahoo's reach drop from historical breadth).
- **`norgate` (built 2026-08-13 per
  `reviews/2026-08-13_norgate-live-meter-scope.md`, soaking):** the WS7 layer —
  Norgate daily survivorship-free membership from 1990-01-02 with full
  delisted history; TOTALRETURN close for direction/MAs/ranges, NONE-basis
  raw volume for D4; window opens 1990-12-28 after the 252-day burn-in.
  Vendor series live outside the repo (`C:\dev\.norgate-store\`, licence:
  personal-use-only, public surface carries derived aggregates only). The
  Saturday refresh runs an alert-only **parallel run** (`parallel_run.py`)
  comparing the Norgate candidate against the published build at the live
  edge; cutover flips the wrapper to `--provider norgate` after 1–2 clean
  Saturdays and restates the published tables to the WS7-layer numbers, with
  the restatement disclosed on the page.

### Point-in-time membership (survivorship mitigation)

Reuse the existing `breadth-thrust-etf` infrastructure rather than reinventing
it. From that project:

```
python scripts/fetch_constituents.py --etf CSP1
```

produces weekly iShares CSP1 (S&P 500 UCITS) Friday snapshots. Copy the output
to `data/constituents_csp1.json` here and the pipeline will mask breadth to
point-in-time membership automatically.

**Caveat — clean point-in-time membership is only available from 2018 onward**
via this source. A 2000–2017 backtest would need a reconstructed historical
membership list (Wikipedia add/drop history) and should be treated as
lower-confidence. Without any snapshot file, the pipeline falls back to a
static current-member universe and flags survivorship bias loudly.

---

## Running it

```bash
pip install -r requirements.txt

# Smoke-test the whole pipeline with synthetic data (no network).
# Renders to data/_selftest/ and docs/_selftest/ — never over the real outputs:
python scripts/pipeline.py --self-test

# Full run (network-bound; run locally, as breadth-thrust-etf does):
#   1. provide data/constituents_csp1.json (preferred) or data/universe.json
#   2. then:
python scripts/pipeline.py            # fetch, compute, study, render
python scripts/pipeline.py --no-fetch # recompute from cached panel only

# Local preview of the dashboard:
npx serve docs
```

The build injects `data/signals.json` into `template.html` and writes
`docs/index.html` for GitHub Pages, consistent with the vault dashboard
architecture (`template.html` is the source; never edit `docs/index.html`).
The self-test runs that identical render path but into `data/_selftest/` and
`docs/_selftest/` (both gitignored), so a synthetic run cannot overwrite the
filed study record or the published dashboard. `tests/test_pipeline_outputs.py`
enforces this.

---

## Architecture

```
breadth-thrust-signal/
├── scripts/
│   ├── compute_breadth.py   # grouped/weighted signal engine (pure, tested)
│   ├── forward_returns.py   # conditional study + bootstrap baseline (pure, tested)
│   ├── membership.py        # CSP1 point-in-time masking + fallback
│   ├── data_providers.py    # csp1 layer: price + volume fetch/cache (yfinance)
│   ├── norgate_provider.py  # norgate layer: WS7 daily PIT panel + live_panel
│   ├── pipeline.py          # fetch -> mask -> compute -> study -> render (--provider)
│   ├── weekly_refresh.py    # guarded Saturday refresh (roster sync / depth gate)
│   ├── parallel_run.py      # alert-only Norgate soak harness (cutover gate)
│   └── validate_d1.py       # cross-check D1 thrust dates vs published anchors
├── tests/                   # engine, guards, comparator, date edges (51 tests)
├── data/                    # signals.json, panel_cache.json, constituents_csp1.json
├── template.html            # dashboard source (light theme, Plotly)
└── docs/index.html          # built GitHub Pages output (do not edit)
```

## First-run findings (2026-06-01)

Decision criterion (the brief): at score ≥ 3, six-month horizon, the median
forward return should be meaningfully above unconditional **and** the win-rate
lift should clear the baseline noise band. Both conditional sample and bootstrap
baseline are period-matched to the 2018–2026 valid-breadth window.

- **Score ≥ 3, 6m (n = 14 fresh events):** median +11.2% vs baseline +7.3%
  (lift +3.9pp) — **passes** the median test. Win rate 78.6% vs baseline 74.8%,
  but 78.6% sits *inside* the baseline 5–95 band [68.2%, 81.0%] — **fails** the
  beyond-noise test.
- **The win-rate lift runs backwards in conviction:** 0.885 (≥1) → 0.864 (≥2)
  → 0.786 (≥3) → 0.500 (≥4, n = 2). The beyond-noise flag fires at ≥1 and ≥2,
  not at the ≥3 decision threshold. For a conviction meter this is the wrong
  direction and undercuts the "more dimensions = stronger edge" premise.
- **Sample is thin.** 26 events at ≥1, 14 at ≥3, 2 at ≥4 over eight years; the
  binomial SE on a 14-event win rate is ~±10pp, so the ≥3 win lift is not
  statistically distinguishable from zero.

**Verdict:** the mechanism is real (anchors validated, untuned) and the 6-month
median lift is real and positive, but the specific ≥3 win-rate criterion is not
met and conviction-monotonicity is inverted. Treat as suggestive, **not** a
confirmed standalone ≥3 timing trigger. Do not wire into `equity-defense-
dashboard` on this evidence alone.

## ERRATUM to the first-run findings (added 2026-08-01, WS7)

The findings above stand as filed and are **not** superseded, but two
corrections apply. Both were established in WS7 (`RESEARCH_MEMO.md`;
`reviews/2026-08-01_ws7_norgate-history-extension.docx`).

1. **Burn-in defect.** The validity gate admitted days on which D2 and D3 were
   mechanically incapable of firing — D2 needs 50 sessions before a 50-day
   average exists, D3 needs 252 before a 52-week high does — so the score was
   capped at 2 for the first year of the panel. D3 first fires 2019-01-10, two
   trading days after the 252-day boundary at 2019-01-08, and **4 of the 26
   events above sit inside that window**. Correcting it moves the 6-month win
   rate by −2.1pp at ≥1 and −1.4pp at ≥2, and not at all at ≥3 or ≥4. The
   conviction inversion survives the correction. `data_ok` now requires every
   dimension to be computable.
2. **The event set is substantially a property of the data layer.** Rerunning
   the same calendar window on daily point-in-time membership with delisted
   names restored leaves **only 16 of the 26 events intact**. At ≥3 both runs
   carry n=14 but only 7 dates coincide, moving the 12-month median from
   +23.05% to +13.28%. The benchmark series is not the cause (0.12% maximum
   difference). The cause is the weekly-snapshot membership and the Yahoo
   delisted gap, both listed as known caveats below.

**What WS7 changes about the verdict.** The ≥3 / 6-month criterion was tested
on a held-out 1990–2017 window and **failed there too**, so it is now formally
rejected rather than merely unconfirmed. Conversely, the inverted conviction
ordering reported above did **not** reproduce out of sample (rank correlation
+0.40 held-out against the negative ordering here) — that inversion was an
eight-year artefact and the four-dimension grouping is vindicated.

## Is it deployable? No — WS8, 2026-08-01

WS7 left one cell alive: fresh events at score ≥ 3, one month forward, beyond
noise on both legs in both windows and genuinely scarce. WS8 asked whether that
is deployable, since WS7 had measured statistical lift and never run a
net-of-cost backtest. Two findings, and they are not in tension.

**The mechanism is real and it generalises.** Rebuilt unchanged on two further
point-in-time universes, the same cell shows a positive median lift in both —
**+1.04pp in the S&P SmallCap 600** (beyond noise on both legs, 42 distinct
episodes) and +0.21pp in the Russell 2000 (within noise). Small-cap breadth
carries a *larger* lift than large-cap's +0.72pp, which is economically
sensible: a thrust across 600 smaller names says more about participation than
the same reading across 500 mega-caps.

**It is not convertible into portfolio value.** An unlevered tilt overlay
(60/40 base, +20pp equity for 21 days on a fresh ≥3 event, 10bp costs) returns
net Sharpe 0.709 against a cost-matched random-entry null whose 95th percentile
is 0.751 — and below that null's *median* of 0.718. All 18 variants fall below
the untilted base of 0.743, monotonically worse with larger tilts and longer
holds, in all three universes.

Why both are true: the one-month **mean** lift is +0.44pp against a **median**
lift of +0.72pp, while volatility runs 1.16× baseline. A portfolio compounds
means and pays for variance, so the statistic that survived every test is the
one a portfolio cares about least. Independently, the +0.14pp of CAGR the tilt
added matches the passive long-bias arithmetic for *any* 20pp tilt held 10.6%
of the time, to four thousandths of a percentage point.

Also dead, killed at the diagnostic stage: an `equity-defense-dashboard`
re-entry accelerator (4–7 usable events in 28 years), a state-conditional
overlay (a pre-2009-only effect), and a defensive-state override whose apparent
+4.58pp lift proved to be a composition artefact.

## Known caveats / next steps

- **Residual data-layer leak.** *(RESOLVED for the Norgate layer, 2026-08-01.)*
  Under the Yahoo path, 111 of 715 ever-members were delisted/renamed beyond
  reach and dropped from historical breadth. Norgate carries all 646 delisted
  ever-members with full history, and member-with-price coverage is complete on
  every sampled date. The caveat still applies to any run on the legacy panel
  cache.
- **Pre-2018 point-in-time membership is unresolved.** *(CLOSED 2026-08-01,
  WS7.)* The assumption that this needed a reconstructed membership list was
  wrong. Norgate resolves daily survivorship-free S&P 500 membership from
  1990-01-02; the effective study window is now 1990-12-28 → 2026-07-31, 8,961
  usable days against 2,109.
- **Small-sample power.** *(ADDRESSED, and the answer was negative.)* On 4.25×
  the data the ≥3 edge does not confirm — it fails the pre-registered rule out
  of sample. The ≥3 signal does clear both legs at the 1-month and 12-month
  horizons in both windows, but that was not the pre-registered horizon and is
  flagged without action; claiming it would require its own pre-registration on
  data not yet spent.

## Refresh cadence — live meter (2026-08-13)

Owner decision: the dashboard is a **live meter**, not a static study snapshot.
`scripts/weekly_refresh.py` (Task Scheduler task "breadth-thrust-signal weekly
refresh", Saturday 07:00 SGT — before the 08:00 vendor gauge guard, so that
guard cross-checks a fresh panel) syncs the point-in-time roster from
breadth-thrust-etf, re-runs the pipeline, and publishes only when the guards
pass: as-of within 3 completed NYSE sessions, study window extended with the
data, survivorship flag still false, valid-constituent floor cleared, test
suite green. A failed run publishes nothing — the deployed page keeps its last
good build, and its client-side banner turns amber once the data is more than
9 calendar days old. The heartbeat is watched by the vault fleet watch on the
"Weekly refresh" commit.

After a successful publish the wrapper also runs the **Norgate parallel run**
(alert-only, `data_local/` only — see the Data section): the cutover candidate
is built and guard-checked every Saturday until the soak clears. In
`--provider norgate` mode (post-cutover) the roster-sync step becomes the
depth gate (NDU readiness and age, $SPX reach, delisted-archive floor) and
the output guards additionally pin the provider tag and the 1990-12-28
window start.

*Last updated: 2026-08-13*
