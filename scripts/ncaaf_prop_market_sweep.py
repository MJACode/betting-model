"""Does the market-relative rule work on COLLEGE football props?

THE ONE CONSTRUCTION THAT WORKS, pointed at a new sport. models/nfl_prop_market
returns +6.89% over ~2,000 bets with positive closing line value; every
projection model in this repo loses. College football is the obvious next place
to look: the same books, three times the games, and pricing that ought to be
softer than the NFL board.

IT IS NOT THE NFL SETUP, and the differences are large enough that a null result
here would say less than an NFL null would:

  * PINNACLE BARELY EXISTS. 568 two-way quotes over 59 games in the 2025 season
    backfill, against betonlineag's 4,563 over 454. The reference the NFL rule
    proved with a placebo is not really available, so the result rests on
    betonlineag -- which clears the same bar on NFL (840 bets, +7.68%, positive
    in all three seasons) but has never been anyone's sole reference.
  * DRAFTKINGS CANNOT BE BET. Every DK college prop quote is one-way, so it
    cannot be de-vigged and cannot be the soft side. Same for betrivers. The
    bettable set is fliff, hardrockbet, fanduel, betmgm, espnbet and
    williamhill_us -- so the DK-only decision invariant simply does not apply
    here, the way it already does not for nfl_prop_market.

THE PLACEBO IS THE POINT OF THIS SCRIPT, not the headline ROI. One college
season yields ~50 bets at the 5pp cut, which is far too few to conclude anything
from on its own -- a 90% CI that wide is compatible with +30% and with -13%. The
question a 50-bet sample CAN answer is the one that decides whether to buy more
seasons: is the edge specific to a sharp reference, or does ANY book produce it?
--all-refs grades every book on the board as the reference. If retail books
reproduce the number, what we are looking at is the sample, and no further
credits should be spent. If only the market makers do, the signal is worth
paying to measure properly.

Everything else is the NFL rule unchanged: equal lines only, pre-game quotes
(t24 is pre-game by construction -- each event was fetched at its own kickoff
minus 24h), one bet per proposition, de-vig both sides, real prices.

    python -m scripts.ncaaf_prop_market_sweep
    python -m scripts.ncaaf_prop_market_sweep --all-refs
    python -m scripts.ncaaf_prop_market_sweep --ref betonlineag --min-edge 0.05
"""
from __future__ import annotations

import argparse
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from data.db import get_connection
from models.market_relative import devig

# market -> the ncaaf_player_game_log column that settles it
MARKET_STAT = {
    "player_pass_yds": "passing_yards",
    "player_pass_tds": "passing_tds",
    "player_pass_completions": "completions",
    "player_pass_attempts": "attempts",
    "player_pass_interceptions": "interceptions",
    "player_rush_yds": "rushing_yards",
    "player_reception_yds": "receiving_yards",
    "player_receptions": "receptions",
}

# Every book with a meaningful two-way college board. The sharp candidates are
# betonlineag and pinnacle; the rest are retail and serve as the placebo.
BETTABLE = ("fliff", "hardrockbet", "fanduel", "betmgm", "espnbet",
            "williamhill_us")
CANDIDATE_REFS = ("betonlineag", "pinnacle", *BETTABLE)


