"""Pure grading for one NFL game's Build Your Own Model fact.

No database. No stake. A win pays +1 unit (1u to win) and a loss costs the
stake that win required. There is no risk cap. A missing price leaves the
units NULL. Pushes and ties are results, not dropped rows.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from byom.constants import (
    DK_HISTORY_START_SEASON,
    LOCK_WINDOW_HOURS,
    NEAR_LOCK_WINDOW_HOURS,
    SHOP_LAG_MINUTES,
    SOURCE_HISTORY,
    SOURCE_ODDS,
)

_KEY = re.compile(r"^(?:NFL_)?(\d{4})_(\d{2})_([A-Z]{2,3})_([A-Z]{2,3})$")
_ET = ZoneInfo("America/New_York")
_Q = Decimal("0.0001")
_LINE = Decimal("0.001")


def parse_ts(value):
    """Timezone-aware UTC, or None. Naive stamps are UTC. Text with Z works."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def parse_game_id(game_id: str) -> tuple[str, int, int, str, str] | None:
    """(canonical_key, season, week, away, home) or None.

    Week comes from the id. games.week is NULL for every NFL season, so it
    is not an input.
    """
    match = _KEY.fullmatch(str(game_id or "").strip())
    if not match:
        return None
    season_s, week_s, away, home = match.groups()
    season, week = int(season_s), int(week_s)
    return f"{season_s}_{week_s}_{away}_{home}", season, week, away, home


def lead_hours(snapshot_at, commence) -> float | None:
    snap = parse_ts(snapshot_at)
    kick = parse_ts(commence)
    if snap is None or kick is None:
        return None
    return (kick - snap).total_seconds() / 3600.0


def _priced(quotes, market: str, bookmaker: str | None = None) -> list[dict]:
    out = []
    for quote in quotes:
        if quote.get("market") != market:
            continue
        if bookmaker is not None and (quote.get("bookmaker") or "").lower() != bookmaker:
            continue
        lead = lead_hours(quote.get("snapshot_at"), quote.get("commence_time"))
        if lead is None:
            continue
        out.append({**quote, "lead_hours": lead, "snapshot_at": parse_ts(quote["snapshot_at"])})
    return out


def first_in_window(quotes, window_hours: int) -> dict | None:
    """Earliest pre-game quote whose lead is at or under `window_hours`."""
    chosen = None
    for quote in quotes:
        lead = quote["lead_hours"]
        if lead < 0 or lead > window_hours:
            continue
        if chosen is None or quote["snapshot_at"] < chosen["snapshot_at"]:
            chosen = quote
    return chosen


def closing_quote(quotes) -> dict | None:
    """Latest pre-game quote. In-play (negative lead) is not a close."""
    chosen = None
    for quote in quotes:
        if quote["lead_hours"] < 0:
            continue
        if chosen is None or quote["snapshot_at"] > chosen["snapshot_at"]:
            chosen = quote
    return chosen


def is_primetime(commence) -> bool | None:
    """Thursday and Monday kickoffs, and any kickoff at 7pm ET or later.

    A Sunday 1pm or 4pm ET kickoff is not primetime. Missing commence is
    None, not a guess.
    """
    kick = parse_ts(commence)
    if kick is None:
        return None
    local = kick.astimezone(_ET)
    if local.weekday() in (0, 3):
        return True
    return local.hour >= 19


def rest_days(team: str, game_day: date | None, played: dict[str, list[date]]) -> int | None:
    """Days since this team's previous game in the same schedule. None when
    this is the first date we have for them."""
    if game_day is None:
        return None
    prior = [d for d in played.get(team, ()) if d < game_day]
    if not prior:
        return None
    return (game_day - max(prior)).days


def roles(spread_home) -> tuple[str | None, str | None]:
    """(home_role, away_role) from the HOME spread. 0 is a pick'em."""
    if spread_home is None:
        return None, None
    spread = Decimal(str(spread_home))
    if spread < 0:
        return "favorite", "underdog"
    if spread > 0:
        return "underdog", "favorite"
    return "pickem", "pickem"


def grade_ats(home_score, away_score, spread_home) -> tuple[str, str] | None:
    """(home, away). Home covers when (home - away) + home_spread > 0."""
    if home_score is None or away_score is None or spread_home is None:
        return None
    adjusted = (Decimal(str(home_score)) - Decimal(str(away_score))
                + Decimal(str(spread_home)))
    if adjusted > 0:
        return "win", "loss"
    if adjusted < 0:
        return "loss", "win"
    return "push", "push"


