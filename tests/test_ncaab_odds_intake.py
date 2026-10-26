"""Men's college basketball in the live odds intake: resolve, never mint.

WHY THIS FILE EXISTS. NCAAB games belong to ESPN's schedule
(data/ingestors/ncaab_teams.py). The odds feed only RESOLVES onto them, and
two things go wrong silently if it does not:

* the 3-letter fallback files "Kentucky Wildcats" and "Kansas State Wildcats"
  under one invented id (measured 2026-10-26: NCAAB_2026-11-03_WIL_WIL);
* on a neutral court the feed may call ESPN's away team home, and a spread
  parsed in the feed's orientation stores the AWAY team's number in
  spread_home, which CLAUDE.md §4 says is always the home number. Every
  away-cover grade off that row would be inverted.

The real-world shape is pinned from ESPN itself: the Champions Classic,
2026-11-10 ET at the United Center, both games neutral-site, Kansas the away
team and Kentucky home in ESPN's orientation, season.year 2027
(tests/fixtures/ncaab_espn_champions_classic_2026.json). The odds events are
built in the Odds API's shape; no test here touches a database or the feed.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.ingestors.odds_ingestor as oi  # noqa: E402
from data.ingestors import ncaab_teams  # noqa: E402

_FIXTURE = Path(__file__).parent / "fixtures" / "ncaab_espn_champions_classic_2026.json"
ESPN = json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _espn_game(event_id: str) -> dict:
    """One fixture event as ESPN orients it, with the game_id ESPN's row gets."""
    ev = next(e for e in ESPN["events"] if e["id"] == event_id)
    teams = {c["homeAway"]: c["team"] for c in ev["competitions"][0]["competitors"]}
    game_date = ncaab_teams.eastern_game_date(ev["date"])
    return {
        "event": ev,
        "home": teams["home"],
        "away": teams["away"],
        "game_date": game_date,
        "commence_time": ev["date"],
        "game_id": ncaab_teams.build_ncaab_game_id(
            game_date, ncaab_teams.ncaab_slug(teams["away"]["location"]),
            ncaab_teams.ncaab_slug(teams["home"]["location"])),
    }


KU_UK = _espn_game("401909786")          # Kansas @ Kentucky, ESPN orientation
GAME_ID = KU_UK["game_id"]
KENTUCKY = KU_UK["home"]["displayName"]  # "Kentucky Wildcats", ESPN's home
KANSAS = KU_UK["away"]["displayName"]    # "Kansas Jayhawks", ESPN's away
TIP = "2026-11-11T02:30:00Z"             # the feed's commence_time for it


def test_the_fixture_is_what_this_file_assumes():
    """If ESPN's orientation in the fixture were different, every flip test
    below would be asserting the wrong thing."""
    assert KU_UK["event"]["competitions"][0]["neutralSite"] is True
    assert (KU_UK["home"]["location"], KU_UK["away"]["location"]) == ("Kentucky", "Kansas")
    assert KU_UK["game_date"] == "2026-11-10"       # 9:30pm ET, 02:30Z the 11th
    assert GAME_ID == "NCAAB_2026-11-10_kansas_kentucky"
    assert KU_UK["event"]["season"]["year"] == 2027


def _book(key, home, away, *, home_ml, away_ml, home_pt, home_sp, away_sp,
          total=148.5):
    """One bookmaker as the Odds API sends it: outcomes keyed by team NAME."""
    return {
        "key": key,
        "markets": [
            {"key": "h2h", "last_update": "2026-11-09T15:00:00Z",
             "outcomes": [{"name": home, "price": home_ml, "sid": f"{key}-ml-{home}"},
                          {"name": away, "price": away_ml, "sid": f"{key}-ml-{away}"}]},
            {"key": "spreads", "last_update": "2026-11-09T15:00:00Z",
             "outcomes": [{"name": home, "price": home_sp, "point": home_pt},
                          {"name": away, "price": away_sp, "point": -home_pt}]},
            {"key": "totals", "last_update": "2026-11-09T15:00:00Z",
             "outcomes": [{"name": "Over", "price": -110, "point": total},
                          {"name": "Under", "price": -110, "point": total}]},
        ],
    }


