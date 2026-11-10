"""NCAAF market-structure lab: the four NCAAB rules pointed at the stored NCAAF archive.

Definitions fixed before any result was read (2026-11-10):

  DATA      2023-2025 Odds API historical pulls stored in `odds` (two a day, 13:55Z and 22:55Z),
            read from the local mirror. Scores from `games`. Closing line = CFBD's stored close.
  SLOTS     D{k}_AM / D{k}_PM: the 13:55Z / 22:55Z pull k ET-days before the game's ET date,
            pre-kick by at least 5 minutes. PRIMARY = D0_AM (game-day morning, the NCAAB instant).
  BOOKS     a bet may be placed at the 7 deciding books (config.BEST_LINE_BOOKMAKERS); the consensus
            is the median over the 10 fetched books (config.LINE_SHOP_BOOKMAKERS).
  TABLES    final-margin and final-total distributions (models/ncaab_margin_dist, unchanged kernel),
            fitted for season S on every earlier season's games and CFBD closes (walk-forward).
  RULES     S  spread: best deciding-book quote vs the consensus line; edge = P(win|no push) - implied
            T  total:  the same on totals
            M  moneyline vs the same book's own spread (power de-vig, mean inverted, P(margin>0))
            C  moneyline vs the consensus spread
            a bet needs >= 3 other books in the consensus; moneylines never shorter than -200.
  GRADING   stake_for: 1 unit to win, risk capped at 3. ROI = units / units risked. 95% interval by
            resampling ET dates. Close value = EV of the bet at the CFBD closing line (same table).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from paths import REPO  # noqa: E402

sys.path.insert(0, str(REPO))
from models import ncaab_margin_dist as md  # noqa: E402

from paths import CACHE as D  # noqa: E402
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)
pd.set_option("display.max_rows", 400)

BETTABLE = ["draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics", "betrivers", "hardrockbet"]
CONS_BOOKS = BETTABLE + ["bovada", "pinnacle", "betparx"]
MIN_OTHER = 3
TOT_SHIFT = 55
RNG = np.random.default_rng(20261110)


def dec(a):
    a = np.asarray(a, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(a > 0, 1 + a / 100.0, 1 + 100.0 / np.abs(a))


def stake(d):
    """(risk, win) for 1 unit to win, risk capped at 3 (tracking.discord_notifier.stake_for)."""
    d = np.asarray(d, float)
    risk = np.minimum(1.0 / (d - 1.0), 3.0)
    return risk, risk * (d - 1.0)


def power_devig(d1, d2):
    """P(side 1) with the vig removed by the power method: find k with p1^k + p2^k = 1."""
    p1, p2 = 1 / np.asarray(d1, float), 1 / np.asarray(d2, float)
    lo, hi = np.full(p1.shape, 0.5), np.full(p1.shape, 3.0)
    for _ in range(60):
        k = (lo + hi) / 2
        s = p1 ** k + p2 ** k
        lo = np.where(s > 1, k, lo)
        hi = np.where(s > 1, hi, k)
    k = (lo + hi) / 2
    return p1 ** k


# ── data ──────────────────────────────────────────────────────────────────────

def load():
    g = pd.read_parquet(D / "g.parquet")
    q = pd.read_parquet(D / "q_hist.parquet")
    q = q[q.bookmaker.isin(CONS_BOOKS)]
    cols = ["game_id", "kick", "et_date", "season", "margin", "total", "close_spread", "close_total", "twin_of",
            "week", "home_team", "away_team"]
    q = q.merge(g[cols], on="game_id", how="inner")
    q = q[q.margin.notna() & (q.pull_ts < q.kick - pd.Timedelta(minutes=5)) & q.season.isin([2023, 2024, 2025])].copy()
    q["canon"] = q.twin_of.fillna(q.game_id)
    # one odds id per real game
    n = q.groupby(["canon", "game_id"]).size().reset_index(name="n").sort_values(["canon", "n"], ascending=[True, False])
    keep = set(n.drop_duplicates("canon").game_id)
    dropped = q.game_id.nunique() - len(keep)
    q = q[q.game_id.isin(keep)].copy()
    pull_et = q.pull_ts.dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None)
    q["lead"] = (pd.to_datetime(q.et_date) - pull_et).dt.days
    q["kind"] = np.where(q.pull_ts.dt.hour < 18, "AM", "PM")
    q["slot"] = "D" + q.lead.astype(str) + "_" + q.kind
    q["hrs"] = (q.kick - q.pull_ts).dt.total_seconds() / 3600
    # the same slot bought twice (overlapping backfills): keep the later pull's row
    before = len(q)
    q = q.sort_values("pull_ts").drop_duplicates(["game_id", "slot", "bookmaker"], keep="last")
    print(f"test quotes: {len(q)} rows ({before - len(q)} repeat-pull rows dropped), {q.game_id.nunique()} games "
          f"({dropped} duplicate odds ids dropped)")
    return g, q


def tables(g, seasons):
    """Walk-forward margin and total tables + offsets, one per test season."""
    base = g[g.twin_of.isna() & g.margin.notna()].sort_values(["game_date", "game_id"])
    out = {}
    for s in seasons:
        tr = base[(base.season < s) & base.close_spread.notna()]
        tt = base[(base.season < s) & base.close_total.notna()]
        Tm = md.fit(tr.margin.astype(int).to_numpy(), (-tr.close_spread).to_numpy())
        Tt = md.fit((tt.total.astype(int) - TOT_SHIFT).to_numpy(), (tt.close_total - TOT_SHIFT).to_numpy())
        out[s] = dict(Tm=Tm, Tt=Tt, c=float((tr.margin + tr.close_spread).mean()),
                      ct=float((tt.total - tt.close_total).mean()), n_m=len(tr), n_t=len(tt))
        print(f"season {s}: margin table on {len(tr)} games (offset {out[s]['c']:+.3f}), "
              f"total table on {len(tt)} (offset {out[s]['ct']:+.3f})")
    return out


# ── pricing ───────────────────────────────────────────────────────────────────

def _sanity(d1, d2):
    s = 1 / d1 + 1 / d2
    return (s >= 1.0) & (s <= 1.15)


def price_spread(x, tabs):
    """x: one slot's quotes (a row per game-book). Returns every priced deciding-book quote."""
    z = x[x.spread_home.notna() & x.sp_home.notna() & x.sp_away.notna()].copy()
    z = z[(z.spread_home.abs() <= 70) & _sanity(dec(z.sp_home), dec(z.sp_away))]
    # a line on the other side of zero from the other books' median is a feed sign error
    med_all = z.groupby("game_id").spread_home.transform("median")
    cnt = z.groupby("game_id").spread_home.transform("size")
    summ = z.groupby("game_id").spread_home.transform("sum")
    z["flag_sign"] = (np.sign(z.spread_home) * np.sign(med_all) < 0) & (cnt >= 3)
    z = z[~z.flag_sign].copy()
    z["cons"] = z.groupby("game_id").spread_home.transform("median")
    z["n_ok"] = z.groupby("game_id").spread_home.transform("size")
    out = []
    for s, zz in z.groupby("season"):
        t = tabs[s]
        zz = zz.copy()
        zz["mu"] = -zz.cons + t["c"]
        ph, pp = md.home_cover(zz.mu.to_numpy(float), zz.spread_home.to_numpy(float), t["Tm"])
        zz["ph"] = ph
        e1 = ph - 1 / dec(zz.sp_home)
        e2 = (1 - ph) - 1 / dec(zz.sp_away)
        zz["side"] = np.where(e1 >= e2, 1, 2)
        zz["edge"] = np.maximum(e1, e2)
        zz["price"] = np.where(zz.side == 1, zz.sp_home, zz.sp_away)
        zz["prob"] = np.where(zz.side == 1, ph, 1 - ph)
        zz["line_side"] = np.where(zz.side == 1, zz.spread_home, -zz.spread_home)
        zz["off_pts"] = zz.line_side - np.where(zz.side == 1, zz.cons, -zz.cons)   # points better than consensus
        res = np.where(zz.side == 1, zz.margin + zz.spread_home, -(zz.margin + zz.spread_home))
        zz["res"] = np.sign(res)
        # value at the CFBD close: same table, mean from the closing line
        mu_c = -zz.close_spread + t["c"]
        phc, _ = md.home_cover(mu_c.to_numpy(float), zz.spread_home.to_numpy(float), t["Tm"])
        pc = np.where(zz.side == 1, phc, 1 - phc)
        d = dec(zz.price)
        zz["ev_close"] = pc * (d - 1) - (1 - pc)
        zz["clv_pts"] = zz.line_side - np.where(zz.side == 1, zz.close_spread, -zz.close_spread)
        out.append(zz)
    z = pd.concat(out)
    return z[z.bookmaker.isin(BETTABLE)]


