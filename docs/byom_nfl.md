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
Seasons before `DK_HISTORY_START_SEASON` (2020) are refused. For each
game it takes the latest DraftKings spread and the latest DraftKings
total whose snapshot is at or before kickoff, from `nfl_odds_history`
and `odds` together. That number is the line. `line_basis` is
`DraftKings line at game start` on every built row, including a row
whose spread and total are null. Moneyline is graded from the score
and does not read a price. The builder reads one game at a time.
Other books are not read. A season is not loaded in one fetch.
