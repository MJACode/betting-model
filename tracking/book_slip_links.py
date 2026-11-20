"""The bet-slip URL a Discord pick post opens. Nothing here places a bet.

The app already opens the odds feed's per-outcome link
(``mobile/src/lib/betslipLinks.ts``). ``fillBetslipLink`` substitutes
``{state}``, ``{pickType}`` and ``{wagerAmount}``. ``appClaimedLink`` moves
a BetMGM link onto ``/sportsapp/``, the path its app claims, and keeps the
``options`` query that names the selection. This module does those string
transforms and no others. It does not call a sportsbook, log in, or send a
stake.

Discord gets one URL, not the app's try-the-next-host loop. For BetMGM the
URL is the first alternate ``appClaimedAlternates`` builds
(``www.<state>.betmgm.com``, same path and query). On 2026-11-15 iOS refused
``sports.<state>`` and opened the app with the selection on the slip from
``www.<state>`` (``docs/sessions/2026-11.md``).

The state is Massachusetts. A template is filled with ``ma``. A host this
module already knows (``sports.<xx>.betmgm.com``, ``<xx>.betrivers.com``,
Caesars ``/us/<xx>/``) is rewritten to ``ma``. A FanDuel or DraftKings link
on any other host is not opened: the app refuses those too
(``appClaimedLink``).

A link is a bet slip only when it still carries an outcome id after that
fill (``outcomes``, ``marketId`` / ``selectionId``, ``options``,
``selectionIds``, ``market_selection_id``, ``deep_link_value``, ``coupon``).
Otherwise the post links the book's sportsbook page — the same page
``appClaimedLink`` returns when it holds no link, or ``BOOK_APPS.web`` in
``mobile/src/lib/sportsbookLinks.ts``. The repo has no per-sport board URL
for a book, so that page is the book's sportsbook home (Massachusetts where
the page itself is state-specific). A book with no such page stays plain
text.

Never raises. A bad value is no link.
"""
from __future__ import annotations

import re

# mike bets from Massachusetts. A state-specific slip uses this, not the
# state the feed happened to template.
STATE = "ma"

_PLACEHOLDER = re.compile(r"\{[a-zA-Z]+\}")
_HTTP = re.compile(r"^https://", re.IGNORECASE)
# Outcome id, as the odds feed writes it (betslipLinks.betslipCombineKind
# plus the Hard Rock and BetRivers shapes in scripts/book_app_links_probe.py).
_OUTCOME = re.compile(
    r"(?:^|[?&#])(?:outcomes|selectionIds|selectionId|marketId|options|"
    r"market_selection_id(?:\[\d+\])?|deep_link_value|coupon)=",
    re.IGNORECASE,
)
_MGM_STORED = re.compile(
    r"^(https://sports\.ma\.betmgm\.com/[a-z]{2})/sports(\?.*)?$",
    re.IGNORECASE,
)
_CAESARS_MA = re.compile(r"/us/ma/bet(?:/|$)", re.IGNORECASE)

# Display name, and the feed key, to the one key the app uses.
_KEY = {
    "draftkings": "draftkings", "dk": "draftkings",
    "fanduel": "fanduel", "fd": "fanduel",
    "betmgm": "betmgm", "mgm": "betmgm",
    "williamhill_us": "williamhill_us", "caesars": "williamhill_us",
    "czr": "williamhill_us",
    "espnbet": "espnbet", "espn": "espnbet", "espn bet": "espnbet",
    "betrivers": "betrivers", "br": "betrivers",
    "bovada": "bovada", "bov": "bovada",
    "pinnacle": "pinnacle", "pin": "pinnacle",
    "fanatics": "fanatics",
    "hardrockbet": "hardrockbet", "hard rock bet": "hardrockbet",
    "ballybet": "ballybet", "bally bet": "ballybet",
    "betparx": "betparx",
    "rebet": "rebet",
    "fliff": "fliff",
}

