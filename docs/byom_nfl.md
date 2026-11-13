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
`byom_game_facts` in `tracking/job_queue.py`. `apply` defaults to false.
A missing sport is NFL. `byom-nba-game-facts` is declared with enabled
false and apply false, so a merge does not backfill production. No NFL
game-facts row is declared.

The builder is `byom/load.py` (`scripts/byom_game_facts.py` for a dry run).
NFL seasons before `DK_HISTORY_START_SEASON` (2020) are refused. NBA
seasons before `NBA_DK_HISTORY_START_SEASON` (2021) are refused.
Measured 2026-10-29: the first NBA season with a DraftKings h2h,
spread, or total is 2021. For each game it takes the latest DraftKings
spread and the latest DraftKings total whose snapshot is at or before
game start.
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
`byom-nfl-refresh` stays off. The worker job `byom_game_facts` accepts
NFL and NBA. A missing sport is NFL. An NFL season before 2020 is
still refused. An NBA season before 2021 is refused. The NBA
declarations stay enabled false. Enable `byom-nba-game-facts` before
`byom-nba-prop-facts`.

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
is left out. Phase A prop filters (player line, DraftKings price band,
team spread, game total, month, weekday, kickoff slot, opponent, player)
are in `byom_prop_phase_a_filters_2026_10_29.sql`, applied by hand.
Stake and kelly are still rejected. Each
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


## Official pick and the bet list

