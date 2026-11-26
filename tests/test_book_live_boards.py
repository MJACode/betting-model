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
    live game (Dallas @ Utah) and one not started, in the "NBA" competition."""
    ev = {"36341634": {"eventId": 36341634, "name": "Dallas Mavericks @ Utah Jazz", "competitionId": 10547864,
                       "openDate": "2026-11-23T00:11:00.000Z"},
          "36345803": {"eventId": 36345803, "name": "Los Angeles Clippers @ Houston Rockets",
                       "competitionId": 10547864, "openDate": "2026-11-24T01:40:00.000Z"}}
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
    comps = {"10547864": {"competitionId": 10547864, "name": "NBA"},
             "12687908": {"competitionId": 12687908, "name": "eBasketball H2H GG League 4x5 Mins"}}
    return {"attachments": {"events": ev, "markets": markets, "competitions": comps}}


def _add_live_game(page, eid, comp_id, comp_name, away, home):
    """A second live game with all three markets, in its own competition."""
    att = page["attachments"]
    att["competitions"][str(comp_id)] = {"competitionId": comp_id, "name": comp_name}
    att["events"][str(eid)] = {"eventId": eid, "name": f"{away} @ {home}", "competitionId": comp_id,
                               "openDate": "2026-11-25T23:30:00.000Z"}
    m = att["markets"]
    m[f"{eid}a"] = {"eventId": eid, "marketType": "MONEY_LINE", "inPlay": True, "marketStatus": "OPEN",
                    "runners": [_runner("AWAY", away, 150), _runner("HOME", home, -180)]}
    m[f"{eid}b"] = {"eventId": eid, "marketType": "MATCH_HANDICAP_(2-WAY)", "inPlay": True, "marketStatus": "OPEN",
                    "runners": [_runner("AWAY", away, -110, 4.5), _runner("HOME", home, -110, -4.5)]}
    m[f"{eid}c"] = {"eventId": eid, "marketType": "TOTAL_POINTS_(OVER/UNDER)", "inPlay": True,
                    "marketStatus": "OPEN",
                    "runners": [_runner("OVER", "Over", -110, 140.5), _runner("UNDER", "Under", -110, 140.5)]}


def test_fanduel_reads_only_live_main_lines_on_the_books_sides():
    [ev] = L.parse_fanduel(fanduel_page(), "NBA")
    assert (ev.home_name, ev.away_name) == ("Utah Jazz", "Dallas Mavericks")
    assert (ev.spread_home, ev.spread_home_price, ev.spread_away_price) == (7.5, -125.0, -106.0)
    assert (ev.total_line, ev.over_price, ev.under_price) == (230.5, -114.0, -114.0)
    assert (ev.home_ml, ev.away_ml) == (260.0, -360.0)
    assert L.parse_fanduel(fanduel_page(in_play=False), "NBA") == []


def test_two_live_markets_of_one_kind_are_not_taken_and_a_suspended_one_is_none():
    page = fanduel_page()
    page["attachments"]["markets"]["m6"] = copy.deepcopy(page["attachments"]["markets"]["m2"])
    [ev] = L.parse_fanduel(page, "NBA")
    assert ev.spread_home is None and ev.total_line == 230.5
    page = fanduel_page()
    page["attachments"]["markets"]["m3"]["marketStatus"] = "SUSPENDED"
    [ev] = L.parse_fanduel(page, "NBA")
    assert ev.total_line is None and ev.spread_home == 7.5


def test_the_event_name_is_the_fallback_for_the_teams():
    page = fanduel_page()
    m = page["attachments"]["markets"]
    for k in ("m1", "m2"):
        del m[k]
    [ev] = L.parse_fanduel(page, "NBA")
    assert (ev.home_name, ev.away_name) == ("Utah Jazz", "Dallas Mavericks")


def test_only_the_sports_own_competitions_get_lines():
    """FanDuel's NBA page carries eBasketball beside the NBA (2026-11-26: 14
    live eBasketball games, "Miami Heat (UNDERRATED) @ ..."); they are not NBA
    games, and a competition not named for the sport gets no lines."""
    page = fanduel_page()
    _add_live_game(page, 99, 12687908, "eBasketball H2H GG League 4x5 Mins",
                   "Miami Heat (UNDERRATED)", "Toronto Raptors (CYPHER)")
    _add_live_game(page, 98, 55555, "Some League Nobody Named", "A Team", "B Team")
    assert [e.event_id for e in L.parse_fanduel(page, "NBA")] == ["36341634"]
    page["attachments"]["competitions"].pop("10547864")         # the NBA's own name gone
    assert L.parse_fanduel(page, "NBA") == []


def ncaab_page():
    """FanDuel's 'ncaab' page as read 2026-11-26 00:14Z: the men's games and,
    in their own competition, a women's game."""
    page = {"attachments": {"events": {}, "markets": {}, "competitions": {}}}
    _add_live_game(page, 1, 10861937, "NCAA Basketball Mens Games", "Duke", "Connecticut")
    _add_live_game(page, 2, 11844241, "NCAA Basketball Women’s Games", "Oregon State (W)", "Vanderbilt (W)")
    return page


