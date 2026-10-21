"""NBA schedule from stats.nba.com: tip-off times, arenas, neutral sites, overtime.

WHY. Every NBA game from 2018-19 to 2025-26 sat in `games` with
`commence_time` NULL (0 of 9,509, measured 2026-10-15), so nothing could bound a
price read on "before tip", anchor a historical purchase on a game's own start,
or know where a game was played. Five neutral-site games a season (Mexico City,
Las Vegas, Berlin, London, Paris) were missing outright: nba_stats_ingestor's
_pair_games drops a game both of whose game-log rows read "@". And `went_to_ot`
was 0 on every row.

stats.nba.com `scheduleleaguev2` carries all of it, one call per season, free:
gameDateTimeUTC, the arena, isNeutral, the NBA Cup label, national TV, the final
score and the status text ("Final/OT2").

WHAT IT WRITES.
  * `nba_schedule` -- one row per NBA.com game id, every game type (regular
    season, play-in, playoffs, NBA Cup knockout). Keyed on the NBA.com id, with
    our `game_id` beside it.
  * `games` -- fills `commence_time` where it is NULL, sets `neutral_site` and
    `went_to_ot`, and inserts a REGULAR-SEASON game that is missing (the
    neutral-site ones) with its final score. It never changes `data_source`,
    a score already stored, or a game of any other type.

stats.nba.com blocks datacenter IPs (docs/sports/nba.md), so this runs on a
residential machine; the worker reads what it wrote. Between loads the worker
keeps the schedule current from ESPN every day
(data/ingestors/nba_schedule_refresh.py, the `nba-schedule` step): new games
under an 'espn:' key, moved tips, postponements. A row this load writes
replaces that game's 'espn:' row.

    python -m data.ingestors.nba_schedule_ingestor --seasons 2019 2027
"""
from __future__ import annotations

import argparse
import re
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from loguru import logger

from data.anon_readable import lock_down
from data.db import get_connection

ET = ZoneInfo("America/New_York")

