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
  segments. Their `nba_pbp_games.source` is `espn_summary_api`. Their `game_date` is our
  `games` row's Eastern date: ESPN dates four of them by a placeholder timestamp a day late
  (DET at POR on 2020-02-23 is ESPN's 2020-02-24T12:00Z), and until 2026-10-17 the ledger
  carried ESPN's day for DET_POR 02-23, DEN_LAC 02-28, GSW_PHX 02-29 and POR_ATL 02-29.

## Tables (all worker-only, locked down where they are created)

| Table | One row per | Key | What a reader needs to know |
|---|---|---|---|
| `nba_pbp_games` | ESPN game loaded | `espn_game_id` | `game_id` is ours (`NBA_<ET date>_<away>_<home>`), and `game_date` is the same Eastern date; `in_games` says whether `games` holds it (regular season only); `match_method`; ESPN's final; the derivation's repair counts in `diagnostics`. **`points_mismatch`** is true when the game's segment points do not equal its final (ESPN's, or `games`' for the one game with no ESPN box): exclude those 9 games from anything that needs points. **`points_source`** is `plays` (each play's own points) or `espn_running_score` (18 games whose plays do not add up; see below). `derivation` is `stints-v2` on the 36 games rebuilt on 2026-10-17 and `stints-v1` on the other 10,195, where v2 builds exactly v1's rows (compared game by game on every one of them). Written in the same commit as the game's plays, so it is the resume ledger. |
| `nba_pbp` | play | `(espn_game_id, play_no)` | `play_no` is the play order used everywhere (period, clock, then ESPN's sequence). `clock_s` = seconds left in the period, `game_s` = game seconds elapsed. `points` is what the play scored; `home_score`/`away_score` are running totals of `points`; ESPN's own columns are kept as `espn_home_score`/`espn_away_score`. In the 18 games whose `points_source` is `espn_running_score`, `points` stays each play's own and does not add up to the final (ESPN's duplicated plays are still in it); read those games' points from `nba_stints`, which do. `team_side` is H or A; on the two free throws ESPN logged with no team it is inferred and `espn_team_id` stays NULL (see below). Athlete ids are ESPN's as ESPN wrote them, including the four second ids below. Read it per game by `espn_game_id`. The shot columns are described under "Things a reader should know". |
| `nba_pbp_box` | player per game in ESPN's box | `(espn_game_id, espn_id)` | side, team, starter, ESPN's whole minutes. |
| `nba_player_id_map` | ESPN athlete | `espn_id` | `player_id` is the NBA.com person id every other NBA table uses (`nba_player_game_log`, `nba_player_game_adv`). Matched by name within team and game; `method` says how. Four rows (`method = 'play_alias_in_game'`) are ids that only ESPN's plays use, mapped through the box player they belong to. |
| `nba_stints` | stretch with the same ten players on the floor | `(espn_game_id, stint_no)` | see below |

**`nba_stints` columns.** `start_s`/`end_s`/`duration_s` are game seconds (0 at tip, 2880 at
the end of regulation, +300 per overtime). The five a side are stored twice, as sorted arrays:
`home_player_ids`/`away_player_ids` (our NBA.com ids, `espn:<id>` where the map has none, the
convention `nba_results_ingestor` already uses; no row carries one since the 2026-10-17 rebuild)
and `home_espn_ids`/`away_espn_ids` (the box score's ids). Arrays
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
- **A free throw ESPN logged with no team** takes the side whose ESPN running score rose on
  that row; a missed one takes the side of the other free throws at that instant, else the
  opponent of the team that fouled. Exactly two plays in the eight seasons need it (ESPN game
  401469046, NBA_2023-02-23_SAS_DAL, plays 46 and 47: a made technical and the missed and-one,
  both San Antonio's). Before, the made one counted for nobody and San Antonio's segments
  summed to 115 against a final of 116. Counted per game in `diagnostics.sides_inferred`.
- **When a side's plays do not add up to ESPN's final**, and ESPN's running score (the score
  columns) ends exactly at it, that side's points come from the running score: each of the
  side's scoring plays is credited with how far the running score rose between it and the
  side's next scoring play. That is 18 games (`points_source = 'espn_running_score'`): ESPN
  logs a play twice (NBA_2025-11-15_DEN_MIN: Jokic's three at sequence 400 and again at 408,
  where the running score does not move), or flags a miss as a make, while its running score
  is right. In those 18 games 69 scoring plays are credited differently from their own
  points: 40 get nothing (25 of them a repeat of a play by the same player for the same points
  within 30 seconds), and 29 are raised or lowered because the running score lags or leads by a
  play or two (worst: NBA_2024-02-14_SAS_DAL's 4th quarter). That is the price of those games
  summing to their final: a few points sit on the neighbouring scoring play of the same side.
  **Only the points are corrected.** In those 18 games the segments' attempts, makes and
  possessions still count ESPN's duplicated plays (checked 2026-10-17 against NBA.com's box on
  the 21 team-games affected: threes made differ on 8, free throws made on 8, field-goal
  attempts on 16; a control of 762 other team-games differs on none for makes). A shot-level
  or three-point-luck reader should exclude `points_source = 'espn_running_score'` games.
  **Not everywhere:** the running score lags the play that scored often enough that crediting
  each scoring row with the rise on that row broke the total in 179 of 2018-19's 1,305 games
  whose plays add up, and 63 of 2025-26's 1,319. Where the running score is short too (9
  games, plays missing from the feed), the plays' own points stand and `points_mismatch` is
  true.