def test_a_womens_game_on_the_mens_page_is_never_a_mens_line():
    """The bug this closes: the men's reader took every live game on the page,
    so 'Oregon State (W) @ Vanderbilt (W)' was handed to the men's resolver."""
    men = L.parse_fanduel(ncaab_page(), "NCAAB")
    assert [(e.away_name, e.home_name) for e in men] == [("Duke", "UConn")]
    women = L.parse_fanduel(ncaab_page(), "NCAABW")
    assert [(e.away_name, e.home_name) for e in women] == [("Oregon State", "Vanderbilt")]
    assert women[0].spread_home == -4.5


def test_the_womens_tag_comes_off_only_a_womens_name():
    assert L.team_name("(12) Vanderbilt (W)", "NCAABW") == "Vanderbilt"
    assert L.team_name("Oregon State (W)", "NCAAB") == "Oregon State (W)"     # never matched as men's
    assert L.team_name("(5) Duke", "NCAAB") == "Duke"
    assert L.team_name("NY Knicks", "NBA") == "NY Knicks"
    assert L.team_name("(9) Connecticut", "NCAAB") == "UConn"
    assert L.team_name("Connecticut (W)", "NCAABW") == "UConn"


def test_fanduel_reads_the_womens_and_euroleague_pages_that_exist():
    """'wncaab' and 'euroleague' answered 404 on 2026-11-26; the women's page
    is 'ncaaw' and EuroLeague is a tab of the basketball page."""
    assert "customPageId=ncaaw" in L._fanduel_url("NCAABW")
    assert "customPageId=ncaab&" in L._fanduel_url("NCAAB")
    assert "page=SPORT&eventTypeId=7522" in L._fanduel_url("EUROLEAGUE")
    for sport in L.FANDUEL_PAGES:
        assert L.FANDUEL_PAGES[sport][1], sport


# ── BetRivers (Kambi) ────────────────────────────────────────────────────────

def _outcome(label, otype, participant, line, american, status="OPEN"):
    o = {"label": label, "type": otype, "participant": participant, "status": status,
         "oddsAmerican": american}
    if line is not None:
        o["line"] = line
    return o


def _offer(label, tags, outcomes):
    return {"criterion": {"label": label}, "tags": tags, "outcomes": outcomes}


def _kambi_event(eid, league, home, away, offers, state="STARTED", sport="basketball"):
    return {"event": {"id": eid, "name": f"{away} @ {home}", "homeName": home, "awayName": away,
                      "start": "2026-11-26T00:42:00Z", "state": state, "group": league.upper(),
                      "path": [{"termKey": sport}, {"termKey": league}]},
            "betOffers": offers, "liveData": {}}


