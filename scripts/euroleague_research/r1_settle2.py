"""Round 1, step 3b: does a tied half / quarter PUSH the two-way moneyline, or
lose it? Same book (BetRivers), same fetch: its two-way h2h_h1 / h2h_q1 price
against its three-way h2h_3_way_h1 / h2h_3_way_q1 price.

If a tie pushes (draw no bet), the two-way home bet is strictly better than the
three-way home bet, so its implied probability is HIGHER, by about the draw's
share. If a tie loses, the two bets are the same event and the implied
probabilities should match up to margin.

    python scripts/euroleague_research/r1_settle2.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

C = Path(r"C:\Users\micha\euroleague_research\cache")
q = pd.read_parquet(C / "period_quotes.parquet")


def imp(a):
    a = np.asarray(a, float)
    return np.where(a > 0, 100 / (a + 100), -a / (-a + 100))


for two, three in [("h2h_h1", "h2h_3_way_h1"), ("h2h_q1", "h2h_3_way_q1")]:
    for book in ["betrivers", "fanatics"]:
        a = q[(q.market == two) & (q.bookmaker == book)][["game_id", "mark", "home_price", "away_price"]]
        b = q[(q.market == three) & (q.bookmaker == book)][["game_id", "mark", "home_price", "away_price", "draw_price"]]
        m = a.merge(b, on=["game_id", "mark"], suffixes=("_2", "_3"))
        if not len(m):
            print(two, three, book, "no paired quotes")
            continue
        h2, a2 = imp(m.home_price_2), imp(m.away_price_2)
        h3, a3, d3 = imp(m.home_price_3), imp(m.away_price_3), imp(m.draw_price)
        s2 = h2 + a2
        s3 = h3 + a3 + d3
        fair2 = h2 / s2                     # two-way, de-vigged
        dnb = (h3 / s3) / ((h3 + a3) / s3)  # three-way, draw removed (draw no bet)
        win3 = h3 / s3                      # three-way fair home WIN (tie loses)
        print(f"== {two} vs {three} at {book}: {len(m)} paired (game, mark) quotes")
        print(f"   two-way raw sum median {np.median(s2):.4f}; three-way raw sum median {np.median(s3):.4f};"
              f" three-way fair draw median {np.median(d3 / s3):.4f}")
        print(f"   two-way home implied minus three-way home implied: median {np.median(h2 - h3):+.4f},"
              f" share > 0: {np.mean(h2 > h3):.3f}")
        print(f"   two-way fair home minus three-way draw-no-bet home: median {np.median(fair2 - dnb):+.4f},"
              f" mean abs {np.mean(np.abs(fair2 - dnb)):.4f}")
        print(f"   two-way fair home minus three-way fair home WIN:    median {np.median(fair2 - win3):+.4f},"
              f" mean abs {np.mean(np.abs(fair2 - win3)):.4f}")
