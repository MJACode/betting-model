"""The question the purchase was bought for: does a book WE CAN BET carry the
open-anchored edge (docs/ufc_market_audit.md section 3c)? And round totals
at real prices for the first time.

Moneyline, walk-forward by year: the rating model fitted only on earlier
years (anchored on BestFightOdds' open, ridge 30, as ml_anchor.py), applied
unchanged to the bought quotes of year Y.
  A. Each decidable book's FIRST daily price for a fight, anchored on that
     book's own no-vig price, graded at it.
  B. Pinnacle-anchored: at every daily or card-day pull where Pinnacle and a
     decidable book both quote the fight, the best decidable price; the first
     pull that clears locks the fight (at least an hour before the start).
  Each with the market alone (no model) as the control row, and EV against
  Pinnacle's last pre-fight no-vig price as the closing-line witness.
Round totals: blind over and under by book at the first and last pull, and
DraftKings against Pinnacle's no-vig price at the same line in the same pull.

Run from the study folder after feed_quotes.py."""
import numpy as np
import pandas as pd

import ml_anchor as A
from ml_base import ci, dec, novig, units

pd.set_option("display.width", 250)
DECIDABLE = ["draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics", "betrivers",
             "hardrockbet"]
CUTS = (0.0, 0.03, 0.06, 0.10)
FLOOR = -300

Q = pd.read_parquet("feed_quotes.parquet")
Q["served_at"] = pd.to_datetime(Q.served_at, utc=True)
Q["commence"] = pd.to_datetime(Q.commence, utc=True)
start = Q.groupby("game_id").commence.max()
Q["start"] = Q.game_id.map(start)
Q = Q[Q.served_at <= Q.start].copy()
Q["lead_h"] = (Q.start - Q.served_at).dt.total_seconds() / 3600

F = pd.read_parquet("fights.parquet").set_index("game_id")
for f in A.DIFFS:
    F[f"d_{f}"] = pd.to_numeric(F[f"a_{f}"], errors="coerce") - pd.to_numeric(F[f"b_{f}"], errors="coerce")
F["d_debut"] = (F.a_n == 0).astype(int) - (F.b_n == 0).astype(int)
for z in A.Z:
    F[z] = F[z].astype(float)
F["year"] = F.date.dt.year
F = F[F.result_a.isin(["win", "loss"])]
F["a_won"] = F.result_a == "win"

# walk-forward opinion b.z per fight: fitted on the archive's years before it
xb = {}
for Y in sorted(F.year.unique()):
    if Y < 2020:
        continue
    tr = A.M[A.M.year < Y]
    mu, sd = tr[A.Z].mean(), tr[A.Z].std().replace(0, 1)
    b = A.fit(A.prep(tr, mu, sd), A.logit(tr.p_open.to_numpy()), tr.a_won.to_numpy(float), 30.0)
    te = F[F.year == Y]
    xb.update(dict(zip(te.index, A.prep(te, mu, sd) @ b)))
F["xb"] = pd.Series(xb)

H2 = Q[(Q.market == "h2h") & Q.pa.notna() & Q.pb.notna()].join(F[["xb", "a_won", "year", "date"]], on="game_id")
H2 = H2[H2.xb.notna()].sort_values("served_at")
pin_close = H2[H2.book == "pinnacle"].groupby("game_id").tail(1).set_index("game_id")
pin_fair_a = novig(pin_close.pa, pin_close.pb)
pin_fair_a = pd.Series(pin_fair_a, index=pin_close.index)
print(f"fights with a decidable first price: {H2[H2.book.isin(DECIDABLE)].game_id.nunique()}, "
      f"with a Pinnacle close: {len(pin_close)}; years {sorted(H2.year.unique())}")


def decide(X, anchor_a, use_model):
    pm = 1 / (1 + np.exp(-(A.logit(np.clip(anchor_a, 1e-6, 1 - 1e-6)) + (X.xb.to_numpy() if use_model else 0))))
    ea, eb = pm * dec(X.pa) - 1, (1 - pm) * dec(X.pb) - 1
    ta = ea >= eb
    return ta, np.where(ta, ea, eb), np.where(ta, X.pa, X.pb)


def report(label, X, ta, price):
    won = np.where(ta, X.a_won, ~X.a_won.astype(bool))
    u, r = units(price, won)
    lo, hi = ci(u, r)
    fair = X.game_id.map(pin_fair_a).to_numpy()
    side_fair = np.where(ta, fair, 1 - fair)
    clv = np.nanmean(side_fair * dec(price) - 1)
    has = np.isfinite(side_fair).mean()
    d = pd.to_datetime(X.date).astype("int64").to_numpy()
    e = d <= np.median(d)
    yrs = X.year.to_numpy()
    by = pd.Series(u).groupby(yrs).sum() / pd.Series(r).groupby(yrs).sum()
    print(f"{label:44} {len(u):5d} bets {u.sum():+7.1f}u {100*u.sum()/r.sum():+6.2f}% [{lo:+.1f},{hi:+.1f}] "
          f"vs Pinnacle close {100*clv:+.2f}% ({has:.0%} have one) early {100*u[e].sum()/r[e].sum():+.1f}% "
          f"late {100*u[~e].sum()/r[~e].sum():+.1f}% years+ {(by>0).sum()}/{len(by)} dogs {np.mean(price>0):.0%}")


