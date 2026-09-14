"""Honest CLV arithmetic: no-vig two-way close vs the price you bet.

Industry standard (OddsShopper, 2026): convert BOTH sides of the closing
two-way market to implied probability, divide each by the sum (multiplicative
/ proportional de-vig), then

    clv_pct = (fair_close_p(side) − fair_bet_p(side)) × 100

Positive = you bought cheaper than the market's true close. The posted close
still has hold in it and flatters or distorts the number; vig widening at
close is the trap that makes raw "cents" look like edge when the fair number
did not move.

Worked OddsShopper example — bet Dodgers −130, close −150 / +135:

    Dodgers raw close  150/250 = 0.60
    Padres  raw close  100/235 ≈ 0.425532
    sum                  = 1.025532  (2.55% vig)
    fair Dodgers         = 0.60 / 1.025532 ≈ 0.58505  (≈ −141)
    bet implied (raw)    = 130/230 ≈ 0.565217
    clv_pct              = (0.58505 − 0.565217) × 100 ≈ +1.98 pp

OddsShopper's worked example only shows one bet price, so the bet stays raw
implied. When the locked two-way is on the snapshot, both sides are de-vigged
and vig widening (−110/−110 → −115/−115) is exactly 0 — not the +1.11 pp raw
cents invent.

Raw close would have reported (0.60 − 0.565217) × 100 ≈ +3.48 pp. The no-vig
figure is the honest one.

Prediction-market prices (Kalshi, Polymarket) are already no-vig: do not
de-vig them again. One-way sportsbook quotes have no second side to remove
hold against, so the fair close is refused rather than invented.

This module is the arithmetic only. The capture path (tracking/paper_tracker)
owns which book is the close, the same-line guard, and the in-play bound.
Full contract: docs/clv.md.
"""
from __future__ import annotations

from models.market_relative import implied

# Exchanges, not sportsbooks. Their two sides already sum to ~1; running the
# sportsbook de-vig on them would invent hold that is not there.
ZERO_VIG_BOOKS = frozenset({"kalshi", "polymarket"})

# Circa is not in The Odds API feed we store. Pinnacle is the sharp close we
# actually have. Callers may pass config.SHARP_BOOKMAKERS instead.
DEFAULT_SHARP_CLOSE_BOOKS = ("pinnacle",)

# Rows captured before 2026-09-14 used raw one-sided implied on the pick's
# book. Pedigree must not average those with the no-vig number.
CLV_METHOD_RAW_LEGACY = "raw_one_sided"
CLV_METHOD_NO_VIG = "no_vig"
CLV_METHOD_ZERO_VIG = "zero_vig"
CLV_METHOD_ONE_WAY = "raw_one_way"

# Published avg_clv_pct / beat-rate pedigree. Legacy raw and one-way juice
# stay on the pick row for pick-detail but do not enter the model average.
PEDIGREE_CLV_METHODS = frozenset({CLV_METHOD_NO_VIG, CLV_METHOD_ZERO_VIG})


def close_book_candidates(
    pick_book: str | None,
    sharp_books: tuple[str, ...] | list[str] = DEFAULT_SHARP_CLOSE_BOOKS,
) -> list[str]:
    """Sharp close first, then the book the pick was priced at.

    Grading DK-in vs DK-close is half-circular. A missing sharp snapshot is
    not a missing capability: the pick's own book is the fallback, never an
    unbounded "latest" quote after first pitch.
    """
    out: list[str] = []
    for book in sharp_books:
        b = (book or "").strip().lower()
        if b and b not in out:
            out.append(b)
    pick = (pick_book or "draftkings").strip().lower() or "draftkings"
    if pick not in out:
        out.append(pick)
    return out


def implied_to_american(p: float) -> int | None:
    """Fair probability → American odds, nearest integer. None if not a prob."""
    if p is None:
        return None
    x = float(p)
    if x <= 0.0 or x >= 1.0:
        return None
    if x >= 0.5:
        return -int(round(100.0 * x / (1.0 - x)))
    return int(round(100.0 * (1.0 - x) / x))


def fair_close_probability(
    side_price,
    other_prices,
    *,
    book: str | None = None,
) -> tuple[float | None, str]:
    """No-vig probability of `side_price` at close, plus the method stamp.

    `other_prices` is the rest of the market (one price for two-way, two for
    a 3-way). Missing/NaN others → one-way: we do not de-vig, and we do not
    pretend the raw juice is fair — method `raw_one_way`, probability is the
    raw implied so pick-detail still has a number, pedigree excludes it.

    Zero-vig books skip de-vig even when both sides are present.
    """
    side_ip = implied(side_price)
    if side_ip is None:
        return None, CLV_METHOD_ONE_WAY
    book_key = (book or "").strip().lower()
    if book_key in ZERO_VIG_BOOKS:
        return side_ip, CLV_METHOD_ZERO_VIG

    others = list(other_prices or [])
    other_ips = [implied(p) for p in others]
    if not other_ips or any(p is None for p in other_ips):
        return side_ip, CLV_METHOD_ONE_WAY

    total = side_ip + sum(other_ips)
    if not total:
        return None, CLV_METHOD_ONE_WAY
    return side_ip / total, CLV_METHOD_NO_VIG


def price_clv_pct(
    bet_american,
    side_close,
    other_prices,
    *,
    book: str | None = None,
    bet_other_prices=None,
    bet_book: str | None = None,
) -> tuple[float | None, str]:
    """Probability-point CLV: (fair_close_p − fair_bet_p) × 100.

    `book` is the close; `bet_book` is the book we bet (defaults to the close
    book). `bet_other_prices` is the rest of the two-way (or 3-way) at LOCK.
    Missing lock others → raw bet implied, matching OddsShopper's Dodgers
    example. Present lock others → both markets are de-vigged, so vig
    widening grades as 0.

    Same-line only is the caller's job. This function will happily difference
    two prices on different numbers; do not call it when the line moved.

    The returned method stamps the CLOSE, which is what pedigree filters on.
    """
    fair, method = fair_close_probability(side_close, other_prices, book=book)
    bet_ip, _bet_method = fair_close_probability(
        bet_american,
        bet_other_prices or [],
        book=bet_book if bet_book is not None else book,
    )
    if bet_ip is None or fair is None:
        return None, method
    return round((fair - bet_ip) * 100, 2), method


def other_side_prices(closing: dict, pick_side: str) -> list:
    """The other American(s) in a closing snapshot for de-vig.

    Totals/props: the opposite over/under. H2H: the opposite team, plus draw
    when the snapshot is 3-way. Missing keys become None and fair_close then
    stamps the market one-way.
    """
    if not closing:
        return []
    if pick_side == "over":
        return [closing.get("under_price")]
    if pick_side == "under":
        return [closing.get("over_price")]
    if pick_side == "home":
        others = [closing.get("away_price")]
        if closing.get("draw_price") is not None:
            others.append(closing.get("draw_price"))
        return others
    if pick_side == "away":
        others = [closing.get("home_price")]
        if closing.get("draw_price") is not None:
            others.append(closing.get("draw_price"))
        return others
    if pick_side == "draw":
        return [closing.get("home_price"), closing.get("away_price")]
    return []