def price_total(x, tabs):
    z = x[x.total_line.notna() & x.over_price.notna() & x.under_price.notna()].copy()
    z = z[(z.total_line.between(20, 100)) & _sanity(dec(z.over_price), dec(z.under_price))]
    z["cons"] = z.groupby("game_id").total_line.transform("median")
    z["n_ok"] = z.groupby("game_id").total_line.transform("size")
    out = []
    for s, zz in z.groupby("season"):
        t = tabs[s]
        zz = zz.copy()
        zz["mu"] = zz.cons + t["ct"] - TOT_SHIFT
        pw, pp, pl = md.probs(zz.mu.to_numpy(float), (zz.total_line - TOT_SHIFT).to_numpy(float), t["Tt"])
        po = pw / (pw + pl)
        e1 = po - 1 / dec(zz.over_price)
        e2 = (1 - po) - 1 / dec(zz.under_price)
        zz["side"] = np.where(e1 >= e2, 1, 2)       # 1 over, 2 under
        zz["edge"] = np.maximum(e1, e2)
        zz["price"] = np.where(zz.side == 1, zz.over_price, zz.under_price)
        zz["prob"] = np.where(zz.side == 1, po, 1 - po)
        zz["off_pts"] = np.where(zz.side == 1, zz.cons - zz.total_line, zz.total_line - zz.cons)
        res = np.where(zz.side == 1, zz.total - zz.total_line, zz.total_line - zz.total)
        zz["res"] = np.sign(res)
        mu_c = zz.close_total + t["ct"] - TOT_SHIFT
        pw, pp, pl = md.probs(mu_c.to_numpy(float), (zz.total_line - TOT_SHIFT).to_numpy(float), t["Tt"])
        poc = pw / (pw + pl)
        pc = np.where(zz.side == 1, poc, 1 - poc)
        d = dec(zz.price)
        zz["ev_close"] = pc * (d - 1) - (1 - pc)
        zz["clv_pts"] = np.where(zz.side == 1, zz.close_total - zz.total_line, zz.total_line - zz.close_total)
        out.append(zz)
    z = pd.concat(out)
    return z[z.bookmaker.isin(BETTABLE)]


