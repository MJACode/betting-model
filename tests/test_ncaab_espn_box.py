"""The NCAAB box-score and period-score feed (data/ingestors/ncaab_espn_box.py)
and its wiring into the refresh pass.

Fixtures are REAL ESPN payloads, trimmed to what the module reads (fetched
2026-10-30, tests/fixtures/ncaab_espn_box/):
  summary_401825519.json   Maryland @ Rutgers 57-68, 2026-02-15, regulation.
                           NCAA's own row for it is in production
                           (contest 6465747): every box number below is
                           NCAA's too.
  summary_401812127.json   Binghamton @ New Hampshire 82-88, 2026-01-22,
                           three overtimes (five periods).
  scoreboard_2026-02-07.json  three finals of one date: Middle Tennessee @
                           Delaware 88-89 in overtime, Oklahoma State @
                           Arizona, Duke @ North Carolina.

The SQL runs on sqlite through a shim that maps %s and NOW(); the real
Postgres run of the same code is tests/test_ncaab_espn_box_pg.py.
"""
from __future__ import annotations

import copy
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

from data.db_setup import SCHEMA_SQL
from data.ingestors import ncaab_espn_box as box
from data.ingestors import ncaab_sdv_import as sdv
from data.ingestors import ncaab_teams as nt

ROOT = Path(__file__).parent.parent
FIX = Path(__file__).parent / "fixtures" / "ncaab_espn_box"


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


SUM_MD_RU = _load("summary_401825519.json")
SUM_3OT = _load("summary_401812127.json")
BOARD_0207 = _load("scoreboard_2026-02-07.json")

# The stored games and ncaab_events rows, as production holds them
# (Supabase, read 2026-10-30): event, game_id, season, date, tip, home id,
# away id, home school, away school, home score, away score, went_to_ot.
GAMES = {
    401825519: ("NCAAB_2026-02-15_maryland_rutgers", 2026, "2026-02-15", "2026-02-15T17:00:00Z",
                164, 120, "Rutgers", "Maryland", 68, 57, 0),
    401812127: ("NCAAB_2026-01-22_binghamton_new-hampshire", 2026, "2026-01-22",
                "2026-01-22T23:00:00Z", 160, 2066, "New Hampshire", "Binghamton", 88, 82, 1),
    401804920: ("NCAAB_2026-02-07_middle-tennessee_delaware", 2026, "2026-02-07",
                "2026-02-07T18:00:00Z", 48, 2393, "Delaware", "Middle Tennessee", 89, 88, 1),
    401827665: ("NCAAB_2026-02-07_oklahoma-state_arizona", 2026, "2026-02-07",
                "2026-02-07T21:00:00Z", 12, 197, "Arizona", "Oklahoma State", 84, 47, 0),
    401820724: ("NCAAB_2026-02-07_duke_north-carolina", 2026, "2026-02-07",
                "2026-02-07T23:30:00Z", 153, 150, "North Carolina", "Duke", 71, 68, 0),
}

# NCAA's (sportsdataverse) rows for 401825519, as production holds them.
SDV_ROWS = [
    {"contest_id": "6465747", "team": "Maryland", "game_date": "2026-02-15",
     "espn_game_id": 401825519, "team_espn_id": 120, "opp_espn_id": 164,
     "team_ncaa_id": "609661", "is_home": False, "season": 2026, "home_espn_id": 164,
     "away_espn_id": 120, "mins": 39.717, "o_poss": 67, "d_poss": 67, "pts": 57,
     "d_pts": 68, "fga": 66, "fgm": 22, "tpa": 30, "tpm": 7, "fta": 13, "ftm": 6,
     "rima": 22, "rimm": 12, "orb": 18, "drb": 23, "tov": 10, "ast": 10, "blk": 2,
     "e_poss": 64.5, "time_per_poss": 18.537, "source": "sportsdataverse_ncaa"},
    {"contest_id": "6465747", "team": "Rutgers", "game_date": "2026-02-15",
     "espn_game_id": 401825519, "team_espn_id": 164, "opp_espn_id": 120,
     "team_ncaa_id": "609851", "is_home": True, "season": 2026, "home_espn_id": 164,
     "away_espn_id": 120, "mins": 39.717, "o_poss": 67, "d_poss": 67, "pts": 68,
     "d_pts": 57, "fga": 53, "fgm": 22, "tpa": 18, "tpm": 5, "fta": 24, "ftm": 19,
     "rima": 13, "rimm": 7, "orb": 9, "drb": 29, "tov": 10, "ast": 12, "blk": 3,
     "e_poss": 64.5, "time_per_poss": 17.03, "source": "sportsdataverse_ncaa"},
]

NOW_0216 = datetime(2026, 2, 16, 15, 0, tzinfo=timezone.utc)


# ── a sqlite stand-in for data.db.DBConnection ───────────────────────────────

def _lite(sql: str) -> str:
    return (sql.replace("NOW()::TEXT", "CURRENT_TIMESTAMP")
               .replace("NOW()", "CURRENT_TIMESTAMP").replace("%s", "?"))


class LiteConn:
    """execute / executemany / commit / rollback over sqlite3, recording every
    write so a test can assert that a repeat run wrote nothing."""

    def __init__(self):
        self.sq = sqlite3.connect(":memory:")
        self.sq.executescript(SCHEMA_SQL)
        for ddl in (nt.EVENTS_DDL, sdv.TEAM_DDL, box.PERIODS_DDL, box.MISSES_DDL):
            self.sq.execute(_lite(ddl))
        self.sq.commit()
        self.writes: list[str] = []

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
        self.sq.commit()

    def rollback(self):
        self.sq.rollback()

    def close(self):
        pass

    def q(self, sql, params=()):
        return self.sq.execute(sql, params).fetchall()


