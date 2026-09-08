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
# The second reference. §5c found betonlineag clears the same bar Pinnacle did
# -- 840 bets, +7.68%, positive in all three seasons, reproduced by no retail
# book -- and used it only to ask whether it opens the markets Pinnacle
# declines (it does not). Used here as an OR alongside Pinnacle; see find_bets
# for the measurement. Verified served by the live endpoint before wiring:
# 48 outcomes against Pinnacle's 42 on the same event, 2026-09-08.
SHARP_BOOKS = ("pinnacle", "betonlineag")

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
    "draftkings", "fanduel", "betmgm", "williamhill_us",
    # Added 2026-09-07 (mike: "add another 2-3 soft books"). These are exactly
    # the three scripts/nfl_prop_book_sweep endorses -- each clears volume,
    # sign, coverage and non-dilution on its own.
    "betrivers", "fliff", "hardrockbet",
)

# espnbet was HERE until 2026-09-08 and should not have been. mike, 2026-09-03:
# "remove william hill and espn bet (shut down last year)". That was applied to
# BEST_LINE_BOOKMAKERS -- the list answering "where should the bettor place
# this?" -- and never to this one, so for five days the rule went on naming
# espnbet as the book to bet at while every other surface treated it as
# unbettable. A soft book IS the side we take; being absent from the bettable
# list is disqualifying here in a way it is not for a reference.
#
# It cost nothing to honour: measured on the `open` board at the 5pp cut,
# dropping it takes 648 bets -> 623 and +63.72u -> +63.48u, i.e. -0.24 units
# across three seasons, while ROI IMPROVES +9.83% -> +10.19% and the interval
# tightens (+3.6, +16.0) -> (+3.7, +16.5). Twenty-five bets that were barely
# break-even, at a book the reader was not going to use.
#
# The guard is scripts/nfl_prop_book_sweep's clause zero plus
# tests/test_book_sweep_bettability.py, which asserts every SOFT_BOOKS entry is
# in BEST_LINE_BOOKMAKERS. That test FAILED on the live config when written --
# this drift was already shipped.

