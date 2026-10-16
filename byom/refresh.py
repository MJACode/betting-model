"""Incremental refresh of the current NFL season, and a freshness report.

The report is read-only. It does not read odds. `apply=False` returns
the report and writes nothing. `apply=True` rebuilds only the due games:
the current season's games from yesterday through seven days ahead, plus
current-season games already played that have no `byom_game_facts` row.

Rest days still use the whole season's schedule. Quotes are fetched only
for the due games.

This is not a schedule. `jobs/declared_jobs.json` lists `byom_refresh`
with enabled false and apply false, so a merge enqueues nothing. The
120h and 24h locks are unchanged and stay UNCONFIRMED.
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


def due_games(conn, today: date | datetime | None = None) -> list[dict]:
    """Games the refresh would rebuild. No odds read."""
    as_of, _now = _clock(today)
    season = current_nfl_season(as_of)
    start = as_of - timedelta(days=REFRESH_LOOKBACK_DAYS)
    end = as_of + timedelta(days=REFRESH_LOOKAHEAD_DAYS)
    have = {
        row[0]
        for row in _fetch(conn, """
            SELECT canonical_key FROM byom_game_facts
             WHERE sport = %s AND season = %s
        """, (SPORT, season))
    }
    due = []
    for game in _games(conn, season):
        parsed = parse_game_id(game["game_id"])
        day = parse_date(game.get("game_date"))
        if parsed is None or day is None:
            continue
        key = parsed[0]
        in_window = start <= day <= end
        missing_past = day < as_of and key not in have
        if not in_window and not missing_past:
            continue
        due.append({
            "game_id": game["game_id"],
            "canonical_key": key,
            "game_date": day.isoformat(),
            "reason": "window" if in_window else "missing",
        })
    return due


def freshness(conn, today: date | datetime | None = None) -> dict:
    """Read-only counts. Does not read odds and does not write."""
    as_of, now = _clock(today)
    season = current_nfl_season(as_of)
    start = as_of - timedelta(days=REFRESH_LOOKBACK_DAYS)
    end = as_of + timedelta(days=REFRESH_LOOKAHEAD_DAYS)
    stale_before = now - timedelta(hours=FRESHNESS_MAX_AGE_HOURS)
    built = {}
    for key, built_at in _fetch(conn, """
        SELECT canonical_key, built_at FROM byom_game_facts
         WHERE sport = %s AND season = %s
    """, (SPORT, season)):
        built[key] = _aware(built_at)
    prop_keys = {
        row[0]
        for row in _fetch(conn, """
            SELECT DISTINCT canonical_key FROM byom_prop_facts
             WHERE sport = %s AND season = %s
        """, (SPORT, season))
    }
    in_window = 0
    missing_game_facts = 0
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
        if day < as_of and key not in built:
            missing_game_facts += 1
    return {
        "season": season,
        "as_of": as_of.isoformat(),
        "due": len(due_games(conn, today=today)),
        "in_window": in_window,
        "missing_game_facts": missing_game_facts,
        "stale_game_facts": stale_game_facts,
        "window_missing_prop_facts": window_missing_prop_facts,
        "writes": False,
    }


def refresh(conn, apply: bool = False, today: date | datetime | None = None) -> dict:
    """Freshness always. Writes only when apply is true, and only the due games."""
    report = freshness(conn, today=today)
    report["apply"] = bool(apply)
    report["written_game_facts"] = 0
    report["written_prop_facts"] = 0
    if not apply:
        return report
    ids = [row["game_id"] for row in due_games(conn, today=today)]
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
