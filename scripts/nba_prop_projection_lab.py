"""NBA prop projection model: calibrated, graded for the MOST UNITS A SEASON (mike, 2026-10-16).

The owner's decision: build the projection model, maximise units won, no per-game or
nightly cap. One bet per proposition across ALL NBA prop models: a (game, player,
market) the shipped Pinnacle same-line-unders rule (nba_prop_market) bets is the
rule's, so this model never bets it, on any line or side, and is graded only on
what it adds.

INPUTS -- read, never written:
  * the verifier's worker-only re-fit (verify_model/work): walk-forward predictions
    pred_wk_<S>, the negative-binomial widths alphas_wk.json, the per-market model
    choices gate_decide_wk.json, the priced quotes quotes.parquet. ESPN-style box
    lines (whole minutes, is_starter), schedule, game and prop odds, and an
    injury table holding only Out and Day-To-Day -- exactly what the worker has.
  * the shipped rule's bet list (results/props_market_bets_sharp_ALL_under_prop_0.00).
  * nba_games (tip times) from the research cache.

THE RULES OF THIS SEARCH:
  * Main lines only: the archive holds one line per book per player-market (13 of
    2,732,516 book-keys carry two), and count markets decide on two-sided quotes.
  * DECIDED AT THE CONSENSUS MAIN LINE ONLY: DraftKings' two-sided line, else the
    line most bettable books hang (lab.main_lines -- the same line the blind bettor
    of bar 9 takes). Per (game, player, market) the candidates are the over and the
    under at that line, each at the best bettable price there. This rule was fixed
    after reading the 2024-25 calibration diagnostics and BEFORE any units cell was
    read: one point off the main line a calibrated probability barely moves while
    the outcome moves 4-8 points (report section 2), so a map fitted on all lines
    prices line-shopping wrongly in the direction that favours the better price.
  * Decided once per game, at the prop snapshot, which must sit 45-70 minutes before
    tip; the 20 games whose snapshot falls outside are dropped.
  * Price floor -200; the best price among config.BEST_LINE_BOOKMAKERS at the main
    line. DraftKings alone and the five books the 2026-27 feed actually returns
    (DraftKings, FanDuel, Fanatics, BetParx, BetRivers) are graded beside it at the
    SAME main line, never chosen on.
  * CALIBRATION FIRST. Per market, logit P(over) = a + b * logit(p_model) (Platt),
    fitted on main-line (claimed, outcome) pairs. 2024-25 is mapped by 2023-24's
    pairs, 2025-26 by 2023-24 + 2024-25's. 2023-24 has no priced season before it:
    its map is refitted every Monday on 2023-24 main-line games played before that
    Monday, once a market has 300 such pairs; until then the 2022-23 walk-forward
    predictions at a proxy line (the weighted average rounded to the half point,
    players with predicted minutes >= 18) stand in. EV and every floor use the
    CALIBRATED probability. Isotonic is fitted beside it as a check, never used.
  * The grid: 13 markets (the 12 count markets + double-double that passed step 4;
    triple-double was closed there) x side (under / over / both) x calibrated-EV
    floor = 546 cells; every qualifying proposition is a bet (no cap). Per market
    the (side, floor) with the most units on 2023-24 + 2024-25 among cells where both
    seasons have >= 30 bets and are positive. 2025-26 chooses nothing.
  * A market enters the card only if its cell passes bars 5-10 on its own three
    seasons and 2025-26 alone is positive. Bar 11 (closing value) cannot be measured:
    one prop snapshot a game.

    python -m scripts.nba_prop_projection_lab base      # scored propositions, window, main line, rule keys
    python -m scripts.nba_prop_projection_lab calib     # the maps, before / after, the diagnostics
    python -m scripts.nba_prop_projection_lab grid      # every cell
    python -m scripts.nba_prop_projection_lab judge     # chosen cells against bars 4-10
    python -m scripts.nba_prop_projection_lab card      # the pooled card and its checks
    python -m scripts.nba_prop_projection_lab ref       # one under a game, for reference
    python -m scripts.nba_prop_projection_lab report    # proj/research.md

No Odds API call, no database read or write.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import models.nba_props as nb  # noqa: E402
import scripts.nba_prop_model_lab as lab  # noqa: E402

TEMP = Path("C:/Users/micha/AppData/Local/Temp/nba_rebuild")
SRC = TEMP / "verify_model" / "work"          # the worker re-fit: read only
OUT = TEMP / "proj"
WORK = OUT / "work"
RULE = TEMP / "results" / "props_market_bets_sharp_ALL_under_prop_0.00.parquet"
VERIFIER_CARD = TEMP / "verify_model" / "bets" / "card_worker_game_best.parquet"
CACHE = Path("C:/Users/micha/Documents/bm-nba/data/local/nba")
VARIANT = "wk"
LEAD_MIN = (45.0, 70.0)
SEASONS = (2024, 2025, 2026)
CHOOSE = (2024, 2025)
CONFIRM = 2026
FLOORS = (0.00, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.12, 0.15, 0.20)
SIDES = {"under": ("under",), "over": ("over",), "both": ("over", "under")}
BOOK_SETS = {"best": None, "dk": ("draftkings",),
             "arriving5": ("draftkings", "fanduel", "fanatics", "betparx", "betrivers")}
PROXY_MIN_HAT = 18.0
MIN_PAIRS = 300
N_BOOT = 4000
N_PLACEBO_MARKET = 20
N_PLACEBO_CARD = 100
KEY = ["game_id", "player_id", "market"]

# the lab's read-side functions read this folder; nothing here calls a lab stage (they write)
lab.WORK = SRC
lab.RESULTS = OUT


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def markets() -> tuple[str, ...]:
    d = json.loads((SRC / f"gate_decide_{VARIANT}.json").read_text(encoding="utf-8"))
    return tuple(m for m, v in d.items() if v["pass"])


def tips() -> pd.Series:
    g = pd.read_parquet(CACHE / "nba_games.parquet", columns=["game_id", "commence_time"]).set_index("game_id")
    return nb._utc(g.commence_time)


def rule_keys() -> pd.DataFrame:
    t = pd.read_parquet(RULE, columns=KEY)
    return t.assign(player_id=t.player_id.astype(str)).drop_duplicates()


def main_line_table() -> pd.DataFrame:
    """The consensus main line per (game, player, market), from the eight bettable books."""
    q = lab.load_quotes()
    q = q[q.usable & ~q.status.isin(["Out", "Doubtful"])]
    L = lab.main_lines(q)
    L["player_id"] = L.player_id.astype(str)
    return L


def week_of(d) -> pd.Series:
    d = pd.to_datetime(pd.Series(d)).reset_index(drop=True).astype("datetime64[ns]")
    return (d - pd.to_timedelta(d.dt.weekday, unit="D")).dt.normalize()


# ── base: every bettable proposition, the window, the main line, the rule's keys ──

KEEP = ["game_id", "game_date", "season", "player_id", "player_name", "team", "market", "side", "line", "book",
        "price", "p_over", "mu", "alpha", "actual", "played", "result", "risk", "units", "half", "status",
        "ev_pin", "pin_fair", "model_prob", "ev"]


def stage_base() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    mks, tip, taken = markets(), tips(), rule_keys()
    tk = set(zip(taken.game_id, taken.player_id, taken.market))
    L = main_line_table().rename(columns={"line": "main_line"})
    snap = pd.read_parquet(SRC / "quotes.parquet", columns=["game_id", "snapshot_at"]).drop_duplicates("game_id")
    lead = (snap.game_id.map(tip) - nb._utc(snap.snapshot_at)).dt.total_seconds() / 60
    lead = pd.Series(lead.values, index=snap.game_id.values)
    notes = {"markets": mks, "rule_keys": len(tk), "window_lead_minutes": list(LEAD_MIN)}
    for name, bs in BOOK_SETS.items():
        P = lab.scored_propositions(VARIANT, dk_only=(name == "dk"), book_set=bs if name == "arriving5" else None)
        n0 = len(P)
        P = P[P.market.isin(mks)][KEEP].copy()
        P["player_id"] = P.player_id.astype(str)
        P["lead_min"] = P.game_id.map(lead)
        inwin = P.lead_min.between(*LEAD_MIN)
        P["rule_key"] = [k in tk for k in zip(P.game_id, P.player_id, P.market)]
        P = P.merge(L, on=KEY, how="left")
        P["is_main"] = P.line == P.main_line
        notes[name] = {"rows_all_markets": n0, "rows_13_markets": len(P),
                       "games": int(P.game_id.nunique()),
                       "games_outside_window": int(P[~inwin].game_id.nunique()),
                       "rows_outside_window": int((~inwin).sum()),
                       "rows_on_rule_keys": int(P[inwin].rule_key.sum()),
                       "rule_keys_found": int(P[inwin & P.rule_key].drop_duplicates(KEY).shape[0]),
                       "keys": int(P[inwin].drop_duplicates(KEY).shape[0]),
                       "keys_with_main_line_row": int(P[inwin & P.is_main].drop_duplicates(KEY).shape[0])}
        P = P[inwin].rename(columns={"model_prob": "prob_raw", "ev": "ev_raw"})
        P.to_parquet(WORK / f"P_{name}.parquet")
        log(f"base {name}: {notes[name]}")
    (WORK / "base_notes.json").write_text(json.dumps(notes, indent=1, default=str), encoding="utf-8")


def load(name: str) -> pd.DataFrame:
    p = WORK / f"P_{name}_cal.parquet"
    return pd.read_parquet(p if p.exists() else WORK / f"P_{name}.parquet")


# ── calibration ────────────────────────────────────────────────────────────────

def pairs_real(P: pd.DataFrame) -> pd.DataFrame:
    """One pair per distinct priced (game, player, market, line) the player played: model P(over), outcome."""
    u = P.drop_duplicates(["game_id", "player_id", "market", "line"])
    u = u[u.played & u.actual.notna()]
    return pd.DataFrame({"season": u.season.values, "market": u.market.values, "p": u.p_over.values,
                         "y": (u.actual > u.line).astype(float).values,
                         "game_date": pd.to_datetime(u.game_date.values), "game_id": u.game_id.values,
                         "player_id": u.player_id.values, "line": u.line.values})


def pairs_proxy_2023(mks: tuple) -> pd.DataFrame:
    """2022-23, predicted by the fold fitted on 2019-2022, at a proxy line (the weighted average rounded to
    the half point) over the players a book would price. The width is alphas[(method, market, 2024)],
    itself fitted on these 2022-23 predictions -- nothing from 2023-24 enters."""
    pred = pd.read_parquet(SRC / f"pred_{VARIANT}_2023.parquet")
    pred = pred[pred.played & ~pred.status.isin(["Out", "Doubtful"]) & (pred.min_hat >= PROXY_MIN_HAT)]
    decide = json.loads((SRC / f"gate_decide_{VARIANT}.json").read_text(encoding="utf-8"))
    alphas = lab.load_alphas(VARIANT)
    parts = []
    for mk in mks:
        spec, d = nb.BY_MARKET[mk], decide[mk]
        y = nb.settle_value(spec, pred).values
        if spec.kind == "count":
            mu = lab.market_mu(pred, spec, d["method"])
            ew = sum(pred[f"ew_{s}"].values for s in spec.parts)
            line = np.floor(ew) + 0.5
            a = alphas[(d["method"], mk, 2024)] if d["dist"] == "nb" else 0.0
            p = nb.p_over(mu, line, a)
            yy = (y > line).astype(float)
        else:
            p = pred[f"pb_{mk}"].values
            yy = y
        ok = np.isfinite(p) & np.isfinite(yy)
        parts.append(pd.DataFrame({"season": 2023, "market": mk, "p": p[ok], "y": yy[ok],
                                   "game_date": pd.to_datetime(pred.game_date.values[ok])}))
    return pd.concat(parts, ignore_index=True)


def _ll(p, y) -> float:
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _iso_fit(p, y):
    from sklearn.isotonic import IsotonicRegression
    return IsotonicRegression(y_min=1e-4, y_max=1 - 1e-4, out_of_bounds="clip").fit(p, y)


def cal_ab(P: pd.DataFrame, M: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """The (a, b) every row is calibrated with: 2024-25 / 2025-26 by season, 2023-24 by the week's map."""
    a, b = np.full(len(P), np.nan), np.full(len(P), np.nan)
    season = P.season.values
    for S in (2025, 2026):
        ms = M[(M.season == S)].set_index("market")
        sel = season == S
        a[sel] = P.market[sel].map(ms.a).values
        b[sel] = P.market[sel].map(ms.b).values
    sel = season == 2024
    if sel.any():
        m24 = M[M.season == 2024].set_index(["week", "market"])
        idx = pd.MultiIndex.from_arrays([week_of(P.game_date.values[sel]).values, P.market.values[sel]])
        a[sel] = m24.a.reindex(idx).values
        b[sel] = m24.b.reindex(idx).values
    return a, b


