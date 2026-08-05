@echo off
rem Weekly vendor gauge guard (approved 2026-08-05) - see
rem reviews/2026-08-05_gauge-vendor-crosscheck.md Proposal section.
rem Alert-only cross-check of the self-computed breadth panel against
rem Norgate vendor counts; all output stays in git-ignored data_local\.
rem Scheduled Sat 08:00 SGT as "breadth-thrust-signal weekly vendor guard".
cd /d C:\dev\breadth-thrust-signal
if not exist data_local mkdir data_local
echo ---- %date% %time% ---- >> data_local\guard.log
python scripts\weekly_vendor_guard.py >> data_local\guard.log 2>&1
