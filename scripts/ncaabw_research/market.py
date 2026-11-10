"""Women's full-game spread and moneyline, the men's two market rules on the
women's boards.

SPREAD (the men's ncaab_spread_market): at a fixed lead before the tip, every
book's spread; the consensus is the median line; one bettable book's quote
priced against it; bet the best quote when its edge clears the cut and at
least three other books quote the game.

MONEYLINE (the men's ncaab_moneyline_own_spread): each bettable book's
moneyline priced off that same book's spread; sides shorter than -200 removed
first; bet the best side when its edge clears the cut.

What is NOT the men's: the margin distribution. The men's is a table from
70,268 games with a closing line. The women's feed holds two seasons, so the
margin around the expected margin is a normal whose spread grows with the size
of the line, fitted on the EARLIER priced season's closing consensus only:

  2025-26 graded with numbers from 2024-25         (walk-forward)
  2026-27 to date with numbers from 2024-26        (walk-forward)
  2024-25 graded with numbers from 2025-26         (a second look, NOT walk-forward)

Boards are the newest snapshot at or before tip - lead (cache/boards.parquet).
Stake: one unit to win, risk capped at 3. 95% interval resampled by date.
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.ncaabw_research._paths import CACHE, SPOOL  # noqa: E402,F401
import config  # noqa: E402

BETTABLE = list(config.BEST_LINE_BOOKMAKERS)
RNG = np.random.default_rng(20261109)
MIN_PRICE = -200


def dec(a):
    a = float(a)
    return 1.0 + a / 100.0 if a > 0 else 1.0 + 100.0 / abs(a)


def imp(a):
    return 1.0 / dec(a)


def load():
    g = pd.read_parquet(CACHE / "games.parquet")
    g = g[g["home_score"].notna()].copy()
    g["margin"] = g["home_score"].astype(float) - g["away_score"].astype(float)
    g["game_date"] = g["game_date"].astype(str).str[:10]
    B = pd.read_parquet(CACHE / "boards.parquet")
    B = B.merge(g[["game_id", "season", "game_date", "margin"]], on="game_id")
    return g, B


def spreads_of(board):
    s = board[board["market"] == "spreads"].dropna(subset=["spread_home", "home_price", "away_price"]).copy()
    s = s[s["spread_home"].abs() <= 70]
    vig = s["home_price"].map(imp) + s["away_price"].map(imp)
    return s[(vig >= 1.0) & (vig <= 1.15)]


def moneylines_of(board):
    m = board[board["market"] == "h2h"].dropna(subset=["home_price", "away_price"]).copy()
    vig = m["home_price"].map(imp) + m["away_price"].map(imp)
    return m[(vig >= 1.0) & (vig <= 1.15)]


def drop_sign_errors(s):
    """A spread on the other side of zero from the other books' median."""
    keep = []
    for gid, x in s.groupby("game_id"):
        lines = x["spread_home"].values
        for i in range(len(x)):
            others = np.delete(lines, i)
            if len(others) and abs(lines[i]) >= 1 and abs(np.median(others)) >= 1 \
                    and np.sign(lines[i]) != np.sign(np.median(others)):
                keep.append(False)
            else:
                keep.append(True)
    return s[np.array(keep, dtype=bool)] if len(s) else s


def fit_margin(close):
    """From closing boards: the offset (mean of margin + consensus) and
    sigma(|line|) = (a + b |line|) sqrt(pi / 2), by least squares on |residual|."""
    s = drop_sign_errors(spreads_of(close))
    cons = s.groupby("game_id").agg(cons=("spread_home", "median"), margin=("margin", "first"))
    r = cons["margin"] + cons["cons"]
    X = np.column_stack([np.ones(len(cons)), cons["cons"].abs()])
    a, b = np.linalg.lstsq(X, r.abs().values, rcond=None)[0]
    k = np.sqrt(np.pi / 2)
    return {"offset": float(r.mean()), "a": float(a * k), "b": float(b * k), "n": int(len(cons)),
            "resid_sd": float(r.std())}


def sigma(fit, line):
    return max(fit["a"] + fit["b"] * abs(line), 6.0)


