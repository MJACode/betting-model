"""The NBA schedule refresh (data/ingestors/nba_schedule_refresh.py) and its wiring.

Until 2026-10-20 nba_schedule was one load by hand (2026-10-15) that nothing
refreshed: 24 NBA Cup week games were not in it, the knockout games were
placeholders, play-in and playoffs had no teams, and a moved tip never arrived.
These pin what the daily refresh reads from ESPN, what it writes and what it
never touches, that it fails open, that it runs before the NBA results step,
and the health check that says when it has stopped.

The ESPN shapes are a trimmed copy of four month scoreboards fetched
2026-10-20 (tests/fixtures/espn_nba_schedule_sample.json): two December 2026
games, two Cup knockout slots with no teams yet, the 2025-26 Cup quarterfinal,
semifinal and final, a 2026 play-in and a playoff game, and a preseason game.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

import data.ingestors.nba_schedule_refresh as nsr

ROOT = Path(__file__).parent.parent
FIX = ROOT / "tests" / "fixtures"
SAMPLE = json.loads((FIX / "espn_nba_schedule_sample.json").read_text(encoding="utf-8"))
POSTPONED = json.loads((FIX / "espn_nba_scoreboard_2025-01-09_postponed.json").read_text(encoding="utf-8"))
PIPE = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def refuse(url):
        raise AssertionError(f"a test reached the network: {url}")
    monkeypatch.setattr(nsr, "fetch_core", refuse, raising=False)


def _by_gid(rows):
    return {r["game_id"]: r for r in rows}


# ── reading ESPN ─────────────────────────────────────────────────────────────

def test_each_game_gets_our_id_its_eastern_date_and_the_leagues_type():
    counts = {}
    rows = _by_gid(nsr.event_rows(SAMPLE, counts))
    assert {g: r["game_type"] for g, r in rows.items()} == {
        "NBA_2026-12-22_TOR_WAS": "regular",
        "NBA_2026-12-22_DAL_GSW": "regular",          # 03:30Z on the 23rd is 10:30pm ET on the 22nd
        "NBA_2025-12-09_MIA_ORL": "regular",          # a Cup quarterfinal counts in the standings
        "NBA_2025-12-13_NYK_ORL": "regular",          # a semifinal too
        "NBA_2025-12-16_SAS_NYK": "cup_final",        # the final does not
        "NBA_2026-04-14_MIA_CHA": "playin",
        "NBA_2026-04-18_TOR_CLE": "playoff",
    }
    # the two knockout slots with no teams yet, and the preseason game
    assert counts == {"no_teams": 2, "other_type": 1}
    gsw = rows["NBA_2026-12-22_DAL_GSW"]
    assert gsw["season"] == 2027 and gsw["nba_game_id"] == "espn:401910171"
    assert gsw["commence_time"] == "2026-12-23T03:30:00+00:00"
    assert rows["NBA_2025-12-13_NYK_ORL"]["is_neutral"] is True
    assert rows["NBA_2025-12-13_NYK_ORL"]["arena_city"] == "Las Vegas"


def test_a_date_with_no_tip_yet_is_stored_without_one():
    """ESPN stamps midnight ET on a game whose time is not set (timeValid
    false). Read as a tip, the window job would decide it at 11pm the night
    before."""
    ev = json.loads(json.dumps(SAMPLE["events"][4]))          # the 2025-26 quarterfinal
    ev["competitions"][0]["timeValid"] = False
    (row,) = nsr.event_rows({"events": [ev]})
    assert row["commence_time"] is None and row["game_date"] == "2025-12-09"


def test_a_postponed_game_is_read_as_postponed():
    rows = _by_gid(nsr.event_rows(POSTPONED))
    assert rows["NBA_2025-01-09_CHA_LAL"]["postponed"] is True
    assert rows["NBA_2025-01-09_CHA_LAL"]["status_text"] == "Postponed"
    assert rows["NBA_2025-01-09_TOR_CLE"]["postponed"] is False


def test_the_months_run_from_this_one_through_the_finals():
    assert nsr.months(date(2026, 10, 20)) == ["202610", "202611", "202612", "202701", "202702",
                                              "202703", "202704", "202705", "202706"]
    assert nsr.months(date(2026, 12, 5), ahead=1) == ["202612", "202701"]


# ── the plan ─────────────────────────────────────────────────────────────────

def _espn(gid, kind="regular", tip="2026-12-23T00:00:00+00:00", eid="1", postponed=False):
    away, home = gid.split("_")[2:]
    return {"nba_game_id": f"espn:{eid}", "game_id": gid, "season": 2027, "game_type": kind,
            "game_date": gid.split("_")[1], "commence_time": tip, "home_team": home,
            "away_team": away, "status_text": "Postponed" if postponed else "Scheduled",
            "postponed": postponed, "arena_name": None, "arena_city": None, "arena_state": None,
            "is_neutral": False, "game_label": None, "national_tv": None}


def _stored(gid, nid, kind="regular", tip="2026-12-23T00:00:00+00:00", status="7:00 pm ET"):
    parts = gid.split("_")
    return {"nba_game_id": nid, "game_id": gid, "season": 2027, "game_type": kind,
            "game_date": parts[1], "commence_time": tip, "home_team": parts[3],
            "away_team": parts[2], "status_text": status}


G1 = "NBA_2026-12-22_TOR_WAS"
G2 = "NBA_2026-12-08_LAL_BOS"       # a Cup week game the October load never had


def test_a_game_the_schedule_lacks_is_added_and_given_a_games_row():
    p = nsr.plan([_espn(G2, eid="9")], [], {}, ["202612"])
    assert [r["game_id"] for r in p["upsert"]] == [G2]
    assert [r["game_id"] for r in p["games_insert"]] == [G2]


def test_only_a_regular_season_game_is_written_into_games():
    """As the NBA.com load: the odds feed writes a playoff game's row."""
    p = nsr.plan([_espn("NBA_2027-04-20_MIA_BOS", kind="playoff")], [], {}, ["202704"])
    assert len(p["upsert"]) == 1 and p["games_insert"] == []