def kambi_list():
    """BetRivers Ohio's live basketball list as read 2026-11-26 01:00Z: one NBA
    game (OKC home, listed as the book lists it, home on OT_ONE), one NCAAB
    game with a lopsided score and no moneyline, one NCAAW game with a ranked
    women's name, and a team total that carries MAIN_LINE too."""
    nba = _kambi_event(1028744802, "nba", "OKC Thunder", "MIN Timberwolves", [
        _offer("Moneyline", ["OFFERED_PREMATCH", "OFFERED_LIVE", "MAIN"],
               [_outcome("OKC Thunder", "OT_ONE", "OKC Thunder", None, "-250"),
                _outcome("MIN Timberwolves", "OT_TWO", "MIN Timberwolves", None, "+200")]),
        _offer("Point Spread", ["OFFERED_PREMATCH", "OFFERED_LIVE", "MAIN_LINE"],
               [_outcome("OKC Thunder", "OT_ONE", "OKC Thunder", -6500, "-112"),
                _outcome("MIN Timberwolves", "OT_TWO", "MIN Timberwolves", 6500, "-108")]),
        _offer("Total Points - Including Overtime", ["OFFERED_PREMATCH", "OFFERED_LIVE", "MAIN_LINE"],
               [_outcome("Over", "OT_OVER", None, 221500, "-110"),
                _outcome("Under", "OT_UNDER", None, 221500, "-110")]),
        _offer("Total Points by OKC Thunder", ["OFFERED_LIVE", "MAIN_LINE"],
               [_outcome("Over", "OT_OVER", None, 114500, "-115"),
                _outcome("Under", "OT_UNDER", None, 114500, "-105")]),
    ])
    ncaab = _kambi_event(1028662139, "ncaab", "Syracuse", "Albany", [
        _offer("Point Spread", ["OFFERED_LIVE", "MAIN_LINE"],
               [_outcome("Syracuse", "OT_ONE", "Syracuse", -22500, "-136"),
                _outcome("Albany", "OT_TWO", "Albany", 22500, "-108")]),
        _offer("Total Points - Including Overtime", ["OFFERED_LIVE", "MAIN_LINE"],
               [_outcome("Over", "OT_OVER", None, 133500, "-115"),
                _outcome("Under", "OT_UNDER", None, 133500, "-127")]),
    ])
    ncaaw = _kambi_event(1030000001, "ncaaw", "(12) Vanderbilt (W)", "Oregon State (W)", [
        _offer("Point Spread", ["OFFERED_LIVE", "MAIN_LINE"],
               [_outcome("(12) Vanderbilt (W)", "OT_ONE", "(12) Vanderbilt (W)", -9500, "-110"),
                _outcome("Oregon State (W)", "OT_TWO", "Oregon State (W)", 9500, "-110")]),
    ])
    return {"events": [nba, ncaab, ncaaw]}


def test_betrivers_reads_main_lines_on_each_teams_own_side():
    [ev] = L.parse_kambi(kambi_list(), "NBA")
    assert (ev.home_name, ev.away_name) == ("OKC Thunder", "MIN Timberwolves")
    assert (ev.home_ml, ev.away_ml) == (-250.0, 200.0)
    assert (ev.spread_home, ev.spread_home_price, ev.spread_away_price) == (-6.5, -112.0, -108.0)
    assert (ev.total_line, ev.over_price, ev.under_price) == (221.5, -110.0, -110.0)   # not the team total


def test_betrivers_keeps_each_league_to_its_own_sport():
    [men] = L.parse_kambi(kambi_list(), "NCAAB")
    assert (men.home_name, men.spread_home, men.total_line, men.home_ml) == ("Syracuse", -22.5, 133.5, None)
    [women] = L.parse_kambi(kambi_list(), "NCAABW")
    assert (women.home_name, women.away_name, women.spread_home) == ("Vanderbilt", "Oregon State", -9.5)
    hockey = {"events": [_kambi_event(1, "ahl", "Hershey Bears", "Wilkes-Barre/Scranton Penguins", [
        _offer("Moneyline - Inc. OT and Shootout", ["OFFERED_LIVE", "MAIN"],
               [_outcome("x", "OT_ONE", "Hershey Bears", None, "-360"),
                _outcome("y", "OT_TWO", "Wilkes-Barre/Scranton Penguins", None, "+215")])], sport="ice_hockey")]}
    assert L.parse_kambi(hockey, "NHL") == []                    # AHL is not the NHL


