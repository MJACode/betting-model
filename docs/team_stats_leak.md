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

---

## Phase 2: the pitcher table, rebuilt

Done 2026-09-03, `data/pitcher_stats_rebuild.py`. **27,278 rows across 2019-2025
and 972 pitchers**, built from `player_game_log`. 2026 was refused by the
script's own guard and is untouched.

The leak is gone, measured with the query that found it — pitcher-seasons of ten
or more starts:

| season | pitcher-seasons | constant ERA — before | constant ERA — after | avg distinct ERAs after |
|---|---|---|---|---|
| 2019 | 170 | essentially all | **0** | 22.5 |
| 2021 | 170 | essentially all | **0** | 20.0 |
| 2022 | 162 | essentially all | **0** | 21.2 |
| 2023 | 162 | essentially all | **0** | 20.5 |
| 2024 | 151 | essentially all | **0** | 20.7 |
| 2025 | 148 | essentially all | **0** | 19.6 |
| 2026 | 158 | 0 (already correct) | 0 | 16.8 |

Historical seasons now carry MORE variation than 2026, which is what a genuine
per-start series looks like over a full season versus a partial one.

### The source was validated before it was trusted

`player_game_log` is not obviously reliable, so it was checked against the leak
itself — which, for all its faults, IS each pitcher's true season-final ERA.
Rebuilding a whole season from pgl and comparing:

| season | pitchers | correlation | MAE | mean bias | pgl game coverage |
|---|---|---|---|---|---|
| 2023 | 142 | **0.957** | 0.196 | +0.002 | 87% |
| 2024 | 132 | **0.920** | 0.234 | +0.025 | 81% |
| 2025 | 117 | **0.720** | 0.432 | +0.179 | 74% |

The agreement degrades exactly in step with coverage, which is what a faithful
source with a hole in it looks like — rather than a source that is simply wrong.

### Innings are in baseball notation, and it matters

`innings_pitched` 5.2 means five and TWO THIRDS. Only .0/.1/.2 fractions occur,
across all 135,010 rows. Summing the column directly is wrong arithmetic and
inflates every ERA — visible above as the mean bias, which was +0.025 on a naive
sum and falls to +0.002 once converted. Everything works in OUTS and converts
once, in `outs_from_ip`.

### `era_last3` deliberately replicates a weaker definition

It is NOT an ERA over the last three starts. The daily ingest computes
`AVG(era)` over the last three stored rows — the mean of three SEASON-TO-DATE
rates, a smoothed near-duplicate of `era` — and will keep doing so tomorrow.

Training on the truer rolling statistic would measure a system nobody deployed,
and would silently redefine ~21% of `mlb_f5_moneyline`'s importance. That is a
model update under §1b, not a leak repair, so it is queued as a decision in
`docs/followups.md` rather than taken here.

The old table happened to be consistent in the same way for the wrong reason:
`era_last3` was the season-final constant, so it equalled `era` exactly. The
model's reliance on it was always effectively reliance on `era`.

### What it cost

Coverage is the honest cost. `player_game_log` holds no rows for any game
involving the White Sox or the Nationals before 2026 — the opponent's starter
included — so those games get no row and drop from training:

| season | 2019-2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|
| both starters found | 86-89% | 81.7% | 75.0% | 93.3% |

The old rows were deleted for those games rather than left standing. A matrix
that is honest where pgl reaches and leaked where it does not is worse than one
with holes, because nothing marks which rows are which. Backfilling pgl from the
MLB StatsAPI is queued in `docs/followups.md`.

Backup: `mlb_pitcher_stats_pre_rebuild_20260903` (35,547 rows, REVOKEd from
`anon` and `authenticated`).

### What it did to the numbers — the answer Phase 2 existed to get

`scripts/walk_forward_eval.py`, fixed params, train <= T and test T+1, across
2019-2026 (the default `train_seasons` stops at 2024, so the seasons must be
passed explicitly or the run never reaches the only honest one):

