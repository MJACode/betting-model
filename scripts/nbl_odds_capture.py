"""The NBL odds capture: the NBL board every five minutes, stored only where a
number moved.

A fork of scripts/ncaabw_odds_capture.py (2026-11-09) on the NBL's feed key
and ESPN's NBL schedule (data/ingestors/nbl_teams.py).

WHY. NBL games tip 02:00-11:30 UTC, which is 9pm to 6:30am Eastern. The
refresh passes fetch hourly overnight (12-6am ET, at :17) and not at all
between 6am and 7am, so no pass stands within minutes of most NBL tips: the
close, and the minutes a book moves before it, fall between passes. Every
pre-game NBL model will be decided at BetRivers alone (the only book a pick may
name that prices the league, docs/sports/nbl.md), against the Australian
books and the exchange, so the moment each of them moves is the data. Five
minutes is the resolution this job buys, and the step the history is bought at
(data/ingestors/nbl_odds_history.py).

WHY CHANGE-ONLY. A row is written only when its (game, market, book) has no
stored quote yet, or when a price or line differs from the stored one (the
latest_odds trigger keeps the stored quote current, blind to in-play rows).

WHAT A TICK DOES (scheduler.run_nbl_odds_capture, every 5 minutes, 24x7):
  1. RUN_NBL_ODDS_CAPTURE=0 -> return. Nothing read, nothing spent.
  2. No NBL league game tips in the next 36 hours (nbl_events) -> return
     before the API call, so the off-season costs nothing.
  3. Build the schedule resolver (nbl_teams.make_resolver). None -> return,
     having spent nothing: ESPN owns every NBL games row.
  4. One bulk call, h2h + spreads + totals at the twenty books of
     odds_ingestor.sport_bookmakers_param("NBL") (two regions: 6 credits when a
     game is listed). Events already started are dropped (CLAUDE.md section 6:
     pre-game and in-play prices never mix).
  5. Parse onto ESPN's games (odds_ingestor._process_events), diff against
     latest_odds, insert only the new and changed rows, print the counts.

A tick that inserts nothing is the normal case and exits 0. It exits 1 when
the feed listed games inside the window and NOT ONE resolved onto ESPN's
schedule: that tick stored nothing because the join is broken.

    python -m scripts.nbl_odds_capture
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from data.db import get_connection, release_read  # noqa: E402
from data.ingestors import nbl_teams  # noqa: E402
from data.ingestors import odds_ingestor  # noqa: E402
from data.ingestors.odds_quota import persist_quota  # noqa: E402
from scripts.ncaabw_odds_capture import drop_started, split_changes, stored_quotes  # noqa: E402

SPORT = nbl_teams.SPORT
MARKETS = ["h2h", "spreads", "totals"]
LOOK_AHEAD_HOURS = 36
RESOLVER_DAYS_FWD = 30


def enabled() -> bool:
    """The kill switch: RUN_NBL_ODDS_CAPTURE=0 (or false/off/no) stops the job
    before it reads or spends anything. Default on."""
    return (os.environ.get("RUN_NBL_ODDS_CAPTURE", "1").strip().lower()
            not in ("0", "false", "off", "no"))


def _ts(value) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def has_upcoming_games(conn, now: datetime) -> bool:
    """Does any NBL league game tip in (now, now + LOOK_AHEAD_HOURS]? One read
    of nbl_events by game_date (the Australian date, so the window is widened
    a day each side), the tip compared in Python. An unreadable table answers
    False: with no schedule nothing could be filed."""
    end = now + timedelta(hours=LOOK_AHEAD_HOURS)
    first = (now - timedelta(days=1)).date().isoformat()
    last = (end + timedelta(days=1)).date().isoformat()
    try:
        rows = conn.execute(
            f"SELECT game_date, commence_time FROM {nbl_teams.EVENTS} "
            "WHERE game_date BETWEEN %s AND %s AND season_type = ANY(%s) "
            "AND home_code IS NOT NULL AND away_code IS NOT NULL",
            (first, last, sorted(nbl_teams.LEAGUE_SEASON_TYPES))).fetchall()
    except Exception as exc:                                    # noqa: BLE001
        logger.warning(f"NBL odds capture: {nbl_teams.EVENTS} unreadable ({exc}); "
                       f"treated as no upcoming games")
        try:
            conn.rollback()
        except Exception:                                       # noqa: BLE001
            pass
        return False
    for _, commence in rows:
        tip = _ts(commence) if commence else None
        if tip is not None and now < tip <= end:
            return True
    return False


def drop_beyond_window(events: list[dict], today: str,
                       days_fwd: int) -> tuple[list[dict], int]:
    """(the events the resolver can reach, how many tip after its window)."""
    last = date.fromisoformat(str(today)[:10]) + timedelta(days=days_fwd + 1)
    keep, beyond = [], 0
    for ev in events:
        tip = _ts(ev.get("commence_time"))
        if tip is not None and tip.date() > last:
            beyond += 1
            continue
        keep.append(ev)
    return keep, beyond


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
        logger.info(f"NBL odds capture: no NBL game tips in the next "
                    f"{LOOK_AHEAD_HOURS}h; no call made")
        return {**counts, "skipped": "no upcoming games"}

    today = config.today_et()
    resolver = nbl_teams.make_resolver(conn, today, days_fwd=RESOLVER_DAYS_FWD)
    release_read(conn)
    if resolver is None:
        logger.warning("NBL odds capture: no schedule resolver; nothing can be filed, "
                       "no call made")
        return {**counts, "skipped": "no resolver"}

    def counted(home_name, away_name, commence_time):
        hit = resolver(home_name, away_name, commence_time)
        counts["resolved" if hit else "unresolved"] += 1
        return hit

    fetched_at = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    events = odds_ingestor._get_odds(nbl_teams.ODDS_API_SPORT_KEY, MARKETS)
    counts["events"] = len(events or [])
    upcoming, counts["started"] = drop_started(events or [], now)
    upcoming, counts["beyond_window"] = drop_beyond_window(upcoming, today, RESOLVER_DAYS_FWD)

    game_rows, odds_rows = odds_ingestor._process_events(
        upcoming, SPORT, "open", fetched_at, resolve_game_id=counted)
    if game_rows:
        logger.warning(f"NBL odds capture: ignoring {len(game_rows)} games row(s); "
                       f"the ESPN schedule owns NBL games")

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
        counts["failed"] = "nothing resolved"
        logger.error(f"NBL odds capture: none of {len(upcoming)} event(s) in range "
                     f"resolved onto the ESPN schedule ({resolver.report()}); nothing stored")
    return counts


def main() -> int:
    if not enabled():
        logger.info("NBL odds capture: RUN_NBL_ODDS_CAPTURE is off; nothing done")
        return 0
    conn = get_connection()
    try:
        counts = capture(conn)
    finally:
        try:
            conn.rollback()
        except Exception:                                       # noqa: BLE001
            pass
        persist_quota(conn)
        conn.close()
    line = " ".join(f"{k}={v}" for k, v in counts.items())
    logger.info(f"NBL odds capture: {line}")
    print(line)
    return 1 if counts.get("failed") else 0


if __name__ == "__main__":
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("nbl-odds-capture")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