def test_betrivers_takes_no_suspended_unpriced_or_unnamed_line():
    data = kambi_list()
    offers = data["events"][0]["betOffers"]
    offers[1]["outcomes"][0]["status"] = "SUSPENDED"              # the spread
    offers[2]["outcomes"][1]["oddsAmerican"] = None               # the total
    offers[0]["outcomes"][0]["participant"] = "Someone Else"      # the moneyline
    assert L.parse_kambi(data, "NBA") == []
    data = kambi_list()
    data["events"][0]["event"]["state"] = "NOT_STARTED"
    assert L.parse_kambi(data, "NBA") == []
    data = kambi_list()
    data["events"][0]["betOffers"].append(copy.deepcopy(data["events"][0]["betOffers"][1]))
    [ev] = L.parse_kambi(data, "NBA")
    assert ev.spread_home is None and ev.total_line == 221.5     # two main spreads: neither


BETRIVERS = next(b for b in L.BOOKS if b.key == "betrivers")


def test_one_betrivers_answer_serves_every_basketball_sport():
    """NBA, NCAAB and NCAABW read one list; the book is asked once a pass."""
    conn, logged = Conn(), []
    sess = Sess(lambda url: Resp(200, kambi_list()))
    hits = {"NBA": ("NBA_G1", False), "NCAAB": ("NCAAB_G1", False), "NCAABW": ("NCAABW_G1", False)}
    f = L.BookFeeds(lambda: conn, lambda: ["NBA", "NCAAB", "NCAABW"], session_factory=lambda: sess,
                    resolvers={s: (lambda c, s=s: (lambda h, a, st: hits[s])) for s in hits},
                    odds_log=lambda c, rows: logged.extend(rows) or len(rows),
                    clock=lambda: datetime(2026, 11, 26, 1, 0, tzinfo=timezone.utc))
    f.ready, f.games_live = True, (1e18, set())
    res = {r["sport"]: r for r in f.pass_once() if r["book"] == "betrivers"}
    assert {s: (r["live"], r["matched"]) for s, r in res.items()} == {"NBA": (1, 1), "NCAAB": (1, 1),
                                                                       "NCAABW": (1, 1)}
    assert [h for u, h in zip(sess.urls, sess.headers) if "kambicdn" in u] == [L.KAMBI_HEADERS]
    assert {(r["game_id"], r["bookmaker"], r["source"]) for r in logged} >= {
        ("NBA_G1", "betrivers", "betrivers_board"), ("NCAABW_G1", "betrivers", "betrivers_board")}
    raw = [p for sql, p in conn.sql if "INSERT INTO book_live_raw" in sql and p[1] == "betrivers"]
    assert len(raw) == 1                                          # one answer, stored once


class Resp:
    def __init__(self, code, body=None, text=None):
        import json
        self.status_code = code
        self.text = text if text is not None else (json.dumps(body) if body is not None else "")


class Sess:
    def __init__(self, answers):
        self.answers, self.urls, self.headers = answers, [], []

    def get(self, url, timeout=None, headers=None):
        self.urls.append(url)
        self.headers.append(headers)
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


def test_a_refusal_backs_off_and_three_leave_the_book_alone():
    t = [0.0]
    conn, sess = Conn(), Sess(lambda url: Resp(403, text="<html>Access Denied</html>"))
    f = L.BookFeeds(lambda: conn, lambda: ["NBA"], session_factory=lambda: sess, resolvers={},
                    odds_log=lambda c, r: 0, monotonic=lambda: t[0], sleep=lambda _s: None,
                    clock=lambda: datetime(2026, 11, 26, 1, 0, tzinfo=timezone.utc))
    f.ready, f.games_live = True, (1e18, set())
    gaps = []
    for _ in range(L.REFUSALS_BEFORE_BACKOFF):
        res = [r for r in f.pass_once() if r["book"] == "fanduel"]
        assert res and res[0]["ok"] is False and res[0]["detail"] == "refused"
        gaps.append(f.gap["fanduel"])
        t[0] += 60                                            # past any gap: always due next pass
    assert gaps[:2] == [2 * L.POLL_SEC, 4 * L.POLL_SEC]       # the gap doubles on each refusal
    asked = len([u for u in sess.urls if "fanduel" in u])
    t[0] += 60
    f.pass_once()
    assert len([u for u in sess.urls if "fanduel" in u]) == asked      # benched 10 min after three
    t[0] += L.BACKOFF_SEC
    f.pass_once()
    assert len([u for u in sess.urls if "fanduel" in u]) == asked + 1