# Kentucky -3.5 / -165, Kansas +3.5 / +140 at DraftKings; FanDuel a hair off.
def _event(feed_home, feed_away, books=("draftkings", "fanduel")):
    """The Kansas-Kentucky event, with the feed calling `feed_home` home.

    Prices belong to TEAMS, not slots, so the same Kentucky -3.5 / -165 is
    sent whichever side the feed puts Kentucky on.
    """
    prices = {
        "draftkings": {KENTUCKY: (-165, -3.5, -110), KANSAS: (140, 3.5, -110)},
        "fanduel":    {KENTUCKY: (-160, -3.5, -108), KANSAS: (136, 3.5, -112)},
        "betmgm":     {KENTUCKY: (-170, -4.0, -110), KANSAS: (145, 4.0, -110)},
    }
    out = []
    for key in books:
        p = prices[key]
        out.append(_book(key, feed_home, feed_away,
                         home_ml=p[feed_home][0], away_ml=p[feed_away][0],
                         home_pt=p[feed_home][1],
                         home_sp=p[feed_home][2], away_sp=p[feed_away][2]))
    return {"id": "oddsapi-ku-uk", "sport_key": "basketball_ncaab",
            "commence_time": TIP, "home_team": feed_home, "away_team": feed_away,
            "bookmakers": out}


def _fake_resolver(hit):
    """Stands in for ncaab_teams.make_resolver's callable."""
    calls = []

    def resolve(home_name, away_name, commence_time):
        calls.append((home_name, away_name, commence_time))
        return hit

    resolve.calls = calls
    return resolve


def _rows(odds, market, book="draftkings"):
    return [r for r in odds if r["market"] == market and r["bookmaker"] == book]


# ── the parser: orientation, game id, no games row ───────────────────────────

class TestNcaabResolvesOntoEspn:
    def test_an_event_in_espn_orientation_is_stored_as_given(self):
        games, odds = oi._process_events(
            [_event(KENTUCKY, KANSAS)], "NCAAB", "open", "2026-11-09T15:00:00Z",
            resolve_game_id=_fake_resolver((GAME_ID, False)))
        assert games == []
        assert {r["game_id"] for r in odds} == {GAME_ID}
        (ml,) = _rows(odds, "h2h")
        assert (ml["home_price"], ml["away_price"]) == (-165, 140)
        (sp,) = _rows(odds, "spreads")
        assert sp["spread_home"] == -3.5
        assert (sp["home_price"], sp["away_price"]) == (-110, -110)

    def test_a_neutral_court_the_feed_flips_is_stored_in_espn_orientation(self):
        """The feed calls Kansas home. ESPN calls Kentucky home. The stored row
        must be Kentucky's: -165 in home_price and -3.5 in spread_home. Parsed
        in the feed's orientation it would hold Kansas's +3.5, and every
        away-cover grade off it would be inverted."""
        resolver = _fake_resolver((GAME_ID, True))
        games, odds = oi._process_events(
            [_event(KANSAS, KENTUCKY)], "NCAAB", "open", "2026-11-09T15:00:00Z",
            resolve_game_id=resolver)
        assert games == []
        assert {r["game_id"] for r in odds} == {GAME_ID}
        # The resolver sees the FEED's orientation; the swap is ours to do.
        assert resolver.calls == [(KANSAS, KENTUCKY, TIP)]
        (ml,) = _rows(odds, "h2h")
        assert (ml["home_price"], ml["away_price"]) == (-165, 140)
        assert ml["home_sid"] == f"draftkings-ml-{KENTUCKY}"
        assert ml["away_sid"] == f"draftkings-ml-{KANSAS}"
        (sp,) = _rows(odds, "spreads")
        assert sp["spread_home"] == -3.5
        (fd,) = _rows(odds, "spreads", "fanduel")
        assert (fd["spread_home"], fd["home_price"], fd["away_price"]) == (-3.5, -108, -112)
        (tot,) = _rows(odds, "totals")
        assert (tot["total_line"], tot["over_price"], tot["under_price"]) == (148.5, -110, -110)

    def test_flipped_and_unflipped_feeds_store_identical_rows(self):
        """The same prices, oriented either way by the feed, must land as the
        same row. This is the property, stated once."""
        def strip(rows):
            return sorted((r["bookmaker"], r["market"], r["home_price"], r["away_price"],
                           r["spread_home"], r["total_line"]) for r in rows)
        _, straight = oi._process_events(
            [_event(KENTUCKY, KANSAS)], "NCAAB", "open", "s",
            resolve_game_id=_fake_resolver((GAME_ID, False)))
        _, flipped = oi._process_events(
            [_event(KANSAS, KENTUCKY)], "NCAAB", "open", "s",
            resolve_game_id=_fake_resolver((GAME_ID, True)))
        assert strip(straight) == strip(flipped)

    def test_no_games_row_is_ever_emitted(self):
        games, _ = oi._process_events(
            [_event(KENTUCKY, KANSAS), _event(KANSAS, KENTUCKY)], "NCAAB", "open", "s",
            resolve_game_id=_fake_resolver((GAME_ID, False)))
        assert games == []

    def test_an_unresolved_event_is_dropped_whole(self):
        games, odds = oi._process_events(
            [_event(KENTUCKY, KANSAS)], "NCAAB", "open", "s",
            resolve_game_id=_fake_resolver(None))
        assert games == [] and odds == []

    @pytest.mark.parametrize("hit", [(None, False), ("", True)])
    def test_a_tuple_without_a_game_id_is_dropped_too(self, hit):
        """A tuple is truthy even when its id is empty."""
        games, odds = oi._process_events(
            [_event(KENTUCKY, KANSAS)], "NCAAB", "open", "s",
            resolve_game_id=_fake_resolver(hit))
        assert games == [] and odds == []

    def test_with_no_resolver_ncaab_writes_nothing(self):
        """Fail closed: a caller that forgot the resolver must not mint
        NCAAB_<date>_WIL_WIL-shaped ids, even with DraftKings present."""
        games, odds = oi._process_events(
            [_event(KENTUCKY, KANSAS)], "NCAAB", "open", "s")
        assert games == [] and odds == []
        assert "NCAAB" in oi.RESOLVE_ONLY_SPORTS
        assert oi.NCAAB_GAMES_ARE_NOT_OURS is True


