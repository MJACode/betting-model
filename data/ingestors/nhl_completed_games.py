"""Played NHL games from nhl_team_game_log, one row per league game id.

The same filter the shot ingestor uses: regular season and playoffs, and a
game whose two log rows are one home team and one away team. A game that
does not match is listed, not fetched.
"""
from __future__ import annotations

from data.season_labels import nhl_season_label

# 2023-24 is ending-year 2024. History before that is not part of this pull.
BACKFILL_FROM_SEASON = 2024


def season_span(run_date: str, backfill: bool) -> tuple[int, int]:
    """Ending-year labels. Daily is the current season only."""
    end = nhl_season_label(run_date)
    if backfill:
        return BACKFILL_FROM_SEASON, end
    return end, end


def completed_games(conn, first: int, last: int) -> tuple[list[dict], list[int]]:
    """(games, odd ids). Each game is one dict the writers share."""
    rows = conn.execute(
        "SELECT nhl_game_id, min(game_id), max(game_id), min(season), min(game_type), "
        "       min(game_date), max(CASE WHEN is_home = 1 THEN team END), "
        "       max(CASE WHEN is_home = 0 THEN team END), count(*), sum(is_home) "
        "FROM nhl_team_game_log WHERE season BETWEEN ? AND ? AND game_type IN (2, 3) "
        "GROUP BY nhl_game_id ORDER BY nhl_game_id",
        (first, last),
    ).fetchall()
    conn.commit()
    games, odd = [], []
    for gid, gmin, gmax, season, gtype, gdate, home, away, n, n_home in rows:
        if n != 2 or n_home != 1 or gmin != gmax or not home or not away:
            odd.append(int(gid))
            continue
        games.append({
            "nhl_game_id": int(gid),
            "our_game_id": gmin,
            "season_end": int(season),
            "game_type": int(gtype),
            "game_date": gdate,
            "home_abbr": home,
            "away_abbr": away,
        })
    return games, odd


def stored_ids(conn, table: str) -> set[int]:
    ids = {int(r[0]) for r in conn.execute(
        f"SELECT DISTINCT nhl_game_id FROM {table}").fetchall()}
    conn.commit()
    return ids
