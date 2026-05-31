@echo off
:: WNBA daily data ingest — runs at 7:00 AM before the 8:00 AM GitHub Actions pipeline.
:: Ingests yesterday's WNBA box scores (for prop settlement + rolling features)
:: and refreshes season-to-date team stats (for game model features).
:: Both steps use nba_api (stats.nba.com) which blocks GitHub Actions IPs,
:: so they run locally instead.

cd /d "C:\Users\Matth\GitHub Repos\Bet Repo\betting-model"

echo [%date% %time%] Starting WNBA daily ingest >> logs\wnba_ingest.log

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

echo [%date% %time%] WNBA ingest complete >> logs\wnba_ingest.log