def price_ml(x, tabs, mode):
    """mode 'own': each book's moneyline vs its own spread. 'cons': vs the consensus spread."""
    z = x[x.ml_home.notna() & x.ml_away.notna()].copy()
    z = z[_sanity(dec(z.ml_home), dec(z.ml_away))]
    sp_ok = (x.spread_home.notna() & x.sp_home.notna() & x.sp_away.notna() & (x.spread_home.abs() <= 70)
             & _sanity(dec(x.sp_home), dec(x.sp_away)))
    xs = x[sp_ok]
    cons = xs.groupby("game_id").spread_home.median()
    n_ok = xs.groupby("game_id").spread_home.size()
    z["cons"] = z.game_id.map(cons)
    z["n_ok"] = z.game_id.map(n_ok).fillna(0)
    # the favourite must agree with the other books' favourite (2+ others)
    z["fav_home"] = dec(z.ml_home) < dec(z.ml_away)
    fh = z.groupby("game_id").fav_home.transform("sum")
    nn = z.groupby("game_id").fav_home.transform("size")
    oth_home = fh - z.fav_home.astype(int)
    oth = nn - 1
    disagree = (oth >= 2) & (((z.fav_home) & (oth_home == 0)) | ((~z.fav_home) & (oth_home == oth)))
    z = z[~disagree].copy()
    out = []
    for s, zz in z.groupby("season"):
        t = tabs[s]
        zz = zz.copy()
        if mode == "own":
            ok = (zz.spread_home.notna() & zz.sp_home.notna() & zz.sp_away.notna() & (zz.spread_home.abs() <= 70)
                  & _sanity(dec(zz.sp_home), dec(zz.sp_away)) & (dec(zz.sp_home) >= 1.5) & (dec(zz.sp_away) >= 1.5))
            # own spread naming the other team favourite by 1.5+ is a broken pair
            ok &= ~((zz.spread_home.abs() >= 1.5) & ((zz.spread_home < 0) != zz.fav_home))
            # own line on the other side of zero from the consensus
            ok &= ~((np.sign(zz.spread_home) * np.sign(zz.cons) < 0))
            zz = zz[ok].copy()
            pcov = power_devig(dec(zz.sp_home), dec(zz.sp_away))
            mu = md.mean_for_cover(pcov, (-zz.spread_home).to_numpy(float), t["Tm"])
        else:
            zz = zz[zz.cons.notna()].copy()
            mu = (-zz.cons + t["c"]).to_numpy(float)
        zz["mu"] = mu
        pw, pp, pl = md.probs(mu, np.zeros(len(zz)), t["Tm"])
        ph = pw / (pw + pl)
        zz["ph"] = ph
        dh, da = dec(zz.ml_home), dec(zz.ml_away)
        e1 = np.where(dh >= 1.5, ph - 1 / dh, -9.0)          # never shorter than -200
        e2 = np.where(da >= 1.5, (1 - ph) - 1 / da, -9.0)
        zz["side"] = np.where(e1 >= e2, 1, 2)
        zz["edge"] = np.maximum(e1, e2)
        zz["price"] = np.where(zz.side == 1, zz.ml_home, zz.ml_away)
        zz["prob"] = np.where(zz.side == 1, ph, 1 - ph)
        zz["off_pts"] = np.nan
        zz["res"] = np.where(zz.side == 1, np.sign(zz.margin), -np.sign(zz.margin))
        mu_c = (-zz.close_spread + t["c"]).to_numpy(float)
        pw, pp, pl = md.probs(mu_c, np.zeros(len(zz)), t["Tm"])
        phc = pw / (pw + pl)
        pc = np.where(zz.side == 1, phc, 1 - phc)
        d = dec(zz.price)
        zz["ev_close"] = pc * (d - 1) - (1 - pc)
        zz["clv_pts"] = np.nan
        out.append(zz)
    z = pd.concat(out)
    z = z[z.edge > -5]
    return z[z.bookmaker.isin(BETTABLE)]


