"""Grade one NFL player prop into a byom_prop_facts row.

No database. No stake. Units are the pair units_1u_to_win already uses:
uncapped 1u-to-win, and the same 3u risk cap. A missing price leaves
both NULL.

The lock window is PROP_LOCK_WINDOW_HOURS (24). That number is
UNCONFIRMED. It is not the live models' price and it is not a filter on
the line or the price.

Standard markets only. A key ending in `_alternate` is an alt ladder and
is not a fact.

Thin data, recorded on the row as log_status:

- logged: the game has a log and this player's normalised name matches
  one row. actual is that row's stat.
- non_participant: the game has a log and this name matches nobody.
  actual is 0. A player who played but whose row never landed looks the
  same as a scratch. The row says which rule fired.
- missing_log: the game has been played and the log has zero rows. The
  ingest has not arrived. actual and both results stay NULL. A missing
  file is not a loss.
- unplayed: the game has no final score. Results stay NULL.
- ambiguous: two log rows normalise to the same name. No guess. Results
  stay NULL.

Anytime TD is rushing_tds + receiving_tds. Passing TDs are a different
market. A return or defensive score is not in nfl_player_game_log, so a
touchdown that is only a return grades as a loss. That is the file's
limit, not a zero we invented.

Tackles are solo + assists. That sum runs short of the number some books
grade. The row stores the sum we have.

Name match is data.name_match.normalize_player_name: case, accents,
punctuation, and a trailing suffix. It does not expand nicknames
(Josh/Joshua). A nickname miss on a logged game is non_participant.
"""
from __future__ import annotations

from decimal import Decimal

from data.name_match import normalize_player_name

from byom.constants import PROP_LOCK_WINDOW_HOURS, SHOP_LAG_MINUTES, SPORT
from byom.game_facts import (
    _priced,
    best_price,
    closing_quote,
    first_in_window,
    parse_game_id,
    quotes_at_lock,
    same_line,
    units_1u_to_win,
)

# Odds API market -> nfl_player_game_log columns summed into actual.
# Alternates are absent on purpose.
MARKET_COLUMNS: dict[str, tuple[str, ...]] = {
    "player_pass_yds": ("passing_yards",),
    "player_pass_attempts": ("attempts",),
    "player_pass_completions": ("completions",),
    "player_pass_tds": ("passing_tds",),
    "player_rush_yds": ("rushing_yards",),
    "player_rush_attempts": ("carries",),
    "player_reception_yds": ("receiving_yards",),
    "player_receptions": ("receptions",),
    "player_rush_reception_yds": ("rushing_yards", "receiving_yards"),
    "player_anytime_td": ("rushing_tds", "receiving_tds"),
    "player_tackles_assists": ("def_tackles_solo", "def_tackle_assists"),
    "player_sacks": ("def_sacks",),
}

ANYTIME_TD_MARKET = "player_anytime_td"
# Yes/No anytime rows are stored at 0.5 when the feed omits a point.
ANYTIME_TD_LINE = Decimal("0.5")

SOURCE_PROPS = "player_prop_odds"


def is_standard_market(market: str | None) -> bool:
    """True for a main line. An alt ladder key is false."""
    if not market or market.endswith("_alternate"):
        return False
    return market in MARKET_COLUMNS


def player_key(name: str | None) -> str:
    return normalize_player_name(name)


def _num(value) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def actual_from_log(row: dict, market: str) -> Decimal:
    """Sum the columns this market grades. A NULL column counts as 0
    once the row itself matched. Passing TDs are not in anytime TD."""
    total = Decimal(0)
    for col in MARKET_COLUMNS[market]:
        value = _num(row.get(col))
        if value is not None:
            total += value
    return total


def grade_ou(actual, line) -> tuple[str, str] | None:
    """(over, under). Push when actual equals the line."""
    if actual is None or line is None:
        return None
    diff = Decimal(str(actual)) - Decimal(str(line))
    if diff > 0:
        return "win", "loss"
    if diff < 0:
        return "loss", "win"
    return "push", "push"


def log_status(played: bool, game_row_count: int, matches: int) -> str:
    if not played:
        return "unplayed"
    if game_row_count <= 0:
        return "missing_log"
    if matches > 1:
        return "ambiguous"
    if matches == 0:
        return "non_participant"
    return "logged"


def _line_of(quote: dict, market: str):
    raw = quote.get("point")
    if raw is None:
        raw = quote.get("line")
    line = _num(raw)
    if line is None and market == ANYTIME_TD_MARKET:
        return ANYTIME_TD_LINE
    return line


def _normalize(quote: dict) -> dict:
    """One shape: point, price_home = over, price_away = under."""
    row = dict(quote)
    market = row.get("market")
    row["point"] = _line_of(row, market)
    if row.get("price_home") is None:
        row["price_home"] = row.get("over_price")
    if row.get("price_away") is None:
        row["price_away"] = row.get("under_price")
    return row


