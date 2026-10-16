"""Read NFL prop lines and write byom_prop_facts.

One game at a time. player_prop_odds is large; a season is not one
fetch. apply=False counts and writes nothing.

The prop lock is PROP_LOCK_WINDOW_HOURS (24, UNCONFIRMED). Rows before
PROP_HISTORY_START_DATE are not built. Alt-ladder market keys are not
read. Does not touch picks.
"""
from __future__ import annotations

from byom.constants import (
    PROP_HISTORY_START_DATE,
    PROP_HISTORY_START_SEASON,
    PROP_LOCK_WINDOW_HOURS,
    SPORT,
)
from byom.game_facts import parse_date, parse_game_id
from byom.prop_facts import MARKET_COLUMNS, SOURCE_PROPS, facts_for_game

# Month 01-12 and day 01-31. '2024-13-45' matches a leading-year check
# and the cast then aborts the game. A value that fails this pattern is
# NULL instead of a cast.
_TS_OK = (
    "^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
)


def _ts_case(expr: str) -> str:
    return (
        f"CASE WHEN {expr}::text ~ '{_TS_OK}' "
        f"THEN {expr}::timestamptz ELSE NULL END"
    )


_SNAP = _ts_case("p.snapshot_at")
_KICK = _ts_case("g.commence_time")

_MARKETS = tuple(MARKET_COLUMNS)

FACT_COLUMNS = (
    "prop_key", "canonical_key", "sport", "season", "week",
    "player_name", "player_key", "team", "market", "line",
    "lock_window_hours", "lock_snapshot_at",
    "dk_over_price", "dk_under_price",
    "grade_over_price", "grade_over_book",
    "grade_under_price", "grade_under_book",
    "close_snapshot_at", "close_over_price", "close_under_price",
    "actual", "over_result", "over_units_uncapped", "over_units_capped",
    "under_result", "under_units_uncapped", "under_units_capped",
    "log_status", "line_source",
)

_LOG_COLS = (
    "player_name", "team",
    "passing_yards", "attempts", "completions", "passing_tds",
    "rushing_yards", "carries", "rushing_tds",
    "receiving_yards", "receptions", "receiving_tds",
    "def_sacks", "def_tackles_solo", "def_tackle_assists",
)


def _fetch(conn, sql, params):
    cur = conn.execute(sql, params)
    return cur.fetchall()


def _games(conn, season: int) -> list[dict]:
    rows = _fetch(conn, """
        SELECT game_id, season, game_date, home_team, away_team,
               home_score, away_score, commence_time
          FROM games
         WHERE sport = %s AND season = %s
           AND game_date >= %s
    """, (SPORT, season, PROP_HISTORY_START_DATE))
    out = []
    for row in rows:
        out.append({
            "game_id": row[0], "season": row[1], "game_date": row[2],
            "home_team": row[3], "away_team": row[4],
            "home_score": row[5], "away_score": row[6],
            "commence_time": row[7],
        })
    return out


def _as_quotes(rows) -> list[dict]:
    out = []
    for row in rows:
        out.append({
            "player_name": row[0], "team": row[1], "market": row[2],
            "bookmaker": row[3], "snapshot_at": row[4],
            "commence_time": row[5], "point": row[6],
            "price_home": row[7], "price_away": row[8],
            "line_source": SOURCE_PROPS,
        })
    return out


def _quotes_for_game(conn, game_id: str) -> list[dict]:
    """DraftKings inside the prop window. One game. The cast sits in a CASE.

    The grade is DraftKings' own price. Other books are not read.
    """
    sql = f"""
        SELECT p.player_name, p.team, p.market, p.bookmaker,
               {_SNAP} AS snapshot_at,
               {_KICK} AS commence_time,
               p.line, p.over_price, p.under_price
          FROM player_prop_odds p
          JOIN games g ON g.game_id = p.game_id
         WHERE p.game_id = %s
           AND p.bookmaker = 'draftkings'
           AND p.market = ANY(%s)
           AND (p.snapshot_type IS NULL OR p.snapshot_type <> 'in_play')
           AND {_KICK} IS NOT NULL
           AND {_SNAP} IS NOT NULL
           AND {_SNAP} <= {_KICK}
           AND {_SNAP} >= {_KICK} - make_interval(hours => %s)
    """
    return _as_quotes(_fetch(
        conn, sql, (game_id, list(_MARKETS), PROP_LOCK_WINDOW_HOURS)))


