"""Round totals: a finish-time model from the fight log, priced against the
2026 DraftKings round-total quotes (the only stored totals prices).

Prediction written before running: the books keep most of the margin on the
OVER (blind over -11%, blind under +3 to +5% on 182 DK quotes), so a model of
P(the fight ends before the line) should find its value on unders, in fights
the moneyline says are lopsided and in divisions that finish more.

Fit: one logistic per line (0.5..4.5) on every fight 2010-2025 with the
moneyline's no-vig close as the mismatch input; tested unchanged on 2026."""
import re, unicodedata
import numpy as np
import pandas as pd
from ml_base import load, dec, units, ci, novig
from scipy.optimize import minimize

pd.set_option("display.width", 250)
M = load()                       # fights with BFO prices
F = pd.read_parquet("fights.parquet").set_index("game_id")
M = M.join(F[[c for c in F.columns if c not in M.columns]], on="game_id")
M = M[M.rounds_done.notna()]


def wclass(w):
    w = str(w).lower()
    for k in ("heavyweight", "light heavyweight", "middleweight", "welterweight", "lightweight",
              "featherweight", "bantamweight", "flyweight", "strawweight"):
        if k in w and not (k == "heavyweight" and "light heavyweight" in w):
            return k
    return "other"


M["wc"] = M.weight_class.map(wclass)
M["mismatch"] = (M.p_close - 0.5).abs()
for c in ("fin_rate", "ko_loss", "kd15", "sub15", "td15", "avg_mins", "slpm", "sapm"):
    M[f"s_{c}"] = pd.to_numeric(M[f"a_{c}"], errors="coerce") + pd.to_numeric(M[f"b_{c}"], errors="coerce")
M["five"] = (M.sched == 5).astype(float)
X_COLS = ["mismatch", "women", "five", "s_fin_rate", "s_ko_loss", "s_kd15", "s_sub15", "s_td15", "s_avg_mins",
          "s_slpm", "s_sapm"] + [f"wc_{w}" for w in ("heavyweight", "light heavyweight", "middleweight",
                                                     "welterweight", "featherweight", "bantamweight",
                                                     "flyweight", "strawweight")]
for w in ("heavyweight", "light heavyweight", "middleweight", "welterweight", "featherweight", "bantamweight",
          "flyweight", "strawweight"):
    M[f"wc_{w}"] = (M.wc == w).astype(float)
M["women"] = M.women.astype(float)


def fit(X, y, lam=1.0):
    X1 = np.c_[np.ones(len(X)), X]
    def f(b):
        s = X1 @ b
        return np.sum(np.logaddexp(0, s) - y * s) + lam * np.sum(b[1:] ** 2)
    def g(b):
        s = X1 @ b; p = 1 / (1 + np.exp(-s)); gr = X1.T @ (p - y); gr[1:] += 2 * lam * b[1:]; return gr
    return minimize(f, np.zeros(X1.shape[1]), jac=g, method="L-BFGS-B").x


tr = M[M.year <= 2025]
mu, sd = tr[X_COLS].mean(), tr[X_COLS].std().replace(0, 1)
def Xof(df):
    return ((df[X_COLS] - mu) / sd).fillna(0.0).to_numpy()
coef = {}
for L in (0.5, 1.5, 2.5, 3.5, 4.5):
    t = tr if L < 3 else tr[tr.sched == 5]
    coef[L] = fit(Xof(t), (t.rounds_done > L).to_numpy(float))
def p_over(df, L):
    b = coef[L]
    return 1 / (1 + np.exp(-(b[0] + Xof(df) @ b[1:])))

# 2026 test: DK totals quotes
O = pd.read_parquet("ufc_odds.parquet")
O = O[(O.market == "totals")].copy()
for c in ("total_line", "over_price", "under_price"):
    O[c] = pd.to_numeric(O[c], errors="coerce")
