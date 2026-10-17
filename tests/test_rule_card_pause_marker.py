"""A paused model's rows say so themselves, whichever writer stores them.

config.PAUSED_NOTE: every row a paused model writes carries downgrade_reason =
'model paused', stamped at write time; every publisher and record query keys on
that marker, so a pick written while paused stays unannounced after an unpause.
The scorer's builders stamp it. The rule cards that write through the shared
insert (models.scorer._insert_picks: mlb_game_market, mlb_total_public_fade,
nhl_over_under) built rows without the column, so a paused rule card's rows
went in unmarked. The insert now stamps the marker on a row that does not set
the column; nba_total_luck, with its own insert, stamps it itself
(tests/test_nba_total_luck.py).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config  # noqa: E402
from models import scorer  # noqa: E402


class _Conn:
    def __init__(self):
        self.rows = []

    def executemany(self, sql, rows):
        self.rows.extend(rows)


def _row(model_id, **extra):
    return {"game_id": "G", "model_id": model_id, "sport": "NHL", "game_date": "2026-11-05",
            "pick_side": "over", "pick_label": "BOS vs NYR Over 6.5", "model_probability": 0.56,
            "dk_implied_prob": 0.52, "edge": 0.04, "dk_odds": -110, "scored_line": 6.5,
            "kelly_fraction": 0.01, "recommended_bet": 10.0, "bankroll_at_pick": 1000.0,
            "injury_flag": 0, "injury_detail": None, "signal_type": "BET",
            "confidence_tier": "MED", **extra}


@pytest.mark.parametrize("paused", [False, True])
def test_a_rule_card_row_without_the_column_is_stamped_when_its_model_is_paused(
        monkeypatch, paused):
    monkeypatch.setattr(scorer, "_auto_paused_models", lambda: set())
    monkeypatch.setattr(scorer, "PAUSED_MODELS", {"nhl_over_under"} if paused else set())
    monkeypatch.setattr(scorer, "_calibrated", lambda model_id, p: p)
    conn = _Conn()
    scorer._insert_picks(conn, [_row("nhl_over_under")])
    assert conn.rows[0]["downgrade_reason"] == (config.PAUSED_NOTE if paused else None)


def test_a_row_that_sets_the_column_keeps_its_own_value(monkeypatch):
    """The scorer's builders decide the column themselves (an EV-floor note, the
    marker, or None): the insert never overrides what a writer set."""
    monkeypatch.setattr(scorer, "_auto_paused_models", lambda: set())
    monkeypatch.setattr(scorer, "PAUSED_MODELS", {"nhl_over_under"})
    monkeypatch.setattr(scorer, "_calibrated", lambda model_id, p: p)
    conn = _Conn()
    scorer._insert_picks(conn, [_row("nhl_over_under", downgrade_reason="ev floor"),
                                _row("mlb_game_market", downgrade_reason=None)])
    assert [r["downgrade_reason"] for r in conn.rows] == ["ev floor", None]