def test_a_listed_game_is_confirmed_and_never_rewritten():
    stored = [_stored(G1, "0022600400")]
    p = nsr.plan([_espn(G1)], stored, {G1: {"commence_time": "2026-12-23T00:00:00+00:00",
                                           "data_source": "live"}}, ["202612"])
    assert p["confirm"] == ["0022600400"]
    assert p["upsert"] == p["times"] == p["status"] == p["games_insert"] == p["games_times"] == []


OLD, NEW = "2026-12-23T00:00:00+00:00", "2026-12-23T01:00:00+00:00"


def test_a_moved_tip_reaches_the_schedule_when_the_odds_feed_shows_it_too():
    p = nsr.plan([_espn(G1, tip=NEW)], [_stored(G1, "0022600400")],
                 {G1: {"commence_time": NEW, "data_source": "live"}}, ["202612"])
    assert p["times"] == [("0022600400", NEW, OLD)] and p["tip_disputed"] == []
    assert p["games_times"] == []                  # the feed's own row: the feed keeps it


def test_espn_alone_never_moves_the_leagues_tip():
    """CHI @ MIL, 2026-10-23: ESPN 4:00pm ET against the league's load, the
    Bucks' release and ticket listings at 7pm CT (measured 2026-10-20). Moved on
    ESPN's word the prop models would decide five hours early."""
    for g in ({G1: {"commence_time": OLD, "data_source": "nba_api_schedule"}},       # feed silent
              {G1: {"commence_time": "2026-12-23T00:10:00+00:00", "data_source": "live"}},  # feed differs
              {}):
        p = nsr.plan([_espn(G1, tip=NEW)], [_stored(G1, "0022600400")], g, ["202612"])
        assert p["times"] == [] and p["games_times"] == [], g
        assert [d[:3] for d in p["tip_disputed"]] == [(G1, OLD, NEW)]
        assert p["confirm"] == ["0022600400"]


FLEX_OLD, FLEX_NEW = "2027-03-11T00:00:00+00:00", "2027-03-11T02:30:00+00:00"   # 7:00pm ET -> 9:30pm ET


def _flex(feed, old=FLEX_OLD, new=FLEX_NEW):
    g = "NBA_2027-03-10_LAL_BOS"
    return nsr.plan([_espn(g, tip=new)], [_stored(g, "0022600900", tip=old)],
                    {g: {"commence_time": feed, "data_source": "live"}}, ["202703"])


