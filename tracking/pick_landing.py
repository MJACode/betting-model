"""The https page a Discord book name opens.

Discord renders a masked link only when the URL is http(s). The book name
stays the link text. The URL is this page (``/pick/<id>`` on the worker that
already serves HTTPS), not one sportsbook.

The page is the book picker. It does not open the Signalbase app. It lists
FanDuel, DraftKings, Fanatics, BetMGM and Caesars on every pick, with a price
when one is stored and the Massachusetts slip when one can be built. A book
with neither gets the sportsbook page ``book_slip_links.page_url`` already
uses (Massachusetts where that page is state-specific). This repo has no
per-sport board URL for a book. Nothing here places a bet, and the HTML
carries no model probability, edge, or stake.

A pick with no id, or an origin that is not an https URL, is not a landing
link. The caller then uses today's direct book link.
"""
from __future__ import annotations

import html
import os
import re
from decimal import Decimal

import config
from tracking.book_slip_links import (
    book_key, page_url, slip_url, _markdown_safe,
    _stored_links,
)

# The worker's public domain (Railway service ``worker``, port 8080). No new
# variable: this is the domain already generated for that service. Set
# PICK_LANDING_ORIGIN to "" to turn the landing link off; a non-https value
# is treated as off.
DEFAULT_ORIGIN = "https://worker-production-229d.up.railway.app"
APP_SCHEME_PREFIX = "signalbase://pick/"

_PICK_PATH = re.compile(r"^/pick/([1-9][0-9]{0,17})$")
# Every landing page names these books, priced or not. Order is the order
# Mike asked for among the rows that have no price. A priced row sorts ahead
# of them; the best price is first.
ALWAYS_ON_PAGE = (
    "fanduel",
    "draftkings",
    "fanatics",
    "betmgm",
    "williamhill_us",
)

_NAME = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betmgm": "BetMGM",
    "williamhill_us": "Caesars",
    "fanatics": "Fanatics",
    "betrivers": "BetRivers",
    "hardrockbet": "Hard Rock Bet",
    "ballybet": "Bally Bet",
    "rebet": "ReBet",
}


def landing_origin() -> str:
    """The https origin of the landing page, or "" when it must not be used."""
    raw = os.environ.get("PICK_LANDING_ORIGIN")
    if raw is None:
        raw = DEFAULT_ORIGIN
    raw = raw.strip().rstrip("/")
    if not raw.lower().startswith("https://"):
        return ""
    if any(ch in raw for ch in " \t\r\n()<>"):
        return ""
    return raw


def pick_id_of(signal: dict | None) -> int | None:
    """A positive integer pick id, or None. Never raises."""
    try:
        if not isinstance(signal, dict):
            return None
        raw = signal.get("pick_id")
        if isinstance(raw, bool) or raw is None:
            return None
        if isinstance(raw, int):
            return raw if raw > 0 else None
        if isinstance(raw, str):
            if not raw.isdigit() or len(raw) > 18 or raw[0] == "0":
                return None
            return int(raw)
        if isinstance(raw, Decimal) and raw == int(raw) and raw > 0:
            return int(raw)
        return None
    except Exception:                                          # noqa: BLE001
        return None


def landing_url(pick_id: int | None) -> str | None:
    origin = landing_origin()
    if not origin or not isinstance(pick_id, int) or pick_id <= 0:
        return None
    url = f"{origin}/pick/{pick_id}"
    if not _markdown_safe(url):
        return None
    return url


def app_open_url(pick_id: int) -> str:
    return f"{APP_SCHEME_PREFIX}{int(pick_id)}"


def discord_book_href(signal: dict | None, book: str | None) -> tuple[str | None, str]:
    """``(url, "landing"|"slip"|"page"|"plain")``. Never raises.

    A pick id and a usable origin win. Otherwise the direct book link.
    """
    try:
        url = landing_url(pick_id_of(signal))
        if url:
            return url, "landing"
        # Looked up on the module so a test can replace it, the same way
        # the notifier used to import the name at call time.
        from tracking import book_slip_links
        return book_slip_links.discord_book_target(signal, book)
    except Exception:                                          # noqa: BLE001
        return None, "plain"


def parse_pick_path(path: str | None) -> int | None:
    match = _PICK_PATH.fullmatch(path or "")
    if not match:
        return None
    return int(match.group(1))


def _decimal(american) -> float | None:
    try:
        a = float(american)
    except (TypeError, ValueError):
        return None
    if a == 0:
        return None
    return 1.0 + (a / 100.0 if a > 0 else 100.0 / abs(a))


