@echo off
rem Weekly guarded refresh (owner decision 2026-08-13: the dashboard is a live
rem meter). Runs the full fetch -> rebuild -> guard -> test -> commit+push
rem chain in scripts\weekly_refresh.py; any guard failure publishes nothing.
rem Scheduled Sat 07:00 SGT as "breadth-thrust-signal weekly refresh" -
rem before the 08:00 vendor gauge guard, so that guard cross-checks the
rem freshly rebuilt panel. Heartbeat watched by C:\dev\scripts\fleet_watch.json.
rem
rem CUT OVER 2026-09-02 (owner decision FLIP, on parallel runs CLEAN 2026-08-22,
rem 2026-08-27 and 2026-08-29): the live meter builds on the Norgate daily
rem point-in-time layer (--provider norgate). Step 1 is the depth gate (NDU
rem readiness and age, $SPX reach, delisted-archive floor) in place of the CSP1
rem roster sync, and the output guards pin the provider tag and the 1990-12-28
rem window start. The CSP1+Yahoo path stays as the flagged fallback: pass
rem --provider csp1 to use it (its survivorship banner returns if it ever
rem governs). norgate is also the CLI default since 2026-09-02; the flag below
rem is explicit on purpose and a test pins it.
rem
rem The Norgate parallel run (scripts\parallel_run.py) is RETIRED from this
rem wrapper. Its job was to soak the cutover candidate against the deployed
rem CSP1 build; post-cutover the deployed build IS the Norgate layer, so the
rem comparison would test the candidate against itself and read CLEAN by
rem construction. The script now refuses a same-layer comparison; re-arm it
rem here only for a future cross-layer cutover.
cd /d C:\dev\breadth-thrust-signal
if not exist data_local mkdir data_local
echo ---- %date% %time% ---- >> data_local\refresh.log
python scripts\weekly_refresh.py --provider norgate >> data_local\refresh.log 2>&1
exit /b %errorlevel%