def _sig(z):
    return 1 / (1 + np.exp(-z))


def _fit_logit(X: list, y) -> np.ndarray:
    X = np.column_stack([np.ones(len(y))] + list(X))
    w = np.zeros(X.shape[1])
    for _ in range(60):
        q = _sig(X @ w)
        g = X.T @ (y - q)
        H = (X * (q * (1 - q))[:, None]).T @ X
        step = np.linalg.solve(H + 1e-9 * np.eye(len(w)), g)
        w += step
        if np.abs(step).max() < 1e-10:
            break
    return w


def _pred_logit(w, X: list) -> np.ndarray:
    return _sig(np.column_stack([np.ones(len(X[0]))] + list(X)) @ w)


def market_novig() -> pd.DataFrame:
    """The bettable books' mean proportional no-vig P(over) at each (game, player, market, line)."""
    q = lab.load_quotes()
    q = q[q.two_sided & q.bookmaker.isin(nb.books())]
    io, iu = nb.implied(q.over_price), nb.implied(q.under_price)
    q = q.assign(fo=io / (io + iu), player_id=q.player_id.astype(str))
    return q.groupby(["game_id", "player_id", "market", "line"]).fo.mean().rename("mkt_over").reset_index()


def stage_calib() -> None:
    mks = markets()
    PB = pd.read_parquet(WORK / "P_best.parquet")
    main = pairs_real(PB[PB.is_main])
    proxy = pairs_proxy_2023(mks)
    proxy_map = nb.fit_calibration(proxy, season=2024)
    rows = []
    m24 = main[main.season == 2024]
    weeks = sorted(week_of(PB[PB.season == 2024].game_date.unique()).unique())
    for w in weeks:
        mp = nb.fit_calibration_before(m24, cutoff=w, min_pairs=MIN_PAIRS)
        n_by = m24[m24.game_date < w].groupby("market").size()
        for mk in mks:
            src = "in_season" if mk in mp else "proxy_2022_23"
            ab = mp.get(mk, proxy_map[mk])
            rows.append({"season": 2024, "week": pd.Timestamp(w), "market": mk, "a": ab[0], "b": ab[1],
                         "source": src, "n_pairs": int(n_by.get(mk, 0))})
    for S in (2025, 2026):
        mp = nb.fit_calibration(main, season=S)
        for mk in mks:
            rows.append({"season": S, "week": pd.NaT, "market": mk, "a": mp[mk][0], "b": mp[mk][1],
                         "source": "season", "n_pairs": int(((main.season < S) & (main.market == mk)).sum())})
    M = pd.DataFrame(rows)
    M["week"] = pd.to_datetime(M.week).astype("datetime64[ns]")
    M.to_parquet(WORK / "calib_maps.parquet")
    a, b = cal_ab(main, M)
    assert np.isfinite(a).all() and np.isfinite(b).all(), "a main-line pair has no calibration map"
    main["p_cal"] = _sig(a + b * nb._logit(main.p.values))
    main.to_parquet(WORK / "calib_pairs_main.parquet")
    # (a) before / after on every main-line pair, out of sample; isotonic beside it (2025, 2026)
    tab = []
    for S in SEASONS:
        for mk in mks:
            t = main[(main.season == S) & (main.market == mk)]
            if t.empty:
                continue
            y = t.y.values
            r = {"season": S, "market": mk, "n": len(t), "claimed_raw": t.p.mean(), "claimed_cal": t.p_cal.mean(),
                 "won": y.mean(), "brier_raw": float(np.mean((t.p - y) ** 2)),
                 "brier_cal": float(np.mean((t.p_cal - y) ** 2)), "ll_raw": _ll(t.p.values, y),
                 "ll_cal": _ll(t.p_cal.values, y)}
            if S in (2025, 2026):
                pr = main[(main.season < S) & (main.market == mk)]
                r["ll_iso"] = _ll(_iso_fit(pr.p.values, pr.y.values).predict(t.p.values), y)
            tab.append(r)
    pd.DataFrame(tab).to_parquet(WORK / "calib_table.parquet")
    # (b) where 2023-24 ran on the proxy
    w24 = M[M.season == 2024]
    srcs = w24.pivot_table(index="week", columns="market", values="source", aggfunc="first")
    on_proxy = {mk: [str(w.date()) for w in srcs.index[srcs[mk] == "proxy_2022_23"]] for mk in mks}
    m24p = main[main.season == 2024].copy()
    m24p["wk"] = week_of(m24p.game_date.values).values
    prox_keys = sum(int(m24p[(m24p.market == mk) & m24p.wk.isin(pd.to_datetime(on_proxy[mk]))].shape[0])
                    for mk in mks)
    proxy_note = {"weeks_on_proxy_by_market": on_proxy, "main_line_pairs_2024_on_proxy": prox_keys,
                  "main_line_pairs_2024": int(len(m24p)),
                  "proxy_map": {m: list(v) for m, v in proxy_map.items()},
                  "own_season_2024_map_insample": {m: list(nb.fit_platt(g.p.values, g.y.values))
                                                   for m, g in m24p.groupby("market")}}
    (WORK / "calib_proxy.json").write_text(json.dumps(proxy_note, indent=1, default=str), encoding="utf-8")
    # (c) why the card decides at the main line: a p-only map fitted on ALL 2023-24 lines, read on 2024-25
    alll = pairs_real(PB)
    allmap = {mk: nb.fit_platt(g.p.values, g.y.values) for mk, g in alll[alll.season == 2024].groupby("market")}
    D = PB[(PB.season == 2025) & ~PB.rule_key].copy()
    pc = np.empty(len(D))
    for mk in mks:
        s = (D.market == mk).values
        pc[s] = nb.apply_calibration(D.p_over.values[s], allmap[mk])
    D["mp"] = np.where(D.side == "over", pc, 1 - pc)
    D["evc"] = nb.expected_value(D.mp, D.price)
    med = D.groupby(KEY).line.median().rename("mline")
    D = D.join(med, on=KEY)
    D["dist"] = pd.cut(D.line - D.mline, [-50, -2.01, -1.01, -0.01, 0.01, 1.01, 2.01, 50],
                       labels=["<=-2", "-2..-1", "-1..0", "median", "0..+1", "+1..+2", ">=+2"])
    s = D[D.result.isin(["W", "L"])].assign(won=lambda x: (x.result == "W").astype(float))
    dist_tab = s.groupby(["side", "dist"], observed=True).agg(n=("won", "size"), claimed=("mp", "mean"),
                                                               won=("won", "mean")).reset_index()
    e = s[s.evc >= 0].assign(pb=lambda x: pd.cut(x.price, [-201, -150, -120, -100, 100, 150, 200, 400, 5000]))
    ev_tab = e.groupby("pb", observed=True).agg(n=("won", "size"), claimed=("mp", "mean"), won=("won", "mean"),
                                                u=("units", "sum"), r=("risk", "sum")).reset_index()
    ev_tab["roi%"] = 100 * ev_tab.u / ev_tab.r
    dist_tab.astype({"dist": str}).to_parquet(WORK / "diag_all_lines_by_distance.parquet")
    ev_tab.astype({"pb": str}).to_parquet(WORK / "diag_all_lines_ev_by_price.parquet")
    # (d) what the model adds to the price: bettable-book no-vig at the main line vs the model vs both
    mn = market_novig()
    mm = main[main.market != "player_double_double"].merge(mn, on=["game_id", "player_id", "market", "line"],
                                                           how="left")
    mm = mm[mm.mkt_over.notna()]
    add = []
    for S in (2025, 2026):
        for mk in mks:
            if mk == "player_double_double":
                continue
            tr, te = mm[(mm.season < S) & (mm.market == mk)], mm[(mm.season == S) & (mm.market == mk)]
            if len(te) < 200:
                add.append({"season": S, "market": mk, "n": len(te)})
                continue
            xm, xk = nb._logit(tr.p.values), nb._logit(tr.mkt_over.values)
            wA, wM, wC = _fit_logit([xm], tr.y.values), _fit_logit([xk], tr.y.values), _fit_logit([xm, xk], tr.y.values)
            tm, tk = nb._logit(te.p.values), nb._logit(te.mkt_over.values)
            y = te.y.values
            add.append({"season": S, "market": mk, "n": len(te), "ll_model_cal": _ll(_pred_logit(wA, [tm]), y),
                        "ll_market": _ll(_pred_logit(wM, [tk]), y), "ll_both": _ll(_pred_logit(wC, [tm, tk]), y),
                        "coef_model": wC[1], "coef_market": wC[2]})
    pd.DataFrame(add).to_parquet(WORK / "diag_model_vs_market.parquet")
    # apply to every book set
    counts = {}
    for name in BOOK_SETS:
        P = pd.read_parquet(WORK / f"P_{name}.parquet")
        a, b = cal_ab(P, M)
        pc = _sig(a + b * nb._logit(P.p_over.values))
        P["p_over_cal"] = pc
        P["model_prob"] = np.where(P.side == "over", pc, 1 - pc)
        P["ev"] = nb.expected_value(P.model_prob, P.price)
        assert P.loc[P.is_main, "ev"].notna().all(), "a main-line row was left uncalibrated"
        P.to_parquet(WORK / f"P_{name}_cal.parquet")
        m = P[P.is_main & ~P.rule_key]
        counts[name] = {str(S): {"main_line_rows": int((m.season == S).sum()),
                                 "ev_raw_ge_0": int(((m.season == S) & (m.ev_raw >= 0)).sum()),
                                 "ev_cal_ge_0": int(((m.season == S) & (m.ev >= 0)).sum())} for S in SEASONS}
        log(f"calibrated {name}: {counts[name]}")
    (WORK / "calib_counts.json").write_text(json.dumps(counts, indent=1), encoding="utf-8")
    print(pd.DataFrame(tab).round(4).to_string())
    print(pd.DataFrame(add).round(4).to_string())


