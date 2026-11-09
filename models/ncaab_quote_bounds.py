"""
The plausible range of an NCAAB quote, and the largest edge a real NCAAB price
gives: the one guard every live NCAAB card reads against a feed typo.

WHY. On 2026-11-03 the odds feed was found holding a DraftKings full-game total
of 1465.0 (NCAAB_2023-03-17_providence_kentucky, stamped 2023-03-12 23:16Z and
stored by the 2026-11-03 backfill; that book's next row is 146.5). The totals
card skipped only a missing line or price, never capped the edge, and the
model's EV floor is only a floor, so a live 1465.0 would have priced the under
near 100% and been written as a bet. None had been bet (ncaab_total_decisions:
140 rows, every total_line 131.5-171.5).

THE RULE. A quote is a data error when its line is outside its market's
LINE_RANGE, or either price is beyond +/-MAX_ABS_PRICE. A data-error quote is
dropped BEFORE any consensus, flag or price reads it, so it cannot move a
median either, and each card logs it by game, book and value and counts it on
its run's diagnostic line. A book's dropped quote is NOT replaced by that
book's older row: its real number at that moment is unknown, so the book has
no quote at that moment (the totals card's first post, below, is the one
exception). What then happens to the game is each card's own
rule:
  * the totals card (scripts/ncaab_total_card.py) prices DraftKings' first
    posted total, which is the first row INSIDE the range (a typo row is
    skipped, the research's rule, so here the next row does stand in); a
    standing total or a first post's price that is a data error makes the
    game wait (status out_of_range, looked at again on the next run);
  * the 15:00 UTC spread and moneyline cards and the two first-half cards
    decide on the books that are left, the dropped quote listed in the
    decision row; a game left with no quote is decided with none.
A missing line or price is not a data error here, nor a price inside
-100..+100: each model's own checks handle those, as before (the moneyline
model's price check keeps such a spread's line in its sign-error median, on
purpose), and the edge cap below catches what they would price.

THE EDGE CAP. A best edge above its model's EDGE_CAP is a data error too, not
a bet: no bet is written, it is logged, and the run fails (each card's
CardIncomplete), so the failure alerter reports it. The totals card holds the game for its next
hour, as it holds a missing box; the cards with one decision moment record the
game as edge_cap with no bet.

THE RANGES, measured 2026-11-03 on the stored pre-game rows of the eight
bettable books (models/ncaab_book_quotes.BOOKS), every season 2021-2026 (the
research copy of `odds` the builds replay, 2026-10-26..30) and the 2026-27
season so far (`odds`, rows stamped at or before the tip):
  full-game total   2021-26: 887,723 rows, 109.5 at the 0.001% quantile, max
                    194.0; one BetMGM row of 42.0 at -10000/+3300 (2020-12-20,
                    milwaukee_green-bay) is the only one under 109.5. 2026-27:
                    125.5-172.5.                       -> 90 to 220
  full-game spread  2021-26: 890,454 rows, -47.5 to +34.5. 2026-27: -44.5 to
                    +11.5 (a -78.5 is stored after a tip, never before).
                                                        -> -60 to +60
  first-half total   2023-26 purchases: 43.5-94.5 over every bought time
                    (52.5-94.5 an hour before tip). 2026-27: 64.5-82.5.
                                                        -> 40 to 120
  first-half spread 2023-26 purchase: -27.5 to +20.5. 2026-27: -18.5 to +5.5.
                                                        -> -35 to +35
  prices            full-game spreads -375..+285; totals -10000..+3300 (the
                    42.0 row; otherwise -4500..+400); moneylines down to
                    -100000 (975 prices at exactly -100000, kept) and up to
                    +10000; first halves -286..+188, first-half moneylines
                    down to -100000. Beyond +/-100000: none at a bettable book
                    in 2021-26, one Pinnacle moneyline (-304573,
                    florida-a-m_purdue 2022-12-29); 2026-27 one Hard Rock
                    moneyline of -200000/+4000 (stetson_clemson, 2026-11-02
                    14:34Z), now dropped.
                                                        -> |price| <= 100000
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

# market -> (lowest, highest) plausible line; spreads are the HOME number.
LINE_RANGE: dict[str, tuple[float, float]] = {
    "totals": (90.0, 220.0),
    "spreads": (-60.0, 60.0),
    "totals_h1": (40.0, 120.0),
    "spreads_h1": (-35.0, 35.0),
}
# Markets with no line: only the prices are checked.
PRICE_ONLY = ("h2h", "h2h_h1")
MAX_ABS_PRICE = 100_000.0       # beyond +/-100000 is a typo; -100000 itself is real

# Each model's cap sits well above the largest edge its own replay produced
# (scripts/ncaab_*_build.py on the research copy, measured 2026-11-03):
#   ncaab_total_blend          0.1606  (2022-2026, 2,436 bets at the 0.04 cut, at
#                              DraftKings' first posted total)
#   ncaab_spread_market        0.1500  (2021-2026, 613 bets at the 0.03 cut)
#   ncaab_moneyline_own_spread 0.0594  (2021-2026, 914 bets at the 0.01 cut)
#   ncaab_moneyline_first_post 0.2416  (2021-2026, 353 bets at the 0.015 cut: BetMGM's
#                              +340 first post on central-connecticut_umass-lowell,
#                              2021-11-17), also the largest of all 97,429 first
#                              posts priced with 3+ other books up, so its cap
#                              sits above it at 0.40 rather than at 0.25
#   ncaab_first_half_total     0.3381  (2023-24 to 2025-26, 17,142 decided games),
#                              then 0.1508: the 0.3381 is FanDuel under 79.5 when
#                              every other book had 68-69, so its cap sits above it
#   ncaab_first_half_spread    0.4633  (2023-24 to 2025-26, 17,206 decided games),
#                              then 0.4108 and 0.2583: all three at a book whose
#                              first-half line no other book had (BetMGM +12.5
#                              against -12.5, DraftKings -14.5 against -9.5,
#                              FanDuel +10.5 against +5), so its cap sits above
#                              them rather than at 0.25, which would remove
#                              three bets from the graded evidence.
EDGE_CAP: dict[str, float] = {
    "ncaab_total_blend": 0.25,
    "ncaab_spread_market": 0.25,
    "ncaab_moneyline_own_spread": 0.25,
    "ncaab_moneyline_first_post": 0.40,
    "ncaab_first_half_spread": 0.60,
    "ncaab_first_half_total": 0.50,
    # The in-play rules (2026-11-07): the largest edge over 61,019 graded
    # decisions was 0.453 (99.9th percentile 0.266), so 0.50 is above every
    # graded bet. A decision over it is a data error: declined, never bet.
    "ncaab_live_spread_h1": 0.50,
    "ncaab_live_spread_h2": 0.50,
    "ncaab_live_total_h2": 0.50,
}


def _known(market: str) -> None:
    if market not in LINE_RANGE and market not in PRICE_ONLY:
        raise ValueError(f"no plausible range for market {market!r}")


def _fmt(x: float) -> str:
    return f"{x:+g}" if abs(x) < 1e6 else f"{x:+.6g}"


def problem(market: str, line=None, prices=()) -> str | None:
    """Why one quote is a data error, or None. A missing line or price is not
    one (the loaders' own checks drop those)."""
    _known(market)
    rng = LINE_RANGE.get(market)
    if rng is not None and line is not None:
        v = float(line)
        if math.isfinite(v) and not rng[0] <= v <= rng[1]:
            return f"line {v:g} outside {rng[0]:g} to {rng[1]:g}"
    for p in prices:
        if p is None:
            continue
        v = float(p)
        if not math.isfinite(v):
            continue
        if abs(v) > MAX_ABS_PRICE:
            return f"price {_fmt(v)} beyond +/-{MAX_ABS_PRICE:.0f}"
    return None


def split(q: pd.DataFrame, market: str, line_col: str | None = "line",
          price_cols=("p1", "p2")) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(the quotes that are not data errors, the ones that are). The second
    carries `market` and `why`. Row order and columns are kept; nothing is
    dropped for a missing value."""
    _known(market)
    bad = np.zeros(len(q), bool)
    why = np.full(len(q), None, dtype=object)
    rng = LINE_RANGE.get(market)
    if rng is not None and line_col is not None and line_col in q.columns:
        v = pd.to_numeric(q[line_col], errors="coerce").to_numpy(float)
        out = np.isfinite(v) & ((v < rng[0]) | (v > rng[1]))
        why[out & ~bad] = [f"line {x:g} outside {rng[0]:g} to {rng[1]:g}" for x in v[out & ~bad]]
        bad |= out
    for c in price_cols:
        if c not in q.columns:
            continue
        p = pd.to_numeric(q[c], errors="coerce").to_numpy(float)
        hi = np.isfinite(p) & (np.abs(p) > MAX_ABS_PRICE)
        new = hi & ~bad
        why[new] = [f"price {_fmt(x)} beyond +/-{MAX_ABS_PRICE:.0f}" for x in p[new]]
        bad |= hi
    kept = q[~bad]
    dropped = q[bad].assign(market=market, why=why[bad])
    return kept, dropped


def describe(dropped: pd.DataFrame, line_col: str | None = "line", price_cols=("p1", "p2"),
             book_col: str = "bookmaker") -> list[str]:
    """One line per dropped quote: game, book, market, line, prices and why."""
    out = []
    for r in dropped.to_dict("records"):
        parts = [str(r.get("game_id")), str(r.get(book_col)), str(r.get("market"))]
        if line_col is not None and r.get(line_col) is not None and not pd.isna(r.get(line_col)):
            parts.append(f"line {float(r[line_col]):g}")
        ps = [r.get(c) for c in price_cols]
        if ps:
            parts.append("prices " + "/".join("-" if v is None or pd.isna(v) else _fmt(float(v))
                                              for v in ps))
        out.append(" ".join(parts) + f": {r.get('why')}")
    return out


def edge_problem(edge, model_id: str) -> str | None:
    """Why a model's edge is a data error, or None. A model with no cap here
    is refused outright, so a new NCAAB card cannot skip choosing one."""
    cap = EDGE_CAP[model_id]
    if edge is None:
        return None
    e = float(edge)
    if math.isfinite(e) and e > cap:
        return f"edge {e:+.4f} above the data-error cap {cap:g}"
    return None
