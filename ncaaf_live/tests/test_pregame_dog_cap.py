"""The live moneyline lane never backs a big pregame underdog.

2026-09-12, mike, on an Oklahoma State ML written at +101 while they led Oregon
by 10 in the second quarter: *"they were huge underdogs to start the game and
half the game is left."* They had been 24.5-point home dogs.

The model was NOT missing the pregame line -- it is a feature, and the engine
declines a game without one. The cut was the problem. These pin the filter that
replaced it, and the two things about it that are easy to get backwards: the
spread is HOME-relative, so the away side's dog points are its negation, and
the cap applies to the moneyline lane only.
"""
from __future__ import annotations

import pytest

from ncaaf_live import serve
from ncaaf_live.serve import LiveEngine


# ── the arithmetic, which is where a sign error would live ───────────────────

def test_home_dog_points_is_the_spread_itself():
    """+24.5 home-relative means the HOME team is getting 24.5."""
    assert LiveEngine._pregame_dog_points("home", 24.5) == 24.5


def test_away_dog_points_is_the_negation():
    """The same +24.5 means the AWAY team is LAYING 24.5."""
    assert LiveEngine._pregame_dog_points("away", 24.5) == -24.5


def test_a_favourite_has_negative_dog_points():
    assert LiveEngine._pregame_dog_points("home", -9.5) == -9.5
    assert LiveEngine._pregame_dog_points("away", -9.5) == 9.5


def test_no_pregame_spread_is_none_not_zero():
    """Zero would read as a pick'em and pass the cap; None is the honest answer."""
    assert LiveEngine._pregame_dog_points("home", None) is None


# ── the filter ───────────────────────────────────────────────────────────────

def _ml(pick, spread, side="home"):
    return LiveEngine._unless_big_dog(pick, "ncaaf_live_win_prob", side, spread)


def test_the_oklahoma_state_pick_is_declined(monkeypatch):
    """The case that prompted this: home side, 24.5-point pregame dog."""
    monkeypatch.setattr(serve, "ML_MAX_PREGAME_DOG_POINTS", 10.0)
    assert _ml("BET", 24.5) is None


def test_a_small_dog_still_bets(monkeypatch):
    monkeypatch.setattr(serve, "ML_MAX_PREGAME_DOG_POINTS", 10.0)
    assert _ml("BET", 7.0) == "BET"


def test_the_cap_is_inclusive(monkeypatch):
    """Exactly at the cap is allowed; a tenth over is not."""
    monkeypatch.setattr(serve, "ML_MAX_PREGAME_DOG_POINTS", 10.0)
    assert _ml("BET", 10.0) == "BET"
    assert _ml("BET", 10.1) is None


def test_a_favourite_is_never_touched(monkeypatch):
    monkeypatch.setattr(serve, "ML_MAX_PREGAME_DOG_POINTS", 10.0)
    assert _ml("BET", -24.5) == "BET"


def test_the_away_side_is_judged_on_its_own_number(monkeypatch):
    """Backing the AWAY team when home is +24.5 means backing a 24.5-point
    FAVOURITE, which the cap must not touch."""
    monkeypatch.setattr(serve, "ML_MAX_PREGAME_DOG_POINTS", 10.0)
    assert _ml("BET", 24.5, side="away") == "BET"
    assert _ml("BET", -24.5, side="away") is None


# ── scope: moneyline only, BET only, and off means off ───────────────────────

@pytest.mark.parametrize("lane", ["ncaaf_live_total", "ncaaf_live_spread"])
def test_other_lanes_are_untouched(monkeypatch, lane):
    """A total has no side that can be a dog; the spread prices the number."""
    monkeypatch.setattr(serve, "ML_MAX_PREGAME_DOG_POINTS", 10.0)
    assert LiveEngine._unless_big_dog("BET", lane, "home", 24.5) == "BET"


def test_avoid_is_informational_and_passes(monkeypatch):
    monkeypatch.setattr(serve, "ML_MAX_PREGAME_DOG_POINTS", 10.0)
    assert _ml("AVOID", 24.5) == "AVOID"
    assert _ml(None, 24.5) is None


def test_a_none_cap_disables_the_filter(monkeypatch):
    monkeypatch.setattr(serve, "ML_MAX_PREGAME_DOG_POINTS", None)
    assert _ml("BET", 99.0) == "BET"


def test_a_missing_spread_cannot_silently_pass_a_huge_dog(monkeypatch):
    """price() declines a game with no pregame line, so this cannot arise on
    the live path -- but if it ever does, the filter must not invent a 0."""
    monkeypatch.setattr(serve, "ML_MAX_PREGAME_DOG_POINTS", 10.0)
    assert _ml("BET", None) == "BET"      # no number to judge; price() already declined


# ── the wiring ───────────────────────────────────────────────────────────────

def test_the_decision_loop_applies_the_filter():
    """Source tripwire: the helper existing is not the same as it running."""
    from pathlib import Path
    src = (Path(serve.__file__)).read_text(encoding="utf-8")
    body = src.split("def price(")[1].split("\n    @")[0]
    assert "_unless_big_dog(" in body, "price() no longer applies the dog cap"


def test_the_cap_comes_from_platform_config():
    import config
    assert serve.ML_MAX_PREGAME_DOG_POINTS == config.NCAAF_LIVE_ML_MAX_PREGAME_DOG_POINTS
