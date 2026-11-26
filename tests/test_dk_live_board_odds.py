"""DraftKings' board lines reach the app (data/ingestors/dk_live_board.py;
mike, 2026-11-25: "just do it").

Pinned here:
  * a read's changed lines become in-play `odds` rows (bookmaker draftkings,
    source dk_live_board), one per market whose number or price moved, each on
    OUR home team's side, none for a market off the board;
  * NCAAF writes none: its live picks are stamped off in-play `odds` rows;
  * a failed odds write costs the reads nothing;
  * NHL and EuroLeague read their league id off DraftKings' sports page by
    name, at most every DISCOVER_RETRY_SEC, and read no board until then;
  * NHL names land on the games table's 32 ids.
"""
from __future__ import annotations

import pandas as pd
import pytest

from data.ingestors import dk_live_board as B


def board(home="Indiana Pacers", away="Boston Celtics", home_nick="Pacers", away_nick="Celtics",
          spread_home=-3.5, home_price="−110", away_price="−110", total=220.5, ml=("−160", "+135"),
          league="42648"):
    ev = {"id": "e1", "name": f"{away} @ {home}", "status": "STARTED", "leagueId": league,
          "startEventDate": "2026-11-25T00:10:00.0000000Z",
          "participants": [
              {"name": home, "venueRole": "Home", "sortOrder": 2, "metadata": {"rosettaTeamName": home_nick}},
              {"name": away, "venueRole": "Away", "sortOrder": 1, "metadata": {"rosettaTeamName": away_nick}}],
          "liveGameState": {"period": "2nd Quarter", "gameTime": 300, "isClockRunning": True},
          "eventScorecard": {"mainScorecard": {"firstTeamScore": "40", "secondTeamScore": "44"}}}
    markets = [{"id": "m1", "eventId": "e1", "name": "Moneyline", "main": True},
               {"id": "m2", "eventId": "e1", "name": "Spread", "main": True},
               {"id": "m3", "eventId": "e1", "name": "Total", "main": True}]
    sels = [{"marketId": "m1", "outcomeType": "Home", "displayOdds": {"american": ml[0]}},
            {"marketId": "m1", "outcomeType": "Away", "displayOdds": {"american": ml[1]}},
            {"marketId": "m2", "outcomeType": "Home", "points": spread_home, "displayOdds": {"american": home_price}},
            {"marketId": "m2", "outcomeType": "Away", "points": -spread_home, "displayOdds": {"american": away_price}},
            {"marketId": "m3", "outcomeType": "Over", "points": total, "displayOdds": {"american": "−112"}},
            {"marketId": "m3", "outcomeType": "Under", "points": total, "displayOdds": {"american": "−108"}}]
    return {"events": [ev], "markets": markets, "selections": sels}


class Resp:
    def __init__(self, code, body=None, text=""):
        self.status_code, self._body, self.text = code, body, text

    def json(self):
        return self._body


class Sess:
    """Answers each URL from `pages` (a list per URL, popped in order)."""

    def __init__(self, pages):
        self.pages, self.urls = pages, []

    def get(self, url, timeout=None):
        self.urls.append(url)
        answers = self.pages.get(url) or self.pages.get("*")
        a = answers.pop(0) if len(answers) > 1 else answers[0]
        return a if isinstance(a, Resp) else Resp(200, a)


class Conn:
    def __init__(self):
        self.reads, self.beats = [], []

    def executemany(self, sql, rows):
        assert "dk_live_reads" in sql
        self.reads.extend(dict(r) for r in rows)

    def execute(self, sql, params=None):
        if "dk_live_feed" in sql:
            self.beats.append(params)
        return self

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def make(sport, pages, *, flipped=False, odds_log=None, clock=None):
    conn, logged = Conn(), []

    def log(c, rows):
        logged.extend(rows)
        return len(rows)
    b = B.Board(sport, lambda: conn, lambda s: Sess(pages),
                lambda c: (lambda home, away, start: ("G1", flipped)),
                odds_log=odds_log or log,
                clock=clock or (lambda: pd.Timestamp("2026-11-25T01:00:00Z")))
    return b, conn, logged


