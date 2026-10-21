"""One quote per book for a fact that already exists.

The fact row stays the DraftKings line at game start. These rows are
the other books, and DraftKings itself, from that same last snapshot
at or before kickoff. A quote with no line is dropped before the rank,
the same way prop facts drop one. The tables are created by
data/migrations/byom_book_quotes_2026_10_21.sql, which is not applied
here. apply=false, and a database without the tables, writes nothing.
"""
from __future__ import annotations

from decimal import Decimal

from byom.game_facts import lead_hours, parse_game_id, parse_ts
from byom.prop_facts import (
    _capture_rank,
    _line_of,
    is_standard_market,
    player_key,
)

GAME_MARKETS = ("spreads", "totals", "h2h")


def _num(value):
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _ready(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT to_regclass(%s)", (f"public.{table}",),
    ).fetchone()
    return row is not None and row[0] is not None


def _prop_row(quote: dict) -> dict | None:
    market = quote.get("market")
    book = (quote.get("bookmaker") or "").strip().lower()
    if not book or not is_standard_market(market):
        return None
    key = player_key(quote.get("player_name"))
    if not key:
        return None
    lead = lead_hours(quote.get("snapshot_at"), quote.get("commence_time"))
    if lead is None or lead < 0:
        return None
    snap = parse_ts(quote.get("snapshot_at"))
    if snap is None:
        return None
    row = dict(quote)
    row["player_key"] = key
    row["market"] = market
    row["book"] = book
    row["snapshot_at"] = snap
    row["point"] = _line_of(row, market)
    return row


def prop_quote_rows(facts: list[dict], quotes: list[dict]) -> list[dict]:
    """One over row and one under row per book, on the DraftKings fact.

    A player and market with no DraftKings fact is not quoted. Two lines
    on one book's last snapshot: the later captured_at, then the higher
    prop_id, then the line text. A null line does not win that rank.
    """
    fact_id = {
        (fact["player_key"], fact["market"]): fact["prop_key"]
        for fact in facts
        if fact.get("player_key") and fact.get("market") and fact.get("prop_key")
    }
    grouped: dict[tuple, list[dict]] = {}
    for quote in quotes:
        row = _prop_row(quote)
        if row is None or row.get("point") is None:
            continue
        if (row["player_key"], row["market"]) not in fact_id:
            continue
        grouped.setdefault(
            (row["player_key"], row["market"], row["book"]), [],
        ).append(row)
    out = []
    for (key, market, book), pool in grouped.items():
        latest = max(quote["snapshot_at"] for quote in pool)
        at_snap = [quote for quote in pool if quote["snapshot_at"] == latest]
        at_line = [quote for quote in at_snap if quote.get("point") is not None]
        if not at_line:
            continue
        quote = max(at_line, key=_capture_rank)
        captured = parse_ts(quote.get("captured_at")) or quote["snapshot_at"]
        base = {
            "fact_id": fact_id[(key, market)],
            "book": book,
            "market": market,
            "line": quote["point"],
            "captured_at": captured,
        }
        out.append({**base, "side": "over", "price": _num(quote.get("over_price"))})
        out.append({**base, "side": "under", "price": _num(quote.get("under_price"))})
    return out


def _game_row(quote: dict) -> dict | None:
    market = quote.get("market")
    book = (quote.get("bookmaker") or "").strip().lower()
    if market not in GAME_MARKETS or not book:
        return None
    lead = lead_hours(quote.get("snapshot_at"), quote.get("commence_time"))
    if lead is None or lead < 0:
        return None
    snap = parse_ts(quote.get("snapshot_at"))
    if snap is None:
        return None
    row = dict(quote)
    row["book"] = book
    row["market"] = market
    row["lead_hours"] = lead
    row["snapshot_at"] = snap
    row["point"] = _num(quote.get("point"))
    row["price_home"] = _num(quote.get("price_home"))
    row["price_away"] = _num(quote.get("price_away"))
    return row