def maps_table() -> pd.DataFrame:
    return pd.read_parquet(WORK / "calib_maps.parquet")


# ── selection and statistics ───────────────────────────────────────────────────

def sort_ev(C: pd.DataFrame, col: str = "ev") -> pd.DataFrame:
    return C.sort_values([col, "market", "player_id", "line"], ascending=[False, True, True, True], kind="mergesort")


def select(C_sorted: pd.DataFrame, floor: float, col: str = "ev") -> pd.DataFrame:
    """Every qualifying proposition: EV at or above the floor, its best-EV side, one per key."""
    return C_sorted[C_sorted[col] >= floor].drop_duplicates(KEY)


def boot(b: pd.DataFrame, n: int = N_BOOT) -> dict:
    """Whole-day bootstrap of ROI (4,000, seed 7 -- the lab's day_ci draws), with a one-sided p-value."""
    s = b[b.result.isin(["W", "L", "P"])]
    if len(s) < 30:
        return {"ci_lo": np.nan, "ci_hi": np.nan, "p_boot": np.nan, "p_norm": np.nan}
    d = s.groupby("game_date").agg(u=("units", "sum"), r=("risk", "sum"))
    u, r = d.u.values, d.r.values
    idx = np.random.default_rng(7).integers(0, len(d), size=(n, len(d)))
    roi = u[idx].sum(axis=1) / r[idx].sum(axis=1)
    lo, hi = np.percentile(roi, [5, 95])
    from scipy.stats import norm
    sd = roi.std(ddof=1)
    return {"ci_lo": round(100 * lo, 2), "ci_hi": round(100 * hi, 2),
            "p_boot": float((roi <= 0).mean()),
            "p_norm": float(norm.sf(roi.mean() / sd)) if sd > 0 else np.nan}


def stats(b: pd.DataFrame, ci: bool = True) -> dict:
    c = lab.cell_stats(b, with_ci=False)
    out = {k: c.get(k) for k in ("bets", "voids", "units", "roi", "u_per_season", "n_2024", "u_2024", "roi_2024",
                                 "n_2025", "u_2025", "roi_2025", "n_2026", "u_2026", "roi_2026", "n_choose",
                                 "u_choose", "roi_choose", "u_early", "u_late", "under_share", "claimed", "won")}
    if ci:
        out.update(boot(b))
    return out


def prices(b: pd.DataFrame) -> dict:
    s = b[b.result.isin(["W", "L", "P"])].price
    if s.empty:
        return {}
    q = np.percentile(s, [0, 5, 50, 95, 100])
    return {"min": int(q[0]), "p5": int(q[1]), "median": int(q[2]), "p95": int(q[3]), "max": int(q[4])}


def candidates(P: pd.DataFrame, mk: str | list, side: str) -> pd.DataFrame:
    mks = [mk] if isinstance(mk, str) else list(mk)
    return sort_ev(P[P.market.isin(mks) & P.side.isin(SIDES[side]) & P.is_main & ~P.rule_key])


# ── the grid ───────────────────────────────────────────────────────────────────

def stage_grid() -> None:
    P = load("best")
    rows = []
    for mk in markets():
        for side in SIDES:
            C = candidates(P, mk, side)
            for f in FLOORS:
                rows.append({"market": mk, "side": side, "floor": f, **stats(select(C, f))})
        log(f"grid {mk}: done")
    G = pd.DataFrame(rows)
    G.to_parquet(WORK / "grid.parquet")
    log(f"grid: {len(G)} cells")


def choose(G: pd.DataFrame) -> pd.DataFrame:
    """Per market: the (side, floor) with the most units on 2023-24 + 2024-25, among cells where both seasons
    have >= 30 bets and are positive. 2025-26 plays no part."""
    ok = G[(G.n_2024 >= 30) & (G.n_2025 >= 30) & (G.u_2024 > 0) & (G.u_2025 > 0)]
    return (ok.sort_values(["u_choose", "floor"], ascending=[False, True]).drop_duplicates("market")
            .reset_index(drop=True))


def neighbours(G: pd.DataFrame, mk: str, side: str, floor: float) -> pd.DataFrame:
    i = FLOORS.index(floor)
    nf = [FLOORS[k] for k in (i - 1, i + 1) if 0 <= k < len(FLOORS)]
    return G[(G.market == mk) & (G.side == side) & G.floor.isin(nf)]


# ── placebo, blinds ────────────────────────────────────────────────────────────

def placebo(P: pd.DataFrame, cells: dict, n: int, M: pd.DataFrame, seed: int = 7) -> list[dict]:
    """Each player's model mean over his main line (counts) or his probability (double-double) handed to
    another player priced in the same market that night; the line re-priced from the shuffled number,
    passed through the SAME calibration map, then each market's own side and floor."""
    rng = np.random.default_rng(seed)
    C = P[P.market.isin(list(cells)) & P.is_main & ~P.rule_key].copy()
    pl = (C.drop_duplicates(KEY)[["game_date", "market", "game_id", "player_id", "mu", "main_line"]]
          .sort_values(["game_date", "market"], kind="mergesort").reset_index(drop=True))
    cnt_pl = pl.market.map(lambda m: nb.BY_MARKET[m].kind == "count").values
    val = np.where(cnt_pl, pl.mu.values / pl.main_line.values, pl.mu.values)
    dcode = pl.game_date.rank(method="dense").values
    mcode = pl.market.astype("category").cat.codes.values
    pos = pd.Series(np.arange(len(pl)), index=pd.MultiIndex.from_frame(pl[KEY]))
    idx = pos.reindex(pd.MultiIndex.from_frame(C[KEY])).values
    cnt = C.market.map(lambda m: nb.BY_MARKET[m].kind == "count").values
    a, b = cal_ab(C, M)
    alpha = np.nan_to_num(C.alpha.values)
    dec = nb.decimal(C.price.values)
    over = C.side.values == "over"
    out = []
    for _ in range(n):
        order = np.lexsort((rng.random(len(pl)), mcode, dcode))
        v = val[order]
        mu_p = np.where(cnt_pl, v * pl.main_line.values, v)[idx]
        po = np.where(cnt, lab._p_over_vec(mu_p, C.line.values, alpha), mu_p)
        pc = _sig(a + b * nb._logit(po))
        mp = np.where(over, pc, 1 - pc)
        Y = C.assign(model_prob=mp, ev=mp * dec - 1)
        bets = [select(sort_ev(Y[(Y.market == mk) & Y.side.isin(SIDES[side])]), floor)
                for mk, (side, floor) in cells.items()]
        bb = pd.concat(bets)
        s = bb[bb.result.isin(["W", "L", "P"])]
        out.append({"roi": 100 * float(s.units.sum() / s.risk.sum()) if len(s) else np.nan,
                    "units": float(s.units.sum()), "bets": len(s)})
    return out


def blind(P: pd.DataFrame, mks: list, side: str, bets: pd.DataFrame) -> dict:
    """The lean, on the same rows: every key's main-line `side` at the best price (the model's own
    population); the same on the keys the model bets; and the one-per-key structure ordered by the highest
    price on offer and at random (mean of 10)."""
    U = P[P.market.isin(mks) & (P.side == side) & P.is_main & ~P.rule_key]
    out = {"main_line": stats(U.drop_duplicates(KEY), ci=False)}
    out["main_line_same_keys"] = stats(U.merge(bets[KEY].drop_duplicates(), on=KEY), ci=False)
    out["highest_price"] = stats(select(sort_ev(U.assign(ev=U.price)), -1e9), ci=False)
    rr = []
    for k in range(10):
        Cr = U.assign(ev=np.random.default_rng(k).random(len(U)))
        rr.append(stats(select(sort_ev(Cr), -1.0), ci=False)["roi"])
    out["random_mean_roi"] = round(float(np.mean(rr)), 2)
    return out


# ── judging the chosen cells ───────────────────────────────────────────────────

def bars(r: dict, nbr: pd.DataFrame, bl: dict | None, pl: list | None) -> dict:
    side_share = max(r["under_share"], 1 - r["under_share"])
    # a confirmation needs a graded season: bar 5's own threshold of 30 bets (turnovers: 49 priced in 2025-26)
    b = {"b4_2026_positive": bool(r["n_2026"] >= 30 and r["u_2026"] > 0),
         "b5_every_season_positive": all((r[f"u_{S}"] > 0) or (r[f"n_{S}"] < 30) for S in SEASONS),
         "b6_200_bets_ci_above_zero": bool(r["bets"] >= 200 and np.nan_to_num(r["ci_lo"], nan=-1) > 0),
         "b7_plateau": bool(len(nbr) > 0 and (nbr.units > 0).all()),
         "b8_both_halves": bool(r["u_early"] > 0 and r["u_late"] > 0)}
    if bl is not None:
        b["b9_beats_blind_side"] = bool(side_share <= 0.70 or (
            r["roi"] > bl["main_line"]["roi"] and r["roi"] > bl["highest_price"]["roi"]
            and r["roi"] > bl["random_mean_roi"]))
    if pl is not None:
        rois = [x["roi"] for x in pl]
        b["b10_placebo"] = bool(len(rois) and np.nanmax(rois) < r["roi"])
    return b


