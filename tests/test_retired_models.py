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
2026-09-08 (mike): the five golf models, and with them the sport -- the first
retirement of a WHOLE sport, and the first for a reason outside the models:
DATAGOLF_API_KEY was never set on the worker, so every golf pipeline step
no-opped and GOLF produced no games, no odds and no picks, ever.
2026-10-15 (mike): the twelve NBA models of 2026-06-19 -- three game models and
nine generic props -- "build new nba models, remove any previous nba models".
They never wrote a BET. Their feature engines, their scorer loop and their
artifacts went with them; the NBA model that replaced them is a rule
(nba_prop_market) with no feature map and no artifact.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import config

ROOT = Path(__file__).resolve().parents[1]
RETIRED_PROPS = ("mlb_prop_batter_hr", "mlb_prop_batter_rbi")
RETIRED_NBA = (
    "nba_moneyline", "nba_over_under", "nba_spread",
    "nba_prop_player_points", "nba_prop_player_rebounds", "nba_prop_player_assists",
    "nba_prop_player_threes", "nba_prop_player_pra", "nba_prop_player_blocks",
    "nba_prop_player_steals", "nba_prop_player_turnovers", "nba_prop_player_dd",
)


def test_the_set_holds_exactly_the_twenty_two_retirements():
    assert set(config.RETIRED_MODELS) == {
        "mlb_live_win_prob", "mlb_live_runline",
        "mlb_prop_batter_hr", "mlb_prop_batter_rbi",
        "golf_outright", "golf_top10", "golf_top20",
        "golf_make_cut", "golf_matchup",
        "nfl_live_prop",
        *RETIRED_NBA,
    }
    assert len(config.RETIRED_MODELS) == 22


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


# ── the game-model half ──────────────────────────────────────────────────────

def test_a_retired_game_model_is_in_no_feature_map():
    """The prop half of this contract checked PROP_FEATURE_MAP only.

    Golf is a GAME model, so it lived in features.feature_engine.FEATURE_MAP,
    which nothing here covered -- and a model left in FEATURE_MAP still has a
    feature list, a training path and a scorer entry waiting for it. Sweeping
    every map rather than the one that happened to matter last time.
    """
    import importlib
    maps = []
    for mod_name, attr in (("features.feature_engine",     "FEATURE_MAP"),
                           ("features.live_game_features", "LIVE_FEATURE_MAP"),
                           ("features.prop_feature_engine", "PROP_FEATURE_MAP")):
        try:
            m = getattr(importlib.import_module(mod_name), attr, None)
        except Exception:                                   # noqa: BLE001
            continue
        if isinstance(m, dict):
            maps.append((f"{mod_name}.{attr}", set(m)))
    assert maps, "no feature map could be imported -- this guard checked nothing"
    for name, keys in maps:
        left = sorted(config.RETIRED_MODELS & keys)
        assert not left, f"{left} are retired but still carry a {name} entry"


def test_the_nba_engines_and_their_scorer_loop_are_gone():
    """FEATURE_MAP is swept above; the NBA models also had their OWN maps and
    loop -- features/nba_feature_engine.py (game), features/nba_prop_feature_engine.py
    (NBA_PROP_FEATURE_MAP) and models.scorer._NBA_PROP_CONFIG, which the NBA
    prop loop iterated instead of PROP_MODELS. The sweep above skips a module
    it cannot import, so a resurrected engine would pass it silently; this
    names them."""
    import models.scorer as scorer
    for rel in ("features/nba_feature_engine.py", "features/nba_prop_feature_engine.py"):
        assert not (ROOT / rel).exists(), f"{rel} is back"
    assert not hasattr(scorer, "_NBA_PROP_CONFIG")
    assert not hasattr(scorer, "run_nba_prop_scorer")
    from features.feature_engine import FEATURE_MAP
    assert not (set(RETIRED_NBA) & set(FEATURE_MAP))


