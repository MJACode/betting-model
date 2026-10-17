"""NHL box scores for prop settlement, from the game that just ended.

Game lines settle off `/v1/score`, which the refresh pass stores every tick.
Skater and goalie props settle off `nhl_skater_game_log` / `nhl_goalie_game_log`,
and those tables were filled only by the morning `top_up` inside
`run_nhl_stats_ingestor` — which the daily pipeline runs AFTER settle. A
final at 10pm therefore graded its moneyline on the evening pass and its
shots-on-goal prop at 7:23am, on the first settle that could see the log.

`/v1/gamecenter/{id}/boxscore` is on the same host as the score, and it is
up when the game is OFF. This module writes the columns the settler reads
(shots, assists, blocked shots, saves, started) and nothing else. The morning
`top_up` still replaces the row with the full stats-API report; the insert
is ON CONFLICT DO NOTHING so a later box pull cannot blank those columns.

One game is one savepoint and one commit. A statement timeout rolls that
game back and the next game still runs.
"""
from __future__ import annotations

from data.db import call_in_savepoint, get_connection, statement_timeout
from data.ingestors.nhl_stats_ingestor import (NHL_API_BASE, NHL_HEADERS,
                                               _norm_nhl, parse_nhl_game)
from data.season_labels import nhl_season_label

BOX_SOURCE = "nhl_web_api|boxscore"

_SKATER_COLS = (
    "nhl_game_id", "player_id", "player_name", "position", "game_id", "season",
    "game_type", "game_date", "team", "opponent", "is_home", "goals", "assists",
    "points", "shots", "pp_goals", "plus_minus", "pim", "hits", "blocked_shots",
    "toi_seconds", "shifts", "source",
)
_GOALIE_COLS = (
    "nhl_game_id", "player_id", "player_name", "game_id", "season", "game_type",
    "game_date", "team", "opponent", "is_home", "started", "decision",
    "toi_seconds", "shots_against", "saves", "goals_against", "source",
)
_TEAM_COLS = (
    "nhl_game_id", "team", "game_id", "season", "game_type", "game_date",
    "opponent", "is_home", "goals_for", "goals_against", "shots_for", "source",
)


def toi_seconds(text) -> int | None:
    """'11:44' and '61:05' are minutes:seconds. A third field is hours."""
    if not isinstance(text, str) or ":" not in text:
        return None
    parts = text.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return None


def _int(v):
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _name(player: dict) -> str:
    raw = player.get("name")
    if isinstance(raw, dict):
        return str(raw.get("default") or "").strip()
    return str(raw or "").strip()


def _decision(raw) -> str | None:
    d = str(raw or "").strip().upper()
    if d in ("W", "L"):
        return d
    if d in ("O", "OT", "OTL"):
        return "OTL"
    return None


def parse_boxscore(payload: dict, game_id: str, game_date: str) -> dict:
    """Team, skater and goalie rows for one final. Empty when the box is
    not posted yet — the caller must not treat that as a logged game."""
    empty = {"team": [], "skater": [], "goalie": []}
    if not payload or not game_id or not game_date:
        return empty
    sides = (payload.get("playerByGameStats") or {})
    home = payload.get("homeTeam") or {}
    away = payload.get("awayTeam") or {}
    home_abbr = _norm_nhl(home.get("abbrev") or "")
    away_abbr = _norm_nhl(away.get("abbrev") or "")
    if not home_abbr or not away_abbr:
        return empty
    try:
        nhl_game_id = int(payload.get("id"))
    except (TypeError, ValueError):
        return empty
    season_raw = payload.get("season")
    try:
        season = int(str(season_raw)[-4:])
    except (TypeError, ValueError):
        season = nhl_season_label(game_date)
    game_type = _int(payload.get("gameType")) or 2

    def side_rows(block: dict, team: str, opp: str, is_home: int) -> tuple[list, list]:
        skaters, goalies = [], []
        for group in ("forwards", "defense"):
            for p in (block or {}).get(group) or []:
                pid = _int(p.get("playerId"))
                name = _name(p)
                if pid is None or not name:
                    continue
                skaters.append({
                    "nhl_game_id": nhl_game_id, "player_id": pid, "player_name": name,
                    "position": p.get("position"), "game_id": game_id, "season": season,
                    "game_type": game_type, "game_date": game_date, "team": team,
                    "opponent": opp, "is_home": is_home,
                    "goals": _int(p.get("goals")), "assists": _int(p.get("assists")),
                    "points": _int(p.get("points")), "shots": _int(p.get("sog")),
                    "pp_goals": _int(p.get("powerPlayGoals")),
                    "plus_minus": _int(p.get("plusMinus")), "pim": _int(p.get("pim")),
                    "hits": _int(p.get("hits")),
                    "blocked_shots": _int(p.get("blockedShots")),
                    "toi_seconds": toi_seconds(p.get("toi")),
                    "shifts": _int(p.get("shifts")), "source": BOX_SOURCE,
                })
        for p in (block or {}).get("goalies") or []:
            pid = _int(p.get("playerId"))
            name = _name(p)
            if pid is None or not name:
                continue
            goalies.append({
                "nhl_game_id": nhl_game_id, "player_id": pid, "player_name": name,
                "game_id": game_id, "season": season, "game_type": game_type,
                "game_date": game_date, "team": team, "opponent": opp,
                "is_home": is_home, "started": int(bool(p.get("starter"))),
                "decision": _decision(p.get("decision")),
                "toi_seconds": toi_seconds(p.get("toi")),
                "shots_against": _int(p.get("shotsAgainst")),
                "saves": _int(p.get("saves")),
                "goals_against": _int(p.get("goalsAgainst")),
                "source": BOX_SOURCE,
            })
        return skaters, goalies

    away_sk, away_g = side_rows(sides.get("awayTeam"), away_abbr, home_abbr, 0)
    home_sk, home_g = side_rows(sides.get("homeTeam"), home_abbr, away_abbr, 1)
    skaters = away_sk + home_sk
    goalies = away_g + home_g
    if not skaters and not goalies:
        return empty
    teams = [
        {
            "nhl_game_id": nhl_game_id, "team": away_abbr, "game_id": game_id,
            "season": season, "game_type": game_type, "game_date": game_date,
            "opponent": home_abbr, "is_home": 0,
            "goals_for": _int(away.get("score")), "goals_against": _int(home.get("score")),
            "shots_for": _int(away.get("sog")), "source": BOX_SOURCE,
        },
        {
            "nhl_game_id": nhl_game_id, "team": home_abbr, "game_id": game_id,
            "season": season, "game_type": game_type, "game_date": game_date,
            "opponent": away_abbr, "is_home": 1,
            "goals_for": _int(home.get("score")), "goals_against": _int(away.get("score")),
            "shots_for": _int(home.get("sog")), "source": BOX_SOURCE,
        },
    ]
    return {"team": teams, "skater": skaters, "goalie": goalies}


