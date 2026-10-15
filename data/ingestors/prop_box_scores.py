"""Box scores for prop bets whose games are already final.

`settle_picks` runs on the evening, hourly, and overnight refresh, and it
already grades props. It can only grade a prop once the player log exists.
NHL skater and goalie logs were written by the morning stats step, which
runs after settle, so a shots-on-goal bet whose game ended at 10pm graded
on the 7:17am pass. NBA, evening WNBA, and NFL have the same gap: the log
is not on the pass that already has the final.

This runs inside `settle_picks`, on its own connection, after the closing
line is committed and before any grade write. It asks which finals still
have an unsettled prop and no log, and fetches only those. A game that
already has a log is not fetched. The grade that follows is unchanged.

WNBA, NBA, and NFL fetches are heavier, so an attempt is written to
`pipeline_log` before the request and not repeated for 50 minutes. NHL and
MLB are one call per missing game and run every pass. A statement timeout
rolls back to a savepoint and the next sport still runs.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from loguru import logger

from data.db import (ConnectionLost, call_in_savepoint, get_connection,
                     statement_timeout)

WINDOW_DAYS = 14
MAX_DATES = 20
COOL_MINUTES = 50

_COOL_STEP = {
    "WNBA": "prop_box_wnba",
    "NBA": "prop_box_nba",
    "NFL": "prop_box_nfl",
}


def _sport_kind(model_id: str) -> tuple[str, str] | None:
    mid = str(model_id or "")
    if mid.startswith("mlb_prop_"):
        return "MLB", "player"
    if mid.startswith("wnba_prop_"):
        return "WNBA", "player"
    if mid.startswith("nba_prop_"):
        return "NBA", "player"
    if mid.startswith("nfl_prop_") or mid == "nfl_live_prop":
        return "NFL", "player"
    if mid == "nhl_prop_saves":
        return "NHL", "goalie"
    if mid.startswith("nhl_prop_"):
        return "NHL", "skater"
    return None


def _window_lo(through: str) -> str:
    end = datetime.strptime(str(through)[:10], "%Y-%m-%d").date()
    return (end - timedelta(days=WINDOW_DAYS - 1)).isoformat()


def _day(value) -> str:
    return str(value)[:10]


def _probe(conn, through: str) -> dict:
    lo = _window_lo(through)
    hi = str(through)[:10]
    rows = conn.execute(
        """
        SELECT p.model_id, p.game_id, p.game_date, p.player_id
          FROM picks p
          JOIN games g ON g.game_id = p.game_id
         WHERE p.signal_type = 'BET'
           AND p.result IS NULL
           AND p.game_date >= %s
           AND p.game_date <= %s
           AND g.home_score IS NOT NULL
           AND (p.model_id LIKE 'mlb_prop_%%'
             OR p.model_id LIKE 'wnba_prop_%%'
             OR p.model_id LIKE 'nba_prop_%%'
             OR p.model_id LIKE 'nfl_prop_%%'
             OR p.model_id LIKE 'nhl_prop_%%'
             OR p.model_id = 'nfl_live_prop')
        """,
        (lo, hi),
    ).fetchall()

    pending: dict = {}
    for model_id, game_id, game_date, player_id in rows:
        kind = _sport_kind(model_id)
        if kind is None or not game_id or game_date is None:
            continue
        sport, log_kind = kind
        day = _day(game_date)
        games = pending.setdefault(sport, {}).setdefault(day, {})
        info = games.setdefault(game_id, {"kinds": set(), "players": set()})
        info["kinds"].add(log_kind)
        if player_id is not None and str(player_id) != "":
            info["players"].add(str(player_id))

    _drop_logged(conn, pending)
    for sport, by_date in list(pending.items()):
        kept = sorted(by_date, reverse=True)[:MAX_DATES]
        pending[sport] = {d: by_date[d] for d in kept}
        if not pending[sport]:
            del pending[sport]
    return pending


def _drop_logged(conn, pending: dict) -> None:
    queries = {
        ("MLB", "player"):
            "SELECT DISTINCT game_id FROM player_game_log WHERE game_id = ANY(%s)",
        ("WNBA", "player"):
            "SELECT DISTINCT game_id FROM wnba_player_game_log WHERE game_id = ANY(%s)",
        ("NBA", "player"):
            "SELECT DISTINCT game_id FROM nba_player_game_log WHERE game_id = ANY(%s)",
        ("NFL", "player"):
            "SELECT DISTINCT game_id FROM nfl_player_game_log WHERE game_id = ANY(%s)",
        ("NHL", "skater"):
            """
            SELECT DISTINCT t.game_id
              FROM nhl_skater_game_log s
              JOIN nhl_team_game_log t
                ON t.nhl_game_id = s.nhl_game_id AND t.team = s.team
             WHERE t.game_id = ANY(%s)
            """,
        ("NHL", "goalie"):
            "SELECT DISTINCT game_id FROM nhl_goalie_game_log WHERE game_id = ANY(%s)",
    }
    for sport, by_date in pending.items():
        ids_by_kind: dict[str, set] = {}
        for games in by_date.values():
            for info in games.values():
                for kind in info["kinds"]:
                    ids_by_kind.setdefault(kind, set())
        for games in by_date.values():
            for gid, info in games.items():
                for kind in info["kinds"]:
                    ids_by_kind[kind].add(gid)
        logged: dict[str, set] = {}
        for kind, ids in ids_by_kind.items():
            sql = queries.get((sport, kind))
            if not sql or not ids:
                logged[kind] = set()
                continue
            found = conn.execute(sql, (list(ids),)).fetchall()
            logged[kind] = {row[0] for row in found}
        for day, games in list(by_date.items()):
            for gid, info in list(games.items()):
                info["kinds"] -= {k for k in info["kinds"] if gid in logged.get(k, set())}
                if not info["kinds"]:
                    del games[gid]
            if not games:
                del by_date[day]


def missing_prop_games(conn, through: str) -> dict:
    """Finals in the prop window that still have an unsettled prop and no log.

    `{sport: {date: {game_id: {"kinds": set, "players": set}}}}`. A statement
    timeout returns an empty dict and leaves the connection usable. Any other
    error is re-raised after the savepoint rolls back.
    """
    try:
        return call_in_savepoint(conn, "prop_box_probe", lambda: _probe(conn, through))
    except Exception as exc:
        if statement_timeout(exc):
            logger.warning("Prop box probe timed out — grading whatever is stored")
            return {}
        raise


def _parse_ts(text) -> datetime | None:
    s = str(text or "").strip()
    if not s:
        return None
    if " " in s and "T" not in s:
        s = s.replace(" ", "T", 1)
    if s.endswith("+00"):
        s = s + ":00"
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _since(through: str) -> str:
    end = datetime.strptime(str(through)[:10], "%Y-%m-%d").date()
    return (end - timedelta(days=1)).isoformat()


def _last_attempt(conn, step: str, since: str):
    def _read():
        row = conn.execute(
            """
            SELECT created_at FROM pipeline_log
             WHERE step = %s AND run_date >= %s
             ORDER BY log_id DESC
             LIMIT 1
            """,
            (step, since),
        ).fetchone()
        return None if row is None else row[0]
    return call_in_savepoint(conn, "prop_box_cool", _read)


def _cooled(conn, step: str, through: str, now: datetime) -> bool:
    ts = _last_attempt(conn, step, _since(through))
    parsed = _parse_ts(ts)
    if parsed is None:
        return False
    return now - parsed.astimezone(timezone.utc) < timedelta(minutes=COOL_MINUTES)


def _mark(conn, step: str, through: str) -> None:
    def _ins():
        conn.execute(
            """
            INSERT INTO pipeline_log
                (run_date, step, status, records_in, records_out, duration_s)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (str(through)[:10], step, "ok", 0, 0, 0),
        )
    call_in_savepoint(conn, "prop_box_mark", _ins)
    conn.commit()


