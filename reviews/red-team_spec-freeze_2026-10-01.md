# Red-team review at the spec-freeze gate — WS10 thrust-subconditions

Filed 2026-10-01 (Thursday, library-verified) by the freeze session (Fable 5.1). Reviewer: the vault `red-team`
agent (quant PM, CIO and CPM lenses), scope the registration `PREREG_thrust-subconditions.md`, the spec
`spec/ws10_prereg_spec.json`, the fixture (`tests/make_ws10_fixture.py`, `tests/fixtures/ws10/expected.json`,
`tests/WS10_FIXTURE.md`), the wrong engine and its drill (`tests/mutants/ws10_wrong.py`, `tests/test_ws10_mutants.py`)
and the contract tests (`tests/test_ws10_contract.py`) at commit `6383cc9`, with the kickoff, the three pinned engine
modules and the duration-state-lab pattern as background. The agent changed nothing in this repository. Every blocking
and must-fix finding was fixed by the freeze session BEFORE the freeze commit, as the brief requires; the worth-noting
items are recorded below with their disposition. The owner decisions the review asked for were resolved by keeping the
kickoff's signed values and stating their consequence, with the alternatives recorded for the owner to rule on as
pre-results amendments if they so choose.

**Verdict of the review as returned: not ready to tag.** Two blocking findings (S1), five must-fix items (S2), a list
of pins (S3). **State at the freeze commit: every S1 and S2 fixed and re-verified; the S3 items fixed or dispositioned.**

## 1. Status

| Item | State |
|---|---|
| Reviewed at | `6383cc9` (spec sha256 `fb5b61ac…`) |
| Frozen set after the fixes | `PREREG_thrust-subconditions.md`, `spec/ws10_prereg_spec.json`, `tests/` at the freeze commit (spec sha256 stamped in the PREREG header by the follow-up commit) |
| Own-data statistics computed | None. Every check ran on the synthetic fixture, the deterministic unit path or the committed files |
| Catches log | Seven lines appended by the agent to `~/.claude/red-team-catches.md` (mirrored at wrap-up) |

## 2. What the freeze session verified and did

