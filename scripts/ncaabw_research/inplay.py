"""Women's in-play spread and total: a game-state model against the in-play
quotes of every 5-minute snapshot.

THE MODEL (the men's ncaab_live_ig shape, on the women's clock): what is still
to come, the margin and the total, is normal with mean X b and variance
s0 + s1 f + s2 f^2, f the share of regulation (2,400 seconds, four quarters)
left. X for the margin: f x the pre-game expected margin; f x the surprise so
far (the current margin less the share of the pre-game margin already due);
f^2 x the surprise. For the total the same three on the pre-game total, plus a
late-and-close term (under 5 minutes left, within 8 points). The pre-game
numbers are the median of the books' last pre-game spread and total. Fitted by
weighted least squares on every 30 seconds of game time of the EARLIER priced
season's games:

  2025-26 graded with a model fitted on 2024-25          (walk-forward)
  2026-27 to date with a model fitted on 2024-26         (walk-forward)
  2024-25 graded with a model fitted on 2025-26          (a second look, NOT walk-forward)

A QUOTE is priced on the state at its own last_update (the last ESPN play
logged at or before it). It is eligible when: a bettable book's; the price
between -250 and +250; the line within 6 points of the median of the other
books in the same snapshot; at least 2 other books quoting that market in the
snapshot; no point scored between the quote's stamp and the snapshot; and the
game in the rule's phase. Rules (the men's three, on quarters): spread in the
first half, spread and total from halftime to two minutes left. Also graded:
the total in the first half.

DECISION, two ways:
  first-eligible  the first snapshot of the phase holding an eligible quote
                  decides the rule for that game: its best-EV quote is bet at
                  or above the cut, and the rule is spent either way (the
                  men's rule).
  first-crossing  the first snapshot of the phase in which an eligible quote's
                  EV is at or above the cut is bet; one bet a game and rule.

Stake: one unit to win, risk capped at 3, at the quote's price. 95% interval
resampled by ET date.

TWO READINGS OF THE PLAY LIST (2026-11-11). The state at an instant was first
read as "the last play ESPN logged": its running score. ESPN logs corrections
late with the score of the moment they belong to, so that reading gave some
states a score from earlier in the game (54 of the halftime total's 689 bets
of 2025-26). NCAABW_INPLAY_STATE=max reads the score as the highest logged so
far, as models/ncaabw_live_ht.py does, and writes inplay_priced_max_<season>
beside the first reading's inplay_priced_<season>. The default is the first
reading, so the tables of 2026-11-09 can be reproduced.
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
from data.ingestors.ncaabw_teams import regulation_periods  # noqa: E402

BETTABLE = set(config.BEST_LINE_BOOKMAKERS)
STATE_MAX = os.environ.get("NCAABW_INPLAY_STATE", "").strip().lower() == "max"
PRICED = "inplay_priced_max" if STATE_MAX else "inplay_priced"
RNG = np.random.default_rng(20261109)
REG_S = 2400.0
CUTS = (0.02, 0.05, 0.08, 0.12)


def dec(a):
    a = float(a)
    return 1.0 + a / 100.0 if a > 0 else 1.0 + 100.0 / abs(a)


def clock_seconds(display) -> float:
    """'9:58' -> 598.0, '0:07.4' -> 7.4; nan when unreadable."""
    try:
        if ":" in str(display):
            m, sec = str(display).split(":", 1)
            return int(m) * 60 + float(sec)
        return float(display)
    except (TypeError, ValueError):
        return float("nan")


def game_seconds(period: int, clock_s: float, season: int) -> float:
    """Seconds of the game gone: four 600-second quarters from 2015-16 (two
    halves before), then 300-second overtimes."""
    n = regulation_periods(season)
    length = REG_S / n
    if period <= n:
        return (period - 1) * length + (length - clock_s)
    return REG_S + (period - n - 1) * 300.0 + (300.0 - clock_s)


def load_games():
    g = pd.read_parquet(CACHE / "games.parquet")
    g = g[g["home_score"].notna()].copy()
    g["final_m"] = g["home_score"].astype(float) - g["away_score"].astype(float)
    g["final_t"] = g["home_score"].astype(float) + g["away_score"].astype(float)
    g["game_date"] = g["game_date"].astype(str).str[:10]
    return g


def priors():
    """Median of the books' last pre-game spread and total (the lead-0 board)."""
    B = pd.read_parquet(CACHE / "boards.parquet")
    c = B[B["lead"] == 0]
    sp = c[(c["market"] == "spreads") & c["spread_home"].notna() & (c["spread_home"].abs() <= 70)]
    to = c[(c["market"] == "totals") & c["total_line"].notna() & c["total_line"].between(90, 200)]
    out = pd.concat([sp.groupby("game_id")["spread_home"].median().rename("prior_spread"),
                     to.groupby("game_id")["total_line"].median().rename("prior_total")], axis=1)
    return out.dropna()