# ── the DraftKings gate ──────────────────────────────────────────────────────

class TestTheDraftKingsGate:
    def test_ncaab_without_draftkings_still_stores_the_other_books(self):
        """The first post from ANY book is the opener the timing work needs."""
        _, odds = oi._process_events(
            [_event(KENTUCKY, KANSAS, books=("fanduel", "betmgm"))], "NCAAB", "open", "s",
            resolve_game_id=_fake_resolver((GAME_ID, False)))
        assert {r["bookmaker"] for r in odds} == {"fanduel", "betmgm"}
        assert {r["game_id"] for r in odds} == {GAME_ID}

    def test_mlb_without_draftkings_still_stores_no_odds(self):
        """The exemption is NCAAB's alone. MLB keeps its games row (this file
        is MLB's schedule) and drops the odds, exactly as before."""
        ev = _event(KENTUCKY, KANSAS, books=("fanduel",))
        ev = {**ev, "home_team": "Seattle Mariners", "away_team": "Boston Red Sox",
              "commence_time": "2026-09-09T23:40:00Z"}
        games, odds = oi._process_events([ev], "MLB", "open", "s")
        assert odds == []
        assert len(games) == 1

    def test_the_exemption_is_a_named_constant(self):
        assert oi.DK_GATE_EXEMPT_SPORTS == frozenset({"NCAAB"})


# ── names, seasons, keys ─────────────────────────────────────────────────────

