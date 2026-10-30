"""Read DraftKings lines and write byom_game_facts.

Reads games, and for NFL also nfl_odds_history. Every sport is read
from odds. Writes only byom_game_facts. Does not touch picks.
`apply=False` is the default: count the rows and write nothing.

The line is the last DraftKings quote at or before game start.
nfl_odds_history and odds are one pool for NFL. Grading uses that
line. The spread price and the total price are the American price on
that quote, or the closest earlier DraftKings price for the same
market and side: same point first, then any point. A moneyline price
is the last pre-start quote that has that side. Another book is not
read. A missing line does not skip the game. A missing American price
is stored as null. byom_backtest counts a played bet with no
DraftKings line, and a played bet that has a line but no American
price, in skipped. Both stay out of the win-loss record and the units.
An unplayed game is in neither. Each build reports how many spread and
total sides used same_point, how many used cross_point, and how many
are line_no_price. Moneyline grading is the score only.
"""
from __future__ import annotations

from byom.constants import (
    DK_HISTORY_START_SEASON,
    NBA_DK_HISTORY_START_SEASON,
    SPORT,
)
from byom.game_facts import assemble_game, parse_date, parse_game_id

# One game at a time. A season of nfl_odds_history is millions of rows
# (one 2026 game, NFL_2026_05_BAL_ATL, is 12,991 DraftKings rows by itself,
# measured 2026-10-16). The index is (game_id, market). This builder reads
# DraftKings h2h, spreads, and totals at or before game start. apply=false
# uses the same reads and writes nothing. price_home is the home price,
# or the over on a total. price_away is the away price, or the under.
_ODDS_SNAPSHOT = """
CASE WHEN o.snapshot_at ~ '^[0-9]{4}-'
     THEN o.snapshot_at::timestamptz
     ELSE NULL END
"""

_MARKETS = "('h2h', 'spreads', 'totals')"

# created_at is text on odds. A value that is not a timestamp is NULL,
# the same guard as snapshot_at, so one bad stamp does not abort the game.
_ODDS_CREATED = """
CASE WHEN o.created_at ~ '^[0-9]{4}-'
     THEN o.created_at::timestamptz
     ELSE NULL END
"""