def grade_ml(home_score, away_score) -> tuple[str, str] | None:
    if home_score is None or away_score is None:
        return None
    home = Decimal(str(home_score))
    away = Decimal(str(away_score))
    if home > away:
        return "win", "loss"
    if home < away:
        return "loss", "win"
    return "tie", "tie"


def grade_total(home_score, away_score, line) -> tuple[str, str] | None:
    """(over, under)."""
    if home_score is None or away_score is None or line is None:
        return None
    adjusted = (Decimal(str(home_score)) + Decimal(str(away_score))
                - Decimal(str(line)))
    if adjusted > 0:
        return "win", "loss"
    if adjusted < 0:
        return "loss", "win"
    return "push", "push"


def units_1u_to_win(result: str | None, american) -> Decimal | None:
    """Units for a bet sized to win 1. No risk cap.

    win -> +1. push or tie -> 0. loss -> minus the stake that 1 unit of
    win required. A missing or zero price is None, not a made-up number.
    """
    if result is None:
        return None
    if result in ("push", "tie"):
        return Decimal("0")
    if result not in ("win", "loss"):
        return None
    if american is None:
        return None
    price = Decimal(str(american))
    if price == 0:
        return None
    if price > 0:
        decimal_odds = Decimal(1) + price / Decimal(100)
    else:
        decimal_odds = Decimal(1) + (Decimal(100) / abs(price))
    if decimal_odds <= 1:
        return None
    if result == "win":
        return Decimal("1")
    risk = (Decimal(1) / (decimal_odds - 1)).quantize(_Q, rounding=ROUND_HALF_UP)
    return -risk


def same_line(left, right) -> bool:
    if left is None or right is None:
        return False
    return abs(Decimal(str(left)) - Decimal(str(right))) <= _LINE


def quotes_at_lock(quotes, lock_at, point=None,
                   lag_minutes: int = SHOP_LAG_MINUTES) -> list[dict]:
    """Latest quote per (market, book) in [lock - lag, lock] at `point`.

    A quote on a different number does not displace that book's quote on
    DraftKings' number. h2h has no line, so those quotes are not filtered
    by point.
    """
    target = parse_ts(lock_at)
    if target is None:
        return []
    floor = target - timedelta(minutes=lag_minutes)
    latest: dict[tuple, tuple] = {}
    for quote in quotes:
        snap = parse_ts(quote.get("snapshot_at"))
        if snap is None or snap > target or snap < floor:
            continue
        market = quote.get("market")
        if market != "h2h" and not same_line(quote.get("point"), point):
            continue
        key = (market, (quote.get("bookmaker") or "").lower())
        prev = latest.get(key)
        if prev is None or snap > prev[0]:
            latest[key] = (snap, quote)
    return [item[1] for item in latest.values()]


def best_price(quotes, market: str, side: str, dk_point, books: list[str]):
    """(price, book) or (None, None).

    Highest American price on `side` at DraftKings' line. `books` order
    breaks a tie. h2h has no line. Totals use price_home as over and
    price_away as under, which is how nfl_odds_history stores them.
    """
    order = {book: i for i, book in enumerate(books)}
    best = None
    for quote in quotes:
        if quote.get("market") != market:
            continue
        book = (quote.get("bookmaker") or "").lower()
        if book not in order:
            continue
        if market != "h2h" and not same_line(quote.get("point"), dk_point):
            continue
        raw = quote.get("price_home") if side == "home" else quote.get("price_away")
        if raw is None:
            continue
        price = Decimal(str(raw))
        if price == 0:
            continue
        rank = order[book]
        if best is None or price > best[0] or (price == best[0] and rank < best[1]):
            best = (price, rank, book)
    if best is None:
        return None, None
    return best[0], best[2]


def _prefer_history(quotes, market: str) -> tuple[list[dict], str | None]:
    """DraftKings quotes for one market. History wins when it has a lock."""
    history = _priced(quotes, market, "draftkings")
    history = [q for q in history if q.get("line_source") == SOURCE_HISTORY]
    odds = _priced(quotes, market, "draftkings")
    odds = [q for q in odds if q.get("line_source") == SOURCE_ODDS]
    if first_in_window(history, LOCK_WINDOW_HOURS) is not None:
        return history, SOURCE_HISTORY
    if first_in_window(odds, LOCK_WINDOW_HOURS) is not None:
        return odds, SOURCE_ODDS
    return [], None