def _pick_game(pool: list[dict], require_line: bool) -> dict | None:
    ready = []
    for quote in pool:
        if require_line and quote.get("point") is None:
            continue
        if (not require_line and quote.get("price_home") is None
                and quote.get("price_away") is None):
            continue
        ready.append(quote)
    if not ready:
        return None
    latest = max(quote["snapshot_at"] for quote in ready)
    at_snap = [quote for quote in ready if quote["snapshot_at"] == latest]

    def rank(quote: dict) -> tuple:
        price = quote.get("price_home")
        if price is None:
            price = Decimal("-999999")
        point = quote.get("point")
        return (price, "" if point is None else format(point, "f"))

    return max(at_snap, key=rank)


def game_quote_rows(canonical_key: str, quotes: list[dict]) -> list[dict]:
    """Spreads, totals, and moneylines. The spread line is that side's number.

    Home spread is the home handicap. Away spread is its opposite. A
    moneyline has a price and no line. A spread or total with no line
    is not a row.
    """
    grouped: dict[tuple, list[dict]] = {}
    for quote in quotes:
        row = _game_row(quote)
        if row is None:
            continue
        grouped.setdefault((row["book"], row["market"]), []).append(row)
    out = []
    for (book, market), pool in grouped.items():
        chosen = _pick_game(pool, require_line=market != "h2h")
        if chosen is None:
            continue
        captured = chosen["snapshot_at"]
        if market == "spreads":
            point = chosen["point"]
            sides = (
                ("home", point, chosen.get("price_home")),
                ("away", -point, chosen.get("price_away")),
            )
        elif market == "totals":
            point = chosen["point"]
            sides = (
                ("over", point, chosen.get("price_home")),
                ("under", point, chosen.get("price_away")),
            )
        else:
            sides = (
                ("home", None, chosen.get("price_home")),
                ("away", None, chosen.get("price_away")),
            )
        for side, line, price in sides:
            if market == "h2h" and price is None:
                continue
            out.append({
                "fact_id": canonical_key,
                "book": book,
                "market": market,
                "side": side,
                "line": line,
                "price": price,
                "captured_at": captured,
            })
    return out


_ODDS_SNAPSHOT = """
CASE WHEN o.snapshot_at ~ '^[0-9]{4}-'
     THEN o.snapshot_at::timestamptz
     ELSE NULL END
"""

_GAME_HISTORY = """
SELECT bookmaker, market, snapshot_at, commence_time, point,
       price_home, price_away
  FROM nfl_odds_history
 WHERE game_id IN (%s, %s)
   AND market IN ('spreads', 'totals', 'h2h')
   AND commence_time IS NOT NULL
   AND snapshot_at <= commence_time
"""

_GAME_ODDS = f"""
SELECT o.bookmaker, o.market,
       {_ODDS_SNAPSHOT} AS snapshot_at,
       g.commence_time::timestamptz AS commence_time,
       CASE o.market
         WHEN 'spreads' THEN o.spread_home
         WHEN 'totals' THEN o.total_line
         ELSE NULL
       END AS point,
       CASE o.market WHEN 'totals' THEN o.over_price ELSE o.home_price END,
       CASE o.market WHEN 'totals' THEN o.under_price ELSE o.away_price END
  FROM odds o
  JOIN games g ON g.game_id = o.game_id
 WHERE o.game_id IN (%s, %s)
   AND o.market IN ('spreads', 'totals', 'h2h')
   AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
   AND g.commence_time IS NOT NULL
   AND {_ODDS_SNAPSHOT} IS NOT NULL
   AND {_ODDS_SNAPSHOT} <= g.commence_time::timestamptz
"""


def _ts_case(expr: str) -> str:
    pattern = (
        "^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
    )
    return (
        f"CASE WHEN {expr}::text ~ '{pattern}' "
        f"THEN {expr}::timestamptz ELSE NULL END"
    )


def _prop_sql() -> str:
    snap = _ts_case("p.snapshot_at")
    kick = _ts_case("g.commence_time")
    return f"""
        SELECT p.player_name, p.team, p.market, p.bookmaker,
               {snap} AS snapshot_at,
               {kick} AS commence_time,
               p.line, p.prop_id, p.created_at,
               p.over_price, p.under_price
          FROM player_prop_odds p
          JOIN games g ON g.game_id = p.game_id
         WHERE p.game_id = %s
           AND p.market = ANY(%s)
           AND (p.snapshot_type IS NULL OR p.snapshot_type <> 'in_play')
           AND {kick} IS NOT NULL
           AND {snap} IS NOT NULL
           AND {snap} <= {kick}
    """


