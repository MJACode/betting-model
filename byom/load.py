"""Read NFL lines and write byom_game_facts.

Reads games, nfl_odds_history and odds. Writes only byom_game_facts.
Does not touch picks. `apply=False` is the default: count the rows and
write nothing.

The line is the last DraftKings snapshot at or before game start, from
either store. A missing line does not skip the game. Prices are not
read. Moneyline is the score only.
"""
from __future__ import annotations

from byom.constants import DK_HISTORY_START_SEASON, SPORT
from byom.game_facts import assemble_game, parse_date, parse_game_id

# One game at a time. A season of nfl_odds_history is millions of rows
# (one 2026 game, NFL_2026_05_BAL_ATL, is 12,991 DraftKings rows by itself,
# measured 2026-10-16). The index is (game_id, market). This builder reads
# DraftKings spreads and totals at or before kickoff. apply=false uses
# the same reads and writes nothing.
_ODDS_SNAPSHOT = """
CASE WHEN o.snapshot_at ~ '^[0-9]{4}-'
     THEN o.snapshot_at::timestamptz
     ELSE NULL END
"""

_QUOTE_FROM_HISTORY = """
SELECT game_id, bookmaker, market, snapshot_at, commence_time, point
  FROM nfl_odds_history
 WHERE game_id IN (%s, %s)
   AND bookmaker = 'draftkings'
   AND market IN ('spreads', 'totals')
   AND commence_time IS NOT NULL
   AND snapshot_at <= commence_time
"""

_QUOTE_FROM_ODDS = f"""
SELECT o.game_id, o.bookmaker, o.market,
       {_ODDS_SNAPSHOT} AS snapshot_at,
       g.commence_time::timestamptz AS commence_time,
       CASE o.market
         WHEN 'spreads' THEN o.spread_home
         WHEN 'totals' THEN o.total_line
         ELSE NULL
       END AS point
  FROM odds o
  JOIN games g ON g.game_id = o.game_id
 WHERE o.game_id IN (%s, %s)
   AND o.bookmaker = 'draftkings'
   AND o.market IN ('spreads', 'totals')
   AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
   AND g.commence_time IS NOT NULL
   AND {_ODDS_SNAPSHOT} IS NOT NULL
   AND {_ODDS_SNAPSHOT} <= g.commence_time::timestamptz
"""

# Column order is the INSERT. built_at is the table default.
FACT_COLUMNS = (
    "canonical_key", "sport", "season", "week", "away_team", "home_team",
    "game_date", "commence_time", "home_score", "away_score",
    "line_basis", "dk_spread_home", "dk_total",
    "ats_home_result", "ats_away_result",
    "ml_home_result", "ml_away_result",
    "ou_over_result", "ou_under_result",
    "home_rest_days", "away_rest_days", "is_primetime", "home_role", "away_role",
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
    """, (SPORT, season))
    out = []
    for row in rows:
        out.append({
            "game_id": row[0], "season": row[1], "game_date": row[2],
            "home_team": row[3], "away_team": row[4],
            "home_score": row[5], "away_score": row[6], "commence_time": row[7],
        })
    return out


def _as_quotes(rows) -> list[dict]:
    out = []
    for row in rows:
        out.append({
            "game_id": row[0], "bookmaker": row[1], "market": row[2],
            "snapshot_at": row[3], "commence_time": row[4],
            "point": row[5],
        })
    return out


def _ids_for(game_id: str) -> tuple[str, str] | None:
    parsed = parse_game_id(game_id)
    if parsed is None:
        return None
    return parsed[0], "NFL_" + parsed[0]


def _dk_quotes(conn, ids: tuple[str, str]) -> list[dict]:
    bare, prefixed = ids
    history = _as_quotes(_fetch(conn, _QUOTE_FROM_HISTORY, (bare, prefixed)))
    odds = _as_quotes(_fetch(conn, _QUOTE_FROM_ODDS, (bare, prefixed)))
    return history + odds


def _played(games: list[dict]) -> dict:
    played: dict[str, list] = {}
    for game in games:
        parsed = parse_game_id(game["game_id"])
        day = parse_date(game.get("game_date"))
        if parsed is None or day is None:
            continue
        _, _, _, away, home = parsed
        played.setdefault(away, []).append(day)
        played.setdefault(home, []).append(day)
    return played


def facts_for_season(conn, season: int) -> list[dict]:
    """The facts this season would write. No INSERT."""
    if season < DK_HISTORY_START_SEASON:
        return []
    games = _games(conn, season)
    played = _played(games)
    facts = []
    for game in games:
        ids = _ids_for(game["game_id"])
        if ids is None:
            continue
        quotes = _dk_quotes(conn, ids)
        fact = assemble_game(game, quotes, played)
        if fact is not None:
            facts.append(fact)
    return facts


def _upsert(conn, facts: list[dict]) -> int:
    if not facts:
        return 0
    cols = ", ".join(FACT_COLUMNS)
    placeholders = ", ".join(["%s"] * len(FACT_COLUMNS))
    updates = ", ".join(
        f"{col} = EXCLUDED.{col}" for col in FACT_COLUMNS if col != "canonical_key")
    sql = (
        f"INSERT INTO byom_game_facts ({cols}, built_at) "
        f"VALUES ({placeholders}, now()) "
        f"ON CONFLICT (canonical_key) DO UPDATE SET {updates}, built_at = now()"
    )
    values = [tuple(fact[col] for col in FACT_COLUMNS) for fact in facts]
    conn.executemany(sql, values)
    return len(values)


def build_season(conn, season: int, apply: bool = False) -> dict:
    """One season. apply=False writes nothing."""
    if season < DK_HISTORY_START_SEASON:
        return {
            "season": season, "facts": 0, "written": 0,
            "skipped": "before DraftKings history",
        }
    facts = facts_for_season(conn, season)
    written = _upsert(conn, facts) if apply else 0
    return {"season": season, "facts": len(facts), "written": written}


def seasons_in_games(conn) -> list[int]:
    rows = _fetch(conn, """
        SELECT DISTINCT season FROM games
         WHERE sport = %s AND season >= %s
         ORDER BY season
    """, (SPORT, DK_HISTORY_START_SEASON))
    return [int(row[0]) for row in rows]


def build_seasons(conn, seasons, apply: bool = False) -> dict:
    if seasons is None:
        seasons = seasons_in_games(conn)
    elif isinstance(seasons, int):
        seasons = [seasons]
    built = [build_season(conn, int(s), apply=apply) for s in seasons]
    if apply:
        conn.commit()
    return {"apply": apply, "seasons": built}