def _num(value):
    if value is None:
        return None
    return Decimal(str(value))


def shop_rows(canonical_key: str, season: int, week: int, window_hours: int,
              slot: dict | None, quotes_in_shop: list[dict]) -> list[dict]:
    """One stored row per book at this DraftKings snapshot's line.

    Every book is kept, including ones the grade will ignore. The grade
    chooses among them later. h2h has no point.
    """
    if slot is None:
        return []
    market = slot.get("market")
    dk_point = None if market == "h2h" else _num(slot.get("point"))
    rows = []
    for quote in quotes_in_shop:
        book = (quote.get("bookmaker") or "").lower()
        if not book:
            continue
        rows.append({
            "canonical_key": canonical_key,
            "sport": "NFL",
            "season": season,
            "week": week,
            "lock_window_hours": window_hours,
            "market": market,
            "bookmaker": book,
            "line_source": quote.get("line_source") or slot.get("line_source"),
            "snapshot_at": parse_ts(quote.get("snapshot_at")),
            "point": None if market == "h2h" else _num(quote.get("point")),
            "dk_point": dk_point,
            "price_home": _num(quote.get("price_home")),
            "price_away": _num(quote.get("price_away")),
        })
    return rows


def regrade_from_shop(fact: dict, stored: list[dict], books: list[str]) -> dict:
    """Overwrite the grade from shop rows already stored at this DK line.

    Rows at a different number are not the lock that was captured. The
    near window is stored and is not the grade. A market with no stored
    row keeps the grade just computed from the quotes still on hand.
    """
    window = fact["lock_window_hours"]
    sides = {
        "spreads": (
            ("home", "dk_spread_home", "grade_spread_home_price",
             "grade_spread_home_book", "ats_home_result", "ats_home_units"),
            ("away", "dk_spread_home", "grade_spread_away_price",
             "grade_spread_away_book", "ats_away_result", "ats_away_units"),
        ),
        "totals": (
            ("home", "dk_total", "grade_over_price", "grade_over_book",
             "ou_over_result", "ou_over_units"),
            ("away", "dk_total", "grade_under_price", "grade_under_book",
             "ou_under_result", "ou_under_units"),
        ),
        "h2h": (
            ("home", None, "grade_ml_home_price", "grade_ml_home_book",
             "ml_home_result", "ml_home_units"),
            ("away", None, "grade_ml_away_price", "grade_ml_away_book",
             "ml_away_result", "ml_away_units"),
        ),
    }
    for market, pairs in sides.items():
        dk_point = None if market == "h2h" else fact.get(pairs[0][1])
        rows = []
        for row in stored:
            if row.get("lock_window_hours") != window or row.get("market") != market:
                continue
            if market != "h2h" and not same_line(row.get("dk_point"), dk_point):
                continue
            rows.append(row)
        if not rows:
            continue
        for side, _point_col, price_col, book_col, result_col, units_col in pairs:
            price, book = best_price(rows, market, side, dk_point, books)
            fact[price_col] = price
            fact[book_col] = book
            fact[units_col] = units_1u_to_win(fact.get(result_col), price)
    return fact


def shop_markets_to_replace(fresh: list[dict], stored_by_key: dict) -> list[tuple]:
    """Markets whose stored DraftKings line is not the lock being written.

    h2h has no line. Its first capture stays. A spread or total whose
    number moved is replaced, so the stored shop is the lock in the row.
    """
    found = []
    seen = set()
    for row in fresh:
        ident = (row["canonical_key"], row["lock_window_hours"], row["market"])
        if ident in seen or row.get("market") == "h2h":
            continue
        olds = [
            old for old in stored_by_key.get(row["canonical_key"], [])
            if old.get("lock_window_hours") == row["lock_window_hours"]
            and old.get("market") == row["market"]
        ]
        if olds and any(
                not same_line(old.get("dk_point"), row.get("dk_point")) for old in olds):
            seen.add(ident)
            found.append(ident)
    return found


def assemble_game(game: dict, quotes: list[dict], played: dict[str, list[date]],
                  books: list[str]) -> dict | None:
    """One facts dict, or None when this game is not built."""
    fact, _shops = capture_game(game, quotes, played, books)
    return fact