def _default_nhl(dates):
    from data.ingestors.nhl_boxscore import fill_missing
    return fill_missing(dates)


def _default_mlb(game_date):
    from data.ingestors.mlb_stats_ingestor import ingest_game_log_for_date
    return ingest_game_log_for_date(game_date)


def _default_wnba(game_date):
    from data.ingestors.wnba_results_ingestor import ingest_wnba_results
    return ingest_wnba_results(run_date=game_date, only_date=game_date)


def _default_nba(dates):
    from data.ingestors.nba_espn_box import fill_missing
    return fill_missing(dates)


def _default_nfl():
    from data.ingestors.nfl_props_data_ingestor import run_nfl_props_data_ingestor
    return run_nfl_props_data_ingestor()


def _nhl_dates(by_date: dict) -> dict[str, set]:
    return {day: set(games) for day, games in by_date.items()}


def _nba_dates(by_date: dict) -> dict:
    return {
        day: {gid: set(info["players"]) for gid, info in games.items()}
        for day, games in by_date.items()
    }


def ensure_prop_box_scores(through: str, *, connect=None, now=None,
                           nhl_fill=None, mlb_fill=None, wnba_fill=None,
                           nba_fill=None, nfl_fill=None) -> dict:
    """Fetch the logs `through`'s unsettled props are waiting on.

    `connect` is a zero-arg callable. When it is omitted, this opens its own
    connection and closes it. The HTTP work uses the fill function's own
    connection, so a timeout there does not abort the grade transaction.
    """
    factory = connect or get_connection
    conn = factory()
    own = connect is None
    clock = now or (lambda: datetime.now(timezone.utc))
    fills = {
        "NHL": nhl_fill or _default_nhl,
        "MLB": mlb_fill or _default_mlb,
        "WNBA": wnba_fill or _default_wnba,
        "NBA": nba_fill or _default_nba,
        "NFL": nfl_fill or _default_nfl,
    }
    out = {"games": {}, "filled": {}, "cooled": [], "errors": []}
    try:
        missing = missing_prop_games(conn, through)
        # The probe is a read. End it before any download so this connection
        # is not holding a snapshot while a box is fetched.
        try:
            conn.rollback()
        except Exception as exc:
            logger.warning(f"Prop box probe rollback failed ({exc})")
        out["games"] = {sport: sum(len(g) for g in dates.values())
                        for sport, dates in missing.items()}
        _fill_open(missing, fills, out)
        _fill_cooled(conn, through, clock(), missing, fills, out)
    finally:
        if own:
            conn.close()
    return out


