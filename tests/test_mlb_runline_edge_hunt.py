"""MLB runline edge hunt: grading, as-of garbage filter, ship bar.

Measure-only. These tests pin the math the 2026-09-19 tables were
taken at — HOME scored_line (§4), the July-1 Action Network both-sides
~100 drop, and the n≥40 / 2-green-month / max-4-per-day clear bar
that refused the +1.2%/42 peak.
"""
from __future__ import annotations

from pathlib import Path

import config
from scripts.mlb_runline_edge_hunt import (
    _sane_split,
    american_units,
    grade_rl,
    is_runline,
    summarize,
)


def test_runline_is_plus_or_minus_one_and_a_half():
    assert is_runline(-1.5) is True
    assert is_runline(1.5) is True
    assert is_runline(-2.5) is False
    assert is_runline(None) is False


def test_home_minus_one_five_covers_only_a_two_run_win():
    """scored_line is the HOME number. Home −1.5 needs a 2-run win."""
    result, _ = grade_rl("home", -1.5, hs=3, aws=1)
    assert result == "WIN"
    result, _ = grade_rl("home", -1.5, hs=2, aws=1)
    assert result == "LOSS"
    result, _ = grade_rl("away", -1.5, hs=2, aws=1)
    assert result == "WIN"
    result, _ = grade_rl("away", -1.5, hs=3, aws=1)
    assert result == "LOSS"


def test_missing_score_is_not_a_push():
    result, units = grade_rl("home", -1.5, hs=None, aws=4)
    assert result is None
    assert units is None


def test_july_first_both_sides_near_100_is_garbage():
    assert _sane_split(100.0, 99.0) is False
    assert _sane_split(56.0, 44.0) is True
    assert _sane_split(90.0, 10.0) is True
    assert _sane_split(80.0, 4.0) is False  # sum 84, off by more than 15


def test_flat_unit_minus_110_is_one_over_one_one():
    assert american_units(-110, True) == 100.0 / 110.0
    assert american_units(-110, False) == -1.0
    assert american_units(150, True) == 1.5


def test_plus_one_point_two_percent_peak_does_not_clear():
    """Jun+Jul green and Sep red is not month-stable even at n=42."""
    rows = (
        [{"game_date": "2026-06-15", "result": "WIN", "units": 0.91}] * 13
        + [{"game_date": "2026-06-16", "result": "LOSS", "units": -1.0}] * 10
        + [{"game_date": "2026-07-03", "result": "WIN", "units": 0.91}] * 7
        + [{"game_date": "2026-07-04", "result": "LOSS", "units": -1.0}] * 6
        + [{"game_date": "2026-09-16", "result": "LOSS", "units": -1.0}] * 4
        + [{"game_date": "2026-09-17", "result": "WIN", "units": 0.91}] * 2
    )
    s = summarize(rows)
    assert s["n"] == 42
    assert s["green_months"] == 2
    assert s["red_months"] == 1
    assert s["months"]["2026-09"]["roi"] < 0
    assert s["roi"] > 0
    assert s["clears"] is False


def test_a_true_clear_needs_n_two_green_months_and_no_red_month():
    rows = []
    for day, n_win, n_loss in (
        ("2026-06-10", 12, 8),
        ("2026-07-10", 12, 8),
        ("2026-09-16", 8, 4),
    ):
        rows.extend(
            [{"game_date": day, "result": "WIN", "units": 0.91}] * n_win
        )
        rows.extend(
            [{"game_date": day, "result": "LOSS", "units": -1.0}] * n_loss
        )
    s = summarize(rows)
    assert s["n"] == 52
    assert s["green_months"] == 3
    assert s["max_per_day"] <= 4 or s["max_per_day"] > 4
    # 20 bets on one day fails the selective cap.
    assert s["max_per_day"] == 20
    assert s["clears"] is False
    # Same units, one bet per calendar day so max/day ≤ 4.
    per_month = {}
    spread = []
    for r in rows:
        m = r["game_date"][:7]
        per_month[m] = per_month.get(m, 0) + 1
        spread.append({**r, "game_date": f"{m}-{per_month[m]:02d}"})
    s2 = summarize(spread)
    assert s2["n"] == 52
    assert s2["green_months"] == 3
    assert s2["max_per_day"] <= 4
    assert s2["roi"] > 0
    assert s2["clears"] is True


def test_hunt_does_not_unpause_or_publish():
    src = Path("scripts/mlb_runline_edge_hunt.py").read_text(encoding="utf-8")
    assert "PAUSED_MODELS" not in src
    assert "PUBLISH=1" not in src
    assert "mlb_runline" in config.PAUSED_MODELS
    assert config.MLB_SPREAD_MARKET_PUBLISH is False
    assert "MLB_RUNLINE_PUBLIC_FADE_PUBLISH" not in dir(config)
