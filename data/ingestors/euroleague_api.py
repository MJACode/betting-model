"""EuroLeague schedule, finals and quarter scores from EuroLeague's own API.

THE SOURCE. https://api-live.euroleague.net/v2/competitions/E/seasons/<code>/games
answers without a key: one call returns a season's every game, played or
scheduled, with its UTC start, both clubs, the score, the four quarter scores
and each overtime, the referees, the venue and a neutral-venue flag. Measured
2026-11-12, seasons E2020 to E2026: 328, 327, 328, 331, 330, 402 and 380 games
(E2026, the season in progress, holds its whole 380-game regular season, so
the schedule is stored weeks ahead from the first run). On every played game
the quarter scores and overtimes sum to the final score (0 mismatches in 2,145).
28 games of E2021 are 'Cancelled' (the Russian clubs' games after 2022-02).

WHAT IS WRITTEN, all in one transaction a season:
  * euroleague_api_raw: the season's answer as fetched, once per change of its
    content (source SOURCE). Free to fetch again, kept so a change in the API
    cannot rewrite what was read.
  * euroleague_teams: each club code, its newest name and every name it has
    carried.
  * euroleague_events: one row a game (euroleague_teams.EVENT_COLS).
  * games: one row a game that is not cancelled, sport EUROLEAGUE, the home
    club's code as home_team, the score filled once the game is played (a
    stored score is never overwritten), went_to_ot, regulation_tie, home_win.
  * euroleague_period_scores: periods 1-4 and each overtime as period 5, 6 ...
    for every played game.

NEUTRAL SITES. The API flags 2 games (both 2024-25). The Final Four is played
in one host city, so every Final Four game is stored neutral too.

    python -m data.ingestors.euroleague_api --seasons 2021 2027            # dry run
    python -m data.ingestors.euroleague_api --seasons 2021 2027 --apply
    python -m data.ingestors.euroleague_api --current --apply              # the worker's daily step
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone

import requests
from loguru import logger

from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current
from data.db import get_connection
from data.ingestors import euroleague_teams as et

BASE = "https://api-live.euroleague.net/v2/competitions/E/seasons/{code}/games"
SOURCE = "euroleague_api_v2"
FIRST_SEASON = 2021            # E2020, the first season the odds feed priced
REGULATION_PERIODS = 4
HEADERS = {"User-Agent": "Mozilla/5.0 (Signalbase)", "Accept": "application/json"}

RAW = "euroleague_api_raw"
RAW_COLS = ("season_code", "endpoint", "sha1", "payload", "fetched_at")
RAW_DDL = """
CREATE TABLE IF NOT EXISTS euroleague_api_raw (
    season_code  TEXT NOT NULL,
    endpoint     TEXT NOT NULL,
    sha1         TEXT NOT NULL,
    payload      JSONB NOT NULL,
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (season_code, endpoint, sha1)
)
"""
PERIODS = "euroleague_period_scores"
PERIOD_COLS = ("game_id", "period", "home_points", "away_points", "season", "source",
               "loaded_at")
PERIODS_DDL = """
CREATE TABLE IF NOT EXISTS euroleague_period_scores (
    game_id      TEXT NOT NULL,
    period       INTEGER NOT NULL,
    home_points  INTEGER NOT NULL,
    away_points  INTEGER NOT NULL,
    season       INTEGER NOT NULL,
    source       TEXT NOT NULL,
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, period)
)
"""

_RAW_INSERT = f"""
INSERT INTO {RAW} (season_code, endpoint, sha1, payload) VALUES (%s, %s, %s, %s::jsonb)
ON CONFLICT (season_code, endpoint, sha1) DO NOTHING
"""
_TEAM_UPSERT = f"""
INSERT INTO {et.TEAMS} (code, name, names, first_season, last_season, updated_at)
VALUES (%s, %s, %s, %s, %s, NOW())
ON CONFLICT (code) DO UPDATE SET
    name = CASE WHEN EXCLUDED.last_season >= COALESCE({et.TEAMS}.last_season, 0)
                THEN EXCLUDED.name ELSE {et.TEAMS}.name END,
    names = ARRAY(SELECT DISTINCT unnest({et.TEAMS}.names || EXCLUDED.names) ORDER BY 1),
    first_season = LEAST({et.TEAMS}.first_season, EXCLUDED.first_season),
    last_season = GREATEST({et.TEAMS}.last_season, EXCLUDED.last_season),
    updated_at = NOW()
