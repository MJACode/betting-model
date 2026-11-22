"""NHL, every market: Pinnacle's no-vig price against a bettable book in the same fetch.

The nhl_over_under rule (models/nhl_totals_market.py) run on every NHL market
the odds table stores: per game, walk the pre-game fetches in time order; in
each fetch that holds Pinnacle at a number, de-vig Pinnacle proportionally
(overround strictly inside COHERENT), price every bettable book in that SAME
fetch at the SAME number (-200 or better), and bet the best EV the first time
it clears the floor. One bet a game per market. Units are the published stake
(1u to win, risk capped at 3); `flat` is 1u risked. Closing-line value is the
taken price against Pinnacle's last pre-game no-vig price at the same number.

Results and verdicts: docs/nhl_sharp_vs_soft.md (2026-11-21).

READ-ONLY. Reads the local parquet copy of the database (docs/local_ops.md),
never production, and writes nothing.

    python -m scripts.nhl_sharp_vs_soft_lab validate          # must reproduce nhl_over_under's table
    python -m scripts.nhl_sharp_vs_soft_lab grid              # every market, three windows, the floor grid
    python -m scripts.nhl_sharp_vs_soft_lab grid --market spreads
    python -m scripts.nhl_sharp_vs_soft_lab kill --market spreads   # the kill tests on one market
    python -m scripts.nhl_sharp_vs_soft_lab grid --market spreads --reference draftkings   # a placebo
    python -m scripts.nhl_sharp_vs_soft_lab kill --market spreads --devig power
    python -m scripts.nhl_sharp_vs_soft_lab check --market spreads   # sign check, blind bets, quote gap
    python -m scripts.nhl_sharp_vs_soft_lab grid --market totals_p1 --fresh-source odds_api_nhl_totals_history --env-file ../../../.env          # this season's bought rows, read from the database

TRAPS. Bought-history rows carry their IMPORT time in created_at, so they are
bounded pre-game on snapshot_at; live rows on both (in-play NHL rows are typed
'open'). Settled 2026-27 games have lost most non-DraftKings rows to the odds
clean-up (data/prune_odds.py; issue #1343), so an in-season replay of a settled
game is not the rule's real input: read the live record for 2026-27 instead.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd

MIRROR = Path(r"C:\Users\micha\Documents\betting_local_copies\supabase_mirror\tables")
SOFT = ["draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics", "betrivers", "hardrockbet"]
SHARP = "pinnacle"
FLOORS = (0.0, 0.005, 0.01, 0.015, 0.02, 0.03, 0.04, 0.06)
MIN_ODDS = -200.0
# "proportional" (the live rule) or "power" (each implied chance raised to the one
# power that makes the set sum to 1; kill-tests.md, "De-vig the sharp pair").
DEVIG = "proportional"
pd.set_option("display.width", 320)
pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 60)

# market -> (outcomes, price columns, line column or None, coherent range)
SPEC = {
    "totals": (("over", "under"), ("over_price", "under_price"), "total_line", (1.0, 1.15)),
    "alternate_totals": (("over", "under"), ("over_price", "under_price"), "total_line", (1.0, 1.15)),
    "totals_p1": (("over", "under"), ("over_price", "under_price"), "total_line", (1.0, 1.15)),
    "team_totals_home": (("over", "under"), ("over_price", "under_price"), "total_line", (1.0, 1.15)),
    "team_totals_away": (("over", "under"), ("over_price", "under_price"), "total_line", (1.0, 1.15)),
    "spreads": (("home", "away"), ("home_price", "away_price"), "spread_home", (1.0, 1.15)),
    "alternate_spreads": (("home", "away"), ("home_price", "away_price"), "spread_home", (1.0, 1.15)),
    "h2h": (("home", "away"), ("home_price", "away_price"), None, (1.0, 1.15)),
    "h2h_3way": (("home", "draw", "away"), ("home_price", "draw_price", "away_price"), None, (1.0, 1.20)),
}


def implied(a):
    a = np.asarray(a, float)
    return np.where(a > 0, 100.0 / (a + 100.0), np.where(a < 0, -a / (-a + 100.0), np.nan))


def dec(a):
    a = np.asarray(a, float)
    return np.where(a > 0, 1 + a / 100.0, np.where(a < 0, 1 + 100.0 / -a, np.nan))


def ts(s):
    return pd.to_datetime(s, utc=True, errors="coerce", format="mixed")


def _read(table, filt=None, cols=None, mirror=None):
    import pyarrow.dataset as ds
    d = ds.dataset(os.path.join(mirror or MIRROR, f"public.{table}"), format="parquet",
                   exclude_invalid_files=True)
    return d.to_table(filter=filt, columns=cols).to_pandas()


def load(mirror=None):
    import pyarrow.compute as pc
    import pyarrow.dataset as ds
    np.seterr(divide="ignore", invalid="ignore")
    nhl = pc.starts_with(ds.field("game_id"), "NHL_")
    games = _read("games", nhl, ["game_id", "season", "commence_time", "home_score", "away_score",
                                 "went_to_ot", "home_win", "home_win_reg", "regulation_tie"],
                  mirror).drop_duplicates("game_id")
    for c in ("home_score", "away_score", "went_to_ot", "home_win", "home_win_reg", "regulation_tie", "season"):
        games[c] = pd.to_numeric(games[c], errors="coerce")
    games["ct"] = ts(games["commence_time"])
    per = _read("nhl_period_scores", None, ["game_id", "home_p1", "home_p2", "home_p3",
                                            "away_p1", "away_p2", "away_p3", "source"], mirror)
    per["rank"] = (per["source"] != "nhl_api_score").astype(int)       # prefer the NHL feed
    per = per.sort_values("rank").drop_duplicates("game_id")
    for c in ("home_p1", "home_p2", "home_p3", "away_p1", "away_p2", "away_p3"):
        per[c] = pd.to_numeric(per[c], errors="coerce")
    games = games.merge(per[["game_id", "home_p1", "home_p2", "home_p3", "away_p1", "away_p2", "away_p3"]],
                        on="game_id", how="left")
    odds = _read("odds", nhl, ["game_id", "market", "bookmaker", "snapshot_type", "snapshot_at", "created_at",
                               "home_price", "away_price", "draw_price", "spread_home", "total_line",
                               "over_price", "under_price", "source"], mirror)
    return games, odds


def add_fresh(games, odds, source, season, env_file):
    """Rows the local copy does not have yet: one source's rows for one season's
    games, read from the database by game id (a small indexed read; the copy
    lags by up to a day). Read-only. Also refreshes that season's scores."""
    import psycopg2
    from dotenv import load_dotenv
    load_dotenv(env_file)
    ids = sorted(games.loc[games.season == season, "game_id"])
    cols = ["game_id", "market", "bookmaker", "snapshot_type", "snapshot_at", "created_at",
            "home_price", "away_price", "draw_price", "spread_home", "total_line",
            "over_price", "under_price", "source"]
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        cur = conn.cursor()
        cur.execute("SET default_transaction_read_only = on")
        cur.execute(f"SELECT {', '.join(c + '::text' for c in cols)} FROM odds "
                    "WHERE game_id = ANY(%s) AND source = %s", (ids, source))
        fresh = pd.DataFrame(cur.fetchall(), columns=cols)
        cur.execute("SELECT game_id, home_score, away_score, regulation_tie FROM games WHERE game_id = ANY(%s)",
                    (ids,))
        sc = pd.DataFrame(cur.fetchall(), columns=["game_id", "home_score", "away_score", "regulation_tie"])
        cur.execute("SELECT DISTINCT ON (game_id) game_id, home_p1, home_p2, home_p3, away_p1, away_p2, away_p3 "
                    "FROM nhl_period_scores WHERE game_id = ANY(%s) "
                    "ORDER BY game_id, (source <> 'nhl_api_score')", (ids,))
        per = pd.DataFrame(cur.fetchall(), columns=["game_id", "home_p1", "home_p2", "home_p3",
                                                    "away_p1", "away_p2", "away_p3"])
    finally:
        conn.close()
    print(f"fresh from the database: {len(fresh):,} {source} rows on "
          f"{fresh.game_id.nunique():,} season-{season} games")
    odds = pd.concat([odds[~((odds.source == source) & odds.game_id.isin(ids))], fresh], ignore_index=True)
    g = games.set_index("game_id")
    for frame in (sc, per):
        f = frame.set_index("game_id").apply(pd.to_numeric, errors="coerce").astype(float)
        g[f.columns] = g[f.columns].astype(float)
        g.update(f)
    return g.reset_index(), odds


