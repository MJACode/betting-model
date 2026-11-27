"""The public NBA feeds, saved change by change (data/ingestors/nba_feeds.py).

What must hold: a row is written only when what we compare changed; the feed's
own restamp is not a change; a state that comes back is written again; a player
dropped from a five shows; a failed read is never taken for an empty feed.
"""
from datetime import date, datetime, timezone

import pytest

from data.ingestors import nba_feeds as nf


def _player(pid, status="Expected", roster="Active", pos="PG", stamp="2026-11-27T08:32:38"):
    return {"personId": pid, "playerName": f"P{pid}", "lineupStatus": status,
            "rosterStatus": roster, "position": pos, "timestamp": stamp}


def _lineups(players, status=1):
    return {"games": [{"gameId": "0022600064", "gameStatus": status, "gameStatusText": "7:00 pm ET",
                       "homeTeam": {"teamAbbreviation": "NYK", "players": players},
                       "awayTeam": {"teamAbbreviation": "MIA", "players": []}}]}


def test_a_restamp_alone_is_not_a_change():
    first = nf.parse_lineups(_lineups([_player(1)]))
    latest = {k: h for k, _s, h in nf.diff({}, first, True)}
    again = nf.parse_lineups(_lineups([_player(1, stamp="2026-11-27T08:47:39")]))
    assert nf.diff(latest, again, True) == []
    assert again["0022600064:1"]["_feed_stamp"] == "2026-11-27T08:47:39"   # kept, not compared


def test_expected_turning_confirmed_is_a_change_for_the_player_and_the_five():
    first = nf.parse_lineups(_lineups([_player(1)]))
    latest = {k: h for k, _s, h in nf.diff({}, first, True)}
    later = nf.parse_lineups(_lineups([_player(1, status="Confirmed")]))
    changed = {k: s for k, s, _h in nf.diff(latest, later, True)}
    assert changed["0022600064:1"]["lineup"] == "Confirmed"
    assert changed["0022600064:NYK:fives"]["expected"] == []
    assert changed["0022600064:NYK:fives"]["confirmed_starters"] == [[1, "PG"]]


def test_a_player_dropped_from_the_expected_five_shows():
    first = nf.parse_lineups(_lineups([_player(1), _player(2, pos="SG")]))
    latest = {k: h for k, _s, h in nf.diff({}, first, True)}
    later = nf.parse_lineups(_lineups([_player(1)]))
    changed = {k: s for k, s, _h in nf.diff(latest, later, True)}
    assert changed["0022600064:2"] == nf.GONE
    assert changed["0022600064:NYK:fives"]["expected"] == [[1, "PG"]]


def test_inactive_players_are_listed_and_are_not_starters():
    items = nf.parse_lineups(_lineups([_player(1, "Confirmed"), _player(9, "Confirmed", "Inactive", "")]))
    five = items["0022600064:NYK:fives"]
    assert five["inactive"] == [9] and five["confirmed_starters"] == [[1, "PG"]]


def test_a_state_that_comes_back_is_written_again():
    a, b = {"x": {"v": 1}}, {"x": {"v": 2}}
    latest: dict = {}
    seen = []
    for items in (a, b, a):
        ch = nf.diff(latest, items, False)
        seen.append(len(ch))
        latest.update({k: h for k, _s, h in ch})
    assert seen == [1, 1, 1]


def test_gone_is_written_once_and_only_for_a_feed_that_lists_everything():
    latest = {"x": nf.state_hash({"v": 1})}
    assert nf.diff(latest, {}, False) == []
    ch = nf.diff(latest, {}, True)
    assert [(k, s) for k, s, _h in ch] == [("x", nf.GONE)]
    latest["x"] = ch[0][2]
    assert nf.diff(latest, {}, True) == []


def test_referee_crews_and_the_replay_centre():
    payload = {"nba": {"Table": {"rows": [{
        "game_id": "0022600064", "game_date": "11/27/2026", "game_code": "20261127/MIANYK",
        "home_team_abbr": "NYK", "away_team_abbr": "MIA", "official1": "Scott Foster",
        "official1_code": 1162, "official2": "Jacyn Goble", "official2_code": 1627962,
        "official3": "Nate Cearley", "official3_code": 1630879, "official4": None,
        "official4_code": None}]},
        "Table1": {"rows": [{"game_date": "11/27/2026", "replaycenter_official": "Matt Myers"}]}},
        "gl": {"Table": {"rows": []}, "Table1": {"rows": []}},
        "wnba": {"Table": {"rows": [{"game_id": "W1", "official1": "X"}]}, "Table1": {"rows": []}}}
    items = nf.parse_referees(payload)
    assert items["nba:0022600064"]["crew"] == [["Scott Foster", 1162], ["Jacyn Goble", 1627962],
                                               ["Nate Cearley", 1630879]]
    assert items["nba:replay:11/27/2026"]["replay_center"] == ["Matt Myers"]
    assert not any(k.startswith("wnba") for k in items)


def test_an_empty_referee_table_is_no_items():
    empty = {"nba": {"Table": {"rows": []}, "Table1": {"rows": []}}}
    assert nf.parse_referees(empty) == {}


