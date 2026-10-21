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

## Backtest

`byom_backtest(season, filters)` is `SECURITY INVOKER` plpgsql. Filter
values are locals. `season` NULL is the current NFL season only: the
year the season starts, in `America/New_York`, and January through
August stay on the previous year's label. A caller can pass an older
season. Filters are side (home/away), role (favorite/underdog/pickem),
weeks, rest days, primetime, and market type. A leg missing that datum
is left out. There is no spread-size, price, or line filter. Each
market row counts wins, losses, pushes, and ties. There is no unit
column and no stake.
Game markets include both sides. Prop markets include the over and the
under. An empty filter object is the whole season. It is not a model
record, and the UI must not present that unfiltered result as one.
The in-function 3s timeout does not apply. Postgres arms
`statement_timeout` when the top-level statement starts, so the
function-level SET does not bound the call. The role timeouts govern:
anon 3s, authenticated 8s. The season cutoff is the same rule as
`byom/season.py`: month >= 9 keeps the calendar year, otherwise the
label is the previous year.
`data/migrations/byom_backtest_rpc_2026_10_16.sql` is registered
and was not applied. The function is in `RPC_ANON_CALLABLE`. It reads
the facts tables, not `picks`.


## Refresh

`byom/refresh.py` reports freshness without reading odds. The due set
is the current season only: games dated from yesterday through seven
days ahead, plus a past game with no fact row, a past fact row that
still has a null score, and a past game that has facts but no prop
facts and has not been scanned for props yet. A null line is not
unfinished. Scores and `built_at` come from one read. After `apply`,
the prop pass stamps `props_scanned_at` on each game it read, including
a game that produced no prop row, and that game leaves the due set.
A game `assemble_game` will not build is not scheduled as missing.
A game today or inside that forward window with no fact row counts as
missing. A row in that window whose `built_at` is more than 24 hours
before the report clock is stale.
Those two day counts and the 24 hour age are the refresh's own bounds.

`apply` false returns the report and writes nothing. `apply` true
rebuilds only the due games, game facts and prop facts, and commits
once. The line on that rebuild is the last DraftKings snapshot at or
before kickoff. Rest days still use the whole season's schedule.
Quotes for a game outside the due set are not fetched.

`byom_refresh` defaults `apply` to false. `jobs/declared_jobs.json`
lists `byom-nfl-refresh` with `enabled` false and `apply` false, so a
merge does not enqueue it. A declared job is enqueued once. This file
does not add a schedule. It does not write `picks`.

## Saved models

`byom_models` and `byom_model_snapshots` are keyed to `auth.uid()`. A
user sees their own rows. The cap is 25 models. Saving an existing name
updates that model and appends a snapshot of `byom_backtest` at that
moment. The snapshot totals and the per-market summary are that one
read. The snapshot stores wins, losses, pushes, and ties. A
stake, kelly, price, line, or spread-size filter is rejected. An
allowlisted key in the wrong case is rejected. There
is no recommended stake.

The RPCs are `SECURITY DEFINER`: `byom_save_model`, `byom_list_models`,
`byom_delete_model`. The user id comes from `auth.uid()`, not from an
argument. The tables are not granted to anon or authenticated. The
functions are granted to authenticated only. They are listed in
`RPC_AFTER_SIGN_IN` and are not in `RPC_ANON_CALLABLE`, so the grant
sweep does not name them.

`data/migrations/byom_saved_models_2026_10_16.sql` is **not** in
`ACTIVE_MIGRATIONS`. The worker will not apply it. It stays unused
until sign-in is turned on. That switch is Matt's. This change does
not set it.

## Mobile data layer

`mobile/src/lib/byom.ts` types the backtest rows and the saved models,
and calls `byom_backtest`, `byom_save_model`, `byom_list_models`, and
`byom_delete_model`. `useByomBacktest` and `useByomModels` load those
calls. A slower backtest response does not replace a newer one.
`byomFilters` rejects a mixed-case or unknown key. No screen imports
them. An empty filter is the whole season and must not be shown as a
saved model record. There is no recommended stake. `package.json` is
unchanged. Sign-in is unchanged.
