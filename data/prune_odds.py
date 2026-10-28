"""
prune_odds.py — retention for line-shopping (non-DraftKings) odds snapshots.

Why this exists
---------------
Both odds tables are append-only: every refresh pass writes a new snapshot row,
~21 per proposition per day (~42 passes/day). For DraftKings that history is
load-bearing — it powers the line-movement card, closing-line/CLV capture, and
opening signals. For the line-shopping books it is NOT: the only readers of
non-DK rows are `v_latest_odds_all_books` and `v_latest_prop_odds_all_books`,
which are DISTINCT ON (…, bookmaker) and therefore only ever return the NEWEST
row per proposition per book. Every older non-DK row is written once and never
read again.

Going from 2 books to 5 took prop writes from ~39K to ~195K rows/day (~92 MB/day,
~2.7 GB/month) against a ~2 GB database. This job bounds that: non-DK rows are
kept only while they can still be read, which turns unbounded growth into a flat
working set of roughly one day's snapshots.

What is deleted (and what is never touched)
-------------------------------------------
NEVER deleted, under any setting:
  * `draftkings`    — the book the models score against; its history feeds
                      line movement, CLV, and opening signals.
  * `sbr_consensus` — synthetic historical lines that the feature engines
                      whitelist for TRAINING. Deleting these would silently
                      degrade model training data.

Deleted, for line-shop books only:
  1. Games older than `keep_days` → every non-DK row EXCEPT the OPENER and the
     CLOSE (the last pre-game snapshot at or before the game's start, below)
     per (game, market, [player], book).
  2. Games before today but inside the window → every non-DK row EXCEPT the
     latest per (game, market, [player], book), which is the only one the
     views can return, plus the opener and the close.

Today's and future rows are left completely alone, so this can never race with
an in-flight ingest or blank out the live line-shopping board.

The close is retained as of 2026-09-03 (mike: "keep one non-dk snapshot per
day"). It is what makes Stage 2's re-sweep reconstructable for propositions that
never got a scored row, and it is the "did the best book beat DK at close?"
feature the caveat below used to warn about. Cost, measured: about +6 MB/day
against the ~210 MB/day that keeping everything would cost.

The close is bounded on the game's start as of 2026-10-26 (mike approved:
"2) yes"). Until then it was the last row TYPED pre-game, and the evening
refresh writes `open` rows after the start: the bulk /odds endpoint returns
events already under way, and run_odds_ingestor does not relabel them (only
the historical purchases call odds_ingestor._mark_in_play:
run_historical_odds_range and nba_odds_history; relabel_in_play is a repair
job run on demand). So the kept close was
routinely a price from after kickoff. Measured 2026-10-26 on
the 44 NCAAF games of 2026-10-24 that hold Pinnacle and FanDuel rows (game
dates inside the window, so already thinned to opener, close and newest):
Pinnacle still had a price from the last hour before kickoff on 4 of 44 games
in spreads and totals and 6 of 44 in h2h; FanDuel on 0 of 44 in every market,
and every FanDuel game kept a pre-game-typed row stamped after the start. Now
the close is the last pre-game row at or before data.first_pitch's cutoff
(the trusted first pitch, else the scheduled start); a game with no start
time keeps the old rule. The opener and Tier 2's newest row are not bounded.

The latest-line tables (latest_odds, latest_prop_odds) have no DELETE
trigger, on the ground that this job always keeps a key's newest pre-game row
(data/migrations/latest_line_state_tables.sql). Since this change it does not
when that row is after the start. The state row keeps its prices, the same
post-start price it showed before, and its id names a deleted row. Checked
2026-10-26: no view or module joins those ids back to the log, and the ladders
had already broken the same claim (NFL_2026_06_ARI_LA
player_pass_yds_alternate: williamhill_us holds 38 state rows, and only 2 of
their source rows survive the prune).

NBA and NCAAB keep their whole price path (NBA 2026-10-17, NCAAB 2026-10-26):
the two tiers skip every `PATH_KEPT_SPORTS` row, and `thin_repeats` deletes
only the middle of an unchanged run, keeping the row where each book moved and
the last row it held. The thinning never touches the books above either, nor a
`cfbd…` archive book (it did until 2026-10-20: it filtered on source alone).

Caveat: pruned history is still gone permanently, and what survives is TWO rows
per proposition per book, not a series. Anything needing intraday non-DK
movement must raise `keep_days` BEFORE relying on it.

How it runs: one proposition per statement (2026-10-20)
-------------------------------------------------------
Every statement touches ONE proposition: one (game, market) in `odds`, one
(game, market, player) in `player_prop_odds`, read through the index that leads
with those columns, and each DELETE is its own committed transaction. The keep
rules partition by (proposition, book), so one proposition's keepers depend on
nothing outside it: on the rows a run visits, running the rules a proposition
at a time keeps and deletes exactly the rows the whole-table statements did,
except among rows of one book that share a timestamp: which of those survives
is now decided by id (it was arbitrary), and when the close and the newest row
tie, one row can now serve as both, where the old ordering might keep two.

Over time it can keep MORE than the whole-table version, never less. A settled
date is not revisited, so a row written later onto a game of a settled date, or
a game whose date moves onto a settled date, stays where the whole-table
version, which re-read every past game daily, would have thinned it.

Why: the whole-table version stopped completing. Measured 2026-10-20 (Railway
logs and the production catalog): every daily run since at least 10-14 died
189 s into the step on "canceling statement due to statement timeout" (the
server's statement_timeout is 120 s). Its first statement was a COUNT over the
whole of `odds` (31.4M rows, 13 GB); its second computed the keep set with a
window over every prunable row of every past game (planner: a sort of ~18.9M
rows, cost 9.69M). And it had stopped working long before the logs reach:
2026-09-01's games hold 2.0 prunable rows per (game, market, book), 09-03's
hold 400. So from 09-03 nothing was thinned in either table, and the prop
table, pruned only after `odds` succeeds, was never reached.

What one run does, per table, in this order (dates are GAME dates):
  A. Settle the newest game date that has left the window, plus any a missed
     run skipped, as Tier 1.
  B. Tier 2 for the dates inside the window.
  R. Retry the settled dates an earlier run left unfinished. After A and B,
     so units that keep timing out (120 s each) can never spend the budget
     the newest dates need.
  C. The backlog: walk back from the oldest settled date toward
     BACKLOG_FLOOR, a date at a time.
A statement that times out or loses its connection (listing a date's games or
a game's propositions included) is rolled back and logged, and the rest of
the date carries on. The date then goes on a retry list and the walk moves
past it, so one unit that always fails costs its own date, not every date
after it. It leaves the list only on a run where all of it succeeds. Every
such failure, and a progress record that cannot be read (that table is
skipped for the run), makes the run raise once both tables have had their
turn, so the pipeline step is marked failed.

A run stops starting new statements when its budget (PRUNE_RUN_SECONDS of wall
time, PRUNE_RUN_ROWS deleted, per table; PRUNE_THIN_SECONDS for the path
thinning) is spent, and carries on from the same place the next day. Which
dates are finished, and which are waiting for a retry, is stored in Supabase,
in a `job_heartbeats` row per table (FRONTIER_JOB_PREFIX + table), so a run
never re-reads a date it has already finished.

The `odds` prune does not visit the games of a `PATH_KEPT_SPORTS` sport: its
row filter never deletes their rows, so each visit read every row of every
market and deleted nothing.

BACKLOG_FLOOR is where the backlog starts, not a retention limit: dates before
it were thinned while the pruner still worked, and the walk does not re-read
them. Unlike the whole-table version, nothing older than the floor is
revisited, so rows written later onto old games are kept. Measured 2026-10-20:
paid NFL history (source `nfl_odds_cache|served=…`, written 2026-09-12) and
`odds_api_nhl_prop_history` (written 2026-09-20) sit on 2025 games with sources
the list below does not name. The whole-table version would have thinned them
on its first successful run.

Usage:
    python -m data.prune_odds                 # prune with config defaults
    python -m data.prune_odds --dry-run       # count what WOULD be deleted
    python -m data.prune_odds --keep-days 5
"""

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ODDS_API_BOOKMAKER, PRUNE_NON_DK_KEEP_DAYS, SHARP_BOOKMAKERS
from data.db import ConnectionLost, DBConnection, get_connection, statement_timeout
from data.first_pitch import pregame_cutoff_sql
from data.ingestors.odds_ingestor import HISTORICAL_ODDS_SOURCE

