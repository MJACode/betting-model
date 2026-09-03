"""Stage 2 step 1 — the best-price threshold sweep's own arithmetic.

mike, 2026-09-03: "stage 2 go." The sweep writes nothing, but it is the
evidence a threshold flip will be argued from, so the two places it could be
quietly wrong are pinned here:

  1. the payout recomputed at the best price, which must match the convention
     mv_scored_pick_outcomes.profit_units already uses, and
  2. the "same picks, better price" column, which must contain EXACTLY the pick
     set today's cut makes — no more. Overstating it would manufacture the
     result the whole flip is being justified by.

Pure functions and fakes. No network, no DB.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import best_line_threshold_sweep as bls  # noqa: E402


# ── 1. the payout at the best price ──────────────────────────────────────────
# Verified 2026-09-03 against stored mv_scored_pick_outcomes rows: WIN at -140
# is +0.7143 (209 rows), at -110 +0.9091 (462), at +150 +1.5000 (188); LOSS is
# -1.0 at every price and PUSH is 0. Same convention, or the sweep's ROI is not
# comparable with the record everything else publishes.

@pytest.mark.parametrize("odds,expected", [(-140, 0.7143), (-110, 0.9091),
                                           (150, 1.5), (-200, 0.5), (100, 1.0)])
def test_a_win_pays_the_stored_convention(odds, expected):
    assert bls.units_at(odds, "WIN") == pytest.approx(expected, abs=5e-5)


@pytest.mark.parametrize("odds", [-140, -110, 150, 100, -2000])
def test_a_loss_costs_one_unit_at_every_price(odds):
    assert bls.units_at(odds, "LOSS") == -1.0


@pytest.mark.parametrize("odds", [-140, 150])
def test_a_push_is_flat(odds):
    assert bls.units_at(odds, "PUSH") == 0.0


def test_a_better_price_pays_more_than_the_dk_price():
    """The whole premise in one line: +100 must beat -110 on the same win."""
    assert bls.units_at(100, "WIN") > bls.units_at(-110, "WIN")


# ── 2. the free half must not quietly grow ───────────────────────────────────

class _Conn:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        self._last = sql
        return self

    def fetchall(self):
        return self._rows

    def close(self):
        pass


def _row(pick_id, p, dk_edge, dk_odds, best_odds, result, day="2026-09-01"):
    """(pick_id, game_date, model_probability, edge, dk_odds, best_edge,
    best_odds, best_book, result) — the fetch query's column order.

    `dk_edge` is passed rather than derived: the collision this file exists to
    catch is two picks that agree on (date, probability, price) and DISAGREE on
    edge, which is what a real prop slate looks like.
    """
    return (pick_id, day, p, dk_edge, dk_odds, dk_edge + 0.02, best_odds,
            "betmgm", result)


def test_the_free_half_never_changes_the_pick_set(monkeypatch):
    """`same @best` must hold EXACTLY the rows today's cut makes.

    Keyed on (date, probability, price) it did not. Two picks on one slate can
    share all three and differ on EDGE — the same probability against two
    different market prices — so a row the cut REJECTED was pulled into the
    better-price column by a colliding tuple. That inflates the one number the
    flip would be argued from, in the flattering direction.

    Rows 1 and 3 below are that collision: same day, same 0.80 probability,
    same -110, and only row 1 clears the 0.10 edge cut. Watched failing against
    the tuple key (n=2 where the cut makes 1).
    """
    rows = [
        _row(1, 0.80, 0.30, -110, 100, "WIN"),    # qualifies
        _row(3, 0.80, 0.01, -110, 100, "LOSS"),   # SAME tuple, fails on edge
        _row(4, 0.51, 0.30, -110, 100, "WIN"),    # fails on probability
    ]
    monkeypatch.setattr(bls.config, "ACTION_THRESHOLDS",
                        {"m": {"min_prob": 0.60, "min_edge": 0.10}}, raising=False)
    monkeypatch.setattr(bls.config, "MODEL_MIN_ODDS", {}, raising=False)
    out = bls.analyse(_Conn(rows), "m", date(2026, 9, 2), min_rows=1)

    assert out["now"]["n"] == 1, "today's cut takes exactly one row here"
    assert out["same_at_best"]["n"] == out["now"]["n"], (
        "the free half changed the pick set — it must only change the payout")
    assert out["same_at_best"]["l"] == 0, (
        "a rejected LOSS was credited to the better price by a colliding key")


def test_the_free_half_is_worth_more_than_the_dk_price():
    """Same one win and one loss, paid at +100 instead of -110."""
    assert (bls.units_at(100, "WIN") + bls.units_at(100, "LOSS")
            > bls.units_at(-110, "WIN") + bls.units_at(-110, "LOSS"))


def test_a_retired_model_is_never_recommended_a_cut():
    """Retirement deletes the model_action_thresholds row (session 170 removed
    batter_hr and batter_rbi that way), and both still carry hundreds of graded
    best-price rows. Recommending a cut for a model that no longer scores is
    noise, so the model list is a JOIN and never a hand-maintained list."""
    src = (Path(__file__).parent.parent / "scripts"
           / "best_line_threshold_sweep.py").read_text(encoding="utf-8")
    assert "FROM model_action_thresholds" in src
    assert "if m in live" in src


def test_the_sweep_writes_nothing():
    """A threshold change is a model update and needs a person's name on it
    (CLAUDE.md §1b). This script is evidence, not an actuator."""
    src = (Path(__file__).parent.parent / "scripts"
           / "best_line_threshold_sweep.py").read_text(encoding="utf-8")
    for forbidden in ("INSERT", "UPDATE ", "DELETE", "commit("):
        assert forbidden not in src, f"the sweep can write ({forbidden})"
