"""Worked CLV for three production picks, from the snapshots stored for them.

3114189  Colton Dach Under 1.5 shots, DraftKings −120.
         DK close Under −145 / Over +105. Pinnacle close Under −142 / Over +107.
         Stored under the old both-sides de-vig: +4.36pp. The same-book
         primary is +8.50% / +4.64pp. Pinnacle power de-vig (the stored
         market edge) is +0.82pp / +1.51%. The audit's +0.30pp is the
         multiplicative close-only figure; power is the method, and both
         are far from +4.36.

2387645  MIA +1.5 at Rebet −132 (away). Rebet close away −133 / home +102,
         spread −1.5. Pinnacle close away −125 / home +113.
         Stored +1.10 under the old method. The market edge flips sign:
         Pinnacle's fair close is a worse price than −132.

3114194  Vince Dunn Under 0.5 assists, DraftKings −160.
         DK close Under −160 / Over +115. Pinnacle close Under −160 / Over +120.
         Primary is 0 (the book we bet did not move). Market edge is negative:
         the fair close is shorter than the juiced −160 we took. Stored +0.56
         because the old method de-vigged the bet as well.
"""
from __future__ import annotations

import pytest

from tracking.clv_math import DEVIG_POWER, market_edge_clv, same_book_clv


def test_3114189_same_book_primary_and_pinnacle_market_edge():
    pct, pp = same_book_clv(-120, -145)
    assert pct == pytest.approx(8.50, abs=0.02)
    assert pp == pytest.approx(4.64, abs=0.02)
    assert pct > 0  # −120 beat DraftKings' own −145

    m_pct, m_pp, method = market_edge_clv(-120, -142, [107], book="pinnacle")
    assert method == DEVIG_POWER
    assert m_pp == pytest.approx(0.82, abs=0.02)
    assert m_pct == pytest.approx(1.51, abs=0.02)
    assert m_pp < 4.36


def test_2387645_market_edge_flips_sign_against_the_stored_plus():
    pct, pp = same_book_clv(-132, -133)
    assert pct > 0 and pp > 0  # −132 is a slightly better price than −133
    assert pct == pytest.approx(0.33, abs=0.02)

    m_pct, m_pp, method = market_edge_clv(-132, -125, [113], book="pinnacle")
    assert method == DEVIG_POWER
    # Stored no_vig number was +1.10. Pinnacle's fair close is the other way.
    assert m_pp < 0
    assert m_pct < 0
    assert m_pp != pytest.approx(1.10, abs=0.2)


def test_3114194_matched_price_is_zero_and_the_fair_close_is_worse():
    assert same_book_clv(-160, -160) == (0.0, 0.0)
    m_pct, m_pp, method = market_edge_clv(-160, -160, [120], book="pinnacle")
    assert method == DEVIG_POWER
    # Stored +0.56 de-vigged the −160 we took. The fair close is below that
    # raw implied, so the market edge is negative.
    assert m_pp < 0
    assert m_pct < 0
    assert m_pp != pytest.approx(0.56, abs=0.2)
