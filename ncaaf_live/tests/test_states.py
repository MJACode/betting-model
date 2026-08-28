"""
Tests for the CFB state builder.

The two failure modes these exist to catch are silent and fatal:

  * a wrong pre/post score convention trains the model on states that already
    contain the touchdown being predicted - a leak that produces a beautiful
    calibration and a worthless engine;
  * a wrong offense/defense -> home/away relabelling swaps every score and
    possession flag on exactly the plays where possession changed, which no
    aggregate metric would ever surface.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ncaaf_live.backtest.states import (  # noqa: E402
    _classify, _detect_score_convention, build_states)


def _plays(rows):
    """rows: list of dicts; fill CFBD-shaped defaults."""
    base = {
        "id": 0, "gameId": 1, "driveId": 1, "playNumber": 0,
        "period": 1, "clock_minutes": 10, "clock_seconds": 0,
        "offense": "Home U", "defense": "Away U",
        "home": "Home U", "away": "Away U",
        "offenseScore": 0, "defenseScore": 0,
        "offenseTimeouts": 3, "defenseTimeouts": 3,
        "down": 1, "distance": 10, "yardsToGoal": 75, "yardsGained": 0,
        "playType": "Rush", "scoring": False,
        "wallclock": "2024-09-07T18:00:00.000Z",
        "season": 2024, "week": 2, "season_type": "regular",
    }
    out = []
    for i, r in enumerate(rows):
        d = dict(base)
        d.update(r)
        d["playNumber"] = r.get("playNumber", i + 1)
        d["id"] = i + 1
        out.append(d)
    return pd.DataFrame(out)


def _platform(final_home=28, final_away=17, **kw):
    row = {"game_id": "NCAAF_2024-09-07_away-u_home-u", "season": 2024,
           "week": 2, "game_date": "2024-09-07",
           "home_team": "Home U", "away_team": "Away U",
           "final_home": final_home, "final_away": final_away,
           "pregame_spread": -7.0, "pregame_total": 52.5,
           "wind_mph": 5.0, "is_dome": False}
    row.update(kw)
    return pd.DataFrame([row])


# ── score convention detection ────────────────────────────────────────────────

def _post_convention_game():
    """Scores that already include the play's points (change ON the row)."""
    return _plays([
        {"offenseScore": 0, "defenseScore": 0},
        {"offenseScore": 7, "defenseScore": 0, "scoring": True,
         "playType": "Passing Touchdown"},
        {"offenseScore": 7, "defenseScore": 0},
        {"offense": "Away U", "defense": "Home U",
         "offenseScore": 3, "defenseScore": 7, "scoring": True,
         "playType": "Field Goal Good"},
    ])


def _pre_convention_game():
    """Scores as the play STARTED (change on the row AFTER the score)."""
    return _plays([
        {"offenseScore": 0, "defenseScore": 0},
        {"offenseScore": 0, "defenseScore": 0, "scoring": True,
         "playType": "Passing Touchdown"},
        {"offenseScore": 7, "defenseScore": 0},
        {"offense": "Away U", "defense": "Home U",
         "offenseScore": 0, "defenseScore": 7, "scoring": True,
         "playType": "Field Goal Good"},
    ])


def _with_raw(df):
    hb = df["offense"].eq(df["home"])
    df = df.copy()
    df["home_pts_raw"] = np.where(hb, df["offenseScore"], df["defenseScore"])
    df["away_pts_raw"] = np.where(hb, df["defenseScore"], df["offenseScore"])
    return df


def test_post_convention_is_detected():
    assert _detect_score_convention(_with_raw(_post_convention_game())) == "post"


def test_pre_convention_is_detected():
    assert _detect_score_convention(_with_raw(_pre_convention_game())) == "pre"


def test_ambiguous_convention_refuses_to_build():
    """Half the scoring plays behaving each way = the feed shape drifted."""
    a = _with_raw(_post_convention_game())
    b = _with_raw(_pre_convention_game())
    b["gameId"] = 2
    with pytest.raises(AssertionError):
        _detect_score_convention(pd.concat([a, b], ignore_index=True))


# ── the leak itself ───────────────────────────────────────────────────────────

def test_a_scoring_plays_state_does_not_contain_its_own_points():
    """
    THE test. Under the post convention, the TD play's row carries 7-0; the
    state a bettor faced was 0-0, and the remaining-points target from that
    state must still include the 7.
    """
    st = build_states(_post_convention_game(), _platform(final_home=28))
    td = st[st["playType"] == "Passing Touchdown"].iloc[0]
    assert td["home_score"] == 0.0, "the TD leaked into its own pre-play state"
    assert td["home_remaining_pts"] == 28.0

    after = st[st["playNumber"] == 3].iloc[0]
    assert after["home_score"] == 7.0
    assert after["home_remaining_pts"] == 21.0


