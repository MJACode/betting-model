"""The Discord book name opens /pick/<id>. The page is the book picker.
It does not open the Signalbase app. No request leaves the process in these
tests: the database read is replaced.
"""
from __future__ import annotations

import threading

import pytest

from monitoring import server
from tracking.book_slip_links import page_url
from tracking.pick_landing import (
    ALWAYS_ON_PAGE, DEFAULT_ORIGIN, book_rows_for_pick, landing_url,
    page_for_context, parse_pick_path, render_html, render_pick_http,
)
import tracking.pick_landing as landing


DK = "https://sportsbook.draftkings.com/?outcomes=0HC84998421N1950_1"
FD = "https://sportsbook.fanduel.com/addToBetslip?marketId=42.579972737&selectionId=484735"
MGM = ("https://sports.{state}.betmgm.com/en/sports"
       "?options=19976337-1562536174-2307719716&type=Single")
MGM_MA = ("https://www.ma.betmgm.com/en/sportsapp/sports/events/19976337"
          "?options=19976337-1562536174-2307719716&type=Single")


def _pick(**over):
    base = {
        "signal_type": "BET",
        "pick_label": "BOS @ NYK Under 220.5",
        "label": "BOS @ NYK Under 220.5",
        "pick_side": "under",
        "side": "under",
        "scored_line": 220.5,
        "line": 220.5,
        "_market": "totals",
        "dk_odds": -110,
        "dk_bet_link": DK,
        "bet_link": DK,
        "best_book": "fanduel",
        "best_odds": -105,
        "best_bet_link": FD,
        "is_live": False,
    }
    base.update(over)
    return base


def test_an_unposted_pick_is_not_readable_from_the_query():
    """The id is a serial and the page is public. Only a pick Discord has posted."""
    import inspect
    src = inspect.getsource(landing.fetch_pick_context)
    assert "push_sent" in src
    assert "discord_signal" in src and "discord_live" in src
    assert "signal_type = 'BET'" in src


def test_the_landing_url_is_https_on_the_worker():
    assert landing_url(42) == f"{DEFAULT_ORIGIN}/pick/42"
    assert parse_pick_path("/pick/42") == 42
    assert parse_pick_path("/pick/0") is None
    assert parse_pick_path("/pick/42/extra") is None


def test_the_page_lists_books_and_marks_the_best_price():
    rows = book_rows_for_pick(_pick(), [{
        "bookmaker": "betmgm",
        "total_line": 220.5,
        "under_price": -108,
        "under_link": MGM,
        "over_price": -112,
        "over_link": None,
    }, {
        "bookmaker": "pinnacle",
        "total_line": 220.5,
        "under_price": 100,
        "under_link": "https://www.pinnacle.com/bet?outcomes=1",
    }, {
        # A different number is a different bet, so it does not replace FanDuel.
        "bookmaker": "fanduel",
        "total_line": 221.5,
        "under_price": -130,
        "under_link": "https://sportsbook.fanduel.com/addToBetslip?marketId=9&selectionId=9",
    }])
    by_name = {r["name"]: r for r in rows}
    assert by_name["FanDuel"]["is_best"] is True
    assert by_name["FanDuel"]["url"] == FD
    assert by_name["FanDuel"]["price_text"] == "-105"
    assert by_name["BetMGM"]["url"] == MGM_MA
    assert by_name["BetMGM"]["is_best"] is False
    assert "Pinnacle" not in by_name
    assert rows[0]["name"] == "FanDuel"
    assert "selectionId=9" not in by_name["FanDuel"]["url"]
    # The five books are on the page even with no stored price.
    assert {"FanDuel", "DraftKings", "Fanatics", "BetMGM", "Caesars"} <= set(by_name)
    assert by_name["Fanatics"]["price_text"] is None
    assert by_name["Fanatics"]["url"] == page_url("fanatics")
    assert by_name["Caesars"]["price_text"] is None
    assert by_name["Caesars"]["url"] == page_url("williamhill_us")
    priced = [r["name"] for r in rows if r["price_text"]]
    assert priced[0] == "FanDuel"
    assert set(priced) >= {"FanDuel", "DraftKings", "BetMGM"}