| Finding | Verified how | Fix applied before the tag |
|---|---|---|
| S1-1 the power contract test unattainable by a correct engine | Reproduced the agent's reading of the test: four events on a positive-drift random walk saturate the win-rate leg, so `p_win` under the tie rule cannot reach α/3 | The comparator's reference implementation now lives in `tests/make_ws10_fixture.py` (`ref_null_sets`, `ref_null_draws`, `ref_mc_p`, `ref_power`, `ref_self_drill`) on a deterministic zero-drift triangle path with 24 events in 12 clusters; power is pinned at +0 / +3 / +10 / +50pp (0.0 / 0.0 / 0.37 / 1.0 at 100 draws against a 300-draw null); the α-instead-of-α/3 and wrong-units mutants are in the drill and are rejected; the contract tests were run against a scratch reference engine built on these functions and pass 46 of 46 |
| S1-2 power near size at the keyed +2.0pp, FAIL unreachable | The agent's two Monte Carlos (0.00 to 0.16 at 15 to 50 clusters) read; the mechanism (a location shift moves the win rate only by the density mass in (−2pp, 0]) accepted | Option (i): the keyed delta stays the kickoff's +2.0pp, and the registration STATES the reachable verdict space (STOP_STEP0, PROPOSE_ENGINE_CHANGE, PROPOSE_CONDITIONAL, ALREADY_CARRIED, UNRESOLVED, each with `_THIN`); descriptive power at +1.0pp and +5.0pp and the clause-level product are printed beside every gate cell; a non-clearing cell reads "not detected at +2.0pp", never "absent"; options (ii) a prior-scaled keyed delta such as +5.0pp and (iii) the median leg as the gate are recorded in §4 below for the owner |
| S2-1 the null sampler unpinned (joint rejection STOPs at about 35 clusters) | The agent's acceptance simulation read; the pinned sequential sampler run at 30 singleton clusters for 2,000 draws completes count-matched | Spec `null.placement` and `null.restart` pin the sequential sampler in chronological cluster order with whole-draw restarts and one `integers` call per placement; the reference implements it; the contract pins the first three draws date for date and the 30-cluster case |
| S2-2 placement range narrower than the treatment's; lag fencepost | Confirmed on the early half (valid sessions end 2017-12-29, the return series continues) and on the docstring's `end − h` position | `complete_window_events` added to the API with the rule "position + 1 + h at most the last index of the return series", applied to the treatment and to the admissible null positions; the contract tests a window that ends 100 sessions before the series and asserts draws land in its last h sessions |
| S2-3 the self-drill tautological | Accepted: sets drawn from the null's own generator are uniform against it by construction | P0-6 is now a centring leg against an independent unconditional reference (bands 0.05 on the win rate, 1.5pp on the median), the STOP; the size leg stays as a labelled smoke check; `self_drill` is in the API and pinned on the unit path, and a shifted null fails it |
| S2-4 fixture blind to the co-fire direction and the membership mask; seven near-misses pass | The agent's `probe_fixture_mutants.py` read | The panel is re-planted at 800 names (so a planted gap cannot blank the 400-member floor) with a late entrant (N798 from session 300), an interior gap (N799, sessions 340 to 345), a 95 per cent step inside the burn-in that makes the four-dimension composite carry a ≥2 event there, and a rise timed to the expiry of the memories that step opened so the frozen event rule and "any dimension newly on" disagree (2019-07-09); the known cases carry candidates that LEAD member fires; the drill now rejects the backward-only co-fire, the forward-filled panel, the present-without-history denominator, `fresh_at` without `data_ok` and the newly-on rule (29 drill tests) |
| S2-5 REDUNDANT is two predicates; §6 overstates the D1 guard | Confirmed from the kickoff's own wording | The kickoff's gate is kept (own dimension only; D4 for MISPLACED); P1's any-of-three predicate is scored as written and the difference is stated in the spec and §15; §6 now says D1 co-firing is reported, not guarded; the share of ADDED ≥2 events inside a before-composite ≥1 memory window and the REMOVED events are declared signal-side counts |
| Dates | Python `datetime` (months 1-indexed) | 2026-10-01 Thursday; 1990-12-28 and 2017-12-29 Fridays; 2018-01-02 Tuesday; 2026-10-03 Saturday; 2026-10-05 Monday; 2026-10-06 Tuesday; 2026-10-08 Thursday — all as the agent verified |

Not verified by the freeze session: the agent's power Monte Carlos on an S&P-like synthetic path (read, not re-run; the
conclusion is robust to any base rate between 0.55 and 0.70 by the agent's own sensitivity, and the registration's
disclosure does not depend on the exact figure).

## 3. Worth-noting items and their disposition

