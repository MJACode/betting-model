"""The projection model's schedule inputs see every regular-season game.

The 2026-27 schedule was loaded on 2026-10-15, before the league set the NBA
Cup week: 24 regular-season games were not in it. models.nba_props.team_games
kept a game only if the schedule listed it (or its box was in the box frame,
which was itself limited to listed games), so a Cup week game dropped out of
both teams' rest, back-to-back, games-in-four-days and road trip, and out of
every player's history -- even after it was played and its box stored (the
same block removed from 2023-24..2025-26: 30 team-games a season with the wrong
rest). These pin that a game `games` holds counts whether or not the schedule
lists it yet, that the postseason stays out (the graded population), and that
nothing changes when every game is listed (the graded frame).
"""
from __future__ import annotations

import pandas as pd

import models.nba_prop_projection as pj
import models.nba_props as nb

A = "NBA_2026-12-05_LAL_BOS"          # listed
CUP = "NBA_2026-12-08_BOS_NYK"        # a Cup week game the October load never had
B = "NBA_2026-12-09_MIA_BOS"          # listed: the night after CUP
PO = "NBA_2027-04-20_BOS_ORL"         # a playoff game


def _games(*ids):
    rows = []
    for gid in ids:
        _, d, away, home = gid.split("_")
        rows.append({"game_id": gid, "season": 2027, "game_date": d, "home_team": home,
                     "away_team": away, "commence_time": f"{d}T23:30:00+00:00"})
    return pd.DataFrame(rows)


def _schedule(extra=()):
    rows = [("NBA_2026-10-20_HOU_OKC", "2026-10-20", "regular"),       # the season's first day
            ("NBA_2027-04-11_DAL_SAS", "2027-04-11", "regular"),       # and its last
            (A, "2026-12-05", "regular"), (B, "2026-12-09", "regular"),
            (PO, "2027-04-20", "playoff"), *extra]
    return pd.DataFrame([{"game_id": g, "season": 2027, "game_date": d, "game_type": t,
                          "commence_time": f"{d}T23:30:00+00:00"} for g, d, t in rows])


def _data(games, schedule, adv=None):
    return {"nba_games": games, "nba_schedule": schedule,
            "nba_player_game_adv": adv if adv is not None else pd.DataFrame(columns=["game_id"])}


def _bos(t):
    return t[t.team == "BOS"].set_index("game_id")


def test_a_cup_week_game_the_schedule_does_not_list_still_counts_for_rest():
    t = _bos(nb.team_games(_data(_games(A, CUP, B), _schedule())))
    assert CUP in t.index
    assert (t.loc[B, "rest"], t.loc[B, "b2b"], t.loc[B, "g4d"]) == (1, 1.0, 2.0)
    assert t.loc[CUP, "road_trip"] == 1 and t.loc[B, "road_trip"] == 0


def test_the_same_game_once_the_refresh_lists_it_reads_the_same():
    listed = _schedule(extra=[(CUP, "2026-12-08", "regular")])
    a = _bos(nb.team_games(_data(_games(A, CUP, B), _schedule())))
    b = _bos(nb.team_games(_data(_games(A, CUP, B), listed)))
    pd.testing.assert_frame_equal(a[["rest", "b2b", "g4d", "road_trip"]], b[["rest", "b2b", "g4d", "road_trip"]])


def test_the_postseason_and_a_day_of_another_kind_stay_out():
    """A playoff game is not a regular-season game; an unlisted game on a day the
    schedule gives the Cup final is the final, which counts only once listed."""
    final_day = "NBA_2026-12-11_BOS_SAS"
    sched = _schedule(extra=[("NBA_2026-12-11_nan_nan", "2026-12-11", "cup_final")])
    t = _bos(nb.team_games(_data(_games(A, B, PO, final_day), sched)))
    assert PO not in t.index and final_day not in t.index
    sched = _schedule(extra=[(final_day, "2026-12-11", "cup_final")])
    assert final_day in _bos(nb.team_games(_data(_games(A, B, final_day), sched))).index


def test_nothing_changes_when_the_schedule_lists_every_game():
    """The graded frame: on 2026-10-20 no NBA games row of 2018-19..2026-27 was
    unlisted (production), so the new rule adds nothing to it."""
    g = _games(A, B, PO)
    assert nb.regular_game_ids(g, _schedule()) == {"NBA_2026-10-20_HOU_OKC", "NBA_2027-04-11_DAL_SAS", A, B}


def test_a_cup_week_box_enters_the_players_history():
    log = pd.DataFrame([{"game_id": gid, "player_id": "1628369", "player_name": "Jayson Tatum",
                         "team": "BOS", "season": 2027, "game_date": gid.split("_")[1], "minutes": 36,
                         "is_starter": 1} for gid in (A, CUP)])
    box = pj.box_from_log(log, _games(A, CUP, B), _schedule())
    assert set(box.game_id) == {A, CUP}
