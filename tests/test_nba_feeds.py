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
    (sql, params), = conn.one                         # the ledger row and nothing else:
    assert n == 0                                     # no "gone" rows from an error
    assert nf.FETCHES in sql and params[3] == 403 and params[-1] == "HTTP 403"


def test_a_good_read_writes_changes_latest_and_ledger_in_one_commit():
    conn = _Conn()
    feed = nf.FEEDS["nba_referees"]
    read = nf.Read(200, 10, {"nba:1": {"crew": [["A", 1]]}})
    n = nf.store(conn, feed, "pc", datetime(2026, 11, 27, tzinfo=timezone.utc), read, {})
    assert n == 1 and conn.commits == 1
    assert nf.CHANGES in conn.one[0][0] and nf.LATEST in conn.one[1][0]
    assert nf.FETCHES in conn.one[2][0] and conn.one[2][1][6] == 1    # the ledger's changed count


def test_a_big_first_read_goes_in_batches_not_a_round_trip_a_row():
    conn = _Conn()
    feed = nf.FEEDS["unabated_props"]
    read = nf.Read(200, 10, {f"k{i}": {"v": i} for i in range(1201)})
    nf.store(conn, feed, "pc", datetime(2026, 11, 27, tzinfo=timezone.utc), read, {})
    changes = [sql for sql, _p in conn.one if nf.CHANGES in sql]
    assert len(changes) == 3 and len(conn.one) == 7       # 3 + 3 batches and the ledger row
    assert sum(len(p) for sql, p in conn.one if nf.CHANGES in sql) == 1201 * 6


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


# ---- the market feeds

NOW = datetime(2026, 11, 27, 19, 0, tzinfo=timezone.utc)


def _pin(live=False, start="2026-11-28T02:10:00Z", limit=250, price=-130):
    matchups = [{"id": 10, "type": "special", "isLive": live,
                 "special": {"category": "Player Props", "description": "LeBron James (Points)"},
                 "parent": {"id": 1, "isLive": live, "startTime": start,
                            "participants": [{"alignment": "home", "name": "Phoenix Suns"},
                                             {"alignment": "away", "name": "Dallas Mavericks"}]},
                 "participants": [{"id": 11, "name": "Over"}, {"id": 12, "name": "Under"}]}]
    markets = [{"matchupId": 10, "key": "s;0;ou", "type": "total", "period": 0,
                "limits": [{"amount": limit, "type": "maxRiskStake"}],
                "prices": [{"participantId": 11, "points": 9.5, "price": price},
                           {"participantId": 12, "points": 9.5, "price": -102}]}]
    return matchups, markets


def test_pinnacle_keeps_the_limit_and_names_the_prop():
    item = nf.parse_pinnacle(*_pin(), NOW)["10:s;0;ou"]
    assert item["limit"] == 250 and item["what"] == "LeBron James (Points)"
    assert item["prices"][0] == {"side": "Over", "points": 9.5, "price": -130}
    assert item["home"] == "Phoenix Suns"


def test_a_limit_move_alone_is_a_change():
    a = nf.parse_pinnacle(*_pin(limit=250), NOW)["10:s;0;ou"]
    b = nf.parse_pinnacle(*_pin(limit=500), NOW)["10:s;0;ou"]
    assert nf.state_hash(a) != nf.state_hash(b)


def test_pinnacle_leaves_out_in_play_and_started_games():
    assert nf.parse_pinnacle(*_pin(live=True), NOW) == {}
    assert nf.parse_pinnacle(*_pin(start="2026-11-27T18:00:00Z"), NOW) == {}


def _unabated(price=-175, modified="2026-11-27T05:06:13", start="2026-11-28T02:30:00"):
    return {"marketSources": [{"id": 27, "name": "Bookmaker"}],
            "people": {"42951": {"firstName": "Matisse", "lastName": "Thybulle"}},
            "odds": {"lg3:pt1:pregame": [{
                "personId": 42951, "eventId": 134394, "eventStart": start, "betTypeId": 69,
                "eventName": "LAL @ SAS",
                "sides": {"si1:pid42951": {"ms27": {
                    "points": 1.5, "price": price, "openerPoints": 1.5, "openerPrice": -165,
                    "statusId": 1, "modifiedOn": modified,
                    "alternateLines": [{"points": 0.5, "price": 239}]}}}}]}}


def test_unabated_keeps_the_opener_and_names_source_and_player():
    item = nf.parse_unabated(_unabated(), NOW)["134394:42951:69:si1:ms27"]
    assert (item["source"], item["player"]) == ("Bookmaker", "Matisse Thybulle")
    assert (item["opener_points"], item["opener_price"], item["price"]) == (1.5, -165, -175)
    assert "alternateLines" not in item