def outcome_result(market, side, line, g):
    """1 win, 0 loss, 0.5 push, nan unknown. g is a games row (Series)."""
    hs, as_ = g["home_score"], g["away_score"]
    if pd.isna(hs) or pd.isna(as_):
        return np.nan
    v = None
    if market in ("totals", "alternate_totals"):
        v = hs + as_
    elif market == "team_totals_home":
        v = hs
    elif market == "team_totals_away":
        v = as_
    elif market == "totals_p1":
        if pd.isna(g["home_p1"]) or pd.isna(g["away_p1"]):
            return np.nan
        v = g["home_p1"] + g["away_p1"]
    if v is not None:
        if v == line:
            return 0.5
        return float((v > line) == (side == "over"))
    if market in ("spreads", "alternate_spreads"):
        m = (hs - as_) + line
        if m == 0:
            return 0.5
        return float((m > 0) == (side == "home"))
    if market == "h2h":
        return float((hs > as_) == (side == "home"))
    if market == "h2h_3way":
        if not pd.isna(g["home_p3"]) and not pd.isna(g["away_p3"]):
            h = g["home_p1"] + g["home_p2"] + g["home_p3"]
            a = g["away_p1"] + g["away_p2"] + g["away_p3"]
            res = "draw" if h == a else ("home" if h > a else "away")
        else:
            if pd.isna(g["regulation_tie"]):
                return np.nan
            res = "draw" if g["regulation_tie"] == 1 else ("home" if hs > as_ else "away")
        return float(res == side)
    return np.nan


