"""EuroLeague halftime research, round 4 (files r4_*): the shared pieces.

The pre-registration (decision time, quote rule, model, cut grid, variants,
baselines, kill tests) is section 0 of
C:\\Users\\micha\\AppData\\Local\\Temp\\euroleague_halftime.md and was written
before any r4 result was computed. This module loads, prices, decides and
grades; it holds no tuned number. Everything it ports is from
models/ncaabw_live_ht.py and scripts/ncaabw_research/inplay.py, unchanged
except the clock definitions EuroLeague's shot feed forces.

Reused: r1_lib.stake / summary (1 unit to win, risk capped at 3; 90% date
bootstrap), r2_lib.load_quotes / last_pretip (the change-only full-game
board, coherent rows only), r2_lib.grade / result (full game, overtime in),
r2_lib.row / md_table / p_one_sided.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import r1_lib as L1  # noqa: E402
import r2_lib as L2  # noqa: E402

CACHE = L2.CACHE
OUT = Path(r"C:\Users\micha\AppData\Local\Temp\euroleague_halftime.md")
DECIDABLE = ["draftkings", "fanduel", "betmgm", "betrivers", "fanatics"]   # also the tie order
REFS = ["pinnacle", "bovada", "marathonbet", "unibet", "paddypower"]
BOOKS = DECIDABLE + REFS
RANK = {b: i for i, b in enumerate(DECIDABLE)}

# ── the ported constants (models/ncaabw_live_ht.py), unchanged ──────────────
REG_S = 2400.0
HALF_S = 1200.0
GRID_STEP_S = 30.0
LATE_F = 300.0 / REG_S
LATE_MARGIN = 8.0
PRICE_BAND = (-250.0, 250.0)
OUTLIER_PTS = 6.0
MIN_OTHERS = 2
LINE_RANGE = (60.0, 260.0)
SPREAD_MAX = 70.0
PRIOR_SPREAD_MAX = 70.0
PRIOR_TOTAL_RANGE = (90.0, 200.0)
CUTS = [0.02, 0.03, 0.05, 0.08, 0.12]
HEADLINE = 0.05
BREAK_OK = (10.0, 25.0)
BUFFER = pd.Timedelta(minutes=1)
WF_SEASONS = [2023, 2024, 2025, 2026, 2027]
SEASON_NAME = {2022: "2021-22", 2023: "2022-23", 2024: "2023-24", 2025: "2024-25",
               2026: "2025-26", 2027: "2026-27 to 11-12"}

REG: list[dict] = []          # the multiplicity registry: one entry per graded cell


# ── settlement asserts (on import) ───────────────────────────────────────────

def _check():
    # full-game settlement, reused from r2_lib (home -6.5 wins by 7 covers; whole line pushes)
    assert list(L2.result("spreads", ["home", "away"], [-6.5, -6.5], [7, 7], [0, 0])) == [1, -1]
    assert list(L2.result("spreads", ["home", "away"], [-3, -3], [3, 3], [0, 0])) == [0, 0]
    assert list(L2.result("totals", ["over", "under"], [160, 160], [0, 0], [160, 160])) == [0, 0]
    assert list(L2.result("h2h", ["home", "away"], [np.nan, np.nan], [-1, -1], [0, 0])) == [-1, 1]
    r, w = L1.stake(np.array([-150, -400, 120]))
    assert np.allclose(r, [1.5, 3.0, 1.0]) and np.allclose(w, [1.0, 0.75, 1.2])
    # the moneyline at the half: home up 10, k = -10. With the margin still to
    # come centred at 0 the home side must be a big favourite; centred at -10
    # (the lead fully given back) it is a coin flip, the tie mass split evenly.
    pw, pp = p_over(np.array([0.0, -10.0]), np.array([8.0, 8.0]), np.array([-10.0, -10.0]))
    ph = pw + 0.5 * pp
    assert ph[0] > 0.85 and abs(ph[1] - 0.5) < 1e-9
    # the spread: home -4.5 at the half, home up 6 -> k = 4.5 - 6 = -1.5
    mu = np.array([0.0])
    pw, pp = p_over(mu, np.array([8.0]), np.array([-(-4.5) - 6.0]))
    assert pp[0] == 0 and abs(pw[0] - norm.sf(-1.5 / 8.0)) < 1e-12


# ── the model (models/ncaabw_live_ht.py + the research script's margin kind) ─

def design(kind, f, cur_m, cur_t, prior_m, prior_t) -> np.ndarray:
    f = np.atleast_1d(np.asarray(f, float))
    if kind == "m":
        sur = np.asarray(cur_m, float) - np.asarray(prior_m, float) * (1 - f)
        return np.column_stack([f * prior_m, f * sur, f * f * sur])
    sur = np.asarray(cur_t, float) - np.asarray(prior_t, float) * (1 - f)
    late = ((f < LATE_F) & (np.abs(cur_m) <= LATE_MARGIN)).astype(float)
    return np.column_stack([f * prior_t, f * sur, f * f * sur, late])


def fit(tr: pd.DataFrame) -> dict:
    """Weighted least squares, the weights from the fitted variance, three passes (unchanged)."""
    out = {}
    for kind, y in (("m", "rem_m"), ("t", "rem_t")):
        X = design(kind, tr.f.values, tr.cur_m.values, tr.cur_t.values, tr.prior_m.values, tr.prior_t.values)
        yy = tr[y].values
        f = tr.f.values
        b = np.linalg.lstsq(X, yy, rcond=None)[0]
        V = np.column_stack([np.ones(len(tr)), f, f ** 2])
        s = None
        for _ in range(3):
            s = np.linalg.lstsq(V, (yy - X @ b) ** 2, rcond=None)[0]
            w = 1.0 / np.sqrt(np.maximum(V @ s, 1.0))
            b = np.linalg.lstsq(X * w[:, None], yy * w, rcond=None)[0]
        out[kind] = {"b": b, "s": s}
    return out


def predict(model, kind, f, cur_m, cur_t, prior_m, prior_t):
    f = np.atleast_1d(np.asarray(f, float))
    mu = design(kind, f, cur_m, cur_t, prior_m, prior_t) @ model[kind]["b"]
    s = model[kind]["s"]
    return mu, np.sqrt(np.maximum(s[0] + s[1] * f + s[2] * f * f, 1.0))


def p_over(mu, sd, k):
    """P(still to come > k), P(push); the points still to come are a whole number (unchanged)."""
    k = np.asarray(k, float)
    whole = np.abs(k - np.round(k)) < 1e-9
    pw = np.where(whole, norm.sf((k + 0.5 - mu) / sd), norm.sf((k - mu) / sd))
    pp = np.where(whole, norm.cdf((k + 0.5 - mu) / sd) - norm.cdf((k - 0.5 - mu) / sd), 0.0)
    return pw, pp


_check()


# ── games, the break, the shot feed ──────────────────────────────────────────

_C: dict = {}


def games() -> pd.DataFrame:
    """Played games with the half-time row and the first shot. `qual` = the
    break is 10-25 minutes and the game has a prior (both numbers)."""
    if "g" in _C:
        return _C["g"]
    g = L2.load_games()
    g = g[g.played].copy()
    h = pd.read_parquet(CACHE / "halftime.parquet")
    g = g.merge(h, on="game_id", how="inner")
    sh = pd.read_parquet(CACHE / "shots.parquet", columns=["game_id", "shot_utc"])
    g = g.merge(sh.groupby("game_id").shot_utc.min().rename("first_shot").reset_index(), on="game_id", how="left")
    g["ht_t"] = g.ht_home + g.ht_away
    g["ht_m"] = g.ht_home - g.ht_away
    g["break_ok"] = g.break_minutes.between(*BREAK_OK)
    pr = priors(g)
    g = g.merge(pr, on="game_id", how="left")
    g["qual"] = g.break_ok & g.prior_t.notna() & g.prior_m.notna()
    _C["g"] = g
    return g


def priors(g: pd.DataFrame) -> pd.DataFrame:
    """Per game: prior_t, prior_m (the median over books of each book's last
    pre-game number, bounded at min(tip, first shot)), and the Pinnacle-only
    pair (pin_t, pin_m) for variant V2."""
    q = L2.load_quotes(coherent_only=True, games=L2.load_games())
    q = q.merge(g[["game_id", "first_shot"]], on="game_id", how="inner")
    q = q[q.snapshot_at <= q.first_shot.fillna(q.tip)]
    last = L2.last_pretip(q)
    sp = last[(last.market == "spreads") & last.line.notna() & (last.line.abs() <= PRIOR_SPREAD_MAX)]
    to = last[(last.market == "totals") & last.line.between(*PRIOR_TOTAL_RANGE)]
    out = pd.concat([(-sp.groupby("game_id").line.median()).rename("prior_m"),
                     to.groupby("game_id").line.median().rename("prior_t"),
                     (-sp[sp.bookmaker == "pinnacle"].set_index("game_id").line).rename("pin_m"),
                     to[to.bookmaker == "pinnacle"].set_index("game_id").line.rename("pin_t")], axis=1)
    return out.rename_axis("game_id").reset_index()


def states() -> dict:
    """Per game: game seconds (running maximum) and the score (running maximum),
    shots sorted by shot_utc then num_anot (the women's reading, unchanged)."""
    if "st" in _C:
        return _C["st"]
    s = pd.read_parquet(CACHE / "shots.parquet", columns=["game_id", "num_anot", "minute", "console",
                                                          "points_home", "points_away", "shot_utc"])
    cs = s.console.str.split(":", expand=True)
    clock = (pd.to_numeric(cs[0], errors="coerce") * 60 + pd.to_numeric(cs[1], errors="coerce")).clip(lower=0)
    m = s.minute.to_numpy()
    reg = m <= 40
    qtr = np.where(reg, (m - 1) // 10 + 1, 5 + (m - 41) // 5)
    gs = np.where(reg, (qtr - 1) * 600 + 600 - clock, REG_S + (qtr - 5) * 300 + 300 - clock)
    s = s.assign(gs=gs).dropna(subset=["gs"]).sort_values(["game_id", "shot_utc", "num_anot"], kind="mergesort")
    out = {}
    for gid, x in s.groupby("game_id", sort=False):
        out[gid] = {"gs": np.maximum.accumulate(x.gs.to_numpy(float)),
                    "h": np.maximum.accumulate(x.points_home.to_numpy(float)),
                    "a": np.maximum.accumulate(x.points_away.to_numpy(float))}
    _C["st"] = out
    return out


def training_rows(seasons, prior_cols=("prior_m", "prior_t")) -> pd.DataFrame:
    """The score every 30 s of regulation of every qualifying game of `seasons`."""
    g = games()
    g = g[g.qual & g.season.isin(seasons)]
    if prior_cols != ("prior_m", "prior_t"):
        g = g[g[prior_cols[0]].notna() & g[prior_cols[1]].notna()]
    st = states()
    grid = np.arange(GRID_STEP_S, REG_S, GRID_STEP_S)
    rows = []
    for r in g.itertuples(index=False):
        x = st.get(r.game_id)
        if x is None:
            continue
        idx = np.searchsorted(x["gs"], grid, side="right") - 1
        ok = idx >= 0
        cm = (x["h"] - x["a"])[idx[ok]]
        ct = (x["h"] + x["a"])[idx[ok]]
        rows.append(pd.DataFrame({"f": 1 - grid[ok] / REG_S, "cur_m": cm, "cur_t": ct,
                                  "prior_m": getattr(r, prior_cols[0]), "prior_t": getattr(r, prior_cols[1]),
                                  "rem_m": r.margin - cm, "rem_t": r.total - ct}))
    return pd.concat(rows, ignore_index=True)


_M: dict = {}


def model_for(season: int, prior_cols=("prior_m", "prior_t")) -> dict:
    """Walk-forward: fitted on every earlier season from 2022; 2022 (no earlier
    season) gets the second-look fit on 2023."""
    key = (season, prior_cols)
    if key not in _M:
        tr_s = [2023] if season == 2022 else list(range(2022, season))
        tr = training_rows(tr_s, prior_cols)
        m = fit(tr)
        m["n_states"] = len(tr)
        m["n_games"] = int(len(tr) / 79) if len(tr) else 0
        m["train"] = tr_s
        _M[key] = m
    return _M[key]


# ── the halftime quotes ──────────────────────────────────────────────────────

def ht_quotes() -> pd.DataFrame:
    """Every in-play quote whose read falls inside a qualifying game's break.
    Adds: line, pa (home/over), pb (away/under), inplay, fresh, med, others, off."""
    if "q" in _C:
        return _C["q"]
    q = pd.read_parquet(CACHE / "inplay_quotes.parquet")
    n0 = len(q)
    bad = q.last_update > q.snapshot_ts
    _C["dropped_future_stamp"] = int(bad.sum())
    q = q[~bad]
    g = games()
    q = q.merge(g[g.qual][["game_id", "season", "game_date", "tip", "margin", "total", "last_q2_shot",
                          "first_q3_shot", "first_shot", "ht_home", "ht_away", "ht_t", "ht_m",
                          "prior_t", "prior_m", "pin_t", "pin_m", "break_minutes"]], on="game_id", how="inner")
    q = q[(q.snapshot_ts > q.last_q2_shot + BUFFER) & (q.snapshot_ts < q.first_q3_shot - BUFFER)].copy()
    tot = q.market == "totals"
    sp = q.market == "spreads"
    q["line"] = np.where(sp, q.spread_home, np.where(tot, q.total_line, np.nan))
    q["pa"] = np.where(tot, q.over_price, q.home_price)
    q["pb"] = np.where(tot, q.under_price, q.away_price)
    q["inplay"] = q.last_update >= q.first_shot
    q["fresh"] = q.inplay & (q.last_update > q.last_q2_shot)
    q["priced"] = np.isfinite(q.pa) & np.isfinite(q.pb) & (q.pa.abs() >= 100) & (q.pb.abs() >= 100)
    q["priced"] &= (q.market == "h2h") | np.isfinite(q.line)
    k = ["snapshot_ts", "game_id", "market"]
    ip = q[q.inplay & q.priced]
    agg = ip.groupby(k).agg(med=("line", "median"), nbooks=("bookmaker", "size")).reset_index()
    q = q.merge(agg, on=k, how="left")
    q["nbooks"] = q.nbooks.fillna(0)
    q["others"] = q.nbooks - (q.inplay & q.priced).astype(int)
    q["off"] = (q.line - q.med).abs()
    q["decidable"] = q.bookmaker.isin(DECIDABLE)
    q = q.sort_values(["game_id", "market", "snapshot_ts", "bookmaker"], kind="mergesort").reset_index(drop=True)
    _C["q"] = q
    _C["n_inplay_rows"] = n0
    return q


def price(q: pd.DataFrame, model: dict, ht_h=None, ht_a=None, prior=("prior_m", "prior_t")) -> pd.DataFrame:
    """Price every quote at the half-time state (f = 0.5). Returns side, price,
    ev, prob, fav. ht_h / ht_a override the state (the placebo)."""
    h = q.ht_home.to_numpy(float) if ht_h is None else np.asarray(ht_h, float)
    a = q.ht_away.to_numpy(float) if ht_a is None else np.asarray(ht_a, float)
    cm, ct = h - a, h + a
    pm, pt = q[prior[0]].to_numpy(float), q[prior[1]].to_numpy(float)
    f = np.full(len(q), 0.5)
    mk = q.market.to_numpy()
    line = q.line.to_numpy(float)
    mu_t, sd_t = predict(model, "t", f, cm, ct, pm, pt)
    mu_m, sd_m = predict(model, "m", f, cm, ct, pm, pt)
    is_t, is_s = mk == "totals", mk == "spreads"
    k = np.where(is_t, line - ct, np.where(is_s, -line - cm, -cm))
    mu = np.where(is_t, mu_t, mu_m)
    sd = np.where(is_t, sd_t, sd_m)
    pw, pp = p_over(mu, sd, np.nan_to_num(k))
    pl = 1 - pw - pp
    with np.errstate(divide="ignore", invalid="ignore"):
        p1 = np.where(mk == "h2h", pw + 0.5 * pp, pw / (pw + pl))
    d1, d2 = L1.dec(q.pa.to_numpy(float)), L1.dec(q.pb.to_numpy(float))
    ev1, ev2 = p1 * d1 - 1, (1 - p1) * d2 - 1
    first = ev1 >= ev2
    out = q.copy()
    out["p_a"] = p1
    out["side"] = np.where(is_t, np.where(first, "over", "under"), np.where(first, "home", "away"))
    out["price"] = np.where(first, q.pa, q.pb)
    out["other_price"] = np.where(first, q.pb, q.pa)
    out["ev"] = np.where(first, ev1, ev2)
    out["prob"] = np.where(first, p1, 1 - p1)
    out["mu"] = mu
    out["sd"] = sd
    out["fav"] = fav_flag(out)
    return out


def fav_flag(x: pd.DataFrame) -> np.ndarray:
    """Favourite: spreads, the side giving points at the half; moneyline, the
    shorter price; totals, NaN."""
    mk = x.market.to_numpy()
    side = x.side.to_numpy()
    line = x.line.to_numpy(float)
    sp_fav = np.where(side == "home", line < 0, line > 0)
    ml_fav = L1.dec(x.price.to_numpy(float)) < L1.dec(x.other_price.to_numpy(float))
    return np.where(mk == "spreads", sp_fav, np.where(mk == "h2h", ml_fav, False))


def eligible(x: pd.DataFrame, min_others: int = MIN_OTHERS, need_fresh: bool = True) -> np.ndarray:
    mk = x.market.to_numpy()
    line = x.line.to_numpy(float)
    ok = x.decidable.to_numpy() & x.inplay.to_numpy() & x.priced.to_numpy()
    if need_fresh:
        ok &= x.fresh.to_numpy()
    ok &= (x.price.to_numpy(float) >= PRICE_BAND[0]) & (x.price.to_numpy(float) <= PRICE_BAND[1])
    ok &= x.others.to_numpy(float) >= min_others
    with np.errstate(invalid="ignore"):
        ok &= (mk == "h2h") | (x.off.to_numpy(float) <= OUTLIER_PTS)
        ok &= np.where(mk == "totals", (line >= LINE_RANGE[0]) & (line <= LINE_RANGE[1]),
                       np.where(mk == "spreads", np.abs(line) <= SPREAD_MAX, True))
    return ok


def decide(x: pd.DataFrame, cut: float, how: str = "first", min_others: int = MIN_OTHERS,
           need_fresh: bool = True) -> pd.DataFrame:
    """One decision per (game, market). how: first | last | crossing."""
    e = x[eligible(x, min_others, need_fresh)]
    if not len(e):
        return e.assign(_r=[])
    e = e.assign(_r=e.bookmaker.map(RANK))
    e = e.sort_values(["game_id", "market", "snapshot_ts", "ev", "_r"], ascending=[True, True, True, False, True],
                      kind="mergesort")
    if how == "crossing":
        return e[e.ev >= cut].drop_duplicates(["game_id", "market"], keep="first")
    pick = "min" if how == "first" else "max"
    ts = e.groupby(["game_id", "market"]).snapshot_ts.transform(pick)
    best = e[e.snapshot_ts == ts].drop_duplicates(["game_id", "market"], keep="first")
    return best[best.ev >= cut]


def decided_games(x: pd.DataFrame, how="first", min_others=MIN_OTHERS, need_fresh=True) -> pd.DataFrame:
    """Every decision (no cut): the deciding quote of each (game, market)."""
    return decide(x, -np.inf, how, min_others, need_fresh)


def grade(df: pd.DataFrame) -> pd.DataFrame:
    if not len(df):
        return df.assign(res=[], risk=[], units=[])
    return L2.grade(df, market_col="market", side_col="side", line_col="line", price_col="price")


# ── the priced, walk-forward table ───────────────────────────────────────────

def priced_wf(prior=("prior_m", "prior_t"), seasons=None) -> pd.DataFrame:
    """Every halftime quote of each walk-forward season priced by that season's
    walk-forward model (2022 with the second-look model; flagged wf=False)."""
    q = ht_quotes()
    if prior != ("prior_m", "prior_t"):
        q = q[q[prior[0]].notna() & q[prior[1]].notna()]
    parts = []
    for s in (seasons or [2022] + WF_SEASONS):
        x = q[q.season == s]
        if not len(x):
            continue
        parts.append(price(x, model_for(s, prior), prior=prior).assign(wf=s != 2022))
    return pd.concat(parts, ignore_index=True)


# ── summaries ────────────────────────────────────────────────────────────────

def row(label: dict, df: pd.DataFrame) -> dict:
    return L2.row(label, df)


def reg(exp: str, cell: str, df: pd.DataFrame) -> dict:
    """Count a cell toward Benjamini-Hochberg and return its row."""
    r = row({"experiment": exp, "cell": cell}, df)
    REG.append({"experiment": exp, "cell": cell, "bets": r["bets"], "units": r["units"],
                "ret%": r["ret%"], "lo%": r["lo%"], "hi%": r["hi%"],
                "p_one": r["p_one"] if np.isfinite(r["p_one"]) else 1.0})
    return r


def price_range(x: pd.DataFrame) -> str:
    if not len(x):
        return "no bets"
    p = x.price.to_numpy(float)
    return (f"median {np.median(p):+.0f}, shortest {p.min():+.0f}, longest {p.max():+.0f}, "
            f"shorter than -300: {100 * np.mean(p < -300):.1f}%, shorter than -500: {100 * np.mean(p < -500):.1f}%")


def md(rows) -> str:
    return L2.md_table(pd.DataFrame(rows))


def section(title: str, script: str, body: str) -> str:
    return f"\n## {title}\n\nScript: `scripts/euroleague_research/{script}`.\n\n{body}\n"
