"""Phase 0 team-stats leak guard: MLB retrain/sweep stays frozen until marked.

docs/team_stats_leak.md / docs/team_stats_rebuild_scope.md Phase 0:
do not retrain against leaked historical team-stats. The gate lives in
config.assert_retrain_allowed and is tripped from models.trainer (and
MLB sweep scripts that import it).
"""
from __future__ import annotations

import pytest

import config


def test_mlb_retrain_refused_while_incomplete(monkeypatch):
    monkeypatch.setattr(config, "TEAM_STATS_ASOF_REBUILD_COMPLETE", False)
    with pytest.raises(RuntimeError, match="as-of rebuild"):
        config.assert_retrain_allowed("MLB", what="retrain")


def test_non_mlb_sports_are_not_gated(monkeypatch):
    monkeypatch.setattr(config, "TEAM_STATS_ASOF_REBUILD_COMPLETE", False)
    for sport in ("NCAAF", "NFL", "UFC", "NBA", "NHL", "WNBA"):
        config.assert_retrain_allowed(sport, what="retrain")  # must not raise


def test_marker_or_env_lifts_the_freeze(monkeypatch):
    monkeypatch.setattr(config, "TEAM_STATS_ASOF_REBUILD_COMPLETE", True)
    config.assert_retrain_allowed("MLB", what="retrain")


def test_trainer_calls_the_guard():
    """A future edit that drops the call would re-open the leak window.

    Read the source file rather than importing models.trainer (heavy deps).
    """
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "models" / "trainer.py").read_text(
        encoding="utf-8")
    for name in ("def train_model(", "def train_prop_model(", "def train_live_model("):
        assert name in src, f"{name} missing from models/trainer.py"
        i = src.index(name)
        # Body until the next top-level def at column 0 roughly — enough to see the guard.
        nxt = src.find("\ndef ", i + 10)
        body = src[i:nxt if nxt != -1 else i + 4000]
        assert "assert_retrain_allowed" in body, f"{name} lost the freeze guard"


def test_frozen_sports_set_is_mlb_only():
    assert set(config.FROZEN_RETRAIN_SPORTS) == {"MLB"}


_GATED_SWEEPS = (
    "scripts/calibrated_threshold_sweep.py",
    "scripts/mlb_runline_sweep.py",
    "scripts/mlb_f5_sweep.py",
    "scripts/best_line_threshold_sweep.py",
    "scripts/live_cut_sweep.py",
    "scripts/live_calibration_sweep.py",
)

_EXEMPT_SWEEPS = (
    "scripts/mlb_prop_market_sweep.py",
)


def test_mlb_threshold_sweeps_call_the_guard():
    """A future edit that drops the call would re-open the leak window."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    for rel in _GATED_SWEEPS:
        src = (root / rel).read_text(encoding="utf-8")
        assert "assert_retrain_allowed" in src or "_guard_mlb" in src, (
            f"{rel} lost the freeze guard"
        )


def test_mlb_prop_market_sweep_is_documented_exempt():
    """Market-relative rule: player_prop_odds + player_game_log, not team-stats."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    src = (root / _EXEMPT_SWEEPS[0]).read_text(encoding="utf-8")
    assert "PHASE 0 EXEMPT" in src
    assert "assert_retrain_allowed" not in src


def test_repo_marker_file_is_present():
    """Rebuild landed 2026-09-03; marker must be in tree so the freeze lifts."""
    assert config._TEAM_STATS_ASOF_MARKER.is_file(), (
        "data/TEAM_STATS_ASOF_REBUILD_COMPLETE missing — MLB retrain stays frozen "
        "against already-rebuilt tables (docs/team_stats_leak.md)"
    )


def test_import_time_flag_follows_marker_file(monkeypatch):
    """Presence of the marker file is enough; no env var required."""
    monkeypatch.delenv("TEAM_STATS_ASOF_REBUILD_COMPLETE", raising=False)
    # Recompute the same expression config uses at import time.
    complete = (
        "".strip().lower() in ("1", "true", "yes")
        or config._TEAM_STATS_ASOF_MARKER.is_file()
    )
    assert complete is True
    monkeypatch.setattr(config, "TEAM_STATS_ASOF_REBUILD_COMPLETE", complete)
    config.assert_retrain_allowed("MLB", what="retrain")