- **A player ESPN logs under a second id** (his plays use one, the box another; 4 games:
  Emanuel Terry in NBA_2019-01-27_PHX_LAL, Eric Moreland in NBA_2019-04-09_TOR_MIN, Jordan
  McLaughlin in NBA_2021-02-10_LAC_MIN, who appears under both ids, and Norvel Pelle in
  NBA_2021-04-03_NYK_DET) is read as the box player of the same side whose name the play text
  carries, when exactly one box player's does. Before, his floor time sat under `espn:<id>`.
  The aliases are in `diagnostics.play_id_aliases`; `nba_pbp` keeps ESPN's ids.
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
- **Zero-second stretches are kept, so weight by possessions, not seconds.** A change made
  while the clock is stopped gives a five that is on the floor for no game time but for real
  events: 880 rows last 0 seconds; 338 of them carry points (504 in all, of 2,306,266) and
  669 a possession (675, of 2,049,251). Three were read play by play, and no direction of
  folding is right in all three. In NBA_2025-11-26_MIN_OKC at 0:26.8 of the 4th, Minnesota
  brought on Reid and Conley at a timeout, committed a 5-second inbound violation, then sent
  McDaniels back on for Conley, all at one instant: the turnover is the zero-second five's,
  and folding it into the stretch before would credit the five from before the timeout. In
  NBA_2025-10-27_DEN_MIN at 0:07 of the 3rd, Denver made two changes and then committed an
  away-from-play foul: the free throw belongs to the five after both changes, which is the
  stretch after, not the one before. In NBA_2025-11-07_BOS_ORL at 2:20 of the 3rd, the
  zero-second row holds Orlando's possession ending at a Boston rebound taken by a player
  logged as entering just after it. So the rows stay. A model that weights stretches by
  seconds gives them nothing; weight by possessions.