def _fill_open(missing: dict, fills: dict, out: dict) -> None:
    nhl = missing.get("NHL") or {}
    if nhl:
        _call_fill("NHL", out, lambda: fills["NHL"](_nhl_dates(nhl)))
    for sport in ("MLB",):
        by_date = missing.get(sport) or {}
        if not by_date:
            continue
        dates = sorted(by_date)

        def _run(dates=dates, sport=sport):
            got = []
            for day in dates:
                got.append(fills[sport](day))
            return got

        _call_fill(sport, out, _run)


def _fill_cooled(conn, through, now, missing, fills, out) -> None:
    for sport, step in _COOL_STEP.items():
        by_date = missing.get(sport) or {}
        if not by_date:
            continue
        try:
            if _cooled(conn, step, through, now):
                out["cooled"].append(sport)
                logger.info(f"Prop box {sport}: last attempt was under "
                            f"{COOL_MINUTES} min ago")
                continue
            _mark(conn, step, through)
        except ConnectionLost:
            raise
        except Exception as exc:
            if statement_timeout(exc):
                logger.warning(f"Prop box {sport}: cooldown check timed out — skipping")
            else:
                logger.warning(f"Prop box {sport}: cooldown check failed ({exc})")
            out["errors"].append(sport)
            continue
        if sport == "NFL":
            _call_fill(sport, out, fills["NFL"])
        elif sport == "NBA":
            payload = _nba_dates(by_date)
            _call_fill(sport, out, lambda payload=payload: fills["NBA"](payload))
        else:
            dates = sorted(by_date)

            def _run(dates=dates, sport=sport):
                return [fills[sport](day) for day in dates]

            _call_fill(sport, out, _run)


def _call_fill(sport: str, out: dict, fn) -> None:
    try:
        out["filled"][sport] = fn()
    except Exception as exc:
        logger.warning(f"Prop box {sport} fetch failed ({exc})")
        out["errors"].append(sport)
