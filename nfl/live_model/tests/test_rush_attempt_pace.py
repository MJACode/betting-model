"""Guards on the rushing model that replaced the pass-attempt one.

WHAT WENT WRONG, SO THE GUARDS HAVE SOMETHING TO BE ABOUT. The model this
replaced priced every live quote with `over_prob(q.line, None, secs)`. Three
separate defects sat inside that one call and each has a test here:

  * `accrued=None` meant the model had NO IDEA what the player had already
    done, so it could not tell a line he had nearly reached from one he would
    have to double his pace to clear. It bet four quarterbacks before they had
    thrown a pass.
  * the function ignored the clock and returned a CONSTANT, which turned the
    expected-value threshold into a pure price filter.
  * the constants were bound as DEFAULT ARGUMENT VALUES, which Python evaluates
    once at import, so editing the shipped number changed nothing.

The most dangerous of the new failure modes is different and quieter: the
market switch. `picks.prop_market` decides which column settles a pick, so a
model that trades rushing attempts while something else still says
`player_pass_attempts` grades every bet against the wrong stat and looks
completely normal doing it. Three tests below exist only for that.
"""
from __future__ import annotations

import pytest

from live_model.models import rush_attempt_pace as rap


# ------------------------------------------------- the claim and its interval
def test_the_deployed_edge_sits_inside_its_measured_interval():
    """The guard that would have caught the model this replaces.

    That one shipped a 1.50 bias against a measured interval of (-0.42, +0.18)
    -- the deployed number was not merely optimistic, it was outside anything
    the data supported. Any future edit to DEPLOY_DELTA has to answer to the
    interval that was actually estimated.
    """
    lo, hi = rap.MEASURED_DELTA_CI
    assert lo < rap.DEPLOY_DELTA <= rap.MEASURED_DELTA, (
        f"deployed delta {rap.DEPLOY_DELTA} is not a haircut inside "
        f"({lo}, {hi})")


def test_the_interval_excludes_zero_so_an_edge_is_actually_claimed():
    lo, _ = rap.MEASURED_DELTA_CI
    assert lo > 0, "an interval spanning zero is not an edge"


# --------------------------------------------------------------- the gates
def _price(line=12.5, accrued=4, secs=1800, mkt=0.5, price=-110.0):
    return rap.under_prob(line, accrued, secs, mkt, price)


def test_a_missing_accrued_count_is_refused_not_treated_as_zero():
    """THE PRODUCTION DEFECT, pinned.

    `gameday.py` passed None here for the whole life of the old model. None and
    zero are different answers: zero means he has not carried yet, None means
    the feed did not say. Reading None as zero makes every line look
    unreachable, which would turn a name-matching failure into a BET.
    """
    assert _price(accrued=None).under_prob is None
    assert _price(accrued=None).reason == "no_accrued"


def test_no_bet_before_a_pace_exists():
    """Four of the old model's bets were placed before the player had touched
    the ball. With no carries there is no pace to compare a requirement to."""
    r = _price(accrued=0)
    assert r.under_prob is None and r.reason.startswith("no_pace_yet")


def test_a_reachable_over_is_declined_rather_than_faded():
    """The edge is specific: the book misprices the over when it needs a SURGE.
    Where the over is reachable at the pace he has been going, the archive says
    the book is about right, and claiming an edge there would be inventing one.
    """
    r = _price(line=8.5, accrued=6, secs=1800)
    assert r.under_prob is None and r.reason.startswith("over_is_reachable")


def test_a_line_he_has_already_passed_is_not_a_live_proposition():
    r = _price(line=3.5, accrued=9)
    assert r.under_prob is None and r.reason == "line_already_passed"


def test_the_juice_ceiling_is_enforced_by_the_model_not_the_board():
    """A ceiling the model applies is a decision; a ceiling the board applies
    is a disappearance -- the pick gets taken and then hidden from the person
    who has to place it."""
    assert _price(price=-200).under_prob is None
    assert _price(price=-140).under_prob is not None


def test_the_late_game_gate_still_fires():
    assert _price(secs=120).under_prob is None
    assert _price(secs=None).under_prob is None


def test_a_surge_requirement_reaches_a_price():
    r = _price(line=12.5, accrued=4, secs=1200)
    assert r.under_prob is not None
    assert r.reason.startswith("pace_surge_required")
    assert 0.0 < r.under_prob < 1.0