# Books whose snapshots must never be pruned. draftkings = the scoring book;
# sbr_consensus = synthetic historical lines used by the feature engines;
# config.SHARP_BOOKMAKERS = market makers whose de-vigged price a model READS.
#
# The sharp books are the 2026-08-31 addition and the distinction is the point.
# A line-shop book's history really is disposable -- only its newest row is ever
# read, to stamp a best price. A sharp book's history is a model INPUT, so
# pruning it deletes the evidence the model is built on. Pinnacle MLB prop
# capture began 2026-08-27; at two-day retention most of it would have been
# thinned before there was enough to validate anything against.
PROTECTED_BOOKMAKERS = (ODDS_API_BOOKMAKER, "sbr_consensus")

# Books protected in ONE table only, because the reason to keep them is
# table-specific (2026-08-31, mike).
#
# config.SHARP_BOOKMAKERS are market makers whose de-vigged PROP price is a
# model input (models/mlb_prop_market, models/nfl_prop_market). Their prop
# history is the evidence those models are built and validated on, so pruning
# it deletes the evidence -- and MLB Pinnacle capture only began 2026-08-27,
# so there is barely any.
#
# They are deliberately NOT protected in `odds`. There the retention rationale
# still holds in full: nothing reads a sharp book's game-level history, and at
# roughly 21 snapshots per proposition per day a blanket protection would put
# back most of the storage the policy exists to save. The narrower carve-out
# gets the model what it needs without undoing that.
PROTECTED_BY_TABLE: dict[str, tuple[str, ...]] = {
    "player_prop_odds": tuple(SHARP_BOOKMAKERS),
}


def _prop_reference_books() -> tuple[str, ...]:
    """Every book a prop model uses as its DE-VIG REFERENCE, from the models.

    DERIVED, NOT RETYPED, and that is the whole point. config.SHARP_BOOKMAKERS
    defaults to "pinnacle" alone, so when betonlineag was added as a second
    reference on 2026-09-08 the protection did not follow it -- the list that
    decides what a model READS and the list that decides what SURVIVES were two
    separate declarations, and only one of them was updated.

    What that cost, measured 2026-09-08: `player_prop_odds` holds pinnacle NFL
    prop rows only from 2026-04-01, and betonlineag NFL `open` rows only from
    2026-09-09. Every earlier sharp snapshot -- the 2023-2025 history the
    market-relative rule's entire record is measured on -- survives ONLY in the
    tracked parquet at data/local/nfl_prop_odds.parquet. Refreshing that cache
    from the database overwrote it with a board that had no 2025 sharp quotes at
    all, and the rule promptly graded negative. The finding was an artefact of
    the deletion, not a result.

    Still live at the time of writing: the NCAAF season backfill's 13,821
    betonlineag t24 rows (38,979 credits) sat unprotected in the same way.
    """
    try:
        import models.nfl_prop_market as _nfl
    except Exception:                                   # noqa: BLE001
        return ()
    return tuple(getattr(_nfl, "SHARP_BOOKS", ()) or ())


def protected_for(table: str) -> tuple[str, ...]:
    """Every book that must survive pruning IN THIS TABLE."""
    extra = PROTECTED_BY_TABLE.get(table, ())
    if table == "player_prop_odds":
        extra = extra + _prop_reference_books()
    return PROTECTED_BOOKMAKERS + tuple(dict.fromkeys(extra))

# Bookmaker PREFIXES that must also survive pruning. CFBD archive lines
# (cfbd_draftkings, cfbd_bovada, cfbd_consensus, …) are historical TRAINING
# data: single-snapshot rows on long-finished games — exactly the shape Tier 1
# deletes. The 2026-08-22 lesson: the first NCAAF lines backfill (47,204 rows)
# was wiped by the next 6am worker run because these labels were not protected.
# Any future sport's read-only archive lines should use a prefix listed here.
PROTECTED_BOOKMAKER_PREFIXES = ("cfbd",)