def best(z):
    z = z[z.edge.notna()].copy()
    z["_d"] = dec(z.price)
    ls = z.line_side if "line_side" in z else pd.Series(0.0, index=z.index)
    z["_ls"] = ls
    z = z.sort_values(["game_id", "edge", "_ls", "_d", "bookmaker"], ascending=[True, False, False, False, True],
                      kind="mergesort")
    return z.drop_duplicates("game_id")


# ── grading ───────────────────────────────────────────────────────────────────

def grade(b):
    """b: chosen bets (one a game). Adds risk/pnl. Returns summary dict."""
    if not len(b):
        return dict(bets=0)
    d = dec(b.price)
    risk, win = stake(d)
    pnl = np.where(b.res > 0, win, np.where(b.res < 0, -risk, 0.0))
    risked = np.where(b.res != 0, risk, 0.0)
    b = b.assign(pnl=pnl, risked=risked)
    by = b.groupby("et_date").agg(p=("pnl", "sum"), r=("risked", "sum"))
    P, R = by.p.to_numpy(), by.r.to_numpy()
    idx = RNG.integers(0, len(by), size=(2000, len(by)))
    boot = P[idx].sum(1) / np.maximum(R[idx].sum(1), 1e-9)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    w, l, p = int((b.res > 0).sum()), int((b.res < 0).sum()), int((b.res == 0).sum())
    top10 = by.p.sort_values(ascending=False).head(10).sum()
    return dict(bets=len(b), rec=f"{w}-{l}-{p}", units=round(pnl.sum(), 2), roi=round(100 * pnl.sum() / max(risked.sum(), 1e-9), 2),
                lo=round(100 * lo, 1), hi=round(100 * hi, 1), ev_close=round(100 * np.nanmean(b.ev_close), 2),
                clv_pts=round(float(np.nanmean(b.clv_pts)), 3) if b.clv_pts.notna().any() else np.nan,
                med_price=int(np.median(b.price)), ex10=round(pnl.sum() - top10, 2), _b=b)