def test_a_moved_tip_reaches_the_schedule_when_the_feed_lists_the_books_start():
    """The odds feed lists the books' start, which on 35 of the 46 2026-27 games
    it had written by 2026-10-20 sat ten minutes after the league's tip
    (production). A flexed game whose feed start sits ten minutes after ESPN's
    new tip has moved, and the schedule must say so: left at 7pm, every NBA
    model would decide three and a half hours before the real tip."""
    p = _flex("2027-03-11T02:40:00+00:00")
    assert p["times"] == [("0022600900", FLEX_NEW, FLEX_OLD)] and p["tip_disputed"] == []
    for lag in ("02:30:00", "02:38:00", "02:52:00"):        # 0, 8 and 22 minutes: all measured
        assert _flex(f"2027-03-11T{lag}+00:00")["times"], lag


def test_a_feed_that_has_not_moved_yet_never_moves_the_tip():
    """The feed still on the old start (ten minutes after it), or before ESPN's
    new tip (the feed never lists a start before the league's), or half an
    hour or more past it, is not a second source for the move."""
    assert _flex("2027-03-11T00:10:00+00:00")["tip_disputed"]                 # the flex, feed not moved
    small = dict(old="2027-03-11T00:00:00+00:00", new="2027-03-11T00:15:00+00:00")
    assert _flex("2027-03-11T00:10:00+00:00", **small)["times"] == []         # 5 minutes before ESPN's
    assert _flex("2027-03-11T03:05:00+00:00")["times"] == []                  # 35 minutes after it
    half = dict(old="2027-03-11T00:00:00+00:00", new="2027-03-11T00:30:00+00:00")
    assert _flex("2027-03-11T00:40:00+00:00", **half)["times"]                # moved: 10 after ESPN's
    assert _flex("2027-03-11T00:10:00+00:00", **half)["times"] == []          # not moved: nearer the old
    early = dict(old="2027-03-11T00:00:00+00:00", new="2027-03-10T23:45:00+00:00")
    assert _flex("2027-03-11T00:10:00+00:00", **early)["times"] == []         # 25 after ESPN's, 10 after the old
    assert _flex("2027-03-10T23:55:00+00:00", **early)["times"]               # moved: before the old


def test_a_tip_the_league_never_set_is_filled():
    p = nsr.plan([_espn(G1, tip=NEW)], [_stored(G1, "0042600101", kind="playoff", tip=None)], {}, ["202612"])
    assert p["times"] == [("0042600101", NEW, None)]


def test_a_games_row_only_this_refresh_wrote_follows_espn():
    p = nsr.plan([_espn(G2, eid="9", tip=NEW)], [_stored(G2, "espn:9", tip=OLD)],
                 {G2: {"commence_time": OLD, "data_source": "espn_schedule"}}, ["202612"])
    assert [r["commence_time"] for r in p["upsert"]] == [NEW]
    assert p["games_times"] == [(G2, NEW)]


def test_a_game_with_no_tip_yet_never_moves_a_stored_tip():
    stored = [_stored(G1, "0022600400")]
    p = nsr.plan([_espn(G1, tip=None)], stored, {}, ["202612"])
    assert p["times"] == [] and p["confirm"] == ["0022600400"]


def test_a_postponement_is_recorded_once():
    stored = [_stored(G1, "0022600400")]
    p = nsr.plan([_espn(G1, postponed=True)], stored, {}, ["202612"])
    assert p["status"] == [("0022600400", "Postponed")]
    stored = [_stored(G1, "0022600400", status="Postponed")]
    assert nsr.plan([_espn(G1, postponed=True)], stored, {}, ["202612"])["status"] == []


def test_an_espn_row_gives_way_to_the_leagues_own_row():
    stored = [_stored(G2, "espn:9"), _stored(G2, "0022601210")]
    p = nsr.plan([_espn(G2, eid="9")], stored, {}, ["202612"])
    assert p["superseded"] == ["espn:9"] and p["upsert"] == []
    assert p["confirm"] == ["0022601210"]


def test_a_listed_game_espn_does_not_show_is_named_not_dropped():
    """A moved game changes its game_id; nothing is deleted on one day's read.
    The Cup placeholders (no teams) and months not fetched are not counted."""
    stored = [_stored(G1, "0022600400"),
              _stored("NBA_2026-12-04_nan_nan", "0022601201"),
              _stored("NBA_2027-01-05_TOR_WAS", "0022600500")]
    p = nsr.plan([], stored, {}, ["202612"])
    assert p["not_on_espn"] == [G1]
    assert p["superseded"] == [] and p["upsert"] == []


def test_an_espn_row_espn_moved_is_updated_in_place_not_named():
    moved = _espn("NBA_2026-12-09_LAL_BOS", eid="9")
    p = nsr.plan([moved], [_stored(G2, "espn:9")], {}, ["202612"])
    assert [r["game_id"] for r in p["upsert"]] == ["NBA_2026-12-09_LAL_BOS"]
    assert p["not_on_espn"] == []


