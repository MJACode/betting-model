"""The NHL schedule refresh (data/ingestors/nhl_schedule_refresh.py) and its wiring.

Until 2026-10-22 an NHL game reached `games` only when a book listed it, about
a day ahead. These pin what the daily refresh reads from the NHL API, the id it
writes (the odds feed's, so the feed's later upsert lands on the same row),
what it never touches, that it fails open, the step's place in the 6am run and
the health check that says when it has stopped.

The API shapes are trimmed copies of two weekly answers fetched 2026-10-22
(tests/fixtures/nhl_api_schedule_sample.json).
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

import data.ingestors.nhl_schedule_refresh as nsr
from data.ingestors.odds_ingestor import _build_game_id, _normalize_team

ROOT = Path(__file__).parent.parent
FIX = json.loads((ROOT / "tests" / "fixtures" / "nhl_api_schedule_sample.json").read_text(encoding="utf-8"))
WEEK1, LAST_WEEK = FIX["2026-10-22"], FIX["2027-04-08"]
PIPE = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
NOW = datetime(2026, 10, 22, 10, 5, tzinfo=timezone.utc)          # the 6am ET run


def _listed(answer):
    return [(g, d["date"]) for d in answer["gameWeek"] for g in d["games"]]


def _rows(answer=WEEK1, now=NOW, counts=None):
    rows, ids = nsr.game_rows(_listed(answer), now, counts)
    return {r["game_id"]: r for r in rows}, ids


# ── the key ──────────────────────────────────────────────────────────────────

# The twelve NHL games the odds feed had stored for 2026-10-22 when this was
# written (production, read-only, 2026-10-22).
STORED_BY_THE_FEED_1022 = {
    "NHL_2026-10-22_ANA_NJD", "NHL_2026-10-22_CAR_EDM", "NHL_2026-10-22_DET_VAN",
    "NHL_2026-10-22_FLA_PIT", "NHL_2026-10-22_LAK_NYI", "NHL_2026-10-22_MIN_CGY",
    "NHL_2026-10-22_NSH_BOS", "NHL_2026-10-22_NYR_TOR", "NHL_2026-10-22_SJS_OTT",
    "NHL_2026-10-22_UTA_SEA", "NHL_2026-10-22_VGK_STL", "NHL_2026-10-22_WPG_DAL",
}


def test_the_ids_are_the_ones_the_odds_feed_stored():
    rows, _ = _rows()
    assert {g for g in rows if g.startswith("NHL_2026-10-22")} == STORED_BY_THE_FEED_1022


def test_the_id_is_built_as_the_odds_feed_builds_it_from_the_books_names():
    """The two writers must agree on every id, or a game becomes two rows. The
    feed: the ET date of the books' start, the full names through
    _normalize_team. The refresh: the ET date of startTimeUTC, the API's codes."""
    rows, _ = _rows()
    for away, home, start in (
            ("Utah Mammoth", "Seattle Kraken", "2026-10-23T02:10:00Z"),       # UTA, 10:10pm ET
            ("Los Angeles Kings", "New York Islanders", "2026-10-22T23:40:00Z"),
            ("Montréal Canadiens", "Winnipeg Jets", "2026-10-25T23:10:00Z"),  # neutral site
            ("Minnesota Wild", "Vancouver Canucks", "2026-10-26T02:10:00Z")):  # next day in UTC
        et = nsr.et_date(start)
        gid = _build_game_id("NHL", et, _normalize_team(away, "NHL"), _normalize_team(home, "NHL"))
        assert gid in rows, gid


def test_a_late_game_keeps_its_eastern_date_and_the_leagues_start():
    rows, _ = _rows()
    van = rows["NHL_2026-10-25_MIN_VAN"]                   # 02:00Z on the 26th is 10pm ET on the 25th
    assert van["commence_time"] == "2026-10-26T02:00:00Z"
    assert van["season"] == 2027 and van["neutral_site"] == 0
    assert rows["NHL_2026-10-25_MTL_WPG"]["neutral_site"] == 1