# Row SOURCES that must survive pruning in `odds` (the one table with the
# column). The historical-endpoint backfill stamps its rows with
# HISTORICAL_ODDS_SOURCE, and those rows are paid movement data on games that
# are by definition older than the retention window -- exactly the shape
# Tier 1 deletes. The 2026-09-01 MLB backfill (three declared jobs, ~31k
# credits, two snapshots a day) was reduced to ONE row per proposition per
# non-DK book by the next 6am prune; measured 2026-09-07, session 252:
# pinnacle / bovada / fanduel at 1.00 rows per (game, market) for May 2024.
# Nothing protected them because nothing named them. Now something does.
#
# Three LADDER sources join it (2026-10-19), and the paid NBA alternate ladders
# (nba_odds_history.ALT_SOURCE) on 2026-10-21. The keepers below are one row per
# (game, market, book) with no line, so a market a book quotes at many lines
# in one fetch (team totals, alternate totals, half and quarter lines) would be
# thinned to one or two arbitrary rungs per game: the paid NBA derivative and
# NHL totals purchases (data/ingestors/nba_odds_history.DERIV_SOURCE,
# nhl_derivative_odds_history.SOURCE), and the live NBA team-total feed
# (data/ingestors/nba_team_total_odds.SOURCE), whose alternates, decision
# fetches and closes are nba_team_total_luck's record. Literals here, pinned to
# the writers' constants by tests/test_nba_team_total_odds.py
# (test_the_prune_protects_every_ladder_source_by_its_writer_s_own_name), so
# the pruner does not import the purchase modules.
#
# The two NCAAB literals (2026-10-26) are the stamps the NCAAB history purchase
# writes on its derivative closes and opens: paid rows on games that are past
# the window by the time they land, the shape Tier 1 deletes. They are named
# here before that writer exists so its first run cannot be thinned by the
# next 6am prune, as the 2026-09-01 MLB backfill was.
PROTECTED_SOURCES = (HISTORICAL_ODDS_SOURCE,
                     "odds_api_nba_derivative_history",
                     "odds_api_nba_alt_history",
                     "odds_api_nhl_totals_history",
                     "odds_api_nba_team_totals_live",
                     "odds_api_ncaab_derivative_close",
                     "odds_api_ncaab_derivative_open")

# Sports whose `odds` rows keep their whole PRICE PATH (2026-10-17, mike: "We
# need nba spread / ml / totals models ... find edge"; docs/nba_models_2026.md
# §6.5). The game-market search needs 2026-27 as a season nobody has looked at,
# with the movement that the opener-and-close survivors cannot show: when each
# book moved, and from what. So the two tiers below never touch these sports'
# rows, and thin_repeats() removes only rows that say nothing new.
#
# Cost, measured 2026-10-17 on 2026-10-15's NBA rows (46 games listed, 10
# books): 33,654 rows a day, of which 1,337 were a price or line differing from
# the same book's previous row (642 of them the first row of a proposition).
# Keeping each run's first and last row is about twice the change count; the
# rest are exact repeats.
#
# NCAAB joins it for its first season (2026-10-26, first game 2026-11-01), so
# that season keeps when each book moved and from what, as the NBA's does. A
# season thinned to opener and close cannot be put back.
PATH_KEPT_SPORTS = ("NBA", "NCAAB")


def _unprotected(params: dict, table: str | None = None) -> str:
    """
    SQL predicate selecting PRUNABLE bookmaker rows; extends `params` with the
    prefix patterns it references. One definition so the counts and both delete
    tiers can never disagree about what "protected" means.

    `table` adds that table's own protected books (see PROTECTED_BY_TABLE).
    Omitting it protects only the global set -- callers that prune a specific
    table must pass it, or a sharp book's history is deleted despite the
    carve-out.
    """
    if table is not None:
        params["protected"] = protected_for(table)
    clauses = ["bookmaker NOT IN %(protected)s"]
    for i, pfx in enumerate(PROTECTED_BOOKMAKER_PREFIXES):
        key = f"protected_pfx_{i}"
        params[key] = pfx + "%"
        clauses.append(f"bookmaker NOT LIKE %({key})s")
    # Only `odds` has a `source` column (player_prop_odds does not, checked
    # against the live schema 2026-09-07); referencing it there would abort
    # the prop prune. Live rows carry NULL and stay prunable; the one live
    # feed with a marker, the NBA team totals, is a ladder (PROTECTED_SOURCES).
    if table == "odds":
        params["protected_sources"] = PROTECTED_SOURCES
        clauses.append("(source IS NULL OR source NOT IN %(protected_sources)s)")
        params["path_kept_sports"] = PATH_KEPT_SPORTS
        clauses.append("(sport IS NULL OR sport NOT IN %(path_kept_sports)s)")
    return "(" + " AND ".join(clauses) + ")"

# (table, identity columns that define one "proposition", a row's GAME date)
#
# Retention is keyed on the GAME's date, never the snapshot's. That matters for
# UFC/golf, which are priced up to 7 days ahead: dating by snapshot would prune
# a future event's only line-shop row.
#
# `player_prop_odds` carries game_date on the row. `odds` has no date column at
# all (only snapshot_at), so a row takes its game's date from `games`, as
# v_latest_odds_all_books does. The prune visits `odds` a game at a time, so
# that date is known before the statement runs and is bound as %(game_day)s:
# a game's rows were Tier 1 or Tier 2 by `games.game_date` before, and are now.
_TABLES = [
    ("odds", ("game_id", "market"), "%(game_day)s"),
    ("player_prop_odds", ("game_id", "market", "player_name"), "game_date"),
]

# The first game date the backlog walk will not go below. Measured 2026-10-20
# on production, prunable rows per (game, market, book): `odds` 2026-09-01 2.0
# (540 rows), 09-02 2.7, 09-03 400 (336,858 rows); `player_prop_odds` per
# (game, market, player, book): 09-01 2.0, 09-02 2.0, 09-03 21.5 (174,946
# rows). Older dates sampled (2026-05-15, 06-15, 08-15, 08-28) sit at 1.0, the
# opener-only rule of the time. So the backlog runs from 09-03; 09-01 is the
# floor so the last two dates the old pruner half-finished are settled too.
BACKLOG_FLOOR = "2026-09-01"

# Per-run budget, PER TABLE. Checked before each date, each game and every
# statement (the listing ones included), so a run ends within the one
# statement in flight when it runs out. The largest units a 0.5% block sample
# of production turned up on 2026-10-20, which is not a proven maximum: in
# `player_prop_odds`, WNBA_2026-10-17_ATL_GSV player_points_alternate for
# Gabby Williams, 23,752 rows; in `odds`, MLB_2026-09-04_DET_CLE h2h, 53,687
# rows. Neither was timed. (One of 17,645 prop rows was read and ranked in
# 2.05 s, measured the same day.) Env-overridable: a Railway variable takes
# effect on the next deploy; the run's log line gives rows per second to tune
# it from.
# Timing: 600 s a table plus the thinning's 300 s is at most 25 minutes, plus
# the statement in flight on each budget (at most 120 s each, the server's
# statement_timeout). The 6am ET daily finished 10:24-10:28 UTC in
# mid-October with the prune failing fast, so it ends by about 7:00am ET at
# the worst, before pipeline_watch reads it at 7:15am ET.
PRUNE_RUN_SECONDS = int(os.environ.get("PRUNE_RUN_SECONDS", "600"))
PRUNE_RUN_ROWS = int(os.environ.get("PRUNE_RUN_ROWS", "10000000"))
# The path-kept sports' repeat thinning's own wall-time budget, run before the
# two tables.
# A cap, not a measurement: the one measured thinning, a dry run over the
# opening week's 773,041 NBA rows, took 38.9 s for five game dates.
PRUNE_THIN_SECONDS = int(os.environ.get("PRUNE_THIN_SECONDS", "300"))

