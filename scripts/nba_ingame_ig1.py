"""IG-1: live totals after in-game shooting luck (docs/nba_models_2026.md 7.2).

The row in 7.2 and the lab's reading of it ("IG-1: how the lab reads the row
above", committed before any IG-1 number) are the specification. In short:

  LUCK (L)    both teams, at the play-by-play state at or before a stamp:
              3 x (3PM - 3PA x e3) + (FTM - FTA x eFT). e3 / eFT = the shooting
              team's own rates over its games on EARLIER dates this season
              (box scores, nba_player_game_log). Through 2024-25 the official
              3PA counts missed end-of-period heaves, so the in-game count adds
              them (heave3); from 2025-26 both leave them out.
  CELLS       IG-1: under when L >= g, over when L <= -g; g = 2, 4, 6, 8;
              windows Q2, halftime, Q3 (by the quote's own stamp,
              nba_ingame_staleness.window_of). control_ig1_persist: the other
              way at the same cuts. 24 + 24 rows.
  POPULATION  both teams >= 10 games this season (CLAUDE.md section 3), and a
              Pinnacle pre-game closing total.
  ELIGIBLE    a deciding book (H.BETTABLE), coherent, a coherent Pinnacle quote
              in the same purchase within 60 s, and no point scored between
              stamp and serving for the quote AND its Pinnacle quote (7.1).
  DECISION    per game and window: the first purchase in the window holding an
              eligible quote; the offers are every eligible quote of that
              purchase in that window; L is read at the earliest stamp among
              the offers and their Pinnacle quotes. Nothing later is looked at.
  MODEL       remaining = C f + w (P - L - C (1 - f)) f / (1 - f); C = Pinnacle's
              pre-game fair total, f = share of 48 min left, P = points so far;
              w per window by least squares on seasons before S. M = P + remaining.
  INFO TEST   rows: Pinnacle's own fresh coherent live totals, first per game and
              window, at Pinnacle's stamp. mu = Pinnacle's fair total from its
              no-vig over price through the empirical spread of (final total -
              Pinnacle live number) on earlier seasons, same window. Without the
              model mu + a0; with it mu + a + b (M - mu); fits on earlier
              seasons, per window. Statistic: mean change in squared error of the
              final total (with minus without; below zero = information), whole-
              day bootstrap 95%, 4,000 resamples, seed 7, on the choosing seasons
              pooled and 2025-26 alone. CLOSED unless the choosing interval lies
              wholly below zero. Diagnostics (a) score-only model, (b) the luck
              term on top of (a), (c) the full model against the deciding books'
              own fair total -- reported, never the gate.
  GRID        only when the test passes: H.run_cells per window, offers priced at
              Pinnacle's live fair total through the same distribution, placebo =
              L shuffled within date (20 runs). CLV and "still offered at the
              next purchase" are not computed (the next purchase is an hour later).

    PYTHONPATH=. NBA_RESEARCH_CACHE=<v2> python -m scripts.nba_ingame_ig1          # test, then grid if it passes
    PYTHONPATH=. NBA_RESEARCH_CACHE=<v2> python -m scripts.nba_ingame_ig1 --info-only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import nba_game_harness as H  # noqa: E402
from scripts.nba_game_market_lab import threshold  # noqa: E402
from scripts.nba_ingame_data import HEAVE_RULE_SEASON, OUT as QUOTES  # noqa: E402
from scripts.nba_ingame_staleness import window_of  # noqa: E402

FAMILY, CONTROL = "IG-1", "control_ig1_persist"
WINDOWS = ("Q2", "halftime", "Q3")
CUTS = (2.0, 4.0, 6.0, 8.0)
SIDES = {"totals": ["over", "under"]}
MIN_GAMES = 10
DIST_MIN_PRIOR = 100
N_PLACEBO = 20
GAME_S = 2880.0
OUT_DIR = QUOTES.parent
CELLS = OUT_DIR / "cells_IG-1.parquet"
INFO = OUT_DIR / "info_IG-1.json"
STATE = ["h_pts", "a_pts", "h_fg3a", "h_fg3m", "h_heave3", "h_fta", "h_ftm",
         "a_fg3a", "a_fg3m", "a_heave3", "a_fta", "a_ftm", "period", "clock_s", "secs_left"]
EXPECTED_ROWS = {FAMILY: len(WINDOWS) * 2 * len(CUTS), CONTROL: len(WINDOWS) * 2 * len(CUTS)}
assert EXPECTED_ROWS == {FAMILY: 24, CONTROL: 24}


# ── expected shooting: each team's own rates on earlier dates ───────────────

def team_rates(box: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """(season, team, game_date, n, e3, eft): the team's 3P% and FT% over its
    games of the same season on dates STRICTLY before game_date, for every
    (season, team, game_date) the team plays on."""
    b = box.groupby(["game_id", "team"], as_index=False)[["fg3_made", "fg3_att", "ft_made", "ft_att"]].sum()
    b = b.merge(games[["game_id", "season", "game_date", "home_team", "away_team"]], on="game_id")
    b = b[(b["team"] == b["home_team"]) | (b["team"] == b["away_team"])]
    d = b.groupby(["season", "team", "game_date"], as_index=False)[
        ["fg3_made", "fg3_att", "ft_made", "ft_att"]].sum().assign(n=1.0)
    d = d.sort_values(["season", "team", "game_date"])
    cols = ["fg3_made", "fg3_att", "ft_made", "ft_att", "n"]
    cum = d.groupby(["season", "team"])[cols].cumsum()
    prev = cum - d[cols].to_numpy()                     # everything before this date
    out = d[["season", "team", "game_date"]].copy()
    out["n"] = prev["n"].to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        out["e3"] = (prev["fg3_made"] / prev["fg3_att"]).to_numpy()
        out["eft"] = (prev["ft_made"] / prev["ft_att"]).to_numpy()
    return out.reset_index(drop=True)


def attach_rates(df: pd.DataFrame, rates: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Adds h_n, h_e3, h_eft, a_n, a_e3, a_eft by the game's teams and date."""
    g = games[["game_id", "home_team", "away_team"]]
    x = df.merge(g, on="game_id", how="left")
    r = rates[["season", "team", "game_date", "n", "e3", "eft"]]
    for side, col in (("h", "home_team"), ("a", "away_team")):
        rr = r.rename(columns={"team": col, "n": f"{side}_n", "e3": f"{side}_e3", "eft": f"{side}_eft"})
        x = x.merge(rr, on=["season", col, "game_date"], how="left")
    return x.drop(columns=["home_team", "away_team"])


