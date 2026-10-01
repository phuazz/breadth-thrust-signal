# WS10 FIXTURE — planted panel and expected values

Synthetic, deterministic, no market data, no random numbers in the panel. Regenerate with
`python tests/make_ws10_fixture.py`; `tests/test_ws10_contract.py` compares the engine with
`tests/fixtures/ws10/expected.json`; `tests/test_ws10_mutants.py` proves the committed wrong engine
fails these expectations while the reference passes.

Panel sha256 `1621c01bff9dc5e5ab8c2aa194e14aa27f01a738467b7fca11251116f8110109`; 572 sessions 2019-01-02 to
2021-03-11, 800 names; first data_ok session 2019-12-19
(index 251); late entrant N798 from
2020-02-26; interior gap N799 on
2020-04-22 to 2020-04-29. Episodes are documented in
the generator's docstring.

| Candidate | first defined | fresh events | daily fire sessions |
|---|---|---|---|
| S-D3 | 2019-01-29 | 2020-04-08, 2020-08-25 | 164 |
| S-D2 | 2019-01-15 | 2020-12-02, 2021-02-10 | 40 |

| Session | date | S-D3 share | S-D2 share |
|---|---|---|---|
| 60 | 2019-03-27 | 95.1188986232791 | 95.1188986232791 |
| 70 | 2019-04-10 | 95.1188986232791 | 95.1188986232791 |
| 134 | 2019-07-09 | 60.07509386733417 | 60.07509386733417 |
| 251 | 2019-12-19 | 0.0 | 0.0 |
| 310 | 2020-03-11 | 5.006257822277847 | 22.5 |
| 315 | 2020-03-18 | 17.521902377972467 | 35.0 |
| 328 | 2020-04-06 | 50.0 | 60.0 |
| 329 | 2020-04-07 | 52.5 | 60.0 |
| 330 | 2020-04-08 | 55.0 | 60.0 |
| 331 | 2020-04-09 | 57.5 | 60.0 |
| 350 | 2020-05-06 | 60.07509386733417 | 60.07509386733417 |
| 360 | 2020-05-20 | 0.0 | 60.0 |
| 369 | 2020-06-02 | 60.0 | 60.0 |
| 400 | 2020-07-15 | 0.0 | 60.0 |
| 428 | 2020-08-24 | 0.0 | 60.0 |
| 429 | 2020-08-25 | 60.0 | 60.0 |
| 470 | 2020-10-21 | 85.0 | 85.0 |
| 478 | 2020-11-02 | 85.0 | 85.0 |
| 479 | 2020-11-03 | 90.0 | 5.0 |
| 480 | 2020-11-04 | 90.0 | 5.0 |
| 481 | 2020-11-05 | 5.0 | 5.0 |
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

- ge2: before ['2020-10-08', '2020-12-02', '2020-12-10']; after ['2020-06-04', '2020-12-02', '2020-12-10']; ADDED ['2020-06-04']; REMOVED ['2020-10-08']
- ge3: before ['2020-12-02', '2020-12-10']; after ['2020-12-02', '2020-12-10']; ADDED []; REMOVED []
- dimension booleans True (all sessions), before {'d1': 88, 'd2': 56, 'd3': 35, 'd4': 25} and after {'d1': 88, 'd2': 56, 'd3': 164, 'd4': 25}: the OR pinned directly, because the 60-session memory can hide a dimension replaced by its candidate
- composite event count over all sessions, before 5 and after 5; >=2 events inside the burn-in (refused): ['2019-03-27']; the frozen event rule and the newly-on near-miss disagree on ['2019-07-09']

Redundancy shares (per cent, window 5 sessions): {'S-D3': {'own': 0.0, 'd1': 50.0, 'd4': 0.0}, 'S-D2': {'own': 50.0, 'd1': 0.0, 'd4': 50.0}}

Member fresh fires: {'zweig': 0, 'ad_ratio_deemer': 0, 'mcclellan': 3, 'pct_above_50dma': 1, 'nhnl_ratio': 2, 'net_new_highs': 3, 'up_volume': 1}

Calendar boundaries, 21 sessions on (fixture calendar): {'2019-12-31': '2020-01-29', '2020-02-28': '2020-03-30'}

Comparator on the deterministic unit path (triangle, 1,200 sessions, 24 events in 12 clusters):

- treatment 3m {'n': 24, 'win_rate': 0.5416666666666666, 'median': 0.030538052208412325}; complete-window events 24
- first three draws, seed key [19901228, 0]: [['2011-03-09', '2011-03-18', '2011-05-24', '2011-06-02', '2011-09-15', '2011-09-26', '2011-12-06', '2011-12-15', '2012-03-02', '2012-03-13', '2012-06-25', '2012-07-04', '2012-10-23', '2012-11-01', '2013-02-13', '2013-02-22', '2013-06-27', '2013-07-08', '2013-09-16', '2013-09-25', '2013-12-03', '2013-12-12', '2014-04-01', '2014-04-10'], ['2011-02-03', '2011-02-14', '2011-07-07', '2011-07-18', '2011-09-21', '2011-09-30', '2012-01-31', '2012-02-09', '2012-04-18', '2012-04-27', '2012-07-05', '2012-07-16', '2012-09-19', '2012-09-28', '2013-01-29', '2013-02-07', '2013-04-12', '2013-04-23', '2013-08-08', '2013-08-19', '2014-01-01', '2014-01-10', '2014-04-23', '2014-05-02'], ['2011-02-21', '2011-03-02', '2011-05-10', '2011-05-19', '2011-09-19', '2011-09-28', '2011-12-09', '2011-12-20', '2012-03-30', '2012-04-10', '2012-07-25', '2012-08-03', '2012-12-17', '2012-12-26', '2013-04-15', '2013-04-24', '2013-06-28', '2013-07-09', '2013-10-15', '2013-10-24', '2014-01-07', '2014-01-16', '2014-04-09', '2014-04-18']]
- null (300 draws) mean win rate 0.496667, mean median -0.000257; p_win 0.318937, p_med 0.259136
- power at +0 / +3 / +10 / +50pp per 3 months (100 draws, alpha/3): {'0.0': 0.0, '3.0': 0.0, '10.0': 0.37, '50.0': 1.0}
- self-drill: {'unconditional_win_rate': 0.5084745762711864, 'unconditional_median': 0.008754625252787473, 'null_mean_win_rate': 0.49666666666666665, 'null_mean_median': -0.00025700606038220553, 'centring_pass': True, 'size_share_at_alpha': 0.04}
- thirty singleton clusters, 2,000 draws: completed 2000, count-matched True
