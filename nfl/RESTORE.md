# NFL model bundle: restore instructions

Contains everything that cost credits or is not trivially re-fetchable.
Last rebuilt 2026-08-15 (Open-Meteo validation + clean opener re-test).

## What is here
- `data/odds_cache/`  : every Odds API snapshot, keyed md5(date|regions|markets).
                        ~45,000 credits of spend. Reruns hit cache = 0 credits.
- `data/weather_cache/`: Open-Meteo ERA5 + issued-forecast pulls. Free but slow
                        to refetch (~30 min). Keyed by endpoint/stadium/span.
- `data/credit_ledger.json` : spend/quota ledger
- `data/processed/`   : derived odds tables, feature matrix, backtest results,
                        `dev_long.parquet` (1.4M spread quotes with BOTH side
                        prices), `book_screen.csv`
- `data/games.csv`, `snap_*.parquet`, `sbr_nfl.json`
- `data_ingest/`, `models/`, `features/`, `scripts/` : all code
- `nfl_game_lines_model_system.md` : the canonical document

## NOT here (free to re-fetch, large)
- `data/raw/pbp_20XX.parquet` : nflverse play-by-play, ~120MB
  refetch: https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{YEAR}.parquet

## Restore
```
mkdir -p ~/nfl_model && cd ~/nfl_model
tar xzf nfl_model_bundle.tar.gz --strip-components=1
pip install lightgbm scikit-learn pyarrow requests pandas numpy scipy --break-system-packages
```
Do NOT install nfl_data_py; it fails to build. Pull nflverse assets directly.

## Live: the weekly wind card
```
export THE_ODDS_API_KEY=...
python scripts/weekly_wind_card.py --days 2            # 1 credit
python scripts/weekly_wind_card.py --dry-run           # 0 credits, weather only
```
Requires egress to `api.open-meteo.com`. Some sandboxes block that host with a
proxy 403 while allowing the archive and historical hosts; if so, run the card
from a machine with open egress. Full weekly routine: see "Runbook: Wind Totals"
at the end of the main document.

## Reproduce the analysis (all zero Odds API credits)
```
python scripts/screen_books.py --rebuild --write       # book integrity screen
python scripts/validate_wind_forecast.py               # every wind number
python scripts/backtest_opener.py --placebo draftkings # opener, correctly priced
python scripts/replay_wind_card.py --season 2024 --week 12 --lead 3 --settle
```

## KNOWN DATA DEFECT (critical)
Four books carry home/away sign flips in the Odds API spreads feed:
`betanysports`, `betsson`, `nordicbet`, `tipico_de`.
Detect via: book_line ~= -pinnacle_line while |pinnacle_line| >= 3.
betanysports flips 16.2% of quotes; dev sd 5.13 vs 0.34-0.68 for clean books.
Re-derived from scratch across all 40 books on 2026-08-15: the list is exactly
these four, no fifth offender. EXCLUDE THEM BEFORE ANY LINE-SHOPPING ANALYSIS.
Re-run `scripts/screen_books.py` whenever a new book appears in the feed.

## OPEN-METEO GOTCHAS
- `wind_speed_10m_previous_dayN` (issued forecasts) is NULL before 2024-01-18.
  The plain `wind_speed_10m` series on the historical endpoint is near-analysis
  and leaks if used as a forecast.
- `previous-runs-api.open-meteo.com` is not reachable; do not build against it.
- Open-Meteo wind and nflverse `wind` correlate only 0.688. A threshold of 12 in
  one is not a threshold of 12 in the other. Use the constants in
  `data_ingest/weather.py`.