def test_a_retired_sport_is_not_still_health_checked():
    """A check for a sport that can no longer produce data can only ever SKIP,
    and a permanently-skipping check is what this whole exercise was about."""
    import tracking.system_health as sh
    src = (ROOT / "tracking" / "system_health.py").read_text(encoding="utf-8")
    assert '"golf_odds"' not in src, "golf is retired but golf_odds is still checked"
    assert not any(m.startswith("golf") for m in sh.KNOWN_UNTRAINED)


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
    for m in RETIRED_PROPS + RETIRED_NBA:
        assert not list(saved.glob(f"{m}_*.pkl")), f"{m} still has an artifact"
    # ...and nothing still asks git to keep one (the .gitignore keep-list and
    # the MANIFEST block, pinned equal by test_model_artifacts_load).
    keep = (ROOT / ".gitignore").read_text(encoding="utf-8")
    manifest = (ROOT / "models" / "saved" / "MANIFEST.md").read_text(encoding="utf-8")
    for m in RETIRED_NBA:
        # "saved/" anchors the id: "wnba_moneyline_" contains "nba_moneyline_".
        assert f"saved/{m}_" not in keep, f"{m} is still on the .gitignore keep-list"
        assert f"saved/{m}_" not in manifest, f"{m} is still in MANIFEST.md"


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
    """mobile RETIRED_MODELS (thresholds.generated.ts, re-exported by
    thresholds.ts) is the client half of the same guard. The two must never
    drift after the generate-from-config split."""
    wrapper = (ROOT / "mobile" / "src" / "lib" / "thresholds.ts").read_text(encoding="utf-8")
    assert "RETIRED_MODELS" in wrapper
    assert "thresholds.generated" in wrapper
    src = (ROOT / "mobile" / "src" / "lib" / "thresholds.generated.ts").read_text(encoding="utf-8")
    block = re.search(r"export const RETIRED_MODELS = new Set<string>\(\[(.*?)\]\);", src, re.S).group(1)
    ids = set(re.findall(r"'([a-z_0-9]+)'", block))
    assert ids == set(config.RETIRED_MODELS)
    # and no bundled threshold survives for any of them
    for m in config.RETIRED_MODELS:
        assert not re.search(rf"^\s*{m}: \{{", src, re.M), f"{m} still has a bundled threshold"


# ── NFL distributional pause (2026-09-14) ──────────────────────────────────

NFL_DISTRIBUTIONAL_PAUSED = frozenset({
    "nfl_prop_pass_yards",
    "nfl_prop_pass_attempts",
    "nfl_prop_pass_completions",
    "nfl_prop_pass_tds",
    "nfl_prop_rush_yards",
    "nfl_prop_rush_attempts",
    "nfl_prop_rec_yards",
    "nfl_prop_receptions",
    "nfl_prop_rush_rec_yards",
    "nfl_prop_anytime_td",
    "nfl_prop_sacks",
})

NFL_KEEP_LIVE = frozenset({
    "nfl_prop_tackles_assists",
    "nfl_prop_market",
    "nfl_wind_totals",
    "nfl_opener_spread",
})
# nfl_live_prop left this set 2026-10-04: RETIRED (mike), not paused.


def test_ten_nfl_distributional_props_are_paused():
    """BET emission stopped for the eleven PROP_MODELS distributional ids.

    Ten from #710 plus nfl_prop_sacks (2026-09-14, mike, design-review
    follow-up). Pause ≠ retire: NONE rows still score; cuts stay.
    """
    assert NFL_DISTRIBUTIONAL_PAUSED <= set(config.PAUSED_MODELS)
    assert len(NFL_DISTRIBUTIONAL_PAUSED) == 11


def test_nfl_tackles_and_rule_lanes_stay_live():
    for mid in NFL_KEEP_LIVE:
        assert mid not in config.PAUSED_MODELS, mid
        assert mid not in config.RETIRED_MODELS, mid


def test_paused_nfl_props_still_in_prop_models_and_thresholds():
    """Pause ≠ retire: still train/score/sync; only BET emission stops."""
    for mid in NFL_DISTRIBUTIONAL_PAUSED:
        assert mid in config.PROP_MODELS, mid
        assert mid in config.ACTION_THRESHOLDS, mid
