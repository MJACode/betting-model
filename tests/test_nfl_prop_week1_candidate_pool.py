"""The week-1 candidate pool survives the first kickoff of the week.

WHAT BROKE (2026-09-13, found from the app). `_score_rows` builds each team's
candidate pool from player appearances in the trailing 45 days, and falls back
to the prior season when that window is empty — the off-season cannot be
bridged, so week 1 has nothing recent to draw on.

The fallback was gated on the WHOLE window being empty. That is true only until
the first game of week 1 kicks off. From that moment `recent` holds the handful
of teams that have played, the gate never opens again, and every team still to
play gets an EMPTY pool. `synth` comes out empty, the builder returns no rows,
and the scorer reports "no scoring rows" and writes nothing at all — not a BET,
not an AVOID, not a NONE.

Measured on production for 2026-09-13: 26 slate teams, 16,489 rows of 2025
history, `recent` non-empty at 115 rows covering 4 teams, and ZERO slate teams
with a candidate. All twelve nfl_prop_* models had been silent since the first
week-1 kickoff three days earlier.

The fixture below is the population the two branches can disagree about — a
PARTIALLY played week 1 — because a fixture where nobody has played passes
either way, which is the blind spot that shipped (CLAUDE.md §7).
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from features.nfl_prop_feature_engine import _score_rows  # noqa: E402


PLAYER_COLS = [
    "player_id", "player_name", "norm_name", "pos", "team", "opponent",
    "game_id", "game_date", "season", "week", "season_type",
    "completions", "attempts", "passing_yards", "passing_tds", "interceptions",
    "sacks_suffered", "passing_air_yards", "carries", "rushing_yards",
    "rushing_tds", "receptions", "targets", "receiving_yards", "receiving_tds",
    "receiving_air_yards", "receiving_yac", "target_share", "air_yards_share",
    "wopr", "def_tackles_solo", "def_tackle_assists", "def_sacks",
    "def_qb_hits", "def_tackles_with_assist",
]


def _player_row(pid, name, team, opp, game_id, game_date, season, week, **stats):
    row = {c: 0.0 for c in PLAYER_COLS}
    row.update({
        "player_id": pid, "player_name": name, "norm_name": name.lower(),
        "pos": "QB", "team": team, "opponent": opp, "game_id": game_id,
        "game_date": game_date, "season": season, "week": week,
        "season_type": "REG",
    })
    # Enough prior volume to clear the passing pool gate (attempts_r3 > 20).
    row.update({"attempts": 34.0, "completions": 22.0, "passing_yards": 260.0})
    row.update(stats)
    return row


def _team_row(game_id, team, opp, game_date, season, week, is_home):
    return {
        "game_id": game_id, "team": team, "opponent": opp,
        "game_date": game_date, "season": season, "week": week,
        "is_home": is_home, "pass_attempts": 34.0, "carries": 25.0,
        "plays": 63.0, "pass_yards": 250.0, "rush_yards": 110.0,
        "spread_line": -2.5, "total_line": 45.5, "roof": "outdoors",
        "temp": 70.0, "wind": 5.0, "div_game": 0,
        "commence_time": f"{game_date}T17:00:00+00:00",
    }


@pytest.fixture
def partially_played_week_one():
    """Week 1 with the Thursday game already played and Sunday still to come.

    PHI played (and is therefore inside the 45-day window). DAL and NYG have
    not, so their only history is last season — the exact case the slate-wide
    gate could not see.
    """
    prior = [                                    # 2025, three games each
        _player_row(f"{t}-qb", f"{t} QB", t, "OPP", f"NFL_2025_1{i}_{t}_OPP",
                    f"2025-12-{10 + i:02d}", 2025, 15 + i)
        for t in ("DAL", "NYG", "PHI")
        for i in range(3)
    ]
    played = [                                   # week 1 Thursday, already played
        _player_row("PHI-qb", "PHI QB", "PHI", "GB", "NFL_2026_01_GB_PHI",
                    "2026-09-10", 2026, 1),
    ]
    player = pd.DataFrame(prior + played)

    team = pd.DataFrame([
        # the played Thursday game
        _team_row("NFL_2026_01_GB_PHI", "PHI", "GB", "2026-09-10", 2026, 1, 1),
        _team_row("NFL_2026_01_GB_PHI", "GB", "PHI", "2026-09-10", 2026, 1, 0),
        # the slate under test
        _team_row("NFL_2026_01_DAL_NYG", "NYG", "DAL", "2026-09-13", 2026, 1, 1),
        _team_row("NFL_2026_01_DAL_NYG", "DAL", "NYG", "2026-09-13", 2026, 1, 0),
    ] + [
        _team_row(f"NFL_2025_1{i}_{t}_OPP", t, "OPP", f"2025-12-{10 + i:02d}",
                  2025, 15 + i, 1)
        for t in ("DAL", "NYG", "PHI") for i in range(3)
    ])

    snaps = pd.DataFrame(columns=["game_id", "team", "norm_name",
                                  "offense_pct", "defense_pct", "st_pct"])
    return player, team, snaps


def test_teams_still_to_play_keep_a_candidate_pool(partially_played_week_one):
    """The Sunday slate scores even though Thursday has already been played.

    This is the assertion that fails on the slate-wide gate: `recent` is
    non-empty (PHI played Thursday), so the old code never reached the
    prior-season fallback and returned an EMPTY frame for DAL @ NYG.
    """
    player, team, snaps = partially_played_week_one
    rows = _score_rows(player, team, snaps, "2026-09-13", "nfl_prop_pass_yards")

    assert not rows.empty, (
        "DAL @ NYG produced no scoring rows — a team that has not played yet "
        "lost its candidate pool the moment another team kicked off"
    )
    assert set(rows["team"]) == {"DAL", "NYG"}
    assert set(rows["game_id"]) == {"NFL_2026_01_DAL_NYG"}


def test_a_clean_week_one_is_unchanged(partially_played_week_one):
    """With nobody played, every team falls back — the old behaviour exactly."""
    player, team, snaps = partially_played_week_one
    player = player[player["season"] == 2025]          # drop the Thursday game
    team = team[team["game_id"] != "NFL_2026_01_GB_PHI"]

    rows = _score_rows(player, team, snaps, "2026-09-13", "nfl_prop_pass_yards")
    assert set(rows["team"]) == {"DAL", "NYG"}