def norm(n: str) -> str:
    s = unicodedata.normalize("NFKD", str(n or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    for j in (" jr", " sr", " ii", " iii", " iv"):
        if s.endswith(j):
            s = s[: -len(j)]
    return "".join(c for c in s if c.isalnum())


def profit(price, won: bool) -> float:
    p = float(price)
    return (p / 100.0 if p > 0 else 100.0 / abs(p)) if won else -1.0


def load_board():
    """-> {(game, player, market, line): {book: (over, under)}}, actuals."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT DISTINCT ON (o.game_id, o.player_name, o.market, o.bookmaker)
               o.game_id, o.player_name, o.market, o.bookmaker,
               o.line, o.over_price, o.under_price
        FROM player_prop_odds o
        WHERE o.snapshot_type = 't24' AND o.game_id LIKE 'NCAAF%%'
          AND o.market = ANY(%s) AND o.line IS NOT NULL
        ORDER BY o.game_id, o.player_name, o.market, o.bookmaker,
                 o.snapshot_at DESC
    """, (list(MARKET_STAT),)).fetchall()

    cols = sorted(set(MARKET_STAT.values()))
    log = {}
    for r in conn.execute(
            f"SELECT player_name, game_id, {', '.join(cols)} "
            f"FROM ncaaf_player_game_log").fetchall():
        log[(norm(r[0]), r[1])] = dict(zip(cols, r[2:]))
    conn.close()

    board = defaultdict(dict)
    for gid, player, market, book, line, op, up in rows:
        board[(gid, norm(player), market, float(line))][book] = (op, up)
    return board, log


def candidates(board, log, ref: str):
    """Every (proposition, side) the rule could take against `ref`."""
    out, diag = [], defaultdict(int)
    for (gid, player, market, line), books in board.items():
        q = books.get(ref)
        if q is None:
            diag["no_ref"] += 1
            continue
        fo, fu = devig(*q)
        if fo is None:
            diag["ref_one_way"] += 1
            continue
        actual = (log.get((player, gid)) or {}).get(MARKET_STAT[market])
        if actual is None:
            diag["no_actual"] += 1
            continue
        if float(actual) == line:
            continue                       # push
        over = float(actual) > line
        for book, (op, up) in books.items():
            if book not in BETTABLE or book == ref:
                continue
            so, su = devig(op, up)
            if so is None:
                continue
            diag["compared"] += 1
            for side, fair, soft_p, price in (("over", fo, so, op),
                                              ("under", fu, su, up)):
                out.append((gid, player, market, side, fair - soft_p,
                            profit(price, over if side == "over" else not over)))
    return out, diag


def dedupe(sel):
    """ONE BET PER PROPOSITION. The same prop at six books is six copies of one
    opinion; counting them separately inflates the bet count and correlates the
    outcomes."""
    best = {}
    for c in sel:
        k = (c[0], c[1], c[2], c[3])
        if k not in best or c[4] > best[k][4]:
            best[k] = c
    return list(best.values())


def grade(sel, rng):
    prof = np.array([c[5] for c in sel])
    idx = rng.integers(0, len(prof), (20000, len(prof)))
    roi = 100 * prof[idx].mean(axis=1)
    return (len(prof), 100 * (prof > 0).mean(), prof.sum(), 100 * prof.mean(),
            np.percentile(roi, 5), np.percentile(roi, 95))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="betonlineag")
    ap.add_argument("--all-refs", action="store_true",
                    help="grade every book as the reference (the placebo)")
    ap.add_argument("--min-edge", type=float, default=None)
    a = ap.parse_args()
    rng = np.random.default_rng(42)
    board, log = load_board()
    print(f"\nNCAAF props, t24 board: {len(board)} propositions, "
          f"{len({k[0] for k in board})} games")

    if a.all_refs:
        cut = a.min_edge if a.min_edge is not None else 0.05
        print(f"\nTHE PLACEBO -- every book as the reference, min edge "
              f"{cut:.0%}, one bet per proposition")
        print(f"\n{'reference':16s} {'bets':>6} {'win%':>6} {'units':>9} "
              f"{'ROI':>8} {'90% CI':>18}")
        print("-" * 68)
        for ref in CANDIDATE_REFS:
            cand, _d = candidates(board, log, ref)
            sel = dedupe([c for c in cand if c[4] >= cut])
            if len(sel) < 40:
                print(f"{ref:16s} {len(sel):>6}   (thin)")
                continue
            n, w, u, roi, lo, hi = grade(sel, rng)
            print(f"{ref:16s} {n:>6} {w:>5.1f}% {u:>+9.2f} {roi:>+7.2f}% "
                  f"{'(' + format(lo, '+.1f') + ', ' + format(hi, '+.1f') + ')':>18}")
        print("\n  A sharp reference should stand apart. If the retail books "
              "below\n  reproduce it, the number is the sample, not an edge.\n")
        return

    cand, diag = candidates(board, log, a.ref)
    print(f"  reference {a.ref} | compared {diag['compared']} | "
          f"no reference {diag['no_ref']} | no actual {diag['no_actual']}")

    print(f"\n{'min_edge':>9} {'bets':>6} {'win%':>6} {'units':>9} {'ROI':>8} "
          f"{'90% CI':>18}")
    print("-" * 62)
    edges = ([a.min_edge] if a.min_edge is not None
             else (0.02, 0.03, 0.04, 0.05, 0.06, 0.08))
    for e in edges:
        sel = dedupe([c for c in cand if c[4] >= e])
        if len(sel) < 40:
            print(f"{e:>8.0%} {len(sel):>6}   (thin)")
            continue
        n, w, u, roi, lo, hi = grade(sel, rng)
        print(f"{e:>8.0%} {n:>6} {w:>5.1f}% {u:>+9.2f} {roi:>+7.2f}% "
              f"{'(' + format(lo, '+.1f') + ', ' + format(hi, '+.1f') + ')':>18}")

    sel = dedupe([c for c in cand if c[4] >= 0.05])
    if len(sel) >= 40:
        print("\nby market at 5% (the NFL rule's pre-committed cut)")
        by = defaultdict(list)
        for c in sel:
            by[c[2]].append(c[5])
        for m, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
            if len(v) < 20:
                continue
            print(f"   {m:26s} {len(v):>5} bets  {100*np.mean(v):>+7.2f}%")


if __name__ == "__main__":
    main()