SCHEDULE_DDL = """
CREATE TABLE IF NOT EXISTS nba_schedule (
    nba_game_id     TEXT PRIMARY KEY,
    game_id         TEXT,
    season          INTEGER NOT NULL,
    game_type       TEXT NOT NULL,
    game_date       TEXT NOT NULL,
    commence_time   TEXT,
    home_team       TEXT NOT NULL,
    away_team       TEXT NOT NULL,
    home_score      INTEGER,
    away_score      INTEGER,
    status_text     TEXT,
    ot_periods      INTEGER,
    arena_name      TEXT,
    arena_city      TEXT,
    arena_state     TEXT,
    is_neutral      BOOLEAN,
    game_label      TEXT,
    game_sublabel   TEXT,
    national_tv     TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

# gameId's first three characters name the type: 0022500001 -> "002".
GAME_TYPES = {"001": "preseason", "002": "regular", "003": "allstar",
              "004": "playoff", "005": "playin", "006": "cup_final"}

_OT = re.compile(r"OT(\d*)", re.IGNORECASE)


def season_str(season: int) -> str:
    """Our label is the ENDING year (2026 = 2025-26); nba_api wants '2025-26'."""
    return f"{season - 1}-{str(season)[-2:]}"


def ot_periods(status_text: str | None) -> int | None:
    """'Final' -> 0, 'Final/OT' -> 1, 'Final/OT2' -> 2; None before the game ends."""
    if not status_text or not str(status_text).startswith("Final"):
        return None
    m = _OT.search(str(status_text))
    if not m:
        return 0
    return int(m.group(1) or 1)


def _tv(row) -> str | None:
    names = []
    for i in range(6):
        v = row.get(f"nationalBroadcasters_{i}_broadcasterDisplay")
        if isinstance(v, str) and v:
            names.append(v)
    return ",".join(names) or None


def schedule_rows(season: int, frame) -> list[dict]:
    """One dict per game in the frame scheduleleaguev2 returned for `season`."""
    out = []
    for row in frame.to_dict("records"):
        gid = str(row.get("gameId") or "")
        kind = GAME_TYPES.get(gid[:3])
        if kind is None:
            continue
        utc = row.get("gameDateTimeUTC")
        commence = None
        game_date = None
        if isinstance(utc, str) and utc:
            dt = datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone(timezone.utc)
            commence = dt.isoformat()
            game_date = dt.astimezone(ET).date().isoformat()
        if game_date is None:
            est = row.get("gameDateEst")
            game_date = str(est)[:10] if est else None
        if game_date is None:
            continue
        home = row.get("homeTeam_teamTricode")
        away = row.get("awayTeam_teamTricode")
        if not home or not away:
            continue                      # a playoff slot not yet decided
        status = row.get("gameStatusText")
        final = isinstance(status, str) and status.startswith("Final")

        def _score(v):
            try:
                return int(v) if final and v is not None else None
            except (TypeError, ValueError):
                return None

        out.append({
            "nba_game_id": gid,
            "game_id": f"NBA_{game_date}_{away}_{home}",
            "season": season,
            "game_type": kind,
            "game_date": game_date,
            "commence_time": commence,
            "home_team": home,
            "away_team": away,
            "home_score": _score(row.get("homeTeam_score")),
            "away_score": _score(row.get("awayTeam_score")),
            "status_text": status if isinstance(status, str) else None,
            "ot_periods": ot_periods(status),
            "arena_name": row.get("arenaName") or None,
            "arena_city": row.get("arenaCity") or None,
            "arena_state": row.get("arenaState") or None,
            "is_neutral": bool(row.get("isNeutral")),
            "game_label": row.get("gameLabel") or None,
            "game_sublabel": row.get("gameSubLabel") or None,
            "national_tv": _tv(row),
        })
    return out


def fetch_season(season: int):
    from nba_api.stats.endpoints import scheduleleaguev2
    for attempt in range(4):
        try:
            return scheduleleaguev2.ScheduleLeagueV2(
                season=season_str(season), timeout=90).get_data_frames()[0]
        except Exception as exc:  # noqa: BLE001 -- stats.nba.com times out at random
            logger.warning(f"schedule {season}: {type(exc).__name__}; retry {attempt + 1}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"stats.nba.com schedule for {season} failed four times")


def write(conn, rows: list[dict]) -> dict:
    conn.executemany("""
        INSERT INTO nba_schedule (nba_game_id, game_id, season, game_type, game_date,
            commence_time, home_team, away_team, home_score, away_score, status_text,
            ot_periods, arena_name, arena_city, arena_state, is_neutral, game_label,
            game_sublabel, national_tv, updated_at)
        VALUES (%(nba_game_id)s, %(game_id)s, %(season)s, %(game_type)s, %(game_date)s,
            %(commence_time)s, %(home_team)s, %(away_team)s, %(home_score)s, %(away_score)s,
            %(status_text)s, %(ot_periods)s, %(arena_name)s, %(arena_city)s, %(arena_state)s,
            %(is_neutral)s, %(game_label)s, %(game_sublabel)s, %(national_tv)s, NOW())
        ON CONFLICT (nba_game_id) DO UPDATE SET
            game_id = EXCLUDED.game_id, game_date = EXCLUDED.game_date,
            commence_time = EXCLUDED.commence_time, home_team = EXCLUDED.home_team,
            away_team = EXCLUDED.away_team,
            home_score = COALESCE(EXCLUDED.home_score, nba_schedule.home_score),
            away_score = COALESCE(EXCLUDED.away_score, nba_schedule.away_score),
            status_text = EXCLUDED.status_text,
            ot_periods = COALESCE(EXCLUDED.ot_periods, nba_schedule.ot_periods),
            arena_name = EXCLUDED.arena_name, arena_city = EXCLUDED.arena_city,
            arena_state = EXCLUDED.arena_state, is_neutral = EXCLUDED.is_neutral,
            game_label = EXCLUDED.game_label, game_sublabel = EXCLUDED.game_sublabel,
            national_tv = EXCLUDED.national_tv, updated_at = NOW()
    """, rows)
    # A game the worker's daily ESPN refresh listed before the league's own load
    # (data/ingestors/nba_schedule_refresh.py) is keyed 'espn:<event id>'. The
    # NBA.com row just written replaces it: one row a game.
    if rows:
        conn.execute("DELETE FROM nba_schedule WHERE nba_game_id LIKE %s AND game_id = ANY(%s)",
                     ("espn:%", [r["game_id"] for r in rows]))

    reg = [r for r in rows if r["game_type"] == "regular"]
    ids = [r["game_id"] for r in reg]
    have = {x[0] for x in conn.execute(
        "SELECT game_id FROM games WHERE game_id = ANY(%s)", (ids,)).fetchall()} if ids else set()

    def _ot(r):
        return (1 if r["ot_periods"] else 0) if r["ot_periods"] is not None else None

    # commence_time only where it is missing; the live feed's own start stays.
    # Batched: one statement per game over the network took ~6 minutes a season.
    upd = [(r["commence_time"], 1 if r["is_neutral"] else 0, _ot(r), r["game_id"])
           for r in reg if r["game_id"] in have]
    conn.executemany("""
        UPDATE games SET
            commence_time = COALESCE(commence_time, %s),
            neutral_site  = %s,
            went_to_ot    = COALESCE(%s, went_to_ot),
            updated_at    = NOW()::TEXT
         WHERE game_id = %s AND sport = 'NBA'
    """, upd)

    # A regular-season game `games` never received (the neutral-site ones) is
    # inserted with its score. ON CONFLICT DO NOTHING: an existing row is never
    # rewritten by this path.
    ins = []
    for r in reg:
        if r["game_id"] in have:
            continue
        hs, as_ = r["home_score"], r["away_score"]
        ins.append((r["game_id"], r["season"], r["game_date"], r["home_team"], r["away_team"],
                    hs, as_, (1 if hs > as_ else 0) if hs is not None and as_ is not None else None,
                    _ot(r) or 0, 1 if r["is_neutral"] else 0, r["commence_time"]))
    conn.executemany("""
        INSERT INTO games (game_id, sport, season, game_date, home_team, away_team,
            home_score, away_score, home_win, went_to_ot, neutral_site,
            commence_time, data_source, created_at, updated_at)
        VALUES (%s, 'NBA', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                'nba_api_schedule', NOW()::TEXT, NOW()::TEXT)
        ON CONFLICT (game_id) DO NOTHING
    """, ins)
    filled, inserted = len(upd), len(ins)
    conn.commit()
    return {"schedule_rows": len(rows), "regular": len(reg),
            "games_updated": filled, "games_inserted": inserted}


def run(first: int, last: int) -> list[dict]:
    conn = get_connection()
    try:
        conn.execute(SCHEDULE_DDL)
        lock_down(conn, "nba_schedule")
        conn.commit()
        out = []
        for season in range(first, last + 1):
            frame = fetch_season(season)
            rows = schedule_rows(season, frame)
            stats = {"season": season, **write(conn, rows)}
            logger.info(stats)
            out.append(stats)
            time.sleep(1.0)
        return out
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"), required=True)
    a = ap.parse_args()
    for s in run(*a.seasons):
        print(s)


if __name__ == "__main__":
    main()