"""
_EVENT_UPSERT = f"""
INSERT INTO {et.EVENTS} (game_id, identifier, season, season_code, game_code, phase, round,
                         game_date, commence_time, home_code, away_code, neutral_site, status,
                         played, venue_code, venue_name, referees, audience, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
ON CONFLICT (game_id) DO UPDATE SET
    phase = EXCLUDED.phase, round = EXCLUDED.round, game_date = EXCLUDED.game_date,
    commence_time = EXCLUDED.commence_time, home_code = EXCLUDED.home_code,
    away_code = EXCLUDED.away_code, neutral_site = EXCLUDED.neutral_site,
    status = EXCLUDED.status, played = EXCLUDED.played, venue_code = EXCLUDED.venue_code,
    venue_name = EXCLUDED.venue_name, referees = EXCLUDED.referees,
    audience = EXCLUDED.audience, updated_at = NOW()
"""
_GAME_UPSERT = """
INSERT INTO games (game_id, sport, season, game_date, home_team, away_team, commence_time,
                   neutral_site, data_source, created_at, updated_at)
VALUES (%s, 'EUROLEAGUE', %s, %s, %s, %s, %s, %s, %s, NOW()::TEXT, NOW()::TEXT)
ON CONFLICT (game_id) DO UPDATE SET
    season = EXCLUDED.season, game_date = EXCLUDED.game_date,
    home_team = EXCLUDED.home_team, away_team = EXCLUDED.away_team,
    commence_time = EXCLUDED.commence_time, neutral_site = EXCLUDED.neutral_site,
    updated_at = NOW()::TEXT
WHERE games.sport = 'EUROLEAGUE'
"""
# A stored score is never overwritten: the WHERE refuses a row that has one.
_SCORE_FILL = """
UPDATE games SET home_score = %s, away_score = %s, home_win = %s, went_to_ot = %s,
                 regulation_tie = %s, updated_at = NOW()::TEXT
 WHERE game_id = %s AND sport = 'EUROLEAGUE'
   AND (home_score IS NULL OR away_score IS NULL)
"""
_PERIOD_INSERT = f"""
INSERT INTO {PERIODS} (game_id, period, home_points, away_points, season, source)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (game_id, period) DO NOTHING
"""


def ensure_tables(conn) -> None:
    et.ensure_tables(conn)
    changed = False
    if not schema_is_current(conn, RAW, columns=RAW_COLS, rls=True, revoked_from=API_ROLES):
        conn.execute(RAW_DDL)
        lock_down(conn, RAW)
        changed = True
    if not schema_is_current(conn, PERIODS, columns=PERIOD_COLS, rls=True,
                             revoked_from=API_ROLES):
        conn.execute(PERIODS_DDL)
        lock_down(conn, PERIODS)
        changed = True
    if changed:
        conn.commit()


# ── fetch and parse ──────────────────────────────────────────────────────────

def fetch_season(code: str, session=None) -> dict:
    s = session or requests
    r = s.get(BASE.format(code=code), headers=HEADERS, timeout=60)
    r.raise_for_status()
    body = r.json()
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise RuntimeError(f"{code}: unexpected answer shape {type(body).__name__}")
    return body


def _periods(partials: dict) -> list[int | None]:
    """[q1, q2, q3, q4, ot1, ot2 ...] from one side's partials."""
    out = [partials.get(f"partials{i}") for i in range(1, REGULATION_PERIODS + 1)]
    extra = partials.get("extraPeriods") or {}
    for k in sorted(extra, key=lambda x: int(x)):
        out.append(extra[k])
    return out


def parse_game(g: dict) -> dict:
    """One game of the API's answer -> the row values. Pure."""
    ident = g["identifier"]
    code = g["season"]["code"]
    season = et.season_label(code)
    home, away = g["local"], g["road"]
    phase = (g.get("phaseType") or {}).get("code")
    status = g.get("gameStatus")
    played = bool(g.get("played")) and status != "Cancelled"
    utc = g.get("utcDate")
    commence = (datetime.fromisoformat(utc.replace("Z", "+00:00")).isoformat()
                if utc else None)
    local_date = str(g.get("localDate") or g.get("date") or utc or "")[:10]
    refs = [(g.get(f"referee{i}") or {}).get("name") for i in range(1, 5)]
    venue = g.get("venue") or {}
    row = {
        "game_id": et.build_game_id(ident), "identifier": ident, "season": season,
        "season_code": code, "game_code": int(g["gameCode"]), "phase": phase,
        "round": g.get("round"), "game_date": local_date, "commence_time": commence,
        "home_code": home["club"]["code"], "away_code": away["club"]["code"],
        "home_name": home["club"]["name"], "away_name": away["club"]["name"],
        "neutral_site": bool(g.get("isNeutralVenue")) or phase == "FF",
        "status": status, "played": played,
        "venue_code": venue.get("code"), "venue_name": venue.get("name"),
        "referees": [r for r in refs if r], "audience": g.get("audience"),
        "home_score": None, "away_score": None, "periods": [],
    }
    if played:
        hp, ap = _periods(home.get("partials") or {}), _periods(away.get("partials") or {})
        hs, as_ = home.get("score"), away.get("score")
        if None in hp or None in ap or len(hp) != len(ap):
            raise ValueError(f"{ident}: incomplete quarter scores {hp} / {ap}")
        if sum(hp) != hs or sum(ap) != as_:
            raise ValueError(f"{ident}: quarters {sum(hp)}-{sum(ap)} do not sum to {hs}-{as_}")
        row.update(home_score=hs, away_score=as_,
                   periods=[(i + 1, h, a) for i, (h, a) in enumerate(zip(hp, ap))])
    return row


def results(row: dict) -> tuple | None:
    """(home_win, went_to_ot, regulation_tie) for a played game, else None."""
    if row["home_score"] is None:
        return None
    reg_h = sum(h for p, h, _ in row["periods"] if p <= REGULATION_PERIODS)
    reg_a = sum(a for p, _, a in row["periods"] if p <= REGULATION_PERIODS)
    ot = int(len(row["periods"]) > REGULATION_PERIODS)
    return int(row["home_score"] > row["away_score"]), ot, int(reg_h == reg_a)


# ── store ────────────────────────────────────────────────────────────────────

def store_season(conn, body: dict) -> dict:
    """One season's answer into the database, one transaction. Returns counts."""
    games = [parse_game(g) for g in body["data"]]
    if not games:
        return {"games": 0}
    code = games[0]["season_code"]
    season = games[0]["season"]
    payload = json.dumps(body, sort_keys=True)
    digest = hashlib.sha1(payload.encode()).hexdigest()
    clubs: dict[str, set] = {}
    for r in games:
        clubs.setdefault(r["home_code"], set()).add(r["home_name"])
        clubs.setdefault(r["away_code"], set()).add(r["away_name"])
    stats = {"season": season, "games": len(games), "played": 0, "cancelled": 0,
             "period_rows": 0}
    conn.execute(_RAW_INSERT, (code, "v2/games", digest, payload))
    conn.executemany(_TEAM_UPSERT, [(c, sorted(n)[-1], sorted(n), season, season)
                                    for c, n in clubs.items()])
    conn.executemany(_EVENT_UPSERT, [(
        r["game_id"], r["identifier"], r["season"], r["season_code"], r["game_code"],
        r["phase"], r["round"], r["game_date"], r["commence_time"], r["home_code"],
        r["away_code"], r["neutral_site"], r["status"], r["played"], r["venue_code"],
        r["venue_name"], r["referees"], r["audience"]) for r in games])
    live = [r for r in games if r["status"] != "Cancelled"]
    stats["cancelled"] = len(games) - len(live)
    conn.executemany(_GAME_UPSERT, [(r["game_id"], r["season"], r["game_date"], r["home_code"],
                                     r["away_code"], r["commence_time"],
                                     int(r["neutral_site"]), SOURCE) for r in live])
    fills, periods = [], []
    for r in live:
        res = results(r)
        if res is None:
            continue
        stats["played"] += 1
        fills.append((r["home_score"], r["away_score"], *res, r["game_id"]))
        periods += [(r["game_id"], p_, h, a, r["season"], SOURCE) for p_, h, a in r["periods"]]
    if fills:
        conn.executemany(_SCORE_FILL, fills)
    if periods:
        conn.executemany(_PERIOD_INSERT, periods)
    stats["period_rows"] = len(periods)
    conn.commit()
    return stats


def current_season_label(now: datetime | None = None) -> int:
    """The season in progress by the calendar: from August the season that ends
    next year. Only picks which season the daily step asks for; every stored
    label comes from the API's own season code."""
    now = now or datetime.now(timezone.utc)
    return now.year + 1 if now.month >= 8 else now.year


def run(seasons: list[int], apply: bool) -> list[dict]:
    out = []
    with requests.Session() as s:
        bodies = [(label, fetch_season(et.season_code(label), s)) for label in seasons]
    for label, body in bodies:
        rows = [parse_game(g) for g in body["data"]]
        played = sum(1 for r in rows if r["played"])
        print(f"EuroLeague {et.season_code(label)} (season {label}): {len(rows)} games, "
              f"{played} played, {sum(1 for r in rows if r['status'] == 'Cancelled')} cancelled")
        if not apply:
            continue
        with get_connection() as conn:
            ensure_tables(conn)
            st = store_season(conn, body)
        logger.info(f"EuroLeague store: {st}")
        out.append(st)
    if not apply:
        print("dry run: nothing written (add --apply)")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EuroLeague games, finals and quarter scores")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"),
                   help="ending-year labels, e.g. 2021 2027")
    g.add_argument("--current", action="store_true", help="the season in progress only")
    ap.add_argument("--apply", action="store_true", help="write to the database")
    a = ap.parse_args(argv)
    seasons = ([current_season_label()] if a.current
               else list(range(a.seasons[0], a.seasons[1] + 1)))
    run(seasons, a.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