def load_states(g, wanted):
    """Per game: the plays in order, as arrays (wallclock ns, game seconds,
    home score, away score, scored?) in OUR orientation."""
    ev = g[g["game_id"].isin(wanted)].set_index("espn_event_id")
    out = {}
    cols = ["game_id", "period_number", "clock_display_value", "home_score", "away_score",
            "wallclock", "scoring_play", "home_team_id", "season"]
    for season in (2025, 2026, 2027):
        f = CACHE / f"pbp_{season}.parquet"
        if not f.exists():
            continue
        df = pd.read_parquet(f, columns=cols)
        df = df[df["game_id"].isin(ev.index)]
        df["wall"] = pd.to_datetime(df["wallclock"], utc=True, errors="coerce")
        df = df.dropna(subset=["wall", "period_number"])
        for eid, x in df.groupby("game_id", sort=False):
            row = ev.loc[eid]
            x = x.sort_values("wall", kind="stable")
            cs = np.array([clock_seconds(v) for v in x["clock_display_value"]], dtype=float)
            gs = np.array([game_seconds(int(p), c, int(season)) if not np.isnan(c) else np.nan
                           for p, c in zip(x["period_number"], cs)], dtype=float)
            h = x["home_score"].astype(float).values; a = x["away_score"].astype(float).values
            if int(x["home_team_id"].iloc[0]) != int(row["home_espn_id"]):
                h, a = a, h
            ok = ~np.isnan(gs)
            if ok.sum() < 50:
                continue
            gs = np.maximum.accumulate(gs[ok])          # the clock never runs backwards
            h, a = h[ok], a[ok]
            scored = x["scoring_play"].fillna(False).astype(bool).values[ok]
            if STATE_MAX:                               # nor does the score
                h, a = np.maximum.accumulate(h), np.maximum.accumulate(a)
                scored = np.concatenate([[False], np.diff(h + a) > 0])
            out[row["game_id"]] = {
                "wall": x["wall"].values[ok].astype("datetime64[ns]").astype("int64"),
                "gs": gs, "h": h, "a": a, "scored": scored}
    return out


def design(kind, f, cur_m, cur_t, prior_m, prior_t):
    f = np.asarray(f, float)
    if kind == "m":
        sur = cur_m - prior_m * (1 - f)
        return np.column_stack([f * prior_m, f * sur, f * f * sur])
    sur = cur_t - prior_t * (1 - f)
    late = ((f < 5 * 60 / REG_S) & (np.abs(cur_m) <= 8)).astype(float)
    return np.column_stack([f * prior_t, f * sur, f * f * sur, late])


