# RESEARCH_MEMO — breadth-thrust-signal

Running record for studies run in this repo. Phase 0 (the conviction meter and
its conditional forward-return study) is documented in `README.md` and
`data/signals.json` (`study` subtree); this memo starts with WS4.

---

## WS4 — breadth stress-test (primer replication), 2026-07-03

**Provenance.** Pre-registered spec `C:\dev\KICKOFF_ws4-breadth-stresstest.md`
(signed off 2026-07-03), operationalising
`studies/reference/BoAML_Quant_Breadth_StressTest_Navigo.docx` against the
actual repos. Cross-project: H1–H3 here, H4 in `equity-defense-dashboard`.
Scope guard held: no deployed configuration changed anywhere.

### Mapping audit (finding 0)

The memo feared a narrowness-as-warning reading inside deployed signals. The
code audit found none: D1–D4 are all thrust-type (change), the Phase 19 gate
(share above 50d MA, 20/50 hysteresis) and the EDD Blowup count (8-day count
of stocks down ≥7%) are washout / stress LEVEL reads — crash participation,
not leadership concentration, which is the object the primer debunks.

### H1 — level vs change information content

Universe: raw CSP1 `ma_breadth` joined to the Phase 0 SPX series, 2,109 days
2018-01-08 → 2026-05-29, one-day lag, standardised OLS, moving-block bootstrap
(2,000 draws, block 21, seed 42).

| Horizon | Level slope (per 1σ) | boot 90% | Change-21d slope | boot 90% |
|---|---|---|---|---|
| 1m | −0.94ppt SIG | [−1.50, −0.32] | −0.43ppt ns | [−0.99, +0.12] |
| 3m | −1.33ppt SIG | [−2.49, −0.12] | −0.43ppt ns | [−1.54, +0.58] |
| 6m | −1.78ppt SIG | [−3.27, −0.22] | −1.42ppt SIG | [−2.77, −0.21] |
| 12m | −2.15ppt ns | [−4.79, +0.63] | +0.33ppt ns | [−2.14, +2.28] |

Reading: breadth LEVEL carries small but beyond-noise **contrarian**
information at 1m–6m (low breadth → higher forward returns; R² ≤ 3.6%). The
memo's paraphrase "level carries nothing" is not supported; what the level
carries is washout mean-reversion — consistent with the primer's actual claim
(narrowness mean-reverts) and with the Phase 19 gate's washout design. The
21-day change adds little on its own.

### H2 — level-quartile events vs the Phase 0 thrust study (reused)

Fresh entries into the bottom / top level quartile (Q1 = 0.440, Q3 = 0.724),
21-day de-cluster, one-day lag, same baseline machinery. Phase 0 thrust rows
REUSED verbatim (not recomputed).

| Condition | n | 1m win (base 67.4%) | 6m win (base 74.8%) | 12m win (base 82.7%) |
|---|---|---|---|---|
| Washout entry (level < Q1) | 34 | **76.5% beyond noise** | **84.8% beyond noise** | 80.6% ns |
| Strength entry (level > Q3) | 36 | 72.2% ns | 65.7% ns (−9pp) | 82.4% ns |
| Thrust events (score ≥ 2, Phase 0) | 22 | 72.7% ns | 86.4% beyond noise at median lift | 86.4% ns |

Reading: washout entries clear the noise band at 1m and 6m; strength entries
carry nothing (6m below base). The Phase 0 thrust study stands as filed
(6-month median lift passes; win-rate lift mostly within noise on n=22).

> **ERRATUM (2026-08-01, WS7).** The Phase 0 thrust row reused above inherits
> two corrections established in WS7. A burn-in defect placed 4 of the 26
> Phase 0 events in a window where D2 and D3 could not fire (−1.4pp on the ≥2
> 6-month win rate), and rerunning the window on daily point-in-time membership
> leaves only 16 of the 26 events intact — at ≥2 the count moves 22 → 23 and
> the 12-month median falls 5.9pp. **The WS4 H2 reading is unchanged in
> direction**: washout entries still clear the band where strength entries do
> not, and that contrast is what H2 was testing. The absolute thrust-row
> figures should be read with the erratum. The level-quartile rows are computed
> from raw breadth and are unaffected.