def capture_game(game: dict, quotes: list[dict], played: dict[str, list[date]],
                 books: list[str]) -> tuple[dict | None, list[dict]]:
    """The facts dict and the lock-time shop rows, or (None, []).

    Shop rows are every book at DraftKings' line inside the lag, for the
    grade window and the near window. The fact's grade uses `books`.

    Not built: the id does not parse, the season in the id is before
    DraftKings history, or no DraftKings market has a snapshot inside the
    lock window. A large spread or a short price is not a reason to skip.
    """
    parsed = parse_game_id(game.get("game_id") or "")
    if parsed is None:
        return None, []
    key, season, week, away, home = parsed
    if season < DK_HISTORY_START_SEASON:
        return None, []

    markets = {}
    sources = []
    for market in ("spreads", "totals", "h2h"):
        pool, source = _prefer_history(quotes, market)
        if source is None:
            markets[market] = None
            continue
        sources.append(source)
        markets[market] = {
            "pool": pool,
            "source": source,
            "lock": first_in_window(pool, LOCK_WINDOW_HOURS),
            "near": first_in_window(pool, NEAR_LOCK_WINDOW_HOURS),
            "close": closing_quote(pool),
        }
    if not any(markets[m] and markets[m]["lock"] for m in markets):
        return None, []

    def lock(market):
        slot = markets.get(market)
        return None if slot is None else slot["lock"]

    def near(market):
        slot = markets.get(market)
        return None if slot is None else slot["near"]

    def close(market):
        slot = markets.get(market)
        return None if slot is None else slot["close"]

    spread = lock("spreads")
    total = lock("totals")
    money = lock("h2h")
    near_spread = near("spreads")
    near_total = near("totals")
    near_money = near("h2h")
    close_spread = close("spreads")
    close_total = close("totals")
    close_money = close("h2h")

    def shop(slot):
        if slot is None:
            return []
        source = slot.get("line_source")
        same = [
            q for q in quotes
            if q.get("line_source") == source and q.get("market") == slot.get("market")
        ]
        point = None if slot.get("market") == "h2h" else slot.get("point")
        return quotes_at_lock(same, slot["snapshot_at"], point)

    spread_shop = shop(spread)
    total_shop = shop(total)
    money_shop = shop(money)
    dk_spread = None if spread is None else spread.get("point")
    dk_total = None if total is None else total.get("point")

    g_sh, g_sh_book = best_price(spread_shop, "spreads", "home", dk_spread, books)
    g_sa, g_sa_book = best_price(spread_shop, "spreads", "away", dk_spread, books)
    g_ov, g_ov_book = best_price(total_shop, "totals", "home", dk_total, books)
    g_un, g_un_book = best_price(total_shop, "totals", "away", dk_total, books)
    g_mh, g_mh_book = best_price(money_shop, "h2h", "home", None, books)
    g_ma, g_ma_book = best_price(money_shop, "h2h", "away", None, books)

    home_score = game.get("home_score")
    away_score = game.get("away_score")
    ats = grade_ats(home_score, away_score, dk_spread)
    ml = grade_ml(home_score, away_score)
    ou = grade_total(home_score, away_score, dk_total)
    home_role, away_role = roles(dk_spread)
    game_day = parse_date(game.get("game_date"))
    commence = game.get("commence_time")
    if parse_ts(commence) is None and spread is not None:
        commence = spread.get("commence_time")

    def pair(result, price):
        if result is None:
            return None, None
        return result, units_1u_to_win(result, price)

    ats_h, ats_hu = pair(None if ats is None else ats[0], g_sh)
    ats_a, ats_au = pair(None if ats is None else ats[1], g_sa)
    ml_h, ml_hu = pair(None if ml is None else ml[0], g_mh)
    ml_a, ml_au = pair(None if ml is None else ml[1], g_ma)
    ou_o, ou_ou = pair(None if ou is None else ou[0], g_ov)
    ou_u, ou_uu = pair(None if ou is None else ou[1], g_un)

    fact = {
        "canonical_key": key,
        "sport": "NFL",
        "season": season,
        "week": week,
        "away_team": away,
        "home_team": home,
        "game_date": game_day,
        "commence_time": parse_ts(commence),
        "home_score": _num(home_score),
        "away_score": _num(away_score),
        "lock_window_hours": LOCK_WINDOW_HOURS,
        "near_window_hours": NEAR_LOCK_WINDOW_HOURS,
        "lock_spread_at": None if spread is None else spread["snapshot_at"],
        "lock_spread_lead_hours": None if spread is None else Decimal(str(round(spread["lead_hours"], 4))),
        "dk_spread_home": _num(dk_spread),
        "dk_spread_home_price": None if spread is None else _num(spread.get("price_home")),
        "dk_spread_away_price": None if spread is None else _num(spread.get("price_away")),
        "lock_total_at": None if total is None else total["snapshot_at"],
        "lock_total_lead_hours": None if total is None else Decimal(str(round(total["lead_hours"], 4))),
        "dk_total": _num(dk_total),
        "dk_over_price": None if total is None else _num(total.get("price_home")),
        "dk_under_price": None if total is None else _num(total.get("price_away")),
        "lock_ml_at": None if money is None else money["snapshot_at"],
        "lock_ml_lead_hours": None if money is None else Decimal(str(round(money["lead_hours"], 4))),
        "dk_ml_home_price": None if money is None else _num(money.get("price_home")),
        "dk_ml_away_price": None if money is None else _num(money.get("price_away")),
        "near_spread_at": None if near_spread is None else near_spread["snapshot_at"],
        "near_spread_home": None if near_spread is None else _num(near_spread.get("point")),
        "near_spread_home_price": None if near_spread is None else _num(near_spread.get("price_home")),
        "near_spread_away_price": None if near_spread is None else _num(near_spread.get("price_away")),
        "near_total_at": None if near_total is None else near_total["snapshot_at"],
        "near_total": None if near_total is None else _num(near_total.get("point")),
        "near_over_price": None if near_total is None else _num(near_total.get("price_home")),
        "near_under_price": None if near_total is None else _num(near_total.get("price_away")),
        "near_ml_at": None if near_money is None else near_money["snapshot_at"],
        "near_ml_home_price": None if near_money is None else _num(near_money.get("price_home")),
        "near_ml_away_price": None if near_money is None else _num(near_money.get("price_away")),
        "close_spread_at": None if close_spread is None else close_spread["snapshot_at"],
        "close_spread_home": None if close_spread is None else _num(close_spread.get("point")),
        "close_spread_home_price": None if close_spread is None else _num(close_spread.get("price_home")),
        "close_spread_away_price": None if close_spread is None else _num(close_spread.get("price_away")),
        "close_total_at": None if close_total is None else close_total["snapshot_at"],
        "close_total": None if close_total is None else _num(close_total.get("point")),
        "close_over_price": None if close_total is None else _num(close_total.get("price_home")),
        "close_under_price": None if close_total is None else _num(close_total.get("price_away")),
        "close_ml_at": None if close_money is None else close_money["snapshot_at"],
        "close_ml_home_price": None if close_money is None else _num(close_money.get("price_home")),
        "close_ml_away_price": None if close_money is None else _num(close_money.get("price_away")),
        "grade_spread_home_price": g_sh,
        "grade_spread_home_book": g_sh_book,
        "grade_spread_away_price": g_sa,
        "grade_spread_away_book": g_sa_book,
        "grade_over_price": g_ov,
        "grade_over_book": g_ov_book,
        "grade_under_price": g_un,
        "grade_under_book": g_un_book,
        "grade_ml_home_price": g_mh,
        "grade_ml_home_book": g_mh_book,
        "grade_ml_away_price": g_ma,
        "grade_ml_away_book": g_ma_book,
        "ats_home_result": ats_h,
        "ats_home_units": ats_hu,
        "ats_away_result": ats_a,
        "ats_away_units": ats_au,
        "ml_home_result": ml_h,
        "ml_home_units": ml_hu,
        "ml_away_result": ml_a,
        "ml_away_units": ml_au,
        "ou_over_result": ou_o,
        "ou_over_units": ou_ou,
        "ou_under_result": ou_u,
        "ou_under_units": ou_uu,
        "home_rest_days": rest_days(home, game_day, played),
        "away_rest_days": rest_days(away, game_day, played),
        "is_primetime": is_primetime(commence),
        "home_role": home_role,
        "away_role": away_role,
        "line_source": "+".join(sorted(set(sources))),
    }
    shops = []
    for window, slots in (
        (LOCK_WINDOW_HOURS, (spread, total, money)),
        (NEAR_LOCK_WINDOW_HOURS, (near_spread, near_total, near_money)),
    ):
        for slot in slots:
            shops.extend(shop_rows(key, season, week, window, slot, shop(slot)))
    return fact, shops
