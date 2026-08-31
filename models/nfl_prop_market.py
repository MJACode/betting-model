"""
Market-relative NFL prop selection: de-vig the sharp book, bet the soft outlier.

WHY THIS EXISTS, AND WHY IT IS NOT THE OTHER MODEL. `models/nfl_prop_backtest`
grades a from-scratch projection against DraftKings. Eleven of twelve markets
lost to the hold, which says our projection is not better than the market's —
not that the market is unbeatable. The construction that is actually documented
to work, and that this repo already runs live on NFL spreads (§28 opener), is
the opposite: take a market-making book's price as the estimate of truth, and
bet wherever a retail book disagrees with it by more than the juice.

Pinnacle is that book here. Measured 2026-08-23: it quotes 8 of our 12 markets
(everything except rush attempts, rush+rec yards, sacks and tackles+assists) at
roughly 55-65% of DraftKings' row count, because it prices fewer players per
game. A market maker declining to quote is itself information, and those four
markets stay projection-only.

THE ONE THING THAT MAKES THIS HONEST. The comparison must be like-for-like on
the LINE. Pinnacle at 5.5 receptions and DraftKings at 6.5 are different
propositions, and treating the price gap between them as an edge would
manufacture one out of thin air — it is the same class of error as the
tackles definitional mismatch, which produced a significant, two-season,
+13% result that was entirely a measurement artifact. Only equal lines are
compared, and how many rows that discards is reported rather than hidden.
"""
from __future__ import annotations

from dataclasses import dataclass

SHARP_BOOK = "pinnacle"

# Markets Pinnacle was measured to quote. Kept explicit rather than discovered
# at runtime so a silent coverage change shows up as a missing market instead of
# a quietly smaller bet set.
SHARP_MARKETS = (
    "player_pass_yds", "player_pass_attempts", "player_pass_completions",
    "player_pass_tds", "player_reception_yds", "player_receptions",
    "player_rush_yds", "player_anytime_td",
)

# The books we BET at. One list, because the card, the backtest and the live
# fetch must agree about who is in play — a book priced live but excluded from
# the backtest would put bets on the board that no measured ROI describes.
#
# Switching a book on is one edit here plus the same key in the ingestor's
# MARKET_BOOKS. Do it only after scripts/nfl_prop_book_sweep has graded it: a
# book that adds volume and loses money is worse than one that adds nothing.
SOFT_BOOKS = (
    "draftkings", "fanduel", "betmgm", "williamhill_us", "espnbet",
)


# The edge maths lives in models/market_relative.py, shared with MLB props
# (2026-08-31). It was written here first and is not NFL-specific: de-vig,
# compare like-for-like on the line, take the difference. Copying it per sport
# is how a bug gets fixed in one place and not the other -- with money attached.
# Re-exported under the original names so every caller, script and test that
# imports them from this module keeps working unchanged.
from models.market_relative import (  # noqa: E402
    MarketBet,
    devig,
    implied,
    find_bets as _find_bets_generic,
)


def find_bets(quotes: dict, min_edge: float = 0.02,
              soft_books: tuple[str, ...] | None = None
              ) -> tuple[list[MarketBet], dict]:
    """NFL binding of the shared selector: Pinnacle is the sharp reference."""
    return _find_bets_generic(quotes, SHARP_BOOK, min_edge, soft_books)


# ── Grading ──────────────────────────────────────────────────────────────────
# Everything below turns selections into a graded record under the same six
# gates as models/nfl_prop_backtest (docs/nfl_props_model.md §5). It shares that
# module's price math and kickoff parsing rather than restating them, because
# two implementations of "did this bet win" is how a backtest and a live scorer
# end up grading different things.

# Odds API market key -> the nfl_player_game_log column that settles it, or a
# DERIVED_ name a caller must compute. Must cover every market anything sweeps:
# a market absent here grades to zero bets, and a silent zero reads as "no edge"
# when it means "could not be measured" — which is exactly how the extended
# sweep first reported that a second market maker opened nothing.
DERIVED_RUSH_REC = "DERIVED_rush_rec_yds"
DERIVED_ANY_TD = "ANY_TD"