# ------------------------------------------- it is a model, not a constant
def test_the_emitted_probability_moves_with_the_book():
    """The defect being fixed was a CONSTANT probability, which collapses the
    expected-value threshold into a price filter. Two different book prices
    must produce two different numbers."""
    cheap = _price(mkt=0.40).under_prob
    dear = _price(mkt=0.60).under_prob
    assert cheap is not None and dear is not None
    assert dear > cheap + 0.10, "the model is not reading the book's price"


def test_the_edge_is_a_shift_on_the_book_not_a_replacement_for_it():
    """Whatever the book says, the model says a bit more -- never less."""
    for mkt in (0.35, 0.45, 0.55, 0.65):
        p = _price(mkt=mkt).under_prob
        assert p > mkt, f"no edge claimed at {mkt}"
        assert p < mkt + 0.13, f"implausible edge claimed at {mkt}"


def test_the_constants_are_read_at_call_time_not_import_time():
    """Python evaluates a default argument ONCE, at import. The model this
    replaces wrote `bias: float = DEPLOY_BIAS`, so editing DEPLOY_BIAS changed
    nothing and the function went on emitting the number it was born with."""
    import unittest.mock as mock
    with mock.patch.object(rap, "DEPLOY_DELTA", 5.0):
        hot = _price().under_prob
    cold = _price().under_prob
    assert hot > cold + 0.2, "DEPLOY_DELTA is frozen into the function object"

    with mock.patch.object(rap, "RATIO_CUT", 99.0):
        assert _price(line=12.5, accrued=4, secs=1200).under_prob is None


def test_the_ratio_is_the_requirement_against_the_actual_pace():
    # 4 carries in 30 elapsed minutes is 0.133/min; 8.5 more in 30 minutes
    # left is 0.283/min. The requirement is 2.125x what he has managed.
    r = rap.pace_ratio(12.5, 4, 1800)
    assert r == pytest.approx(2.125, rel=1e-3)
    assert rap.pace_ratio(12.5, 0, 1800) is None     # no pace to compare
    assert rap.pace_ratio(3.5, 9, 1800) is None      # already past the line


# -------------------------------- the quiet one: which stat settles the pick
def test_the_written_market_is_taken_from_the_model():
    """A market switch that updated the model and not the pick writer would
    stamp every new pick `player_pass_attempts` and settle a rushing bet
    against passing attempts -- silently, and unrecoverably after the fact."""
    from live_model import pick_writer
    assert pick_writer.LANE_MARKET == rap.MARKET


def test_the_worker_buys_the_market_the_model_trades():
    """The Odds API charges per market per event call, so the bought market is
    derived from the model rather than written out twice."""
    from live_model.workers.gameday import GamedayWorker
    w = GamedayWorker(dry_run=True)
    assert w.prop_markets == (rap.MARKET,)


def test_settlement_resolves_this_model_per_pick_not_per_model_id():
    """The old map hardcoded nfl_live_prop to "attempts". Re-pointing it at
    "carries" would have re-graded the 22 already-settled pass-attempt picks,
    which CLAUDE.md section 1c forbids. Resolving from picks.prop_market grades
    each pick against the market it was actually written on."""
    from tracking.paper_tracker import (_PROP_MARKET_STAT_BY_MODEL,
                                        _PROP_STAT_MAP)
    assert _PROP_STAT_MAP["nfl_live_prop"] == ("nfl_player", "FROM_PROP_MARKET")
    by_market = _PROP_MARKET_STAT_BY_MODEL["nfl_live_prop"]
    assert by_market[rap.MARKET] == "carries"
    # The old picks must still grade on the stat they were written against.
    assert by_market["player_pass_attempts"] == "attempts"


def test_the_book_move_guard_covers_the_new_market():
    """A market absent from SETTLED_TOL falls back to 0.0, where any juice
    wobble counts as the book moving and the settled-state rule never lets a
    bet through -- a model that silently never fires."""
    from live_model.config import BOOK_MOVE_MAX, SETTLED_TOL
    assert SETTLED_TOL.get(rap.MARKET) == 0.5
    assert BOOK_MOVE_MAX.get(rap.MARKET) is not None
