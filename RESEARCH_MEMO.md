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

*Last updated: 2026-07-03.*