print("\n== A. each decidable book's first daily price, anchored on itself")
for book in DECIDABLE + ["pinnacle"]:
    X = H2[(H2.book == book) & (H2.lead_h >= 1)].groupby("game_id").head(1)
    if len(X) < 50:
        continue
    for use_model in (False, True):
        ta, ev, price = decide(X, novig(X.pa, X.pb), use_model)
        for cut in (CUTS if use_model else (0.0,)):
            s = (ev >= cut) & (price >= FLOOR)
            if s.sum() >= 20:
                tag = f"{book} first, {'model' if use_model else 'market only'} EV>={cut:.2f}"
                report(tag, X[s], ta[s], price[s])
    print(f"   {book}: first price a median {X.lead_h.median()/24:.1f} days before the fight")

print("\n== B. Pinnacle-anchored, best decidable price in the same pull, first clearing pull locks")
P = H2[H2.book == "pinnacle"][["game_id", "served_at", "pa", "pb"]].rename(columns={"pa": "qa", "pb": "qb"})
S = H2[H2.book.isin(DECIDABLE) & (H2.lead_h >= 1)]
J = S.merge(P, on=["game_id", "served_at"])
for use_model in (False, True):
    for cut in (CUTS if use_model else (0.0, 0.02)):
        ta, ev, price = decide(J, novig(J.qa, J.qb), use_model)
        K = J.assign(ta=ta, ev=ev, price=price)
        K = K[(K.ev >= cut) & (K.price >= FLOOR)]
        K = K.sort_values(["served_at", "ev"], ascending=[True, False]).groupby("game_id").head(1)
        if len(K) >= 20:
            report(f"Pinnacle-anchored, {'model' if use_model else 'market only'} EV>={cut:.2f}",
                   K, K.ta.to_numpy(), K.price.to_numpy())

print("\n== Round totals")
T = Q[(Q.market == "totals") & Q.line.notna() & Q.over.notna() & Q.under.notna() & (Q.lead_h >= 1)]
T = T.join(F[["rounds_done", "year", "date"]], on="game_id")
T = T[T.rounds_done.notna() & (T.rounds_done != T.line)].sort_values("served_at")
for book in ("draftkings", "pinnacle", "williamhill_us", "fanduel", "betmgm"):
    for when in ("first", "last"):
        X = T[T.book == book]
        X = X.groupby("game_id").head(1) if when == "first" else X.groupby("game_id").tail(1)
        if len(X) < 50:
            continue
        for side in ("under", "over"):
            won = (X.rounds_done < X.line) if side == "under" else (X.rounds_done > X.line)
            price = (X.under if side == "under" else X.over).to_numpy()
            u, r = units(price, won.to_numpy())
            lo, hi = ci(u, r)
            print(f"{book:15} {when:5} blind {side:5}: {len(u):5d} bets {u.sum():+7.1f}u "
                  f"{100*u.sum()/r.sum():+6.2f}% [{lo:+.1f},{hi:+.1f}]")
PT = T[T.book == "pinnacle"][["game_id", "served_at", "line", "over", "under"]].rename(
    columns={"over": "po", "under": "pu"})
for book in ("draftkings", "williamhill_us", "fanduel", "betmgm"):
    J = T[T.book == book].merge(PT, on=["game_id", "served_at", "line"])
    if len(J) < 50:
        continue
    fu = novig(J.pu, J.po)
    for side in ("under", "over"):
        fair = fu if side == "under" else 1 - fu
        price = (J.under if side == "under" else J.over).to_numpy()
        ev = fair * dec(price) - 1
        for cut in (0.0, 0.02, 0.04):
            K = J.assign(ev=ev, price=price)
            K = K[K.ev >= cut].groupby("game_id").head(1)
            if len(K) < 20:
                continue
            won = (K.rounds_done < K.line) if side == "under" else (K.rounds_done > K.line)
            u, r = units(K.price.to_numpy(), won.to_numpy())
            lo, hi = ci(u, r)
            print(f"{book} {side} vs Pinnacle same line EV>={cut:.2f}: {len(u):4d} bets {u.sum():+6.1f}u "
                  f"{100*u.sum()/r.sum():+6.2f}% [{lo:+.1f},{hi:+.1f}]")
