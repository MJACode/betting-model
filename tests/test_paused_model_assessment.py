"""The standing assessment: a losing model is swept, not paused.

CLAUDE.md section 1b (mike, 2026-09-12). These pin the four things the tool
must not quietly lose, each of which would turn a "no" into a false "yes":
both pause registers, the graded universe, the era, and the honesty of the
fallback population.
"""
from __future__ import annotations

from pathlib import Path

from scripts import paused_model_assessment as pma

SRC = (Path(__file__).parent.parent / "scripts" / "paused_model_assessment.py").read_text(
    encoding="utf-8")


def _rows(n, roi_each, date="2026-09-01"):
    return [{"date": date, "p": 0.70, "edge": 0.20,
             "u": roi_each, "res": "WIN" if roi_each > 0 else "LOSS"}
            for _ in range(n)]


def test_it_sweeps_both_pause_registers():
    """config.PAUSED_MODELS is what a person chose; model_auto_pauses is what
    the 250-bet review decided. Sweeping only the first missed the two models
    auto-paused the day before this shipped."""
    assert "_auto_paused_models" in SRC
    assert "set(config.PAUSED_MODELS) | set(_auto_paused_models())" in SRC


def test_it_prefers_the_graded_universe_and_names_the_fallback():
    assert "FROM mv_scored_pick_outcomes" in SRC
    assert "SETTLED BETS ONLY" in SRC, (
        "a BET-only sweep is systematically optimistic and must say so")
    body = SRC[SRC.index("def fetch("):SRC.index("def grade(")]
    assert body.index("mv_scored_pick_outcomes") < body.index("FROM picks"), (
        "the graded universe comes first; picks is the fallback")


def test_a_cell_below_the_floor_is_not_a_result():
    cells = pma.sweep(_rows(10, 0.9))
    assert all(c["n"] < pma.MIN_SETTLED for c in cells)
    assert pma.MIN_SETTLED == 25


def test_units_are_none_when_the_pick_carries_no_price():
    """profit_flat fabricates -110 for an unpriced pick (CLAUDE.md section 6),
    so an unpriced row must drop out rather than contribute invented units."""
    assert pma._units(None, "WIN") is None
    assert pma._units(None, "LOSS") is None
    assert pma._units(-110.0, "PUSH") == 0.0
    assert round(pma._units(150.0, "WIN"), 4) == 1.5
    assert pma._units(-200.0, "LOSS") == -1.0


def test_the_grade_reports_a_lower_bound_not_just_a_headline():
    g = pma.grade(_rows(30, 0.9) + _rows(30, -1.0))
    assert g["n"] == 60 and g["roi"] is not None and g["ci_lo"] is not None
    assert g["ci_lo"] < g["roi"], "the interval must be below the point estimate"


def test_the_era_check_is_applied_to_every_candidate():
    """The check that changed the answer: pooled records span retrains, and
    every candidate collapsed once scoped to the artifact actually deployed."""
    assert "def active_era(" in SRC
    assert "WHERE is_active = 1" in SRC
    body = SRC[SRC.index("def assess("):SRC.index("def main(")]
    assert "era_rows" in body and "NOT yet evidence about this model" in body


def test_the_plateau_and_the_time_split_are_both_required():
    body = SRC[SRC.index("def assess("):SRC.index("def main(")]
    assert "c[\"plateau\"] >= MIN_PLATEAU" in body
    assert "half_a" in body and "half_b" in body
    assert "FAILS THE TIME SPLIT" in body and "PEAK, NOT A PLATEAU" in body


def test_it_writes_no_threshold():
    for banned in ("UPDATE model_action_thresholds", "INSERT INTO model_action_thresholds",
                   "PAUSED_MODELS.add", "DELETE FROM model_auto_pauses"):
        assert banned not in SRC, "a threshold change is a model update with a name on it"


def test_the_rule_is_in_claude_md():
    rules = (Path(__file__).parent.parent / "CLAUDE.md").read_text(encoding="utf-8")
    assert "A LOSING MODEL IS AN ASSESSMENT TO RUN, NOT A MODEL TO PAUSE" in rules
    assert "docs/paused_model_assessment.md" in rules
