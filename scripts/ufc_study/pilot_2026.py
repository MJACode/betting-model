"""Market-structure pilot on the stored 2026 UFC odds (June-Nov 2026).

Pilot only: ~300 fights resolves a return to roughly +-12 points, so nothing
here is a verdict. Prints: identity match rate, blind favourite / underdog by
price band at the first and last pre-fight quote, the Pinnacle-vs-soft
same-snapshot rule, and blind over / under by round line.
"""
import numpy as np
import pandas as pd
from datetime import timedelta

pd.set_option("display.width", 250)
O = pd.read_parquet("ufc_odds.parquet")
G = pd.read_parquet("games.parquet")
FL = pd.read_parquet("fight_log.parquet")

O["snap"] = pd.to_datetime(O.snapshot_at, utc=True, format="mixed")
for c in ("home_price","away_price","total_line","over_price","under_price"):
    O[c] = pd.to_numeric(O[c], errors="coerce")
G["ct"] = pd.to_datetime(G.commence_time, utc=True, format="mixed", errors="coerce")


def slug_pair(gid):
    p = gid.split("_")
    return p[1], frozenset(p[2:4]) if len(p) == 4 else None


# fight results: one row per fight from the fight log
fl = FL.copy()
fl["d"] = pd.to_datetime(fl.game_date)
for c in ("end_round","end_time_sec","scheduled_rounds"):
    FL[c] = pd.to_numeric(FL[c], errors="coerce"); fl[c] = pd.to_numeric(fl[c], errors="coerce")
first = fl.sort_values("log_id").drop_duplicates("game_id")
res = {}
for r in first.itertuples():
    d, pair = slug_pair(r.game_id)
    res.setdefault(pair, []).append(r)

# winner per game: fighter_name with result == win
win = FL[FL.result == "win"].set_index("game_id").fighter_name.to_dict()

def find(gid):
    d, pair = slug_pair(gid)
    d = pd.Timestamp(d)
    for r in res.get(pair, []):
        if abs((r.d - d).days) <= 1:
            return r
    return None

