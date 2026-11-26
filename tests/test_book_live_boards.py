"""Every other book's own live page (data/ingestors/book_live_boards.py; mike,
2026-11-25: "yes do it for all books").

Pinned here:
  * FanDuel's league page: only in-play, open main markets; home and away from
    the runners' own result type; the total off the over runner; a kind with
    two live markets on one game is not taken; the event name as a fallback;
  * a read places the game on our row, writes only changed markets, as the
    book's own key with source '<book>_board', turned over when the book lists
    the teams the other way round;
  * NCAAF and MLB are never asked about (their picks are stamped off in-play
    odds rows);
  * a refusal is recorded, never worked around, and three in a row leave the
    book alone for BACKOFF_SEC; a network error never raises;
  * at most CAPTURES_PER_DAY raw answers per book, sport and status a day,
    one an hour; the public web keys never reach the stored URL;
  * the board starts the thread beside itself and restarts on its file.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from data.ingestors import book_live_boards as L
from data.ingestors import dk_live_board as B

ROOT = Path(__file__).resolve().parents[1]


def _runner(side, name, price, handicap=None, status="ACTIVE"):
    r = {"runnerName": name, "result": {"type": side}, "runnerStatus": status,
         "winRunnerOdds": {"americanDisplayOdds": {"americanOdds": price, "americanOddsInt": price}}}
    if handicap is not None:
        r["handicap"] = handicap
    return r


def fanduel_page(in_play=True):
    """The shape of FanDuel's NBA league page captured 2026-11-23 01:17Z: one
    live game (Dallas @ Utah) and one not started."""
    ev = {"36341634": {"eventId": 36341634, "name": "Dallas Mavericks @ Utah Jazz",
                       "openDate": "2026-11-23T00:11:00.000Z"},
          "36345803": {"eventId": 36345803, "name": "Los Angeles Clippers @ Houston Rockets",
                       "openDate": "2026-11-24T01:40:00.000Z"}}
    markets = {
        "m1": {"eventId": 36341634, "marketType": "MONEY_LINE", "inPlay": in_play, "marketStatus": "OPEN",
               "runners": [_runner("AWAY", "Dallas Mavericks", -360), _runner("HOME", "Utah Jazz", 260)]},
        "m2": {"eventId": 36341634, "marketType": "MATCH_HANDICAP_(2-WAY)", "inPlay": in_play,
               "marketStatus": "OPEN",
               "runners": [_runner("AWAY", "Dallas Mavericks", -106, -7.5), _runner("HOME", "Utah Jazz", -125, 7.5)]},
        "m3": {"eventId": 36341634, "marketType": "TOTAL_POINTS_(OVER/UNDER)", "inPlay": in_play,
               "marketStatus": "OPEN",
               "runners": [_runner("OVER", "Over", -114, 230.5), _runner("UNDER", "Under", -114, 230.5)]},
        "m4": {"eventId": 36345803, "marketType": "MONEY_LINE", "inPlay": False, "marketStatus": "OPEN",
               "runners": [_runner("AWAY", "Los Angeles Clippers", 400), _runner("HOME", "Houston Rockets", -550)]},
        "m5": {"eventId": 36341634, "marketType": "NBA_FINALS_WINNER", "inPlay": in_play, "marketStatus": "OPEN",
               "runners": []},
    }
    return {"attachments": {"events": ev, "markets": markets}}


def test_fanduel_reads_only_live_main_lines_on_the_books_sides():
    [ev] = L.parse_fanduel(fanduel_page())
    assert (ev.home_name, ev.away_name) == ("Utah Jazz", "Dallas Mavericks")
    assert (ev.spread_home, ev.spread_home_price, ev.spread_away_price) == (7.5, -125.0, -106.0)
    assert (ev.total_line, ev.over_price, ev.under_price) == (230.5, -114.0, -114.0)
    assert (ev.home_ml, ev.away_ml) == (260.0, -360.0)
    assert L.parse_fanduel(fanduel_page(in_play=False)) == []


def test_two_live_markets_of_one_kind_are_not_taken_and_a_suspended_one_is_none():
    page = fanduel_page()
    page["attachments"]["markets"]["m6"] = copy.deepcopy(page["attachments"]["markets"]["m2"])
    [ev] = L.parse_fanduel(page)
    assert ev.spread_home is None and ev.total_line == 230.5
    page = fanduel_page()
    page["attachments"]["markets"]["m3"]["marketStatus"] = "SUSPENDED"
    [ev] = L.parse_fanduel(page)
    assert ev.total_line is None and ev.spread_home == 7.5


def test_the_event_name_is_the_fallback_for_the_teams():
    page = fanduel_page()
    m = page["attachments"]["markets"]
    for k in ("m1", "m2"):
        del m[k]
    [ev] = L.parse_fanduel(page)
    assert (ev.home_name, ev.away_name) == ("Utah Jazz", "Dallas Mavericks")


class Resp:
    def __init__(self, code, body=None, text=None):
        import json
        self.status_code = code
        self.text = text if text is not None else (json.dumps(body) if body is not None else "")


class Sess:
    def __init__(self, answers):
        self.answers, self.urls = answers, []

    def get(self, url, timeout=None):
        self.urls.append(url)
        a = self.answers(url)
        if isinstance(a, Exception):
            raise a
        return a


class Conn:
    def __init__(self):
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        return self

    def fetchall(self):
        return []

    def commit(self):
        pass

    def close(self):
        pass


def feeds(answers, *, flipped=False, live=("NBA",), clock=None):
    conn, logged, sess = Conn(), [], Sess(answers)
    f = L.BookFeeds(lambda: conn, lambda: list(live), session_factory=lambda: sess,
                    resolvers={"NBA": lambda c: (lambda h, a, s: ("NBA_G1", flipped) if h == "Utah Jazz" else None)},
                    odds_log=lambda c, rows: logged.extend(rows) or len(rows),
                    clock=clock or (lambda: datetime(2026, 11, 26, 1, 0, tzinfo=timezone.utc)))
    f.ready = True                       # tables exist
    f.games_live = (1e18, set())         # no schedule read in a test
    return f, conn, logged, sess


FANDUEL = next(b for b in L.BOOKS if b.key == "fanduel")


def test_a_read_writes_the_books_changed_lines_on_our_row():
    f, conn, logged, _ = feeds(lambda url: Resp(200, fanduel_page()))
    res = f.read(FANDUEL, "NBA")
    assert (res["ok"], res["live"], res["matched"], res["written"]) == (True, 1, 1, 3)
    for r in logged:
        assert (r["bookmaker"], r["source"], r["snapshot_type"], r["game_id"]) == \
            ("fanduel", "fanduel_board", "in_play", "NBA_G1")
    by = {r["market"]: r for r in logged}
    assert (by["spreads"]["spread_home"], by["spreads"]["home_price"]) == (7.5, -125.0)
    assert f.read(FANDUEL, "NBA")["written"] == 0          # nothing moved
    assert any("book_live_feed" in sql for sql, _ in conn.sql)


def test_a_flipped_game_is_written_on_our_home_teams_side():
    f, _conn, logged, _ = feeds(lambda url: Resp(200, fanduel_page()), flipped=True)
    f.read(FANDUEL, "NBA")
    by = {r["market"]: r for r in logged}
    assert (by["spreads"]["spread_home"], by["spreads"]["home_price"]) == (-7.5, -106.0)
    assert (by["h2h"]["home_price"], by["h2h"]["away_price"]) == (-360.0, 260.0)


def test_ncaaf_and_mlb_are_never_asked_about():
    assert "NCAAF" not in L.LIVE_SPORTS and "MLB" not in L.LIVE_SPORTS
    assert set(L.LIVE_SPORTS) <= set(B.ODDS_LOG_SPORTS)
    for b in L.BOOKS:
        assert not ({"NCAAF", "MLB"} & set(b.sports)), b.key


def test_a_refusal_is_recorded_and_three_leave_the_book_alone():
    t = [0.0]
    conn, sess = Conn(), Sess(lambda url: Resp(403, text="<html>Access Denied</html>"))
    f = L.BookFeeds(lambda: conn, lambda: ["NBA"], session_factory=lambda: sess, resolvers={},
                    odds_log=lambda c, r: 0, monotonic=lambda: t[0],
                    clock=lambda: datetime(2026, 11, 26, 1, 0, tzinfo=timezone.utc))
    f.ready, f.games_live = True, (1e18, set())
    for _ in range(L.REFUSALS_BEFORE_BACKOFF):
        res = [r for r in f.pass_once() if r["book"] == "fanduel"]
        assert res and res[0]["ok"] is False and res[0]["detail"] == "refused"
        t[0] += L.POLL_SEC
    asked = len([u for u in sess.urls if "fanduel" in u])
    t[0] += L.POLL_SEC
    f.pass_once()
    assert len([u for u in sess.urls if "fanduel" in u]) == asked      # backed off
    t[0] += L.BACKOFF_SEC
    f.pass_once()
    assert len([u for u in sess.urls if "fanduel" in u]) == asked + 1


def test_a_network_error_never_raises():
    f, _conn, _logged, _ = feeds(lambda url: ConnectionError("reset"))
    res = f.read(FANDUEL, "NBA")
    assert res["ok"] is False and "ConnectionError" in res["detail"]


def test_a_captured_book_stores_its_answer_and_parses_nothing():
    betmgm = next(b for b in L.BOOKS if b.key == "betmgm")
    assert betmgm.parse is None
    f, conn, logged, _ = feeds(lambda url: Resp(200, {"fixtures": []}))
    res = f.read(betmgm, "NBA")
    assert res["ok"] and logged == []
    raw = [p for sql, p in conn.sql if "INSERT INTO book_live_raw" in sql]
    assert raw and raw[0][1] == "betmgm" and "accessid" not in raw[0][3]


def test_captures_are_a_few_a_day_one_an_hour():
    c = L.Captures(per_day=3)
    t0 = datetime(2026, 11, 26, 0, 30, tzinfo=timezone.utc)
    assert c.want("fanduel", "NBA", 200, t0)
    assert not c.want("fanduel", "NBA", 200, t0 + timedelta(minutes=30))
    assert c.want("fanduel", "NBA", 403, t0 + timedelta(minutes=30))      # another status
    assert c.want("fanduel", "NBA", 200, t0 + timedelta(hours=1))
    assert c.want("fanduel", "NBA", 200, t0 + timedelta(hours=2))
    assert not c.want("fanduel", "NBA", 200, t0 + timedelta(hours=3))      # three today


def test_the_stored_url_carries_no_web_key():
    for b in L.BOOKS:
        url = b.url("NBA")
        if url:
            s = L.stored_url(url)
            assert "_ak=" not in s and "accessid" not in s, s


def test_the_board_starts_the_thread_and_restarts_on_its_file():
    src = (ROOT / "data" / "ingestors" / "dk_live_board.py").read_text(encoding="utf-8")
    assert "start_in_background(get_connection" in src
    assert "data/ingestors/book_live_boards.py" in B.FEED_FILES
    main = src[src.index("def main("):]
    assert main.index("if not a.dry_run:\n        # Every other book") < main.index("while end is None")
