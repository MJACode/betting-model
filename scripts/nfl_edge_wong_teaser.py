"""
Wong teasers: are NFL teaser legs that move a line THROUGH 3 and 7 a +EV
2-team teaser at today's prices?  (docs/nfl_edge_search.md hypothesis.)

Run:  PYTHONIOENCODING=utf-8 python -m scripts.nfl_edge_wong_teaser
Reads only the local cache via scripts.nfl_edge_lib. No database, no network,
no Odds API credits.

CONSTRUCTION (written before any outcome was read)
==================================================
Proposition / one bet per proposition
    A teaser LEG is one side of one game's point spread (game x spread x side),
    or one side of one game's total (game x total x side). Each leg appears at
    most once per table. A teaser TICKET is 2 (or 3) legs from DIFFERENT games.

Side point x
    x is the side's own number: home x = -spread_line (nflverse spread_line is
    positive when HOME is favoured), away x = +spread_line. x > 0 = underdog.
    margin = the side's score margin (home: result, away: -result).
    Teased by t points the leg WINS if margin + x + t > 0, PUSHES if == 0,
    LOSES otherwise. Totals: an UNDER at T teased by t wins if total < T + t,
    an OVER wins if total > T - t, == is a push.

Sets fixed in advance (not fitted)
    WONG (classic):  dogs x in {+1.5, +2, +2.5}, favourites x in {-7.5, -8, -8.5}.
    PLACEBO (do not cross both 3 and 7 at 6 points):
                     dogs x in {+3.5 .. +5.5}, favourites x in {-3.5 .. -6.5}.
    The same starting lines are used for 6, 6.5, 7 and 10-point teasers. The
    full grid x = -10.5 .. +10.5 (every 0.5) is printed as the neighbourhood.

Decision time / line used
    (a) CLOSE: the nflverse closing spread_line / total_line, 1999-2025, all game
        types (REG + postseason). This is a closing-line study: the line is the
        last one before kickoff, not a bettable quote.
    (b) BETTABLE (2020-2025, odds_hist): for each game the latest snapshot_at
        with lead_hours >= 1.0 among BETTABLE_HIST books (the bettable venues
        and their historical names in the archive); every bettable quote at
        that snapshot forms the board. A quote more than 2.0 points from the
        board median is dropped as a mapping error (count printed). The leg
        qualifies on the BEST point any bettable book shows for that side at
        that snapshot (the book you would bet it at); the board-median line is
        a printed sensitivity. No quote after the decision snapshot is read.
        Total bucket in (b) comes from the bettable totals board at the latest
        totals snapshot >= 1h before kickoff (2020-2022 totals snapshots are
        ~120h old - printed).
    No feature in any rule is derived from the outcome.

Price used
    The data has NO teaser prices. Every table reports the leg break-even and
    the 2-team EV across a stated price grid: -110, -115, -120, -125, -130,
    -135, -140 (decimal d). 3-team 10-point: +200 .. -140 grid.
    Leg independence: EV2 = w^2 * d - 1 with w the leg win rate.
    Push grading (both reported):
      push = loss    : a pushed leg loses the ticket. EV = w^k d - 1.
      push = removed : a pushed leg is removed; if no other leg loses the ticket
                       is refunded (graded no action), any other loss loses it.
                       EV = w^k (d-1) - [1 - (w+p)^k]. This is a LOWER bound
                       on "removed": a book that reduces the ticket and pays
                       the shorter teaser price pays more than a refund.
    Leg tables also print the decided-leg rate w/(w+l).
    Break-even leg rate for a k-team ticket at decimal d: (1/d)^(1/k).

Independence check
    WONG legs at 6 points paired WITHIN the same week (season, week, game type),
    different games: (i) all within-week pairs -> joint win rate vs w^2;
    (ii) a realised betting record: each week the qualifying legs are paired in
    kickoff order (leg 1+2, 3+4, ...; an odd leftover leg is not bet), graded
    at each price, CI by cluster bootstrap on WEEK. The 10-point 3-team record
    groups legs three at a time the same way.

Added after the first run (labelled in the output, NOT registered): the compact
all-era grids for 6.5/7/10 points, and a "WONG dogs only" read, which the
first run's role split surfaced. It is printed as post-hoc, never as a
held-out result.

Fit / hold-out
    FIT seasons 1999-2019, HOLD-OUT 2020-2025 read once.
    Registered filter F1: keep the game-total buckets (<=41, 41.5-44.5,
    45-47.5, 48+) whose FIT WONG-leg win rate (push = loss) exceeds the 2-team
    break-even at -120 (73.85%). Registered filter F2: same rule on
    total bucket x (dog/fav) cells with >= 100 fit legs. Totals legs (d): keep
    each (side, starting total) cell with >= 100 fit legs whose fit win rate
    exceeds 73.85%. -120 is a reference point inside the grid, not a measured
    current market price.

Eras: 1999-2014, 2015-2025 (extra point moved back in 2015), 2020-2025.
Early/late: REG weeks 1-9, REG weeks 10+, postseason.
CI: 90%, cluster bootstrap; leg rates cluster on game_id, multi-leg tickets and
2-team EV intervals on week. Volume = legs (or tickets) per season.
Results are in UNITS (1 unit = 1 flat ticket).
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from scripts.nfl_edge_lib import (BETTABLE_HIST, am_to_dec, at_lead, boot_ci,
                                  games, odds_hist)

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 400)

PRICES2 = [-110, -115, -120, -125, -130, -135, -140]
PRICES3 = [200, 180, 160, 140, 120, 100, -110, -120, -130, -140]
FIT = (1999, 2019)
HOLD = (2020, 2025)
REF_PRICE = -120
BE2_REF = float((1 / am_to_dec(REF_PRICE)) ** 0.5)
WONG_DOG = [1.5, 2.0, 2.5]
WONG_FAV = [-7.5, -8.0, -8.5]
PLAC_DOG = [3.5, 4.0, 4.5, 5.0, 5.5]
PLAC_FAV = [-3.5, -4.0, -4.5, -5.0, -5.5, -6.0, -6.5]
ERAS = {"1999-2014": (1999, 2014), "2015-2025": (2015, 2025),
        "2020-2025": (2020, 2025), "FIT 1999-2019": FIT, "ALL 1999-2025": (1999, 2025)}
LOWVOL = 15  # legs/season at or below this = strict low-volume cell
NB = 2000


def be(price, k=2):
    return float((1 / am_to_dec(price)) ** (1 / k))


def ev_k(w, p, price, k=2, rule="loss"):
    d = float(am_to_dec(price))
    if rule == "loss":
        return w ** k * d - 1
    return w ** k * (d - 1) - (1 - (w + p) ** k)


def total_bucket(t):
    return pd.cut(t, [-np.inf, 41.0, 44.5, 47.5, np.inf],
                  labels=["<=41", "41.5-44.5", "45-47.5", "48+"])


# ─── legs ──────────────────────────────────────────────────────────────────

def spread_legs(g: pd.DataFrame, x_home: pd.Series, total: pd.Series) -> pd.DataFrame:
    base = pd.DataFrame({
        "game_id": g["game_id"].values, "season": g["season"].values,
        "week": g["week"].values, "game_type": g["game_type"].values,
        "kick": g["kick"].values, "roof": g["roof"].values,
        "location": g["location"].values, "total_ln": total.values})
    h = base.copy(); h["side"] = "home"; h["x"] = x_home.values; h["margin"] = g["result"].values
    a = base.copy(); a["side"] = "away"; a["x"] = -x_home.values; a["margin"] = -g["result"].values
    L = pd.concat([h, a], ignore_index=True)
    L["indoor"] = np.where(L["roof"].isin(["dome", "closed"]), "indoor", "outdoor")
    L["tb"] = total_bucket(L["total_ln"])
    L["role"] = np.where(L["x"] > 0, "dog", np.where(L["x"] < 0, "fav", "pk"))
    L["week_key"] = L["season"].astype(str) + "_" + L["game_type"] + "_" + L["week"].astype(str)
    L["phase"] = np.where(L["game_type"] != "REG", "post",
                          np.where(L["week"] <= 9, "REG wk1-9", "REG wk10+"))
    L["set"] = np.select(
        [L["x"].isin(WONG_DOG + WONG_FAV), L["x"].isin(PLAC_DOG + PLAC_FAV)],
        ["WONG", "PLACEBO"], "other")
    return L


def grade(L: pd.DataFrame, t: float) -> pd.DataFrame:
    s = L["margin"] + L["x"] + t
    out = L.copy()
    out["win"] = (s > 0).astype(int)
    out["push"] = (s == 0).astype(int)
    return out


def leg_stats(G: pd.DataFrame, cluster="game_id", n_seasons=None, nb=NB) -> dict:
    n = len(G)
    if n == 0:
        return {"legs": 0}
    w = G["win"].mean(); p = G["push"].mean(); l = 1 - w - p
    _, (lo, hi) = boot_ci(G["win"].values, G[cluster].values, n=nb)
    ns = n_seasons or G["season"].nunique()
    return {"legs": n, "per_szn": round(n / ns, 1), "win%": round(100 * w, 2),
            "push%": round(100 * p, 2), "loss%": round(100 * l, 2),
            "win%_dec": round(100 * w / (w + l), 2) if w + l > 0 else np.nan,
            "ci90_lo": round(100 * lo, 1), "ci90_hi": round(100 * hi, 1)}


def ev_row(G: pd.DataFrame, prices=PRICES2, k=2, nb=NB) -> dict:
    """EV per ticket (units) at each price under leg independence, both push rules,
    plus a week-cluster 90% CI on the -120 (2-team) or +100 (3-team) EV."""
    w = G["win"].mean(); p = G["push"].mean()
    out = {}
    for pr in prices:
        out[f"{pr:+d}"] = round(100 * ev_k(w, p, pr, k, "loss"), 1)
    ref = REF_PRICE if k == 2 else 100
    _, (lo, hi) = boot_ci(G["win"].values, G["week_key"].values, n=nb)
    out[f"EV{ref:+d}_lo"] = round(100 * ev_k(lo, 0, ref, k, "loss"), 1)
    out[f"EV{ref:+d}_hi"] = round(100 * ev_k(hi, 0, ref, k, "loss"), 1)
    out[f"rm{ref:+d}"] = round(100 * ev_k(w, p, ref, k, "removed"), 1)
    return out


def era_slice(L, era):
    a, b = ERAS[era]
    return L[(L["season"] >= a) & (L["season"] <= b)]


def nseas(era):
    a, b = ERAS[era]
    return b - a + 1


# ─── printing helpers ──────────────────────────────────────────────────────

def hdr(s):
    print("\n" + "=" * 100 + "\n" + s + "\n" + "=" * 100)


def grid_table(L, t, era, k=2, prices=PRICES2):
    rows = []
    G = grade(era_slice(L, era), t)
    for x in np.arange(-10.5, 10.51, 0.5):
        c = G[G["x"] == x]
        if len(c) == 0:
            continue
        r = {"x": f"{x:+.1f}", "teased": f"{x + t:+.1f}",
             "set": c["set"].iloc[0]}
        r.update(leg_stats(c, n_seasons=nseas(era)))
        w, p = c["win"].mean(), c["push"].mean()
        for pr in ([-110, -120, -130, -140] if k == 2 else [160, 100, -120]):
            r[f"EV{pr:+d}"] = round(100 * ev_k(w, p, pr, k, "loss"), 1)
        r["low"] = "LOW" if r["per_szn"] <= LOWVOL else ""
        rows.append(r)
    return pd.DataFrame(rows)


def set_table(L, t, eras, k=2, prices=PRICES2, sets=("WONG", "PLACEBO")):
    rows = []
    for era in eras:
        G = grade(era_slice(L, era), t)
        for s in sets:
            for role in ("dog+fav", "dog", "fav"):
                c = G[G["set"] == s]
                if role != "dog+fav":
                    c = c[c["role"] == role]
                r = {"era": era, "set": s, "role": role}
                r.update(leg_stats(c, n_seasons=nseas(era)))
                r.update(ev_row(c, prices, k))
                rows.append(r)
    return pd.DataFrame(rows)


def split_table(L, t, dim, eras=("FIT 1999-2019", "2020-2025", "1999-2014", "2015-2025"),
                setname="WONG"):
    rows = []
    for era in eras:
        G = grade(era_slice(L, era), t)
        G = G[G["set"] == setname]
        for lev, c in G.groupby(dim, observed=True):
            r = {"era": era, dim: lev}
            r.update(leg_stats(c, n_seasons=nseas(era)))
            w, p = c["win"].mean(), c["push"].mean()
            r["EV-120"] = round(100 * ev_k(w, p, -120, 2), 1)
            r["EV-130"] = round(100 * ev_k(w, p, -130, 2), 1)
            r["low"] = "LOW" if r["per_szn"] <= LOWVOL else ""
            rows.append(r)
    return pd.DataFrame(rows)


# ─── pairing (independence + realised record) ──────────────────────────────

def pair_checks(G: pd.DataFrame, label: str, prices=PRICES2, nb=4000):
    """G: graded legs of one set. (i) all within-week pairs, (ii) kickoff-order pairs."""
    G = G.sort_values(["week_key", "kick", "game_id"]).reset_index(drop=True)
    # (i) all within-week pairs from different games
    jw, jcnt, wk = [], [], []
    for key, c in G.groupby("week_key"):
        if len(c) < 2:
            continue
        wins = c["win"].values; gids = c["game_id"].values
        s = 0; n = 0
        for i, j in itertools.combinations(range(len(c)), 2):
            if gids[i] == gids[j]:
                continue
            s += wins[i] * wins[j]; n += 1
        if n:
            jw.append(s); jcnt.append(n); wk.append(key)
    jw = np.array(jw, float); jcnt = np.array(jcnt, float)
    joint = jw.sum() / jcnt.sum()
    # week-cluster bootstrap of joint and of the marginal product among weeks with pairs
    wk_set = set(wk)
    Gp = G[G["week_key"].isin(wk_set)]
    wsum = Gp.groupby("week_key")["win"].sum().reindex(wk).values
    wcnt = Gp.groupby("week_key")["win"].count().reindex(wk).values
    rng = np.random.default_rng(11)
    idx = rng.integers(0, len(wk), size=(nb, len(wk)))
    j_b = jw[idx].sum(1) / jcnt[idx].sum(1)
    m_b = (wsum[idx].sum(1) / wcnt[idx].sum(1)) ** 2
    diff = j_b - m_b
    marg = wsum.sum() / wcnt.sum()
    print(f"\n[{label}] all within-week pairs: weeks={len(wk)} pairs={int(jcnt.sum())} "
          f"joint win={100*joint:.2f}%  marginal^2={100*marg**2:.2f}%  "
          f"joint - marginal^2 = {100*(joint - marg**2):+.2f}pp "
          f"(90% CI {100*np.quantile(diff,0.05):+.2f} .. {100*np.quantile(diff,0.95):+.2f})")
    # (ii) kickoff-order pairing
    tickets = []
    for key, c in G.groupby("week_key", sort=False):
        c = c.reset_index(drop=True)
        used = []
        rows = list(c.itertuples())
        i = 0
        while i + 1 < len(rows):
            a, b = rows[i], rows[i + 1]
            if a.game_id == b.game_id:   # cannot pair the same game; skip ahead
                i += 1
                continue
            tickets.append({"week_key": key, "season": a.season,
                            "wins": a.win + b.win, "pushes": a.push + b.push,
                            "loss_any": int((a.win + a.push == 0) or (b.win + b.push == 0))})
            i += 2
    T = pd.DataFrame(tickets)
    if T.empty:
        print("  no tickets"); return
    rows = []
    for pr in prices:
        d = float(am_to_dec(pr))
        for rule in ("loss", "removed"):
            if rule == "loss":
                prof = np.where(T["wins"] == 2, d - 1, -1.0)
            else:
                prof = np.where(T["loss_any"] == 1, -1.0, np.where(T["wins"] == 2, d - 1, 0.0))
            roi, (lo, hi) = boot_ci(prof, T["week_key"].values, n=nb)
            rows.append({"price": f"{pr:+d}", "push": rule, "tickets": len(T),
                         "per_szn": round(len(T) / T["season"].nunique(), 1),
                         "units": round(prof.sum(), 2), "roi%": round(100 * roi, 2),
                         "ci90_lo": round(100 * lo, 1), "ci90_hi": round(100 * hi, 1),
                         "ticket_win%": round(100 * (T["wins"] == 2).mean(), 2)})
    print(f"[{label}] realised kickoff-order 2-team record (one ticket per pair, week-clustered CI):")
    R = pd.DataFrame(rows)
    print(R[R["push"] == "loss"].to_string(index=False))
    if T["pushes"].sum() > 0:
        print(R[R["push"] == "removed"].to_string(index=False))
    else:
        print("  (no pushed legs in these tickets: 'removed' identical to 'loss')")
    return T


def era_grid(L, t, eras=("1999-2014", "2015-2025", "2020-2025")):
    """Compact neighbourhood: every starting line x, leg win% / push% per era."""
    rows = []
    for x in np.arange(-10.5, 10.51, 0.5):
        r = {"x": f"{x:+.1f}", "teased": f"{x + t:+.1f}"}
        for era in eras:
            G = grade(era_slice(L, era), t)
            c = G[G["x"] == x]
            r[f"n {era}"] = len(c)
            r[f"win% {era}"] = round(100 * c["win"].mean(), 1) if len(c) else np.nan
            r[f"push% {era}"] = round(100 * c["push"].mean(), 1) if len(c) else np.nan
        r["set"] = L.loc[L["x"] == x, "set"].iloc[0] if (L["x"] == x).any() else ""
        if sum(r[f"n {e}"] for e in eras):
            rows.append(r)
    return pd.DataFrame(rows)


def realised_k(G: pd.DataFrame, k: int, label: str, prices, nb=4000):
    """k-team tickets: each week the legs are grouped in kickoff order (k at a time,
    distinct games, leftover legs not bet). push = loss and push = removed (refund
    when no other leg loses). CI by cluster bootstrap on week."""
    G = G.sort_values(["week_key", "kick", "game_id"])
    T = []
    for key, c in G.groupby("week_key", sort=False):
        c = c.drop_duplicates("game_id")
        rows = list(c.itertuples())
        for i in range(0, len(rows) - k + 1, k):
            grp = rows[i:i + k]
            T.append({"week_key": key, "season": grp[0].season,
                      "wins": sum(r.win for r in grp),
                      "loss_any": int(any(r.win + r.push == 0 for r in grp))})
    T = pd.DataFrame(T)
    if T.empty:
        print(f"[{label}] no tickets"); return
    out = []
    for pr in prices:
        d = float(am_to_dec(pr))
        for rule in ("loss", "removed"):
            prof = (np.where(T["wins"] == k, d - 1, -1.0) if rule == "loss" else
                    np.where(T["loss_any"] == 1, -1.0, np.where(T["wins"] == k, d - 1, 0.0)))
            roi, (lo, hi) = boot_ci(prof, T["week_key"].values, n=nb)
            out.append({"price": f"{pr:+d}", "push": rule, "tickets": len(T),
                        "per_szn": round(len(T) / T["season"].nunique(), 1),
                        "units": round(prof.sum(), 2), "roi%": round(100 * roi, 2),
                        "ci90_lo": round(100 * lo, 1), "ci90_hi": round(100 * hi, 1),
                        "ticket_win%": round(100 * (T["wins"] == k).mean(), 2)})
    R = pd.DataFrame(out)
    print(f"[{label}] realised kickoff-order {k}-team record:")
    print(R[R["push"] == "loss"].to_string(index=False))
    rm = R[R["push"] == "removed"]
    if not np.allclose(rm["units"].values, R[R["push"] == "loss"]["units"].values):
        print(rm.to_string(index=False))
    else:
        print("  (push = removed identical to push = loss: no pushed leg changed a ticket)")


# ─── bettable board (b) ────────────────────────────────────────────────────

def bettable_board():
    o = odds_hist(["spreads", "totals"])
    o = o[o["bookmaker"].isin(BETTABLE_HIST) & (o["lead_hours"] >= 1.0)]
    o = o[o["point"].notna()]
    out = {}
    for m in ("spreads", "totals"):
        y = o[o["market"] == m]
        last = y.groupby("game_id")["snapshot_at"].transform("max")
        y = y[y["snapshot_at"] == last].copy()
        y["med"] = y.groupby("game_id")["point"].transform("median")
        bad = (y["point"] - y["med"]).abs() > 2.0
        print(f"  {m}: board quotes={len(y)} games={y['game_id'].nunique()} "
              f"dropped >2pt from median={int(bad.sum())}; decision lead hours "
              f"median={y.groupby('game_id')['lead_hours'].min().median():.2f} "
              f"share>12h={100*(y.groupby('game_id')['lead_hours'].min() > 12).mean():.1f}%")
        out[m] = y[~bad]
    sp = out["spreads"]
    b = sp.groupby("game_id").agg(home_best=("point", "max"), home_worst=("point", "min"),
                                  home_med=("point", "median"), books=("bookmaker", "nunique"),
                                  lead=("lead_hours", "min")).reset_index()
    tt = out["totals"].groupby("game_id").agg(total_med=("point", "median"),
                                              total_lead=("lead_hours", "min")).reset_index()
    return b.merge(tt, on="game_id", how="left")


def bettable_legs(g: pd.DataFrame, board: pd.DataFrame, which="best") -> pd.DataFrame:
    gg = g.merge(board, on="game_id", how="inner")
    if which == "best":
        # home's best point = max home point; away's best = -(min home point)
        Lh = spread_legs(gg, gg["home_best"], gg["total_med"].fillna(gg["total_line"]))
        La = spread_legs(gg, gg["home_worst"], gg["total_med"].fillna(gg["total_line"]))
        L = pd.concat([Lh[Lh["side"] == "home"], La[La["side"] == "away"]], ignore_index=True)
    else:
        med = (gg["home_med"] * 2).round() / 2   # a .25 median rounds to a half point
        L = spread_legs(gg, med, gg["total_med"].fillna(gg["total_line"]))
    return L


# ─── main ──────────────────────────────────────────────────────────────────

def main():
    g = games()
    g = g[(g["season"] <= 2025) & g["result"].notna() & g["spread_line"].notna()].copy()
    L = spread_legs(g, -g["spread_line"], g["total_line"])
    print(f"games 1999-2025 with result and close: {len(g)}  legs: {len(L)}  "
          f"neutral-site games: {(g['location'] == 'Neutral').sum()}")
    print(f"2-team break-even leg rate: " + ", ".join(f"{p:+d}:{100*be(p):.2f}%" for p in PRICES2))
    print(f"3-team break-even leg rate: " + ", ".join(f"{p:+d}:{100*be(p,3):.2f}%" for p in PRICES3))

    # (a) grid, 6 points, by era
    for era in ("1999-2014", "2015-2025", "2020-2025"):
        hdr(f"(a) CLOSE, 6-pt leg grid by starting line x, {era}  "
            f"(EV = 2-team ticket EV % under independence, push = loss; LOW = <= {LOWVOL} legs/season)")
        print(grid_table(L, 6, era).to_string(index=False))

    # (a) WONG vs PLACEBO, 6 points, eras, EV across the price grid
    hdr("(a) CLOSE, 6-pt WONG vs PLACEBO by era: leg rates; 2-team EV % per ticket at each price "
        "(push=loss), week-cluster 90% CI at -120, and rm-120 = push removed (refund) at -120")
    print(set_table(L, 6, list(ERAS)).to_string(index=False))

    # (c) 6.5, 7 points (2-team), 10 points (3-team)
    for t in (6.5, 7.0):
        hdr(f"(c) CLOSE, {t}-pt WONG vs PLACEBO by era (2-team EV %)")
        print(set_table(L, t, ["1999-2014", "2015-2025", "2020-2025"]).to_string(index=False))
        hdr(f"(c) CLOSE, {t}-pt leg grid, 2015-2025")
        print(grid_table(L, t, "2015-2025").to_string(index=False))
    hdr("(c) CLOSE, 10-pt 3-team: WONG vs PLACEBO by era (3-team EV % per ticket at each price; CI at +100)")
    print(set_table(L, 10, ["1999-2014", "2015-2025", "2020-2025"], k=3, prices=PRICES3).to_string(index=False))
    hdr("(c) CLOSE, 10-pt leg grid, 2015-2025 (EV = 3-team ticket EV %, push = loss)")
    print(grid_table(L, 10, "2015-2025", k=3).to_string(index=False))
    for t in (6.5, 7.0, 10.0):
        hdr(f"(c) CLOSE, {t}-pt leg grid, every era (leg win% and push%)")
        print(era_grid(L, t).to_string(index=False))
    G10 = grade(L, 10)
    for per, (a, b) in (("1999-2014", (1999, 2014)), ("2015-2025", (2015, 2025)),
                        ("2020-2025", (2020, 2025))):
        c = G10[(G10["set"] == "WONG") & (G10["season"] >= a) & (G10["season"] <= b)]
        realised_k(c, 3, f"10-pt 3-team WONG close {per}", PRICES3)
        c = G10[(G10["set"] == "PLACEBO") & (G10["season"] >= a) & (G10["season"] <= b)]
        realised_k(c, 3, f"10-pt 3-team PLACEBO close {per}", [100, -120])
    hdr("(c) CLOSE, 6-pt 3-team: WONG by era (3-team EV % per ticket)")
    print(set_table(L, 6, ["1999-2014", "2015-2025", "2020-2025"], k=3, prices=PRICES3,
                    sets=("WONG",)).to_string(index=False))

    # splits for the WONG set
    for dim in ("tb", "side", "indoor", "role", "phase"):
        hdr(f"(a) CLOSE, 6-pt WONG legs split by {dim}")
        print(split_table(L, 6, dim).to_string(index=False))

    hdr("(a) CLOSE, 6-pt WONG legs: every season")
    G6 = grade(L, 6)
    W6 = G6[G6["set"] == "WONG"]
    P6 = G6[G6["set"] == "PLACEBO"]
    rows = []
    for s in sorted(W6["season"].unique()):
        r = {"season": s}
        c = W6[W6["season"] == s]
        st = leg_stats(c, n_seasons=1, nb=1000)
        r.update({k: st[k] for k in ("legs", "win%", "push%", "ci90_lo", "ci90_hi")})
        r["EV-120"] = round(100 * ev_k(c["win"].mean(), 0, -120), 1)
        pc = P6[P6["season"] == s]
        r["plac_legs"] = len(pc); r["plac_win%"] = round(100 * pc["win"].mean(), 2)
        rows.append(r)
    print(pd.DataFrame(rows).to_string(index=False))

    # neighbourhood: total bucket x role x side, fit vs hold-out
    hdr("(a) CLOSE, 6-pt WONG neighbourhood: total bucket x role x home/away, FIT 1999-2019 vs HOLD 2020-2025")
    rows = []
    Wf = W6[(W6["season"] >= FIT[0]) & (W6["season"] <= FIT[1])]
    Wh = W6[(W6["season"] >= HOLD[0]) & (W6["season"] <= HOLD[1])]
    for (tb, role, side), c in Wf.groupby(["tb", "role", "side"], observed=True):
        h = Wh[(Wh["tb"] == tb) & (Wh["role"] == role) & (Wh["side"] == side)]
        sf = leg_stats(c, n_seasons=21, nb=1000)
        sh = leg_stats(h, n_seasons=6, nb=1000) if len(h) else {"legs": 0}
        rows.append({"tb": tb, "role": role, "side": side,
                     "fit_legs": sf["legs"], "fit_win%": sf["win%"], "fit_lo": sf["ci90_lo"],
                     "fit_hi": sf["ci90_hi"],
                     "hold_legs": sh.get("legs", 0), "hold_per_szn": sh.get("per_szn"),
                     "hold_win%": sh.get("win%"), "hold_lo": sh.get("ci90_lo"),
                     "hold_hi": sh.get("ci90_hi"),
                     "hold_EV-120": round(100 * ev_k(h["win"].mean(), 0, -120), 1) if len(h) else np.nan,
                     "low": "LOW" if sh.get("per_szn", 0) and sh["per_szn"] <= LOWVOL else ""})
    print(pd.DataFrame(rows).to_string(index=False))

    # registered filters: fit -> hold-out, read once
    hdr(f"FIT/HOLD-OUT: registered filters fitted on 1999-2019 (threshold = 2-team break-even at "
        f"{REF_PRICE:+d} = {100*BE2_REF:.2f}%), 2020-2025 read once")
    fit_tb = Wf.groupby("tb", observed=True)["win"].agg(["mean", "size"])
    print("F1 fit win% by total bucket:", {k: round(100 * v, 2) for k, v in fit_tb["mean"].items()})
    keep1 = [k for k, v in fit_tb["mean"].items() if v > BE2_REF]
    fit_tr = Wf.groupby(["tb", "role"], observed=True)["win"].agg(["mean", "size"])
    keep2 = [k for k, r in fit_tr.iterrows() if r["size"] >= 100 and r["mean"] > BE2_REF]
    print("F1 kept buckets:", keep1)
    print("F2 kept (bucket, role):", keep2)
    rows = []
    for name, cf, ch in [
        ("WONG all", Wf, Wh),
        ("F1 kept", Wf[Wf["tb"].isin(keep1)], Wh[Wh["tb"].isin(keep1)]),
        ("F1 dropped", Wf[~Wf["tb"].isin(keep1)], Wh[~Wh["tb"].isin(keep1)]),
        ("F2 kept", Wf[[(a, b) in keep2 for a, b in zip(Wf["tb"], Wf["role"])]],
                    Wh[[(a, b) in keep2 for a, b in zip(Wh["tb"], Wh["role"])]]),
        ("F2 dropped", Wf[[(a, b) not in keep2 for a, b in zip(Wf["tb"], Wf["role"])]],
                       Wh[[(a, b) not in keep2 for a, b in zip(Wh["tb"], Wh["role"])]])]:
        for per, c, ns in (("fit", cf, 21), ("hold", ch, 6)):
            r = {"set": name, "period": per}
            r.update(leg_stats(c, n_seasons=ns, nb=4000))
            r.update(ev_row(c))
            rows.append(r)
    print(pd.DataFrame(rows).to_string(index=False))

    # independence + realised record
    hdr("INDEPENDENCE + REALISED 2-TEAM RECORD (6-pt WONG legs, closing line)")
    for per, (a, b) in (("1999-2014", (1999, 2014)), ("2015-2025", (2015, 2025)),
                        ("2020-2025", (2020, 2025)), ("FIT 1999-2019", FIT)):
        pair_checks(W6[(W6["season"] >= a) & (W6["season"] <= b)], f"WONG {per}")
    Hf = Wh[Wh["tb"].isin(keep1)]
    if len(Hf):
        pair_checks(Hf, "WONG F1-kept HOLD 2020-2025")
    pair_checks(P6[(P6["season"] >= 2015)], "PLACEBO 2015-2025")

    # (b) bettable line 2020-2025
    hdr("(b) BETTABLE board, latest snapshot >= 1h before kickoff, 2020-2025")
    board = bettable_board()
    gb = g[(g["season"] >= 2020) & (g["season"] <= 2025)]
    Lb = bettable_legs(gb, board, "best")
    Lm = bettable_legs(gb, board, "median")
    Lc = spread_legs(gb, -gb["spread_line"], gb["total_line"])
    # agreement of WONG qualification: bettable-best vs close
    k = ["game_id", "side"]
    cmp_ = Lb[k + ["x", "set"]].merge(Lc[k + ["x", "set"]], on=k, suffixes=("_bet", "_close"))
    print("bettable-best x minus close x (side-relative):",
          (cmp_["x_bet"] - cmp_["x_close"]).round(1).value_counts().sort_index().to_dict())
    print("WONG qualification crosstab (rows = bettable best line, cols = nflverse close):")
    print(pd.crosstab(cmp_["set_bet"], cmp_["set_close"]).to_string())
    rows = []
    for t in (6, 6.5, 7):
        for name, LL in (("bettable best", Lb), ("bettable median", Lm), ("nflverse close", Lc)):
            G = grade(LL, t)
            for s in ("WONG", "PLACEBO"):
                c = G[G["set"] == s]
                r = {"teaser": t, "line": name, "set": s}
                r.update(leg_stats(c, n_seasons=6))
                r.update(ev_row(c))
                rows.append(r)
    print(pd.DataFrame(rows).to_string(index=False))
    # legs that qualify on one basis but not the other (6 pt)
    Gb = grade(Lb, 6).merge(Lc[k + ["set"]].rename(columns={"set": "set_close"}), on=k)
    for lab, c in (("WONG on bettable AND close", Gb[(Gb["set"] == "WONG") & (Gb["set_close"] == "WONG")]),
                   ("WONG on bettable, NOT close", Gb[(Gb["set"] == "WONG") & (Gb["set_close"] != "WONG")]),
                   ):
        st = leg_stats(c, n_seasons=6)
        print(f"  {lab}: {st}")
    Gc = grade(Lc, 6).merge(Lb[k + ["set"]].rename(columns={"set": "set_bet"}), on=k)
    c = Gc[(Gc["set"] == "WONG") & (Gc["set_bet"] != "WONG")]
    print(f"  WONG on close, NOT on bettable (graded at close): {leg_stats(c, n_seasons=6)}")
    hdr("(b) BETTABLE best line, 6-pt leg grid 2020-2025")
    Lb2 = Lb.copy()
    Lb2["season"] = Lb2["season"].astype(int)
    print(grid_table(Lb2, 6, "2020-2025").to_string(index=False))
    hdr("(b) BETTABLE best line, 6-pt WONG: every season and early/late, 2-team realised record")
    Gb6 = grade(Lb, 6)
    Wb = Gb6[Gb6["set"] == "WONG"]
    def _szn(c):
        s = leg_stats(c, n_seasons=1, nb=1000)
        s["EV-120"] = round(100 * ev_k(c["win"].mean(), c["push"].mean(), -120), 1)
        s["EV-130"] = round(100 * ev_k(c["win"].mean(), c["push"].mean(), -130), 1)
        return pd.Series(s)
    print(Wb.groupby("season").apply(_szn).to_string())
    print(Wb.groupby("role").apply(lambda c: pd.Series({**leg_stats(c, n_seasons=6), **ev_row(c)})).to_string())
    print(Wb.groupby("side").apply(lambda c: pd.Series(leg_stats(c, n_seasons=6, nb=1000))).to_string())
    print(Wb.groupby("phase").apply(lambda c: pd.Series(leg_stats(c, n_seasons=6, nb=1000))).to_string())
    print(Wb.groupby("tb", observed=True).apply(lambda c: pd.Series(leg_stats(c, n_seasons=6, nb=1000))).to_string())
    pair_checks(Wb, "WONG bettable-best 2020-2025")
    Wbf = Wb[Wb["tb"].isin(keep1)]
    if len(Wbf):
        r = leg_stats(Wbf, n_seasons=6, nb=4000); r.update(ev_row(Wbf))
        print("  F1-kept (fit on close 1999-2019) on bettable 2020-2025:", r)
        pair_checks(Wbf, "WONG bettable-best F1-kept 2020-2025")
    hdr("(b) BETTABLE best line, 10-pt 3-team WONG / PLACEBO 2020-2025")
    Gb10 = grade(Lb, 10)
    rows = []
    for s in ("WONG", "PLACEBO"):
        for role in ("dog+fav", "dog", "fav"):
            c = Gb10[Gb10["set"] == s]
            if role != "dog+fav":
                c = c[c["role"] == role]
            r = {"set": s, "role": role}
            r.update(leg_stats(c, n_seasons=6)); r.update(ev_row(c, PRICES3, 3))
            rows.append(r)
    print(pd.DataFrame(rows).to_string(index=False))
    realised_k(Gb10[Gb10["set"] == "WONG"], 3, "10-pt 3-team WONG bettable-best 2020-2025", PRICES3)

    # POST-HOC (not registered): the dog half of the WONG set. Seen in the role
    # split above; reported so the reader can see it, NOT a fitted/held-out result.
    hdr("POST-HOC, NOT REGISTERED: WONG dogs only (+1.5..+2.5 teased 6), realised 2-team records")
    for lab, c in (("close 1999-2014", W6[(W6["role"] == "dog") & (W6["season"] <= 2014)]),
                   ("close 2015-2019", W6[(W6["role"] == "dog") & (W6["season"].between(2015, 2019))]),
                   ("close 2020-2025", W6[(W6["role"] == "dog") & (W6["season"] >= 2020)]),
                   ("bettable-best 2020-2025", Wb[Wb["role"] == "dog"])):
        st = leg_stats(c, n_seasons=c["season"].nunique(), nb=4000)
        print(f"  {lab}: legs={st['legs']} per_szn={st['per_szn']} win%={st['win%']} "
              f"ci90={st['ci90_lo']}..{st['ci90_hi']}")
        realised_k(c, 2, f"dogs-only {lab}", PRICES2)

    # (d) totals teaser legs
    hdr("(d) CLOSE totals teaser legs, 6 pt: UNDER teased up / OVER teased down, by starting total and era")
    gt = g[g["total_line"].notna() & g["total"].notna()]
    TL = []
    for sd in ("under", "over"):
        df = pd.DataFrame({"game_id": gt["game_id"].values, "season": gt["season"].values,
                           "week": gt["week"].values, "game_type": gt["game_type"].values,
                           "T": gt["total_line"].values, "tot": gt["total"].values})
        df["side"] = sd
        s = (df["T"] + 6 - df["tot"]) if sd == "under" else (df["tot"] - (df["T"] - 6))
        df["win"] = (s > 0).astype(int); df["push"] = (s == 0).astype(int)
        df["week_key"] = df["season"].astype(str) + "_" + df["game_type"] + "_" + df["week"].astype(str)
        TL.append(df)
    TL = pd.concat(TL, ignore_index=True)
    TL["Tb"] = np.clip(np.floor(TL["T"] / 1.0) * 1.0, 35, 55)  # 1-point bins, ends pooled
    rows = []
    for (sd, Tb), c in TL.groupby(["side", "Tb"]):
        r = {"side": sd, "T_bin": f"{Tb:.0f}-{Tb+0.5:.1f}" if 35 < Tb < 55 else ("<=35.5" if Tb == 35 else ">=55")}
        for era in ("1999-2014", "2015-2025", "2020-2025"):
            a, b = ERAS[era]
            cc = c[(c["season"] >= a) & (c["season"] <= b)]
            r[f"n {era}"] = len(cc)
            r[f"win% {era}"] = round(100 * cc["win"].mean(), 1) if len(cc) else np.nan
            r[f"push% {era}"] = round(100 * cc["push"].mean(), 1) if len(cc) else np.nan
        _, (lo, hi) = boot_ci(c[c["season"] >= 2015]["win"].values, c[c["season"] >= 2015]["game_id"].values, n=1000) \
            if (c["season"] >= 2015).any() else (np.nan, (np.nan, np.nan))
        r["2015-25 ci90"] = f"{100*lo:.1f}..{100*hi:.1f}"
        rows.append(r)
    print(pd.DataFrame(rows).to_string(index=False))
    # registered totals filter: fit 1999-2019 cells by exact starting total
    TLf = TL[(TL["season"] >= FIT[0]) & (TL["season"] <= FIT[1])]
    TLh = TL[(TL["season"] >= HOLD[0]) & (TL["season"] <= HOLD[1])]
    cell = TLf.groupby(["side", "T"])["win"].agg(["mean", "size"])
    keepT = [k for k, r in cell.iterrows() if r["size"] >= 100 and r["mean"] > BE2_REF]
    print(f"totals registered cells kept on FIT (>=100 legs, win > {100*BE2_REF:.2f}%): {keepT}")
    rows = []
    for name, cf, ch in (("totals kept", TLf[[ (a, b) in keepT for a, b in zip(TLf['side'], TLf['T'])]],
                                           TLh[[ (a, b) in keepT for a, b in zip(TLh['side'], TLh['T'])]]),
                         ("all unders", TLf[TLf["side"] == "under"], TLh[TLh["side"] == "under"]),
                         ("all overs", TLf[TLf["side"] == "over"], TLh[TLh["side"] == "over"])):
        for per, c, ns in (("fit", cf, 21), ("hold", ch, 6)):
            if len(c) == 0:
                rows.append({"set": name, "period": per, "legs": 0}); continue
            r = {"set": name, "period": per}
            r.update(leg_stats(c, n_seasons=ns, nb=2000))
            r.update(ev_row(c))
            rows.append(r)
    print(pd.DataFrame(rows).to_string(index=False))

    # (d) totals at bettable board, near-kickoff only
    hdr("(d) BETTABLE totals board (median bettable total at latest snapshot >= 1h, lead <= 12h only), 6-pt legs 2020-2025")
    bt = board[board["total_lead"] <= 12][["game_id", "total_med"]]
    gtb = gt.merge(bt, on="game_id")
    gtb["Tbet"] = (gtb["total_med"] * 2).round() / 2
    rows = []
    for sd in ("under", "over"):
        s = (gtb["Tbet"] + 6 - gtb["total"]) if sd == "under" else (gtb["total"] - (gtb["Tbet"] - 6))
        c = pd.DataFrame({"game_id": gtb["game_id"], "season": gtb["season"],
                          "win": (s > 0).astype(int), "push": (s == 0).astype(int),
                          "week_key": gtb["season"].astype(str) + "_" + gtb["game_type"] + "_" + gtb["week"].astype(str),
                          "T": gtb["Tbet"]})
        kept = c[[ (sd, t) in keepT for t in c["T"]]]
        for name, cc in ((f"{sd} all", c), (f"{sd} registered-kept", kept)):
            if len(cc) == 0:
                rows.append({"set": name, "legs": 0}); continue
            r = {"set": name}
            r.update(leg_stats(cc, n_seasons=cc["season"].nunique(), nb=2000))
            r.update(ev_row(cc))
            rows.append(r)
    print(f"games with a bettable total <= 12h before kickoff, by season: "
          f"{gtb.groupby('season').size().to_dict()}")
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
