"""Round 2, experiment D: three mechanisms of our own for the first half and
three for the first quarter, plus round 1's frozen first-quarter under lead
read unchanged (pre-registration: section 0.5 of euroleague_round2.md).
Returns / prints markdown.

  H1-i / Q1-i     club(-pair) period share of the full-game total, prior games only
  H1-ii / Q1-ii   the period moneyline shrunk toward 50% (k fitted on earlier seasons)
  H1-iii / Q1-iii the stale derivative: the full game moved T-60 -> T-10, the period line did not
  P2              r1_method V2 totals_q1, fitted 2023-24..2025-26, graded 2026-27, by its own code

    python scripts/euroleague_research/r3_d_periods.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import expit, logit

import r1_lib as L1
import r2_lib as L2
import r3_lib as R

EXP = "D"
K_SHARE = 40.0
DEC_PERIOD = ["fanduel", "betmgm", "betrivers", "fanatics", "draftkings"]
OFF = ["betus", "gtbets", "mybookieag"]
SHARE_GRID = {"h1": [0.5, 1.0, 1.5, 2.0], "q1": [0.25, 0.5, 0.75, 1.0]}
SHARE_HEAD = {"h1": 1.0, "q1": 0.5}
SHRINK_GRID = [0.00, 0.01, 0.02, 0.03, 0.04]
SHRINK_HEAD = 0.02
STALE_GRID = {"h1": [0.5, 1.0, 1.5], "q1": [0.25, 0.5, 0.75]}
STALE_HEAD = {"h1": 1.0, "q1": 0.5}
FRAC = {"h1": 0.5, "q1": 0.25}


def period_cols(per):
    return f"{per}_total", f"{per}_margin"


def attach(z: pd.DataFrame, g1: pd.DataFrame, per: str) -> pd.DataFrame:
    tcol, mcol = period_cols(per)
    z = z.merge(g1[["game_id", "season", "game_date", tcol, mcol]], on="game_id", how="left", suffixes=("", "_g"))
    if "season_g" in z:
        z["season"] = z.season.fillna(z.season_g)
        z = z.drop(columns="season_g")
    if "game_date_g" in z:
        z["game_date"] = z.game_date.fillna(z.game_date_g)
        z = z.drop(columns="game_date_g")
    z["total"], z["margin"] = z[tcol], z[mcol]
    return z


# ── the full-game anchor at the period quote's fetch ─────────────────────────

def anchors(q: pd.DataFrame, mark: str) -> pd.DataFrame:
    """Per game: the full-game total at `mark`: Pinnacle's ladder fair at the
    same fetch, else Pinnacle's main total on the board at the period fetch's
    asked_at, else DraftKings'."""
    pin = R.pin_ladder()
    pin = pin[pin.mark == mark][["game_id", "pin_total"]]
    ids = q[q.mark == mark].groupby("game_id").asked_at.min()
    ids = pd.to_datetime(ids, utc=True)
    g, fq, dt, cb, fp = R.fullgame()
    b = L2.board_at(fq[fq.market == "totals"], ids)
    pm = b[b.bookmaker == "pinnacle"].set_index("game_id").line
    dm = b[b.bookmaker == "draftkings"].set_index("game_id").line
    a = pd.DataFrame({"game_id": ids.index})
    a = a.merge(pin, on="game_id", how="left")
    a["pin_main"] = a.game_id.map(pm)
    a["dk_main"] = a.game_id.map(dm)
    a["anchor"] = a.pin_total.fillna(a.pin_main).fillna(a.dk_main)
    a["anchor_src"] = np.where(a.pin_total.notna(), "pinnacle ladder", np.where(a.pin_main.notna(), "pinnacle main",
                               np.where(a.dk_main.notna(), "draftkings main", "none")))
    return a


# ── H1-i / Q1-i: club shares ─────────────────────────────────────────────────