def by_season(b):
    return " ".join(f"{int(s)}:{len(x)}/{x.pnl.sum():+.1f}" for s, x in b.groupby("season"))


def halves(b):
    """Each season split at its median bet date: early half / late half units and ROI."""
    out = []
    for nm, pick in (("early", True), ("late", False)):
        parts = []
        for s, x in b.groupby("season"):
            mid = x.et_date.sort_values().iloc[len(x) // 2]
            parts.append(x[(x.et_date < mid)] if pick else x[(x.et_date >= mid)])
        y = pd.concat(parts) if parts else b.iloc[:0]
        out.append(f"{nm} {len(y)}/{y.pnl.sum():+.1f}u/{100*y.pnl.sum()/max(y.risked.sum(),1e-9):+.1f}%")
    return " | ".join(out)


def sweep(name, priced, cuts, extra=None):
    cand = best(priced)
    cand = cand[cand.n_ok - 1 >= MIN_OTHER]
    rows = []
    keep = {}
    for c in cuts:
        b = cand[cand.edge > c]
        if extra is not None:
            b = extra(b)
        r = grade(b)
        if r["bets"] == 0:
            rows.append(dict(rule=name, cut=c, bets=0))
            continue
        bb = r.pop("_b")
        keep[c] = bb
        r.update(rule=name, cut=c, seasons=by_season(bb), halves=halves(bb))
        rows.append(r)
    return pd.DataFrame(rows), keep, cand


if __name__ == "__main__":
    g, q = load()
    tabs = tables(g, [2023, 2024, 2025])
    slots = q.groupby("slot").game_id.nunique().sort_values(ascending=False)
    print("games per slot:\n", slots.head(16).to_string())
    print("hours before kickoff by slot (median):\n", q.groupby("slot").hrs.median().round(1).loc[slots.head(12).index].to_string())
    cols = ["rule", "cut", "bets", "rec", "units", "roi", "lo", "hi", "ev_close", "clv_pts", "med_price", "ex10", "seasons", "halves"]
    order = ["D0_AM", "D0_PM", "D1_PM", "D1_AM", "D2_AM", "D3_AM", "D4_AM", "D5_AM"]
    allres = []
    for slot in order:
        x = q[q.slot == slot]
        if x.game_id.nunique() < 200:
            continue
        for name, fn, cuts in (
            ("S spread", lambda v: price_spread(v, tabs), [0.01, 0.02, 0.03, 0.04, 0.05, 0.06]),
            ("T total", lambda v: price_total(v, tabs), [0.01, 0.02, 0.03, 0.04, 0.05, 0.06]),
            ("M ml-own", lambda v: price_ml(v, tabs, "own"), [0.005, 0.01, 0.015, 0.02, 0.03, 0.04]),
            ("C ml-cons", lambda v: price_ml(v, tabs, "cons"), [0.01, 0.02, 0.03, 0.04, 0.05, 0.06]),
        ):
            pr = fn(x)
            res, keep, cand = sweep(name, pr, cuts)
            res.insert(0, "slot", slot)
            res.insert(1, "games", x.game_id.nunique())
            allres.append(res)
            pd.to_pickle(dict(keep=keep, cand=cand), D / f"bets_{slot}_{name.split()[0]}.pkl")
    R = pd.concat(allres, ignore_index=True)
    R.to_csv(D / "lab_results.csv", index=False)
    show = ["slot", "games"] + [c for c in cols if c in R.columns]
    for rule, x in R.groupby("rule"):
        print(f"\n===== {rule} =====")
        print(x[show].drop(columns=["rule"]).to_string(index=False))
