"""Full-game round 1, step 2: the blind baselines. Prints markdown.

Reads (r2_lib docstring): first = each book's first post; close = the board at
the last ledger snapshot <= tip - 10 min. Books: DraftKings alone, and the best
decidable price (h2h: best price per side across the five decidable books;
spreads / totals: the modal decidable number, ties nearest the median then the
lower, and the best price on it). At the first post the best-decidable board
is read at the first ledger moment every decidable book that ever quotes the
game's market has posted (one moment; in 2021-22 to 2024-25 that is
DraftKings' first post). Sides: home, away, favourite, underdog (h2h and
spreads), over, under (totals). Neutral-site games are included here (a
blind bet on a quote does not depend on "home" meaning anything); the home
baselines in r2_leads.py exclude them.
"""
import numpy as np
import pandas as pd
import r2_lib as L

g = L.load_games()
g = g[g.played]
q = L.load_quotes(games=g)
q = q[q.played].copy()
q["seen"] = L.seen_at(q.snapshot_at)
dt = L.decision_times(g)


def board_gm(q, T):
    """T: DataFrame game_id, market, T. Last row per (game, market, book) with snapshot_at <= T."""
    z = q.merge(T, on=["game_id", "market"], how="inner")
    z = z[z.snapshot_at <= z["T"]]
    return z.drop_duplicates(["game_id", "market", "bookmaker"], keep="last")


def modal_line(b):
    """Per (game, market): the modal line, ties nearest the median, then the lower."""
    out = {}
    for (gid, m), x in b.groupby(["game_id", "market"]):
        vc = x.line.value_counts()
        top = vc[vc == vc.max()].index.to_numpy(float)
        med = float(np.median(x.line))
        top = sorted(top, key=lambda v: (abs(v - med), v))
        out[(gid, m)] = top[0]
    return pd.Series(out, name="mline")


def sides_of(b, market):
    """Two side rows per quote: side, price, fav flag (by the quote's own prices / line)."""
    z = L.sides_long(b[b.market == market])
    if market == "h2h":
        z["fav"] = np.where(z.side == "home", z.pa_pow > 0.5, z.pa_pow < 0.5)
        z["dog"] = np.where(z.side == "home", z.pa_pow < 0.5, z.pa_pow > 0.5)
    elif market == "spreads":
        z["fav"] = np.where(z.side == "home", z.line < 0, z.line > 0)
        z["dog"] = np.where(z.side == "home", z.line > 0, z.line < 0)
    else:
        z["fav"] = False
        z["dog"] = False
    return z


def best_decidable(b, market):
    """The best decidable price per side (see the docstring)."""
    d = b[(b.market == market) & b.bookmaker.isin(L.DECIDABLE)]
    if market != "h2h":
        ml = modal_line(d)
        d = d.merge(ml.rename_axis(["game_id", "market"]).reset_index(), on=["game_id", "market"])
        d = d[d.line == d.mline]
    z = L.sides_long(d)
    z["dz"] = L.dec(z.price)
    z = z.sort_values(["game_id", "side", "dz", "bookmaker"], ascending=[True, True, False, True])
    z = z.drop_duplicates(["game_id", "side"], keep="first").copy()
    if market == "h2h":
        # favourite = the side whose best price is shorter
        piv = z.pivot_table(index="game_id", columns="side", values="dz")
        hf = (piv["home"] < piv["away"]).rename("hf")
        af = (piv["home"] > piv["away"]).rename("af")
        z = z.merge(hf, left_on="game_id", right_index=True).merge(af, left_on="game_id", right_index=True)
        z["fav"] = np.where(z.side == "home", z.hf, z.af)
        z["dog"] = np.where(z.side == "home", z.af, z.hf)
    elif market == "spreads":
        z["fav"] = np.where(z.side == "home", z.line < 0, z.line > 0)
        z["dog"] = np.where(z.side == "home", z.line > 0, z.line < 0)
    else:
        z["fav"] = False
        z["dog"] = False
    return z


SIDESETS = {"h2h": ["home", "away", "fav", "dog"], "spreads": ["home", "away", "fav", "dog"],
            "totals": ["over", "under"]}