O["snap"] = pd.to_datetime(O.snapshot_at, utc=True, format="mixed")
G = pd.read_parquet("games.parquet").set_index("game_id")
O = O.join(G[["home_team", "away_team", "commence_time"]], on="game_id")
O["ct"] = pd.to_datetime(O.commence_time, utc=True, format="mixed", errors="coerce")
O = O[(O.snap <= O.ct) & O.total_line.notna() & O.over_price.notna() & O.under_price.notna()]


def slugify(n):
    n = unicodedata.normalize("NFKD", str(n)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")


T26 = M[M.year == 2026].copy()
T26["pair"] = [frozenset((slugify(a), slugify(b))) for a, b in zip(T26.a_name, T26.b_name)]
O["pair"] = [frozenset((slugify(a), slugify(b))) for a, b in zip(O.home_team, O.away_team)]
O["gdate"] = pd.to_datetime(O.game_id.str.split("_").str[1])
idx = {}
for r in T26.itertuples():
    idx.setdefault(r.pair, []).append((r.date, r.Index))
def find(p, d):
    for dd, i in idx.get(p, []):
        if abs((dd - d).days) <= 1:
            return i
    return None
key = O[["pair", "gdate"]].drop_duplicates()
key["ix"] = [find(p, d) for p, d in zip(key.pair, key.gdate)]
O = O.merge(key, on=["pair", "gdate"]); O = O[O.ix.notna()]
O["ix"] = O.ix.astype(int)
O = O.join(T26.drop(columns=["pair"]), on="ix", rsuffix="_f")
O["lead_h"] = (O.ct - O.snap).dt.total_seconds() / 3600
O = O[O.lead_h >= 1.0]          # no quote inside the last hour (stale or in-play risk)
print("2026 fights with a totals quote:", O.ix.nunique(), "books", O.bookmaker.value_counts().to_dict())

O["po"] = np.nan
for L in (0.5, 1.5, 2.5, 3.5, 4.5):
    m = O.total_line == L
    if m.any():
        O.loc[m, "po"] = p_over(O[m], L)
O = O[O.po.notna()]
O["ev_o"] = O.po * dec(O.over_price) - 1
O["ev_u"] = (1 - O.po) * dec(O.under_price) - 1
O["push"] = O.rounds_done == O.total_line
O = O[~O.push]
O["over_won"] = O.rounds_done > O.total_line

# calibration of the model on the 2026 DK quotes vs the de-vigged price
D = O[O.bookmaker == "draftkings"].sort_values("snap").groupby("ix").tail(1)
pm = D.po.clip(1e-4, 1 - 1e-4); pk = novig(D.over_price, D.under_price).clip(1e-4, 1 - 1e-4); y = D.over_won.astype(float)
print(f"DK last quote, {len(D)} fights: logloss model {-(y*np.log(pm)+(1-y)*np.log(1-pm)).mean():.4f} "
      f"market {-(y*np.log(pk)+(1-y)*np.log(1-pk)).mean():.4f}")

for book in ("draftkings", "williamhill_us", "pinnacle"):
    for when in ("first", "last"):
        Q = O[O.bookmaker == book].sort_values("snap")
        Q = Q.groupby("ix").head(1) if when == "first" else Q.groupby("ix").tail(1)
        for side in ("under", "over"):
            for cut in (-1.0, 0.0, 0.04, 0.08):
                ev = Q.ev_u if side == "under" else Q.ev_o
                s = ev >= cut
                if s.sum() < 8:
                    continue
                price = (Q.under_price if side == "under" else Q.over_price)[s]
                won = (~Q.over_won if side == "under" else Q.over_won)[s]
                u, r = units(price, won.to_numpy())
                lo, hi = ci(u, r)
                tag = "blind" if cut < -0.5 else f"EV>={cut:.2f}"
                print(f"{book:15} {when:5} {side:5} {tag:8}: {s.sum():3d} bets {u.sum():+6.1f}u ret {100*u.sum()/r.sum():+6.1f}% [{lo:+.0f},{hi:+.0f}]")