def prepare(odds, games, market):
    outs, pcols, lcol, coh = SPEC[market]
    o = odds[(odds.market == market) & (odds.snapshot_type == "open")].copy()
    o = o[o.bookmaker.isin(SOFT + [SHARP])]
    for c in pcols:
        o[c] = pd.to_numeric(o[c], errors="coerce")
    o["line"] = pd.to_numeric(o[lcol], errors="coerce") if lcol else 0.0
    o = o.dropna(subset=list(pcols) + ["line"])
    o["snap"] = ts(o["snapshot_at"])
    o["cts"] = ts(o["created_at"])
    o = o.merge(games[["game_id", "ct", "season"]], on="game_id", how="inner")
    src = o["source"].fillna("")
    o = o[src != "sbr_archive_nhl"]
    src = o["source"].fillna("")
    # Pre-game only. Bought-history rows carry their import time in created_at,
    # so they are bounded on snapshot_at; live rows on both (in-play is 'open').
    hist = src.str.contains("histor")
    o = o[(o.snap <= o.ct) & (hist | (o.cts <= o.ct))]
    o["fetch"] = o["created_at"]
    ft = o.groupby(["game_id", "fetch"]).snap.max().rename("fetch_time")
    o = o.join(ft, on=["game_id", "fetch"])
    imps = np.column_stack([implied(o[c]) for c in pcols])
    o["overround"] = imps.sum(axis=1)
    o = o[(o.overround > coh[0]) & (o.overround < coh[1])]
    o = o.sort_values("snap").drop_duplicates(["game_id", "fetch", "bookmaker", "line"], keep="last")
    return o, outs, pcols


def fair_probs(pi):
    """No-vig probabilities from a rows x outcomes array of implied chances."""
    if DEVIG == "proportional":
        return pi / pi.sum(axis=1, keepdims=True)
    lo, hi = np.ones(len(pi)), np.full(len(pi), 4.0)
    for _ in range(60):                       # bisection on k: sum(p ** k) = 1
        k = (lo + hi) / 2
        over = (pi ** k[:, None]).sum(axis=1) > 1
        lo, hi = np.where(over, k, lo), np.where(over, hi, k)
    k = (lo + hi) / 2
    f = pi ** k[:, None]
    return f / f.sum(axis=1, keepdims=True)


def fetch_bests(o, outs, pcols):
    """Every (game, fetch, soft book, line, side) priced against Pinnacle in the same fetch."""
    p = o[o.bookmaker == SHARP]
    s = o[o.bookmaker != SHARP]
    pi = np.column_stack([implied(p[c]) for c in pcols])
    fair = fair_probs(pi)
    pf = p[["game_id", "fetch", "line"]].copy()
    for i, k in enumerate(outs):
        pf[f"fair_{k}"] = fair[:, i]
    m = s.merge(pf, on=["game_id", "fetch", "line"], how="inner")
    rows = []
    for i, k in enumerate(outs):
        price = m[pcols[i]].values
        ev = m[f"fair_{k}"].values * dec(price) - 1
        r = m[["game_id", "fetch", "fetch_time", "ct", "season", "bookmaker", "line"]].copy()
        r["side"], r["price"], r["fair"], r["ev"] = k, price, m[f"fair_{k}"].values, ev
        r["book_rank"] = r["bookmaker"].map({b: j for j, b in enumerate(SOFT)})
        r["side_rank"] = i
        rows.append(r[price >= MIN_ODDS])
    return pd.concat(rows, ignore_index=True)


