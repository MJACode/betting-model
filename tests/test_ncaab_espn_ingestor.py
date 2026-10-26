"""The NCAAB schedule/results ingestor (data/ingestors/ncaab_espn_ingestor.py)
and its wiring into the daily pipeline and the refresh pass.

Fixtures are REAL ESPN payloads, trimmed (fetched 2026-10-26, tests/fixtures/ncaab_espn/):
  scoreboard_2025-11-27.json  Thanksgiving 2025: Richmond @ Furman (neutral;
                              Furman is D1 but absent from ESPN's groups list),
                              South Florida @ Western Kentucky 97-91 in
                              overtime (neutral, period 3), and Oklahoma State
                              @ Northwestern, tipped 03:51Z = 22:51 ET on the
                              27th (the late-tip date rule).
  scoreboard_2026-11-03.json  Bethesda (not D1) @ Pacific with no tip time yet
                              (timeValid false, ESPN's 05:00Z stamp), and
                              Manhattan @ Kentucky, scheduled.
  teams.json / groups.json    /teams?groups=50 and the groups listing, trimmed;
                              groups carries Queens, which /teams lacks.

The SQL runs on sqlite through a shim that maps %s and NOW() (the module's SQL
is written to stay inside what both engines accept), so these tests exercise
real state: a moved event keeps its id, a stored score stays stored.
"""
from __future__ import annotations

import copy
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from data.db_setup import SCHEMA_SQL
from data.ingestors import ncaab_espn_ingestor as ing
from data.ingestors import ncaab_teams as nt

ROOT = Path(__file__).parent.parent
FIX = Path(__file__).parent / "fixtures" / "ncaab_espn"


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


BOARD_1127 = _load("scoreboard_2025-11-27.json")
BOARD_1103 = _load("scoreboard_2026-11-03.json")
TEAMS = _load("teams.json")
GROUPS = _load("groups.json")

AFTER_1127 = datetime(2025, 11, 28, 12, 0, tzinfo=timezone.utc)


# ── a sqlite stand-in for data.db.DBConnection ───────────────────────────────

def _lite(sql: str) -> str:
    return (sql.replace("NOW()::TEXT", "CURRENT_TIMESTAMP")
               .replace("NOW()", "CURRENT_TIMESTAMP").replace("%s", "?"))


class LiteConn:
    """execute / executemany / commit / rollback over sqlite3, recording every
    write statement so a test can assert that a repeat pass wrote nothing."""

    def __init__(self):
        self.sq = sqlite3.connect(":memory:")
        self.sq.executescript(SCHEMA_SQL)
        for ddl in (nt.TEAMS_DDL, nt.EVENTS_DDL, nt.EVENTS_INDEX_DDL, nt.VENUES_DDL):
            self.sq.execute(_lite(ddl))
        self.sq.commit()
        self.writes: list[str] = []
        self.commits = 0

    def _note(self, sql):
        head = sql.strip().split(None, 1)[0].upper()
        if head in ("INSERT", "UPDATE", "DELETE"):
            self.writes.append(" ".join(sql.split()))

    def execute(self, sql, params=()):
        self._note(sql)
        return self.sq.execute(_lite(sql), tuple(params or ()))

    def executemany(self, sql, rows):
        self._note(sql)
        self.sq.executemany(_lite(sql), [tuple(r) for r in rows])

    def commit(self):
        self.commits += 1
        self.sq.commit()

    def rollback(self):
        self.sq.rollback()

    def close(self):
        pass

    def q(self, sql, params=()):
        return self.sq.execute(sql, params).fetchall()


class Espn:
    """A fake get_json: boards by YYYYMMDD, plus /teams and groups. Records calls."""

    def __init__(self, boards=None):
        self.boards = dict(boards or {})
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url, params):
        self.calls.append((url, dict(params)))
        if url == ing.TEAMS_URL:
            return copy.deepcopy(TEAMS)
        if url == ing.GROUPS_URL:
            return copy.deepcopy(GROUPS)
        if url == ing.SCOREBOARD_URL:
            return copy.deepcopy(self.boards.get(params["dates"], {"events": []}))
        raise AssertionError(f"unexpected URL {url}")

    def scoreboard_dates(self):
        return [p["dates"] for u, p in self.calls if u == ing.SCOREBOARD_URL]


