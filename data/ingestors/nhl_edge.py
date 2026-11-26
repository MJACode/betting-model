"""NHL EDGE season-to-date snapshots. Personal, non-commercial. Not a pick input.

One call per skater, goalie and team on `/v1/edge/...`. There is no bulk
file (measured 2026-11-26: the landing pages are the single leader in each
category, a few KB). The detail document already carries the pieces:

  * skater-detail: top shot speed, max skating speed, bursts, distance,
    shot location (`sogSummary` / `sogDetails`), zone time
  * goalie-detail: save% by danger band (`shotLocationSummary`, code
    `high`) and the 17-area grid (`shotLocationDetails`)
  * team-detail: shot speed, skating, distance, location, zone time.
    The id is numeric. Utah has two rows in the team list (59 Hockey Club,
    68 Mammoth); both detail calls return team id 68, so the higher id is
    the one requested.

The roster is the stats summary, paged at 100 (a `limit=-1` still returned
100 of 789 skaters). A player the EDGE detail does not list (HTTP 404) is
skipped. The payload is the document, so a field this extract does not
promote is still stored.

A night is one `snapshot_date`. The same date is replaced on a retry.
There is no backfill: the endpoint is the season to date, not a past day.

    python -m data.ingestors.nhl_edge --daily
    python -m data.ingestors.nhl_edge --daily --apply
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

from loguru import logger

from data.db import ConnectionLost, get_connection
from data.ingestors.nhl_polite_http import FetchFailed, get_json
from data.ingestors.nhl_stats_ingestor import NHL_API_BASE, NHL_STATS_BASE, _norm_nhl
from data.season_labels import nhl_season_label

SOURCE = "nhl_api"
PAUSE_S = 0.5
PAGE = 100

SKATER_COLS = (
    "snapshot_date", "season_id", "game_type", "player_id", "team_abbr",
    "player_name", "position", "games_played", "top_shot_mph", "top_shot_percentile",
    "max_skate_mph", "max_skate_percentile", "bursts_over_20", "distance_miles",
    "oz_pct", "nz_pct", "dz_pct", "high_danger_shooting_pct", "payload", "source",
)
GOALIE_COLS = (
    "snapshot_date", "season_id", "game_type", "player_id", "team_abbr",
    "player_name", "games_played", "save_pct", "high_danger_save_pct",
    "high_danger_saves", "payload", "source",
)
TEAM_COLS = (
    "snapshot_date", "season_id", "game_type", "team_id", "team_abbr",
    "top_shot_mph", "shots_over_90", "max_skate_mph", "bursts_over_20",
    "bursts_over_22", "distance_miles", "oz_pct", "nz_pct", "dz_pct",
    "high_danger_shooting_pct", "payload", "source",
)


def season_id_for(run_date: str) -> int:
    end = nhl_season_label(run_date)
    return int(f"{end - 1}{end}")


def _f(node, *path):
    cur = node
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    if isinstance(cur, bool) or cur is None:
        return None
    if isinstance(cur, (int, float)):
        return float(cur)
    return None


def _i(node, *path):
    value = _f(node, *path)
    if value is None:
        return None
    return int(value)


def _band(rows, code: str, field: str):
    for row in rows or []:
        if row.get("locationCode") == code:
            value = row.get(field)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    return None


def _zone(node: dict | None, prefix: str):
    if not isinstance(node, dict):
        return None
    return _f(node, prefix)


def _payload(body: dict) -> str:
    return json.dumps(body, separators=(",", ":"), default=str)


def skater_record(body: dict, snapshot_date: str, season_id: int, game_type: int) -> dict | None:
    player = (body or {}).get("player") or {}
    if player.get("id") is None:
        return None
    team = ((player.get("team") or {}).get("abbrev"))
    zone = body.get("zoneTimeDetails") if isinstance(body.get("zoneTimeDetails"), dict) else {}
    return {
        "snapshot_date": snapshot_date,
        "season_id": int(season_id),
        "game_type": int(game_type),
        "player_id": int(player["id"]),
        "team_abbr": _norm_nhl(team) if team else None,
        "player_name": _join_name(player),
        "position": player.get("position"),
        "games_played": _i(player, "gamesPlayed"),
        "top_shot_mph": _f(body, "topShotSpeed", "imperial"),
        "top_shot_percentile": _f(body, "topShotSpeed", "percentile"),
        "max_skate_mph": _f(body, "skatingSpeed", "speedMax", "imperial"),
        "max_skate_percentile": _f(body, "skatingSpeed", "speedMax", "percentile"),
        "bursts_over_20": _f(body, "skatingSpeed", "burstsOver20", "value"),
        "distance_miles": _f(body, "totalDistanceSkated", "imperial"),
        "oz_pct": _zone(zone, "offensiveZonePctg"),
        "nz_pct": _zone(zone, "neutralZonePctg"),
        "dz_pct": _zone(zone, "defensiveZonePctg"),
        "high_danger_shooting_pct": _band(body.get("sogSummary"), "high", "shootingPctg"),
        "payload": _payload(body),
        "source": SOURCE,
    }


def goalie_record(body: dict, snapshot_date: str, season_id: int, game_type: int) -> dict | None:
    player = (body or {}).get("player") or {}
    if player.get("id") is None:
        return None
    team = ((player.get("team") or {}).get("abbrev"))
    summary = body.get("shotLocationSummary") or []
    return {
        "snapshot_date": snapshot_date,
        "season_id": int(season_id),
        "game_type": int(game_type),
        "player_id": int(player["id"]),
        "team_abbr": _norm_nhl(team) if team else None,
        "player_name": _join_name(player),
        "games_played": _i(player, "gamesPlayed"),
        "save_pct": _band(summary, "all", "savePctg"),
        "high_danger_save_pct": _band(summary, "high", "savePctg"),
        "high_danger_saves": _band(summary, "high", "saves"),
        "payload": _payload(body),
        "source": SOURCE,
    }


def team_record(body: dict, snapshot_date: str, season_id: int, game_type: int,
                team_abbr: str | None = None) -> dict | None:
    team = (body or {}).get("team") or {}
    if team.get("id") is None:
        return None
    abbr = team.get("abbrev") or team_abbr
    zone = body.get("zoneTimeDetails") if isinstance(body.get("zoneTimeDetails"), dict) else {}
    return {
        "snapshot_date": snapshot_date,
        "season_id": int(season_id),
        "game_type": int(game_type),
        "team_id": int(team["id"]),
        "team_abbr": _norm_nhl(abbr) if abbr else None,
        "top_shot_mph": _f(body, "shotSpeed", "topShotSpeed", "imperial"),
        "shots_over_90": _f(body, "shotSpeed", "shotAttemptsOver90", "value"),
        "max_skate_mph": _f(body, "skatingSpeed", "speedMax", "imperial"),
        "bursts_over_20": _f(body, "skatingSpeed", "burstsOver20", "value"),
        "bursts_over_22": _f(body, "skatingSpeed", "burstsOver22", "value"),
        "distance_miles": _f(body, "distanceSkated", "total", "imperial"),
        "oz_pct": _zone(zone, "offensiveZonePctg"),
        "nz_pct": _zone(zone, "neutralZonePctg"),
        "dz_pct": _zone(zone, "defensiveZonePctg"),
        "high_danger_shooting_pct": _band(body.get("sogSummary"), "high", "shootingPctg"),
        "payload": _payload(body),
        "source": SOURCE,
    }


def _join_name(player: dict) -> str | None:
    def text(node):
        if isinstance(node, dict):
            return (node.get("default") or "").strip()
        return (node or "").strip() if isinstance(node, str) else ""
    name = f"{text(player.get('firstName'))} {text(player.get('lastName'))}".strip()
    return name or None


def current_team_ids(team_rows: list[dict], standings_abbrs: list[str]) -> list[tuple[int, str]]:
    """(team id, abbrev) for the clubs in the standings.

    When one abbrev has two ids, the higher one is the current club.
    Measured: UTA 59 and 68 both return EDGE team id 68.
    """
    by: dict[str, list[int]] = {}
    for row in team_rows:
        code = row.get("triCode")
        if code is None or row.get("id") is None:
            continue
        by.setdefault(str(code), []).append(int(row["id"]))
    out = []
    for abbr in standings_abbrs:
        ids = by.get(abbr) or []
        if not ids:
            continue
        out.append((max(ids), _norm_nhl(abbr)))
    return out


def rest_rows(path: str, cayenne: str | None = None, get=get_json,
              limit: int = PAGE, pause_s: float = 0.0) -> list[dict]:
    """Every row of a stats REST report. The server caps a page at 100.

    `start` is an offset (measured on skater/summary: start=2 skips the
    first two). A page that adds nothing stops the loop.
    """
    found: list[dict] = []
    start = 0
    total = None
    seen_ids: set[int] = set()
    while True:
        query = f"limit={int(limit)}&start={int(start)}"
        if cayenne:
            query = f"cayenneExp={quote(cayenne)}&{query}"
        url = f"{NHL_STATS_BASE}/{path}?{query}"
        body = get(url)
        page = body.get("data") or []
        total = int(body.get("total") or 0)
        added = 0
        for row in page:
            marker = row.get("playerId", row.get("id"))
            key = int(marker) if marker is not None else None
            if key is not None and key in seen_ids:
                continue
            if key is not None:
                seen_ids.add(key)
            found.append(row)
            added += 1
        if not page or added == 0 or len(found) >= total:
            break
        start += len(page)
        if pause_s:
            time.sleep(pause_s)
        if start > total + limit:
            break
    return found


def _insert_sql(table: str, cols: tuple[str, ...], pk: tuple[str, ...]) -> str:
    sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in pk)
    values = ", ".join(
        f"%({c})s::jsonb" if c == "payload" else f"%({c})s" for c in cols)
    return (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({values}) "
        f"ON CONFLICT ({', '.join(pk)}) DO UPDATE SET {sets}, fetched_at = NOW()"
    )


_SKATER_SQL = _insert_sql(
    "nhl_edge_skater_snapshots", SKATER_COLS,
    ("snapshot_date", "season_id", "game_type", "player_id"))
_GOALIE_SQL = _insert_sql(
    "nhl_edge_goalie_snapshots", GOALIE_COLS,
    ("snapshot_date", "season_id", "game_type", "player_id"))
_TEAM_SQL = _insert_sql(
    "nhl_edge_team_snapshots", TEAM_COLS,
    ("snapshot_date", "season_id", "game_type", "team_id"))


def _flush(conn, sql: str, rows: list[dict]) -> None:
    if not rows:
        return

    def once():
        conn.executemany(sql, rows)
        conn.commit()

    try:
        once()
    except ConnectionLost:
        logger.warning("connection lost mid-batch — re-running it")
        once()


def _one(url: str, get) -> dict | None:
    try:
        return get(url)
    except FetchFailed as exc:
        if exc.status == 404:
            return None
        raise


def daily(run_date: str, apply: bool, pause_s: float = PAUSE_S, get=get_json,
          game_type: int = 2) -> dict:
    season_id = season_id_for(run_date)
    cayenne = f"seasonId={season_id} and gameTypeId={int(game_type)}"
    logger.info(f"NHL EDGE {run_date} season {season_id} game type {game_type}")
    skaters = rest_rows("skater/summary", cayenne, get=get, pause_s=pause_s)
    time.sleep(pause_s)
    goalies = rest_rows("goalie/summary", cayenne, get=get, pause_s=pause_s)
    time.sleep(pause_s)
    teams = rest_rows("team", get=get, pause_s=pause_s)
    time.sleep(pause_s)
    standings = get(f"{NHL_API_BASE}/standings/now")
    time.sleep(pause_s)
    abbrs = []
    for row in standings.get("standings") or []:
        abbrev = (row.get("teamAbbrev") or {}).get("default")
        if abbrev:
            abbrs.append(abbrev)
    club_ids = current_team_ids(teams, abbrs)
    if not skaters or not club_ids:
        raise RuntimeError(
            f"NHL EDGE roster was empty (skaters {len(skaters)}, teams {len(club_ids)})")

    skater_rows, goalie_rows, team_rows = [], [], []
    missed = 0

    def pause():
        if pause_s:
            time.sleep(pause_s)

    for row in skaters:
        pid = row.get("playerId")
        if pid is None:
            continue
        body = _one(f"{NHL_API_BASE}/edge/skater-detail/{int(pid)}/{season_id}/{game_type}", get)
        pause()
        if body is None:
            missed += 1
            continue
        record = skater_record(body, run_date, season_id, game_type)
        if record:
            skater_rows.append(record)
    for row in goalies:
        pid = row.get("playerId")
        if pid is None:
            continue
        body = _one(f"{NHL_API_BASE}/edge/goalie-detail/{int(pid)}/{season_id}/{game_type}", get)
        pause()
        if body is None:
            missed += 1
            continue
        record = goalie_record(body, run_date, season_id, game_type)
        if record:
            goalie_rows.append(record)
    for tid, abbr in club_ids:
        body = _one(f"{NHL_API_BASE}/edge/team-detail/{int(tid)}/{season_id}/{game_type}", get)
        pause()
        if body is None:
            missed += 1
            continue
        record = team_record(body, run_date, season_id, game_type, abbr)
        if record:
            team_rows.append(record)
    if not skater_rows and not goalie_rows and not team_rows:
        raise RuntimeError("NHL EDGE stored nothing")
    if apply:
        conn = get_connection()
        try:
            _flush(conn, _SKATER_SQL, skater_rows)
            _flush(conn, _GOALIE_SQL, goalie_rows)
            _flush(conn, _TEAM_SQL, team_rows)
        finally:
            conn.close()
    logger.success(
        f"NHL EDGE {run_date}: {len(skater_rows)} skaters, {len(goalie_rows)} goalies, "
        f"{len(team_rows)} teams, {missed} without a detail"
        + ("" if apply else " (dry run)"))
    return {"ok": True, "snapshot_date": run_date, "season_id": season_id,
            "skaters": len(skater_rows), "goalies": len(goalie_rows),
            "teams": len(team_rows), "missed": missed,
            "written": (len(skater_rows) + len(goalie_rows) + len(team_rows)) if apply else 0}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--daily", action="store_true", required=True)
    ap.add_argument("--date", default=None, help="YYYY-MM-DD, default today ET. This is the snapshot date.")
    ap.add_argument("--apply", action="store_true", help="write to Supabase")
    args = ap.parse_args()
    if args.date:
        run_date = args.date
    else:
        run_date = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    daily(run_date, args.apply)