def training_rows(states, g, pri, seasons):
    gi = g.set_index("game_id")
    rows = []
    grid = np.arange(30.0, REG_S, 30.0)
    for gid, st in states.items():
        if gid not in pri.index or gi.loc[gid, "season"] not in seasons:
            continue
        idx = np.searchsorted(st["gs"], grid, side="right") - 1
        ok = idx >= 0
        cur_m = (st["h"] - st["a"])[idx[ok]]; cur_t = (st["h"] + st["a"])[idx[ok]]
        f = 1 - grid[ok] / REG_S
        rows.append(pd.DataFrame({
            "f": f, "cur_m": cur_m, "cur_t": cur_t,
            "prior_m": -pri.loc[gid, "prior_spread"], "prior_t": pri.loc[gid, "prior_total"],
            "rem_m": gi.loc[gid, "final_m"] - cur_m, "rem_t": gi.loc[gid, "final_t"] - cur_t}))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def fit(tr):
    out = {}
    for kind, y in (("m", "rem_m"), ("t", "rem_t")):
        X = design(kind, tr["f"], tr["cur_m"], tr["cur_t"], tr["prior_m"], tr["prior_t"])
        b = np.linalg.lstsq(X, tr[y].values, rcond=None)[0]
        for _ in range(3):                      # reweight by the fitted variance
            r2 = (tr[y].values - X @ b) ** 2
            V = np.column_stack([np.ones(len(tr)), tr["f"], tr["f"] ** 2])
            s = np.linalg.lstsq(V, r2, rcond=None)[0]
            var = np.maximum(V @ s, 1.0)
            w = 1.0 / np.sqrt(var)
            b = np.linalg.lstsq(X * w[:, None], tr[y].values * w, rcond=None)[0]
        out[kind] = {"b": b, "s": s}
    return out


def predict(model, kind, f, cur_m, cur_t, prior_m, prior_t):
    X = design(kind, f, cur_m, cur_t, prior_m, prior_t)
    mu = X @ model[kind]["b"]
    f = np.asarray(f, float)
    var = np.maximum(model[kind]["s"][0] + model[kind]["s"][1] * f + model[kind]["s"][2] * f * f, 1.0)
    return mu, np.sqrt(var)


def p_over(mu, sd, k):
    """P(remaining > k), P(push), with the remaining a whole number."""
    whole = np.abs(k - np.round(k)) < 1e-9
    pw = np.where(whole, norm.sf((k + 0.5 - mu) / sd), norm.sf((k - mu) / sd))
    pp = np.where(whole, norm.cdf((k + 0.5 - mu) / sd) - norm.cdf((k - 0.5 - mu) / sd), 0.0)
    return pw, pp


def quote_table(g, pri, states):
    Q = pd.read_parquet(CACHE / "inplay_quotes.parquet")
    Q = Q[Q["market"].isin(["spreads", "totals"]) & Q["game_id"].isin(states) & Q["game_id"].isin(pri.index)]
    Q = Q.merge(g[["game_id", "season", "game_date", "final_m", "final_t"]], on="game_id")
    lu = Q["last_update"].dt.as_unit("ns").astype("int64").values
    sn = pd.to_datetime(Q["snapshot_ts"], utc=True).dt.as_unit("ns").astype("int64").values
    gs = np.full(len(Q), np.nan); cm = np.full(len(Q), np.nan); ct = np.full(len(Q), np.nan)
    fresh = np.zeros(len(Q), bool); over = np.zeros(len(Q), bool)
    for gid, idx in Q.groupby("game_id").indices.items():
        st = states[gid]
        i = np.searchsorted(st["wall"], lu[idx], side="right") - 1
        j = np.searchsorted(st["wall"], sn[idx], side="right") - 1
        ok = i >= 0
        ii = np.clip(i, 0, None)
        gs[idx] = np.where(ok, st["gs"][ii], np.nan)
        cm[idx] = np.where(ok, (st["h"] - st["a"])[ii], np.nan)
        ct[idx] = np.where(ok, (st["h"] + st["a"])[ii], np.nan)
        csum = np.cumsum(st["scored"])
        fresh[idx] = ok & (csum[np.clip(j, 0, None)] == csum[ii])
        over[idx] = sn[idx] > st["wall"][-1]           # the snapshot is after the last play logged
    Q["gs"], Q["cur_m"], Q["cur_t"], Q["fresh"], Q["after_end"] = gs, cm, ct, fresh, over
    Q = Q.dropna(subset=["gs"])
    Q["prior_m"] = -Q["game_id"].map(pri["prior_spread"])
    Q["prior_t"] = Q["game_id"].map(pri["prior_total"])
    Q["f"] = np.clip(1 - Q["gs"] / REG_S, 0, 1)
    return Q