def _group_dk(quotes: list[dict]) -> dict[tuple, list[dict]]:
    """(player_key, market) -> priced DraftKings quotes inside the window."""
    grouped: dict[tuple, list[dict]] = {}
    for quote in quotes:
        market = quote.get("market")
        if (quote.get("bookmaker") or "").lower() != "draftkings":
            continue
        if not is_standard_market(market):
            continue
        key = player_key(quote.get("player_name"))
        if not key:
            continue
        priced = _priced([quote], market, "draftkings")
        if not priced:
            continue
        row = priced[0]
        row["player_key"] = key
        row["player_name"] = quote.get("player_name")
        row["team"] = quote.get("team")
        row["point"] = _line_of(row, market)
        grouped.setdefault((key, market), []).append(row)
    return grouped


def _rows_for_player(log_rows: list[dict], key: str) -> list[dict]:
    return [row for row in log_rows if player_key(row.get("player_name")) == key]


def facts_for_game(game: dict, quotes: list[dict], log_rows: list[dict],
                   books: list[str]) -> list[dict]:
    """Prop facts for one game. Empty when the id does not parse or no
    DraftKings standard market locks inside the prop window."""
    parsed = parse_game_id(game.get("game_id") or "")
    if parsed is None:
        return []
    canonical, season, week, _away, _home = parsed
    played = game.get("home_score") is not None and game.get("away_score") is not None
    quotes = [
        _normalize(quote) for quote in quotes
        if is_standard_market(quote.get("market"))
    ]
    game_rows = len(log_rows)
    out = []
    for (key, market), pool in _group_dk(quotes).items():
        lock = first_in_window(pool, PROP_LOCK_WINDOW_HOURS)
        if lock is None:
            continue
        lock_at = lock["snapshot_at"]
        lines = []
        seen_lines = []
        for quote in pool:
            if quote["snapshot_at"] != lock_at:
                continue
            line = quote.get("point")
            if line is None or any(same_line(line, prev) for prev in seen_lines):
                continue
            seen_lines.append(line)
            lines.append(line)
        matches = _rows_for_player(log_rows, key)
        status = log_status(played, game_rows, len(matches) if played else 0)
        for line in lines:
            out.append(_one(
                canonical, season, week, game, pool, quotes, books,
                key, market, line, lock, status, matches, played,
            ))
    return out


def _one(canonical, season, week, game, pool, quotes, books,
         key, market, line, lock, status, matches, played) -> dict:
    shop = quotes_at_lock(
        [q for q in quotes if player_key(q.get("player_name")) == key
         and q.get("market") == market],
        lock["snapshot_at"], line, SHOP_LAG_MINUTES)
    # quotes_at_lock reads `point`. Prop rows from the loader use `point`.
    over_price, over_book = best_price(shop, market, "home", line, books)
    under_price, under_book = best_price(shop, market, "away", line, books)
    close_pool = [q for q in pool if same_line(q.get("point"), line)]
    close = closing_quote(close_pool)
    actual = None
    graded = None
    if status == "logged" and matches:
        actual = actual_from_log(matches[0], market)
        graded = grade_ou(actual, line)
    elif status == "non_participant":
        actual = Decimal(0)
        graded = grade_ou(actual, line)
    over_result = under_result = None
    if graded is not None:
        over_result, under_result = graded
    over_u, over_c = units_1u_to_win(over_result, over_price)
    under_u, under_c = units_1u_to_win(under_result, under_price)
    line_text = format(line, "f")
    return {
        "prop_key": f"{canonical}|{market}|{key}|{line_text}",
        "canonical_key": canonical,
        "sport": SPORT,
        "season": season,
        "week": week,
        "player_name": lock.get("player_name") or key,
        "player_key": key,
        "team": lock.get("team"),
        "market": market,
        "line": line,
        "lock_window_hours": PROP_LOCK_WINDOW_HOURS,
        "lock_snapshot_at": lock["snapshot_at"],
        "dk_over_price": _num(lock.get("price_home")),
        "dk_under_price": _num(lock.get("price_away")),
        "grade_over_price": over_price,
        "grade_over_book": over_book,
        "grade_under_price": under_price,
        "grade_under_book": under_book,
        "close_snapshot_at": None if close is None else close["snapshot_at"],
        "close_over_price": None if close is None else _num(close.get("price_home")),
        "close_under_price": None if close is None else _num(close.get("price_away")),
        "actual": actual,
        "over_result": over_result,
        "over_units_uncapped": over_u,
        "over_units_capped": over_c,
        "under_result": under_result,
        "under_units_uncapped": under_u,
        "under_units_capped": under_c,
        "log_status": status,
        "line_source": lock.get("line_source") or SOURCE_PROPS,
        "game_date": game.get("game_date"),
    }
