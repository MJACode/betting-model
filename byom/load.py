"""Read NFL lines and write byom_game_facts.

Reads games, nfl_odds_history and odds. Writes only byom_game_facts.
Does not touch picks. `apply=False` is the default: count the rows and
write nothing.
"""
from __future__ import annotations

from byom.constants import DK_HISTORY_START_SEASON, LOCK_WINDOW_HOURS, SPORT
from byom.game_facts import (
    capture_game,
    parse_date,
    parse_game_id,
    regrade_from_shop,
    shop_markets_to_replace,
    shop_windows,
)

# One game at a time. A season of nfl_odds_history is millions of rows
# (one 2026 game, NFL_2026_05_BAL_ATL, is 12,991 DraftKings rows by itself,
# measured 2026-10-16). The index is (game_id, market). DraftKings inside
# the lock window comes first; other books are read only inside the shop
# slices shop_windows() names. apply=false uses the same reads and writes
# nothing.
_ODDS_SNAPSHOT = """
CASE WHEN o.snapshot_at ~ '^[0-9]{4}-'
     THEN o.snapshot_at::timestamptz
     ELSE NULL END
"""

_QUOTE_FROM_HISTORY = """
SELECT game_id, bookmaker, market, snapshot_at, commence_time,
       point, price_home, price_away
  FROM nfl_odds_history
 WHERE game_id IN (%s, %s)
   AND bookmaker = 'draftkings'
   AND market IN ('spreads', 'totals', 'h2h')
   AND commence_time IS NOT NULL
   AND snapshot_at <= commence_time
   AND snapshot_at >= commence_time - make_interval(hours => %s)
"""

