"""Incremental refresh of the current NFL season, and a freshness report.

The report is read-only. It does not read odds. `apply=False` returns
the report and writes nothing. `apply=True` rebuilds only the due games:
the current season's games from yesterday through seven days ahead, plus
a past game with no fact row, a past fact row that is still missing a
score, and a past game that has facts but no prop facts.

Rest days still use the whole season's schedule. Quotes are fetched only
for the due games.

This is not a schedule. `jobs/declared_jobs.json` lists `byom_refresh`
with enabled false and apply false, so a merge enqueues nothing.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from byom.constants import SPORT
from byom.game_facts import parse_date, parse_game_id
from byom.load import _fetch, _games
from byom.season import current_nfl_season

# Not a lock window. The due set is this many days back and this many
# days forward from the report date, inclusive.
REFRESH_LOOKBACK_DAYS = 1
REFRESH_LOOKAHEAD_DAYS = 7

# Not a lock window. A window row older than this is stale on the report.
# The report does not write.
FRESHNESS_MAX_AGE_HOURS = 24

_ET = ZoneInfo("America/New_York")


def _clock(today: date | datetime | None) -> tuple[date, datetime]:
    if today is None:
        now = datetime.now(_ET)
        return now.date(), now
    if isinstance(today, datetime):
        if today.tzinfo is None:
            now = today.replace(tzinfo=_ET)
        else:
            now = today.astimezone(_ET)
        return now.date(), now
    now = datetime(today.year, today.month, today.day, tzinfo=_ET)
    return today, now


def _aware(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=_ET)
        return value
    return None


def _window(as_of: date) -> tuple[date, date]:
    return (
        as_of - timedelta(days=REFRESH_LOOKBACK_DAYS),
        as_of + timedelta(days=REFRESH_LOOKAHEAD_DAYS),
    )


def _fact_rows(conn, season: int) -> dict[str, tuple]:
    """canonical_key -> (home_score, away_score)."""
    return {
        row[0]: (row[1], row[2])
        for row in _fetch(conn, """
            SELECT canonical_key, home_score, away_score
              FROM byom_game_facts
             WHERE sport = %s AND season = %s
        """, (SPORT, season))
    }


def _prop_keys(conn, season: int) -> set[str]:
    return {
        row[0]
        for row in _fetch(conn, """
            SELECT DISTINCT canonical_key FROM byom_prop_facts
             WHERE sport = %s AND season = %s
        """, (SPORT, season))
    }


def _incomplete(row: tuple | None) -> bool:
    """A null score is unfinished. A null line is not."""
    if row is None:
        return False
    return row[0] is None or row[1] is None


def due_games(conn, today: date | datetime | None = None) -> list[dict]:
    """Games the refresh would rebuild. No odds read.

    A past fact row with a null score is incomplete: the row was written
    before the game finished and has since left the window. A null line
    is not incomplete. A past game that already has a finished fact row
    and no prop row is due so the prop backfill can run.
    """
    as_of, _now = _clock(today)
    season = current_nfl_season(as_of)
    start, end = _window(as_of)
    facts = _fact_rows(conn, season)
    props = _prop_keys(conn, season)
    due = []
    for game in _games(conn, season):
        parsed = parse_game_id(game["game_id"])
        day = parse_date(game.get("game_date"))
        if parsed is None or day is None:
            continue
        key = parsed[0]
        in_window = start <= day <= end
        past = day < as_of
        stored = facts.get(key)
        if in_window:
            reason = "window"
        elif past and stored is None:
            reason = "missing"
        elif past and _incomplete(stored):
            reason = "incomplete"
        elif past and key not in props:
            reason = "props"
        else:
            continue
        due.append({
            "game_id": game["game_id"],
            "canonical_key": key,
            "game_date": day.isoformat(),
            "reason": reason,
        })
    return due


def freshness(conn, today: date | datetime | None = None,
              due: list[dict] | None = None) -> dict:
    """Read-only counts. Does not read odds and does not write.

    Pass `due` when the caller already ran due_games, so the report and
    the rebuild share one read.
    """
    as_of, now = _clock(today)
    season = current_nfl_season(as_of)
    start, end = _window(as_of)
    stale_before = now - timedelta(hours=FRESHNESS_MAX_AGE_HOURS)
    facts = _fact_rows(conn, season)
    built = {}
    for key, built_at in _fetch(conn, """
        SELECT canonical_key, built_at FROM byom_game_facts
         WHERE sport = %s AND season = %s
    """, (SPORT, season)):
        built[key] = _aware(built_at)
    prop_keys = _prop_keys(conn, season)
    in_window = 0
    missing_game_facts = 0
    incomplete_game_facts = 0
    stale_game_facts = 0
    window_missing_prop_facts = 0
    for game in _games(conn, season):
        parsed = parse_game_id(game["game_id"])
        day = parse_date(game.get("game_date"))
        if parsed is None or day is None:
            continue
        key = parsed[0]
        window = start <= day <= end
        if window:
            in_window += 1
            if key not in prop_keys:
                window_missing_prop_facts += 1
            stamped = built.get(key)
            if stamped is not None and stamped < stale_before:
                stale_game_facts += 1
        if key not in built and day <= end:
            missing_game_facts += 1
        if day < as_of and _incomplete(facts.get(key)):
            incomplete_game_facts += 1
    if due is None:
        due = due_games(conn, today=today)
    return {
        "season": season,
        "as_of": as_of.isoformat(),
        "due": len(due),
        "in_window": in_window,
        "missing_game_facts": missing_game_facts,
        "incomplete_game_facts": incomplete_game_facts,
        "stale_game_facts": stale_game_facts,
        "window_missing_prop_facts": window_missing_prop_facts,
        "writes": False,
    }


def refresh(conn, apply: bool = False, today: date | datetime | None = None) -> dict:
    """Freshness always. Writes only when apply is true, and only the due games."""
    due = due_games(conn, today=today)
    report = freshness(conn, today=today, due=due)
    report["apply"] = bool(apply)
    report["written_game_facts"] = 0
    report["written_prop_facts"] = 0
    if not apply:
        return report
    ids = [row["game_id"] for row in due]
    if not ids:
        return report
    from byom.load import build_season
    from byom.prop_load import build_season as build_props

    game = build_season(
        conn, report["season"], apply=True, game_ids=ids)
    prop = build_props(
        conn, report["season"], apply=True, game_ids=ids)
    conn.commit()
    report["written_game_facts"] = game["written"]
    report["written_prop_facts"] = prop["written"]
    return report