def test_pre_convention_scores_are_used_directly():
    st = build_states(_pre_convention_game(), _platform(final_home=28))
    td = st[st["playType"] == "Passing Touchdown"].iloc[0]
    assert td["home_score"] == 0.0
    assert st[st["playNumber"] == 3].iloc[0]["home_score"] == 7.0


# ── relabelling ───────────────────────────────────────────────────────────────

def test_offense_relative_fields_map_by_possession():
    """When the AWAY team has the ball, offenseScore is the AWAY score."""
    plays = _plays([
        {"offenseScore": 0, "defenseScore": 0},
        {"offense": "Away U", "defense": "Home U",
         "offenseScore": 0, "defenseScore": 0,
         "offenseTimeouts": 2, "defenseTimeouts": 3},
        {"offense": "Away U", "defense": "Home U",
         "offenseScore": 7, "defenseScore": 0, "scoring": True,
         "playType": "Rushing Touchdown"},
        {"offenseScore": 0, "defenseScore": 7},
    ])
    st = build_states(plays, _platform(final_home=14, final_away=7))
    away_poss = st[st["playNumber"] == 2].iloc[0]
    assert away_poss["has_ball_home"] == 0.0
    assert away_poss["home_timeouts"] == 3.0   # defense's timeouts are HOME's
    assert away_poss["away_timeouts"] == 2.0
    last = st[st["playNumber"] == 4].iloc[0]
    assert last["away_score"] == 7.0 and last["home_score"] == 0.0


# ── clock ─────────────────────────────────────────────────────────────────────

def test_seconds_remaining_spans_periods():
    plays = _plays([
        {"period": 1, "clock_minutes": 15, "clock_seconds": 0},
        {"period": 2, "clock_minutes": 7, "clock_seconds": 30},
        {"period": 4, "clock_minutes": 0, "clock_seconds": 42},
    ])
    st = build_states(plays, _platform())
    assert st.iloc[0]["seconds_remaining"] == 3600.0
    assert st.iloc[1]["seconds_remaining"] == 450 + 2 * 900
    assert st.iloc[2]["seconds_remaining"] == 42.0
    assert st.iloc[1]["half_seconds_remaining"] == 450.0


# ── OT and targets ────────────────────────────────────────────────────────────

def test_ot_states_dropped_but_ot_points_stay_in_targets():
    """
    Markets settle including OT, so the TARGET from a Q4 state includes OT
    scoring - while the OT rows themselves are unpriceable and dropped.
    """
    # A real (post-convention) score history: games start 0-0, which is what
    # lets the shift produce correct pre-play scores. An earlier fixture that
    # STARTED mid-game at 21-21 was testing an impossible input.
    plays = _plays([
        {"period": 1, "offenseScore": 0, "defenseScore": 0},
        {"period": 2, "offenseScore": 21, "defenseScore": 14, "scoring": True,
         "playType": "Passing Touchdown"},
        {"period": 3, "offense": "Away U", "defense": "Home U",
         "offenseScore": 21, "defenseScore": 21, "scoring": True,
         "playType": "Rushing Touchdown"},
        {"period": 4, "clock_minutes": 0, "clock_seconds": 30,
         "offenseScore": 21, "defenseScore": 21},
        {"period": 5, "clock_minutes": 0, "clock_seconds": 0,
         "offenseScore": 21, "defenseScore": 21},
    ])
    st = build_states(plays, _platform(final_home=28, final_away=21))
    assert (st["period"] <= 4).all(), "an OT state survived the filter"
    q4 = st.iloc[-1]
    assert q4["home_remaining_pts"] == 7.0, "OT points missing from the target"


def test_negative_target_drops_the_whole_game():
    """A final below a mid-game score = untrustworthy series, all of it."""
    plays = _post_convention_game()
    st = build_states(plays, _platform(final_home=3, final_away=0))
    assert st.empty
    assert st.attrs["dropped_games_negative_target"] == 1


def test_missing_pregame_line_filters_the_game():
    """No market number -> nothing to anchor to -> not a training state."""
    st = build_states(_post_convention_game(),
                      _platform(pregame_total=np.nan))
    assert st.empty


# ── playType routing ──────────────────────────────────────────────────────────

