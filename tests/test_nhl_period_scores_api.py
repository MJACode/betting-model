"""Goals by period from the NHL's score feed: only regulation goals count toward a period,
and a game whose periods do not add up to the stored final is not written."""
from __future__ import annotations

from data.ingestors import nhl_period_scores_api as a


def _goal(period, team, kind="REG"):
    return {"period": period, "teamAbbrev": team, "periodDescriptor": {"periodType": kind}}


def _game(goals, state="OFF", home="VGK", away="TOR"):
    return {"id": 2025020748, "gameState": state, "homeTeam": {"abbrev": home}, "awayTeam": {"abbrev": away},
            "goals": goals}


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