@pytest.fixture(autouse=True)
def _no_ddl_and_no_cache(monkeypatch):
    """The tables already exist in LiteConn; ensure_tables' catalog reads are
    Postgres-only. And the resolver's process cache must not leak between tests."""
    monkeypatch.setattr(nt, "ensure_tables", lambda conn: None)
    nt.reset_registry_cache()
    yield
    nt.reset_registry_cache()


@pytest.fixture
def conn():
    return LiteConn()


def _game(conn, game_id):
    rows = conn.q("SELECT game_id, sport, season, game_date, home_team, away_team, "
                  "home_score, away_score, home_win, went_to_ot, regulation_tie, "
                  "commence_time, neutral_site, conference_game, venue_id, data_source "
                  "FROM games WHERE game_id = ?", (game_id,))
    if not rows:
        return None
    keys = ("game_id", "sport", "season", "game_date", "home_team", "away_team",
            "home_score", "away_score", "home_win", "went_to_ot", "regulation_tie",
            "commence_time", "neutral_site", "conference_game", "venue_id", "data_source")
    return dict(zip(keys, rows[0]))


def _event(board, event_id):
    return next(e for e in board["events"] if e["id"] == str(event_id))


def _board_with(board, event_id, fn):
    b = copy.deepcopy(board)
    fn(_event(b, event_id))
    return b


USF_WKU = "NCAAB_2025-11-27_south-florida_western-kentucky"
OKST_NW = "NCAAB_2025-11-27_oklahoma-state_northwestern"
RICH_FUR = "NCAAB_2025-11-27_richmond_furman"
MAN_UK = "NCAAB_2026-11-03_manhattan_kentucky"
BETH_PAC = "NCAAB_2026-11-03_bethesda_pacific"


# ── parsing ──────────────────────────────────────────────────────────────────

def test_an_overtime_neutral_site_final_parses_in_espns_orientation():
    p = ing.parse_event(_event(BOARD_1127, 401830875))
    assert p["home"]["school"] == "Western Kentucky" and p["away"]["school"] == "South Florida"
    assert (p["home_score"], p["away_score"]) == (91, 97)
    assert p["final"] and p["period"] == 3 and p["went_to_ot"] == 1
    assert p["neutral_site"] is True and p["conference_game"] is False
    assert p["season"] == 2026 and p["season_type"] == 2
    assert p["commence_time"] == "2025-11-27T22:30:00Z"
    assert p["venue"] == {"venue_id": 2761, "name": p["venue"]["name"], "city": p["venue"]["city"],
                          "state": p["venue"]["state"], "indoor": True}
    assert p["notes"] == "Marriott Bonvoy Battle 4 Atlantis"
    assert p["status"] == "STATUS_FINAL" and p["off"] is False


def test_a_late_tip_files_on_its_eastern_date():
    p = ing.parse_event(_event(BOARD_1127, 401812276))
    assert p["commence_time"] == "2025-11-28T03:51:00Z"
    assert p["game_date"] == "2025-11-27"              # 22:51 ET on the 27th


def test_a_tbd_tip_has_no_commence_time_but_keeps_its_date():
    p = ing.parse_event(_event(BOARD_1103, 401917511))
    assert p["commence_time"] is None                  # not ESPN's midnight stamp
    assert p["game_date"] == "2026-11-03" and p["season"] == 2027
    assert not p["final"] and p["home_score"] is None


def test_in_progress_scores_are_never_final():
    b = _board_with(BOARD_1127, 401830875, lambda e: e["competitions"][0]["status"].update(
        {"period": 2, "type": {"name": "STATUS_IN_PROGRESS", "state": "in", "completed": False}}))
    p = ing.parse_event(_event(b, 401830875))
    assert not p["final"] and p["home_score"] is None and p["away_score"] is None


def test_an_event_without_two_real_teams_is_dropped():
    b = _board_with(BOARD_1127, 401830875, lambda e: e["competitions"][0]["competitors"][0]
                    .update(team={"id": "-1", "location": "TBD", "displayName": "TBD"}))
    assert ing.parse_event(_event(b, 401830875)) is None


# ── teams and slugs ──────────────────────────────────────────────────────────

