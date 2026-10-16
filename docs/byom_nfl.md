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
schedule in `games` is not built. `line_source` names the table the lock
quote came from.

The lock columns hold the first DraftKings pre-game snapshot at or under a
120 hour lead, and a second snapshot at or under 24 hours. **Both numbers
are UNCONFIRMED placeholders.** They are columns the builder fills, not
check constraints. The grade is the 120h DraftKings line at the best price
on that same line. The closing DraftKings price is stored and is not the
grade. Each result stores two unit columns. `*_units_uncapped` is 1u-to-win
with no risk ceiling. `*_units_capped` matches `stake_for`: risk above 3
is cut to 3, and a win is recomputed from that risk. A -400 loss is -4
uncapped and -3 capped. A missing price leaves both NULL. Pushes and ties
are stored. There is no stake column.

`data/migrations/byom_facts_schema_2026_10_16.sql` is registered for the
worker and was not applied by the change that added it. The tables stay
empty until someone runs the builder with `--apply`. That job is
`byom_game_facts` in `tracking/job_queue.py`. `apply` defaults to false.
`jobs/declared_jobs.json` lists it as `byom-nfl-game-facts-shop` with
`enabled` false and `apply` false. `sync_declared_jobs` does not enqueue
`enabled: false`, so a merge does not backfill production. Turning it on
is the owner's call, and `apply` has to be set true in that same change.

The builder is `byom/load.py` (`scripts/byom_game_facts.py` for a dry run).
`byom/constants.py` holds `LOCK_WINDOW_HOURS` (120) and
`NEAR_LOCK_WINDOW_HOURS` (24). Both are UNCONFIRMED. Seasons before
`DK_HISTORY_START_SEASON` (2020) are refused. The grade is the best
American price, per side, among `BEST_LINE_BOOKMAKERS` on DraftKings'
number, from a quote in the 30 minutes up to that lock. A quote on a
different number does not count. History is preferred over `odds` when
both have a lock for that market. `line_source` records which table.
Closing prices are stored and are not the grade. The builder reads one
game at a time: DraftKings inside the lock window, then other books only
inside that game's shop slices. A season is not loaded in one fetch.
`byom_game_facts_units_2026_10_16.sql` renames the unit columns. It is
registered and was not applied.

`byom_lock_shop` stores every book's quote at DraftKings' line at the
grade lock and at the near lock, inside that 30-minute lag, including
Pinnacle. The app does not read it. The migration revokes anon and
authenticated and enables RLS with no policy. The worker owns the table.
The first capture is kept. A rebuild grades from those rows, so 2026
stays the same after the non-DraftKings quotes are pruned. A spread or
total whose DraftKings number has moved replaces that market. h2h has no
number: it is replaced when the stored DraftKings `snapshot_at` is not
the lock being written, or when the stored rows have no DraftKings row.
Another book's timestamp may be earlier inside the lag and is not the
check. The grade still uses `BEST_LINE_BOOKMAKERS`; the other books are
stored so the price can be recomputed.
`data/migrations/byom_lock_shop_2026_10_16.sql` is registered for the
worker and was not applied by the change that added it. The windows are
UNCONFIRMED and are not check constraints.

Once the owner sets the declared job `enabled` and `apply` true, the
cadence is daily, before `prune-odds`. `data/prune_odds.py` deletes
non-DraftKings rows from `odds` and `player_prop_odds` for games before
today, keeping the opener and the close. It does not delete from
`nfl_odds_history`. A lock quote that lives only in `odds` is neither
the opener nor the close. The first apply has to land before
`2026-10-17`, the prune of games dated `2026-10-16`.
`byom.constants.SHOP_FIRST_APPLY_BEFORE` is that date.

## Prop facts

`byom_prop_facts` is one standard prop at the DraftKings lock.
`player_prop_odds` is the source, from `2023-09-01`
(`PROP_HISTORY_START_DATE`). Seasons before 2023 are refused. The lock is
the first DraftKings snapshot at or under `PROP_LOCK_WINDOW_HOURS` (24).
**That window is UNCONFIRMED.** It is not the 120h game lock and it is
not a check constraint. A market key ending in `_alternate` is an alt
ladder and is not built. The grade is the best price at that line among
`BEST_LINE_BOOKMAKERS`. Closing prices are stored and are not the grade.
Each side stores `*_units_uncapped` and `*_units_capped`. There is no
stake column.

The stat is `nfl_player_game_log`. `log_status` says which rule fired:

| status | meaning |
|---|---|
| `logged` | one log row matches the normalised name; `actual` is that stat |
| `non_participant` | the game's log has rows and this name is not among them; `actual` is 0. A player whose row never landed looks the same as a scratch |
| `missing_log` | the game has a score and the log has zero rows. Results stay NULL. A missing file is not a loss |
| `unplayed` | no final score. The line is kept. Results stay NULL |
| `ambiguous` | two log rows normalise to the same name. No guess. Results stay NULL |

Anytime TD is `rushing_tds + receiving_tds`. Passing TDs are
`player_pass_tds`. A return or defensive touchdown is not in the weekly
file, so a score that is only a return grades as a loss. The name match
does not expand nicknames, so Josh and Joshua do not meet.

`byom_prop_facts_units_2026_10_16.sql` adds the labelled unit columns and
`log_status`, and drops `over_units` / `under_units`. It is registered
and was not applied. The job `byom_prop_facts` defaults `apply` to false.
`jobs/declared_jobs.json` lists `byom-nfl-prop-facts` with `enabled`
false and `apply` false, so a merge does not enqueue a writer. The
builder reads one game at a time.

## Backtest

`byom_backtest(season, filters)` is `SECURITY INVOKER` plpgsql. Filter
values are locals. `season` NULL is the current NFL season only: the
year the season starts, in `America/New_York`, and January through
August stay on the previous year's label. A caller can pass an older
season. Filters are side (home/away), role (favorite/underdog/pickem),
weeks, rest days, primetime, and market type. A leg missing that datum
is left out. There is no spread-size, price, or line filter. Each
market row sums `units_uncapped` and `units_capped`. There is no stake.
Game markets include both sides. Prop markets include the over and the
under. `data/migrations/byom_backtest_rpc_2026_10_16.sql` is registered
and was not applied. The function is in `RPC_ANON_CALLABLE`. It reads
the facts tables, not `picks`.

## Refresh

`byom/refresh.py` reports freshness without reading odds. The due set
is the current season only: games dated from yesterday through seven
days ahead, plus current-season games already played that have no
`byom_game_facts` row. A row in that window whose `built_at` is more
than 24 hours before the report clock is stale. Those two day counts
and the 24 hour age are the refresh's own bounds. They are not the
lock windows. The 120h and 24h locks stay UNCONFIRMED.

`apply` false returns the report and writes nothing. `apply` true
rebuilds only the due games, game facts and prop facts, and commits
once. Rest days still use the whole season's schedule. Quotes for a
game outside the due set are not fetched.

`byom_refresh` defaults `apply` to false. `jobs/declared_jobs.json`
lists `byom-nfl-refresh` with `enabled` false and `apply` false, so a
merge does not enqueue it. A declared job is enqueued once. This file
does not add a schedule. It does not write `picks`.