def price_quotes(Q, model):
    Q = Q.copy()
    mu_m, sd_m = predict(model, "m", Q["f"], Q["cur_m"], Q["cur_t"], Q["prior_m"], Q["prior_t"])
    mu_t, sd_t = predict(model, "t", Q["f"], Q["cur_m"], Q["cur_t"], Q["prior_m"], Q["prior_t"])
    is_sp = (Q["market"] == "spreads").values
    k = np.where(is_sp, -Q["spread_home"].values - Q["cur_m"].values, Q["total_line"].values - Q["cur_t"].values)
    mu = np.where(is_sp, mu_m, mu_t); sd = np.where(is_sp, sd_m, sd_t)
    pw, pp = p_over(mu, sd, k)
    pl = 1 - pw - pp
    p1 = pw / (pw + pl)                       # home covers / over
    a1 = np.where(is_sp, Q["home_price"].values, Q["over_price"].values).astype(float)
    a2 = np.where(is_sp, Q["away_price"].values, Q["under_price"].values).astype(float)
    d1 = np.where(a1 > 0, 1 + a1 / 100, 1 + 100 / np.abs(a1)); d2 = np.where(a2 > 0, 1 + a2 / 100, 1 + 100 / np.abs(a2))
    ev1 = p1 * d1 - 1; ev2 = (1 - p1) * d2 - 1
    first = ev1 >= ev2
    Q["side"] = np.where(is_sp, np.where(first, "home", "away"), np.where(first, "over", "under"))
    Q["price"] = np.where(first, a1, a2); Q["ev"] = np.where(first, ev1, ev2)
    Q["prob"] = np.where(first, p1, 1 - p1)
    final = np.where(is_sp, Q["final_m"].values + Q["spread_home"].values, Q["final_t"].values - Q["total_line"].values)
    res = np.where(first, final, -final)
    d = np.where(first, d1, d2)
    risk = np.minimum(1 / (d - 1), 3.0)
    Q["units"] = np.where(res > 0, risk * (d - 1), np.where(res < 0, -risk, 0.0)); Q["risk"] = risk
    line = np.where(is_sp, Q["spread_home"].values, Q["total_line"].values)
    Q["line"] = line
    med = Q.groupby(["snapshot_ts", "game_id", "market"])["line"].transform("median")
    n = Q.groupby(["snapshot_ts", "game_id", "market"])["line"].transform("size")
    Q["off"] = (Q["line"] - med).abs(); Q["others"] = n - 1
    Q["eligible"] = (Q["bookmaker"].isin(BETTABLE) & Q["price"].between(-250, 250) & (Q["off"] <= 6)
                     & (Q["others"] >= 2) & Q["fresh"] & ~Q["after_end"]
                     & np.where(is_sp, np.abs(line) <= 70, (line >= 60) & (line <= 260)))
    h1 = Q["gs"] < 1200; h2 = (Q["gs"] >= 1200) & (Q["gs"] <= REG_S - 120)
    Q["rule"] = np.where(is_sp, np.where(h1, "spread_h1", np.where(h2, "spread_h2", "")),
                         np.where(h1, "total_h1", np.where(h2, "total_h2", "")))
    return Q[Q["rule"] != ""]