| model | 2021 | 2022 | 2023 | 2024 | 2025 | **2026** | mean |
|---|---|---|---|---|---|---|---|
| `mlb_f5_moneyline` — before either rebuild | — | 0.636 | 0.628 | 0.640 | 0.633 | **0.560** | — |
| `mlb_f5_moneyline` — after | 0.534 | 0.579 | 0.546 | 0.582 | 0.572 | **0.537** | **0.558** |
| `mlb_moneyline` — before either rebuild | — | 0.613 | 0.605 | 0.605 | 0.615 | **0.529** | — |
| `mlb_moneyline` — after | 0.547 | 0.563 | 0.570 | 0.538 | 0.576 | **0.559** | **0.559** |
| `mlb_over_under` — before either rebuild | — | 0.547 | 0.573 | 0.574 | 0.569 | **0.508** | — |
| `mlb_over_under` — after | 0.514 | 0.516 | 0.505 | 0.519 | 0.502 | **0.486** | **0.507** |
| `mlb_runline` — before either rebuild | — | 0.613 | 0.631 | 0.525 | 0.636 | **0.568** | — |
| `mlb_runline` — after | 0.513 | 0.572 | 0.579 | 0.460 | 0.618 | **0.588** | **0.555** |

**The leaked seasons collapsed to the honest season's level.** Before the
rebuild the shape was unmistakable — four seasons at 0.63-0.64 and the one
honestly-featurised season at 0.560. After it, all six folds sit in a single
band of 0.534-0.582 with no leaked/honest split left in the data.

`mlb_moneyline` shows the same collapse from the other direction, and it is the
cleaner demonstration of the two: its leaked seasons fell from ~0.61 to ~0.56
while its ONE honest season ROSE, 0.529 before either rebuild to 0.566 after
the team tables and 0.559 now. Both models converge on the same place from
opposite ends — a real signal worth about **0.55-0.56**, which the leak was
inflating to 0.61-0.64 in every season it touched.

The other two models split the verdict rather than repeating it, which is why
the scope insisted on measuring all four:

* **`mlb_over_under` has no signal at all.** Every fold lands between 0.486 and
  0.519, mean **0.507**, and 2026 comes in at **0.486 — below a coin flip**.
  Zero of six folds clear 0.55. Its pre-rebuild 0.55-0.57 was the leak in its
  entirety; there is nothing underneath it.
* **`mlb_runline` is unstable, not good.** Mean 0.555 hides a swing from
  **0.460 to 0.618**, and its base rate moves from 0.364 to 0.495 across the
  same folds — the target mix itself is changing between seasons. This script's
  own doctrine applies: what matters is not the best fold but whether the folds
  AGREE, and these do not. The mean is not a number to act on.

This is outcome (a) of the two the scope named: *the models never had the edge
their history advertised.* `mlb_f5_moneyline`'s honest mean is **0.558 across
six folds**, not the 0.6415 `holdout_accuracy` its registry row still reports
from a 2024 holdout that sat inside its own training seasons.

**It is not a coverage artifact, which was the obvious objection.** Counting
games where BOTH starters carry a non-null ERA, before the rebuild against
after:

| | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | total |
|---|---|---|---|---|---|---|---|---|
| before | 2,469 | 1,628 | 2,785 | 2,911 | 2,559 | 2,337 | 2,139 | 16,828 |
| after | 2,585 | 1,699 | 2,593 | 2,710 | 2,437 | 2,142 | 1,954 | 16,120 |

A **4.2%** net reduction — and 2019 and 2020 actually GAINED coverage, because
the old table had holes of its own. A 4% change in training rows does not move
AUC by 0.08. The drop is the leak leaving.

And the rows that DID leave argue the same way. Each fold's test set shrank
5-10% (2024: 1,475 -> 1,332), and what drops out is disproportionately EARLY-
SEASON starts — a pitcher's first outings, which now carry no prior line and
so no ERA. Those are precisely the rows where the old table's leak was at its
maximum: a season-final ERA stamped on a first start is a pure statement about
the future, with no legitimate signal mixed in. Part of the 0.63-0.64 the
leaked seasons advertised lived in exactly the rows that no longer exist.

**The "before" row predates BOTH rebuilds** — f5 was never re-walked per season
between Phase 1 and Phase 2, because Phase 1 moved its aggregate barely at all
(0.560 -> 0.562 on 2026).
