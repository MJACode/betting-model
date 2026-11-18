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

> **Size is recorded every hour since 2026-11-16** (`db_health_snapshots`,
> and every table's size every six hours in `db_table_snapshots`; the ops
> dashboard's Database tab, `docs/monitoring.md`). The first snapshot read
> 109,078,711,443 bytes (pg_size_pretty 102 GB) at 03:41 UTC. Use those
> tables for growth instead of re-measuring by hand.

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
Model building runs on mike's PC (mike, 2026-11-15): retrains, sweeps and
full-history BYOM backfills. The worker can also run them
(`tracking/job_queue.py`, `retrain_model`), and it did occasionally: 7 retrains
on 2026-09-01, 13 sweeps from 09-16 to 10-28, 8 BYOM backfills from 10-28 to
11-05 (`worker_jobs`). After a move, a whole-history query against Postgres
would return a truncated table with **no error**. So every whole-history
loader goes through one reader. It knows the archive boundary (an
`archive_watermarks` row per table, kept in Supabase). On the PC it reads the
archive files for the older rows. On the worker, or wherever the files are
missing, it raises. The worker's recurring jobs don't need the archive: the
daily `byom_refresh` reads the current season, and the weekly calibration reads
graded picks (`mv_scored_pick_outcomes`).

Measured 2026-11-15 on the PC (32 GB of memory, pyarrow): all 83,872,923 prop
rows in 13.6 s, and all 57,362,605 `odds` rows in 12.0 s. One day of props
(65,774 rows) took 1.63 s from the files and 3.97 s from Supabase. The same applies to the
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
| Archive | **mike's PC**, one Parquet file per table per month, never rewritten | every row that leaves Postgres | the one history reader: retrains, sweeps, research |
| Archive backup | **Supabase Storage**, the same files | the same rows | nothing routinely; it is the copy to restore from |
| PC copy | mike's machine | the live tables (daily, append-only) | local research next to the archive |

**Why the archive has a second copy in Supabase Storage** (mike, 2026-11-15:
*"Yes, keep a copy"*). Supabase Pro keeps 7 days of its own daily backups
(Supabase docs, "Database Backups"). So a week after rows leave Postgres, the
archive is their only copy. On the PC alone, one failed disk would lose the
paid history. Storage is part of the Supabase project, and the Pro plan
includes 100 GB of it ($0.0213 per GB per month beyond that; Supabase docs,
"Storage pricing"). The whole database is 3.47 GB as Parquet. Nothing in this
design needs Supabase's Team plan.

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

## 8. Moving rows out: what goes now, and what has to change first (2026-11-16)

mike, 2026-11-16: *"move all the historical data past a certain point to my
laptop and just keep what was needed in Supabase"*, and of the exact repeats:
*"keep it in the archive on my computer"*.

**Measured that day** (`pg_total_relation_size`; shares from the PC copy):

- The database is 101.75 GB: player props 40.0, game odds 23.1, NFL odds history 8.8, play-by-play about 7.0.
- **Exact repeats are the biggest share.** A repeat is a row with the same line and price as the same book's row before it.
  - Props: 66.0% of rows (about 26.4 GB).
  - Game odds: 53.8% (about 12.4 GB).
- **A 90-day cutoff by itself moves about 30 GB**, because props are 87.7% recent.

**The tool:** `scripts/archive_rows.py`. A game's rows leave Supabase only after five checks:
1. The PC copy picks them and writes a Parquet file under `betting_local_copies\archive`.
2. The file is read back and matches.
3. It is uploaded to the private Storage bucket `archive` and read back byte for byte.
   Storage refuses one object over its file-size limit (it refused 52.9 MB and 70.5 MB files on 2026-11-16), so a file over 40 MB goes up in parts (`<file>.part-001`, `-002`, ...). The parts, joined, must hash to the file.
4. In one transaction, Postgres picks the same rows by the same rule, with the same count and fingerprint.
5. The ledger `archive_batches` records it.

Each kept row is the opener or the close of its proposition. A rung of an alternate line is its own proposition.

**What reads old rows** (an audit of every production reader, 2026-11-16). Only the prop repeats can move today. `archive_rows.ALLOWED` and `REFUSED` enforce that.

| Move | Blocked by | What unblocks it |
|---|---|---|
| Prop repeats | moved 11-16 and 11-17; the 2026-11-18 audit then found the app's "At pick" price (#1458) and research replays (below) | allowed in the tool; nothing scheduled runs it |
| Game-odds repeats | The 2026-11-18 audit, below: the app's line history for past picks, the first-half CLV close, the NCAAB spread and moneyline builds, the MLB market-movement feature, the paid in-play buyers, the NFL cache import, and research scripts that rebuild fetches or measure price age | those readers read the archive too (the one history reader, section 3c); the buyers and importers take a ledger |
| Older than 90 days, both tables | Teams board (the ±1.5 run line close is not the only `spreads` row of a game); CLV's same-line close; BYOM's lock candidates; `v_nhl_player_prop_odds`; `team_period_results`; the app's line charts | the opener/close table keyed with the line (section 3b), and those readers moved to it |

**The re-buy (#1384) counts archived rows as held.** Its planner finds thinned games by counting rows per line. It now counts the archive too, so it does not buy back what is on the PC.
- Props: `odds_rebuy.prop_history`.
- Game odds, from 2026-11-18: `odds_rebuy.odds_history`, used by the game, extra-market and in-play plans. Without it, a game whose other books' repeats were archived would drop to `THIN_MAX_ROWS` rows a line and be bought again.

**Game-odds repeats stay in Supabase (reader audit, 2026-11-18).** mike asked that day for the odds table to be done the same way as props. Measured on the PC copy that day:
- 28,198,332 of the 59,301,354 `odds` rows (47.6%) are repeats, for games that started over 3 days ago.
- 23,828,919 of them fall outside the four readers the 11-16 audit named.
- A second audit read every reader of `odds` on `origin/master`.
  - Protecting what its readers touch, in whole groups, leaves 1,279,329 repeats (2.2% of the table). The groups were every game with a pick, all NCAAB and NBA pre-game rows, all MLB in-play rows, NCAAF paid history, and NHL moneyline paid history and 3-way rows.
  - That figure counts 596,699 NFL cache-import rows the keep list now holds.
  - A finer keep list would free more; that is not measured.
- Nothing moves until the readers read the archive too. The readers went from 4 to more than 14 in two days, and the prop move already changed an app screen (below).

What the audit found reading those rows, by what breaks:
- **The app (production).** The line-history card for a past pick shows "At pick" only when the book's last stored row before the pick is within 6 hours of it (`AT_PICK_MAX_MS`, `mobile/src/lib/lineMovementView.ts`). A repeat is the row that keeps a standing price inside those 6 hours.
- **First-half CLV (production).** `tracking/paper_tracker._closing_odds` reads the NCAAB first-half close from a row on the pick's line after the pick. When the line moves later, only repeats sit on that line after the pick. The backfill reaches 7 days back.
- **NCAAB builds (live models).** `scripts/ncaab_spread_market_build.py` and `scripts/ncaab_moneyline_build.py` read each book's rows in the hour before 15:00 UTC (`models/ncaab_book_quotes.py`). A book whose price stood still in that hour drops out.
- **Buyers and importers.**
  - The re-buy planner: now fixed, above.
  - `data/ingestors/nfl_odds_cache_import.py` resumes on stored served times.
  - `data/ingestors/ncaab_odds_history.py` replays dedupe on the exact stamp.
  - `data/ingestors/ncaaf_derivative_history.py` buys a game at a pull only if the game holds a row from it.
- **Research.** `scripts/ncaaf_search/steam_lag.py`, `scripts/nhl_moneyline_rebuild.py`, `scripts/nhl_regulation_game_day_grade.py`, `scripts/live_inning_gate_replay.py`, `scripts/nba_research_cache.py` / `scripts/nba_game_harness.py` and `models/backtester.py` rebuild fetches, need a row inside a window, or measure how long a price stood.

**Not checked:** the rule's "row before it" ignores `source`, so a reader that filters on `source` can see a different row before a repeat. The safe verdicts for readers that filter on `source` are not verified.

`scripts/archive_rows.py` keeps the code for this: `_ODDS_KEEP` (the rows a reader needs whole), `prepare_range` (every date from one pass of the copy) and `--batch-rows` (small games together, each still checked on its own). Its `REFUSED` entry blocks the move.
- **Never run against Postgres:** the batched removal. Its first use should be one date, with the row counts and the ledger read back before `--pending`.
- **The odds table holds 85,666 games against 1,007 for props,** so removing one game a transaction would take about 38 hours.

**The prop move cost past prop picks their "At pick" price (measured 2026-11-18).** The same app rule reads `player_prop_odds`.
- **Measured:** 77,435 pre-game prop picks are on games whose repeats were archived. On the PC copy plus the archive files, 74,913 had a row at the pick's book within 6 hours before the pick. On the PC copy alone, as Supabase now is, 70,266 do. So up to 4,647 cards lost "At pick" and now say the book's newest price is from before the pick.
  - In 4,613 of those, the row left before the pick holds the locked line and price, so the card would otherwise have shown it.
  - On five sampled picks, the app's own read on live Supabase (the newest 500 rows) put the last row before the pick 6 h 2 min to 9 h 10 min back. The archive holds a row with the same prices 1 min 50 s to 1 h 2 min before each pick.
- **How it was counted** (the PC copy and the archive files, read-only):
  - the pick's book is `decision_book`, else DraftKings;
  - the market comes from the app's model-to-market map;
  - the player comes from the label.
  - It ignores the card's 500-row cap.
- **The prop CLV close is unaffected:** it is the newest row before the start.

**The prop readers, audited after the move (2026-11-18).** It ran on `origin/master` at c1e4240c.
- **How the rule keeps rows.** The kept "close" is the last pre-game row of the proposition, of whatever type. The repeat check runs per type.
  - NHL files its last pre-game pull as `close` (`nhl_prop_odds_ingestor.py`), and so does NBA for games with a bet (`nba_prop_close_ingestor.py`).
  - So for those props, the last `open` row can have moved, and so can `open` repeats after the start.
- **Production:**
  - The "At pick" card (#1458).
  - The app's divider, "Some prices after your pick not shown", now shows less often. That is harmless.
  - `latest_prop_odds_recompute`, live in the catalog, takes alternate-line rows at `MAX(snapshot_at)`. It runs only from the update trigger or a manual rebuild of `latest_prop_odds`. For a past game whose newest row is a moved post-start `open` repeat, only the rungs that changed at that instant would survive.
- **Research, when replayed on past games against the database:**
  - `models/nfl_prop_market.drop_pulled_quotes` (a price over 30 minutes behind the book's newest row reads as pulled);
  - `models/nfl_prop_injury_veto` (the quote's time is now the start of the unchanged run);
  - `scripts/nfl_edge_cache.py` with `nfl_edge_prop_market_floor.py` (a bucket with no change has no row);
  - `scripts/nhl_prop_card.py` and `nhl_props_card.py` (the newest `open` fetch);
  - `scripts/nhl_prop_ev_lab.py` (its "close" is the newest `open` fetch).
  - Live runs read unstarted games and are unchanged.
- **Could re-insert moved rows:** `scripts/restore_sharp_prop_history.py`, a manual script. It anti-joins on the exact stamp.
- **Unchanged** (the price as of a time, the first row, unstarted games, or bought single snapshots): the scorer, the prop CLV close, BYOM prop facts and lock candidates, the NBA prop models and their training, and the ingestors' existence checks.

**Running it** (from the repo, with `SUPABASE_SERVICE_ROLE_KEY` in `.env`):

```bash
python scripts/archive_rows.py run --table player_prop_odds --rule repeat --start 2026-03-01 --end <3 days ago>   # prepare and upload, any time
python scripts/archive_rows.py remove --table player_prop_odds --rule repeat --pending                         # 01:30-05:30 ET only
python scripts/archive_rows.py status
```

**When it touches Supabase.** Only step 4 reads Postgres, and only between 01:30 and 05:30 ET. Inside that window it also pauses for the hourly refresh pass and while more than 6 other statements are running.
- Preparing (steps 1 and 2) reads the PC copy alone. `--check` adds a Postgres check, but step 4 makes the same check anyway.
- A game whose removal runs past 900 s is noted in the ledger and tried again the next night.
- A game where Postgres and the file disagree is refused and noted. It is prepared again after the next copy.

**Why (measured 2026-11-16).** The database server is small for what it holds. It has 256 MB of shared buffers and a 60-connection limit, and it holds 101 GB.
- Supabase's compute table gives a 60-connection limit only to its two smallest sizes, with 0.5 GB and 1 GB of memory.
- It recommends at most 10 GB of data for the 1 GB size.
- The dashboard's compute page would confirm which size this is. At 02:28 ET on 2026-11-18 it read Medium, with 13 of 120 connections in use.
- A game's prop rows come off disk at 650-2,300 rows a second: 45,000 rows in 70 s, 340,000 in 148 s.
- The daytime prepare pass also checked every game in Postgres, from 09:00 to 13:50 ET.
- The project logged 178 statement timeouts in those hours, 79 of them reads from the app. That compares with at most 5 an hour in the 18 hours before the pass, and none after it stopped.
- So nothing in this tool reads Postgres in the daytime.

**Getting the space back: the props table was rewritten online on 2026-11-18 (measured).** Removed rows leave their space inside the table file until the table is rewritten.
- **What was used:** `pg_repack` 1.5.2, not `archive_rows.py reclaim`. `reclaim` runs `VACUUM FULL`, which blocks every read and write of the table for the whole rewrite. `pg_repack` holds that lock only for a moment at the start and at the swap.
- **When:** 02:29 to 02:55 ET. The copy took about 10 minutes and the 5 indexes about 16.
- **Result:** the props table's data went from 26.05 to 10.73 GB, and its indexes from 4.37 to 4.33 GB. The whole database went from 93.34 to 78.01 GB. The dashboard read 81.55 GB used of 135 afterwards, including 3.3 GB of write-ahead log.
- **Disk headroom:** database plus log peaked at 112.14 GB, 17.8 GB over where it started. That is the new table plus its indexes, plus the log grown to 4 GB (its `max_wal_size`).
- **Checks:** a count and checksum of the 37,193,430 rows up to ID 121,946,715, the 17:49 baseline on 11-17, matched before and after.
  - The 1.15 million rows written after that baseline (IDs up to 123,097,605) were not checksummed before the rewrite.
  - Triggers, the anon read rule, permissions and all 5 indexes were unchanged. The 3:15 refresh pass's 21,218 new rows all reached `latest_prop_odds`. There were no app errors and no failed app reads in any 5-minute window.
- **Not tested:** rows arriving mid-run. None arrived: the last ID stayed at 123,097,605 from 02:28 to 03:17, and the change log table stayed empty. So nothing here shows how a run behaves on `odds`, or at a busier hour, while rows are being written.

**`odds` gives back nothing from a rewrite until rows leave it** (2026-11-18).
- A 0.2% block sample holds 34.2 live rows a page, against 34 for a packed page at its 228-byte average row.
- Dead rows: 107,448 of 59.5M.
- Its indexes can shrink, by `REINDEX CONCURRENTLY` as on props (#1345).

**How to run it again:**
- **The client must match the database extension exactly.** The extension is 1.5.2, and that is the highest version Supabase offers. The PostgreSQL apt repository the image uses (PGDG) has 1.5.3, which refuses to run: "program 'pg_repack 1.5.3' does not match database library 'pg_repack 1.5.2'". `scripts/pg_repack_helper.sh` builds 1.5.2 from the upstream source tag when apt has no exact match.
- **Where it runs:** a temporary Railway service. Image `postgres:17-bookworm`, restart policy NEVER.
  - Variables: `DATABASE_URL=${{worker.DATABASE_URL}}`, `REPACK_TABLE`, `REPACK_MODE` (`dry` first, then `run`), and `REPACK_SH`.
  - `REPACK_SH` is the script in base64. Encode it from the committed file, `git show HEAD:scripts/pg_repack_helper.sh | base64 -w0`, because a Windows checkout carries CRLF line endings.
  - Start command: `bash -c 'echo "$REPACK_SH" | base64 -d > /tmp/r.sh && exec bash /tmp/r.sh'`. Create it live, not staged: Railway's pending-changes list holds old worker settings, and committing it would push them too.
- **Connection:** it uses port 5432, Supavisor's session pooler. Flags: `-k --no-order --no-kill-backend --wait-timeout=120`.
- **Guard:** start `python -m scripts.pg_repack_guard --table <t> --abort-gib <line>` before the rewrite. Set the line under the disk's auto-grow point, which is 90% of the disk. It cancels the rewrite from SQL, and `pg_repack` then removes its own trigger and copy tables. That was rehearsed twice on `nfl_live_prop_snapshots`.
- **Never stop it from Railway.** A redeploy or delete mid-run kills the client before it cleans up, which leaves a trigger on the table.
- **Finding its connections:** Supavisor rewrites `application_name`, so they are found by what they run.
- **When to run it:** after the 02:15 refresh pass, never inside :15 to :28 past the hour, and finished before 05:40. The rebuild was moved off the evening of 11-17 because the dashboard's disk speed allowance read 8% after that day's work. On 11-18 the day's point read 99%.
- **Free space needed:** the new table plus its indexes, plus up to 4 GB of log.
- **Delete the service afterwards.** A restart would run the rewrite again.

The disk itself shrinks only at a Supabase project upgrade, to 1.2x the database ("Manage disk size", Supabase docs).