# Where each table's progress lives: one `job_heartbeats` row per table.
# Not a watched job (tracking/job_heartbeat.MAX_SILENCE does not list it), so
# the watchdog never reads it. `detail` holds {"lo": d1, "hi": d2, "retry":
# [dates]}: every game date in [lo, hi) has been settled as Tier 1 by this
# code, except the dates on `retry`, which had a failed statement and are
# retried first on the next run.
FRONTIER_JOB_PREFIX = "prune_odds_frontier:"

_IS_PRE = "(snapshot_type IS NULL OR snapshot_type <> 'in_play')"

# The game's pre-game cutoff, joined onto every row of the proposition as
# `b.close_by` (2026-10-26). One primary-key read of `games` inside the same
# statement, so a proposition is still one statement (a separate lookup would
# be a statement the budget has to allow for). %(game_id)s is bound in every
# prune statement already. games.game_id is the primary key (checked against
# the live catalog 2026-10-26), so the join can never multiply a row; a game
# with no row, or no commence_time, gives one NULL and the close falls open to
# the rule before this change. The cutoff SQL carries no literal percent sign,
# which psycopg2 would read as a placeholder.
_CLOSE_BY_JOIN = (f"LEFT JOIN (SELECT ({pregame_cutoff_sql('g')})::timestamptz AS close_by"
                  f" FROM games g WHERE g.game_id = %(game_id)s) b ON TRUE")

# A row that may be kept as the CLOSE: pre-game typed AND stamped at or before
# the game's cutoff. Cast, never compared as text: both columns are TEXT, and
# their shapes differ (measured 2026-10-26 on NCAAF 2026-10-24: snapshot_at
# ends 'Z', commence_time ends '+00:00' on 44 games and '.000Z' on 245). As
# text '...T19:00:00Z' sorts after '...T19:00:00+00:00', the same instant.
_IS_CLOSE = (f"({_IS_PRE} AND (b.close_by IS NULL"
             f" OR snapshot_at::timestamptz <= b.close_by))")


def _pk(table: str) -> str:
    return "odds_id" if table == "odds" else "prop_id"


def _day(d: str, n: int) -> str:
    return (date.fromisoformat(d) + timedelta(days=n)).isoformat()


def doomed_sql(table: str, identity: tuple[str, ...], row_date: str,
               prunable: str) -> str:
    """SELECT the rows of ONE proposition that the two tiers delete.

    The proposition is bound by `identity` (%(game_id)s, %(market)s[,
    %(player_name)s]) and read through the index that leads with those columns.

    WHAT SURVIVES A SETTLED GAME: the OPENER and the CLOSE, per (proposition,
    book).

    The opener (2026-08-25): an opening line is not redundant history, it is
    the only record of where a book started, and open->close movement is the
    basis of both CLV measurement and the §28-style opener rules.

    The close (2026-09-03, mike: "keep one non-dk snapshot per day"): an opener
    alone cannot answer either question the retained history exists for — the
    best price available at DECISION time (Stage 2's re-sweep, for propositions
    that never got a scored row: abs(edge) > MAX_EDGE_CAP, and NONE rows
    `cleanup-picks` removes) or "did the best book beat DK at close?", which
    this module's own docstring warned would need exactly this retained BEFORE
    anyone relied on it.

    Cost, measured 2026-09-02 rather than estimated: one day of non-DK rows is
    297,975 in `odds` and 105,105 in `player_prop_odds`, thinning to 2,787 and
    6,594 distinct (proposition, book). A second retained row per proposition
    is about +6 MB/day, against the ~210 MB/day keeping everything would cost.

    ONE SCAN, AND THAT IS LOAD-BEARING. A version with a second anti-join beside
    the opener's stopped completing (`canceling statement due to statement
    timeout`), so every rule here is a window over the one read of the
    proposition's rows: no NOT IN, no second pass.

    The close must never be an in-play price: that is a different proposition
    entirely (CLAUDE.md §6), and keeping one as "the close" would hand every
    later analysis a price from the third inning. Partitioning the DESC ranking
    by the close flag puts candidate rows in their own partition, so
    rn_last = 1 AND is_close is the newest CANDIDATE row rather than the newest
    row that happens to be one. NULL snapshot_type counts as pre-game, as every
    reader treats it.

    A candidate is pre-game TYPED and stamped at or before the game's pre-game
    cutoff (2026-10-26, mike approved: "2) yes"): data.first_pitch's bound,
    the trusted first pitch else the scheduled start, joined in as
    `b.close_by`. Until then the close was the last pre-game-typed row, and
    the evening refresh keeps writing `open` rows after the game starts (§7's
    leak trap), so the kept close was routinely a post-start price (module
    docstring, measured). A game with no start time keeps the old rule: NULL
    fails open. When every pre-game-typed row is after the start, the
    proposition keeps its opener and no close. Run read-only on production
    2026-10-26 (this SELECT, NCAAF_2026-10-24_baylor_kansas h2h, start
    17:02:30Z): FanDuel's `open` row at 20:17Z, the old close, is doomed; its
    opener is now the close; its in-play newest row stays for Tier 2.

    Only the close is bounded. The opener deliberately ranks every row,
    in-play included (a proposition first quoted in play still keeps where it
    started), and rn_newest is the row the live all-books views return, which
    Tier 2 must keep whenever it was written.

    Tier 1 (game date before the cutoff) deletes everything but the keepers.
    Tier 2 (cutoff to today) also keeps the NEWEST row, the one the DISTINCT ON
    views return; rn_newest ranks it among the Tier 2 rows only, as the old
    Tier 2 statement did. Rows of today and later are never selected.

    Ties on snapshot_at (a ladder market writes many rows per book per pass)
    break on the primary key, so which row is "first" is fixed rather than
    whatever order the scan happened to return.
    """
    pk = _pk(table)
    part_by = ", ".join(identity) + ", bookmaker"
    match = " AND ".join(f"{c} = %({c})s" for c in identity)
    return f"""
        SELECT {pk} FROM (
            SELECT {pk},
                   {row_date} AS row_date,
                   ROW_NUMBER() OVER (
                       PARTITION BY {part_by} ORDER BY snapshot_at ASC, {pk} ASC
                   ) AS rn_first,
                   ROW_NUMBER() OVER (
                       PARTITION BY {part_by}, {_IS_CLOSE} ORDER BY snapshot_at DESC, {pk} DESC
                   ) AS rn_last,
                   ROW_NUMBER() OVER (
                       PARTITION BY {part_by}, ({row_date} >= %(cutoff)s)
                       ORDER BY snapshot_at DESC, {pk} DESC
                   ) AS rn_newest,
                   {_IS_CLOSE} AS is_close
            FROM {table}
            {_CLOSE_BY_JOIN}
            WHERE {match}
              AND {prunable}
              AND {row_date} < %(today)s
        ) u
        WHERE NOT (rn_first = 1 OR (is_close AND rn_last = 1))
          AND (row_date < %(cutoff)s OR rn_newest > 1)
    """