def _insert_absent(conn, table: str, conflict: tuple[str, ...], cols: tuple[str, ...],
                   rows: list[dict]) -> int:
    if not rows:
        return 0
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) "
        f"VALUES ({', '.join('%(' + c + ')s' for c in cols)}) "
        f"ON CONFLICT ({', '.join(conflict)}) DO NOTHING"
    )
    conn.executemany(sql, [{c: r.get(c) for c in cols} for r in rows])
    return len(rows)


def store_boxscore(conn, parsed: dict) -> dict:
    """Insert one game. Existing rows are left as they are, so the morning
    stats-API top-up is not overwritten by this thinner box."""
    if not parsed["skater"] and not parsed["goalie"]:
        return {"team": 0, "skater": 0, "goalie": 0}

    def _write():
        return {
            "team": _insert_absent(conn, "nhl_team_game_log", ("nhl_game_id", "team"),
                                   _TEAM_COLS, parsed["team"]),
            "skater": _insert_absent(conn, "nhl_skater_game_log",
                                     ("nhl_game_id", "player_id"),
                                     _SKATER_COLS, parsed["skater"]),
            "goalie": _insert_absent(conn, "nhl_goalie_game_log",
                                     ("nhl_game_id", "player_id"),
                                     _GOALIE_COLS, parsed["goalie"]),
        }

    return call_in_savepoint(conn, "nhl_box_game", _write)


def fill_missing(dates_to_games: dict[str, set[str]], *, get_json=None,
                 connect=None) -> dict:
    """Fetch and store box scores for the given dates' game ids only.

    `dates_to_games` is `{game_date: {our game_id, ...}}`. A date whose box
    is not up yet is skipped; the next pass asks again. One game's timeout
    does not drop the others.
    """
    import requests
    from loguru import logger

    if not dates_to_games:
        return {"games": 0, "skipped": 0, "errors": 0}

    def _default_get(url):
        resp = requests.get(url, headers=NHL_HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.json()

    get_json = get_json or _default_get
    own = connect is None
    conn = (connect or get_connection)()
    games = skipped = errors = 0
    try:
        for game_date, wanted in sorted(dates_to_games.items()):
            if not wanted:
                continue
            try:
                score = get_json(f"{NHL_API_BASE}/score/{game_date}")
            except Exception as exc:                          # noqa: BLE001
                logger.warning(f"NHL box score: score fetch {game_date} failed: {exc}")
                errors += 1
                continue
            for g in (score or {}).get("games") or []:
                row = parse_nhl_game(g)
                if not row or row.get("home_score") is None:
                    continue
                if row["game_id"] not in wanted:
                    continue
                nhl_id = g.get("id")
                if nhl_id is None:
                    skipped += 1
                    continue
                try:
                    box = get_json(f"{NHL_API_BASE}/gamecenter/{nhl_id}/boxscore")
                    parsed = parse_boxscore(box, row["game_id"], row["game_date"])
                    if not parsed["skater"] and not parsed["goalie"]:
                        skipped += 1
                        continue
                    store_boxscore(conn, parsed)
                    conn.commit()
                    games += 1
                except Exception as exc:                      # noqa: BLE001
                    if statement_timeout(exc):
                        logger.warning(
                            f"NHL box score: {row['game_id']} timed out — next pass")
                    else:
                        logger.warning(f"NHL box score: {row['game_id']} failed: {exc}")
                    errors += 1
                    try:
                        conn.rollback()
                    except Exception:                          # noqa: BLE001
                        pass
    finally:
        if own:
            conn.close()
    logger.info(f"NHL box scores: {games} game(s) stored, {skipped} not posted, "
                f"{errors} error(s)")
    return {"games": games, "skipped": skipped, "errors": errors}