### H3 — narrowness replication (reference exhibit; no decision)

Mega-cap-led month := trailing 12m SPY total return beats RSP by more than the
threshold. Monthly, 2004-05 → 2025-07, n=255, unconditional 12m positive share
85.1%.

| Threshold | Flagged months | Subsequent 12m positive | Episodes |
|---|---|---|---|
| >0ppt | 136 (~11.3y) | 82.4% | 15 |
| >+2ppt | 102 (~8.5y) | 85.3% | 13 |
| >+5ppt | 41 (~3.4y) | **95.1%** | 8 |

Reading: narrow leadership carried no bearish information on own data —
directionally replicating the primer's 1986→ finding (~76% positive). Power
caveat as pre-registered: ~8–11 independent years per threshold.

### H4 — EDD composite attribution (in `equity-defense-dashboard`)

Engine replicated exactly before variants ran (0 score mismatches on 7,167
rows; recomputed equity curves match stored `bt.comp` / `bt.compIef` to the
cent — the `or CASH_RATE` falsy-coercion of 0.0 returns was the one subtlety).
Repo cost model used (10 bps per unit of allocation change), superseding the
spec's 5 bps placeholder. Full window 1998-01-05 → 2026-07-02, IEF leg:

| Variant | Sharpe | CAGR | MaxDD | Switches |
|---|---|---|---|---|
| Full composite | 0.834 | 10.15% | −24.9% | 103 |
| minus Blowup | 0.828 | 10.22% | −24.9% | 93 |
| minus VIX term | 0.823 | 10.30% | −24.9% | 83 |
| minus 200d MA | 0.743 | 9.90% | −36.3% | 80 |
| minus 12m momentum | 0.743 | 9.19% | −39.8% | 122 |
| minus 10m SMA | 0.743 | 9.51% | −39.9% | 98 |

Pre-registered decision (Blowup): ΔSharpe −0.006, ΔMaxDD 0.0ppt → **ON
NOTICE** (bands |ΔSharpe| ≤ 0.05, |ΔMaxDD| ≤ 2ppt). VIX term structure sits in
the same within-band zone (−0.011). The three trend/momentum legs are
load-bearing: removing any one takes MaxDD from −24.9% to −36% / −40%.
2014→ subwindow (regime-concentration check): minus-Blowup −0.023, still
within band; trend-leg removals IMPROVE post-2014 (V-shaped era penalises
defence) — exactly the era-dependence the spec flagged; the full window is
decisive. Solo-through-ALLOC_MAP is degenerate (max score 1 → never
defensive); the solo view is the repo's own standalone strategies S1–S4,
quoted in the results JSON.

### Decisions

| Component | Decision | Basis |
|---|---|---|
| D1–D4 thrust dimensions | KEEP | H2 reuse; Phase 0 stands |
| Phase 19 washout gate design | KEEP (no action; closed at WS3) | H1 contrarian level slope; H2 washout lift |
| Narrowness-as-bearish concept | REJECT (graveyard) | H3: 82–95% positive vs 85% base |
| EDD Blowup sub-signal | ON NOTICE | H4 bands: −0.006 / 0.0ppt |
| EDD VIX term-structure sub-signal | FLAGGED (informational) | H4: −0.011 / 0.0ppt |
| EDD trend/momentum legs | KEEP | H4: removal → MaxDD −36% to −40% |

### Trial register

~65 configurations evaluated, 0 selected for deployment: H1 8 regressions;
H2 10 level-conditional rows (+20 reused); H3 3 thresholds; H4 11 variants ×
2 defensive legs × 2 windows = 44 runs. No parameter was tuned to data;
quartiles, de-cluster window and bands were fixed in the spec before running.

### Artefacts