def test_d1_is_the_union_of_teams_and_groups():
    d1 = {t["espn_id"]: t for t in ing.merge_d1(TEAMS, GROUPS)}
    assert set(d1) == {96, 2363, 279, 231, 257, 58, 98, 197, 77, 2511}
    assert d1[96]["conference"] == "Southeastern Conference"
    assert d1[231]["conference"] is None               # Furman: groups omits the SoCon
    queens = d1[2511]                                  # groups only, no location
    assert queens["school"] == "Queens University" and queens["keep_school"] is True
    assert queens["conference"] == "Atlantic Sun Conference"
    assert all(t["is_d1"] for t in d1.values())


def test_refresh_teams_writes_the_registry(conn):
    out = ing.refresh_teams(conn, get_json=Espn())
    assert out["d1_teams"] == 10 and out["added"] == 10 and out["groups_only"] == 1
    rows = {r[0]: r[1:] for r in conn.q(
        "SELECT espn_id, school, slug, is_d1, conference FROM ncaab_teams")}
    assert rows[96] == ("Kentucky", "kentucky", 1, "Southeastern Conference")
    assert rows[2511][:3] == ("Queens University", "queens-university", 1)


def test_a_colliding_slug_gets_the_espn_id_and_never_moves(conn):
    taken = {"kentucky": 96}
    assert ing.assign_slug("Kentucky", 999, taken) == "kentucky-999"
    assert ing.assign_slug("Kentucky", 96, taken) == "kentucky"
    # Two new teams in one batch cannot collide with each other either.
    batch = {}
    assert ing.assign_slug("Saint Mary's", 1, batch) == "saint-mary-s"
    assert ing.assign_slug("Saint Mary’s", 2, batch) == "saint-mary-s-2"

    ing.refresh_teams(conn, get_json=Espn())
    # A non-D1 opponent whose school slugs like a D1 one: the later id is suffixed.
    ing.upsert_teams(conn, [{"espn_id": 4444, "school": "Kentucky", "mascot": "Knights"}],
                     ing._registry(conn))
    assert conn.q("SELECT slug, is_d1 FROM ncaab_teams WHERE espn_id = 4444") == [("kentucky-4444", 0)]
    # ESPN renames a school: the school follows, the slug (in every game_id) stays.
    renamed = copy.deepcopy(TEAMS)
    for item in renamed["sports"][0]["leagues"][0]["teams"]:
        if item["team"]["id"] == "96":
            item["team"]["location"] = "Kentucky Commonwealth"
    espn = Espn()
    espn_teams = lambda url, params: renamed if url == ing.TEAMS_URL else espn(url, params)  # noqa: E731
    ing.refresh_teams(conn, get_json=espn_teams)
    assert conn.q("SELECT school, slug FROM ncaab_teams WHERE espn_id = 96") == \
        [("Kentucky Commonwealth", "kentucky")]


def test_a_scoreboard_sighting_never_downgrades_d1_and_refresh_upgrades(conn):
    # First seen on a scoreboard (no D1 list yet): stored as not D1.
    ing.upsert_teams(conn, [{"espn_id": 231, "school": "Furman", "mascot": "Paladins"}], {})
    assert conn.q("SELECT is_d1 FROM ncaab_teams WHERE espn_id = 231") == [(0,)]
    ing.refresh_teams(conn, get_json=Espn())
    assert conn.q("SELECT is_d1, slug FROM ncaab_teams WHERE espn_id = 231") == [(1, "furman")]
    # A later scoreboard-shaped write of a D1 school leaves it D1.
    ing.upsert_teams(conn, [{"espn_id": 231, "school": "Furman"}], ing._registry(conn))
    assert conn.q("SELECT is_d1 FROM ncaab_teams WHERE espn_id = 231") == [(1,)]


# ── one day ──────────────────────────────────────────────────────────────────

