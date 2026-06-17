@echo off
:: Basketball (WNBA + NBA) daily data ingest — runs at 7:00 AM before the
:: GitHub Actions pipeline. Ingests yesterday's box scores (for prop settlement +
:: rolling features) and refreshes season-to-date team stats (for game model
:: features) for BOTH leagues. All steps use nba_api (stats.nba.com), which
:: blocks GitHub Actions datacenter IPs, so they run locally instead.
::
:: NOTE: the Task Scheduler job "\BettingModel\WNBA Daily Ingest" points at this
:: file. It now covers NBA too (one job for both basketball leagues). WNBA games
:: run May–Oct, NBA games Oct–Jun, so each league's steps no-op cleanly off-season.

cd /d "C:\Users\Matth\GitHub Repos\Bet Repo\betting-model"

echo [%date% %time%] Starting basketball daily ingest >> logs\wnba_ingest.log

:: ── WNBA ──────────────────────────────────────────────────────────────────────
C:\Python314\python.exe -m run_pipeline --step wnba-game-log >> logs\wnba_ingest.log 2>&1
if %errorlevel% neq 0 (
    echo [%date% %time%] ERROR: wnba-game-log failed >> logs\wnba_ingest.log
) else (
    echo [%date% %time%] OK: wnba-game-log >> logs\wnba_ingest.log
)

C:\Python314\python.exe -m run_pipeline --step wnba_stats >> logs\wnba_ingest.log 2>&1
if %errorlevel% neq 0 (
    echo [%date% %time%] ERROR: wnba_stats failed >> logs\wnba_ingest.log
) else (
    echo [%date% %time%] OK: wnba_stats >> logs\wnba_ingest.log
)

:: ── NBA ───────────────────────────────────────────────────────────────────────
C:\Python314\python.exe -m run_pipeline --step nba-game-log >> logs\wnba_ingest.log 2>&1
if %errorlevel% neq 0 (
    echo [%date% %time%] ERROR: nba-game-log failed >> logs\wnba_ingest.log
) else (
    echo [%date% %time%] OK: nba-game-log >> logs\wnba_ingest.log
)

C:\Python314\python.exe -m run_pipeline --step nba_stats >> logs\wnba_ingest.log 2>&1
if %errorlevel% neq 0 (
    echo [%date% %time%] ERROR: nba_stats failed >> logs\wnba_ingest.log
) else (
    echo [%date% %time%] OK: nba_stats >> logs\wnba_ingest.log
)

echo [%date% %time%] Basketball ingest complete >> logs\wnba_ingest.log
