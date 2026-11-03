"""ncaab_player_box.py -- men's college basketball player box scores from ESPN.

WHY THIS EXISTS. The Stats tab (Matt, 2026-11-03) needs one row per player per
game for Hit Rates (L3/L5/L10/H2H) and the Averages windows, the shape every
other basketball league already has (wnba_player_game_log,
nba_player_game_log). ncaab_player_season holds season totals only, and only
to 2025-26 (sportsdataverse has no in-season build).

THE SOURCE is the same ESPN game summary data/ingestors/ncaab_espn_box.py
already fetches for every final: `boxscore.players[]`, one block per team, each
with `statistics[0].labels` and an `athletes[]` list. Stats are read BY LABEL
(MIN, PTS, FG, 3PT, FT, REB, AST, TO, STL, BLK, OREB, DREB, PF), with the NBA
parser's rules for who played (data/ingestors/nba_espn_box.py): a didNotPlay
athlete, or one with no minutes and every count zero, is left out.

TWO WRITE PATHS, ONE TABLE:
  * the team box feed calls store_from_summary() on the payload it already
    holds, so a new final costs no extra ESPN call;
  * run_recent() / run_backfill() fetch the summary for finals that have no
    player rows yet (games stored before this module existed, 2025-26, and any
    game whose player box was refused and is due again).

WHAT IT REFUSES, recorded in ncaab_player_box_misses, never guessed:
  * a summary that is not for the stored event, or whose team blocks do not
    name the stored pair of ESPN team ids;
  * a team whose players' points do not add up to the stored final (the
    stored final settled the picks, CLAUDE.md section 1c), or that has no
    player who played.
A refused game stores nothing, and the team box is never held back by it.

COST. run_recent reads the database first and calls ESPN only for finals of
the last RECENT_DAYS ET dates with no player row. In steady state that is
none, because the team box feed stores them; it exists so a refused or
pre-existing game is picked up. At most MAX_GAMES_PER_PASS games and
TIME_BUDGET_S seconds a pass. 403 or 429 stops the run.

Usage:
    python -m data.ingestors.ncaab_player_box --recent [--date D] [--days 3]
    python -m data.ingestors.ncaab_player_box --seasons 2026 2027
"""
from __future__ import annotations

import argparse
import time
from datetime import date, datetime, timedelta, timezone

from loguru import logger

from data.db import ConnectionLost, call_in_savepoint, get_connection
from data.ingestors import ncaab_espn_box as box
from data.ingestors.nba_espn_box import _played
from data.ingestors.wnba_results_ingestor import _min_to_float, _split_made_att, _to_int

SOURCE = "espn_summary"
TABLE = "ncaab_player_game_log"
MISSES_TABLE = "ncaab_player_box_misses"
MIGRATION = "add_ncaab_player_game_log_2026_11_03.sql"

RECENT_DAYS = 3
MAX_GAMES_PER_PASS = 40
TIME_BUDGET_S = 60.0
REQUEST_SLEEP = box.REQUEST_SLEEP
MAX_ATTEMPTS = 6
COOL_MINUTES = 50
STOP_AFTER_FAILURES = 3

# Earliest season the job may backfill: 2025-26 (ending-year label). Matt,
# 2026-11-03: "This season + 2025-26".
FIRST_SEASON = 2026

COLS = ("game_id", "player_id", "player_name", "team", "team_espn_id", "espn_event_id",
        "season", "game_date", "position", "is_starter", "minutes", "points", "rebounds",
        "offensive_reb", "defensive_reb", "assists", "steals", "blocks", "turnovers",
        "fouls", "fg_made", "fg_att", "fg3_made", "fg3_att", "ft_made", "ft_att", "source")

_INSERT = (f"INSERT INTO {TABLE} (" + ", ".join(COLS) + ") VALUES ("
           + ", ".join(["%s"] * len(COLS)) + ") ON CONFLICT (game_id, player_id) DO NOTHING")
_MISS_UPSERT = f"""
INSERT INTO {MISSES_TABLE} (espn_event_id, game_id, attempts, first_at, last_at, reason)
VALUES (%s, %s, 1, %s, %s, %s)
ON CONFLICT (espn_event_id) DO UPDATE SET
    attempts = {MISSES_TABLE}.attempts + 1,
    last_at  = EXCLUDED.last_at,
    reason   = EXCLUDED.reason
"""
_CLEAR_MISS = f"DELETE FROM {MISSES_TABLE} WHERE espn_event_id = %s"


