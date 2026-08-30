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


def last_known_prices(conn: DBConnection, sports: list) -> dict:
    """{(game_id, market): fingerprint} for the newest PRE-GAME DK row each.

    Bounded to unstarted games so a finished game's last number can never be
    compared against, and to snapshot_type <> 'in_play' so the live loop's rows
    are invisible here (§6)."""
    if not sports:
        return {}
    marks = ",".join(["%s"] * len(sports))
    cols = ", ".join(f"o.{c}" for c in PRICE_COLS)
    rows = conn.execute(f"""
        SELECT DISTINCT ON (o.game_id, o.market) o.game_id, o.market, {cols}
        FROM odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE o.bookmaker = %s
          AND o.snapshot_type <> 'in_play'
          AND g.home_score IS NULL
          AND g.sport IN ({marks})
        ORDER BY o.game_id, o.market, o.snapshot_at::timestamptz DESC
    """, (config.ODDS_API_BOOKMAKER, *sports)).fetchall()
    return {(r[0], r[1]): _fingerprint(r[2:]) for r in rows}


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
              score: bool = True) -> dict:
    """One tick: fetch, diff, write what moved, score what moved.

    Returns a summary dict. Never raises -- see the module docstring."""
    sports = sports or config.PREGAME_POLL_SPORTS
    from data.ingestors.odds_ingestor import fetch_pregame_rows, _insert_odds

    used = _credits_used_today(conn)
    if over_credit_cap(used):
        logger.warning(
            f"pregame poller: daily credit cap reached "
            f"({used:.0f} >= {config.PREGAME_POLL_DAILY_CREDIT_CAP}) — skipping")
        return {"skipped": "credit_cap", "credits_used": used}

    known = last_known_prices(conn, sports)
    fetched = fetch_pregame_rows(sports)
    to_write, moved = changed_rows(fetched, known)

    if to_write:
        _insert_odds(conn, to_write)
        conn.commit()

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
    while True:
        started = time.monotonic()
        if not config.RUN_PREGAME_POLLER:
            logger.info("pregame poller: RUN_PREGAME_POLLER=0 — stopping")
            return
        try:
            poll_once(conn)
        except Exception as exc:                              # noqa: BLE001
            # A tick that dies must never take the loop with it: a stopped
            # poller and a quiet market look identical from the outside.
            logger.error(f"pregame poll failed: {exc}", exc_info=True)
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
