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


def test_the_big_favourite_floor_admits_minus_4000_and_nothing_shorter():
    assert ART["models"][R.HEAVY_FAV_ML]["price_range"]["shortest"] == -4000.0
    assert config.min_odds_for(R.HEAVY_FAV_ML) == -4000
    assert ART["models"][R.HEAVY_FAV_ML]["price_range"]["longest"] <= -500


def test_the_home_moneyline_and_the_big_favourite_lose_their_conflicting_games():
    a = set(ART["models"][R.HOME_ML]["replay"]["lost_to_conflicts"])
    b = set(ART["models"][R.HEAVY_FAV_ML]["replay"]["lost_to_conflicts"])
    assert a == b and len(a) == 6
    for model in (R.HOME_DOG_SPREAD, R.H1_DOG_ML, R.Q1_SHARE_TOTAL):
        assert ART["models"][model]["replay"]["lost_to_conflicts"] == []


def test_the_replayed_records_are_the_researchs_less_the_conflicts():
    got = {m: (ART["models"][m]["replay"]["all"]["bets"], ART["models"][m]["replay"]["all"]["units"])
           for m in R.MODELS}
    assert got == {R.HOME_ML: (978, 65.8), R.HEAVY_FAV_ML: (176, 39.43), R.HOME_DOG_SPREAD: (455, 54.54),
                   R.H1_DOG_ML: (465, 19.14), R.Q1_SHARE_TOTAL: (63, 17.71)}


def test_the_relocated_venues_are_the_researchs():
    # read, never imported: the research module runs its whole study on import
    src = (build.RESEARCH / "r2_leads.py").read_text(encoding="utf-8")
    for grp, name in (("R1", "R1"), ("R2", "R2"), ("excluded", "EXCL")):
        for club, venue in R.RELOCATED_VENUES[grp]:
            assert f'("{club}", "{venue}")' in src, (grp, club, venue)
