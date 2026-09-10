@echo off
REM Daily local collector for the Morocco Inflation Tracker.
REM Portable: cd to the repo root (parent of this script), no hard-coded path.
REM Registered in Windows Task Scheduler to run once a day.

cd /d "%~dp0.."
echo ==== %DATE% %TIME% ==== >> collect.log

REM 1. sync with GitHub so the push is a fast-forward
git pull --rebase origin main >> collect.log 2>&1

REM 2. collect today's prices — abort loudly if it fails (empty day = worst case)
"venv\Scripts\python.exe" scripts\collect_daily.py >> collect.log 2>&1
if errorlevel 1 (
  echo ECHEC COLLECTE -- jour non ajoute, rien committe >> collect.log
  exit /b 1
)

REM 3. rebuild the indices
"venv\Scripts\python.exe" scripts\build_daily_index.py >> collect.log 2>&1
"venv\Scripts\python.exe" scripts\build_inflation_index.py >> collect.log 2>&1

REM 4. commit + push only if something changed
git add data\prix_actuels.csv data\indice_quotidien.csv data\serie_logement.csv data\indice_inflation.csv data\official\cpi_maroc_faostat.csv data\aswak_catalog.csv
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "chore: releve quotidien (%DATE%)" >> collect.log 2>&1
  git push origin main >> collect.log 2>&1
  echo pushed >> collect.log
) else (
  echo no change >> collect.log
)
