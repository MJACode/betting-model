"""UFC prop markets at BestFightOdds' last recorded prices, 2021-06 on
(docs/ufc_market_audit.md section 5). Run from the study folder after
prop_load.py.

  python prop_grade.py blind      # every price bet blind, by market, side, book and year
  python prop_grade.py models     # three mechanisms per market, walk-forward, kill tests

UNITS. Every bet is 1 unit to win, risk capped at 3 (stake_for), at the
deciding book's own price. The 90% interval is a bootstrap over cards (a
card's bets are not independent). "Best of five" takes, per prop, the best
price among DraftKings, FanDuel, BetMGM, Caesars and BetRivers.

THE THREE MECHANISMS (each decided at the best of five, EV against its own
probability, a bet when EV >= the cut):
  1. price:  the five books' consensus no-vig probability (power method over
             the market's full set of outcomes), so the bet is a book that
             strays from the others.
  2. anchor: that probability as a fixed logit offset plus a ridge-penalised
             fit on the fighters' pre-fight inputs (models/ufc_ratings), fitted
             on earlier years only.
  3. ml:     the method and round markets rescaled so each fighter's outcomes
             sum to the fight-winner market's no-vig chance (the deepest
             market), and "goes the distance" from the rescaled decisions.
"""
import sys

import numpy as np
import pandas as pd

RNG = np.random.default_rng(20261113)
BOOKS = ["draftkings", "fanduel", "betmgm", "williamhill_us", "betrivers"]
CUTS = [0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20]
MAIN_CUT = 0.08
TEST_YEARS = [2022, 2023, 2024, 2025, 2026]

D = pd.read_parquet("props.parquet")
D = D[D.bookmaker.isin(BOOKS)].copy()
X = pd.read_parquet("fights.parquet").set_index("game_id")

FAMILIES = {
    "KO/TKO by fighter": ([8], "f"),
    "Submission by fighter": ([9], "f"),
    "Decision by fighter": ([11], "f"),
    "Inside the distance by fighter": ([10], "f"),
    "Goes the distance": ([1], "0"),
    "Fighter wins in round N": ([13, 14, 15, 16, 17], "f"),
    "Fight ends in round N": ([22, 23, 24, 25, 26], "0"),
    "Fighter wins by method in round N": ([174, 175, 179, 180, 181, 182, 183, 184, 185, 186], "f"),
    "Round totals": ([32, 33, 34, 35], "0"),
}


def units(dec, won):
    risk = np.minimum(1.0 / (dec - 1.0), 3.0)
    return np.where(won == 1, risk * (dec - 1.0), -risk), risk


def summary(df, label=None):
    """bets, units, return and the 90% card-bootstrap interval of df (dec, won, event_date, year)."""
    df = df[df.won.notna()]
    if df.empty:
        return dict(bets=0, units=0.0, ret=np.nan, ci90="", years_pos="")
    u, r = units(df.dec.to_numpy(), df.won.to_numpy())
    g = pd.DataFrame({"e": df.event_date.to_numpy(), "u": u, "r": r}).groupby("e").sum()
    idx = RNG.integers(0, len(g), size=(2000, len(g)))
    boot = g.u.to_numpy()[idx].sum(1) / g.r.to_numpy()[idx].sum(1)
    lo, hi = np.percentile(boot, [5, 95]) * 100
    by = pd.DataFrame({"y": df.year.to_numpy(), "u": u, "r": r}).groupby("y").sum()
    by = by[by.r > 0]
    out = dict(bets=len(df), units=round(u.sum(), 1), ret=round(100 * u.sum() / r.sum(), 1),
               ci90=f"[{lo:+.1f}, {hi:+.1f}]", years_pos=f"{(by.u > 0).sum()}/{len(by)}")
    if label:
        out = {"": label, **out}
    return out


def best_of_five(df):
    """Per (fight, prop, fighter, side): the row at the best price among the five."""
    df = df.sort_values("dec", ascending=False)
    return df.drop_duplicates(["matchup_id", "prop_type", "team", "side"])


def family_rows(name):
    pts, kind = FAMILIES[name]
    df = D[D.prop_type.isin(pts)]
    return df[df.team > 0] if kind == "f" else df[df.team == 0]


# ── blind ────────────────────────────────────────────────────────────────────

