# Tier-2 #4 — gauge-upgrade audit: vendor internals vs deployed gauges

**Date**: 2026-08-05 (Wednesday — weekday verified with Python `datetime`).
**Scope**: breadth-thrust-signal + market-regime-dashboard, per the Tier-2
queue set after the Norgate subscription. REVIEW-AND-PROPOSE — nothing
deployed changes with this filing.
**Artefacts**: `scripts/gauge_vendor_crosscheck.py` (deployed-logic
imports: `compute_breadth` thresholds + `_crossed_up_within`,
`norgate_provider` panel path exactly as `ws7_extension.build()`);
statistics + event dates `data/gauge_vendor_crosscheck.json`. Vendor pulls
are runtime-only; no vendor series values are committed (licence).

## Headline verdicts

1. **market-regime-dashboard: KEEP AS-IS — nothing to migrate.** The
   repo contains no constituent-breadth internals at all; its gauges are
   froth/macro series (FRED, AAII/NAAIM scrapes, valuation) outside
   Norgate's coverage, and its ops model is CI-updated public data —
   local-only NDU would regress it. No further work proposed.
2. **breadth-thrust-signal: the WS7 self-computed layer STANDS.** It is
   definition-controlled, point-in-time, survivorship-free and filed;
   replacing it with packaged vendor series would surrender exactly that
   control. The audit question was narrower: can vendor series serve as
   a cheap standing GUARD? Answer per pair below.

## Per-pair findings (self-computed 1990-2026 vs vendor, ~9,200 joint days)

| Pair | Corr (levels / daily changes) | Verdict |
|---|---|---|
| P3 advances & declines | 0.9992 / 0.9996 and 0.9999 / 0.9999, scale ≈ 1.0 | **GUARD-READY** — near-identical; Deemer 10d >1.90 day-flags agree 99.91%, episodes 63 matched of self 67 / vendor 65 |
| P4 % above 50d MA | 0.9993 / 0.9926, scale 0.974 | **GUARD-READY** — 13 of 17/19 thrust events matched; unmatched are boundary-timing cases |
| P2 McClellan oscillator | 0.9982 / 0.9992, **scale 2.05** | **GUARD WITH CONVERSION** — vendor is ratio-adjusted (×1000/(adv+dec) ≈ 2.05× on a ~500-name universe, stable); the deployed −50 raw-count threshold ≈ −102 vendor units; usable only with the conversion documented |
| P1 packaged #SPXZWBT | **0.847** / 0.69 | **DO NOT ADOPT — definitional trap confirmed and RESOLVED**: #SPXZWBT is the 10-day **SIMPLE** MA of adv/(adv+dec) (corr 1.0000 to SMA10 of the vendor's own counts); the canonical and deployed Zweig leg is the **EMA10** (self vs EMA10-of-vendor-counts corr 0.9987). Unchanged-issues hypothesis tested and rejected (0.808). A drop-in adoption would have silently changed the signal: 38 vendor events vs 51 self, only 24 matching. Any vendor guard for this leg must be BUILT from #SPXADV/#SPXDEC |
| P5 52W NH / NL | 0.982 (scale 0.85) / 0.950 (scale 1.0) | **LOOSE GUARD ONLY** — vendor counts ~15% fewer highs, consistent with a price-basis vs the deployed TR-close basis; ratio-thrust events 246 matched of 270/304; self stays authoritative |
| P6 up-volume (D4) | — | **NO VENDOR EQUIVALENT** — no SPX up/down-volume series in the package (only the McClellan Volume Oscillator); D4 stands alone on self-computed data |

## Proposal (optional, behind approval — NOT built)

A single standing guard fits the existing weekly refresh: recompute the
week's D1 Deemer flags and %MA50 from `#SPXADV`/`#SPXDEC`/`#SPX%MA50`
(plus EMA10-of-counts for the Zweig line) and alert on any day-flag or
thrust-event disagreement — the same divergence-check pattern as the
breadth-thrust-etf Stage-1 publisher. Estimated one short script and one
line in the weekly job. P2/P5 are excluded from alerting (conversion and
basis noise would false-positive); P1 uses counts, never the packaged
ZWBT. Say the word and it gets built as its own small session; declining
costs nothing — the audit value (the ZWBT trap is now on record) is
already banked.

## Three silent-failure modes, defended

Definitional mismatch papered over (per-pair units/basis/scale reported;
events only compared on like terms; the P1 trap caught, decomposed and
resolved rather than averaged away); membership-timing conflation (level
and change correlations reported separately; differences filed as
findings); look-alike events counted as agreement (±5-trading-day
matching with unmatched dates listed on both sides).