def _fetch(conn, sql, params):
    cur = conn.execute(sql, params)
    return cur.fetchall()


def _ids(canonical_key: str) -> tuple[str, str] | None:
    parsed = parse_game_id(canonical_key)
    if parsed is None:
        return None
    return parsed[0], "NFL_" + parsed[0]


def _game_quotes(conn, canonical_key: str) -> list[dict]:
    ids = _ids(canonical_key)
    if ids is None:
        return []
    rows = []
    for sql in (_GAME_HISTORY, _GAME_ODDS):
        for row in _fetch(conn, sql, ids):
            rows.append({
                "bookmaker": row[0], "market": row[1],
                "snapshot_at": row[2], "commence_time": row[3],
                "point": row[4], "price_home": row[5], "price_away": row[6],
            })
    return game_quote_rows(canonical_key, rows)


def _replace(conn, table: str, fact_ids: list[str], rows: list[dict]) -> int:
    if fact_ids:
        conn.execute(
            f"DELETE FROM {table} WHERE fact_id = ANY(%s)",
            (fact_ids,),
        )
    if not rows:
        return 0
    conn.executemany(
        f"""
        INSERT INTO {table}
          (fact_id, book, market, side, line, price, captured_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fact_id, book, market, side) DO UPDATE
          SET line = EXCLUDED.line,
              price = EXCLUDED.price,
              captured_at = EXCLUDED.captured_at
        """,
        [
            (row["fact_id"], row["book"], row["market"], row["side"],
             row["line"], row["price"], row["captured_at"])
            for row in rows
        ],
    )
    return len(rows)


def write_game_quotes(conn, facts: list[dict]) -> int:
    """Replace quotes for these facts. No table, no write."""
    if not facts or not _ready(conn, "byom_game_book_quotes"):
        return 0
    rows = []
    ids = []
    for fact in facts:
        key = fact.get("canonical_key")
        if not key:
            continue
        ids.append(key)
        rows.extend(_game_quotes(conn, key))
    return _replace(conn, "byom_game_book_quotes", ids, rows)


def write_prop_quotes(conn, facts: list[dict], canonical_keys: list[str]) -> int:
    """Replace prop quotes for these games. A game with no fact loses its quotes."""
    if not _ready(conn, "byom_prop_book_quotes"):
        return 0
    from byom.prop_facts import MARKET_COLUMNS

    keys = list(dict.fromkeys(canonical_keys))
    fact_ids = []
    if keys:
        cur = conn.execute(
            "SELECT fact_id FROM byom_prop_book_quotes "
            "WHERE split_part(fact_id, '|', 1) = ANY(%s)",
            (keys,),
        )
        fact_ids = [row[0] for row in cur.fetchall()]
    rows = []
    by_game: dict[str, list[dict]] = {}
    for fact in facts:
        by_game.setdefault(fact["canonical_key"], []).append(fact)
    sql = _prop_sql()
    markets = list(MARKET_COLUMNS)
    for key, game_facts in by_game.items():
        ids = _ids(key)
        if ids is None:
            continue
        fetched = []
        for game_id in ids:
            for row in _fetch(conn, sql, (game_id, markets)):
                fetched.append({
                    "player_name": row[0], "team": row[1], "market": row[2],
                    "bookmaker": row[3], "snapshot_at": row[4],
                    "commence_time": row[5], "point": row[6],
                    "prop_id": row[7], "captured_at": row[8],
                    "over_price": row[9], "under_price": row[10],
                })
        rows.extend(prop_quote_rows(game_facts, fetched))
        fact_ids.extend(fact["prop_key"] for fact in game_facts)
    return _replace(
        conn, "byom_prop_book_quotes", list(dict.fromkeys(fact_ids)), rows,
    )
