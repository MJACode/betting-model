"""Round 4, experiment 4: are the books' halftime full-game lines re-hung
mechanically off the pre-game number, and where do they miss?

Totals: share2 = sum(final - half-time total) / sum(final) over the EARLIER
seasons (2021-22 uses 2022-23). Mechanical = half-time total + prior_t x share2.
Spreads: share_m = slope through the origin of (final - half-time margin) on
prior_m over the earlier seasons. Mechanical home spread = -(half-time margin +
prior_m x share_m). Each book's FIRST fresh halftime quote. Descriptive and
in-sample: nothing here is a bet rule and nothing is registered."""
from __future__ import annotations

import numpy as np
import pandas as pd

import r4_lib as L


def ols(y, X, names):
    X = np.column_stack([np.ones(len(y)), X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ b
    s2 = r @ r / (len(y) - X.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    return {n: f"{bb:+.3f} ({ss:.3f})" for n, bb, ss in zip(["const"] + names, b, se)}


def shares() -> pd.DataFrame:
    g = L.games()
    g = g[g.qual]
    rows = []
    for s in [2022] + L.WF_SEASONS:
        tr = g[g.season.isin([2023] if s == 2022 else list(range(2022, s)))]
        sh2 = (tr.total - tr.ht_t).sum() / tr.total.sum()
        shm = ((tr.margin - tr.ht_m) * tr.prior_m).sum() / (tr.prior_m ** 2).sum()
        rows.append({"season": s, "share2": sh2, "share_m": shm})
    return pd.DataFrame(rows)


def first_fresh(mkt: str) -> pd.DataFrame:
    q = L.ht_quotes()
    x = q[(q.market == mkt) & q.fresh & q.priced]
    x = x.sort_values("snapshot_ts").drop_duplicates(["game_id", "bookmaker"], keep="first")
    return x.merge(shares(), on="season", how="left")


def run() -> str:
    out = []
    sh = shares()
    out.append("### The shares used (fitted on earlier seasons)\n\n"
               + L.md(sh.assign(season=sh.season.map(L.SEASON_NAME)).round(4).to_dict("records")))

    # ── totals ──
    t = first_fresh("totals")
    t["mech"] = t.ht_t + t.prior_t * t.share2
    t["dev"] = t.line - t.mech                                   # book minus mechanical
    t["sur"] = t.ht_t - t.prior_t * (1 - t.share2)               # the first half's surprise
    t["miss"] = t.total - t.line                                 # final minus the book's total (+ = over wins)
    rows = []
    for (s, b), x in t.groupby(["season", "bookmaker"]):
        if len(x) < 25:
            continue
        rows.append({"season": L.SEASON_NAME[s], "book": b, "games": len(x),
                     "book - mechanical: mean": round(x.dev.mean(), 2), "sd": round(x.dev.std(), 2),
                     "mean |dev|": round(x.dev.abs().mean(), 2),
                     "share within 1 point": round((x.dev.abs() <= 1).mean(), 3),
                     "final - book: mean": round(x.miss.mean(), 2)})
    out.append("### Totals: each book's first fresh halftime total against the mechanical line\n\n"
               "`book - mechanical` > 0: the book hangs a higher total than half-time points + the pre-game "
               "total x the usual second-half share. `final - book` > 0: the game went over the book's total.\n\n"
               + L.md(rows))
    bins = [-np.inf, -10, -4, 4, 10, np.inf]
    labs = ["<= -10 (low-scoring half)", "-10 to -4", "-4 to +4", "+4 to +10", ">= +10 (high-scoring half)"]
    t["bin"] = pd.cut(t.sur, bins, labels=labs)
    rows = []
    for who, x0 in (("DraftKings", t[t.bookmaker == "draftkings"]), ("all decidable books", t[t.decidable]),
                    ("Pinnacle (reference)", t[t.bookmaker == "pinnacle"])):
        for bn, x in x0.groupby("bin", observed=True):
            rows.append({"book": who, "first-half surprise": str(bn), "quotes": len(x),
                         "book - mechanical": round(x.dev.mean(), 2),
                         "final - book (+ = over)": round(x.miss.mean(), 2),
                         "over won": round((x.miss > 0).mean(), 3),
                         "second half: actual - book implied": round(((x.total - x.ht_t) - (x.line - x.ht_t)).mean(), 2)})
    out.append("### Totals by the first half's surprise (half-time points minus the share of the pre-game total "
               "due by the half)\n\n" + L.md(rows))
    dk = t[t.bookmaker == "draftkings"]
    reg = [{"fit": "DraftKings line: (book total - half-time points)", **ols((dk.line - dk.ht_t).to_numpy(float),
                                                                             np.column_stack([dk.prior_t, dk.sur]), ["prior_t", "surprise"])},
           {"fit": "what happened: (final - half-time points), same games", **ols((dk.total - dk.ht_t).to_numpy(float),
                                                                                 np.column_stack([dk.prior_t, dk.sur]), ["prior_t", "surprise"])}]
    out.append(f"### Totals: the book's second half against what happened (DraftKings, {len(dk):,} games, OLS, SE in brackets)\n\n"
               + L.md(reg))

    # ── spreads ──
    p = first_fresh("spreads")
    p["mech"] = -(p.ht_m + p.prior_m * p.share_m)
    p["dev"] = p.line - p.mech                                   # + = the book gives the home side more points
    p["cover"] = p.margin + p.line                               # + = home covers the book's number
    p["fav_home"] = p.prior_m > 0
    p["fav_lead"] = np.where(p.fav_home, p.ht_m, -p.ht_m)       # the pre-game favourite's half-time lead
    rows = []
    for (s, b), x in p.groupby(["season", "bookmaker"]):
        if len(x) < 25:
            continue
        rows.append({"season": L.SEASON_NAME[s], "book": b, "games": len(x),
                     "book - mechanical: mean": round(x.dev.mean(), 2), "sd": round(x.dev.std(), 2),
                     "mean |dev|": round(x.dev.abs().mean(), 2),
                     "share within 1 point": round((x.dev.abs() <= 1).mean(), 3),
                     "home cover margin: mean": round(x.cover.mean(), 2)})
    out.append("### Spreads: each book's first fresh halftime home spread against the mechanical number\n\n"
               "`book - mechanical` > 0: the book gives the home side more points than the half-time margin + the "
               "pre-game margin x the usual share. `home cover margin` = final margin + the book's home spread.\n\n"
               + L.md(rows))
    fb = [-np.inf, -10, -4, -0.5, 0.5, 4, 10, np.inf]
    fl = ["favourite trails by 10+", "trails by 4-10", "trails by 1-4", "level", "leads by 1-4", "leads by 4-10", "leads by 10+"]
    p["fbin"] = pd.cut(p.fav_lead, fb, labels=fl)
    # the favourite's view of the book's line: points the pre-game favourite gives at the half
    p["fav_line"] = np.where(p.fav_home, p.line, -p.line)
    p["fav_mech"] = np.where(p.fav_home, p.mech, -p.mech)
    p["fav_cover"] = np.where(p.fav_home, p.cover, -p.cover)
    rows = []
    for who, x0 in (("DraftKings", p[p.bookmaker == "draftkings"]), ("all decidable books", p[p.decidable]),
                    ("Pinnacle (reference)", p[p.bookmaker == "pinnacle"])):
        for bn, x in x0.groupby("fbin", observed=True):
            rows.append({"book": who, "pre-game favourite at the half": str(bn), "quotes": len(x),
                         "book line (favourite's side)": round(x.fav_line.mean(), 2),
                         "mechanical (favourite's side)": round(x.fav_mech.mean(), 2),
                         "book - mechanical": round((x.fav_line - x.fav_mech).mean(), 2),
                         "favourite's cover margin": round(x.fav_cover.mean(), 2),
                         "favourite covered": round((x.fav_cover > 0).mean(), 3)})
    out.append("### Spreads by the pre-game favourite's half-time lead\n\n"
               "Lines on the favourite's side (negative = the favourite gives points). `favourite's cover margin` "
               "> 0: the favourite covered the book's halftime number.\n\n" + L.md(rows))
    dk = p[p.bookmaker == "draftkings"]
    surm = dk.ht_m - 0.5 * dk.prior_m
    reg = [{"fit": "DraftKings line: (-book home spread - half-time margin)",
            **ols((-dk.line - dk.ht_m).to_numpy(float), np.column_stack([dk.prior_m, surm]), ["prior_m", "surprise_m"])},
           {"fit": "what happened: (final margin - half-time margin), same games",
            **ols((dk.margin - dk.ht_m).to_numpy(float), np.column_stack([dk.prior_m, surm]), ["prior_m", "surprise_m"])}]
    out.append(f"### Spreads: the book's second-half margin against what happened (DraftKings, {len(dk):,} games, OLS, SE in brackets)\n\n"
               "surprise_m = half-time margin - half the pre-game margin (home view).\n\n" + L.md(reg))

    # is the book's stray from the mechanical number information or noise?
    rows = []
    for who, sel in (("DraftKings", "draftkings"), ("FanDuel", "fanduel"), ("BetMGM", "betmgm"),
                     ("Pinnacle (reference)", "pinnacle")):
        x = p[p.bookmaker == sel]
        if len(x) >= 100:
            rows.append({"market": "spread", "book": who, "games": len(x),
                         **ols(x.cover.to_numpy(float), x.dev.to_numpy(float).reshape(-1, 1), ["slope on (book - mechanical)"])})
        y = t[t.bookmaker == sel]
        if len(y) >= 100:
            rows.append({"market": "total", "book": who, "games": len(y),
                         **ols(y.miss.to_numpy(float), y.dev.to_numpy(float).reshape(-1, 1), ["slope on (book - mechanical)"])})
    out.append("### Is the book's stray from the mechanical number information or noise?\n\n"
               "Spread: home cover margin (final margin + book home spread) on (book - mechanical). Total: (final - book) "
               "on (book - mechanical). A slope of 0 means the book's stray is information (the book is right where it "
               "departs from the formula); +1 for the spread or -1 for the total means the stray is pure noise. "
               "In sample, one row per game per book.\n\n" + L.md(rows))
    return "\n\n".join(out)


if __name__ == "__main__":
    print(run())