def cover_probs(m, sd, s):
    """(P home covers, P push, P away covers) at home number s, the final
    margin a whole number around mean m."""
    k = -s
    if abs(k - round(k)) < 1e-9:
        pw = float(norm.sf((k + 0.5 - m) / sd))
        pp = float(norm.cdf((k + 0.5 - m) / sd) - norm.cdf((k - 0.5 - m) / sd))
    else:
        pw = float(norm.sf((k - m) / sd)); pp = 0.0
    return pw, pp, 1.0 - pw - pp


def stake(price, won, push=False):
    d = dec(price)
    risk = min(1.0 / (d - 1.0), 3.0)
    if push:
        return 0.0, risk
    return (risk * (d - 1.0) if won else -risk), risk


def summarise(bets, label):
    if not len(bets):
        print(f"  {label:44s}    0 bets")
        return
    u, r = bets["units"].values, bets["risk"].values
    ud = pd.Series(u).groupby(bets["game_date"].values).sum()
    rd = pd.Series(r).groupby(bets["game_date"].values).sum()
    idx = RNG.integers(0, len(ud), size=(2000, len(ud)))
    boot = ud.values[idx].sum(axis=1) / rd.values[idx].sum(axis=1) * 100
    lo, hi = np.percentile(boot, [2.5, 97.5])
    w, l = int((u > 0).sum()), int((u < 0).sum())
    clv = f"  close {bets['clv'].mean():+.2f}" if "clv" in bets and bets["clv"].notna().any() else ""
    print(f"  {label:44s} {len(bets):4d} bets {w}-{l}-{len(bets) - w - l}  {u.sum():+7.2f}u "
          f"{u.sum() / r.sum() * 100:+6.2f}% [{lo:+.1f}, {hi:+.1f}]  prices "
          f"{bets['price'].min():.0f}..{bets['price'].max():.0f}{clv}")


def spread_bets(board, close, fit, min_others=3):
    """Every game's best bettable spread quote against the consensus."""
    s = drop_sign_errors(spreads_of(board))
    cs = drop_sign_errors(spreads_of(close)).groupby("game_id")["spread_home"].median()
    rows = []
    for gid, x in s.groupby("game_id"):
        cons = float(x["spread_home"].median())
        m = -cons + fit["offset"]
        sd = sigma(fit, cons)
        best = None
        for q in x.itertuples(index=False):
            if q.bookmaker not in BETTABLE:
                continue
            pw, pp, pl = cover_probs(m, sd, q.spread_home)
            eh = pw / (pw + pl) - imp(q.home_price)
            ea = pl / (pw + pl) - imp(q.away_price)
            side, edge, price = ("home", eh, q.home_price) if eh >= ea else ("away", ea, q.away_price)
            better = q.spread_home if side == "home" else -q.spread_home
            key = (edge, better, price, -ord(q.bookmaker[0]))
            if best is None or key > best[0]:
                best = (key, q, side, edge, price)
        if best is None:
            continue
        _, q, side, edge, price = best
        res = q.margin + q.spread_home
        won = res > 0 if side == "home" else res < 0
        u, risk = stake(price, won, push=(res == 0))
        cl = cs.get(gid, np.nan)
        clv = (q.spread_home - cl) if side == "home" else (cl - q.spread_home)
        # the same side at the consensus line, -110
        cres = q.margin + cons
        cwon = cres > 0 if side == "home" else cres < 0
        cu, crisk = stake(-110, cwon, push=(cres == 0))
        rows.append({"game_id": gid, "season": q.season, "game_date": q.game_date, "book": q.bookmaker,
                     "side": side, "line": q.spread_home, "price": price, "edge": edge,
                     "cons": cons, "others": len(x) - 1, "off": abs(q.spread_home - cons),
                     "units": u, "risk": risk, "clv": clv, "cons_units": cu, "cons_risk": crisk})
    out = pd.DataFrame(rows)
    return out[out["others"] >= min_others] if len(out) else out


def win_prob_from_spread(fit, s, home_price, away_price):
    """The book's own fair P(home wins) from its spread: de-vig the two prices
    (power method), find the mean margin that gives that cover chance at the
    line, then P(margin > 0) with no tie."""
    ph, pa = imp(home_price), imp(away_price)
    lo, hi = 0.5, 3.0
    for _ in range(60):                       # power de-vig: ph^k + pa^k = 1
        k = (lo + hi) / 2
        if ph ** k + pa ** k > 1:
            lo = k
        else:
            hi = k
    target = ph ** k / (ph ** k + pa ** k)
    sd = sigma(fit, s)
    a, b = -80.0, 80.0
    for _ in range(60):
        m = (a + b) / 2
        pw, pp, pl = cover_probs(m, sd, s)
        if pw / (pw + pl) < target:
            a = m
        else:
            b = m
    pw0 = float(norm.sf((0.5 - m) / sd)); pl0 = float(norm.cdf((-0.5 - m) / sd))
    return pw0 / (pw0 + pl0)