def test_a_day_writes_games_events_and_venues(conn):
    espn = Espn({"20251127": BOARD_1127})
    t = ing.ingest_day(conn, "2025-11-27", get_json=espn)
    assert t["games_inserted"] == 3 and t["scores_filled"] == 3 and not t["failed"]
    g = _game(conn, USF_WKU)
    assert g["sport"] == "NCAAB" and g["data_source"] == "espn" and g["season"] == 2026
    assert (g["home_team"], g["away_team"]) == ("Western Kentucky", "South Florida")
    assert (g["home_score"], g["away_score"], g["home_win"]) == (91, 97, 0)
    assert (g["went_to_ot"], g["regulation_tie"]) == (1, 1)
    assert (g["neutral_site"], g["conference_game"], g["venue_id"]) == (1, 0, 2761)
    assert g["commence_time"] == "2025-11-27T22:30:00Z"
    fur = _game(conn, RICH_FUR)
    assert (fur["home_score"], fur["away_score"], fur["home_win"], fur["went_to_ot"]) == (73, 72, 1, 0)
    assert _game(conn, OKST_NW)["game_date"] == "2025-11-27"
    ev = conn.q("SELECT game_id, home_espn_id, away_espn_id, status, neutral_site "
                "FROM ncaab_events WHERE espn_event_id = 401830875")
    assert ev == [(USF_WKU, 98, 58, "STATUS_FINAL", 1)]
    assert conn.q("SELECT venue_id, city, indoor FROM ncaab_venues WHERE venue_id = 2761") == \
        [(2761, "Nassau", 1)]
    # the D1 registry was loaded first (no D1 row existed), then the board
    assert espn.calls[0][0] == ing.TEAMS_URL and espn.scoreboard_dates() == ["20251127"]


def test_a_repeat_of_the_same_day_writes_nothing(conn):
    espn = Espn({"20251127": BOARD_1127})
    ing.ingest_day(conn, "2025-11-27", get_json=espn)
    conn.writes.clear()
    t = ing.ingest_day(conn, "2025-11-27", get_json=espn)
    assert t["unchanged"] == 3 and t["games_inserted"] == t["games_updated"] == 0
    assert conn.writes == []


def test_a_non_d1_opponent_and_a_tbd_tip(conn):
    ing.ingest_day(conn, "2026-11-03", get_json=Espn({"20261103": BOARD_1103}))
    assert conn.q("SELECT school, slug, is_d1 FROM ncaab_teams WHERE espn_id = 3246") == \
        [("Bethesda", "bethesda", 0)]
    g = _game(conn, BETH_PAC)
    assert g["commence_time"] is None and g["game_date"] == "2026-11-03" and g["season"] == 2027
    assert _game(conn, MAN_UK)["commence_time"] == "2026-11-04T00:00:00Z"


def test_a_moved_event_keeps_its_game_id(conn):
    espn = Espn({"20261103": BOARD_1103})
    ing.ingest_day(conn, "2026-11-03", get_json=espn)
    # ESPN moves Manhattan @ Kentucky (same event id) to the next night.
    moved = _board_with(BOARD_1103, 401921801, lambda e: (
        e.update(date="2026-11-05T00:30Z"), e["competitions"][0].update(date="2026-11-05T00:30Z")))
    moved["events"] = [_event(moved, 401921801)]
    espn.boards["20261104"] = moved
    t = ing.ingest_day(conn, "2026-11-04", get_json=espn)
    assert t["moved"] == 1 and t["games_inserted"] == 0
    g = _game(conn, MAN_UK)                            # the id still says 11-03
    assert g["game_date"] == "2026-11-04" and g["commence_time"] == "2026-11-05T00:30:00Z"
    assert conn.q("SELECT count(*) FROM games WHERE sport = 'NCAAB'") == [(2,)]
    assert conn.q("SELECT game_id, game_date FROM ncaab_events WHERE espn_event_id = 401921801") \
        == [(MAN_UK, "2026-11-04")]


def test_a_tbd_sighting_keeps_a_tip_already_stored_on_that_date(conn):
    espn = Espn({"20261103": BOARD_1103})
    ing.ingest_day(conn, "2026-11-03", get_json=espn)
    espn.boards["20261103"] = _board_with(
        BOARD_1103, 401921801, lambda e: e["competitions"][0].update(timeValid=False))
    ing.ingest_day(conn, "2026-11-03", get_json=espn)
    assert _game(conn, MAN_UK)["commence_time"] == "2026-11-04T00:00:00Z"


def test_a_stored_score_is_never_overwritten(conn):
    espn = Espn({"20251127": BOARD_1127})
    ing.ingest_day(conn, "2025-11-27", get_json=espn)

    def rescore(e):
        for c in e["competitions"][0]["competitors"]:
            c["score"] = "99" if c["homeAway"] == "home" else "97"
    espn.boards["20251127"] = _board_with(BOARD_1127, 401830875, rescore)
    t = ing.ingest_day(conn, "2025-11-27", get_json=espn)
    assert t["score_conflicts"] == 1 and t["scores_filled"] == 0
    g = _game(conn, USF_WKU)
    assert (g["home_score"], g["away_score"], g["home_win"]) == (91, 97, 0)


