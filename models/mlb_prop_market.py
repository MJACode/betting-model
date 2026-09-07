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


DO NOT WIRE THIS. Measured 2026-09-07 over 6,931 graded selections and
158 dates: NEGATIVE at every threshold from 2pp to 6pp, negative in BOTH
halves of a time split, and negative in five of six months. The one
positive cell (7pp, +7.11%) sits on 76 bets between neighbours of -0.54%
and -3.54% -- a peak, not a plateau, which is exactly what CLAUDE.md 7
says to reject. Full write-up, including what it does NOT say about the
NFL result, in docs/mlb_prop_market_eval.md.
"""

from __future__ import annotations

from data.first_pitch import pregame_cutoff_sql
from features.feature_engine import _parse_iso_ts
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
    """Newest PRE-GAME quote per (game, player, market, book) for one date.

    Newest rather than opening: this is the price a bet would actually be
    placed at. in_play rows are excluded -- CLAUDE.md section 6, pre-game and
    in-play prices never mix.

    EXCLUDING snapshot_type='in_play' IS NOT ENOUGH, and this function shipped
    for six days believing it was. The prop ingestor keeps snapshotting after
    first pitch and labels those rows 'open': measured 2026-09-06, 5,583 of
    24,034 DraftKings batter_total_bases rows (23%) carry a snapshot_at after
    their game started. Ordering by snapshot_at DESC then preferentially picks
    exactly those, because they are the newest.

    What that did to the numbers, on 10 dates of Pinnacle coverage:

        unbounded    n=1585   actual over 24.7%   DK de-vigged 34.9%   -10.1pp
        pre-game     n=1116   actual over 41.6%   DK de-vigged 41.7%    -0.2pp

    A ten-point disagreement with the book's own price, gone. The first grading
    of this rule on MLB came back negative at every threshold and it was this,
    not the rule. Same bug as pick 107657 (tests/test_prop_price_pregame_bound),
    fixed there for the prop scorer in 2026-09-03 and never applied here --
    section 1b's "a bug fixed in one copy of an edge calculation and not the
    other is the same failure with money attached", which is the reason
    market_relative.py is shared in the first place.

    models/wnba_prop_market.load_wnba_prop_quotes already did this correctly.
    The bound is pregame_cutoff_sql (actual first pitch, clamped), and post-cut
    snapshots are dropped on PARSED timestamps in Python -- snapshot_at and
    commence_time are TEXT in mixed 'Z'/offset shapes and string order is not
    chronological order.
    """
    rows = conn.execute(f"""
        SELECT o.game_id, o.player_name, o.market, o.bookmaker,
               o.line, o.over_price, o.under_price,
               o.snapshot_at, {pregame_cutoff_sql("g")}
        FROM player_prop_odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE o.game_date = %(d)s
          AND o.market = ANY(%(m)s)
          AND o.bookmaker = ANY(%(b)s)
          AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
        ORDER BY o.snapshot_at
    """, {"d": game_date, "m": list(markets),
          "b": [SHARP_BOOK, *SOFT_BOOKS]}).fetchall()

    quotes: dict = {}
    best: dict = {}
    for gid, player, market, book, line, op, up, snap, cutoff in rows:
        if line is None:
            continue
        cut_dt = _parse_iso_ts(cutoff)
        snap_dt = _parse_iso_ts(snap)
        if cut_dt is not None and snap_dt is not None and snap_dt >= cut_dt:
            continue                                   # post-first-pitch quote
        key = (gid, player, market, book)
        # Latest QUALIFYING snapshot wins. An unparseable timestamp loses to any
        # parsed one rather than winning by string order, which is how the
        # session-106 WNBA leak got in.
        if key in best and snap_dt is not None and best[key] is not None                 and snap_dt < best[key]:
            continue
        best[key] = snap_dt
        quotes[key] = {
            "line": float(line),
            "over_price": None if op is None else float(op),
            "under_price": None if up is None else float(up),
        }
    return quotes


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
