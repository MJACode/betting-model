"""NBA player box scores from ESPN, for the worker.

`nba_api` reads stats.nba.com, which blocks this worker, so the morning
`nba-game-log` step does not run here. ESPN's basketball summary is the same
shape the WNBA results step already parses, and it is reachable from the
worker. Rows are written only when every unsettled prop's player_id on that
game resolved to a name already in `nba_player_game_log`. A name that did
not resolve leaves the game unlogged, so the settler does not void the bet
as a DNP.
"""
from __future__ import annotations

from loguru import logger

from data.db import call_in_savepoint, get_connection, statement_timeout
from data.ingestors.injury_ingestor import ESPN_HEADERS
from data.ingestors.nba_stats_ingestor import (
    _build_game_id, _nba_season_for_date, _norm_nba, _upsert_player_log,
)
from data.ingestors.wnba_results_ingestor import (
    _min_to_float, _split_made_att, _to_int, norm_player_name,
)

ESPN_NBA_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
)
ESPN_NBA_SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
)

_LABELS_NEEDED = ("MIN", "PTS", "REB", "OREB", "DREB", "AST", "STL", "BLK", "TO",
                  "FG", "3PT", "FT")


def parse_nba_scoreboard(data: dict, game_date: str) -> list[dict]:
    """Completed games only. game_id is NBA_{date}_{away}_{home}."""
    out = []
    for ev in (data or {}).get("events") or []:
        comps = ev.get("competitions") or []
        if not comps:
            continue
        comp = comps[0]
        completed = bool(((ev.get("status") or {}).get("type") or {}).get("completed"))
        if not completed:
            continue
        home = away = None
        for c in comp.get("competitors") or []:
            team = c.get("team") or {}
            abbrev = _norm_nba(team.get("abbreviation") or "", team.get("displayName") or "")
            if c.get("homeAway") == "home":
                home = abbrev
            elif c.get("homeAway") == "away":
                away = abbrev
        if not home or not away:
            continue
        out.append({
            "event_id": str(ev.get("id") or ""),
            "game_id": _build_game_id(game_date, away, home),
            "game_date": game_date,
            "home": home,
            "away": away,
        })
    return out


def parse_nba_box(data: dict) -> list[dict]:
    """Per-player stats by label. DNP and empty rows are omitted. `starter`
    stays a bool here; the row written to Postgres uses 0/1."""
    out = []
    for team_block in ((data or {}).get("boxscore") or {}).get("players") or []:
        team_info = team_block.get("team") or {}
        team = _norm_nba(team_info.get("abbreviation") or "",
                         team_info.get("displayName") or "")
        if not team:
            continue
        blocks = team_block.get("statistics") or []
        if not blocks:
            continue
        block = blocks[0]
        labels = [str(x).upper() for x in (block.get("labels") or block.get("names") or [])]
        idx = {lab: i for i, lab in enumerate(labels)}

        def stat(row, label, idx=idx):
            i = idx.get(label)
            return row[i] if i is not None and i < len(row) else None

        for ath in block.get("athletes") or []:
            if ath.get("didNotPlay"):
                continue
            row = ath.get("stats") or []
            if not row:
                continue
            a = ath.get("athlete") or {}
            name = a.get("displayName") or ""
            if not name:
                continue
            fg_m, fg_a = _split_made_att(stat(row, "FG"))
            fg3_m, fg3_a = _split_made_att(stat(row, "3PT"))
            ft_m, ft_a = _split_made_att(stat(row, "FT"))
            out.append({
                "name": name,
                "team": team,
                "starter": bool(ath.get("starter")),
                "minutes": _min_to_float(stat(row, "MIN")),
                "points": _to_int(stat(row, "PTS")),
                "rebounds": _to_int(stat(row, "REB")),
                "offensive_reb": _to_int(stat(row, "OREB")),
                "defensive_reb": _to_int(stat(row, "DREB")),
                "assists": _to_int(stat(row, "AST")),
                "steals": _to_int(stat(row, "STL")),
                "blocks": _to_int(stat(row, "BLK")),
                "turnovers": _to_int(stat(row, "TO")),
                "fg_made": fg_m, "fg_att": fg_a,
                "fg3_made": fg3_m, "fg3_att": fg3_a,
                "ft_made": ft_m, "ft_att": ft_a,
            })
    return out


