# NBA play-by-play and on-court lineup segments

**What it is for.** The NBA game-market search (docs/nba_models_2026.md section 6, on the
`nba-game-models` branch) needs player ratings that owe nothing to the betting market:
adjusted plus-minus from lineup segments, a garbage-time flag, and shot-level three-point
luck. This is the data for all three, free, 2018-19 through 2025-26, in Supabase.

Code: `data/ingestors/nba_pbp.py` (download, match, write) and `data/ingestors/nba_stints.py`
(the segment derivation, pure). Tests: `tests/test_nba_pbp.py`, `tests/test_nba_stints.py`.

## Source

- **sportsdataverse's GitHub release of ESPN's feed**, one parquet per season:
  `espn_nba_pbp/play_by_play_<year>.parquet` and
  `espn_nba_player_boxscores/player_box_<year>.parquet`. Free, no key.
- **The file year is our season label (the ending year).** `play_by_play_2019` runs
  2018-10-16 to 2019-06-13 and every row carries `season = 2019`.
- ESPN season types kept: 2 regular season, 3 postseason, 5 play-in. Preseason and the
  All-Star games (teams GIA, USA, STARS, STRIPES) are dropped.
- **Gaps.** The release lacks seven regular-season games: six from late February 2019-20 and
  NBA_2026-01-20_LAC_CHI.
  `--fill-gaps` reads those from ESPN's own free scoreboard and summary endpoints, which the
  release is a flattening of; on a game present in both, the two paths build identical
  segments. Their `nba_pbp_games.source` is `espn_summary_api`.

## Tables (all worker-only, locked down where they are created)

| Table | One row per | Key | What a reader needs to know |
|---|---|---|---|
| `nba_pbp_games` | ESPN game loaded | `espn_game_id` | `game_id` is ours (`NBA_<ET date>_<away>_<home>`); `in_games` says whether `games` holds it (regular season only); `match_method`; ESPN's final; the derivation's repair counts in `diagnostics`. Written in the same commit as the game's plays, so it is the resume ledger. |
| `nba_pbp` | play | `(espn_game_id, play_no)` | `play_no` is the play order used everywhere (period, clock, then ESPN's sequence). `clock_s` = seconds left in the period, `game_s` = game seconds elapsed. `points` is what the play scored; `home_score`/`away_score` are running totals of `points`; ESPN's own columns are kept as `espn_home_score`/`espn_away_score`. `team_side` is H or A. `shot_value` is 1, 2 or 3 on every attempt. `coord_x`/`coord_y` are ESPN's raw shot location in feet, basket at (25, 0), NULL where ESPN has none. `wallclock` is ESPN's UTC timestamp. Athlete ids are ESPN's. Read it per game by `espn_game_id`. |
| `nba_pbp_box` | player per game in ESPN's box | `(espn_game_id, espn_id)` | side, team, starter, ESPN's whole minutes. |
| `nba_player_id_map` | ESPN athlete | `espn_id` | `player_id` is the NBA.com person id every other NBA table uses (`nba_player_game_log`, `nba_player_game_adv`). Matched by name within team and game; `method` says how. |
| `nba_stints` | stretch with the same ten players on the floor | `(espn_game_id, stint_no)` | see below |

**`nba_stints` columns.** `start_s`/`end_s`/`duration_s` are game seconds (0 at tip, 2880 at
the end of regulation, +300 per overtime). The five a side are stored twice, as sorted arrays:
`home_player_ids`/`away_player_ids` (our NBA.com ids, `espn:<id>` where the map has none, the
convention `nba_results_ingestor` already uses) and `home_espn_ids`/`away_espn_ids`. Arrays
rather than five columns, because a model asks "is this player on the floor", and sorted, so
the same five always give the same array (equality and GROUP BY work). `n_home`/`n_away` count
the players. Per side: points, possessions, and the counts the Oliver possession estimate needs
(`fga`, `fg3a`, `fg3m`, `fta`, `ftm`, `oreb`, `tov`). `home_score_start`/`away_score_start` are
the score when the stretch began. `garbage_time` is true when the whole row is garbage time.

**Joins.** To `games` on `game_id` (regular season). To player tables on
`unnest(home_player_ids)` = `player_id`. Postseason and play-in games carry the same id format
and join to `nba_player_game_adv` the same way, but are not in `games`.

## How a stretch is built (each rule is pinned by a test that was watched to fail)

- **Order** by clock, not ESPN's sequence number (sorting by sequence put periods out of
  order in 239 games of 2018-19).
- **Points** from what the play is: a made field goal is its shot value, a made free throw
  is 1. ESPN's score columns are stale on non-scoring rows, and its `score_value` is 0 on every
  made free throw in 2018-19.
