import sys
from pathlib import Path

import pandas as pd

from paths import CACHE as D  # noqa: E402
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)
pd.set_option("display.max_rows", 400)
f = sys.argv[1] if len(sys.argv) > 1 else "lab_results.csv"
R = pd.read_csv(D / f)
R = R[R.bets > 0]
R["cell"] = (R.bets.astype(int).astype(str) + " " + R.units.map("{:+.1f}u".format) + " " + R.roi.map("{:+.1f}%".format)
             + " [" + R.lo.map("{:.0f}".format) + "," + R.hi.map("{:.0f}".format) + "] cv" + R.ev_close.map("{:+.1f}".format))
order = ["D0_AM", "D0_PM", "D1_PM", "D1_AM", "D2_AM", "D3_AM", "D4_AM", "D5_AM"]
for rule, x in R.groupby("rule"):
    print(f"\n===== {rule}: bets units ROI [95% interval] cv=value at the close, % a bet =====")
    t = x.pivot(index="slot", columns="cut", values="cell").reindex([o for o in order if o in set(x.slot)])
    print(t.to_string())
if len(sys.argv) > 2:
    rule, slot = sys.argv[2], sys.argv[3]
    x = R[(R.rule == rule) & (R.slot == slot)]
    print(x[["cut", "bets", "rec", "units", "roi", "clv_pts", "med_price", "ex10", "seasons", "halves"]].to_string(index=False))
