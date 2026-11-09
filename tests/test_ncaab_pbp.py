"""NCAAB play-by-play: one parser for the season files and ESPN's live summary,
in OUR orientation, with the clock the model reads."""
from __future__ import annotations

import pandas as pd

from data.ingestors import ncaab_pbp as P


def test_clock_and_game_seconds():
    assert P.clock_seconds("19:58") == 1198
    assert P.clock_seconds("0:07.4") == 7.4
    assert P.clock_seconds(None) is None
    assert P.game_seconds(1, 1198) == 2          # two seconds into the first half
    assert P.game_seconds(1, 0) == 1200
    assert P.game_seconds(2, 0) == 2400          # end of regulation
    assert P.game_seconds(3, 300) == 2400        # start of the first overtime
    assert P.game_seconds(4, 0) == 3000


def _kw(**over):
    base = dict(espn_game_id=1, play_no=1, sequence_number=10, game_id="NCAAB_x", season=2026,
                season_type=2, period=1, clock_display="15:00", wallclock="2026-02-07T21:15:00Z",
                type_id=558, type_text="JumpShot", scoring_play=True, shooting_play=True,
                score_value=2, points_attempted=2, home_score=10, away_score=4, team_id=12,
                home_espn_id=12, away_espn_id=197, athlete_id_1=None, athlete_id_2=None,
                text="made", swapped=False, source="t")
    base.update(over)
    return base


def test_play_row_keeps_or_swaps_to_our_orientation():
    r = P.play_row(**_kw())
    assert (r["home_score"], r["away_score"], r["team_side"]) == (10, 4, "H")
    assert r["game_s"] == 300
    # ESPN listed 12 home; our games row has 197 home: scores and side turn round
    s = P.play_row(**_kw(swapped=True))
    assert (s["home_score"], s["away_score"], s["team_side"]) == (4, 10, "A")


def test_orientation_against_the_stored_event():
    ev = {"home_espn_id": 12, "away_espn_id": 197}
    assert P.orientation(12, 197, ev) is False
    assert P.orientation(197, 12, ev) is True
    assert P.orientation(12, 999, ev) is None


def test_summary_rows_read_the_competitors_for_orientation():
    summary = {"header": {"season": {"type": 2}, "competitions": [{"competitors": [
        {"homeAway": "home", "team": {"id": "12"}}, {"homeAway": "away", "team": {"id": "197"}}]}]},
        "plays": [{"sequenceNumber": "1", "period": {"number": 1}, "clock": {"displayValue": "20:00"},
                   "wallclock": "2026-02-07T21:10:04Z", "type": {"id": "615", "text": "Jumpball"},
                   "homeScore": 0, "awayScore": 0},
                  {"sequenceNumber": "2", "period": {"number": 1}, "clock": {"displayValue": "19:40"},
                   "wallclock": "2026-02-07T21:10:25Z", "type": {"id": "572", "text": "LayUpShot"},
                   "homeScore": 2, "awayScore": 0, "scoringPlay": True, "scoreValue": 2,
                   "team": {"id": "12"}}]}
    rows = P.summary_rows(summary, espn_game_id=1, game_id="g", season=2026,
                          home_espn_id=197, away_espn_id=12)
    # our games row has 197 home: ESPN's home 2 points are the AWAY team's
    assert [(r["play_no"], r["home_score"], r["away_score"], r["team_side"]) for r in rows] == \
        [(1, 0, 0, None), (2, 0, 2, "A")]
    assert rows[1]["game_s"] == 20 and rows[1]["source"] == P.LIVE_SOURCE


def test_release_games_groups_each_game_in_play_order():
    df = pd.DataFrame({"game_id": [2, 1, 1, 2], "game_play_number": [1, 2, 1, 2],
                       "home_team_id": [5, 3, 3, 5]})
    got = [(g, [r["game_play_number"] for r in recs]) for g, recs in P.release_games(df)]
    assert got == [(1, [1, 2]), (2, [1, 2])]


def test_ledger_reads_numeric_final_scores_as_integers():
    rows = [P.play_row(**_kw()), P.play_row(**_kw(play_no=2, home_score=80, away_score=70))]
    led = P.game_ledger(rows, event={"game_id": "g", "home_score": 80.0, "away_score": 70.0},
                        swapped=False, source="t")
    assert led["games_home_score"] == 80 and isinstance(led["games_home_score"], int)
    assert led["score_matches"] is True
