"""The NFL prop cuts are a volume control, and the look-ahead that feeds them.

Two changes on 2026-09-07 (matt), pinned here because both are the kind that a
later "reset the placeholders" edit would silently undo:

  1. Per-market floors replacing the uniform 0.55 / 0.05 placeholder. Derived
     from the top decile of each market's own edge distribution on the Week-1
     board — NOT swept on a record, because these models have zero settled
     bets. They cut one Sunday from 112 BETs to ~18.
  2. The scorer scores the whole look-ahead window instead of one date, off the
     SAME constant the card fetches on.

Neither test asserts the models are profitable. docs/nfl_props_model.md §5b
walk-forwards all eleven against real DraftKings prices and every one loses;
these floors reduce exposure to that, they do not reverse it.
"""
from __future__ import annotations

import ast
import io
import math
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# The uniform placeholder these replaced. Any market back at this pair means
# the reset happened.
PLACEHOLDER = (0.55, 0.05)

MARKETS = (
    "nfl_prop_pass_yards", "nfl_prop_pass_attempts", "nfl_prop_pass_completions",
    "nfl_prop_pass_tds", "nfl_prop_rush_yards", "nfl_prop_rush_attempts",
    "nfl_prop_rec_yards", "nfl_prop_receptions", "nfl_prop_rush_rec_yards",
    "nfl_prop_anytime_td", "nfl_prop_sacks", "nfl_prop_tackles_assists",
)


@pytest.fixture(scope="module")
def cfg():
    import config
    return config


def test_no_nfl_prop_market_is_back_on_the_uniform_placeholder(cfg):
    """0.55/0.05 was applied to twelve markets with different base rates.

    anytime TD hits ~27% and receptions ~50%; one floor cannot be right for
    both, which is what made it a placeholder rather than a cut.
    """
    offenders = [
        m for m in MARKETS
        if (cfg.MODEL_PROB_THRESHOLDS[m], cfg.MODEL_EDGE_THRESHOLDS[m]) == PLACEHOLDER
    ]
    assert offenders == [], (
        f"back on the uniform placeholder: {offenders}. These were tightened "
        "2026-09-07 (matt) to cut a Week-1 Sunday from 112 BETs to ~18."
    )


def test_every_nfl_prop_edge_floor_is_tighter_than_the_placeholder(cfg):
    for m in MARKETS:
        assert cfg.MODEL_EDGE_THRESHOLDS[m] >= 0.15, (
            f"{m} edge floor {cfg.MODEL_EDGE_THRESHOLDS[m]} is looser than the "
            "0.15 minimum of the derived set"
        )


def test_the_three_threshold_dicts_agree_for_every_nfl_prop_market(cfg):
    """The scorer reads MODEL_*_THRESHOLDS; the app reads ACTION_THRESHOLDS.

    They disagreeing is how a pick gets made and then hidden, or shown and
    never made.
    """
    for m in MARKETS:
        act = cfg.ACTION_THRESHOLDS[m]
        assert act["min_prob"] == cfg.MODEL_PROB_THRESHOLDS[m], m
        assert act["min_edge"] == cfg.MODEL_EDGE_THRESHOLDS[m], m


def test_the_prop_window_has_exactly_one_declaration(cfg):
    """scheduler must READ config.NFL_PROP_WINDOW_HOURS, not redeclare it.

    The card fetched ten days of board while the scorer scored one date, for
    exactly as long as the two owned separate numbers.
    """
    assert cfg.NFL_PROP_WINDOW_HOURS > 0
    src = io.open(REPO / "scheduler.py", encoding="utf-8").read()
    assignments = [
        n for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.Assign)
        and any(getattr(t, "id", "") == "NFL_PROP_WINDOW_HOURS" for t in n.targets)
    ]
    assert assignments == [], (
        "scheduler.py re-declares NFL_PROP_WINDOW_HOURS; it must import it "
        "from config so the card and the scorer cannot drift apart"
    )

    import scheduler
    assert scheduler.NFL_PROP_WINDOW_HOURS == cfg.NFL_PROP_WINDOW_HOURS


def test_the_scorer_step_covers_the_whole_window_not_one_date(monkeypatch, cfg):
    """The regression itself: score every date in the window, not just today."""
    import run_pipeline

    seen: list[str] = []

    def fake(target_date=None, dry_run=False):
        seen.append(target_date)
        return {"picks": 0, "bets": 0, "skipped_dupes": 0}

    monkeypatch.setattr("models.scorer.run_nfl_prop_scorer", fake)
    run_pipeline.step_nfl_prop_scoring("2026-09-07", dry_run=True)

    expected = max(2, math.ceil(cfg.NFL_PROP_WINDOW_HOURS / 24)) + 1
    assert len(seen) == expected, (
        f"scored {len(seen)} date(s), expected {expected} across a "
        f"{cfg.NFL_PROP_WINDOW_HOURS:g}h window"
    )
    assert seen[0] == "2026-09-07"
    # the Week-1 Sunday must be inside the window from the Monday before it
    assert "2026-09-13" in seen


def test_one_bad_date_does_not_cost_the_others(monkeypatch, cfg):
    """The near dates are the ones with games about to start."""
    import run_pipeline

    seen: list[str] = []

    def fake(target_date=None, dry_run=False):
        seen.append(target_date)
        if target_date == "2026-09-09":
            raise RuntimeError("boom")
        return {"picks": 1, "bets": 1, "skipped_dupes": 0}

    monkeypatch.setattr("models.scorer.run_nfl_prop_scorer", fake)
    ok = run_pipeline.step_nfl_prop_scoring("2026-09-07", dry_run=True)

    assert ok is False, "a failed date must be reported"
    assert len(seen) > 3, "the loop stopped at the failure instead of continuing"
