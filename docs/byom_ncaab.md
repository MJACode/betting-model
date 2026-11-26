# Build Your Own Model — NCAAB game lines

Matt, 2026-11-26: "Do NCAAB next". Scope chosen the same day: game lines
only (moneyline, spread, total), no player props, the same way NHL joined
on 2026-11-05 (`docs/byom_nhl.md`). These rows are not picks. Nothing here
writes `picks`, posts to Discord, or changes a live model.

**Seasons.** The ending year, the NBA split: the season that opened
2026-11-01 is 2027 in `games` (measured 2026-11-26). The first built
season is 2021 (`byom.constants.NCAAB_DK_HISTORY_START_SEASON`): sampling
300 games per season joined to `odds` (DraftKings, h2h/spreads/totals),
2018, 2019 and 2020 had 0 of 300, 2021 had 194 of 300. Roughly 55–65% of
sampled games in each season since have a DraftKings line; a game with
none is still a fact row with a null line, as on every sport.

**Ids.** `canonical_key` is `games.game_id`
(`NCAAB_2026-11-24_ohio_new-mexico-state`). Teams are the stored school
names (`New Mexico State`), so a label reads `New Mexico State -2.5`.

**Server.** `data/migrations/byom_ncaab_2026_11_26.sql` (in
`ACTIVE_MIGRATIONS`) adds `NCAAB` to the sport check and the ending-year
rule in `byom_legs` and `byom_save_model`, patching the live bodies at
anchors. No conference table exists, so `division_game` never matches an
NCAAB game and the app hides the Division filter for NCAAB.

**Builder.** `byom/constants.py`, `season.py`, `load.py`, `official.py`,
`refresh.py`. The backfill is the declared job `byom-ncaab-game-facts`
(every season from 2021, about an hour by the NHL rate). The daily 10:41am
refresh and the per-pass alert rebuild keep the current season current.
Stored odds only: no API credits.

**Alerts.** `byom.alerts.ALERT_SPORTS` is NFL and NCAAB. One `byom_alerts`
job per sport per refresh pass. `byom_save_model` strips the sport from the
stored filters, so the pass puts the model's sport back before calling
`byom_legs` (a missing sport is NFL).

**App.** `ByomSport` includes NCAAB: game bets only, rest chips, "tipoff",
pick'em allowed, no matchup sheet, no Division filter.

Tests: `tests/test_byom_ncaab.py`, `mobile/scripts/verify_byom_alerts.ts`.