def test_what_is_not_stored():
    week = json.loads(json.dumps(WEEK1))
    games = week["gameWeek"][1]["games"]                    # 2026-10-23: MTL @ CHI, TBL @ COL
    pre = dict(games[0], id=1, gameType=1, homeTeam={"abbrev": "BOS"}, awayTeam={"abbrev": "PHI"})
    ppd = dict(games[0], id=2, gameScheduleState="PPD", homeTeam={"abbrev": "SEA"}, awayTeam={"abbrev": "SJS"})
    ifn = dict(games[0], id=3, gameType=3, ifNecessary=True, homeTeam={"abbrev": "NYR"}, awayTeam={"abbrev": "NJD"})
    odd = dict(games[0], id=4, homeTeam={"abbrev": "XYZ"}, awayTeam={"abbrev": "BOS"})
    live = dict(games[1], id=5, gameState="LIVE")
    games[:] = [games[0], pre, ppd, ifn, odd, live]
    counts: dict = {}
    rows, ids = _rows(week, counts=counts)
    day = {g for g in rows if g.startswith("NHL_2026-10-23")}
    assert day == {"NHL_2026-10-23_MTL_CHI"}
    assert counts == {"other_type": 1, "state_ppd": 1, "if_necessary": 1, "unknown_team": 1,
                      "started": 1}
    # A started game is still listed (never called gone); a postponed one is not.
    assert "NHL_2026-10-23_TBL_COL" in ids and "NHL_2026-10-23_SJS_SEA" not in ids


def test_a_game_that_has_started_by_the_clock_is_not_kept():
    rows, ids = _rows(now=datetime(2026, 10, 22, 23, 0, tzinfo=timezone.utc))
    assert "NHL_2026-10-22_NSH_BOS" not in rows and "NHL_2026-10-22_NSH_BOS" in ids
    assert "NHL_2026-10-22_LAK_NYI" in rows                 # 23:30Z


# ── the walk ─────────────────────────────────────────────────────────────────

def _api(pages: dict, fail_at: str | None = None):
    asked = []

    def get(url):
        asked.append(url)
        cursor = url.rsplit("/", 1)[1]
        if cursor == fail_at:
            raise TimeoutError("read timed out")
        return pages[cursor]
    return get, asked


def test_the_walk_follows_next_start_date_to_the_end_of_the_season():
    mid = json.loads(json.dumps(WEEK1))
    mid["nextStartDate"] = "2027-04-08"                      # a break is skipped by the API itself
    get, asked = _api({"2026-10-22": mid, "2027-04-08": LAST_WEEK})
    w = nsr.walk(date(2026, 10, 22), get, sleep=0)
    assert [u.rsplit("/", 1)[1] for u in asked] == ["2026-10-22", "2027-04-08"]
    assert w["weeks"] == 2 and w["failed"] is None and w["covered_to"] == "2027-04-14"
    assert w["meta"]["regularSeasonEndDate"] == "2027-04-10"


def test_the_walk_stops_past_the_playoffs():
    mid = json.loads(json.dumps(WEEK1))
    mid["nextStartDate"] = "2027-07-01"                      # after playoffEndDate 2027-06-10
    get, asked = _api({"2026-10-22": mid})
    w = nsr.walk(date(2026, 10, 22), get, sleep=0)
    assert len(asked) == 1 and w["failed"] is None


def test_a_week_that_fails_keeps_the_weeks_before_it():
    get, _ = _api({"2026-10-22": WEEK1}, fail_at="2026-10-29")
    w = nsr.walk(date(2026, 10, 22), get, sleep=0)
    assert w["weeks"] == 1 and w["covered_to"] == "2026-10-28"
    assert w["failed"].startswith("week of 2026-10-29: TimeoutError")


def test_the_walk_is_bounded():
    def get(url):
        cursor = date.fromisoformat(url.rsplit("/", 1)[1])
        page = json.loads(json.dumps(WEEK1))
        page["nextStartDate"] = (cursor + timedelta(days=7)).isoformat()
        page["playoffEndDate"] = "2099-01-01"
        return page
    w = nsr.walk(date(2026, 10, 22), get, sleep=0)
    assert w["calls"] == nsr.MAX_CALLS and "stopped at" in w["failed"]


# ── the plan ─────────────────────────────────────────────────────────────────

LIVE_START = "2026-10-24T17:10:00+00:00"       # the books' start: ten minutes after the league's


def _stored(gid, source=nsr.DATA_SOURCE, start=None, score=None):
    _, day, away, home = gid.split("_")
    return {"game_id": gid, "game_date": day, "home_team": home, "away_team": away,
            "commence_time": start, "data_source": source, "home_score": score}