def blind():
    rows = []
    for name in FAMILIES:
        df = family_rows(name)
        for side, sname in ((1, "yes"), (2, "no")):
            s = df[df.side == side]
            if s.won.notna().sum() < 100:
                continue
            for bk in BOOKS:
                rows.append({"market": name, "side": sname, "book": bk, **summary(s[s.bookmaker == bk])})
            rows.append({"market": name, "side": sname, "book": "best of five", **summary(best_of_five(s))})
    t = pd.DataFrame(rows)
    print("\n== every price bet blind, by market, side and book (2021-06 to 2026-11)")
    print(t.to_string(index=False))

    rows = []
    for name in FAMILIES:
        df = best_of_five(family_rows(name))
        for side, sname in ((1, "yes"), (2, "no")):
            s = df[df.side == side]
            if s.won.notna().sum() < 100:
                continue
            for y in sorted(s.year.unique()):
                rows.append({"market": name, "side": sname, "year": y, **summary(s[s.year == y])})
    print("\n== best of five, by year")
    print(pd.DataFrame(rows).drop(columns=["years_pos"]).to_string(index=False))

    # favourite / underdog split of the fighter props' "yes" side
    fav = fight_winner_fair()
    rows = []
    for name, (pts, kind) in FAMILIES.items():
        if kind != "f":
            continue
        s = best_of_five(family_rows(name))
        s = s[s.side == 1].join(fav, on="matchup_id")
        s["is_fav"] = np.where(s.team == 1, s.p1 > 0.5, s.p1 < 0.5)
        for who in (True, False):
            rows.append({"market": name, "fighter": "favourite" if who else "underdog",
                         **summary(s[s.is_fav == who])})
    print("\n== fighter props, yes side at the best of five: the fight's favourite vs underdog")
    print(pd.DataFrame(rows).to_string(index=False))

    # the DQ / could-not-continue sensitivity: graded as a TKO
    rows = []
    for name in ("KO/TKO by fighter", "Inside the distance by fighter", "Fighter wins in round N"):
        s = best_of_five(family_rows(name))
        s = s[s.side == 1]
        alt = s.assign(won=s.won_as_tko)
        rows.append({"market": name, "graded": "void (main)", **summary(s)})
        rows.append({"market": name, "graded": "as a TKO", **summary(alt)})
    print("\n== a DQ or could-not-continue end voided vs graded as a TKO (yes side, best of five)")
    print(pd.DataFrame(rows).to_string(index=False))


# ── no-vig probabilities ─────────────────────────────────────────────────────

def power_novig(p):
    """Power de-vig: the k with sum(p_i ** k) = 1 (p: implied probabilities)."""
    p = np.asarray(p, float)
    lo, hi = 0.5, 5.0
    for _ in range(60):
        k = (lo + hi) / 2
        if (p ** k).sum() > 1:
            lo = k
        else:
            hi = k
    return p ** k


def set_fair(sets, sched=None):
    """Consensus no-vig per outcome. sets: lists of (prop_type, team, side),
    each a full set of outcomes; sched: only fights scheduled for that many
    rounds. Returns a series keyed (matchup_id, prop_type, team, side): the
    mean over the books that priced the full set."""
    out = []
    base = D if sched is None else D[D.sched == sched]
    for members in sets:
        mem = pd.MultiIndex.from_tuples(members, names=["prop_type", "team", "side"])
        sub = base.merge(mem.to_frame(index=False), on=["prop_type", "team", "side"])
        full = sub.groupby(["matchup_id", "bookmaker"]).size()
        full = full[full == len(members)].index
        sub = sub.set_index(["matchup_id", "bookmaker"]).loc[full].reset_index()
        sub["imp"] = 1 / sub.dec
        fair = sub.groupby(["matchup_id", "bookmaker"]).imp.transform(lambda s: power_novig(s.to_numpy()))
        sub["fair"] = fair
        out.append(sub.groupby(["matchup_id", "prop_type", "team", "side"]).fair.mean())
    return pd.concat(out).groupby(level=[0, 1, 2, 3]).mean()


def fight_winner_fair():
    f = set_fair([[(0, 0, 1), (0, 0, 2)]]).xs(1, level="side").reset_index()
    return f[f.prop_type == 0].set_index("matchup_id").fair.rename("p1").to_frame()


METHOD = [(8, 1, 1), (9, 1, 1), (11, 1, 1), (8, 2, 1), (9, 2, 1), (11, 2, 1)]
TWO_WAY = {name: [[(pt, tn, 1), (pt, tn, 2)] for pt in FAMILIES[name][0]
                  for tn in ((1, 2) if FAMILIES[name][1] == "f" else (0,))]
           for name in ("Goes the distance", "Inside the distance by fighter", "Round totals")}


def round_sets(sched):
    """Round betting: each fighter wins in round 1..sched, or by decision."""
    return [[(12 + n, tn, 1) for tn in (1, 2) for n in range(1, sched + 1)] + [(11, 1, 1), (11, 2, 1)]]


