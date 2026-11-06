# Build Your Own Model — NHL game bets

Matt, 2026-11-05: "Yes go". NHL is game bets only: moneyline, puck line
(the `spreads` market), and over/under. There are no player props.

- **Data.** `byom_game_facts` with sport `NHL`, keyed by the game id. The
  first season is 2021 (2020-21, `NHL_DK_HISTORY_START_SEASON`). Measured
  2026-11-05: 2019 and 2020 have no DraftKings line. 2021 has 97%
  moneylines and 80% puck lines. 2022 has 38% puck lines. 2023 on is
  100% for all three markets. The season label is the ending year, the
  same rule as NBA.
- **Lines.** NHL uses the official line (the first DraftKings quote where
  the bet fit the rules) and the closing line, the same as NFL and NBA
  (`docs/byom_nfl.md`). Staking is 1u to win, with risk capped at 3u.
  The moneyline grades on the final score, so overtime and shootouts
  count.
- **Filters.** Home or away. Favorite or underdog, read off the puck
  line; there is no pick'em, because the line is always ±1.5.
  Back-to-back or 2+ days rest. There is no primetime.
- **Jobs.** `byom-nhl-game-facts` is declared on (a one-time backfill
  from 2021). The 10:41 ET scheduler job queues an NHL `byom_refresh`
  every day. Refresh never marks an NHL game due for props
  (`refresh.PROP_SPORTS`).
- **SQL.** `byom_nhl_2026_11_05.sql` (ACTIVE_MIGRATIONS) lets `byom_legs`
  and `byom_save_model` accept NHL.