def closes(o, outs, pcols):
    """Pinnacle's last pre-game fetch per game: its no-vig probability at each number."""
    p = o[o.bookmaker == SHARP]
    last = p.groupby("game_id").fetch_time.transform("max")
    p = p[p.fetch_time == last]
    pi = np.column_stack([implied(p[c]) for c in pcols])
    fair = fair_probs(pi)
    cl = p[["game_id", "line"]].copy()
    for i, k in enumerate(outs):
        cl[f"close_{k}"] = fair[:, i]
    cl["close_time"] = p["fetch_time"].values
    return cl.drop_duplicates(["game_id", "line"])


def first_bets(c, floor, window=None):
    """The rule at one floor: per game, the first fetch whose best candidate clears it."""
    x = c[c.ev >= floor]
    if window is not None:
        x = x[window(x)]
    if x.empty:
        return x
    x = x.sort_values(["game_id", "fetch_time", "ev", "book_rank", "side_rank"],
                      ascending=[True, True, False, True, True])
    first_fetch = x.groupby("game_id").fetch_time.transform("min")
    x = x[x.fetch_time == first_fetch]
    return x.drop_duplicates("game_id", keep="first")


def grade(bets, market, games, cl, outs):
    if bets.empty:
        return bets
    g = games.set_index("game_id")
    b = bets.copy()
    b["res"] = [outcome_result(market, sd, ln, g.loc[gid]) for gid, sd, ln in
                zip(b.game_id, b.side, b.line)]
    b = b[b.res.notna()].copy()
    if b.empty:
        return b
    d = dec(b.price)
    b["dec"] = d
    risk = np.minimum(1.0 / (d - 1.0), 3.0)
    b["risk"] = risk
    b["units"] = np.where(b.res == 1, risk * (d - 1), np.where(b.res == 0, -risk, 0.0))
    b["flat"] = np.where(b.res == 1, d - 1, np.where(b.res == 0, -1.0, 0.0))
    b = b.merge(cl, on=["game_id", "line"], how="left")
    cf = np.full(len(b), np.nan)
    for k in outs:
        cf = np.where(b.side == k, b[f"close_{k}"], cf)
    b["close_fair"] = cf
    b["clv_ev"] = b.close_fair * b.dec - 1
    b["lead_h"] = (b.ct - b.fetch_time).dt.total_seconds() / 3600
    return b