_QUOTE_FROM_HISTORY = f"""
SELECT game_id, bookmaker, market, snapshot_at, commence_time, point,
       price_home, price_away,
       NULL::timestamptz AS created_at,
       NULL::bigint AS quote_id
  FROM nfl_odds_history
 WHERE game_id IN (%s, %s)
   AND bookmaker = 'draftkings'
   AND market IN {_MARKETS}
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
       END AS point,
       CASE o.market
         WHEN 'totals' THEN o.over_price
         ELSE o.home_price
       END AS price_home,
       CASE o.market
         WHEN 'totals' THEN o.under_price
         ELSE o.away_price
       END AS price_away,
       {_ODDS_CREATED} AS created_at,
       o.odds_id AS quote_id
  FROM odds o
  JOIN games g ON g.game_id = o.game_id
 WHERE o.game_id = %s
   AND o.bookmaker = 'draftkings'
   AND o.market IN {_MARKETS}
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
    "dk_ml_home_price", "dk_ml_away_price",
    "dk_spread_home_price", "dk_spread_away_price",
    "dk_total_over_price", "dk_total_under_price",
    "ats_home_result", "ats_away_result",
    "ml_home_result", "ml_away_result",
    "ou_over_result", "ou_under_result",
    "home_rest_days", "away_rest_days", "is_primetime", "home_role", "away_role",
)


def _fetch(conn, sql, params):
    cur = conn.execute(sql, params)
    return cur.fetchall()


def _dk_history_floor(sport: str) -> int | None:
    """First season whose DraftKings game lines are built.

    NFL is 2020. NBA is 2021. Any other sport has no floor.
    """
    if sport == SPORT:
        return DK_HISTORY_START_SEASON
    if sport == "NBA":
        return NBA_DK_HISTORY_START_SEASON
    return None


def _games(conn, season: int, sport: str = SPORT) -> list[dict]:
    rows = _fetch(conn, """
        SELECT game_id, season, game_date, home_team, away_team,
               home_score, away_score, commence_time, sport, week
          FROM games
         WHERE sport = %s AND season = %s
    """, (sport, season))
    out = []
    for row in rows:
        out.append({
            "game_id": row[0], "season": row[1], "game_date": row[2],
            "home_team": row[3], "away_team": row[4],
            "home_score": row[5], "away_score": row[6], "commence_time": row[7],
            "sport": row[8], "week": row[9],
        })
    return out


def _as_quotes(rows) -> list[dict]:
    out = []
    for row in rows:
        out.append({
            "game_id": row[0], "bookmaker": row[1], "market": row[2],
            "snapshot_at": row[3], "commence_time": row[4],
            "point": row[5], "price_home": row[6], "price_away": row[7],
            "created_at": row[8], "quote_id": row[9],
        })
    return out


def _ids_for(game_id: str) -> tuple[str, str] | None:
    parsed = parse_game_id(game_id)
    if parsed is None:
        return None
    return parsed[0], "NFL_" + parsed[0]


def _played(games: list[dict]) -> dict:
    played: dict[str, list] = {}
    for game in games:
        day = parse_date(game.get("game_date"))
        if day is None:
            continue
        parsed = parse_game_id(game["game_id"])
        if parsed is not None:
            _, _, _, away, home = parsed
        else:
            away = game.get("away_team")
            home = game.get("home_team")
            if not away or not home:
                continue
        played.setdefault(away, []).append(day)
        played.setdefault(home, []).append(day)
    return played


def _dk_quotes(conn, game_id: str, sport: str) -> list[dict]:
    """DraftKings quotes for one game. NFL also reads nfl_odds_history.

    odds is read on games.game_id only. Measured 2026-10-23, two NFL
    games in each season 2020–2026: every DraftKings h2h/spread/total
    row was on that id, and the bare key had zero. History still uses
    the bare key and the NFL_ key. Other books are not in either query.
    """
    odds = _as_quotes(_fetch(conn, _QUOTE_FROM_ODDS, (game_id,)))
    if sport != SPORT:
        return odds
    ids = _ids_for(game_id)
    if ids is None:
        return odds
    history = _as_quotes(_fetch(conn, _QUOTE_FROM_HISTORY, ids))
    return history + odds


def facts_for_season(conn, season: int,
                     game_ids: list[str] | None = None,
                     sport: str = SPORT) -> list[dict]:
    """The facts this season would write. No INSERT.

    `game_ids` None reads every game. A list reads only those games.
    Rest days still come from the whole season's schedule. NFL seasons
    before 2020, and NBA seasons before 2021, are empty.
    """
    floor = _dk_history_floor(sport)
    if floor is not None and season < floor:
        return []
    schedule = _games(conn, season, sport)
    played = _played(schedule)
    if game_ids is None:
        games = schedule
    else:
        wanted = set(game_ids)
        games = [game for game in schedule if game["game_id"] in wanted]
    facts = []
    for game in games:
        if sport == SPORT and _ids_for(game["game_id"]) is None:
            continue
        quotes = _dk_quotes(conn, game["game_id"], sport)
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


def price_fallback_counts(facts) -> dict:
    """Spread and total sides priced by a fallback, or left unpriced.

    `same_point` is a side whose graded quote had no American price and
    an earlier pre-start DraftKings quote at that point did.
    `cross_point` is a side priced from an earlier quote at a different
    point. `line_no_price` is a graded line with no American price on
    any pre-start DraftKings quote for that side. Each of the four
    sides is one count. Moneyline sides are not in these counts. A
    side with no graded line is not `line_no_price`.
    """
    counts = {"same_point": 0, "cross_point": 0, "line_no_price": 0}
    for fact in facts:
        for basis in (fact.get("_price_basis") or {}).values():
            if basis in counts:
                counts[basis] += 1
    return counts


def _sport_or_nfl(sport) -> str:
    """An omitted sport is NFL. An explicit null is the same."""
    if not sport:
        return SPORT
    return str(sport)


def build_season(conn, season: int, apply: bool = False,
                 game_ids: list[str] | None = None,
                 sport: str | None = SPORT) -> dict:
    """One season of one sport. apply=False writes nothing.

    `game_ids` limits which games are read. None is the whole season.
    `sport` null is NFL. The result includes the fallback counts.
    """
    sport = _sport_or_nfl(sport)
    empty_counts = {"same_point": 0, "cross_point": 0, "line_no_price": 0}
    floor = _dk_history_floor(sport)
    if floor is not None and season < floor:
        return {
            "season": season, "sport": sport, "facts": 0, "written": 0,
            "skipped": "before DraftKings history",
            **empty_counts,
        }
    facts = facts_for_season(conn, season, game_ids=game_ids, sport=sport)
    written = _upsert(conn, facts) if apply else 0
    return {
        "season": season, "sport": sport,
        "facts": len(facts), "written": written,
        **price_fallback_counts(facts),
    }


def seasons_in_games(conn, sport: str = SPORT) -> list[int]:
    floor = ""
    params: tuple = (sport,)
    start = _dk_history_floor(sport)
    if start is not None:
        floor = " AND season >= %s"
        params = (sport, start)
    rows = _fetch(conn, f"""
        SELECT DISTINCT season FROM games
         WHERE sport = %s{floor}
         ORDER BY season
    """, params)
    return [int(row[0]) for row in rows]


def sports_in_games(conn) -> list[str]:
    rows = _fetch(conn, """
        SELECT DISTINCT sport FROM games
         WHERE sport IS NOT NULL
         ORDER BY sport
    """, ())
    return [str(row[0]) for row in rows]


def build_seasons(conn, seasons, apply: bool = False,
                  sport: str | None = SPORT) -> dict:
    """`sport` null is NFL. Passing None does not query with a null sport."""
    sport = _sport_or_nfl(sport)
    if seasons is None:
        seasons = seasons_in_games(conn, sport)
    elif isinstance(seasons, int):
        seasons = [seasons]
    built = [
        build_season(conn, int(s), apply=apply, sport=sport) for s in seasons
    ]
    if apply:
        conn.commit()
    return {"apply": apply, "sport": sport, "seasons": built}