def _seed(conn, events):
    for eid in events:
        (gid, season, gdate, tip, hid, aid, home, away, hs, as_, ot) = GAMES[eid]
        conn.sq.execute(
            "INSERT INTO games (game_id, sport, season, game_date, home_team, away_team, "
            "home_score, away_score, commence_time, went_to_ot) "
            "VALUES (?, 'NCAAB', ?, ?, ?, ?, ?, ?, ?, ?)",
            (gid, season, gdate, home, away, hs, as_, tip, ot))
        conn.sq.execute(
            "INSERT INTO ncaab_events (espn_event_id, game_id, season, game_date, "
            "commence_time, home_espn_id, away_espn_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (eid, gid, season, gdate, tip, hid, aid))
    conn.sq.commit()


class Espn:
    """A fake get_json: summaries by event id, scoreboards by YYYYMMDD; an
    entry may be an exception to raise. Records every call."""

    def __init__(self, summaries=None, boards=None):
        self.summaries = dict(summaries or {})
        self.boards = dict(boards or {})
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url, params):
        self.calls.append((url, dict(params)))
        if url == box.SUMMARY_URL:
            v = self.summaries.get(int(params["event"]))
        else:
            v = self.boards.get(params["dates"], {"events": []})
        if isinstance(v, Exception):
            raise v
        if v is None:
            raise _http_error(404)
        return copy.deepcopy(v)


def _http_error(code):
    resp = requests.Response()
    resp.status_code = code
    return requests.HTTPError(f"{code} Client Error", response=resp)


@pytest.fixture(autouse=True)
def _no_ddl(monkeypatch):
    """The tables already exist in LiteConn; ensure_tables' catalog reads are
    Postgres-only (the Postgres file runs the real one)."""
    monkeypatch.setattr(box, "ensure_tables", lambda conn: None)
    monkeypatch.setattr(box.time, "sleep", lambda s: None)


@pytest.fixture
def conn():
    return LiteConn()


def _game(eid):
    (gid, season, gdate, tip, hid, aid, home, away, hs, as_, ot) = GAMES[eid]
    return {"espn_event_id": eid, "game_id": gid, "season": season, "game_date": gdate,
            "commence_time": tip, "home_espn_id": hid, "away_espn_id": aid,
            "home_team": home, "away_team": away, "home_score": hs, "away_score": as_,
            "went_to_ot": ot}


def _stats(conn, eid=None):
    sql = ("SELECT contest_id, team, is_home, o_poss, d_poss, pts, d_pts, fga, fgm, tpa, tpm, "
           "fta, ftm, orb, drb, tov, ast, blk, mins, source FROM ncaab_team_game_stats")
    if eid is not None:
        return conn.q(sql + " WHERE espn_game_id = ? ORDER BY contest_id, team", (eid,))
    return conn.q(sql + " ORDER BY contest_id, team")


def _periods(conn, game_id):
    return conn.q("SELECT period, home_points, away_points, source FROM ncaab_period_scores "
                  "WHERE game_id = ? ORDER BY period", (game_id,))