Matt, 2026-11-04. A builder bet becomes official at the first DraftKings
quote at or before kickoff where the leg fits the model's rules and the
side has an American price. That line and price are the bet of record. A
later move does not change it. The closing line above is still graded
beside it. The rules that move with the quote are the role (favorite,
underdog, pick'em, from the DraftKings home spread in force) and the
line, price, team-spread and game-total bands. The builder stores one
candidate per pre-kickoff snapshot where those numbers changed
(`context_at_lock`, `team_spread`, `game_total` on `byom_official_legs`).
`byom_legs` locks the earliest candidate that fits the role and the bands
together. A line band is the prop line. A team spread of +3 to +7 is
`min_team_spread` / `max_team_spread`. A price band is that quote's
American price. A total has no role. A role with no spread in force yet
matches only a model that asks for any role. Props use the role of the
player's team. The code is `byom/official.py`. NFL only.

Rows stored before `byom_official_lock_bands_2026_11_04.sql` have
`context_at_lock` false. A band on those rows still reads the closing
line, so the lock does not move until the official rebuild rewrites the
candidates. The closing timing's bands are still the closing line.

Staking is the main models' `stake_for`: 1u to win, risk capped at 3u
(`byom_risk_units`, `byom_win_units`). A -400 win is +0.75u. A -400 loss
is -3u. This applies to both timings and to `byom_backtest`.

The RPCs are in `data/migrations/byom_official_legs_2026_11_04.sql`, which
is in `ACTIVE_MIGRATIONS`:

| RPC | Returns |
|---|---|
| `byom_record(season, filters)` | timing (official or close), market, bets, wins, losses, pushes, ties, units, risked, skipped |
| `byom_bets(season, filters, timing)` | the counted bets, newest first, with `byom_leg_label`; 500 per call, and `total_bets` |
| `byom_backtest(season, filters)` | unchanged columns; the closing rows of `byom_record` |

Line, price, spread, and total bands are part of the official lock
search (`data/migrations/byom_official_lock_bands_2026_11_04.sql`). The
app leads with the official record when that record has a bet. An empty
official record beside a closing record leads with the close, so the
card is not 0-0 while the rebuild is unfinished or for a season the
official build does not cover. The closing line stays under the official
headline. The bets are on `ByomBetsScreen`.

## Trend filters (2026-11-05)

Matt, 2026-11-05: game bets needed more inputs ("if you don't select prime
time it's basically every bet"), and he approved three steps.

**The More filters sheet on game bets.** Moneyline, spread (puck line) and
total get the sheet props already had: price, month, weekday, NFL kickoff
slot, opponent. A game bet has no player line and no player; a total has
no team, so it has no opponent and no team's last game. NFL game bets get
Rest (short week, 6 days or fewer; off a bye, 12 or more), the same cuts the
NFL prop chips use. NBA and NHL keep their back-to-back and 2+ days chips.

**Five server keys** (`byom_trend_filters_2026_11_05.sql`, graded by
`byom_legs` and kept by `byom_save_model`):

| Key | Values | Meaning |
|---|---|---|
| `line_move` | toward / against / none | The DraftKings line since the first stored quote (the opener), on this side. A spread moves toward home when the home number falls; a total or a prop toward the over when it rises; a moneyline toward a side when its implied chance rises. |
| `prev_result` | won / lost | The bet team's previous game this season. |
| `prev_ats` | covered / not_covered | That game against its closing spread. |
| `prev_total` | over / under | Both teams' previous games went over (or both under). |
| `division_game` | true / false | Both teams in one division that season (`byom_team_division`). |

**No lookahead.** On the official line, `line_move` is the move up to the
quote that became the bet, so the lock is the first quote where the move
fits; the close is never used for an official bet. A last-game filter is not
known until that game is over: 4 hours after the previous start.
A stored candidate is the line until the next one (a row is written only
on a change), so the lock is the quote still in force at that moment, made
official at that moment; a line that never moved after the previous game is
not dropped (CE review, #1187). The wait is the bet team's previous start
for `prev_result` / `prev_ats`, and both teams' for `prev_total`. On the
closing line both are known at kickoff. A team's first game of a season has
no previous game, so a last-game filter leaves it out. The opener is the
first DraftKings quote stored, not necessarily DraftKings' own open; a move
on a spread, total or prop is the number only, not the price.

**Chips (Matt, 2026-11-05).** The app offers Moved toward and Moved away;
"Didn't move" is dropped, because on the official line the opener has not
moved, so it was nearly every bet. The server still accepts `none`, and a
model saved with it still shows the chip. NBA player props hold one stored
line each before 2026-27 (measured 2026-11-05: 1.00 candidates per prop for
2023-24 to 2025-26, 10.97 for 2026-27), so the Trends tab says line history
starts in 2026-27. NFL props hold about 2.4 per prop for 2023-2025.

**Divisions** are a fixed list in `byom_team_division`: NFL since 2002, NBA
since 2004-05, NHL from 2013-14 with the 2020-21 temporary divisions and the
2021-22 realignment. NHL's UTA code is Arizona through 2023-24 and Utah
after. Codes match `byom_game_facts` (measured 2026-11-05).

**Season breakdown.** Under All seasons the record card is followed by one
row per season (the headline's timing) and "Up in X of Y seasons". Under 50
bets (`BYOM_SMALL_SAMPLE_BETS`, the main models' gate) a note says the record
could be luck.

## Refresh

Since 2026-11-04 the scheduler queues `byom_refresh` with apply true every
day at 10:41 ET (`scheduler.run_byom_nfl_refresh`), after
`nfl_player_game_log` has landed (about 6am ET). The declared
`byom-nfl-refresh` is on, as a one-time catch-up.

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
stake or kelly filter is rejected. Since
`byom_save_filters_2026_11_05.sql` (ACTIVE_MIGRATIONS, 2026-11-05) the
save keeps all 22 keys the preview grades (`byom_legs`): before it, the
live save kept 9 and silently dropped the Phase A keys (price, player,
opponents, months, weekdays, kick slots, team spread, game total) and
refused `min_line` / `max_line`. An unknown key is refused by name, a
null value is not stored, and the values are checked by the preview's
parser, because the save grades through `byom_backtest` before it
writes. An allowlisted key in the wrong case is rejected. An NHL model
cannot be a pick'em. There is no recommended stake.

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
is unchanged. NBA props are a separate sport on the same builder.
`docs/byom_nba.md`.

`mobile/src/lib/byom.ts` types the rows and calls `byom_backtest`,
`byom_save_model`, `byom_list_models`, and `byom_delete_model`.
`useByomBacktest` and `useByomModels` still drop a slower response.
`byomFilters` rejects a mixed-case or unknown key.
