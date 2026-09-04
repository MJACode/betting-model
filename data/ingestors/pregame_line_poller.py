"""
Watch DraftKings' PRE-GAME numbers continuously, and act only on what moved.

WHY THIS EXISTS
The pre-game board was re-read by the 28-job refresh pass, which takes ~12
minutes. Scheduled every 10 minutes in the evening it could never keep up: 18
passes ran in a 5-hour window on 2026-08-29 -- one every 17 minutes -- and the
ticks in between were silently skipped. A line that opened and moved inside
that gap was priced long after it was takeable, if at all.

mike, 2026-08-30: "why not run this like we do the live poller every few
seconds for games not started ... and that should be the cadence 24x7".

So this is the live loop's shape applied to unstarted games. It is emphatically
NOT the refresh pass run more often: that pass rebuilds features, settles bets,
sends notifications and health-checks, none of which belongs on a
price-watching cadence, and running it 2,880 times a day would cost 634 MB of
database growth per day against a 5 GB database.

THE ONE IDEA THAT MAKES IT AFFORDABLE
Measured over 39,146 pre-game observations in 48 hours, 95% of polls find DK's
number UNCHANGED. So the loop diffs first and only then writes and scores:

    fetch (~13 credits, all sports, one bulk call each)
      -> diff against the last stored DK row per (game_id, market)
      -> write ONLY changed rows
      -> score ONLY the games that changed

That turns ~2.25M audit rows a day into roughly 112k, and turns a 150-second
full-board score into a handful of games. The pattern is the house one, not an
invention: live_price_log.py and scripts/dk_freshness_compare.py both write on
change, for the same reason.

WHAT IT DELIBERATELY DOES NOT DO
  * It does not settle, notify, or health-check. Those stay on the refresh
    pass, which still runs.
  * It does not touch in-play rows. Games that have started belong to the live
    loop, and the two must never write the same lane (§6: pre-game and in-play
    prices never mix).
  * It does not re-price a locked pick. It calls the ordinary scorer, so §1c
    holds exactly as it does on any other pass: a BET freezes its pair, and
    only pairs that never produced a bet are re-scored.

SAFETY
  * A daily credit cap (PREGAME_POLL_DAILY_CREDIT_CAP), mirroring the live
    loop's, so a runaway loop cannot eat a month's plan.
  * A kill switch (RUN_PREGAME_POLLER) readable from Railway without a deploy.
  * Every tick is independent: an exception in one is logged and the loop
    continues, because a poller that dies on one bad payload is worse than no
    poller at all -- it looks exactly like a quiet market.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import config
from data.db import DBConnection, get_connection

logger = logging.getLogger(__name__)

_ET = ZoneInfo("America/New_York")

# The columns whose movement counts as "the price changed". Deliberately the
# decision-relevant ones only: a link or a DK selection id can churn without the
# number moving, and treating that as a change would re-score the whole board
# for nothing -- which is the exact cost this module exists to avoid.
PRICE_COLS = ("home_price", "away_price", "draw_price",
              "spread_home", "total_line", "over_price", "under_price")


def _num(v):
    """Compare prices as numbers, not text.

    `odds` stores these as TEXT in mixed shapes ('-110' vs '-110.0'), so a
    string compare reports a change on every poll and defeats the diff. Anything
    unparseable falls back to its raw value, so a genuinely odd payload still
    compares equal to itself rather than churning."""
    if v is None:
        return None
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return v


def _key(row: dict) -> tuple:
    return (row["game_id"], row["market"])


def _fingerprint(row) -> tuple:
    """The decision-relevant price shape of one row, as a comparable tuple."""
    if isinstance(row, dict):
        return tuple(_num(row.get(c)) for c in PRICE_COLS)
    return tuple(_num(v) for v in row)


# THE SEED IS KEYED, NOT A TABLE SCAN (2026-09-04). The previous seed read
# "the newest pre-game DK row for EVERY unstarted game" as one DISTINCT ON over
# the whole odds table -- a Parallel Seq Scan of 842 MB (shared read=88,408
# pages, 6.1 s alone, 27 s+ when contended) every PREGAME_POLL_RESEED_SEC, and
# the app's own reads timed out underneath it: 41 statement timeouts across
# every view the app reads in the one minute it ran (postgres log, 20:28 UTC),
# the same storm several times a day. See data/migrations/
# skip_scan_latest_odds_views.sql for the app side of the same measurement.
#
# The poller never needed every unstarted game. It needs the newest stored row
# for the keys the API JUST QUOTED, and only for those it has not seen since
# the last seed. So the seed takes the keys and does one backward probe of
# idx_odds_book_snap (game_id, market, bookmaker, snapshot_at) per key:
# measured 0.27 ms and ~5 buffers per key, 4,752 keys in 1.3 s, no scan, no
# sort. A key with no stored row simply comes back absent, which changed_rows
# reads as "never seen" -- the same answer the old seed gave.
#
# "Newest" is ORDER BY snapshot_at DESC on the TEXT column so the index
# supplies the order. The old seed cast to timestamptz first (the data-
# integrity rule: parse before comparing). Measured before relying on it: over
# every (game, market, book) key since 2026-09-01, the text-latest row and
# max(snapshot_at::timestamptz) disagreed 0 times in 7,348 keys, and 482,349 of
# 482,457 DK pre-game rows for unstarted games are the 20-char 'Z' shape.
SEED_SQL = f"""
    SELECT k.game_id, k.market, {", ".join(f"l.{c}" for c in PRICE_COLS)}
    FROM unnest(%s::text[], %s::text[]) AS k(game_id, market)
    CROSS JOIN LATERAL (
        SELECT {", ".join(f"o.{c}" for c in PRICE_COLS)}
        FROM odds o
        WHERE o.game_id = k.game_id
          AND o.market = k.market
          AND o.bookmaker = %s
          AND o.snapshot_type <> 'in_play'
        ORDER BY o.snapshot_at DESC
        LIMIT 1
    ) l
