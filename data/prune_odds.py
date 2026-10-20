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
     CLOSE (the last pre-game-typed snapshot) per (game, market, [player],
     book).
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

NBA keeps its whole price path (2026-10-17): the two tiers skip every
`PATH_KEPT_SPORTS` row, and `thin_repeats` deletes only the middle of an
unchanged run, keeping the row where each book moved and the last row it held.

Caveat: pruned history is still gone permanently, and what survives is TWO rows
per proposition per book, not a series. Anything needing intraday non-DK
movement must raise `keep_days` BEFORE relying on it.

Usage:
    python -m data.prune_odds                 # prune with config defaults
    python -m data.prune_odds --dry-run       # count what WOULD be deleted
    python -m data.prune_odds --keep-days 5
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ODDS_API_BOOKMAKER, PRUNE_NON_DK_KEEP_DAYS, SHARP_BOOKMAKERS
from data.db import get_connection, DBConnection
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
PROTECTED_SOURCES = (HISTORICAL_ODDS_SOURCE,)

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
PATH_KEPT_SPORTS = ("NBA",)


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
    # the prop prune. Live rows carry NULL and stay prunable.
    if table == "odds":
        params["protected_sources"] = PROTECTED_SOURCES
        clauses.append("(source IS NULL OR source NOT IN %(protected_sources)s)")
        params["path_kept_sports"] = PATH_KEPT_SPORTS
        clauses.append("(sport IS NULL OR sport NOT IN %(path_kept_sports)s)")
    return "(" + " AND ".join(clauses) + ")"

# (table, identity columns that define one "proposition", how to date a row)
#
# `player_prop_odds` carries game_date directly. `odds` does NOT have a date
# column at all (only snapshot_at), which is why v_latest_odds_all_books joins
# `games` — we do the same here so retention is keyed on the GAME's date, not
# the snapshot's. That matters for UFC/golf, which are priced up to 7 days
# ahead: dating by snapshot would prune a future event's only line-shop row.
_TABLES = [
    ("odds", ("game_id", "market"),
     "game_id IN (SELECT game_id FROM games WHERE game_date {op} %({param})s)"),
    ("player_prop_odds", ("game_id", "market", "player_name"),
     "game_date {op} %({param})s"),
]


def _older_than(date_sql: str, op: str, param: str) -> str:
    """Predicate selecting rows whose GAME date compares `op` to `param`."""
    return date_sql.format(op=op, param=param)


def _counts(conn: DBConnection, table: str) -> tuple[int, int]:
    """(total rows, non-protected rows) — for logging the before/after picture."""
    params: dict = {"protected": PROTECTED_BOOKMAKERS}
    pred = _unprotected(params, table)
    row = conn.execute(f"""
        SELECT COUNT(*),
               COUNT(*) FILTER (WHERE {pred})
        FROM {table}
    """, params).fetchone()
    return int(row[0]), int(row[1])


