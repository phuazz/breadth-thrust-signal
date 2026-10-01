# WS10 FIXTURE — planted panel and expected values

Synthetic, deterministic, no market data, no random numbers. Regenerate with
`python tests/make_ws10_fixture.py`; `tests/test_ws10_contract.py` compares the engine with
`tests/fixtures/ws10/expected.json`; `tests/test_ws10_mutants.py` proves the committed wrong engine
fails these expectations while the reference passes.

Panel sha256 `2c3c92d40d6c6c20e01a8fbbcb610c0bc5b559870f8f59924156a2af83482389`; 572 sessions 2019-01-02 to
2021-03-11, 400 names; first data_ok session 2019-12-19
(index 251). Episodes are documented in the generator's docstring.

| Candidate | first defined | fresh events | daily fire sessions |
|---|---|---|---|
| S-D3 | 2019-01-29 | 2020-04-07, 2020-08-25 | 189 |
| S-D2 | 2019-01-15 | 2020-12-02, 2021-02-10 | 27 |

| Session | date | S-D3 share | S-D2 share |
|---|---|---|---|
| 70 | 2019-04-10 | 60.0 | 60.0 |
| 251 | 2019-12-19 | 0.0 | 0.0 |
| 310 | 2020-03-11 | 5.0 | 25.0 |
| 327 | 2020-04-03 | 50.0 | 60.0 |
| 328 | 2020-04-06 | 50.0 | 60.0 |
| 329 | 2020-04-07 | 55.0 | 60.0 |
| 331 | 2020-04-09 | 60.0 | 60.0 |
| 360 | 2020-05-20 | 0.0 | 60.0 |
| 369 | 2020-06-02 | 60.0 | 60.0 |
| 400 | 2020-07-15 | 0.0 | 60.0 |
| 428 | 2020-08-24 | 0.0 | 60.0 |
| 429 | 2020-08-25 | 60.0 | 60.0 |
| 470 | 2020-10-21 | 85.0 | 85.0 |
| 478 | 2020-11-02 | 85.0 | 85.0 |
| 479 | 2020-11-03 | 95.0 | 10.0 |
| 480 | 2020-11-04 | 95.0 | 10.0 |
| 481 | 2020-11-05 | 10.0 | 10.0 |
| 490 | 2020-11-18 | 0.0 | 0.0 |
| 500 | 2020-12-02 | 95.0 | 95.0 |
| 508 | 2020-12-14 | 95.0 | 95.0 |
| 509 | 2020-12-15 | 95.0 | 0.0 |
| 519 | 2020-12-29 | 0.0 | 0.0 |
| 520 | 2020-12-30 | 95.0 | 95.0 |
| 529 | 2021-01-12 | 95.0 | 0.0 |
| 549 | 2021-02-09 | 0.0 | 0.0 |
| 550 | 2021-02-10 | 90.0 | 90.0 |
| 560 | 2021-02-24 | 90.0 | 0.0 |

H-M on the planted panel (fresh events at the threshold, data_ok sessions only):

- ge2: before ['2020-10-12', '2020-12-02', '2020-12-10']; after ['2020-06-04', '2020-12-02', '2020-12-10']; ADDED ['2020-06-04']
- ge3: before ['2020-12-02', '2020-12-10']; after ['2020-12-02', '2020-12-10']; ADDED []
- dimension booleans True (all sessions), before {'d1': 57, 'd2': 42, 'd3': 32, 'd4': 10} and after {'d1': 57, 'd2': 42, 'd3': 189, 'd4': 10}: the OR pinned directly, because the 60-session memory can hide a dimension replaced by its candidate

Redundancy shares (per cent, window 5 sessions): {'S-D3': {'own': 0.0, 'd1': 50.0, 'd4': 0.0}, 'S-D2': {'own': 50.0, 'd1': 0.0, 'd4': 50.0}}

Member fresh fires: {'zweig': 0, 'ad_ratio_deemer': 0, 'mcclellan': 3, 'pct_above_50dma': 1, 'nhnl_ratio': 2, 'net_new_highs': 3, 'up_volume': 1}

Calendar boundaries, 21 sessions on (fixture calendar): {'2019-12-31': '2020-01-29', '2020-02-28': '2020-03-30'}