def by_market(rows):
    return {r["market"]: r for r in rows}


def test_the_first_read_of_a_game_writes_its_three_markets():
    b, _conn, logged = make("NBA", {"*": [board()]})
    res = b.read()
    assert res["ok"] and res["written"] == 1 and res["odds"] == 3
    m = by_market(logged)
    assert set(m) == {"spreads", "totals", "h2h"}
    for r in logged:
        assert (r["bookmaker"], r["snapshot_type"], r["source"], r["sport"], r["game_id"]) == \
            ("draftkings", "in_play", "dk_live_board", "NBA", "G1")
        assert r["snapshot_at"].startswith("2026-11-25T01:00:00")
    assert (m["spreads"]["spread_home"], m["spreads"]["home_price"], m["spreads"]["away_price"]) == \
        (-3.5, -110.0, -110.0)
    assert (m["totals"]["total_line"], m["totals"]["over_price"], m["totals"]["under_price"]) == \
        (220.5, -112.0, -108.0)
    assert (m["h2h"]["home_price"], m["h2h"]["away_price"]) == (-160.0, 135.0)


def test_only_a_market_that_moved_is_written_again():
    t = [pd.Timestamp("2026-11-25T01:00:00Z")]
    b, _conn, logged = make("NBA", {"*": [board(), board(), board(home_price="−125", away_price="+105")]},
                            clock=lambda: t[0])
    b.read()
    t[0] += pd.Timedelta(seconds=1)
    assert b.read()["odds"] == 0                     # nothing changed
    t[0] += pd.Timedelta(seconds=1)
    assert b.read()["odds"] == 1
    assert logged[-1]["market"] == "spreads" and logged[-1]["home_price"] == -125.0


def test_a_flipped_game_is_written_on_our_home_teams_side():
    b, _conn, logged = make("NBA", {"*": [board()]}, flipped=True)
    b.read()
    m = by_market(logged)
    assert (m["spreads"]["spread_home"], m["spreads"]["home_price"]) == (3.5, -110.0)
    assert (m["h2h"]["home_price"], m["h2h"]["away_price"]) == (135.0, -160.0)


def test_a_market_off_the_board_writes_no_row():
    body = board()
    body["markets"] = [m for m in body["markets"] if m["name"] != "Total"]
    b, _conn, logged = make("NBA", {"*": [body]})
    b.read()
    assert set(by_market(logged)) == {"spreads", "h2h"}


def test_ncaaf_writes_no_odds_row():
    """ncaaf_live/serve.py stamps each live pick's best price off the newest
    in-play odds row per book; a second DraftKings writer would move it."""
    assert "NCAAF" not in B.ODDS_LOG_SPORTS
    assert "MLB" not in B.ODDS_LOG_SPORTS
    b, conn, logged = make("NCAAF", {"*": [board()]})
    assert b.read()["written"] == 1 and len(conn.reads) == 1
    assert logged == []


def test_a_failed_odds_write_costs_the_reads_nothing():
    def boom(conn, rows):
        raise RuntimeError("odds down")
    b, conn, _logged = make("NBA", {"*": [board()]}, odds_log=boom)
    res = b.read()
    assert res["ok"] and res["written"] == 1 and res["odds"] == 0 and len(conn.reads) == 1


# ─── league ids read off DraftKings' sports page ──────────────────────────────

HOCKEY_PAGE = ('..."eventGroupId":"42133","eventGroupName":"NHL"...'
               '{"name":"KHL","displayGroupId":"6","eventGroupId":"88671"}...')
BASKETBALL_PAGE = ('{"name":"Euroleague","displayGroupId":"4","eventGroupId":"123456"}'
                   '"eventGroupId":"777","eventGroupName":"Euroleague Women"')


def test_a_league_id_is_read_off_the_page_by_its_name():
    assert B.discover_league(HOCKEY_PAGE, "nhl")[0] == "42133"
    lid, near = B.discover_league(BASKETBALL_PAGE, "euroleague")
    assert lid == "123456" and set(near) == {"123456", "777"}
    assert B.discover_league('"eventGroupId":"1","eventGroupName":"Euroleague Women"', "euroleague")[0] is None