| S3 item | Disposition |
|---|---|
| Holm thresholds restated and rounded in the spec | FIXED: the spec carries the rule `alpha / (m − k + 1)` only; the contract asserts the engine's steps equal `alpha/3, alpha/2, alpha` exactly |
| "Gate cell" undefined for `_THIN` and P0-7 | FIXED: `null.gate_cells` lists the six 3m cells |
| The High-field transport does not exist | FIXED by disclosure: the run session writes `scripts/ws10_high_cache.py` with its own smoke check; descriptive only; P0-8 bounds it to NOT_RUN |
| P0-1 members per day: mask count or `valid_count` | FIXED: the membership-mask count (`data_quality.members_per_day`) |
| The last-fresh-event guard key does not state the threshold | FIXED: `last_fresh_event_ge1_on_or_before_2026-09-01` |
| A candidate with zero events in a half has no defined G1 status | FIXED: power 0, UNRESOLVED (spec `power.cell_status_rule`; contract) |
| "H-M's comparator is the seen set" while G3 is scored against the null; the registry has no caller | FIXED by rewording §8 and spec `h_m.gate_scored_against`; the runner routes every comparator through `CandidateRegistry.assert_comparator` and records the checks in the manifest, stated as a discipline |
| Removed events not a declared count | FIXED: `removed_events` in the API; declared in spec `h_m.removed` and P0-3 |
| G2 has no thinness statement | FIXED: the candidate's event count beside the status, the suffix THIN_G2 below ten events, the lead/lag split of co-fires reported; the mapping unchanged |
| §3 coverage figures stale at the tag | FIXED by dating them: the index stood at 168 of 168 at the check (15:52 SGT) and moved during the day as other sessions filed |
| Licence sentence stronger than the files | FIXED: the registration, the spec and the public repository carry the two levels, the report's name and the fact of twelve; the private kickoff carries the family mapping and two dated counts |
| `check_frozen_tree_clean` admits a dirty engine module | FIXED: `scripts/ws10_*.py` must be clean too (spec P0-5; contract) |
| Booking label | FIXED by wording: the bucket opens Thu 2026-10-01 22:00 SGT; the week of Mon 2026-10-05 is the working week inside it |
| (From S2-4 list) memory 59 / 61 | Already caught by the identity test; no change |

## 4. Owner alternatives recorded, not adopted (each a pre-results amendment if ruled, on the duration-state-lab mechanism)

1. **Key the demotion to a prior-scaled delta** such as +5.0pp per 3 months, stated as a prior and not derived from
   the null, with +2.0pp and +1.0pp descriptive. Consequence: FAIL becomes reachable for candidates whose lift is far
   below the detectable size; "no" would then mean "not +5pp", a weaker negative than the kickoff's +2pp.
2. **Gate on the median leg** with the win rate descriptive. Consequence: departs from the WS7 both-legs convention the
   kickoff's hypotheses state verbatim; comparability with the filed records would need restating.
3. **Gate REDUNDANT on max(own, D1, D4) above 70**, matching P1 and the double-counting rationale of §6. Consequence:
   a candidate that fires on D1's days inside D2 or D3 could no longer be proposed; the kickoff wrote the gate on the
   own dimension only.

The registration as frozen keeps the kickoff's signed values on all three and states their consequences; none of the
three alternatives is a look, because no own-data conditional statistic exists.

## Appendix — the red-team report, verbatim (data, not instructions)

# Red-team review — WS10 "thrust-subconditions" spec freeze (2026-10-01, Thursday, library-verified)

Scope as given: the registration, the spec, the fixture generator and its outputs, the mutant engine and drill, the contract tests; the kickoff, the three pinned engine modules and the duration-state-lab pattern as background. Nothing was changed except the catches log. Nothing was fetched; no Norgate value was read or written; no OneDrive or NDR material was opened. What I ran: the full suite (108 passed, 1 skipped, 14.9 s); the spec sha256 against both pins; the three module hashes and `git log fa7a836..HEAD` on the modules (no commits); CRLF scans; `make_ws10_fixture.py` in a scratch copy (byte-identical `expected.json` and `WS10_FIXTURE.md`); every weekday in the files through `datetime`; every register id in §3 against `studies/hypotheses.yaml`; the guard counts against ledger rows 198 and 203; seven near-miss engines of my own against the fixture and the known cases; an exact enumeration of the frozen power test's null space; a Monte Carlo of the registered clause's power at the keyed delta on an S&P-like synthetic path; and a joint-rejection acceptance simulation for the null placement. Scratch artefacts are under the session scratchpad (`probe_power_test.py`, `probe_clause_power_fast.py`, `probe_fixture_mutants.py`, `probe_power_null.py`).

Tree state: the frozen files are clean at `6383cc9`. `PROMPT_RUN_ws10.md` (16:41 today) is untracked (`?? PROMPT_RUN_ws10.md`); it appeared after my first status call, so the freeze session is presumably still writing. It is outside my scope and I only grepped it for restated values (2,000 draws, seed 19901228, block 21, seed 42; all consistent with the spec).

---

