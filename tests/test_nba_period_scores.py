"""data/ingestors/nba_period_scores: the quarter scores a first-half or
first-quarter NBA bet is graded on.

A wrong quarter grades a bet wrong; a missing one only leaves it unsettled.
So a game whose quarters do not add up to the final, or whose two sides list
different numbers of periods, is skipped rather than stored.
"""
from data.ingestors.nba_period_scores import parse_period_rows


def _event(home_lines, away_lines, home_score, away_score, completed=True,
           home="DET", away="PHX", date="2026-01-16T00:00Z"):
    def comp(side, abbrev, lines, score):
        return {"homeAway": side, "team": {"abbreviation": abbrev},
                "score": str(score), "linescores": [{"value": v} for v in lines]}
    return {"date": date, "status": {"type": {"completed": completed}},
            "competitions": [{"competitors": [comp("home", home, home_lines, home_score),
                                              comp("away", away, away_lines, away_score)]}]}


def test_one_row_per_period_under_our_game_id():
    rows = parse_period_rows({"events": [_event([30, 28, 25, 29], [27, 26, 30, 24], 112, 107)]})
    assert [r["period"] for r in rows] == [1, 2, 3, 4]
    assert rows[0] == {"game_id": "NBA_2026-01-15_PHX_DET", "period": 1, "home_points": 30,
                       "away_points": 27, "source": "espn_scoreboard"}


def test_overtime_periods_follow_the_fourth():
    rows = parse_period_rows({"events": [_event([25, 25, 25, 25, 10], [25, 25, 25, 25, 8], 110, 108)]})
    assert [r["period"] for r in rows] == [1, 2, 3, 4, 5]


def test_quarters_that_do_not_sum_to_the_final_are_skipped():
    assert parse_period_rows({"events": [_event([30, 28, 25, 29], [27, 26, 30, 24], 113, 107)]}) == []


def test_unfinished_games_and_mismatched_period_counts_are_skipped():
    assert parse_period_rows({"events": [_event([30, 28], [27, 26], 58, 53, completed=False)]}) == []
    assert parse_period_rows({"events": [_event([30, 28, 25, 29, 5], [27, 26, 30, 24], 117, 107)]}) == []


def test_espn_team_codes_map_to_ours():
    rows = parse_period_rows({"events": [_event([30, 28, 25, 29], [27, 26, 30, 24], 112, 107,
                                                home="GS", away="NY")]})
    assert rows[0]["game_id"] == "NBA_2026-01-15_NYK_GSW"
