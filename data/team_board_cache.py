"""
Refresh the Teams-board cache — `team_stats_board_cache`, one row per
(sport, season, team).

Why a cache exists (2026-09-04): `team_stats_board('MLB', 2026)` measured at
31.7 s against an 8 s statement timeout, because it recomputed the pre-game
closing line for every finished game of the season on every call — 88,040
odds rows sorted to disk to keep 3,766. A finished game's closing line never
changes and a season aggregate moves once a day, so the board is computed once
here and read many times by the app. `data/migrations/cache_team_stats_board.sql`
has the measurements and the schema.

Per (sport, season) pair, deliberately: each refresh is one transaction that
swaps that pair's rows, so the app never reads a half-built board, and each
pair fits inside any statement window on its own. The whole set is a few
minutes on the worker, which has no timeout.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

from loguru import logger

# Every sport with a Teams board. Mirrors `supportsTeamBoard` in the app's
# teamStatCatalog (BALL = MLB, NBA, WNBA, NHL, NFL, NCAAF); UFC and golf have
# no teams.
TEAM_BOARD_SPORTS: tuple[str, ...] = ("MLB", "WNBA", "NBA", "NHL", "NFL", "NCAAF")


def team_board_seasons(today: date | None = None) -> tuple[int, ...]:
    """The seasons the app can ask for, and one more.

    The app tries the current calendar year then the previous one
    (`seasonCandidates`). NHL, NBA and NCAAF label a season by its ENDING year
    (CLAUDE.md §4), so a season in progress each autumn carries NEXT year's
    label — refreshing year+1 too means the board is never empty for those
    sports the week a season opens. A pair with no finished games writes zero
    rows, which costs nothing.
    """
    y = (today or date.today()).year
    return (y - 1, y, y + 1)


def team_board_pairs(today: date | None = None) -> list[tuple[str, int]]:
    """Every (sport, season) the daily refresh walks."""
    return [(s, yr) for s in TEAM_BOARD_SPORTS for yr in team_board_seasons(today)]


def refresh_team_board_cache(
    pairs: Iterable[tuple[str, int]] | None = None,
) -> dict[tuple[str, int], int]:
    """Refresh each (sport, season); return rows written per pair.

    One pair failing does not stop the rest — a bad NCAAF season must not cost
    MLB its board — but every failure is logged and the pair is reported with
    -1 so the caller can see it rather than assume it was empty.
    """
    from data.db import get_connection

    out: dict[tuple[str, int], int] = {}
    conn = get_connection()
    try:
        # One statement per pair, each its own transaction (the function body
        # is the delete+insert), so a failure rolls back only that pair.
        conn._conn.autocommit = True
        for sport, season in pairs if pairs is not None else team_board_pairs():
            try:
                row = conn.execute(
                    "SELECT public.refresh_team_stats_board(%s, %s)", (sport, season)
                ).fetchone()
                n = int(row[0]) if row else 0
                out[(sport, season)] = n
                logger.info(f"  team board {sport} {season}: {n} rows")
            except Exception as exc:  # noqa: BLE001 — per-pair isolation is the point
                out[(sport, season)] = -1
                logger.error(f"  team board {sport} {season} failed: {exc}")
    finally:
        conn.close()
    return out
