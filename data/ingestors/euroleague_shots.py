"""EuroLeague shot charts from EuroLeague's own API: every shot, with the
wall-clock time it was logged.

WHY. The in-play prices are stored every 5 minutes during games
(euroleague_inplay_quotes), but a model that decides at a moment of the game
(halftime, the end of a quarter) has to know when that moment was on the wall
clock. EuroLeague's play-by-play carries only the game clock (MINUTE,
MARKERTIME). Its shot chart, `live.euroleague.net/api/Points`, carries a UTC
stamp on every shot (`UTC`, e.g. 20251211190842 on a game that tipped at
19:05:00Z), measured 2026-11-13. The last shot of the second quarter and the
first of the third bracket halftime on the wall clock.

WHAT IS WRITTEN. One row per shot in euroleague_shots (worker-only): the
game, the shot's running number (NUM_ANOT), the club, player id and name, the
action (2FGM, 2FGA, 3FGM, 3FGA, FTM, FTA ...), points, court coordinates and
zone, fastbreak / second-chance / points-off-turnover flags, the minute and
game clock, the running score (A is the home club: TeamA is EuroLeague's
local club), and the UTC time. Keyed on (game_id, num_anot), so a re-run
stores nothing twice. A played game whose chart came back empty is recorded
in euroleague_shot_fetches so it is not asked again every run.

    python -m data.ingestors.euroleague_shots --seasons 2022 2027            # dry run
    python -m data.ingestors.euroleague_shots --seasons 2022 2027 --apply
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone

import requests
from loguru import logger

from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current
from data.db import get_connection

URL = "https://live.euroleague.net/api/Points"
HEADERS = {"User-Agent": "Mozilla/5.0 (Signalbase)", "Accept": "application/json"}
SOURCE = "euroleague_api_points"
# One call at a time: four at once tripped Cloudflare's rate limit (HTTP 429,
# error 1015) after 63 games on 2026-11-13.
PAUSE_S = 1.5
BACKOFF_S = 60
RETRIES = 5
TABLE = "euroleague_shots"
COLS = ("game_id", "num_anot", "team", "player_id", "player", "action", "points",
        "coord_x", "coord_y", "zone", "fastbreak", "second_chance", "points_off_turnover",
        "minute", "console", "points_home", "points_away", "shot_utc", "source")
DDL = """
CREATE TABLE IF NOT EXISTS euroleague_shots (
    game_id              TEXT NOT NULL,
    num_anot             INTEGER NOT NULL,
    team                 TEXT,
    player_id            TEXT,
    player               TEXT,
    action               TEXT,
    points               INTEGER,
    coord_x              INTEGER,
    coord_y              INTEGER,
    zone                 TEXT,
    fastbreak            BOOLEAN,
    second_chance        BOOLEAN,
    points_off_turnover  BOOLEAN,
    minute               INTEGER,
    console              TEXT,
    points_home          INTEGER,
    points_away          INTEGER,
    shot_utc             TIMESTAMPTZ,
    source               TEXT NOT NULL,
    loaded_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, num_anot)
)
"""
FETCHES = "euroleague_shot_fetches"
FETCH_COLS = ("game_id", "fetched_at", "shots", "status")
FETCH_DDL = """
CREATE TABLE IF NOT EXISTS euroleague_shot_fetches (
    game_id     TEXT PRIMARY KEY,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    shots       INTEGER NOT NULL,
    status      TEXT NOT NULL
)
"""
_INSERT = (f"INSERT INTO {TABLE} ({', '.join(COLS)}) VALUES ({', '.join(['%s'] * len(COLS))}) "
           "ON CONFLICT (game_id, num_anot) DO NOTHING")
_FETCH_UPSERT = f"""
INSERT INTO {FETCHES} (game_id, fetched_at, shots, status) VALUES (%s, NOW(), %s, %s)
ON CONFLICT (game_id) DO UPDATE SET fetched_at = NOW(), shots = EXCLUDED.shots,
    status = EXCLUDED.status
