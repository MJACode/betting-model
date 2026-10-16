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
grade. Results are 1u-to-win units, with no risk cap and no stake. Pushes
and ties are stored.

`data/migrations/byom_facts_schema_2026_10_16.sql` is registered for the
worker and was not applied by the change that added it. The tables are
empty until a later change builds them. That change does not belong in
`jobs/declared_jobs.json`: a merge of the schema must not backfill
production.