- **Shot value** (2 or 3): ESPN's `points_attempted` where the file has it, the made shot's
  `score_value`, "three point" in the text, the distance in the text (24 ft or more is a
  three, 21 or less a two), then the shot location for 22-23 ft. Measured against the files'
  own truth: 0.04-0.08% wrong.
- **Substitutions during free throws** wait until the last free throw, so the trip belongs to
  the five on the floor at the foul (the convention public adjusted plus-minus work uses).
- **Who starts a period.** Period 1 is the box score's starters. For later periods a player
  starts when his first appearance is anything but being substituted in. A player who logs
  nothing all period (a known ESPN gap) fills the fifth spot: first whoever was on the floor
  when the previous period ended, then by box-score time not yet accounted for.
- **Repairs.** ESPN half-logs some substitutions ("X enters the game for " with no one
  leaving). After each clock instant a side with six loses the player whose next appearance is
  being substituted in (or who never appears again), and a side with four gains the player whose
  next appearance is a play. A play by a player we did not have on the floor puts him on.
- **Possessions** are counted from events: a made shot (an and-one ends at its free throw), a
  made last free throw (technical, flagrant and clear-path free throws never end one), a
  defensive rebound, a turnover, and the end of a period when the team holding the ball got it
  with time on the clock. A possession counts in the stretch where it ends. The team
  "offensive rebound" ESPN logs after every missed non-final free throw is not a rebound.