def luck_points(df: pd.DataFrame) -> pd.Series:
    """L: both teams' 3 x (3PM - 3PA x e3) + (FTM - FTA x eFT). Before the
    2025-26 heave rule the attempts include missed heaves (the box rates do)."""
    old = (df["season"] < HEAVE_RULE_SEASON).to_numpy()
    tot = np.zeros(len(df))
    for s in ("h", "a"):
        att3 = df[f"{s}_fg3a"].to_numpy(float) + np.where(old, df[f"{s}_heave3"].to_numpy(float), 0.0)
        tot += 3.0 * (df[f"{s}_fg3m"].to_numpy(float) - att3 * df[f"{s}_e3"].to_numpy(float))
        tot += df[f"{s}_ftm"].to_numpy(float) - df[f"{s}_fta"].to_numpy(float) * df[f"{s}_eft"].to_numpy(float)
    return pd.Series(tot, index=df.index)


# ── eligibility, windows and the decision ───────────────────────────────────

def window_label(q: pd.DataFrame) -> pd.Series:
    w = window_of(q)
    lab = pd.Series(None, index=q.index, dtype=object)
    for name in WINDOWS:
        lab[w[name] & lab.isna()] = name
    return lab


def pin_fresh_flag(q: pd.DataFrame, rows: pd.DataFrame) -> np.ndarray:
    """True where the row's Pinnacle quote (same purchase, its pin_stamp) had no
    point scored between its stamp and serving."""
    pin = q[q["book"] == H.SHARP].set_index(["game_id", "market", "fetch_at", "stamp"])["pts_since_stamp"]
    key = pd.MultiIndex.from_frame(rows[["game_id", "market", "fetch_at", "pin_stamp"]])
    return (pin.reindex(key).to_numpy() == 0)