def prune_table(conn: DBConnection, table: str, identity: tuple[str, ...],
                date_sql: str, keep_days: int, today: str,
                dry_run: bool = False) -> dict:
    """
    Prune line-shop snapshots for one table. Returns a summary dict.

    Two tiers, both scoped to non-protected bookmakers AND to games before today,
    so live rows are never touched and this can't race with an in-flight ingest.
    """
    cutoff = (date.fromisoformat(today) - timedelta(days=keep_days)).isoformat()
    pk = "odds_id" if table == "odds" else "prop_id"
    part_by = ", ".join(identity) + ", bookmaker"
    params = {"protected": PROTECTED_BOOKMAKERS, "cutoff": cutoff, "today": today}
    prunable = _unprotected(params, table)

    before_cutoff = _older_than(date_sql, "<", "cutoff")
    before_today = _older_than(date_sql, "<", "today")
    at_or_after_cutoff = _older_than(date_sql, ">=", "cutoff")

    # WHAT SURVIVES A SETTLED GAME: the OPENER and the CLOSE, per
    # (proposition, book). One subquery computing both, deliberately — see the
    # performance note below.
    #
    # The opener (2026-08-25): an opening line is not redundant history, it is
    # the only record of where a book started, and open->close movement is the
    # basis of both CLV measurement and the §28-style opener rules.
    #
    # The close (2026-09-03, mike: "keep one non-dk snapshot per day"): an
    # opener alone cannot answer either question the retained history exists
    # for — the best price available at DECISION time (Stage 2's re-sweep, for
    # propositions that never got a scored row: abs(edge) > MAX_EDGE_CAP, and
    # NONE rows `cleanup-picks` removes) or "did the best book beat DK at
    # close?", which this module's own docstring warned would need exactly this
    # retained BEFORE anyone relied on it.
    #
    # Cost, measured 2026-09-02 rather than estimated: one day of non-DK rows is
    # 297,975 in `odds` and 105,105 in `player_prop_odds`, thinning to 2,787 and
    # 6,594 distinct (proposition, book). A second retained row per proposition
    # is about +6 MB/day, against the ~210 MB/day keeping everything would cost.
    #
    # ONE SUBQUERY, NOT TWO, AND THAT IS LOAD-BEARING. The first version of this
    # added a second `{pk} NOT IN (...)` beside the opener's, and the dry-run
    # stopped completing at all: `canceling statement due to statement timeout`
    # against a table where the unchanged version finishes in ~80s. Two
    # anti-joins over 2.2M and 2.5M rows is not the same shape as one. Both
    # keep-rules are therefore computed by two window functions over a SINGLE
    # scan, and each delete tier still references exactly one NOT IN.
    #
    # The close must never be an in-play price: that is a different proposition
    # entirely (CLAUDE.md §6), and keeping one as "the close" would hand every
    # later analysis a price from the third inning. Partitioning the DESC
    # ranking by the pre-game flag puts pre-game rows in their own partition, so
    # rn_last = 1 AND is_pre is the newest PRE-GAME row rather than the newest
    # row that happens to be pre-game. NULL counts as pre-game, as every reader
    # treats it.
    #
    # It is the last pre-game-TYPED row, which is not automatically the last row
    # before first pitch — the evening refresh keeps writing `open` rows after
    # the game starts (§7's leak trap). snapshot_at is retained with it, so an
    # analysis can still apply the `<= commence_time` bound; what this
    # guarantees is that a row EXISTS to be bounded, where today there is none.
    is_pre = "(snapshot_type IS NULL OR snapshot_type <> 'in_play')"
    select_keepers = f"""
        SELECT {pk} FROM (
            SELECT {pk},
                   ROW_NUMBER() OVER (
                       PARTITION BY {part_by} ORDER BY snapshot_at ASC
                   ) AS rn_first,
                   ROW_NUMBER() OVER (
                       PARTITION BY {part_by}, {is_pre} ORDER BY snapshot_at DESC
                   ) AS rn_last,
                   {is_pre} AS is_pre
            FROM {table}
            WHERE {prunable}
              AND {before_today}
        ) k WHERE rn_first = 1 OR (is_pre AND rn_last = 1)
    """

    # Tier 1 — settled games past the window: drop every non-DK row EXCEPT the
    # opener and the close.
    where_old = f"""
        WHERE {prunable}
          AND {before_cutoff}
          AND {pk} NOT IN ({select_keepers})
    """
    # Tier 2 — inside the window but before today: keep the row the DISTINCT ON
    # views can return (newest) plus the opener; drop what is in between.
    select_superseded = f"""
        SELECT {pk} FROM (
            SELECT {pk}, ROW_NUMBER() OVER (
                       PARTITION BY {part_by} ORDER BY snapshot_at DESC
                   ) AS rn
            FROM {table}
            WHERE {prunable}
              AND {at_or_after_cutoff}
              AND {before_today}
        ) t WHERE rn > 1
          AND {pk} NOT IN ({select_keepers})
    """

    # Count both tiers BEFORE deleting — counting after would always be 0.
    old_n = int(conn.execute(
        f"SELECT COUNT(*) FROM {table} {where_old}", params).fetchone()[0])
    superseded_n = int(conn.execute(
        f"SELECT COUNT(*) FROM ({select_superseded}) s", params).fetchone()[0])

    res = {"table": table, "cutoff": cutoff,
           "old_games": old_n, "superseded": superseded_n,
           "dry_run": dry_run}

    if dry_run:
        res["deleted"] = 0
        return res

    conn.execute(f"DELETE FROM {table} {where_old}", params)
    conn.execute(f"DELETE FROM {table} WHERE {pk} IN ({select_superseded})", params)
    res["deleted"] = old_n + superseded_n
    return res


# One row's whole quote, as text that compares NULL-safely in Postgres and in
# SQLite (the test stand-in): a NULL renders as an empty field.
_QUOTE_KEY = " || '|' || ".join(
    f"COALESCE(CAST({c} AS TEXT), '')"
    for c in ("home_price", "away_price", "draw_price", "spread_home", "total_line",
              "over_price", "under_price"))

THIN_REPEATS_SQL = f"""
    SELECT odds_id FROM (
        SELECT odds_id, {_QUOTE_KEY} AS q,
               LAG({_QUOTE_KEY}) OVER w AS q_prev,
               LEAD({_QUOTE_KEY}) OVER w AS q_next
          FROM odds
         WHERE game_id IN ({{ids}})
           AND source IS NULL
        WINDOW w AS (PARTITION BY game_id, market, bookmaker,
                     (snapshot_type IS NULL OR snapshot_type <> 'in_play')
                     ORDER BY snapshot_at, odds_id)
    ) t
    WHERE q = q_prev AND q = q_next
"""