# ── the run: fail-open ───────────────────────────────────────────────────────

class _Conn:
    """Answers the two reads; records every write."""

    def __init__(self, stored=(), games=()):
        self.stored, self.games = list(stored), list(games)
        self.writes, self.committed, self.rolled_back, self.closed = [], 0, 0, False

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if s.startswith("SELECT nba_game_id"):
            self._rows = [tuple(r[c] for c in ("nba_game_id", "game_id", "season", "game_type",
                                               "game_date", "commence_time", "home_team",
                                               "away_team", "status_text")) for r in self.stored]
        elif s.startswith("SELECT game_id, commence_time, data_source FROM games"):
            self._rows = [g for g in self.games if g[0] in params[0]]
        else:
            self.writes.append((s, params))
            self._rows = []
        return self

    def executemany(self, sql, rows):
        self.writes.append((" ".join(sql.split()), list(rows)))

    def fetchall(self):
        return self._rows

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1

    def close(self):
        self.closed = True


NOW = datetime(2025, 12, 1, 12, 0, tzinfo=timezone.utc)


def _board(month):
    """The fixture's 2025-12 events for 202512, nothing for any other month."""
    return {"events": [e for e in SAMPLE["events"] if e["date"].startswith("2025-12")] if month == "202512" else []}


def test_espn_unreachable_writes_nothing_and_never_raises():
    calls = []

    def boom(url, params):
        raise ConnectionError("403 from site.api.espn.com")

    def core_boom(url):
        raise ConnectionError("timed out from sports.core.api.espn.com")

    t = nsr.refresh("2025-12-01", get_json=boom, core_json=core_boom,
                    connect=lambda: calls.append(1), now=NOW)
    assert t["failed"] == t["months"] and t["fetched"] == [] and calls == []
    assert t["via_core"] == []


def test_one_failed_month_is_left_as_stored_and_the_rest_are_written():
    conn = _Conn()

    def get(url, params):
        if params["dates"] == "202601":
            raise TimeoutError("read timed out")
        assert params["limit"] == nsr.EVENT_LIMIT
        return _board(params["dates"])

    def core(url):
        raise TimeoutError("read timed out")       # the fallback host is down too

    t = nsr.refresh("2025-12-01", get_json=get, core_json=core, connect=lambda: conn, now=NOW)
    assert t["failed"] == ["202601"] and "202512" in t["fetched"]
    assert t["upsert"] == 3 and t["games_insert"] == 2          # QF and SF are regular; the final is not
    assert conn.committed == 1 and any("INSERT INTO nba_schedule" in w[0] for w in conn.writes)


def test_an_empty_answer_for_a_month_the_schedule_fills_is_a_failure_not_a_wipe():
    conn = _Conn(stored=[_stored("NBA_2026-01-05_TOR_WAS", "0022600500")])
    t = nsr.refresh("2025-12-01", get_json=lambda url, p: _board(p["dates"]),
                    connect=lambda: conn, now=NOW)
    assert "202601" in t["failed"] and "202601" not in t["fetched"]
    assert t["not_on_espn"] == 0


def test_a_run_stamps_every_row_espn_confirmed():
    """updated_at on the rows ESPN listed is the one thing the health check
    reads; without the stamp a working refresh reads as stopped after 36 hours.
    (tests/test_nba_schedule_refresh_pg.py runs the same write on Postgres.)"""
    conn = _Conn(stored=[_stored("NBA_2025-12-09_MIA_ORL", "0062500001", tip="2025-12-09T23:00:00+00:00")])
    t = nsr.refresh("2025-12-01", get_json=lambda url, p: _board(p["dates"]),
                    connect=lambda: conn, now=NOW)
    assert t["confirm"] == 1
    stamps = [p for s, p in conn.writes
              if s.startswith("UPDATE nba_schedule SET updated_at = NOW() WHERE nba_game_id = ANY")]
    assert stamps == [(["0062500001"],)]


def test_a_failed_write_rolls_back_and_is_reported():
    class _Broken(_Conn):
        def executemany(self, sql, rows):
            raise RuntimeError("connection reset")

    conn = _Broken()
    t = nsr.refresh("2025-12-01", get_json=lambda url, p: _board(p["dates"]),
                    connect=lambda: conn, now=NOW)
    assert t["error"] and conn.rolled_back >= 1 and conn.committed == 0


