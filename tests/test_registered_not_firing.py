"""A registered model that has not fired must be VISIBLE, not absent.

mike, 2026-08-30: "I know NFL models will start firing in a week or so... I did
not even see them as models in the railway dashboard."

He was right, and the cause is not registration. NFL has 15 threshold rows and
12 active artifacts, but ZERO picks ever -- and the performance panel was built
from graded outcomes alone, so a model with no settled pick simply did not
exist on the page. That is CLAUDE.md section 7 exactly: an empty board and a
broken pipeline look identical. The week before kickoff is precisely when you
need to tell them apart.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from monitoring import store

ROOT = Path(__file__).parent.parent


def test_performance_starts_from_the_registered_models_not_the_graded_picks():
    src = inspect.getsource(store.model_performance)
    assert "FROM model_action_thresholds t" in src, (
        "built from outcomes alone, a model with no settled pick is invisible")
    assert "LEFT JOIN agg" in src, "an inner join drops the not-yet-firing models"


def test_a_model_with_picks_but_no_threshold_row_is_still_listed():
    """The UNION arm. A retired model keeps its record even after its threshold
    row goes; losing it would silently rewrite history."""
    src = inspect.getsource(store.model_performance)
    assert "UNION ALL" in src
    assert "WHERE NOT EXISTS (SELECT 1 FROM model_action_thresholds t" in src


def test_it_reports_whether_the_model_is_paused_and_whether_it_is_trained():
    """Three states have to be distinguishable on the page, because the fix for
    each is different: paused (a decision), no artifact (a retrain), and
    awaiting its first pick (nothing -- wait for kickoff)."""
    src = inspect.getsource(store.model_performance)
    assert "t.paused" in src
    assert "is_active = 1" in src
    for col in ("paused", "trained"):
        assert f'"{col}"' in src, f"{col} is queried but never returned"


def test_the_sport_survives_when_there_are_no_graded_picks():
    """sport comes off the outcomes matview, which has no row for a model that
    never fired -- so NFL would chip as blank without the fallback."""
    src = inspect.getsource(store.model_performance)
    assert "upper(split_part(t.model_id, '_', 1))" in src


def test_the_dashboard_renders_the_not_yet_firing_state():
    html = (ROOT / "monitoring/static/dashboard.html").read_text(encoding="utf-8")
    assert "not yet firing" in html
    assert "registered · no trained artifact" in html
    assert "registered · awaiting first pick" in html


def test_the_zero_state_short_circuits_before_the_roi_row():
    """Rendering a 0-0 record through the normal row prints '0-0' and a '—' ROI,
    which reads as a model that lost nothing rather than one that never ran."""
    html = (ROOT / "monitoring/static/dashboard.html").read_text(encoding="utf-8")
    body = html[html.index("function renderPerf()"):html.index("function renderLiveCal()")]
    assert body.index("if(!settled){") < body.index('${roi==null?"record only"'), (
        "the zero-state must return before the ROI row is rendered")
