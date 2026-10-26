"""The NCAAB odds capture: the college basketball board every five minutes,
stored only where a number moved.

WHY. The refresh passes fetch NCAAB odds hourly overnight and through the day,
and every ten minutes in the evening. College basketball openers are posted
overnight and in the morning, inside the hourly gaps, and which book posts
first, and when, can only be answered from stored timestamps: an hourly look
says a line appeared somewhere in the last sixty minutes. Five minutes is the
resolution this job buys (2026-10-26, ahead of the 2026-11-01 opener).

WHY CHANGE-ONLY. The board is about 150 games x 10 books x 3 markets. Written
whole every five minutes that is ~1.3M odds rows a day, nearly all repeats.
The pre-game poller measured 95% of polls finding the number unchanged
(data/ingestors/pregame_line_poller.py), so this job diffs first: a row is
written only when its (game, market, book) has no stored quote yet, or when a
price or line differs from the stored one. The stored quote is latest_odds,
one row per (game_id, market, bookmaker), kept current by the AFTER INSERT
trigger on odds (data/migrations/latest_line_state_tables.sql) and blind to
in-play rows. ONE read, keyed on the game ids in hand.

WHAT A TICK DOES (scheduler.run_ncaab_odds_capture, every 5 minutes, 24x7):
  1. RUN_NCAAB_ODDS_CAPTURE=0 -> return. Nothing read, nothing spent.
  2. No NCAAB game tips in the next 36 hours (ncaab_events, one read) ->
     return before the API call, so the off-season costs nothing.
  3. Build the schedule resolver (data/ingestors/ncaab_teams.make_resolver).
     None (empty team registry or no scheduled games) -> return, having
     spent nothing: ESPN owns every NCAAB games row and the odds feed never
     mints one, so without the resolver nothing could be written anyway.
  4. One bulk call, h2h + spreads + totals at every line-shop book (~3
     credits). Events already started are dropped: their prices are in-play,
     not pre-game (CLAUDE.md §6: pre-game and in-play prices never mix).
     Events tipping past the resolver's schedule window are set aside under
     their own count: they cannot resolve yet, and counted as unresolved they
     would hide a real name or schedule mismatch.
  5. Parse onto ESPN's games (odds_ingestor._process_events), diff against
     latest_odds, insert only the new and changed rows, print the counts.

A tick that inserts nothing is the normal case and exits 0. It exits non-zero
when an exception is raised (the call failed, the write failed), and when the
feed listed games inside the window and NOT ONE resolved onto ESPN's
schedule: that tick stored nothing because the join is broken, and it must not
look like a quiet board. Either way the job's heartbeat records an error and
the failure alerter reports it. The credit headers of the call are written to
odds_api_quota, as every other Odds API job writes them.

    python -m scripts.ncaab_odds_capture
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from data.db import get_connection, release_read  # noqa: E402
from data.ingestors import ncaab_teams  # noqa: E402
from data.ingestors import odds_ingestor  # noqa: E402
from data.ingestors.odds_quota import persist_quota  # noqa: E402
# One definition of "the price moved": the pre-game poller's columns and its
# number-not-text comparison. odds stores prices as TEXT in mixed shapes and
# latest_odds as NUMERIC (Decimal through psycopg), so a raw == between the
# feed's int and the stored value would report a change on every tick.
from data.ingestors.pregame_line_poller import PRICE_COLS, _fingerprint  # noqa: E402

SPORT = ncaab_teams.SPORT
MARKETS = ["h2h", "spreads", "totals"]

# How far ahead a scheduled tip makes the call worth its credits. Openers go
# up the night before and the morning of; 36 hours covers tomorrow's slate
# from any hour today, and nothing earlier is spent in the off-season.
LOOK_AHEAD_HOURS = 36

# How many days past today the schedule resolver reads (make_resolver's
# days_fwd, passed explicitly so this bound and the resolver cannot drift). An
# event tipping later than that, plus match_event's one day of skew, cannot
# resolve on this tick. 10 is make_resolver's own default. The ESPN schedule
# step stores 14 days ahead, and college lines can go up earlier than 10 days
# out (NCAAF games of 2026-10-10..25: 22 of 164 had their first stored spread
# at DraftKings, FanDuel, BetMGM, Bovada or Pinnacle 10 or more days before
# kickoff; production read 2026-10-26), so this is the number to widen if
# NCAAB openers turn out to be posted that far ahead.
RESOLVER_DAYS_FWD = 10

_ET = ZoneInfo("America/New_York")


def enabled() -> bool:
    """The kill switch: RUN_NCAAB_ODDS_CAPTURE=0 (or false/off/no) stops the
    job before it reads or spends anything. Default on."""
    return (os.environ.get("RUN_NCAAB_ODDS_CAPTURE", "1").strip().lower()
            not in ("0", "false", "off", "no"))


def _ts(value) -> datetime | None:
    """An ISO timestamp as an aware UTC datetime; a naive one is read as UTC
    (ESPN and the odds feed both send UTC). None when it does not parse."""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def has_upcoming_games(conn, now: datetime) -> bool:
    """Does any scheduled NCAAB game tip in (now, now + LOOK_AHEAD_HOURS]?

    One read of ncaab_events by game_date (indexed), with the tip compared in
    Python rather than cast in SQL: one malformed commence_time would make a
    SQL cast raise, and a raise here reads as "no games", which would switch
    the capture off for the whole season without a word. A row with no
    parseable tip counts as upcoming when its date is inside the window, so a
    time ESPN has not posted yet still spends the call.

    An unreadable table (it is created by the ESPN ingestor's first write)
    answers False: with no schedule the resolver cannot resolve anything, so
    the call would buy nothing that could be stored.
    """
    end = now + timedelta(hours=LOOK_AHEAD_HOURS)
    first = now.astimezone(_ET).date().isoformat()
    last = end.astimezone(_ET).date().isoformat()
    try:
        rows = conn.execute(
            "SELECT game_date, commence_time FROM ncaab_events "
            "WHERE game_date BETWEEN %s AND %s", (first, last)).fetchall()
    except Exception as exc:                                    # noqa: BLE001
        logger.warning(f"NCAAB odds capture: ncaab_events unreadable ({exc}); "
                       f"treated as no upcoming games")
        try:
            conn.rollback()
        except Exception:                                       # noqa: BLE001
            pass
        return False
    for game_date, commence in rows:
        tip = _ts(commence) if commence else None
        if tip is None:
            if first <= str(game_date) <= last:
                return True
            continue
        if now < tip <= end:
            return True
    return False


def drop_started(events: list[dict], now: datetime) -> tuple[list[dict], int]:
    """(the events still to tip, how many were dropped).

    An event whose commence_time is at or before `now` is in play, and its
    prices are in-play prices. An event with no parseable commence_time is
    dropped too: it cannot be dated, and _process_events would refuse it.
    """
    keep, dropped = [], 0
    for ev in events:
        tip = _ts(ev.get("commence_time"))
        if tip is None or tip <= now:
            dropped += 1
            continue
        keep.append(ev)
    return keep, dropped


def drop_beyond_window(events: list[dict], today: str,
                       days_fwd: int) -> tuple[list[dict], int]:
    """(the events the resolver can reach, how many tip after its window).

    make_resolver(conn, today, days_fwd=...) reads ESPN's games through
    today + days_fwd, and match_event accepts an event up to one ET day from
    its game, so an event dated later than today + days_fwd + 1 resolves to
    None on every tick until it comes into range. Handed to the parser it
    would be counted unresolved, and _process_events logs a warning for each
    such event on each tick (288 ticks a day).
    """
    last = (date.fromisoformat(str(today)[:10])
            + timedelta(days=days_fwd + 1)).isoformat()
    keep, beyond = [], 0
    for ev in events:
        if ncaab_teams.eastern_game_date(ev.get("commence_time")) > last:
            beyond += 1
            continue
        keep.append(ev)
    return keep, beyond


def _key(row) -> tuple:
    return (row["game_id"], row["market"], row["bookmaker"])


def stored_quotes(conn, game_ids) -> dict:
    """{(game_id, market, bookmaker): price fingerprint} from latest_odds, for
    the games in hand. ONE read; a key with no stored quote is absent."""
    ids = sorted({g for g in game_ids if g})
    if not ids:
        return {}
    rows = conn.execute(
        f"SELECT game_id, market, bookmaker, {', '.join(PRICE_COLS)} "
        f"FROM latest_odds WHERE game_id = ANY(%s)", (ids,)).fetchall()
    return {(r[0], r[1], r[2]): _fingerprint(r[3:]) for r in rows}


def split_changes(rows: list[dict], stored: dict) -> tuple[list[dict], dict]:
    """(the rows to write, {"new", "changed", "unchanged"} counts).

    A key with no stored quote is NEW, never unchanged: the first number a
    book posts for a game is the one this job exists to time. `stored` is
    updated as rows are accepted, so a key quoted twice in one fetch (two feed
    events resolving onto one game) is written once unless the two differ.
    """
    known = dict(stored)
    to_write: list[dict] = []
    counts = {"new": 0, "changed": 0, "unchanged": 0}
    for row in rows:
        k = _key(row)
        fp = _fingerprint(row)
        if k not in known:
            counts["new"] += 1
        elif known[k] != fp:
            counts["changed"] += 1
        else:
            counts["unchanged"] += 1
            continue
        known[k] = fp
        to_write.append(row)
    return to_write, counts


def capture(conn, now: datetime | None = None) -> dict:
    """One tick against `conn`. Returns the counts; writes only new and
    changed rows. Raises on a failed call or a failed write. Sets "failed"
    when the feed listed games in range and none resolved (main exits 1)."""
    now = now or datetime.now(timezone.utc)
    counts = {"events": 0, "started": 0, "beyond_window": 0, "resolved": 0,
              "unresolved": 0, "new": 0, "changed": 0, "unchanged": 0,
              "inserted": 0}

    if not has_upcoming_games(conn, now):
        release_read(conn)
        logger.info(f"NCAAB odds capture: no NCAAB game tips in the next "
                    f"{LOOK_AHEAD_HOURS}h; no call made")
        return {**counts, "skipped": "no upcoming games"}

    today = config.today_et()
    resolver = ncaab_teams.make_resolver(conn, today, days_fwd=RESOLVER_DAYS_FWD)
    # The resolver's reads are done; do not hold their transaction open across
    # the network call (data/db.release_read).
    release_read(conn)
    if resolver is None:
        logger.warning("NCAAB odds capture: no schedule resolver (team registry "
                       "or schedule window empty); nothing can be filed, no call made")
        return {**counts, "skipped": "no resolver"}

    def counted(home_name, away_name, commence_time):
        hit = resolver(home_name, away_name, commence_time)
        counts["resolved" if hit else "unresolved"] += 1
        return hit

    # Stamped in the feed's own shape ('...Z'), because snapshot_at is TEXT and
    # the latest_odds trigger keeps the newest row by comparing it as text. A
    # row normally carries its market's last_update; this is the fallback.
    fetched_at = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    events = odds_ingestor._get_odds(ncaab_teams.ODDS_API_SPORT_KEY, MARKETS)
    counts["events"] = len(events or [])
    upcoming, counts["started"] = drop_started(events or [], now)
    upcoming, counts["beyond_window"] = drop_beyond_window(upcoming, today,
                                                           RESOLVER_DAYS_FWD)

    game_rows, odds_rows = odds_ingestor._process_events(
        upcoming, SPORT, "open", fetched_at, resolve_game_id=counted)
    if game_rows:
        # The resolver path emits none (ESPN owns every NCAAB games row).
        # Anything here is the other path, and is not ours to write.
        logger.warning(f"NCAAB odds capture: ignoring {len(game_rows)} games "
                       f"row(s); the ESPN schedule owns NCAAB games")

    stored = stored_quotes(conn, {r["game_id"] for r in odds_rows})
    to_write, diff = split_changes(odds_rows, stored)
    counts.update(diff)
    if to_write:
        odds_ingestor._insert_odds(conn, to_write)
        conn.commit()
        counts["inserted"] = len(to_write)
    else:
        release_read(conn)

    if upcoming and not counts["resolved"]:
        # Every event the feed listed inside the window failed to join ESPN's
        # schedule (a team-name or schedule mismatch, the NCAAF twin-games
        # shape), so this tick stored nothing. Exiting 0 would beat "ok" on a
        # capture that records no opener at all; the heartbeat must say error.
        counts["failed"] = "nothing resolved"
        logger.error(f"NCAAB odds capture: none of {len(upcoming)} event(s) in range "
                     f"resolved onto the ESPN schedule; nothing stored")
    return counts


def main() -> int:
    if not enabled():
        logger.info("NCAAB odds capture: RUN_NCAAB_ODDS_CAPTURE is off; nothing done")
        return 0
    conn = get_connection()
    try:
        counts = capture(conn)
    finally:
        # The call's credit headers, stored the way every Odds API job stores
        # them (data/ingestors/odds_quota.py: once per run, own commit, never
        # raises), so odds_api_quota and the credit health check stay current
        # with the most frequent caller. capture() has committed or raised; a
        # raise mid-write leaves an aborted transaction, which the rollback
        # clears first. A tick that made no call has nothing to store.
        try:
            conn.rollback()
        except Exception:                                       # noqa: BLE001
            pass
        persist_quota(conn)
        conn.close()
    line = " ".join(f"{k}={v}" for k, v in counts.items())
    logger.info(f"NCAAB odds capture: {line}")
    print(line)
    if counts.get("failed"):
        return 1
    return 0


if __name__ == "__main__":
    # API telemetry for the live monitor (monitoring/): the fetch is a paid
    # Odds API call. Best-effort and silent.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("ncaab-odds-capture")
    except Exception:  # noqa: BLE001
        pass

    sys.exit(main())