def test_a_dry_run_reads_and_writes_nothing():
    conn = _Conn()
    t = nsr.refresh("2025-12-01", get_json=lambda url, p: _board(p["dates"]),
                    connect=lambda: conn, now=NOW, dry_run=True)
    assert t["upsert"] == 3 and conn.writes == [] and conn.committed == 0


# ── the fallback host: sports.core.api.espn.com ──────────────────────────────
# site.api.espn.com answered the worker 403 on every day it was probed from
# 2026-08-08 to 2026-09-30 (system_health_checks, espn_wnba_api) while the core
# host kept serving it. A month the scoreboard refuses is read from the core
# host. Shapes: a trimmed copy of core documents fetched 2026-10-21
# (tests/fixtures/espn_nba_core_sample.json).

CORE = json.loads((FIX / "espn_nba_core_sample.json").read_text(encoding="utf-8"))


def _core(calls=None):
    def fetch(url):
        assert url.startswith("https://"), url             # ESPN's links say http://
        if calls is not None:
            calls.append(url)
        month = re.search(r"/events\?dates=(\d{6})&limit=1000$", url)
        if month:
            return CORE["listings"].get(month.group(1), {"count": 0, "pageCount": 1, "items": []})
        return CORE["docs"][url.split("?")[0]]               # KeyError: a document ESPN would 404
    return fetch


def _refused(url, params):
    raise ConnectionError("403 Client Error: Forbidden for url: https://site.api.espn.com/...")


def test_the_fallback_host_reads_the_same_games_as_the_scoreboard():
    """December 2025 from both hosts: the same games, ids, dates, types, tips,
    arenas and labels. The core host carries no status or broadcasts inline
    (each is one more link per game), so those stay empty."""
    core = _by_gid(nsr.event_rows(nsr.core_month("202512", _core(), {})))
    site = _by_gid(nsr.event_rows(_board("202512")))
    assert sorted(core) == sorted(site) == ["NBA_2025-12-09_MIA_ORL", "NBA_2025-12-13_NYK_ORL",
                                            "NBA_2025-12-16_SAS_NYK"]
    for gid in site:
        drop = ("status_text", "postponed", "national_tv")
        same = {k: v for k, v in core[gid].items() if k not in drop}
        assert same == {k: v for k, v in site[gid].items() if k not in drop}, gid
        assert core[gid]["status_text"] is None and core[gid]["postponed"] is False
    assert core["NBA_2025-12-16_SAS_NYK"]["game_type"] == "cup_final"


def test_the_fallback_types_a_play_in_and_skips_a_slot_with_no_teams():
    calls, counts = [], {}
    rows = nsr.event_rows(nsr.core_month("202604", _core(calls), {}))
    assert [(r["game_id"], r["game_type"], r["season"]) for r in rows] == [
        ("NBA_2026-04-14_MIA_CHA", "playin", 2026)]
    assert nsr.event_rows(nsr.core_month("202612", _core(calls), {}), counts) == []
    assert counts == {"no_teams": 1}
    assert not any("/teams/-" in u for u in calls)          # ESPN's -1 and -2 are not teams


def test_each_team_is_fetched_once_a_run():
    calls, teams = [], {}
    nsr.core_month("202512", _core(calls), teams)
    nsr.core_month("202512", _core(calls), teams)
    team_calls = [u for u in calls if "/teams/" in u]
    assert len(team_calls) == len(set(team_calls)) == 4     # ORL, MIA, NYK, SAS


def test_a_month_the_scoreboard_refuses_is_read_from_the_fallback_host():
    """This month and next only: read from this machine on 2026-10-21 a core
    month cost 209 calls and 170 seconds, so all nine months would add about
    18 minutes to the 6am run. A game more than a month out is not priced,
    and its month is read again by the time it is near. The months past the
    fallback's reach stay failed, so the step still goes red during a block."""
    conn = _Conn()
    t = nsr.refresh("2025-12-01", get_json=_refused, core_json=_core(), connect=lambda: conn, now=NOW)
    assert t["via_core"] == ["202512", "202601"] == t["months"][:nsr.CORE_MONTHS]
    assert t["failed"] == t["months"][nsr.CORE_MONTHS:] and "202604" in t["failed"]
    assert t["upsert"] == 3 and t["games_insert"] == 2      # QF, SF and final; QF and SF are regular
    assert conn.committed == 1