# WHAT THIS TRADE ACTUALLY IS, because §5c rejected the same change once and the
# reversal should not look like an oversight. Measured on the same three seasons:
#
#     set                bets   win%      ROI    units             CI
#     the original 5      954  57.5%  +10.33%   +98.6u  (+4.2, +16.3)
#     all 13 books       1585  56.0%   +6.72%  +106.5u  (+1.9, +11.4)
#
# BOTH ARE POSITIVE AND BOTH EXCLUDE ZERO, so this was never "does breadth
# work". It is total units against risk-adjusted return: the extra books add
# roughly 8 units on 66% more bets, i.e. the MARGINAL bets return about +1.25%
# -- real, but thin against a ~3% hold and thin enough that a small pricing
# change could take it negative.
#
# §5c declined that trade on the reasoning that flat staking makes it strictly
# worse risk-adjusted. mike took the other side with the numbers in front of
# him, which is a preference about ROI versus volume rather than a correction.
# Eight books rather than thirteen keeps most of the volume and drops the books
# that fail the sweep's bar on their own.
#
# THE SWEEP'S CRITERIA STILL HAVE THE FLAW §5c NAMED: all four clauses judge a
# book IN ISOLATION and none asks whether the enlarged SET earns more. The set
# numbers above are the answer to that question and are the reason this is
# defensible; re-run scripts/nfl_prop_book_sweep before changing it again.


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
    """NFL binding: a bet if EITHER sharp reference disagrees by min_edge.

    TWO REFERENCES, TAKEN AS AN OR AND NOT AN AND. Measured 2026-09-08 over
    2023-2025 with the shipped guards (equal lines, pre-game, one bet per
    proposition, real prices), at the pre-committed 5pp:

        selection      bets   win%      ROI            90% CI     by season
        pinnacle        643  57.4%   +9.80%    (+3.5, +16.0)  +12.7 +8.9  +7.4
        betonlineag     253  52.6%   +4.12%    (-6.6, +14.6)  -12.5 +8.0 +22.5
        EITHER          832  56.4%   +8.91%    (+3.4, +14.5)   +7.6 +8.6 +10.9
        both agreeing    60  48.3%   -6.87%   (-27.5, +14.0)          --

    EITHER adds 29% more bets and 18% more UNITS (+74.1 against +63.0) for
    0.9pp of ROI, and its season spread is 3.3pp against Pinnacle's 5.3pp --
    Pinnacle alone is DECLINING (+12.7 -> +8.9 -> +7.4) while the pair holds
    (+7.6 -> +8.6 -> +10.9), which is what §5c predicted as books tighten.

    THE CONSENSUS VERSION WAS THE HYPOTHESIS AND IT LOST. Requiring BOTH books
    to disagree looks like stronger evidence and returns -6.87% on 60 bets. Two
    market makers rarely disagree with the same soft price at 5pp, and when they
    do it is the soft book being right about something they both missed. Written
    down because it is the intuitive thing to try next.

    NOT A THRESHOLD CHANGE. 5pp is pre-committed (§5c) and both configurations
    plateau at 5-6pp rather than peaking: EITHER runs +1.96 / +5.06 / +8.91 /
    +10.04 at 3/4/5/6pp. The cut is untouched; only the reference set moves.

    betonlineag is a REFERENCE, never a book we bet -- SOFT_BOOKS is unchanged.
    """
    best: dict = {}
    diag_out: dict = {}
    for ref in SHARP_BOOKS:
        bets, diag = _find_bets_generic(quotes, ref, min_edge, soft_books)
        for k, v in diag.items():
            diag_out[f"{ref}_{k}"] = v
        for b in bets:
            key = (b.game_id, b.player, b.market, b.side, b.book)
            prev = best.get(key)
            if prev is None or b.edge > prev.edge:
                best[key] = b
    out = list(best.values())

    # THE FLAT KEYS ARE A CONTRACT, not decoration. The card logs them, the
    # replay harness reads them, and tests assert on them -- namespacing them
    # per reference and stopping there broke two tests that had every right to
    # expect `no_sharp` and `one_way` to exist. Per-reference keys are kept
    # alongside, because "Pinnacle had no quote but betonlineag did" is exactly
    # what a two-reference diagnostic should be able to say.
    # HOW EACH ONE AGGREGATES IS NOT UNIFORM, and blanket-summing got it wrong:
    # it reported no_sharp=2 for a single proposition that neither reference
    # quoted, because each reference counted the same absence once.
    #
    #   compared / line_mismatch  SUM -- these count COMPARISONS, and two
    #                             references genuinely make twice as many.
    #   one_way / no_sharp        MAX -- "at least one reference found this
    #                             proposition unusable for this reason". MIN was
    #                             tried first and is wrong: the two references
    #                             can fail on the SAME proposition for DIFFERENT
    #                             reasons -- a one-way Pinnacle quote with no
    #                             betonlineag quote at all is one_way=1/no_sharp=0
    #                             under one and 0/1 under the other, and min
    #                             reports zero of both. Max is exact for a single
    #                             reference and truthful for two.
    #   sharp_quotes              MAX -- the same propositions seen twice.
    for name in ("compared", "line_mismatch"):
        diag_out[name] = sum(diag_out.get(f"{ref}_{name}", 0)
                             for ref in SHARP_BOOKS)
    for name in ("one_way", "no_sharp"):
        diag_out[name] = max(
            (diag_out.get(f"{ref}_{name}", 0) for ref in SHARP_BOOKS),
            default=0)
    diag_out["sharp_quotes"] = max(
        (diag_out.get(f"{ref}_sharp_quotes", 0) for ref in SHARP_BOOKS),
        default=0)
    diag_out["bets"] = len(out)
    return out, diag_out


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
