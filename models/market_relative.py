"""
Market-relative selection: de-vig a market maker, bet the soft book's outlier.

WHY THIS IS SHARED AND NOT COPIED PER SPORT
-------------------------------------------
This is the one construction in this repo with a blind-tested positive result:
models/nfl_prop_market measured +10.22% train and +10.76% blind over 954 bets,
on a pre-committed 5pp threshold. It was written NFL-first, and the edge maths
in it is not NFL-specific at all -- it is de-vig, compare like-for-like, take
the difference.

MLB props needed the same construction in 2026-08-31, and copying the file is
how this repo has accumulated work before (CLAUDE.md 1b: the live price log
existed for MLB and not NCAAF; the first-signal lock for NFL and nowhere else,
each found only when it produced a visible failure in the sport that lacked
it). A bug fixed in one copy of an edge calculation and not the other is the
same failure with money attached. So the maths lives here once and both sports
call it.

WHAT THE CALLER OWNS: loading quotes, and knowing which of its markets the
sharp book actually prices. What this module owns: the arithmetic.

THE ONE THING THAT MAKES IT HONEST -- carried over verbatim in intent from the
NFL module, because it is the trap that matters. The comparison must be
like-for-like on the LINE. A sharp book at 5.5 and a soft book at 6.5 are
different propositions, and treating the price gap between them as an edge
manufactures one out of thin air. Only equal lines are compared, and the count
discarded for mismatch is REPORTED rather than hidden -- if most quotes are
dropped, the result is about coverage, not about edge.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketBet:
    game_id: str
    player: str
    market: str
    side: str            # "over" | "under"
    book: str            # the soft book being bet
    line: float
    price: float         # the soft book's American price on that side
    fair: float          # the sharp book's de-vigged probability for that side
    edge: float          # fair - the soft book's own de-vigged probability
    sharp_price: float   # what the sharp book asked for the same side


def implied(american) -> float | None:
    """American price -> implied probability, vig included."""
    if american is None:
        return None
    x = float(american)
    return (100.0 / (x + 100.0)) if x > 0 else (abs(x) / (abs(x) + 100.0))


def devig(over_price, under_price) -> tuple[float | None, float | None]:
    """Proportional de-vig. None for either side means the market is one-way."""
    o, u = implied(over_price), implied(under_price)
    if o is None or u is None:
        return None, None
    t = o + u
    return (o / t, u / t) if t else (None, None)


def find_bets(quotes: dict, sharp_book: str, min_edge: float = 0.02,
              soft_books: tuple[str, ...] | None = None
              ) -> tuple[list[MarketBet], dict]:
    """
    `quotes` is {(game_id, player, market, book): {line, over_price, under_price}}.

    Returns the qualifying bets and a diagnostic dict. The diagnostic is not
    decoration: `line_mismatch` counts soft quotes dropped for sitting on a
    different number than the sharp book, and if that is most of them then the
    result is about coverage rather than about edge.
    """
    diag = {"sharp_quotes": 0, "compared": 0, "line_mismatch": 0,
            "one_way": 0, "no_sharp": 0, "bets": 0}

    sharp = {k[:3]: v for k, v in quotes.items() if k[3] == sharp_book}
    diag["sharp_quotes"] = len(sharp)

    out: list[MarketBet] = []
    for (gid, player, market, book), q in quotes.items():
        if book == sharp_book:
            continue
        if soft_books and book not in soft_books:
            continue
        s = sharp.get((gid, player, market))
        if s is None:
            diag["no_sharp"] += 1
            continue
        # Like-for-like on the line, or it is not the same bet.
        if (s.get("line") is None or q.get("line") is None
                or float(s["line"]) != float(q["line"])):
            diag["line_mismatch"] += 1
            continue

        f_over, f_under = devig(s.get("over_price"), s.get("under_price"))
        b_over, b_under = devig(q.get("over_price"), q.get("under_price"))
        if f_over is None or b_over is None:
            diag["one_way"] += 1
            continue
        diag["compared"] += 1

        for side, fair, book_p, price, sharp_p in (
            ("over", f_over, b_over, q.get("over_price"), s.get("over_price")),
            ("under", f_under, b_under, q.get("under_price"), s.get("under_price")),
        ):
            if price is None:
                continue
            edge = fair - book_p
            if edge >= min_edge:
                out.append(MarketBet(gid, player, market, side, book,
                                     float(q["line"]), float(price), fair, edge,
                                     float(sharp_p)))
    diag["bets"] = len(out)
    return out, diag