class TestLabels:
    def test_the_odds_api_key(self):
        assert oi.SPORT_KEYS["NCAAB"] == "basketball_ncaab"
        assert oi.SPORT_KEYS["NCAAB"] == ncaab_teams.ODDS_API_SPORT_KEY

    @pytest.mark.parametrize("game_date", ["2026-11-01", "2026-11-10", "2026-12-31",
                                           "2027-03-15", "2027-04-06"])
    def test_the_season_is_the_ending_year(self, game_date):
        """ESPN labels 2026-27 as 2027 (the fixture's season.year)."""
        assert oi._season_label("NCAAB", game_date) == 2027
        assert oi._season_label("NCAAB", game_date) == ncaab_teams.ncaab_season_label(game_date)

    def test_the_other_sports_labels_did_not_move(self):
        assert oi._season_label("NBA", "2026-10-25") == 2027
        assert oi._season_label("NBA", "2027-04-01") == 2027
        assert oi._season_label("NCAAF", "2027-01-10") == 2026
        assert oi._season_label("NCAAF", "2026-11-28") == 2026
        assert oi._season_label("MLB", "2026-10-25") == 2026
        assert oi._season_label("NHL", "2026-09-29") == 2027

    def test_the_name_is_returned_untouched_and_silently(self):
        """The 3-letter fallback would turn both Wildcats into WIL and warn on
        every school every pass. NCAAB never mints, so the value is unused."""
        seen = []
        sink = logger.add(lambda m: seen.append(m.record["level"].name), level="WARNING")
        try:
            assert oi._normalize_team("Kentucky Wildcats", "NCAAB") == "Kentucky Wildcats"
            assert oi._normalize_team("Kansas State Wildcats", "NCAAB") == "Kansas State Wildcats"
        finally:
            logger.remove(sink)
        assert seen == []


# ── the real resolver, end to end, against a fake catalog ────────────────────

class _Result:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


def _registry_rows():
    """ncaab_teams rows for the fixture's four schools, plus the Wildcats
    namesake the 3-letter fallback would have collided Kentucky with."""
    rows = []
    for ev in ESPN["events"]:
        for c in ev["competitions"][0]["competitors"]:
            t = c["team"]
            rows.append((int(t["id"]), t["location"], ncaab_teams.ncaab_slug(t["location"]),
                         t["name"], t["displayName"], t["shortDisplayName"],
                         t["abbreviation"], True, None))
    rows.append((2306, "Kansas State", "kansas-state", "Wildcats", "Kansas State Wildcats",
                 "Kansas St", "KSU", True, None))
    return rows


def _events_rows():
    out = []
    for eid in ("401909564", "401909786"):
        g = _espn_game(eid)
        out.append((g["game_id"], g["game_date"], g["commence_time"],
                    int(g["home"]["id"]), int(g["away"]["id"])))
    return out


class _CatalogConn:
    """Answers the two reads ncaab_teams.make_resolver makes, and records
    everything else so a test can check order and writes."""

    def __init__(self, *, teams=None, events=None):
        self.teams = _registry_rows() if teams is None else teams
        self.events = _events_rows() if events is None else events
        self.log: list[tuple] = []

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split())
        self.log.append(("execute", s, params))
        if "FROM ncaab_teams" in s:
            return _Result(self.teams)
        if "FROM ncaab_events" in s:
            lo, hi = params
            return _Result([r for r in self.events if lo <= r[1] <= hi])
        return _Result([])

    def executemany(self, sql, rows):
        self.log.append(("executemany", " ".join(str(sql).split()), list(rows)))

    def commit(self):
        self.log.append(("commit",))

    def rollback(self):
        self.log.append(("rollback",))

    def close(self):
        self.log.append(("close",))

    def writes(self, table):
        return [e[2] for e in self.log
                if e[0] == "executemany" and f"INSERT INTO {table} " in e[1]]


@pytest.fixture(autouse=True)
def _fresh_registry():
    ncaab_teams.reset_registry_cache()
    yield
    ncaab_teams.reset_registry_cache()