import unicodedata, re
def slugify(n):
    n = unicodedata.normalize("NFKD", str(n)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")

gmeta = G.set_index("game_id")[["home_team", "away_team", "ct", "game_date"]]
ids = O.game_id.unique()
rows = []
for gid in ids:
    r = find(gid)
    if gid not in gmeta.index:
        continue
    m = gmeta.loc[gid]
    rows.append(dict(game_id=gid, home=m.home_team, away=m.away_team, ct=m.ct,
                     matched=r is not None,
                     fl_gid=None if r is None else r.game_id,
                     method=None if r is None else r.method,
                     end_round=None if r is None else r.end_round,
                     end_time=None if r is None else r.end_time_sec,
                     sched=None if r is None else r.scheduled_rounds,
                     winner=None if r is None else win.get(r.game_id)))
F = pd.DataFrame(rows)
print("odds game ids", len(ids), "with games row", len(F), "matched to a UFC result", F.matched.sum(),
      "distinct fights", F.fl_gid.nunique(), "ct missing", F.ct.isna().sum())
F = F[F.matched & F.ct.notna()].copy()
F["home_won"] = [None if w is None else (slugify(w) == slugify(h)) if slugify(w) in (slugify(h), slugify(a)) else None
                 for w, h, a in zip(F.winner, F.home, F.away)]
print("winner resolvable", F.home_won.notna().sum(), "draw/nc", F.winner.isna().sum())

# pre-fight quotes only
O2 = O.merge(F[["game_id", "ct", "fl_gid"]], on="game_id")
O2 = O2[O2.snap <= O2.ct]
print("pre-fight rows", len(O2), "of", len(O))


def dec(a):
    a = np.asarray(a, float)
    return np.where(a > 0, 1 + a / 100, 1 + 100 / -a)

def units(price, won):
    """1 unit to win, risk capped at 3 (the published stake)."""
    d = dec(price)
    risk = np.minimum(1 / (d - 1), 3.0)
    return np.where(won, risk * (d - 1), -risk), risk

# ── moneyline: one quote per fight per book at first and last pre-fight pull
H = O2[(O2.market == "h2h") & O2.home_price.notna() & O2.away_price.notna()].copy()
H = H.sort_values("snap")
H = H.merge(F[["game_id", "home_won"]], on="game_id")
H = H[H.home_won.notna()]
# de-duplicate the fight across orientation twins: keep one game id per fight
keep = F.drop_duplicates("fl_gid").game_id
H = H[H.game_id.isin(keep)]


def blind(tbl, label):
    out = []
    for when, g in (("first", tbl.groupby(["game_id", "bookmaker"]).head(1)),
                    ("last", tbl.groupby(["game_id", "bookmaker"]).tail(1))):
        g = g[g.bookmaker == "draftkings"]
        fav_home = g.home_price < g.away_price
        fav_price = np.where(fav_home, g.home_price, g.away_price)
        dog_price = np.where(fav_home, g.away_price, g.home_price)
        fav_won = np.where(fav_home, g.home_won, ~g.home_won.astype(bool))
        for side, price, won in (("fav", fav_price, fav_won.astype(bool)), ("dog", dog_price, ~fav_won.astype(bool))):
            band = pd.cut(price, [-100000, -400, -250, -150, -100, 0, 150, 250, 400, 100000])
            u, risk = units(price, won)
            d = pd.DataFrame(dict(band=band, u=u, risk=risk, won=won))
            s = d.groupby("band", observed=True).agg(n=("u", "size"), units=("u", "sum"), risk=("risk", "sum"))
            s["ret%"] = 100 * s.units / s.risk
            s.insert(0, "side", side); s.insert(0, "when", when)
            out.append(s)
            tot_u, tot_r = u.sum(), risk.sum()
            print(f"{label} DK {when:5} blind {side}: {len(u)} bets {tot_u:+.2f}u ret {100*tot_u/tot_r:+.1f}%")
    return pd.concat(out)

print(blind(H, "ML"))

# ── Pinnacle vs soft, same snapshot: de-vig Pinnacle, bet a decidable soft book
#    whose price beats Pinnacle's fair price by EV >= cut.
DECIDABLE = {"draftkings", "fanduel", "betmgm", "williamhill_us", "betrivers", "hardrockbet", "fliff", "ballybet"}
P = H[H.bookmaker == "pinnacle"][["game_id", "snap", "home_price", "away_price"]].rename(
    columns={"home_price": "ph", "away_price": "pa", "snap": "psnap"})
S = H[H.bookmaker.isin(DECIDABLE)]
J = S.merge(P, on="game_id")
J = J[(J.snap - J.psnap).abs() <= timedelta(seconds=300)]
ih, ia = 1 / dec(J.ph), 1 / dec(J.pa)
J["fh"] = ih / (ih + ia); J["fa"] = 1 - J.fh
J["ev_h"] = J.fh * dec(J.home_price) - 1
J["ev_a"] = J.fa * dec(J.away_price) - 1
for cut in (0.0, 0.02, 0.04, 0.06):
    # first qualifying quote per fight (the lock), either side
    c = []
    for side in ("h", "a"):
        q = J[J[f"ev_{side}"] >= cut].copy()
        q["side"] = side
        q["price"] = q.home_price if side == "h" else q.away_price
        q["won"] = q.home_won.astype(bool) if side == "h" else ~q.home_won.astype(bool)
        q["ev"] = q[f"ev_{side}"]
        c.append(q)
    q = pd.concat(c).sort_values("snap").groupby("game_id").head(1)
    q = q[q.price >= -300]
    u, risk = units(q.price, q.won)
    se = np.std(u, ddof=1) / np.sqrt(len(u)) if len(u) > 1 else np.nan
    print(f"ML pinnacle-vs-soft EV>={cut:.2f}: {len(q)} bets {u.sum():+.2f}u ret {100*u.sum()/risk.sum():+.1f}% "
          f"(se/bet {se:.2f}u) dogs {(q.price>0).mean():.0%} books {q.bookmaker.value_counts().to_dict()}")

# ── totals: blind over / under at DK, first and last
T = O2[(O2.market == "totals") & O2.total_line.notna() & O2.over_price.notna()].copy().sort_values("snap")
T = T[T.game_id.isin(keep)].merge(F[["game_id", "end_round", "end_time", "sched"]], on="game_id")
T["rc"] = (T.end_round - 1) + T.end_time / 300.0
for when, g in (("first", T.groupby(["game_id", "bookmaker"]).head(1)),
                ("last", T.groupby(["game_id", "bookmaker"]).tail(1))):
    g = g[g.bookmaker == "draftkings"]
    g = g[g.rc.notna() & (g.rc != g.total_line)]
    for side in ("over", "under"):
        won = (g.rc > g.total_line) if side == "over" else (g.rc < g.total_line)
        price = g.over_price if side == "over" else g.under_price
        u, risk = units(price, won.values)
        print(f"TOT DK {when:5} blind {side:5}: {len(u)} bets {u.sum():+.2f}u ret {100*u.sum()/risk.sum():+.1f}%  "
              f"lines {g.total_line.value_counts().to_dict()}")
F.to_parquet("fights_2026.parquet")