def club_shares(g1: pd.DataFrame, per: str) -> pd.DataFrame:
    tcol, _ = period_cols(per)
    g = g1[g1.played & g1[tcol].notna() & (g1.fg_total > 0)].sort_values("tip").reset_index(drop=True).copy()
    g["share"] = g[tcol] / g.fg_total
    idx = R.prior_index(g.tip)
    lsum, ln = 0.0, 0
    csum, cn = {}, {}
    league, dh, da = np.full(len(g), np.nan), np.zeros(len(g)), np.zeros(len(g))
    ptr = 0
    for i in range(len(g)):
        while ptr < idx[i]:
            s = float(g.share.iloc[ptr])
            lsum += s
            ln += 1
            for c in (g.home_code.iloc[ptr], g.away_code.iloc[ptr]):
                csum[c] = csum.get(c, 0.0) + s
                cn[c] = cn.get(c, 0) + 1
            ptr += 1
        if ln == 0:
            continue
        lm = lsum / ln
        league[i] = lm
        for arr, c in ((dh, g.home_code.iloc[i]), (da, g.away_code.iloc[i])):
            n = cn.get(c, 0)
            arr[i] = (csum.get(c, 0.0) - n * lm) / (n + K_SHARE)
    g["league_share"], g["dev_home"], g["dev_away"] = league, dh, da
    g["pair_share"] = g.league_share + g.dev_home + g.dev_away
    return g[["game_id", "league_share", "dev_home", "dev_away", "pair_share", "share"]]


def share_bets(mb0: pd.DataFrame, A: pd.DataFrame, S: pd.DataFrame, g1, per, m):
    """mb0: R.modal_best of the books' T-10 quotes (computed once; it does not
    depend on the shares)."""
    mb = mb0.merge(A[["game_id", "anchor"]], on="game_id").merge(S[["game_id", "pair_share", "league_share"]], on="game_id")
    mb["implied"] = mb.pair_share * mb.anchor
    mb["edge_pts"] = mb.implied - mb.line
    over = mb[mb.edge_pts >= m].assign(side="over", price=lambda d: d.best_pa, bookmaker=lambda d: d.book_a)
    under = mb[mb.edge_pts <= -m].assign(side="under", price=lambda d: d.best_pb, bookmaker=lambda d: d.book_b)
    z = pd.concat([over, under], ignore_index=True)
    z = attach(z, g1, per)
    if not len(z):
        z["res"] = []
        z["risk"] = []
        z["units"] = []
        return z
    return L1.grade_rows(z, f"totals_{per}")


def share_placebo(mb_dec, A, S, g1, per, m, graded_ids, real, n=200, seed=11):
    rng = np.random.default_rng(seed)
    out = []
    graded = S[S.game_id.isin(graded_ids)].merge(g1[["game_id", "season"]], on="game_id")
    for _ in range(n):
        P = graded.copy()
        dev = (P.pair_share - P.league_share).to_numpy()
        P["pair_share"] = P.league_share + pd.Series(dev, index=P.index).groupby(P.season).transform(
            lambda v: rng.permutation(v.to_numpy()))
        zz = share_bets(mb_dec, A, P, g1, per, m)
        out.append(100 * zz.units.sum() / zz.risk.sum() if len(zz) and zz.risk.sum() > 0 else np.nan)
    o = np.array(out)
    return {"m": m, "real ret%": round(real, 2), "placebo mean ret%": round(float(np.nanmean(o)), 2),
            "placebo 95th pct": round(float(np.nanpercentile(o, 95)), 2), "share >= real": round(float(np.nanmean(o >= real)), 3)}