class TestTheRealResolver:
    def test_both_orientations_land_on_espns_row(self):
        resolve = oi._ncaab_resolver(_CatalogConn(), "2026-11-10")
        assert resolve is not None
        assert resolve(KENTUCKY, KANSAS, TIP) == (GAME_ID, False)
        assert resolve(KANSAS, KENTUCKY, TIP) == (GAME_ID, True)

    def test_a_flipped_feed_parses_into_espns_orientation(self):
        resolve = oi._ncaab_resolver(_CatalogConn(), "2026-11-10")
        _, odds = oi._process_events([_event(KANSAS, KENTUCKY)], "NCAAB", "open", "s",
                                     resolve_game_id=resolve)
        (sp,) = _rows(odds, "spreads")
        assert sp["game_id"] == GAME_ID
        assert sp["spread_home"] == -3.5

    def test_the_wildcats_namesake_does_not_resolve_onto_kentucky(self):
        resolve = oi._ncaab_resolver(_CatalogConn(), "2026-11-10")
        assert resolve("Kansas State Wildcats", KANSAS, TIP) is None

    def test_an_empty_schedule_window_is_no_resolver(self):
        assert oi._ncaab_resolver(_CatalogConn(events=[]), "2026-11-10") is None

    def test_an_unreadable_catalog_is_no_resolver(self):
        class _Broken:
            def execute(self, *a, **k):
                raise RuntimeError("relation ncaab_teams does not exist")

            def rollback(self):
                pass

        assert oi._ncaab_resolver(_Broken(), "2026-11-10") is None

    def test_a_registry_filled_after_a_failed_look_is_seen(self):
        """The registry caches an EMPTY list when its table is unreadable. A
        long-lived poller that looked first must still pick NCAAB up once the
        ESPN ingestor has written the table, without a restart."""
        assert oi._ncaab_resolver(_CatalogConn(teams=[]), "2026-11-10") is None
        assert oi._ncaab_resolver(_CatalogConn(), "2026-11-10") is not None

    def test_the_dispatcher(self):
        assert oi._schedule_resolver("NCAAB", _CatalogConn(), "2026-11-10") is not None
        assert oi._schedule_resolver("MLB", _CatalogConn(), "2026-11-10") is None
        assert oi.SCHEDULE_RESOLVED_SPORTS == ("NFL", "NCAAB")


# ── the three callers ────────────────────────────────────────────────────────

@pytest.fixture
def no_feed(monkeypatch):
    """Every Odds API entry point replaced; a test that reaches the network
    fails instead of spending."""
    def _boom(*a, **k):
        raise AssertionError("the Odds API must not be called from a test")

    monkeypatch.setattr(oi, "_get_odds", _boom)
    monkeypatch.setattr(oi, "_get_historical_odds", _boom)
    monkeypatch.setattr(oi, "REQUEST_SLEEP", 0)
    monkeypatch.setattr(oi, "persist_quota", lambda conn: None)
    monkeypatch.setattr(oi, "lock_down", lambda conn, table: None)


def _resolver_spy(monkeypatch, conn, result="real"):
    """Patch ncaab_teams.make_resolver, logging into the connection's log so
    a test can see what was committed before it ran."""
    real = ncaab_teams.make_resolver

    def spy(c, around_date, *a, **k):
        conn.log.append(("make_resolver", around_date))
        return real(c, around_date, *a, **k) if result == "real" else result

    monkeypatch.setattr(ncaab_teams, "make_resolver", spy)


class TestRunOddsIngestor:
    def test_ncaab_is_in_the_default_pass_and_runs_last(self, monkeypatch, no_feed):
        called = []
        monkeypatch.setattr(oi, "get_connection", lambda: _CatalogConn())
        monkeypatch.setattr(oi, "_get_odds", lambda key, markets: called.append(key) or [])
        result = oi.run_odds_ingestor()
        assert "NCAAB" in result["sports"]
        assert called[-1] == "basketball_ncaab"
        # The NFL is still pulled too: its path is unchanged.
        assert "americanfootball_nfl" in called

    def test_it_stores_resolved_odds_and_no_games_row(self, monkeypatch, no_feed):
        conn = _CatalogConn()
        monkeypatch.setattr(oi, "get_connection", lambda: conn)
        monkeypatch.setattr(oi, "_get_odds", lambda key, markets: [_event(KANSAS, KENTUCKY)])
        _resolver_spy(monkeypatch, conn)
        result = oi.run_odds_ingestor(sport="NCAAB", target_date="2026-11-10")
        assert result["games"] == 0
        assert all(batch == [] for batch in conn.writes("games"))
        (odds,) = conn.writes("odds")
        assert {r["game_id"] for r in odds} == {GAME_ID}
        (sp,) = _rows(odds, "spreads")
        assert sp["spread_home"] == -3.5

    def test_earlier_sports_are_committed_before_the_schedule_read(self, monkeypatch, no_feed):
        """ncaab_teams rolls back on an unreadable table. Every sport's odds
        sit on one connection until the end of the loop, so the commit has to
        come first or a missing NCAAB table takes the pass's MLB rows with it."""
        conn = _CatalogConn()
        mlb = {**_event(KENTUCKY, KANSAS), "home_team": "Seattle Mariners",
               "away_team": "Boston Red Sox", "commence_time": "2026-09-09T23:40:00Z"}
        feeds = {"baseball_mlb": [mlb], "basketball_ncaab": [_event(KANSAS, KENTUCKY)]}
        monkeypatch.setattr(oi, "get_connection", lambda: conn)
        monkeypatch.setattr(oi, "_get_odds", lambda key, markets: feeds.get(key, []))
        _resolver_spy(monkeypatch, conn)
        oi.run_odds_ingestor(target_date="2026-11-10")
        mlb_insert = next(i for i, e in enumerate(conn.log)
                          if e[0] == "executemany" and "INSERT INTO odds " in e[1]
                          and e[2] and e[2][0]["sport"] == "MLB")
        resolver_built = next(i for i, e in enumerate(conn.log) if e[0] == "make_resolver")
        assert any(e[0] == "commit" for e in conn.log[mlb_insert:resolver_built]), (
            "the MLB rows were still uncommitted when the NCAAB schedule was read")

    def test_no_resolver_means_ncaab_is_skipped_not_minted(self, monkeypatch, no_feed):
        conn = _CatalogConn()
        monkeypatch.setattr(oi, "get_connection", lambda: conn)
        monkeypatch.setattr(oi, "_get_odds", lambda key, markets: [_event(KANSAS, KENTUCKY)])
        _resolver_spy(monkeypatch, conn, result=None)
        result = oi.run_odds_ingestor(sport="NCAAB", target_date="2026-11-10")
        assert result["games"] == 0 and result["odds_rows"] == 0
        assert conn.writes("games") == [] and conn.writes("odds") == []


