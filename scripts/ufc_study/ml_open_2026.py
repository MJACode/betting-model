"""Is a DECIDABLE book's first stored price as soft as the BestFightOdds open?

Frozen model: the open-anchored ridge fit on every fight through 2025 (BFO
open as the anchor). Scored on 2026 fights at each US book's FIRST stored
pre-fight quote, anchored on that book's own no-vig price, graded at that
quote. Also: when the first stored quote was taken relative to the fight, and
the closing-line value of each bet against the same book's last pre-fight
quote and Pinnacle's last pre-fight no-vig price."""
import re, unicodedata
import numpy as np
import pandas as pd
import ml_anchor as A
from ml_base import units, dec, novig, ci

pd.set_option("display.width", 250)
LAM = float(__import__("sys").argv[1]) if len(__import__("sys").argv) > 1 else 30.0
M = A.M
tr = M[M.year <= 2025]
mu, sd = tr[A.Z].mean(), tr[A.Z].std().replace(0, 1)
b = A.fit(A.prep(tr, mu, sd), A.logit(tr.p_open.to_numpy()), tr.a_won.to_numpy(float), LAM)
print("coefficients", dict(zip(A.Z, np.round(b, 3))))

# fights.parquet holds every 2026 fight with features (including ones without BFO odds)
F = pd.read_parquet("fights.parquet")
F = F[F.date.dt.year == 2026].copy()
for f in A.DIFFS:
    F[f"d_{f}"] = pd.to_numeric(F[f"a_{f}"], errors="coerce") - pd.to_numeric(F[f"b_{f}"], errors="coerce")
F["d_debut"] = (F.a_n == 0).astype(int) - (F.b_n == 0).astype(int)
for z in A.Z:
    F[z] = F[z].astype(float)
F["xb"] = A.prep(F, mu, sd) @ b


def slugify(n):
    n = unicodedata.normalize("NFKD", str(n)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")


F["a_slug"] = F.a_name.map(slugify); F["b_slug"] = F.b_name.map(slugify)
F["pair"] = [frozenset((x, y)) for x, y in zip(F.a_slug, F.b_slug)]

O = pd.read_parquet("ufc_odds.parquet")
O = O[O.market == "h2h"].copy()
for c in ("home_price", "away_price"):
    O[c] = pd.to_numeric(O[c], errors="coerce")
O["snap"] = pd.to_datetime(O.snapshot_at, utc=True, format="mixed")
G = pd.read_parquet("games.parquet").set_index("game_id")
O = O.join(G[["home_team", "away_team", "commence_time"]], on="game_id")
O["ct"] = pd.to_datetime(O.commence_time, utc=True, format="mixed", errors="coerce")
O = O[O.snap <= O.ct]
O["h_slug"] = O.home_team.map(slugify); O["a_slug2"] = O.away_team.map(slugify)
O["pair"] = [frozenset((x, y)) for x, y in zip(O.h_slug, O.a_slug2)]
O["gdate"] = pd.to_datetime(O.game_id.str.split("_").str[1])

# join odds rows to 2026 fights by pair and date within a day
idx = {}
for r in F.itertuples():
    idx.setdefault(r.pair, []).append(r)
def find(pair, d):
    for r in idx.get(pair, []):
        if abs((r.date - d).days) <= 1:
            return r.game_id
    return None
key = O[["pair", "gdate"]].drop_duplicates()
key["fid"] = [find(p, d) for p, d in zip(key.pair, key.gdate)]
O = O.merge(key, on=["pair", "gdate"])
O = O[O.fid.notna()]
O = O.merge(F[["game_id", "a_slug", "xb", "result_a"]], left_on="fid", right_on="game_id", suffixes=("", "_f"))
O = O[O.result_a.isin(["win", "loss"])]
# orient prices to A
a_home = O.h_slug == O.a_slug
O["pa"] = np.where(a_home, O.home_price, O.away_price)
O["pb"] = np.where(a_home, O.away_price, O.home_price)
O["a_won"] = O.result_a == "win"
O = O.sort_values("snap")
print("2026 fights with a US-book quote:", O.fid.nunique())

last = O.groupby(["fid", "bookmaker"]).tail(1).set_index(["fid", "bookmaker"])
pin_last = O[O.bookmaker == "pinnacle"].groupby("fid").tail(1).set_index("fid")
DECIDABLE = ["draftkings", "fanduel", "betmgm", "williamhill_us", "betrivers", "hardrockbet"]
for book in DECIDABLE + ["pinnacle"]:
    first = O[O.bookmaker == book].groupby("fid").head(1).copy()
    if len(first) < 20:
        continue
    lead_h = (first.ct - first.snap).dt.total_seconds() / 3600
    p_anchor = novig(first.pa, first.pb)
    pm = 1 / (1 + np.exp(-(A.logit(p_anchor) + first.xb)))
    ev_a = pm * dec(first.pa) - 1; ev_b = (1 - pm) * dec(first.pb) - 1
    take_a = ev_a >= ev_b
    ev = np.where(take_a, ev_a, ev_b); price = np.where(take_a, first.pa, first.pb)
    won = np.where(take_a, first.a_won, ~first.a_won)
    # CLV vs the same book's last pre-fight quote, and vs Pinnacle's last no-vig
    L = last.reindex(list(zip(first.fid, [book] * len(first))))
    lprice = np.where(take_a, L.pa.to_numpy(), L.pb.to_numpy())
    P = pin_last.reindex(first.fid)
    pin_fair = np.where(take_a, novig(P.pa, P.pb), 1 - novig(P.pa, P.pb))
    print(f"\n{book}: {len(first)} fights, first quote lead median {lead_h.median():.0f}h "
          f"(p10 {lead_h.quantile(.1):.0f}h, p90 {lead_h.quantile(.9):.0f}h)")
    for cut in (0.0, 0.03, 0.06, 0.10):
        s = (ev >= cut) & (price >= -300)
        if s.sum() < 5:
            continue
        u, r = units(price[s], won[s])
        lo, hi = ci(u, r)
        clv_book = np.nanmean(1 / dec(lprice[s]) - 1 / dec(price[s]))
        beat = np.nanmean(dec(price[s]) > dec(lprice[s]))
        clv_pin = np.nanmean(pin_fair[s] * dec(price[s]) - 1)
        print(f"   EV>={cut:.2f}: {s.sum():4d} bets {u.sum():+6.1f}u ret {100*u.sum()/r.sum():+6.1f}% [{lo:+.0f},{hi:+.0f}] "
              f"CLV(implied, own close) {100*clv_book:+.2f}pp beat-close {beat:.0%} EV vs Pinnacle close {100*np.nanmean(clv_pin):+.1f}% "
              f"dogs {np.mean(price[s]>0):.0%}")