def run_share(md, per, q, g1, A):
    market = f"totals_{per}"
    S = club_shares(g1, per)
    qt = q[(q.market == market) & (q.mark == "T-10")]
    tag = "H1-i" if per == "h1" else "Q1-i"
    md.append(f"\n### {tag}. Club-pair {per.upper()} share of the full-game total (r3_d_periods.py)\n")
    sd = S[S.game_id.isin(qt.game_id)]
    md.append(f"Pair-share deviation from the league mean on the priced games: SD {(sd.pair_share - sd.league_share).std():.4f}, "
              f"league mean share {sd.league_share.mean():.4f}; anchor sources at T-10: "
              f"{A.anchor_src.value_counts().to_dict()}.\n")
    dec_q = qt[qt.season.isin([2026, 2027]) & qt.bookmaker.isin(DEC_PERIOD)]
    off_q = qt[qt.season.isin([2024, 2025]) & qt.bookmaker.isin(OFF)]
    mb_dec = R.modal_best(dec_q, "over", "under")
    mb_off = R.modal_best(off_q, "over", "under")
    rows = []
    bets = {}
    for m in SHARE_GRID[per]:
        z = share_bets(mb_dec, A, S, g1, per, m)
        bets[m] = z
        rows.append(R.reg(EXP, f"{tag} {market} share rule, decidable, m {m}", z) |
                    {"over share%": round(100 * float((z.side == "over").mean()), 1) if len(z) else np.nan})
        zo = share_bets(mb_off, A, S, g1, per, m)
        rows.append(R.row({"experiment": EXP, "cell": f"{tag} {market} share rule, OFFSHORE reference 2023-24/2024-25, m {m}"}, zo) |
                    {"over share%": round(100 * float((zo.side == "over").mean()), 1) if len(zo) else np.nan})
    md.append(R.table(rows))
    # the headline, plus any other grid cell whose interval is above zero (kill-tested, flagged as not the headline)
    test = [SHARE_HEAD[per]] + [m for m in SHARE_GRID[per] if m != SHARE_HEAD[per]
                                and len(bets[m]) and R.row({}, bets[m])["lo%"] > 0]
    prow = []
    for m in test:
        z = bets[m]
        real = 100 * z.units.sum() / z.risk.sum() if len(z) and z.risk.sum() > 0 else np.nan
        prow.append(share_placebo(mb_dec, A, S, g1, per, m, dec_q.game_id.unique(), real))
    md.append("\nPlacebo (pair deviations shuffled across each season's games, 200 times), the headline"
              + (" and every other grid cell with its interval above zero" if len(test) > 1 else "") + ":\n")
    md.append(R.table(prow))
    for m in test:
        z = bets[m]
        lab = "the headline" if m == SHARE_HEAD[per] else "NOT the headline: a grid cell with its interval above zero"
        md.append(f"\nKill rows at m = {m} ({lab}): price range {R.price_range(z)}\n")
        md.append(R.table(R.kill_rows(f"{tag} m {m}", z, fav_col=None)))
    return bets


# ── H1-ii / Q1-ii: the moneyline shrink ──────────────────────────────────────

def fit_k(df):
    L = logit(df.p_med.clip(1e-6, 1 - 1e-6)).to_numpy()
    y = df.y.to_numpy(float)

    def nll(k):
        p = np.clip(expit(k * L), 1e-12, 1 - 1e-12)
        return -np.sum(y * np.log(p) + (1 - y) * np.log(1 - p))
    return float(minimize_scalar(nll, bounds=(0.2, 2.0), method="bounded").x)