MARKET_STAT = {
    "player_pass_yds": "passing_yards", "player_pass_attempts": "attempts",
    "player_pass_completions": "completions", "player_pass_tds": "passing_tds",
    "player_reception_yds": "receiving_yards", "player_receptions": "receptions",
    "player_rush_yds": "rushing_yards", "player_anytime_td": "ANY_TD",
    # The markets Pinnacle declines. Present so a sweep over them is GRADED
    # rather than silently empty; whether they are traded is a separate
    # decision in SHARP_MARKETS. tackles+assists is here for completeness and
    # is definitionally unreliable on our side — see docs §5b.
    "player_rush_attempts": "carries",
    "player_sacks": "def_sacks",
    "player_rush_reception_yds": DERIVED_RUSH_REC,
}


def best_per_prop(bets):
    """One bet per (game, player, market, side), best edge first.

    The same proposition available at three books is three copies of ONE
    opinion. The backtest and the live card must select identically or the card
    shows a slate the measured ROI never described, so both call this.
    """
    out, seen = [], set()
    for b in sorted(bets, key=lambda x: -x.edge):
        prop = (b.game_id, b.player, b.market, b.side)
        if prop in seen:
            continue
        seen.add(prop)
        out.append(b)
    return out


def grade(bets, actuals: dict, snapshots: dict, kickoffs: dict,
          dedupe: bool = True) -> list[dict]:
    """
    Settle `bets` against actuals, dropping post-kickoff quotes.

    `dedupe` keeps ONE bet per (game, player, market, side), best edge first.
    The same proposition available at three books is three copies of one
    opinion; counting them separately inflates the sample and narrows the
    confidence interval around a bet you only really made once.
    """
    from models.nfl_prop_backtest import american_to_profit, _as_dt

    out = []
    for b in (best_per_prop(bets) if dedupe else sorted(bets, key=lambda x: -x.edge)):
        snap = _as_dt(snapshots.get((b.game_id, b.player, b.market, b.book)))
        ko = _as_dt(kickoffs.get(b.game_id))
        if snap and ko and snap >= ko:
            continue                                  # gate 3: post-kickoff
        actual = actuals.get((b.game_id, b.player, b.market))
        if actual is None:
            continue                                  # never played / no stat
        if actual == b.line:
            result, profit = "PUSH", 0.0              # whole-number lines push
        else:
            won = (actual > b.line) if b.side == "over" else (actual < b.line)
            result = "WIN" if won else "LOSS"
            profit = american_to_profit(b.price) if won else -1.0
        out.append({"season": season_of(b.game_id), "game_id": b.game_id,
                    "player": b.player, "market": b.market, "side": b.side,
                    "book": b.book, "line": b.line, "price": b.price,
                    "edge": b.edge, "actual": actual,
                    "result": result, "profit": profit})
    return out


def season_of(game_id: str) -> int:
    """NFL_{season}_{week}_{away}_{home} — the label, never derived from a date."""
    return int(game_id.split("_")[1])


def summarise(graded: list[dict], draws: int = 2000, seed: int = 0) -> dict:
    import numpy as np
    if not graded:
        return {"bets": 0}
    prof = np.array([g["profit"] for g in graded], dtype=float)
    dec = [g for g in graded if g["result"] != "PUSH"]
    rng = np.random.default_rng(seed)
    boot = [rng.choice(prof, prof.size, replace=True).mean() * 100 for _ in range(draws)]
    lo, hi = np.percentile(boot, [2.5, 97.5])
    per_season: dict = {}
    for g in graded:
        per_season.setdefault(g["season"], []).append(g["profit"])
    return {
        "bets": len(graded),
        "pushes": sum(1 for g in graded if g["result"] == "PUSH"),
        "win_pct": round(100 * sum(g["result"] == "WIN" for g in dec) / len(dec), 2) if dec else 0.0,
        "roi_pct": round(100 * prof.sum() / prof.size, 2),
        "roi_ci": (round(lo, 2), round(hi, 2)),
        "units": round(float(prof.sum()), 1),
        "per_season": {s: {"bets": len(v), "roi_pct": round(100 * sum(v) / len(v), 2)}
                       for s, v in sorted(per_season.items())},
    }