def delete_sql(table: str, identity: tuple[str, ...], row_date: str,
               prunable: str) -> str:
    """DELETE one proposition's doomed rows, by primary key.

    The window runs once (`MATERIALIZED`). The DELETE then looks those ids up
    on the primary key and does not repeat the proposition predicate.

    Measured 2026-10-21 on `player_prop_odds`, game `NFL_2026_06_BAL_CLE`,
    market `player_pass_yds_alternate`, player Deshaun Watson (8,284 rows,
    4,819 of them doomed). The previous statement was
    `DELETE ... WHERE game_id = ... AND prop_id IN (SELECT <window>)`.
    Postgres estimated that proposition at 1 row (plan cost 6.22) and ran a
    nested-loop semi join that re-executed the window once per row. The
    server cancelled it at `statement_timeout` (SQLSTATE 57014, query id
    2366139515779304512, 10:43:35 UTC). The window by itself, materialized,
    took 44 ms; primary-key lookups of the doomed ids took 438 ms. Putting
    the proposition predicate back on the DELETE made the planner rescan the
    proposition index once per doomed id (24,484,201 rows rejected by the
    join filter, 8.5 s) — the same quadratic shape, so the DELETE must not
    carry it. The read inside the CTE still names the proposition, and the
    ids it returns are the only rows deleted.
    """
    pk = _pk(table)
    return (f"WITH doomed AS MATERIALIZED ("
            f"{doomed_sql(table, identity, row_date, prunable)}) "
            f"DELETE FROM {table} WHERE {pk} IN (SELECT {pk} FROM doomed)")


def count_sql(table: str, identity: tuple[str, ...], row_date: str,
              prunable: str) -> str:
    return (f"SELECT COUNT(*) FROM "
            f"({doomed_sql(table, identity, row_date, prunable)}) d")


def _distinct(conn: DBConnection, table: str, col: str, fixed: dict) -> list:
    """Every value of `col` under the `fixed` index prefix, in order, by a
    loose index scan: one index probe per value, never a read of the rows."""
    where = " AND ".join(f"{c} = %({c})s" for c in fixed)
    sql = f"""
        WITH RECURSIVE s(v) AS (
            SELECT MIN({col}) FROM {table} WHERE {where}
            UNION ALL
            SELECT (SELECT MIN({col}) FROM {table}
                     WHERE {where} AND {col} > s.v)
              FROM s WHERE s.v IS NOT NULL
        )
        SELECT v FROM s WHERE v IS NOT NULL
    """
    return [r[0] for r in conn.execute(sql, dict(fixed)).fetchall()]


def propositions(conn: DBConnection, table: str, identity: tuple[str, ...],
                 game_id: str, budget: "Budget | None" = None) -> list[dict]:
    """Every proposition one game has in `table`, as identity dicts. With a
    budget, it is checked before each listing statement (one NFL game's props
    take about 23), so a spent budget starts none of them."""
    units = [{identity[0]: game_id}]
    for col in identity[1:]:
        found = []
        for u in units:
            if budget is not None:
                budget.check()
            found += [{**u, col: v} for v in _distinct(conn, table, col, u)]
        units = found
    return units


def _games_on(conn: DBConnection, day: str, skip_sports: tuple[str, ...] = ()) -> list[str]:
    """The games dated `day`, leaving out `skip_sports`. The `odds` prune
    passes PATH_KEPT_SPORTS: its row filter never deletes those sports' rows,
    so visiting their games read every row of every market and deleted
    nothing. A game is skipped by the GAME's sport while the row filter reads
    the row's, so if the two ever disagreed the skip could only keep more
    rows, never delete more."""
    sql = "SELECT game_id FROM games WHERE game_date = %(day)s"
    params: dict = {"day": day}
    if skip_sports:
        sql += " AND (sport IS NULL OR sport NOT IN %(skip_sports)s)"
        params["skip_sports"] = tuple(skip_sports)
    return [r[0] for r in conn.execute(sql + " ORDER BY game_id", params).fetchall()]


class BudgetSpent(Exception):
    """The run's budget is used up; stop starting statements."""


class Budget:
    """Wall seconds and rows deleted, whichever runs out first."""

    def __init__(self, seconds: float | None = None, rows: int | None = None,
                 clock=time.monotonic):
        self._clock = clock
        self.deadline = clock() + (PRUNE_RUN_SECONDS if seconds is None else seconds)
        self.rows_left = PRUNE_RUN_ROWS if rows is None else rows

    def check(self) -> None:
        if self.rows_left <= 0 or self._clock() >= self.deadline:
            raise BudgetSpent()

    def charge(self, n: int) -> None:
        self.rows_left -= max(int(n or 0), 0)


def _frontier_job(table: str) -> str:
    return FRONTIER_JOB_PREFIX + table


class FrontierUnreadable(RuntimeError):
    """The progress record could not be read. The table is skipped for the
    run: treating a failed read as "no record" restarted the backlog from
    scratch and then overwrote the good record with the restarted one."""


def read_frontier(conn: DBConnection, table: str) -> tuple[str, str, list[str]] | None:
    """(lo, hi, retry) for `table`, or None when there is no usable record
    (none stored, or one this code cannot parse). Raises FrontierUnreadable
    when the read itself fails."""
    try:
        row = conn.execute(
            "SELECT detail FROM job_heartbeats WHERE job_id = %(job)s",
            {"job": _frontier_job(table)}).fetchone()
    except Exception as exc:                            # noqa: BLE001
        try:
            conn.rollback()
        except Exception:                               # noqa: BLE001
            pass
        raise FrontierUnreadable(
            f"progress record could not be read, table skipped this run: "
            f"{str(exc)[:120]}") from exc
    if not row or not row[0]:
        return None
    try:
        d = json.loads(row[0])
        lo, hi = date.fromisoformat(d["lo"]).isoformat(), date.fromisoformat(d["hi"]).isoformat()
        retry = sorted({date.fromisoformat(x).isoformat() for x in d.get("retry", [])})
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    return (lo, hi, retry) if lo <= hi else None


