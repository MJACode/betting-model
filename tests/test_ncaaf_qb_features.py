"""
Leakage and correctness tests for the NCAAF QB feature layer.

The leakage tests are the ones that matter. A QB feature that peeks at the game
being predicted is the single most dangerous thing in this whole feature set,
because "who started" is nearly a label: the box score of game G names game G's
starter, and a model given that would post a spectacular backtest and lose
money live. So the strictly-prior property is pinned directly rather than
inferred from metrics.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ncaaf_search.qb import (  # noqa: E402
    build_qb_team_features, merge_qb_features, QB_TEAM_COLS, QB_FEATURES,
    RECENT_GAMES,
)


def _qb_rows(team: str, spec: list[tuple]) -> list[dict]:
    """
    spec: [(game_no, [(player_id, attempts, yards, ints, rush_yds), ...]), ...]
    The first passer listed in each game is the primary.
    """
    out = []
    for gno, passers in spec:
        for i, (pid, att, yds, ints, rush) in enumerate(passers):
            out.append({
                "game_id": f"G{gno}", "team": team, "season": 2024,
                "week": gno, "game_date": pd.Timestamp(f"2024-09-{gno:02d}"),
                "player_id": pid, "player_name": f"P{pid}",
                "is_primary": 1 if i == 0 else 0,
                "attempts": att, "completions": att // 2, "pass_yards": yds,
                "pass_td": 1, "interceptions": ints, "rush_yards": rush,
            })
    return out


def _frame(rows) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _feat(df: pd.DataFrame, game_id: str, team: str = "T") -> dict:
    r = df[(df["game_id"] == game_id) & (df["team"] == team)]
    assert len(r) == 1, f"expected exactly one row for {game_id}/{team}"
    return r.iloc[0].to_dict()


# ── LEAKAGE ───────────────────────────────────────────────────────────────────

def test_a_games_features_never_use_that_game():
    """
    THE leakage test. Poison every stat in game 4 and assert games 1-4 are
    byte-identical. Game 4's own row must not move: it is computed from games
    1-3 only.
    """
    spec = [(1, [("A", 30, 300, 0, 20)]), (2, [("A", 28, 250, 1, 10)]),
            (3, [("A", 32, 310, 0, 15)]), (4, [("A", 25, 200, 2, 5)]),
            (5, [("A", 27, 260, 1, 12)])]
    base = build_qb_team_features(_frame(_qb_rows("T", spec)))

    rows = _qb_rows("T", spec)
    for r in rows:
        if r["game_id"] == "G4":
            r.update(player_id="ZZZ", attempts=99, pass_yards=9999,
                     interceptions=9, rush_yards=999)
    after = build_qb_team_features(_frame(rows))

    for gid in ("G1", "G2", "G3", "G4"):
        b, a = _feat(base, gid), _feat(after, gid)
        for c in QB_TEAM_COLS:
            assert (pd.isna(b[c]) and pd.isna(a[c])) or b[c] == pytest.approx(a[c]), (
                f"{gid}.{c} changed when G4 was poisoned -- the feature is "
                "reading the game it is supposed to predict")


def test_later_games_do_change_when_poisoned():
    """Control: if nothing moved anywhere the test above proves nothing."""
    spec = [(1, [("A", 30, 300, 0, 20)]), (2, [("A", 28, 250, 1, 10)]),
            (3, [("A", 32, 310, 0, 15)]), (4, [("A", 25, 200, 2, 5)]),
            (5, [("A", 27, 260, 1, 12)])]
    base = build_qb_team_features(_frame(_qb_rows("T", spec)))
    rows = _qb_rows("T", spec)
    for r in rows:
        if r["game_id"] == "G4":
            r.update(player_id="ZZZ", attempts=99, pass_yards=9999)
    after = build_qb_team_features(_frame(rows))
    assert _feat(base, "G5")["qb_ypa_recent"] != pytest.approx(
        _feat(after, "G5")["qb_ypa_recent"]), "poisoning G4 did not reach G5"


def test_first_game_has_no_qb_features_at_all():
    """No prior game means no information. NaN, never an imputed zero."""
    f = _feat(build_qb_team_features(
        _frame(_qb_rows("T", [(1, [("A", 30, 300, 0, 20)])]))), "G1")
    for c in QB_TEAM_COLS:
        assert pd.isna(f[c]), f"{c} was populated with no prior game"


def test_qb_changed_needs_two_prior_games_not_one():
    """With a single prior game there is nothing to compare it against."""
    df = build_qb_team_features(_frame(_qb_rows(
        "T", [(1, [("A", 30, 300, 0, 0)]), (2, [("B", 30, 300, 0, 0)]),
              (3, [("B", 30, 300, 0, 0)])])))
    assert pd.isna(_feat(df, "G2")["qb_changed"])
    assert _feat(df, "G3")["qb_changed"] == 1.0     # A -> B happened before G3


# ── CORRECTNESS ───────────────────────────────────────────────────────────────

def test_current_qb_is_the_previous_games_primary():
    df = build_qb_team_features(_frame(_qb_rows("T", [
        (1, [("A", 30, 300, 0, 0)]),
        (2, [("A", 30, 300, 0, 0)]),
        (3, [("B", 30, 600, 0, 0)]),          # B takes over
        (4, [("B", 30, 600, 0, 0)]),
    ])))
    # entering G4 the current QB is B, who has 1 prior start -> "new"
    f4 = _feat(df, "G4")
    assert f4["qb_prior_starts"] == 1.0
    assert f4["qb_is_new"] == 1.0
    assert f4["qb_changed"] == 1.0            # the A->B switch happened at G3
    # entering G3 the current QB is still A with 2 starts
    assert _feat(df, "G3")["qb_prior_starts"] == 2.0
    assert _feat(df, "G3")["qb_is_new"] == 0.0


def test_qb_changed_flags_the_switch_on_the_following_game():
    df = build_qb_team_features(_frame(_qb_rows("T", [
        (1, [("A", 30, 300, 0, 0)]), (2, [("A", 30, 300, 0, 0)]),
        (3, [("B", 30, 300, 0, 0)]), (4, [("B", 30, 300, 0, 0)])])))
    # the switch is visible entering G4 (G3 primary B != G2 primary A)
    assert _feat(df, "G4")["qb_changed"] == 1.0
    assert _feat(df, "G3")["qb_changed"] == 0.0


def test_share_recent_detects_a_two_qb_rotation():
    """A committee offence is a different team than a stable one."""
    stable = build_qb_team_features(_frame(_qb_rows("T", [
        (1, [("A", 30, 300, 0, 0)]), (2, [("A", 30, 300, 0, 0)]),
        (3, [("A", 30, 300, 0, 0)]), (4, [("A", 30, 300, 0, 0)])])))
    split = build_qb_team_features(_frame(_qb_rows("T", [
        (1, [("A", 16, 150, 0, 0), ("B", 14, 140, 0, 0)]),
        (2, [("A", 16, 150, 0, 0), ("B", 14, 140, 0, 0)]),
        (3, [("A", 16, 150, 0, 0), ("B", 14, 140, 0, 0)]),
        (4, [("A", 16, 150, 0, 0), ("B", 14, 140, 0, 0)])])))
    assert _feat(stable, "G4")["qb_share_recent"] == pytest.approx(1.0)
    assert _feat(split, "G4")["qb_share_recent"] == pytest.approx(16 / 30)


def test_rate_stats_use_only_the_current_qbs_own_attempts():
    """
    The backup's terrible line must not drag the starter's YPA. This is the
    whole point of conditioning on QB identity rather than using team passing.
    """
    df = build_qb_team_features(_frame(_qb_rows("T", [
        (1, [("A", 10, 200, 0, 0), ("B", 10, 0, 5, 0)]),
        (2, [("A", 10, 200, 0, 0), ("B", 10, 0, 5, 0)])])))
    f = _feat(df, "G2")
    assert f["qb_ypa_recent"] == pytest.approx(20.0)      # A only, not 10.0
    assert f["qb_int_rate_recent"] == pytest.approx(0.0)


def test_recent_window_is_bounded():
    """Old games must fall out, or 'recent form' is just a season average."""
    spec = [(i, [("A", 10, 0 if i <= 3 else 300, 0, 0)]) for i in range(1, 8)]
    f = _feat(build_qb_team_features(_frame(_qb_rows("T", spec))), "G7")
    assert f["qb_ypa_recent"] == pytest.approx(30.0), (
        f"window is not limited to {RECENT_GAMES} games")


def test_rush_ypg_is_per_appearance_not_per_window_slot():
    df = build_qb_team_features(_frame(_qb_rows("T", [
        (1, [("A", 10, 100, 0, 60)]),
        (2, [("B", 10, 100, 0, 0)]),          # A does not appear
        (3, [("A", 10, 100, 0, 40)]),
        (4, [("A", 10, 100, 0, 0)])])))
    # entering G4: A appeared in G1 and G3 within the 3-game window
    assert _feat(df, "G4")["qb_rush_ypg_recent"] == pytest.approx(50.0)


def test_teams_are_independent():
    rows = _qb_rows("T", [(1, [("A", 30, 300, 0, 0)]), (2, [("A", 30, 300, 0, 0)])])
    rows += _qb_rows("U", [(1, [("X", 30, 900, 0, 0)]), (2, [("X", 30, 900, 0, 0)])])
    df = build_qb_team_features(_frame(rows))
    assert _feat(df, "G2", "T")["qb_ypa_recent"] == pytest.approx(10.0)
    assert _feat(df, "G2", "U")["qb_ypa_recent"] == pytest.approx(30.0)


def test_empty_input_returns_the_right_shape():
    out = build_qb_team_features(pd.DataFrame())
    assert list(out.columns) == ["game_id", "team"] + QB_TEAM_COLS
    assert out.empty


# ── DIFF / MERGE ──────────────────────────────────────────────────────────────

def _games():
    return pd.DataFrame([{"game_id": "G2", "home_team": "T", "away_team": "U"}])


def _qb_team(home: dict, away: dict) -> pd.DataFrame:
    base = {c: np.nan for c in QB_TEAM_COLS}
    return pd.DataFrame([{"game_id": "G2", "team": "T", **base, **home},
                         {"game_id": "G2", "team": "U", **base, **away}])


def test_positive_diff_always_means_good_for_home():
    """
    Registry-wide sign convention. For qb_changed / qb_is_new /
    qb_int_rate_recent a bigger raw number is WORSE, so those diffs are
    negated; getting one of them backwards flips the model's read on every
    QB-disruption game while every metric still looks fine.
    """
    g = merge_qb_features(_games(), _qb_team(
        home={"qb_ypa_recent": 9.0, "qb_changed": 1.0, "qb_is_new": 1.0,
              "qb_int_rate_recent": 0.05},
        away={"qb_ypa_recent": 6.0, "qb_changed": 0.0, "qb_is_new": 0.0,
              "qb_int_rate_recent": 0.01}))
    r = g.iloc[0]
    assert r["d_qb_ypa_recent"] > 0, "home throws better -> positive"
    assert r["d_qb_changed"] < 0, "home just changed QB -> bad for home"
    assert r["d_qb_is_new"] < 0, "home has the inexperienced QB -> bad for home"
    assert r["d_qb_int_rate_recent"] < 0, "home throws more picks -> bad for home"


def test_either_changed_is_a_game_level_flag_the_diff_would_cancel():
    """Both teams changing QB is maximal disruption but a zero diff."""
    both = merge_qb_features(_games(), _qb_team(
        home={"qb_changed": 1.0}, away={"qb_changed": 1.0})).iloc[0]
    assert both["d_qb_changed"] == 0.0
    assert both["qb_either_changed"] == 1.0

    one = merge_qb_features(_games(), _qb_team(
        home={"qb_changed": 1.0}, away={"qb_changed": 0.0})).iloc[0]
    assert one["qb_either_changed"] == 1.0

    neither = merge_qb_features(_games(), _qb_team(
        home={"qb_changed": 0.0}, away={"qb_changed": 0.0})).iloc[0]
    assert neither["qb_either_changed"] == 0.0


def test_missing_qb_table_yields_nan_columns_not_a_crash():
    g = merge_qb_features(_games(), pd.DataFrame())
    for c in QB_FEATURES:
        assert c in g.columns and g[c].isna().all()


def test_every_declared_feature_is_actually_produced():
    g = merge_qb_features(_games(), _qb_team({"qb_ypa_recent": 8.0},
                                             {"qb_ypa_recent": 7.0}))
    for c in QB_FEATURES:
        assert c in g.columns, f"{c} is declared in QB_FEATURES but never built"