class Refused(ValueError):
    """ESPN answered, but not with a player box this module will store."""


# ── parsing ──────────────────────────────────────────────────────────────────

def _blocks(js: dict):
    """(ESPN team id, label index, statistics block) per team."""
    for tb in ((js or {}).get("boxscore") or {}).get("players") or []:
        tid = box._int(((tb or {}).get("team") or {}).get("id"))
        stats = (tb or {}).get("statistics") or []
        if tid is None or not stats:
            continue
        block = stats[0] or {}
        labels = [str(x).upper() for x in (block.get("labels") or block.get("names") or [])]
        yield tid, {lab: i for i, lab in enumerate(labels)}, block


def parse_players(js: dict) -> dict[int, list[dict]]:
    """ESPN team id -> the players who played, each stat read by label."""
    out: dict[int, list[dict]] = {}
    for tid, idx, block in _blocks(js):
        def stat(row, label, idx=idx):
            i = idx.get(label)
            return row[i] if i is not None and i < len(row) else None

        players = out.setdefault(tid, [])
        for ath in block.get("athletes") or []:
            if not _played(ath, idx):
                continue
            row = ath.get("stats") or []
            a = ath.get("athlete") or {}
            pid, name = str(a.get("id") or "").strip(), str(a.get("displayName") or "").strip()
            if not pid or not name:
                continue
            fg_m, fg_a = _split_made_att(stat(row, "FG"))
            fg3_m, fg3_a = _split_made_att(stat(row, "3PT"))
            ft_m, ft_a = _split_made_att(stat(row, "FT"))
            pos = (a.get("position") or {}).get("abbreviation") if isinstance(a.get("position"), dict) else None
            players.append({
                "player_id": pid, "player_name": name,
                "position": (str(pos).strip() or None) if pos else None,
                "is_starter": 1 if ath.get("starter") else 0,
                "minutes": _min_to_float(stat(row, "MIN")),
                "points": _to_int(stat(row, "PTS")),
                "rebounds": _to_int(stat(row, "REB")),
                "offensive_reb": _to_int(stat(row, "OREB")),
                "defensive_reb": _to_int(stat(row, "DREB")),
                "assists": _to_int(stat(row, "AST")),
                "steals": _to_int(stat(row, "STL")),
                "blocks": _to_int(stat(row, "BLK")),
                "turnovers": _to_int(stat(row, "TO")),
                "fouls": _to_int(stat(row, "PF")),
                "fg_made": fg_m, "fg_att": fg_a,
                "fg3_made": fg3_m, "fg3_att": fg3_a,
                "ft_made": ft_m, "ft_att": ft_a,
            })
    return out


def player_rows(game: dict, js: dict) -> list[tuple]:
    """The rows for one stored game (COLS order). Refused unless both stored
    teams are present and each team's player points equal its stored final."""
    header = (js or {}).get("header") or {}
    if box._int(header.get("id")) != int(game["espn_event_id"]):
        raise Refused(f"summary is for event {header.get('id')}, not {game['espn_event_id']}")
    by_team = parse_players(js)
    home, away = int(game["home_espn_id"]), int(game["away_espn_id"])
    if not {home, away} <= set(by_team):
        raise Refused(f"player box names teams {sorted(by_team)}, stored pair "
                      f"{sorted((home, away))}")
    hs, as_ = box._final(game)
    rows = []
    for tid, name, final in ((home, game["home_team"], hs), (away, game["away_team"], as_)):
        players = by_team[tid]
        if not players:
            raise Refused(f"team {tid} has no player who played")
        pts = sum(p["points"] or 0 for p in players)
        if pts != final:
            raise Refused(f"team {tid} players score {pts}, final {final}")
        for p in players:
            r = dict(p, game_id=game["game_id"], team=name, team_espn_id=tid,
                     espn_event_id=int(game["espn_event_id"]), season=int(game["season"]),
                     game_date=game["game_date"], source=SOURCE)
            rows.append(tuple(r[c] for c in COLS))
    return rows