def save_frontier(conn: DBConnection, table: str, lo: str, hi: str,
                  retry=()) -> None:
    """Record (lo, hi, retry), committed on its own AFTER every statement of
    the date it describes has committed, so a date is never recorded as
    finished before it is. Best-effort: a lost write costs the next run a
    re-read of dates it had finished (they delete nothing), never a row."""
    try:
        conn.execute("""
            INSERT INTO job_heartbeats (job_id, last_run_at, last_status, detail)
            VALUES (%(job)s, %(at)s, %(status)s, %(detail)s)
            ON CONFLICT (job_id) DO UPDATE SET
                last_run_at = EXCLUDED.last_run_at,
                last_status = EXCLUDED.last_status,
                detail      = EXCLUDED.detail
        """, {"job": _frontier_job(table), "at": datetime.now(timezone.utc).isoformat(),
              "status": "frontier",
              "detail": json.dumps({"lo": lo, "hi": hi, "retry": sorted(retry)})})
        conn.commit()
    except Exception as exc:                            # noqa: BLE001
        logger.warning(f"prune frontier write failed for {table}: {exc}")
        try:
            conn.rollback()
        except Exception:                               # noqa: BLE001
            pass
        # A timeout or a lost connection is retried by the next run's write. Any
        # other error is a bug, and a record that is never written means every
        # run re-walks the same dates with nothing to say so.
        if not (statement_timeout(exc) or isinstance(exc, ConnectionLost)):
            raise


def _absorb(conn: DBConnection, exc: Exception) -> None:
    """Roll back after a failed statement. A timeout or a lost connection is
    the caller's to log and skip past; any other error is raised."""
    try:
        conn.rollback()
    except Exception:                                   # noqa: BLE001
        pass
    if not (statement_timeout(exc) or isinstance(exc, ConnectionLost)):
        raise exc


def _prune_date(conn: DBConnection, table: str, identity: tuple[str, ...],
                row_date: str, day: str, cutoff: str, today: str,
                dry_run: bool, budget: Budget, res: dict) -> bool:
    """Run every proposition of every game dated `day`. True when all of them
    ran. A statement that timed out or lost its connection, the listing of the
    date's games or of one game's propositions included, is rolled back,
    logged, and leaves the date unfinished; the rest of the date carries on.
    The budget is checked before the date, before each game and before every
    statement, so a spent budget starts nothing new."""
    budget.check()
    base: dict = {"cutoff": cutoff, "today": today, "game_day": day}
    prunable = _unprotected(base, table)
    sql = (count_sql if dry_run else delete_sql)(table, identity, row_date, prunable)

    def failed(where: dict, exc: Exception) -> None:
        res["failed"].append({"day": day, **where, "error": str(exc)[:120]})
        logger.warning(f"prune {table} {day} {where}: {str(exc)[:120]}")

    try:
        games = _games_on(conn, day, PATH_KEPT_SPORTS if table == "odds" else ())
    except Exception as exc:                            # noqa: BLE001
        _absorb(conn, exc)
        failed({"listing": "games"}, exc)
        return False
    ok = True
    for game_id in games:
        budget.check()
        try:
            units = propositions(conn, table, identity, game_id, budget)
        except BudgetSpent:
            raise
        except Exception as exc:                        # noqa: BLE001
            _absorb(conn, exc)
            ok = False
            failed({"game_id": game_id, "listing": "propositions"}, exc)
            continue
        for unit in units:
            budget.check()
            try:
                cur = conn.execute(sql, {**base, **unit})
                if dry_run:
                    n = int(cur.fetchone()[0])
                    conn.rollback()
                else:
                    n = max(int(cur.rowcount or 0), 0)
                    conn.commit()
            except Exception as exc:                    # noqa: BLE001
                _absorb(conn, exc)
                ok = False
                failed(unit, exc)
                continue
            budget.charge(n)
            res["statements"] += 1
            res["would_delete" if dry_run else "deleted"] += n
    return ok


def prune_table(conn: DBConnection, table: str, identity: tuple[str, ...],
                row_date: str, keep_days: int, today: str,
                dry_run: bool = False, budget: Budget | None = None,
                floor: str = BACKLOG_FLOOR) -> dict:
    """
    Prune line-shop snapshots for one table, a proposition per statement, in
    four phases (module docstring): A settles the dates that have left the
    window, B thins the window, R retries the dates an earlier run left
    unfinished, C walks the backlog toward `floor`. Stops at the budget.
    Returns a summary dict.

    A date with a failed statement does not stop the walk. It goes on the
    record's retry list and the settled range moves past it; it leaves the
    list only on a run where every statement of it succeeds. Raises
    FrontierUnreadable, before touching anything, when the record cannot be
    read.
    """
    budget = budget or Budget()
    started = time.monotonic()
    cutoff = _day(today, -keep_days)
    rec = read_frontier(conn, table)
    newest_settled = _day(cutoff, -1)
    lo, hi, retry_list = rec if rec else (newest_settled, newest_settled, [])
    hi = min(hi, cutoff)                  # keep_days was raised since
    lo = min(lo, hi)
    # A retry date outside the settled range is walked again by A or C anyway.
    retry = {d for d in retry_list if lo <= d < hi}
    res = {"table": table, "cutoff": cutoff, "dry_run": dry_run, "deleted": 0,
           "would_delete": 0, "statements": 0, "failed": [], "budget_spent": False,
           "frontier_before": rec}

    def mark(new_lo: str, new_hi: str) -> None:
        nonlocal lo, hi
        lo, hi = new_lo, new_hi
        if not dry_run:
            save_frontier(conn, table, lo, hi, retry)

    def settle(d: str) -> None:
        """Settle `d`; a date with a failed statement goes on the retry list."""
        if _prune_date(conn, table, identity, row_date, d, cutoff, today,
                       dry_run, budget, res):
            retry.discard(d)
        else:
            retry.add(d)

    try:
        d = hi                            # A: settle what has left the window
        while d < cutoff:
            settle(d)
            mark(lo, _day(d, 1))
            d = _day(d, 1)
        d = cutoff                        # B: thin the window
        while d < today:
            _prune_date(conn, table, identity, row_date, d, cutoff, today,
                        dry_run, budget, res)
            d = _day(d, 1)
        for d in sorted(retry):           # R: what an earlier run left unfinished
            settle(d)
            if d not in retry:
                mark(lo, hi)
        d = _day(lo, -1)                  # C: the backlog, newest first
        while d >= floor:
            settle(d)
            mark(d, hi)
            d = _day(d, -1)
    except BudgetSpent:
        res["budget_spent"] = True
    res["frontier"] = {"lo": lo, "hi": hi}
    res["retry"] = sorted(retry)
    res["backlog_done"] = lo <= floor
    res["seconds"] = round(time.monotonic() - started, 1)
    return res