def _seed_copies(conn, n, *, start=990000, tip="2026-02-15T17:00:00Z", game_date="2026-02-15"):
    """n more finals shaped like Maryland @ Rutgers, each under its own event
    id and game id, tipping 10 minutes apart (the first tips earliest).
    Returns their event ids, oldest first, and a summary per event: the real
    payload with the header naming that event."""
    (_, season, _, _, hid, aid, home, away, hs, as_, ot) = GAMES[401825519]
    t0 = datetime.fromisoformat(tip.replace("Z", "+00:00"))
    ids, sums = [], {}
    for k in range(n):
        eid = start + k
        gid = f"NCAAB_{game_date}_copy-{eid}"
        at = (t0 + timedelta(minutes=10 * k)).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.sq.execute(
            "INSERT INTO games (game_id, sport, season, game_date, home_team, away_team, "
            "home_score, away_score, commence_time, went_to_ot) "
            "VALUES (?, 'NCAAB', ?, ?, ?, ?, ?, ?, ?, ?)",
            (gid, season, game_date, home, away, hs, as_, at, ot))
        conn.sq.execute(
            "INSERT INTO ncaab_events (espn_event_id, game_id, season, game_date, "
            "commence_time, home_espn_id, away_espn_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (eid, gid, season, game_date, at, hid, aid))
        js = copy.deepcopy(SUM_MD_RU)
        js["header"]["id"] = str(eid)
        ids.append(eid)
        sums[eid] = js
    conn.sq.commit()
    return ids, sums


def _without_turnovers(js):
    """ESPN renames its turnover fields: every box score lacks turnovers."""
    js = copy.deepcopy(js)
    for t in js["boxscore"]["teams"]:
        for s in t["statistics"]:
            if s.get("name") in ("turnovers", "totalTurnovers"):
                s["name"] += "Renamed"
    return js


class Clock:
    """A fake monotonic clock that a fake ESPN moves forward."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


# ── parsing a real summary ───────────────────────────────────────────────────

def test_a_real_summary_parses_to_ncaas_own_numbers():
    sides = box.parse_summary(SUM_MD_RU, 401825519)
    assert set(sides) == {120, 164}
    md, ru = sides[120], sides[164]
    assert md["score"] == 57 and ru["score"] == 68
    assert md["periods"] == [27, 30] and ru["periods"] == [27, 41]
    for team, s in ((md, SDV_ROWS[0]), (ru, SDV_ROWS[1])):
        for k in ("fga", "fgm", "tpa", "tpm", "fta", "ftm", "orb", "drb", "tov", "ast", "blk"):
            assert team["box"][k] == s[k], k


def test_the_rows_for_a_real_game():
    rows = box.box_rows(_game(401825519), box.parse_summary(SUM_MD_RU, 401825519))
    by_team = {r[box.BOX_COLS.index("team")]: dict(zip(box.BOX_COLS, r)) for r in rows}
    ru, md = by_team["Rutgers"], by_team["Maryland"]
    assert ru["contest_id"] == md["contest_id"] == "espn:401825519"
    assert (ru["is_home"], md["is_home"]) == (True, False)
    assert (ru["team_espn_id"], ru["opp_espn_id"]) == (164, 120)
    assert (ru["pts"], ru["d_pts"], md["pts"], md["d_pts"]) == (68, 57, 57, 68)
    assert ru["season"] == 2026 and ru["game_date"] == "2026-02-15"
    assert ru["mins"] == 40.0 and ru["source"] == "espn_summary"
    for k in ("rima", "rimm", "e_poss", "time_per_poss", "team_ncaa_id"):
        assert ru[k] is None and md[k] is None, k


def test_the_possession_estimate_and_its_mirror():
    """fga - orb + tov + 0.475 x fta, each team's own as o_poss and the
    opponent's as d_poss: one team's o_poss is the other's d_poss, as in
    NCAA's rows."""
    rows = box.box_rows(_game(401825519), box.parse_summary(SUM_MD_RU, 401825519))
    by_team = {r[box.BOX_COLS.index("team")]: dict(zip(box.BOX_COLS, r)) for r in rows}
    md, ru = by_team["Maryland"], by_team["Rutgers"]
    assert md["o_poss"] == pytest.approx(66 - 18 + 10 + 0.475 * 13)     # 64.175
    assert ru["o_poss"] == pytest.approx(53 - 9 + 10 + 0.475 * 24)      # 65.4
    assert md["d_poss"] == ru["o_poss"] and ru["d_poss"] == md["o_poss"]
    # The estimate runs below NCAA's play-by-play count (67 here); per game
    # the mean gap over 2020-21..2025-26 is under half a possession, and this
    # game sits inside the usual spread of a couple of possessions.
    mean = (md["o_poss"] + ru["o_poss"]) / 2
    assert 64.0 < mean < 67.0
    assert box.possessions({"fga": 66, "orb": 18, "tov": 10, "fta": 13}) == 64.175


def test_three_overtimes_keep_every_period():
    sides = box.parse_summary(SUM_3OT, 401812127)
    rows = box.period_rows(_game(401812127), sides, box.PERIODS_FROM_SUMMARY)
    assert [(r[1], r[2], r[3]) for r in rows] == [
        (1, 26, 40), (2, 31, 17), (3, 7, 7), (4, 11, 11), (5, 13, 7)]
    stats = box.box_rows(_game(401812127), sides)
    assert {dict(zip(box.BOX_COLS, r))["mins"] for r in stats} == {55.0}


# ── the refresh-pass run ─────────────────────────────────────────────────────

def test_a_run_stores_box_and_periods_and_a_second_run_writes_nothing(conn):
    _seed(conn, [401825519])
    espn = Espn({401825519: SUM_MD_RU})
    t = box.run_recent("2026-02-16", now=NOW_0216, connect=lambda: conn, get_json=espn)
    assert (t["due"], t["fetched"], t["games_stored"]) == (1, 1, 1)
    assert (t["box_rows"], t["period_rows"], t["failed"]) == (2, 2, [])
    rows = _stats(conn, 401825519)
    assert [(r[0], r[1], r[5], r[7], r[15]) for r in rows] == [
        ("espn:401825519", "Maryland", 57.0, 66.0, 10.0),
        ("espn:401825519", "Rutgers", 68.0, 53.0, 10.0)]
    assert _periods(conn, "NCAAB_2026-02-15_maryland_rutgers") == [
        (1, 27, 27, "espn_summary"), (2, 41, 30, "espn_summary")]

    calls, writes = len(espn.calls), len(conn.writes)
    t2 = box.run_recent("2026-02-16", now=NOW_0216 + timedelta(hours=1),
                        connect=lambda: conn, get_json=espn)
    assert t2["due"] == 0 and t2["games_stored"] == 0
    assert len(espn.calls) == calls, "a stored game was fetched again"
    assert len(conn.writes) == writes, "a second run wrote something"


def test_only_recent_finals_are_due(conn):
    _seed(conn, [401825519, 401812127])           # 2026-02-15 and 2026-01-22
    espn = Espn({401825519: SUM_MD_RU, 401812127: SUM_3OT})
    box.run_recent("2026-02-16", now=NOW_0216, connect=lambda: conn, get_json=espn)
    assert [p["event"] for _, p in espn.calls] == ["401825519"]


def test_an_unscored_game_is_not_due(conn):
    _seed(conn, [401825519])
    conn.sq.execute("UPDATE games SET home_score = NULL, away_score = NULL")
    espn = Espn({401825519: SUM_MD_RU})
    t = box.run_recent("2026-02-16", now=NOW_0216, connect=lambda: conn, get_json=espn)
    assert t["due"] == 0 and espn.calls == []


def test_the_pass_cap_leaves_the_rest_for_the_next_pass(conn):
    _seed(conn, [401804920, 401827665, 401820724])
    espn = Espn({})                                   # every summary 404s
    t = box.run_recent("2026-02-08", now=datetime(2026, 2, 8, 15, tzinfo=timezone.utc),
                       connect=lambda: conn, get_json=espn, max_games=2)
    assert t["due"] == 2 and t["left"] == 1 and len(espn.calls) == 2


def test_the_time_budget_stops_fetching_and_leaves_the_rest(conn):
    """The only bound on wall-clock time: once the budget is spent no further
    summary is fetched, and the games not reached are counted as left."""
    ids, sums = _seed_copies(conn, 10)
    clock = Clock()
    espn = Espn(sums)

    def slow(url, params):            # every summary takes 20 seconds
        clock.t += 20.0
        return espn(url, params)
    t = box.run_recent("2026-02-16", now=NOW_0216, connect=lambda: conn, get_json=slow,
                       budget_s=50.0, clock=clock)
    # fetched at 0, 20 and 40 seconds; at 60 the 50-second budget is spent
    assert len(espn.calls) == 3
    assert (t["due"], t["fetched"], t["games_stored"], t["left"]) == (10, 3, 3, 7)
    assert t["failed"] == []
    # the three newest went first; the seven older ones wait for the next pass
    assert [int(p["event"]) for _, p in espn.calls] == ids[::-1][:3]


# ── what is refused, and that refusing never raises ──────────────────────────

def _broken(js, path, value):
    js = copy.deepcopy(js)
    node = js
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value
    return js


MALFORMED = {
    "no box score": _broken(SUM_MD_RU, ["boxscore"], {}),
    "a team without FGA": _broken(
        SUM_MD_RU, ["boxscore", "teams", 0, "statistics"],
        [s for s in SUM_MD_RU["boxscore"]["teams"][0]["statistics"]
         if s["name"] != "fieldGoalsMade-fieldGoalsAttempted"]),
    "not final": _broken(SUM_MD_RU, ["header", "competitions", 0, "status", "type"],
                         {"name": "STATUS_IN_PROGRESS", "state": "in", "completed": False}),
    "periods do not sum": _broken(
        SUM_MD_RU, ["header", "competitions", 0, "competitors", 0, "linescores"],
        [{"displayValue": "27"}, {"displayValue": "40"}]),
    "another event": _broken(SUM_MD_RU, ["header", "id"], "401825520"),
    "a different final": _broken(
        SUM_MD_RU, ["header", "competitions", 0, "competitors", 0, "score"], "69"),
    "not JSON we know": ["unexpected", "list"],
    "empty": {},
}


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_a_malformed_or_partial_summary_is_skipped_without_raising(conn, name):
    """Nothing of the bad game is stored (its periods included), the miss is
    recorded, the run is not red, and the next game still lands."""
    _seed(conn, [401825519, 401812127])
    espn = Espn({401825519: MALFORMED[name], 401812127: SUM_3OT})
    t = box.run_recent("2026-02-16", now=NOW_0216, connect=lambda: conn, get_json=espn,
                       days=30)
    assert t["refused"] == 1 and t["failed"] == [], t
    assert _stats(conn, 401825519) == []
    assert _periods(conn, "NCAAB_2026-02-15_maryland_rutgers") == []
    assert conn.q("SELECT espn_event_id, attempts FROM ncaab_box_misses") == [(401825519, 1)]
    assert len(_stats(conn, 401812127)) == 2


def test_a_404_is_a_miss_and_a_403_stops_the_run_red(conn):
    _seed(conn, [401804920, 401827665, 401820724])
    now = datetime(2026, 2, 8, 15, tzinfo=timezone.utc)
    t = box.run_recent("2026-02-08", now=now, connect=lambda: conn, get_json=Espn({}))
    assert t["refused"] == 3 and t["failed"] == [] and t["stopped"] is None

    conn2 = LiteConn()
    _seed(conn2, [401804920, 401827665, 401820724])
    espn = Espn({e: _http_error(403) for e in (401804920, 401827665, 401820724)})
    t = box.run_recent("2026-02-08", now=now, connect=lambda: conn2, get_json=espn)
    assert len(espn.calls) == 1, "kept calling ESPN after a 403"
    assert t["stopped"] == "ESPN answered 403" and t["failed"] == ["espn-403"]
    assert t["left"] == 3
    assert conn2.q("SELECT COUNT(*) FROM ncaab_box_misses") == [(0,)]


def test_one_failed_fetch_ends_the_passs_run(conn):
    """On a refresh pass the next pass is the retry: the first fetch that
    fails (after the helper's own retry) stops the run, so an ESPN outage
    costs one fetch a pass, not three. The games stay due, nothing is
    recorded against them, and the step is red."""
    _seed(conn, [401804920, 401827665, 401820724])
    err = requests.ConnectionError("reset")
    espn = Espn({e: err for e in (401804920, 401827665, 401820724)})
    t = box.run_recent("2026-02-08", now=datetime(2026, 2, 8, 15, tzinfo=timezone.utc),
                       connect=lambda: conn, get_json=espn)
    assert len(espn.calls) == 1, "kept calling an ESPN that did not answer"
    assert t["fetch_errors"] == 1 and t["failed"] == ["espn-unreachable"]
    assert t["left"] == 2
    assert conn.q("SELECT COUNT(*) FROM ncaab_box_misses") == [(0,)], (
        "an unreachable ESPN is not a fact about the game")


def test_the_backfill_tolerates_two_failed_fetches_and_stops_at_three(conn):
    _seed(conn, [401804920, 401827665, 401820724])
    err = requests.ConnectionError("reset")
    espn = Espn({e: err for e in (401804920, 401827665, 401820724)})
    t = box.run_box_backfill(2026, 2026, now=datetime(2026, 2, 8, 15, tzinfo=timezone.utc),
                             connect=lambda: conn, get_json=espn)
    assert len(espn.calls) == 3
    assert t["fetch_errors"] == 3 and t["failed"] == ["espn-unreachable"]


def test_a_refused_game_cools_and_then_stops_being_fetched(conn):
    _seed(conn, [401825519])
    bad = MALFORMED["no box score"]
    espn = Espn({401825519: bad})
    now = NOW_0216
    box.run_recent("2026-02-16", now=now, connect=lambda: conn, get_json=espn)
    assert len(espn.calls) == 1
    box.run_recent("2026-02-16", now=now + timedelta(minutes=10),
                   connect=lambda: conn, get_json=espn)
    assert len(espn.calls) == 1, "retried inside the cool-down"
    for i in range(1, box.MAX_ATTEMPTS + 2):
        box.run_recent("2026-02-16", now=now + timedelta(hours=i),
                       connect=lambda: conn, get_json=espn)
    assert len(espn.calls) == box.MAX_ATTEMPTS
    assert conn.q("SELECT attempts FROM ncaab_box_misses") == [(box.MAX_ATTEMPTS,)]
    # ESPN fixes the game later: the season backfill tries it once more
    espn.summaries[401825519] = SUM_MD_RU
    t = box.run_box_backfill(2026, 2026, now=now + timedelta(days=1),
                             connect=lambda: conn, get_json=espn)
    assert t["games_stored"] == 1 and len(_stats(conn, 401825519)) == 2


def test_a_write_failure_is_red_and_does_not_raise(conn, monkeypatch):
    _seed(conn, [401825519])

    def boom(*a, **k):
        raise RuntimeError("disk full")
    monkeypatch.setattr(box, "write_game", boom)
    t = box.run_recent("2026-02-16", now=NOW_0216, connect=lambda: conn,
                       get_json=Espn({401825519: SUM_MD_RU}))
    assert t["failed"] == ["NCAAB_2026-02-15_maryland_rutgers"]


# ── a feed-wide break is red, and stays red after the games stop being due ──

@pytest.mark.parametrize("how", ["a renamed turnover field", "the summary answers 404"])
def test_a_feed_wide_break_turns_the_step_red_and_keeps_it_red(conn, how):
    """ESPN changes the summary for every game. Each game alone is a refusal,
    which is green; five refused in a row with nothing stored is the feed,
    not the games. The step stays red on every later pass, including the
    ones where every game has used up its attempts and nothing is due."""
    ids, sums = _seed_copies(conn, box.REFUSED_RUN_RED + 1)
    espn = Espn({e: _without_turnovers(js) for e, js in sums.items()}
                if how.startswith("a renamed") else {})
    t = box.run_recent("2026-02-16", now=NOW_0216, connect=lambda: conn, get_json=espn)
    assert (t["refused"], t["games_stored"]) == (len(ids), 0)
    assert t["refused_run"] == len(ids)
    assert t["failed"] == ["espn-box-refused"]
    for i in range(1, box.MAX_ATTEMPTS + 2):
        t = box.run_recent("2026-02-16", now=NOW_0216 + timedelta(hours=i),
                           connect=lambda: conn, get_json=espn)
    assert t["due"] == 0, "the games should have used up their attempts by now"
    assert t["failed"] == ["espn-box-refused"], "green again once nothing was due"


def test_a_break_that_arrives_one_game_a_pass_still_turns_red(conn):
    """A quiet night: one new final a pass, each refused. Counted across
    passes from the stored rows, not per pass."""
    ids, sums = _seed_copies(conn, box.REFUSED_RUN_RED)
    espn = Espn({e: _without_turnovers(js) for e, js in sums.items()})
    conn.sq.execute("UPDATE games SET home_score = NULL, away_score = NULL "
                    "WHERE game_id LIKE '%copy%'")
    conn.sq.commit()
    seen = []
    for k, eid in enumerate(ids):     # the final of one more game lands each pass
        conn.sq.execute("UPDATE games SET home_score = 68, away_score = 57 WHERE game_id = ?",
                        (f"NCAAB_2026-02-15_copy-{eid}",))
        conn.sq.commit()
        t = box.run_recent("2026-02-16", now=NOW_0216 + timedelta(minutes=10 * k),
                           connect=lambda: conn, get_json=espn)
        seen.append((t["due"], t["refused_run"], t["failed"]))
    assert [s[0] for s in seen] == [1] * len(ids)
    assert [s[1] for s in seen] == list(range(1, len(ids) + 1))
    assert [s[2] for s in seen] == [[]] * (len(ids) - 1) + [["espn-box-refused"]]


def test_refused_games_behind_a_stored_newer_one_stay_green(conn):
    """Games ESPN cannot answer for happen one at a time (a box score it never
    posts). As long as a newer game was stored, the refusals are about the
    games, and their retries on later passes stay green."""
    ids, sums = _seed_copies(conn, box.REFUSED_RUN_RED + 1)
    broken = {e: _without_turnovers(js) for e, js in sums.items()}
    broken[ids[-1]] = sums[ids[-1]]              # the newest game is fine
    espn = Espn(broken)
    t = box.run_recent("2026-02-16", now=NOW_0216, connect=lambda: conn, get_json=espn)
    assert (t["refused"], t["games_stored"], t["refused_run"]) == (len(ids) - 1, 1, 0)
    assert t["failed"] == []
    t = box.run_recent("2026-02-16", now=NOW_0216 + timedelta(hours=1),
                       connect=lambda: conn, get_json=espn)
    assert (t["due"], t["refused"], t["games_stored"]) == (len(ids) - 1, len(ids) - 1, 0)
    assert t["failed"] == [], "retrying old refusals is not a break"


# ── two sources, one game ────────────────────────────────────────────────────

def _insert_sdv(conn):
    cols = [c for c in sdv.TEAM_COLS if c != "loaded_at"]
    for r in SDV_ROWS:
        conn.sq.execute(f"INSERT INTO ncaab_team_game_stats ({', '.join(cols)}) VALUES "
                        f"({', '.join('?' * len(cols))})", tuple(r[c] for c in cols))
    conn.sq.commit()


def test_no_key_collision_with_a_sportsdataverse_row(conn):
    """NCAA's rows for the same game keep their key and their numbers; the
    ESPN rows land beside them under their own key and source."""
    _seed(conn, [401825519])
    _insert_sdv(conn)
    box.run_recent("2026-02-16", now=NOW_0216, connect=lambda: conn,
                   get_json=Espn({401825519: SUM_MD_RU}))
    rows = conn.q("SELECT contest_id, team, source, o_poss FROM ncaab_team_game_stats "
                  "WHERE espn_game_id = 401825519 ORDER BY contest_id, team")
    assert [(r[0], r[1], r[2]) for r in rows] == [
        ("6465747", "Maryland", "sportsdataverse_ncaa"),
        ("6465747", "Rutgers", "sportsdataverse_ncaa"),
        ("espn:401825519", "Maryland", "espn_summary"),
        ("espn:401825519", "Rutgers", "espn_summary")]
    assert rows[0][3] == 67 and rows[1][3] == 67, "NCAA's row was rewritten"
    # Every NCAA contest id is digits only (all 188,424 production rows,
    # 2026-10-30), so the ESPN key can never equal one.
    assert not box.contest_id(401825519).isdigit()


def documented_reader_sql() -> str:
    """The one-source-per-game query exactly as docs/sports/ncaab.md prints
    it (the indented block under "Two sources, one game"), so the test runs
    what a reader would copy."""
    doc = (ROOT / "docs" / "sports" / "ncaab.md").read_text(encoding="utf-8")
    section = doc[doc.index("**Two sources, one game.**"):]
    lines, started = [], False
    for ln in section.splitlines():
        if ln.startswith("    SELECT"):
            started = True
        if started:
            lines.append(ln[4:])
            if ln.rstrip().endswith(";"):
                break
    assert started, "no SQL block under 'Two sources, one game' in docs/sports/ncaab.md"
    return "\n".join(lines).rstrip().rstrip(";")


def _norm(sql: str) -> str:
    return " ".join(sql.replace(";", " ").split())


def _team_row(**kw):
    cols = [c for c in sdv.TEAM_COLS if c != "loaded_at"]
    row = {c: None for c in cols}
    row.update(kw)
    return tuple(row[c] for c in cols), cols


def insert_reader_cases(execute):
    """Four games, each a case the reader has to get right; `execute(sql,
    params)` inserts one row. Production, read 2026-10-30: espn_game_id is
    NULL on 138,338 of 188,424 NCAA rows (every season before 2022-23), and
    team_espn_id is NULL on 8,854, the non-Division I side of a game.
      * contest 4100001 (2014-15), NCAA only, no espn_game_id: keep both rows.
      * 401824899, a Division I team against Hawaii Pacific (not D-I), under
        both sources: NCAA's pair has no team id for Hawaii Pacific, ESPN's
        has 2269. Keep NCAA's two rows, not three.
      * 401812127, ESPN only: keep both rows."""
    def put(**kw):
        params, cols = _team_row(**kw)
        execute(f"INSERT INTO ncaab_team_game_stats ({', '.join(cols)}) VALUES "
                f"({', '.join(['%s'] * len(cols))})", params)
    for team, tid, home in (("Kansas", 2305, True), ("Duke", 150, False)):
        put(contest_id="4100001", team=team, team_espn_id=tid, is_home=home, season=2015,
            o_poss=70, source="sportsdataverse_ncaa")
    for src, cid, hp_id in (("sportsdataverse_ncaa", "6460001", None),
                            ("espn_summary", "espn:401824899", 2269)):
        put(contest_id=cid, team="Hawaii", espn_game_id=401824899, team_espn_id=62,
            is_home=True, season=2026, o_poss=71, source=src)
        put(contest_id=cid, team="Hawaii Pacific", espn_game_id=401824899,
            team_espn_id=hp_id, is_home=False, season=2026, o_poss=71, source=src)
    for team, tid, home in (("New Hampshire", 160, True), ("Binghamton", 2066, False)):
        put(contest_id="espn:401812127", team=team, espn_game_id=401812127,
            team_espn_id=tid, is_home=home, season=2026, o_poss=80.5, source="espn_summary")


READER_EXPECTED = [
    ("4100001", "Duke", "sportsdataverse_ncaa"),
    ("4100001", "Kansas", "sportsdataverse_ncaa"),
    ("6460001", "Hawaii", "sportsdataverse_ncaa"),
    ("6460001", "Hawaii Pacific", "sportsdataverse_ncaa"),
    ("6465747", "Maryland", "sportsdataverse_ncaa"),
    ("6465747", "Rutgers", "sportsdataverse_ncaa"),
    ("espn:401812127", "Binghamton", "espn_summary"),
    ("espn:401812127", "New Hampshire", "espn_summary"),
]


def test_the_documented_reader_keeps_one_source_per_game_and_every_season(conn):
    """The query the docs and the module docstring give: every game once,
    from one source, NCAA's where it holds the game. It must keep the
    seasons with no espn_game_id and must not split a game against a
    non-Division I team into three rows. The same query runs on Postgres in
    tests/test_ncaab_espn_box_pg.py."""
    sql = documented_reader_sql()
    assert _norm(sql) in _norm(box.__doc__), "module docstring and docs give different queries"
    _seed(conn, [401825519])
    _insert_sdv(conn)
    box.run_recent("2026-02-16", now=NOW_0216, connect=lambda: conn,
                   get_json=Espn({401825519: SUM_MD_RU}))
    insert_reader_cases(lambda s, p: conn.sq.execute(_lite(s), p))
    conn.sq.commit()
    total = conn.q("SELECT COUNT(*) FROM ncaab_team_game_stats")[0][0]
    assert total == 12
    picked = conn.q(f"SELECT contest_id, team, source FROM ({sql}) r "
                    "ORDER BY contest_id, team")
    assert picked == READER_EXPECTED


# ── the period backfill ──────────────────────────────────────────────────────

def test_the_period_backfill_stores_every_game_on_a_board_and_is_idempotent(conn):
    _seed(conn, [401804920, 401827665, 401820724])
    espn = Espn(boards={"20260207": BOARD_0207})
    t = box.run_period_backfill(2026, 2026, connect=lambda: conn, get_json=espn)
    assert (t["due"], t["games_stored"], t["period_rows"], t["not_on_board"]) == (3, 3, 7, 0)
    assert [p["dates"] for _, p in espn.calls] == ["20260207"]
    assert _periods(conn, "NCAAB_2026-02-07_middle-tennessee_delaware") == [
        (1, 41, 43, "espn_scoreboard"), (2, 38, 36, "espn_scoreboard"),
        (3, 10, 9, "espn_scoreboard")]
    assert _periods(conn, "NCAAB_2026-02-07_duke_north-carolina") == [
        (1, 29, 41, "espn_scoreboard"), (2, 42, 27, "espn_scoreboard")]
    calls, writes = len(espn.calls), len(conn.writes)
    t2 = box.run_period_backfill(2026, 2026, connect=lambda: conn, get_json=espn)
    assert t2["due"] == 0 and len(espn.calls) == calls and len(conn.writes) == writes


def test_a_period_backfill_refuses_a_board_that_disagrees_with_the_stored_final(conn):
    _seed(conn, [401804920, 401827665, 401820724])
    conn.sq.execute("UPDATE games SET home_score = 90 WHERE game_id LIKE '%delaware'")
    conn.sq.commit()
    t = box.run_period_backfill(2026, 2026, connect=lambda: conn,
                                get_json=Espn(boards={"20260207": BOARD_0207}))
    assert t["refused"] == 1 and t["games_stored"] == 2
    assert _periods(conn, "NCAAB_2026-02-07_middle-tennessee_delaware") == []


def test_an_early_morning_tip_is_read_from_the_previous_board():
    """ESPN files a tip after midnight ET on the previous date's board
    (ncaab_espn_ingestor.EARLY_TIP_HOUR_ET)."""
    g = {"game_date": "2025-11-10", "commence_time": "2025-11-10T06:00:00Z"}
    late = {"game_date": "2025-11-10", "commence_time": "2025-11-11T00:30:00Z"}
    assert box._board_dates([g]) == ["2025-11-09", "2025-11-10"]
    assert box._board_dates([late]) == ["2025-11-10"]


# ── wiring: the refresh pass, the step, the job ──────────────────────────────

PIPE = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
SH = (ROOT / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")


def _pos(pattern):
    m = re.search(pattern, SH, re.M)
    assert m, pattern
    return m.start()


def test_the_step_is_registered_and_dispatchable():
    choices = PIPE[PIPE.index('parser.add_argument("--step"'):PIPE.index('help="Run a single pipeline step"')]
    assert '"ncaab-box"' in choices
    assert re.search(r'"ncaab-box":\s*lambda: step_ncaab_box\(run_date\)', PIPE)


def test_the_refresh_pass_runs_it_on_hourly_passes_only_after_the_ncaab_results_step():
    """Sequential, after the results group has finished writing the finals it
    reads, and before the health check that closes the pass. HOURLY passes
    only (7 am-5 pm and midnight-5 am ET): an evening pass already runs
    455-526 s (median and 90th percentile, 7 days to 2026-10-30) against its
    600 s tick, so this step's up-to-150 s there would push the pass past the
    tick and skip the next one."""
    assert not re.search(r"^\s*par ncaab-box$", SH, re.M), "ncaab-box must be a sequential step"
    assert len(re.findall(r"^\s*step ncaab-box$", SH, re.M)) == 1
    at = _pos(r"^\s+step ncaab-box$")
    opener = SH.rfind('if [ "$MODE" = "hourly" ]; then', 0, at)
    assert opener != -1, "ncaab-box must sit inside an hourly-only block"
    assert not re.search(r"^\s*fi\s*$", SH[opener:at], re.M), (
        "ncaab-box must sit inside an hourly-only block, not after one")
    results = _pos(r"^par ncaab-results$")
    group_end = SH.index("par_wait", results)
    assert results < group_end < at < _pos(r"^step health-check$")


@pytest.mark.parametrize("failed,ok", [([], True), (["espn-403"], False)])
def test_the_step_goes_red_only_on_a_failure(monkeypatch, failed, ok):
    import run_pipeline
    monkeypatch.setattr(box, "run_recent", lambda run_date: {**box.new_totals(), "failed": failed})
    assert run_pipeline.step_ncaab_box("2026-11-04") is ok


def test_a_step_that_raises_is_a_false_not_a_crash(monkeypatch):
    import run_pipeline

    def boom(run_date):
        raise RuntimeError("database gone")
    monkeypatch.setattr(box, "run_recent", boom)
    assert run_pipeline.step_ncaab_box("2026-11-04") is False


def test_the_backfill_jobs_validate_and_are_free():
    """The two declarations validate and spend nothing. Whether each is on is
    the owner's one-line switch (`enabled`): no test pins it, so turning one
    on needs no test change. tests/test_ncaab_odds_history.py leaves this
    job type out of its credit-approval check for the same reason."""
    from tracking import job_queue as q
    _, validate = q.JOBS["ncaab_box_backfill"]
    assert validate({"kind": "periods", "first": 2021, "last": 2026}) == {
        "kind": "periods", "first": 2021, "last": 2026}
    assert validate({"kind": "box"}) == {"kind": "box", "first": 2027, "last": 2027}
    for bad in ({"kind": "box", "first": 2026, "last": 2026}, {"kind": "periods", "first": 2030},
                {"kind": "odds"}, {"kind": "periods", "max_credits": 1}):
        with pytest.raises(ValueError):
            validate(bad)
    declared = json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    mine = {e["key"]: e for e in declared if e["job_type"] == "ncaab_box_backfill"}
    assert set(mine) == {"ncaab-period-scores-2021-2026", "ncaab-box-scores-2027"}
    for e in mine.values():
        assert validate(e["args"]) == e["args"]
        assert isinstance(e.get("enabled", True), bool)
        assert not any("credit" in k for k in e["args"])


@pytest.mark.parametrize("key", ["ncaab-period-scores-2021-2026", "ncaab-box-scores-2027"])
def test_turning_a_backfill_on_is_one_line(monkeypatch, key):
    """The after-merge step: set `enabled` to true on one declaration. Every
    declaration test in the suite still passes with it on."""
    import tests.test_ncaab_odds_history as odds_hist
    real = json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    flipped = [dict(e, enabled=True) if e["key"] == key else e for e in real]
    text = json.dumps(flipped)
    real_read = Path.read_text

    def read_text(self, *a, **k):
        if self.name == "declared_jobs.json":
            return text
        return real_read(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", read_text)
    test_the_backfill_jobs_validate_and_are_free()
    odds_hist.test_the_declared_ncaab_jobs_validate_in_order_and_fit_the_approval()


def test_the_job_runs_the_cli_it_names(monkeypatch):
    from tracking import job_queue as q
    seen = {}
    monkeypatch.setattr(q, "_run_script_main",
                        lambda mod, argv: seen.update(mod=mod, argv=argv) or "ok")
    job, _ = q.JOBS["ncaab_box_backfill"]
    job(kind="periods", first=2021, last=2026)
    assert seen == {"mod": "data.ingestors.ncaab_espn_box",
                    "argv": ["--periods", "--seasons", "2021", "2026"]}


# ── the two table definitions agree ──────────────────────────────────────────

def _columns(ddl: str, table: str) -> list[str]:
    body = ddl[ddl.index(f"{table} ("):]
    body = body[body.index("(") + 1:]
    depth, out = 1, []
    for i, ch in enumerate(body):
        depth += ch == "("
        depth -= ch == ")"
        if depth == 0:
            body = body[:i]
            break
    for line in body.splitlines():
        line = " ".join(line.strip().rstrip(",").split())
        if line and not line.upper().startswith("PRIMARY KEY"):
            out.append(line)
    return out


def test_the_migration_and_the_write_time_ddl_define_the_same_tables():
    sql = (ROOT / "data" / "migrations" / "add_ncaab_period_scores_2026_10_30.sql").read_text(
        encoding="utf-8")
    for table, ddl in (("ncaab_period_scores", box.PERIODS_DDL),
                       ("ncaab_box_misses", box.MISSES_DDL)):
        assert _columns(sql, f"public.{table}") == _columns(ddl, table), table
    assert "PRIMARY KEY (game_id, period)" in sql and "PRIMARY KEY (game_id, period)" in box.PERIODS_DDL
    assert "idx_ncaab_period_scores_season" in sql
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert "add_ncaab_period_scores_2026_10_30.sql" in ACTIVE_MIGRATIONS


def test_the_migration_returns_before_it_takes_a_lock():
    sql = (ROOT / "data" / "migrations" / "add_ncaab_period_scores_2026_10_30.sql").read_text(
        encoding="utf-8")
    code = "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())
    head = code.split("CREATE TABLE IF NOT EXISTS", 1)[0]
    assert "relrowsecurity" in head and "has_table_privilege" in head and "RETURN" in head
    assert code.count("DO $mig$") == 1