def missing_at(bets: pd.DataFrame, X: pd.DataFrame) -> int:
    """Bets (graded) whose main line the book set does not quote on the same side."""
    s = bets[bets.result.isin(["W", "L", "P"])]
    k = X[X.is_main][KEY + ["side"]].drop_duplicates()
    return int(len(s) - len(s.merge(k, on=KEY + ["side"])))


def stage_judge() -> None:
    G = pd.read_parquet(WORK / "grid.parquet")
    P, PD, PA = load("best"), load("dk"), load("arriving5")
    M = maps_table()
    ch = choose(G)
    recs = []
    for r in ch.to_dict("records"):
        mk, side, f = r["market"], r["side"], r["floor"]
        bets = select(candidates(P, mk, side), f)
        nbr = neighbours(G, mk, side, f)
        lean = "under" if r["under_share"] >= 0.5 else "over"
        bl = blind(P, [mk], lean, bets)
        pl = placebo(P, {mk: (side, f)}, N_PLACEBO_MARKET, M)
        bb = bars(r, nbr, bl, pl)
        rec = {**r, "neighbours": nbr[["floor", "bets", "units", "roi", "u_2024", "u_2025", "u_2026"]].to_dict(
            "records"), "blind_side": lean, "blind": bl,
               "placebo_mean": float(np.nanmean([x["roi"] for x in pl])),
               "placebo_max": float(np.nanmax([x["roi"] for x in pl])),
               "dk": stats(select(candidates(PD, mk, side), f), ci=False), "dk_missing": missing_at(bets, PD),
               "arriving5": stats(select(candidates(PA, mk, side), f), ci=False),
               "arriving5_missing": missing_at(bets, PA), "prices": prices(bets), **bb}
        rec["enters_card"] = all(bb.values())
        recs.append(rec)
        bets.to_parquet(OUT / f"bets_market_{mk}_{side}_ev{f:.2f}.parquet")
        log(f"judged {mk} {side} ev>={f:.2f}: {r['bets']} bets {r['roi']:+.2f}% "
            f"u {r['u_2024']:+.1f}/{r['u_2025']:+.1f}/{r['u_2026']:+.1f} ci {r['ci_lo']}..{r['ci_hi']} "
            f"placebo max {rec['placebo_max']:.2f} enters={rec['enters_card']}")
    J = pd.DataFrame(recs)
    J.to_pickle(WORK / "judge.pkl")
    none = sorted(set(markets()) - set(ch.market))
    (WORK / "judge_no_cell.json").write_text(json.dumps(none), encoding="utf-8")
    log(f"markets with no cell positive in both choosing seasons: {none}")


# ── the pooled card ────────────────────────────────────────────────────────────

def card_bets(P: pd.DataFrame, cells: dict, shift: int = 0) -> pd.DataFrame:
    out = []
    for mk, (side, f) in cells.items():
        i = min(max(FLOORS.index(f) + shift, 0), len(FLOORS) - 1)
        out.append(select(candidates(P, mk, side), FLOORS[i]))
    return pd.concat(out, ignore_index=True) if out else P.iloc[0:0]


def by(b: pd.DataFrame, col: str) -> pd.DataFrame:
    s = b[b.result.isin(["W", "L", "P"])]
    g = s.groupby(col, observed=True)
    t = pd.DataFrame({"bets": g.size(), "units": g.units.sum(), "risk": g.risk.sum(),
                      "claimed_cal": g.model_prob.mean(), "claimed_raw": g.prob_raw.mean(),
                      "won": g.result.apply(lambda x: (x == "W").mean()),
                      "implied": g.price.apply(lambda x: float(np.mean(nb.implied(x))))})
    t["roi%"] = 100 * t.units / t.risk
    return t.drop(columns="risk")


def bh_read(G: pd.DataFrame, cells: dict) -> dict:
    """Benjamini-Hochberg over EVERY cell searched (a cell without 30 graded bets counts as p = 1), one-sided
    p from the day bootstrap's normal reading."""
    from statsmodels.stats.multitest import multipletests
    p = G.p_norm.fillna(1.0).values
    out = {"cells_searched": len(G)}
    keep = G[["market", "side", "floor", "p_norm", "p_boot"]].copy()
    for q, tag in ((0.05, "q05"), (0.10, "q10")):
        keep[tag] = multipletests(p, alpha=q, method="fdr_bh")[0]
        out[f"survive_{tag}"] = int(keep[tag].sum())
    keep["bonferroni"] = keep.p_norm.fillna(1.0) < 0.05 / len(G)
    out["survive_bonferroni"] = int(keep.bonferroni.sum())
    mine = pd.DataFrame([{"market": m, "side": s_, "floor": f} for m, (s_, f) in cells.items()])
    out["card_cells"] = keep.merge(mine, on=["market", "side", "floor"]).to_dict("records") if len(mine) else []
    return out