def run_shrink(md, per, q, g1):
    market = f"h2h_{per}"
    tag = "H1-ii" if per == "h1" else "Q1-ii"
    _, mcol = period_cols(per)
    x = q[(q.market == market) & (q.mark == "T-10")]
    med = x.groupby("game_id").pa_fair.median().rename("p_med").reset_index()
    med = med.merge(g1[["game_id", "season", mcol]], on="game_id")
    med = med[med[mcol] != 0]
    med["y"] = (med[mcol] > 0).astype(float)
    ks = {}
    for s in (2026, 2027):
        tr = med[(med.season < s) & (med.season >= 2024)]
        ks[s] = (fit_k(tr), len(tr))
    md.append(f"\n### {tag}. The {per.upper()} moneyline shrunk toward 50% (r3_d_periods.py)\n")
    md.append("k (logit P = k x logit(median no-vig over every book at T-10), no intercept, ties out), fitted on earlier seasons: " +
              "; ".join(f"graded {s}: k = {k:.4f} on {n} games" for s, (k, n) in ks.items()) + "\n")
    dq = x[x.bookmaker.isin(DEC_PERIOD) & x.season.isin([2026, 2027])]
    md.append(f"Decidable books quoting at T-10 in the graded seasons: {dq.groupby(['season', 'bookmaker']).game_id.nunique().to_dict()}\n")
    z = dq.merge(med[["game_id", "p_med"]], on="game_id")
    z["k"] = z.season.map({s: v[0] for s, v in ks.items()})
    z["p_s"] = expit(z.k * logit(z.p_med.clip(1e-6, 1 - 1e-6)))
    a = z.assign(side="home", price=z.pa, fair=z.pa_fair, pm=z.p_s)
    b = z.assign(side="away", price=z.pb, fair=1 - z.pa_fair, pm=1 - z.p_s)
    s2 = pd.concat([a, b], ignore_index=True)
    s2["edge"] = s2.pm - s2.fair
    s2["fav"] = s2.price < 0
    s2 = s2[s2.price >= -200]
    one = s2.sort_values(["game_id", "edge", "bookmaker"], ascending=[True, False, True]).drop_duplicates("game_id")
    one = L1.grade_rows(one, market)
    rows = []
    for c in SHRINK_GRID:
        y = one[one.edge > c]
        rows.append(R.reg(EXP, f"{tag} {market} shrink, decidable, cut {c:.2f}", y) |
                    {"underdog share%": round(100 * float((~y.fav).mean()), 1) if len(y) else np.nan})
    md.append(R.table(rows))
    # controls: the blind underdog at the best decidable price, all games and the bet games
    dog = s2[~s2.fav]
    dog = R.best_price(dog, keys=("game_id",))
    dog = L1.grade_rows(dog, market)
    hb = one[one.edge > SHRINK_HEAD]
    md.append("\nControls (not counted): the blind underdog at the best decidable price:\n")
    md.append(R.table([R.row({"control": "every graded game"}, dog),
                       R.row({"control": "the headline rule's games only"}, dog[dog.game_id.isin(hb.game_id)])] +
                      [R.row({"control": f"every graded game, season {int(s)}"}, xs) for s, xs in dog.groupby("season")]))
    md.append(f"\nKill rows at the headline cut {SHRINK_HEAD}: price range {R.price_range(hb)}\n")
    md.append(R.table(R.kill_rows(f"{tag} cut {SHRINK_HEAD}", hb)))
    return one


# ── H1-iii / Q1-iii: the stale derivative ────────────────────────────────────

def run_stale(md, per, q, g1):
    market = f"totals_{per}"
    tag = "H1-iii" if per == "h1" else "Q1-iii"
    pin = R.pin_ladder()
    p10 = pin[pin.mark == "T-10"].set_index("game_id").pin_total
    p60 = pin[pin.mark == "T-60"].set_index("game_id").pin_total
    x = q[q.market == market]
    a = x[x.mark == "T-10"][["game_id", "bookmaker", "season", "game_date", "line", "pa", "pb"]]
    b = x[x.mark == "T-60"][["game_id", "bookmaker", "line"]].rename(columns={"line": "line60"})
    z = a.merge(b, on=["game_id", "bookmaker"])
    z["fg_move"] = z.game_id.map(p10) - z.game_id.map(p60)
    z = z[z.fg_move.notna()]
    z["gap"] = FRAC[per] * z.fg_move - (z.line - z.line60)
    md.append(f"\n### {tag}. The stale {per.upper()} total: the full game moved T-60 -> T-10 (r3_d_periods.py)\n")
    dz = z[z.bookmaker.isin(DEC_PERIOD) & z.season.isin([2026, 2027])]
    md.append(f"Decidable quotes with both marks and a Pinnacle move: {len(dz)} on {dz.game_id.nunique()} games; "
              f"Pinnacle full-game total moved on {100 * float((dz.fg_move != 0).mean()):.1f}% of them (mean |move| "
              f"{dz.fg_move.abs().mean():.2f}); the book's {per} line moved on {100 * float((dz.line != dz.line60).mean()):.1f}%; "
              f"|gap| >= {STALE_HEAD[per]} on {100 * float((dz.gap.abs() >= STALE_HEAD[per]).mean()):.1f}%.\n")
    rows = []
    bets = {}
    for books, seasons, lab in ((DEC_PERIOD, [2026, 2027], "decidable"), (OFF, [2024, 2025], "OFFSHORE reference 2023-24/2024-25")):
        zz = z[z.bookmaker.isin(books) & z.season.isin(seasons)].copy()
        zz["absgap"] = zz.gap.abs()
        one = zz.sort_values(["game_id", "absgap", "bookmaker"], ascending=[True, False, True]).drop_duplicates("game_id")
        for m in STALE_GRID[per]:
            y = one[one.absgap >= m].copy()
            y["side"] = np.where(y.gap > 0, "over", "under")
            y["price"] = np.where(y.side == "over", y.pa, y.pb)
            y = attach(y, g1, per)
            y = L1.grade_rows(y, market) if len(y) else y.assign(res=[], risk=[], units=[])
            if lab == "decidable":
                bets[m] = y
                rows.append(R.reg(EXP, f"{tag} {market} stale rule, decidable, m {m}", y) |
                            {"over share%": round(100 * float((y.side == "over").mean()), 1) if len(y) else np.nan})
            else:
                rows.append(R.row({"experiment": EXP, "cell": f"{tag} {market} stale rule, {lab}, m {m}"}, y) |
                            {"over share%": round(100 * float((y.side == "over").mean()), 1) if len(y) else np.nan})
    md.append(R.table(rows))
    y = bets[STALE_HEAD[per]]
    md.append(f"\nKill rows at the headline m = {STALE_HEAD[per]}: price range {R.price_range(y)}\n")
    md.append(R.table(R.kill_rows(f"{tag} m {STALE_HEAD[per]}", y, fav_col=None)))
    return bets


