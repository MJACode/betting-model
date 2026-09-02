"""The retirement contract, pinned for every retired model at once.

A retired model is gone from its registry (config.MODELS / PROP_MODELS /
LIVE_MODELS) and from every threshold dict, so nothing can score, train or
sync a threshold row for it -- which is what drops it from every track-record
view (they all INNER JOIN model_action_thresholds). Its picks stay in the DB
and keep grading (CLAUDE.md §1c), and every aggregation that reads raw picks
rather than the views consults config.RETIRED_MODELS.

2026-08-30 (matt): mlb_live_win_prob, mlb_live_runline (tests/test_live_orchestrator.py
pins their live-specific half).
2026-09-02 (matt): mlb_prop_batter_hr, mlb_prop_batter_rbi -- the first
PRE-GAME retirements, and the first time "out of every total" was the ask.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import config

ROOT = Path(__file__).resolve().parents[1]
RETIRED_PROPS = ("mlb_prop_batter_hr", "mlb_prop_batter_rbi")


def test_the_set_holds_all_four():
    assert set(config.RETIRED_MODELS) == {
        "mlb_live_win_prob", "mlb_live_runline",
        "mlb_prop_batter_hr", "mlb_prop_batter_rbi",
    }


@pytest.mark.parametrize("model_id", sorted(config.RETIRED_MODELS))
def test_a_retired_model_is_in_no_registry_and_no_threshold_dict(model_id):
    assert model_id not in config.MODELS
    assert model_id not in config.PROP_MODELS
    assert model_id not in config.LIVE_MODELS
    assert model_id not in config.PAUSED_MODELS       # nothing left to pause
    assert model_id not in config.ACTION_THRESHOLDS   # -> threshold_sync prunes its row
    assert model_id not in config.MODEL_PROB_THRESHOLDS
    assert model_id not in config.MODEL_EDGE_THRESHOLDS
    assert model_id not in config.MODEL_MIN_ODDS
    assert model_id not in config.PROB_ONLY_MODELS
    assert model_id not in config.MODEL_BET_SIZE_MULTIPLIER


def test_retired_is_disjoint_from_paused_and_from_every_registry():
    live = set(config.MODELS) | set(config.PROP_MODELS) | set(config.LIVE_MODELS)
    assert not (config.RETIRED_MODELS & live)
    assert not (config.RETIRED_MODELS & config.PAUSED_MODELS)


# ── the prop-specific half ───────────────────────────────────────────────────

def test_the_batter_loop_cannot_score_a_retired_prop():
    """The batter scorer iterates its OWN config dict, not PROP_MODELS. Removing
    a model from the registry alone would not have stopped it."""
    from models.scorer import _BATTER_PROP_CONFIG
    for m in RETIRED_PROPS:
        assert m not in _BATTER_PROP_CONFIG


def test_a_retired_prop_has_no_feature_map_and_no_training_label():
    from features import prop_feature_engine as fe
    for m in RETIRED_PROPS:
        assert m not in fe.PROP_FEATURE_MAP
        assert m not in fe.PENDING_RETRAIN_FEATURES
    # The training tuples are local to build_prop_training_matrix; the
    # tripwire is the source, read with an explicit encoding (§7).
    src = (ROOT / "features" / "prop_feature_engine.py").read_text(encoding="utf-8")
    batter_models = re.search(r"_BATTER_MODELS = \((.*?)\)", src, re.S).group(1)
    batter_target = re.search(r"_BATTER_TARGET = \{(.*?)\}", src, re.S).group(1)
    for m in RETIRED_PROPS:
        assert m not in batter_models
        assert m not in batter_target


def test_retired_prop_picks_still_settle_on_their_own_stat():
    """Their unsettled BETs (16 HR, 4 RBI on retirement day) must keep grading
    on the right column; these maps are keyed by model_id, not by the registry,
    and must NOT be pruned with the registry entry."""
    from tracking.paper_tracker import _PROP_MARKET_FOR_MODEL, _PROP_STAT_MAP
    assert _PROP_STAT_MAP["mlb_prop_batter_hr"] == ("batter", "home_runs")
    assert _PROP_STAT_MAP["mlb_prop_batter_rbi"] == ("batter", "rbi")
    assert _PROP_MARKET_FOR_MODEL["mlb_prop_batter_hr"] == "batter_home_runs"
    assert _PROP_MARKET_FOR_MODEL["mlb_prop_batter_rbi"] == "batter_rbis"


def test_the_artifacts_are_gone():
    saved = ROOT / "models" / "saved"
    for m in RETIRED_PROPS:
        assert not list(saved.glob(f"{m}_*.pkl")), f"{m} still has an artifact"


# ── out of every total that reads raw picks ─────────────────────────────────

def test_the_cli_performance_summary_excludes_retired_models():
    from tracking.paper_tracker import _NOT_RETIRED
    assert _NOT_RETIRED.startswith("model_id NOT IN (")
    for m in config.RETIRED_MODELS:
        assert f"'{m}'" in _NOT_RETIRED
    src = (ROOT / "tracking" / "paper_tracker.py").read_text(encoding="utf-8")
    body = src[src.index("def print_performance_summary"):]
    body = body[:body.index("\ndef ", 10)] if "\ndef " in body[10:] else body
    # every settled-BET query in the summary carries the clause
    assert body.count("signal_type = 'BET'") == body.count("{_NOT_RETIRED}") == 3


def test_the_threshold_review_slate_never_sees_a_retired_model():
    from tracking.threshold_review import _slate

    class _Conn:
        def execute(self, sql, params=None):
            return self
        def fetchall(self):
            return [("mlb_prop_batter_rbi", 293, 41.0),
                    ("mlb_prop_batter_hr", 256, -47.0),
                    ("mlb_prop_pitcher_k", 78, 0.2)]

    assert _slate(_Conn()) == [("mlb_prop_pitcher_k", 78, 0.2)]


def test_the_streamlit_dashboard_fallback_excludes_retired_models():
    """dashboard/app.py cannot be imported here (it configures a Streamlit page
    at import), so the tripwire is the source: the generic fallback clause must
    fold RETIRED_MODELS into its NOT IN list, or a retired model -- absent from
    ACTION_THRESHOLDS -- is re-admitted at the generic cut."""
    src = (ROOT / "dashboard" / "app.py").read_text(encoding="utf-8")
    assert "_action_covered |= set(RETIRED_MODELS)" in src
    assert src.index("_action_covered |= set(RETIRED_MODELS)") < src.index("_ACTION_FILTER = ")


def test_the_app_mirrors_the_same_set():
    """mobile/src/lib/thresholds.ts RETIRED_MODELS is the client half of the
    same guard (its passesActionFilter refuses a retired model before the
    server threshold row is consulted). The two must never drift."""
    src = (ROOT / "mobile" / "src" / "lib" / "thresholds.ts").read_text(encoding="utf-8")
    block = re.search(r"export const RETIRED_MODELS = new Set<string>\(\[(.*?)\]\);", src, re.S).group(1)
    ids = set(re.findall(r"'([a-z_0-9]+)'", block))
    assert ids == set(config.RETIRED_MODELS)
    # and no bundled threshold survives for any of them
    for m in config.RETIRED_MODELS:
        assert not re.search(rf"^\s*{m}: \{{", src, re.M), f"{m} still has a bundled threshold"
