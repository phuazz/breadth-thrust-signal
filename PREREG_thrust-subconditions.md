# PREREG — thrust-subconditions (WS10), breadth-thrust-signal

**Frozen 2026-10-01 (Thursday, library-verified) at the commit tagged `prereg-freeze` in this repository; the
freeze commit hash and the spec sha256 are stamped into this header by the follow-up commit (the house pattern):
freeze commit `<stamped by the follow-up commit>`, spec sha256 `b805afaf4f02988bf9d1e7b83d0f7ed4d41696a327b610371d8b78e936b13f33`.** Nothing in
this file, in `spec/ws10_prereg_spec.json` or in `tests/` may change after the tag. A different question is a new
registration. The vault-root kickoff `C:\dev\KICKOFF_thrust-subconditions.md` is the design record; where the two
differ, this file governs, and every value the engine reads lives in `spec/ws10_prereg_spec.json` and nowhere else —
the engine reads the spec and never restates a value in code.

**Context: Personal.** Public repository (`phuazz/breadth-thrust-signal`). The Norgate licence is personal-use-only:
no vendor series value enters a tracked file; the study writes derived aggregates only. The NDR report that prompted
the study is licensed research read through a CGSI seat and stays in `OneDrive\Main\NDR`; this registration, its spec
and this public repository carry only the two published threshold levels (55.0 and 90.0), the report's name and the
fact that it lists twelve thrust indicators (the private vault-docs kickoff carries the indicator-family mapping and two
dated active counts). Nothing in this document is an instruction to trade.

**Owner decision that opens this study (2026-09-18, kickoff):** NDR's twelve-thrust count is NOT adopted and
crowd-sentiment's thrust trigger is untouched. What may be tested is two sub-conditions the meter does not carry,
placed INSIDE the existing dimensions as OR-members, with thresholds frozen at NDR's published levels. The draft was
signed off 2026-09-18 and no owner decision is open at the freeze.

**Binding, unchanged by this registration:** the meter's four-dimension rule, the canonical thresholds (Zweig
0.40 / 0.615, A/D ratio 1.90, share above the 50-day average 25 / 75, NH/NL 10 / 50, up-volume 0.90), the one-day
lag, the McClellan Summation exclusion and the 60-session memory. Only H-M passing could ever propose an engine
change, and that is a separate owner-approved commit with its own MOBILE_CHECK pass.

---

## 1. Objective (verbatim from the kickoff)

Do two frozen sub-conditions, deGraaf 20-day highs and the share above the 10-day average, add information inside
breadth-thrust-signal's four dimensions?

What it should do: fire on breadth surges the existing members miss, and change the meter's fresh-event set in a way
that carries forward lift beyond noise. What it currently does: neither exists in the engine; D2 fires on a 25→75
surge in the share above the 50-day average, D3 on new-high/new-low surges. Layer A (information) only; no deployment
claim of any kind.

## 2. Sources

- `C:\dev\KICKOFF_thrust-subconditions.md` (design record, signed off 2026-09-18; ledger check re-run and extended
  2026-10-01, vault-docs `1e8d1c8`).
- This project's `CLAUDE.md` and `README.md`; the engine modules at pinned sha256 (spec `engine.modules_sha256`):
  `scripts/compute_breadth.py`, `scripts/forward_returns.py`, `scripts/norgate_provider.py`, unchanged since
  `fa7a836` and the same pins smallcap-thrust-lab PREREG-1 carried.
- The house pattern for a frozen registration: `C:\dev\duration-state-lab\PREREG.md`, its `spec/prereg_spec.json`,
  `tests/test_contract.py`, `tests/test_mutants.py` and `PROMPT_RUN.md` (read only); `C:\dev\smallcap-thrust-lab\PREREG.md`
  as the sibling registration on this engine.
- `C:\dev\studies\2026-09-03_prereg-design-lessons.md` §7 (the K/P/R proposals, pending decision 2) and §11 (the
  Sharpe standard-error convention, not applicable here: no Sharpe statistic is read); the WS7-bar re-analysis design
  `C:\dev\studies\2026-09-17_ws7-bar-reanalysis_DESIGN.md` (unregistered) for the shape of the comparator.
- The NDR Breadth Thrust Watch report (OneDrive, licensed): the two published threshold levels only.

## 3. Ledger check, 2026-10-01 (verdict ADJACENT)

Run through `/ledger-check` at the freeze: `studies/hypotheses_index.md` read whole (168 of 168 rows, 100 per cent;
149 of 275 records unreviewed, at the time of the check, 15:52 SGT; the index moved during the day as other sessions
filed), the matched records opened by id in `studies/hypotheses.yaml`, and
`STUDIES_LEDGER.md` grepped on deGraaf, 20-day high, 10-day average, above 10-day, breadth-thrust-signal, WS7, WS8,
smallcap-thrust-lab, thrust-subconditions and bar-reanalysis. "deGraaf" and "20-day high" match nothing in the
ledger; "10-day" matches only the gold-miner family and D1's own 10-day A/D member. **Both candidates are new to the
vault; the panel, the rule and the comparator are inherited.** Every breadth-thrust-signal record cited is `†`
(extracted, unreviewed).