def summarise(b, label):
    if not len(b):
        print(f"  {label:38s}    0 bets")
        return
    u, r = b["units"].values, b["risk"].values
    ud = pd.Series(u).groupby(b["game_date"].values).sum(); rd = pd.Series(r).groupby(b["game_date"].values).sum()
    idx = RNG.integers(0, len(ud), size=(2000, len(ud)))
    boot = ud.values[idx].sum(axis=1) / rd.values[idx].sum(axis=1) * 100
    lo, hi = np.percentile(boot, [2.5, 97.5])
    print(f"  {label:38s} {len(b):5d} bets {int((u > 0).sum())}-{int((u < 0).sum())}  {u.sum():+8.2f}u "
          f"{u.sum() / r.sum() * 100:+6.2f}% [{lo:+.1f}, {hi:+.1f}]  prices {b['price'].min():.0f}..{b['price'].max():.0f}"
          f"  ev mean {b['ev'].mean():.3f}")


def decide(Q, cut, how):
    E = Q[Q["eligible"]].sort_values(["game_id", "rule", "snapshot_ts", "ev"], ascending=[True, True, True, False])
    if how == "first-eligible":
        first_ts = E.groupby(["game_id", "rule"])["snapshot_ts"].transform("min")
        best = E[E["snapshot_ts"] == first_ts].groupby(["game_id", "rule"]).head(1)
        return best[best["ev"] >= cut]
    over = E[E["ev"] >= cut]
    return over.groupby(["game_id", "rule"]).head(1)


if __name__ == "__main__":
    g = load_games()
    pri = priors()
    L = pd.read_parquet(CACHE / "inplay_quotes.parquet", columns=["game_id"])
    wanted = set(pri.index) | set(L["game_id"])
    states = load_states(g, wanted)
    print(f"games with a pre-game prior {len(pri):,}; with in-play quotes {L['game_id'].nunique():,}; "
          f"with a play-by-play {len(states):,}")
    Q0 = quote_table(g, pri, states)
    print(f"in-play spread and total quotes with a state: {len(Q0):,} on {Q0['game_id'].nunique():,} games "
          f"({Q0.groupby('season')['game_id'].nunique().to_dict()})")
    folds = [("2025-26, model from 2024-25 (walk-forward)", [2025], 2026),
             ("2026-27 to date, model from 2024-26 (walk-forward)", [2025, 2026], 2027),
             ("2024-25, model from 2025-26 (second look)", [2026], 2025)]
    for label, tr_s, te_s in folds:
        tr = training_rows(states, g, pri, tr_s)
        if not len(tr):
            print(f"\n=== {label}: no training games")
            continue
        model = fit(tr)
        print(f"\n=== {label}\n  fitted on {len(tr):,} states; margin b {np.round(model['m']['b'], 3)} var "
              f"{np.round(model['m']['s'], 1)}; total b {np.round(model['t']['b'], 3)} var {np.round(model['t']['s'], 1)}")
        te_rows = training_rows(states, g, pri, [te_s])
        if len(te_rows):
            for kind, y in (("m", "rem_m"), ("t", "rem_t")):
                mu, sd = predict(model, kind, te_rows["f"], te_rows["cur_m"], te_rows["cur_t"],
                                 te_rows["prior_m"], te_rows["prior_t"])
                z = (te_rows[y] - mu) / sd
                print(f"  out of sample, {kind}: mean error {(te_rows[y] - mu).mean():+.2f}, "
                      f"spread ratio {z.std():.3f} on {len(te_rows):,} states")
        Q = price_quotes(Q0[Q0["season"] == te_s], model)
        print(f"  quotes in a phase {len(Q):,}; eligible {int(Q['eligible'].sum()):,} "
              f"on {Q[Q['eligible']]['game_id'].nunique():,} games")
        Q.to_parquet(CACHE / f"{PRICED}_{te_s}.parquet", index=False)
        for how in ("first-eligible", "first-crossing"):
            print(f" {how}:")
            for rule in ("spread_h1", "spread_h2", "total_h2", "total_h1"):
                for cut in CUTS:
                    b = decide(Q[Q["rule"] == rule], cut, how)
                    summarise(b, f"{rule} EV >= {cut:.2f}")
