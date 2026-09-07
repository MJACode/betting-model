"""A rule is not a missing artifact, and the dashboard must not conflate them.

nfl_wind_totals, nfl_opener_spread, nfl_prop_market, nfl_live_prop and
wnba_prop_market carry thresholds and fire, but have no trained artifact and
never will -- the logic IS the model. config.py says so at nfl_prop_market: "a
rule with no artifact".

The roster page had two states, `version` or not, so all five rendered as a red
NO ARTIFACT. That put nfl_prop_market -- the only NFL prop approach with a
positive blind result, +10.33% over 954 bets -- on screen looking broken, and
the summary line counted five rules as five outages.

The same confusion had already produced a false test failure the same day:
test_artifact_deserialises rejected ncaaf_spread and ncaaf_spread_premium for
carrying model=None, which is correct for a kind='cross_book_opener' rule.
Third time it cost something, so it is pinned here.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest

import config

DASH = Path(__file__).resolve().parent.parent / "monitoring" / "static" / "dashboard.html"
HTML = io.open(DASH, encoding="utf-8").read()

# Rules: they carry a cut and fire, but are in no training registry.
KNOWN_RULES = {
    "nfl_wind_totals", "nfl_opener_spread", "nfl_prop_market",
    "nfl_live_prop", "wnba_prop_market",
}


@pytest.mark.parametrize("model_id", sorted(KNOWN_RULES))
def test_a_rule_carries_a_cut_but_is_in_no_training_registry(model_id):
    """The property the dashboard keys on. If one of these ever enters MODELS
    or PROP_MODELS it stops being a rule and this test says so."""
    assert model_id in config.ACTION_THRESHOLDS, f"{model_id} has no cut"
    trainable = set(config.MODELS) | set(config.PROP_MODELS) | set(config.LIVE_MODELS)
    assert model_id not in trainable, (
        f"{model_id} is now trainable — it is no longer a rule")


def test_the_roster_query_flags_rules():
    """monitoring/store.model_roster must emit is_rule, derived from the
    registries rather than a hardcoded list of ids — a hardcoded list is one
    the next rule would not be on."""
    import inspect

    from monitoring import store

    src = inspect.getsource(store.model_roster)
    assert '"is_rule"' in src, src
    assert "PROP_MODELS" in src and "LIVE_MODELS" in src, (
        "LIVE_MODELS must be included, or four trained live models are "
        "mislabelled as rules")


def test_the_dashboard_renders_a_third_state():
    assert "RULES MODEL" in HTML
    assert "m.is_rule" in HTML
    # ...and still keeps the real failure state, or an outage becomes invisible.
    assert "NO ARTIFACT" in HTML


def test_a_rule_is_not_styled_as_a_warning():
    """It was amber, the same as a broken model. A rule is a normal state."""
    assert ".pill.rule{color:var(--muted)" in HTML


def test_the_summary_counts_rules_apart_from_outages():
    """`5 no artifact` read as five outages when it was five rules and no
    outage."""
    assert "${rules} rules" in HTML
    assert "m.is_rule).length" in HTML


def test_a_rule_sorts_with_the_live_models_not_the_broken_ones():
    """It is firing. Only a genuinely missing artifact belongs with problems."""
    assert "m.is_rule?1 : 2" in HTML
