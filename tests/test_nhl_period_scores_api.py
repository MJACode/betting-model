"""Goals by period from the NHL's score feed: only regulation goals count toward a period,
and a game whose periods do not add up to the stored final is not written."""
from __future__ import annotations

from pathlib import Path

from data.ingestors import nhl_period_scores_api as a


def _goal(period, team, kind="REG"):
    return {"period": period, "teamAbbrev": team, "periodDescriptor": {"periodType": kind}}


def _game(goals, state="OFF", home="VGK", away="TOR", **over):
    base = {
        "id": 2025020748, "gameState": state, "gameType": 2, "gameDate": "2026-01-15",
        "season": 20252026, "gameOutcome": {"lastPeriodType": "REG"},
        "homeTeam": {"abbrev": home, "score": 0}, "awayTeam": {"abbrev": away, "score": 0},
        "goals": goals,
    }
    base.update(over)
    return base


def test_goals_are_counted_into_the_period_they_were_scored_in():
    g = _game([_goal(1, "TOR"), _goal(1, "VGK"), _goal(1, "TOR"), _goal(2, "VGK"), _goal(3, "TOR"), _goal(3, "VGK")])
    assert a.period_goals(g) == ([1, 1, 1], [2, 0, 1])


def test_overtime_and_shootout_goals_belong_to_no_period():
    g = _game([_goal(1, "TOR"), _goal(2, "VGK"), _goal(4, "VGK", "OT"), _goal(5, "TOR", "SO")])
    assert a.period_goals(g) == ([0, 1, 0], [1, 0, 0])


def test_a_team_named_as_an_object_is_read_too():
    g = _game([{"period": 1, "teamAbbrev": {"default": "TOR"}, "periodDescriptor": {"periodType": "REG"}}])
    assert a.period_goals(g) == ([0, 0, 0], [1, 0, 0])


def test_a_game_still_in_play_or_a_goal_for_neither_side_is_not_a_result():
    assert a.period_goals(_game([_goal(1, "TOR")], state="LIVE")) is None
    assert a.period_goals(_game([_goal(1, "SEA")])) is None
    assert a.period_goals({"id": 1, "gameState": "OFF", "homeTeam": {"abbrev": "VGK"}, "awayTeam": {"abbrev": "TOR"}}) is None


def test_the_final_may_exceed_the_periods_by_one_overtime_goal_and_nothing_else():
    assert a.agrees([2, 1, 2], [2, 1, 0], 5, 3)            # decided in regulation
    assert a.agrees([1, 1, 3], [3, 1, 1], 6, 5)            # level after three, home won it after
    assert a.agrees([1, 1, 3], [3, 1, 1], 5, 6)
    assert not a.agrees([1, 1, 3], [3, 1, 1], 5, 5)        # level after three and no winner: not a final
    assert not a.agrees([1, 1, 3], [3, 1, 1], 6, 6)
    assert not a.agrees([2, 1, 2], [2, 1, 0], 6, 3)        # a regulation win cannot gain a goal
    assert not a.agrees([2, 1, 2], [2, 1, 0], 4, 3)        # the final never trails the periods
    assert not a.agrees([2, 1, 2], [2, 1, 0], None, 3)


def test_rows_carry_their_own_source_and_never_overwrite_the_archive():
    class Conn:
        def executemany(self, sql, rows):
            self.sql, self.rows = sql, rows

        def commit(self):
            pass
    c = Conn()
    assert a._write(c, [("G", "2026-01-15", 2026, 1, 1, 3, 3, 1, 1, a.SOURCE)]) == 1
    assert "ON CONFLICT DO NOTHING" in c.sql and a.SOURCE == "nhl_api_score"
    assert a._write(c, []) == 0


def test_a_feed_game_becomes_the_same_game_id_the_games_table_uses():
    # 2026-10-18 CBJ at MIN, the score feed's goals: P1 MIN, P1 CBJ, P2 MIN.
    g = _game(
        [_goal(1, "MIN"), _goal(1, "CBJ"), _goal(2, "MIN")],
        home="MIN", away="CBJ", gameDate="2026-10-18", season=20262027,
        homeTeam={"abbrev": "MIN", "score": 2}, awayTeam={"abbrev": "CBJ", "score": 1},
        gameOutcome={"lastPeriodType": "REG"}, id=2026020135,
    )
    rows = a.rows_for_feed([g])
    assert rows == [("NHL_2026-10-18_CBJ_MIN", "2026-10-18", 2027, 1, 1, 0, 1, 0, 0, "nhl_api_score")]


def test_top_up_fetches_only_dates_a_final_is_still_missing(monkeypatch):
    fetched = []

    def fetch(day):
        fetched.append(day)
        if day != "2026-10-18":
            return []
        return [_game(
            [_goal(1, "MIN"), _goal(1, "CBJ"), _goal(2, "MIN")],
            home="MIN", away="CBJ", gameDate="2026-10-18", season=20262027,
            homeTeam={"abbrev": "MIN", "score": 2}, awayTeam={"abbrev": "CBJ", "score": 1},
        )]

    monkeypatch.setattr(a, "fetch", fetch)
    monkeypatch.setattr(a.time, "sleep", lambda _s: None)

    class Conn:
        def execute(self, sql, params=None):
            assert "nhl_period_scores" in sql
            assert "NOT EXISTS" in sql
            assert params == ("2026-10-21", "nhl_api_score")
            return self

        def fetchall(self):
            return [("2026-10-01",), ("2026-10-18",)]

        def executemany(self, sql, rows):
            self.sql = sql
            self.rows = rows

        def commit(self):
            pass

    conn = Conn()
    assert a.top_up("2026-10-21", conn) == 1
    assert fetched == ["2026-10-01", "2026-10-18"]
    assert conn.rows[0][0] == "NHL_2026-10-18_CBJ_MIN"
    assert "ON CONFLICT DO NOTHING" in conn.sql


def test_the_daily_nhl_results_step_fills_missing_period_scores():
    src = Path("run_pipeline.py").read_text(encoding="utf-8")
    body = src.split("def step_nhl_results", 1)[1].split("\ndef ", 1)[0]
    assert "top_up" in body
    assert body.index("ingest_nhl_scores_for_date") < body.index("top_up")
