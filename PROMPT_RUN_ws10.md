# PROMPT_RUN — WS10 thrust-subconditions (build and run, Opus fast)

Paste into a fresh Claude Code session opened at `C:\dev\breadth-thrust-signal`. The registration is frozen at
the tag `prereg-freeze` (2026-10-01); verify the tag exists and that `PREREG_thrust-subconditions.md`,
`spec/ws10_prereg_spec.json` and `tests/` are clean against HEAD before pasting. NDU must be running (the
intraday-high sensitivity pulls one field into a study-only cache); the live meter's cache is read as it is and
never refreshed or written by this run.

```
We are executing the FROZEN registration WS10 thrust-subconditions of breadth-thrust-signal at
C:\dev\breadth-thrust-signal. Read CLAUDE.md, PREREG_thrust-subconditions.md (sections 6, 10 and 20
last) and spec/ws10_prereg_spec.json first; they layer on C:\dev\CLAUDE.md. Read the API in the module
docstring of tests/test_ws10_contract.py, the reference implementation in tests/make_ws10_fixture.py
(its functions are the semantics of every rule where the words leave room; the engine must reproduce
the null sampler draw for draw) and the fixture record tests/WS10_FIXTURE.md. Execute VERBATIM.
Anything the spec does not answer is a STOP: write it to ESCALATION_ws10.md and stop. Never redesign,
never tune, never read a cell the spec does not declare, never edit PREREG_thrust-subconditions.md,
spec/ or tests/.

Before any code, restate the three ways this study could be silently wrong and the guard for each
(PREREG section 6): a definition mismatch on the member condition (window, inclusion, tie rule, share
formula, no forward fill, no history-less denominator); double counting across D1, D4 and the own
dimension's members, in both directions of the co-fire window; a comparator that is not like-for-like
(an unpinned sampler, a placement range narrower than the treatment's, a self-drill with no independent
reference) or the seen set on the wrong side of it. Plus the universe difference read as a threshold,
the power trap and the stated reachable verdict space under the keyed +2.0pp (section 10), look-ahead,
and the fixture discipline (the committed wrong engine must keep failing).

Build, in this order, one commit each:
1. scripts/ws10_subconditions.py — every function of the contract API exactly as the docstring of
   tests/test_ws10_contract.py states it: load_spec and get (a missing key raises FreezeViolation, never
   a default), spec_hash, the four exception classes, resolve_session, candidate_share (100 * count /
   members, multiplication first; a name counts only with its close and its rolling statistic defined;
   NaN below the member floor; never emitted before the member's own window), daily_fire, fresh_events,
   candidate_events (BurnInRefusal below HL_LOOKBACK plus the member's window, or with no data_ok
   session), member_fresh_fires, cofire_share (either direction), cofire_split, redundancy (status,
   n_events, thin), composite_with_members (identical to compute_composite when nothing is admitted;
   the candidate boolean OR-ed into its dimension; an event is a session on which n_dimensions
   increases), fresh_at, before_set (no candidate argument), added_events, removed_events,
   memory_window_share, CandidateRegistry, forward_stats (the lag through forward_returns.conditional_table),
   complete_window_events, forward_window_end, cluster_ids, cluster_count, null_sets (the pinned
   SEQUENTIAL sampler of spec null.placement: identical to ref_null_sets draw for draw), null_draws,
   mc_p, per_horizon_p, holm, power, self_drill, cell_status, clause_status, verdict. Every constant
   comes from the spec through get(); the three engine modules are imported read-only and never modified.
2. scripts/ws10_run.py — Stop; spec_hash_or_stop; check_engine_modules; check_frozen_tree_clean (the
   frozen files AND scripts/ws10_*.py); event_set_guard; the Step 0 block (P0-1 to P0-8 in the spec's
   step0_probes, FAIL_STOP, no outcome statistic; power and the self-drill from random entries only; the
   membership-mask count for P0-1); the run harness over the spec's null.cell_order with the per-cell seed
   keys; every comparator routed through CandidateRegistry.assert_comparator with the checks recorded in
   the manifest; the writers for results/ws10_results.json (declared cells only), results/ws10_full.json,
   results/ws10_step0.json, results/ws10_manifest.json and data_local/ws10_runs_log.jsonl. The manifest
   records the git revision, the tag, the spec sha256, the three module hashes, the NDU database time,
   the cache vintage and the realised window end. VERIFY that FROZEN_SPEC_SHA256 in
   tests/test_ws10_contract.py and tests/test_ws10_mutants.py equals
   `python -c "import hashlib;print(hashlib.sha256(open('spec/ws10_prereg_spec.json','rb').read()).hexdigest())"`;
   if they differ, STOP.
3. scripts/ws10_high_cache.py — the study-only High transport the frozen norgate_provider does not
   provide (spec data.high_basis_study_cache): price_timeseries on the TOTALRETURN basis, PaddingType.NONE,
   no start_date, the High column kept, full-symbol keys, parquet footer provenance as the live cache,
   written under C:/dev/.norgate-store/breadth-thrust-signal-ws10 and never under the live meter's root;
   a smoke check that one symbol's High is at or above its Close on every session. Descriptive use only.
4. python -m pytest tests/ -q must be green with every contract test RUNNING (none skipped) and the
   mutant drill still passing, before Step 0 touches real data.
5. Step 0 on real data: the panel from the live meter's cache WITHOUT refresh (norgate_provider.build_panel
   and membership_mask on the full-symbol universe; data_quality recorded), the four-dimension composite
   through compute_breadth.compute_composite, the event-set reproduction guard (98 fresh events at >=1 to
   2026-09-01; 46 at >=3 in 41 clusters to 2026-07-31; last fresh event at any threshold 2025-05-05 —
   exact, else STOP), candidate computability on every data_ok session from 1990-12-28, the signal-side
   counts per half (fresh events, clusters, the lead/lag split, the ADDED and REMOVED >=2 and >=3 counts,
   the memory-window share), $SPX continuity and the half bounds as sessions, the hash and tree checks,
   the self-drill's centring leg per gate cell (STOP outside the bands; the size leg reported), power at
   +2.0pp (keyed) and at +1.0pp and +5.0pp per 3 months for each of the six gate cells with the
   clause-level product and the THIN and demotion flags, and the study-only High cache for the intraday
   sensitivity (a shortfall records NOT_RUN, it does not STOP). Any STOP is filed in
   results/ws10_step0.json and the run ends. No candidate-conditional forward return, win rate, median,
   lift or percentile in this step.
6. The full run ONCE: every cell in spec null.cell_order against the count-matched cluster-structured
   null (2,000 draws, seed key [19901228, cell_index], the pinned sequential sampler, complete windows on
   the return series); the WS7 both-legs read beside each gate cell (unconditional_baseline, block 21,
   seed 42, period-matched to the half; never a gate); Holm per hypothesis per half across {1m, 3m, 6m}
   with the steps computed from alpha; the redundancy block per candidate with its count, THIN_G2 flag and
   lead/lag split; H-M with both candidates admitted (before counts and the before set's 3m statistics
   labelled SEEN, after counts, the ADDED >=2 cells gated and the >=3 cells reported, the REMOVED events
   and the memory-window share beside); the sensitivities at 3m (the four threshold variants and the
   intraday-high variant, labelled, never in a family); the cell and clause statuses from the power
   figures; the gate table; the verdict enum computed mechanically from spec verdict.rule_in_order with
   the _THIN suffix; predictions P1 to P3 scored mechanically from spec predictions.*.scored_right_if.
   Every figure beside its baseline (the null's 95th percentiles and the WS7 band), its event and cluster
   counts and its half. Write the four results files.
7. Commit the four results files and the runs log entry. Do not interpret. Hand off with the path of
   results/ws10_results.json and the verdict enum; the Fable verdict read, the prediction scoring review
   and the ledger and register filing follow in a separate session.

Hold to: no contractions and British spelling in code comments and commit messages; Python months are
1-indexed and comments say so; date arithmetic through pandas only; no Norgate value in any tracked file
(derived aggregates only; the results files carry shares, counts, dates and return statistics, never a
per-symbol price); nothing of NDR's beyond the two published threshold levels; the fixture and the
tests are frozen and are not edited to make them pass; the live meter, its cache, data/signals.json,
docs/ and template.html are never written.
```
