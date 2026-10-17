# Build Your Own Model — NFL facts

The member's own rules read `byom_game_facts` (and, later, `byom_prop_facts`).
These rows are not picks. Nothing here writes `picks`, posts to Discord, or
changes a live model.

`canonical_key` is `season_WW_away_home` (`2024_01_BAL_KC`).

| Store | Key |
|---|---|
| `games.game_id` | `NFL_` + the key. `games.week` is NULL on every NFL season; week is parsed from the key |
| `nfl_odds_history.game_id` | the bare key for 2020–2025; `NFL_` + the key for 2026. `lead_hours` is NULL on the 2026 rows, so lead is `commence_time - snapshot_at` |
| `odds.game_id` | `NFL_` + the key |

DraftKings rows in `nfl_odds_history` start at the 2020 season (measured:
`min(season)` where `bookmaker = 'draftkings'` is 2020). The 2015–2019
schedule in `games` is not built.

`line_basis` is `DraftKings line at game start`: the last DraftKings
snapshot at or before kickoff. That label is stored on the row and is
what a screen shows. The line is not a filter and not a reason to skip
a game. A moneyline result is the score only. There is no price column
and no unit column. Pushes and ties are stored.

`data/migrations/byom_facts_schema_2026_10_16.sql` is registered for the
worker and was not applied by the change that added it. The tables stay
empty until someone runs the builder with `--apply`. That job is
`byom_game_facts` in `tracking/job_queue.py`. `apply` defaults to false,
and the job is not in `jobs/declared_jobs.json`, so a merge does not
backfill production.

The builder is `byom/load.py` (`scripts/byom_game_facts.py` for a dry run).
`byom/constants.py` holds `LOCK_WINDOW_HOURS` (120) and
`NEAR_LOCK_WINDOW_HOURS` (24). Both are UNCONFIRMED. Seasons before
`DK_HISTORY_START_SEASON` (2020) are refused. The grade is DraftKings'
own price on the lock snapshot. `grade_*_book` is `draftkings`. Another
book's price is not the grade. History is preferred over `odds` when
both have a lock for that market. `line_source` records which table.
Closing prices are stored and are not the grade. The builder reads one
game at a time, DraftKings inside the lock window. Other books are not
read here. The lock-shop change is what stores them. A season is not
loaded in one fetch.
`byom_game_facts_units_2026_10_16.sql` renames the unit columns. It is
registered and was not applied.