class TestFetchPregameRows:
    """The 30-second poller's read half. Its anchor is NOW, so the resolver is
    stubbed rather than built from the fixture's November window."""

    def test_a_stubbed_resolver_is_used(self, monkeypatch, no_feed):
        conn = _CatalogConn()
        monkeypatch.setattr(oi, "get_connection", lambda: conn)
        monkeypatch.setattr(oi, "_get_odds", lambda key, markets: [_event(KANSAS, KENTUCKY)])
        _resolver_spy(monkeypatch, conn, result=_fake_resolver((GAME_ID, True)))
        rows = oi.fetch_pregame_rows(["NCAAB"])
        assert {r["game_id"] for r in rows} == {GAME_ID}
        (sp,) = _rows(rows, "spreads")
        assert sp["spread_home"] == -3.5
        assert conn.writes("games") == []

    def test_no_resolver_returns_nothing_for_ncaab(self, monkeypatch, no_feed):
        conn = _CatalogConn()
        monkeypatch.setattr(oi, "get_connection", lambda: conn)
        monkeypatch.setattr(oi, "_get_odds", lambda key, markets: [_event(KANSAS, KENTUCKY)])
        _resolver_spy(monkeypatch, conn, result=None)
        assert oi.fetch_pregame_rows(["NCAAB"]) == []
        assert conn.writes("games") == []


def _unresolvable_event():
    """A real-shaped event whose names are in no registry: the case the
    range backfill would have paid for, dropped and ledgered."""
    ev = _event(KANSAS, KENTUCKY)
    rename = {KANSAS: "Texas A&M-CC Islanders", KENTUCKY: "Grambling St Tigers"}
    for b in ev["bookmakers"]:
        for m in b["markets"]:
            for o in m["outcomes"]:
                o["name"] = rename.get(o["name"], o["name"])
    return {**ev, "id": "oddsapi-unresolvable", "home_team": rename[KANSAS],
            "away_team": rename[KENTUCKY]}


