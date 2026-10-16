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
`byom_game_facts` in `tracking/job_queue.py`. `apply` defaults to false,
and the job is not in `jobs/declared_jobs.json`, so a merge does not
backfill production.

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
grade lock and at the near lock, inside that 30-minute lag. The first
capture is kept. A rebuild grades from those rows, so 2026 stays the
same after the non-DraftKings quotes are pruned. A spread or total whose
DraftKings number has moved replaces that market's shop. The grade still
uses `BEST_LINE_BOOKMAKERS`; the other books are stored so the price can
be recomputed. `data/migrations/byom_lock_shop_2026_10_16.sql` is
registered for the worker and was not applied by the change that added
it. The windows are UNCONFIRMED and are not check constraints.