def test_unabated_change_is_the_price_not_the_feeds_stamp():
    a = nf.parse_unabated(_unabated(), NOW)["134394:42951:69:si1:ms27"]
    restamp = nf.parse_unabated(_unabated(modified="2026-11-27T06:00:00"), NOW)["134394:42951:69:si1:ms27"]
    moved = nf.parse_unabated(_unabated(price=-180), NOW)["134394:42951:69:si1:ms27"]
    assert nf.state_hash(a) == nf.state_hash(restamp) != nf.state_hash(moved)


def test_unabated_leaves_out_a_started_game():
    assert nf.parse_unabated(_unabated(start="2026-11-27T18:00:00"), NOW) == {}


def _pp(count=0, line=24.5, status="pre_game"):
    return {"included": [{"type": "new_player", "id": "p1",
                          "attributes": {"display_name": "Jalen Brunson", "team": "NYK"}}],
            "data": [{"id": "17", "attributes": {
                "status": status, "stat_type": "Points", "line_score": line, "odds_type": "standard",
                "start_time": "2026-11-27T19:00:00-05:00", "trending_count": count,
                "updated_at": "x"},
                "relationships": {"new_player": {"data": {"type": "new_player", "id": "p1"}}}}]}


def test_prizepicks_a_pick_count_ticking_up_is_not_a_line_change():
    l1, c1 = nf.parse_prizepicks(_pp(count=100))
    l2, c2 = nf.parse_prizepicks(_pp(count=180))
    assert nf.state_hash(l1["17"]) == nf.state_hash(l2["17"])
    assert nf.state_hash(c1["17"]) != nf.state_hash(c2["17"])
    assert l1["17"]["player"] == "Jalen Brunson" and c2["17"]["trending_count"] == 180


def test_prizepicks_no_count_no_popularity_item_and_live_lines_left_out():
    lines, counts = nf.parse_prizepicks(_pp(count=0))
    assert "17" in lines and counts == {}
    assert nf.parse_prizepicks(_pp(status="in_game")) == ({}, {})


def _ud(sport="NBA", payout="1.14"):
    return {"games": [{"id": 5, "sport_id": sport, "abbreviated_title": "PHI @ IND",
                       "scheduled_at": "2026-11-28T00:30:00Z", "status": "scheduled"}],
            "appearances": [{"id": "a1", "match_id": 5, "player_id": "pl"}],
            "players": [{"id": "pl", "first_name": "LeBron", "last_name": "James"}],
            "over_under_lines": [{"id": "L1", "stat_value": "17.5", "line_type": "balanced",
                                  "status": "active", "live_event": False, "updated_at": "t",
                                  "over_under": {"appearance_stat": {"appearance_id": "a1", "stat": "points"}},
                                  "options": [{"choice": "lower", "american_price": "-167",
                                               "decimal_price": "1.6", "payout_multiplier": "0.81"},
                                              {"choice": "higher", "american_price": "+135",
                                               "decimal_price": "2.35", "payout_multiplier": payout}]}]}


def test_underdog_keeps_nba_lines_only_with_each_sides_payout():
    item = nf.parse_underdog_lines(_ud())["L1"]
    assert item["player"] == "LeBron James" and item["line"] == "17.5"
    assert [o["choice"] for o in item["options"]] == ["higher", "lower"]
    assert nf.parse_underdog_lines(_ud(sport="NFL")) == {}
    assert nf.state_hash(item) != nf.state_hash(nf.parse_underdog_lines(_ud(payout="1.20"))["L1"])


def _sl(over=85, status="pre_game", payout="1.72"):
    opt = lambda side, mult: {"outcome": side, "outcome_value": 1.5, "payout_multiplier": mult,
                              "status": "active", "subject_team": "MIA"}
    return [{"sport": "nba", "game_status": status, "game_id": "g", "subject_id": "1081",
             "market_type": "assists_over_under_player_1081", "wager_type": "assists",
             "line_type": "normal", "status": "active", "updated_at": 1,
             "options": [opt("over", payout), opt("under", "1.85")],
             "pick_stats": {"counts": {"over": over, "under": 2, "total": over + 2}}}]


def test_sleeper_lines_and_pick_counts_are_separate_items():
    l1, c1 = nf.parse_sleeper_lines(_sl(over=85))
    l2, c2 = nf.parse_sleeper_lines(_sl(over=120))
    key = "g:assists_over_under_player_1081:normal"
    assert nf.state_hash(l1[key]) == nf.state_hash(l2[key])
    assert c1[key]["over"] == 85 and c2[key]["total"] == 122
    assert nf.state_hash(l1[key]) != nf.state_hash(nf.parse_sleeper_lines(_sl(payout="1.60"))[0][key])
    assert nf.parse_sleeper_lines(_sl(status="in_game")) == ({}, {})