# One row's whole quote, as text that compares NULL-safely in Postgres and in
# SQLite (the test stand-in): a NULL renders as an empty field.
_QUOTE_KEY = " || '|' || ".join(
    f"COALESCE(CAST({c} AS TEXT), '')"
    for c in ("home_price", "away_price", "draw_price", "spread_home", "total_line",
              "over_price", "under_price"))

def _thin_book_filter() -> tuple[str, tuple]:
    """The protected books as a positional predicate and its parameters: the
    same books and `cfbd…` prefixes the two tiers never delete (protected_for
    and PROTECTED_BOOKMAKER_PREFIXES), without the tiers' sport exclusion,
    which would skip every row the thinning is for. The prefix patterns are
    parameters, never literals, because a literal percent sign in a
    parameterised statement breaks psycopg2's interpolation."""
    books = protected_for("odds")
    clauses = [f"bookmaker NOT IN ({', '.join(['%s'] * len(books))})"]
    clauses += ["bookmaker NOT LIKE %s"] * len(PROTECTED_BOOKMAKER_PREFIXES)
    return (" AND ".join(clauses),
            (*books, *(p + "%" for p in PROTECTED_BOOKMAKER_PREFIXES)))


_THIN_BOOKS_SQL, _THIN_BOOK_PARAMS = _thin_book_filter()

# ONE (game, market) per statement, bound positionally as (game_id, market,
# *_THIN_BOOK_PARAMS). The window partitions by (game, market, book, pre-game
# or in-play), so a statement per (game, market) keeps exactly what one
# statement over a whole date kept.
#
# Protected books are left out of the window entirely (2026-10-20). The module
# docstring has always said draftkings and sbr_consensus are never deleted
# under any setting, and until then this statement filtered on source alone,
# so it deleted their repeated rows. Leaving a book out of the window cannot
# change what another book keeps: the window partitions by book.
THIN_REPEATS_SQL = f"""
    SELECT odds_id FROM (
        SELECT odds_id, {_QUOTE_KEY} AS q,
               LAG({_QUOTE_KEY}) OVER w AS q_prev,
               LEAD({_QUOTE_KEY}) OVER w AS q_next
          FROM odds
         WHERE game_id = %s
           AND market = %s
           AND source IS NULL
           AND {_THIN_BOOKS_SQL}
        WINDOW w AS (PARTITION BY game_id, market, bookmaker,
                     (snapshot_type IS NULL OR snapshot_type <> 'in_play')
                     ORDER BY snapshot_at, odds_id)
    ) t
    WHERE q = q_prev AND q = q_next
"""

# Every market one game has in `odds`, by a loose index scan on idx_odds_game
# (game_id, market, snapshot_type): one probe per market, never a read of the
# rows. Positional, like the rest of the thinning.
_GAME_MARKETS_SQL = """
    WITH RECURSIVE s(v) AS (
        SELECT MIN(market) FROM odds WHERE game_id = %s
        UNION ALL
        SELECT (SELECT MIN(market) FROM odds WHERE game_id = %s AND market > s.v)
          FROM s WHERE s.v IS NOT NULL
    )
    SELECT v FROM s WHERE v IS NOT NULL
"""


def thin_repeats(conn: DBConnection, today: str, sports: tuple[str, ...] = PATH_KEPT_SPORTS,
                 lookback_days: int = 21, dry_run: bool = False,
                 budget: Budget | None = None) -> dict:
    """Delete the middle of every unchanged run in a path-kept sport's `odds` rows.

    A run is consecutive rows of one (game, market, book, pre-game-or-in-play)
    with the same price and line. Its FIRST row says when the book moved there
    and its LAST says it was still quoting there, so both stay; the rows
    between say nothing either one does not. Lossless for every as-of read:
    "the newest row at or before T" returns the same price before and after.

    Settled games only (game_date < today), ONE (game, market) per statement,
    each committed on its own (2026-10-20). It was one statement for every
    game of a date. Measured that day, before tip-off: NBA_2026-10-20_BOS_DET
    held 77,278 `odds` rows, 25,737 to 25,778 per market (h2h, spreads,
    totals). Eleven games that size would be one statement over ~850k rows,
    against the 120 s statement_timeout.
    A statement that times out or loses its connection, a game's market
    listing included, is rolled back, logged in `failed`, and skipped; the
    next run's look-back still covers its date, so it is retried, never lost.
    Any other error is raised. Paid history (any non-NULL source) and the
    protected books (draftkings, sbr_consensus, `cfbd…`) are never touched.
    The bound is `lookback_days` so the job stays small every day; a date it
    misses is thinned by a wider run.

    `budget` (default PRUNE_THIN_SECONDS of wall time) is checked at the top
    of every game and before every statement, so a run overshoots it by at
    most the statement in flight. Dates go newest first: a spent budget leaves
    the oldest dates, which earlier runs have already thinned, while the
    newest settled date holds a whole day of unthinned rows."""
    budget = budget or Budget(seconds=PRUNE_THIN_SECONDS)
    start = (date.fromisoformat(today) - timedelta(days=lookback_days)).isoformat()
    out = {"sports": list(sports), "since": start, "dates": 0, "rows": 0,
           "statements": 0, "failed": [], "dry_run": dry_run, "budget_spent": False}
    marks = ", ".join(["%s"] * len(sports))
    dates = [str(r[0])[:10] for r in conn.execute(
        f"SELECT DISTINCT game_date FROM games WHERE sport IN ({marks}) "
        f"AND game_date >= %s AND game_date < %s ORDER BY 1 DESC",
        (*sports, start, today)).fetchall()]
    count = f"SELECT COUNT(*) FROM ({THIN_REPEATS_SQL}) s"
    # Same plan failure as delete_sql: `WHERE game_id = ... AND odds_id IN
    # (SELECT <window>)` re-executes the window once per row when the
    # planner estimates one row. The window is materialized once; the DELETE
    # looks the ids up by primary key. The game and market stay on the read
    # inside the CTE, which is what bounds it.
    delete = (f"WITH doomed AS MATERIALIZED ({THIN_REPEATS_SQL}) "
              f"DELETE FROM odds WHERE odds_id IN (SELECT odds_id FROM doomed)")

    def failed(d: str, gid: str, market: str | None, exc: Exception) -> None:
        out["failed"].append({"day": d, "game_id": gid, "market": market,
                              "error": str(exc)[:120]})
        logger.warning(f"thin repeats {d} {gid} {market or 'market listing'}: "
                       f"{str(exc)[:120]}")

    try:
        for d in dates:
            budget.check()
            ids = [r[0] for r in conn.execute(
                f"SELECT game_id FROM games WHERE sport IN ({marks}) AND game_date = %s "
                f"ORDER BY game_id", (*sports, d)).fetchall()]
            if not ids:
                continue
            for gid in ids:
                budget.check()
                try:
                    markets = [r[0] for r in conn.execute(
                        _GAME_MARKETS_SQL, (gid, gid)).fetchall()]
                except Exception as exc:            # noqa: BLE001
                    _absorb(conn, exc)
                    failed(d, gid, None, exc)
                    continue
                for market in markets:
                    budget.check()
                    try:
                        if dry_run:
                            n = conn.execute(
                                count, (gid, market, *_THIN_BOOK_PARAMS)).fetchone()[0]
                        else:
                            n = conn.execute(delete, (gid, market,
                                                      *_THIN_BOOK_PARAMS)).rowcount
                            conn.commit()
                    except Exception as exc:        # noqa: BLE001
                        _absorb(conn, exc)
                        failed(d, gid, market, exc)
                        continue
                    n = max(int(n or 0), 0)
                    budget.charge(n)
                    out["statements"] += 1
                    out["rows"] += n
            out["dates"] += 1
    except BudgetSpent:
        out["budget_spent"] = True
    return out


