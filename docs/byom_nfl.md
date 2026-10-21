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

## Prop facts

`byom_prop_facts` is one standard prop at the DraftKings line at game
start: the last DraftKings snapshot at or before kickoff. Two points
on that snapshot are one fact. A quote with no line is dropped before
the rank, so a later capture with no point does not replace a line
beside it. The later `created_at` (captured_at) wins, then the higher
`prop_id`, then the line text.
`player_prop_odds` is the source, from `2023-09-01`
(`PROP_HISTORY_START_DATE`). Seasons before 2023 are refused. The same
`line_basis` label is stored on the row. The line is not a filter. A
market key ending in `_alternate` is an alt ladder and is not built.
There is no price column and no unit column. A rebuild deletes that
game's prop rows in the same transaction, then inserts the rows this
pass produced.

The stat is `nfl_player_game_log`. `log_status` says which rule fired:

| status | meaning |
|---|---|
| `logged` | one log row matches the normalised name; `actual` is that stat |
| `non_participant` | the game's log has rows and this name is not among them. The player did not play, or the row never landed. `actual` and both results stay NULL. The row is not in the record, the success stats, or the totals |
| `missing_log` | the game has a score and the log has zero rows. Results stay NULL. A missing file is not a loss and is not in the record |
| `unplayed` | no final score. The line is kept. Results stay NULL |
| `ambiguous` | two log rows normalise to the same name and the quote's team does not pick exactly one. No guess. Results stay NULL |

A quote with no posted line is not a fact. The backtest skips it. It is
not graded. Anytime TD is the exception only when the feed omits the
number on a Yes/No market: that posted bet is 0.5. A null line on any
other market is skipped.

Anytime TD is `rushing_tds + receiving_tds`. Passing TDs are
`player_pass_tds`. A return or defensive touchdown is not in the weekly
file, so a score that is only a return grades as a loss when the player
logged a row. A player who did not play is not an Anytime TD 'No' win.
The name match does not expand nicknames, so Josh and Joshua do not meet,
and that miss stays ungraded.

`log_status` is on the facts schema. The job `byom_prop_facts` defaults
`apply` to false. `jobs/declared_jobs.json` lists `byom-nfl-prop-facts`
with `enabled` false and `apply` false, so a merge does not enqueue a
writer. The builder reads one game at a time.