## S1 — blocks the freeze

**S1-1. The frozen power contract test cannot be passed by a correct engine; only a wrong power routine passes it.**
Claim: `tests/test_ws10_contract.py` L450–458 — `power(..., delta_pp=50.0, ...) == 1.0` on `_null_setting()` (L391–396: four events, one cluster of three plus a singleton, seed-3 random walk with positive drift, 300 null draws), with `mc_p` pinned "at or beyond includes the tie" (L432–433) and `per_horizon_p = max` (L435).
Evidence: `probe_power_test.py` enumerates every admissible joint placement on that exact path (50,850 placements): 82.5 per cent of complete-window 63-session forward returns are positive and 55.7 per cent of placements have all four returns positive, i.e. a null win rate of exactly 1.0. The treatment with +50pp has win rate 1.0, so under the pinned tie rule p_win ≈ (1 + 167) / 301 ≈ 0.56 against the α/3 bar of 0.0167 on every power draw; P(at most 4 of 300 null draws at the ceiling) is 6 × 10⁻⁹⁸. `big == 1.0` is unattainable. The engines that pass are the wrong ones: a strict `>` on the win leg inside `power`, or a power scored on the median leg alone. Either overstates run-time power, which is the figure that decides FAIL against UNRESOLVED. The second assertion (`nil <= 0.10`) is satisfied by anything, including a routine that uses δ in the wrong units or α instead of α/3 (my harness: both mutants pass both assertions wherever the reference does), so the power layer has no discriminating test at all.
Class: new — SATURATION TEST BLOCKED BY A DISCRETE LEG (kin to GUARD THAT CONTENT CANNOT SATISFY; BATTERY SCOPED TO THE NAMED RISKS).
Fix before the tag: re-plant the saturation case with enough independent events on a zero-drift path that the null's mass at win rate 1.0 is below α/3 (about 24 events in 12 clusters at base 0.5 gives 0.5¹² ≈ 0.0002); add a deterministic mid-range case from a reference `ref_null_sets` / `ref_null_draws` / `ref_power` in `make_ws10_fixture.py` with the expected power pinned in `expected.json`, and add the pp-unit and α-step mutants to `ws10_wrong.py` so the drill rejects them.

**S1-2. At the keyed +2.0pp the registered clause has power near its size at any plausible count, so every non-clearing cell files UNRESOLVED and the negative branch of the verdict is unreachable.**
Claim: PREREG §10 L262–269 and spec `power` L199–209 — power at +2.0pp per 3 months, demotion below 0.80, THIN below 0.50; §11 L288–294 and spec `verdict` L229–237 present FAIL, NO_INFORMATION and ADDS_FIRES_WITHOUT_INFORMATION as outcomes; P2 (L336–337) names FAIL.
Evidence: the clause requires BOTH legs at α/3. A +2pp location shift moves the median leg by about one null sd but moves the win rate only by the density mass in (−2pp, 0], about 0.09 on a 3m distribution with sd 8.5 per cent, against a null sd of the win rate of 0.11 at 15 clusters and 0.056 at 50. Two independent Monte Carlos (`probe_clause_power.py`, `probe_clause_power_fast.py`; S&P-like path, base positive share 0.645, sequential cluster placement, 2,000-draw nulls, 400–500 power draws) give power at +2pp of 0.00–0.01 at 15 clusters / 20 events, 0.04–0.06 at 25 / 40, 0.14–0.16 at 50 / 80; 0.80 is reached only at about +6pp (25 clusters) or +4pp (50 clusters). At +2pp the median leg alone reads 0.05 / 0.17 / 0.30 and the win leg alone 0.02 / 0.10 / 0.25. The real base rate is the filed WS7 baseline (seen; I did not read the cache); the conclusion holds across any base between 0.55 and 0.70. Consequence under the rules as frozen: no cell can reach power 0.80, so `cell_status` is PASS or UNRESOLVED only; FAIL, NO_INFORMATION and ADDS_FIRES_WITHOUT_INFORMATION cannot occur; `_THIN` (power < 0.50) attaches to every verdict; and the 2031-01 re-read, with about 15 per cent more data, sits at the same floor. The conjunctive clause compounds it: even where both halves reached 0.80 the clause-level power would be 0.64 (MIXED SIDEDNESS INSIDE A CONJUNCTIVE CLAUSE, 2026-09-25).
Class: new — DEMOTION KEYED BELOW THE CLAUSE'S REACH (kin to THINNESS RULE THAT RESCUES A FAIL; POWER GATE ON A DIFFERENT CLAUSE).
Owner decision before the tag (all pre-results): (i) accept that the verdict space is {PROPOSE*, ALREADY_CARRIED, UNRESOLVED, STOP} and say so in §10–§11, removing FAIL from P2 and the prose; or (ii) key δ to an effect the two-leg statistic can detect at the plausible count (a prior such as +5pp per 3 months, with +2pp and +1pp descriptive), stated as a prior, not derived from the null (FLOOR DEFINED AS ITS OWN MDE, 2026-09-25); or (iii) gate on the median leg with the win rate descriptive. Whichever is chosen, print the clause-level (product) power beside the per-cell figures.