def stage_card() -> None:
    J = pd.read_pickle(WORK / "judge.pkl")
    P, PD, PA = load("best"), load("dk"), load("arriving5")
    M = maps_table()
    G = pd.read_parquet(WORK / "grid.parquet")
    entered = J[J.enters_card]
    cells = {r.market: (r.side, float(r.floor)) for r in entered.itertuples()}
    res = {"cells": cells, "bh": bh_read(G, cells)}
    if not cells:
        (WORK / "card.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
        log("no market entered the card")
        return
    taken = rule_keys()
    b = card_bets(P, cells)
    assert nb.exclude_taken(b, taken).shape[0] == b.shape[0], "a card bet sits on the rule's propositions"
    b.to_parquet(OUT / "bets_card_best.parquet")
    res["best"] = {**stats(b), "prices": prices(b)}
    for name, X in (("dk", PD), ("arriving5", PA)):
        bx = card_bets(X, cells)
        assert nb.exclude_taken(bx, taken).shape[0] == bx.shape[0]
        bx.to_parquet(OUT / f"bets_card_{name}.parquet")
        res[name] = {**stats(bx), "prices": prices(bx), "card_bets_without_a_quote_here": missing_at(b, X)}
    res["neighbours"] = {f"every floor {s:+d} step": stats(card_bets(P, cells, s), ci=False) for s in (-1, 1)}
    pl = placebo(P, cells, N_PLACEBO_CARD, M)
    rois = np.array([x["roi"] for x in pl])
    res["placebo"] = {"n": len(pl), "mean_roi": float(np.nanmean(rois)), "p95_roi": float(np.nanpercentile(rois, 95)),
                      "max_roi": float(np.nanmax(rois)), "mean_units": float(np.mean([x["units"] for x in pl])),
                      "share_ge_real": float(np.mean(rois >= res["best"]["roi"]))}
    res["blind"] = {side: blind(P, [m for m, (s_, _) in cells.items() if s_ in (side, "both")], side, b)
                    for side in ("under", "over") if any(s_ in (side, "both") for s_, _ in cells.values())}
    res["by_market"] = by(b, "market").round(4).reset_index().to_dict("records")
    res["by_book"] = by(b, "book").round(4).reset_index().to_dict("records")
    res["by_side"] = by(b, "side").round(4).reset_index().to_dict("records")
    res["by_season"] = by(b, "season").round(4).reset_index().to_dict("records")
    x = b.assign(pband=pd.cut(b.price, [-201, -150, -120, -100, 100, 150, 200, 400, 5000]).astype(str))
    res["by_price"] = by(x, "pband").round(4).reset_index().to_dict("records")
    x = b.assign(cband=pd.cut(b.model_prob, [0, .45, .5, .525, .55, .575, .6, .65, 1]).astype(str))
    res["by_calibrated_prob"] = by(x, "cband").round(4).reset_index().to_dict("records")
    res["by_status"] = by(b, "status").round(4).reset_index().to_dict("records")
    g = b[b.result.isin(["W", "L", "P"])]
    res["bets_a_night"] = g.groupby("game_date").size().describe().round(1).to_dict()
    res["bets_a_game"] = g.groupby("game_id").size().describe().round(1).to_dict()
    pin = g[g.result.isin(["W", "L"]) & g.ev_pin.notna()]
    res["pinnacle_same_line"] = {"covered": len(pin),
                                 "median_ev_vs_pinnacle": float(pin.ev_pin.median()) if len(pin) else None,
                                 "share_positive": float((pin.ev_pin > 0).mean()) if len(pin) else None}
    # before / after on the band that gets bet: the same cells chosen by the RAW EV at the same floors
    raw = []
    for mk, (side, f) in cells.items():
        raw.append(select(sort_ev(P[P.market.eq(mk) & P.side.isin(SIDES[side]) & P.is_main & ~P.rule_key],
                                  "ev_raw"), f, "ev_raw"))
    raw = pd.concat(raw)
    wl, wr = g[g.result.isin(["W", "L"])], raw[raw.result.isin(["W", "L"])]
    res["band"] = {"calibrated_card": {"bets": len(wl), "claimed_cal": float(wl.model_prob.mean()),
                                       "claimed_raw": float(wl.prob_raw.mean()),
                                       "won": float((wl.result == "W").mean()),
                                       "implied": float(np.mean(nb.implied(wl.price)))},
                   "same_cells_on_raw_ev": {"bets": len(wr), "claimed_raw": float(wr.prob_raw.mean()),
                                            "won": float((wr.result == "W").mean()),
                                            **{k: v for k, v in stats(raw, ci=False).items()
                                               if k in ("units", "roi", "u_2024", "u_2025", "u_2026")}}}
    (WORK / "card.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    log(json.dumps({k: res[k] for k in ("cells", "best", "dk", "arriving5", "placebo")}, default=str)[:4000])


# ── robustness of the card: where its units come from ──────────────────────────

def scored_set(book_set: tuple) -> pd.DataFrame:
    """Propositions priced at another book set, run through the same window, main line, rule exclusion and
    calibration maps as the card (nothing re-chosen)."""
    tip, taken = tips(), rule_keys()
    tk = set(zip(taken.game_id, taken.player_id, taken.market))
    L = main_line_table().rename(columns={"line": "main_line"})
    P = lab.scored_propositions(VARIANT, book_set=book_set)
    P = P[P.market.isin(markets())][KEEP].copy()
    P["player_id"] = P.player_id.astype(str)
    snap = pd.read_parquet(SRC / "quotes.parquet", columns=["game_id", "snapshot_at"]).drop_duplicates("game_id")
    lead = pd.Series((snap.game_id.map(tip) - nb._utc(snap.snapshot_at)).dt.total_seconds().values / 60,
                     index=snap.game_id.values)
    P = P[P.game_id.map(lead).between(*LEAD_MIN)]
    P["rule_key"] = [k in tk for k in zip(P.game_id, P.player_id, P.market)]
    P = P.merge(L, on=KEY, how="left")
    P["is_main"] = P.line == P.main_line
    P = P.rename(columns={"model_prob": "prob_raw", "ev": "ev_raw"})
    a, b = cal_ab(P, maps_table())
    pc = _sig(a + b * nb._logit(P.p_over.values))
    P["model_prob"] = np.where(P.side == "over", pc, 1 - pc)
    P["ev"] = nb.expected_value(P.model_prob, P.price)
    return P


def stage_robust() -> None:
    J = pd.read_pickle(WORK / "judge.pkl")
    cells = {r.market: (r.side, float(r.floor)) for r in J[J.enters_card].itertuples()}
    b = pd.read_parquet(OUT / "bets_card_best.parquet")
    g = b[b.result.isin(["W", "L", "P"])].copy()
    res = {}
    # Pinnacle at the bet's own line (a stand-in for closing value, not bar 11)
    res["pinnacle_quotes_the_line"] = stats(g[g.ev_pin.notna()], ci=True)
    res["pinnacle_silent"] = stats(g[g.ev_pin.isna()], ci=True)
    res["pinnacle_agrees_ev_pos"] = stats(g[g.ev_pin > 0], ci=False)
    res["pinnacle_disagrees"] = stats(g[g.ev_pin <= 0], ci=False)
    # every bettable price at the bet's line and side: the second-best and the median book
    q = lab.load_quotes()
    q = q[q.usable & ~q.status.isin(["Out", "Doubtful"]) & q.bookmaker.isin(nb.books())]
    q = q[(q.market.map(lambda m: nb.BY_MARKET[m].kind) != "count") | q.two_sided]
    q["player_id"] = q.player_id.astype(str)
    parts = []
    for side, col in (("over", "over_price"), ("under", "under_price")):
        s = q[q[col].notna()][KEY + ["line", "bookmaker", col]].rename(columns={col: "px"})
        parts.append(s.assign(side=side))
    Q = pd.concat(parts)
    Q = Q[Q.px >= lab.PRICE_FLOOR]
    k = g[KEY + ["line", "side"]].drop_duplicates()
    Q = Q.merge(k, on=KEY + ["line", "side"])
    Q = Q.sort_values("px", ascending=False)
    agg = Q.groupby(KEY + ["line", "side"]).px.agg(n_books="size", second=lambda s: s.iloc[1] if len(s) > 1 else np.nan,
                                                   median="median").reset_index()
    g = g.merge(agg, on=KEY + ["line", "side"], how="left")
    res["by_books_at_line"] = by(g.assign(nb_=g.n_books.clip(upper=5).astype("Int64").astype(str)), "nb_").round(
        4).reset_index().to_dict("records")

    def regrade(x: pd.DataFrame, col: str) -> pd.DataFrame:
        x = x[x[col].notna()].copy()
        risk, win = nb.stake(x[col].values)
        w = x.result.values == "W"
        x["price"] = x[col]
        x["risk"] = np.where(x.result.isin(["W", "L"]), risk, 0.0)
        x["units"] = np.where(w, win, np.where(x.result.values == "L", -risk, 0.0))
        return x

    two = g[g.n_books >= 2]
    res["two_or_more_books_at_line_best_price"] = stats(two, ci=True)
    res["two_or_more_books_at_line_second_best_price"] = stats(regrade(two, "second"), ci=True)
    res["median_book_price"] = stats(regrade(g, "median"), ci=True)
    # other book sets, same maps, same cells (nothing re-chosen)
    for tag, bs in (("config_live5_dk_fd_mgm_wh_fanatics", ("draftkings", "fanduel", "betmgm", "williamhill_us",
                                                             "fanatics")),
                    ("without_hardrock", tuple(x for x in nb.books() if x != "hardrockbet"))):
        X = scored_set(bs)
        bx = card_bets(X, cells)
        res[tag] = {**stats(bx), "prices": prices(bx)}
        res[tag + "_by_market"] = by(bx, "market").round(4).reset_index().to_dict("records")
        log(f"{tag}: {res[tag]['bets']} bets {res[tag]['roi']}%")
    for name in ("dk", "arriving5"):
        bx = pd.read_parquet(OUT / f"bets_card_{name}.parquet")
        res[f"{name}_by_market"] = by(bx, "market").round(4).reset_index().to_dict("records")
    # does the model add anything over the price? per market and side: the card's bets against a blind bet on
    # the same side at the main line, reweighted to the card's own mix of price bands
    P = load("best")
    bands = [-201, -150, -120, -100, 100, 150, 200, 400, 5000]
    pm = []
    for mk, (side_, f) in cells.items():
        for sd in SIDES[side_]:
            cb = g[(g.market == mk) & (g.side == sd)]
            if len(cb) < 30:
                continue
            U = P[(P.market == mk) & (P.side == sd) & P.is_main & ~P.rule_key].drop_duplicates(KEY)
            U = U[U.result.isin(["W", "L", "P"])]
            cbb, ubb = pd.cut(cb.price, bands), pd.cut(U.price, bands)
            cr = cb.groupby(cbb, observed=True).risk.sum()
            ur = U.groupby(ubb, observed=True).agg(u=("units", "sum"), r=("risk", "sum"))
            roi_b = (ur.u / ur.r).reindex(cr.index)
            matched = float((cr * roi_b).sum() / cr[roi_b.notna()].sum()) if roi_b.notna().any() else np.nan
            ev3 = pd.qcut(cb.ev, 3, labels=["low", "mid", "high"])
            t3 = cb.groupby(ev3, observed=True).agg(u=("units", "sum"), r=("risk", "sum"))
            pm.append({"market": mk, "side": sd, "bets": len(cb),
                       "card_roi": 100 * float(cb.units.sum() / cb.risk.sum()),
                       "blind_roi": 100 * float(U.units.sum() / U.risk.sum()),
                       "blind_roi_price_matched": 100 * matched,
                       **{f"card_roi_ev_{k}": 100 * float(t3.u[k] / t3.r[k]) for k in t3.index}})
    res["model_vs_price"] = pm
    # the verifier's flagged roster defect: a player who played but was on no pre-game roster (back after 30+
    # days, on no injury list) enters his teammates' returning minutes. Card bets in those team-games, removed.
    ros = pd.read_parquet(SRC / "asof_roster.parquet", columns=["game_id", "team", "player_id"])
    lg = pd.read_parquet(CACHE / "nba_player_game_log.parquet", columns=["game_id", "team", "player_id"])
    lg["player_id"] = lg.player_id.astype(str)
    ros["player_id"] = ros.player_id.astype(str)
    late = lg.merge(ros.assign(on=1), on=["game_id", "team", "player_id"], how="left")
    late = late[late.on.isna() & late.game_id.isin(set(b.game_id))]
    hit = set(zip(late.game_id, late.team))
    flag = np.array([k in hit for k in zip(b.game_id, b.team)])
    res["roster_defect"] = {"team_games_touched": len(hit), "card_bets_touched": int(flag.sum()),
                            "card_without_them": stats(b[~flag], ci=True),
                            "touched_bets_only": stats(b[flag], ci=False)}
    (WORK / "robust.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    log(json.dumps({k: (v if not isinstance(v, dict) else {kk: v.get(kk) for kk in ("bets", "roi", "u_2024",
                                                                                  "u_2025", "u_2026", "ci_lo")})
                    for k, v in res.items() if not k.endswith("by_market") and k != "by_books_at_line"},
                   default=str))


# ── reference: one under a game ─────────────────────────────────────────────────

def one_a_game(P: pd.DataFrame, mks: tuple, exclude: bool, col: str = "ev") -> pd.DataFrame:
    C = P[P.market.isin(mks) & (P.side == "under") & P.is_main]
    if exclude:
        C = C[~C.rule_key]
    C = sort_ev(C, col)
    return C[C[col] >= 0.0].drop_duplicates(KEY).drop_duplicates("game_id")