def _american(odds) -> str | None:
    dec = _decimal(odds)
    if dec is None:
        return None
    n = int(round(float(odds)))
    if n == 0:
        return None
    return f"+{n}" if n > 0 else str(n)


def _bettable() -> set[str]:
    return {book_key(b) or b for b in config.BEST_LINE_BOOKMAKERS}


def _shop_index(key: str) -> int:
    books = config.BEST_LINE_BOOKMAKERS
    try:
        return list(books).index(key)
    except ValueError:
        return len(books)


def _same_number(scored, offered) -> bool:
    if scored is None or offered is None:
        return False
    try:
        return abs(float(scored) - float(offered)) < 1e-6
    except (TypeError, ValueError):
        return False


def _market_kind(market: str | None) -> str:
    m = (market or "").lower()
    if m.startswith("h2h") or m == "method":
        return "moneyline"
    if "spread" in m:
        return "spread"
    if "total" in m:
        return "total"
    return "other"


def _quote_matches(pick: dict, row: dict, *, prop: bool) -> tuple[object, str | None] | None:
    """``(price, link)`` when ``row`` is this pick's bet, else None."""
    side = (pick.get("pick_side") or pick.get("side") or "").strip().lower()
    market = pick.get("prop_market") if prop else pick.get("_market")
    kind = "total" if prop else _market_kind(market)
    scored = pick.get("scored_line")
    if pick.get("line") is not None and scored is None:
        scored = pick.get("line")
    if kind == "moneyline":
        pass
    elif kind == "spread":
        if not _same_number(scored, row.get("spread_home")):
            return None
    elif kind == "total":
        offered = row.get("line") if prop else row.get("total_line")
        if not _same_number(scored, offered):
            return None
    else:
        return None
    if side == "home":
        return row.get("home_price"), row.get("home_link")
    if side == "away":
        return row.get("away_price"), row.get("away_link")
    if side == "over":
        return row.get("over_price"), row.get("over_link")
    if side == "under":
        return row.get("under_price"), row.get("under_link")
    return None


def _player_in_label(label: str | None, player: str | None) -> bool:
    if not player or not label:
        return False
    def norm(text: str) -> str:
        return re.sub(r"[^a-z0-9]", "", text.lower())
    needle = norm(player)
    return len(needle) >= 3 and needle in norm(label)


def _put(offers: dict, book: str | None, price, link) -> None:
    key = book_key(book)
    if not key or key not in _bettable():
        return
    slot = offers.get(key)
    if slot is None:
        offers[key] = {"price": price, "link": link if isinstance(link, str) else None}
        return
    if price is not None:
        slot["price"] = price
    if isinstance(link, str) and link.strip():
        slot["link"] = link


def _stored_price(pick: dict, key: str):
    best = book_key(pick.get("best_book"))
    decided = book_key(pick.get("decision_book"))
    if key == best and pick.get("best_odds") is not None:
        return pick.get("best_odds")
    if key == "draftkings" and pick.get("dk_odds") is not None:
        return pick.get("dk_odds")
    if key == decided:
        return pick.get("decision_odds") if pick.get("decision_odds") is not None else pick.get("decision_odds_raw")
    if key == "draftkings":
        return pick.get("dk_odds")
    return None


def _always_index(key: str) -> int:
    try:
        return ALWAYS_ON_PAGE.index(key)
    except ValueError:
        return len(ALWAYS_ON_PAGE) + _shop_index(key)