def test_one_shared_refusal_counts_once_not_once_per_sport():
    """NBA, NCAAB and NCAABW share BetRivers' one answer: a single refused
    answer is one refusal, so it takes three passes, not one, to back off."""
    t = [0.0]
    conn, sess = Conn(), Sess(lambda url: Resp(429, text="Too Many Requests"))
    f = L.BookFeeds(lambda: conn, lambda: ["NBA", "NCAAB", "NCAABW"], session_factory=lambda: sess,
                    resolvers={}, odds_log=lambda c, r: 0, monotonic=lambda: t[0], sleep=lambda _s: None,
                    clock=lambda: datetime(2026, 11, 26, 1, 0, tzinfo=timezone.utc))
    f.ready, f.games_live = True, (1e18, set())

    def asked():
        return len([u for u in sess.urls if "kambicdn" in u])

    for n in range(1, L.REFUSALS_BEFORE_BACKOFF + 1):
        res = [r for r in f.pass_once() if r["book"] == "betrivers"]
        # all three sports until the third refusal, which backs off at once
        assert [r["detail"] for r in res] == ["refused"] * (3 if n < L.REFUSALS_BEFORE_BACKOFF else 1)
        assert asked() == n                                    # one request a pass
        t[0] += 60
    f.pass_once()
    assert asked() == L.REFUSALS_BEFORE_BACKOFF                # now backed off, all three sports
    t[0] += L.BACKOFF_SEC
    f.pass_once()
    assert asked() == L.REFUSALS_BEFORE_BACKOFF + 1


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


# ─── BetMGM: the right public access id, read off its public page ─────────────
# mike, 2026-11-26: "Get we're just scraping odds data ... let's just do it".

import base64 as _b64  # noqa: E402

BETMGM = next(b for b in L.BOOKS if b.key == "betmgm")
CAESARS = next(b for b in L.BOOKS if b.key == "williamhill_us")
_FRESH = _b64.b64encode(b"11111111-2222-3333-4444-555555555555").decode()
BETMGM_PAGE_HTML = f'<html><script src="/en/app.js"></script>window.cfg={{"accessId":"{_FRESH}"}}</html>'


def _betmgm_answer(url):
    if "betmgm.com/en/sports" in url:
        return Resp(200, text=BETMGM_PAGE_HTML)
    if "/cds-api/bettingoffer/fixtures" in url:
        return Resp(400, text='{"message":"Access id not allowed for application"}')
    return Resp(200, text="")                       # the page's config / js assets


def test_a_wrong_site_access_id_is_dropped_and_the_public_page_gives_the_right_one():
    f, _conn, _logged, sess = feeds(_betmgm_answer)
    res = f.read(BETMGM, "NBA")
    assert res["ok"] is False and res["status"] == 400
    # the id we sent (the first hardcoded one) is marked bad and never offered again
    assert L.BETMGM_ACCESS_IDS[0] in f.betmgm_keys.bad
    # the page was read and the id it ships is now the current one
    assert any("betmgm.com/en/sports" in u for u in sess.urls)
    assert f.betmgm_keys.current() == _FRESH
    # the next url carries the public id read off the page
    assert f._url_for(BETMGM, "NBA") == L._betmgm_url("NBA", _FRESH)


def test_with_no_id_at_all_the_page_is_read_before_any_fixtures_call():
    f, _conn, _logged, sess = feeds(_betmgm_answer)
    f.betmgm_keys = L.BetMGMKeys(())                 # nothing to try
    res = f.read(BETMGM, "NBA")
    assert res["detail"] == "no url"                 # no id, so no fixtures request
    assert not any("/cds-api/" in u for u in sess.urls)
    assert any("/en/sports" in u for u in sess.urls) and f.betmgm_keys.current() == _FRESH


