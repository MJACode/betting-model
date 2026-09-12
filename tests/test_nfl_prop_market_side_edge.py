"""The market-relative rule may hold the two sides to different edge floors.

WHY (2026-09-12). NFL prop markets carry a measured OVER-LEAN: across 27,976
propositions 2023-25, graded at the best bettable price with no model consulted,
blind unders return -1.3% against blind overs at -7.9%
(`scripts/nfl_prop_over_lean.py`), and the gap survives at a FLAT price, so it
is a lean in the LINE rather than an artifact of shopping.

That predicts -- before any split of the rule's own record -- that an over bet
needs a bigger disagreement than an under bet to be worth the same. It does:
at the shipped 5pp cut `nfl_prop_market`'s unders return +12.36% (CI +7.2,
+17.5, all three seasons positive) and its overs +4.11% (CI spanning zero),
and the over curve climbs monotonically with the cut (5pp +4.1%, 6pp +15.8%,
7pp +20.5%) while the under curve is flat (+12.4 / +13.5 / +12.2).

SO THE FLOOR IS PER SIDE, and these tests pin the three properties that makes
safe:

  1. it TIGHTENS, never loosens -- a per-side floor below the base cut cannot
     let a bet through that the base cut rejects, so raising --min-edge always
     narrows the card no matter what the side map says;
  2. it is OPT-IN -- the shared `market_relative.find_bets` behaves exactly as
     before when no side map is passed, so the WNBA, MLB and NCAAF ports of the
     same rule are untouched. CLAUDE.md §1b: mechanics are shared, CUTS are
     measured per model and never copied across;
  3. NFL's own numbers live in config, so the cut is config-canonical like
     every other threshold in this repo.
"""
from __future__ import annotations

import config
import models.nfl_prop_market as mk
from models.market_relative import find_bets as generic_find_bets

SHARP = "pinnacle"
SOFT = ("draftkings",)


def _quotes(line: float = 4.5):
    """One proposition, priced so the soft book disagrees with the sharp book
    on BOTH sides -- so a side filter is the only thing that can separate them."""
    return {
        ("G1", "player one", "player_receptions", SHARP): {
            "line": line, "over_price": -140, "under_price": 115},
        ("G1", "player one", "player_receptions", "draftkings"): {
            "line": line, "over_price": 125, "under_price": -160},
    }


def _edges(quotes) -> dict[str, float]:
    bets, _ = generic_find_bets(quotes, SHARP, min_edge=-1.0, soft_books=SOFT)
    return {b.side: b.edge for b in bets}


def test_a_side_map_tightens_only_the_side_it_names():
    q = _quotes()
    e = _edges(q)
    assert set(e) == {"over", "under"}, e
    base = min(e.values()) - 0.001
    over_only = max(e["over"], base) + 0.001

    both, _ = generic_find_bets(q, SHARP, min_edge=base, soft_books=SOFT)
    assert {b.side for b in both} == {"over", "under"}

    tightened, _ = generic_find_bets(
        q, SHARP, min_edge=base, soft_books=SOFT,
        min_edge_by_side={"over": over_only})
    assert {b.side for b in tightened} == {"under"}, [b.side for b in tightened]


def test_the_side_map_can_never_loosen_the_base_cut():
    """A floor below --min-edge must not resurrect a bet the base cut rejected.

    Without this the flag is a footgun: someone raising the cut to sweep a
    tighter grid would silently keep every over at the old number.
    """
    q = _quotes()
    e = _edges(q)
    above_everything = max(e.values()) + 0.05
    out, _ = generic_find_bets(q, SHARP, min_edge=above_everything, soft_books=SOFT,
                               min_edge_by_side={"over": 0.0, "under": 0.0})
    assert out == []


def test_the_shared_helper_is_unchanged_when_no_side_map_is_given():
    """The WNBA / MLB / NCAAF ports call the same function and must not move."""
    q = _quotes()
    before, d0 = generic_find_bets(q, SHARP, min_edge=0.01, soft_books=SOFT)
    after, d1 = generic_find_bets(q, SHARP, min_edge=0.01, soft_books=SOFT,
                                  min_edge_by_side=None)
    assert [(b.side, b.edge) for b in before] == [(b.side, b.edge) for b in after]
    assert d0 == d1


def test_the_nfl_binding_passes_the_side_map_through():
    q = _quotes()
    e = _edges(q)
    base = min(e.values()) - 0.001
    over_only = max(e["over"], base) + 0.001
    out, _ = mk.find_bets(q, min_edge=base, soft_books=SOFT,
                          min_edge_by_side={"over": over_only})
    assert {b.side for b in out} == {"under"}, [b.side for b in out]


def test_config_carries_the_nfl_side_cut_and_the_over_is_the_stricter_one():
    side = config.NFL_PROP_MARKET_SIDE_EDGE
    assert set(side) == {"over", "under"}
    assert side["under"] == config.MODEL_EDGE_THRESHOLDS["nfl_prop_market"], (
        "the under side keeps the pre-committed 5pp cut")
    assert side["over"] > side["under"], (
        "the over side is the one the measured over-lean says must be stricter")