def test_two_leagues_of_one_name_are_no_league():
    page = HOCKEY_PAGE + '"eventGroupId":"999","eventGroupName":"N.H.L."'
    assert B.discover_league(page, "nhl")[0] is None


def test_nhl_reads_its_board_at_the_discovered_id(monkeypatch):
    hockey = B.DISCOVER["NHL"][0]
    nhl = board(home="BOS Bruins", away="TOR Maple Leafs", home_nick=None, away_nick=None)
    pages = {hockey: [Resp(200, text=HOCKEY_PAGE)], B.BOARD_URL.format(league="42133"): [nhl]}
    conn, logged = Conn(), []
    sess = Sess(pages)
    b = B.Board("NHL", lambda: conn, lambda s: sess, lambda c: (lambda h, a, s: ("NHL_G", False)),
                odds_log=lambda c, rows: logged.extend(rows) or len(rows),
                clock=lambda: pd.Timestamp("2026-11-25T01:00:00Z"))
    res = b.read()
    assert sess.urls == [hockey, B.BOARD_URL.format(league="42133")]
    assert res["written"] == 1 and len(logged) == 3 and b.league_id == "42133"
    b.read()
    assert sess.urls.count(hockey) == 1                # found once, never asked again


def test_a_league_not_listed_reads_no_board_until_the_retry():
    eu = B.DISCOVER["EUROLEAGUE"][0]
    clock = [1000.0]
    sess = Sess({eu: [Resp(200, text='"eventGroupId":"42648","eventGroupName":"NBA"')]})
    b = B.Board("EUROLEAGUE", lambda: Conn(), lambda s: sess, lambda c: None)
    import data.ingestors.dk_live_board as mod
    real = mod.time.monotonic
    try:
        mod.time.monotonic = lambda: clock[0]
        res = b.read()
        assert res["detail"] == "league not listed" and sess.urls == [eu]
        clock[0] += 60
        b.read()
        assert sess.urls == [eu]                       # not asked again inside the retry
        clock[0] += B.DISCOVER_RETRY_SEC
        b.read()
        assert sess.urls == [eu, eu]
    finally:
        mod.time.monotonic = real


# ─── NHL names onto OUR ids ───────────────────────────────────────────────────

# Every NHL team id the games table held for 2026-10-01 onward (read 2026-11-25).
GAMES_TABLE_NHL_IDS = {
    "ANA", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI", "COL", "DAL", "DET", "EDM", "FLA", "LAK", "MIN", "MTL", "NJD",
    "NSH", "NYI", "NYR", "OTT", "PHI", "PIT", "SEA", "SJS", "STL", "TBL", "TOR", "UTA", "VAN", "VGK", "WPG", "WSH"}


def test_every_nhl_team_has_a_nickname():
    assert set(B.NHL_NICKNAMES.values()) == GAMES_TABLE_NHL_IDS


@pytest.mark.parametrize("name,team", [
    ("Bruins", "BOS"), ("BOS Bruins", "BOS"), ("TOR Maple Leafs", "TOR"), ("Detroit Red Wings", "DET"),
    ("UTA Mammoth", "UTA"), ("Utah Hockey Club", "UTA"), ("LA Kings", "LAK"), ("WPG Jets", "WPG"),
    ("Toronto", None), ("Wings", None), ("", None)])
def test_nhl_names_resolve_by_nickname(name, team):
    assert B.nickname_team(B.NHL_NICKNAMES, name) == team


def test_nba_and_nfl_names_still_resolve_by_nickname():
    assert B.nickname_team(B.NBA_NICKNAMES, "Pacers") == "IND"
    assert B.nickname_team(B.NBA_NICKNAMES, "Indiana Pacers") == "IND"
    assert B.nickname_team(B.NFL_NICKNAMES, "NY Giants") == "NYG"
    assert B.nickname_team(B.NBA_NICKNAMES, "Ducks") is None


def test_every_league_has_a_resolver():
    assert set(B.RESOLVERS) == set(B.LEAGUES)