def test_the_page_is_not_re_read_within_the_discover_window():
    f, _conn, _logged, sess = feeds(_betmgm_answer)
    f.read(BETMGM, "NBA")
    pages = sum("/en/sports" in u for u in sess.urls)
    f.read(BETMGM, "NCAAB")                          # the fresh id works now; no new page read
    assert sum("/en/sports" in u for u in sess.urls) == pages


# ─── Caesars: request the way the site's own JS does, then stop ──────────────

def test_caesars_warms_the_site_then_sends_the_browser_xhr_headers():
    def answer(url):
        return Resp(200, text="<html></html>") if url == L.CAESARS_SITE else Resp(200, body={"competitions": []})
    f, _conn, _logged, sess = feeds(answer)
    f.read(CAESARS, "NBA")
    api = next(u for u in sess.urls if "americanwagering.com" in u)
    assert sess.urls.index(L.CAESARS_SITE) < sess.urls.index(api)     # site loaded first, for cookies
    hdr = sess.headers[sess.urls.index(api)]
    assert hdr and hdr.get("Origin") == "https://sportsbook.caesars.com"
    # warmed once only
    f.read(CAESARS, "NCAAB")
    assert sum(u == L.CAESARS_SITE for u in sess.urls) == 1


def test_caesars_still_blocked_stays_refused_with_no_escalation():
    calls = []

    def answer(url):
        calls.append(url)
        return Resp(200, text="<html></html>") if url == L.CAESARS_SITE else Resp(403, text="<html>403 ERROR</html>")
    f, _conn, _logged, sess = feeds(answer)
    res = f.read(CAESARS, "NBA")
    assert res["refused"] is True and res["detail"] == "refused"
    assert sum("americanwagering.com" in u for u in calls) == 1       # one try, no retry to beat the wall


# ─── pacing: as fast as the book allows, never bursting (2026-11-26) ──────────
# mike: "Everything needs to be 1 second or less".

def test_next_book_gap_is_the_floor_until_the_book_pushes_back():
    assert L.next_book_gap(L.POLL_SEC, False) == L.POLL_SEC          # clean read: the 1 s floor
    assert L.next_book_gap(L.POLL_SEC, True) == 2 * L.POLL_SEC       # pushed back: double
    assert L.next_book_gap(2 * L.POLL_SEC, True) == 4 * L.POLL_SEC
    assert L.next_book_gap(L.MAX_POLL_SEC, True) == L.MAX_POLL_SEC   # capped at the ceiling
    assert L.next_book_gap(16.0, True) == min(L.MAX_POLL_SEC, 32.0)
    assert L.next_book_gap(8.0, False) == L.POLL_SEC                 # one clean read returns to the floor


def test_a_clean_read_keeps_the_book_at_the_one_second_floor():
    t = [100.0]
    f, _conn, _logged, _ = feeds(lambda url: Resp(200, fanduel_page()))
    f.monotonic = lambda: t[0]
    f.sleep = lambda _s: None
    f.pass_once()
    assert f.gap["fanduel"] == L.POLL_SEC and L.POLL_SEC <= 1.0
    assert f.due[("fanduel", "NBA")] == t[0] + L.POLL_SEC


def test_no_two_requests_are_closer_than_the_min_gap():
    sleeps = []
    t = [0.0]
    f, _conn, _logged, sess = feeds(lambda url: Resp(200, fanduel_page()), live=("NBA", "NHL"))
    f.monotonic = lambda: t[0]                                       # time does not advance mid-pass
    f.sleep = lambda s: sleeps.append(s)
    f.pass_once()                                                    # FanDuel NBA and NHL are both due
    assert len([u for u in sess.urls if "fanduel" in u]) >= 2        # two real requests
    assert any(abs(s - L.MIN_REQUEST_GAP_SEC) < 1e-9 for s in sleeps)  # spaced by the min gap