def thin_repeats(conn: DBConnection, today: str, sports: tuple[str, ...] = PATH_KEPT_SPORTS,
                 lookback_days: int = 21, dry_run: bool = False) -> dict:
    """Delete the middle of every unchanged run in a path-kept sport's `odds` rows.

    A run is consecutive rows of one (game, market, book, pre-game-or-in-play)
    with the same price and line. Its FIRST row says when the book moved there
    and its LAST says it was still quoting there, so both stay; the rows
    between say nothing either one does not. Lossless for every as-of read:
    "the newest row at or before T" returns the same price before and after.

    Settled games only (game_date < today), one game date per transaction, so
    a slow day cannot hold a lock over a live ingest and a failure loses one
    date's thinning, not the run. Paid history (any non-NULL source) is never
    touched. The bound is `lookback_days` so the job stays small every day; a
    date it misses is thinned by a wider run, never lost."""
    start = (date.fromisoformat(today) - timedelta(days=lookback_days)).isoformat()
    out = {"sports": list(sports), "since": start, "dates": 0, "rows": 0, "dry_run": dry_run}
    marks = ", ".join(["%s"] * len(sports))
    dates = [str(r[0])[:10] for r in conn.execute(
        f"SELECT DISTINCT game_date FROM games WHERE sport IN ({marks}) "
        f"AND game_date >= %s AND game_date < %s ORDER BY 1",
        (*sports, start, today)).fetchall()]
    for d in dates:
        ids = [r[0] for r in conn.execute(
            f"SELECT game_id FROM games WHERE sport IN ({marks}) AND game_date = %s",
            (*sports, d)).fetchall()]
        if not ids:
            continue
        sql = THIN_REPEATS_SQL.format(ids=", ".join(["%s"] * len(ids)))
        if dry_run:
            n = int(conn.execute(f"SELECT COUNT(*) FROM ({sql}) s", ids).fetchone()[0])
        else:
            n = conn.execute(f"DELETE FROM odds WHERE odds_id IN ({sql})", ids).rowcount
            conn.commit()
        out["dates"] += 1
        out["rows"] += max(int(n or 0), 0)
    return out


def run_prune_odds(run_date: str = None, keep_days: int = None,
                   dry_run: bool = False) -> dict:
    """Prune line-shop snapshots in both odds tables. Safe to run any time."""
    today = run_date or date.today().isoformat()
    keep = PRUNE_NON_DK_KEEP_DAYS if keep_days is None else keep_days

    if keep < 1:
        raise ValueError("keep_days must be >= 1 — pruning today's rows would "
                         "blank the live line-shopping board")

    summary = {"today": today, "keep_days": keep, "tables": []}

    # First, and committed on its own: the table prune below has failed on a
    # statement timeout, and a failure there must not take the path thinning
    # down with it.
    with get_connection() as conn:
        summary["thinned"] = thin_repeats(conn, today, dry_run=dry_run)
        logger.info(f"{'[dry-run] ' if dry_run else ''}path-kept sports "
                    f"{summary['thinned']['sports']}: "
                    f"{summary['thinned']['rows']:,} repeated rows "
                    f"{'would be ' if dry_run else ''}thinned over "
                    f"{summary['thinned']['dates']} game dates")

    with get_connection() as conn:
        for table, identity, date_sql in _TABLES:
            before_total, before_shop = _counts(conn, table)
            res = prune_table(conn, table, identity, date_sql, keep, today,
                              dry_run=dry_run)

            would = res["old_games"] + res["superseded"]
            if dry_run:
                logger.info(
                    f"[dry-run] {table}: would delete {would:,} line-shop rows "
                    f"({res['old_games']:,} past games + {res['superseded']:,} "
                    f"superseded) — {before_shop:,} of {before_total:,} rows are "
                    f"line-shop"
                )
            else:
                after_total, after_shop = _counts(conn, table)
                logger.success(
                    f"✓ {table}: pruned {would:,} line-shop rows "
                    f"({before_total:,} → {after_total:,}); "
                    f"line-shop rows now {after_shop:,}"
                )
            res.update(before_rows=before_total, before_line_shop=before_shop)
            summary["tables"].append(res)

        if not dry_run:
            conn.commit()

    return summary


def main():
    ap = argparse.ArgumentParser(description="Prune non-DraftKings odds snapshots")
    ap.add_argument("--date", help="Treat this date as 'today' (YYYY-MM-DD)")
    ap.add_argument("--keep-days", type=int, default=None,
                    help=f"Days of line-shop history to keep "
                         f"(default {PRUNE_NON_DK_KEEP_DAYS})")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would be deleted, delete nothing")
    args = ap.parse_args()

    run_prune_odds(run_date=args.date, keep_days=args.keep_days, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