def eligible(q: pd.DataFrame) -> pd.DataFrame:
    """Deciding-book live totals that pass 7.1, with their window."""
    d = q[(q["market"] == "totals") & q["book"].isin(H.BETTABLE) & q["coherent"]
          & q["pin_fa"].notna() & (q["pts_since_stamp"] == 0)].copy()
    d = d[pin_fresh_flag(q, d)]
    d["window"] = window_label(d)
    return d[d["window"].notna()].reset_index(drop=True)


def decisions(el: pd.DataFrame) -> pd.DataFrame:
    """Per (game, window) the offers of the first purchase holding an eligible
    quote, each carrying T (that purchase's serving time) and t0 (the earliest
    stamp among the offers and their Pinnacle quotes)."""
    first = el.groupby(["game_id", "window"])["fetch_at"].min().rename("first_fetch").reset_index()
    x = el.merge(first, on=["game_id", "window"])
    x = x[x["fetch_at"] == x["first_fetch"]].drop(columns="first_fetch")
    t0 = pd.concat([x["stamp"], x["pin_stamp"]], axis=1).min(axis=1)
    x = x.assign(_t=t0)
    x["t0"] = x.groupby(["game_id", "window"])["_t"].transform("min")
    x["T"] = x.groupby(["game_id", "window"])["served_at"].transform("max")
    return x.drop(columns="_t").reset_index(drop=True)


def state_at_t0(dec: pd.DataFrame, q: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, window): the play-by-play state of the quote (an offer
    or its Pinnacle quote) stamped at t0."""
    cand = dec[["game_id", "window", "t0", "stamp", *STATE]]
    pin_rows = q[q["book"] == H.SHARP][["game_id", "market", "fetch_at", "stamp", *STATE]]
    pk = dec[["game_id", "window", "t0", "market", "fetch_at", "pin_stamp"]].rename(columns={"pin_stamp": "stamp"})
    pins = pk.merge(pin_rows, on=["game_id", "market", "fetch_at", "stamp"], how="inner").drop(
        columns=["market", "fetch_at"])
    allr = pd.concat([cand, pins], ignore_index=True)
    allr = allr[allr["stamp"] == allr["t0"]].drop_duplicates(["game_id", "window"])
    return allr.drop(columns="stamp").reset_index(drop=True)


def info_rows(q: pd.DataFrame) -> pd.DataFrame:
    """Pinnacle's own coherent live totals that pass 7.1, the first per game and
    window (by purchase, then stamp), with the state at its own stamp."""
    p = q[(q["book"] == H.SHARP) & (q["market"] == "totals") & q["coherent"]
          & (q["pts_since_stamp"] == 0)].copy()
    p["window"] = window_label(p)
    p = p[p["window"].notna()].sort_values(["game_id", "window", "fetch_at", "stamp"])
    return p.drop_duplicates(["game_id", "window"]).reset_index(drop=True)


# ── pricing: Pinnacle's pre-game close and its live fair total ──────────────

def close_totals(data: H.Data) -> pd.DataFrame:
    """(game_id, C): Pinnacle's pre-game fair total, its close's no-vig price
    solved through the harness's empirical distribution (seasons before S)."""
    close = H.pinnacle_close(data)
    dist = H.close_dist(close, data.games)
    c = close[close["market"] == "totals"].copy()
    sig = np.array([dist.get((int(s), "totals")) for s in c["season"]], dtype=object)
    ok = np.array([v is not None for v in sig])
    c = c[ok]
    c["C"] = H.solve_any(threshold("totals", c["close_line"]), c["close_fa"].to_numpy(), sig[ok])
    return c[["game_id", "C"]]


