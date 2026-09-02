# CLAUDE.md — breadth-thrust-signal

Project rules layering on top of the vault master `CLAUDE.md`. Context:
**Personal** research (systematic investing). Senior-analyst tone, no
contractions, British / Singapore spelling.

## What this project is

A risk-on breadth-thrust conviction meter and conditional forward-return study.
The bullish mirror of `equity-defense-dashboard`. See `README.md` for the full
design.

## Hard rules specific to this project

- **The score is four dimensions, not eight signals.** Do not "restore" the
  naive 0–8 sum. The A/D family (Zweig, McClellan, 10-day A/D) is collapsed into
  D1 on purpose, because those signals share one underlying series. Any change
  to the grouping must be justified against double-counting.
- **Never fit the McClellan Summation threshold to the data.** It is excluded
  deliberately. Re-introducing it with an "empirically derived" threshold is
  in-sample overfitting and is not permitted without an out-of-sample defence.
- **Thresholds are canonical and frozen.** Zweig 0.40 / 0.615, A/D ratio 1.90,
  %-above-MA 25/75, NH/NL 10/50. Do not optimise these in-sample.
- **Signal is lagged one day** before any forward return is measured. The
  `test_no_lookahead_signal_is_lagged` test guards this; do not weaken it.
- **Forward-return claims always carry their baseline.** Never present a
  conditional win rate or median without the unconditional bootstrap baseline
  and the lift. A number without its base rate is misleading.
- **Survivorship discipline.** The deployed layer is Norgate daily
  point-in-time membership with full delisted history (since the 2026-09-02
  cutover; the CLI default). The CSP1 weekly snapshots are the flagged
  fallback's point-in-time source (`--provider csp1`). If the static-universe
  fallback beneath that is ever used, the `survivorship_bias` flag must stay
  visible in both `signals.json` and the dashboard banner.
- **Volume is unadjusted.** Direction and MAs use adjusted close; the up-volume
  ratio uses raw volume. Do not mix these.

## Dashboard rules (inherit vault dashboard architecture)

- `template.html` is the source. **Never edit `docs/index.html`** — it is built.
- Light theme, sans-serif, high contrast.
- Build: `python scripts/pipeline.py` (canonical, not `build.py`). Builds the
  Norgate layer by default since 2026-09-02 (NDU must be running; vendor
  series stay in `C:\dev\.norgate-store\`); `--provider csp1` is the flagged
  fallback and needs the CSP1 roster.
- **The page is a LIVE METER** (owner decision 2026-08-13). The weekly guarded
  refresh is `scripts/weekly_refresh.py` (schtask Sat 07:00 SGT); it must never
  publish with a guard failing, and the client-side staleness banner
  (`renderStaleness`) plus the fleet-watch heartbeat row are its guard layer —
  do not remove either.

## Tests

`python -m pytest tests/ -q` must pass before any commit. The suite covers
thrust detection on planted synthetic surges, score bounds, the OR-within-
dimension invariant, the no-lookahead lag, and date edge cases (month and year
boundaries via a date library).

*Last updated: 2026-09-02*