# ── P2: the frozen first-quarter under lead ──────────────────────────────────

def run_p2(md):
    pin = R.pin_ladder().copy()
    pin["total_us"] = np.nan
    pin["spread_us"] = np.nan
    orig = pd.read_parquet

    def rp(path, *a, **k):
        if str(path).endswith("fullgame.parquet"):
            return pin
        return orig(path, *a, **k)
    pd.read_parquet = rp
    try:
        import r1_method as M
    finally:
        pd.read_parquet = orig
    g = M.g
    md.append("\n### P2. Round 1's frozen first-quarter total lead, read unchanged (r3_d_periods.py, running r1_method's own fit and decide)\n")
    rows = []
    allb = []
    for S, fit_seasons in ((2026, [2024, 2025]), (2027, [2024, 2025, 2026])):
        fit_ids = g[g.season.isin(fit_seasons) & g.played].game_id.to_numpy()
        model = M.fit("V2", "totals_q1", fit_ids)
        gr = g[(g.season == S) & g.played].game_id.to_numpy()
        d = M.decide("V2", "totals_q1", "T-10", model, gr, L1.DECIDABLE)
        d["grade_season"] = S
        allb.append(d)
        y = d[d.edge > 0.02]
        rows.append({"graded season": S, "fit a": round(model["a"], 3), "fit b": round(model["b"], 4), "fit games": model["n"],
                     "games decided": len(d), **{k: v for k, v in L1.summary(y).items() if k in ("bets", "W", "L", "P", "units", "ret%", "lo%", "hi%")},
                     "unders": int((y.side == "under").sum())})
    md.append("Round 1: graded 2026-27 fit a = -7.826, b = 0.2978 on 1,023 games; pooled cut 0.02: 59 bets, +10.85 units, "
              "+14.96%; 2026-27 alone 4 bets, +1.80 units.\n")
    md.append(R.table(rows))
    B = pd.concat(allb, ignore_index=True)
    y = B[(B.edge > 0.02)]
    md.append("\nPooled (reproduction check) and the 2026-27 read:\n")
    r = [R.row({"subset": "pooled 2025-26 + 2026-27 (reproduction)"}, y),
         R.reg(EXP, "P2 frozen Q1 total lead, 2026-27 read", y[y.grade_season == 2027]) | {"subset": "2026-27 (no new games since round 1)"}]
    md.append(R.table(r))
    return B


def run():
    md = ["\n## D. First half and first quarter: our own mechanisms (r3_d_periods.py)\n"]
    q = R.period_main()
    g1 = R.period_games()
    # period totals and moneylines are not home bets: neutral games stay in
    A = anchors(q, "T-10")
    for per in ("h1", "q1"):
        run_share(md, per, q, g1, A)
    for per in ("h1", "q1"):
        run_shrink(md, per, q, g1)
    for per in ("h1", "q1"):
        run_stale(md, per, q, g1)
    run_p2(md)
    return "\n".join(md)


if __name__ == "__main__":
    print(run())