def test_yahoo_keeps_money_and_bets_shares_per_option():
    g = {"gameId": "nba.g.2026112718", "status": "PREGAME", "startTime": "2026-11-27T16:00:00-08:00",
         "homeTeam": {"abbreviation": "NY"}, "awayTeam": {"abbreviation": "MIA"},
         "gameOddsSummary": {"pregameOddsDisplay": "-2.5, O/U 222.5"},
         "gameLineSixPack": [{"type": "OVER_UNDER", "period": "FULL_GAME", "status": "AVAILABLE",
                              "options": [{"name": "Over 222.5", "americanOdds": -108,
                                           "stakePercentage": "78.39", "wagerPercentage": "83.19",
                                           "isCorrect": None}]}]}
    item = nf.parse_yahoo_game(g)
    opt = item["markets"][0]["options"][0]
    assert (opt["money_pct"], opt["bets_pct"], opt["price"]) == ("78.39", "83.19", -108)
    assert item["home"] == "NY" and item["status"] == "PREGAME"


def test_yahoo_has_a_code_for_every_team_and_no_code_twice():
    assert len(nf.YAHOO_TEAM_CODE) == 30 == len(set(nf.YAHOO_TEAM_CODE.values()))
    assert nf.YAHOO_TEAM_CODE["NYK"] == "18"          # nba.g.2026112718 was MIA at NYK


def test_a_yahoo_backfill_refused_part_way_keeps_what_it_read(monkeypatch):
    calls = []

    def fake_date(d, codes):
        calls.append(d)
        if d == date(2026, 10, 22):
            raise ConnectionError("refused")
        return {f"nba.g.{d:%Y%m%d}18": {"game": "x", "markets": []}}, 10, None

    monkeypatch.setattr(nf, "read_yahoo_date", fake_date)
    monkeypatch.setattr(nf, "_home_codes", lambda d: ["18"])
    monkeypatch.setattr(nf, "load_latest", lambda conn, feed: {})
    monkeypatch.setattr(nf.time, "sleep", lambda s: None)
    conn = _Conn()
    res = nf.backfill_yahoo(conn, "pc", date(2026, 10, 20), date(2026, 10, 25))
    assert res["games"] == 2 and res["resume_from"] == "2026-10-22"
    assert calls == [date(2026, 10, 20), date(2026, 10, 21), date(2026, 10, 22)]
    assert conn.commits == 3                              # two stored dates and the failed one's ledger row


def test_the_daily_injury_report_step_asks_for_completed_days_only(monkeypatch):
    import run_pipeline
    from data.ingestors import nba_injury_report
    asked = {}
    monkeypatch.setattr(nba_injury_report, "run_dates",
                        lambda dates, label="run", dedupe=True: asked.update(dates=dates) or {"dates": len(dates)})
    assert run_pipeline.step_nba_injury_report("2026-11-27") is True
    assert asked["dates"] == [date(2026, 11, 24), date(2026, 11, 25), date(2026, 11, 26)]


def test_the_injury_report_step_is_in_the_morning_run_and_callable_by_name():
    import pathlib
    src = pathlib.Path("run_pipeline.py").read_text(encoding="utf-8")
    assert '"nba-injury-report", lambda: step_nba_injury_report(run_date), run_date)' in src
    assert '"nba-injury-report": lambda: step_nba_injury_report(run_date)' in src


def test_a_failing_injury_report_step_reports_false_not_an_exception(monkeypatch):
    import run_pipeline
    from data.ingestors import nba_injury_report

    def boom(*a, **k):
        raise RuntimeError("403")
    monkeypatch.setattr(nba_injury_report, "run_dates", boom)
    assert run_pipeline.step_nba_injury_report("2026-11-27") is False


def test_a_feed_is_due_only_when_its_own_interval_has_passed():
    now = datetime(2026, 11, 27, 19, 0, tzinfo=timezone.utc)                # 2pm ET
    from datetime import timedelta
    feeds = [nf.FEEDS["nba_lineups"], nf.FEEDS["pinnacle_nba"], nf.FEEDS["prizepicks_counts"]]
    last = {"nba_lineups": now - timedelta(seconds=58), "pinnacle_nba": now - timedelta(seconds=120),
            "prizepicks_counts": now - timedelta(minutes=61)}
    assert [f.name for f in nf.due_feeds(feeds, last, now)] == ["nba_lineups", "prizepicks_counts"]
    assert [f.name for f in nf.due_feeds(feeds, {}, now)] == [f.name for f in feeds]   # never read: due


def test_the_worker_runs_the_feeds_every_minute_and_leaves_the_big_file_to_the_pc():
    import inspect
    import scheduler
    src = inspect.getsource(scheduler.run_nba_feeds)
    assert '"--tick"' in src and "NBA_FEEDS_WORKER_SKIP" in src and "timeout=" in src
    assert scheduler.NBA_FEEDS_WORKER_SKIP == "unabated_props"
    whole = inspect.getsource(scheduler)
    assert 'id="nba_feeds"' in whole
    assert scheduler.owns("nba_feeds") or scheduler.SERVICE_ROLE in ("poller", "pollers")
    assert "nba_feeds" in scheduler._PIPELINE_JOBS and "nba_feeds" not in scheduler._POLLER_JOBS