Inherited, each re-read by id and holding as the kickoff states it: `2026-08-01-breadth-thrust-signal-6` (rejected;
"a signal result, not a plumbing one; 74 configs evaluated, 0 parameters tuned"; no reopen), `-9` (inconclusive; its
reopen CONSUMED 2026-09-02 by smallcap-thrust-lab on the S&P 400; "the S&P 500 itself remains spent for this
question"), `-1` (rejected, the tilt), `-8` (superseded, the WS7 erratum), `2026-08-13-breadth-thrust-signal-1`
(confirmed, all four dimensions compute point-in-time pre-2018 on the Norgate layer), `2026-09-02-smallcap-thrust-lab-1`
(conditional [post-2009]), `-2` (rejected), `-3` (confirmed), `-4` (inconclusive; "the 46 large-cap and 48 mid-cap
events are spent for the corroboration question"), `2026-07-11-command-centre-5` (rejected; the two thrust
definitions are near-disjoint and stay separate), `2026-08-27-event-studies-4` and `-7` (no-effect; the vendor's
premise did not replicate), and the lessons memo's open finding on the WS7 bar.

Added at the re-run (the kickoff's section 2 carries the full statements): `2026-09-29-event-studies-1`/`-2` and
`2026-09-22-event-studies-1`/`-2` (breadth-divergence records on the same panel; the legs part company across
horizons, hence both legs stay in the clause and the horizons form one Holm family), `2026-09-18-breadth-thrust-etf-1`
(WS20, a second breadth statistic added nothing conditional on the first; informs P1), `2026-09-26-nq-orb-lab-2`/`-4`
(the 0.80 demotion rule in practice), the unregistered WS7-bar re-analysis design (the comparator's pattern; its
second null N2 is not adopted), and the open WS9 6-to-9-month question (no collision: the 6m cells here are the
candidates' own events, and the existing ≥3 cells at 6m are SEEN and sit on the comparator's side only).

## 4. Prior looks and the SEEN declaration

| Record or surface | Panel | Family | Cells seen | Direction | Use here |
|---|---|---|---|---|---|
| Phase 0 (2026-06-01), WS4-H2 | S&P 500, CSP1 layer, 2018-01 → 2026-05 | four-dimension fresh events, thresholds ≥1 to ≥4 | 1w, 1m, 3m, 6m, 12m | 6m median lift positive; win leg inside the band | the four-dimension event set is SEEN |
| WS7 (`-6`, `-7`, `-9`), results JSON | S&P 500, Norgate layer, 1990-12-28 → 2026-07-31, both halves | the same, held-out and pooled | the full 4 × 5 grid written; 1m, 6m, 12m rows in the memo; the ≥3 3m rows read by smallcap-thrust-lab | ≥3 / 6m rejected; 1m and 12m flagged | SEEN on both halves; the comparator side only |
| Live page (cutover row 2026-09-02) | S&P 500, Norgate layer, 1990-12-28 → live | fresh ≥1 to ≥4 | ≥3 at 1m, 6m, 12m with noise badges | as WS7 | SEEN |
| smallcap-thrust-lab H2 (`2026-09-02-…-4`) | the 46 S&P 500 fresh ≥3 events to 2026-09-01 | 3m `$SPX` medians by mid-cap confirmation | 3m | +2.61pp, inside the interval | the ≥3 3m cell is SEEN |
| Signal-side counts (cutover and smallcap rows) | S&P 500 | 98 fresh events to 2026-09-01; 46 at ≥3 in 41 clusters to 2026-07-31; last 2025-05-05 | none | — | the Step 0 reproduction guard |

**Seen:** the event sets of the existing four dimensions on both halves and every conditional statistic ever filed
on them; the NDR report's indicator list, its threshold column (May 2025 copy) and its current count; the vault's own
WS7, WS8 and small-cap records. **Not seen: no forward return, no win rate, no median, no lift and no percentile has
been computed for either candidate sub-condition on any panel, and no composite with either candidate admitted has
ever been built.** The candidates' event sets are unseen on both halves. The seen four-dimension event sets enter
this registration only as the comparator (the H-M "before" set and the Step 0 reproduction guard); a candidate or
added event set can never be a comparator (§8, and the contract test that pins it). Signal-side counts computed at
Step 0 are not looks under the SEEN doctrine (lessons memo §5, D1). The fixtures under `tests/fixtures/ws10/` are
synthetic and carry no market data.

## 5. Data and window (frozen; machine-readable copy `spec/ws10_prereg_spec.json` `data`)

- **Panel.** The deployed Norgate daily point-in-time S&P 500 panel: watchlist `S&P 500 Current & Past`, membership
  through `norgate_provider.membership_mask` on the full-symbol universe (effective-date convention, no shift),
  TOTALRETURN close for every candidate statistic, NONE-basis volume untouched (both candidates are price-based). The
  panel is masked by membership before any rolling statistic, the engine's own convention for D2 and D3, so a member
  counts only with the required history inside its membership.
- **Cache.** `C:\dev\.norgate-store\breadth-thrust-signal` as refreshed by the live meter's last Saturday run; the
  study never refreshes it and never writes to it; the NDU database time and the cache vintage are recorded in the
  manifest. The intraday-high sensitivity reads the `High` field of the TOTALRETURN basis from a study-only cache
  (`…\breadth-thrust-signal-ws10`) pulled by the run session.
- **Benchmark.** `$SPX` on the NONE basis through `norgate_provider.benchmark_series`, the price index WS7 and WS8
  used; the lift is a within-series difference, so the omitted dividend enters both sides.
- **Window.** 1990-12-28 (the first `data_ok` session after the 252-session burn-in; asserted equal, else STOP) to
  live (the last `data_ok` session in the cache at run time, recorded). Halves, the WS7 split kept for comparability:
  early 1990-12-28 → 2017-12-29, late 2018-01-02 → live; both bounds are sessions (Friday and Tuesday,
  library-verified) and the engine asserts it on the panel calendar.
- **Expected panel (Step 0, FAIL_STOP):** at least 1,290 ever-members; a membership-mask count of 490 to 510 on every
  `data_ok` session (the cutover row's 498 / 500 / 507; the mask count, not `valid_count`, so a halted name cannot
  STOP the run); the four-dimension event set reproduces the filed counts (98 fresh events at ≥1 to 2026-09-01; 46 at
  ≥3 in 41 clusters to 2026-07-31; last fresh event at any threshold 2025-05-05) exactly.
- **Date handling.** Every date operation goes through pandas / `datetime` (Python months are 1-indexed and the code
  comments say so); session arithmetic runs on the panel's own calendar; one month-boundary and one year-boundary
  fixture sit in the battery.

## 6. Three ways this study could be silently wrong, and the guard for each

At least one of the three is a way the COMPARATOR could be wrong (lessons memo §7.2 P4); here it is the third.
Every guard names the test that enforces it; the tests were committed before this section was written.

1. **A definition mismatch on the member condition produces a different event set under the same name.** A
   20-day high on closes against intraday highs, 20 sessions against 19 or 20 calendar days, a 10-day average
   including or excluding today, at-or-above against strictly above, a share divided before it is scaled: each
   is a near-miss that fires on other days, and the published levels were calibrated to NDR's own definitions.
   A forward-filled panel or a denominator that counts members without the required history belongs to the same
   class: it changes the share on every session a name has a gap or has just entered. *Guards:* the close-based
   20-session and 10-session definitions, the at-or-above rule, the share formula and the no-fill denominator are
   frozen in the spec (`candidates`); the planted panel pins the frozen rules against their nearest wrong
   neighbours — `tests/test_ws10_mutants.py` rejects the 19-session window, the strict new high, the 11-session
   and exclude-today averages, the strict threshold, the division-first share, the forward-filled panel and the
   present-without-history denominator (the panel carries a late entrant and an interior gap for this), and
   `tests/test_ws10_contract.py` pins a flat series at its closing high, a step-then-flat series above its average
   for exactly nine sessions, the gap and the entrant leaving the denominator, and exact equality at the planted
   55.0 and 90.0 (`test_flat_series_is_at_its_closing_high_under_the_inclusive_rule`,
   `test_step_then_flat_sits_above_its_ten_session_average_for_exactly_nine_sessions`,
   `test_a_gap_and_a_late_entrant_leave_the_denominator`, `test_candidate_shares_match_the_fixture`); the
   intraday-high variant runs as a labelled sensitivity, never in a family (spec `candidates.S-D3.labelled_sensitivity`).
2. **Double counting.** Both candidates are fast breadth measures that co-fire with D1 and D4, and with their own
   dimension's members, on the same days, so a "confirming" fire may be the same information wearing a new hat, and
   a member admitted inside an existing memory window adds a fire without adding an event. *Guards:* the redundancy
   and placement gate G2 with its pinned member fresh-fire rule (20 sessions False then True) and 5-session window in
   either direction — a candidate that LEADS a member fire co-fires, which is the kickoff's own mechanism and the
   direction a backward-looking window would miss (`test_member_fresh_fires_match_the_fixture`,
   `test_redundancy_on_the_planted_panel`, `test_redundancy_rule_known_cases`; the 4- and 6-session window and the
   backward-only mutants in the drill); the lead/lag split and the candidate's event count reported beside every G2
   status; OR-membership inside a dimension rather than a new dimension, pinned by the identity with
   `compute_composite` when nothing is admitted, by the OR-ed dimension counts, which a dimension REPLACED by its
   candidate cannot reproduce even though the 60-session memory hides the replacement from `n_dimensions`, and by the
   planted memory-expiry coincidence on which the frozen event rule and "any dimension newly on" disagree
   (`test_composite_with_members_is_the_engine_when_nothing_is_admitted`, `test_added_and_removed_events_match_the_fixture`;
   the replace, memory and newly-on mutants in the drill); H-M gated on the ADDED events only, never on the before
   set, with the REMOVED events and the share of added events inside an existing memory window declared as signal-side
   counts. D1 co-firing is reported and not guarded by G2: the gate reads the own dimension (REDUNDANT) and D4
   (MISPLACED) as the kickoff wrote it, and prediction P1 scores on any of the three shares (§15).
3. **The comparator is not like-for-like, or the wrong set sits on the wrong side of it.** A whole-window
   resample with no event count — the WS7 bar — clears both legs for random event sets 17 to 27 per cent of the
   time at 46 to 48 events (lessons memo §3.3; the WS7-bar re-analysis design); a count-matched null that ignores
   clustering, lets clusters overlap, or draws from sessions the observed events could not occupy (incomplete
   forward windows) moves the bar's dispersion in a direction that depends on the horizon, and any null returns a
   p-value, so nothing looks wrong. Separately, the seen four-dimension set could be scored as a treatment, or a
   candidate set used as a comparator. A sampler left unpinned between a joint whole-set rejection and a sequential
   placement would let the build decide whether the study runs at all (a joint draw of thirty clusters on a 27-year
   half is accepted about once in two thousand attempts). *Guards:* the primary null is count-matched,
   cluster-structured, placed SEQUENTIALLY on complete-window sessions of the return series with the lag included,
   separated by more than the cluster gap, seeded per cell and pinned draw for draw to the reference sampler in
   `tests/make_ws10_fixture.py` (`test_null_sets_reproduce_the_pinned_draws`,
   `test_null_draws_statistics_and_p_conventions`,
   `test_sampler_runs_at_thirty_clusters_and_lands_in_the_last_sessions_of_an_early_ending_window`,
   `test_complete_window_rule_includes_the_lag`; the count mutant in the drill); the Step 0 self-drill's centring leg
   checks the null's mean win rate and median against the unconditional complete-window figures over the half's valid
   sessions, an independent reference, and STOPs outside its bands, while its size leg is a labelled smoke check that
   cannot fail by construction (P0-6; `test_self_drill_reproduces_the_pinned_values_and_rejects_a_shifted_null`); the
   power routine is pinned on the same deterministic path at four effect sizes, including a saturation case a correct
   engine attains (`test_power_reproduces_the_pinned_values`; the α-instead-of-α/3 and wrong-units mutants in the
   drill); the comparator's observables are printed beside the treatment's before any percentile is read; the WS7
   read is reported beside the primary and is not admissible as a gate (spec
   `null.whole_window_resample_admissible_as_a_gate` false); `CandidateRegistry.assert_comparator` refuses a candidate
   or added set as a comparator, the runner routes every comparator it uses through it and records the checks in the
   manifest, and `before_set` takes no candidate argument (`test_the_seen_set_is_the_only_admissible_comparator`).

Plus the universe difference read as a threshold: the 90 level was published for a multi-cap universe and is
applied to the S&P 500 — the level is a prior, the ±5-point sensitivities are reported, and no level is chosen from
the outcome (§10, §13). Plus the power trap: a clause that cannot detect the registered effect reading as a
negative — power at +2.0pp per 3 months keyed to the 0.80 demotion and the 0.50 THIN suffix
(`test_power_is_one_at_a_huge_effect_and_the_size_at_zero`, `test_cell_and_clause_status_rules`). Plus look-ahead:
the one-session lag through `forward_returns.conditional_table` (`test_forward_stats_are_lagged_one_session`; the
unlagged mutant in the drill) and the burn-in and non-session refusals
(`test_refuses_any_computation_before_the_burn_in_plus_its_own_window`,
`test_no_event_inside_the_burn_in_even_when_the_share_crosses`, `test_non_session_date_is_refused`). Plus the
fixture discipline learned on 2026-09-19 (duration-state-lab A1): the wrong engine is committed under
`tests/mutants/ws10_wrong.py` and `tests/test_ws10_mutants.py` proves the planted expectations reject every
mutation while the reference passes — verified before the tag (29 drill tests), and the contract tests themselves were
run against a scratch reference engine built on the fixture's reference functions (46 of 46 pass; the engine was not
committed), so the contract is known to be satisfiable by a correct engine.

## 7. The two candidate definitions (frozen; spec `candidates`)

- **S-D3 (deGraaf), inside D3.** Share of members whose TOTALRETURN close is at a 20-session closing high: close at
  or above the maximum close over the trailing 20 sessions including today, on the membership-masked panel. Required
  history 20 sessions. Threshold **55.0 per cent, at or above**, NDR's published level, a prior and not a
  calibration. Declared sensitivities 50.0 and 60.0. A labelled intraday-high variant (high at or above the 20-session
  maximum high, from the study-only High cache) is reported at 3m, both legs, both halves — never a gate, never in
  a family.
- **S-D2 (share above the 10-day average), inside D2.** Share of members whose close is strictly above the simple
  mean of close over the trailing 10 sessions including today. Required history 10 sessions. Threshold **90.0 per
  cent, at or above**, NDR's published level for its own multi-cap universe, applied to the S&P 500 as a prior.
  Declared sensitivities 85.0 and 95.0. Universe caveat declared: the published levels are carried across a universe
  difference, not calibrated.
- **Shares** are in per cent over members present that day with the required history; a share is NaN where fewer
  than 400 such members exist (the engine's floor) and is never emitted before the required-history session.
- **Fresh events (the standalone cells).** A member fires on the first session its share is at or above its threshold
  after at least 20 consecutive defined sessions strictly below. Events are admitted only on `data_ok` sessions at or
  after the window start; the 20-session lookback may reach into the burn-in, no event may sit inside it. A request
  for candidate events before the first `data_ok` session, or on a panel with none, raises `BurnInRefusal`; any date
  argument that is not a session on the panel calendar raises `NonSessionDate`.
- **As OR-members (H-M).** The daily boolean "share at or above threshold" is OR-ed into its dimension as a daily
  boolean of the same kind as the existing members'; `compute_composite`'s 60-session memory and its event logic (a
  fresh event is the session on which `n_dimensions` increases) apply unchanged. With both candidate booleans False
  everywhere, the composite with members admitted must equal `compute_composite`'s output exactly (contract test).
- **One-day lag.** Every forward return is measured from the close of the session after the signal close, through
  `forward_returns.conditional_table`, whose `shift(1)` is the engine's guard.
- **Existing members' fresh fires (for the redundancy gate, pinned at the freeze).** The first session a member's
  daily boolean is True after at least 20 consecutive sessions False, on `data_ok` sessions: the same rule as the
  candidates. Members: D1 `zweig`, `ad_ratio_deemer`, `mcclellan`; D2 `pct_above_50dma`; D3 `nhnl_ratio`,
  `net_new_highs`; D4 `up_volume`.

## 8. Comparator (frozen; spec `null`, `ws7_read`, `h_m`)

- **Primary null, the only gate instrument: count-matched, cluster-structured random event sets.** For a cell
  (hypothesis, half, horizon) the observed set is `complete_window_events(treatment)`: the treatment events whose
  LAGGED forward window is complete on the return series (return-series position + 1 + h at most the last index; the
  rule in spec `horizons.complete_window_rule`). Events are grouped into clusters by the WS7 rule (a gap strictly
  greater than 63 calendar days starts a new cluster). A draw preserves the cluster count, each cluster's event count
  and each cluster's within-cluster offsets in positions of the half's valid sessions (its `data_ok` sessions, in
  order). **The sampler is pinned and sequential:** clusters are placed in chronological order of the observed set;
  each cluster's start is drawn uniformly over the positions on which the whole cluster fits, every event of the
  cluster is complete at the horizon on the return series, and every event is more than 63 calendar days from every
  event already placed in the draw; the admissible positions are enumerated in ascending order and one
  `rng.integers(len(admissible))` call chooses among them; a cluster with no admissible position restarts the whole
  draw, and 10,000 restarts for one draw is a STOP. Because the complete-window rule lives on the return series, the
  early half's late-2017 events are admissible on both the treatment and the null side although the half's valid
  sessions end 2017-12-29. 2,000 draws per cell; `numpy.random.default_rng([19901228, cell_index])` with the cell
  order listed in the spec; each draw scores the win rate and the median of the lagged forward returns. Monte Carlo
  p = (1 + draws at or beyond the observed) / (1 + 2,000) for each leg; the per-horizon p is max(p_win, p_med).
  The 95th percentiles of the null win-rate and median distributions are reported beside the observed values. The
  reference implementation of the sampler (`tests/make_ws10_fixture.py`, `ref_null_sets`) is the semantics; the
  contract pins the engine to it draw for draw on a deterministic path. A whole-window resample with no event count
  is not admissible as a gate.
- **The WS7 both-legs read, beside the primary for comparability, never a gate:** `forward_returns.unconditional_baseline`
  (moving-block bootstrap, block 21, 2,000 draws, seed 42, period-matched to the half) and `lift_table`'s two
  beyond-noise flags, so every cell can be read against the filed records' own bar.
- **H-M: the seen four-dimension event set is the descriptive reference, the random null is the gate instrument.**
  The "before" set is the four-dimension composite's fresh ≥2 (gated) and ≥3 (reported) events; the "after" set is the
  composite with both candidates admitted; the ADDED set is the after events whose signal date is not a before event
  date at the same threshold, and the REMOVED set is the mirror (a candidate that merely leads an existing member shifts
  events rather than adds them). The added set is the treatment and is tested as its own event set against the primary
  null; the before set is never scored as a treatment and never used as a null; its own 3m statistics are reported
  beside the change, labelled SEEN, with the share of added events whose signal date lies inside a before-composite
  ≥1 memory window (a promotion of an existing single-dimension state). **The engine refuses a candidate or added
  set offered as a comparator** (`CandidateRegistry.assert_comparator`, `ComparatorMisuse`); the runner routes every
  comparator it uses through the registry and records the checks in the manifest; `before_set` takes no candidate
  argument. This is a labelling discipline enforced in the runner and pinned by the contract, not a property of the
  statistic, and the registration says so.
- **Self-drill (Step 0, P0-6).** Per gate cell, the centring leg is the STOP: the null's mean per-draw win rate must
  lie within 0.05 of the unconditional share of positive complete-window lagged 3m returns over the half's valid
  sessions, and the null's mean per-draw median within 1.5pp of the unconditional median of the same returns — a
  reference computed directly from the return series, never through the null generator (coarse centring bands,
  pre-results). The size leg — the share of 200 random sets drawn on the self-drill stream and scored through the
  cell's own null with p at or below 0.05 — is reported as a smoke check and labelled as such: it cannot fail by
  construction and is not a STOP.

## 9. Step 0 probes (comparator-side, FAIL_STOP, no outcome statistic; spec `step0_probes`)

P0-1 panel identity (the membership-mask count) and the four-dimension event-set reproduction (the filed counts,
exactly); P0-2 both candidate shares defined on every `data_ok` session from the window start, first computable session
reported; P0-3 signal-side counts (fresh events and clusters per candidate per half, the lead/lag split of co-fires,
the ADDED and REMOVED ≥2 and ≥3 counts per half, the share of added ≥2 events inside a before-composite ≥1 memory
window) — counts, not looks; P0-4 `$SPX` continuous over the window and the half bounds resolving to sessions; P0-5
the spec sha256, the three module hashes, a clean tree on the frozen files and on `scripts/ws10_*.py`, and the
`prereg-freeze` tag reachable; P0-6 the self-drill's centring leg (STOP) with its size leg reported; P0-7 power at
+2.0pp (keyed) and at +1.0pp and +5.0pp (descriptive) per 3 months for each of the six gate cells, the clause-level
product per hypothesis, from the null spread at random entries only, with THIN and demotion flags; P0-8 the study-only
High cache (a shortfall records the intraday sensitivity NOT_RUN and does not STOP, the sensitivity being no gate). No
candidate-conditional forward return, win rate, median, lift or percentile is computed at Step 0. Any STOP files
`results/ws10_step0.json` and ends the run.

## 10. Cells, Holm families, power and gates (frozen; spec `horizons`, `holm`, `power`, `gates`)

- **Horizons.** 1m = 21, 3m = 63, 6m = 126 sessions on the `$SPX` calendar; **3m is the primary**. 12m and 1w are
  never computed as evidence.
- **Holm.** One family = the three horizons of one hypothesis in one half, step-down at α = 0.05 (thresholds 0.05/3,
  0.05/2, 0.05); a horizon clears if and only if Holm rejects it. Every clause requires the 3m cell to clear in both
  halves; the conjunction's family-wise rate is at most 0.05², printed beside the result (0.0025 expected false
  INFORMATIVE candidates under the global null).
- **Power and the 0.80 demotion rule (lessons memo §3.5; nq-orb-lab precedent).** The gate cells are the six 3m
  cells (H-S1, H-S2 and H-M ≥2, each in both halves; spec `null.gate_cells`). For each, Step 0 draws 1,000 random
  sets with the cell's observed structure through the pinned sampler on the power stream, adds the declared δ to
  every lagged 3m forward return of the drawn set and scores max(p_win, p_med) against the cell's own 2,000-draw
  null; power = the share of draws with that p ≤ 0.05/3 (the conservative Holm step, the other two horizons assumed
  null). Keyed δ = **+2.0pp per 3 months** (the kickoff's); +1.0pp and +5.0pp reported beside it, and the
  clause-level power (the product of the two halves) printed beside the per-cell figures. **THIN** below 0.50
  (suffix `_THIN`). **Demotion** below 0.80: a cell that does not clear reads **UNRESOLVED**, never FAIL. Cell
  status: PASS if it clears; FAIL if it does not clear and power at +2.0pp is at least 0.80; UNRESOLVED otherwise; a
  cell with no treatment event has power 0 and reads UNRESOLVED. Clause status over the two halves: PASS if both
  PASS; FAIL if any half FAIL; UNRESOLVED otherwise.
- **What the keyed delta implies, stated at the freeze (red-team S1-2, 2026-10-01).** The two-leg clause requires
  the win rate and the median to clear at α/3; a +2.0pp location shift moves the median by about one null standard
  deviation but moves the win rate only by the density mass in (−2pp, 0], about 0.09 on a 3-month return
  distribution with a standard deviation near 8.5 per cent, against a null standard deviation of the win rate of
  about 0.11 at 15 clusters and 0.056 at 50. The reviewer's Monte Carlo on an S&P-like synthetic path puts the
  clause's power at +2.0pp at 0.00 to 0.16 for 15 to 50 clusters, reaching 0.80 only near +6pp at 25 clusters or
  +4pp at 50. **Consequence, pre-committed rather than widened:** no gate cell is expected to reach 0.80, so FAIL is
  not expected to be reachable, every verdict is expected to carry `_THIN`, and the reachable verdict space is
  STOP_STEP0, PROPOSE_ENGINE_CHANGE, PROPOSE_CONDITIONAL, ALREADY_CARRIED and UNRESOLVED. A non-clearing cell reads
  "not detected at +2.0pp", never "absent". The study can therefore say "yes" (a candidate that clears a count-matched
  null at α/3 in both halves) and "already carried" (G2 is signal-side and needs no power), and defers "no" to
  accrual under a fresh registration that declares its own keyed delta or statistic. The owner's alternatives — a
  prior-scaled keyed delta such as +5.0pp, or the median leg alone as the gate — are recorded in §20 and would be
  pre-results amendments if ruled; neither is a look, because no own-data conditional statistic exists.
- **G1 (standalone information), per candidate.** The candidate's fresh events clear both legs against the primary
  null at 3m under Holm, in both halves. Status PASS | FAIL | UNRESOLVED. INFORMATIVE means G1 PASS.
- **G2 (redundancy and placement), per candidate.** The share of the candidate's fresh events within 5 sessions
  (either direction) of a fresh fire of any existing member of its own dimension, of D1, and of D4, on the pooled
  window and reported per half. MISPLACED if the D4 share is strictly greater than the own-dimension share; else
  REDUNDANT if the own-dimension share is strictly above 70 per cent; else DISTINCT; NO_EVENTS if the candidate never
  fires. The D1 share is reported and never gated (the kickoff's rule as written; P1 scores on any of the three
  shares, a different predicate, acknowledged). The status carries the candidate's event count, the suffix THIN_G2
  below ten fresh events in the pooled window (the mapping is unchanged; the reader sees the count) and the lead/lag
  split of its co-fires (member fire before, on, or after the candidate's session). A REDUNDANT candidate is recorded
  as "already carried"; a MISPLACED one as such; neither is proposed for the engine.
- **G3 (the meter).** The ADDED fresh ≥2 events of the composite with both candidates admitted clear both legs against
  the primary null at 3m under Holm, in both halves. Status PASS | FAIL | UNRESOLVED. The ≥3 added events are
  reported at 3m, never gated; the REMOVED events at both thresholds and the memory-window share are reported beside.
- **Sensitivities (descriptive, never gated, in no family):** S-D3 at 50.0 and 60.0, S-D2 at 85.0 and 95.0, and the
  S-D3 intraday-high variant, each at 3m, both legs, both halves, against the primary null, with its own cell index.
- **Every figure** carries its baseline (the null's 95th percentiles and the WS7 band), its event and cluster counts
  and its half. No conditional figure is shown without its baseline.

## 11. Verdict mapping (over gate statuses only; spec `verdict`)

In order: **STOP_STEP0** if any probe stopped. **PROPOSE_ENGINE_CHANGE** if G3 PASS and both candidates are
proposable (G1 PASS and G2 DISTINCT). **PROPOSE_CONDITIONAL** if G3 PASS and exactly one candidate is proposable:
the proposal names that candidate and the separate engine-change registration must re-measure H-M on the proposed
member set before adoption (H-M was measured once, with both admitted, as registered). **ADDS_FIRES_WITHOUT_INFORMATION**
if G3 FAIL and at least one candidate is proposable. **ALREADY_CARRIED** if at least one candidate is G1 PASS and no
candidate is proposable. **NO_INFORMATION** if every candidate is G1 FAIL. **UNRESOLVED** otherwise (a deciding clause
below its power floor did not pass). Suffix `_THIN` when the keyed power of any gate cell is below 0.50. The gate
table travels with the verdict. **UNRESOLVED opens no engine change, reopens nothing, and is re-read once only, under
a fresh registration by accrual, not before 2031-01;** accrual alone cannot lift the two-leg clause's power at +2.0pp
to 0.80, so that registration declares its own keyed delta or statistic before it runs. Under the keyed delta as
frozen, FAIL and the two verdicts built on it (NO_INFORMATION, ADDS_FIRES_WITHOUT_INFORMATION) are not expected to be
reachable (§10); they stay in the mapping so that the rule is complete over the status space, not because the
registration expects them. Only the two PROPOSE verdicts propose anything, and the proposal is a separate
owner-approved commit with its own MOBILE_CHECK pass; this registration changes nothing live.

## 12. Register mapping

Three records, one per hypothesis, filed at the freeze as PENDING placeholders in the register's form (verdict
`inconclusive`, `cause_of_death` "PENDING — pre-registered, not run", `status_raw` PRE-REGISTERED; the gold-drivers
precedent of 2026-10-01) and overwritten by the verdict read:

- **H-S1 (deGraaf, standalone):** fresh S-D3 events carry 3-month forward S&P 500 returns whose conditional win rate
  AND median both exceed the 95th percentile of the count-matched, cluster-structured null, in both halves, under Holm
  across {1, 3, 6} months. Record: G1 status, the two halves' cells, G2 status and shares.
- **H-S2 (share above the 10-day, standalone):** the same statement for fresh S-D2 events. Record as above.
- **H-M (the meter):** with both candidates admitted as OR-members, the ADDED fresh ≥2 conviction events carry
  3-month lift beyond the null in both halves. Record: G3 status, the added counts, the before set's seen statistics
  labelled as such, the ≥3 descriptive.

The verdict row in the ledger cites all three; a sensitivity, the WS7 read, the self-drill and the power figures are
reported in the row and the results file, never as records.

## 13. Prohibited claims

No deployment, tilt or portfolio claim (WS8 rejected the tilt family). No statement that the meter should carry more
than four dimensions or a count-based score. No threshold chosen from the outcome: the sensitivities and the intraday
variant are descriptive. No "independent confirmation": both candidates are measured on the same panel and the same
episodes as the existing members. No REDUNDANT or MISPLACED candidate described as adding information. No UNRESOLVED
clause described as a negative result, and no non-clearing cell described as "absent" rather than "not detected at
+2.0pp". No figure for either candidate without its baseline, its episode count and its half. No NDR figure, table or
series beyond the two published threshold levels.

## 14. Stop conditions

Any Step 0 probe fails (STOP_STEP0; the block is filed and the run ends). The spec hash, a module hash or the
tree-cleanliness check fails. A null draw cannot be placed in 10,000 attempts. A candidate share is undefined on any
`data_ok` session inside the window. The four-dimension event set does not reproduce the guard counts. Anything the
spec does not answer is written to `ESCALATION_ws10.md` and the run stops; nothing is designed around.

## 15. Registered predictions (verbatim from the kickoff) and how each is scored

- **P1** — S-D2 is REDUNDANT with D1 or D4 above the 70 per cent line (0.6). Right if S-D2's own-dimension, D1 or D4
  co-fire share is strictly above 70.0. This predicate reads any of the three shares; the G2 gate reads the own
  dimension only (and D4 for MISPLACED), as the kickoff wrote both, so P1 can be right while G2 reads DISTINCT. The
  difference is stated here and in the spec so the word "REDUNDANT" is not read as one predicate.
- **P2** — S-D3 clears H-S1 in the 1990–2017 half but not 2018→ (0.4). Right if S-D3's early-half cell status is
  PASS and its late-half cell status is FAIL or UNRESOLVED.
- **P3** — H-M fails because the added events number under 15 in the later half (0.5). Right if G3 is not PASS and
  the ADDED fresh ≥2 events in the late half number fewer than 15; at such a count the clause is expected to read
  UNRESOLVED under the demotion rule, which scores as a non-pass.

Only H-M passing proposes an engine change. The predictions are leans, not gates; they are scored at the verdict
read whatever they turn out to be.

## 16. Outputs

`results/ws10_results.json` — the declared cells only, the file the verdict reader opens: `run` (git revision, tag,
spec sha256, module hashes, NDU time, cache vintage, window end, panel facts), `step0`, per candidate the signal-side
counts, the six gate cells with observed values beside the null's 95th percentiles and the WS7 flags, the Holm steps,
the power figures, the redundancy block and the G1/G2 statuses, `h_m` (before and after counts, the SEEN before
statistics labelled, the added cells, G3), the sensitivities, the gate table, the verdict and the predictions scored.
`results/ws10_full.json` — every computed row including the self-drill and the ≥3 descriptive; not opened at the
verdict read except where this document names a descriptive. `results/ws10_step0.json`, `results/ws10_manifest.json`,
`data_local/ws10_runs_log.jsonl`. The four results files are tracked; `data/signals.json`, `docs/index.html`,
`template.html` and the live meter's cache are never written.

## 17. Run protocol

Build and run from `PROMPT_RUN_ws10.md` on Opus fast, verbatim: read order, the three silent-wrong ways restated,
build in the stated order with one commit each (the engine, the runner, and the study-only High transport
`scripts/ws10_high_cache.py`, which the frozen `norgate_provider` does not provide and which carries its own smoke
check), the battery green (every contract test running, none skipped) before any real data, Step 0 with FAIL_STOP,
the full run ONCE, results committed, no interpretation. The Fable
verdict read, the prediction scoring and the filing follow in a separate session. Anything the spec does not answer
is a STOP parked to `ESCALATION_ws10.md`, never a design-around. The run is booked for the bucket Thu 2026-10-01
22:00 → Thu 2026-10-08 22:00 SGT (week of Mon 2026-10-05), suggested slot Mon 2026-10-05 or Tue 2026-10-06 evening
SGT after the Sat 2026-10-03 WS7 review; the dates are flagged for the owner's confirmation.

## 18. Filing

Kickoff row in `C:\dev\STUDIES_LEDGER.md` (2026-10-01, Personal, breadth-thrust-signal, PRE-REGISTERED, "kickoff,
pre-registered, no result"), three PENDING placeholder records (H-S1, H-S2, H-M) in `studies/hypotheses.yaml`, the
index regenerated, four guards green; the kickoff's Status line set to FROZEN with the tag; `C:\dev\NEXT.md` carries
the frozen registration with its run window. The verdict row, the three records' results and the memo entry land after
the run.

## 19. What this registration did not do

It computed no forward return, no event-conditional statistic and no percentile for either candidate; it built no
composite with a candidate admitted; it read no NDR material beyond the two levels; it opened no results JSON row of
the existing records beyond those the kickoff and the smallcap-thrust-lab registration already cite; it did not
refresh or write the live meter's cache; it did not change the engine modules, the pipeline, the refresh guards, the
page or `data/signals.json`; it did not register the WS7-bar re-analysis, the mid-cap replication of a clearing
member, the deviation-from-trend or three-day price thrusts, or any twelve-thrust count; it did not adopt a second
null; it did not change the keyed delta, the both-legs rule or the G2 predicate after the red-team review (it stated
their consequences and recorded the owner's alternatives in §20); it did not pull the High field (the run session
does, into a study-only cache). The freeze-time pins — design decisions taken before any outcome exists, listed in
the spec's `freeze_time_pins` — are: the existing members' fresh-fire definition; per-horizon count matching on
complete windows with the complete-window rule on the return series; the sequential sampler; the self-drill's
centring leg; the half-wise Holm family with the clause-level product printed; the conservative power step and the
stated reachable verdict space; zero-event cells UNRESOLVED; the D1 share reported not gated and P1's predicate
acknowledged; G2's count, THIN_G2 suffix and lead/lag split; the OR-member daily boolean and the event rule; REMOVED
events and the memory-window share as declared counts; the cache read without refresh and the run-session High
transport; H-M measured once with both admitted and PROPOSE_CONDITIONAL for the one-proposable case; the 2031-01
re-read date with its own keyed delta.

## 20. Freeze review record

The vault `red-team` agent reviewed the registration, the spec, the fixture, the wrong engine and the contract tests at
`6383cc9` (spec sha256 `fb5b61ac…`) and returned "not ready to tag": two blocking findings, five must-fix items and
thirteen worth-noting pins. The full report and the freeze session's verification table are filed in
`reviews/red-team_spec-freeze_2026-10-01.md`. Every S1 and S2 was fixed before the freeze commit; the S3 items were
fixed or dispositioned; nothing in the fixes reads a result, because none exists.

| Finding | Disposition before the tag |
|---|---|
| S1-1 the power contract test unattainable by a correct engine (a saturated win-rate leg on a positive-drift path) | FIXED: the comparator's reference implementation (sampler, draws, Monte Carlo p, power, self-drill) lives in `tests/make_ws10_fixture.py` on a deterministic zero-drift path with 24 events in 12 clusters; power pinned at +0 / +3 / +10 / +50pp as 0.0 / 0.0 / 0.37 / 1.0; the α-step and wrong-units mutants rejected; the contract run against a scratch reference engine, 46 of 46 |
| S1-2 the keyed +2.0pp has power near size, so FAIL is unreachable and the study cannot say "no" | ADOPTED option (i): the keyed delta stays the kickoff's; §10 and §11 state the reachable verdict space and the reading "not detected at +2.0pp"; +1.0pp and +5.0pp and the clause-level product printed; options (ii) a prior-scaled delta and (iii) the median leg recorded below for the owner |
| S2-1 the sampler unpinned between joint and sequential rejection | FIXED: sequential placement pinned in the spec and the reference, draw for draw in the contract; 30 clusters for 2,000 draws tested |
| S2-2 the null's placement range narrower than the treatment's; the lag fencepost | FIXED: `complete_window_events` on the return series with the lag, on both sides; an early-ending window tested |
| S2-3 the self-drill tautological | FIXED: centring leg against an independent unconditional reference (bands 0.05 / 1.5pp) is the STOP; size leg a labelled smoke check; in the API and pinned |
| S2-4 the fixture blind to the co-fire direction and the membership mask | FIXED: 800-name panel with a late entrant, an interior gap, a burn-in composite event and a memory-expiry coincidence; leading candidates in the known cases; five more near-miss engines rejected |
| S2-5 "REDUNDANT" two predicates; §6 overstating the D1 guard | FIXED by statement: the kickoff's gate kept, P1's any-of-three predicate scored as written and distinguished in §6, §10, §15 and the spec; the memory-window share and the REMOVED events declared; option (iv) gating on max(own, D1, D4) recorded below |
| S3 Holm thresholds restated; gate cells undefined; High transport absent; mask count; guard key threshold; zero-event cells; comparator wording; removed events; G2 thinness; stale §3 figures; licence sentence; dirty engine module; booking label | all FIXED as listed in the review file §3 |

**Owner alternatives recorded, not adopted** (each a pre-results amendment on the duration-state-lab mechanism if the
owner so rules; none is a look): (ii) key the demotion to a prior-scaled delta such as +5.0pp per 3 months, with
+2.0pp and +1.0pp descriptive — FAIL becomes reachable, and "no" would mean "not +5pp"; (iii) gate on the median leg
with the win rate descriptive — departs from the WS7 both-legs convention the hypotheses state; (iv) gate REDUNDANT
on max(own, D1, D4) above 70 — a candidate that fires on D1's days inside D2 or D3 could no longer be proposed.

Catches logged by the reviewer in `~/.claude/red-team-catches.md` (seven lines): SATURATION TEST BLOCKED BY A
DISCRETE LEG; DEMOTION KEYED BELOW THE CLAUSE'S REACH; NULL SAMPLER UNPINNED BETWEEN JOINT AND SEQUENTIAL
REJECTION; COMPARATOR PLACEMENT RANGE NARROWER THAN THE TREATMENT'S; ONE WORD, TWO PREDICATES; and two instances
(GUARD TAUTOLOGICAL BY CONSTRUCTION; FIXTURE BLIND TO THE DIRECTION AND THE MASK).
