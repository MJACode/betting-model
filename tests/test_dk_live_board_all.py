"""DraftKings' own in-play board for every sport with an in-play model
(data/ingestors/dk_live_board.py; mike, 2026-11-13: "Move everything over to
the fast way").

Pinned here:
  * every league is read: NCAAB, women's college basketball, NBA, NCAAF, NFL;
  * period names per sport: halves for NCAAB, quarters elsewhere, halftime the
    end of the period before it, overtime in no phase, an unknown name None;
  * football: possession, down and distance on our sides, the moneyline, and a
    flipped game turns both over;
  * each sport's names land on OUR team ids: NBA and NFL by DraftKings'
    nickname (every id the games table holds), college football by school
    name with accents folded and four aliases, women's with the [W] tag off;
    a pair that matches two games is refused, a twin row on the next day loses
    to the game's own date;
  * the pacing: a live league every second, an idle one every 30 s, never two
    requests closer than half a second, and a refusal backs the league off.
"""
from __future__ import annotations

import copy

import pytest

from data.ingestors import dk_live_board as B


# A college football board, built from the fields of DraftKings' live read of
# Memphis @ South Florida printed 2026-11-13 05:0x UTC (4th quarter, 0:12 left,
# Memphis 52-41, Memphis ball 3rd and 10): DraftKings lists the away team first.
def football_board():
    ev = {"id": "e1", "name": "Memphis @ South Florida", "status": "STARTED",
          "startEventDate": "2026-11-13T00:30:00.0000000Z",
          "participants": [
              {"name": "South Florida", "venueRole": "Home", "sortOrder": 2,
               "metadata": {"shortName": "USF", "rosettaTeamName": "Bulls"}},
              {"name": "Memphis", "venueRole": "Away", "sortOrder": 1,
               "metadata": {"shortName": "MEM", "rosettaTeamName": "Tigers"}}],
          "liveGameState": {"period": "4th Quarter", "gameTime": 12},
          "eventScorecard": {"mainScorecard": {
              "liveScoreData": {"americanFootballPossession": "Possession [T1]", "americanFootballCurrentDown": "3",
                                "americanFootballYardLine": "58", "americanFootballYardsToGo": "10",
                                "shortName": "USF"},
              "intervalName": "T", "firstTeamScore": "52", "secondTeamScore": "41"}}}
    markets = [{"id": "m1", "eventId": "e1", "name": "Moneyline", "main": True},
               {"id": "m2", "eventId": "e1", "name": "Spread", "main": True},
               {"id": "m3", "eventId": "e1", "name": "Total", "main": True}]
    sels = [{"marketId": "m1", "outcomeType": "Away", "displayOdds": {"american": "−8000"}},
            {"marketId": "m1", "outcomeType": "Home", "displayOdds": {"american": "+4700"}},
            {"marketId": "m2", "outcomeType": "Away", "points": -10.5, "displayOdds": {"american": "−2700"}},
            {"marketId": "m2", "outcomeType": "Home", "points": 10.5, "displayOdds": {"american": "+990"}},
            {"marketId": "m3", "outcomeType": "Over", "points": 93.5, "displayOdds": {"american": "+950"}},
            {"marketId": "m3", "outcomeType": "Under", "points": 93.5, "displayOdds": {"american": "−2400"}}]
    return {"events": [ev], "markets": markets, "selections": sels}


def test_every_sport_with_an_in_play_model_is_read():
    assert B.LEAGUES == {"NCAAB": "92483", "NCAABW": "36647", "NBA": "42648", "NCAAF": "87637", "NFL": "88808"}
    assert set(B.RESOLVERS) == set(B.LEAGUES)


@pytest.mark.parametrize("sport,label,period", [
    ("NCAAB", "1st Half", 1), ("NCAAB", "Halftime", 1), ("NCAAB", "OT", 3),
    ("NBA", "1st Quarter", 1), ("NBA", "Halftime", 2), ("NBA", "4th Quarter", 4), ("NBA", "OT", 5),
    ("NFL", "3rd Quarter", 3), ("NCAABW", "2nd Quarter", 2), ("NCAAF", "Halftime", 2),
    ("NBA", "End of 1st Quarter", None), ("NCAAB", "1st Quarter", None), (None, None, None)])
def test_period_names_per_sport(sport, label, period):
    assert B.period_of(label, sport or "NBA") == period


def test_the_football_board_carries_possession_down_distance_and_the_moneyline():
    ev, = B.parse_board(football_board(), "NCAAF")
    assert (ev.home_name, ev.away_name, ev.home_score, ev.away_score) == ("South Florida", "Memphis", 41, 52)
    assert (ev.period, ev.clock_s) == (4, 12.0)
    assert (ev.possession, ev.down, ev.distance, ev.yardline) == ("away", 3, 10, 58)
    assert (ev.home_ml, ev.away_ml) == (4700.0, -8000.0)
    assert (ev.spread_home, ev.spread_home_price, ev.spread_away_price) == (10.5, 990.0, -2700.0)
    assert (ev.home_nick, ev.away_nick) == ("Bulls", "Tigers")


def test_a_flipped_game_turns_the_moneyline_and_possession_over():
    ev, = B.parse_board(football_board(), "NCAAF")
    r = B.oriented(ev, flipped=True)
    assert (r["home_ml"], r["away_ml"], r["possession"]) == (-8000.0, 4700.0, "home")
    assert (r["home_score"], r["away_score"], r["spread_home"]) == (52, 41, -10.5)


def test_a_moneyline_move_is_a_change_and_the_row_carries_every_column():
    ev, = B.parse_board(football_board(), "NCAAF")
    row = {"sport": "NCAAF", "game_id": "g", "read_at": None, **B.oriented(ev, False)}
    assert set(B.READ_COLS) == set(row)
    moved = {**row, "home_ml": 5000.0}
    assert B.changed(row, moved) and not B.changed(row, dict(row))


