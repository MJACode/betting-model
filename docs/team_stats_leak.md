# The historical team-stats leak

**Every MLB model's historical performance is inflated, and 2026 is the only
honest season we have.** Found 2026-09-03 while diagnosing why
`mlb_f5_moneyline` collapsed in 2026. It did not collapse. It is the first
season the model was measured without help.

---

## What the table actually contains

`mlb_team_stats` is the source of the team-quality features every MLB model
reads — `d_ops`, `d_wrc_plus`, `d_woba`, `d_team_era`, `home_win_pct`,
`d_run_differential` and the rest. `_team_stats_before(team, season, as_of_date)`
takes the newest row at or before the game date.

| season | rows | distinct `as_of_date` | avg `games_played` |
|---|---|---|---|
| 2023 | 60 | **2** (`2023-01-01`, `2023-10-01`) | **162** |
| 2024 | 60 | **2** (`2024-01-01`, `2024-10-01`) | **162** |
| 2025 | 61 | **2** | 198 |
| 2026 | **4,230** | **141** (daily) | 77 |

A historical season has two snapshots and both carry **the completed season**.
LAD in 2024:

| as_of_date | games_played | ops | wrc_plus | wins |
|---|---|---|---|---|
| **2024-01-01** | **162** | **0.781** | **109.0** | 0 |
| 2024-10-01 | 162 | 0.781 | 109.0 | 97 |

The January 1st row holds the full 2024 season's batting line. So every 2024
training game picks up `as_of_date <= game_date` → the `2024-01-01` row → **the
final numbers for the season that game belongs to.**

The model is told how each team performed across the whole season, then asked to
predict a game inside it. That is a target leak, and it is §7's "leakage hides
in the latest snapshot" in a table nobody had checked.

2026 has none of this: 141 daily snapshots, `games_played` averaging 77, genuine
as-of-date. **2026 is the only season featurised honestly.**

---

## What it did to the numbers

`scripts/walk_forward_eval.py`, fixed params, train ≤T and test T+1:

| model | 2022 | 2023 | 2024 | 2025 | **2026** |
|---|---|---|---|---|---|
| `mlb_f5_moneyline` | 0.636 | 0.628 | 0.640 | 0.633 | **0.560** |
| `mlb_moneyline` | 0.613 | 0.605 | 0.605 | 0.615 | **0.529** |
| `mlb_over_under` | 0.547 | 0.573 | 0.574 | 0.569 | **0.508** |
| `mlb_runline` | 0.613 | 0.631 | 0.525 | 0.636 | **0.568** |

(AUC. `mlb_runline` 2024 is an outlier low inside the leaked block — the pattern
is strong, not perfect.)

**Every model drops in the one honest season.** `mlb_over_under` lands on 0.508,
which is a coin flip. The honest range across all four is roughly **0.51-0.57**,
not the 0.60-0.64 the leaked seasons advertise.

This also explains the registry. `mlb_f5_moneyline`'s active build reports
`holdout_accuracy 0.6415` on a 2024 holdout that was inside its own training
seasons — two separate reasons the same number is not real.

---

## Eight features are dead as well

The same backfill left the counting stats empty. Measured on the built feature
matrices, 2024 vs 2026:

| feature | sd 2024 | sd 2026 | mean 2024/25 | mean 2026 |
|---|---|---|---|---|
| `home_win_pct` | 0.000 | 0.080 | 0.000 | 0.501 |
| `away_win_pct` | 0.000 | 0.077 | 0.000 | 0.498 |
| `d_run_differential` | 0.000 | 76.103 | 0.000 | 1.104 |
| `home_injury_adj` | 0.000 | 53.042 | 0.000 | 27.235 |
| `away_injury_adj` | 0.000 | 58.348 | 0.000 | 28.082 |
| `home_starter_out` | 0.000 | 0.000 | 0.000 | **1.000** |
| `away_starter_out` | 0.000 | 0.031 | 0.000 | 0.999 |
| `home_has_returnee` / `away_has_returnee` | 0.000 | 0.000 | 0.000 | 0.000 |

