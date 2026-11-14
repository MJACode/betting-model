"""Method-of-victory props (free archive, one price per fighter-method, near
the close): blind bets by method for the favourite and the underdog. Tests
the published lead that 'favourite by decision' is under-priced."""
import numpy as np, pandas as pd
from ml_base import units, ci
from _paths import UUD_CSV
u = pd.read_csv(UUD_CSV, low_memory=False)
u["date"] = pd.to_datetime(u.date); u["year"] = u.date.dt.year
u = u[u.Winner.isin(["Red", "Blue"]) & u.R_odds.notna() & u.B_odds.notna()]
def mcls(f):
    f = str(f).upper()
    return "dec" if f.startswith(("U-DEC","S-DEC","M-DEC","DEC")) else "ko" if "KO" in f else "sub" if "SUB" in f else None
u["m"] = u.finish.map(mcls)
u = u[u.m.notna()]
fav_r = u.R_odds < u.B_odds
rows = []
for who in ("fav", "dog"):
    r_side = fav_r if who == "fav" else ~fav_r
    for m in ("dec", "ko", "sub"):
        price = np.where(r_side, u[f"r_{m}_odds"], u[f"b_{m}_odds"])
        won = (np.where(r_side, u.Winner == "Red", u.Winner == "Blue")) & (u.m == m)
        ok = ~np.isnan(price.astype(float))
        U, R = units(price[ok], won[ok].to_numpy() if hasattr(won,'to_numpy') else won[ok])
        lo, hi = ci(U, R)
        yrs = u.year.to_numpy()[ok]
        by = pd.Series(U).groupby(yrs).sum()/pd.Series(R).groupby(yrs).sum()
        rows.append(dict(bet=f"{who} by {m}", n=ok.sum(), units=round(U.sum(),1), ret=round(100*U.sum()/R.sum(),2),
                         ci90=f"[{lo:+.1f},{hi:+.1f}]", years_pos=f"{(by>0).sum()}/{len(by)}", first=int(yrs.min())))
print(pd.DataFrame(rows).to_string(index=False))