def test_scores_fill_once_the_game_goes_final(conn):
    pre = _board_with(BOARD_1127, 401830875, lambda e: e["competitions"][0]["status"].update(
        {"period": 0, "type": {"name": "STATUS_SCHEDULED", "state": "pre", "completed": False}}))
    espn = Espn({"20251127": pre})
    ing.ingest_day(conn, "2025-11-27", get_json=espn)
    assert _game(conn, USF_WKU)["home_score"] is None
    espn.boards["20251127"] = BOARD_1127
    t = ing.ingest_day(conn, "2025-11-27", get_json=espn)
    assert t["scores_filled"] == 1
    assert (_game(conn, USF_WKU)["home_score"], _game(conn, USF_WKU)["away_score"]) == (91, 97)


def _postpone(e):
    e["competitions"][0]["status"].update(
        {"period": 0, "type": {"name": "STATUS_POSTPONED", "state": "post", "completed": False}})


def test_postponed_on_first_sight_writes_no_games_row(conn):
    b = _board_with(BOARD_1103, 401921801, _postpone)
    t = ing.ingest_day(conn, "2026-11-03", get_json=Espn({"20261103": b}))
    assert t["postponed_unseen"] == 1 and _game(conn, MAN_UK) is None
    assert conn.q("SELECT count(*) FROM ncaab_events WHERE espn_event_id = 401921801") == [(0,)]


def test_a_postponed_game_records_its_status_and_is_never_due(conn):
    espn = Espn({"20261103": BOARD_1103})
    ing.ingest_day(conn, "2026-11-03", get_json=espn)
    espn.boards["20261103"] = _board_with(BOARD_1103, 401921801, _postpone)
    t = ing.ingest_day(conn, "2026-11-03", get_json=espn)
    assert t["postponed"] == 1
    assert conn.q("SELECT status FROM ncaab_events WHERE espn_event_id = 401921801") == \
        [("STATUS_POSTPONED",)]
    assert _game(conn, MAN_UK)["home_score"] is None
    # the next day, Kentucky's game is past and unscored but postponed: not due.
    # (Pacific's TBD game on the same date still is.)
    conn.sq.execute("UPDATE games SET home_score = 80, away_score = 60 WHERE game_id = ?",
                    (BETH_PAC,))
    later = datetime(2026, 11, 4, 18, 0, tzinfo=timezone.utc)
    assert ing.due_dates(conn, "2026-11-04", later) == []


def test_a_second_event_for_the_same_game_is_refused(conn):
    dup = copy.deepcopy(BOARD_1103)
    twin = copy.deepcopy(_event(dup, 401921801))
    twin["id"] = "401999999"
    dup["events"].append(twin)
    t = ing.ingest_day(conn, "2026-11-03", get_json=Espn({"20261103": dup}))
    assert t["id_collisions"] == 1 and t["games_inserted"] == 2
    assert conn.q("SELECT espn_event_id FROM ncaab_events WHERE game_id = ?", (MAN_UK,)) == \
        [(401921801,)]


def test_an_orientation_change_on_a_stored_event_is_not_written(conn):
    espn = Espn({"20261103": BOARD_1103})
    ing.ingest_day(conn, "2026-11-03", get_json=espn)

    def flip(e):
        for c in e["competitions"][0]["competitors"]:
            c["homeAway"] = "away" if c["homeAway"] == "home" else "home"
    espn.boards["20261103"] = _board_with(BOARD_1103, 401921801, flip)
    t = ing.ingest_day(conn, "2026-11-03", get_json=espn)
    assert t["teams_changed"] == 1
    assert conn.q("SELECT home_espn_id, away_espn_id FROM ncaab_events "
                  "WHERE espn_event_id = 401921801") == [(96, 2363)]


def test_one_bad_event_does_not_lose_the_rest_of_the_day(conn, monkeypatch):
    real = ing._one_event

    def flaky(conn_, p, *a, **k):
        if p["espn_event_id"] == 401812276:
            raise RuntimeError("boom")
        return real(conn_, p, *a, **k)
    monkeypatch.setattr(ing, "_one_event", flaky)
    t = ing.ingest_day(conn, "2025-11-27", get_json=Espn({"20251127": BOARD_1127}))
    assert t["errors"] == 1 and t["failed"] == ["2025-11-27:401812276"]
    assert t["games_inserted"] == 2 and _game(conn, OKST_NW) is None


