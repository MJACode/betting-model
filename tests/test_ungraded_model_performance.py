"""A model with a settled record must not read as "awaiting first pick".

Matt, 2026-09-04, with the app's Models tab beside the dashboard: the numbers
on the models do not match what the Retool app is fed.

The Models panel (monitoring/store.py::model_performance) is also the query the
Retool app was ported from on 2026-08-31, so whatever it reports, Retool
reports. It aggregated `mv_scored_pick_outcomes` and nothing else — and that
matview only carries what it can regrade from box scores: an explicit model
allow-list, and no in-play picks (`p.is_live IS NOT TRUE`, plus no `*_live_*`
model in the list). Since `profit_units` exists ONLY in the matview, every model
outside it joined to nothing, came back settled=0, and the dashboard rendered
that zero as "registered · awaiting first pick".

Measured against production 2026-09-04 — eleven models, 182 settled BETs, all
reading as never having fired:

    mlb_live_total_runs   94  58-36  +12.25u   <- best MLB model on the app
    mlb_live_win_prob     17   7-10   -5.44u      (retired)
    mlb_live_runline      16   6-10   -6.08u      (retired)
    ufc_total_rounds      13   8-5    -1.86u
    mlb_f5_over_under     11   8-1    unpriced
    ncaaf_live_total       8   3-5    -2.50u
    mlb_f5_runline         7   4-3    unpriced
    wnba_spread            6   2-4    -2.15u
    ufc_method_of_victory  5   3-2    unpriced
    ufc_moneyline          3   2-1    +0.57u
    ncaaf_live_win_prob    2   1-1    -0.58u

That is CLAUDE.md §7 exactly: an empty board and a broken pipeline look
identical, and here the whole of UFC and every live lane looked like the
latter.

The fix is a second arm on the `agg` CTE reading those models out of `picks`
(`profit_flat` is units x 100). What this test pins is the arm's SCOPE, because
two narrower filters are both wrong: keying on `model_id LIKE '%_live_%'` fixes
the live lanes and leaves UFC broken, and keying on `is_live` would sweep every
pre-game prop model's in-play picks into its pre-game row — a different bet at
a different price, which CLAUDE.md §6 keeps apart. Keying on "the matview does
not grade this model at all" is disjoint by construction, so no model is split
across the two arms, and the arm empties itself as the allow-list grows.
"""
from __future__ import annotations

import inspect

import pytest

from monitoring import store
from tests.test_monitoring import FakeConn


def _sql() -> str:
    return inspect.getsource(store.model_performance)


def _second_arm() -> str:
    """The second arm of the agg CTE, SELECT list included.

    Sliced at UNION ALL rather than at `FROM picks`: SQL puts the SELECT list
    above the FROM, so slicing at the FROM drops every aggregate the arm is
    being asserted about.
    """
    src = _sql()
    assert "UNION ALL" in src, "no second arm — ungraded models have no source"
    return src[src.index("UNION ALL"):]


def test_models_the_matview_does_not_grade_are_sourced_from_picks():
    """The matview holds no row for these models, so their record can only come
    from `picks`. Without this arm all eleven report settled=0."""
    arm = _second_arm()
    assert "FROM picks" in arm, (
        "with no picks arm, mlb_live_total_runs reports 0 settled against a "
        "real 94, and every UFC model reports 0 against a real 21")
    assert "profit_flat" in arm


def test_the_arm_is_scoped_by_absence_from_the_matview_not_by_model_id():
    """A model-id pattern is the tempting filter and it goes stale: `_live_`
    would fix the five live lanes and leave UFC, wnba_spread and the two F5
    markets reading as never fired. Absence from the matview covers all of
    them and empties itself as the allow-list grows."""
    arm = _second_arm()
    assert "NOT EXISTS" in arm and "mv_scored_pick_outcomes" in arm, (
        "the arm must select models the matview does not grade")
    assert "m.model_id = p.model_id" in arm, (
        "the anti-join keys on model_id — that is what makes the arms disjoint")
    assert "LIKE" not in arm, "a model-id pattern goes stale; use the anti-join"


def test_the_arm_does_not_key_on_is_live():
    """`is_live IS TRUE` would fold every pre-game prop model's in-play picks
    into its pre-game row (CLAUDE.md §6 — pre-game and in-play never mix).
    Measured 2026-09-04: that filter would have moved mlb_prop_batter_hits by
    116 settled picks it never took pre-game."""
    assert "is_live" not in _second_arm()


def test_the_arm_prices_units_the_same_way_the_matview_does():
    """The matview leaves profit_units NULL for an unpriced pick so it lands in
    neither the units nor the ROI denominator. The picks arm has no such column
    and has to reproduce the gate, or an unpriced pick is settled at a price
    that never existed — three of the eleven models above are fully unpriced."""
    arm = _second_arm()
    assert "FILTER (WHERE p.dk_odds IS NOT NULL)" in arm
    assert "/ 100.0" in arm, "profit_flat is units x 100"


def test_both_arms_stay_inside_the_settled_bet_gate():
    """NO_ACTION (a void) and NULL (unsettled) sit alongside WIN/LOSS/PUSH in
    picks.result. A void never stood, so it belongs in no denominator."""
    src = _sql()
    assert src.count("result IN ('WIN', 'LOSS', 'PUSH')") == 2, (
        "each arm gates on settled BET picks independently")
    assert src.count("signal_type = 'BET'") == 2


def test_a_recovered_row_still_reports_roi_over_the_priced_bets():
    """The Python half is shared by both arms — a row from the picks arm must
    come out of it with the same push-excluded denominator as a matview one."""
    rows = FakeConn([("mlb_live_total_runs", "MLB", 94, 58, 36, 0, 94, 12.25,
                      "2026-09-03", False, True)])
    m = store.model_performance(rows)[0]
    assert m["settled"] == 94 and m["wins"] == 58
    assert m["roi_pct"] == pytest.approx(12.25 / 94 * 100)


def test_a_fully_unpriced_recovered_model_reports_no_roi():
    """ufc_method_of_victory has never had a price — The Odds API carries no
    method market. Its record is real and its ROI must stay None rather than
    become 0.0%, which reads as break-even."""
    rows = FakeConn([("ufc_method_of_victory", "UFC", 5, 3, 2, 0, 0, 0.0,
                      "2026-08-22", False, True)])
    m = store.model_performance(rows)[0]
    assert m["settled"] == 5 and m["wins"] == 3
    assert m["roi_pct"] is None
