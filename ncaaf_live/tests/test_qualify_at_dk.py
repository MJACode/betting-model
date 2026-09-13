"""Qualify at the price the cut was swept on; bet at the best book.

2026-09-12, mike: *"need less volume as I said, figure out a better approach"*
and, standing, *"best book always"*.

Both NCAAF live models' `min_edge` / `min_ev` were swept on the 2025 replay,
which carries DraftKings in-play history only. Production decides at the best
of thirteen books, and that price is a mean 6.21pp cheaper than DK for
ncaaf_live_win_prob (median 5.23pp; 12 of 16 of this season's BETs were decided
away from DK) and 1.54pp for ncaaf_live_total. Edge is `p - implied`, so a
cheaper implied inflates the edge one-for-one: a 0.10 floor swept on DK is
worth about 0.04 against a best-of-13 price.

These pin the split: the GATE reads DraftKings, the BET is still placed and
recorded at the best quote. Getting that backwards either loosens every floor
by the shop's own margin (the defect) or throws away the better price (which
the standing instruction forbids).
"""
from __future__ import annotations

from pathlib import Path

from ncaaf_live import serve


def test_the_gate_reads_the_draftkings_numbers():
    """Source tripwire: `price()` must pass the DK edge and DK price into
    `_decide`, not the decision-price versions."""
    src = Path(serve.__file__).read_text(encoding="utf-8")
    body = src.split("def price(")[1].split("\n    @")[0]
    assert 'self._decide(p, edge, min_prob, min_edge, c["dk_odds"]' in body, (
        "the gate is no longer reading the DraftKings edge/price -- every floor "
        "is then loosened by whatever the shop saves")
    assert "d_edge, min_prob, min_edge, d_price" not in body


def test_the_bet_is_still_recorded_at_the_best_price():
    """The standing instruction. The decision_* columns and the stake must
    still come from the best bettable quote -- this change moves the GATE, not
    the price."""
    src = Path(serve.__file__).read_text(encoding="utf-8")
    body = src.split("def price(")[1].split("\n    @")[0]
    assert "_deciding(" in body, "the best-price lookup was removed"
    assert "_price_fields(d_book, d_price, d_implied, d_edge" in body, (
        "the pick no longer records the best bettable price")
    assert "self._kelly(p, d_implied, pick)" in body, (
        "the stake is no longer sized at the decision price")


def test_a_cheaper_book_no_longer_buys_its_way_past_the_floor():
    """The arithmetic the change exists for: DK implied 0.60, best book 0.54,
    model 0.68. Decision edge 0.14 clears a 0.10 floor; DK edge 0.08 does not."""
    d = serve.LiveEngine._decide
    # gate on the DK numbers -> declined
    assert d(0.68, 0.08, 0.62, 0.10, -150.0, None) is None
    # gate on the shopped numbers -> would have fired
    assert d(0.68, 0.14, 0.62, 0.10, -117.0, None) == "BET"


def test_the_stale_line_cap_still_judges_the_dk_edge():
    """It always did, for the same reason -- a cheaper price adds edge that is
    the price difference, not a stale quote. This change puts the floors on the
    same footing, so the cap's own contract must not have moved."""
    src = Path(serve.__file__).read_text(encoding="utf-8")
    assert "cap_edge=edge" in src.split("def price(")[1].split("\n    @")[0]
