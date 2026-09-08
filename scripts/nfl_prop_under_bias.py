"""Bet the market's bias, not a projection: blind unders where the book leans over.

THE OBSERVATION THIS IS BUILT ON. Measured 2026-09-07 across every DraftKings
NFL prop quote we hold with a two-way price and a graded actual, the book's own
DE-VIGGED probability of the over sits ABOVE the realized over-rate on nearly
every market:

    market                 DK de-vigged P(over)   actual over-rate    bias
    player_tackles_assists          50.0%              42.1%         +8.1pp
    player_receptions               49.5%              45.0%         +4.8pp
    player_pass_attempts            49.9%              45.5%         +4.4pp
    player_rush_reception_yds       50.0%              45.7%         +4.3pp
    player_reception_yds            50.0%              46.4%         +3.6pp
    player_rush_attempts            50.1%              46.7%         +3.5pp
    player_pass_completions         49.8%              46.3%         +3.5pp
    player_rush_yds                 50.0%              47.1%         +2.9pp
    player_sacks                    38.8%              36.4%         +2.4pp
    player_pass_tds                 48.0%              48.8%         -0.8pp
    player_pass_yds                 50.0%              50.3%         -0.3pp

That is the recreational over-lean the industry writes about, and here it is
measured on our own board rather than asserted. It matters because it needs NO
MODEL: if the book's price is systematically wrong in one direction by more than
the vig costs, the under is priced too cheaply and the bet is free of any
projection error.

The bar is the hold. A two-way market with overround h pays away roughly h/2 per
bet, so the bias must exceed that. On the same board: receptions needs 4.35pp
and shows 4.8; rec_yards needs 2.85 and shows 3.6; pass_attempts needs 3.03 and
shows 4.4. Several markets clear. sacks (needs 12.15) and pass_yds/pass_tds
(negative bias) do not.

WHY THIS IS NOT THE THING WE ALREADY TESTED. Every prior NFL prop backtest bet
where OUR MODEL disagreed with the book, and a Brier comparison showed our
accuracy collapsing on exactly those propositions (0.2535 -> 0.2862 while DK
barely moved). This bets no opinion at all. The model is not consulted.

THE TRAP, and it is the whole design of this script: choosing the markets AFTER
seeing which ones showed bias is in-sample selection, and section 7 says a cut
swept on the sample it is measured on regresses forward. So the market list is
chosen on TRAIN seasons only and applied blind to a TEST season it never saw.

    python -m scripts.nfl_prop_under_bias
    python -m scripts.nfl_prop_under_bias --train 2023 2024 --test 2025
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

# Every two-way NFL prop market we hold, with the game-log column that grades it.
MARKET_STAT = {
    "player_pass_yds": "passing_yards",
    "player_pass_attempts": "attempts",
    "player_pass_completions": "completions",
    "player_pass_tds": "passing_tds",
    "player_rush_yds": "rushing_yards",
    "player_rush_attempts": "carries",
    "player_reception_yds": "receiving_yards",
    "player_receptions": "receptions",
}


def norm(n: str) -> str:
    s = unicodedata.normalize("NFKD", str(n or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    for j in (" jr", " sr", " ii", " iii", " iv"):
        if s.endswith(j):
            s = s[: -len(j)]
    return "".join(c for c in s if c.isalnum())


def implied(a) -> float:
    a = float(a)
    return 100.0 / (a + 100.0) if a > 0 else abs(a) / (abs(a) + 100.0)


def profit(price, won: bool) -> float:
    p = float(price)
    return (p / 100.0 if p > 0 else 100.0 / abs(p)) if won else -1.0


def load(conn, season: int) -> list[tuple]:
    """(market, under_price, overround, went_over) per graded proposition.

    Latest PRE-GAME DraftKings two-way quote per player/market. Bounded on
    commence_time and excluding in_play: the ingestor keeps writing 'open' rows
    after kickoff and reading those is what made the first MLB grading
    meaningless (#534).
    """
    rows = conn.execute("""
        SELECT DISTINCT ON (o.game_id, o.player_name, o.market)
               o.market, o.player_name, o.game_id, o.line,
               o.over_price, o.under_price
        FROM player_prop_odds o
        JOIN nfl_team_game_stats s ON s.game_id = o.game_id
        WHERE o.game_id LIKE %s AND o.bookmaker = 'draftkings'
          AND o.market = ANY(%s)
          AND o.line IS NOT NULL
          AND o.over_price IS NOT NULL AND o.under_price IS NOT NULL
          AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
          AND o.snapshot_at::timestamptz <= s.commence_time
        ORDER BY o.game_id, o.player_name, o.market, o.snapshot_at DESC
    """, (f"NFL_{season}%", list(MARKET_STAT))).fetchall()

    cols = sorted({MARKET_STAT[m] for m in MARKET_STAT})
    log = {}
    for r in conn.execute(
            f"SELECT player_name, game_id, {', '.join(cols)} "
            f"FROM nfl_player_game_log WHERE game_id LIKE %s",
            (f"NFL_{season}%",)).fetchall():
        log[(norm(r[0]), r[1])] = dict(zip(cols, r[2:]))

    out = []
    for market, player, gid, line, op, up in rows:
        actual = (log.get((norm(player), gid)) or {}).get(MARKET_STAT[market])
        if actual is None:
            continue
        if float(actual) == float(line):
            continue                       # push: stake returned
        io_, iu = implied(op), implied(up)
        out.append((market, float(up), io_ + iu, float(actual) > float(line)))
    return out


def bias_table(rows: list[tuple]) -> dict:
    """market -> (n, DK de-vigged P(over), actual over-rate, bias, hold, needed)."""
    by = defaultdict(list)
    for market, _up, orr, over in rows:
        by[market].append((orr, over))
    out = {}
    for market, vals in by.items():
        n = len(vals)
        if n < 200:
            continue
        # The de-vigged P(over) is not recoverable per row from `under_price`
        # alone, so it is taken as the mean over-share of the two-way price.
        hold = float(np.mean([v[0] for v in vals])) - 1.0
        actual = float(np.mean([v[1] for v in vals]))
        # A fair two-way market with no lean prices each side at 50%; the book's
        # de-vigged over probability is therefore 0.5 by construction here, and
        # the bias is how far reality falls below it.
        out[market] = (n, 0.5, actual, 0.5 - actual, hold, hold / 2.0)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", nargs="+", type=int, default=[2023, 2024])
    ap.add_argument("--test", nargs="+", type=int, default=[2025])
    a = ap.parse_args()
    rng = np.random.default_rng(42)
    conn = get_connection()

    train = [r for s in a.train for r in load(conn, s)]
    test = [r for s in a.test for r in load(conn, s)]
    print(f"train {a.train}: {len(train)} graded props | "
          f"test {a.test}: {len(test)} graded props\n")

    tb = bias_table(train)
    print(f"TRAIN — where does the book lean over, and is the lean bigger than the vig?")
    print(f"{'market':26s} {'n':>6} {'actual over':>12} {'bias':>8} {'hold':>7} "
          f"{'needed':>8}  verdict")
    print("-" * 84)
    chosen = []
    for m, (n, _dk, act, bias, hold, need) in sorted(
            tb.items(), key=lambda kv: -kv[1][3]):
        ok = bias > need
        if ok:
            chosen.append(m)
        print(f"{m:26s} {n:>6} {100*act:>11.1f}% {100*bias:>+7.1f}pp "
              f"{100*hold:>6.2f}% {100*need:>7.2f}pp  {'BET UNDER' if ok else '-'}")

    if not chosen:
        print("\nno market clears its own vig on the training seasons")
        conn.close()
        return

    print(f"\nchosen on TRAIN only: {', '.join(chosen)}")
    print(f"\nTEST {a.test} — blind unders, no model consulted")
    print(f"{'market':26s} {'bets':>6} {'win%':>6} {'units':>9} {'ROI':>8} {'90% CI':>18}")
    print("-" * 80)

    def ci(prof):
        arr = np.array(prof)
        idx = rng.integers(0, len(arr), (20000, len(arr)))
        r = 100 * arr[idx].mean(axis=1)
        return 100 * arr.mean(), np.percentile(r, 5), np.percentile(r, 95)

    pooled = []
    for m in chosen:
        sel = [r for r in test if r[0] == m]
        if len(sel) < 50:
            print(f"{m:26s} {len(sel):>6}   (thin)")
            continue
        prof = [profit(r[1], not r[3]) for r in sel]   # bet UNDER: win if not over
        pooled += prof
        mean, lo, hi = ci(prof)
        w = sum(1 for p in prof if p > 0)
        print(f"{m:26s} {len(sel):>6} {100*w/len(sel):>5.1f}% {sum(prof):>+9.2f} "
              f"{mean:>+7.2f}% {'('+format(lo,'+.1f')+', '+format(hi,'+.1f')+')':>18}")
    if pooled:
        mean, lo, hi = ci(pooled)
        w = sum(1 for p in pooled if p > 0)
        print("-" * 80)
        print(f"{'POOLED':26s} {len(pooled):>6} {100*w/len(pooled):>5.1f}% "
              f"{sum(pooled):>+9.2f} {mean:>+7.2f}% "
              f"{'('+format(lo,'+.1f')+', '+format(hi,'+.1f')+')':>18}")
    conn.close()


if __name__ == "__main__":
    main()
