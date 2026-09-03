"""Every model bets under a price floor — not just the seventeen that named one.

mike, 2026-09-03, on seeing `LAD ML F5  -290 @ FanDuel  3u to win 0.91u`:
"Why is there a -295 pick?!?! I thought we had juice rules. this needs to be
removed."

We did have a juice rule and it reached 17 of 69 models: sixteen props at -140
and ncaaf_moneyline at -250. `MODEL_MIN_ODDS.get(model_id)` returned None for
the other 52, and None meant NO FLOOR. The pick was DK -330 against a 0.7674
break-even with a model probability of 0.7729 — an edge of 0.54%, on a Kelly
fraction of 0.0023 — because mlb_f5_moneyline's cut is min_prob 0.74 with
min_edge 0.0, and a zero edge floor accepts exactly that.

The floor is a HOUSE RISK RULE, not a swept cut: it is not derived from any
model's record and is not claimed optimal for any of them. §1b's "never copy a
threshold across models" is about cuts measured on a record; this is the bar
below which the payout stops covering model error at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402
from models.scorer import _blocked_by_min_odds  # noqa: E402


def test_every_registered_model_has_an_effective_floor():
    """The property that was false for 52 models."""
    for model_id in config.ACTION_THRESHOLDS:
        floor = config.min_odds_for(model_id)
        assert floor is not None, f"{model_id} still bets with no price floor"
        assert floor < 0, f"{model_id}'s floor {floor} is not a juice bound"


def test_the_offending_pick_would_now_be_blocked():
    """DK -330 on mlb_f5_moneyline — the exact pick that prompted this."""
    assert _blocked_by_min_odds("mlb_f5_moneyline", -330.0) is True
    assert _blocked_by_min_odds("mlb_f5_moneyline", -290.0) is True


def test_ordinary_prices_still_fire():
    assert _blocked_by_min_odds("mlb_f5_moneyline", -180.0) is False
    assert _blocked_by_min_odds("mlb_f5_moneyline", 120.0) is False


def test_an_explicit_floor_wins_in_BOTH_directions():
    """A model naming its own floor keeps it whether that is tighter or looser
    than the house default. ncaaf_moneyline's -250 is LOOSER than -200 and must
    stay looser, or this "fix" silently re-cuts a model that was swept."""
    assert config.min_odds_for("mlb_prop_pitcher_k") == -140      # tighter
    assert _blocked_by_min_odds("mlb_prop_pitcher_k", -150.0) is True
    assert config.min_odds_for("ncaaf_moneyline") == -250         # looser
    assert _blocked_by_min_odds("ncaaf_moneyline", -240.0) is False


def test_a_pick_with_no_price_is_never_blocked_by_the_floor():
    """Prob-only fallbacks carry no book price and must keep firing — the floor
    is about a price being bad, not about a price being absent."""
    assert _blocked_by_min_odds("mlb_f5_moneyline", None) is False


def test_the_scorer_does_not_index_MODEL_MIN_ODDS_directly():
    """Two log lines did `MODEL_MIN_ODDS[model_id]`, which is a KeyError for
    any model without an explicit entry — now the common case. The message
    would have crashed the very branch that blocks the bet."""
    src = (Path(__file__).parent.parent / "models"
           / "scorer.py").read_text(encoding="utf-8")
    assert "MODEL_MIN_ODDS[" not in src


def test_the_mirror_never_writes_a_null_floor():
    """model_action_thresholds.min_odds is what the app's action filter, the
    Discord card and the track-record views read. A NULL there re-opens the
    hole downstream of a scorer that has closed it."""
    src = (Path(__file__).parent.parent / "data"
           / "threshold_sync.py").read_text(encoding="utf-8")
    assert "min_odds_for(mid)" in src
    assert "MODEL_MIN_ODDS.get(mid)" not in src


def test_the_default_is_overridable_without_a_code_change():
    """It is a house risk number, so it belongs behind an env var — the value
    is a judgement, not a measurement."""
    src = (Path(__file__).parent.parent / "config.py").read_text(encoding="utf-8")
    assert 'os.environ.get("DEFAULT_MIN_ODDS"' in src


def test_the_measured_blast_radius_is_recorded():
    """§1b: never estimate what you can measure. Whoever changes this number
    next needs the prospective count, not the misleading all-history one."""
    src = (Path(__file__).parent.parent / "config.py").read_text(encoding="utf-8")
    assert "38 bets" in src and "-330" in src
