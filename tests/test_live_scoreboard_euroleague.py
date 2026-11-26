"""EuroLeague live scores on the Scoreboard (data/ingestors/live_scoreboard.py;
mike, 2026-11-25: "Why don't I see euroleague in the live feed").

Pinned here, on the real answers of game 110 of 2026-27 (Panathinaikos 74,
Barcelona 76) and states of it the halftime tests already build:
  * a finished game reads Final with the final score, home on EuroLeague's A;
  * the break reads Half at the half's score, though the third quarter's
    array already holds the substitutions logged in the break;
  * mid-quarter reads the quarter and the clock left;
  * a pre-game answer, or clubs that are not ours, write nothing;
  * the tick never calls inside the halftime loop's read window, writes
    source euroleague_api, and costs no other sport its tick.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone

from data.ingestors import live_scoreboard as ls
from tests._euroleague_live_synth import AWAY, GAME_ID, HOME, answers, at_break, third_begun

GAME = {"game_id": GAME_ID, "sport": "EUROLEAGUE", "game_date": "2026-11-13", "home_team": HOME,
        "away_team": AWAY, "home_score": None, "away_score": None,
        "commence_time": "2026-11-13T19:15:00+00:00"}


def test_the_finished_game_reads_final_with_the_home_club_first():
    row = ls.parse_euroleague(GAME, answers()["pbp"])
    assert row["state"] == "post" and row["clock_label"] == "Final"
    assert (row["home_score"], row["away_score"]) == (74, 76)
    assert row["event_id"] == "110" and row["sport"] == "EUROLEAGUE" and row["period"] == 4


def test_the_break_reads_half_at_the_halfs_score():
    row = ls.parse_euroleague(GAME, at_break()["pbp"])
    assert row["state"] == "in" and row["clock_label"] == "Half" and row["period"] == 2
    assert (row["home_score"], row["away_score"]) == (33, 32)


def test_the_third_quarter_begun_reads_q3():
    row = ls.parse_euroleague(GAME, third_begun()["pbp"])
    assert row["state"] == "in" and row["period"] == 3 and row["clock_label"].startswith("Q3")


def test_mid_quarter_reads_the_quarter_and_the_clock_left():
    pbp = copy.deepcopy(answers()["pbp"])
    q2 = pbp["SecondQuarter"]
    cut = next(i for i, p in enumerate(q2) if p.get("POINTS_A") == 19 and p.get("POINTS_B") == 19)
    pbp["SecondQuarter"] = q2[:cut + 1]
    pbp["ThirdQuarter"], pbp["ForthQuarter"], pbp["ExtraTime"] = [], [], []
    pbp["Live"] = True
    row = ls.parse_euroleague(GAME, pbp)
    assert row["clock_label"] == "Q2 09:12" and (row["home_score"], row["away_score"]) == (19, 19)


def test_before_the_tip_and_with_strange_clubs_nothing_is_written():
    pre = copy.deepcopy(answers()["pbp"])
    for q in ("FirstQuarter", "SecondQuarter", "ThirdQuarter", "ForthQuarter", "ExtraTime"):
        pre[q] = []
    pre["Live"] = False
    assert ls.parse_euroleague(GAME, pre) is None
    assert ls.parse_euroleague(GAME, None) is None
    flipped = {**GAME, "home_team": AWAY, "away_team": HOME}
    assert ls.parse_euroleague(flipped, answers()["pbp"]) is None


def test_the_quiet_window_is_the_halftime_loops_read_instant():
    at = lambda m, s: datetime(2026, 11, 25, 20, m, s, tzinfo=timezone.utc)   # noqa: E731
    assert not ls.euroleague_quiet(at(0, 5))
    assert ls.euroleague_quiet(at(0, 37))           # the loop's mark + 37 s
    assert ls.euroleague_quiet(at(1, 0))
    assert not ls.euroleague_quiet(at(1, 50))
    assert ls.euroleague_quiet(at(5, 40))


class _Cur:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, games):
        self.games, self.upserts = games, []

    def execute(self, sql, params=None):
        if "to_regclass" in sql:
            return _Cur([(True,)])
        if "FROM public.games" in sql:
            assert "EUROLEAGUE" in params["sports"]
            cols = ("game_id", "sport", "game_date", "home_team", "away_team",
                    "home_score", "away_score", "commence_time")
            return _Cur([tuple(g[c] for c in cols) for g in self.games])
        if "FROM public.live_scoreboard" in sql:
            return _Cur([])
        if "INSERT INTO public.live_scoreboard" in sql:
            self.upserts.append(params)
            return _Cur([])
        raise AssertionError(sql)

    def commit(self):
        pass

    def rollback(self):
        pass


def _no_espn(sport, dates):
    raise AssertionError("no ESPN sport is on this slate")


def test_a_tick_writes_the_live_game_from_the_league_api():
    asked = []

    def fetch(season, code):
        asked.append((season, code))
        return at_break()["pbp"]
    conn = _Conn([GAME])
    now = datetime(2026, 11, 13, 20, 12, 5, tzinfo=timezone.utc)
    out = ls.run_once(conn, now=now, fetch=_no_espn, euroleague_fetch=fetch)
    assert out == {"EUROLEAGUE": 1} and asked == [("E2026", 110)]
    [row] = conn.upserts
    assert row["source"] == "euroleague_api" and row["clock_label"] == "Half"
    assert row["snapshot_at"] == now.isoformat()


def test_a_tick_inside_the_read_window_calls_nothing():
    def fetch(season, code):
        raise AssertionError("inside the halftime loop's read window")
    conn = _Conn([GAME])
    now = datetime(2026, 11, 13, 20, 11, 0, tzinfo=timezone.utc)
    assert ls.run_once(conn, now=now, fetch=_no_espn, euroleague_fetch=fetch) == {}
    assert conn.upserts == []


def test_a_settled_or_far_off_game_is_not_asked_for():
    def fetch(season, code):
        raise AssertionError("not due")
    settled = {**GAME, "home_score": "74", "away_score": "76"}
    now = datetime(2026, 11, 13, 20, 12, 5, tzinfo=timezone.utc)
    assert ls.run_once(_Conn([settled]), now=now, fetch=_no_espn, euroleague_fetch=fetch) == {}
    early = datetime(2026, 11, 13, 17, 2, 5, tzinfo=timezone.utc)
    assert ls.run_once(_Conn([GAME]), now=early, fetch=_no_espn, euroleague_fetch=fetch) == {}


def test_espn_rows_still_say_espn_site():
    src = (ls.__file__ and open(ls.__file__, encoding="utf-8").read())
    assert '"source": "espn_site"' in src and "%(source)s" in src
