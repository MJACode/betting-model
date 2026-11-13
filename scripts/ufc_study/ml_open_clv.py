"""Historical open-anchored bets: EV against the no-vig close (mid), i.e. does
the model at the open predict the line's move. Walk-forward, ridge 30."""
import numpy as np, pandas as pd
import ml_anchor as A
from ml_base import dec, novig, units, ci
T = A.walk("open", 30.0)
pm = T.p_model
ev_a = pm*dec(T.a_open)-1; ev_b = (1-pm)*dec(T.b_open)-1
take_a = ev_a >= ev_b
ev = np.where(take_a, ev_a, ev_b); price = np.where(take_a, T.a_open, T.b_open)
fair_close = np.where(take_a, T.p_close, 1-T.p_close)
won = np.where(take_a, T.a_won, ~T.a_won)
# the open's own margin
ov = 1/dec(T.a_open)+1/dec(T.b_open)-1
cv = 1/dec(T.a_close_mid)+1/dec(T.b_close_mid)-1
print("median margin open %.3f close-mid %.3f" % (np.median(ov), np.median(cv)))
for cut in (0.0, 0.03, 0.06, 0.10):
    s = (ev>=cut)&(price>=-300)
    u,r = units(price[s], won[s]); lo,hi = ci(u,r)
    print(f"EV>={cut:.2f} {s.sum()} bets ret {100*u.sum()/r.sum():+.1f}% [{lo:+.1f},{hi:+.1f}]  EV vs no-vig close {100*np.mean(fair_close[s]*dec(price[s])-1):+.2f}%  "
          f"beat close-mid {np.mean(dec(price[s])>dec(np.where(take_a,T.a_close_mid,T.b_close_mid)[s])):.0%}")
# by year at EV>=0.06
s=(ev>=0.06)&(price>=-300)
u,r=units(price[s],won[s])
d=pd.DataFrame(dict(y=T.year.to_numpy()[s],u=u,r=r,clv=fair_close[s]*dec(price[s])-1))
g=d.groupby('y').agg(n=('u','size'),u=('u','sum'),r=('r','sum'),clv=('clv','mean')); g['ret']=100*g.u/g.r; g['clv']*=100
print(g.round(2).to_string())