# The ids the games table holds, read 2026-11-13 (SELECT DISTINCT home_team ...
# WHERE sport = 'NBA' / 'NFL' AND season >= 2026; 'NaN' dropped).
NBA_IDS = {"ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW", "HOU", "IND", "LAC", "LAL",
           "MEM", "MIA", "MIL", "MIN", "NOP", "NYK", "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR",
           "UTA", "WAS"}
NFL_IDS = {"ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB", "HOU", "IND",
           "JAX", "KC", "LA", "LAC", "LV", "MIA", "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SEA", "SF",
           "TB", "TEN", "WAS"}


def test_every_nickname_lands_on_one_of_our_ids_and_every_id_has_one():
    assert set(B.NBA_NICKNAMES.values()) == NBA_IDS and len(B.NBA_NICKNAMES) == 30
    assert set(B.NFL_NICKNAMES.values()) == NFL_IDS and len(B.NFL_NICKNAMES) == 32


class Conn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        return self

    def fetchall(self):
        return self.rows

    def commit(self):
        pass


def test_nba_resolves_by_nickname_either_way_round(monkeypatch):
    monkeypatch.setattr(B, "_today_et", lambda: "2026-11-13")
    resolve = B.nickname_resolver("NBA")(Conn([("NBA_2026-11-13_NYK_IND", "2026-11-13", "IND", "NYK")]))
    assert resolve("Pacers", "Knicks", "2026-11-14T00:10:00.0000000Z") == ("NBA_2026-11-13_NYK_IND", False)
    assert resolve("Knicks", "Pacers", "2026-11-14T00:10:00.0000000Z") == ("NBA_2026-11-13_NYK_IND", True)
    assert resolve("Pacers", "Celtics", "2026-11-14T00:10:00.0000000Z") is None
    assert resolve("Pacers", "Hoosiers", "2026-11-14T00:10:00.0000000Z") is None


def test_college_football_folds_accents_takes_aliases_and_the_games_own_date(monkeypatch):
    monkeypatch.setattr(B, "_today_et", lambda: "2026-11-14")
    rows = [("NCAAF_2026-11-14_san-jose-state_air-force", "2026-11-14", "Air Force", "San José State"),
            ("NCAAF_2026-11-15_san-jose-state_air-force", "2026-11-15", "Air Force", "San José State"),
            ("NCAAF_2026-11-14_duke_miami", "2026-11-14", "Miami", "Duke"),
            ("NCAAF_2026-11-14_north-dakota-state_hawai-i", "2026-11-14", "Hawai'i", "North Dakota State")]
    resolve = B.ncaaf_resolver(Conn(rows))
    # 7:30 pm ET on the 14th: the twin row on the 15th loses to the game's own date
    assert resolve("Air Force", "San Jose State", "2026-11-15T00:30:00.0000000Z") == \
        ("NCAAF_2026-11-14_san-jose-state_air-force", False)
    assert resolve("Miami FL", "Duke", "2026-11-14T17:00:00.0000000Z") == ("NCAAF_2026-11-14_duke_miami", False)
    assert resolve("Hawaii", "North Dakota State", "2026-11-15T04:00:00Z")[0].endswith("hawai-i")


def test_a_pair_matching_two_games_on_one_date_is_refused():
    games = [("a", "2026-11-14", "UCLA", "USC"), ("b", "2026-11-14", "USC", "UCLA")]
    assert B.pair_match(games, "ucla", "usc", "2026-11-14T20:00:00Z", key=B._fold) is None


def test_womens_names_drop_the_tag(monkeypatch):
    seen = []
    import data.ingestors.ncaabw_teams as W
    monkeypatch.setattr(W, "make_resolver", lambda conn, d: (lambda h, a, s: seen.append((h, a)) or ("g", False)))
    resolve = B.ncaabw_resolver(None)
    assert resolve("Washington [W]", "CSU Bakersfield [W]", "x") == ("g", False)
    assert seen == [("Washington", "CSU Bakersfield")]


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_the_pacer_reads_live_leagues_every_second_idle_ones_every_30_s_and_spaces_requests():
    clock = Clock()
    p = B.Pacer(["NBA", "NCAAB"], poll=1.0, clock=clock)
    sp, wait = p.next()
    assert wait == 0.0
    p.done(sp, {"ok": True, "live": 3})
    other, wait = p.next()
    assert other != sp and wait == pytest.approx(B.MIN_GAP_SEC)     # half a second between any two requests
    clock.t += wait
    p.done(other, {"ok": True, "live": 0})                          # idle: next read in 30 s
    nxt, wait = p.next()
    assert nxt == sp and wait == pytest.approx(1.0 - B.MIN_GAP_SEC)
    assert p.due[other] == pytest.approx(clock.t + B.IDLE_POLL_SEC)


def test_a_refused_league_reads_slower_and_five_in_a_row_back_it_off():
    clock = Clock()
    p = B.Pacer(["NBA"], poll=1.0, clock=clock)

    class Board_:
        refusals = 0
    b = Board_()
    p.done("NBA", {"ok": True, "live": 2}, b)
    p.done("NBA", {"ok": False, "live": 0, "detail": "HTTP 403"}, b)
    assert p.gap["NBA"] == 2.0
    b.refusals = B.REFUSALS_BEFORE_BACKOFF
    p.done("NBA", {"ok": False, "live": 0, "detail": "HTTP 403"}, b)
    assert p.due["NBA"] == pytest.approx(clock.t + B.BACKOFF_SEC) and b.refusals == 0
