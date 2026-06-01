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

# Smoke-test the whole pipeline with synthetic data (no network):
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

---

## Architecture

```
breadth-thrust-signal/
├── scripts/
│   ├── compute_breadth.py   # grouped/weighted signal engine (pure, tested)
│   ├── forward_returns.py   # conditional study + bootstrap baseline (pure, tested)
│   ├── membership.py        # point-in-time masking + fallback
│   ├── data_providers.py    # price + volume fetch/cache (yfinance)
│   ├── pipeline.py          # fetch -> mask -> compute -> study -> render
│   └── validate_d1.py       # cross-check D1 thrust dates vs published anchors
├── tests/test_engine.py     # 6 tests: thrust detection, scoring, no-lookahead, date edges
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

## Known caveats / next steps

- **Residual data-layer leak.** Membership is survivorship-correct, but 111 of
  715 ever-members were delisted/renamed beyond Yahoo's reach and cannot be
  fetched, so they drop from historical breadth (surfaced in `signals.json`
  `data_quality` and the dashboard scope banner). Delisted names skew weak, so
  their absence mildly understates past declines.
- **Pre-2018 point-in-time membership is unresolved.** Extending before 2018
  needs a reconstructed historical membership list and would be lower-confidence.
- **Small-sample power.** Eight years yields too few fresh events to confirm a
  ≥3 edge. Re-evaluate as the window lengthens, or test whether the cleaner
  ≥1/≥2 6-month signal is the more honest object of study.

*Last updated: 2026-06-01*