- **Garbage time**, Cleaning the Glass's published rule
  (https://cleaningtheglass.com/stats/guide/garbage_time): 4th quarter; margin of 25 or more
  with 12-9 minutes left, 20 with 9-6, 10 after that; two or fewer of the game's starters on
  the floor combined; and the game "can never go back to being non-garbage time". So it is the
  final stretch of a regulation game in which all of that holds to the buzzer; an overtime game
  has none. A stretch is split where garbage time begins, so each row is wholly in or out.

## What was loaded, and the checks (measured 2026-10-17 on production)

| Season | `games` rows | matched (a) | stint points = final (b) | five a side, share of time (c) | time = 48 min + 5 per OT (d) | NBA.com seconds by mapped players on the floor (e) | player seconds within 30 s of NBA.com | possessions vs NBA.com, mean / mean absolute | garbage time, share of time |
|---|---|---|---|---|---|---|---|---|---|
| 2019 | 1,230 | 1,230 | 1,225 (99.59%) | 99.980% | 1,230 (100%) | 99.997% | 99.54% | -0.62 / 0.67 | 2.90% |
| 2020 | 1,059 | 1,059 (6 from ESPN's endpoint) | 1,058 (99.91%) | 99.961% | 1,059 (100%) | 100.000% | 99.48% | -0.60 / 0.65 | 2.49% |
| 2021 | 1,080 | 1,080 | 1,080 (100%) | 99.993% | 1,080 (100%) | 99.999% | 99.55% | -0.57 / 0.62 | 3.22% |
| 2022 | 1,230 | 1,230 | 1,227 (99.76%) | 99.996% | 1,230 (100%) | 100.000% | 99.65% | -0.60 / 0.64 | 2.95% |
| 2023 | 1,230 | 1,230 | 1,224 (99.51%) | 99.997% | 1,229 (99.92%) | 100.000% | 99.08% | -0.57 / 0.64 | 2.52% |
| 2024 | 1,230 | 1,230 | 1,223 (99.43%) | 99.995% | 1,230 (100%) | 100.000% | 99.59% | -0.57 / 0.63 | 3.18% |
| 2025 | 1,230 | 1,230 | 1,228 (99.84%) | 99.997% | 1,230 (100%) | 100.000% | 99.32% | -0.62 / 0.69 | 3.08% |
| 2026 | 1,230 | 1,230 (1 from ESPN's endpoint) | 1,227 (99.76%) | 99.998% | 1,230 (100%) | 100.000% | 99.47% | -0.58 / 0.65 | 3.37% |

Bars: (b) and (d) at least 99% of games, (c) at least 98% of game time. Every season clears all
three. Also loaded and not in `games` (which holds the regular season only): 672 postseason
games, 37 play-in games and the three NBA Cup finals (2023-12-09, 2024-12-17, 2025-12-16), the
same postseason and play-in counts `nba_player_game_adv` holds. Rows: 4,836,266 plays (1,151 MB),
314,149 segments (151 MB), 266,040 box rows, 10,231 games, 1,315 ESPN ids (1,313 matched).

**The 27 games that miss (b) are the feed's, not the derivation's.** In all 27 the segment
points equal the plays' points, and ESPN's own final equals `games`; ESPN's play list does not
add up to ESPN's own final (duplicated or missing plays, and in NBA_2023-01-12_CLE_POR a play
list that stops after three quarters, which is also the one game that misses (d)). ESPN's live
summary endpoint returns the same broken lists, so there was nothing better to read.

**Possessions** run about 0.6 a player-game under NBA.com's count (out of roughly 50-100), a
consistent small undercount rather than noise; NBA.com's exact definition is not published.

**Repairs** the derivation made, all eight seasons (`nba_pbp_games.diagnostics`): a period's
five completed from the previous period's end 80 times out of 83,064 team-periods, and from box
time 2 times; still short of five once (NBA_2019-01-07_SAS_DET); six seen before any substitution
151 times; a player put on the floor because he made a play 882 times; a sixth player taken off
944 times and a fifth put on 357 times, both by looking ahead in the period. One 2018-19 game
(NBA_2018-11-18_NYK_ORL) has no box score in the release; its roster comes from its plays and
its periods' fives from first appearances.

Queries (Supabase SQL editor or the MCP, read-only):

```sql
-- (a) matched per season
SELECT g.season, count(*) games, count(p.game_id) matched,
       count(*) FILTER (WHERE p.source = 'espn_summary_api') from_espn_summary
  FROM games g LEFT JOIN nba_pbp_games p ON p.game_id = g.game_id
 WHERE g.sport = 'NBA' AND g.season BETWEEN 2019 AND 2026 GROUP BY 1 ORDER BY 1;

-- (b), (c), (d); periods from nba_period_scores, the ledger's count where it has none (4 games of 2020)
WITH s AS (SELECT game_id, sum(home_pts) hp, sum(away_pts) ap, sum(duration_s)::numeric secs,
                  (sum(duration_s) FILTER (WHERE n_home = 5 AND n_away = 5))::numeric five
             FROM nba_stints WHERE season_type = 2 GROUP BY game_id),
     per AS (SELECT game_id, max(period) np FROM nba_period_scores GROUP BY game_id)
SELECT g.season, count(*) games,
       count(*) FILTER (WHERE s.hp = g.home_score AND s.ap = g.away_score) b_points_match,
       round(100 * sum(s.five) / sum(s.secs), 3) c_pct,
       count(*) FILTER (WHERE abs(s.secs - (2880 + 300 * greatest(coalesce(per.np, p.n_periods) - 4, 0))) < 0.5) d_match
  FROM games g JOIN s USING (game_id) JOIN nba_pbp_games p ON p.game_id = g.game_id
  LEFT JOIN per ON per.game_id = g.game_id
 WHERE g.sport = 'NBA' GROUP BY 1 ORDER BY 1;

-- (e) and the two validations against NBA.com (nba_player_game_adv, regular season)
WITH pc AS (SELECT s.game_id, pid, sum(s.duration_s) secs,
                   sum(CASE WHEN pid = ANY(s.home_player_ids) THEN s.home_poss ELSE s.away_poss END) off_poss
              FROM nba_stints s, unnest(s.home_player_ids || s.away_player_ids) pid GROUP BY 1, 2)
SELECT a.season,
       round(100.0 * sum(a.seconds_played) FILTER (WHERE pc.pid IS NOT NULL) / sum(a.seconds_played), 3) e_pct,
       round(100.0 * avg((abs(coalesce(pc.secs, 0) - a.seconds_played) <= 30)::int), 2) within_30s_pct,
       round(avg(pc.off_poss - a.possessions)::numeric, 2) poss_mean_diff,
       round(avg(abs(pc.off_poss - a.possessions))::numeric, 2) poss_mae
  FROM nba_player_game_adv a LEFT JOIN pc ON pc.game_id = a.game_id AND pc.pid = a.player_id
 WHERE a.played AND a.game_type = 'regular' GROUP BY 1 ORDER BY 1;
```

**Things a reader should know.** Gap games' `nba_pbp_box` rows list only players who played
(ESPN's summary path drops did-not-play rows). The release puts every free throw at (25, 13.75)
while ESPN's endpoint gives free throws no location; either way a free throw's location means
nothing. Shot locations are ESPN's, in feet, basket at (25, 0).

## Commands

```bash
# all through the wrapper that puts the production DATABASE_URL in the process only
python -m data.ingestors.nba_pbp --seasons 2019-2026 --build-map        # id map first
python -m data.ingestors.nba_pbp --seasons 2019-2026 --load             # resumable
python -m data.ingestors.nba_pbp --seasons 2019-2026 --fill-gaps        # after --load
python -m data.ingestors.nba_pbp --seasons 2019 --load --rederive-stints   # new derivation
python -m data.ingestors.nba_pbp --seasons 2019 --dry-run               # derive, write nothing
```

A re-run writes nothing already stored. `--rederive-stints` replaces a season's stretches and
ledger rows and leaves its plays and box as stored.
