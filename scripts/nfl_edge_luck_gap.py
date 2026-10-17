"""
Luck gap: does the NFL spread/total market over-weight points that came from
LUCK, so that teams whose actual margin has run far ahead of their play-by-play
expected margin are overvalued against the spread, and pairs of "lucky"
offenses are overvalued on totals?  (docs/nfl_edge_search.md hypothesis; a
grade-B publisher reports 157-108-7 ATS since 2018 and 35-19-1 on totals 2023,
with no published definition.)

Run:  PYTHONIOENCODING=utf-8 python -m scripts.nfl_edge_luck_gap
Reads only the local cache via scripts.nfl_edge_lib. No database, no network,
no Odds API credits.

CONSTRUCTION (written before any outcome was read)
==================================================
Expected points (one definition, pre-registered)
    For every team-game 2016-2025 (REG + POST) from nflverse play-by-play:
      O_T = sum of LUCK-NEUTRAL EPA over T's offensive scrimmage plays
            (play_type 'pass' or 'run'; kneels, spikes, no-plays and two-point
            tries excluded), where
              * a play with interception == 1 gets the FIT-league (2016-2019)
                mean EPA of interception plays (removes return yardage and
                pick-sixes; the cost of throwing it is kept);
              * any other play with fumble == 1 gets the FIT-league mean EPA of
                fumble plays of its play_type (removes WHO RECOVERED; the cost
                of fumbling is kept).
      Special teams are NOT in O at all: field goals and extra points (own and
      opponent make/miss), kick/punt return TDs, muffs and blocked kicks fall
      into the luck residual by construction (intended: "opponent missed
      kicks", "return TDs"). Red-zone and third-down outcomes ARE in O (EPA
      credits the TD), so red-zone variance is treated as skill here - stated,
      not tested.
    Expected points for, fitted by OLS on FIT team-games only (2016-2019):
        PF_T = a + b1 * O_T + b2 * O_opp            (coefficients printed)
      xPF_T = a + b1 O_T + b2 O_opp ;  xPA_T = a + b1 O_opp + b2 O_T.
      luckPF_T = PF_T - xPF_T   (points scored beyond the efficiency)
      luckM_T  = (PF_T - PA_T) - (xPF_T - xPA_T) = luckPF_T - luckPF_opp
      xM_T     = xPF_T - xPA_T  (the efficiency-only margin, for the control)
    The FIT coefficients use FIT outcomes of FIT games (an in-sample mapping of
    efficiency to points inside FIT); hold-out seasons use the FIT
    coefficients unchanged.
    Descriptive luck components (printed, NOT selection inputs): fumble
    recoveries by T minus half of all fumbles in the game; FG points minus the
    FIT make rate by 5-yard distance bucket, own minus opponent; non-offensive
    (return) TDs, own minus opponent.

As-of windows (strictly prior games only)
    Per team, within the SAME season (REG + POST in kickoff order), the mean
    over the previous N games of each per-game quantity, N in {4, 6, 8} (needs
    >= N prior games) and season-to-date STD (needs >= 4 prior games). The
    current game is never in its own window. Consequence: N=4 first fires in
    week 5, N=6 in week 7, N=8 in week 9, STD in week 5 - so "early (weeks
    1-8)" is really weeks 5-8 and N=8 has no early bets. Carry-over across
    seasons is a different construction and is not run.

Selection - SIDES (one bet per game)
    D = gapM_home - gapM_away (window means of luckM). If |D| > cut, bet the
    side AGAINST the team with the larger gap. cut = the FIT-season quantile q
    of |D| among eligible FIT games, per N, q in {0.50, 0.75, 0.90, 0.95,
    0.975} (cut values printed). The same numeric cut is used in the hold-out.
Selection - TOTALS (one bet per game)
    S = luckPF_home(window) + luckPF_away(window) - the two offenses' combined
    scoring luck. UNDER if S > FIT quantile q of S. Mirror (exploratory,
    labelled): OVER if S < FIT quantile (1 - q).

Decision time and price
    FIT 2016-2019 (discovery): the nflverse CLOSING spread_line / total_line at
        -110 (a closing-line study, not a bettable quote). home_point =
        -spread_line. Push (integer line hit) = 0 units.
    HOLD 2020-2025 (read once): the bettable board at T-3h from odds_hist:
        each BETTABLE_HIST book's latest quote with lead_hours >= 3 AND
        snapshot_at >= (both teams' previous kickoff + 4h) (so the quote
        post-dates the information the window uses). Prices outside
        [-1000, -100] U [100, 1000] are dropped (the -100000 placeholder).
        The game's line is the MODAL point across those books (tie -> closest
        to the board median, then the lower point); the bet is graded at that
        point and the BEST price among books quoting exactly that point for the
        side taken. Games with no valid board are not bet (count printed).
        Totals at T-3h are ~120h stale in 2020-2022 (measured on the cache), so
        the TOTALS bettable hold-out is 2023-2025 only; 2020-2025 totals are
        also graded at the nflverse close -110 (labelled).
        Sensitivity: the same hold-out bets at the nflverse close -110.
    No observed weather, no same-game statistic, no closing line in the
    hold-out decision.

Registered cell (chosen on FIT only, before the hold-out is read)
    Sides: N = the window with the highest FIT ROI averaged over the five q;
    within it q = the q maximising the mean FIT ROI of {q and its neighbours}
    (a plateau, not a peak). Totals (UNDER): the same rule. The registered cell
    is graded ONCE in the hold-out; the full hold-out grid is printed as the
    neighbourhood around it.

Published rule
    The publisher's rule is not specified, so it cannot be graded AS STATED.
    The nearest analogue printed: the registered side cell at the nflverse
    close -110 for 2018-2025 (the publisher's period), labelled an analogue,
    not a replication.

Controls (must NOT work if the mechanism is real)
    P1 shuffled: within each season the per-game luck values are randomly
       reassigned across team-game rows (200 reps), windows and quantile cuts
       recomputed, same selection -> the noise floor; the real cell's
       percentile among reps is printed.
    P2 efficiency-only: window mean of xM; bet ON the higher-xM team when
       |D_x| > its own FIT quantile cut (the repo's prior: ~null).
    P3 actual-margin-only: window mean of actual margin; bet AGAINST the team
       with the higher margin at its own FIT quantile cuts. A lucky team
       usually has a good record, so if P3 matches the real rule the luck
       decomposition adds nothing.
    Totals controls: UNDER when the window sum of ACTUAL PF is high (P3T);
       OVER when the window sum of xPF is high (P2T); shuffled (P1T).

Inference
    90% CI by cluster bootstrap on game_id (one bet per game per cell),
    4000 draws, seed 7 (the same resampling as nfl_edge_lib.boot_ci). One-sided
    p = exact binomial on decided bets vs the break-even of the cell's mean price
    (the first run used the share of bootstrap ROI <= 0, which degenerates on a
    1-bet cell; replaced after that run, no selection changed). Benjamini-Hochberg at q = 0.10 over the
    hold-out cells of the three hypothesis grids (sides 20, totals UNDER 20,
    totals OVER 20 exploratory = 60); controls are not hypotheses and are not
    counted. LOW = <= 15 bets per season (the strict low-volume cells).
    Every season separately; early/late = REG weeks 1-8, REG weeks 9+, POST.
Results are in UNITS (1 unit = 1 flat bet).
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from scripts.nfl_edge_lib import (BETTABLE_HIST, CACHE, am_to_dec, games,
                                  odds_hist, profit_units)

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 500)

FIT = (2016, 2019)
HOLD = (2020, 2025)
SEASONS = list(range(2016, 2026))
NS = [4, 6, 8, "STD"]
QS = [0.50, 0.75, 0.90, 0.95, 0.975]
LOWVOL = 15
NB = 4000
NSHUF = 200
PBP_COLS = ["game_id", "season", "week", "season_type", "home_team", "away_team",
            "posteam", "defteam", "play_type", "epa", "fumble", "interception",
            "two_point_attempt", "success", "yards_gained", "fumble_recovery_1_team",
            "td_team", "return_touchdown", "field_goal_result", "kick_distance"]


def hdr(s):
    print("\n" + "=" * 110 + "\n" + s + "\n" + "=" * 110)


# ─── inference ──────────────────────────────────────────────────────────────

def boot(profit, cluster, n=NB, seed=7):
    """ROI, 90% CI and one-sided p (share of bootstrap ROI <= 0), clusters resampled."""
    profit = np.asarray(profit, float)
    if len(profit) == 0:
        return np.nan, np.nan, np.nan, np.nan
    uniq, inv = np.unique(np.asarray(cluster), return_inverse=True)
    sums = np.bincount(inv, weights=profit)
    cnts = np.bincount(inv)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(uniq), size=(n, len(uniq)))
    roi = sums[idx].sum(1) / cnts[idx].sum(1)
    lo, hi = np.quantile(roi, [0.05, 0.95])
    p = max((roi <= 0).mean(), 1.0 / (n + 1))
    return profit.sum() / len(profit), lo, hi, p


def cell(B: pd.DataFrame, nseas: int) -> dict:
    if len(B) == 0:
        return {"bets": 0, "per_szn": 0.0, "W-L-P": "0-0-0", "units": 0.0, "roi%": np.nan,
                "ci90_lo": np.nan, "ci90_hi": np.nan, "p1": np.nan, "low": "LOW"}
    roi, lo, hi, _ = boot(B["profit"].values, B["game_id"].values)
    w = int((B["profit"] > 0).sum()); pu = int((B["profit"] == 0).sum()); l = len(B) - w - pu
    p = binom_p(B)
    ps = len(B) / nseas
    return {"bets": len(B), "per_szn": round(ps, 1), "W-L-P": f"{w}-{l}-{pu}",
            "units": round(B["profit"].sum(), 2), "roi%": round(100 * roi, 2),
            "ci90_lo": round(100 * lo, 1), "ci90_hi": round(100 * hi, 1),
            "p1": round(p, 4), "low": "LOW" if ps <= LOWVOL else ""}


def binom_p(B: pd.DataFrame) -> float:
    """One-sided exact binomial p: wins among DECIDED bets (pushes dropped) vs the
    break-even rate of the cell's mean decimal price. Replaces the bootstrap p of
    the first run, which degenerates to 1/(n+1) for a 1-bet or all-win cell."""
    dec = B["profit"] != 0
    n = int(dec.sum())
    if n == 0:
        return np.nan
    k = int((B.loc[dec, "profit"] > 0).sum())
    p0 = float(1.0 / np.mean(am_to_dec(B.loc[dec, "pr"].astype(float).values)))
    return float(binomtest(k, n, p0, alternative="greater").pvalue)


def bh(p: np.ndarray, q=0.10):
    p = np.asarray(p, float)
    m = len(p)
    order = np.argsort(p)
    thr = q * (np.arange(1, m + 1)) / m
    passed = p[order] <= thr
    k = np.max(np.where(passed)[0]) + 1 if passed.any() else 0
    out = np.zeros(m, bool)
    out[order[:k]] = True
    return out, (thr[k - 1] if k else 0.0)


# ─── team-game table from pbp ───────────────────────────────────────────────

def load_plays():
    """Per-season pbp -> scrimmage plays, fumbles, FGs, return TDs (compact)."""
    scrim, fum, fg, rtd = [], [], [], []
    for s in SEASONS:
        p = pd.read_parquet(CACHE / f"pbp_{s}.parquet", columns=PBP_COLS)
        p = p[p["season_type"].isin(["REG", "POST"])]
        sc = p[p["play_type"].isin(["pass", "run"]) & (p["two_point_attempt"] != 1)
               & p["epa"].notna() & p["posteam"].notna()]
        scrim.append(sc[["game_id", "season", "posteam", "defteam", "play_type", "epa",
                         "fumble", "interception", "success", "yards_gained"]].copy())
        f = p[(p["fumble"] == 1) & p["fumble_recovery_1_team"].notna()]
        fum.append(f[["game_id", "season", "fumble_recovery_1_team"]].copy())
        k = p[p["field_goal_result"].isin(["made", "missed", "blocked"]) & p["posteam"].notna()]
        fg.append(k[["game_id", "season", "posteam", "field_goal_result", "kick_distance"]].copy())
        r = p[(p["return_touchdown"] == 1) & p["td_team"].notna()]
        rtd.append(r[["game_id", "season", "td_team"]].copy())
        # home/away identity per game, pbp naming (consistent within a season)
        del p
    return (pd.concat(scrim, ignore_index=True), pd.concat(fum, ignore_index=True),
            pd.concat(fg, ignore_index=True), pd.concat(rtd, ignore_index=True))


def team_games():
    scrim, fum, fg, rtd = load_plays()
    fitmask = scrim["season"].between(*FIT)
    m_int = scrim.loc[fitmask & (scrim["interception"] == 1), "epa"].mean()
    m_fum = scrim[fitmask & (scrim["fumble"] == 1) & (scrim["interception"] != 1)] \
        .groupby("play_type")["epa"].mean()
    print(f"FIT neutral EPA constants: interception plays {m_int:+.3f}; fumble plays "
          + ", ".join(f"{k} {v:+.3f}" for k, v in m_fum.items()))
    adj = scrim["epa"].copy()
    isint = scrim["interception"] == 1
    isfum = (scrim["fumble"] == 1) & ~isint
    adj[isint] = m_int
    adj[isfum] = scrim.loc[isfum, "play_type"].map(m_fum)
    scrim["adj"] = adj
    off = scrim.groupby(["game_id", "posteam"]).agg(
        O=("adj", "sum"), O_raw=("epa", "sum"), plays=("adj", "size"),
        sr=("success", "mean"), ypp=("yards_gained", "mean")).reset_index() \
        .rename(columns={"posteam": "team"})

    # FG expectation by 5-yard bucket on FIT
    fg["bucket"] = (fg["kick_distance"] // 5 * 5).clip(15, 60)
    fg["made"] = (fg["field_goal_result"] == "made").astype(int)
    rate = fg[fg["season"].between(*FIT)].groupby("bucket")["made"].mean()
    fg["fg_luck"] = 3 * (fg["made"] - fg["bucket"].map(rate).fillna(fg["made"].mean()))
    fgl = fg.groupby(["game_id", "posteam"])["fg_luck"].sum().reset_index() \
        .rename(columns={"posteam": "team"})
    fum_tot = fum.groupby("game_id").size().rename("fum_n")
    fum_rec = fum.groupby(["game_id", "fumble_recovery_1_team"]).size().rename("fum_rec") \
        .reset_index().rename(columns={"fumble_recovery_1_team": "team"})
    rt = rtd.groupby(["game_id", "td_team"]).size().rename("ret_td").reset_index() \
        .rename(columns={"td_team": "team"})

    g = games()
    g = g[g["season"].between(*FIT[:1] + (HOLD[1],)) & g["result"].notna()
          & g["game_type"].notna()].copy()
    # pbp naming of home/away (nflverse schedules and pbp differ, e.g. OAK/LV 2019)
    ids = pd.concat([pd.read_parquet(CACHE / f"pbp_{s}.parquet",
                                     columns=["game_id", "home_team", "away_team"])
                     .drop_duplicates("game_id") for s in SEASONS], ignore_index=True)
    g = g.drop(columns=["home_team", "away_team"]).merge(ids, on="game_id", how="inner")
    base = g[["game_id", "season", "week", "game_type", "kick", "home_team", "away_team",
              "home_score", "away_score"]]
    h = base.assign(team=base["home_team"], opp=base["away_team"], role="home",
                    PF=base["home_score"], PA=base["away_score"])
    a = base.assign(team=base["away_team"], opp=base["home_team"], role="away",
                    PF=base["away_score"], PA=base["home_score"])
    T = pd.concat([h, a], ignore_index=True)[["game_id", "season", "week", "game_type",
                                               "kick", "team", "opp", "role", "PF", "PA"]]
    T = T.merge(off, on=["game_id", "team"], how="left")
    T = T.merge(off[["game_id", "team", "O", "O_raw"]].rename(
        columns={"team": "opp", "O": "O_opp", "O_raw": "O_raw_opp"}), on=["game_id", "opp"], how="left")
    T = T.merge(fgl, on=["game_id", "team"], how="left").merge(
        fgl.rename(columns={"team": "opp", "fg_luck": "fg_luck_opp"}), on=["game_id", "opp"], how="left")
    T = T.merge(fum_rec, on=["game_id", "team"], how="left").merge(fum_tot, on="game_id", how="left")
    T = T.merge(rt, on=["game_id", "team"], how="left").merge(
        rt.rename(columns={"team": "opp", "ret_td": "ret_td_opp"}), on=["game_id", "opp"], how="left")
    for c in ("fg_luck", "fg_luck_opp", "fum_rec", "fum_n", "ret_td", "ret_td_opp"):
        T[c] = T[c].fillna(0.0)
    miss = T["O"].isna() | T["O_opp"].isna()
    print(f"team-games {len(T)}; dropped for missing pbp {int(miss.sum())}")
    T = T[~miss].copy()
    # components (descriptive), own minus opponent, per game
    T["c_fum"] = T["fum_rec"] - 0.5 * T["fum_n"]
    T["c_fg"] = T["fg_luck"] - T["fg_luck_opp"]
    T["c_rtd"] = T["ret_td"] - T["ret_td_opp"]
    return T


def fit_points(T):
    F = T[T["season"].between(*FIT)]
    X = np.column_stack([np.ones(len(F)), F["O"], F["O_opp"]])
    beta, *_ = np.linalg.lstsq(X, F["PF"].values, rcond=None)
    pred = X @ beta
    r2 = 1 - ((F["PF"] - pred) ** 2).sum() / ((F["PF"] - F["PF"].mean()) ** 2).sum()
    a, b1, b2 = beta
    print(f"FIT OLS (team-games {len(F)}): PF = {a:.3f} + {b1:.4f}*O_T + {b2:+.4f}*O_opp ; R^2 = {r2:.3f}")
    T["xPF"] = a + b1 * T["O"] + b2 * T["O_opp"]
    T["xPA"] = a + b1 * T["O_opp"] + b2 * T["O"]
    T["luckPF"] = T["PF"] - T["xPF"]
    T["M"] = T["PF"] - T["PA"]
    T["xM"] = T["xPF"] - T["xPA"]
    T["luckM"] = T["M"] - T["xM"]
    # what the luck residual is made of (FIT, descriptive)
    X2 = np.column_stack([np.ones(len(F)), F["c_fum"], F["c_fg"], F["c_rtd"]])
    y = T.loc[F.index, "luckM"].values
    b, *_ = np.linalg.lstsq(X2, y, rcond=None)
    r2c = 1 - ((y - X2 @ b) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    print(f"FIT luckM per game: sd {y.std():.2f} pts.  luckM ~ fumble-recovery excess "
          f"({b[1]:+.2f}/recovery) + FG luck diff ({b[2]:+.2f}/pt) + return-TD diff "
          f"({b[3]:+.2f}/TD); R^2 = {r2c:.3f}")
    for nm, c in (("fumble-recovery excess", "c_fum"), ("FG luck diff", "c_fg"),
                  ("return-TD diff", "c_rtd")):
        r = np.corrcoef(T.loc[F.index, c], y)[0, 1]
        print(f"   corr(luckM, {nm}) = {r:+.3f}   (alone R^2 {r*r:.3f})")
    sd_ofs = T.loc[F.index, "xM"].std()
    print(f"FIT xM per game sd {sd_ofs:.2f}; actual M sd {T.loc[F.index,'M'].std():.2f}")
    return T


# ─── windows ────────────────────────────────────────────────────────────────

ROLL_COLS = ["luckM", "luckPF", "xM", "M", "PF", "xPF", "c_fum", "c_fg", "c_rtd"]


def add_windows(T, cols=ROLL_COLS):
    T = T.sort_values(["season", "team", "kick", "game_id"]).reset_index(drop=True)
    T["k_prior"] = T.groupby(["season", "team"], sort=False).cumcount()
    T = pd.concat([T, add_windows_fast(T, cols)], axis=1)
    # check the cumsum windows against an explicit shift(1).rolling(n) per team-season
    for n in (4, 8):
        chk = T.groupby(["season", "team"], sort=False)["luckM"].transform(
            lambda s: s.shift(1).rolling(n, min_periods=n).mean())
        assert np.allclose(chk.fillna(-999).values, T[f"luckM_{n}"].fillna(-999).values, atol=1e-9)
    chk = T.groupby(["season", "team"], sort=False)["luckM"].transform(
        lambda s: s.shift(1).expanding().mean())
    chk = chk.where(T["k_prior"] >= 4)
    assert np.allclose(chk.fillna(-999).values, T["luckM_STD"].fillna(-999).values, atol=1e-9)
    return T


def add_windows_fast(T, cols):
    """Same as add_windows for the shuffle loop (cumsum differences)."""
    grp = T.groupby(["season", "team"], sort=False)
    k = T["k_prior"].values
    out = {}
    for c in cols:
        cs = grp[c].cumsum().values
        v = T[c].values
        prior = cs - v
        out[f"{c}_STD"] = np.where(k >= 4, prior / np.clip(k, 1, None), np.nan)
        for n in (4, 6, 8):
            # sum of games k-n .. k-1 = prior_cs(k) - prior_cs(k-n)
            lag = grp[c].shift(n).values  # value n games back (index k-n)
            csl = pd.Series(cs).groupby([T["season"].values, T["team"].values]).shift(n).values
            # cs at index k-n includes value k-n; prior sum up to k-1 minus cs up to k-n-1
            prev = csl - lag            # cumsum through k-n-1
            prev = np.where(np.isnan(prev) & (k == n), 0.0, prev)
            s = prior - prev
            out[f"{c}_{n}"] = np.where(k >= n, s / n, np.nan)
    return pd.DataFrame(out, index=T.index)


def game_frame(T):
    w = [c for c in T.columns if any(c.startswith(r + "_") for r in ROLL_COLS)]
    keep = ["game_id", "kick"] + w
    H = T[T["role"] == "home"][keep + ["season", "week", "game_type", "team"]]
    A = T[T["role"] == "away"][keep + ["team"]].drop(columns=["kick"])
    G = H.merge(A, on="game_id", suffixes=("_h", "_a"))
    return G


# ─── prices ─────────────────────────────────────────────────────────────────

def valid_price(x):
    x = pd.to_numeric(x, errors="coerce")
    return ((x <= -100) & (x >= -1000)) | ((x >= 100) & (x <= 1000))


def board(market, info):
    o = odds_hist([market])
    n0 = len(o)
    o = o[o["bookmaker"].isin(BETTABLE_HIST) & o["point"].notna()]
    o = o[valid_price(o["price_home"]) & valid_price(o["price_away"])]
    o = o[o["lead_hours"] >= 3.0]
    o = o.merge(info, on="game_id", how="inner")
    o = o[o["snapshot_at"] >= o["info_after"]]
    o = o.sort_values("snapshot_at").groupby(["game_id", "bookmaker"], as_index=False).tail(1)
    med = o.groupby("game_id")["point"].median().rename("med")
    cnt = o.groupby(["game_id", "point"]).size().rename("nb").reset_index().merge(med, on="game_id")
    cnt["dist"] = (cnt["point"] - cnt["med"]).abs()
    modal = cnt.sort_values(["game_id", "nb", "dist", "point"], ascending=[True, False, True, True]) \
        .groupby("game_id").head(1)[["game_id", "point"]]
    at = o.merge(modal, on=["game_id", "point"])
    at["dh"] = am_to_dec(at["price_home"].astype(float))
    at["da"] = am_to_dec(at["price_away"].astype(float))
    bh_ = at.loc[at.groupby("game_id")["dh"].idxmax(), ["game_id", "price_home"]]
    ba_ = at.loc[at.groupby("game_id")["da"].idxmax(), ["game_id", "price_away"]]
    out = modal.merge(bh_, on="game_id").merge(ba_, on="game_id")
    meta = o.groupby("game_id").agg(books=("bookmaker", "nunique"), lead=("lead_hours", "median")).reset_index()
    out = out.merge(meta, on="game_id")
    out["price_home"] = out["price_home"].astype(float)
    out["price_away"] = out["price_away"].astype(float)
    out["point"] = out["point"].astype(float)
    return out


# ─── bets ───────────────────────────────────────────────────────────────────

def side_bets(G, D, cut, fade=True, src="close"):
    """D = home value - away value. fade: bet against the larger; else back it."""
    sel = np.abs(D) > cut
    X = G[sel].copy()
    d = D[sel]
    larger_home = d > 0
    bet_home = ~larger_home if fade else larger_home
    X["bet_home"] = bet_home.values if hasattr(bet_home, "values") else bet_home
    if src == "close":
        X["pt"] = X["home_point_close"]
        X["pr"] = -110.0
    else:
        X = X[X["b_point"].notna()]
        X["pt"] = X["b_point"]
        X["pr"] = np.where(X["bet_home"], X["b_ph"], X["b_pa"])
    s = X["result"] + X["pt"]
    won = np.where(X["bet_home"], s > 0, s < 0).astype(int)
    push = (s == 0).astype(int)
    X["profit"] = profit_units(won, X["pr"].values, push.values)
    return X


def total_bets(G, S, cut, under=True, src="close"):
    sel = (S > cut) if under else (S < cut)
    X = G[sel].copy()
    if src == "close":
        X["pt"] = X["total_line"]
        X["pr"] = -110.0
    else:
        X = X[X["t_point"].notna()]
        X["pt"] = X["t_point"]
        X["pr"] = X["t_pu"] if under else X["t_po"]
    won = (X["total"] < X["pt"]) if under else (X["total"] > X["pt"])
    push = (X["total"] == X["pt"]).astype(int)
    X["profit"] = profit_units(won.astype(int).values, X["pr"].values, push.values)
    return X


def phase(G):
    return np.where(G["game_type"] != "REG", "POST",
                    np.where(G["week"] <= 8, "REG wk1-8", "REG wk9+"))


# ─── grids ──────────────────────────────────────────────────────────────────

def wcol(stat, n, side):
    return f"{stat}_{n}_{side}"


def side_D(G, stat, n):
    return G[wcol(stat, n, "h")] - G[wcol(stat, n, "a")]


def total_S(G, stat, n):
    return G[wcol(stat, n, "h")] + G[wcol(stat, n, "a")]


def side_cuts(Gfit, stat):
    out = {}
    for n in NS:
        D = side_D(Gfit, stat, n).dropna().abs()
        out[n] = {q: float(D.quantile(q)) for q in QS}
    return out


def total_cuts(Gfit, stat, under=True):
    out = {}
    for n in NS:
        S = total_S(Gfit, stat, n).dropna()
        out[n] = {q: float(S.quantile(q if under else 1 - q)) for q in QS}
    return out


def side_grid(G, stat, cuts, fade, src, nseas):
    rows, bets = [], {}
    for n in NS:
        D = side_D(G, stat, n)
        ok = D.notna()
        for q in QS:
            B = side_bets(G[ok], D[ok], cuts[n][q], fade=fade, src=src)
            r = {"N": n, "q": q, "cut": round(cuts[n][q], 2)}
            r.update(cell(B, nseas))
            rows.append(r)
            bets[(n, q)] = B
    return pd.DataFrame(rows), bets


def total_grid(G, stat, cuts, under, src, nseas):
    rows, bets = [], {}
    for n in NS:
        S = total_S(G, stat, n)
        ok = S.notna()
        for q in QS:
            B = total_bets(G[ok], S[ok], cuts[n][q], under=under, src=src)
            r = {"N": n, "q": q, "cut": round(cuts[n][q], 2)}
            r.update(cell(B, nseas))
            rows.append(r)
            bets[(n, q)] = B
    return pd.DataFrame(rows), bets


def register(grid):
    """N with the best mean FIT ROI over q; q = best mean of itself + neighbours."""
    m = grid.groupby("N", sort=False)["roi%"].mean()
    n = m.idxmax()
    g = grid[grid["N"] == n].set_index("q")["roi%"].reindex(QS).values
    sm = [np.nanmean(g[max(0, i - 1):i + 2]) for i in range(len(QS))]
    q = QS[int(np.nanargmax(sm))]
    return n, q, m, sm


def season_table(B, label):
    if len(B) == 0:
        print(f"[{label}] no bets"); return
    rows = []
    for s, x in B.groupby("season"):
        r = {"season": s}; r.update(cell(x, 1)); r.pop("low"); r.pop("per_szn"); rows.append(r)
    print(f"[{label}] by season:")
    print(pd.DataFrame(rows).to_string(index=False))


def phase_grid(bets, nseas, label):
    rows = []
    for (n, q), B in bets.items():
        if len(B) == 0:
            continue
        for ph in ("REG wk1-8", "REG wk9+", "POST"):
            x = B[B["phase"] == ph]
            c = cell(x, nseas)
            rows.append({"N": n, "q": q, "phase": ph, "bets": c["bets"], "units": c["units"],
                         "roi%": c["roi%"], "ci90_lo": c["ci90_lo"], "ci90_hi": c["ci90_hi"]})
    P = pd.DataFrame(rows)
    print(f"[{label}] early/late (REG wk1-8 is really wk5-8: windows need prior games):")
    W = P.pivot_table(index=["N", "q"], columns="phase", values=["bets", "roi%"], sort=False)
    print(W.to_string())


def volume_table(bets, label):
    rows = []
    for (n, q), B in bets.items():
        r = {"N": n, "q": q}
        vc = B.groupby("season").size() if len(B) else pd.Series(dtype=int)
        for s in sorted(set(SEASONS)):
            if s in vc.index:
                r[s] = int(vc[s])
        rows.append(r)
    V = pd.DataFrame(rows).fillna(0)
    print(f"[{label}] bets per season at each cut:")
    print(V.to_string(index=False))


# ─── shuffle placebo ────────────────────────────────────────────────────────

def shuffle_placebo(T, Gbase, kind, nrep=NSHUF):
    """kind 'side' (luckM, fade) or 'total' (luckPF, under). Per rep: permute
    the per-game value within season across team-game rows, recompute windows
    and FIT-quantile cuts, select, grade FIT at close and HOLD at the board."""
    col = "luckM" if kind == "side" else "luckPF"
    rng = np.random.default_rng(2024)
    res = []
    home = (T["role"] == "home").values
    Tid = T[["game_id", "season"]]
    for rep in range(nrep):
        Tp = T[["season", "team", "k_prior", "game_id", "role"]].copy()
        v = T[col].values.copy()
        for s in SEASONS:
            m = (T["season"] == s).values
            v[m] = rng.permutation(v[m])
        Tp[col] = v
        W = add_windows_fast(Tp, [col])
        W["game_id"] = T["game_id"].values
        Hh = W[home].set_index("game_id")
        Aa = W[~home].set_index("game_id")
        for n in NS:
            c = f"{col}_{n}"
            h = Hh[c].reindex(Gbase["game_id"]).values
            a = Aa[c].reindex(Gbase["game_id"]).values
            val = (h - a) if kind == "side" else (h + a)
            val = pd.Series(val, index=Gbase.index)
            fitm = Gbase["season"].between(*FIT).values
            okv = val.notna().values
            for q in QS:
                if kind == "side":
                    cut = float(np.nanquantile(np.abs(val[fitm & okv]), q))
                    for era, src in (("FIT", "close"), ("HOLD", "board")):
                        em = Gbase["season"].between(*(FIT if era == "FIT" else HOLD)).values & okv
                        B = side_bets(Gbase[em], val[em], cut, fade=True, src=src)
                        res.append((rep, n, q, era, len(B), B["profit"].mean() if len(B) else np.nan))
                else:
                    cut = float(np.nanquantile(val[fitm & okv], q))
                    for era, src, yrs in (("FIT", "close", FIT), ("HOLD23", "board", (2023, 2025))):
                        em = Gbase["season"].between(*yrs).values & okv
                        B = total_bets(Gbase[em], val[em], cut, under=True, src=src)
                        res.append((rep, n, q, era, len(B), B["profit"].mean() if len(B) else np.nan))
    return pd.DataFrame(res, columns=["rep", "N", "q", "era", "bets", "roi"])


def placebo_table(R, real, era, label):
    rows = []
    for (n, q), x in R[R["era"] == era].groupby(["N", "q"], sort=False):
        rr = real.get((n, q), np.nan)
        rows.append({"N": n, "q": q, "real_roi%": round(100 * rr, 2) if rr == rr else np.nan,
                     "shuf_mean%": round(100 * x["roi"].mean(), 2),
                     "shuf_p5%": round(100 * x["roi"].quantile(0.05), 2),
                     "shuf_p95%": round(100 * x["roi"].quantile(0.95), 2),
                     "real_pctile": round(100 * (x["roi"] < rr).mean(), 1) if rr == rr else np.nan,
                     "shuf_bets": round(x["bets"].mean(), 1)})
    print(f"[{label}] shuffled-assignment noise floor ({R['rep'].nunique()} reps):")
    print(pd.DataFrame(rows).to_string(index=False))


# ─── main ───────────────────────────────────────────────────────────────────

def main():
    hdr("1. Construction: expected points from luck-neutral EPA (constants and fit on 2016-2019 only)")
    T = team_games()
    T = fit_points(T)
    T = add_windows(T)

    g = games()[["game_id", "result", "total", "spread_line", "total_line", "home_point_close"]]
    G = game_frame(T).merge(g, on="game_id", how="left")
    G["phase"] = phase(G)
    # info window: both teams' previous kickoff + 4h
    T_sorted = T.sort_values(["season", "team", "kick"])
    T_sorted["prev_kick"] = T_sorted.groupby(["season", "team"])["kick"].shift(1)
    pk = T_sorted.groupby("game_id")["prev_kick"].max().rename("pk").reset_index()
    info = pk.assign(info_after=pk["pk"].fillna(pd.Timestamp("1900-01-01", tz="UTC")) + pd.Timedelta(hours=4))[
        ["game_id", "info_after"]]

    hdr("2. Hold-out bettable board (T-3h, after both teams' previous game, BETTABLE_HIST, modal point, best price)")
    sp = board("spreads", info).rename(columns={"point": "b_point", "price_home": "b_ph",
                                                "price_away": "b_pa", "books": "b_books", "lead": "b_lead"})
    tt = board("totals", info).rename(columns={"point": "t_point", "price_home": "t_po",
                                               "price_away": "t_pu", "books": "t_books", "lead": "t_lead"})
    G = G.merge(sp, on="game_id", how="left").merge(tt, on="game_id", how="left")
    Hg = G[G["season"].between(*HOLD)]
    for s, x in Hg.groupby("season"):
        cmp = x[x["b_point"].notna()]
        print(f"  {s}: games {len(x)}; spread board {x['b_point'].notna().sum()} "
              f"(median quote lead {x['b_lead'].median():.2f}h, books {x['b_books'].median():.0f}); "
              f"|board - close| mean {np.abs(cmp['b_point'] - cmp['home_point_close']).mean():.2f}, "
              f"sign disagree {(np.sign(cmp['b_point']) * np.sign(cmp['home_point_close']) < 0).sum()}; "
              f"totals board {x['t_point'].notna().sum()} (median lead {x['t_lead'].median():.1f}h)")
    print(f"  board best price: spreads home median {Hg['b_ph'].median():.0f}, away {Hg['b_pa'].median():.0f}; "
          f"totals over {Hg['t_po'].median():.0f}, under {Hg['t_pu'].median():.0f}")

    Gf = G[G["season"].between(*FIT)].copy()
    Gh = G[G["season"].between(*HOLD)].copy()
    G23 = G[G["season"].between(2023, 2025)].copy()
    nF, nH = FIT[1] - FIT[0] + 1, HOLD[1] - HOLD[0] + 1

    print("\nWindow spread (FIT, game-level): sd of D = gap_home - gap_away per N: "
          + ", ".join(f"N={n}: {side_D(Gf, 'luckM', n).std():.2f}" for n in NS))

    # ── FIT ──
    hdr("3. FIT 2016-2019 at the nflverse close -110 (discovery; the hold-out is not read here)")
    cS = side_cuts(Gf, "luckM")
    fitS, betsFS = side_grid(Gf, "luckM", cS, True, "close", nF)
    print("SIDES - fade the team with the larger luck gap:")
    print(fitS.to_string(index=False))
    cU = total_cuts(Gf, "luckPF", True)
    fitU, betsFU = total_grid(Gf, "luckPF", cU, True, "close", nF)
    print("\nTOTALS - UNDER when the two offenses' combined scoring luck is high:")
    print(fitU.to_string(index=False))
    cO = total_cuts(Gf, "luckPF", False)
    fitO, betsFO = total_grid(Gf, "luckPF", cO, False, "close", nF)
    print("\nTOTALS (exploratory mirror) - OVER when combined scoring luck is low:")
    print(fitO.to_string(index=False))
    phase_grid(betsFS, nF, "FIT sides")
    phase_grid(betsFU, nF, "FIT totals UNDER")

    nS, qS, mS, smS = register(fitS)
    nU, qU, mU, smU = register(fitU)
    nO, qO, _, _ = register(fitO)
    print(f"\nREGISTERED on FIT: sides N={nS} q={qS} (cut {cS[nS][qS]:.2f}); "
          f"mean FIT ROI by N: {dict((k, round(float(v), 2)) for k, v in mS.items())}; "
          f"neighbour means over q: {[round(float(x), 2) for x in smS]}")
    print(f"REGISTERED on FIT: totals UNDER N={nU} q={qU} (cut {cU[nU][qU]:.2f}); "
          f"mean FIT ROI by N: {dict((k, round(float(v), 2)) for k, v in mU.items())}; "
          f"neighbour means over q: {[round(float(x), 2) for x in smU]}")
    print(f"(exploratory OVER mirror by the same rule: N={nO} q={qO})")

    # ── controls on FIT ──
    hdr("4. Controls on FIT (close -110)")
    cX = side_cuts(Gf, "xM")
    fitX, _ = side_grid(Gf, "xM", cX, False, "close", nF)
    print("P2 efficiency-only: BACK the team with the higher window expected margin (xM):")
    print(fitX.to_string(index=False))
    cM = side_cuts(Gf, "M")
    fitM, _ = side_grid(Gf, "M", cM, True, "close", nF)
    print("\nP3 actual-margin-only: FADE the team with the higher window actual margin:")
    print(fitM.to_string(index=False))
    cPF = total_cuts(Gf, "PF", True)
    fitPF, _ = total_grid(Gf, "PF", cPF, True, "close", nF)
    print("\nP3T actual-points-only: UNDER when the two offenses' window actual PF is high:")
    print(fitPF.to_string(index=False))
    cXPF = total_cuts(Gf, "xPF", True)
    fitXPF, _ = total_grid(Gf, "xPF", cXPF, True, "close", nF)
    print("\nP2T efficiency-only totals (direction as the luck rule: UNDER when window xPF sum is high;"
          " the OVER side is its mirror at ~ -ROI - vig):")
    print(fitXPF.to_string(index=False))

    # overlap of the luck selection with the actual-margin selection (FIT)
    ov = []
    for n in NS:
        for q in QS:
            a = betsFS[(n, q)][["game_id", "bet_home"]]
            Dm = side_D(Gf, "M", n)
            ok = Dm.notna()
            b = side_bets(Gf[ok], Dm[ok], cM[n][q], fade=True, src="close")[["game_id", "bet_home"]]
            j = a.merge(b, on="game_id", suffixes=("_l", "_m"))
            ov.append({"N": n, "q": q, "luck_bets": len(a), "margin_bets": len(b), "same_game": len(j),
                       "same_side%": round(100 * (j["bet_home_l"] == j["bet_home_m"]).mean(), 1) if len(j) else np.nan})
    print("\nOverlap of the luck-gap fade with the actual-margin fade (FIT):")
    print(pd.DataFrame(ov).to_string(index=False))
    corr = np.corrcoef(side_D(Gf, "luckM", 6).fillna(0), side_D(Gf, "M", 6).fillna(0))[0, 1]
    print(f"corr(D_luck, D_margin) at N=6 on FIT games: {corr:+.3f}")

    if "--fit-only" in sys.argv:
        print("--fit-only: stopping before the hold-out is read.")
        return

    # ── HOLD (read once) ──
    hdr("5. HOLD-OUT 2020-2025 - read once. Sides at the T-3h bettable board; totals bettable 2023-2025 only")
    holdS, betsHS = side_grid(Gh, "luckM", cS, True, "board", nH)
    print("SIDES - fade the larger luck gap - BETTABLE board (FIT cuts):")
    print(holdS.to_string(index=False))
    holdU, betsHU = total_grid(G23, "luckPF", cU, True, "board", 3)
    print("\nTOTALS UNDER - BETTABLE board 2023-2025 (FIT cuts):")
    print(holdU.to_string(index=False))
    holdO, betsHO = total_grid(G23, "luckPF", cO, False, "board", 3)
    print("\nTOTALS OVER mirror (exploratory) - BETTABLE board 2023-2025:")
    print(holdO.to_string(index=False))

    print("\nSensitivity - the same hold-out selections at the nflverse close -110:")
    hcS, _ = side_grid(Gh, "luckM", cS, True, "close", nH)
    print("SIDES 2020-2025 close -110:")
    print(hcS.to_string(index=False))
    hcU, _ = total_grid(Gh, "luckPF", cU, True, "close", nH)
    print("\nTOTALS UNDER 2020-2025 close -110 (2020-2022 totals have no fresh bettable quote):")
    print(hcU.to_string(index=False))

    print(f"\nREGISTERED cells graded once in the hold-out:")
    r1 = holdS[(holdS["N"] == nS) & (holdS["q"] == qS)]
    r2 = holdU[(holdU["N"] == nU) & (holdU["q"] == qU)]
    print("sides:"); print(r1.to_string(index=False))
    print("totals UNDER:"); print(r2.to_string(index=False))
    season_table(betsHS[(nS, qS)], f"HOLD sides registered N={nS} q={qS}")
    season_table(betsHU[(nU, qU)], f"HOLD totals UNDER registered N={nU} q={qU}")
    season_table(betsFS[(nS, qS)], f"FIT sides registered N={nS} q={qS}")
    season_table(betsFU[(nU, qU)], f"FIT totals UNDER registered N={nU} q={qU}")
    phase_grid(betsHS, nH, "HOLD sides bettable")
    phase_grid(betsHU, 3, "HOLD totals UNDER bettable 2023-2025")
    volume_table({**{k: v for k, v in betsFS.items()}}, "FIT sides")
    volume_table(betsHS, "HOLD sides")
    volume_table(betsFU, "FIT totals UNDER")
    volume_table(betsHU, "HOLD totals UNDER (2023-2025)")

    # season-by-season for every N at the registered q
    rows = []
    for n in NS:
        for era_bets in (betsFS, betsHS):
            B = era_bets[(n, qS)]
            for s, x in B.groupby("season"):
                c = cell(x, 1)
                rows.append({"N": n, "season": s, "bets": c["bets"], "units": c["units"], "roi%": c["roi%"]})
    Y = pd.DataFrame(rows).pivot_table(index="season", columns="N", values=["bets", "roi%"], sort=False)
    print(f"\nSides, every season, every N at q={qS} (FIT close -110 / HOLD bettable):")
    print(Y.to_string())

    # publisher-period analogue
    Ga = G[G["season"].between(2018, 2025)]
    D = side_D(Ga, "luckM", nS)
    ok = D.notna()
    Ba = side_bets(Ga[ok], D[ok], cS[nS][qS], fade=True, src="close")
    c = cell(Ba, 8)
    print(f"\nPublisher-period ANALOGUE (not a replication; their rule is unpublished): registered side "
          f"cell N={nS} q={qS}, 2018-2025, nflverse close -110: "
          + ", ".join(f"{k}={float(v) if isinstance(v, (float, np.floating)) else v}" for k, v in c.items()))

    # components in the registered side selection (faded team minus the other)
    for era, Bx in (("FIT", betsFS[(nS, qS)]), ("HOLD", betsHS[(nS, qS)])):
        sgn = np.where(Bx["bet_home"], -1, 1)  # faded team = away if bet_home
        comp = {}
        for cc in ("luckM", "c_fum", "c_fg", "c_rtd", "M", "xM"):
            comp[cc] = round(float(np.mean(sgn * (Bx[wcol(cc, nS, 'h')] - Bx[wcol(cc, nS, 'a')]))), 2)
        dog = np.where(Bx["bet_home"], Bx["home_point_close"] > 0, Bx["home_point_close"] < 0)
        print(f"{era} registered side bets: faded-minus-backed window means per game {comp}; "
              f"bet is the closing underdog in {100*np.mean(dog):.1f}%")

    # ── controls on HOLD ──
    hdr("6. Controls on the hold-out (bettable board; totals 2023-2025)")
    hX, _ = side_grid(Gh, "xM", cX, False, "board", nH)
    print("P2 efficiency-only: BACK the higher window xM:")
    print(hX.to_string(index=False))
    hM, _ = side_grid(Gh, "M", cM, True, "board", nH)
    print("\nP3 actual-margin-only: FADE the higher window actual margin:")
    print(hM.to_string(index=False))
    hPF, _ = total_grid(G23, "PF", cPF, True, "board", 3)
    print("\nP3T actual-points-only UNDER (2023-2025):")
    print(hPF.to_string(index=False))
    hXPF, _ = total_grid(G23, "xPF", cXPF, True, "board", 3)
    print("\nP2T efficiency-only UNDER when xPF sum high (2023-2025):")
    print(hXPF.to_string(index=False))

    hdr(f"7. P1 shuffled-assignment placebo ({NSHUF} reps)")
    Gbase = G[G["season"].between(FIT[0], HOLD[1])][
        ["game_id", "season", "week", "game_type", "result", "total", "home_point_close",
         "total_line", "b_point", "b_ph", "b_pa", "t_point", "t_po", "t_pu"]].reset_index(drop=True)
    Rs = shuffle_placebo(T, Gbase, "side")
    placebo_table(Rs, {k: v["profit"].mean() for k, v in betsFS.items() if len(v)}, "FIT", "sides FIT close")
    placebo_table(Rs, {k: v["profit"].mean() for k, v in betsHS.items() if len(v)}, "HOLD", "sides HOLD bettable")
    Rt = shuffle_placebo(T, Gbase, "total")
    placebo_table(Rt, {k: v["profit"].mean() for k, v in betsFU.items() if len(v)}, "FIT", "totals UNDER FIT close")
    placebo_table(Rt, {k: v["profit"].mean() for k, v in betsHU.items() if len(v)}, "HOLD23",
                  "totals UNDER HOLD bettable 2023-2025")

    hdr("8. Benjamini-Hochberg over the hold-out hypothesis cells (q = 0.10)")
    allc = pd.concat([holdS.assign(grid="sides fade"), holdU.assign(grid="totals UNDER"),
                      holdO.assign(grid="totals OVER (expl)")], ignore_index=True)
    allc = allc[allc["bets"] > 0]
    passed, thr = bh(allc["p1"].values)
    allc["BH_pass"] = passed
    print(f"comparisons m = {len(allc)}; BH largest passing threshold = {thr:.4f}; cells passing = {int(passed.sum())}")
    print(allc.sort_values("p1").head(12)[["grid", "N", "q", "bets", "units", "roi%", "ci90_lo",
                                          "ci90_hi", "p1", "BH_pass"]].to_string(index=False))

    # ── POST-HOC (added after the hold-out was read; not registered, not in BH) ──
    hdr("9. POST-HOC checks on the exploratory OVER mirror (added after section 5 was read; not registered)")
    G2022 = G[G["season"].between(2020, 2022)].copy()
    hoC, betsHoC = total_grid(Gh, "luckPF", cO, False, "close", nH)
    print("OVER mirror, 2020-2025 at the nflverse close -110:")
    print(hoC.to_string(index=False))
    ho22, _ = total_grid(G2022, "luckPF", cO, False, "close", 3)
    print("\nOVER mirror, 2020-2022 only (seasons in neither FIT nor the bettable 2023-2025 grid), close -110:")
    print(ho22.to_string(index=False))
    cPFlo = total_cuts(Gf, "PF", False)
    fPFlo, _ = total_grid(Gf, "PF", cPFlo, False, "close", nF)
    print("\nControl: OVER when the two offenses' window ACTUAL PF sum is LOW - FIT close -110:")
    print(fPFlo.to_string(index=False))
    hPFlo, _ = total_grid(G23, "PF", cPFlo, False, "board", 3)
    print("\nControl: OVER when window ACTUAL PF sum is LOW - HOLD 2023-2025 bettable board:")
    print(hPFlo.to_string(index=False))
    hPFlo22, _ = total_grid(G2022, "PF", cPFlo, False, "close", 3)
    print("\nControl: OVER when window ACTUAL PF sum is LOW - 2020-2022 close -110:")
    print(hPFlo22.to_string(index=False))
    for q in (0.90, 0.95):
        B = betsHO[(6, q)]
        season_table(B, f"OVER mirror N=6 q={q} HOLD 2023-2025 bettable")
        cl = B.copy()
        cl["pt"] = cl["total_line"]; cl["pr"] = -110.0
        won = (cl["total"] > cl["pt"]).astype(int); push = (cl["total"] == cl["pt"]).astype(int)
        cl["profit"] = profit_units(won.values, cl["pr"].values, push.values)
        c = cell(cl, 3)
        print(f"  same bets at the nflverse close -110: W-L-P {c['W-L-P']}, units {c['units']}, "
              f"roi {c['roi%']}% (CI {c['ci90_lo']}..{c['ci90_hi']})")
        print(f"  over price taken: mean {B['pr'].mean():.1f}, max {B['pr'].max():.0f}, min {B['pr'].min():.0f}; "
              f"board total minus close: mean {(B['pt'] - B['total_line']).mean():+.2f}, "
              f"share board < close {100*(B['pt'] < B['total_line']).mean():.0f}%; "
              f"median board lead {B['t_lead'].median():.1f}h")
        season_table(betsHoC[(6, q)][betsHoC[(6, q)]["season"] <= 2022], f"OVER mirror N=6 q={q} 2020-2022 close")
    # base rate: every 2023-2025 game with a board, over and under at the board
    Gb = G23[G23["t_point"].notna()]
    for nm, under in (("UNDER", True), ("OVER", False)):
        B = total_bets(Gb, pd.Series(np.ones(len(Gb)), index=Gb.index), 0.0 if under else 2.0,
                       under=under, src="board")
        c = cell(B, 3)
        print(f"Base rate 2023-2025, every game with a totals board, {nm} at the best board price: "
              f"bets {c['bets']}, W-L-P {c['W-L-P']}, roi {c['roi%']}% (CI {c['ci90_lo']}..{c['ci90_hi']})")


if __name__ == "__main__":
    main()