- **Garbage time**, Cleaning the Glass's published rule
  (https://cleaningtheglass.com/stats/guide/garbage_time): 4th quarter; margin of 25 or more
  with 12-9 minutes left, 20 with 9-6, 10 after that; two or fewer of the game's starters on
  the floor combined; and the game "can never go back to being non-garbage time". So it is the
  final stretch of a regulation game in which all of that holds to the buzzer; an overtime game
  has none. A stretch is split where garbage time begins, so each row is wholly in or out.

## What was loaded, and the checks (re-measured 2026-10-17 on production, after the rebuild)

| Season | `games` rows | matched (a) | stint points = final (b) | five a side, share of time (c) | time = 48 min + 5 per OT (d) | NBA.com seconds by mapped players on the floor (e) | player seconds within 30 s of NBA.com | possessions vs NBA.com, mean / mean absolute | garbage time, share of time (all game types) |
|---|---|---|---|---|---|---|---|---|---|
| 2019 | 1,230 | 1,230 | 1,228 (99.84%) | 99.980% | 1,230 (100%) | 99.999% | 99.55% | -0.62 / 0.67 | 2.90% |
| 2020 | 1,059 | 1,059 (6 from ESPN's endpoint) | 1,059 (100%) | 99.961% | 1,059 (100%) | 100.000% | 99.48% | -0.60 / 0.65 | 2.49% |
| 2021 | 1,080 | 1,080 | 1,080 (100%) | 99.993% | 1,080 (100%) | 100.000% | 99.56% | -0.57 / 0.62 | 3.22% |
| 2022 | 1,230 | 1,230 | 1,229 (99.92%) | 99.996% | 1,230 (100%) | 100.000% | 99.65% | -0.60 / 0.64 | 2.95% |
| 2023 | 1,230 | 1,230 | 1,227 (99.76%) | 99.997% | 1,229 (99.92%) | 100.000% | 99.08% | -0.57 / 0.64 | 2.52% |
| 2024 | 1,230 | 1,230 | 1,229 (99.92%) | 99.995% | 1,230 (100%) | 100.000% | 99.59% | -0.57 / 0.63 | 3.18% |
| 2025 | 1,230 | 1,230 | 1,230 (100%) | 99.997% | 1,230 (100%) | 100.000% | 99.32% | -0.62 / 0.69 | 3.08% |
| 2026 | 1,230 | 1,230 (1 from ESPN's endpoint) | 1,228 (99.84%) | 99.998% | 1,230 (100%) | 100.000% | 99.47% | -0.58 / 0.65 | 3.37% |

Bars: (b) and (d) at least 99% of games, (c) at least 98% of game time. Every season clears all
three. Also loaded and not in `games` (which holds the regular season only): 672 postseason
games, 37 play-in games and the three NBA Cup finals (2023-12-09, 2024-12-17, 2025-12-16), the
same postseason and play-in counts `nba_player_game_adv` holds; all of them now sum to ESPN's
final. Rows: 4,836,266 plays (1,151 MB), 314,148 segments (151 MB), 266,040 box rows, 10,231
games, 1,319 ESPN ids (1,317 matched).

**The 9 games that miss (b) are the feed's, and each is flagged `points_mismatch`**:
NBA_2018-12-07_OKC_CHI, NBA_2019-03-04_NOP_UTA, NBA_2022-01-26_LAC_ORL, NBA_2023-01-12_CLE_POR,
NBA_2023-03-09_UTA_ORL, NBA_2023-03-16_IND_MIL, NBA_2024-02-08_CLE_BKN, NBA_2025-11-17_OKC_NOP and
NBA_2026-01-20_LAC_CHI. In all 9 ESPN's play list and ESPN's own running score both stop short
of ESPN's final, which equals `games`: plays are missing (in CLE_POR the list stops after three
quarters, which is also the one game that misses (d)). ESPN's live summary endpoint returns the
same lists, so there was nothing better to read. Before the 2026-10-17 rebuild 27 regular-season
games missed (b); 18 now take their points from ESPN's running score (see "How a stretch is
built") and SAS_DAL 2023-02-23 adds up once its technical free throw has a team. The flag agrees
with (b) on every regular-season game (the query below counts disagreements: 0 in every season).

**(e)'s last gap** is NBA_2019-01-26_GSW_BOS: ESPN logs Daniel Theis only being substituted out
at the start of the 4th, never coming on, so NBA.com's 222 seconds for him sit in no segment.

**Possessions** run about 0.6 a player-game under NBA.com's count (out of roughly 50-100), a
consistent small undercount rather than noise; NBA.com's exact definition is not published.

**Repairs** the derivation made, all eight seasons (`nba_pbp_games.diagnostics`): a period's
five completed from the previous period's end 80 times out of 83,064 team-periods, and from box
time 2 times; still short of five once (NBA_2019-01-07_SAS_DET); six seen before any substitution
151 times; a player put on the floor because he made a play 881 times; a sixth player taken off
943 times and a fifth put on 357 times, both by looking ahead in the period; a team inferred
for a free throw 2 times; a second ESPN id read as its box player in 4 games. One 2018-19 game
(NBA_2018-11-18_NYK_ORL) has no box score in the release; its roster comes from its plays, its
periods' fives from first appearances, and its `points_mismatch` from `games`' final.

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
       count(*) FILTER (WHERE p.points_mismatch) b_flagged,
       count(*) FILTER (WHERE (s.hp = g.home_score AND s.ap = g.away_score) = p.points_mismatch) b_flag_wrong,
       round(100 * sum(s.five) / sum(s.secs), 3) c_pct,
       count(*) FILTER (WHERE abs(s.secs - (2880 + 300 * greatest(coalesce(per.np, p.n_periods) - 4, 0))) < 0.5) d_match
  FROM games g JOIN s USING (game_id) JOIN nba_pbp_games p ON p.game_id = g.game_id
  LEFT JOIN per ON per.game_id = g.game_id
 WHERE g.sport = 'NBA' GROUP BY 1 ORDER BY 1;

-- the ledger: where segment points came from, and which games miss the final
SELECT derivation, points_source, points_mismatch, count(*) FROM nba_pbp_games GROUP BY 1, 2, 3;

-- garbage time, share of segment time (all game types)
SELECT season, round((100.0 * sum(duration_s) FILTER (WHERE garbage_time) / sum(duration_s))::numeric, 2)
  FROM nba_stints GROUP BY 1 ORDER BY 1;

-- placeholder ids left in the segments (none)
SELECT s.game_id, pid, count(*) FROM nba_stints s, unnest(s.home_player_ids || s.away_player_ids) pid
 WHERE pid LIKE 'espn:%' GROUP BY 1, 2;

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

## Things a reader should know

- **`shot_value`** is 1, 2 or 3 on every attempt. It is NULL on 21 rows that carry ESPN's
  shooting flag: all 21 are ESPN's "No Shot (Default Shot)" placeholder that did not score, and
  they are not attempts (11 of them in 2018-19).
- **`coord_x`/`coord_y` are not only on shots.** They are ESPN's location in feet, basket at
  (25, 0), and ESPN puts one on many other plays too: in 2025-26, 217,064 of the 344,014 plays
  without the shooting flag carry one (rebounds, fouls, turnovers). Filter on `shot_value` (or
  `shooting_play`) before reading a location as a shot's. The release puts every free throw at
  (25, 13.75) while ESPN's endpoint gives free throws no location; either way a free throw's
  location means nothing.
- **2025-26 counts more attempts than NBA.com.** In 2025-26 our field-goal attempts in the
  1,229 regular-season games from the release are 220,086 against NBA.com's 218,975 (+0.51%),
  and three-point attempts 91,994 against 90,893 (+1.21%). NBA.com stopped charging players
  with end-of-quarter heaves that season: ESPN logs 1,057 misses from 36 feet or more (by the
  shot's coordinates) in the last 3 seconds of quarters 1-3, all threes, which is 96% of the
  three-point excess. ESPN's text for them reads "misses heave jump shot", with no distance.
  In 2018-19 to 2024-25 both count the heaves (2024-25 has 617 by the same measure) and attempts agree
  within 0.03% (three-point attempts within 0.19%). For three-point luck, drop those misses in
  every season (period 1-3, `clock_s` <= 3, a miss whose coordinates are 36 feet or more from
  the basket) so the seasons compare.
- **Possessions** in the segments run about 0.6 a player-game under NBA.com's count (-0.57 to
  -0.62 a season, the table above).
- **Points in 18 games come from ESPN's running score** (`points_source`), and 9 games miss the
  final (`points_mismatch`); see the table above.
- **Zero-second stretches**: 880 rows; weight by possessions, not seconds (see "How a stretch
  is built").
- Gap games' `nba_pbp_box` rows list only players who played (ESPN's summary path drops
  did-not-play rows).

## Commands

```bash
# all through the wrapper that puts the production DATABASE_URL in the process only
python -m data.ingestors.nba_pbp --seasons 2019-2026 --build-map        # id map first
python -m data.ingestors.nba_pbp --seasons 2019-2026 --load             # resumable
python -m data.ingestors.nba_pbp --seasons 2019-2026 --fill-gaps        # after --load
python -m data.ingestors.nba_pbp --seasons 2019 --load --rederive-stints   # new derivation
python -m data.ingestors.nba_pbp --seasons 2019 --dry-run               # derive, write nothing
python -m data.ingestors.nba_pbp --rebuild ids.txt [--dry-run]          # named stored games, from Supabase alone
```

A re-run writes nothing already stored. `--rederive-stints` replaces a season's stretches and
ledger rows and leaves its plays and box as stored. `--rebuild` re-derives the games a file lists
(ESPN ids, one a line) from `nba_pbp` and `nba_pbp_box` alone, so gap games rebuild too, and
replaces each one's ledger row and stretches, and its plays where this code sets them
differently, in one transaction per game. The 36 games of 2026-10-17 were rebuilt this way.
