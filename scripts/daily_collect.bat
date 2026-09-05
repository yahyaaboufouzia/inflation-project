@echo off
REM Daily local collector for the Morocco Inflation Tracker.
REM Registered in Windows Task Scheduler to run once a day: it appends today's
REM real retail prices, refreshes the index, and commits + pushes the data.

cd /d "C:\Users\lenovo\Documents\inflation-project"
echo ==== %DATE% %TIME% ==== >> collect.log

REM 1. sync with GitHub so the push is a fast-forward
git pull --rebase origin main >> collect.log 2>&1

REM 2. append today's real prices, then rebuild the inflation index
"venv\Scripts\python.exe" scripts\append_today.py >> collect.log 2>&1
"venv\Scripts\python.exe" scripts\build_inflation_index.py >> collect.log 2>&1

REM 3. commit + push only if something changed
git add data\prix_actuels.csv data\indice_inflation.csv data\official\cpi_maroc_worldbank.csv
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "chore: mise a jour quotidienne des prix (%DATE%)" >> collect.log 2>&1
  git push origin main >> collect.log 2>&1
  echo pushed >> collect.log
) else (
  echo no change >> collect.log
)
