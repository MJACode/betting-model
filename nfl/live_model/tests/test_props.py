"""
Prop engine: game script, opportunity, and the injury gate.

The game-script behaviour is the whole thesis of the prop lane, so it is
tested as a MECHANISM (the direction and rough magnitude of the response to the
scoreboard) rather than against fixed numbers that a retrain would break.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from live_model.engine.props import (  # noqa: E402
    detect_inactive, price_over, project, remaining_team_plays,
    script_pass_rate,
)
from live_model.state import GameState, PlayerState  # noqa: E402

NOW = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)


def game(diff: int, period: int = 4, clock: int = 600) -> GameState:
    """`diff` is the HOME margin."""
    home = 21 + max(diff, 0)
    away = 21 - min(diff, 0)
    return GameState("g", NOW, period, clock, home, away, "home", 1, 10, 50,
                     3, 3, -3.0, 46.0, None, True, 90, 0.58, 0.58)


def rb(active=True):
    return PlayerState("rb", "g", NOW, "home", "RB", 0, 0, 0, 0, 12, 55, 3, 2,
                       14, 0.55, active)


def wr(active=True):
    return PlayerState("wr", "g", NOW, "home", "WR", 0, 0, 0, 0, 0, 0, 7, 5,
                       62, 0.72, active)


def qb(active=True):
    return PlayerState("qb", "g", NOW, "home", "QB", 24, 16, 190, 1, 2, 8, 0,
                       0, 0, 1.0, active)


# ------------------------------------------------------------- game script
def test_trailing_teams_throw_and_leading_teams_run():
    down = script_pass_rate(game(-14), "home")
    tied = script_pass_rate(game(0), "home")
    up = script_pass_rate(game(+14), "home")
    assert down > tied > up
    assert down > 0.8 and up < 0.35


def test_the_script_effect_strengthens_as_the_clock_runs_out():
    """Down 10 in the first quarter is a game; down 10 with five minutes left
    is a mandate. If the model does not steepen, it will keep pricing fourth
    quarter props off first quarter tendencies, which is the exact error the
    books make and the reason this lane exists."""
    early = script_pass_rate(game(-10, period=1, clock=600), "home")
    late = script_pass_rate(game(-10, period=4, clock=300), "home")
    assert late > early


def test_the_pass_rate_never_reaches_a_certainty():
    for diff in (-40, -21, 0, 21, 40):
        r = script_pass_rate(game(diff), "home")
        assert 0.1 < r < 0.95


def test_a_trailing_team_runs_more_plays_than_a_leading_one():
    assert remaining_team_plays(game(-14), "home") > remaining_team_plays(game(14), "home")


def test_remaining_plays_go_to_zero_with_the_clock():
    assert remaining_team_plays(game(0, period=4, clock=0), "home") == 0.0


# ------------------------------------------------------------- projections
def test_trailing_collapses_the_run_game_and_lifts_the_pass_game():
    """The headline case: a team down two scores in the fourth. The back's
    remaining rushing yards should fall away and the receiver's and the
    quarterback's should rise. This is the edge, stated as a test."""
    down, up = game(-14), game(+14)
    rush_down = project(rb(), down, "player_rush_yds", 90.0).mu_remaining
    rush_up = project(rb(), up, "player_rush_yds", 90.0).mu_remaining
    rec_down = project(wr(), down, "player_reception_yds", 90.0).mu_remaining
    rec_up = project(wr(), up, "player_reception_yds", 90.0).mu_remaining
    assert rush_down < rush_up
    assert rec_down > rec_up


def test_accrued_production_is_carried_not_re_predicted():
    p = project(qb(), game(0), "player_pass_yds", 90.0)
    assert p.accrued == 190
    assert p.mu_remaining > 0


def test_variance_grows_with_the_opportunity_count():
    """A compound distribution: more snaps left means a wider outcome, which is
    what keeps a late prop from being priced with absurd certainty."""
    early = project(wr(), game(0, period=1, clock=900), "player_reception_yds", 20.0)
    late = project(wr(), game(0, period=4, clock=120), "player_reception_yds", 120.0)
    assert early.var_remaining > late.var_remaining


def test_efficiency_shrinks_toward_the_positional_prior():
    """A back averaging 12 yards a carry on three carries is not a 12 yards a
    carry back. Without shrinkage the model bets that noise every week."""
    hot = PlayerState("x", "g", NOW, "home", "RB", 0, 0, 0, 0, 3, 36, 0, 0, 0,
                      0.5, True)
    p = project(hot, game(0), "player_rush_yds", 40.0)
    implied = p.mu_remaining / max(
        remaining_team_plays(game(0), "home")
        * (1 - script_pass_rate(game(0), "home")) * 0.5, 1e-9)
    assert implied < 9.0        # nowhere near the observed 12.0


# ------------------------------------------------------------- injury gate
def test_an_inactive_player_can_never_be_bet_over():
    """The failure mode: a book leaves a line up after a player walks off, the
    model sees a huge gap, and we bet the over on a man in the blue tent."""
    p = project(qb(active=False), game(0), "player_pass_yds", 90.0)
    assert not p.active
    assert p.mu_remaining == 0.0
    assert price_over(p, 250)["over"] == 0.0


def test_an_inactive_player_already_past_the_line_is_settled_not_bet():
    p = project(qb(active=False), game(0), "player_pass_yds", 90.0)
    assert price_over(p, 150)["over"] == 1.0     # 190 accrued, already over
    assert price_over(p, 150)["degenerate"]


def test_inactivity_is_detected_only_after_meaningful_absence():
    """Conservative on purpose. Standing a healthy player down costs a bet we
    do not make; the opposite costs a bet we should not have made."""
    assert not detect_inactive(qb(), qb(), team_plays_since=3)
    assert detect_inactive(qb(), qb(), team_plays_since=15)
    touched = PlayerState("qb", "g", NOW, "home", "QB", 26, 17, 205, 1, 2, 8,
                          0, 0, 0, 1.0, True)
    assert not detect_inactive(qb(), touched, team_plays_since=30)
    assert not detect_inactive(None, qb(), team_plays_since=99)


# ---------------------------------------------------------------- pricing
def test_over_and_under_sum_to_one():
    p = project(wr(), game(0), "player_reception_yds", 90.0)
    q = price_over(p, p.accrued + 15)
    assert q["over"] + q["under"] == pytest.approx(1.0)


def test_the_over_gets_harder_as_the_line_rises():
    p = project(wr(), game(0), "player_reception_yds", 90.0)
    probs = [price_over(p, p.accrued + k)["over"] for k in range(0, 60, 5)]
    assert all(a >= b for a, b in zip(probs, probs[1:]))


def test_count_markets_get_a_continuity_correction():
    """Receptions are integers. Without the half point correction the over on
    a whole number line is systematically mispriced."""
    p = project(wr(), game(0), "player_receptions", 90.0)
    assert 0.0 < price_over(p, p.accrued + 2)["over"] < 1.0


def test_an_unsupported_market_raises_rather_than_guessing():
    with pytest.raises(ValueError):
        project(wr(), game(0), "player_field_goals", 90.0)