Constant in every training season, so **XGBoost never splits on them** — a
constant offers no gain. Eight of 25 features are inert: the model has no notion
of team record or run differential at all. They cannot explain the 2026 drop
(they are ignored in training, so their inference values change nothing), but
they are eight features of capacity spent on nothing.

`injuries` starts **2026-04-05**; there is no historical injury data to build
those from. `home_starter_out = 1.0` for every 2026 game is separately wrong —
a flag that is always true is not a flag.

---

## What to do about it

**Do not retrain against the current table.** More trials on leaked features
produce a better-fitting model of a leak.

1. **Rebuild `mlb_team_stats` as a real as-of-date series.** `games` covers
   2009-2026, so wins, losses and run differential are reconstructable exactly,
   by date, for every historical season. That alone revives three dead features
   and removes the leak from the counting stats.
2. **Rate stats as-of-date** (`ops`, `wrc_plus`, `woba`) need cumulative
   aggregation from `player_game_log` (481k rows). Harder, and the bigger prize:
   these are the features the models actually split on.
3. **Re-measure after the rebuild** with `walk_forward_eval`. If the leaked
   seasons fall to ~0.55 the models were never better than they are now; if they
   stay high, the signal is real and was merely mis-served.
4. **Only then decide about `mlb_f5_moneyline`.** Pausing it today on a number
   produced by a leaked comparison would be the same mistake in the other
   direction.

## It is four sports, not one

`count(DISTINCT as_of_date)` per season, checked 2026-09-03:

| table | historical seasons | 2026 | verdict |
|---|---|---|---|
| `mlb_team_stats` | 2 | 141 | **leaked** |
| `nba_team_stats` | 1 | 31 | **leaked** |
| `nhl_team_stats` | 1 | 143 | **leaked** |
| `wnba_team_stats` | 1 | 70 | **leaked** |
| `ncaaf_team_stats` | **14-16 weekly, every season** | 14 | **clean** |

Each leaked row holds its OWN season's final numbers, verified against `games`
rather than assumed — NBA BOS 2023 stored 57 wins at `2022-09-01` against an
actual 57 that season and 51 the season before; WNBA CON 2025 stored 11 against
an actual 11 and a prior-season 28; NHL BOS 2025 stored 33 against 33.

**NCAAF is clean and is the template**: 14-16 weekly snapshots per season for
every season, which is exactly the shape the other four need.

The rebuild is scoped in `docs/team_stats_rebuild_scope.md`.


---

## The same leak, one table deeper, and it matters more

Found 2026-09-03 after the team-stats rebuild moved `mlb_f5_moneyline` not at
all. **`mlb_pitcher_stats` holds each pitcher's SEASON-FINAL ERA on every start.**

| season | pitcher-seasons (10+ starts) | constant ERA | varying | avg distinct values |
|---|---|---|---|---|
| 2019-2025 | ~180 each | essentially all | 0-4 | **1.0** |
| 2026 | 160 | **0** | **160** | **17.2** |

Aaron Nola's 33 rows for 2024 all read 3.57 — his final 2024 ERA. `era_last3` is
constant too, so "last three starts" is also a season-final number.

This is the leak that carries the model: `d_starter_era_last3` (0.213) and
`d_starter_era` (0.186) are the two most important features in
`mlb_f5_moneyline`, **40% of total importance between them**. It is why
rebuilding the team tables improved `mlb_moneyline` (2026 AUC 0.529 to 0.566)
and left `mlb_f5_moneyline` untouched (0.560 to 0.562).

It is exactly reconstructable from `player_game_log`, which carries
`innings_pitched`, `p_earned_runs`, `p_strikeouts`, `p_walks`, `p_hits_allowed`
and `p_home_runs` per start: **era, k9, bb9, hr9, whip and every last-3 variant
are exact**, and only `xfip` needs a league constant. That is the next rebuild.
