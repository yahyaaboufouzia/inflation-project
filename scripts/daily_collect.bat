@echo off
REM Daily local collector for the Morocco Inflation Tracker.
REM Registered in Windows Task Scheduler to run once a day. It pulls any remote
REM changes, scrapes today's real prices, and commits + pushes the refreshed data.

cd /d "C:\Users\lenovo\Documents\inflation-project"

echo ==== %DATE% %TIME% ==== >> collect.log

REM 1. sync with GitHub first so the push is a fast-forward
git pull --rebase origin main >> collect.log 2>&1

REM 2. collect today's real prices and rebuild the index
"venv\Scripts\python.exe" scripts\run_daily.py >> collect.log 2>&1

REM 3. commit + push only if the data actually changed
git add data\observations.csv data\daily\index.csv
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "chore: local daily data refresh" >> collect.log 2>&1
  git push origin main >> collect.log 2>&1
  echo pushed >> collect.log
) else (
  echo no change >> collect.log
)