def ends_sets(sched):
    return [[(21 + n, 0, 1) for n in range(1, sched + 1)] + [(1, 0, 1)]]


# ── the anchored fit ─────────────────────────────────────────────────────────

FIGHTER_IN = ["ko_win", "sub_win", "dec_rate", "fin_rate", "kd15", "sub15", "td15", "slpm",
              "sapm", "avg_mins", "n", "ko_loss", "win_rate", "elo", "age", "reach"]
FIGHT_IN = ["fin_rate", "dec_rate", "ko_loss", "kd15", "sub15", "td15", "slpm", "sapm",
            "avg_mins", "n"]


def inputs(rows, kind):
    """Pre-fight inputs for each outcome row (matchup_id, team), oriented to
    the fighter the prop is about (x) against his opponent (y), or summed
    over both for a fight prop."""
    F = D.drop_duplicates("matchup_id").set_index("matchup_id")[["game_id", "f1_is_a"]]
    r = rows.join(F, on="matchup_id")
    fx = X.reindex(r.game_id)
    out = {}
    if kind == "f":
        x_is_a = np.where(r.team.to_numpy() == 1, r.f1_is_a.to_numpy(), ~r.f1_is_a.to_numpy().astype(bool))
        for c in FIGHTER_IN:
            a, b = fx[f"a_{c}"].to_numpy(float), fx[f"b_{c}"].to_numpy(float)
            out[f"x_{c}"] = np.where(x_is_a, a, b)
            out[f"y_{c}"] = np.where(x_is_a, b, a)
    else:
        for c in FIGHT_IN:
            out[f"s_{c}"] = fx[f"a_{c}"].to_numpy(float) + fx[f"b_{c}"].to_numpy(float)
        out["abs_d_elo"] = np.abs(fx.a_elo.to_numpy(float) - fx.b_elo.to_numpy(float))
    out["women"] = fx.women.to_numpy(float)
    out["five"] = (fx.sched.to_numpy(float) == 5).astype(float)
    return pd.DataFrame(out, index=rows.index)


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def fit_offset(Z, off, y, ridge=30.0):
    """Logistic regression on Z with a fixed offset, an unpenalised intercept
    and a ridge penalty on the slopes (IRLS)."""
    A = np.column_stack([np.ones(len(Z)), Z])
    w = np.zeros(A.shape[1])
    pen = np.full(A.shape[1], ridge)
    pen[0] = 0.0
    for _ in range(50):
        eta = off + A @ w
        p = 1 / (1 + np.exp(-eta))
        g = A.T @ (y - p) - pen * w
        H = (A * (p * (1 - p))[:, None]).T @ A + np.diag(pen)
        step = np.linalg.solve(H, g)
        w += step
        if np.abs(step).max() < 1e-8:
            break
    return w


def walk_forward(rows, kind, placebo=False):
    """rows: one per outcome (matchup_id, prop_type, team, side, fair, won, year).
    Returns the anchored probability for each test-year row."""
    Z = inputs(rows, kind)
    p_out = pd.Series(np.nan, index=rows.index)
    for y in TEST_YEARS:
        tr = (rows.year < y) & rows.won.notna()
        te = rows.year == y
        if tr.sum() < 200 or not te.any():
            continue
        mu, sd = Z[tr].mean(), Z[tr].std().replace(0, 1).fillna(1)
        z = ((Z - mu) / sd).fillna(0.0).clip(-4, 4).to_numpy()
        ztr = z[tr.to_numpy()]
        if placebo:
            ztr = ztr[RNG.permutation(len(ztr))]
        w = fit_offset(ztr, logit(rows.fair[tr].to_numpy()), rows.won[tr].to_numpy())
        eta = logit(rows.fair[te].to_numpy()) + w[0] + z[te.to_numpy()] @ w[1:]
        p_out[te] = 1 / (1 + np.exp(-eta))
    return p_out


# ── the three mechanisms ─────────────────────────────────────────────────────

def outcome_rows(name):
    """One row per (fight, outcome) of a market: its consensus fair chance,
    the fight-winner-coherent chance where the market has one, the best of
    five's price and the result."""
    pts, kind = FAMILIES[name]
    best = best_of_five(family_rows(name))
    if name in TWO_WAY:
        fair = set_fair(TWO_WAY[name])
    elif name in ("KO/TKO by fighter", "Submission by fighter", "Decision by fighter"):
        fair = set_fair([METHOD])
    elif name == "Fighter wins in round N":
        fair = pd.concat([set_fair(round_sets(3), 3), set_fair(round_sets(5), 5)])
    elif name == "Fight ends in round N":
        fair = pd.concat([set_fair(ends_sets(3), 3), set_fair(ends_sets(5), 5)])
    else:
        return None
    best = best.join(fair.rename("fair"), on=["matchup_id", "prop_type", "team", "side"])
    best = best[best.fair.notna() & best.prop_type.isin(pts)]
    return best


