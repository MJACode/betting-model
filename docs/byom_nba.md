# Build Your Own Model — NBA props

Same three steps as NFL (`docs/byom_nfl.md`). The sport is the Models
tab. NBA shows the fourteen markets below. NFL is unchanged.

These rows are not picks. Nothing here writes `picks`.

## Markets

One standard DraftKings line per player per game. An alt ladder
(`*_alternate`) is not a fact. No position chip, no line range, no EV.

| Screen | Odds API market | Actual |
|---|---|---|
| Points | `player_points` | `points` |
| Rebounds | `player_rebounds` | `rebounds` |
| Assists | `player_assists` | `assists` |
| Threes | `player_threes` | `fg3_made` |
| PRA | `player_points_rebounds_assists` | points + rebounds + assists |
| Points + Reb | `player_points_rebounds` | points + rebounds |
| Points + Ast | `player_points_assists` | points + assists |
| Reb + Ast | `player_rebounds_assists` | rebounds + assists |
| Blocks | `player_blocks` | `blocks` |
| Steals | `player_steals` | `steals` |
| Blocks + Steals | `player_blocks_steals` | blocks + steals |
| Turnovers | `player_turnovers` | `turnovers` |
| Double-double | `player_double_double` | 1 when two of points, rebounds, assists, steals, blocks are 10 or more, else 0 |
| Triple-double | `player_triple_double` | 1 when three of those are 10 or more, else 0 |

A NULL column counts as 0 once the log row matched. Double-double and
triple-double are Yes only on the screen. Yes is the over leg. The
line is 0.5 when the feed omits the number, the same fill as Anytime
TD. A counting market with no posted line is not a fact.

The log is `nba_player_game_log`. `log_status` is the NFL rule: a name
that is not in a logged game stays ungraded. A missing file is not a
loss. The name match does not expand nicknames.

`over_price` and `under_price` are the American prices on the same
DraftKings quote as the line. A side that quote does not price is
null. Another book is not the price. There is no constant price.
Staking is 1u to win at that price. A loss on minus odds is
`-abs(price)/100`. A loss on plus odds is `-100/price`.

The builder is `byom/prop_load.py` with `sport="NBA"`
(`python -m scripts.byom_prop_facts --sport NBA`). It refuses a season
before 2023 and a game dated before `2023-09-01`. The canonical key is
the game id. `week` is null. That column was `NOT NULL`.
`data/migrations/byom_nba_props_2026_10_29.sql` drops the constraint.
It is not in `ACTIVE_MIGRATIONS`. Apply it by hand, after
`byom_prop_side_2026_10_28.sql`. It also replaces `byom_backtest` and
`byom_save_model`. A missing `sport` is still NFL. `"NBA"` reads NBA
rows. Any other sport is refused. Do not re-apply the older backtest
files after it.

The prop-facts job validator accepts NBA. `byom-nba-prop-facts` is in
`jobs/declared_jobs.json` with enabled false and apply false, so a
merge does not enqueue a backfill. Apply
`data/migrations/byom_nba_props_2026_10_29.sql` by hand first. Matt
confirms that production apply, then CPO sets enabled true and apply
true. Run `byom-nba-game-facts` before it. Rest filters need
`byom_game_facts` for that game. The game-facts job accepts NBA. A
missing sport is still NFL. An NFL season before 2020 is still
refused; NBA is not. `byom-nba-game-facts` is the same off
declaration. Rest chips stay empty until those game facts exist.

## Backtest and save

`byom_backtest` takes `sport` inside the filter object and does not
store it. The app sends that key only for NBA. An NFL call omits it,
so the builder that is already live keeps working until this file is
applied. `"NBA"` with a null season is the ending year in
`America/New_York`: October through December are next year, January
through September stay on the calendar year. That is
`byom.season.current_nba_season`. Passing a season uses that season.

Back-to-back is `min_rest_days` 1 and `max_rest_days` 1. That is one
day since the previous game in `byom_game_facts`, the same rest the
NBA prop frame calls a back-to-back. `2+ days rest` is
`min_rest_days` 2. The two chips are exclusive. A second tap clears
the chip. The board's "up to 3" is not on the screen, because these
two cannot be combined. The player's team is still `side` home or away.
A prop save requires `prop_side` over or under. The screen does not
offer under on a double-double or a triple-double.

`byom_save_model` writes `byom_models.sport` and strips `sport` out of
the stored filters. Units on the screen follow the NFL rule: one prop
market, and `prop_side` over or under. A yes-only market shows units
only for over.

The list on My models, when the Models tab is NBA, is that user's NBA
rows. Other sports still have no builder.
