"""A ladder of strikes is an implied distribution. Read a fair price off it.

WHY THIS EXISTS. Every prop reference this repo has ever used quotes ONE number:
Pinnacle says over/under 249.5 and we de-vig the two prices into a fair
probability at 249.5 and nowhere else. That single-point view is the direct
cause of the biggest data loss in the whole prop programme -- `models/
nfl_prop_market` can only compare a sharp and a soft book when they quote the
SAME line, and 63,676 NFL propositions are discarded because they do not (65% of
the comparable board on NCAAF, `docs/nfl_prop_offset_evidence.md`).

Kalshi quotes differently. It lists a LADDER of strikes per player, each a
separate contract paying out if the stat clears it, e.g. Dak Prescott passing
yards on 2026-09-08:

    174.5  199.5  224.5  249.5  274.5  299.5  324.5  349.5
     .835   .785   .650   .510   .365   .225   .140   .095

That is a survival function, P(X > strike), sampled at eight points. Given it,
the fair probability at ANY line is an interpolation rather than a lookup, so a
soft book hanging 252.5 against a sharp 249.5 stops being a discarded row and
becomes a priced one.

TWO THINGS THIS IS NOT.

  * It is not a de-vig. There is no vig to remove: the ladder is a two-sided
    exchange order book, and the mid of a 1-2c spread is already a fair estimate.
    Proportional de-vigging is an ASSUMPTION about how a book distributes its
    margin; this replaces that assumption with a measurement. The spread is still
    a cost and is still gated on -- see MAX_SPREAD.
  * It is not validated. Kalshi's NFL prop markets are new: settled history
    reaches back only to 2026 preseason (measured 2026-09-08). Nothing here is
    wired into production scoring, and it must not be until it is graded on its
    own record the way §5c graded Pinnacle -- with a placebo. This module and its
    ingestor exist so that history starts accumulating now instead of when
    somebody next asks.

THE MONOTONICITY PROBLEM IS REAL AND IS HANDLED. A survival function cannot
increase, but quoted mids can: a thin rung goes stale, one side of the book
empties, and 274.5 prints above 249.5. Interpolating through that produces a
fair probability that is confidently wrong rather than obviously broken, so the
mids are projected onto the nearest non-increasing sequence (pool-adjacent
violators) before anything is read off them.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# A rung wider than this is treated as unpriced. Set from the real board rather
# than from taste, and the first value chosen (0.10) was wrong: receiving-yards
# ladders quote 1-2c, but Dak Prescott's passing-yards ladder on 2026-09-08 -- the
# very example this module is built around -- quotes 10-12c through its BODY, so
# 0.10 deleted the middle of the distribution and left the interpolator with a
# gap exactly where the line usually sits.
#
# 0.15 keeps that body. The genuinely uninformative rungs are excluded by the
# separate bid > 0 rule below: the deep tails print bid 0.00 against an ask of
# 0.06-0.11, which is not a wide market but a one-sided one.
#
# NOTE ON WHAT A WIDE SPREAD MEANS HERE. We are not trading these contracts, we
# are reading a fair value off them, so width is uncertainty rather than cost.
# That is why the bar is looser than it would be for execution -- and why the
# spread is retained on every rung, so a later grader can weight by it.
MAX_SPREAD = 0.15

# Fewer rungs than this is not a distribution, it is a couple of points. Three
# is the minimum that can bracket an interior line and still show a shape.
MIN_RUNGS = 3

# Logit is undefined at 0 and 1, and a settled-looking rung at 0.995 should not
# become infinite leverage on the interpolation.
_EPS = 1e-4


@dataclass(frozen=True)
class Rung:
    """One strike on the ladder. `strike` is the number the stat must EXCEED."""

    strike: float
    bid: float
    ask: float

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid


def _logit(p: float) -> float:
    p = min(max(p, _EPS), 1.0 - _EPS)
    return math.log(p / (1.0 - p))


def _expit(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _monotone(mids: list[float]) -> list[float]:
    """Nearest NON-INCREASING sequence, by pool-adjacent-violators.

    Isotonic regression rather than "drop the offenders": dropping throws away a
    real quote because its neighbour is stale, and which of the two is stale is
    exactly what we do not know. PAVA keeps every rung and moves the pair the
    least distance that restores the ordering, which is the minimum-assumption
    repair.
    """
    # Blocks of (sum, count) merged left-to-right whenever the running means
    # would ascend.
    blocks: list[list[float]] = []
    for m in mids:
        blocks.append([m, 1.0])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] < blocks[-1][0] / blocks[-1][1]:
            s, c = blocks.pop()
            blocks[-1][0] += s
            blocks[-1][1] += c
    out: list[float] = []
    for s, c in blocks:
        out.extend([s / c] * int(c))
    return out


class Ladder:
    """An implied survival function, read off a strike ladder.

    `p_over(line)` is the whole interface. It returns None rather than a guess
    whenever the ladder cannot honestly answer -- too few usable rungs, or a line
    outside the strikes actually quoted.
    """

    def __init__(self, rungs: list[Rung], max_spread: float = MAX_SPREAD,
                 min_rungs: int = MIN_RUNGS):
        # bid > 0 is the one-sided test and does more work than the width gate:
        # a 0.00 bid means nobody will buy at any price, so the "mid" is half an
        # ask and carries no market opinion at all.
        usable = [r for r in rungs
                  if r.bid > 0 and r.ask > 0
                  and r.spread <= max_spread and 0.0 <= r.mid <= 1.0]
        usable.sort(key=lambda r: r.strike)
        # A duplicated strike is a data error, not two opinions; keep the tighter.
        dedup: dict[float, Rung] = {}
        for r in usable:
            prev = dedup.get(r.strike)
            if prev is None or r.spread < prev.spread:
                dedup[r.strike] = r
        usable = [dedup[k] for k in sorted(dedup)]

        self.strikes = [r.strike for r in usable]
        self.raw_mids = [r.mid for r in usable]
        self.mids = _monotone(self.raw_mids) if usable else []
        self.rungs = usable
        self.min_rungs = min_rungs

    def __len__(self) -> int:
        return len(self.strikes)

    @property
    def usable(self) -> bool:
        return len(self.strikes) >= self.min_rungs

    @property
    def repaired(self) -> bool:
        """True when the quotes were not monotone and PAVA moved them."""
        return any(abs(a - b) > 1e-12 for a, b in zip(self.raw_mids, self.mids))

    def p_over(self, line: float) -> float | None:
        """P(stat > line), or None if the ladder cannot support the question.

        NO EXTRAPOLATION. Beyond the quoted strikes the shape of the tail is
        exactly what nobody has priced, and inventing it is how a fair value
        becomes a fabricated one. A line outside the ladder returns None and the
        caller skips the proposition -- which is what it does today anyway.
        """
        if not self.usable:
            return None
        lo, hi = self.strikes[0], self.strikes[-1]
        if line < lo or line > hi:
            return None
        for i, s in enumerate(self.strikes):
            if abs(s - line) < 1e-9:
                return self.mids[i]
            if s > line:
                x0, x1 = self.strikes[i - 1], s
                y0, y1 = self.mids[i - 1], self.mids[i]
                # LINEAR IN LOGIT, not in probability. A survival function is
                # sigmoid-shaped, so straight-line interpolation between .650 and
                # .510 is fine in the body and badly wrong near the tails, where
                # it can walk a probability toward 0 or past it. Logit space is
                # where the curve is closest to straight.
                w = (line - x0) / (x1 - x0)
                return _expit((1.0 - w) * _logit(y0) + w * _logit(y1))
        return None

    def implied_median(self) -> float | None:
        """The strike where P(over) crosses 0.50.

        WHY IT IS WORTH HAVING. A sportsbook's line sits at the MEDIAN, because
        that is where over/under prices equalise -- while a projection model
        naturally produces a MEAN, and yardage is right-skewed, so mean > median
        and a naive model bets OVER systematically (Peabody; corroborated by
        Unabated -- docs/prop_market_research.md). This exposes the market's own
        median so a projection can be compared against the right quantity.
        """
        if not self.usable:
            return None
        for i in range(1, len(self.strikes)):
            y0, y1 = self.mids[i - 1], self.mids[i]
            if (y0 - 0.5) * (y1 - 0.5) <= 0 and y0 != y1:
                x0, x1 = self.strikes[i - 1], self.strikes[i]
                w = (y0 - 0.5) / (y0 - y1)
                return x0 + w * (x1 - x0)
        return None


def from_kalshi(markets: list[dict]) -> Ladder:
    """Build a ladder from Kalshi market objects.

    Kalshi lists "300+ passing yards" with floor_strike 299.5, i.e. the contract
    pays if the stat EXCEEDS 299.5 -- already the over convention, no adjustment.
    Prices moved to `*_dollars` fields; reading the old `yes_bid`/`yes_ask` names
    silently yields nothing, which is how the first probe of this concluded the
    board had no two-sided quotes when in fact every market did.
    """
    rungs = []
    for m in markets:
        strike = m.get("floor_strike")
        bid, ask = m.get("yes_bid_dollars"), m.get("yes_ask_dollars")
        if strike is None or bid in (None, "") or ask in (None, ""):
            continue
        try:
            rungs.append(Rung(float(strike), float(bid), float(ask)))
        except (TypeError, ValueError):
            continue
    return Ladder(rungs)
