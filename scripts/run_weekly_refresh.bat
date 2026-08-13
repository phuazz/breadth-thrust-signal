@echo off
rem Weekly guarded refresh (owner decision 2026-08-13: the dashboard is a live
rem meter). Runs the full fetch -> rebuild -> guard -> test -> commit+push
rem chain in scripts\weekly_refresh.py; any guard failure publishes nothing.
rem Scheduled Sat 07:00 SGT as "breadth-thrust-signal weekly refresh" -
rem before the 08:00 vendor gauge guard, so that guard cross-checks the
rem freshly rebuilt panel. Heartbeat watched by C:\dev\scripts\fleet_watch.json.
rem After a SUCCESSFUL publish, the Norgate parallel run (scope memo
rem 2026-08-13) soaks the cutover candidate: alert-only, writes data_local\ only.
cd /d C:\dev\breadth-thrust-signal
if not exist data_local mkdir data_local
echo ---- %date% %time% ---- >> data_local\refresh.log
python scripts\weekly_refresh.py >> data_local\refresh.log 2>&1
if %errorlevel% EQU 0 (
  echo ---- %date% %time% ---- >> data_local\parallel_run.log
  python scripts\parallel_run.py >> data_local\parallel_run.log 2>&1
)