def _plan(stored, rows=None, ids=None, covered=("2026-10-22", "2026-10-28"), now=NOW):
    if rows is None:
        r, ids_ = _rows()
        rows, ids = list(r.values()), ids_ if ids is None else ids
    return nsr.plan(rows, ids, stored, covered, now)


def test_a_game_games_lacks_is_inserted():
    p = _plan([])
    assert len(p["insert"]) == 27                            # every fixture game of the first week
    assert not (p["times"] or p["confirm"] or p["orphans"] or p["conflicts"])


def test_a_row_the_odds_feed_wrote_is_never_touched():
    """Its start is the books' (ten minutes after the league's): following the
    API would flip it back every morning."""
    p = _plan([_stored("NHL_2026-10-24_ANA_PHI", "live", LIVE_START)])
    assert "NHL_2026-10-24_ANA_PHI" not in [r["game_id"] for r in p["insert"]]
    assert not (p["times"] or p["confirm"] or p["orphans"])


def test_the_refreshs_own_row_follows_a_moved_start():
    p = _plan([_stored("NHL_2026-10-24_ANA_PHI", start="2026-10-24T23:00:00Z"),
               _stored("NHL_2026-10-24_LAK_NJD", start="2026-10-24T19:30:00Z")])
    assert p["times"] == [("NHL_2026-10-24_ANA_PHI", "2026-10-24T17:00:00Z", "2026-10-24T23:00:00Z")]
    assert p["confirm"] == ["NHL_2026-10-24_LAK_NJD"]       # unchanged: confirmed


def test_a_started_or_scored_own_row_is_never_touched():
    now = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)
    rows = [{"game_id": "NHL_2026-10-24_ANA_PHI", "season": 2027, "game_date": "2026-10-24",
             "home_team": "PHI", "away_team": "ANA", "commence_time": "2026-10-24T20:00:00Z",
             "neutral_site": 0}]
    p = nsr.plan(rows, {"NHL_2026-10-24_ANA_PHI"},
                 [_stored("NHL_2026-10-24_ANA_PHI", start="2026-10-24T17:00:00Z")],
                 ("2026-10-24", "2026-10-30"), now)
    assert not (p["times"] or p["confirm"] or p["orphans"] or p["insert"])
    p = _plan([_stored("NHL_2026-10-24_ANA_PHI", start="2026-10-24T23:00:00Z", score=3)])
    assert not (p["times"] or p["confirm"] or p["orphans"])


def test_a_game_moved_to_another_date_leaves_its_old_row_as_an_orphan():
    """The date is part of the id: the moved game is inserted under its new
    date's id, and the refresh's own row on the old date is removed."""
    p = _plan([_stored("NHL_2026-10-27_ANA_PHI", start="2026-10-27T23:00:00Z")])
    assert p["orphans"] == ["NHL_2026-10-27_ANA_PHI"]
    assert "NHL_2026-10-24_ANA_PHI" in [r["game_id"] for r in p["insert"]]


def test_an_orphan_is_only_ever_the_refreshs_own_future_row_inside_the_weeks_read():
    p = _plan([
        _stored("NHL_2026-10-27_ANA_PHI", "live", "2026-10-27T23:10:00+00:00"),   # the feed's
        _stored("NHL_2026-11-05_ANA_PHI", start="2026-11-05T23:00:00Z"),          # past the weeks read
        _stored("NHL_2026-10-21_ANA_PHI", start="2026-10-21T23:00:00Z"),          # already started
        _stored("NHL_2026-10-26_ANA_PHI", start="2026-10-26T23:00:00Z", score=2),  # scored
    ])
    assert p["orphans"] == []


def test_the_same_two_teams_that_day_under_another_id_is_not_inserted():
    """A feed that ever keys the home side differently (a neutral site) would
    otherwise give the game two rows."""
    p = _plan([_stored("NHL_2026-10-25_WPG_MTL", "live", "2026-10-25T23:10:00+00:00")])
    assert ("NHL_2026-10-25_MTL_WPG", "NHL_2026-10-25_WPG_MTL") in p["conflicts"]
    assert "NHL_2026-10-25_MTL_WPG" not in [r["game_id"] for r in p["insert"]]