`scripts/ws4_stresstest.py`, `scripts/ws4_charts.py`,
`reviews/2026-07-03_ws4_results.json`, `reviews/charts/ws4_*.png`,
`equity-defense-dashboard/scripts/ws4_attribution.py`,
`…/reviews/2026-07-03_ws4_attribution.json`, technical record
`reviews/2026-07-03_ws4_breadth-stresstest.docx`, graveyard update
`regime-library/indicators/graveyard-breadth-narrowness.yaml`.

### Next

Feed the Blowup ON-NOTICE and VIX-leg findings into the next scheduled EDD
review; no re-opening of the closed WS0–WS3 decisions. The washout-entry
lift (H2) is a candidate future study as an entry-timing overlay — new spec
required; do not bolt onto this one.

---

## WS7 — Norgate point-in-time history extension, 2026-08-01

**Provenance.** Pre-registered spec `C:\dev\KICKOFF_ws7-norgate-history-extension.md`
(committed before any result was computed, `vault-docs@9d7c233`; sign-off
cleared `c417b3e`). Context: Personal. The Norgate licence is
personal-use-only; no vendor series values are published and nothing is routed
through Navigo. Closes the Phase 0 caveat "pre-2018 point-in-time membership
is unresolved".

### Feasibility (why the Phase 0 assumption was wrong)

Phase 0 assumed extending before 2018 required a reconstructed Wikipedia
add/drop history and would be lower-confidence. A probe of the local NDU
installation disproved that: Norgate resolves daily, survivorship-free S&P 500
membership from 1990-01-02, with full price history for delisted members.
Member-with-price coverage is **complete** — 500/500, 499/499, 505/505 on every
sampled date, against 111 of 715 ever-members unfetchable on the Yahoo path.
The extension is not lower-confidence than the filed run; it is strictly
cleaner.

Effective window **1990-12-28 → 2026-07-31, 8,961 usable days**, against the
filed 2,109. Members 498–507 every day. Full two-basis pull of 1,299
ever-members takes 66 seconds with zero failures.

### Build step 0 — the look-ahead gate (PASSED)

Norgate's constituent flag transitions on the **effective** date, not the
announcement date: TSLA 2020-12-21, META 2013-12-23, BRK.B 2010-02-16 all land
on the documented effective date, corroborated by adds and drops clustering 35%
and 39% on Mondays. No mask shift applied; applying one would have introduced
the look-ahead it was meant to remove.

### Finding 0 — a burn-in defect in the FILED Phase 0 record

Found while validating, not sought. `data_ok` admitted days on which D2 and D3
were mechanically incapable of firing — D2 needs 50 days of history before a
50-day average exists, D3 needs 252 before a 52-week high does — so for the
first year of any panel the score is capped at 2 by construction. In the filed
record **D3 first fires 2019-01-10, two trading days after the 252-day boundary
at 2019-01-08**, and 4 of its 26 events sit inside that window.

Effect on the filed headline is small: the 6-month win rate falls 2.1pp at ≥1
and 1.4pp at ≥2, and not at all at ≥3 or ≥4. The conviction inversion survives
the correction, so this is a recorded defect, not a retraction.

Detection required explicit computability counts (`ma_valid_count`,
`hl_valid_count`): `new_highs` is a sum of booleans and reads 0 during burn-in,
indistinguishable from a genuine day with no new highs. A NaN would have been
the kinder failure. `data_ok` now requires every dimension to be computable.

### H1 — held-out out-of-sample test (the decision)

Frozen Phase 0 spec applied unchanged to **1990-12-28 → 2017-12-31**, a window
that played no part in its design. 6,805 days, 70 events, 48 clusters.

Pre-registered rule at score ≥ 3, six-month horizon, both legs required
(median leg tightened at sign-off to the 95th-percentile bootstrap bar):

| Leg | Conditional | Bootstrap 95th pct | Verdict |
|---|---|---|---|
| Win rate | 75.0% | 78.0% | **FAIL** |
| Median return | +6.89% | +5.96% | PASS |

