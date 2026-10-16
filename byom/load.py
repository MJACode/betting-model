"""Read NFL lines and write byom_game_facts.

Reads games, nfl_odds_history and odds. Writes only byom_game_facts.
Does not touch picks. `apply=False` is the default: count the rows and
write nothing.
"""
from __future__ import annotations

from byom.constants import DK_HISTORY_START_SEASON, LOCK_WINDOW_HOURS, SPORT
from byom.game_facts import assemble_game, parse_date, parse_game_id

_QUOTE_FROM_HISTORY = """
SELECT game_id, bookmaker, market, snapshot_at, commence_time,
       point, price_home, price_away
  FROM nfl_odds_history
 WHERE season = %s
   AND market IN ('spreads', 'totals', 'h2h')
   AND commence_time IS NOT NULL
   AND snapshot_at <= commence_time
   AND snapshot_at >= commence_time - make_interval(hours => %s)
"""

_QUOTE_FROM_ODDS = """
SELECT o.game_id, o.bookmaker, o.market,
       o.snapshot_at::timestamptz AS snapshot_at,
       g.commence_time::timestamptz AS commence_time,
       CASE o.market
         WHEN 'spreads' THEN o.spread_home
         WHEN 'totals' THEN o.total_line
         ELSE NULL
       END AS point,
       CASE WHEN o.market = 'totals' THEN o.over_price ELSE o.home_price END
         AS price_home,
       CASE WHEN o.market = 'totals' THEN o.under_price ELSE o.away_price END
         AS price_away
  FROM odds o
  JOIN games g ON g.game_id = o.game_id
 WHERE g.sport = 'NFL'
   AND g.season = %s
   AND o.market IN ('spreads', 'totals', 'h2h')
   AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
   AND g.commence_time IS NOT NULL
   AND o.snapshot_at ~ '^[0-9]{4}-'
   AND o.snapshot_at::timestamptz <= g.commence_time::timestamptz
   AND o.snapshot_at::timestamptz
         >= g.commence_time::timestamptz - make_interval(hours => %s)
"""

# Column order is the INSERT. built_at is the table default.
FACT_COLUMNS = (
    "canonical_key", "sport", "season", "week", "away_team", "home_team",
    "game_date", "commence_time", "home_score", "away_score",
    "lock_window_hours", "near_window_hours",
    "lock_spread_at", "lock_spread_lead_hours", "dk_spread_home",
    "dk_spread_home_price", "dk_spread_away_price",
    "lock_total_at", "lock_total_lead_hours", "dk_total",
    "dk_over_price", "dk_under_price",
    "lock_ml_at", "lock_ml_lead_hours", "dk_ml_home_price", "dk_ml_away_price",
    "near_spread_at", "near_spread_home", "near_spread_home_price",
    "near_spread_away_price",
    "near_total_at", "near_total", "near_over_price", "near_under_price",
    "near_ml_at", "near_ml_home_price", "near_ml_away_price",
    "close_spread_at", "close_spread_home", "close_spread_home_price",
    "close_spread_away_price",
    "close_total_at", "close_total", "close_over_price", "close_under_price",
    "close_ml_at", "close_ml_home_price", "close_ml_away_price",
    "grade_spread_home_price", "grade_spread_home_book",
    "grade_spread_away_price", "grade_spread_away_book",
    "grade_over_price", "grade_over_book",
    "grade_under_price", "grade_under_book",
    "grade_ml_home_price", "grade_ml_home_book",
    "grade_ml_away_price", "grade_ml_away_book",
    "ats_home_result", "ats_home_units", "ats_away_result", "ats_away_units",
    "ml_home_result", "ml_home_units", "ml_away_result", "ml_away_units",
    "ou_over_result", "ou_over_units", "ou_under_result", "ou_under_units",
    "home_rest_days", "away_rest_days", "is_primetime", "home_role", "away_role",
    "line_source",
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


def _quotes(conn, season: int, source: str, sql: str) -> list[dict]:
    rows = _fetch(conn, sql, (season, LOCK_WINDOW_HOURS))
    out = []
    for row in rows:
        out.append({
            "game_id": row[0], "bookmaker": row[1], "market": row[2],
            "snapshot_at": row[3], "commence_time": row[4],
            "point": row[5], "price_home": row[6], "price_away": row[7],
            "line_source": source,
        })
    return out


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


def facts_for_season(conn, season: int, books: list[str]) -> list[dict]:
    """The facts this season would write. No INSERT."""
    if season < DK_HISTORY_START_SEASON:
        return []
    games = _games(conn, season)
    quotes = _quotes(conn, season, "nfl_odds_history", _QUOTE_FROM_HISTORY)
    quotes += _quotes(conn, season, "odds", _QUOTE_FROM_ODDS)
    by_key: dict[str, list] = {}
    for quote in quotes:
        parsed = parse_game_id(quote["game_id"])
        if parsed is None:
            continue
        by_key.setdefault(parsed[0], []).append(quote)
    played = _played(games)
    facts = []
    for game in games:
        parsed = parse_game_id(game["game_id"])
        if parsed is None:
            continue
        fact = assemble_game(game, by_key.get(parsed[0], []), played, books)
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


def build_season(conn, season: int, apply: bool = False,
                 books: list[str] | None = None) -> dict:
    """One season. apply=False writes nothing."""
    if books is None:
        from config import BEST_LINE_BOOKMAKERS
        books = list(BEST_LINE_BOOKMAKERS)
    if season < DK_HISTORY_START_SEASON:
        return {
            "season": season, "facts": 0, "written": 0,
            "skipped": "before DraftKings history",
        }
    facts = facts_for_season(conn, season, books)
    written = _upsert(conn, facts) if apply else 0
    return {"season": season, "facts": len(facts), "written": written}


def seasons_in_games(conn) -> list[int]:
    rows = _fetch(conn, """
        SELECT DISTINCT season FROM games
         WHERE sport = %s AND season >= %s
         ORDER BY season
    """, (SPORT, DK_HISTORY_START_SEASON))
    return [int(row[0]) for row in rows]


def build_seasons(conn, seasons, apply: bool = False,
                  books: list[str] | None = None) -> dict:
    if seasons is None:
        seasons = seasons_in_games(conn)
    elif isinstance(seasons, int):
        seasons = [seasons]
    built = [build_season(conn, int(s), apply=apply, books=books) for s in seasons]
    if apply:
        conn.commit()
    return {"apply": apply, "seasons": built}
