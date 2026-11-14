"""The committed EuroLeague pre-game artifact (models/saved/euroleague_pregame_2027.json)
and the config it ships with.

The artifact is written only when the build's replay matched the research bet
for bet (scripts/euroleague_pregame_build.py --write refuses otherwise). These
pin that it did, that the card's numbers are the build's, and that no config
cut or floor removes a replayed bet: the rule is the cut.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config  # noqa: E402
import models.euroleague_pregame as R  # noqa: E402
from scripts import euroleague_pregame_build as build  # noqa: E402

ART = R.load_artifact(2027)


def test_the_artifact_is_the_2026_27_one_and_its_replay_matched_the_research():
    assert ART["season"] == 2027 and ART["replay_matches_research"] is True
    assert set(ART["models"]) == set(R.MODELS)
    assert ART["deciding_books"] == list(R.DECIDABLE)
    assert ART["decision_lead_min"] == 10


@pytest.mark.parametrize("model", R.MODELS)
def test_the_artifacts_rule_is_the_builds(model):
    m = ART["models"][model]
    assert m["market"] == R.MARKET[model]
    want = dict(build.PARAMS[model])
    if "relocated_venues" in want:
        want["relocated_venues"] = {k: [list(v) for v in vs] for k, vs in want["relocated_venues"].items()}
    assert m["params"] == want
    assert m["uplift"] == m["uplift_by_season"]["2027"]["uplift"]


@pytest.mark.parametrize("model", R.MODELS)
def test_no_cut_or_floor_in_config_removes_a_replayed_bet(model):
    m = ART["models"][model]
    assert config.min_ev_for(model) <= m["ev_min"]
    assert config.MODEL_EDGE_THRESHOLDS[model] <= m["edge_min"]
    assert config.ACTION_THRESHOLDS[model]["min_edge"] == config.MODEL_EDGE_THRESHOLDS[model]
    assert config.MODEL_PROB_THRESHOLDS[model] == 0.0 == config.ACTION_THRESHOLDS[model]["min_prob"]
    assert config.min_odds_for(model) <= m["price_range"]["shortest"]
    assert config.SCORING_METHODS[model] == "rule"
    assert model in config.MODELS_ON_OWN_PROBABILITY
    assert model not in config.PAUSED_MODELS


def test_the_floors_sit_just_under_the_replay_not_far_under():
    for model in R.MODELS:
        m = ART["models"][model]
        assert m["ev_min"] - config.min_ev_for(model) < 0.011, model
        assert m["edge_min"] - config.MODEL_EDGE_THRESHOLDS[model] < 0.011, model


def test_the_big_favourite_moneyline_is_gone_from_the_artifact_and_config():
    # Removed before it went live (mike, 2026-11-14: "odds cutoff for favorites
    # should be -200"): every bet it found was -500 or shorter.
    gone = "euroleague_heavy_fav_ml"
    assert gone not in ART["models"] and gone not in R.MODELS
    for table in (config.ACTION_THRESHOLDS, config.MODEL_EDGE_THRESHOLDS, config.MODEL_PROB_THRESHOLDS,
                  config.MODEL_MIN_ODDS, config.MODEL_OWN_EV_FLOOR, config.SCORING_METHODS):
        assert gone not in table
    assert gone not in config.MODELS_ON_OWN_PROBABILITY


def test_the_replayed_records_are_the_researchs():
    # With no rule left to conflict with in one pass, each live population is
    # the research's best-deciding-book read, bet for bet.
    got = {m: (ART["models"][m]["replay"]["all"]["bets"], ART["models"][m]["replay"]["all"]["units"])
           for m in R.MODELS}
    assert got == {R.HOME_ML: (984, 64.8), R.HOME_DOG_SPREAD: (455, 54.54),
                   R.H1_DOG_ML: (465, 19.14), R.Q1_SHARE_TOTAL: (63, 17.71)}


def test_the_relocated_venues_are_the_researchs():
    # read, never imported: the research module runs its whole study on import
    src = (build.RESEARCH / "r2_leads.py").read_text(encoding="utf-8")
    for grp, name in (("R1", "R1"), ("R2", "R2"), ("excluded", "EXCL")):
        for club, venue in R.RELOCATED_VENUES[grp]:
            assert f'("{club}", "{venue}")' in src, (grp, club, venue)