class TestHistoricalBackfill:
    """Neither historical entry point buys NCAAB.

    run_historical_odds_range ledgers every (date, hour) it buys, and an
    NCAAB event that does not resolve is dropped. A slate with one event the
    registry cannot name was paid for, half-stored and ledgered, so the
    dropped event was gone and a re-run skipped the hour. The ledger key is
    also the one the dedicated NCAAB history purchase resumes on, which keeps
    unmatched events for replay: an hour bought here first would block it.
    """

    def _wire(self, monkeypatch, conn):
        paid, opened = [], []
        monkeypatch.setattr(oi, "get_connection", lambda: opened.append(1) or conn)
        # A recorder, not the raising stub: the loop swallows exceptions into
        # stats["errors"], so a raise would hide a call that was attempted.
        monkeypatch.setattr(oi, "_get_historical_odds",
                            lambda *a, **k: paid.append(a)
                            or [_event(KANSAS, KENTUCKY), _unresolvable_event()])
        return paid, opened

    def test_the_range_backfill_refuses_ncaab_before_paying_or_ledgering(
            self, monkeypatch, no_feed):
        """The schedule is there and one of the two events resolves: the
        partial slate that used to be ledgered. Nothing is bought, no
        connection is opened, so no ledger row can exist."""
        conn = _CatalogConn()
        paid, opened = self._wire(monkeypatch, conn)
        stats = oi.run_historical_odds_range("NCAAB", "2026-11-10", "2026-11-11",
                                             hours_utc=[3, 15])
        assert paid == [], "the 10x historical endpoint was called for NCAAB"
        assert opened == [] and conn.log == []
        assert stats["skipped"] == "resolve_only_sport"
        assert (stats["calls"], stats["credits_spent"], stats["odds_rows"],
                stats["games"], stats["errors"]) == (0, 0, 0, 0, 0)

    def test_a_worker_job_for_ncaab_history_is_refused_at_validation(self, monkeypatch, no_feed):
        """The historical_odds job validates against SPORT_KEYS, which now
        includes NCAAB. It must refuse NCAAB with a clear error before any
        row is queued: NCAAB history is bought by ncaab_odds_history, which
        keeps unmatched events. The run-time refusal above stays as the
        backstop for a row written past the validator."""
        from tracking import job_queue as q

        with pytest.raises(ValueError, match="ncaab_odds_history"):
            q._validate_historical_odds({"sport": "ncaab", "start": "2026-11-10",
                                         "end": "2026-11-12", "credit_cap": 5000})
        conn = _CatalogConn()
        paid, opened = self._wire(monkeypatch, conn)
        stats = q._job_historical_odds(sport="NCAAB", start="2026-11-10", end="2026-11-12",
                                       hours_utc=[12], bookmakers=None, credit_cap=5000,
                                       markets=None, ignore_ledger=False)
        assert paid == [] and opened == []
        assert stats["skipped"] == "resolve_only_sport"

    def test_the_nfl_backfill_still_buys(self, monkeypatch, no_feed):
        """Positive control: the refusal is NCAAB's alone. The NFL range path
        pays and ledgers exactly as it did before this change."""
        conn = _CatalogConn()
        paid, opened = self._wire(monkeypatch, conn)
        stats = oi.run_historical_odds_range("NFL", "2026-11-10", "2026-11-10",
                                             hours_utc=[15])
        assert len(paid) == 1 and stats["calls"] == 1
        assert "skipped" not in stats
        assert any(e[0] == "execute" and "INSERT INTO odds_history_pulls" in e[1]
                   for e in conn.log)

    def test_the_single_date_path_refuses_before_paying(self, monkeypatch, no_feed):
        """run_historical_odds builds no resolver; it would pay 10x and drop
        every event. It returns before the call (no_feed raises on one)."""
        out = oi.run_historical_odds("NCAAB", "2026-11-10")
        assert out["odds_rows"] == 0 and out["skipped"] == "resolve_only_sport"


# ── the request log can file NCAAB calls under NCAAB ─────────────────────────

def test_the_request_log_tags_ncaab():
    from monitoring import probe

    _, sport = probe._redact(
        "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds?apiKey=SECRET&markets=h2h")
    assert sport == "NCAAB"
    _, sport = probe._redact(
        "https://site.api.espn.com/apis/site/v2/sports/basketball/"
        "mens-college-basketball/scoreboard?dates=20261110")
    assert sport == "NCAAB"


def test_the_cli_offers_ncaab_and_nfl():
    src = inspect.getsource(oi)
    cli = src[src.index('if __name__ == "__main__":'):]
    assert '"NCAAB"' in cli and '"NFL"' in cli


def test_the_resolver_looks_thirty_days_ahead(monkeypatch):
    """A game the feed lists more than ten days out must still resolve: NCAAB is
    exempt from the DraftKings gate so the first posted price is kept."""
    seen = {}

    def spy(conn, around_date, *a, **k):
        seen.update(k)
        return None

    monkeypatch.setattr(ncaab_teams, "make_resolver", spy)
    oi._ncaab_resolver(object(), "2026-11-02")
    assert seen.get("days_fwd") == 30