def test_a_month_the_fallback_host_breaks_on_is_failed_whole():
    """One document the core host does not answer fails its month: a month
    read in part would name every game it missed as no longer listed."""
    docs = dict(CORE["docs"])
    docs.pop(next(k for k in docs if k.endswith("/events/401809837")))

    def fetch(url):
        month = re.search(r"/events\?dates=(\d{6})", url)
        if month:
            return CORE["listings"].get(month.group(1), {"count": 0, "pageCount": 1, "items": []})
        return docs[url.replace("http://", "https://").split("?")[0]]

    t = nsr.refresh("2025-12-01", get_json=_refused, core_json=fetch, connect=lambda: _Conn(), now=NOW)
    assert "202512" in t["failed"] and "202512" not in t["via_core"] and "202601" in t["via_core"]


def test_a_listing_of_more_than_one_page_fails_its_month():
    def fetch(url):
        return {"count": 1200, "pageCount": 2, "items": []}

    with pytest.raises(ValueError):
        nsr.core_month("202512", fetch, {})


# ── the NBA.com load replaces an 'espn:' row ─────────────────────────────────

def test_the_leagues_own_load_removes_the_espn_row_of_every_game_it_writes():
    from data.ingestors import nba_schedule_ingestor as ing
    rows = [{"nba_game_id": "0022601210", "game_id": G2, "season": 2027, "game_type": "regular",
             "game_date": "2026-12-08", "commence_time": None, "home_team": "BOS", "away_team": "LAL",
             "home_score": None, "away_score": None, "status_text": None, "ot_periods": None,
             "arena_name": None, "arena_city": None, "arena_state": None, "is_neutral": False,
             "game_label": None, "game_sublabel": None, "national_tv": None}]

    class _Ing(_Conn):
        def execute(self, sql, params=()):
            if sql.strip().startswith("SELECT game_id FROM games"):
                self._rows = [(G2,)]
                return self
            return super().execute(sql, params)

    conn = _Ing()
    ing.write(conn, rows)
    deletes = [(s, p) for s, p in conn.writes if s.startswith("DELETE FROM nba_schedule")]
    assert deletes and deletes[0][1] == ("espn:%", [G2])


# ── wiring ───────────────────────────────────────────────────────────────────

def test_the_daily_pipeline_refreshes_the_schedule_before_the_nba_results_step():
    daily = PIPE[PIPE.index("def run_daily_pipeline"):]
    assert daily.index('results["nba_schedule"] = step_nba_schedule(run_date)') \
        < daily.index('results["nba_results"] = step_nba_results(run_date)')


def test_the_step_is_a_cli_choice_and_dispatches():
    assert '"nba-schedule"' in PIPE
    assert re.search(r'"nba-schedule":\s*lambda: step_nba_schedule\(run_date\)', PIPE)


@pytest.mark.parametrize("totals,ok", [
    ({"failed": [], "error": None, "fetched": ["202610"]}, True),
    ({"failed": ["202611"], "error": None, "fetched": ["202610"]}, False),
    ({"failed": [], "error": "RuntimeError: x", "fetched": ["202610"]}, False),
    ({"failed": [], "error": None, "fetched": []}, False),
])
def test_the_step_goes_red_on_any_failed_month(monkeypatch, totals, ok):
    import run_pipeline
    monkeypatch.setattr(nsr, "refresh", lambda run_date: dict(totals))
    assert run_pipeline.step_nba_schedule("2026-10-20") is ok


# ── the health check ─────────────────────────────────────────────────────────

class _HealthConn:
    def __init__(self, games_near, updated_at):
        self.games_near, self.updated_at = games_near, updated_at

    def execute(self, sql, params=()):
        self._row = (self.games_near,) if "FROM games" in sql else (self.updated_at,)
        return self

    def fetchone(self):
        return self._row


@pytest.mark.parametrize("games_near,age_h,status", [
    (12, 2, "OK"),
    (12, 40, "STALE"),            # no row confirmed for 40 hours while games are near
    (0, 400, "SKIPPED"),          # the offseason
])
def test_the_health_check_says_when_the_refresh_has_stopped(games_near, age_h, status):
    import tracking.system_health as sh
    r = sh.HealthReport("2026-10-20")
    ts = datetime.now(timezone.utc) - timedelta(hours=age_h)
    sh.check_nba_schedule_refresh(_HealthConn(games_near, ts), r, "2026-10-20")
    (res,) = [x for x in r.results if x["check_name"] == "nba_schedule_refresh"]
    assert res["status"] == status and res["severity"] == "WARN"
