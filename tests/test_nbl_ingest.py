"""NBL groundwork: identity, ESPN's results parser, the odds resolver, the
history purchase and the forward capture (data/ingestors/nbl_*.py,
scripts/nbl_odds_capture.py, scripts/nbl_dk_probe.py)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import config
from data import prune_odds
from data.ingestors import nbl_espn as ne
from data.ingestors import nbl_odds_history as nh
from data.ingestors import nbl_teams as nt
from data.ingestors import odds_ingestor as oi

NOW = datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)


# ── identity ─────────────────────────────────────────────────────────────────

def test_game_id_is_espns_event_id():
    assert nt.build_game_id(401875310) == "NBL_401875310"
    with pytest.raises(ValueError):
        nt.build_game_id("2026-11-13_NZL_BRI")


def test_every_feed_name_in_the_census_maps_to_a_club():
    nt.reset_registry_cache()
    for name, code in config.NBL_ODDS_API_MAP.items():
        assert nt.resolve_team_name(name) == code
    # the one name the feed spells differently from ESPN
    assert nt.resolve_team_name("S.E. Melbourne Phoenix") == "PNX"
    assert len(set(config.NBL_ODDS_API_MAP.values())) == 10


def test_a_name_off_the_map_resolves_only_on_an_exact_stored_name():
    nt.reset_registry_cache()
    reg = [{"code": "MEL", "name": "Melbourne United", "names": []},
           {"code": "PNX", "name": "South East Melbourne Phoenix", "names": []}]
    assert nt.resolve_team_name("Melbourne", reg) is None      # two Melbourne clubs
    assert nt.resolve_team_name("Shanghai Sharks", reg) is None


GAMES = [
    {"game_id": "NBL_401875298", "home_code": "SYD", "away_code": "NZL",
     "commence_time": "2026-11-15T04:00:00+00:00", "game_date": "2026-11-15"},
    {"game_id": "NBL_401875400", "home_code": "NZL", "away_code": "SYD",
     "commence_time": "2026-11-17T06:30:00+00:00", "game_date": "2026-11-17"},
]


def test_match_event_places_the_nearest_meeting_and_says_when_flipped():
    assert nt.match_event(GAMES, "SYD", "NZL", "2026-11-15T04:00:00Z") == ("NBL_401875298", False)
    # the feed calling ESPN's away club home is flagged, so the caller swaps
    assert nt.match_event(GAMES, "NZL", "SYD", "2026-11-15T04:10:00Z") == ("NBL_401875298", True)
    # two days later is the other meeting, not this one
    assert nt.match_event(GAMES, "NZL", "SYD", "2026-11-17T06:30:00Z") == ("NBL_401875400", False)
    assert nt.match_event(GAMES, "SYD", "NZL", "2026-11-20T04:00:00Z") is None


# ── the odds feed ────────────────────────────────────────────────────────────

def test_the_odds_ingestor_never_mints_an_nbl_game_and_skips_the_draftkings_gate():
    assert oi.SPORT_KEYS["NBL"] == "basketball_nbl"
    assert "NBL" in oi.RESOLVE_ONLY_SPORTS
    assert "NBL" in oi.SCHEDULE_RESOLVED_SPORTS
    assert "NBL" in oi.DK_GATE_EXEMPT_SPORTS
    ev = [{"id": "x", "commence_time": "2026-11-15T04:00:00Z", "home_team": "Sydney Kings",
           "away_team": "New Zealand Breakers", "bookmakers": []}]
    games, rows = oi._process_events(ev, "NBL", "open", "2026-11-14T15:00:00Z")
    assert games == [] and rows == []


def test_the_live_pull_asks_twenty_books_in_two_regions():
    books = oi.sport_bookmakers_param("NBL").split(",")
    assert len(books) == len(set(books)) == 20
    assert "betrivers" in books and "pinnacle" in books and "betfair_ex_au" in books


def test_the_season_label_is_the_ending_year():
    assert oi._season_label("NBL", "2026-11-14") == 2027
    assert oi._season_label("NBL", "2027-02-14") == 2027
    assert nt.season_label_for_date("2026-09-19") == 2027


def _spread_event(home, away, home_point):
    return [{"id": "x", "commence_time": "2026-11-15T04:00:00Z",
             "home_team": home, "away_team": away,
             "bookmakers": [{"key": "betrivers", "last_update": "2026-11-14T15:00:00Z",
                             "markets": [{"key": "spreads", "last_update": "2026-11-14T15:00:00Z",
                                          "outcomes": [
                                              {"name": home, "price": -117, "point": home_point},
                                              {"name": away, "price": -107,
                                               "point": -home_point}]}]}]}]


def test_a_flipped_event_stores_the_home_clubs_spread():
    resolver = nt.Resolver([], GAMES)
    # the feed lists ESPN's away club (NZL) as home at +9.5
    ev = _spread_event("New Zealand Breakers", "Sydney Kings", 9.5)
    games, rows = oi._process_events(ev, "NBL", "open", "2026-11-14T15:05:00Z",
                                     resolve_game_id=resolver)
    assert games == []
    (row,) = rows
    assert row["game_id"] == "NBL_401875298"
    assert float(row["spread_home"]) == -9.5            # SYD, ESPN's home club


def test_the_cleanup_protects_the_bought_sources_and_keeps_the_path():
    assert nh.PREGAME_SOURCE in prune_odds.PROTECTED_SOURCES
    assert nh.INPLAY_SOURCE in prune_odds.PROTECTED_SOURCES
    assert "NBL" in prune_odds.PATH_KEPT_SPORTS


def test_the_history_names_ten_books_so_it_bills_one_region():
    p = nh._params(NOW)
    books = p["bookmakers"].split(",")
    assert books == config.NBL_HISTORY_BOOKMAKERS and len(set(books)) == 10
    assert books[0] == "betrivers"
    assert nh.SNAPSHOT_COST == 30
    assert nh.FIRST_HISTORY_DAY.isoformat() == "2024-09-24"


def test_the_history_spends_nothing_before_the_feeds_first_snapshot():
    games = [{"season": 2025, "game_date": "2024-09-19"}, {"season": 2025, "game_date": "2025-03-23"}]
    days = nh.season_days(games, NOW)[2025]
    assert days[0].isoformat() == "2024-09-24"
    assert days[-1].isoformat() == "2025-03-24"


def test_every_nbl_dense_window_stays_inside_its_utc_day():
    # the latest stored tip of 2025-26 is 11:30 UTC; the window ends 2.5 h later
    tip = datetime(2026, 1, 10, 11, 30, tzinfo=timezone.utc)
    assert (tip + nh.DENSE_AFTER).date() == tip.date()
    assert (datetime(2026, 1, 10, 2, 0, tzinfo=timezone.utc) - nh.DENSE_BEFORE).date() == tip.date()


# ── ESPN's results ───────────────────────────────────────────────────────────

def _event(**kw):
    e = {"id": "401875310", "date": "2026-11-13T06:30Z",
         "season": {"year": 2027, "slug": "regular-season"},
         "status": {"type": {"name": "STATUS_FINAL"}},
         "competitions": [{"neutralSite": False, "venue": {"fullName": "Spark Arena",
                                                           "address": {"city": "Auckland"}},
                           "competitors": [
             {"homeAway": "home", "score": "94",
              "team": {"id": "6", "abbreviation": "NZL", "displayName": "New Zealand Breakers"},
              "linescores": [{"value": v} for v in (14, 26, 20, 19, 15)]},
             {"homeAway": "away", "score": "90",
              "team": {"id": "2", "abbreviation": "BRI", "displayName": "Brisbane Bullets"},
              "linescores": [{"value": v} for v in (24, 16, 22, 17, 11)]}]}]}
    for k, v in kw.items():
        e[k] = v
    return e


def test_parse_event_reads_quarters_overtime_and_espns_label():
    r = ne.parse_event(_event())
    assert r["game_id"] == "NBL_401875310" and r["season"] == 2027
    assert (r["home_code"], r["away_code"]) == ("NZL", "BRI")
    assert (r["home_score"], r["away_score"]) == (94, 90)
    assert r["periods"][-1] == (5, 15, 11)
    assert r["game_date"] == "2026-11-13"
    assert ne.results(r) == (1, 1, 1)          # home win, overtime, tied after forty


def test_parse_event_refuses_periods_that_do_not_sum_and_a_wrong_label():
    bad = _event()
    bad["competitions"][0]["competitors"][0]["score"] = "95"
    with pytest.raises(ValueError):
        ne.parse_event(bad)
    with pytest.raises(ValueError):
        ne.parse_event(_event(season={"year": 2026, "slug": "regular-season"}))


def test_only_league_games_that_are_final_live_or_ahead_reach_games():
    final = ne.parse_event(_event())
    assert ne.is_league_game(final, NOW)
    pre = ne.parse_event(_event(season={"year": 2027, "slug": "preseason"}))
    assert not ne.is_league_game(pre, NOW)
    stale = ne.parse_event(_event(date="2022-12-16T08:30Z",
                                  season={"year": 2023, "slug": "regular-season"},
                                  status={"type": {"name": "STATUS_SCHEDULED"}}))
    assert not ne.is_league_game(stale, NOW)
    ahead = ne.parse_event(_event(date="2027-01-01T08:30Z",
                                  status={"type": {"name": "STATUS_SCHEDULED"}}))
    assert ne.is_league_game(ahead, NOW)
    mislabelled = ne.parse_event(_event(id="401707730", date="2024-09-09T09:30Z",
                                        season={"year": 2025, "slug": "regular-season"}))
    assert not ne.is_league_game(mislabelled, NOW)


def test_one_bad_event_is_refused_and_the_rest_are_kept():
    # a game ESPN marks final before its line scores are in
    bad = _event(id="401875311")
    bad["competitions"][0]["competitors"][0]["linescores"] = []
    rows, refused = ne.parse_events([_event(), bad])
    assert [r["espn_id"] for r in rows] == [401875310]
    assert [eid for eid, _ in refused] == ["401875311"]


def test_a_club_from_outside_the_league_never_reaches_games():
    e = _event(season={"year": 2027, "slug": "regular-season"})
    e["competitions"][0]["competitors"][1]["team"] = {"id": "110305",
                                                      "displayName": "Shanghai Sharks"}
    r = ne.parse_event(e)
    assert r["away_code"] is None and not ne.is_league_game(r, NOW)


def test_club_counts_name_the_season_whose_clubs_disagree():
    rows = [ne.parse_event(_event(id=str(i))) for i in range(3)]
    assert ne.club_counts(rows, NOW) == {2027: {"NZL": 3, "BRI": 3}}


def test_a_season_spans_two_calendar_years():
    assert ne.years_for([2027]) == [2026, 2027]
    assert ne.years_for([2025, 2026]) == [2024, 2025, 2026]


def test_the_summary_keeps_box_and_plays_and_drops_the_text():
    js = {"boxscore": {"players": [1]}, "header": {"id": 1}, "news": {"big": 1},
          "plays": [{"id": "1", "text": "Taine Murray misses", "homeScore": 3, "period": {"number": 1}}]}
    c = ne.compact_summary(js)
    assert set(c) == {"boxscore", "header", "format", "gameInfo", "plays"}
    assert c["plays"] == [{"id": "1", "homeScore": 3, "period": {"number": 1}}]


# ── the forward capture ──────────────────────────────────────────────────────

class _Conn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        class R:
            def __init__(s, rows):
                s._rows = rows

            def fetchall(s):
                return s._rows
        return R(self.rows)


def test_the_capture_calls_only_when_a_game_tips_within_36_hours():
    from scripts import nbl_odds_capture as cap
    soon = [("2026-11-15", "2026-11-15T04:00:00+00:00")]
    later = [("2026-11-20", "2026-11-20T04:00:00+00:00")]
    assert cap.has_upcoming_games(_Conn(soon), NOW) is True
    assert cap.has_upcoming_games(_Conn(later), NOW) is False
    assert cap.has_upcoming_games(_Conn([]), NOW) is False


def test_the_capture_sets_aside_events_past_the_resolver_window():
    from scripts import nbl_odds_capture as cap
    evs = [{"commence_time": "2026-11-15T04:00:00Z"}, {"commence_time": "2027-01-30T04:00:00Z"}]
    keep, beyond = cap.drop_beyond_window(evs, "2026-11-14", 30)
    assert keep == evs[:1] and beyond == 1


def test_the_capture_job_runs_every_five_minutes_and_is_watched(monkeypatch):
    import scheduler
    from tests.test_nba_prop_window import _fires
    from tests.test_nba_prop_window import _jobs
    from tracking.job_heartbeat import MAX_SILENCE
    job = _jobs(monkeypatch)["nbl_odds_capture"]
    assert job.name.startswith("NBL odds capture")
    assert job.max_instances == 1 and job.coalesce is True
    start = datetime(2026, 11, 15, 3, 0, tzinfo=timezone.utc)
    fires = _fires(job, start, start + timedelta(minutes=59))
    assert len(fires) == 12 and all(f.minute % 5 == 2 for f in fires)
    assert "nbl_odds_capture" in scheduler._PIPELINE_JOBS
    assert MAX_SILENCE["nbl_odds_capture"] == 20


# ── the DraftKings probe ─────────────────────────────────────────────────────

def test_the_draftkings_probe_finds_only_nbl_leagues_on_the_page():
    from scripts import nbl_dk_probe as dk
    page = ('{"displayGroupId":4,"eventGroupId":42648,"eventGroupName":"NBA",'
            '{"name":"NBL","displayGroupId":"4","eventGroupId":"88671048","path":"/x"}'
            '"eventGroupId":"104","eventGroupName":"Australia - NBL"')
    assert dk.league_ids(page) == {"88671048": "NBL", "104": "Australia - NBL"}