# ── the database ─────────────────────────────────────────────────────────────

def ensure_tables(conn) -> None:
    """Apply the migration when the table is missing. On a current schema this
    is one catalog read and no DDL (data/ddl_guard.py)."""
    row = conn.execute("SELECT to_regclass(%s), to_regclass(%s)",
                       (f"public.{TABLE}", f"public.{MISSES_TABLE}")).fetchone()
    if row and row[0] is not None and row[1] is not None:
        conn.rollback()
        return
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / "migrations" / MIGRATION
    conn.execute(path.read_text(encoding="utf-8"))
    conn.commit()


def write_players(conn, rows: list[tuple]) -> int:
    def _write():
        if rows:
            conn.executemany(_INSERT, rows)
        return len(rows)
    return call_in_savepoint(conn, "ncaab_player_box", _write)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def record_miss(conn, game: dict, reason: str, now: datetime) -> None:
    stamp = _iso(now)
    call_in_savepoint(conn, "ncaab_player_box_miss", lambda: conn.execute(
        _MISS_UPSERT, (game["espn_event_id"], game["game_id"], stamp, stamp, reason[:300])))


def store_from_summary(conn, game: dict, js: dict, now: datetime) -> tuple[int, str | None]:
    """Parse and store one game's player box from a summary already in hand.
    Returns (rows sent, refusal reason or None). Never raises on content; the
    caller commits."""
    try:
        rows = player_rows(game, js)
    except (Refused, box.Refused, KeyError, TypeError, AttributeError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, (Refused, box.Refused)) else f"malformed: {exc!r}"
        logger.warning(f"NCAAB player box: {game['game_id']} not stored: {reason}")
        record_miss(conn, game, reason, now)
        return 0, reason
    n = write_players(conn, rows)
    call_in_savepoint(conn, "ncaab_player_box_clear",
                      lambda: conn.execute(_CLEAR_MISS, (game["espn_event_id"],)))
    return n, None


_NO_PLAYERS = (f" AND NOT EXISTS (SELECT 1 FROM {TABLE} p "
               "WHERE p.espn_event_id = e.espn_event_id)")
_NOT_COOLING = (f" AND NOT EXISTS (SELECT 1 FROM {MISSES_TABLE} m "
                "WHERE m.espn_event_id = e.espn_event_id "
                "AND (m.attempts >= %s OR m.last_at > %s))")


def due_games(conn, *, first: str | None = None, last: str | None = None,
              seasons: tuple[int, int] | None = None, now: datetime,
              respect_misses: bool = True, limit: int | None = None) -> list[dict]:
    """Finals with an ESPN event and no player rows, newest first."""
    sql, params = box._GAMES_SQL, []
    if first is not None:
        sql += " AND g.game_date >= %s AND g.game_date <= %s"
        params += [first, last]
    if seasons is not None:
        sql += " AND e.season >= %s AND e.season <= %s"
        params += list(seasons)
    sql += _NO_PLAYERS
    if respect_misses:
        sql += _NOT_COOLING
        params += [MAX_ATTEMPTS, _iso(now - timedelta(minutes=COOL_MINUTES))]
    sql += box._NEWEST_FIRST
    if limit is not None:
        sql += " LIMIT %s"
        params.append(int(limit))
    return box._rows_to_games(conn.execute(sql, tuple(params)).fetchall())


# ── the runners ──────────────────────────────────────────────────────────────

def new_totals() -> dict:
    return {"due": 0, "fetched": 0, "games_stored": 0, "player_rows": 0, "refused": 0,
            "left": 0, "fetch_errors": 0, "stopped": None, "reasons": {}, "failed": []}