def test_sleeper_week_matches_the_measured_weeks():
    assert nf.sleeper_week(date(2026, 10, 20)) == 1
    assert nf.sleeper_week(date(2026, 10, 25)) == 1
    assert nf.sleeper_week(date(2026, 11, 23)) == 6
    assert nf.sleeper_week(date(2026, 11, 29)) == 6
    assert nf.sleeper_week(date(2026, 11, 30)) == 7


def test_projections_keep_today_on_and_ignore_the_batch_stamp():
    row = {"date": "2026-11-27", "player_id": "1265", "team": "POR", "opponent": "GSW",
           "stats": {"sp": 1620.0, "pts": 12.84}, "updated_at": 1, "company": "rotowire",
           "player": {"first_name": "Jrue", "last_name": "Holiday", "injury_status": None}}
    old = dict(row, date="2026-11-25")
    items = nf.parse_sleeper_projections([row, old], date(2026, 11, 27))
    assert list(items) == ["2026-11-27:1265"]
    restamped = nf.parse_sleeper_projections([dict(row, updated_at=2)], date(2026, 11, 27))
    assert nf.state_hash(items["2026-11-27:1265"]) == nf.state_hash(restamped["2026-11-27:1265"])
    moved = nf.parse_sleeper_projections([dict(row, stats={"sp": 1500.0, "pts": 12.0})], date(2026, 11, 27))
    assert nf.state_hash(items["2026-11-27:1265"]) != nf.state_hash(moved["2026-11-27:1265"])


def test_slate_dates_include_yesterday_before_3am_et():
    late = datetime(2026, 11, 28, 5, 30, tzinfo=timezone.utc)      # 00:30 ET
    assert nf.slate_dates(late) == [date(2026, 11, 27), date(2026, 11, 28)]
    day = datetime(2026, 11, 27, 19, 0, tzinfo=timezone.utc)       # 14:00 ET
    assert nf.slate_dates(day) == [date(2026, 11, 27)]


class _Conn:
    def __init__(self):
        self.many, self.one, self.commits = [], [], 0

    def executemany(self, sql, rows):
        self.many.append((sql, list(rows)))

    def execute(self, sql, params=None):
        self.one.append((sql, params))

    def commit(self):
        self.commits += 1


def test_a_failed_read_writes_its_ledger_row_and_nothing_else():
    conn = _Conn()
    feed = nf.FEEDS["nba_lineups"]
    latest = {"0022600064:1": "h"}
    read = nf.Read(403, 10, {}, error="HTTP 403")
    n = nf.store(conn, feed, "pc", datetime(2026, 11, 27, tzinfo=timezone.utc), read, latest)
    assert n == 0 and conn.many == []                 # no "gone" rows from an error
    (sql, params), = conn.one
    assert nf.FETCHES in sql and params[3] == 403 and params[-1] == "HTTP 403"


def test_a_good_read_writes_changes_latest_and_ledger_in_one_commit():
    conn = _Conn()
    feed = nf.FEEDS["nba_referees"]
    read = nf.Read(200, 10, {"nba:1": {"crew": [["A", 1]]}})
    n = nf.store(conn, feed, "pc", datetime(2026, 11, 27, tzinfo=timezone.utc), read, {})
    assert n == 1 and conn.commits == 1
    assert nf.CHANGES in conn.many[0][0] and nf.LATEST in conn.many[1][0]
    assert conn.one[0][1][6] == 1                     # the ledger's changed count


def test_news_stops_at_the_first_page_holding_a_known_item(monkeypatch):
    pages = {1: {"news_items": [{"id": 3}, {"id": 2}], "meta": {"next": 2}},
             2: {"news_items": [{"id": 1}], "meta": {"next": None}}}
    asked = []

    class _R:
        status_code = 200
        content = b"x"

        def __init__(self, page):
            self._p = page

        def json(self):
            return pages[self._p]

    def fake_get(url, timeout=60, **params):
        asked.append(params["page"])
        return _R(params["page"])

    monkeypatch.setattr(nf, "_get", fake_get)
    monkeypatch.setattr(nf.time, "sleep", lambda s: None)
    assert set(nf.read_news(known={"2"}).items) == {"3", "2"} and asked == [1]
    asked.clear()
    assert set(nf.read_news(known=set()).items) == {"3", "2", "1"} and asked == [1, 2]


def test_one_read_turns_an_exception_into_a_ledger_error(monkeypatch):
    def boom(now=None):
        raise RuntimeError("connection reset")
    feed = nf.Feed("nba_lineups", boom, lambda now: 60, lists_everything=True)
    state = {"nba_lineups": {"k": "h"}}
    res = nf.one_read(None, feed, "pc", measure=state)
    assert res["error"].startswith("RuntimeError") and res["changed"] == 0
    assert state["nba_lineups"] == {"k": "h"}


@pytest.mark.parametrize("name", sorted(nf.FEEDS))
def test_every_feed_names_a_cadence(name):
    assert nf.FEEDS[name].every_sec(datetime(2026, 11, 27, 14, 0, tzinfo=timezone.utc)) >= 60
