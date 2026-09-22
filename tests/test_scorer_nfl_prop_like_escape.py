"""Regression: #813's unescaped LIKE '%' aborted every Daily Scorer pass.

On 2026-09-22 ~11:10 UTC, deploy of #813 added

    AND model_id NOT LIKE 'nfl_prop_%'

to both non-BET clears in models/scorer.run_scorer. DBConnection.execute
adapts ?→%s and psycopg2 then %-interpolates the whole statement against
the params tuple. A bare % is a format spec; with one bound game_id the
interpolation raises exactly:

    IndexError: tuple index out of range

(or TypeError: not enough arguments for format string under plain %-format).
Railway worker logs (virtuous-light / production):

    Pick lock: 26 game-model pick(s) already locked for 2026-09-22 — preserving
    ERROR | Scorer failed: tuple index out of range
    ERROR | ✗ Scoring failed: tuple index out of range

pipeline_runs.run_id 2e0048f0e2b749b6ad437ad633a6e039 (hourly, ok=false,
failed_steps=scoring, started_at 2026-09-22T11:17:00Z). Same class as #243
(signal_delivery's LIKE '%:early').

The production pattern must be written 'nfl_prop_%%' so the DB sees one
wildcard after psycopg2's escape. These tests reproduce the short-tuple
crash on the broken form and pin that the live SQL interpolates.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "models" / "scorer.py").read_text(encoding="utf-8")


def _between(start: str, end: str) -> str:
    i = SRC.index(start)
    return SRC[i:SRC.index(end, i)]


def _first_sql(block: str) -> str:
    return re.search(r'"""(.*?)"""', block, re.S).group(1)


def _per_game_sql() -> str:
    return _first_sql(_between(
        "ONE GAME = ONE TRANSACTION",
        "for model_id in relevant_models:",
    ))


def _sweep_sql() -> str:
    return _first_sql(_between(
        "# Housekeeping for the pairs the lock deliberately leaves open.",
        'logger.info(f"Cleared unsettled picks',
    ))


def _broken_per_game_sql() -> str:
    """The #813 form that crashed production: single % in the LIKE pattern."""
    return _per_game_sql().replace("nfl_prop_%%", "nfl_prop_%")


def test_unescaped_like_percent_raises_on_short_params_tuple():
    """Reproduce the production IndexError / format failure on one param."""
    broken = _broken_per_game_sql()
    assert "NOT LIKE 'nfl_prop_%'" in broken
    assert "NOT LIKE 'nfl_prop_%%'" not in broken
    with pytest.raises((IndexError, TypeError, ValueError)):
        broken % ("MLB_2026-09-22_ARI_COL",)


def test_live_per_game_clear_interpolates_with_one_game_id():
    sql = _per_game_sql()
    assert "NOT LIKE 'nfl_prop_%%'" in sql
    # Must not raise — this is the statement the first unscored game runs
    # immediately after pick-lock.
    rendered = sql % ("MLB_2026-09-22_ARI_COL",)
    assert "nfl_prop_%" in rendered
    assert "%%" not in rendered


def test_live_sweep_clear_interpolates_with_date_horizon_now():
    sql = _sweep_sql()
    assert "NOT LIKE 'nfl_prop_%%'" in sql
    rendered = sql % ("2026-09-22", "2026-09-29", "2026-09-22T11:18:00+00:00")
    assert "nfl_prop_%" in rendered
    assert "%%" not in rendered


def test_escape_tripwire_is_on_the_pr_ci_subset():
    """#813's pin ran in CI; the %-escape tripwire that would have blocked
    it was not. Keep both on the subset so the next bare % fails the PR."""
    yml = (ROOT / ".github" / "workflows" / "pr-ci.yml").read_text(
        encoding="utf-8")
    assert "tests/test_sql_percent_escaping.py" in yml
    assert "tests/test_scorer_nfl_prop_like_escape.py" in yml