def _run_games(conn, games, totals, *, get_json, sleep, budget_s, now,
               clock=time.monotonic, stop_after=STOP_AFTER_FAILURES) -> None:
    start, in_a_row = clock(), 0
    for i, game in enumerate(games):
        if budget_s is not None and clock() - start > budget_s:
            totals["left"] += len(games) - i
            return
        if i and sleep:
            time.sleep(sleep)
        try:
            js = box.fetch_summary(game["espn_event_id"], get_json)
        except Exception as exc:                          # noqa: BLE001
            code = box._status_code(exc)
            if code in (403, 429):
                totals["stopped"] = f"ESPN answered {code}"
                totals["failed"].append(f"espn-{code}")
                totals["left"] += len(games) - i
                logger.error(f"NCAAB player box: ESPN answered {code}; stopping the run")
                return
            if code is not None and 400 <= code < 500:
                record_miss(conn, game, f"ESPN answered {code}", now)
                conn.commit()
                totals["refused"] += 1
                continue
            totals["fetch_errors"] += 1
            in_a_row += 1
            logger.warning(f"NCAAB player box: event {game['espn_event_id']} fetch failed: {exc}")
            if in_a_row >= stop_after:
                totals["stopped"] = f"{in_a_row} fetch failures in a row"
                totals["failed"].append("espn-unreachable")
                totals["left"] += len(games) - i - 1
                return
            continue
        in_a_row = 0
        totals["fetched"] += 1
        try:
            n, reason = store_from_summary(conn, game, js, now)
            conn.commit()
        except ConnectionLost:
            raise
        except Exception as exc:                          # noqa: BLE001
            logger.warning(f"NCAAB player box: {game['game_id']} write failed: {exc}")
            try:
                conn.rollback()
            except Exception:                             # noqa: BLE001
                pass
            totals["failed"].append(game["game_id"])
            continue
        if reason is None:
            totals["games_stored"] += 1
            totals["player_rows"] += n
        else:
            totals["refused"] += 1
            key = reason.split(":")[0][:60]
            totals["reasons"][key] = totals["reasons"].get(key, 0) + 1


def _open(connect):
    return (connect or get_connection)(), connect is None


def run_recent(run_date: str | None = None, days: int = RECENT_DAYS, *,
               now: datetime | None = None, get_json=None, connect=None,
               sleep: float = REQUEST_SLEEP, max_games: int = MAX_GAMES_PER_PASS,
               budget_s: float | None = TIME_BUDGET_S, clock=time.monotonic) -> dict:
    """The refresh-pass catch-up: finals of the last `days` ET dates with no
    player rows. No ESPN call when nothing is due."""
    now = now or datetime.now(timezone.utc)
    today = run_date or box._today_et(now)
    first = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
    conn, own = _open(connect)
    totals = new_totals()
    try:
        ensure_tables(conn)
        games = due_games(conn, first=first, last=today, now=now, limit=max_games + 1)
        conn.rollback()
        if len(games) > max_games:
            totals["left"] += 1
            games = games[:max_games]
        totals["due"] = len(games)
        if games:
            _run_games(conn, games, totals, get_json=get_json, sleep=sleep,
                       budget_s=budget_s, now=now, clock=clock, stop_after=1)
    finally:
        if own:
            conn.close()
    if totals["due"]:
        logger.info(f"NCAAB player box (ESPN): {_summary(totals)}")
    return totals


def run_backfill(first_season: int, last_season: int, *, now: datetime | None = None,
                 get_json=None, connect=None, sleep: float = REQUEST_SLEEP,
                 echo: bool = False) -> dict:
    """Every final of the seasons with no player rows, one summary call each.
    A game refused before is tried once more. Re-running stores nothing twice."""
    now = now or datetime.now(timezone.utc)
    conn, own = _open(connect)
    totals = new_totals()
    try:
        ensure_tables(conn)
        games = due_games(conn, seasons=(first_season, last_season), now=now,
                          respect_misses=False)
        conn.rollback()
        totals["due"] = len(games)
        if echo:
            print(f"player box backfill {first_season}-{last_season}: {len(games)} game(s) due")
        _run_games(conn, games, totals, get_json=get_json, sleep=sleep, budget_s=None, now=now)
    finally:
        if own:
            conn.close()
    logger.info(f"NCAAB player box backfill {first_season}-{last_season}: {_summary(totals)}")
    return totals


def _summary(t: dict) -> dict:
    return {k: (len(v) if isinstance(v, list) else v) for k, v in t.items()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--recent", action="store_true")
    g.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"))
    ap.add_argument("--date")
    ap.add_argument("--days", type=int, default=RECENT_DAYS)
    a = ap.parse_args(argv)
    if a.recent:
        t = run_recent(a.date, a.days)
    else:
        t = run_backfill(a.seasons[0], a.seasons[1], echo=True)
    print(_summary(t))
    return 1 if t["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
