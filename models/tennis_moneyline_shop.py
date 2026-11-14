"""Tennis match winner: the decidable books' prices against Pinnacle's fair
price at the same moment. One rule, two models: `atp_moneyline_shop` (men's
tour) and `wta_moneyline_shop` (women's tour).

The decision code, shared by the replay over the bought history
(scripts/tennis_moneyline_replay.py) and the live card, so the backtest runs
what the live path runs. The research is in docs/sports/tennis.md
("Match winner, round 1").

FROZEN 2026-11-14 before the replay at the live decision time was read:
  reference   Pinnacle's two prices standing at the same snapshot as the
              decidable quotes, de-vigged by the power method (each implied
              chance raised to the one power that makes the pair sum to 1).
              The multiplicative de-vig handed longshots about 2 points too
              much on 20,822 Pinnacle pairs at the close; the power de-vig is
              within about 1.5 points in every bin
  EV          p x decimal - 1, plus the deciding book's retirement term: a
              book that voids the bet on the player who retires after set one
              (DraftKings) gives back the stake on our side's retirement, +r;
              a book that voids every bet on a retirement (Caesars, and the
              books whose rule we have not read) also takes away our win when
              the other player retires, +r - r x (decimal - 1); a book that
              grades the retiring player a loss (FanDuel, BetMGM, Pinnacle)
              adds nothing. r is the per-side chance of a retirement after set
              one, by tour and best of, read off the archive's 2015-2019 tour
              matches, before any priced season
  bet         0.02 <= EV < 0.05 at a price of -500 or longer; above 0.05 the
              quote is more often an error than an edge (the cut grid falls
              away there)
  one bet     per match: the best EV across the decidable books and both sides
"""
from __future__ import annotations

from dataclasses import dataclass

from models import tennis_common as tc

MODEL_IDS = {"ATP": "atp_moneyline_shop", "WTA": "wta_moneyline_shop"}

DECIDABLE = ("draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics",
             "betrivers", "hardrockbet")
REFERENCE = "pinnacle"

EV_MIN = 0.02
EV_MAX = 0.05
PRICE_FLOOR = -500

# Per-side chance of a retirement after the first set, archive tour-level
# matches 2015-2019, walkovers out (scripts/tennis_shop_study.retire_rates,
# run 2026-11-14).
RETIRE_RATE = {("ATP", 3): 0.0107, ("ATP", 5): 0.0191, ("WTA", 3): 0.0134}

# The feed's men's Grand Slam keys: best of five sets.
BEST_OF_FIVE_KEYS = frozenset({
    "tennis_atp_aus_open_singles", "tennis_atp_french_open",
    "tennis_atp_wimbledon", "tennis_atp_us_open",
})


def tour_of(sport_key: str) -> str | None:
    if sport_key.startswith("tennis_atp_"):
        return "ATP"
    if sport_key.startswith("tennis_wta_"):
        return "WTA"
    return None


def best_of(sport_key: str) -> int:
    return 5 if sport_key in BEST_OF_FIVE_KEYS else 3


def power_devig(price_a: float, price_b: float) -> tuple[float, float]:
    """Power de-vig of a two-way American pair: (ia**k, ib**k) with k such
    that they sum to 1, found by bisection."""
    ia, ib = tc.implied(price_a), tc.implied(price_b)
    lo, hi = 0.3, 3.0
    for _ in range(60):
        k = (lo + hi) / 2
        if ia ** k + ib ** k > 1.0:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2
    return ia ** k, ib ** k


def retirement_term(book: str, rate: float, decimal: float) -> float:
    rule = tc.MONEYLINE_RULE.get(book, tc.DEFAULT_MONEYLINE_RULE)
    if rule == tc.RULE_RETIREE_VOID:
        return rate
    if rule == tc.RULE_FULL_MATCH:
        return rate - rate * (decimal - 1)
    return 0.0


@dataclass(frozen=True)
class Quote:
    book: str
    price_a: int
    price_b: int


@dataclass(frozen=True)
class Choice:
    """The best side and book for one match at one moment. `bet` is whether it
    clears the rule; `reason` says why not when it does not."""
    side: str            # "a" (the feed's home player) or "b"
    book: str
    price: int
    p_ref: float         # Pinnacle's power-de-vigged chance for the side
    ev: float
    bet: bool
    reason: str


def decide(quotes: list[Quote], ref: Quote | None, sport_key: str, *,
           ev_min: float = EV_MIN, ev_max: float = EV_MAX,
           price_floor: int = PRICE_FLOOR) -> Choice | None:
    """The one decision for a match from the quotes standing at one moment:
    the best EV quote (book and side) below ev_max at price_floor or longer,
    a bet when its EV is at least ev_min. None when there is nothing to price
    (a tour this model does not cover, or no reference pair); a Choice with
    bet False and its reason otherwise."""
    tour = tour_of(sport_key)
    if tour is None or ref is None:
        return None
    rate = RETIRE_RATE[(tour, best_of(sport_key))]
    pa, pb = power_devig(ref.price_a, ref.price_b)
    best, seen = None, False
    for q in quotes:
        if q.book not in DECIDABLE:
            continue
        seen = True
        for side, price, p in (("a", q.price_a, pa), ("b", q.price_b, pb)):
            d = tc.american_to_decimal(price)
            ev = p * d - 1 + retirement_term(q.book, rate, d)
            if price < price_floor or ev >= ev_max:
                continue
            if best is None or ev > best[4]:
                best = (side, q.book, int(price), p, ev)
    if best is None:
        return Choice("", "", 0, 0.0, 0.0, False,
                      "no_decidable_quote" if not seen else "no_quote_in_range")
    side, book, price, p, ev = best
    bet = ev >= ev_min
    return Choice(side, book, price, p, ev, bet, "" if bet else "below_ev_min")
