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
a game. A moneyline result is the score only. Pushes and ties are stored.

Grading uses that line. The spread price and the total price are the
American price on that same quote. When that quote has no American
price, the price is the most recent pre-start DraftKings quote at the
same point that has one, and if none does, the most recent pre-start
priced quote for that side. A quote after kickoff is not used. Another
book is never the price, and neither is a constant such as −110. A
moneyline has no point, so each side is the last pre-start DraftKings
quote that has that side's price. A tie on the snapshot breaks on
`created_at`, then the higher id, then the line text. A stored price
is American: a whole number with absolute value at least 100. A
decimal such as 1.91 is not a price, so the fallback looks for an
American one. The columns are `dk_ml_home_price`, `dk_ml_away_price`,
`dk_spread_home_price`, `dk_spread_away_price`, `dk_total_over_price`,
and `dk_total_under_price`. They were added by
`data/migrations/byom_dk_start_price_2026_10_23.sql`, applied in
production on 2026-10-23 at 8:10 AM CT (version 20261023131032). That
file stays as applied. The fallback rule and the new `skipped` count
are `data/migrations/byom_dk_price_fallback_2026_10_23.sql`, applied in
production as version `20261023225630`. That file is **not** in
`ACTIVE_MIGRATIONS`. The worker will not re-run it, and the file stays
as applied. The backfill runs after that function. `week` may be null:
NFL week still comes from the id, and the other sports have no week. `is_primetime`
is the NFL rule only (Thursday, Monday, or 7pm ET or later). Any other
sport stores null.

`data/migrations/byom_facts_schema_2026_10_16.sql` is registered for the
worker and was not applied by the change that added it. The tables stay
empty until someone runs the builder with `--apply`. That job is
`byom_game_facts` in `tracking/job_queue.py`. `apply` defaults to false,
and the job is not in `jobs/declared_jobs.json`, so a merge does not
backfill production.

The builder is `byom/load.py` (`scripts/byom_game_facts.py` for a dry run).
NFL seasons before `DK_HISTORY_START_SEASON` (2020) are refused. Other
sports are not. For each game it takes the latest DraftKings spread and
the latest DraftKings total whose snapshot is at or before game start.
NFL reads `nfl_odds_history` and `odds` together. Every sport reads
`odds`, matched on `games.game_id`. Measured 2026-10-23 on two NFL
games in each season 2020–2026: DraftKings h2h, spread, and total rows
were on that id, and the bare key had zero. `nfl_odds_history` still
matches the bare key and the `NFL_` key. The spread and the total
take their price from the graded quote when it has an American price,
then from the closest earlier DraftKings price at that point, then
from the most recent priced DraftKings quote for that side. A
moneyline side uses the last pre-start quote that has that side. A
price that is not American is not stored. `line_basis` is `DraftKings line at game start` on every built
row, including a row whose spread, total, and prices are null. Moneyline
is graded from the score. The builder reads one game at a time. Other
books are not read. A season is not loaded in one fetch.

The script defaults to NFL and writes nothing without `--apply`.
`--sport all --apply` is the backfill across every sport in `games`.
It runs after `byom_dk_price_fallback_2026_10_23.sql`, in the same
window, so the stored prices follow the fallback rule. It was not run.
The printed JSON includes `same_point`, `cross_point`, and
`line_no_price`: how many spread and total sides were priced from an
earlier quote at the graded point, how many from an earlier quote at
another point, and how many graded lines still have no American price.
Each of those four sides is one count. Moneyline sides are not in the
three counts. A queued `byom_game_facts` job with `sport` null builds
NFL and still does not write unless `apply` is true.
`byom-nfl-refresh` stays off. The worker job `byom_game_facts` still
accepts NFL only and is still undeclared.

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
`over_price` and `under_price` are the American prices on the same
DraftKings quote that supplied the line. A side that quote does not
price is null. An earlier quote is not used. Another book is not used.
There is no constant price and no unit column on the row. A rebuild
deletes that game's prop rows in the same transaction, then inserts
the rows this pass produced. The columns are
`data/migrations/byom_prop_facts_dk_prices_2026_10_28.sql`, applied
by hand. It is not in `ACTIVE_MIGRATIONS`.

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