def test_the_five_books_are_listed_when_only_draftkings_has_a_price():
    rows = book_rows_for_pick(_pick(best_book=None, best_odds=None, best_bet_link=None))
    assert [r["name"] for r in rows] == [
        "DraftKings", "FanDuel", "Fanatics", "BetMGM", "Caesars",
    ]
    assert rows[0]["is_best"] is True and rows[0]["price_text"] == "-110"
    assert rows[0]["url"] == DK
    for row in rows[1:]:
        assert row["price_text"] is None and row["is_best"] is False
        assert row["url"].startswith("https://")
        assert row["kind"] == "page"
    assert tuple(ALWAYS_ON_PAGE) == (
        "fanduel", "draftkings", "fanatics", "betmgm", "williamhill_us",
    )


def test_a_live_pick_does_not_use_a_pregame_quote():
    rows = book_rows_for_pick(_pick(is_live=True, best_book=None, best_odds=None,
                                    best_bet_link=None), [{
        "bookmaker": "fanduel",
        "total_line": 220.5,
        "under_price": -101,
        "under_link": FD,
    }])
    assert rows[0]["name"] == "DraftKings" and rows[0]["url"] == DK
    assert rows[0]["is_best"] is True
    assert {r["name"] for r in rows} >= {
        "FanDuel", "DraftKings", "Fanatics", "BetMGM", "Caesars",
    }
    assert "fanduel.com/addToBetslip" not in " ".join(r["url"] for r in rows)


def test_a_non_bet_lists_nothing():
    page = page_for_context(7, _pick(signal_type="NONE"))
    assert page["books"] == []
    assert page["label"] is None
    assert page["app_url"] == "signalbase://pick/7"


def test_the_html_does_not_open_the_app_and_escapes_the_label():
    page = page_for_context(42, _pick(pick_label='<script>alert(1)</script> Under'))
    html = render_html(page)
    assert "signalbase://" not in html
    assert "iframe" not in html
    assert "<script" not in html
    assert "window.location" not in html
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert 'class="best"' in html
    # href escaping turns & into &amp;. The selection id is the bet.
    assert "selectionId=484735" in html
    assert "marketId=42.579972737" in html
    assert "model_probability" not in html
    assert "kelly" not in html
    assert ">Best</span>" in html


def test_a_failed_read_does_not_include_the_error(monkeypatch):
    def boom(_pick_id):
        raise RuntimeError("postgres://user:secret@db.example/app")

    monkeypatch.setattr(landing, "fetch_pick_context", boom)
    status, body = render_pick_http(9)
    text = body.decode()
    assert status == 200
    assert "secret" not in text and "postgres" not in text
    assert "signalbase://" not in text
    assert "No sportsbook link" in text


def test_a_missing_pick_does_not_open_the_app(monkeypatch):
    monkeypatch.setattr(landing, "fetch_pick_context", lambda _pick_id: None)
    status, body = render_pick_http(9)
    text = body.decode()
    assert status == 200
    assert "signalbase://" not in text
    assert "No sportsbook link" in text


def test_the_http_route_needs_no_token(monkeypatch):
    monkeypatch.setattr(landing, "fetch_pick_context", lambda pick_id: _pick(pick_id=pick_id))
    srv = server.build_server("127.0.0.1", 0, "s3cret")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        import urllib.error
        import urllib.request
        with urllib.request.urlopen(base + "/pick/42", timeout=5) as resp:
            body = resp.read().decode()
            assert resp.status == 200
            assert "text/html" in resp.headers["Content-Type"]
        assert "signalbase://" not in body
        assert "FanDuel" in body and "DraftKings" in body
        assert "Fanatics" in body and "BetMGM" in body and "Caesars" in body
        assert "Best" in body
        assert "s3cret" not in body
        with pytest.raises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(base + "/api/snapshot", timeout=5)
        assert denied.value.code == 401
    finally:
        srv.shutdown()
