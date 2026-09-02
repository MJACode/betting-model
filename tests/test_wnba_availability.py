"""
Tests for features/wnba_availability.py — pure functions, no DB.

The look-ahead tests are the important ones. Every feature here is built from
games before the one being predicted, and the whole point of the module is to
add tonight's information without adding tonight's outcome.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from features.wnba_availability import (  # noqa: E402
    absence_features,
    absent_teammates,
    build_context_features,
    expected_rotation,
    is_starter_tier,
    prior_rows,
    recent_team_game_dates,
    rotation_rank,
    usage_features,
)


def _row(pid, date, minutes, fga=5, fta=2, pts=10, team="LV"):
    return {
        "player_id": pid, "team": team, "game_date": date, "game_id": f"g_{date}",
        "minutes": minutes, "fg_att": fga, "ft_att": fta, "points": pts,
    }


def _team_rows(n_games=10, players=("p1", "p2", "p3", "p4", "p5", "p6")):
    """n_games of a stable 6-player rotation, dates 2026-06-01..."""
    rows = []
    for g in range(n_games):
        date = f"2026-06-{g + 1:02d}"
        for i, pid in enumerate(players):
            rows.append(_row(pid, date, minutes=32 - i * 4))  # 32,28,24,20,16,12
    return rows


# ── window / prior ────────────────────────────────────────────────────────────

def test_prior_rows_excludes_same_and_future_dates():
    rows = [_row("p1", "2026-06-01", 30), _row("p1", "2026-06-02", 30),
            _row("p1", "2026-06-03", 30)]
    got = prior_rows(rows, "2026-06-02")
    assert [r["game_date"] for r in got] == ["2026-06-01"]


def test_recent_team_game_dates_caps_at_lookback():
    rows = _team_rows(n_games=14)
    dates = recent_team_game_dates(rows, "2026-06-20", lookback=10)
    assert len(dates) == 10
    assert dates[-1] == "2026-06-14"          # most recent prior game
    assert dates[0] == "2026-06-05"           # 10 back


# ── expected rotation ─────────────────────────────────────────────────────────

def test_expected_rotation_applies_minutes_floor():
    rows = _team_rows()
    rot = expected_rotation(rows, "2026-06-11")
    # 32,28,24,20,16 clear the 15-minute bar; 12 does not
    assert set(rot) == {"p1", "p2", "p3", "p4", "p5"}
    assert "p6" not in rot


def test_expected_rotation_applies_appearance_share():
    rows = _team_rows()
    # p7 plays heavy minutes but only twice in ten games -> below 0.5 share
    rows += [_row("p7", "2026-06-01", 30), _row("p7", "2026-06-02", 30)]
    rot = expected_rotation(rows, "2026-06-11")
    assert "p7" not in rot


def test_expected_rotation_ignores_future_games():
    rows = _team_rows(n_games=10)
    # A player who only appears AFTER the game date must never be in tonight's rotation
    rows += [_row("p9", f"2026-06-{d:02d}", 34) for d in range(11, 21)]
    rot = expected_rotation(rows, "2026-06-11")
    assert "p9" not in rot


def test_expected_rotation_empty_before_first_game():
    assert expected_rotation(_team_rows(), "2026-05-01") == {}


def test_expected_rotation_zero_minute_rows_are_not_appearances():
    rows = _team_rows()
    rows += [_row("p8", f"2026-06-{d:02d}", 0) for d in range(1, 11)]
    assert "p8" not in expected_rotation(rows, "2026-06-11")


# ── role ──────────────────────────────────────────────────────────────────────

def test_rotation_rank_orders_by_minutes():
    rot = expected_rotation(_team_rows(), "2026-06-11")
    assert rotation_rank(rot, "p1") == 1
    assert rotation_rank(rot, "p5") == 5
    assert rotation_rank(rot, "p6") is None


def test_is_starter_tier_top_five_only():
    rot = expected_rotation(_team_rows(), "2026-06-11")
    assert is_starter_tier(rot, "p1") == 1
    assert is_starter_tier(rot, "p5") == 1
    assert is_starter_tier(rot, "p6") == 0     # not in rotation at all


# ── absence ───────────────────────────────────────────────────────────────────

def test_absent_teammates_excludes_self_and_present():
    rot = expected_rotation(_team_rows(), "2026-06-11")
    present = {"p1", "p3", "p4"}
    out = absent_teammates(rot, present, exclude_player_id="p1")
    assert sorted(out) == ["p2", "p5"]


def test_absence_features_sum_vacated_workload():
    rot = expected_rotation(_team_rows(), "2026-06-11")
    present = {"p3", "p4", "p5"}               # p1 (32 min) and p2 (28 min) out
    f = absence_features(rot, present, player_id="p3")
    assert f["teammates_out"] == 2
    assert f["teammate_minutes_out"] == 60.0   # 32 + 28
    assert f["teammate_fga_out"] == 10.0       # 5 + 5
    assert f["top_teammate_out"] == 1


def test_absence_features_full_strength_is_all_zero():
    rot = expected_rotation(_team_rows(), "2026-06-11")
    present = set(rot)
    f = absence_features(rot, present, player_id="p3")
    assert f["teammates_out"] == 0
    assert f["teammate_minutes_out"] == 0.0
    assert f["top_teammate_out"] == 0


def test_absence_features_ignore_the_player_themselves():
    """A player's own absence must never count as a teammate being out."""
    rot = expected_rotation(_team_rows(), "2026-06-11")
    present = set(rot) - {"p2"}
    f = absence_features(rot, present, player_id="p2")
    assert f["teammates_out"] == 0