# ── the refresh-pass step costs nothing when nothing is due ──────────────────

@pytest.fixture
def no_http(monkeypatch):
    import requests

    def refuse(*a, **k):
        raise AssertionError("an HTTP call was made")
    monkeypatch.setattr(requests, "get", refuse)
    monkeypatch.setattr(requests.Session, "request", refuse)


def test_run_results_makes_no_http_call_on_an_empty_database(conn, no_http):
    t = ing.run_results("2026-11-03", now=datetime(2026, 11, 3, 23, tzinfo=timezone.utc),
                        connect=lambda: conn)
    assert t["dates"] == 0 and t["dates_fetched"] == 0 and not t["failed"]


def test_run_results_makes_no_http_call_before_tip_or_after_the_scores(conn, no_http):
    ing.ingest_day(conn, "2026-11-03", get_json=Espn({"20261103": BOARD_1103}))
    conn.sq.execute("UPDATE games SET commence_time = '2026-11-03T23:00:00Z' WHERE game_id = ?",
                    (BETH_PAC,))
    # 2026-11-02 evening ET: nothing on the 3rd has started, the TBD tip now has a time
    t = ing.run_results("2026-11-02", now=datetime(2026, 11, 2, 23, tzinfo=timezone.utc),
                        connect=lambda: conn)
    assert t["dates_fetched"] == 0
    # both games scored: nothing due on the 4th either
    conn.sq.execute("UPDATE games SET home_score = 70, away_score = 60 WHERE sport = 'NCAAB'")
    t = ing.run_results("2026-11-04", now=datetime(2026, 11, 4, 18, tzinfo=timezone.utc),
                        connect=lambda: conn)
    assert t["dates_fetched"] == 0


def test_run_results_fetches_only_the_due_date_and_fills_it(conn):
    pre = copy.deepcopy(BOARD_1127)
    for e in pre["events"]:
        e["competitions"][0]["status"].update(
            {"period": 0, "type": {"name": "STATUS_SCHEDULED", "state": "pre", "completed": False}})
    ing.ingest_day(conn, "2025-11-27", get_json=Espn({"20251127": pre}))
    espn = Espn({"20251127": BOARD_1127})
    t = ing.run_results("2025-11-28", now=AFTER_1127, connect=lambda: conn, get_json=espn, sleep=0)
    assert espn.scoreboard_dates() == ["20251127"]
    assert espn.calls == [(ing.SCOREBOARD_URL, {"dates": "20251127", "groups": "50",
                                                "limit": 500})]
    assert t["scores_filled"] == 3 and not t["failed"]
    assert _game(conn, OKST_NW)["home_score"] == 81


def test_a_tbd_tip_is_due_once_its_date_is_live_or_past(conn):
    ing.ingest_day(conn, "2026-11-03", get_json=Espn({"20261103": BOARD_1103}))
    conn.sq.execute("UPDATE games SET home_score = 1, away_score = 0 WHERE game_id = ?", (MAN_UK,))
    # the day before: not due
    assert ing.due_dates(conn, "2026-11-02", datetime(2026, 11, 2, 23, tzinfo=timezone.utc)) == []
    # on the day (a live-slate date): due, there is no other way to learn it tipped
    assert ing.due_dates(conn, "2026-11-03", datetime(2026, 11, 3, 15, tzinfo=timezone.utc)) == \
        ["2026-11-03"]
    # the day after: still due until ESPN has the final
    assert ing.due_dates(conn, "2026-11-04", datetime(2026, 11, 4, 18, tzinfo=timezone.utc)) == \
        ["2026-11-03"]


def test_the_due_window_is_bounded(conn):
    ing.ingest_day(conn, "2025-11-27", get_json=Espn({"20251127": BOARD_1127}))
    conn.sq.execute("UPDATE games SET home_score = NULL, away_score = NULL")
    assert ing.due_dates(conn, "2025-11-28", AFTER_1127) == ["2025-11-27"]
    far = datetime(2025, 12, 20, 12, tzinfo=timezone.utc)
    assert ing.due_dates(conn, "2025-12-20", far) == []     # past HEAL_DAYS