---

## S2 — fix before the tag

**S2-1. The null placement sampler is unpinned between joint and sequential rejection, and the literal reading STOPs the study at about 35 clusters a half.**
Claim: spec `null.placement` and `null.separation` L161–162 ("drawn uniformly without replacement … separated by more than 63 calendar days (rejection-sampled; 10000 failed attempts for one draw is a STOP)"); PREREG L219–223; contract docstring L39–43.
Evidence: `probe_power_null.py` — on a 27-year half (7,046 business days) a joint draw of k starts with whole-set rejection is accepted with probability 0.53 at 10 singleton clusters, 0.07 at 20, 0.0005 at 30 (about 2,000 attempts a draw, 4 million for 2,000 draws) and 0 of 2,000 at 40 (a Step 0 STOP under L162). Sequential placement (each start uniform over positions admissible given the clusters already placed) runs at any plausible count but samples a slightly different distribution; the contract test L399–423 passes both. Nothing in the spec or docstring says which; an Opus session must pick, and the pick decides whether the study runs. Multi-event clusters make the joint acceptance worse than my singleton figures.
Class: new — NULL SAMPLER UNPINNED BETWEEN JOINT AND SEQUENTIAL REJECTION.
Fix: pin sequential placement in the observed cluster order, each start uniform over the admissible positions given those already placed, a restart of the whole draw when a cluster has no admissible position, 10,000 restarts a STOP; add a contract case with 30 clusters on a 2,000-session calendar that must return 2,000 draws.

**S2-2. The null's placement range is narrower than the treatment's admissible range in the early half, and the lag-one window makes the docstring's last admissible start one session short.**
Claim: spec L159 (observed set = events "whose forward window at the horizon is complete on the return series") and L161 (placement where "every event's forward window at the horizon is complete") against contract docstring L41–42 ("every event sits at least horizon_sessions before the end of valid_sessions").
Evidence: for the early half, `valid_sessions` ends 2017-12-29 while the return series continues, so a treatment event in the last 126 sessions of 2017 is scored at 6m (its window is complete on `$SPX`) but no null draw can be placed there; the placement universe excludes 21 / 63 / 126 sessions of about 6,800. Separately, under the one-session lag an event at position `end − h` satisfies the docstring yet needs `px[end − h + 1 + h]`, one past the end; `forward_stats` drops it (contract L369 pins exactly this drop), so that draw is one event short of count-matched. The contract test cannot see either, because its `valid = cal[251:]` ends with its calendar (L403). There is also no API function for the treatment-side filter ("complete on the return series"), so the fencepost is implemented twice by hand.
Class: MACHINE SPEC AND PROSE DISAGREE ON A CONSEQUENCE (instance); COMPARATOR UNGUARDED (instance) — new name in the log: COMPARATOR PLACEMENT RANGE NARROWER THAN THE TREATMENT'S.
Fix: give `null_sets` the return series (or its last index) and define the admissible start as `s + 1 + h <= last index of the return series`; add `complete_window_events(events, index_series, h)` to the API and use it on both sides; add a contract case whose `valid_sessions` ends 100 sessions before the return series and asserts draws land in the last h sessions of `valid_sessions`.