def stage_ref() -> None:
    P, PD = load("best"), load("dk")
    mks = markets()
    res = {}
    for tag, ex, col in (("calibrated_excluding_rule", True, "ev"), ("calibrated_including_rule", False, "ev"),
                         ("uncalibrated_excluding_rule", True, "ev_raw")):
        b = one_a_game(P, mks, ex, col)
        res[tag] = {**stats(b), "prices": prices(b), "dk": stats(one_a_game(PD, mks, ex, col), ci=False)}
        b.to_parquet(OUT / f"bets_ref_one_under_a_game_{tag}.parquet")
    # the verifier's one-a-game bets (all lines, uncalibrated): the "before" band
    v = pd.read_parquet(VERIFIER_CARD)
    v = v[v.result.isin(["W", "L"])]
    res["verifier_one_a_game_band"] = {"bets": len(v), "claimed_raw": float(v.model_prob.mean()),
                                       "won": float((v.result == "W").mean()),
                                       "implied": float(np.mean(nb.implied(v.price)))}
    (WORK / "ref.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    log(json.dumps(res, default=str)[:3000])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["base", "calib", "grid", "judge", "card", "robust", "ref", "report"])
    a = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    if a.stage == "report":
        stage_report()
        return
    {"base": stage_base, "calib": stage_calib, "grid": stage_grid, "judge": stage_judge, "card": stage_card,
     "robust": stage_robust, "ref": stage_ref}[a.stage]()


# ── the report ─────────────────────────────────────────────────────────────────

LABEL = {"player_points": "Points", "player_rebounds": "Rebounds", "player_assists": "Assists",
         "player_threes": "Threes", "player_points_rebounds_assists": "Pts+Reb+Ast",
         "player_points_rebounds": "Pts+Reb", "player_points_assists": "Pts+Ast",
         "player_rebounds_assists": "Reb+Ast", "player_blocks": "Blocks", "player_steals": "Steals",
         "player_blocks_steals": "Blocks+Steals", "player_turnovers": "Turnovers",
         "player_double_double": "Double-double"}


def _md(df: pd.DataFrame, fmt: str = "{:.2f}") -> str:
    def f(v):
        if isinstance(v, (float, np.floating)):
            return "" if np.isnan(v) else fmt.format(v)
        return str(v)
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(f(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(out)


def _u(x) -> str:
    return f"{x:+,.1f}"


def _row(name: str, s: dict) -> dict:
    return {"": name, "bets": f"{s['bets']:,}", "units": _u(s["units"]), "ROI %": f"{s['roi']:+.2f}",
            "units a season": _u(s["units"] / 3),
            "2023-24 / 2024-25 / 2025-26 units": f"{_u(s['u_2024'])} / {_u(s['u_2025'])} / {_u(s['u_2026'])}",
            "ROI by season %": f"{s['roi_2024']:+.2f} / {s['roi_2025']:+.2f} / {s['roi_2026']:+.2f}",
            "90% CI %": (f"{s['ci_lo']:+.2f}..{s['ci_hi']:+.2f}" if s.get("ci_lo") is not None
                         and not pd.isna(s.get("ci_lo")) else "")}


def stage_report() -> None:
    base = json.loads((WORK / "base_notes.json").read_text(encoding="utf-8"))
    cnt = json.loads((WORK / "calib_counts.json").read_text(encoding="utf-8"))
    prox = json.loads((WORK / "calib_proxy.json").read_text(encoding="utf-8"))
    card = json.loads((WORK / "card.json").read_text(encoding="utf-8"))
    rob = json.loads((WORK / "robust.json").read_text(encoding="utf-8"))
    ref = json.loads((WORK / "ref.json").read_text(encoding="utf-8"))
    J = pd.read_pickle(WORK / "judge.pkl")
    G = pd.read_parquet(WORK / "grid.parquet")
    CT = pd.read_parquet(WORK / "calib_table.parquet")
    M = maps_table()
    DT = pd.read_parquet(WORK / "diag_all_lines_by_distance.parquet")
    DE = pd.read_parquet(WORK / "diag_all_lines_ev_by_price.parquet")
    DM = pd.read_parquet(WORK / "diag_model_vs_market.parquet")
    none_cell = json.loads((WORK / "judge_no_cell.json").read_text(encoding="utf-8"))
    cells = card["cells"]
    best, dk, a5 = card["best"], card["dk"], card["arriving5"]
    c5 = rob["config_live5_dk_fd_mgm_wh_fanatics"]
    L = []
    w = L.append
    w("# NBA prop projection model: calibrated, every qualifying bet, graded for units\n")
    w("Asked for by mike on 2026-10-16: build the projection model, maximise units won, no per-game or nightly "
      "cap, one bet per proposition across every NBA prop model. Code: `scripts/nba_prop_projection_lab.py` "
      "(stages base, calib, grid, judge, card, robust, ref, report) and the calibration pieces in "
      "`models/nba_props.py`. Inputs: the verifier's worker-only re-fit (`verify_model/work/`), read only. "
      "No odds-feed call, no database read or write.\n")

    # ── 0. the answer
    w("## 0. The answer\n")
    mk_list = ", ".join(f"{LABEL[m]} {s if s != 'both' else 'both sides'} (calibrated EV >= {f:.2f})"
                        for m, (s, f) in cells.items())
    w(f"**The card: {mk_list}.** Every qualifying proposition at the consensus main line, the best of the "
      f"eight bettable books, price floor -200, never a proposition the shipped Pinnacle rule bets.\n")
    rows = [_row("eight books (the spec)", best), _row("DraftKings alone", dk),
            _row("the five books the 2026-27 feed returns", a5),
            _row("the five books config collects (DK, FD, MGM, Caesars, Fanatics)", c5)]
    w(_md(pd.DataFrame(rows)) + "\n")
    w(f"- **{_u(best['units'] / 3)} units a season at the eight books, {best['roi']:+.2f}% on "
      f"{best['bets']:,} bets** (about {card['bets_a_night']['mean']:.0f} bets a night, "
      f"{card['bets_a_game']['mean']:.0f} a game). 2025-26, never used to choose anything: "
      f"{_u(best['u_2026'])} units, {best['roi_2026']:+.2f}%.")
    w(f"- Every bar that can be measured passes for the pooled card and for each of its {len(cells)} markets at "
      f"the eight books (section 7). Bar 11 (closing value) is **unmeasurable**: one prop snapshot a game. So "
      f"`passes_all_bars` is false, by that bar alone.")
    w(f"- **Most of the edge is the best price, not only the model.** Graded at the second-best price at the same "
      f"line (bets with two or more books there), the card falls from "
      f"{rob['two_or_more_books_at_line_best_price']['roi']:+.2f}% to "
      f"{rob['two_or_more_books_at_line_second_best_price']['roi']:+.2f}%; 2025-26 from "
      f"{_u(rob['two_or_more_books_at_line_best_price']['u_2026'])} to "
      f"{_u(rob['two_or_more_books_at_line_second_best_price']['u_2026'])} units. At DraftKings alone the "
      f"card is {dk['roi']:+.2f}%, with 2025-26 at {dk['roi_2026']:+.2f}%.")
    w(f"- **Which books the worker sees decides the units.** In 2025-26 the card makes {_u(best['u_2026'])} units "
      f"at the eight books, {_u(a5['u_2026'])} at the five books the 2026-27 feed returns (the verifier's "
      f"measurement: DraftKings, FanDuel, Fanatics, BetParx, BetRivers), {_u(c5['u_2026'])} at the five books "
      f"`config.LIVE_FEED_BOOKMAKERS` lists (DraftKings, FanDuel, BetMGM, Caesars, Fanatics) and "
      f"{_u(dk['u_2026'])} at DraftKings alone ({dk['roi_2026']:+.2f}%). The backtest graded the eight books in "
      f"`config.BEST_LINE_BOOKMAKERS`; the live prop fetch would have to collect all eight for the worker to "
      f"see what was graded.")
    asr = next(r for r in J.to_dict("records") if r["market"] == "player_assists") if "player_assists" in cells \
        else None
    if asr is not None:
        w(f"- **Assists overs clear only by shopping eight books**: {asr['roi']:+.2f}% there, "
          f"{asr['dk']['roi']:+.2f}% at DraftKings alone and {asr['arriving5']['roi']:+.2f}% at the five books "
          f"the feed returns. They are in the card because the pre-registered process put them there.")
    w(f"- The calibrated probability is honest at the population level and still overclaims on the bets it "
      f"selects: claimed {card['band']['calibrated_card']['claimed_cal']:.3f}, won "
      f"{card['band']['calibrated_card']['won']:.3f}, price implied (vig in) "
      f"{card['band']['calibrated_card']['implied']:.3f}. Before calibration the one-a-game card claimed "
      f"{ref['verifier_one_a_game_band']['claimed_raw']:.3f} and won {ref['verifier_one_a_game_band']['won']:.3f}.\n")

    # ── 1. what was built
    w("## 1. What was graded\n")
    nb_ = base["best"]
    w(f"- **Inputs the worker will have:** ESPN-style box lines (whole minutes, starter flag), schedule, game and "
      f"prop odds, an injury table holding only Out and Day-To-Day. The predictions, widths and model choices are "
      f"the verifier's worker re-fit, unchanged; the 13 markets are the ones that beat the naive projections "
      f"(triple-double closed).")
    w(f"- **Decision time:** the one prop snapshot, inside 45-70 minutes before tip. "
      f"{nb_['games_outside_window']} of {nb_['games']:,} games fall outside and are dropped.")
    w(f"- **One bet per proposition across every NBA prop model:** the shipped Pinnacle same-line-unders rule's "
      f"{base['rule_keys']:,} (game, player, market) keys are removed on every line and both sides before "
      f"anything is chosen; {nb_['rule_keys_found']:,} of them sit in the graded population. Every saved bet list "
      f"is checked against the rule's list before it is written.")
    w("- **Main lines only.** The archive holds one line per book per player-market. The card decides at the "
      "consensus main line (DraftKings' two-sided line, else the line most bettable books hang), over or under, "
      "at the best bettable price there. Why the decision is not allowed off that line: section 2.3.")
    w("- **Units:** one unit to win, risk capped at 3. ROI = units won / units risked. Voids (did not play) take "
      "their slot and score nothing.\n")

    # ── 2. calibration
    w("## 2. Calibration\n")
    w("### 2.1 The map, and why this one\n")
    pts = CT[CT.market == "player_points"]
    gap = 100 * (pts.won - pts.claimed_raw)
    iso = CT.dropna(subset=["ll_iso"])
    iso_better = iso[iso.ll_iso < iso.ll_cal]
    w(f"Per market, `logit P(over) = a + b * logit(p_model)` (Platt), fitted on main-line (claimed probability, "
      f"outcome) pairs. A per-market map because the defect differs by market (the raw model under-calls the "
      f"points over by {gap.min():.1f}-{gap.max():.1f} points a season; blocks, steals and threes barely move). "
      f"Two parameters because the measured defect is a shift plus a slope; the map stays strictly monotone, so "
      f"it never ties two bets, and it does not flatten in the tails the way isotonic does. Isotonic was fitted "
      f"beside it on the same pairs: out of sample it beats the Platt map in {len(iso_better)} of {len(iso)} "
      f"market-seasons, by at most {1000 * (iso_better.ll_cal - iso_better.ll_iso).max():.2f} thousandths of log "
      f"loss, and is worse in the rest by up to {1000 * (iso.ll_iso - iso.ll_cal).max():.2f} (table below, "
      f"`ll_iso`).\n")
    wk = prox["weeks_on_proxy_by_market"]
    longest = max(wk, key=lambda m: len(wk[m]))
    last_wk = (pd.Timestamp(wk[longest][-1]) + pd.Timedelta(days=6)).date()
    pm, om = prox["proxy_map"], prox["own_season_2024_map_insample"]
    slope_rows = ", ".join(f"{LABEL[m]} {pm[m][1]:.2f} against {om[m][1]:.2f}"
                           for m in ("player_rebounds_assists", "player_points", "player_rebounds"))
    w(f"Walk-forward: 2024-25 is mapped by 2023-24's pairs, 2025-26 by 2023-24 + 2024-25's. 2023-24 has no priced "
      f"season before it, so its map is refitted every Monday on 2023-24 main-line games played before that "
      f"Monday, once a market holds {MIN_PAIRS} such pairs. Until then the 2022-23 walk-forward predictions at a "
      f"proxy line stand in: {prox['main_line_pairs_2024_on_proxy']:,} of {prox['main_line_pairs_2024']:,} "
      f"2023-24 main-line propositions (the opening week in every market; {LABEL[longest]} until {last_wk}). "
      f"The proxy was rejected as the whole 2023-24 map after one check: its slopes are far steeper than the ones "
      f"2023-24's own main lines produce ({slope_rows}), so it would have inflated 2023-24's EV in a season used "
      f"for choosing.\n")
    mm = M[M.season.isin([2025, 2026])][["season", "market", "a", "b", "n_pairs"]].copy()
    mm["market"] = mm.market.map(LABEL)
    w("Maps used for 2024-25 and 2025-26 (`b` below 1 = the raw model is overconfident):\n")
    w(_md(mm.pivot_table(index="market", columns="season", values=["a", "b"]).round(3).reset_index()
          .set_axis(["market", "a 2024-25", "a 2025-26", "b 2024-25", "b 2025-26"], axis=1), "{:+.3f}") + "\n")
    w("### 2.2 Before and after, out of sample, every main-line proposition\n")
    ct = CT.copy()
    ct["market"] = ct.market.map(LABEL)
    ct = ct[["season", "market", "n", "claimed_raw", "claimed_cal", "won", "brier_raw", "brier_cal", "ll_raw",
             "ll_cal", "ll_iso"]]
    w(_md(ct, "{:.4f}") + "\n")
    w("Turnovers: 49 main-line propositions in 2025-26. The books barely priced the market that season.\n")
    rows = []
    for name, x in (("verifier's one-a-game card, raw model, all lines", ref["verifier_one_a_game_band"]),):
        rows.append({"bets": f"{x['bets']:,}", "": name, "claimed (raw)": f"{x['claimed_raw']:.3f}",
                     "claimed (calibrated)": "", "won": f"{x['won']:.3f}", "price implied": f"{x['implied']:.3f}"})
    b1 = card["band"]["same_cells_on_raw_ev"]
    rows.append({"bets": f"{b1['bets']:,}", "": "the card's markets, sides and floors, chosen on RAW EV",
                 "claimed (raw)": f"{b1['claimed_raw']:.3f}", "claimed (calibrated)": "",
                 "won": f"{b1['won']:.3f}", "price implied": ""})
    b2 = card["band"]["calibrated_card"]
    rows.append({"bets": f"{b2['bets']:,}", "": "the card, chosen on CALIBRATED EV",
                 "claimed (raw)": f"{b2['claimed_raw']:.3f}", "claimed (calibrated)": f"{b2['claimed_cal']:.3f}",
                 "won": f"{b2['won']:.3f}", "price implied": f"{b2['implied']:.3f}"})
    w("**Calibration error in the band that gets bet** (win rate on decided bets):\n")
    w(_md(pd.DataFrame(rows)[["", "bets", "claimed (raw)", "claimed (calibrated)", "won", "price implied"]]) + "\n")
    vb = ref["verifier_one_a_game_band"]
    w(f"Selecting on EV still selects on the model's own error, so the card's bets win "
      f"{100 * (b2['claimed_cal'] - b2['won']):.1f} points less than the calibrated number claims "
      f"({100 * (vb['claimed_raw'] - vb['won']):.1f} points on the verifier's card before calibration). The "
      f"number a member is shown should be the calibrated one, read as an upper bound.\n")
    rows = []
    for S in SEASONS:
        x = cnt["best"][str(S)]
        rows.append({"season": S, "main-line propositions (both sides, rule's removed)": f"{x['main_line_rows']:,}",
                     "EV >= 0, raw": f"{x['ev_raw_ge_0']:,}", "EV >= 0, calibrated": f"{x['ev_cal_ge_0']:,}"})
    w("How many propositions clear EV >= 0, before and after (eight books):\n")
    w(_md(pd.DataFrame(rows)) + "\n")
    w("### 2.3 Why the card decides only at the main line\n")
    w("A map fitted on every line (each book's own line) was read on 2024-25 first. At the consensus line it is "
      "right; one point off it, the calibrated number barely moves while the outcome moves 4-8 points, in the "
      "direction that favours the better-priced side. Every price band of EV >= 0 bets then loses. This was "
      "read on 2024-25 (a choosing season) before any units cell existed; the main-line rule follows from it.\n")
    dt = DT.copy()
    w("2024-25, map fitted on every 2023-24 line; line minus the players' median line across books:\n")
    w(_md(dt, "{:.3f}") + "\n")
    de = DE[["pb", "n", "claimed", "won", "roi%"]].rename(columns={"pb": "price"})
    w("Those EV >= 0 bets by price:\n")
    w(_md(de, "{:.3f}") + "\n")
    w("### 2.4 What the model adds to the price\n")
    w("Log loss at the main line, out of sample: the calibrated model alone, the bettable books' own no-vig "
      "probability alone, and both together (a logistic fit on the earlier seasons). The books' number beats the "
      "calibrated model in most markets. Adding the model helps in blocks, steals, blocks+steals, threes, "
      "rebounds, assists and reb+ast (model weight 0.2-0.6) and barely at all in points and the scoring combos "
      "(0.12-0.22). This is not a card (it would re-open the soft-book consensus rule section 4.3 of "
      "`docs/nba_models_2026.md` closed); it is the honest read of where the model has information.\n")
    dm = DM.dropna(subset=["ll_market"]).copy()
    dm["market"] = dm.market.map(LABEL)
    w(_md(dm[["season", "market", "n", "ll_model_cal", "ll_market", "ll_both", "coef_model", "coef_market"]],
          "{:.4f}") + "\n")

    # ── 3. the grid
    w("## 3. The grid\n")
    w(f"{len(G)} cells: 13 markets x under / over / both x 14 calibrated-EV floors "
      f"({', '.join(f'{f:.2f}' for f in FLOORS)}). Every qualifying proposition is a bet. Per market, the side and "
      f"floor with the most units on 2023-24 + 2024-25, among cells where both seasons have 30+ bets and are "
      f"positive. Then bars 4-10 on all three seasons. A confirmation needs a graded season: 30+ bets in "
      f"2025-26, bar 5's own threshold.\n")
    rows = []
    for r in J.to_dict("records"):
        bars_ = [k for k in r if k.startswith("b") and k[1:2].isdigit()]
        failed = [k.split("_")[0] for k in bars_ if not r[k]]
        rows.append({"market": LABEL[r["market"]], "side": r["side"], "floor": f"{r['floor']:.2f}",
                     "bets": f"{r['bets']:,}", "units": _u(r["units"]), "ROI %": f"{r['roi']:+.2f}",
                     "units 23-24 / 24-25 / 25-26": f"{_u(r['u_2024'])} / {_u(r['u_2025'])} / {_u(r['u_2026'])}",
                     "90% CI %": f"{r['ci_lo']:+.2f}..{r['ci_hi']:+.2f}",
                     "early / late units": f"{_u(r['u_early'])} / {_u(r['u_late'])}",
                     "neighbours (floor: units)": ", ".join(f"{x['floor']:.2f}: {_u(x['units'])}"
                                                            for x in r["neighbours"]),
                     "placebo max %": f"{r['placebo_max']:+.2f}",
                     "blind same side %": f"{r['blind']['main_line']['roi']:+.2f} ({r['blind_side']})",
                     "DraftKings alone %": f"{r['dk']['roi']:+.2f}",
                     "five feed books %": f"{r['arriving5']['roi']:+.2f}",
                     "verdict": "in the card" if r["enters_card"] else "out: " + ", ".join(failed)})
    w(_md(pd.DataFrame(rows)) + "\n")
    if none_cell:
        w(f"No cell positive in both choosing seasons (closed): {', '.join(LABEL[m] for m in none_cell)}.\n")
    w("Turnovers: out because 2025-26 cannot confirm it (13 bets; the books barely priced turnovers that "
      "season), not because it lost.\n")
    w("Units by floor, every market and side (2023-24 + 2024-25 | 2025-26):\n")
    for mk in markets():
        g = G[G.market == mk]
        t = g.pivot_table(index="side", columns="floor", values="u_choose").round(0)
        t2 = g.pivot_table(index="side", columns="floor", values="u_2026").round(0)
        tt = t.astype(int).astype(str) + " / " + t2.astype(int).astype(str)
        tt.columns = [f"{c:.2f}" for c in tt.columns]
        w(f"**{LABEL[mk]}**\n")
        w(_md(tt.reset_index()) + "\n")

    # ── 4. the card
    w("## 4. The pooled card\n")
    w(_md(pd.DataFrame([_row("the card", best)] + [_row(f"every floor {k.split()[-2]} step", v)
                                                   for k, v in card["neighbours"].items()])) + "\n")
    w(f"- Halves (each season split at its midpoint): early {_u(best['u_early'])}, late {_u(best['u_late'])} units.")
    pl = card["placebo"]
    w(f"- Placebo ({pl['n']} shuffles of the model's numbers within each night and market, the same calibration "
      f"maps, the same floors): mean {pl['mean_roi']:+.2f}%, 95th percentile {pl['p95_roi']:+.2f}%, best "
      f"{pl['max_roi']:+.2f}%. The real card beats all {pl['n']}.")
    bu = card["blind"].get("under", {})
    bo = card["blind"].get("over", {})
    w(f"- Blind, same side, same propositions (main line, best price): under {bu['main_line']['roi']:+.2f}% on "
      f"{bu['main_line']['bets']:,}; over {bo['main_line']['roi']:+.2f}% on {bo['main_line']['bets']:,}. The "
      f"card is {best['under_share'] * 100:.0f}% unders.")
    pr = best["prices"]
    bp = pd.DataFrame(card["by_price"])
    long_ = bp[bp.pband.isin(["(150, 200]", "(200, 400]", "(400, 5000]"])]
    vlong = bp[bp.pband.isin(["(200, 400]", "(400, 5000]"])]
    w(f"- **Prices the card lays** (American): min {pr['min']}, 5th percentile {pr['p5']}, median {pr['median']:+d}, "
      f"95th percentile {pr['p95']:+d}, max {pr['max']:+d}. Longer than +150: {int(long_.bets.sum()):,} bets "
      f"({100 * long_.bets.sum() / best['bets']:.1f}%); longer than +200: {int(vlong.bets.sum()):,} bets, "
      f"{_u(float(vlong.units.sum()))} units. Shorter than -150: "
      f"{int(bp[bp.pband == '(-201, -150]'].bets.sum()):,} bets.")
    pin = rob["pinnacle_quotes_the_line"]
    w(f"- Where Pinnacle quotes the bet's line ({pin['bets']:,} bets): {pin['roi']:+.2f}%, and the median bet has "
      f"EV {card['pinnacle_same_line']['median_ev_vs_pinnacle']:+.3f} against Pinnacle's no-vig "
      f"({100 * card['pinnacle_same_line']['share_positive']:.0f}% positive). Where Pinnacle is silent "
      f"({rob['pinnacle_silent']['bets']:,}): {rob['pinnacle_silent']['roi']:+.2f}%. Not bar 11; a stand-in.\n")
    t = pd.DataFrame(rob["model_vs_price"])
    t["market"] = t.market.map(LABEL)
    t = t.rename(columns={"card_roi": "card ROI %", "blind_roi": "blind same side ROI %",
                          "blind_roi_price_matched": "blind, card's price mix ROI %",
                          "card_roi_ev_low": "card, lowest-EV third %", "card_roi_ev_mid": "middle third %",
                          "card_roi_ev_high": "highest-EV third %"})
    w("**What the model adds over the price, per market and side.** A blind bet on the same side at the main "
      "line, reweighted to the card's own mix of prices, loses in every row; the card wins in every row. Within "
      "the card, the highest-EV third beats the lowest in most rows (not threes overs, not blocks+steals "
      "unders):\n")
    w(_md(t) + "\n")
    w("Book sets and prices (same maps, same cells, nothing re-chosen):\n")
    rows = [_row("eight books", best), _row("DraftKings alone", dk), _row("five books the feed returns", a5),
            _row("five books config collects", c5), _row("eight books without Hard Rock", rob["without_hardrock"]),
            _row("two+ books at the line, best price", rob["two_or_more_books_at_line_best_price"]),
            _row("same bets, second-best price", rob["two_or_more_books_at_line_second_best_price"]),
            _row("every bet at the median book's price", rob["median_book_price"])]
    w(_md(pd.DataFrame(rows)) + "\n")
    w(f"Card bets with no quote at that line and side: {dk['card_bets_without_a_quote_here']:,} at DraftKings, "
      f"{a5['card_bets_without_a_quote_here']:,} at the five feed books.\n")
    for k, title in (("by_market", "By market"), ("by_book", "By deciding book"), ("by_side", "By side"),
                     ("by_price", "By price"), ("by_calibrated_prob", "By calibrated probability"),
                     ("by_status", "By injury status at the decision")):
        t = pd.DataFrame(card[k])
        if "market" in t:
            t["market"] = t.market.map(LABEL)
        w(f"**{title}**\n")
        w(_md(t, "{:.3f}") + "\n")
    t = pd.DataFrame(rob["by_books_at_line"]).rename(columns={"nb_": "bettable books at the line (5 = 5+)"})
    w("**By how many bettable books hang the line**\n")
    w(_md(t, "{:.3f}") + "\n")
    for name, title in (("dk_by_market", "DraftKings alone, by market"),
                        ("arriving5_by_market", "Five feed books, by market")):
        t = pd.DataFrame(rob[name])
        t["market"] = t.market.map(LABEL)
        w(f"**{title}**\n")
        w(_md(t, "{:.3f}") + "\n")

    # ── 5. multiplicity
    bh = card["bh"]
    w("## 5. How much was searched\n")
    w(f"- {bh['cells_searched']} cells in the grid (every one counted, including those with too few bets, at "
      f"p = 1). One-sided p per cell from the whole-day bootstrap. Benjamini-Hochberg: {bh['survive_q05']} cells "
      f"survive at q = 0.05, {bh['survive_q10']} at q = 0.10; Bonferroni ({bh['cells_searched']} tests): "
      f"{bh['survive_bonferroni']}. Neighbouring floors share most of their bets, so these are not independent "
      f"discoveries.")
    t = pd.DataFrame(bh["card_cells"])
    t["market"] = t.market.map(LABEL)
    t["floor"] = t.floor.map(lambda v: f"{v:.2f}")
    t["p (one-sided)"] = t.p_norm.map(lambda v: f"{v:.1e}")
    w("- The card's cells:\n")
    w(_md(t[["market", "side", "floor", "p (one-sided)", "q05", "q10", "bonferroni"]]) + "\n")
    w("- Not counted as cells: the calibration diagnostics in section 2 (all-lines map, model vs market), the "
      "book-set and price regrades in section 4, and the one-a-game reference in section 6 -- none chose "
      "anything.")
    w("- One choice was made after reading data: deciding at the main line only (section 2.3), on 2024-25.\n")

    # ── 6. one under a game
    w("## 6. Reference: one under a game, same calibrated inputs\n")
    rows = []
    for tag, title in (("calibrated_excluding_rule", "calibrated, rule's propositions removed"),
                       ("calibrated_including_rule", "calibrated, rule's propositions allowed"),
                       ("uncalibrated_excluding_rule", "raw model, rule's propositions removed")):
        x = ref[tag]
        r_ = _row(title, x)
        r_["DraftKings alone %"] = f"{x['dk']['roi']:+.2f}"
        r_["claimed / won"] = f"{x['claimed']:.3f} / {x['won']:.3f}"
        rows.append(r_)
    w(_md(pd.DataFrame(rows)) + "\n")
    x = ref["calibrated_excluding_rule"]["prices"]
    w(f"Prices (calibrated, rule removed): min {x['min']}, 5th {x['p5']}, median {x['median']:+d}, 95th "
      f"{x['p95']:+d}, max {x['max']:+d}. One a game is about {ref['calibrated_excluding_rule']['units'] / 3:.0f} "
      f"units a season; the card is about {best['units'] / 3:.0f}.\n")

    # ── 7. bars
    w("## 7. The bars, for the pooled card at the eight books\n")
    bars_rows = [
        ("1. Real prices", "pass", "best bettable book at the main line; DraftKings and two five-book sets beside it"),
        ("2. Units, one to win", "pass", "risk capped at 3"),
        ("3. Every scored candidate graded", "pass", f"{len(G)} cells over every main-line proposition"),
        ("4. Walk-forward, confirmed on 2025-26", "pass", f"2025-26 {_u(best['u_2026'])} units, {best['roi_2026']:+.2f}%"),
        ("5. Positive every season", "pass", f"{_u(best['u_2024'])} / {_u(best['u_2025'])} / {_u(best['u_2026'])}"),
        ("6. >= 200 bets, CI above zero", "pass", f"{best['bets']:,} bets, {best['ci_lo']:+.2f}..{best['ci_hi']:+.2f}%"),
        ("7. Plateau", "pass", "every floor one step down / up: " + " / ".join(
            f"{v['roi']:+.2f}%" for v in card["neighbours"].values())),
        ("8. Both halves", "pass", f"{_u(best['u_early'])} / {_u(best['u_late'])}"),
        ("9. Beats the blind same side", "pass", f"unders {best['under_share'] * 100:.0f}%; blind under "
                                                f"{bu['main_line']['roi']:+.2f}%"),
        ("10. Placebo", "pass", f"best of {pl['n']} shuffles {pl['max_roi']:+.2f}%"),
        ("11. Closing value", "UNMEASURABLE", "one prop snapshot a game; the live card must store a closing price"),
        ("12. No look-ahead", "pass", "verifier's audit of the inputs; maps fitted only on earlier games; one "
                                      "small known roster defect carried (section 8)"),
        ("13. Name integrity", "pass", "shared names refused at matching (verifier's priced universe)")]
    w(_md(pd.DataFrame(bars_rows, columns=["bar", "card", "evidence"])) + "\n")

    # ── 8. caveats
    w("## 8. What this does not show, and what the live card needs\n")
    w("- **Stale or outlier quotes cannot be ruled out.** The archive stores no per-book update time. The best "
      "price carries much of the edge (section 4: second-best price, median book). The highest-ROI deciding books "
      "are the second-region ones (BetParx, BetRivers, Hard Rock).")
    w(f"- **Volume.** About {card['bets_a_night']['mean']:.0f} bets a night (up to {card['bets_a_night']['max']:.0f}), "
      f"on top of the Pinnacle rule's. Every one is a separate proposition; many share a game.")
    w("- **The live path has never been run** (the verifier's open item stands): the card needs the whole roster "
      "passed as tonight's rows, the main line computed exactly as here, the feed's alternate-line markets "
      "excluded, the calibration maps (2025-26's season-level map is the one fitted on 2023-24 + 2024-25; a "
      "2026-27 map would be fitted on all three priced seasons), the Pinnacle rule's picks read first so this "
      "model never bets the same proposition, and a closing snapshot stored for every bet.")
    w("- **Injury statuses:** the worker sees Doubtful, Questionable and Probable as one Day-To-Day status, as "
      "here. Out is excluded from betting.")
    rd = rob["roster_defect"]
    w(f"- **Carried from the verifier's inputs, not fixed:** a player back after more than 30 days and on no "
      f"injury list joins the inferred roster only by playing, and then counts in his teammates' returning "
      f"minutes. On this card it touches {rd['team_games_touched']:,} team-games and "
      f"{rd['card_bets_touched']:,} bets. Without them: {rd['card_without_them']['bets']:,} bets, "
      f"{rd['card_without_them']['roi']:+.2f}% (CI {rd['card_without_them']['ci_lo']:+.2f}.."
      f"{rd['card_without_them']['ci_hi']:+.2f}), by season {_u(rd['card_without_them']['u_2024'])} / "
      f"{_u(rd['card_without_them']['u_2025'])} / {_u(rd['card_without_them']['u_2026'])} units. It does not "
      f"drive the result.")
    w("- **Turnovers** could not be confirmed (2025-26 barely priced). **Double-double** has no cell positive in "
      "both choosing seasons. **Points, Pts+Reb, Pts+Ast, Pts+Reb+Ast** fail (section 3).\n")

    # ── 9. files
    w("## 9. Files\n")
    files = sorted(p.name for p in OUT.glob("bets_*.parquet"))
    w("Bet lists (`C:/Users/micha/AppData/Local/Temp/nba_rebuild/proj/`): " + ", ".join(f"`{f}`" for f in files)
      + ". Work files (maps, grid, judgements, diagnostics): `proj/work/`.\n")
    text = "\n".join(L)
    assert "lane" not in text.lower(), "the report uses a banned word"
    (OUT / "research.md").write_text(text, encoding="utf-8")
    log(f"report written: {OUT / 'research.md'} ({len(text):,} chars)")


if __name__ == "__main__":
    main()
