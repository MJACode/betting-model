# Data archive: no deletions, a small live database, a full history

Design and measurements, 2026-11-14 (mike: *"the supabase DB is getting too
large … We should not be deleting any data, that needs to be a hard rule that
only mike can override"*). The rule itself is in CLAUDE.md §1b ("NO DATA IS
EVER DELETED"). This file holds what was measured, what still deletes, and the
plan. **Built so far: the deleting jobs are stopped and the PC copy keeps what
Supabase loses (section 2). The archive itself is not built.** Tracked in issues #1343 (stop the
deleting jobs), #1344 (rank the slow queries on a morning window) and #1345
(build the archive). Every number below names the query
or log that produced it, and all were read on 2026-11-14 between 19:38 and
20:05 UTC.

## 1. What was measured

**Size.** The database is 98 GB (`pg_database_size`). Three tables of price
snapshots hold 70 GB of it:

| Table | Total | Table data | Indexes | Rows (planner estimate) |
|---|---|---|---|---|
| `player_prop_odds` | 40 GB | 26 GB | 14 GB | 81.6M |
| `odds` | 21 GB | 12 GB | 9.8 GB | 51.5M |
| `nfl_odds_history` | 8.7 GB | 4.0 GB | 4.7 GB | 35.8M |
| `ncaab_pbp` | 4.2 GB | 2.9 GB | 1.3 GB | 11.4M |
| `latest_prop_odds` (a cache) | 4.0 GB | 2.1 GB | 1.9 GB | 9.4M |
| `picks_log` | 2.6 GB | 2.5 GB | 0.2 GB | 8.5M |
| `kalshi_game_markets` | 2.0 GB | 1.3 GB | 0.8 GB | 5.3M |

(`pg_total_relation_size` / `pg_relation_size` / `pg_indexes_size`.)

**The machine.** `shared_buffers` 256 MB, `effective_cache_size` 768 MB,
`max_connections` 60. Those are Supabase's **Micro** compute: 1 GB of memory,
a shared 2-core CPU. Supabase's own table (docs, "Compute and Disk") recommends
Micro for databases up to **10 GB**; ours is 98 GB. The docs also say the
small sizes can burst disk reads for a while each day, then drop to a slow
baseline once that daily allowance is used up. That is the morning slowdown,
measured in detail the same day under issue #1328 (the nightly PC copy's run
grew from about 75 minutes to 9 hours as the allowance ran out).

**The same data, compressed, is small.** The copy on mike's PC holds all
248M rows in **3.47 GB** of Parquet files. `player_prop_odds` is 82.4M rows in
1.6 GB there, against 40 GB in Postgres. Most of a stored row is not price
data. In `player_prop_odds` the two deep links average 94 and 93 bytes, the
two book ids 25 and 28, and the three timestamps (stored as text) 21 to 31.
The line and both prices are 5 to 6 bytes each (`pg_stats.avg_width`).

**Most of the bulk is recent.** Sampled share of each table's data by date
(1% block sample, `pg_column_size`; props by game date, `odds` by snapshot date):

| Age | `player_prop_odds` | `odds` |
|---|---|---|
| under 30 days | 7.2 GB | 3.1 GB |
| 30 to 60 days | 9.3 GB | 0.7 GB |
| 60 to 90 days | 5.7 GB | 0.5 GB |
| 90 to 180 days | 0.7 GB | 0.1 GB |
| 180 to 365 days | 0.5 GB | 1.7 GB |
| over 365 days | 1.2 GB | 5.8 GB |

So **90% of the prop table is under 90 days old**. Collection grew sharply
from September (more books, more markets, more passes). Archiving everything
older than 90 days would move about 10% of the prop table and 64% of `odds`.
That is roughly 17 GB of the 98, not "the majority". The real cause of the
size is the rate of writing, which is section 5.

**Write rate.** Primary keys moved by 11.67M in `player_prop_odds` and 20.17M
in `odds` between the first snapshot of 2026-11-07 and the first of
2026-11-14. That is 1.67M and 2.88M rows written a day. It includes
purchased history, which lands with old snapshot dates.

**Repeats.** On three NBA games of 2026-11-13, 472,370 prop rows were stored
pre-game. Only 183,105 of them (39%) were a new line or a changed price for
the same player, market, line and book. **61% were exact repeats** of the row
before. (On 2026-10-15's NBA game lines the pruner's own docstring measured
1,337 changes in 33,654 rows.)