_QUOTE_FROM_ODDS = f"""
SELECT o.game_id, o.bookmaker, o.market,
       {_ODDS_SNAPSHOT} AS snapshot_at,
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
 WHERE o.game_id IN (%s, %s)
   AND o.bookmaker = 'draftkings'
   AND o.market IN ('spreads', 'totals', 'h2h')
   AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
   AND g.commence_time IS NOT NULL
   AND {_ODDS_SNAPSHOT} IS NOT NULL
   AND {_ODDS_SNAPSHOT} <= g.commence_time::timestamptz
   AND {_ODDS_SNAPSHOT}
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
    "ats_home_result", "ats_home_units_uncapped", "ats_home_units_capped",
    "ats_away_result", "ats_away_units_uncapped", "ats_away_units_capped",
    "ml_home_result", "ml_home_units_uncapped", "ml_home_units_capped",
    "ml_away_result", "ml_away_units_uncapped", "ml_away_units_capped",
    "ou_over_result", "ou_over_units_uncapped", "ou_over_units_capped",
    "ou_under_result", "ou_under_units_uncapped", "ou_under_units_capped",
    "home_rest_days", "away_rest_days", "is_primetime", "home_role", "away_role",
    "line_source",
)

# The lock-time shop. First capture wins (ON CONFLICT DO NOTHING) so a
# later rebuild still grades 2026 after the non-DraftKings quotes are gone.
SHOP_COLUMNS = (
    "canonical_key", "sport", "season", "week", "lock_window_hours",
    "market", "bookmaker", "line_source", "snapshot_at", "point",
    "dk_point", "price_home", "price_away",
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


def _as_quotes(rows, source: str) -> list[dict]:
    out = []
    for row in rows:
        out.append({
            "game_id": row[0], "bookmaker": row[1], "market": row[2],
            "snapshot_at": row[3], "commence_time": row[4],
            "point": row[5], "price_home": row[6], "price_away": row[7],
            "line_source": source,
        })
    return out


def _ids_for(game_id: str) -> tuple[str, str] | None:
    parsed = parse_game_id(game_id)
    if parsed is None:
        return None
    return parsed[0], "NFL_" + parsed[0]


def _dk_quotes(conn, ids: tuple[str, str]) -> list[dict]:
    bare, prefixed = ids
    history = _as_quotes(_fetch(
        conn, _QUOTE_FROM_HISTORY, (bare, prefixed, LOCK_WINDOW_HOURS)),
        "nfl_odds_history")
    odds = _as_quotes(_fetch(
        conn, _QUOTE_FROM_ODDS, (bare, prefixed, LOCK_WINDOW_HOURS)),
        "odds")
    return history + odds


def _shop_quotes(conn, ids: tuple[str, str], windows: list[tuple]) -> list[dict]:
    """Non-DraftKings rows inside the lock slices. No slices, no read."""
    if not windows:
        return []
    bare, prefixed = ids
    clauses = []
    params: list = [bare, prefixed]
    for market, floor, lock_at in windows:
        clauses.append(
            "(market = %s AND snapshot_at >= %s AND snapshot_at <= %s)")
        params.extend([market, floor, lock_at])
    arms = " OR ".join(clauses)
    history_sql = f"""
        SELECT game_id, bookmaker, market, snapshot_at, commence_time,
               point, price_home, price_away
          FROM nfl_odds_history
         WHERE game_id IN (%s, %s)
           AND bookmaker <> 'draftkings'
           AND commence_time IS NOT NULL
           AND snapshot_at <= commence_time
           AND ({arms})
    """
    odds_sql = f"""
        SELECT o.game_id, o.bookmaker, o.market,
               {_ODDS_SNAPSHOT} AS snapshot_at,
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
         WHERE o.game_id IN (%s, %s)
           AND o.bookmaker <> 'draftkings'
           AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
           AND g.commence_time IS NOT NULL
           AND {_ODDS_SNAPSHOT} IS NOT NULL
           AND ({arms.replace("snapshot_at", _ODDS_SNAPSHOT)})
           AND {_ODDS_SNAPSHOT} <= g.commence_time::timestamptz
    """
    return (_as_quotes(_fetch(conn, history_sql, params), "nfl_odds_history")
            + _as_quotes(_fetch(conn, odds_sql, params), "odds"))


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


def _load_shop(conn, season: int) -> dict[str, list[dict]]:
    rows = _fetch(conn, """
        SELECT canonical_key, lock_window_hours, market, bookmaker,
               point, dk_point, price_home, price_away, line_source
          FROM byom_lock_shop
         WHERE season = %s AND sport = %s
    """, (season, SPORT))
    out: dict[str, list[dict]] = {}
    for row in rows:
        out.setdefault(row[0], []).append({
            "canonical_key": row[0],
            "lock_window_hours": row[1],
            "market": row[2],
            "bookmaker": row[3],
            "point": row[4],
            "dk_point": row[5],
            "price_home": row[6],
            "price_away": row[7],
            "line_source": row[8],
        })
    return out


def season_facts_and_shop(conn, season: int, books: list[str]):
    """Facts this season would write, and the shop rows from the quotes
    still stored. No INSERT. Grades use the shop already captured when
    that row is still at this DraftKings line."""
    if season < DK_HISTORY_START_SEASON:
        return [], []
    games = _games(conn, season)
    played = _played(games)
    stored = _load_shop(conn, season)
    facts = []
    shops = []
    for game in games:
        ids = _ids_for(game["game_id"])
        if ids is None:
            continue
        quotes = _dk_quotes(conn, ids)
        quotes += _shop_quotes(conn, ids, shop_windows(quotes))
        fact, fresh = capture_game(game, quotes, played, books)
        if fact is None:
            continue
        regrade_from_shop(fact, stored.get(fact["canonical_key"], []), books)
        facts.append(fact)
        shops.extend(fresh)
    return facts, shops


def facts_for_season(conn, season: int, books: list[str]) -> list[dict]:
    """The facts this season would write. No INSERT."""
    facts, _shops = season_facts_and_shop(conn, season, books)
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


def _write_shop(conn, season: int, shops: list[dict], stored: dict) -> int:
    """Insert shop rows. A book already captured at this line stays.

    When the DraftKings line for a market has moved, that market's stored
    rows are the previous lock. They are replaced by this one.
    """
    if not shops:
        return 0
    for key, window, market in shop_markets_to_replace(shops, stored):
        conn.execute("""
            DELETE FROM byom_lock_shop
             WHERE canonical_key = %s
               AND lock_window_hours = %s
               AND market = %s
        """, (key, window, market))
    cols = ", ".join(SHOP_COLUMNS)
    placeholders = ", ".join(["%s"] * len(SHOP_COLUMNS))
    sql = (
        f"INSERT INTO byom_lock_shop ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT (canonical_key, lock_window_hours, market, bookmaker) "
        f"DO NOTHING"
    )
    values = [tuple(row[col] for col in SHOP_COLUMNS) for row in shops]
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
            "season": season, "facts": 0, "written": 0, "shop": 0,
            "skipped": "before DraftKings history",
        }
    facts, shops = season_facts_and_shop(conn, season, books)
    written = 0
    if apply:
        stored = _load_shop(conn, season)
        _write_shop(conn, season, shops, stored)
        written = _upsert(conn, facts)
    return {
        "season": season, "facts": len(facts), "written": written,
        "shop": len(shops) if apply else 0,
    }


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
