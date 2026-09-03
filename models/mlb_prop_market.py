"""
Market-relative MLB player props: de-vig Pinnacle, bet DraftKings' outlier.

WHY THIS EXISTS
---------------
The projection models lose. Measured 2026-08-31 over every settled BET:
mlb_prop_batter_hits -11.25%/405, batter_tb -11.72%/153, pitcher_hits
-27.93%/65, pitcher_walks -21.16%/74 -- nine of eleven prop models negative,
and a 185-cell threshold sweep on calibrated probabilities found only twelve
cells profitable even IN-SAMPLE, with a train-to-test correlation of 0.055.
There is no cut to find. Picking one on history predicts nothing forward.

This repo has already run that experiment once and drawn the conclusion, in
models/nfl_prop_backtest: eleven of twelve NFL markets lost to the hold, which
says our projection is not better than the market's -- not that the market is
unbeatable. The construction that then worked, models/nfl_prop_market, is the
opposite one, and it is the only blind-tested positive result here: +10.22%
train, +10.76% blind, 954 bets, on a pre-committed threshold.

This is that construction for MLB. The arithmetic is shared rather than copied
(models/market_relative.py); this module owns only what is MLB-specific --
which markets Pinnacle actually prices, and how to load quotes.

WHAT PINNACLE ACTUALLY QUOTES, and why most markets are absent
--------------------------------------------------------------
Measured over 2026-08-28..31, Pinnacle rows as a share of DraftKings rows:

    batter_total_bases    69.5%
    pitcher_strikeouts    28.0%
    pitcher_hits_allowed  24.8%
    pitcher_outs          22.5%
    batter_home_runs      14.8%
    batter_runs_scored     2.3%
    batter_hits, batter_rbis, batter_walks,
    pitcher_earned_runs, pitcher_walks,
    batter_stolen_bases    0.0%

A market maker declining to quote is itself information. Half the book is not
priced by Pinnacle at all, so those markets CANNOT be traded this way and stay
projection-only. Listed explicitly rather than discovered at runtime so a
coverage change shows up as a missing market instead of a quietly smaller bet
set -- the same reason models/nfl_prop_market names its eight.

STATUS: SHADOW. NOT WIRED TO THE SCORER, NOT PRODUCING BETS.
-----------------------------------------------------------
Pinnacle MLB prop capture began 2026-08-27. There is no history to backtest
against, so no threshold here is validated and none is pre-committed. Adopting
a cut chosen on four days of data would be exactly the in-sample selection that
put a +7.31% board number in front of a -9.81% record.

So this runs forward and writes nothing that decides anything. The go-live gate
in CLAUDE.md section 2 -- 50 settled picks, positive flat ROI, calibration error
under 5%, per model -- is the bar, and it is forward-looking, which is what this
situation needs.
"""

from __future__ import annotations

from models.market_relative import MarketBet, devig, find_bets, implied  # noqa: F401

SHARP_BOOK = "pinnacle"

# Markets Pinnacle was MEASURED to price for MLB (2026-08-28..31), with its row
# count as a share of DraftKings'. Anything under a few percent is not real
# coverage -- batter_runs_scored at 2.3% would produce a handful of comparisons
# a week and a record that means nothing -- so the traded set is the five above
# a 10% floor.
SHARP_COVERAGE = {
    "batter_total_bases":   0.695,
    "pitcher_strikeouts":   0.280,
    "pitcher_hits_allowed": 0.248,
    "pitcher_outs":         0.225,
    "batter_home_runs":     0.148,
    "batter_runs_scored":   0.023,
}
MIN_COVERAGE = 0.10
SHARP_MARKETS = tuple(m for m, c in SHARP_COVERAGE.items() if c >= MIN_COVERAGE)

# The books we would BET at. DraftKings alone for now: it is the book every
# threshold, settlement and CLV measure in this repo is pinned to, and adding a
# second book changes what "the record" means. One list, so a card, a backtest
# and a live fetch cannot disagree about who is in play.
SOFT_BOOKS = ("draftkings",)

# Deliberately no default threshold constant. The NFL rule's 5pp was
# PRE-COMMITTED against a blind season; there is nothing to pre-commit against
# here yet, so a number in this file would look validated and would not be.
# Callers pass min_edge explicitly and own that choice.


def load_quotes(conn, game_date: str, markets=SHARP_MARKETS) -> dict:
    """Newest pre-game quote per (game, player, market, book) for one date.

    Newest rather than opening: this is the price a bet would actually be
    placed at. in_play rows are excluded -- CLAUDE.md section 6, pre-game and
    in-play prices never mix.
    """
    rows = conn.execute("""
        SELECT DISTINCT ON (game_id, player_name, market, bookmaker)
               game_id, player_name, market, bookmaker, line, over_price, under_price
        FROM player_prop_odds
        WHERE game_date = %(d)s
          AND market = ANY(%(m)s)
          AND bookmaker = ANY(%(b)s)
          AND (snapshot_type IS NULL OR snapshot_type <> 'in_play')
        ORDER BY game_id, player_name, market, bookmaker, snapshot_at DESC
    """, {"d": game_date, "m": list(markets),
          "b": [SHARP_BOOK, *SOFT_BOOKS]}).fetchall()

    return {
        (gid, player, market, book): {
            "line": None if line is None else float(line),
            "over_price": None if op is None else float(op),
            "under_price": None if up is None else float(up),
        }
        for gid, player, market, book, line, op, up in rows
    }


def card(conn, game_date: str, min_edge: float,
         markets=SHARP_MARKETS) -> tuple[list[MarketBet], dict]:
    """Today's market-relative selections, plus the coverage diagnostic.

    The diagnostic is returned, never swallowed: on a thin day `line_mismatch`
    and `no_sharp` explain an empty card, and an empty card that looks like
    "no edge" when it means "Pinnacle priced nothing" is the failure mode this
    repo keeps rediscovering (an absent producer looks exactly like a quiet
    market).
    """
    quotes = load_quotes(conn, game_date, markets)
    return find_bets(quotes, SHARP_BOOK, min_edge=min_edge, soft_books=SOFT_BOOKS)
