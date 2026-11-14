"""What the shipped UFC opening-price rule is expected to make, from the bought
history, decided as the live card decides (noon pulls only, at least 7 days
out, EV >= 0.06, -300 floor). Per year: bets, units risked, units won, return,
the model's own average EV at the bet, and the EV the market's close implies
(Pinnacle's last pre-fight no-vig price). Then units a year under three
returns: the backtest's, the closing-price estimate, and half the backtest's.

Run from the study folder (feed_quotes.parquet, fights.parquet, ml_hist.parquet).
"""
from pathlib import Path

import numpy as np
import pandas as pd

exec(Path(__file__).with_name("feed_kill.py").read_text(encoding="utf-8").split('print("\\n-- neighbourhood")')[0]
     .replace("MIN_LEAD = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0", "MIN_LEAD = 168.0"))

K = lock(J0, J0.xb.to_numpy(), 0.06, stages=["daily"])
u, r = grade(K)
fair = K.game_id.map(pin_fair_a).to_numpy()
side_fair = np.where(K.ta, fair, 1 - fair)
K = K.assign(u=u, r=r, ev_close=side_fair * dec(K.price.to_numpy()) - 1,
             won=np.where(K.ta, K.a_won, ~K.a_won.astype(bool)))
g = K.groupby("year").agg(bets=("u", "size"), risked=("r", "sum"), units=("u", "sum"),
                          model_ev=("ev", "mean"), close_ev=("ev_close", "mean"), won=("won", "mean"))
g["return%"] = 100 * g.units / g.risked
g["model_ev%"] = 100 * g.model_ev
g["close_ev%"] = 100 * g.close_ev
print(g[["bets", "risked", "units", "return%", "model_ev%", "close_ev%", "won"]].round(2).to_string())
tot_u, tot_r = u.sum(), r.sum()
print(f"\nall: {len(u)} bets, {tot_r:.1f} units risked ({tot_r/len(u):.2f} a bet), {tot_u:+.1f} units, "
      f"return {100*tot_u/tot_r:+.2f}%; model's own EV at the bet {100*K.ev.mean():+.2f}% "
      f"(median {100*K.ev.median():+.2f}%); EV against Pinnacle's close {100*np.nanmean(K.ev_close):+.2f}%; "
      f"won {K.won.mean():.1%} at a median price {K.price.median():+.0f}")
full = g.loc[[y for y in g.index if 2021 <= y <= 2025]]
per_year_bets = full.bets.mean()
risk_per_bet = tot_r / len(u)
print(f"full seasons 2021-2025: {per_year_bets:.0f} bets a year on average "
      f"(range {full.bets.min():.0f}-{full.bets.max():.0f}); "
      f"2026 (fights to {str(K.loc[K.year == 2026, 'date'].max())[:10]}): {int(g.loc[2026, 'bets'])} bets")
for label, ret in (("backtest return", tot_u / tot_r), ("EV against the close", np.nanmean(K.ev_close)),
                   ("half the backtest return", tot_u / tot_r / 2)):
    print(f"  at the {label} ({100*ret:+.2f}%): {per_year_bets * risk_per_bet * ret:+.1f} units a year "
          f"on {per_year_bets:.0f} bets")