# Hosts the app will open a slip on. A link on any other host for these
# books is a state-specific domain the app does not use.
_HOST = {
    "draftkings": re.compile(r"^sportsbook\.draftkings\.com$"),
    "fanduel": re.compile(r"^sportsbook\.fanduel\.com$"),
    "betmgm": re.compile(r"^(?:www\.ma\.betmgm\.com|sports\.ma\.betmgm\.com)$"),
    "williamhill_us": re.compile(r"^sportsbook\.caesars\.com$"),
    "betrivers": re.compile(r"^ma\.betrivers\.com$"),
    "hardrockbet": re.compile(r"^(?:app|www)\.hardrock\.bet$"),
    "espnbet": re.compile(r"^(?:sportsbook\.thescore\.bet|(?:www\.)?espnbet\.com)$"),
    "fanatics": re.compile(r"^(?:sportsbook\.fanatics\.com|betfanatics\.com)$"),
}

# No betslip link: the page the app opens. BetMGM and Caesars are the
# Massachusetts forms of appClaimedLink(book, null, "ma"), on the host iOS
# took for BetMGM. The rest are BOOK_APPS.web.
_PAGE = {
    "draftkings": "https://sportsbook.draftkings.com/",
    "fanduel": "https://sportsbook.fanduel.com/",
    "betmgm": "https://www.ma.betmgm.com/en/sportsapp/sports",
    "williamhill_us": "https://sportsbook.caesars.com/us/ma/bet/",
    "espnbet": "https://espnbet.com/",
    "bovada": "https://www.bovada.lv/",
    "pinnacle": "https://www.pinnacle.com/",
    "fanatics": "https://sportsbook.fanatics.com/",
    "betrivers": "https://www.betrivers.com/",
    "hardrockbet": "https://www.hardrock.bet/",
    "ballybet": "https://www.ballybet.com/",
    "betparx": "https://www.betparx.com/",
    "rebet": "https://play.rebet.app/",
}


def book_key(name: str | None) -> str | None:
    """Feed key for a published book name. None when the name is unknown."""
    text = (name or "").strip().lower()
    return _KEY.get(text)


def fill_betslip_link(link: str | None, state: str | None) -> str | None:
    """``fillBetslipLink`` in betslipLinks.ts. None when a placeholder remains."""
    if not isinstance(link, str):
        return None
    out = link.strip()
    if not _HTTP.match(out):
        return None
    if "{state}" in out:
        if not state:
            return None
        out = out.replace("{state}", state.lower())
    out = out.replace("{pickType}", "single").replace("{wagerAmount}", "")
    if _PLACEHOLDER.search(out):
        return None
    return out


def _host_of(url: str) -> str:
    found = re.match(r"^https://([^/?#]+)", url, re.IGNORECASE)
    return found.group(1).lower() if found else ""


def _to_ma(url: str) -> str:
    """Known state slots become ``ma``. Anything else is left alone."""
    url = re.sub(
        r"https://sports\.[a-z]{2}\.betmgm\.com",
        "https://sports.ma.betmgm.com",
        url,
        count=1,
        flags=re.IGNORECASE,
    )
    url = re.sub(
        r"https://www\.[a-z]{2}\.betmgm\.com",
        "https://www.ma.betmgm.com",
        url,
        count=1,
        flags=re.IGNORECASE,
    )

    def _rivers(match: re.Match) -> str:
        return "https://ma.betrivers.com"

    url = re.sub(
        r"https://(?!www\.)[a-z]{2}\.betrivers\.com",
        _rivers,
        url,
        count=1,
        flags=re.IGNORECASE,
    )
    url = re.sub(r"/us/[a-z]{2}/", "/us/ma/", url, count=1, flags=re.IGNORECASE)
    return url


def _has_outcome(url: str) -> bool:
    return _OUTCOME.search(url) is not None


def _host_ok(key: str, url: str) -> bool:
    host = _host_of(url)
    if not host or "{" in host:
        return False
    own = _HOST.get(key)
    if own is not None:
        return own.match(host) is not None
    return not any(pat.match(host) for pat in _HOST.values())


