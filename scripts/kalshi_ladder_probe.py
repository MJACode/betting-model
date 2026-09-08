"""How much of the board does a Kalshi ladder price that our references cannot?

THE NUMBER THIS EXISTS TO PRODUCE. `models/nfl_prop_market` can only compare a
sharp and a soft book when they quote the SAME line, and that requirement throws
away 63,676 NFL propositions (65% of the comparable NCAAF board). A ladder prices
ANY line by interpolation, so the question is no longer "does Kalshi have a
number" but "how many rows does it turn from discarded into priced".

This measures exactly that against the live board, three ways per soft-book
quote:

    priced now      a sharp reference quotes the SAME line -- today's capability
    kalshi          a Kalshi ladder brackets the line -- the new capability
    RECOVERED       kalshi can price it and no sharp reference can

It is a coverage measurement, NOT a profitability one. Whether the ladder's fair
value is any GOOD is a separate question that needs settled results, and Kalshi's
NFL prop history reaches back only to 2026 preseason.

    python -m scripts.kalshi_ladder_probe
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

import models.nfl_prop_market as mk
from data.db import get_connection
from data.ingestors.kalshi_prop_ingestor import SERIES_MARKET, ladders
from data.ingestors.nfl_props_data_ingestor import norm_player_name


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=10)
    a = ap.parse_args()

    logger.info("pulling Kalshi ladders ...")
    lads = ladders()
    if not lads:
        logger.error("no Kalshi ladders — nothing to compare")
        return

    conn = get_connection()
    rows = conn.execute("""
        SELECT DISTINCT ON (o.game_id, o.player_name, o.market, o.bookmaker)
               o.game_date, o.player_name, o.market, o.bookmaker,
               o.line, o.over_price, o.under_price
        FROM player_prop_odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE o.game_id LIKE 'NFL%%'
          AND o.line IS NOT NULL
          AND o.game_date::date >= CURRENT_DATE
          AND o.game_date::date <= CURRENT_DATE + %s
        ORDER BY o.game_id, o.player_name, o.market, o.bookmaker,
                 o.snapshot_at DESC
    """, (a.days,)).fetchall()
    conn.close()
    logger.info(f"{len(rows)} live board quotes in the next {a.days} days")

    # A sharp reference can price a proposition only at its OWN line.
    sharp_lines = defaultdict(set)
    for gd, player, market, book, line, op, up in rows:
        if book in mk.SHARP_BOOKS and op is not None and up is not None:
            sharp_lines[(str(gd), norm_player_name(player), market)].add(float(line))

    tally = defaultdict(int)
    by_market = defaultdict(lambda: defaultdict(int))
    for gd, player, market, book, line, op, up in rows:
        if book not in mk.SOFT_BOOKS or op is None or up is None:
            continue
        key = (str(gd), norm_player_name(player), market)
        line = float(line)
        now_ok = line in sharp_lines.get(key, set())
        lad = lads.get(key)
        kal_ok = lad is not None and lad.p_over(line) is not None

        tally["soft_quotes"] += 1
        by_market[market]["soft_quotes"] += 1
        if now_ok:
            tally["priced_now"] += 1
            by_market[market]["priced_now"] += 1
        if kal_ok:
            tally["kalshi"] += 1
            by_market[market]["kalshi"] += 1
        if kal_ok and not now_ok:
            tally["recovered"] += 1
            by_market[market]["recovered"] += 1
        if lad is None:
            tally["no_ladder"] += 1

    n = tally["soft_quotes"] or 1
    print(f"\nKalshi ladder coverage against the live NFL board")
    print(f"  markets mapped: {len(SERIES_MARKET)} | usable ladders: {len(lads)}")
    print(f"\n  {'soft-book quotes':22s} {tally['soft_quotes']:>7,}")
    print(f"  {'priced now (same line)':22s} {tally['priced_now']:>7,}  "
          f"{100*tally['priced_now']/n:>5.1f}%")
    print(f"  {'kalshi can price':22s} {tally['kalshi']:>7,}  "
          f"{100*tally['kalshi']/n:>5.1f}%")
    print(f"  {'RECOVERED':22s} {tally['recovered']:>7,}  "
          f"{100*tally['recovered']/n:>5.1f}%   <- new rows")
    print(f"  {'no ladder at all':22s} {tally['no_ladder']:>7,}")

    print(f"\n  {'market':28s} {'soft':>7s} {'now':>7s} {'kalshi':>7s} {'recovered':>10s}")
    for m, d in sorted(by_market.items(), key=lambda kv: -kv[1]["soft_quotes"]):
        print(f"  {m:28s} {d['soft_quotes']:>7,} {d['priced_now']:>7,} "
              f"{d['kalshi']:>7,} {d['recovered']:>10,}")
    print("\n  Coverage only. Whether the ladder's fair value is GOOD needs "
          "settled\n  results, and Kalshi NFL prop history starts at 2026 "
          "preseason.\n")


if __name__ == "__main__":
    main()
