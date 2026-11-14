"""The shipped rule's bets in the backtest, as picks: fighter, opponent, the
price and book taken, days before the fight, the model's chance against the
price's, and the result. Prints the 2026 bets, then the share by side and
price. Run from the study folder."""
from pathlib import Path

import numpy as np
import pandas as pd

exec(Path(__file__).with_name("feed_kill.py").read_text(encoding="utf-8").split('print("\\n-- neighbourhood")')[0]
     .replace("MIN_LEAD = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0", "MIN_LEAD = 168.0"))
K = lock(J0, J0.xb.to_numpy(), 0.06, stages=["daily"])
u, r = grade(K)
Fx = pd.read_parquet("fights.parquet").set_index("game_id")
K = K.assign(u=u)
K["pick"] = np.where(K.ta, K.game_id.map(Fx.a_name), K.game_id.map(Fx.b_name))
K["vs"] = np.where(K.ta, K.game_id.map(Fx.b_name), K.game_id.map(Fx.a_name))
K["fav"] = np.where(K.price < 0, "favourite", "underdog")
K["implied"] = 1 / dec(K.price.to_numpy())
pm = 1 / (1 + np.exp(-(A.logit(np.clip(novig(K.qa, K.qb), 1e-6, 1 - 1e-6)) + K.xb)))
K["model"] = np.where(K.ta, pm, 1 - pm)
K["won"] = np.where(K.ta, K.a_won, ~K.a_won.astype(bool))
show = K[K.year == 2026].sort_values("date")
for x in show.itertuples():
    print(f"{str(x.date)[:10]}  {x.pick} over {x.vs}: {x.price:+.0f} at {x.book}, "
          f"{x.lead_h/24:.0f} days out; model {x.model:.0%} vs price {x.implied:.0%} "
          f"(EV {x.ev:+.0%}) -> {'WON' if x.won else 'lost'} {x.u:+.2f}u")
print(f"\n{len(show)} bets in 2026 (fights to {str(show.date.max())[:10]}); all years: {len(K)} bets, "
      f"{(K.price > 0).mean():.0%} underdogs, median price {K.price.median():+.0f}")
print(K.groupby("fav").agg(bets=("u", "size"), units=("u", "sum"), won=("won", "mean")).round(2).to_string())
