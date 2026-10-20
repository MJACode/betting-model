"""CLV arithmetic. Two numbers, never mixed.

PRIMARY — same-book raw price. The book the bet was taken at
(``clv_bet_book``), last pre-start snapshot, same side, same line. Neither
side is de-vigged.

    clv_pct = (taken_decimal / close_decimal − 1) × 100     # percent
    clv_pp  = (raw_close_implied − raw_taken_implied) × 100  # probability points

Beat = the price we took is better than that book's close (``clv_pct > 0``).
No snapshot at that book on that line → both are None. Another book is not
a substitute.

SECONDARY — market edge. Pinnacle's last pre-start snapshot only, power
de-vigged (3-way power when the close has a draw). The taken side stays raw.

    market_clv_pct = (taken_decimal × fair_close_prob − 1) × 100
    market_clv_pp  = (fair_close_prob − raw_taken_implied) × 100

No Pinnacle close, or a one-way quote with nothing to de-vig against → None.
The method stamp on the row is ``standard_v2``. The de-vig method is
``power`` / ``power_3way`` / ``zero_vig``, recorded separately.

Same-line is the caller's job: a moved number does not get a price CLV.
Full contract: docs/clv.md.
"""
from __future__ import annotations

from models.market_relative import implied

# Exchanges, not sportsbooks. A close read from one of these is already
# no-vig; power de-vig would invent hold.
ZERO_VIG_BOOKS = frozenset({"kalshi", "polymarket"})

# The sharp close we store. Circa is not in the feed. Callers may pass
# config.SHARP_BOOKMAKERS; the secondary metric never falls through to a
# soft book.
DEFAULT_SHARP_CLOSE_BOOKS = ("pinnacle",)

CLV_METHOD_STANDARD = "standard_v2"

# Pre-standard stamps. Kept so a row written under an older definition can
# be named, and so pedigree can refuse it. None of these is averaged.
CLV_METHOD_RAW_LEGACY = "raw_one_sided"
CLV_METHOD_NO_VIG = "no_vig"
CLV_METHOD_ZERO_VIG = "zero_vig"
CLV_METHOD_ONE_WAY = "raw_one_way"
CLV_METHOD_DK_GRADED_LEGACY = "graded_at_dk_legacy"

DEVIG_POWER = "power"
DEVIG_POWER_3WAY = "power_3way"

# Published averages. Old methods stay on the row until the recompute
# stamps standard_v2, and they do not enter the average while they wait.
PEDIGREE_CLV_METHODS = frozenset({CLV_METHOD_STANDARD})

# Bisection shared with the SQL recompute (clv_power_fair). Same bounds,
# same iteration count, so a row the migration writes matches this module.
_POWER_LO = 0.05
_POWER_HI = 12.0
_POWER_ITERS = 80


def close_book_candidates(
    pick_book: str | None = None,
    sharp_books: tuple[str, ...] | list[str] = DEFAULT_SHARP_CLOSE_BOOKS,
) -> list[str]:
    """Sharp books only. The pick's book is not a close for the market-edge
    number, and it is not a fallback when Pinnacle is missing.

    ``pick_book`` is accepted so older call sites keep parsing; it is not
    appended. The primary metric looks the bet book up on its own.
    """
    del pick_book
    out: list[str] = []
    for book in sharp_books:
        b = (book or "").strip().lower()
        if b and b not in out:
            out.append(b)
    return out


def american_to_decimal(american) -> float | None:
    """American → decimal odds. None when the price is missing or zero."""
    if american is None:
        return None
    try:
        o = float(american)
    except (TypeError, ValueError):
        return None
    if o != o or o == 0.0:  # NaN or a price that is not a price
        return None
    if o > 0:
        return 1.0 + o / 100.0
    return 1.0 + 100.0 / abs(o)


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


def _round_pct(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def same_book_clv(bet_american, close_american) -> tuple[float | None, float | None]:
    """Primary CLV. Raw vs raw. Returns ``(clv_pct, clv_pp)``.

    ``clv_pct`` is percent: ``(taken_decimal / close_decimal − 1) × 100``.
    ``clv_pp`` is probability points:
    ``(raw_close_implied − raw_taken_implied) × 100``.

    Positive = the close is a worse price than the one we took. Neither
    input is de-vigged. Missing either price → ``(None, None)``.
    """
    taken_p = implied(bet_american)
    close_p = implied(close_american)
    taken_d = american_to_decimal(bet_american)
    close_d = american_to_decimal(close_american)
    if taken_p is None or close_p is None or taken_d is None or close_d is None:
        return None, None
    if close_d == 0:
        return None, None
    pct = (taken_d / close_d - 1.0) * 100.0
    pp = (close_p - taken_p) * 100.0
    return _round_pct(pct), _round_pct(pp)


def power_fair(prices: list) -> list[float] | None:
    """Power de-vig. Solve ``Σ p_i^k = 1`` and return fair probabilities
    in the same order.

    Two prices or three. A missing price, a non-probability, or a single
    side returns None — a one-way quote is not given a made-up hold.
    """
    ips: list[float] = []
    for price in prices:
        p = implied(price)
        if p is None or p <= 0.0 or p >= 1.0:
            return None
        ips.append(p)
    if len(ips) < 2:
        return None
    # Already fair (an exchange, or a book that took no hold).
    if abs(sum(ips) - 1.0) < 1e-12:
        return ips
    lo, hi = _POWER_LO, _POWER_HI
    for _ in range(_POWER_ITERS):
        k = (lo + hi) / 2.0
        total = sum(p ** k for p in ips)
        if total > 1.0:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2.0
    powered = [p ** k for p in ips]
    scale = sum(powered)
    if not scale:
        return None
    return [v / scale for v in powered]


def market_edge_clv(
    bet_american,
    side_close,
    other_prices,
    *,
    book: str | None = None,
) -> tuple[float | None, float | None, str | None]:
    """Secondary CLV against a de-vigged close. Returns
    ``(market_clv_pct, market_clv_pp, devig_method)``.

    The taken side is raw. The close is power-de-vigged, or left raw when
    ``book`` is already no-vig. One-way closes return ``(None, None, None)``.
    """
    taken_p = implied(bet_american)
    taken_d = american_to_decimal(bet_american)
    if taken_p is None or taken_d is None:
        return None, None, None

    book_key = (book or "").strip().lower()
    others = [p for p in (other_prices or [])]
    if book_key in ZERO_VIG_BOOKS:
        fair = implied(side_close)
        method = CLV_METHOD_ZERO_VIG
    else:
        if any(p is None for p in others) or not others:
            return None, None, None
        fair_all = power_fair([side_close, *others])
        if not fair_all:
            return None, None, None
        fair = fair_all[0]
        method = DEVIG_POWER_3WAY if len(others) >= 2 else DEVIG_POWER
    if fair is None:
        return None, None, None
    pct = (taken_d * fair - 1.0) * 100.0
    pp = (fair - taken_p) * 100.0
    return _round_pct(pct), _round_pct(pp), method


def other_side_prices(closing: dict, pick_side: str) -> list:
    """The other American(s) in a closing snapshot, for the market-edge de-vig.

    Totals/props: the opposite over/under. H2H: the opposite team, plus draw
    when the snapshot is 3-way. Missing keys stay None so the caller can
    refuse a one-way de-vig.
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