"""


def ensure_tables(conn) -> None:
    changed = False
    if not schema_is_current(conn, TABLE, columns=COLS, rls=True, revoked_from=API_ROLES):
        conn.execute(DDL)
        lock_down(conn, TABLE)
        changed = True
    if not schema_is_current(conn, FETCHES, columns=FETCH_COLS, rls=True,
                             revoked_from=API_ROLES):
        conn.execute(FETCH_DDL)
        lock_down(conn, FETCHES)
        changed = True
    if changed:
        conn.commit()


def _utc(v) -> datetime | None:
    s = str(v or "").strip()
    if len(s) != 14 or not s.isdigit():
        return None
    return datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse(game_id: str, body: dict) -> list[tuple]:
    """The API's answer -> row tuples in COLS order. Pure."""
    out = []
    for r in (body or {}).get("Rows") or []:
        n = _int(r.get("NUM_ANOT"))
        if n is None:
            continue
        out.append((
            game_id, n, (r.get("TEAM") or "").strip() or None,
            (r.get("ID_PLAYER") or "").strip() or None, r.get("PLAYER"),
            (r.get("ID_ACTION") or "").strip() or None, _int(r.get("POINTS")),
            _int(r.get("COORD_X")), _int(r.get("COORD_Y")), r.get("ZONE"),
            str(r.get("FASTBREAK")) == "1", str(r.get("SECOND_CHANCE")) == "1",
            str(r.get("POINTS_OFF_TURNOVER")) == "1", _int(r.get("MINUTE")),
            r.get("CONSOLE"), _int(r.get("POINTS_A")), _int(r.get("POINTS_B")),
            _utc(r.get("UTC")), SOURCE))
    return out


def fetch(session, season_code: str, game_code: int) -> dict:
    r = session.get(URL, params={"gamecode": game_code, "seasoncode": season_code},
                    headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json() if r.text.strip() else {}


def todo(conn, first: int, last: int) -> list[tuple]:
    """Played games of seasons first..last with no fetch on record:
    (game_id, season_code, game_code)."""
    have = set()
    if conn.execute(f"SELECT to_regclass('public.{FETCHES}')").fetchone()[0] is not None:
        have = {r[0] for r in conn.execute(f"SELECT game_id FROM {FETCHES}").fetchall()}
    rows = conn.execute(
        "SELECT game_id, season_code, game_code FROM euroleague_events "
        "WHERE season BETWEEN %s AND %s AND played ORDER BY commence_time DESC",
        (first, last)).fetchall()
    conn.commit()
    return [tuple(r) for r in rows if r[0] not in have]


def run(first: int, last: int, apply: bool) -> dict:
    with get_connection() as conn:
        if apply:
            ensure_tables(conn)
        games = todo(conn, first, last)
    print(f"EuroLeague shots, seasons {first}-{last}: {len(games)} played games to fetch")
    if not apply:
        print("dry run: nothing fetched or written (add --apply)")
        return {"todo": len(games)}
    stats = {"games": 0, "shots": 0, "empty": 0, "errors": 0}
    session = requests.Session()

    def one(g):
        """One game, sequentially, PAUSE_S apart. On HTTP 429 (Cloudflare's
        rate limit, error 1015) wait and ask again, BACKOFF_S doubling; a
        game still refused after RETRIES stops the run (the next run resumes)."""
        gid, code, n = g
        wait = BACKOFF_S
        for _ in range(RETRIES):
            time.sleep(PAUSE_S)
            try:
                return gid, parse(gid, fetch(session, code, n)), None
            except requests.HTTPError as exc:
                if getattr(exc.response, "status_code", None) != 429:
                    return gid, [], str(exc)[:200]
                logger.warning(f"EuroLeague shots: rate-limited at {gid}; waiting {wait}s")
                time.sleep(wait)
                wait *= 2
            except Exception as exc:                            # noqa: BLE001
                return gid, [], str(exc)[:200]
        return gid, [], "RATE_LIMITED"

    with get_connection() as conn:
        for g in games:
            gid, rows, err = one(g)
            if err == "RATE_LIMITED":
                stats["stopped"] = f"still rate-limited at {gid}; a re-run resumes"
                logger.warning(f"EuroLeague shots: {stats['stopped']}")
                break
            if err:
                stats["errors"] += 1
                logger.warning(f"EuroLeague shots {gid}: {err}")
                continue
            if rows:
                conn.executemany(_INSERT, rows)
            conn.execute(_FETCH_UPSERT, (gid, len(rows), "ok" if rows else "empty"))
            conn.commit()
            stats["games"] += 1
            stats["shots"] += len(rows)
            stats["empty"] += int(not rows)
            if stats["games"] % 200 == 0:
                logger.info(f"EuroLeague shots: {stats}")
    print("EuroLeague shots:", stats)
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EuroLeague shot charts with wall-clock times")
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"), required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    st = run(a.seasons[0], a.seasons[1], a.apply)
    return 1 if st.get("errors") or st.get("stopped") else 0


if __name__ == "__main__":
    sys.exit(main())
