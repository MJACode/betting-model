"""Share of the shipped rule's bets (168 hours, EV >= 0.06) with a fighter
making his UFC debut. The live card skips a fighter it cannot place on his
ufcstats record, and a debutant has none until after his first fight."""
from pathlib import Path
import pandas as pd
exec(Path(__file__).with_name("feed_kill.py").read_text(encoding="utf-8").split('print("\n-- neighbourhood")')[0]
     .replace("MIN_LEAD = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0", "MIN_LEAD = 168.0"))
Fd = pd.read_parquet("fights.parquet").set_index("game_id")
K = lock(J0, J0.xb.to_numpy(), 0.06)
deb = K.game_id.map((Fd.a_n == 0) | (Fd.b_n == 0)).to_numpy()
u, r = grade(K)
print(f"bets with a debutant: {deb.sum()} of {len(K)} ({deb.mean():.1%}); without them "
      f"{(~deb).sum()} bets {u[~deb].sum():+.1f}u {100*u[~deb].sum()/r[~deb].sum():+.2f}%; "
      f"debut bets alone {100*u[deb].sum()/r[deb].sum():+.2f}%")