def test_playtype_classes():
    cls = _classify(pd.Series([
        "Pass Reception", "Pass Incompletion", "Sack", "Rush",
        "Rushing Touchdown", "Punt", "Field Goal Good", "Kickoff",
        "Timeout", "Penalty", "End Period", "Pass Interception Return",
    ]))
    assert cls["is_pass"].tolist() == [True, True, True, False, False, False,
                                       False, False, False, False, False, True]
    assert cls["is_rush"].tolist() == [False, False, False, True, True, False,
                                       False, False, False, False, False, False]
    # kickoffs/timeouts/penalties/period markers are NOT scrimmage plays
    assert cls["is_scrim"].tolist() == [True, True, True, True, True, True,
                                        True, False, False, False, False, True]


def test_pass_rate_is_strictly_pre_play():
    plays = _plays([
        {"playType": "Pass Reception"},
        {"playType": "Pass Reception"},
        {"playType": "Rush"},
    ])
    st = build_states(plays, _platform())
    # the first play sees only the prior (no plays yet)
    from ncaaf_live.config import LEAGUE_PASS_RATE
    assert st.iloc[0]["home_pass_rate"] == pytest.approx(LEAGUE_PASS_RATE)
    # the third play has seen 2 passes in 2 plays - rate above prior, and the
    # play itself (a rush) is not in its own denominator
    assert st.iloc[2]["home_pass_rate"] > LEAGUE_PASS_RATE


# ── platform join ─────────────────────────────────────────────────────────────

def test_join_key_is_exact_and_carries_the_line():
    st = build_states(_post_convention_game(), _platform())
    assert (st["pregame_total"] == 52.5).all()
    assert (st["game_id"] == "NCAAF_2024-09-07_away-u_home-u").all()


def test_halftime_scores_carried_for_2h_settlement():
    plays = _plays([
        {"period": 1, "offenseScore": 0, "defenseScore": 0},
        {"period": 2, "offenseScore": 14, "defenseScore": 3, "scoring": True,
         "playType": "Passing Touchdown"},
        {"period": 3, "offenseScore": 14, "defenseScore": 3},
    ])
    st = build_states(plays, _platform(final_home=28, final_away=10))
    assert (st["half_home_score"] == 14.0).all()
    assert (st["half_away_score"] == 3.0).all()


def test_rematch_resolves_to_the_nearest_date():
    """
    Two platform rows for the same (season, home, away) - a week-1 meeting and
    a bowl rematch. The pbp wallclock date must pick the right one; a
    week-keyed join would collide (postseason weeks restart at 1).
    """
    plat = pd.concat([
        _platform(final_home=28, final_away=17, game_date="2024-09-07"),
        _platform(final_home=45, final_away=44, game_date="2024-12-28",
                  game_id="NCAAF_2024-12-28_away-u_home-u"),
    ], ignore_index=True)
    st = build_states(_post_convention_game(), plat)
    assert (st["final_home"] == 28).all(), "joined to the bowl rematch row"
    assert (st["game_id"] == "NCAAF_2024-09-07_away-u_home-u").all()


def test_no_platform_row_within_two_days_means_no_states():
    st = build_states(_post_convention_game(),
                      _platform(game_date="2024-11-30"))
    assert st.empty, "a 12-week date gap must not be bridged"


def test_play_order_is_drive_then_play_number_not_play_number_alone():
    """
    Regression for the scrambled-order bug: CFBD playNumber is a PER-DRIVE
    counter, so plays arriving drive-interleaved must re-order by
    (driveId, playNumber). Under the wrong sort the second drive's play 1
    lands before the first drive's play 2 and every shift-based quantity
    (pre-play scores, pace, pass rate) reads a scrambled game.
    """
    plays = _plays([
        {"driveId": 2, "playNumber": 1, "offenseScore": 7, "defenseScore": 0},
        {"driveId": 1, "playNumber": 1, "offenseScore": 0, "defenseScore": 0},
        {"driveId": 1, "playNumber": 2, "offenseScore": 7, "defenseScore": 0,
         "scoring": True, "playType": "Passing Touchdown"},
    ])
    st = build_states(plays, _platform(final_home=28))
    assert st.iloc[0]["driveId"] == 1
    td = st[st["playType"] == "Passing Touchdown"].iloc[0]
    assert td["home_score"] == 0.0, "scrambled order leaked the TD into itself"
    # the drive-2 play comes AFTER the TD and sees the 7
    assert st.iloc[-1]["driveId"] == 2
    assert st.iloc[-1]["home_score"] == 7.0