**Verdict: FAIL.** The signal does not clear the pre-registered bar on
genuinely out-of-sample data — the same way it failed in-sample at Phase 0, now
on 4.25× the data. Per the spec, that is the conclusion; it is not an occasion
to revisit thresholds.

Full grid (Y = clears the 95th-percentile bootstrap band):

| Horizon | Thr | n | Clusters | Win | Band hi | W | Median | Band hi | M |
|---|---|---|---|---|---|---|---|---|---|
| 1m | ≥3 | 32 | 28 | 75.0% | 66.2% | Y | +1.78% | +1.33% | Y |
| 6m | ≥1 | 70 | 48 | 75.7% | 78.0% | · | +6.89% | +5.96% | Y |
| 6m | ≥2 | 54 | 40 | 72.2% | 78.0% | · | +6.29% | +5.96% | Y |
| 6m | ≥3 | 32 | 28 | 75.0% | 78.0% | · | +6.89% | +5.96% | Y |
| 6m | ≥4 | 8 | 8 | 87.5% | 78.0% | Y | +12.20% | +5.96% | Y |
| 12m | ≥3 | 32 | 28 | 87.5% | 82.7% | Y | +13.49% | +11.83% | Y |
| 12m | ≥4 | 8 | 8 | 100.0% | 82.7% | Y | +19.96% | +11.83% | Y |

**Observation, explicitly NOT a rescue of the failed test.** The ≥3 signal
clears both legs at 1m and at 12m, in the held-out window and again pooled,
while failing at the pre-registered 6m. Reporting this is honest; acting on it
would be horizon-shopping after a failed test. If the 12-month reading is to
be claimed, it requires its own pre-registered study on data not yet used —
which, the held-out window now being spent, means waiting for new data or
accepting a weaker claim. Recorded so it is not rediscovered as if new.

The ≥4 bucket carries 8 events in 8 clusters. Under the pre-registered cluster
floor its large lift is reported but **not** treated as established.

### H1b — conviction monotonicity (falsification test)

Phase 0's win-rate lift ran backwards in conviction (0.885 at ≥1 down to 0.500
at ≥4), which would undercut the four-dimension premise. **It does not
reproduce.** Spearman rank correlation between threshold and 6-month win-rate
lift is **+0.40 held-out** and **+0.20 pooled**. The inversion was eight-year
noise. The conviction meter is not falsified; it is simply not strong enough at
≥3 to clear the noise band at six months.

### H2 — pooled full window (reported after H1, not as confirmation)

1990-12-28 → 2026-07-31, 8,961 days, 98 events, 65 clusters. At ≥3, 6m: win
76.1% vs band hi 78.0% (FAIL), median +7.69% vs +6.37% (PASS). Same verdict as
H1. Contains the window whose result was already known, so no decision hangs
on it.

### H3 — anchor validation

Anchor list fixed before the run from Tom Aspray, "Only Seventh Buy Signal
Since 2000", Forbes, 2023-04-09, with source disagreements logged rather than
reconciled.

| Anchor | Result | Note |
|---|---|---|
| May 2004 | **MISS** | contested — omitted by a Morris list that could not be verified |
| March 2009 | MATCH | corroborated |
| October 2011 | MATCH | corroborated |
| October 2013 | MATCH | corroborated |
| October 2015 | MATCH | contested by the same list |
| 2019-01-10 / 2019-01-04 | MATCH | reported separately, never merged |
| 2023-11-03 | MATCH | existing repo anchor |

The single miss is precisely the anchor the second source omits. The engine
agrees with the list that excludes 2004 — a convergence worth noting, though
one anchor is not evidence for either list.

### H3b — the silent-period negative test

The literature reports no Zweig Breadth Thrust between August 1984 and March
2009, so H3 cannot positively validate 1990–2003. Our D1-Zweig leg fires **7
days in 6 episodes** across those thirteen years (1996-08-02, 1996-09-13,
1996-09-16, 2002-10-21, 2003-03-21, 2003-10-07, 2003-12-01). Single digits, as
pre-registered. **The EMA(10) large-cap proxy is not materially looser than the
canonical NYSE simple-average definition.** This test could only ever fail the
implementation; it did not.