def _log_for_game(conn, game_id: str) -> list[dict]:
    cols = ", ".join(_LOG_COLS)
    rows = _fetch(conn, f"""
        SELECT {cols}
          FROM nfl_player_game_log
         WHERE game_id = %s
    """, (game_id,))
    out = []
    for row in rows:
        out.append(dict(zip(_LOG_COLS, row)))
    return out


def facts_for_season(conn, season: int,
                     game_ids: list[str] | None = None) -> tuple[list[dict], list[str]]:
    """Facts, and the canonical keys of the games this read considered.

    `game_ids` None reads every game. A list reads only those games.
    A game with no lock is still in the key list so a rebuild can delete
    the rows the previous window wrote.
    """
    if season < PROP_HISTORY_START_SEASON:
        return [], []
    games = _games(conn, season)
    if game_ids is not None:
        wanted = set(game_ids)
        games = [game for game in games if game["game_id"] in wanted]
    facts = []
    keys = []
    for game in games:
        parsed = parse_game_id(game["game_id"])
        if parsed is None or parse_date(game.get("game_date")) is None:
            continue
        keys.append(parsed[0])
        quotes = _quotes_for_game(conn, game["game_id"])
        log_rows = _log_for_game(conn, game["game_id"])
        facts.extend(facts_for_game(game, quotes, log_rows))
    return facts, keys


def _upsert(conn, facts: list[dict], canonical_keys: list[str]) -> int:
    """Delete this build's games, then insert. Same transaction.

    A prop_key from an earlier window is not left behind. Games with no
    facts this pass are cleared too.
    """
    keys = list(dict.fromkeys(canonical_keys))
    if keys:
        conn.execute(
            "DELETE FROM byom_prop_facts WHERE canonical_key = ANY(%s)",
            (keys,))
    if not facts:
        return 0
    cols = ", ".join(FACT_COLUMNS)
    placeholders = ", ".join(["%s"] * len(FACT_COLUMNS))
    updates = ", ".join(
        f"{col} = EXCLUDED.{col}" for col in FACT_COLUMNS if col != "prop_key")
    sql = (
        f"INSERT INTO byom_prop_facts ({cols}, built_at) "
        f"VALUES ({placeholders}, now()) "
        f"ON CONFLICT (prop_key) DO UPDATE SET {updates}, built_at = now()"
    )
    values = [tuple(fact[col] for col in FACT_COLUMNS) for fact in facts]
    conn.executemany(sql, values)
    return len(values)


def build_season(conn, season: int, apply: bool = False,
                 game_ids: list[str] | None = None) -> dict:
    """One season. apply=False writes nothing. `game_ids` limits the read."""
    if season < PROP_HISTORY_START_SEASON:
        return {
            "season": season, "facts": 0, "written": 0,
            "skipped": "before player_prop_odds history",
        }
    facts, keys = facts_for_season(conn, season, game_ids=game_ids)
    written = _upsert(conn, facts, keys) if apply else 0
    return {"season": season, "facts": len(facts), "written": written}


def build_seasons(conn, seasons, apply: bool = False) -> dict:
    if seasons is None:
        rows = _fetch(conn, """
            SELECT DISTINCT season FROM games
             WHERE sport = %s AND season >= %s
             ORDER BY season
        """, (SPORT, PROP_HISTORY_START_SEASON))
        seasons = [int(row[0]) for row in rows]
    elif isinstance(seasons, int):
        seasons = [seasons]
    built = [build_season(conn, int(s), apply=apply) for s in seasons]
    if apply:
        conn.commit()
    return {"apply": apply, "seasons": built}