def _markdown_safe(url: str) -> bool:
    """A URL Discord can put inside ``](…)`` without the link swallowing the field."""
    if not url.startswith("https://") or len(url) > 900:
        return False
    return not any(ch in url for ch in " \t\r\n()<>")


def _betmgm_slip(filled: str) -> str | None:
    """The app's claimed path, on the host iOS opened the slip from.

    ``appClaimedLink`` rewrites ``/en/sports?options=`` to
    ``/en/sportsapp/sports?options=``. ``appClaimedAlternates`` then offers
    ``www.<state>`` with that same path and query. The query is the bet.
    """
    match = _MGM_STORED.match(filled)
    if not match:
        return None
    query = match.group(2) or ""
    claimed = f"{match.group(1)}/sportsapp/sports{_betmgm_event_path(query)}{query}"
    return claimed.replace("https://sports.ma.betmgm.com/",
                           "https://www.ma.betmgm.com/", 1)


_MGM_ONE_CLASSIC = re.compile(r"[?&]options=(\d+)-\d+-\d+(?:&|$)")


def _betmgm_event_path(query: str) -> str:
    """``betmgmEventPath`` in betslipLinks.ts: ``/events/<fixture>`` for one
    classic ``fixture-market-option`` selection, else "". BetMGM's docs:
    "Add one selection and open the event page". The member lands on the
    game even when the selection does not reach the slip (Matt, 2026-11-20)."""
    found = _MGM_ONE_CLASSIC.search(query)
    return f"/events/{found.group(1)}" if found else ""


def slip_url(key: str, link: str | None) -> str | None:
    """The outcome URL for ``key``, or None. Not a sportsbook home page."""
    filled = fill_betslip_link(link, STATE)
    if not filled:
        return None
    filled = _to_ma(filled)
    if key == "betmgm":
        opened = _betmgm_slip(filled)
        if opened and _has_outcome(opened) and _host_ok(key, opened) and _markdown_safe(opened):
            return opened
        if (_has_outcome(filled) and _host_ok(key, filled)
                and _markdown_safe(filled)):
            return filled
        return None
    if key == "williamhill_us" and not _CAESARS_MA.search(filled):
        return None
    if not _has_outcome(filled) or not _host_ok(key, filled) or not _markdown_safe(filled):
        return None
    return filled


def page_url(key: str | None) -> str | None:
    """The book's sportsbook page, when this book has one in the app."""
    if not key:
        return None
    url = _PAGE.get(key)
    if url and _markdown_safe(url):
        return url
    return None


def _stored_links(signal: dict, key: str) -> list[str]:
    """Links that belong to ``key``. A DraftKings slip is never a FanDuel link."""
    best = book_key(signal.get("best_book"))
    decision = book_key(signal.get("decision_book"))
    own = signal.get("bet_link") or signal.get("dk_bet_link")
    best_link = signal.get("best_bet_link")
    out: list[str] = []
    if key == "draftkings":
        if isinstance(own, str):
            out.append(own)
        if best == "draftkings" and isinstance(best_link, str):
            out.append(best_link)
        return out
    if best == key and isinstance(best_link, str):
        out.append(best_link)
    if decision == key and isinstance(own, str):
        out.append(own)
    return out


def discord_book_target(signal: dict | None, book: str | None) -> tuple[str | None, str]:
    """``(url, "slip"|"page"|"plain")``. Never raises.

    ``slip`` opens that outcome. ``page`` is the book's sportsbook page.
    ``plain`` is no link.
    """
    try:
        key = book_key(book)
        if not key:
            return None, "plain"
        for raw in _stored_links(signal or {}, key):
            url = slip_url(key, raw)
            if url:
                return url, "slip"
        page = page_url(key)
        if page:
            return page, "page"
        return None, "plain"
    except Exception:                                          # noqa: BLE001
        return None, "plain"
