@echo off
REM Daily local collector for the Morocco Inflation Tracker (DAILY index).
REM Registered in Windows Task Scheduler to run once a day: it scrapes today's
REM prices for the whole catalog, rebuilds the DAILY index, refreshes the
REM official series, and commits + pushes the data.

cd /d "C:\Users\lenovo\Documents\inflation-project"
echo ==== %DATE% %TIME% ==== >> collect.log

REM 1. sync with GitHub so the push is a fast-forward
git pull --rebase origin main >> collect.log 2>&1

REM 2. scrape today's prices, rebuild the daily index, refresh the official series
"venv\Scripts\python.exe" scripts\collect_daily.py >> collect.log 2>&1
"venv\Scripts\python.exe" scripts\build_daily_index.py >> collect.log 2>&1
"venv\Scripts\python.exe" scripts\build_inflation_index.py >> collect.log 2>&1

REM 3. commit + push only if something changed
git add data\prix_actuels.csv data\indice_quotidien.csv data\indice_inflation.csv data\official\cpi_maroc_faostat.csv data\aswak_catalog.csv
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "chore: releve quotidien (%DATE%)" >> collect.log 2>&1
  git push origin main >> collect.log 2>&1
  echo pushed >> collect.log
) else (
  echo no change >> collect.log
)
