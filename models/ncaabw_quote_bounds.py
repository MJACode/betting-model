"""
The plausible range of an NCAABW (women's college basketball) quote, and the
largest edge a real NCAABW price gives: the guard the women's cards read
against a feed typo.

A fork of the men's models/ncaab_quote_bounds.py (2026-11-10): the same rule
and the same functions, with the women's ranges. The men's file tells the
story (a DraftKings total of 1465.0 for 146.5 in the stored history).

THE RULE. A quote is a data error when its line is outside its market's
LINE_RANGE, or either price is beyond +/-MAX_ABS_PRICE. It is dropped before
anything prices it; the totals card's first post is then the first row INSIDE
the range. A best edge above the model's EDGE_CAP is a data error too: no bet
is written and the run fails.

THE RANGES, measured 2026-11-09 on every pre-game row the feed's history
holds for women's games (fourteen books, 2024-11-12 to 2026-11-09;
scripts/ncaabw_research/quotes.py):
  full-game total   39,328 rows: 108.8 at the 0.1% quantile, 172.5 at the
                    99.9%, max 179.5; one row of 41.5 is the only one under
                    100. DraftKings: 107.5 to 173.5.        -> 90 to 200
  full-game spread  63,209 rows: -73.5 to +70.5, and 274 rows are beyond 60
                    points either way. Women's lines run far wider than the
                    men's (-47.5 to +34.5), so the men's +/-60 would drop
                    real quotes.                             -> -85 to +85
  prices            totals -1430 to +1030 (DraftKings' totals -120 to -102);
                    moneylines down to -100000, kept.        -> |price| <= 100000
The feed carries no women's first-half line, so there is no first-half range.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

# market -> (lowest, highest) plausible line; spreads are the HOME number.
LINE_RANGE: dict[str, tuple[float, float]] = {
    "totals": (90.0, 200.0),
    "spreads": (-85.0, 85.0),
}
# Markets with no line: only the prices are checked.
PRICE_ONLY = ("h2h",)
MAX_ABS_PRICE = 100_000.0       # beyond +/-100000 is a typo; -100000 itself is real

# The cap sits well above the largest edge the model's own replay produced:
#   ncaabw_total_blend   0.2076 over the 1,730 priced games of 2024-25 and
#                        2025-26 on the two-season blend (99.9th percentile
#                        0.1977; scripts/ncaabw_research/totals_c.py), so 0.30.
#   ncaabw_live_total_ht 0.371 over the 967 replayed halftime bets of 2024-25
#                        and 2025-26 (median 0.062; two above 0.30, both
#                        won), so 0.40. The bets the research made on a wrong
#                        halftime score reached 0.48 (models/ncaabw_live_ht.
#                        states_from_rows tells that story).
EDGE_CAP: dict[str, float] = {
    "ncaabw_total_blend": 0.30,
    "ncaabw_live_total_ht": 0.40,
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
    is refused outright, so a new NCAABW card cannot skip choosing one."""
    cap = EDGE_CAP[model_id]
    if edge is None:
        return None
    e = float(edge)
    if math.isfinite(e) and e > cap:
        return f"edge {e:+.4f} above the data-error cap {cap:g}"
    return None