### H4 — reconciliation against the filed record: ERRATUM TRIGGERED

Rerunning the filed calendar window (2018-01-08 → 2026-05-29) on the Norgate
layer produces a materially different event set, and the reason is not the
index series — Yahoo `^GSPC` and Norgate `$SPX` differ by at most 0.12%.

**Only 16 of the 26 filed events survive.** Ten are filed-only, twelve are
Norgate-only. At ≥3 both runs carry n=14 but only 7 dates coincide, moving the
12-month median from **+23.05% to +13.28%**.

| Thr | Horizon | Filed n → Norgate n | Filed win → Norgate win | Median Δ |
|---|---|---|---|---|
| ≥1 | 6m | 26 → 28 | 88.5% → 85.7% | −1.8pp |
| ≥2 | 6m | 22 → 23 | 86.4% → 87.0% | −1.7pp |
| ≥3 | 6m | 14 → 14 | 78.6% → 78.6% | −1.4pp |
| ≥3 | 12m | 14 → 14 | 85.7% → 85.7% | **−9.8pp** |

Six rows breach the pre-registered erratum bands. The cause is the data layer
Phase 0 documented as a known caveat: weekly Friday snapshots forward-filled
onto a daily calendar, plus 111 ever-members missing from the Yahoo panel. The
filed event set is substantially an artefact of that layer. **The Phase 0 and
WS4-H2 records receive an appended erratum; they are not superseded**, per
sign-off item 3.

### Decisions

| Component | Decision | Basis |
|---|---|---|
| ≥3 / 6m as a standalone timing trigger | **REJECT** | H1 held-out FAIL on the win leg; H2 pooled agrees |
| Four-dimension conviction grouping | **KEEP** | H1b: inversion does not reproduce, ρ +0.40 / +0.20 |
| Canonical frozen thresholds | **KEEP** | H3b: not looser than canonical; H3 5 of 6 anchors match |
| Norgate as the project data layer | **ADOPT** | Complete coverage, daily PIT, 4.25× window |
| Filed Phase 0 numbers | **ERRATUM** | H4: 16 of 26 events survive the layer change |
| ≥3 at 1m / 12m | **FLAGGED, no action** | Clears both legs but was not the pre-registered horizon |

### Trial register

Seven pre-registered tests, **0 parameters tuned, 0 configurations selected**:
H1 (4 thresholds × 5 horizons = 20 cells), H1b (1 rank correlation), H2 (20
cells, pooled), H3 (8 anchors), H3b (1 count), H4 (8 reconciliation rows × 3
variants). Every threshold, window, band and anchor was fixed in the spec and
committed before the first result existed. One deviation logged: the median
leg was tightened from Phase 0's undefined "meaningfully above" to the
95th-percentile bootstrap bar, agreed at sign-off before running.

### Artefacts