**S2-3. The Step 0 self-drill P0-6 cannot fail, has no API entry and no test.**
Claim: PREREG L238–240 and spec L256 — 200 random sets "scored through the cell's own null; the share with per-horizon p ≤ 0.05 must lie in [0.00, 0.10], else STOP"; §6 item 3 (L163–164) lists it among the comparator guards.
Evidence: sets drawn from the null's own generator scored against that null return p ≈ U(0,1) for any placement rule, so the share at or below 0.05 is 0.05 ± 0.015 (sd at n = 200); the band's upper edge is 3.2 sd away. A null restricted to bull years would pass. The contract docstring (L7–60) lists no self-drill function; §6's rule "every guard names the test that enforces it" is not met here (no test is named for P0-6). The catches log has this class twice already (2026-09-26, 2026-10-01).
Class: GUARD TAUTOLOGICAL BY CONSTRUCTION (instance).
Fix: replace the uniformity leg with a centring leg that has an independent reference — the null's mean of per-draw medians and win rates within a stated band of the half's unconditional complete-window figures (seen, the WS7 baseline) — keep the size leg as a smoke check labelled as such, name the function in the API and pin it on the synthetic path.

**S2-4. The fixture is blind to the direction of the co-fire window and to the membership mask; seven near-miss engines pass.**
Claim: PREREG §6 L145–147 ("the 5-session window … either direction", guarded by `test_redundancy_on_the_planted_panel` and `test_redundancy_rule_known_cases`); §5 L106–107 ("a member counts only with the required history inside its membership"); spec L120 and L139.
Evidence (`probe_fixture_mutants.py`): (a) a co-fire that counts only member fires at or before the candidate reproduces every fixture share (`expected.json` L151–162: S-D3 own 0 / d1 50 / d4 0, S-D2 own 50 / d1 0 / d4 50) and the contract's 60.0 known case (L291–295: all five planted candidates sit at or after their fires), while the kickoff's mechanism (L219–222) is that the candidates LEAD — the untested direction; (b) `ffill` before the rolling statistic and (c) a denominator counting members present without the required history are identical to the reference on the fixture (no missing close, L72 of the mutant test asserts it; no entrant), and differ on a 60-session panel with one interior NaN (reference NaN, mutant 100.0) or 20 entrants (100.0 against 95.2); (d) `fresh_at`/`before_set` without the `data_ok` clause (no ≥2 event sits inside the fixture's burn-in; caught at run time only by the real-panel guard); (e) an event rule "any dimension newly on" instead of "n_dimensions increases" (identical on all 572 sessions, including the identity test). Memory 59 / 61 are caught by the identity test; not blind.
Class: FIXTURE BLIND TO THE WINDOW (instance) — logged as FIXTURE BLIND TO THE DIRECTION AND THE MASK.
Fix: plant a candidate event 1–5 sessions BEFORE a member fire in the known cases and on the panel; plant one interior NaN and one late entrant in the fixture (NaN rows are legitimate on a padding-NONE panel); add the three mutants to `ws10_wrong.py` and the drill.

**S2-5. P1's "REDUNDANT" and gate G2's "REDUNDANT" are different predicates under one word, and §6 claims a D1 guard that G2 does not provide.**
Claim: PREREG L334–335 / spec L244 — P1 right if the own, D1 or D4 share is above 70; L274–276 / spec L145 — REDUNDANT only if the own-dimension share is above 70, D1 reported never gated (freeze pin L301); §6 item 2 L144–153 names "co-fire with D1 and D4" as the double-counting risk and G2 as its guard; §13 L321 "No REDUNDANT … candidate described as adding information".
Evidence: a candidate with own 30 / D1 85 / D4 10 scores P1 right, reads DISTINCT and is proposable; with G1 and G3 PASS the verdict is PROPOSE_ENGINE_CHANGE for a member that fires on D1's days inside D2 or D3, which is the duplication `compute_breadth.py` L5–24 exists to prevent, and nothing in H-M's random null distinguishes "a D1 day promoted to ≥2" from a new episode. The kickoff wrote the gate this way (L164–167) and the pin is pre-results, so no results-contingent choice is open; but the registration contradicts itself on what REDUNDANT means, and §6's guard claim overstates.
Class: new — ONE WORD, TWO PREDICATES.
Fix (owner decision): either gate REDUNDANT on max(own, D1, D4) > 70, matching P1 and §6, or keep the pin and rewrite P1 as "co-fires above 70 with D1 or D4" with §6 stating that D1 co-firing is reported, not guarded. Either way, add a declared signal-side count: the share of ADDED ≥2 events whose signal date falls inside a before-composite ≥1 memory window.

---

## S3 — worth noting

- **Holm thresholds restated and rounded.** Spec L193 carries `[0.016667, 0.025, 0.05]` beside the α/3 rule; `np.allclose` against `alpha/3` is False (contract L447 then fails an engine that reads the spec's value, as "never restate" would push it to). Replace with exact fractions or delete.
- **"Gate cell" is undefined** for the `_THIN` suffix (spec L238) and P0-7; the runner must pick the six 3m cells. Under S1-2 the point is moot, but pin it.
- **The High-field transport does not exist.** Spec L76–82 and PREREG L110–111 have the run session pull `High`; `norgate_provider._pull` (L228–241) returns `Close` and `Volume` only and the modules are frozen, so the Opus session writes a new pull, cache and reader with no API entry and no test. P0-8 bounds it to NOT_RUN, so descriptive only; say so or pre-declare NOT_RUN.
- **P0-1 "members per day inside [490, 510]"** (spec L251) does not say mask count or `valid_count`; a halted-name day would spuriously STOP on `valid_count`. Pin the mask count (`data_quality.members_per_day`, provider L393–406; the cutover row reads 498/500/507).
- **`last_fresh_event_on_or_before_2026-09-01`** (spec L71) does not state the threshold; the ledger's 2025-05-05 is the last event at any threshold. Name it in the key.
- **A candidate with zero events in a half** has no defined G1 cell status (n = 0: the null and power cannot be built); contract L487 pairs NO_EVENTS with G1 FAIL, which the power rule cannot produce. Pin UNRESOLVED_THIN.
- **"H-M's comparator is the seen four-dimension event set"** (PREREG L231) while G3 is scored against the random null and the before set is descriptive; `CandidateRegistry.assert_comparator` has no caller in the API, so §6 item 3's refusal is a labelling discipline, not a mechanical guard. Reword.
- **Removed events are not a declared count.** The fixture itself shows one (`expected.json` L100–114: 2020-10-12 is a before ≥2 event absent from after); "the change in the event set" (spec L224) should name before-not-after explicitly, since a candidate that merely leads an existing member shifts events rather than adds them.
- **G2 has no thinness statement** though it can convert a G1 and G3 PASS into ALREADY_CARRIED; at three events one event moves the share by 33 points. State a minimum count or the count beside the status in the verdict table, and report the lead/lag split of co-fires.
- **§3 figures will be stale at the tag**: PREREG L55–56 "168 of 168 rows … 149 of 275 records"; the index now stamps 170 of 170 and 284 (L18). The WS10 placeholders are not yet filed, as §18 expects.
- **Licence sentence stronger than the files.** PREREG L12–14 "nothing of NDR's beyond the two published threshold levels enters any file"; the kickoff (L21–27, vault-docs) carries NDR's indicator-family mapping and two dated active counts. The public PREREG itself carries only the two levels, the report's name and the fact of twelve; say that.
- **`check_frozen_tree_clean` admits a dirty engine module** (contract L137 treats `" M scripts/ws10_subconditions.py"` as clean), so a results file could cite a revision that does not contain the engine that produced it. Require `scripts/ws10_*.py` clean too.
- **Booking**: the bucket opens Thu 2026-10-01 22:00 while labelled "week of Mon 2026-10-05"; weekdays all verified correct.

---

## Verified sound

Spec sha256 `fb5b61ac…` equals `FROZEN_SPEC_SHA256` in both test files; every frozen file is LF and `.gitattributes` pins it. The three module hashes match the spec and smallcap-thrust-lab's pins, with no commit touching them since `fa7a836`. The fixture is deterministic and carries no market data; regeneration is byte-identical. The committed drill genuinely bites: all thirteen named mutations are rejected and the reference passes; the exact-threshold plants (220 of 400, 360 of 400) and the multiplication-first formula are correct and the division-first mutant is caught at 55.0. The 20-defined-sessions-below rule, the NaN break, the burn-in refusal and the non-session refusal are correctly specified and tested. `composite_with_members` is pinned to `compute_composite` by frame equality, which also catches a memory off-by-one. The cluster rule's known cases are right (63 days joins, 67 splits; dates verified). The month and year boundary cases exist. The one-session lag through `conditional_table` is correct and the unlagged mutant is caught. Count matching per horizon on complete windows is the right instrument (BAR WITH NO EVENT COUNT, 2026-09-03). Monte Carlo p with the +1 convention, the tie rule and `max(p_win, p_med)` are correct; Holm's step-down is correctly specified and its four known cases are right. The verdict mapping is exhaustive and exclusive over the status space and no outcome can be chosen after the fact; PROPOSE_CONDITIONAL's re-measure clause and the 2031-01 re-read are pre-committed. The SEEN table is complete as far as the ledger shows (deGraaf and 20-day high match nothing; the only other 10-day breadth reading is the gold-miner family already cited); the Step 0 guard counts (98 fresh to 2026-09-01; 46 at ≥3 in 41 clusters to 2026-07-31; last 2025-05-05) match ledger rows 198 and 203 exactly, and the [490, 510] and 1,290 panel guards sit around the cutover row's 498/500/507 and 1,301. Every register id cited in §3 resolves; the PENDING placeholder form matches the gold-drivers precedent and `check_register.py`'s vocabulary. No Norgate value and no NDR figure beyond 55.0 and 90.0 enters a tracked file; nothing writes the live cache, `data/signals.json`, `docs/` or `template.html`. Every weekday claim is correct (2026-10-01 Thu; 1990-12-28, 2017-12-29 Fri; 2018-01-02 Tue; 2026-10-05 Mon; 2026-10-06 Tue; 2026-10-08 Thu; 2026-10-03 Sat). No contractions, no American spellings; figures in the prose carry their basis.

---

## Lens verdicts

- **Quant PM:** not ready to tag. The member rules are well guarded, but the null-and-power layer has a test that no correct engine can pass, a sampler whose literal reading stops the run, a placement range narrower than the treatment's, and a keyed effect the two-leg statistic cannot detect at any plausible count.
- **CIO:** the consequences are fixed before the result and nothing deploys on anything but PASS, which is the right side to fail on; but as frozen the study cannot say "no", every verdict will read `_THIN`, and the REDUNDANT predicate differs between the prediction and the gate. The owner should decide the keyed effect and the G2 predicate now, pre-results.
- **CPM:** §10–§11 present FAIL and NO_INFORMATION as live outcomes they are not; §8 names a comparator the gate does not use; §6 claims a D1 guard G2 does not provide; §3's coverage figures are already stale. A careful reader would be misled on the first three.

Catches log: seven lines appended to `C:\Users\phuaz\.claude\red-team-catches.md` (two new classes on the power layer, one on the sampler, one on the placement range, one on the predicate collision, two instances). Nothing else was written anywhere.