def rows_for_game(players: list[dict], name_to_id: dict[str, str],
                  needed_ids: set[str], game: dict) -> tuple[list[dict], list[str]]:
    """Matched log rows, and the box names that did not resolve.

    When a needed player_id is missing and some box name did not resolve,
    return no rows. Writing the others would make the settler treat the
    unmatched bet as a DNP.
    """
    season = _nba_season_for_date(game["game_date"])
    matched = []
    unmatched = []
    for p in players:
        key = norm_player_name(p["name"])
        pid = name_to_id.get(key)
        if not pid:
            unmatched.append(p["name"])
            continue
        matched.append({
            "player_id": pid,
            "player_name": p["name"],
            "team": p["team"],
            "game_id": game["game_id"],
            "game_date": game["game_date"],
            "season": season,
            "minutes": p["minutes"],
            "is_starter": int(p["starter"]),
            "points": p["points"],
            "rebounds": p["rebounds"],
            "offensive_reb": p["offensive_reb"],
            "defensive_reb": p["defensive_reb"],
            "assists": p["assists"],
            "steals": p["steals"],
            "blocks": p["blocks"],
            "turnovers": p["turnovers"],
            "fg_made": p["fg_made"], "fg_att": p["fg_att"],
            "fg3_made": p["fg3_made"], "fg3_att": p["fg3_att"],
            "ft_made": p["ft_made"], "ft_att": p["ft_att"],
        })
    have = {r["player_id"] for r in matched}
    if (set(needed_ids) - have) and unmatched:
        return [], unmatched
    return matched, unmatched


def _name_map(conn, since: str) -> dict[str, str]:
    """Normalized name -> player_id. A name worn by two ids is dropped."""
    def _read():
        return conn.execute(
            "SELECT player_id, player_name FROM nba_player_game_log "
            "WHERE game_date >= %s",
            (since,),
        ).fetchall()

    rows = call_in_savepoint(conn, "nba_box_names", _read)
    by_name: dict[str, str] = {}
    ambiguous: set[str] = set()
    for pid, name in rows:
        key = norm_player_name(name)
        if not key or key in ambiguous:
            continue
        sid = str(pid)
        if key in by_name and by_name[key] != sid:
            ambiguous.add(key)
            del by_name[key]
        else:
            by_name[key] = sid
    return by_name


def fill_missing(dates_to_games: dict[str, dict[str, set[str]]], *, get_json=None,
                 connect=None) -> dict:
    """`dates_to_games` is `{date: {game_id: {player_id, ...}}}`.

    Only those games are fetched. A game that does not resolve every needed
    player is left unlogged.
    """
    import requests
    from datetime import timedelta
    from datetime import date as date_cls

    if not dates_to_games:
        return {"games": 0, "skipped": 0, "errors": 0}

    def _default_get(url, params):
        resp = requests.get(url, params=params, headers=ESPN_HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.json()

    get_json = get_json or _default_get
    own = connect is None
    conn = (connect or get_connection)()
    games = skipped = errors = 0
    try:
        dates = sorted(dates_to_games)
        since = (date_cls.fromisoformat(dates[0]) - timedelta(days=400)).isoformat()
        try:
            names = _name_map(conn, since)
        except Exception as exc:                              # noqa: BLE001
            if statement_timeout(exc):
                logger.warning("NBA box score: name map timed out — next pass")
            else:
                logger.warning(f"NBA box score: name map failed: {exc}")
            return {"games": 0, "skipped": 0, "errors": 1}
        for game_date, wanted in dates_to_games.items():
            try:
                board = get_json(ESPN_NBA_SCOREBOARD_URL,
                                 {"dates": game_date.replace("-", "")})
            except Exception as exc:                          # noqa: BLE001
                logger.warning(f"NBA box score: scoreboard {game_date} failed: {exc}")
                errors += 1
                continue
            by_id = {g["game_id"]: g for g in parse_nba_scoreboard(board, game_date)}
            for game_id, needed in wanted.items():
                game = by_id.get(game_id)
                if not game or not game.get("event_id"):
                    skipped += 1
                    continue
                try:
                    summary = get_json(ESPN_NBA_SUMMARY_URL, {"event": game["event_id"]})
                    players = parse_nba_box(summary)
                    rows, unmatched = rows_for_game(players, names, set(needed), game)
                    if not rows:
                        logger.info(f"NBA box score: {game_id} left unlogged "
                                    f"({len(unmatched)} name(s) unresolved)")
                        skipped += 1
                        continue
                    def _write(rows=rows):
                        return _upsert_player_log(conn, rows)
                    call_in_savepoint(conn, "nba_box_game", _write)
                    conn.commit()
                    games += 1
                except Exception as exc:                      # noqa: BLE001
                    if statement_timeout(exc):
                        logger.warning(f"NBA box score: {game_id} timed out — next pass")
                    else:
                        logger.warning(f"NBA box score: {game_id} failed: {exc}")
                    errors += 1
                    try:
                        conn.rollback()
                    except Exception:                          # noqa: BLE001
                        pass
    finally:
        if own:
            conn.close()
    logger.info(f"NBA box scores: {games} game(s) stored, {skipped} skipped, "
                f"{errors} error(s)")
    return {"games": games, "skipped": skipped, "errors": errors}