def run_prune_odds(run_date: str = None, keep_days: int = None,
                   dry_run: bool = False, seconds: float | None = None,
                   rows: int | None = None) -> dict:
    """Prune line-shop snapshots in both odds tables. Safe to run any time.

    The path thinning (PATH_KEPT_SPORTS) runs first, then each table, each on
    its own connection and with its own budget (`seconds`, default
    PRUNE_THIN_SECONDS for the thinning and PRUNE_RUN_SECONDS for each table),
    so a slow or failed one cannot starve the others.

    Raises once both tables have had their turn when any of the three had a
    problem: an error that is not a timeout, a progress record that could not
    be read (that table is skipped), or any statement that timed out or lost
    its connection. Until 2026-10-20 a timed-out statement went into the log
    line only, so a run whose every statement timed out reported success. The
    log lines keep their counts either way."""
    today = run_date or date.today().isoformat()
    keep = PRUNE_NON_DK_KEEP_DAYS if keep_days is None else keep_days

    if keep < 1:
        raise ValueError("keep_days must be >= 1 — pruning today's rows would "
                         "blank the live line-shopping board")

    summary = {"today": today, "keep_days": keep, "tables": []}
    tag = "[dry-run] " if dry_run else ""

    errors = []
    # First, on its own connection and in its own try: neither it nor the
    # table prunes can stop the other. Before 2026-10-20 a raise here left the
    # function before either table was visited, every day it recurred.
    summary["thinned"] = None
    try:
        with get_connection() as conn:
            thinned = thin_repeats(conn, today, dry_run=dry_run, budget=Budget(
                PRUNE_THIN_SECONDS if seconds is None else seconds, rows))
        summary["thinned"] = thinned
        failed = (f"; {len(thinned['failed'])} statements failed"
                  if thinned["failed"] else "")
        spent = "; budget spent" if thinned.get("budget_spent") else ""
        logger.info(f"{tag}path-kept sports {thinned['sports']}: "
                    f"{thinned['rows']:,} repeated rows "
                    f"{'would be ' if dry_run else ''}thinned over "
                    f"{thinned['dates']} game dates in "
                    f"{thinned['statements']:,} statements{spent}{failed}")
        if thinned["failed"]:
            errors.append(f"path thinning: {len(thinned['failed'])} statements failed")
    except Exception as exc:                            # noqa: BLE001
        logger.error(f"{tag}path thinning failed: {exc}")
        errors.append(f"path thinning: {exc}")

    for table, identity, row_date in _TABLES:
        try:
            with get_connection() as conn:
                if not dry_run:
                    try:
                        from tracking.job_heartbeat import ensure_schema
                        ensure_schema(conn)
                        conn.commit()
                    except Exception as exc:            # noqa: BLE001
                        logger.warning(f"prune frontier table check failed: {exc}")
                        conn.rollback()
                res = prune_table(conn, table, identity, row_date, keep, today,
                                  dry_run=dry_run, budget=Budget(seconds, rows))
        except Exception as exc:                        # noqa: BLE001
            logger.error(f"{tag}{table} prune failed: {exc}")
            errors.append(f"{table}: {exc}")
            continue
        n = res["would_delete"] if dry_run else res["deleted"]
        verb = "would go" if dry_run else "deleted"
        backlog = "done" if res["backlog_done"] else "continues next run"
        spent = "; budget spent" if res["budget_spent"] else ""
        failed = f"; {len(res['failed'])} statements failed" if res["failed"] else ""
        retry = res.get("retry") or []
        again = (f"; {len(retry)} game dates to retry ({', '.join(retry[:5])}"
                 f"{', …' if len(retry) > 5 else ''})") if retry else ""
        logger.info(
            f"{tag}{table}: {n:,} line-shop rows {verb} in "
            f"{res['statements']:,} statements over {res['seconds']:,} s; settled game dates "
            f"{res['frontier']['lo']} to {res['frontier']['hi']} (exclusive); "
            f"backlog {backlog}{spent}{failed}{again}")
        summary["tables"].append(res)
        if res["failed"]:
            errors.append(f"{table}: {len(res['failed'])} statements failed")

    if errors:
        raise RuntimeError("; ".join(errors))
    return summary


def main():
    ap = argparse.ArgumentParser(description="Prune non-DraftKings odds snapshots")
    ap.add_argument("--date", help="Treat this date as 'today' (YYYY-MM-DD)")
    ap.add_argument("--keep-days", type=int, default=None,
                    help=f"Days of line-shop history to keep "
                         f"(default {PRUNE_NON_DK_KEEP_DAYS})")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would be deleted, delete nothing")
    ap.add_argument("--seconds", type=float, default=None,
                    help=f"Wall-time budget per table and for the path thinning "
                         f"(default {PRUNE_RUN_SECONDS} a table, "
                         f"{PRUNE_THIN_SECONDS} for the thinning)")
    ap.add_argument("--rows", type=int, default=None,
                    help=f"Rows-deleted budget per table (default {PRUNE_RUN_ROWS:,})")
    args = ap.parse_args()

    run_prune_odds(run_date=args.date, keep_days=args.keep_days, dry_run=args.dry_run,
                   seconds=args.seconds, rows=args.rows)


if __name__ == "__main__":
    main()