def pick(z, s):
    if s in ("fav", "dog"):
        return z[z[s].astype(bool)]
    return z[z.side == s]


# the boards
close_T = dt["close"].rename("T").reset_index().rename(columns={"index": "game_id"})
close_T = pd.concat([close_T.assign(market=m) for m in L.MARKETS])
close = board_gm(q, close_T)
fp = L.first_posts(q)
dfp = fp[fp.bookmaker.isin(L.DECIDABLE)].groupby(["game_id", "market"]).seen.max().rename("T").reset_index()
first_full = board_gm(q, dfp)

rows, srows = [], []
for market in L.MARKETS:
    sets = {
        ("first", "draftkings"): sides_of(fp[fp.bookmaker == "draftkings"], market),
        ("first", "best decidable"): best_decidable(first_full, market),
        ("close", "draftkings"): sides_of(close[close.bookmaker == "draftkings"], market),
        ("close", "best decidable"): best_decidable(close, market),
    }
    for (read, book), z in sets.items():
        z = L.grade(z)
        for s in SIDESETS[market]:
            x = pick(z, s)
            rows.append(L.row({"market": market, "read": read, "book": book, "side": s, "season": "all"}, x))
            for season, xs in x.groupby("season"):
                srows.append(L.row({"market": market, "read": read, "book": book, "side": s, "season": int(season)}, xs))
        if market == "h2h":
            # the repo's -200 floor on the favourite
            x = pick(z, "fav")
            x = x[x.price >= -200]
            rows.append(L.row({"market": market, "read": read, "book": book, "side": "fav, -200 floor", "season": "all"}, x))
        rows.append(L.row({"market": market, "read": read, "book": book, "side": "every quote both ways", "season": "all"}, z))

print("## r2_baselines.py\n")
print("### Blind baselines, pooled 2021-22 to 2026-27 (return = units / units risked; 90% interval resampling dates)\n")
print(L.md_table(pd.DataFrame(rows)))
print("\n### Blind baselines by season\n")
print(L.md_table(pd.DataFrame(srows)))

# moneyline price bands
brows = []
for read, book, z in [("close", "draftkings", sides_of(close[close.bookmaker == "draftkings"], "h2h")),
                      ("close", "best decidable", best_decidable(close, "h2h")),
                      ("first", "draftkings", sides_of(fp[fp.bookmaker == "draftkings"], "h2h")),
                      ("close", "pinnacle (reference, not bettable)", sides_of(close[close.bookmaker == "pinnacle"], "h2h"))]:
    z = L.grade(z)
    z["band"] = L.ml_band(z.price)
    for band in L.BANDS:
        x = z[z.band == band]
        r = L.row({"read": read, "book": book, "band": band}, x)
        r["mean_fair%"] = round(100 * float(x.fair.mean()), 2) if len(x) else np.nan
        r["win%"] = round(100 * float((x.res > 0).mean()), 2) if len(x) else np.nan
        brows.append(r)
print("\n### Moneyline sides by price band (every side, unfloored), pooled seasons\n")
print(L.md_table(pd.DataFrame(brows)))

# by band and season at the DK close
z = L.grade(sides_of(close[close.bookmaker == "draftkings"], "h2h"))
z["band"] = L.ml_band(z.price)
t = []
for (band, season), x in z.groupby(["band", "season"]):
    t.append(L.row({"band": band, "season": int(season)}, x))
print("\n### DraftKings close moneyline sides, band by season\n")
print(L.md_table(pd.DataFrame(t).sort_values(["band", "season"])))

# the sample resolution
print("\n### What the sample resolves\n")
for market in L.MARKETS:
    z = L.grade(sides_of(close[close.bookmaker == "draftkings"], market))
    x = pick(z, "home" if market != "totals" else "over")
    x = x[x.res != 0]
    per = x.units / x.risk
    n = len(x)
    hw = 1.645 * per.std() / np.sqrt(n) * 100
    print(f"- {market}: one side at the DraftKings close, {n} graded bets; per-bet return sd {per.std():.3f}; "
          f"90% half-width of a return = +/-{hw:.1f} points (2,700 bets of the same sd: +/-{1.645 * per.std() / np.sqrt(2700) * 100:.1f})")
