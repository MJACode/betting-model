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
    """A future edit that drops the call would re-open the leak window."""
    import inspect
    import models.trainer as trainer

    for fn in (trainer.train_model, trainer.train_prop_model, trainer.train_live_model):
        src = inspect.getsource(fn)
        assert "assert_retrain_allowed" in src, f"{fn.__name__} lost the freeze guard"


def test_frozen_sports_set_is_mlb_only():
    assert set(config.FROZEN_RETRAIN_SPORTS) == {"MLB"}
