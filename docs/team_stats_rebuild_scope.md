# Scope: rebuilding the team-stats tables as real as-of-date series

The leak is described in `docs/team_stats_leak.md`. This is what fixing it
involves, what is exactly recoverable from data already held, what is only
approximable, and what cannot be recovered at all.

---

## 1. Blast radius, measured

`count(DISTINCT as_of_date)` per season:

| table | historical seasons | 2026 | verdict |
|---|---|---|---|
| `mlb_team_stats` | **2** (`01-01`, `10-01`) | 141 daily | **leaked** |
| `nba_team_stats` | **1** (prior-year `09-01`) | 31 | **leaked** |
| `nhl_team_stats` | **1** (prior-year `10-01`) | 143 | **leaked** |
| `wnba_team_stats` | **1** (`01-01`) | 70 | **leaked** |
| `ncaaf_team_stats` | **14-16 weekly, every season** | 14 | **clean** |

Each leaked row carries its OWN season's final numbers, verified against the
`games` table rather than assumed:

| sport | row | stored | that season's actual | prior season |
|---|---|---|---|---|
| NBA | BOS 2023 @ `2022-09-01` | 82 GP, **57 W** | **57** | 51 |
| NBA | MIL 2024 @ `2023-09-01` | 82 GP, **49 W** | **49** | 58 |
| WNBA | CON 2025 @ `2025-01-01` | 44 GP, **11 W** | **11** | 28 |
| NHL | BOS 2025 @ `2024-10-01` | 82 GP, **33 W** | **33** | 53 |
| MLB | LAD 2024 @ `2024-01-01` | **162 GP**, .781 OPS | full season | — |

**NCAAF is the template.** The right shape already exists in this repo, which
is the strongest argument that the rebuild is a known quantity rather than a
research project.

---

## 2. What is exactly recoverable

**Tier 1 — counting stats, from `games` alone.** 87,147 rows covering
2009-2026, with final scores and `home_win`. Cumulative per team per date:

* `games_played`, `wins`, `losses`
* `run_differential` / `point_differential` / `goal_differential`
* home/away splits, last-N form

Exact, every sport, every season we have games for. **This alone revives
`home_win_pct`, `away_win_pct` and `d_run_differential`** — three of the eight
dead features — and removes the leak from every counting stat.

**Tier 2 — MLB rate stats, from `player_game_log`.** 481k rows, 2019-2026,
~1,800-2,400 games per season, with the raw components:

| stat | recoverable? | from |
|---|---|---|
| `team_era` | **exact** | `p_earned_runs`, `innings_pitched` |
| `team_whip` | **exact** | `p_walks`, `p_hits_allowed`, `innings_pitched` |
| `iso` | **exact** | `total_bases`, `hits`, `at_bats` |
| `team_fip` | near-exact | `p_home_runs`, `p_walks`, `p_strikeouts`, IP (no HBP) |
| `ops` | **approximate** | no HBP or SF columns, so OBP is slightly low |
| `k_pct`, `bb_pct` | **approximate** | PA approximated as AB + BB |
| `babip` | **approximate** | no SF |
| `woba` | **no** | needs event weights and HBP |
| `wrc_plus` | **no** | needs league and park context |

`wrc_plus` and `woba` are the awkward ones: they are among the model's most-used
features (`d_wrc_plus` and `d_woba` rank 4th and 7th by importance) and they are
the two that cannot be rebuilt from what we hold.

---

## 3. What cannot be recovered

* **NHL rate stats.** `nhl_skater_stats` has **0 rows** and `nhl_goalie_stats`
  has 221. There is no per-game NHL player data to aggregate. NHL tier 1 is
  fine; NHL tier 2 needs an external source or those features get dropped.
* **MLB `wrc_plus` / `woba`** as above — external, or substitute a computable
  proxy (wOBA-approx from the components we do have) and accept it is a
  different feature.
* **Historical injuries.** `injuries` starts 2026-04-05. Nothing to rebuild
  from; those four features stay dead for training unless a source is bought.

**A team-coverage gap to fix on the way:** `player_game_log` shows 28 distinct
teams for most MLB seasons and 26 for 2025, against 30 real teams. Some team
labels are not mapping. That must be resolved before any aggregate is trusted,
or a rebuilt table quietly omits two clubs.

---

## 4. Sequencing

**Phase 0 — freeze.** No MLB/NBA/NHL/WNBA retrains against the current tables.
More Optuna trials on leaked features fit the leak better. (`ncaaf` is unaffected.)

**Phase 1 — tier 1 rebuild, all four sports.** A backfill job that walks each
season by date and writes cumulative counting stats. Deterministic, verifiable
against `games`, no external calls. Runs on the worker via `job_queue`.

**Phase 2 — re-measure, and this is the decision point.** `walk_forward_eval`
on all four MLB models plus the NBA/NHL/WNBA equivalents. Two outcomes:

* leaked seasons fall to ≈ the 2026 level → **the models never had an edge**,
  and the honest baseline is AUC 0.51-0.57. That is a strategy question, not a
  modelling one.
* they stay high → the signal is real and was being mis-served; proceed.

**Phase 3 — tier 2 MLB rate stats**, only if Phase 2 justifies it. This is the
larger and less certain piece, and it is where `wrc_plus`/`woba` force a choice.

**Phase 4 — NHL rate stats**, external source or drop.

---

## 5. The test that should have caught this

Cheap, permanent, and it fails loudly on exactly this class of bug:

> **No stats row may claim more `games_played` than that team had actually
> played by its own `as_of_date`**, computed from the `games` table.

`BOS 2023 @ 2022-09-01, games_played 82` fails it instantly — the season had not
started. A companion assertion that every season has more than a handful of
distinct `as_of_date` values would have flagged all four tables on day one.

Both belong in the suite before the rebuild lands, so the rebuild is verified by
something other than the person who wrote it.

---

## 6. Decisions this needs

1. **Phase 1 now, or wait for Phase 2's answer?** Phase 1 is a day of
   deterministic work and unblocks the only honest measurement we can make.
2. **`wrc_plus` / `woba`:** external source, computed proxy, or drop the
   features? They are top-10 by importance, so this is not a small call.
3. **NHL:** external rate-stat source, or run NHL on counting stats only?
4. **Historical injuries:** buy, or accept those four features stay dead?