`scripts/norgate_provider.py`, `scripts/ws7_extension.py`,
`scripts/ws7_charts.py`, `tests/test_norgate_layer.py`,
`reviews/2026-08-01_ws7_results.json`, `reviews/charts/ws7_*.png`, technical
record `reviews/2026-08-01_ws7_norgate-history-extension.docx`. Commits
`886a7e6` (data layer), `a949d29` (run). Vendor cache lives outside the repo at
`C:\dev\.norgate-store\` — this repository is public and the licence is
personal-use-only.

### Next

The held-out window is now spent; it cannot be reused for the 12-month
question H1 surfaced. Either wait for genuinely new data, or pre-register a
12-month study accepting that its evidence is pooled rather than held-out and
saying so. Do not re-open the ≥3 / 6m decision on this evidence.

---

## WS8 — is the surviving cell deployable net of costs? 2026-08-01

**Provenance.** Pre-registered spec
`C:\dev\KICKOFF_ws8-thrust-tilt-deployability.md` (committed `vault-docs@8740710`
before any result; sign-off cleared same day). Context: Personal.

**Verdict in one line: the mechanism is real and generalises across three
independent cross-sections; it is not convertible into portfolio value.**

### What was already dead before WS8 started

WS7 rejected ≥3 / six months. Follow-up diagnostics then killed three more
candidate structures *before* any strategy was built. Recorded so they are not
re-tread:

| Structure | Why it died |
|---|---|
| EDD re-entry accelerator | The 42-day cooldown floor binds on only 9.0% of days, in episodes of median length 6 — it bites only after the raw score has already collapsed. Fresh thrusts landing while it binds: 4–7 in 28 years. |
| State-conditional overlay (drawdown / sub-200d) | Median lift +2.6 to +13.0pp in 1990–2008, +0.2 to −1.9pp in 2009–2026. Post-GFC the state base rate is 80–95%; dip-buying worked unconditionally. |
| Defensive-state override | Pooled +4.58pp 6m lift is a **composition artefact**: the ≥3 condition holds on 34% of defensive days pre-2009 but 93% post-2009, so the conditional sample over-samples the better era. Split: +5.99pp on 7 episodes pre-2009, −0.46pp post. The lift exists in neither era. |
| Risk-reduction / leverage framing | Forward max drawdown after a thrust is equal to or worse than baseline at every horizon. |
| Long-horizon holds | A 12-month hold is in the market 95.3% of days at ≥1. Buy-and-hold wearing a signal. |

**Shared root cause: the score is not scarce** — on 63% of days at ≥2 and 36%
at ≥3.

### H1 — the tilt backtest (the decision)

Unlevered overlay on a 60/40 SPX/Treasury base, monthly rebalance. V1: fresh
≥3 event → +20pp equity for 21 days. Costs 10bp per unit of allocation change.
Primary benchmark is a **cost-matched random-entry null** — the same tilt count,
size, duration and costs, placed by random circular rotation of the realised
tilt series, which preserves clustering exactly and destroys only the timing.

| | Net Sharpe |
|---|---|
| Untilted 60/40 base | 0.743 |
| **Headline V1 (+20pp, 21d)** | **0.709** |
| Null p5 / p50 / p95 | 0.672 / 0.718 / **0.751** |

**FAIL** against the pre-registered bar, and *below the null median* — the
timing loses to randomly-placed tilts of identical size and frequency. **All 18
variants underperform the untilted base**, monotonically worse in both tilt size
and hold length. Both eras agree (−0.041 pre-2009, −0.029 post), so this is not
era-dependence.

**Mechanism, confirmed three independent ways.**

1. The 1-month **mean** lift is +0.44pp against a **median** lift of +0.72pp,
   while volatility runs **1.16×** baseline. A portfolio compounds means and
   pays for variance; the statistic that survived every WS7 test is the one a
   portfolio cares about least.
2. The observed CAGR gain of +0.14pp matches the passive long-bias arithmetic
   (0.106 × 0.20 × (10.4% − 4%) ≈ +0.136pp) to four thousandths of a point.
   The timing contributed nothing.
3. It loses to its own null.

### H2 — cross-sectional replication (the mechanism test)

Breadth rebuilt unchanged on two further point-in-time universes; each trades
its own index.

| Universe | Window | n | Clusters | Median | Base | Lift | Beyond noise |
|---|---|---|---|---|---|---|---|
| S&P 500 (WS7) | 1990–2026 | 46 | 41 | +1.97% | +1.25% | **+0.72pp** | both legs |
| S&P SmallCap 600 | 1995–2026 | 48 | 42 | +2.46% | +1.42% | **+1.04pp** | both legs |
| Russell 2000 | 1991–2026 | 21 | 19 | +1.59% | +1.38% | +0.21pp | neither |

**Gate PASSES.** The mechanism replicates — strongly in the S&P 600 (a *larger*
lift than large caps, beyond noise on both legs, 42 episodes) and weakly in the
Russell 2000 (positive but within noise). Small-cap breadth carrying at least as
much information as large-cap is economically coherent: a "thrust" across 600
smaller names is a more meaningful statement about participation than the same
reading across 500 mega-caps.

**But the tilt fails in every universe:** Sharpe delta −0.034 (S&P 500), −0.007
(S&P 600), −0.045 (Russell 2000). Even the best case buys +0.47pp of CAGR for
3.8pp of extra drawdown.

### Deviations, both forced, both guarded

1. **Bond leg.** The spec named IEF; IEF begins 2002-07-26 and the window opens
   1990. Rather than splice mid-sample, the whole window uses one synthetic
   constant-maturity 10-year Treasury total return, validated against IEF over
   the overlap: correlation 0.957, annual return gap −0.39pp. The decision is
   near-insensitive since signal and null share the bond leg.
2. **Count-based thresholds.** The McClellan floor (−50 net advances) and net
   new highs (>20) are **counts, not ratios**. Taking "rebuild unchanged"
   literally would make the signal ~4× looser on a 1,950-name Russell than on
   the S&P 500 — the opposite of faithful. Both scaled and literal runs are
   reported; scaling is the headline. `scale=1.0` leaves every filed S&P 500
   result bit-identical, verified by re-running the WS7 H1 decision.

### Decisions

| Component | Decision | Basis |
|---|---|---|
| Thrust as an exposure-tilt strategy | **REJECT** | Fails its null; all 18 variants below base; fails in all three universes |
| Thrust as a real breadth phenomenon | **CONFIRMED** | Replicates in S&P 600 beyond noise on 42 episodes; positive in Russell 2000 |
| Small-cap breadth as the stronger read | **FLAGGED** | +1.04pp vs +0.72pp large-cap; candidate for any future work |
| EDD integration | **REJECT** | Intervention surface is 4–7 events in 28 years |
| Frozen engine constants | **KEEP** | Untouched; scaling only restores meaning across universes |

### Trial register

18 tilt variants × 1 universe + 4 replication runs (2 universes × 2 scaling
modes) + 1 null of 2,000 draws = **23 configurations, 0 parameters tuned, 0
selected for deployment**. Δ, hold, base weights, costs and the decision rule
were all fixed in the spec before this code existed.

### Artefacts

`scripts/ws8_tilt.py`, `scripts/ws8_replication.py`,
`scripts/ws8_fetch_universes.py`, `scripts/ws8_charts.py`,
`reviews/2026-08-01_ws8_results.json`,
`reviews/2026-08-01_ws8_replication.json`, `reviews/charts/ws8_*.png`,
technical record `reviews/2026-08-01_ws8_thrust-tilt-deployability.docx`.
Commit `34e4466`.

### Next

Nothing further on the tilt. If the project continues, the one live thread is
the S&P 600 result — small-cap breadth carries the stronger signal, and the
question of whether it is monetisable in a *small-cap* vehicle (rather than as
an SPX tilt) has not been asked. That needs its own pre-registration and should
not be bolted onto this one.

---

## Live-meter cutover to the Norgate layer, 2026-09-02

Not a study. The public page moved from the CSP1/Yahoo layer to the WS7
Norgate point-in-time layer (owner decision FLIP on three clean parallel runs:
2026-08-22, 2026-08-27, 2026-08-29), and the restatement is disclosed on the
page beside the numbers. The reconciliation table, the rendered-page
measurements and the operational changes are in the cutover addendum of
`reviews/2026-08-13_norgate-live-meter-scope.md`. What matters for this memo:
the live ≥3 / six-month cell reproduces H2 exactly (n = 46, win 76.1 %,
median +7.69 %) and the page states the WS7 verdict beside it; the Phase 0 and
WS4-H2 thrust-row figures (n = 14; +23.05 % at 12 months) have left the public
page and stand here with their erratum; the ≥3 cells at 1m and 12m render
with their noise badges and the FLAGGED-no-action status stated beside them.
Thresholds, the four-dimension grouping, the 60-day memory and the one-day lag
are unchanged. Commits `06e814b` (cutover) and `4fc3e54` (first Norgate-layer
publish, as of 2026-09-01).

*Last updated: 2026-09-02.*