def summarise(b, label):
    if b is None or b.empty:
        return {"rule": label, "bets": 0}
    n = len(b)
    mu, sd = b.flat.mean(), b.flat.std(ddof=1)
    half = b.sort_values("fetch_time")
    early, late = half.iloc[: n // 2], half.iloc[n // 2:]
    out = {
        "rule": label, "bets": n,
        "units": round(b.units.sum(), 1),
        "ret%": round(100 * b.units.sum() / b.risk.sum(), 2),
        "flat_u": round(b.flat.sum(), 1),
        "flat%": round(100 * mu, 2),
        "95%": f"{100*(mu-1.96*sd/np.sqrt(n)):+.1f}..{100*(mu+1.96*sd/np.sqrt(n)):+.1f}" if n > 1 else "",
        "ev%": round(100 * b.ev.mean(), 2),
        "clv%": round(100 * b.clv_ev.mean(), 2),
        "clv_n": int(b.clv_ev.notna().sum()),
        "beat%": round(100 * (b.clv_ev > 0).sum() / max(b.clv_ev.notna().sum(), 1), 1),
        "early%": round(100 * early.flat.mean(), 1), "late%": round(100 * late.flat.mean(), 1),
        "med_px": float(np.median(b.price)),
        "lead_h": round(float(np.median(b.lead_h)), 1),
    }
    for s, gg in b.groupby("season"):
        out[str(s)] = f"{100*gg.flat.mean():+.1f}({len(gg)})"
    return out


WINDOWS = {
    "any": None,
    "lead<=10h": lambda x: (x.ct - x.fetch_time) <= pd.Timedelta(hours=10),
    "lead<=2h": lambda x: (x.ct - x.fetch_time) <= pd.Timedelta(hours=2),
}


def run(market, games, odds, floors=FLOORS, windows=WINDOWS, seasons=None):
    o, outs, pcols = prepare(odds, games, market)
    if seasons is not None:
        o = o[o.season.isin(seasons)]
    c = fetch_bests(o, outs, pcols)
    cl = closes(o, outs, pcols)
    res, allb = [], {}
    for wname, w in windows.items():
        for f in floors:
            b = grade(first_bets(c, f, w), market, games, cl, outs)
            res.append(summarise(b, f"{wname} EV>={f}"))
            allb[(wname, f)] = b
    return pd.DataFrame(res), allb, o, c


def boot_day(b, n=4000, seed=7):
    """95% interval of the flat return, resampling whole game days."""
    rng = np.random.default_rng(seed)
    day = b.ct.dt.tz_convert("America/New_York").dt.date
    g = b.groupby(day).agg(p=("flat", "sum"), k=("flat", "size"))
    p, k = g.p.values, g.k.values
    idx = rng.integers(0, len(g), size=(n, len(g)))
    r = p[idx].sum(1) / k[idx].sum(1)
    return f"{100*np.percentile(r, 2.5):+.1f}..{100*np.percentile(r, 97.5):+.1f}"


def tab(b, by, label):
    rows = []
    for key, g in b.groupby(by):
        rows.append({label: key, "bets": len(g), "units": round(g.units.sum(), 1),
                     "flat%": round(100 * g.flat.mean(), 1), "clv%": round(100 * g.clv_ev.mean(), 2),
                     "beat%": round(100 * (g.clv_ev > 0).sum() / max(g.clv_ev.notna().sum(), 1), 1),
                     "med_px": float(np.median(g.price))})
    return pd.DataFrame(rows).to_string(index=False)


def kill(market, games, odds, floors=(0.01, 0.015, 0.02), seasons=None):
    _, allb, _, _ = run(market, games, odds, floors=floors, seasons=seasons,
                        windows={"any": None, "lead<=2h": WINDOWS["lead<=2h"]})
    for (w, f), b in allb.items():
        if b.empty:
            continue
        print(f"\n##### {market} {w} EV>={f}: {len(b)} bets, units {b.units.sum():+.1f}, "
              f"flat {100*b.flat.mean():+.2f}%, by-day bootstrap {boot_day(b)}")
        day = b.ct.dt.tz_convert("America/New_York").dt.date
        top = b.groupby(day).units.sum().nlargest(10).index
        rest = b[~day.isin(top)]
        print(f"   without its ten best dates: {len(rest)} bets, units {rest.units.sum():+.1f}, "
              f"flat {100*rest.flat.mean():+.2f}%")
        if market in ("spreads", "alternate_spreads"):
            b["fav_side"] = np.where(((b.side == "home") & (b.line < 0)) | ((b.side == "away") & (b.line > 0)),
                                     "favourite -1.5", "underdog +1.5")
            print(tab(b, "fav_side", "side"))
            print(tab(b, "side", "home/away"))
        else:
            print(tab(b, "side", "side"))
        print(tab(b, "bookmaker", "book"))
        b["band"] = pd.cut(b.price, [-201, -150, -110, 100, 150, 200, 300, 2000])
        print(tab(b, "band", "price band"))
        b["lead"] = pd.cut(b.lead_h, [-1, 0.5, 2, 6, 12, 24, 400])
        print(tab(b, "lead", "hours before start"))
        print(tab(b, "season", "season"))
        # Season by season interval, the season test.
        for s, g in b.groupby("season"):
            if len(g) >= 20:
                print(f"   season {s}: {len(g)} bets flat {100*g.flat.mean():+.1f}% by-day {boot_day(g)}")


def check(market, games, odds, floor=0.015, seasons=None):
    """Is the data right? The reference's close against what happened (the sign
    check), every book blind on both sides at its own last pre-game quote, and
    the reference-to-bet-book quote gap on the rule's bets."""
    o, outs, pcols = prepare(odds, games, market)
    if seasons is not None:
        o = o[o.season.isin(seasons)]
    g = games.set_index("game_id")
    cl = closes(o, outs, pcols).reset_index(drop=True)
    a = outs[0]
    cl["res"] = [outcome_result(market, a, ln, g.loc[gid]) for gid, ln in zip(cl.game_id, cl.line)]
    cl = cl[cl.res.isin([0.0, 1.0])]
    cl["bucket"] = pd.cut(cl[f"close_{a}"], [0, .25, .35, .45, .55, .65, .75, 1])
    print(f"\n1. {SHARP}'s close, P({a}) said vs happened, by line (pushes left out)")
    print(cl.groupby(["line", "bucket"], observed=True).agg(
        n=("res", "size"), said=(f"close_{a}", "mean"), happened=("res", "mean"))
        .query("n >= 30").round(3).to_string())

    last = o.sort_values("fetch_time").drop_duplicates(["game_id", "bookmaker", "line"], keep="last")
    rows = []
    for k, col in zip(outs, pcols):
        x = last[["game_id", "bookmaker", "season", "line", col]].rename(columns={col: "price"})
        x["side"] = k
        rows.append(x)
    bl = pd.concat(rows, ignore_index=True)
    bl["res"] = [outcome_result(market, sd, ln, g.loc[gid]) for gid, sd, ln in
                 zip(bl.game_id, bl.side, bl.line)]
    bl = bl[bl.res.notna()]
    d = dec(bl.price)
    bl["flat"] = np.where(bl.res == 1, d - 1, np.where(bl.res == 0, -1.0, 0.0))
    print(f"\n2. Blind at each book's last pre-game quote, flat return % (bets)")
    t = bl.groupby(["bookmaker", "side"]).flat.agg(["mean", "size"])
    print(t.assign(mean=lambda x: (100 * x["mean"]).round(2)).unstack("side").to_string())

    c = fetch_bests(o, outs, pcols)
    b = first_bets(c, floor)
    sn = o[["game_id", "fetch", "bookmaker", "line", "snap"]]
    b = b.merge(sn, on=["game_id", "fetch", "bookmaker", "line"], how="left")
    ref = sn[sn.bookmaker == SHARP].rename(columns={"snap": "ref_snap"}).drop(columns="bookmaker")
    b = b.merge(ref, on=["game_id", "fetch", "line"], how="left")
    gap = (b.ref_snap - b.snap).dt.total_seconds()
    print(f"\n3. {SHARP}'s snapshot time minus the bet book's, seconds, on the EV>={floor} bets")
    print(gap.describe(percentiles=[.5, .9, .99]).round(0).to_string())


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("validate", "grid", "kill", "check"))
    ap.add_argument("--market", nargs="*", default=None)
    ap.add_argument("--mirror", default=None, help="the tables folder of the local copy")
    ap.add_argument("--devig", choices=("proportional", "power"), default="proportional")
    ap.add_argument("--reference", default="pinnacle",
                    help="the reference book (a placebo when not pinnacle); it leaves the bettable list")
    ap.add_argument("--seasons", nargs=2, type=int, default=None, help="first and last ending year")
    ap.add_argument("--fresh-source", default=None,
                    help="also read this odds source for --fresh-season's games from the database")
    ap.add_argument("--fresh-season", type=int, default=2027)
    ap.add_argument("--env-file", default=None, help="the .env holding DATABASE_URL, for --fresh-source")
    a = ap.parse_args()
    global DEVIG, SHARP, SOFT
    DEVIG, SHARP = a.devig, a.reference
    SOFT = [b for b in SOFT if b != SHARP]
    seasons = range(a.seasons[0], a.seasons[1] + 1) if a.seasons else None
    games, odds = load(a.mirror)
    if a.fresh_source:
        games, odds = add_fresh(games, odds, a.fresh_source, a.fresh_season, a.env_file)
    if a.cmd == "validate":
        # nhl_over_under's evidence table (models/nhl_totals_market.py): 2,768 / 1,859 /
        # 1,276 / 819 / 548 bets at 0 / 0.005 / 0.01 / 0.015 / 0.02, +60.2u and +4.72% at 0.01.
        t, _, _, _ = run("totals", games, odds, floors=(0.0, 0.005, 0.01, 0.015, 0.02),
                         windows={"any": None}, seasons=range(2021, 2027))
        print(t.to_string(index=False))
        return
    for mk in (a.market or list(SPEC)):
        if a.cmd == "kill":
            kill(mk, games, odds, seasons=seasons)
            continue
        if a.cmd == "check":
            check(mk, games, odds, seasons=seasons)
            continue
        print()
        print(f"=== {mk} ===")
        t, _, o, _ = run(mk, games, odds, seasons=seasons)
        print(f"rows {len(o):,} games {o.game_id.nunique():,} seasons {sorted(int(s) for s in o.season.unique())} "
              f"pinnacle games {o[o.bookmaker == SHARP].game_id.nunique():,}")
        print(t.to_string(index=False))


if __name__ == "__main__":
    main()