def test_an_own_row_still_unlisted_by_any_book_near_puck_drop_is_named():
    p = _plan([_stored("NHL_2026-10-22_NSH_BOS", start="2026-10-22T23:00:00Z"),
               _stored("NHL_2026-10-25_FLA_CHI", start="2026-10-25T19:00:00Z")])
    assert p["unlisted_soon"] == ["NHL_2026-10-22_NSH_BOS"]


# ── the run ──────────────────────────────────────────────────────────────────

class _Conn:
    """Records what the run sends; answers the one read with `stored`."""

    def __init__(self, stored=()):
        self.stored = list(stored)
        self.writes: list = []
        self.committed = self.rolled_back = 0

    def execute(self, sql, params=None):
        self._last = " ".join(sql.split())
        if not self._last.startswith("SELECT"):
            self.writes.append((self._last, params))
        return self

    def executemany(self, sql, rows):
        self.writes.append((" ".join(sql.split()), list(rows)))

    def fetchall(self):
        if self._last.startswith("SELECT game_id, game_date"):
            return [tuple(s[c] for c in nsr._STORED_COLS) for s in self.stored]
        if self._last.startswith("DELETE"):
            return [("deleted",)]
        return []

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


def _run(conn, pages=None, fail_at=None, **kw):
    get, _ = _api(pages or {"2026-10-22": dict(WEEK1, nextStartDate=None)}, fail_at)
    return nsr.refresh("2026-10-22", get_json=get, connect=lambda: conn, now=NOW, sleep=0, **kw)


def test_a_run_writes_its_plan_once():
    conn = _Conn([_stored("NHL_2026-10-24_LAK_NJD", start="2026-10-24T19:30:00Z")])
    t = _run(conn)
    assert nsr.step_ok(t) and t["insert"] == 26 and t["confirm"] == 1
    inserts = [w for w in conn.writes if w[0].startswith("INSERT INTO games")]
    assert len(inserts) == 1 and "ON CONFLICT (game_id) DO NOTHING" in inserts[0][0]
    assert all(row[-1] == nsr.DATA_SOURCE for row in inserts[0][1])
    assert conn.committed == 1


def test_every_update_and_delete_names_the_row_as_the_refreshs_own():
    """A row the odds feed reaches between the read and the write is the
    feed's: the guard is in the statement, not only in the plan."""
    for sql in (nsr._TIMES, nsr._CONFIRM, nsr._DELETE):
        flat = " ".join(sql.split())
        assert "data_source = %s" in flat and "home_score IS NULL" in flat and "'NHL'" in flat
    flat = " ".join(nsr._DELETE.split())
    assert "NOT EXISTS (SELECT 1 FROM odds" in flat and "NOT EXISTS (SELECT 1 FROM picks" in flat


def test_an_api_that_does_not_answer_writes_nothing():
    opened = []
    t = nsr.refresh("2026-10-22", get_json=_api({}, fail_at="2026-10-22")[0],
                    connect=lambda: opened.append(1), now=NOW, sleep=0)
    assert t["failed"] and not t["weeks"] and opened == []
    assert not nsr.step_ok(t)


def test_a_week_that_fails_mid_walk_fails_the_step_but_writes_the_weeks_read():
    conn = _Conn()
    t = _run(conn, pages={"2026-10-22": WEEK1}, fail_at="2026-10-29")
    assert t["insert"] == 27 and conn.committed == 1 and not nsr.step_ok(t)


def test_an_empty_answer_over_stored_games_removes_nothing():
    empty = json.loads(json.dumps(WEEK1))
    empty["nextStartDate"] = None
    for d in empty["gameWeek"]:
        d["games"] = []
    conn = _Conn([_stored("NHL_2026-10-27_ANA_PHI", start="2026-10-27T23:00:00Z")])
    t = _run(conn, pages={"2026-10-22": empty})
    assert t["orphans"] == 0 and not any(w[0].startswith("DELETE") for w in conn.writes)
    assert not nsr.step_ok(t)


def test_more_vanished_rows_than_postponements_explain_are_kept_and_fail_the_step():
    gone = [_stored(f"NHL_2026-10-2{d}_ANA_{h}", start=f"2026-10-2{d}T23:00:00Z")
            for d in range(3, 9) for h in ("BUF", "DET")]
    assert len(gone) > nsr.MAX_ORPHAN_DELETES
    conn = _Conn(gone)
    t = _run(conn)
    assert t["orphans_held"] == len(gone) and t["orphans"] == 0
    assert not any(w[0].startswith("DELETE") for w in conn.writes)
    assert not nsr.step_ok(t)