def test_a_failed_date_is_reported_and_the_rest_still_run(conn):
    pre = copy.deepcopy(BOARD_1103)
    ing.ingest_day(conn, "2026-11-03", get_json=Espn({"20261103": pre}))

    def broken(url, params):
        raise RuntimeError("ESPN 403")
    t = ing.run_results("2026-11-04", now=datetime(2026, 11, 4, 18, tzinfo=timezone.utc),
                        connect=lambda: conn, get_json=broken, sleep=0)
    assert t["failed"] == ["2026-11-03"] and t["errors"] == 1


# ── the multi-day runners ────────────────────────────────────────────────────

def test_backfill_is_idempotent_and_loads_teams_once(conn, capsys):
    espn = Espn({"20251127": BOARD_1127, "20251128": {"events": []}})
    t = ing.run_backfill("2025-11-27", "2025-11-28", connect=lambda: conn, get_json=espn, sleep=0)
    assert t["dates"] == 2 and t["games_inserted"] == 3 and not t["failed"]
    assert [u for u, _ in espn.calls].count(ing.TEAMS_URL) == 1
    assert "2025-11-27: " in capsys.readouterr().out
    t2 = ing.run_backfill("2025-11-27", "2025-11-28", connect=lambda: conn, get_json=espn, sleep=0)
    assert t2["games_inserted"] == 0 and t2["unchanged"] == 3
    with pytest.raises(ValueError):
        ing.run_backfill("2025-11-28", "2025-11-27", connect=lambda: conn, get_json=espn)


def test_schedule_refresh_covers_today_and_the_next_days(conn):
    espn = Espn({"20261103": BOARD_1103})
    t = ing.run_schedule_refresh("2026-11-01", days=3, connect=lambda: conn, get_json=espn, sleep=0)
    assert espn.scoreboard_dates() == ["20261101", "20261102", "20261103", "20261104"]
    assert t["games_inserted"] == 2 and t["teams"]["d1_teams"] == 10 and not t["failed"]


# ── wiring: the daily pipeline and the refresh pass ──────────────────────────

PIPE = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
SH = (ROOT / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")


def test_both_steps_are_registered_and_dispatchable():
    choices = PIPE[PIPE.index('parser.add_argument("--step"'):PIPE.index('help="Run a single pipeline step"')]
    assert '"ncaab-results"' in choices and '"ncaab-schedule"' in choices
    assert re.search(r'"ncaab-results":\s*lambda: step_ncaab_results\(run_date\)', PIPE)
    assert re.search(r'"ncaab-schedule":\s*lambda: step_ncaab_schedule\(run_date\)', PIPE)


def test_the_daily_run_ingests_ncaab_before_it_settles():
    daily = PIPE[PIPE.index("def run_daily_pipeline"):]
    sched = daily.index('results["ncaab_schedule"] = step_ncaab_schedule(run_date)')
    res = daily.index('results["ncaab_results"] = step_ncaab_results(run_date)')
    assert sched < res < daily.index('results["settle"] = step_settle(yesterday)')


def test_the_refresh_pass_runs_ncaab_results_in_the_results_group():
    group = SH[SH.index("# GROUP 3"):]
    group = group[:group.index("par_wait")]
    assert re.search(r"^par ncaab-results$", group, re.M)
    # every parallel step the pass names is one run_pipeline can dispatch
    table = PIPE[PIPE.index("step_fns = {"):PIPE.index("success = _timed_step")]
    for name in re.findall(r"^par (\S+)$", SH, re.M):
        assert f'"{name}":' in table, f"refresh_pass.sh runs unknown step {name!r}"


@pytest.mark.parametrize("failed,ok", [([], True), (["2026-11-03"], False)])
def test_the_steps_go_red_on_a_failed_date(monkeypatch, failed, ok):
    import run_pipeline
    monkeypatch.setattr(ing, "run_results", lambda run_date: {**ing.new_totals(), "failed": failed})
    monkeypatch.setattr(ing, "run_schedule_refresh",
                        lambda run_date: {**ing.new_totals(), "failed": failed})
    assert run_pipeline.step_ncaab_results("2026-11-04") is ok
    assert run_pipeline.step_ncaab_schedule("2026-11-04") is ok


def test_a_step_that_raises_is_a_false_not_a_crash(monkeypatch):
    import run_pipeline

    def boom(run_date):
        raise RuntimeError("db down")
    monkeypatch.setattr(ing, "run_results", boom)
    assert run_pipeline.step_ncaab_results("2026-11-04") is False