def moneyline_bets(board, fit):
    s = drop_sign_errors(spreads_of(board))
    ml = moneylines_of(board)
    sp = s[["game_id", "bookmaker", "spread_home", "home_price", "away_price"]].rename(
        columns={"spread_home": "sp_line", "home_price": "sp_home", "away_price": "sp_away"})
    x = ml.drop(columns=["spread_home"]).merge(sp, on=["game_id", "bookmaker"])
    x = x[x["bookmaker"].isin(BETTABLE)]
    rows = []
    for gid, grp in x.groupby("game_id"):
        best = None
        for q in grp.itertuples(index=False):
            # the moneyline's favourite must be the spread's when the spread is 1.5 or more
            if abs(q.sp_line) >= 1.5 and ((q.sp_line < 0) != (q.home_price < q.away_price)):
                continue
            p = win_prob_from_spread(fit, q.sp_line, q.sp_home, q.sp_away)
            for side, prob, price in (("home", p, q.home_price), ("away", 1 - p, q.away_price)):
                if price < MIN_PRICE:
                    continue
                edge = prob - imp(price)
                key = (edge, price, -ord(q.bookmaker[0]))
                if best is None or key > best[0]:
                    best = (key, q, side, edge, price, prob)
        if best is None:
            continue
        _, q, side, edge, price, prob = best
        won = q.margin > 0 if side == "home" else q.margin < 0
        u, risk = stake(price, won)
        rows.append({"game_id": gid, "season": q.season, "game_date": q.game_date, "book": q.bookmaker,
                     "side": side, "price": price, "edge": edge, "prob": prob,
                     "units": u, "risk": risk, "fav": price < 0})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    g, B = load()
    close = B[B["lead"] == 0]
    print("games with a closing board by season:", close.groupby("season")["game_id"].nunique().to_dict())
    sp = drop_sign_errors(spreads_of(close))
    nb_books = sp.groupby(["season", "game_id"]).size().groupby("season").describe()[["mean", "50%", "max"]]
    print("books quoting a closing spread per game:\n", nb_books.round(1).to_string())
    folds = [("2025-26 on numbers from 2024-25 (walk-forward)", [2025], 2026),
             ("2026-27 to date on numbers from 2024-26 (walk-forward)", [2025, 2026], 2027),
             ("2024-25 on numbers from 2025-26 (second look)", [2026], 2025)]
    for label, tr, te in folds:
        fit = fit_margin(close[close["season"].isin(tr)])
        print(f"\n=== {label}\n  margin numbers: {fit}")
        for lead in (10, 30, 60, 120, 240):
            board = B[(B["lead"] == lead) & (B["season"] == te)]
            if not len(board):
                continue
            sb = spread_bets(board, close, fit)
            print(f" SPREAD, {lead} minutes before the tip: {board['game_id'].nunique()} games with a board, "
                  f"{len(sb)} with a bettable quote and 3+ other books")
            for cut in (0.01, 0.02, 0.03, 0.04, 0.05):
                summarise(sb[sb["edge"] > cut] if len(sb) else sb, f"edge > {cut:.2f}")
            if len(sb):
                b3 = sb[sb["edge"] > 0.03]
                if len(b3):
                    c = b3.assign(units=b3["cons_units"], risk=b3["cons_risk"], price=-110)
                    summarise(c, "  > 0.03 bets at the consensus line, -110")
                    summarise(b3[b3["off"] >= 1.0], "  > 0.03, quote 1+ point off the consensus")
                    summarise(b3[b3["off"] < 1.0], "  > 0.03, under a point off")
            mb_ = moneyline_bets(board, fit)
            print(f" MONEYLINE, {lead} minutes before the tip: {len(mb_)} games with a priced side at -200 or longer")
            for cut in (0.0, 0.005, 0.01, 0.015, 0.02, 0.03):
                summarise(mb_[mb_["edge"] > cut] if len(mb_) else mb_, f"edge > {cut:.3f}")