def book_rows_for_pick(pick: dict | None, game_rows=(), prop_rows=()) -> list[dict]:
    """Books for one pick. The best price is first. The five named books are
    always present.

    Each row is ``name``, ``price_text``, ``url``, ``is_best``, ``kind``
    (``slip`` or ``page``). A priced book we can link is included even when it
    is not one of the five. A book among the five with no stored price still
    gets a row: its Massachusetts slip when one can be built, otherwise
    ``page_url``. Current quotes at the pick's number replace the stored
    price and link. A live pick uses only the links stored on the row: a
    pre-game quote is a different bet.

    Which stored link belongs to which book is ``_stored_links`` — a
    DraftKings slip is never listed under FanDuel.
    """
    if not pick or pick.get("signal_type") not in (None, "BET"):
        return []
    offers: dict[str, dict] = {}
    for key in _bettable():
        stored = _stored_links(pick, key)
        if stored or _stored_price(pick, key) is not None:
            _put(offers, key, _stored_price(pick, key), stored[0] if stored else None)
    if not pick.get("is_live"):
        label = pick.get("pick_label") or pick.get("label")
        for row in game_rows or ():
            found = _quote_matches(pick, row, prop=False)
            if not found:
                continue
            _put(offers, row.get("bookmaker"), found[0], found[1])
        for row in prop_rows or ():
            if not _player_in_label(label, row.get("player_name")):
                continue
            found = _quote_matches(pick, row, prop=True)
            if not found:
                continue
            _put(offers, row.get("bookmaker"), found[0], found[1])
    for key in ALWAYS_ON_PAGE:
        offers.setdefault(key, {"price": None, "link": None})

    rows = []
    for key, slot in offers.items():
        url = slip_url(key, slot.get("link"))
        kind = "slip" if url else None
        if not url:
            url = page_url(key)
            kind = "page" if url else None
        if not url:
            continue
        rows.append({
            "key": key,
            "name": _NAME.get(key, key),
            "price": slot.get("price"),
            "price_text": _american(slot.get("price")),
            "url": url,
            "kind": kind,
            "decimal": _decimal(slot.get("price")),
        })
    best_dec = max((r["decimal"] for r in rows if r["decimal"] is not None), default=None)
    for row in rows:
        row["is_best"] = best_dec is not None and row["decimal"] == best_dec
    rows.sort(key=lambda r: (
        0 if r["is_best"] else 1,
        0 if r["decimal"] is not None else 1,
        -(r["decimal"] if r["decimal"] is not None else 0.0),
        _always_index(r["key"]),
    ))
    for row in rows:
        row.pop("decimal", None)
        row.pop("price", None)
        row.pop("key", None)
    return rows


def _market_for(model_id: str | None) -> str | None:
    if not model_id:
        return None
    from tracking.paper_tracker import _market_for_pick
    return _market_for_pick(model_id)


def fetch_pick_context(pick_id: int) -> dict | None:
    """The pick and the current same-game quotes. None when the id is absent.

    The connection is the worker's. A failure raises; the page renderer
    turns that into the empty page and does not include the message.
    """
    from data.db import get_connection
    from tracking.publish_keys import live_lock_key_sql, lock_key_sql
    # The same key the Discord ledger uses. An unposted BET is not on this
    # page: the id is a serial, and the page is public.
    key = (f"CASE WHEN p.is_live THEN {live_lock_key_sql('p')} "
           f"ELSE {lock_key_sql('p')} END")
    conn = get_connection()
    try:
        row = conn.execute(
            f"""
            SELECT p.pick_id, p.pick_label, p.pick_side, p.scored_line, p.model_id,
                   p.game_id, p.dk_odds, p.dk_bet_link, p.best_book, p.best_odds,
                   p.best_bet_link, p.decision_book, p.decision_odds, p.prop_market,
                   p.is_live, p.signal_type
              FROM picks p
             WHERE p.pick_id = %s
               AND p.signal_type = 'BET'
               AND EXISTS (
                    SELECT 1 FROM push_sent s
                     WHERE s.lock_key = {key}
                       AND s.kind IN ('discord_signal', 'discord_live', 'discord_void')
               )
            """,
            (pick_id,),
        ).fetchone()
        if not row:
            return None
        pick = {
            "pick_id": int(row[0]),
            "pick_label": row[1],
            "label": row[1],
            "pick_side": row[2],
            "side": row[2],
            "scored_line": row[3],
            "line": row[3],
            "model_id": row[4],
            "game_id": row[5],
            "dk_odds": row[6],
            "dk_bet_link": row[7],
            "best_book": row[8],
            "best_odds": row[9],
            "best_bet_link": row[10],
            "decision_book": row[11],
            "decision_odds": row[12],
            "prop_market": row[13],
            "is_live": bool(row[14]),
            "signal_type": row[15],
        }
        game_rows: list[dict] = []
        prop_rows: list[dict] = []
        if pick["signal_type"] == "BET" and not pick["is_live"] and pick["game_id"]:
            if pick["prop_market"]:
                found = conn.execute(
                    """
                    SELECT bookmaker, line, over_price, under_price,
                           over_link, under_link, player_name
                      FROM latest_prop_odds
                     WHERE game_id = %s AND market = %s
                    """,
                    (pick["game_id"], pick["prop_market"]),
                ).fetchall()
                prop_rows = [{
                    "bookmaker": r[0], "line": r[1],
                    "over_price": r[2], "under_price": r[3],
                    "over_link": r[4], "under_link": r[5],
                    "player_name": r[6],
                } for r in found]
            else:
                market = _market_for(pick["model_id"])
                pick["_market"] = market
                if market:
                    found = conn.execute(
                        """
                        SELECT bookmaker, home_price, away_price, over_price,
                               under_price, spread_home, total_line,
                               home_link, away_link, over_link, under_link
                          FROM latest_odds
                         WHERE game_id = %s AND market = %s
                           AND bookmaker <> 'sbr_consensus'
                        """,
                        (pick["game_id"], market),
                    ).fetchall()
                    game_rows = [{
                        "bookmaker": r[0],
                        "home_price": r[1], "away_price": r[2],
                        "over_price": r[3], "under_price": r[4],
                        "spread_home": r[5], "total_line": r[6],
                        "home_link": r[7], "away_link": r[8],
                        "over_link": r[9], "under_link": r[10],
                    } for r in found]
        pick["_game_rows"] = game_rows
        pick["_prop_rows"] = prop_rows
        return pick
    finally:
        conn.close()