"""


def last_known_prices(conn: DBConnection, keys) -> dict:
    """{(game_id, market): fingerprint} for the newest PRE-GAME DK row of each
    key in `keys`. Keys with no stored row are absent from the result.

    Bounded to snapshot_type <> 'in_play' so the live loop's rows are
    invisible here (section 6). Started games are not excluded here any more:
    the caller only asks about keys the API is currently quoting, and the API
    quotes unstarted games."""
    keys = sorted({(g, m) for g, m in keys})
    if not keys:
        return {}
    rows = conn.execute(SEED_SQL, ([g for g, _ in keys], [m for _, m in keys],
                                   config.ODDS_API_BOOKMAKER)).fetchall()
    return {(r[0], r[1]): _fingerprint(r[2:]) for r in rows}


def quoted_keys(fetched: list) -> set:
    """The (game_id, market) keys a fetch will be diffed on: DK, pre-game."""
    return {_key(row) for row in fetched
            if row.get("bookmaker") == config.ODDS_API_BOOKMAKER
            and row.get("snapshot_type") != "in_play"}


def changed_rows(fetched: list, known: dict) -> tuple:
    """Split fetched DK rows into (rows_to_write, game_ids_that_moved).

    A row we have never seen counts as changed -- a brand-new game's opener is
    the single most valuable number in this system (§28's whole thesis), so
    "unknown" must never be treated as "unchanged"."""
    to_write, moved = [], set()
    for row in fetched:
        if row.get("bookmaker") != config.ODDS_API_BOOKMAKER:
            continue                      # other books are recorded elsewhere
        if row.get("snapshot_type") == "in_play":
            continue                      # the live loop owns that lane
        k = _key(row)
        if _fingerprint(row) != known.get(k):
            to_write.append(row)
            moved.add(row["game_id"])
    return to_write, moved


def _credits_used_today(conn: DBConnection) -> float:
    """This loop's own Odds API burn today, from the telemetry probe."""
    try:
        row = conn.execute("""
            SELECT COALESCE(SUM(credits), 0) FROM api_call_log
            WHERE host = 'api.the-odds-api.com'
              AND source = 'pregame_poller'
              AND ts >= date_trunc('day', now() AT TIME ZONE 'America/New_York')
        """).fetchone()
        return float(row[0]) if row else 0.0
    except Exception as exc:                                  # noqa: BLE001
        # Unknown burn must not silently disable the loop OR uncap it. Treat it
        # as zero and let the cap be enforced on the next readable tick: the
        # Odds API's own quota is the backstop either way.
        logger.warning(f"pregame poller: credit read failed ({exc})")
        return 0.0


def over_credit_cap(used: float) -> bool:
    cap = config.PREGAME_POLL_DAILY_CREDIT_CAP
    return bool(cap) and used >= cap


def poll_once(conn: DBConnection, sports: list | None = None,
              score: bool = True, known: dict | None = None) -> dict:
    """One tick: fetch, diff, write what moved, score what moved.

    `known` is the caller's fingerprint map, MUTATED IN PLACE with whatever this
    tick writes. Pass None and the tick seeds its own from the database, which
    is what a one-off call or a test wants.

    WHY THE CALLER OWNS THE MAP. The first seed re-read DK's whole pre-game
    history for every unstarted game -- about 1,525 games and 142k heap
    fetches out of a 1.18 GB table. Rebuilding it once per tick was the single
    most expensive statement in the database: measured 2026-09-02 from
    pg_stat_statements, **4,291 calls, 88,398 s total, 20,601 ms mean -- 24.6
    HOURS of database time**, against a 30-second poll interval. At the tail
    (>60 s observed) the loop spent its whole cycle inside this one query and
    slept not at all.

    Nothing about that read was necessary. The poller already knows what it
    wrote; the map only has to be SEEDED from the database, then kept current
    from the writes. run_forever re-seeds periodically so a row written by
    another writer (the refresh pass) cannot drift the map forever.

    AND THE SEED ITSELF IS KEYED (2026-09-04). Even once per 15 minutes, the
    whole-table read was a 6-27 s sequential scan of the odds table that
    starved every app query running beside it (see SEED_SQL). A re-seed is now
    an EMPTY map: the next tick looks up exactly the keys the API quoted, one
    index probe each, and nothing else.

    Returns a summary dict. Never raises -- see the module docstring."""
    sports = sports or config.PREGAME_POLL_SPORTS
    from data.ingestors.odds_ingestor import fetch_pregame_rows, _insert_odds

    used = _credits_used_today(conn)
    if over_credit_cap(used):
        logger.warning(
            f"pregame poller: daily credit cap reached "
            f"({used:.0f} >= {config.PREGAME_POLL_DAILY_CREDIT_CAP}) — skipping")
        return {"skipped": "credit_cap", "credits_used": used}

    if known is None:
        known = {}
    fetched = fetch_pregame_rows(sports)
    # Seed ONLY what this fetch quoted and the map does not yet hold. After a
    # re-seed (an empty map) that is every quoted key, once; on an ordinary
    # tick it is the handful of games the API started quoting since.
    missing = quoted_keys(fetched) - known.keys()
    if missing:
        known.update(last_known_prices(conn, missing))
    to_write, moved = changed_rows(fetched, known)

    if to_write:
        _insert_odds(conn, to_write)
        conn.commit()
        # Fold the writes in only AFTER the commit. Doing it earlier would let a
        # failed insert leave the map claiming a price the database never took,
        # and the next tick would then see no change and never retry it.
        for row in to_write:
            known[_key(row)] = _fingerprint(row)

    scored = 0
    if score and moved:
        from models.scorer import run_scorer
        result = run_scorer(target_date=config.today_et(), only_games=moved)
        scored = result.get("total_picks", 0)

    logger.info(f"pregame poll: {len(fetched)} quoted, {len(to_write)} changed, "
                f"{len(moved)} game(s) re-scored, {scored} pick(s)")
    return {"quoted": len(fetched), "written": len(to_write),
            "games_moved": len(moved), "picks": scored, "credits_used": used}


def run_forever(interval_sec: int | None = None) -> None:
    """The supervised loop. One connection, reused; one tick per interval."""
    interval = interval_sec or config.PREGAME_POLL_INTERVAL_SEC
    logger.info(f"pregame line poller starting — every {interval}s over "
                f"{','.join(config.PREGAME_POLL_SPORTS)}")
    conn = get_connection()
    # The fingerprint map lives across ticks -- see poll_once. `known is None`
    # is the re-seed signal, so a reconnect below re-seeds by clearing it.
    known: dict | None = None
    last_seed = 0.0
    while True:
        started = time.monotonic()
        if not config.RUN_PREGAME_POLLER:
            logger.info("pregame poller: RUN_PREGAME_POLLER=0 — stopping")
            return
        try:
            # Re-seed on a bounded schedule. The map drifts two ways and both
            # are self-correcting only at a seed: another writer moving a price
            # we did not write, and started games whose entries are now dead
            # weight. Neither can produce a WRONG pick -- a stale entry costs at
            # most one redundant write and re-score -- so the interval trades
            # database time against that, not against correctness.
            if known is None or (started - last_seed) >= config.PREGAME_POLL_RESEED_SEC:
                # An empty map IS the seed: the tick below looks up every key
                # the API quotes, one index probe each (SEED_SQL), instead of
                # reading the whole table up front.
                known = {}
                last_seed = started
                logger.info("pregame poller: fingerprint map cleared for re-seed")
            poll_once(conn, known=known)
            if len(known) and started == last_seed:
                logger.info(f"pregame poller: fingerprint map seeded "
                            f"({len(known)} game/market pairs)")
        except Exception as exc:                              # noqa: BLE001
            # A tick that dies must never take the loop with it: a stopped
            # poller and a quiet market look identical from the outside.
            logger.error(f"pregame poll failed: {exc}", exc_info=True)
            # The map may be half-updated by a tick that died mid-write, so
            # throw it away rather than carry a guess forward.
            known = None
            try:
                conn.rollback()
            except Exception:                                 # noqa: BLE001
                conn = get_connection()
        # Sleep the REMAINDER, so a slow tick does not compound into drift.
        time.sleep(max(0.0, interval - (time.monotonic() - started)))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    try:
        from monitoring.probe import install
        install("pregame_poller")
    except Exception:                                         # noqa: BLE001
        pass
    run_forever()