## 2. What deleted, and what still does

Measured from `pg_stat_user_tables` (rows deleted since 2026-03-30) and the
worker's logs.

**Stopped 2026-11-14 (mike: "Yes, stop tonight"; issue #1343).** The first four
jobs in the table below now ask `config.data_deletion_approved(<job>)` and
delete nothing without an entry in `config.DATA_DELETION_APPROVALS`: the odds
prune (`prune_odds`), the API call log (`api_call_log`, whose daily rollup
still runs), `app_timings` and `player_news`. The PC copy keeps every row that
leaves Supabase in `<table>/vanished/`, and every removed bucket file in
`storage_vanished/`. Pinned by `tests/test_no_data_deleted.py` and
`tests/test_local_mirror.py`. **Still deleting:** `lineup_slots`,
`capper_picks` and the rewrites below. Each writer replaces its rows by
design, and changing that touches its readers. The PC copy now keeps what
they remove.

**Destroying records (history that exists nowhere else):**

| Job | Table | Measured |
|---|---|---|
| `data/prune_odds.py`, daily ~06:30-08:50 ET | `odds`, `player_prop_odds` (books other than DraftKings, the sharp books and paid-history sources) | 2.50M `odds` + 6.27M prop rows + 0.34M repeat rows deleted in the seven runs 11-08 to 11-14 (worker logs). The prop backlog is still walking back toward 2026-09-01, so September's 38.7M prop rows are next. |
| `monitoring/store.py` `prune()` | `api_call_log`, older than 7 days | 11.6M rows deleted since 03-30. Daily totals survive in `api_call_daily`; the individual calls do not. |
| `data/app_timings_retention.py` | `app_timings` | app load-time records |
| `data/ingestors/player_news_ingestor.py` | `player_news`, older than 21 days | 9,855 rows |
| `data/ingestors/lineup_ingestor.py` | `lineup_slots`, replaced per game and team | 632,363 rows; earlier versions of a lineup are lost |
| `tracking/eggz_picks.py` | `capper_picks`, ungraded rows re-parsed per message | 11,197 rows |

**Rewrites of the same facts (need a check each, not assumed safe):**
`nhl_goalie_stats` (season rebuilds in `data/nhl_asof.py`, goalie swaps),
`mlb_pitcher_stats` (the 2026-09-03 rebuild), the play-by-play tables
(delete-then-rewrite per game from the same feed), and `games` (merges of
duplicate ids by alias migrations and one-off scripts).

**Not records:** `latest_odds`, `latest_prop_odds`, `latest_live_game_state`,
`injury_status_current`, `ncaab_injury_open`, `team_stats_board_cache`, the
`byom_*_facts` tables. Each is rebuilt from a stored table. (`alt_game_lines`
looks like one too; not verified.)

**`picks`:** 4.31M rows deleted since 03-30, almost all of them NONE and AVOID
rows rewritten by each scoring pass. The `picks_audit_trigger` copies every
insert, update and delete into `picks_log` first, so none of those is lost.

**The PC copy deletes too.** `scripts/local_mirror.py` "converges" to Supabase:
when a range of rows shrinks upstream it pulls the range again and the old
rows are gone locally. So every pruned row is also removed from the backup,
usually within a night.

## 3. Does moving history out affect the models?

Not if three things hold. Each one is a real reader found in the code.

**a. The cutoff is per table and keyed on the game's date, never the snapshot's.**
`models/scorer.py:2023` reads a game's first-ever snapshot as its opener, and a
game can be priced weeks ahead (`jobs/declared_jobs.json:989` cites a 09-05
price on a 10-24 game). Cutting by snapshot date would delete openers of games
not yet played.

**b. What production reads stays in the live database.** Readers that reach
back further than a few weeks:

- The Teams board refresh (daily, `run_pipeline.py:136`) recomputes last
  season, this season and next every day. It reads each finished game's closing
  line from the raw `odds` table (`team_stats_board_commence_bound_2026_09_30.sql`,
  lines 103-155). For MLB that reaches back to March 2025.
- CLV backfill on every settle walks from the first pick ever
  (`tracking/paper_tracker.py:1957`). Today it only revisits picks not yet
  stamped, so its real reach is short.
- The app's line-history screens read `odds` and `player_prop_odds` by game,
  with no date bound (`mobile/src/lib/queries.ts:3300`, `:3339`, `:3696`, `:4150`).
- The NBA first-basket build reads the whole current season of `nba_pbp` daily.
- The Kalshi ingestor runs an unbounded DISTINCT over `kalshi_game_markets`.

The clean way to keep all of these fast is a small permanent table: **one row
per game, market and book, holding the opener, the close and the decision-time
price**. It stays in Postgres forever and those readers move to it. The raw
snapshots behind it can then leave.

**c. Whole-history readers must fail loudly, not train on half the data.**
Retraining runs on the worker as well as locally (`tracking/job_queue.py:2896`,
`retrain_model`), and so do research sweeps and the BYOM builds. After a move,
a whole-history query against Postgres would return a truncated table with
**no error**. So every whole-history loader goes through one reader. It knows
the archive boundary (an `archive_watermarks` row per table), reads the
archive for older rows, and raises if it can't. The same applies to the
ingestors' "is this already stored?" checks before buying history
(`nba_odds_history.py`, `prop_odds_ingestor.py`, `odds_ingestor.py`). Without
it, a purchase job would see an archived season as missing and **buy it
again**.

Not yet read: `models/scorer.py` lines 714, 2306, 2434, 2732, 3384, 3841 and
3916, the live loops, and `game_market_gate.py:331`. They must be checked
before any rows move.

For **results**, keeping everything is a gain. Today the history of every
book but DraftKings and the sharp books is cut to an opener and a close two
days after the game. Book-versus-book closing value, line-shopping research
and any model that reads when books moved all depend on the history being
deleted now.

## 4. The design

| Layer | Where | Holds | Read by |
|---|---|---|---|
| Live | Supabase Postgres | everything production reads: all small tables whole and forever, the big snapshot tables for settled games inside their window, the opener/close table forever | scorers, app, Discord, worker jobs |
| Archive | **Supabase Storage**, one Parquet file per table per month, never rewritten | every row that leaves Postgres | the one history reader, research, retrains |
| PC copy | mike's machine | the live tables (daily, append-only) and the archive files | local retrains and research, through DuckDB |

**Why the archive lives in Supabase Storage and not only on the PC.** CLAUDE.md
§1b says everything is stored in Supabase first, and that the PC copy is a
backup, never the only copy. A PC-only archive would make one disk in one house
the sole copy of the paid history, and the cloud worker can't reach the PC.
Storage satisfies both rules. It is part of the Supabase project, the PC
mirror already copies its buckets, and the Pro plan includes 100 GB of it
($0.0213 per GB per month beyond that; Supabase docs, "Manage Storage size
usage"). The whole database is 3.47 GB as Parquet.

**How a row leaves Postgres.** Copy one table-month to Parquet. Upload it.
Read it back and check the row count and a hash of every row against Postgres.
Do the same against the PC copy. Write the `archive_watermarks` row. Only then
remove those rows. Deleting rows from a Postgres table does not shrink the
file on disk; the table has to be rewritten (`pg_repack`, which needs free
space the size of the table). Monthly partitions fix that going forward:
moving a month out becomes "detach one partition", with no row-by-row delete
and no cleanup cost.

**Windows.** One number doesn't fit every table. Proposed starting points,
each to be confirmed against the readers in section 3:

- Price snapshot tables (`player_prop_odds`, `odds`, `nfl_odds_history`,
  `kalshi_*`, the in-play quote tables): settled games older than 90 days.
  This depends on the opener/close table existing first; without it the Teams
  board needs about 20 months of `odds`.
- Play-by-play tables: seasons before the current one.
- `picks_log`, `api_call_log`, `app_timings`: older than 90 days.
- Everything else (`games`, `picks`, stats and game logs, injuries): stays
  whole. Each is under 1 GB.

## 5. Making it fast

In order of payoff per hour of work:

1. **Stop writing repeats.** 61% of the prop rows sampled, and about 96% of
   the NBA game-line rows, were exact repeats. Write a row only when a line
   appears, moves or disappears, and keep "still offered at T" in the
   latest-line table, which is already updated on every write. This cuts the
   write rate, the index size, the vacuum work and the nightly backup together.
   It isn't deletion; the repeats are never written.
2. **Fix the queries that read whole tables** (verified below).
3. **Compute size.** Micro is sized for 10 GB. Small (2 GB memory, ~$15 a
   month) is sized for 50 GB, and Medium (4 GB, ~$60) for 100 GB. A change
   takes under 2 minutes of downtime (Supabase docs).
4. **The archive**, which mainly stops the growth from reaching the live
   database.

**The other chat's five fixes, checked.** Query statistics are cumulative
since 2026-04-04, so old versions of rewritten queries still show up.

| Item | Verdict |
|---|---|
| 1. NFL opening-line card | Right about the effect. An index by game already exists (`idx_nfl_odds_hist_game`), but the planner uses the time-ordered primary key and reads two days of every game (EXPLAIN, 2026-11-14). An index ending in the snapshot time would let it go straight to the games. |
| 2. Pick-history safety check | Right. `picks_log` has only its primary key, so the date lookup reads all 2.6 GB. Recorded: 2,054 calls, 4.1 TB read. |
| 3. NCAAF current-price check | Not pinned to one query yet. Two candidates read `odds` broadly: an unsettled-games DISTINCT ON over five sports (4,566 calls, 20.7 s each) and an all-bookmaker DISTINCT by game. |
| 4. API-credit check | Right. `api_call_log` is indexed by (api, time) and by time, not by host or source. Of the 15 heaviest recorded queries, it was the only one that ran in a 5-minute window this afternoon: 9 calls, 218 MB. |
| 5. Daily API totals | Right that it's small now. The query was narrowed to two days on 2026-10-03, and the old whole-table version is what tops the cumulative list (9.4 TB). |

**Heavy readers the other chat didn't list:**

- the nightly PC backup's own range counts. Four queries, about 792 GB read
  since the copy began on 2026-11-03.
- the MLB starting-pitcher reads of `player_game_log` (1.9 TB recorded).
- `refresh_team_stats_board` (0.9 TB recorded).

(`SELECT MAX(created_at) FROM injuries`, 0.6 TB recorded, was fixed by an
index on 2026-11-14, issue #1328.) A morning-window measurement is still
needed to rank these by what runs now.

## 6. The nightly backup

**What it does now** (`scripts/local_mirror.py`, last night's log): it is
already a diff for the 12 tables over 2M rows. It appends new rows, re-counts
every range and re-hashes a rotating seventh. Last night it ran **00:30 to
09:35 ET** and pulled **67.6M rows**, 27% of everything it holds:

- 32.1M rows from re-copying 288 small tables whole. 12.7M of those are the
  two latest-line caches.
- 35.5M rows from the large tables: `odds` 18.8M (256 ranges re-pulled),
  `nfl_odds_history` 5.5M, `player_prop_odds` 5.0M.

Ranges are re-pulled mostly because the pruner changed them overnight.

**What changes:**

1. **Append-only.** Done 2026-11-14. A row whose key is in none of its chunk's
   replacements is written to `<table>/vanished/` before the old chunk goes.
   This morning's 1.08M pruned prop rows were already gone from the PC: the
   copy's prop pass ended at 14:32 UTC, after the prune (13:38-13:49 UTC), and
   its counts matched Supabase at 14:35.
2. **No more nightly whole copies of unchanged tables.** Copy incrementally
   wherever there is a key and a way to see changes. Skip the latest-line
   caches; they can be rebuilt.
3. **Archived months are frozen.** They are verified once when written, then
   checked against a stored hash, never re-counted against Postgres.
4. **A full check once a month**, as you suggested: every row hashed on both
   sides, run on a weekend afternoon, with the result written to Supabase.

With deletions stopped and repeats no longer written, a night's work becomes
roughly the day's new rows.

## 7. Order of work

1. Stop the deleting jobs (section 2), and make the PC copy append-only the
   same day.
2. Index fixes (section 5), each measured before and after.
3. Write only changes, starting with the prop table.
4. The opener/close table; move the Teams board, CLV and the app's
   line-history screens to it.
5. The one history reader and `archive_watermarks`.
6. The archive job, one table-month at a time, starting with `odds` before
   2025.
7. Monthly partitions for the two big odds tables.