def live_dists(rows: pd.DataFrame, min_prior: int = DIST_MIN_PRIOR) -> dict:
    """(season, window) -> ResidDist of (final total - Pinnacle's live number)
    on earlier seasons in the window (own season where fewer than min_prior)."""
    r = pd.DataFrame({"season": rows["season"].astype(int), "market": rows["window"],
                      "resid": rows["final_home"] + rows["final_away"] - rows["pin_line_live"]})
    return H.dist_by_season(r, sorted(r["season"].unique()), min_prior=min_prior)


def fair_mu(line, fa, season, window, dists: dict) -> np.ndarray:
    sig = np.array([dists.get((int(s), w)) for s, w in zip(season, window)], dtype=object)
    out = np.full(len(sig), np.nan)
    ok = np.array([v is not None for v in sig])
    if ok.any():
        out[ok] = H.solve_any(threshold("totals", np.asarray(line, float)[ok]),
                              np.asarray(fa, float)[ok], sig[ok])
    return out


# ── the model and the information test ──────────────────────────────────────

def model_terms(df: pd.DataFrame, luck: bool = True) -> pd.DataFrame:
    """x (the pace term), base (P + C f) and the luck term L f/(1-f)."""
    f = df["secs_left"].to_numpy(float) / GAME_S
    P = (df["h_pts"] + df["a_pts"]).to_numpy(float)
    C = df["C"].to_numpy(float)
    L = df["L"].to_numpy(float) if luck else 0.0
    ratio = f / (1.0 - f)
    return pd.DataFrame({"x": (P - L - C * (1.0 - f)) * ratio, "base": P + C * f,
                         "luck_term": df["L"].to_numpy(float) * ratio}, index=df.index)


def fit_w(tr: pd.DataFrame, luck: bool = True) -> float:
    m = model_terms(tr, luck)
    y = (tr["final_home"] + tr["final_away"]).to_numpy(float)
    den = float((m["x"] ** 2).sum())
    if float(np.abs(m["x"]).max()) < 1e-9:     # no pace term at all (to rounding)
        return 0.0
    return float((m["x"] * (y - m["base"])).sum() / den)


def predict_M(df: pd.DataFrame, w: float, luck: bool = True) -> np.ndarray:
    m = model_terms(df, luck)
    return (m["base"] + w * m["x"]).to_numpy()


def ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Least squares; a regressor that is constant (to rounding) beside the
    intercept gets coefficient 0 instead of a huge fit to rounding noise."""
    beta = np.zeros(X.shape[1])
    keep = np.array([True] + [float(np.std(X[:, j])) > 1e-9 for j in range(1, X.shape[1])])
    beta[keep] = np.linalg.lstsq(X[:, keep], y, rcond=None)[0]
    return beta


def info_frame(rows: pd.DataFrame, mu_col: str = "mu", seasons=None) -> pd.DataFrame:
    """Walk-forward per (test season S, window): the squared-error change of
    each row of S. Adds columns d_main, d_a, d_b (with minus without) and the
    fitted coefficients. Every fit uses seasons < S only."""
    out = []
    seasons = sorted(rows["season"].unique()) if seasons is None else seasons
    for S in seasons:
        for wdw in WINDOWS:
            te = rows[(rows["season"] == S) & (rows["window"] == wdw)]
            tr = rows[(rows["season"] < S) & (rows["window"] == wdw)]
            if te.empty or len(tr) < 50:
                continue
            w_full, w_raw = fit_w(tr, True), fit_w(tr, False)
            res = {}
            for name, part in (("tr", tr), ("te", te)):
                y = (part["final_home"] + part["final_away"]).to_numpy(float)
                mu = part[mu_col].to_numpy(float)
                res[name] = dict(y=y, mu=mu, M=predict_M(part, w_full, True),
                                 Mr=predict_M(part, w_raw, False),
                                 lt=model_terms(part)["luck_term"].to_numpy())
            a, b = res["tr"], res["te"]
            one_tr, one_te = np.ones(len(a["y"])), np.ones(len(b["y"]))
            a0 = float(np.mean(a["y"] - a["mu"]))
            base = b["mu"] + a0
            c_main = ols(np.column_stack([one_tr, a["M"] - a["mu"]]), a["y"] - a["mu"])
            main = b["mu"] + np.column_stack([one_te, b["M"] - b["mu"]]) @ c_main
            c_raw = ols(np.column_stack([one_tr, a["Mr"] - a["mu"]]), a["y"] - a["mu"])
            raw = b["mu"] + np.column_stack([one_te, b["Mr"] - b["mu"]]) @ c_raw
            c_lk = ols(np.column_stack([one_tr, a["Mr"] - a["mu"], a["lt"]]), a["y"] - a["mu"])
            lk = b["mu"] + np.column_stack([one_te, b["Mr"] - b["mu"], b["lt"]]) @ c_lk
            y = b["y"]
            out.append(te[["game_id", "season", "game_date", "window"]].assign(
                d_main=(y - main) ** 2 - (y - base) ** 2,
                d_a=(y - raw) ** 2 - (y - base) ** 2,
                d_b=(y - lk) ** 2 - (y - raw) ** 2,
                se_base=(y - base) ** 2,
                w_full=w_full, w_raw=w_raw, b_main=c_main[1], b_raw=c_raw[1], b_luck=c_lk[2],
                n_train=len(tr)))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def mean_ci(df: pd.DataFrame, col: str, n_boot: int = H.N_BOOT, seed: int = H.SEED) -> dict:
    """Mean of col and its whole-day bootstrap 95% interval."""
    if df.empty:
        return {"n": 0, "mean": np.nan, "lo": np.nan, "hi": np.nan}
    s = df.groupby("game_date")[col].agg(["sum", "size"])
    rng = np.random.default_rng(seed)
    S, N = s["sum"].to_numpy(), s["size"].to_numpy()
    out = np.empty(n_boot)
    step = max(1, 2_000_000 // max(len(s), 1))
    for i in range(0, n_boot, step):
        k = min(step, n_boot - i)
        idx = rng.integers(0, len(s), size=(k, len(s)))
        out[i:i + k] = S[idx].sum(1) / N[idx].sum(1)
    lo, hi = np.percentile(out, [2.5, 97.5])
    return {"n": int(len(df)), "games": int(df["game_id"].nunique()), "mean": float(df[col].mean()),
            "lo": float(lo), "hi": float(hi)}


def gate_passes(choose_ci: dict) -> bool:
    """7.3 as the lab reads it: information only when the choosing seasons'
    interval lies wholly below zero."""
    return bool(np.isfinite(choose_ci.get("hi", np.nan)) and choose_ci["hi"] < 0)


# ── assembling the populations ──────────────────────────────────────────────

def with_population(df: pd.DataFrame, rates: pd.DataFrame, games: pd.DataFrame,
                    C: pd.DataFrame) -> pd.DataFrame:
    x = attach_rates(df, rates, games).merge(C, on="game_id", how="inner")
    keep = (x["h_n"] >= MIN_GAMES) & (x["a_n"] >= MIN_GAMES) & x["C"].notna()
    x = x[keep].copy()
    x["L"] = luck_points(x)
    return x[x["L"].notna()].reset_index(drop=True)


def strength_frame(states: pd.DataFrame, window: str, control: bool) -> pd.DataFrame:
    """(game_id, market, strength): the signal toward OVER. IG-1 bets against
    luck (toward over = -L); the control bets with it (+L)."""
    s = states[states["window"] == window]
    sign = 1.0 if control else -1.0
    return pd.DataFrame({"game_id": s["game_id"].to_numpy(), "market": "totals",
                         "strength": sign * s["L"].to_numpy(float)})


def side_strength(off: pd.DataFrame, signal: pd.DataFrame) -> pd.DataFrame:
    """Offers carrying the signal in THAT side's favour: +signal for over,
    -signal for under (nba_game2_luck.side_strength's convention)."""
    x = off.drop(columns=[c for c in ("strength",) if c in off]).merge(
        signal[["game_id", "market", "strength"]], on=["game_id", "market"], how="inner")
    return x.assign(strength=np.where(x["side"] == "over", x["strength"], -x["strength"]))


# ── the run ─────────────────────────────────────────────────────────────────

def build(q: pd.DataFrame, data: H.Data) -> dict:
    games = data.games
    box = pd.read_parquet(H.CACHE / "nba_player_game_log.parquet",
                          columns=["game_id", "team", "fg3_made", "fg3_att", "ft_made", "ft_att"])
    box = box[box["team"].notna() & (box["team"] != "NaN")]
    rates = team_rates(box, games)
    C = close_totals(data)
    # information-test rows: Pinnacle's own fresh quotes
    ir = info_rows(q).rename(columns={"line": "pin_line_live", "fa": "pin_fa_live"})
    ir = with_population(ir, rates, games, C)
    dists = live_dists(ir)
    ir["mu"] = fair_mu(ir["pin_line_live"], ir["pin_fa_live"], ir["season"], ir["window"], dists)
    # decision rows: the deciding books' first eligible purchase per game and window
    el = eligible(q)
    dec = decisions(el)
    st = state_at_t0(dec, q)
    st = st.merge(dec[["game_id", "window", "season", "game_date"]].drop_duplicates(["game_id", "window"]),
                  on=["game_id", "window"])
    st = with_population(st, rates, games, C)
    dec = dec[dec.set_index(["game_id", "window"]).index.isin(st.set_index(["game_id", "window"]).index)]
    dec = dec.reset_index(drop=True)
    pin_dec = dec.sort_values("stamp").drop_duplicates(["game_id", "window"])
    pin_dec = pin_dec.assign(mu=fair_mu(pin_dec["pin_line"], pin_dec["pin_fa"], pin_dec["season"],
                                        pin_dec["window"], dists))
    st = st.merge(pin_dec[["game_id", "window", "mu", "final_home", "final_away"]], on=["game_id", "window"])
    # diagnostic (c): the deciding books' own fair total, median over the offers
    dec["mu_book"] = fair_mu(dec["line"], dec["fa"], dec["season"], dec["window"], dists)
    mb = dec.groupby(["game_id", "window"])["mu_book"].median().rename("mu_book").reset_index()
    st = st.merge(mb, on=["game_id", "window"], how="left")
    fallback = sorted(str(k) for k, v in dists.items() if "own season" in v.label)
    return {"rates": rates, "C": C, "info_rows": ir, "dists": dists, "dist_fallback": fallback,
            "eligible": el, "decisions": dec, "states": st}


def info_test(b: dict) -> dict:
    ir = b["info_rows"]
    f = info_frame(ir, "mu", seasons=[s for s in sorted(ir["season"].unique()) if s > H.REGIME])
    st = b["states"].dropna(subset=["mu_book"])
    fc = info_frame(st, "mu_book", seasons=[s for s in sorted(st["season"].unique()) if s > H.REGIME])
    out = {"rows": {int(s): {w: int(((ir["season"] == s) & (ir["window"] == w)).sum()) for w in WINDOWS}
                    for s in sorted(ir["season"].unique())},
           "dist_fallback": b["dist_fallback"], "panels": {}}
    for label, frame, col in (("main", f, "d_main"), ("a_score_only", f, "d_a"),
                              ("b_luck_on_score_only", f, "d_b"), ("c_vs_deciding_books", fc, "d_main")):
        res = {}
        for span, mask in (("choose", frame["season"].isin(H.CHOOSE)), ("2026", frame["season"] == H.CONFIRM)):
            res[span] = mean_ci(frame[mask], col)
            res[span]["base_mse"] = float(frame.loc[mask, "se_base"].mean())
            for w in WINDOWS:
                res[f"{span}_{w}"] = mean_ci(frame[mask & (frame["window"] == w)], col, n_boot=1000)
        for s in sorted(frame["season"].unique()):
            res[f"season_{int(s)}"] = mean_ci(frame[frame["season"] == s], col, n_boot=1000)
        out["panels"][label] = res
    coefs = f.groupby(["season", "window"])[["w_full", "w_raw", "b_main", "b_raw", "b_luck", "n_train"]].first()
    out["coefs"] = {f"{int(s)}|{w}": {k: float(v) for k, v in r.items()} for (s, w), r in coefs.iterrows()}
    out["passes"] = gate_passes(out["panels"]["main"]["choose"])
    out["confirm_covers_zero"] = not (out["panels"]["main"]["2026"]["hi"] < 0)
    return out


def ingame_data(games: pd.DataFrame) -> H.Data:
    """A Data whose pre-game purchase list is empty: next_fetch_check then
    returns False everywhere, and the run reports those columns as NaN."""
    fetches = pd.DataFrame({"game_id": pd.Series(dtype=str),
                            "fetch_at": pd.Series(dtype="datetime64[ns, UTC]"),
                            "lead_min": pd.Series(dtype=float)})
    return H.Data(games=games, quotes=pd.DataFrame(columns=["game_id", "market", "book", "snapshot_at",
                                                            "fetch_at", "line", "price_a", "price_b",
                                                            "coherent"]),
                  fetches=fetches)


def grid(b: dict, data: H.Data) -> pd.DataFrame:
    games = data.games
    dists = b["dists"]
    dec, st = b["decisions"], b["states"]
    dd = H.Data(games=games, quotes=ingame_data(games).quotes, fetches=ingame_data(games).fetches)
    rows = []
    for wdw in WINDOWS:
        d = dec[dec["window"] == wdw].rename(columns={"stamp": "snapshot_at"})
        off = H.offers(d)
        fair = st[st["window"] == wdw][["game_id", "season", "mu"]].assign(market="totals")
        fair["sigma"] = pd.Series([dists.get((int(s), wdw)) for s in fair["season"]],
                                  index=fair.index, dtype=object)
        fair["p_home"] = np.nan
        fair = fair[fair["mu"].notna()]
        neutral = H.fair_offers(off, fair)
        times = d.drop_duplicates("game_id")[["game_id", "T"]].assign(lead_min=np.nan)
        for family, control in ((FAMILY, False), (CONTROL, True)):
            sig = strength_frame(st, wdw, control)
            cand = side_strength(neutral, sig)
            pls = []
            for r in range(N_PLACEBO):
                sh = H.shuffle_within_date(sig, games, np.random.default_rng(r))
                pls.append(side_strength(neutral, sh))
            rows += H.run_cells(dd, family, wdw, cand, neutral, CUTS, SIDES, close=None, sig=None,
                                placebo=pls, strength="strength", times=times)
            print(f"  graded {family} {wdw}", flush=True)
    cells = pd.DataFrame(rows)
    for c in ("share_still_offered", "units_still_offered", "clv_median", "clv_share_positive",
              "pool_clv_median"):
        if c in cells:
            cells[c] = np.nan
    return cells


def price_ranges(bets_dir: Path, keys: pd.DataFrame) -> dict:
    """Prices of the bets of the given (family, point, side, cut) cells,
    every graded season pooled (2021-22 to 2025-26)."""
    if not bets_dir.exists():
        return {}
    b = pd.concat([pd.read_parquet(p) for p in bets_dir.glob("bets_*.parquet")], ignore_index=True)
    b = b[b["season"].isin(tuple(H.CHOOSE) + (H.CONFIRM,))]
    out = {}
    for _, k in keys.iterrows():
        x = b[(b["family"] == k["family"]) & (b["point"] == k["point"]) & (b["cell_side"] == k["side"])
              & np.isclose(b["cut"], k["cut"])]
        if len(x):
            out[f"{k['family']}|{k['point']}|{k['side']}|{k['cut']}"] = {
                "min": float(x["price"].min()), "median": float(x["price"].median()),
                "max": float(x["price"].max()),
                "record": f"{int((x['result'] == 'W').sum())}-{int((x['result'] == 'L').sum())}-{int((x['result'] == 'P').sum())}",
                "books": x["book"].value_counts().to_dict()}
    return out


def main() -> None:
    from scripts.nba_game2_verdict import house_verdict, HOUSE_BARS
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quotes", default=str(QUOTES))
    ap.add_argument("--info-only", action="store_true")
    a = ap.parse_args()
    pd.set_option("display.width", 250)
    q = pd.read_parquet(a.quotes)
    data = H.load(H.CACHE)
    b = build(q, data)
    print("dist fallback (own season):", b["dist_fallback"])
    print("decision games per season x window:")
    print(b["states"].groupby(["season", "window"]).size().unstack().to_string())
    info = info_test(b)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    INFO.write_text(json.dumps(info, indent=1, default=float), encoding="utf-8")
    print("\ninformation-test rows (Pinnacle's own fresh quotes, population):", info["rows"])
    for p, res in info["panels"].items():
        print(f"\n[{p}] change in squared error of the final total (points^2; below zero = information)")
        for k, v in res.items():
            extra = f"  (baseline mean squared error {v['base_mse']:.1f})" if "base_mse" in v else ""
            print(f"  {k:<18} n {v['n']:>6}  mean {v['mean']:+.3f}  95% {v['lo']:+.3f} .. {v['hi']:+.3f}{extra}")
    print("\ncoefficients per test season and window:")
    for k, v in info["coefs"].items():
        print(" ", k, {kk: round(vv, 4) for kk, vv in v.items()})
    print(f"\nINFORMATION TEST PASSES: {info['passes']}  (2025-26 interval covers zero: "
          f"{info['confirm_covers_zero']})  -> {INFO}")
    if a.info_only or not info["passes"]:
        if not info["passes"]:
            print("IG-1 CLOSED without a grid (7.3).")
        return
    os.environ.setdefault("NBA_GAME2_BETS", str(OUT_DIR / "bets_IG-1"))
    for old in Path(os.environ["NBA_GAME2_BETS"]).glob("bets_*.parquet"):
        old.unlink()                     # a stale run's bets would mix into the price ranges
    cells = grid(b, data)
    assert cells.groupby("family").size().to_dict() == EXPECTED_ROWS, cells.groupby("family").size()
    cells.to_parquet(CELLS, index=False)
    h = house_verdict(cells)
    h.drop(columns=["placebo_rois"]).to_parquet(OUT_DIR / "verdict_house_IG-1.parquet", index=False)
    print(f"\n{len(h)} candidate cells; {int(h['house_passes'].sum())} pass the house standard; "
          f"{int(h['h2_ci95'].sum())} clear the 95% interval alone")
    cols = ["point", "side", "cut", "pool_n", "pool_units", "pool_roi", "pool_ci95_lo", "pool_ci95_hi",
            "pool_seasons_counted", "pool_seasons_positive", "roi_choose", "n_confirm", "roi_confirm",
            "dk_n_choose", "dk_roi_choose", "dk_roi_confirm", "blind_pool_over", "blind_pool_under",
            "house_failed"]
    print(h[cols].to_string(index=False))
    ctl = cells[cells["family"] == CONTROL]
    print("\ncontrol (reported, never judged):")
    print(ctl[[c for c in cols if c != "house_failed"]].to_string(index=False))
    passing = h[h["house_passes"]]
    if len(passing):
        print("\nprice ranges of passing cells:",
              json.dumps(price_ranges(Path(os.environ["NBA_GAME2_BETS"]),
                                      passing[["family", "point", "side", "cut"]]), indent=1))


if __name__ == "__main__":
    main()