def coherent(rows, name):
    """Mechanism 3: rescale each fighter's method or round outcomes to the
    fight-winner no-vig chance. NaN where the market has no such link."""
    if name not in ("KO/TKO by fighter", "Submission by fighter", "Decision by fighter",
                    "Fighter wins in round N", "Inside the distance by fighter", "Goes the distance"):
        return pd.Series(np.nan, index=rows.index)
    ml = fight_winner_fair().p1
    meth = set_fair([METHOD]).reset_index()
    meth = meth.merge(ml, left_on="matchup_id", right_index=True)
    tot = meth.groupby(["matchup_id", "team"]).fair.transform("sum")
    meth["scaled"] = meth.fair * np.where(meth.team == 1, meth.p1, 1 - meth.p1) / tot
    m = meth.set_index(["matchup_id", "prop_type", "team"]).scaled
    if name == "Inside the distance by fighter":
        ko = m.xs(8, level="prop_type")
        sub = m.xs(9, level="prop_type")
        itd = (ko + sub).rename("c")
        c = rows.join(itd, on=["matchup_id", "team"]).c
        return np.where(rows.side == 1, c, 1 - c)
    if name == "Goes the distance":
        dec = m.xs(11, level="prop_type").groupby(level="matchup_id").sum().rename("c")
        c = rows.join(dec, on="matchup_id").c
        return np.where(rows.side == 1, c, 1 - c)
    if name == "Fighter wins in round N":
        rr = pd.concat([set_fair(round_sets(3), 3), set_fair(round_sets(5), 5)]).rename("fair")
        rr = rr.reset_index().merge(ml, left_on="matchup_id", right_index=True)
        tot = rr.groupby(["matchup_id", "team"]).fair.transform("sum")
        rr["c"] = rr.fair * np.where(rr.team == 1, rr.p1, 1 - rr.p1) / tot
        return rows.join(rr.set_index(["matchup_id", "prop_type", "team", "side"]).c,
                         on=["matchup_id", "prop_type", "team", "side"]).c
    return rows.join(m.rename("c"), on=["matchup_id", "prop_type", "team"]).c


def bets(rows, prob, cut):
    ev = prob * rows.dec - 1
    return rows[(ev >= cut) & rows.won.notna() & rows.year.isin(TEST_YEARS)]


def models():
    for name, (pts, kind) in FAMILIES.items():
        rows = outcome_rows(name)
        if rows is None or len(rows) < 500:
            print(f"\n== {name}: no full outcome set to take a no-vig price from")
            continue
        rows = rows.reset_index(drop=True)
        probs = {"1 price": rows.fair, "2 anchor": walk_forward(rows, kind),
                 "3 ml": pd.Series(coherent(rows, name), index=rows.index)}
        print(f"\n== {name}: {len(rows):,} outcomes priced, {rows.matchup_id.nunique():,} fights")
        out = []
        for mech, p in probs.items():
            if p.notna().sum() == 0:
                continue
            for cut in CUTS:
                out.append({"mechanism": mech, "cut": cut, **summary(bets(rows, p, cut))})
        print(pd.DataFrame(out).to_string(index=False))
        for mech, p in probs.items():
            if p.notna().sum() == 0:
                continue
            b = bets(rows, p, MAIN_CUT)
            if len(b) < 30:
                continue
            res = summary(b)
            if res["ret"] <= 0:
                continue
            print(f"  -- kill tests, mechanism {mech} at EV >= {MAIN_CUT}")
            early, late = b[b.year <= 2023], b[b.year >= 2024]
            print("   ", summary(early, "2022-23"), "\n   ", summary(late, "2024-26"))
            for side in (1, 2):
                print("   ", summary(b[b.side == side], f"side {side}"))
            print("   ", summary(b[b.dec >= 3], "price +200 or longer"), "\n   ",
                  summary(b[b.dec < 3], "shorter than +200"))
            if mech == "2 anchor":
                pl = []
                for _ in range(20):
                    pp = walk_forward(rows, kind, placebo=True)
                    s = summary(bets(rows, pp, MAIN_CUT))
                    pl.append(s["ret"])
                pl = np.array(pl, float)
                print(f"    placebo (inputs shuffled within the training years, 20 runs): "
                      f"median return {np.nanmedian(pl):+.1f}%, {np.mean(pl >= res['ret']):.0%} "
                      f"at or above the real {res['ret']:+.1f}%")


if __name__ == "__main__":
    {"blind": blind, "models": models}[sys.argv[1]]()
