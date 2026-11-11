"""The two live NCAAF in-play models' 2026 record from the picks extract, in
units: one to win, risk capped at 3, at COALESCE(decision_odds, dk_odds).
signal_type BET; condition_status VOID and DUPLICATE excluded."""
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR, WORK  # noqa: E402
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(str(CACHE))
p = pd.read_parquet(D / "ncaaf_picks.parquet")
p = p[p["model_id"].isin(["ncaaf_live_win_prob", "ncaaf_live_total"])]
print("rows by model / signal_type:\n", p.groupby(["model_id", "signal_type"]).size().to_string())
b = p[p["signal_type"] == "BET"].copy()
print("BET rows by condition_status:\n", b.groupby(["model_id", b["condition_status"].fillna("(none)")]).size().to_string())
b = b[~b["condition_status"].isin(["VOID", "DUPLICATE"])]
b["season_year"] = b["game_date"].str.slice(0, 4)
print("BET rows by game_date year:", b.groupby(["model_id", "season_year"]).size().to_dict())
b = b[b["game_date"] >= "2026-08-01"]
print("results:\n", b.groupby(["model_id", b["result"].fillna("(unsettled)")]).size().to_string())
price = pd.to_numeric(b["decision_odds"], errors="coerce").fillna(pd.to_numeric(b["dk_odds"], errors="coerce"))
b["price"] = price
print("settled BETs with no price:", int((b["result"].isin(["WIN", "LOSS", "PUSH"]) & b["price"].isna()).sum()))
s = b[b["result"].isin(["WIN", "LOSS", "PUSH"]) & b["price"].notna()].copy()
d = np.where(s["price"] >= 100, 1 + s["price"] / 100.0, 1 + 100.0 / s["price"].abs())
s["risk"] = np.minimum(1.0 / (d - 1.0), 3.0)
s["units"] = np.where(s["result"] == "WIN", s["risk"] * (d - 1.0), np.where(s["result"] == "LOSS", -s["risk"], 0.0))
for m, g in s.groupby("model_id"):
    w, l, pu = (g["result"] == "WIN").sum(), (g["result"] == "LOSS").sum(), (g["result"] == "PUSH").sum()
    print(f"{m}: {w}-{l}-{pu}, {g['units'].sum():+.2f} units on {g['risk'].sum():.2f} risked "
          f"({g['units'].sum() / g['risk'].sum():+.4f}), {len(g)} settled bets, game dates {g['game_date'].min()} .. "
          f"{g['game_date'].max()}, prices {g['price'].min():.0f} / {g['price'].median():.0f} / {g['price'].max():.0f}")
    for lab, x in (("to 2026-09-18", g[g["game_date"] <= "2026-09-18"]), ("from 2026-09-19", g[g["game_date"] >= "2026-09-19"])):
        if len(x):
            print(f"    {lab}: {(x['result'] == 'WIN').sum()}-{(x['result'] == 'LOSS').sum()}-{(x['result'] == 'PUSH').sum()}, "
                  f"{x['units'].sum():+.2f} units on {x['risk'].sum():.2f} risked")
print("stake_units set on any of these:", int(s["stake_units"].notna().sum()))
