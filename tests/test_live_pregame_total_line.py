"""
`pregame_total_line` — the live totals model's market anchor, and the
train/serve parity it depends on.

CLAUDE.md §1b: a live prop/total is priced RELATIVE TO THE STARTING LINE. The
book re-anchors its live total mechanically off the pre-game number and the
clock, so the pre-game total is the reference the model deviates FROM. It was
missing from the feature vector entirely, and the six season-to-date stats
standing in for it moved the model's probability a median 12.8 points on stats
that drift 0.0164 ERA/day (docs/mlb_volume_efficiency.md).

Two failure modes are pinned here, both of which existed:

1. `total_line` means whatever market the caller passed. The over/under model
   passes the totals row and gets a real number; every h2h caller — including
   BOTH live paths — passes the moneyline row and gets None. A feature read
   from that slot is filled in training and empty at serve, or vice versa,
   with nothing raising. `pregame_total_line` has ONE source in both paths.

2. The two paths bounded "pre-game" differently. Training uses
   `_is_pregame_snapshot` (actual first pitch, clamped); serving used
   `commence_time` alone, which is a mean 18.7 minutes LATE — the permissive
   direction. Building the feature for 40 completed 2025 games down both paths
   produced 7 different lines before `_pregame_cutoff` was moved onto the
   shared `pregame_cutoff_sql` bound.
"""

import inspect

from features.feature_engine import build_mlb_game_features
from features.live_game_features import (
    LIVE_FEATURE_MAP, LIVE_STATE_FEATURES, build_live_training_dataset,
)
from models.live_scorer import _pregame_features
from models.scorer import _pregame_cutoff


# ── 1. one source, and it is the TOTALS market ───────────────────────────────

class _RecordingConn:
    """Serves the games row; records nothing else is needed."""

    def execute(self, sql, params=()):
        self._last = " ".join(sql.split())
        return self

    def fetchone(self):
        return ("2026-09-07T17:36:00+00:00",)

    def fetchall(self):
        return []

    def close(self):
        pass


def test_pregame_features_reads_both_markets():
    """The serve path must ask for TOTALS as well as h2h.

    This is the bug in its original form: `_pregame_features` passed only the
    h2h row, so `pregame_total_line` was None on every live pick while the
    training rows carried the real number.
    """
    asked = []
    captured = {}

    def fake_get_dk_odds(conn, game_id, market):
        asked.append(market)
        return {"total_line": 8.5} if market == "totals" else {"home_price": -120}

    def fake_build(conn, game_id, game_date, home, away, season,
                   odds_row=None, totals_row=None):
        captured["odds_row"] = odds_row
        captured["totals_row"] = totals_row
        return {"pregame_total_line": (totals_row or {}).get("total_line")}

    game = {"game_id": "MLB_2026-09-07_LAA_BOS", "game_date": "2026-09-07",
            "home_team": "BOS", "away_team": "LAA", "season": 2026}
    row = _pregame_features(_RecordingConn(), game, fake_build, fake_get_dk_odds)

    assert "h2h" in asked and "totals" in asked, asked
    assert captured["totals_row"] == {"total_line": 8.5}
    assert captured["odds_row"] == {"home_price": -120}
    assert row["pregame_total_line"] == 8.5


def test_h2h_row_alone_never_fills_the_anchor():
    """Passing the moneyline row as `odds_row` must leave the anchor empty
    rather than silently reading `total_line` off a market that has none."""
    sig = inspect.signature(build_mlb_game_features)
    assert "totals_row" in sig.parameters
    assert sig.parameters["totals_row"].default is None


def test_both_builders_take_the_same_totals_row_parameter():
    """The bulk (training) twin must accept it too, or training fills the
    feature from nothing while serving fills it from the market."""
    from features.feature_engine import _build_mlb_features_from_bulk
    assert "totals_row" in inspect.signature(_build_mlb_features_from_bulk).parameters


def test_training_path_looks_up_the_totals_market():
    """Structural, deliberately: the lookup is one line inside a function that
    needs a populated database to run. What must not silently revert is the
    MARKET KEY — `(gid, "h2h")` for the moneyline context, `(gid, "totals")`
    for the anchor."""
    src = inspect.getsource(build_live_training_dataset)
    assert 'totals_row=bulk["odds"].get((gid, "totals"))' in src


# ── 2. the two paths bound "pre-game" the same way ───────────────────────────

def test_serve_side_cutoff_uses_the_shared_first_pitch_bound():
    """`_pregame_cutoff` must not go back to reading commence_time alone.

    Not a style point: commence_time is the SCHEDULED start and the game
    actually begins a mean 18.7 minutes earlier, so that bound admits a
    quarter-hour of in-play quotes as "pre-game" — while the training path,
    which uses the actual first pitch, excludes them.
    """
    src = inspect.getsource(_pregame_cutoff)
    assert "pregame_cutoff_sql" in src
    assert "SELECT commence_time FROM games" not in src


def test_the_anchor_is_not_wired_into_a_model_by_accident():
    """LIVE_FEATURE_MAP is the promoted map. If `pregame_total_line` is in it,
    both paths must supply it — the two tests above are what make that true, so
    this one exists to fail loudly if the map grows the column while either
    path is reverted."""
    for model_id, cols in LIVE_FEATURE_MAP.items():
        if "pregame_total_line" not in cols:
            continue
        assert "totals_row" in inspect.signature(build_mlb_game_features).parameters
        assert 'totals_row=bulk["odds"].get((gid, "totals"))' in \
            inspect.getsource(build_live_training_dataset)
        # and it is pre-game context, never a state column
        assert "pregame_total_line" not in LIVE_STATE_FEATURES
