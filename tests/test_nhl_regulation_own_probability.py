"""nhl_moneyline_regulation decides on its own probability (mike, 2026-10-03).

The promoted correction is a two-way map: a side under 0.5 becomes
1 - f(1 - p). In the three-way regulation market 1 - p is not the other side,
so it lifted every outcome under 50% by ~6 points (0.380 -> 0.443 on
"NYR (Regulation)", 2026-10-02) and the scorer wrote BETs below the model's
own 0.05 cut that the app and Discord then hid.
"""
from __future__ import annotations

import pytest

import config
from models import scorer

BORROWED = {"method": "platt", "a": 1.0, "b": -0.259947}


@pytest.fixture
def mapped(monkeypatch):
    """The production map for this model, without a database."""
    monkeypatch.setattr(scorer, "_CAL_CACHE", {"nhl_moneyline_regulation": BORROWED,
                                               "nhl_moneyline": BORROWED})


def test_regulation_is_listed():
    assert "nhl_moneyline_regulation" in config.MODELS_ON_OWN_PROBABILITY


def test_the_correction_does_not_touch_a_regulation_probability(mapped):
    assert scorer._calibrated("nhl_moneyline_regulation", 0.380) == pytest.approx(0.380)


def test_the_two_way_moneyline_keeps_its_correction(mapped):
    """mike, 2026-10-01: the correction stays on the moneyline. Only the
    three-way market was wrong."""
    assert scorer._calibrated("nhl_moneyline", 0.380) == pytest.approx(0.4429, abs=1e-3)


def test_nyr_regulation_2026_10_02_is_not_a_bet(mapped):
    """raw 0.380 at +180 (implied 0.357): edge 0.023, under the 0.05 cut."""
    implied = 100 / 280
    signal = scorer._decide("nhl_moneyline_regulation", 0.380, implied, 0.380 - implied, 180.0,
                            is_prop=False)
    assert signal != "BET"