# ── usage ─────────────────────────────────────────────────────────────────────

def test_usage_features_true_shooting_and_rates():
    prior = [_row("p1", f"2026-06-{d:02d}", minutes=30, fga=10, fta=5, pts=25)
             for d in range(1, 11)]
    u = usage_features(prior)
    # TS% = pts / (2 * (FGA + 0.44*FTA)) = 25 / (2 * 12.2)
    assert abs(u["ts_pct"] - 25 / (2 * (10 + 0.44 * 5))) < 1e-4
    assert abs(u["usage_per_min"] - (10 + 0.44 * 5) / 30) < 1e-4
    assert abs(u["pts_per_min"] - 25 / 30) < 1e-4
    assert u["fga_last3_avg"] == 10.0


def test_usage_features_short_window_returns_none_not_zero():
    prior = [_row("p1", "2026-06-01", 30)]
    u = usage_features(prior)
    assert u["fga_last5_avg"] is None          # only 1 prior game
    assert u["fga_last3_avg"] is None


def test_usage_features_empty_history_is_all_none():
    u = usage_features([])
    assert u["ts_pct"] is None and u["usage_per_min"] is None


def test_usage_features_zero_minutes_does_not_divide_by_zero():
    prior = [_row("p1", f"2026-06-{d:02d}", minutes=0, fga=0, fta=0, pts=0)
             for d in range(1, 11)]
    u = usage_features(prior)
    assert u["usage_per_min"] is None
    assert u["pts_per_min"] is None


# ── assembled block ───────────────────────────────────────────────────────────

def test_build_context_features_integration():
    team = _team_rows()
    player = [r for r in team if r["player_id"] == "p3"]
    present = {"p3", "p4", "p5"}               # p1, p2 out
    f = build_context_features(team, player, "p3", "2026-06-11", present)
    assert f["rotation_rank"] == 3
    assert f["is_starter_tier"] == 1
    assert f["teammates_out"] == 2
    assert f["teammate_minutes_out"] == 60.0
    assert f["ts_pct"] is not None


def test_build_context_features_sentinel_rank_for_non_rotation_player():
    team = _team_rows()
    player = [r for r in team if r["player_id"] == "p6"]
    f = build_context_features(team, player, "p6", "2026-06-11", {"p6"})
    assert f["rotation_rank"] == 99            # sentinel, never None
    assert f["is_starter_tier"] == 0


def test_build_context_features_is_look_ahead_safe():
    """Adding games AFTER the target date must not change a single feature."""
    team = _team_rows()
    player = [r for r in team if r["player_id"] == "p3"]
    before = build_context_features(team, player, "p3", "2026-06-11", {"p3", "p4", "p5"})

    future = team + [_row(p, f"2026-06-{d:02d}", 40, fga=20, fta=10, pts=40)
                     for d in range(11, 20) for p in ("p1", "p2", "p3")]
    future_player = [r for r in future if r["player_id"] == "p3"]
    after = build_context_features(future, future_player, "p3", "2026-06-11",
                                   {"p3", "p4", "p5"})
    assert before == after
