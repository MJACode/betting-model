"""Full-game round 1, step 2b: the market's own accuracy. Prints markdown.

For Pinnacle and DraftKings, the open (each book's first post) and the close
(the board at the last ledger snapshot <= tip - 10 min), on the SAME games
(both books, both reads, per market). Targets: h2h home win (overtime
included); spreads home covers at that quote's own line (pushes dropped);
totals over at its own line (pushes dropped). Probabilities de-vigged: power
for h2h, multiplicative for spreads and totals.

Columns: log loss, Brier, the constant-rate log loss (the sample's own mean
rate, an in-sample floor any line should beat), and the calibration slope and
intercept of logit(P(y)) = a + b * logit(p) (b < 1: the line's favourites are
too short / its probabilities too extreme; b > 1: too timid).
"""
import numpy as np
import pandas as pd
import r2_lib as L

g = L.load_games()
g = g[g.played]
q = L.load_quotes(games=g)
q = q[q.played].copy()
dt = L.decision_times(g)
close = L.board_at(q, dt["close"])
fp = L.first_posts(q)


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def calib(y, p, it=50):
    X = np.column_stack([np.ones(len(p)), logit(p)])
    b = np.array([0.0, 1.0])
    for _ in range(it):
        z = X @ b
        mu = 1 / (1 + np.exp(-z))
        W = mu * (1 - mu)
        H = X.T @ (X * W[:, None])
        gr = X.T @ (y - mu)
        step = np.linalg.solve(H, gr)
        b = b + step
        if np.abs(step).max() < 1e-10:
            break
    cov = np.linalg.inv(H)
    return b[0], b[1], np.sqrt(cov[1, 1])


def target(z, market):
    if market == "h2h":
        return (z.margin > 0).astype(float), z.pa_pow
    if market == "spreads":
        c = z.margin + z.line
        return np.where(c == 0, np.nan, (c > 0).astype(float)), z.pa_mult
    c = z.total - z.line
    return np.where(c == 0, np.nan, (c > 0).astype(float)), z.pa_mult


rows = []
for market in L.MARKETS:
    parts = {}
    for read, b in (("open", fp), ("close", close)):
        for book in ("pinnacle", "draftkings"):
            z = b[(b.market == market) & (b.bookmaker == book)].copy()
            y, p = target(z, market)
            z["y"] = y
            z["p"] = np.asarray(p, float)
            parts[(read, book)] = z.set_index("game_id")
    common = set.intersection(*[set(v.index) for v in parts.values()])
    for (read, book), z in parts.items():
        for scope in ("all", "season"):
            zz = z.loc[sorted(common)]
            groups = [("all", zz)] if scope == "all" else list(zz.groupby("season"))
            for sname, x in groups:
                x = x[np.isfinite(x.y)]
                y = x.y.to_numpy()
                p = np.clip(x.p.to_numpy(), 1e-6, 1 - 1e-6)
                ll = -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
                br = np.mean((p - y) ** 2)
                r = y.mean()
                ll0 = -(r * np.log(r) + (1 - r) * np.log(1 - r))
                a, s, se = calib(y, p)
                rows.append({"market": market, "season": sname if sname == "all" else int(sname),
                             "read": read, "book": book, "n": len(x), "logloss": ll, "brier": br,
                             "const_logloss": ll0, "calib_slope": s, "slope_se": se, "calib_icpt": a,
                             "mean_p": float(p.mean()), "mean_y": float(r)})
t = pd.DataFrame(rows)
print("## r2_accuracy.py\n")
print("### The open and the close, Pinnacle and DraftKings, on the same games (pooled)\n")
print(L.md_table(t[t.season == "all"].drop(columns="season")))
print("\n### By season\n")
print(L.md_table(t[t.season != "all"].sort_values(["market", "season", "read", "book"])))

# how stale is each book's close (minutes from its last change to tip)
x = close[close.bookmaker.isin(["pinnacle", "draftkings"])]
x = x.assign(stale_min=(x.tip - x.snapshot_at).dt.total_seconds() / 60)
s = x.groupby(["market", "bookmaker"]).stale_min.quantile([.25, .5, .75]).unstack().round(0).reset_index()
print("\n### The close's age: minutes from the book's last change to the tip, at the close read\n")
print(L.md_table(s))
