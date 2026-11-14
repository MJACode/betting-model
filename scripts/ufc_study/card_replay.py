"""The card's own code against the research, bet for bet, on the bought history.

For each year Y of the bought feed history, the production build
(scripts/ufc_open_moneyline_build.build, through Y-1: the research's
walk-forward fold) gives the coefficients; the production ratings
(models/ufc_ratings.replay) give each fight's inputs; the card's decision
(models/ufc_open_moneyline.decide_pull) runs on every pull at least a week
out, in time order, and the first that clears locks the fight. The result
is compared with the research's rule (feed_kill.py's lock at 168 hours and
EV >= 0.06): the same fights, side, book and price.

Run from the study folder (feed_quotes.parquet), with DATABASE_URL set for the
fight log and the archive opens (small reads)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))
exec(Path(__file__).with_name("feed_kill.py").read_text(encoding="utf-8").split('print("\\n-- neighbourhood")')[0]
     .replace("MIN_LEAD = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0", "MIN_LEAD = 168.0"))

import config  # noqa: E402
from data.db import get_connection  # noqa: E402
from models import ufc_open_moneyline as om  # noqa: E402
from models import ufc_ratings as R  # noqa: E402
from scripts.ufc_open_moneyline_build import build  # noqa: E402

research = lock(J0, J0.xb.to_numpy(), 0.06)
conn = get_connection()
rows, profiles = R.load(conn)
z = {}
R.replay(rows, profiles, on_fight=lambda gid, a, b, d: z.__setitem__(gid, d))
arts = {Y: build(conn, through=Y - 1) for Y in sorted(J0.year.dropna().unique().astype(int))}
conn.close()
floor, cut = config.min_odds_for(om.MODEL_ID), config.min_ev_for(om.MODEL_ID)

card_bets = {}
for (gid, served), g in J0.sort_values("served_at").groupby(["game_id", "served_at"], sort=False):
    if gid in card_bets:
        continue
    yr = int(g.year.iloc[0])
    xb = om.opinion(arts[yr], z[gid])
    books = {r.book: (float(r.pa), float(r.pb)) for r in g.itertuples()}
    pick, _ = om.decide_pull((float(g.qa.iloc[0]), float(g.qb.iloc[0])), books, xb, cut, floor)
    if pick is not None:
        card_bets[gid] = (served, pick.side, pick.book, pick.price, xb)

R_ = {r.game_id: (r.served_at, "a" if r.ta else "b", r.book, float(r.price), r.xb)
      for r in research.itertuples()}
same = [g for g in R_ if g in card_bets and R_[g][:4] == card_bets[g][:4]]
only_r = sorted(set(R_) - set(card_bets))
only_c = sorted(set(card_bets) - set(R_))
differ = [g for g in R_ if g in card_bets and R_[g][:4] != card_bets[g][:4]]
dxb = max((abs(R_[g][4] - card_bets[g][4]) for g in R_ if g in card_bets), default=0.0)
print(f"research {len(R_)} bets, card {len(card_bets)}: identical {len(same)}, research only "
      f"{len(only_r)}, card only {len(only_c)}, same fight different bet {len(differ)}; "
      f"largest opinion difference {dxb:.2e}")
for g in (only_r + only_c + differ)[:10]:
    print("  ", g, R_.get(g), card_bets.get(g))