`log_status` is on the facts schema. The job `byom_prop_facts` still
defaults `apply` to false when the argument is omitted.
`jobs/declared_jobs.json` lists `byom-nfl-prop-facts` with `enabled`
true and `apply` true, and with no season. `sync_declared_jobs`
enqueues that one backfill: every NFL season from 2023 whose
`game_date` is on or after `2023-09-01`. Apply the price-column
migration before that job runs. A failed row keeps dedupe key
`byom-nfl-prop-facts`, so a retry needs that row gone. The dry run
is `python -m scripts.byom_prop_facts`. The write is the same command
with `--apply`. One season is `--season 2024`. The printed JSON has
one entry per season: `facts`, `written`, and `canonical_keys`. The
builder reads one game at a time.

## Backtest

`byom_backtest(season, filters)` is `SECURITY INVOKER` plpgsql. Filter
values are locals. `season` NULL is the current NFL season only: the
year the season starts, in `America/New_York`, and January through
August stay on the previous year's label. A caller can pass an older
season. Filters are side (home/away on a moneyline or spread, over/under
on a total, and the player's team on a prop), role (favorite/underdog/pickem),
weeks, rest days, primetime, and market type. A leg missing that datum
is left out. There is no spread-size, price, or line filter. Each
market row counts wins, losses, pushes, and ties, plus `units` and
`skipped`. Staking is 1u to win at the stored DraftKings price. A win
is +1. A loss is `-abs(price)/100` on minus odds and `-100/price` on
plus odds. A push and a tie are 0 and stay in the push or tie count.
`skipped` counts a played bet with no DraftKings line at all: no
spread point, no total, or no American moneyline price. It also counts
a played bet that has a DraftKings line but no American price anywhere
before kickoff. Those bets stay out of wins, losses, pushes, ties, and
units. There is no screen for that count. A line whose quote had no
price is priced from the fallback above and is in the record when that
fallback finds an American price. An unplayed game stays out of the
record and out of `skipped`. A graded prop leg uses `over_price` or
`under_price` on that side. The American check is the same one the
game legs use. A graded side with no American price is left out of
wins, losses, pushes, ties, and units, and counted in `skipped`. An
ungraded prop (null result) stays out of the record and out of
`skipped`. That function is
`data/migrations/byom_backtest_prop_dk_prices_2026_10_28.sql`. It is
not in `ACTIVE_MIGRATIONS`. Matt applies it by hand after the price
columns. It keeps `byom_backtest_v1` and the return columns. It keeps
the total-leg side labels from `byom_total_side_2026_10_25.sql`.
`data/migrations/byom_prop_side_2026_10_28.sql` replaces that function
and `byom_save_model`. `prop_side` `over` keeps the over leg and
`under` keeps the under leg. A missing `prop_side` still counts both.
The player's team stays on `side`. One of the twelve NFL prop markets
with no `prop_side` is refused on save. A filter with no prop market
drops `prop_side`. It is not in `ACTIVE_MIGRATIONS`. Apply it by hand
after the price backtest and after `byom_total_side_2026_10_25.sql`.
Do not re-apply the older backtest files after it. Unknown filter
keys are rejected. The field names `market`, `bets`, `wins`,
`losses`, `pushes`, and `ties` are unchanged.
Moneyline and spread legs are home and away. Prop markets include the
over and the under. An empty filter object is the whole season. It is not a model
record, and the UI must not present that unfiltered result as one.
The in-function 3s timeout does not apply. Postgres arms
`statement_timeout` when the top-level statement starts, so the
function-level SET does not bound the call. The role timeouts govern:
anon 3s, authenticated 8s. The season cutoff is the same rule as
`byom/season.py`: month >= 9 keeps the calendar year, otherwise the
label is the previous year.
`data/migrations/byom_backtest_rpc_2026_10_16.sql` is registered. It
returns early when the function body contains `byom_backtest_v1`.
Production `byom_backtest` is the applied fallback
`byom_dk_price_fallback_2026_10_23.sql` (version `20261023225630`).
`byom_dk_start_price_2026_10_23.sql` (version `20261023131032`) was not
edited. That applied fallback still labels a total leg with a null
side, so a saved over or under matches no total leg until the next
file is applied. `data/migrations/byom_total_side_2026_10_25.sql`
replaces `byom_backtest` and labels those legs `over` and `under`, so
a side filter keeps that one leg. It keeps `byom_backtest_v1` in the
body, so the registered file's skip still holds. It also replaces
`byom_save_model` with the one-market side refusals. It is **not** in
`ACTIVE_MIGRATIONS`. Matt applies it by hand.
`data/migrations/byom_backtest_prop_dk_prices_2026_10_28.sql` is the
body after that. It keeps the total-leg labels and stakes each prop
side at `over_price` or `under_price`. Apply the price columns first.
Do not re-apply `byom_total_side_2026_10_25.sql` after it. The
function is in `RPC_ANON_CALLABLE`. It reads the facts tables, not
`picks`.


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

`data/migrations/byom_saved_models_2026_10_16.sql` is applied in
production as version `20261023222927`. It is **not** in
`ACTIVE_MIGRATIONS`. The worker will not re-run it. Do not edit that
file. The one-market side refusals are in
`data/migrations/byom_total_side_2026_10_25.sql`, which replaces
`byom_save_model` and is also not in `ACTIVE_MIGRATIONS`. Matt applies
that file by hand.

## Mobile

The Models tab’s second segment is My models. Signed out, it does not
call the list and it does not say the list is empty. Signed in, it
lists that user’s NFL rows from `byom_list_models`. Rank and the builder preview
call `byom_backtest` (`fetchByomScopedBacktest`): this season is one
call with season null, and all seasons is one call per season from
2020 through the current NFL season. The create flow is three steps
(bet type, side, name). Step 1 is the three game bets and the twelve
NFL props, each its own choice: Passing yards, Passing TDs, Pass
attempts, Completions, Rushing yards, Rush attempts, Receiving yards,
Receptions, Rush + rec yards, Anytime TD, Tackles + assists, Sacks.
Save stays off until a moneyline or spread has a
team or a favorite, underdog, or pick’em, and until an over/under is
Over or Under. A prop stays off until Over or Under is set. Anytime
TD stays off until Yes, which is the over leg. The under is not a
choice on that market. The player’s team is Any, Home, or Away. Any
does not need a favorite. Team Any with a favorite or underdog set can be saved
on a moneyline or a spread.
A missing side is not stored as both sides. The preview does not grade
that missing choice. Editing a saved model is one screen. A rename
saves the new name first and removes the old row only when that save
wrote a different id. At 25 models a new name is refused and the
original stays. A name that already belongs to another model asks,
and the prompt says that model will be overwritten. One model’s
backtest can fail without clearing the rest of the list. An empty
filter is not graded. The backtest’s left-out count is not parsed.
Price and line filters are not on screen. There is no position chip,
no line-range filter, and no EV. A saved game market shows units. A
prop shows units only when the filter is exactly that one market and
Over or Under is set. Anytime TD shows units only for Yes, which is
over. A mix, two props, a prop with no side, and an empty market list
do not.
There is no recommended stake. `package.json` is unchanged. Sign-in
is unchanged. NBA props are not in this builder.

`mobile/src/lib/byom.ts` types the rows and calls `byom_backtest`,
`byom_save_model`, `byom_list_models`, and `byom_delete_model`.
`useByomBacktest` and `useByomModels` still drop a slower response.
`byomFilters` rejects a mixed-case or unknown key.