def _page(pick_id: int, label: str | None, rows: list[dict]) -> dict:
    return {
        "pick_id": pick_id,
        "label": label,
        "app_url": app_open_url(pick_id),
        "books": rows,
    }


def page_for_context(pick_id: int, ctx: dict | None) -> dict:
    """A BET (or a fixture that names no signal type) lists its books.
    Anything else is the empty page: the app link, no label, no slips."""
    if not ctx or ctx.get("signal_type") not in (None, "BET"):
        return _page(pick_id, None, [])
    label = ctx.get("pick_label") or ctx.get("label")
    rows = book_rows_for_pick(ctx, ctx.get("_game_rows") or (), ctx.get("_prop_rows") or ())
    return _page(pick_id, label if isinstance(label, str) else None, rows)


_CSS = """
body{margin:0;background:#F2F2F7;color:#000;font:16px/1.35 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:28rem;margin:0 auto;padding:24px 16px 48px}
.brand{margin:0 0 8px;font-size:13px;letter-spacing:.04em;text-transform:uppercase;color:#3C3C43}
h1{margin:0 0 8px;font-size:22px;line-height:1.25}
.note,.fine{color:#3C3C43;font-size:15px}
ul{list-style:none;margin:16px 0 0;padding:0}
li{margin:0 0 8px}
li a{display:flex;align-items:center;gap:8px;min-height:44px;padding:12px 14px;border-radius:12px;background:#fff;color:#000;text-decoration:none}
li.best a{background:#E8F8EC}
.name{font-weight:600;flex:1}
.tag{font-size:13px;font-weight:600;color:#1A7F37}
.price{font-variant-numeric:tabular-nums}
.empty{padding:12px 14px;background:#fff;border-radius:12px}
""".replace("\n", "")


def render_html(page: dict) -> str:
    """The landing document. It is the book picker. It does not open the app."""
    label = page.get("label")
    title = html.escape(label) if isinstance(label, str) and label.strip() else "This pick"
    items = []
    for row in page.get("books") or []:
        url = row.get("url") or ""
        if not isinstance(url, str) or not url.startswith("https://"):
            continue
        klass = "best" if row.get("is_best") else ""
        tag = '<span class="tag">Best</span>' if row.get("is_best") else ""
        price = html.escape(row["price_text"]) if row.get("price_text") else ""
        price_html = f'<span class="price">{price}</span>' if price else ""
        items.append(
            f'<li class="{klass}"><a href="{html.escape(url, quote=True)}">'
            f'<span class="name">{html.escape(str(row.get("name") or ""))}</span>'
            f"{tag}{price_html}</a></li>"
        )
    books = (
        "<ul>" + "".join(items) + "</ul>"
        if items
        else '<p class="empty">No sportsbook link is available for this pick.</p>'
    )
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<meta name=\"robots\" content=\"noindex\">"
        f"<title>{title} · Signalbase</title><style>{_CSS}</style></head><body><main>"
        "<p class=\"brand\">Signalbase</p>"
        f"<h1>{title}</h1>"
        "<p class=\"note\">Choose a sportsbook. The link opens that book’s bet slip. "
        "It does not place the bet.</p>"
        f"{books}"
        "<p class=\"fine\">The highlighted book has the best price. "
        "A book with no price opens that book’s page. "
        "A book that asks for a state is filled for Massachusetts.</p>"
        "</main></body></html>"
    )


def render_pick_http(pick_id: int) -> tuple[int, bytes]:
    """``(200, html)``. A missing pick and a failed read use the same page."""
    try:
        ctx = fetch_pick_context(pick_id)
        page = page_for_context(pick_id, ctx) if ctx else _page(pick_id, None, [])
    except Exception:                                          # noqa: BLE001
        page = _page(pick_id, None, [])
    body = render_html(page).encode("utf-8")
    return 200, body