def test_a_dry_run_writes_nothing():
    conn = _Conn()
    t = _run(conn, dry_run=True)
    assert t["plan"]["insert"] and conn.writes == [] and conn.rolled_back == 1


def test_a_failed_write_is_rolled_back_and_reported():
    class Broken(_Conn):
        def executemany(self, sql, rows):
            raise RuntimeError("deadlock detected")
    conn = Broken()
    t = _run(conn)
    assert t["error"].startswith("RuntimeError") and conn.rolled_back == 1 and conn.committed == 0
    assert not nsr.step_ok(t)


# ── the step and its place in the 6am run ────────────────────────────────────

def test_the_daily_run_refreshes_the_nhl_schedule():
    daily = PIPE[PIPE.index("def run_daily_pipeline"):]
    assert 'results["nhl_schedule"] = step_nhl_schedule(run_date)' in daily
    assert '"nhl-schedule"' in PIPE
    assert re.search(r'"nhl-schedule":\s*lambda: step_nhl_schedule\(run_date\)', PIPE)


@pytest.mark.parametrize("totals,ok", [
    ({"failed": None, "error": None, "weeks": 25, "orphans_held": 0}, True),
    ({"failed": "week of 2026-10-29: TimeoutError", "error": None, "weeks": 1, "orphans_held": 0}, False),
    ({"failed": None, "error": "RuntimeError: x", "weeks": 25, "orphans_held": 0}, False),
    ({"failed": None, "error": None, "weeks": 0, "orphans_held": 0}, False),
    ({"failed": None, "error": None, "weeks": 25, "orphans_held": 9}, False),
])
def test_the_step_reports_a_refresh_that_did_not_finish(monkeypatch, totals, ok):
    import run_pipeline
    monkeypatch.setattr(nsr, "refresh", lambda run_date: dict(totals))
    assert run_pipeline.step_nhl_schedule("2026-10-22") is ok


# ── the readers that act on a game skip a row no book has listed ─────────────

def test_the_marker_the_readers_skip_is_the_one_the_refresh_writes():
    assert nsr.listed_by_a_book() == "COALESCE(data_source, '') <> 'nhl_schedule'"
    assert nsr.listed_by_a_book("g") == "COALESCE(g.data_source, '') <> 'nhl_schedule'"
    assert nsr.DATA_SOURCE == "nhl_schedule"


def test_the_prop_purchase_does_not_buy_a_game_only_the_schedule_holds(monkeypatch):
    """The prop-odds step buys for today's events the Odds API lists, if the
    game has a `games` row. A game no book lists game lines for had no row
    before the refresh and was skipped; with the refresh's row it still is."""
    import data.ingestors.nhl_prop_odds_ingestor as ing
    start = datetime(2026, 10, 22, 23, 0, tzinfo=timezone.utc)
    bought = []

    class Conn:
        def commit(self):
            pass

        def close(self):
            pass

    gid = "NHL_2026-10-22_NSH_BOS"
    monkeypatch.setattr(ing, "ODDS_API_KEY", "test")
    monkeypatch.setattr(ing, "_events", lambda _today: ([{
        "id": "ev", "home": "Boston Bruins", "away": "Nashville Predators", "start": start}], 0))
    monkeypatch.setattr(ing, "_existing_game_ids", lambda _conn, ids: set(ids))
    monkeypatch.setattr(ing, "_schedule_only_ids", lambda _conn, ids: {gid} & set(ids))
    monkeypatch.setattr(ing, "_stored_snapshots", lambda _conn, ids: ({g: [] for g in ids}, set()))
    monkeypatch.setattr(ing, "_event_props", lambda event_id: bought.append(event_id) or ([], 0))
    monkeypatch.setattr(ing, "get_connection", lambda: Conn())
    monkeypatch.setattr(ing, "persist_quota", lambda _conn: None)
    import models.nhl_goalie_gate as gate
    monkeypatch.setattr(gate, "known_games", lambda _conn, ids: {})
    out = ing.run_nhl_prop_odds_ingestor(now=datetime(2026, 10, 22, 14, 0, tzinfo=timezone.utc))
    assert bought == [] and out["unknown_games"] == 1 and out["open"] == 0
