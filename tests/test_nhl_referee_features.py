"""Referee features for the NHL total: point-in-time, shrunk, and off by default.

The live card prices Pinnacle's no-vig. These tests pin the three ways that
would make the backtest lie: a referee's own game in his prior, a future game
in an earlier prior, and the production flag moving a bet.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import models.nhl_referee_features as rf
import models.nhl_totals_market as mk

T0 = "2026-10-07 20:17:07.100000+00"
T1 = "2026-10-07 21:00:07.200000+00"


def _games():
    return pd.DataFrame([
        {"game_id": "G0", "commence_time": "2024-01-01T00:00:00Z", "goals": 4, "pp_opp": 2, "penalties": 2},
        {"game_id": "G1", "commence_time": "2024-01-02T00:00:00Z", "goals": 8, "pp_opp": 6, "penalties": 6},
        {"game_id": "G2", "commence_time": "2024-01-03T00:00:00Z", "goals": 6, "pp_opp": 4, "penalties": 4},
    ])


def _officials():
    return pd.DataFrame([
        {"game_id": "G0", "role": "referee", "full_name": "A"},
        {"game_id": "G1", "role": "referee", "full_name": "B"},
        {"game_id": "G2", "role": "referee", "full_name": "A"},
        {"game_id": "G2", "role": "linesman", "full_name": "L"},
    ])


def test_shrinkage_is_the_league_mean_when_the_sample_is_empty():
    assert rf.shrunk_deviation(0, 0, 6.0, k=50) == 0.0
    # One earlier game at 4, league mean 6, prior weight 50.
    assert rf.shrunk_deviation(4, 1, 6.0, k=50) == pytest.approx(304 / 51 - 6)


def test_a_referees_own_game_and_later_games_stay_out_of_his_prior():
    built = rf.build_referee_features(_games(), _officials(), k=50)
    by = built.set_index("game_id")
    assert by.loc["G0", "ref_goals_dev"] == 0.0
    assert by.loc["G1", "ref_goals_dev"] == 0.0
    assert by.loc["G2", "ref_goals_dev"] == pytest.approx(304 / 51 - 6)
    assert int(by.loc["G2", "ref_n_mean"]) == 1

    later = _games()
    later.loc[later.game_id == "G2", "goals"] = 99
    again = rf.build_referee_features(later, _officials(), k=50).set_index("game_id")
    assert again.loc["G2", "ref_goals_dev"] == pytest.approx(by.loc["G2", "ref_goals_dev"])
    assert again.loc["G0", "ref_goals_dev"] == 0.0

    moved = _games()
    moved.loc[moved.game_id == "G0", "goals"] = 10
    changed = rf.build_referee_features(moved, _officials(), k=50).set_index("game_id")
    # Ref A prior sum is now 10, league mean of G0 and G1 is 9.
    assert changed.loc["G2", "ref_goals_dev"] == pytest.approx(rf.shrunk_deviation(10, 1, 9.0, k=50))
    assert changed.loc["G2", "ref_goals_dev"] != pytest.approx(by.loc["G2", "ref_goals_dev"])


def test_two_games_at_one_commence_time_do_not_inform_each_other():
    games = pd.DataFrame([
        {"game_id": "A", "commence_time": "2024-01-01T00:00:00Z", "goals": 2, "pp_opp": 1, "penalties": 1},
        {"game_id": "B", "commence_time": "2024-01-02T01:00:00Z", "goals": 9, "pp_opp": 5, "penalties": 5},
        {"game_id": "C", "commence_time": "2024-01-02T01:00:00Z", "goals": 3, "pp_opp": 2, "penalties": 2},
    ])
    officials = pd.DataFrame([
        {"game_id": "A", "role": "referee", "full_name": "A"},
        {"game_id": "B", "role": "referee", "full_name": "A"},
        {"game_id": "C", "role": "referee", "full_name": "A"},
    ])
    built = rf.build_referee_features(games, officials, k=50).set_index("game_id")
    # Both B and C see only game A. Neither sees the other.
    assert built.loc["B", "ref_goals_dev"] == pytest.approx(built.loc["C", "ref_goals_dev"])
    assert built.loc["B", "ref_n_mean"] == 1


def test_walk_forward_folds_use_only_earlier_seasons():
    assert rf.season_folds([2026, 2024, 2025]) == [([2024], 2025), ([2024, 2025], 2026)]
    assert rf.season_folds([2024]) == []


def test_zero_features_leave_pinnacle_unchanged():
    X = np.zeros((200, 3))
    y = np.array([0.0, 1.0] * 100)
    offset = np.zeros(200)
    model = rf.RefTotalsModel(C=1.0, intercept=False).fit(X, y, offset)
    features = {name: 0.0 for name in rf.FEATURES}
    assert model.adjust_over(0.53, features) == pytest.approx(0.53, abs=1e-9)


def test_the_first_plus_ev_snapshot_is_the_bet_and_a_later_one_is_not():
    long = pd.DataFrame([
        {"game_id": "G", "snap_t": 2, "ev": 0.05, "book_ord": 0, "side": "over", "price": -110},
        {"game_id": "G", "snap_t": 1, "ev": 0.02, "book_ord": 1, "side": "under", "price": -105},
        {"game_id": "G", "snap_t": 1, "ev": 0.009, "book_ord": 0, "side": "over", "price": 100},
    ])
    picked = rf.select_first_plus_ev(long, 0.01)
    assert len(picked) == 1
    assert picked.iloc[0]["side"] == "under"
    assert picked.iloc[0]["snap_t"] == 1
    assert rf.flat_profit(6, 6.0, "over", -110) == 0.0
    assert rf.flat_profit(7, 6.0, "over", -110) == pytest.approx(100 / 110)
    assert rf.flat_profit(5, 6.0, "over", -110) == -1.0


def test_the_flag_ships_off_and_a_passed_model_does_not_move_the_live_rule():
    assert mk.USE_NHL_REF_FEATURES is False

    class _PushOver:
        def adjust_over(self, p_over, features):
            return 0.9

    pin = {
        "game_id": "NHL_2026-10-08_PHI_OTT", "book": "pinnacle", "created_at": T1,
        "snapshot_at": "2026-10-07T21:00:07Z", "total_line": 6.0,
        "over_price": 104, "under_price": -119,
    }
    soft = {
        "game_id": "NHL_2026-10-08_PHI_OTT", "book": "betmgm", "created_at": T1,
        "snapshot_at": "2026-10-07T21:00:07Z", "total_line": 6.0,
        "over_price": -115, "under_price": -105,
    }
    plain, _ = mk.find_bets([pin, soft])
    forced, _ = mk.find_bets(
        [pin, soft], ref_model=_PushOver(),
        ref_by_game={"NHL_2026-10-08_PHI_OTT": {"ref_goals_dev": 5.0}},
    )
    assert len(plain) == 1 and plain[0].side == "under"
    assert [(b.side, b.price, b.fair) for b in forced] == [(b.side, b.price, b.fair) for b in plain]

    mk.USE_NHL_REF_FEATURES = True
    try:
        moved, _ = mk.find_bets(
            [pin, soft], ref_model=_PushOver(),
            ref_by_game={"NHL_2026-10-08_PHI_OTT": {"ref_goals_dev": 5.0}},
        )
    finally:
        mk.USE_NHL_REF_FEATURES = False
    assert len(moved) == 1
    assert moved[0].side == "over"
    assert moved[0].fair == pytest.approx(0.9)
    assert mk.USE_NHL_REF_FEATURES is False
