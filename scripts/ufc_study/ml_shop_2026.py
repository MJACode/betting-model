"""2026 pilot of the executable shape: at each stored pull where Pinnacle and a
decidable US book are both quoted (within 5 minutes), anchor the frozen model on
Pinnacle's no-vig price, bet the best decidable price if EV >= cut; the first
qualifying pull locks the fight. Graded at that price; CLV vs Pinnacle's last
pre-fight no-vig. Also the same rule with the model removed (market only)."""
import sys, numpy as np, pandas as pd
from datetime import timedelta
from pathlib import Path
exec(Path(__file__).with_name("ml_open_2026.py").read_text(encoding="utf-8").split("last = O.groupby")[0])
DEC = ["draftkings","fanduel","betmgm","williamhill_us","betrivers","hardrockbet","fliff","ballybet"]
O["slot"] = O.snap.dt.floor("5min")
P = O[O.bookmaker=="pinnacle"].groupby(["fid","slot"]).tail(1)[["fid","slot","pa","pb","snap"]].rename(columns={"pa":"ppa","pb":"ppb","snap":"psnap"})
S = O[O.bookmaker.isin(DEC)]
J = S.merge(P, on=["fid","slot"])
J = J[(J.snap-J.psnap).abs()<=timedelta(minutes=5)]
pin_last = O[O.bookmaker=="pinnacle"].groupby("fid").tail(1).set_index("fid")
J["pfair"] = novig(J.ppa, J.ppb)
J["lead_h"] = (J.ct-J.snap).dt.total_seconds()/3600
for use_model in (True, False):
  for min_lead in (0, 24, 72):
    for cut in (0.0, 0.02, 0.04, 0.06):
        X = J[J.lead_h>=min_lead].copy()
        pm = 1/(1+np.exp(-(A.logit(X.pfair)+(X.xb if use_model else 0))))
        X["eva"]=pm*dec(X.pa)-1; X["evb"]=(1-pm)*dec(X.pb)-1
        X["take_a"]=X.eva>=X.evb; X["ev"]=np.where(X.take_a,X.eva,X.evb); X["price"]=np.where(X.take_a,X.pa,X.pb)
        X=X[(X.ev>=cut)&(X.price>=-300)]
        # best decidable price within the pull for the chosen side, then first pull per fight
        X=X.sort_values(["fid","slot","ev"],ascending=[True,True,False]).groupby(["fid","slot"]).head(1)
        X=X.sort_values("snap").groupby("fid").head(1)
        if len(X)<5: continue
        won=np.where(X.take_a,X.a_won,~X.a_won)
        u,r=units(X.price,won)
        PL=pin_last.reindex(X.fid); pf=np.where(X.take_a,novig(PL.pa,PL.pb),1-novig(PL.pa,PL.pb))
        clv=np.nanmean(pf*dec(X.price)-1)
        lo,hi=ci(u,r)
        print(f"model={use_model!s:5} lead>={min_lead:2}h EV>={cut:.2f}: {len(X):3d} bets {u.sum():+6.1f}u ret {100*u.sum()/r.sum():+6.1f}% [{lo:+.0f},{hi:+.0f}] "
              f"EV vs Pinnacle close {100*clv:+.2f}% median lead {X.lead_h.median():.0f}h dogs {np.mean(X.price>0):.0%}")
