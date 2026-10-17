"""IG-2: a game-state model against the live moneyline and spread.

docs/nba_models_2026.md section 7.2 (the family) and 7.3 (the gate). The
information test runs first; the 18-cell grid runs only for a market whose
information test clears. Every quote, choice, grade and pooled column comes
from scripts/nba_game_harness (H): side_probs, with_ev, choose, grade, roi,
boot, run_cells, shuffle_within_date, pinnacle_close, close_dist, solve_any.

EVERYTHING BELOW WAS WRITTEN AND COMMITTED BEFORE THE INFORMATION TEST OR ANY
CELL WAS RUN (2026-10-17). A later change gets its own dated line.

ELIGIBLE QUOTE (section 7.1's freshness rule, as the staleness gate imposed it)
  A deciding book's in-play quote (config.BEST_LINE_BOOKMAKERS), market h2h or
  spreads, coherent, with a coherent Pinnacle quote in the same fetch stamped
  within 60 s (pin_fa present), no point scored between the quote's stamp and
  served_at, and none between the Pinnacle quote's stamp and served_at.
PHASES
  scripts/nba_ingame_staleness.window_of, unchanged: Q1-Q2 (periods 1-2, live
  or the break after Q1), Q3 (period 3, live or the break after it), Q4 (period
  4, live, clock_s >= 360). Halftime is not an IG-2 phase.
DECISION
  One per (game, market, phase): the FIRST fetch in the phase that carries an
  eligible deciding quote. Every eligible deciding quote in that fetch is an
  offer; harness choose() takes the best-EV one (ties to the earlier book). A
  later fetch in the same phase is never used, whatever its EV (the
  first-signal replay needs the 5-minute archive, section 7.4).
STATE
  Each quote's own row of the shared table (scripts/nba_ingame_data.py): the
  plays ESPN logged at or before its stamp. Nothing after the stamp.
THE MODEL (section 7.2: margin, seconds left, Pinnacle's pre-game close spread
as the prior with Stern 1994 variance, team fouls, top-minute players' fouls)
  f = secs_left / 2880; m = home minus away points so far; mu_pre = the home
  margin Pinnacle's last pre-tip coherent spread implies (H.pinnacle_close,
  solved through H.close_dist, the harness's own pricing); pl = clock_s / 720.
  Remaining home margin R = final margin (official, overtime included) - m.
    E[R] = b1 f mu_pre + b2 f + b3 m + b4 m f                     (Stern core)
         + b5 pen_diff pl + b6 tf_diff pl                          (team fouls)
         + b7 trouble_diff f + b8 out_diff f + b9 top_diff f       (top players)
  pen_diff = [away team fouls in the period >= 5] - [home's]; tf_diff = away
  minus home team fouls in the period; for each side's three top-minute
  starters (nba_ingame_data's TOP PLAYERS): trouble = how many have personal
  fouls >= period + 1, out = how many have >= 6, top = their summed fouls;
  each *_diff is away minus home (a positive value favours home).
  Var(R) = s1 f + s0 (Stern's variance, plus a floor). Weighted least squares,
  weights 1 / Var, two passes; the variance is the least-squares line of the
  squared residuals on f (s0 >= 0.25, s1 > 0).
  The final home margin is Normal(m + E[R], sqrt(Var)): moneyline p_home =
  Phi(mean / sd); a spread offer is priced by H.side_probs (integer continuity,
  pushes at whole numbers).
TRAINING (walk-forward)
  Season S is predicted by a model fit on seasons before S only (fit()
  refuses any row of season >= S). Training rows: every game's state each 30
  s of game time with 360 <= secs_left <= 2850, from the play-by-play built by
  nba_ingame_data's own functions. A game whose play-by-play final differs
  from the official final, or with no Pinnacle pre-game spread close, is left
  out of training (counted). 2020-21 has no earlier season: it is fit on
  itself, graded and reported as in-sample, never pooled or chosen on.

THE INFORMATION TEST (section 7.3), fixed now
  Rows: Pinnacle's own quote at each decision fetch (the one the decision's
  eligible deciding quotes were paired with), one per (game, market, phase),
  state at Pinnacle's stamp. Benchmark: Pinnacle's live no-vig. Moneyline:
  log loss of the home win; spread: squared error of the final home margin,
  Pinnacle's implied margin solved from its own number and no-vig with the
  model's sd at that state (H.solve_any).
  For each season S in 2022..2026, both stacks are fit on the test rows of
  seasons before S; every row carries its own season's walk-forward model
  (2020-21's rows its in-sample one):
    base      logistic y ~ 1 + logit(Pinnacle)            | OLS margin ~ 1 + mu_pin
    combined  logistic y ~ 1 + logit(Pinnacle) + logit(model) | OLS ~ 1 + mu_pin + mu_model
  The change is combined minus base on season S (negative = the model adds
  information), averaged per row, whole-day bootstrap 95% interval, 4,000
  resamples, seed 7, on 2022-2025 pooled and on 2026 alone.
  READING: a market has information only when BOTH intervals lie wholly below
  zero. A market without it is closed and its 9 cells are not graded. The
  family is closed when both markets are.
  REPORTED BESIDE, never the gate (declared now, before any result):
    (a) the same stacked test with each eligible deciding quote at the decision
        fetch against its OWN no-vig (the books whose prices are bet);
    (b) the Stern core alone (b1-b4) against Pinnacle, the same test;
    (c) the raw Pinnacle loss (no recalibration) and the model's own loss.

THE GRID (section 7.2: 2 markets x 3 phases x EV >= 0.02 / 0.05 / 0.08 = 18)
  Side: the side the model favours, per game = the side whose best deciding
  offer has the higher model EV (H.side_mask's per-game side "model", column
  side_pick). Price: best of the 8 deciding books, -200 floor, DraftKings alone
  beside (H.run_cells). The market's fair line for the blind bets: Pinnacle's
  live no-vig at the paired quote (spread mean solved at its own number with
  the offer's model sd).
  Placebo (20 runs, rng seed = run number, as the second search's labs): the
  model's disagreement with Pinnacle at the decision (logit points for the
  moneyline, margin points for the spread, at Pinnacle's state) is shuffled
  between games on the same date and market by H.shuffle_within_date and added
  back to each game's own Pinnacle fair line. Pinnacle's line is never shuffled.
  Not defined in play, emitted as NaN: still offered at the next fetch (an
  hour later the game is elsewhere) and closing-line value.
  For every cell that passes the house standard (scripts/nba_game2_verdict.
  house_verdict), reported beside: the price range, and units split by whether
  the bet's side outscored its opponent in the 120 s before the stamp (the
  deciding books' own moneyline lag the freshness rule does not remove).

    PYTHONPATH=. NBA_RESEARCH_CACHE=<v2> python -m scripts.nba_ingame_ig2 --info
    PYTHONPATH=. NBA_RESEARCH_CACHE=<v2> python -m scripts.nba_ingame_ig2 --grid
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import nba_game_harness as H  # noqa: E402
from scripts.nba_game_market_lab import norm_cdf, threshold  # noqa: E402
from scripts.nba_ingame_data import OUT, OUT_DIR  # noqa: E402
from scripts.nba_ingame_staleness import window_of  # noqa: E402

FAMILY = "IG-2"
PHASES = ("Q1-Q2", "Q3", "Q4")
_WINDOW = {"Q1-Q2": "Q1-Q2", "Q3": "Q3", "Q4": "Q4 6+ min"}
MARKETS = ("h2h", "spreads")
CUTS = (0.02, 0.05, 0.08)
GRADED = (2022, 2023, 2024, 2025, 2026)
FIT_FROM = 2021
GRID_STEP_S = 30
TRAIN_SECS = (360, 2850)
REG_S, PERIOD_S = 2880.0, 720.0
S0_FLOOR = 0.25
N_PLACEBO = 20
CORE = ["x_mu_pre", "x_f", "x_m", "x_mf"]
FOULS = ["x_pen", "x_tf", "x_trouble", "x_out", "x_top"]
FEATURES = CORE + FOULS
TRAIN_CACHE = OUT_DIR / "ig2_train_states.parquet"
PRIOR_CACHE = OUT_DIR / "ig2_prior.parquet"
CELLS_OUT = OUT_DIR / "cells_IG-2.parquet"
INFO_OUT = OUT_DIR / "ig2_info.json"
BETS_DIR = OUT_DIR / "ig2_bets"


# ── eligibility and the decision ───────────────────────────────────────────

def phase_label(q: pd.DataFrame) -> pd.Series:
    """'Q1-Q2' / 'Q3' / 'Q4' from the staleness module's windows; '' outside."""
    w = window_of(q)
    return pd.Series(np.select([w[_WINDOW[p]].to_numpy() for p in PHASES], list(PHASES), ""),
                     index=q.index)


def with_pin_freshness(q: pd.DataFrame) -> pd.DataFrame:
    """pin_pts_since: points scored between the paired Pinnacle quote's stamp
    and its served_at (from Pinnacle's own row in the same fetch)."""
    pin = q[q["book"] == H.SHARP].set_index(["game_id", "market", "fetch_at", "stamp"])
    pin = pin[~pin.index.duplicated()]["pts_since_stamp"]
    key = pd.MultiIndex.from_frame(q[["game_id", "market", "fetch_at", "pin_stamp"]])
    return q.assign(pin_pts_since=pin.reindex(key).to_numpy())


def eligible(q: pd.DataFrame) -> pd.DataFrame:
    """Deciding-book quotes that pass section 7.1's freshness rule, in a phase."""
    if "pin_pts_since" not in q:
        q = with_pin_freshness(q)
    if "phase_ig2" not in q:
        q = q.assign(phase_ig2=phase_label(q))
    m = (q["book"].isin(H.BETTABLE) & q["market"].isin(MARKETS) & q["coherent"].astype(bool)
         & q["pin_fa"].notna() & (q["pts_since_stamp"] == 0) & (q["pin_pts_since"] == 0)
         & (q["phase_ig2"] != ""))
    return q[m].copy()


def decision_quotes(el: pd.DataFrame) -> pd.DataFrame:
    """The eligible quotes of the FIRST eligible fetch per (game, market, phase)."""
    first = el.groupby(["game_id", "market", "phase_ig2"])["fetch_at"].transform("min")
    return el[el["fetch_at"] == first].copy()


# ── the pre-game prior ─────────────────────────────────────────────────────

def pregame_prior(cache: Path = H.CACHE, refresh: bool = False) -> pd.DataFrame:
    """(game_id, season, mu_pre): the home margin Pinnacle's pre-tip spread close
    implies, solved through the harness's walk-forward empirical distribution."""
    if PRIOR_CACHE.exists() and not refresh:
        return pd.read_parquet(PRIOR_CACHE)
    data = H.load(cache)
    close = H.pinnacle_close(data)
    dist = H.close_dist(close, data.games)
    c = close[close["market"] == "spreads"].copy()
    sig = np.array([dist.get((int(s), "spreads")) for s in c["season"]], dtype=object)
    ok = np.array([v is not None for v in sig])
    c = c[ok]
    c["mu_pre"] = H.solve_any(threshold("spreads", c["close_line"]), c["close_fa"].to_numpy(), sig[ok])
    out = c[["game_id", "season", "mu_pre"]].reset_index(drop=True)
    out.to_parquet(PRIOR_CACHE, index=False)
    return out


# ── features and the state model ───────────────────────────────────────────

def features(df: pd.DataFrame) -> pd.DataFrame:
    """The model's inputs (module docstring) from a state frame carrying
    secs_left, clock_s, period, h_pts, a_pts, mu_pre, team fouls in the period
    and the top players' fouls. Adds x_* columns, m and f."""
    f = df["secs_left"].to_numpy(float) / REG_S
    pl = df["clock_s"].to_numpy(float) / PERIOD_S
    m = (df["h_pts"] - df["a_pts"]).to_numpy(float)
    per = df["period"].to_numpy(float)
    htf, atf = df["h_tf_period"].fillna(0).to_numpy(float), df["a_tf_period"].fillna(0).to_numpy(float)
    ht = np.column_stack([df[f"h_top{k}_pf"].fillna(0).to_numpy(float) for k in (1, 2, 3)])
    at = np.column_stack([df[f"a_top{k}_pf"].fillna(0).to_numpy(float) for k in (1, 2, 3)])
    trouble = (at >= per[:, None] + 1).sum(1) - (ht >= per[:, None] + 1).sum(1)
    out_ = (at >= 6).sum(1) - (ht >= 6).sum(1)
    top = at.sum(1) - ht.sum(1)
    return df.assign(
        f=f, m=m,
        x_mu_pre=f * df["mu_pre"].to_numpy(float), x_f=f, x_m=m, x_mf=m * f,
        x_pen=((atf >= 5).astype(float) - (htf >= 5).astype(float)) * pl,
        x_tf=(atf - htf) * pl,
        x_trouble=trouble * f, x_out=out_ * f, x_top=top * f)


class StateModel:
    """Final home margin ~ Normal(m + X b, sqrt(s1 f + s0)), fit on seasons < S."""

    def __init__(self, cols=FEATURES):
        self.cols = list(cols)
        self.beta = self.s1 = self.s0 = None
        self.S = None
        self.n_train = 0

    def fit(self, train: pd.DataFrame, S: int, allow_own_season: bool = False) -> "StateModel":
        seasons = set(int(s) for s in train["season"].unique())
        if allow_own_season:
            if seasons != {S}:
                raise ValueError(f"an in-sample fit takes season {S} alone, got {sorted(seasons)}")
        elif any(s >= S for s in seasons):
            raise ValueError(f"walk-forward: a model for season {S} cannot see seasons {sorted(seasons)}")
        X = train[self.cols].to_numpy(float)
        y = (train["final_margin"] - train["m"]).to_numpy(float)
        f = train["f"].to_numpy(float)
        w = 1.0 / np.maximum(f, 1e-3)
        for _ in range(2):
            sw = np.sqrt(w)
            self.beta = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)[0]
            r2 = (y - X @ self.beta) ** 2
            A = np.column_stack([f, np.ones_like(f)])
            s1, s0 = np.linalg.lstsq(A, r2, rcond=None)[0]
            self.s1, self.s0 = max(float(s1), 1e-6), max(float(s0), S0_FLOOR)
            w = 1.0 / (self.s1 * f + self.s0)
        self.S, self.n_train = S, len(train)
        return self

    def predict(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """(mean final home margin, sd) at each state."""
        mean = df["m"].to_numpy(float) + df[self.cols].to_numpy(float) @ self.beta
        sd = np.sqrt(self.s1 * df["f"].to_numpy(float) + self.s0)
        return mean, sd

    def p_home(self, df: pd.DataFrame) -> np.ndarray:
        return p_home_from(*self.predict(df))


def p_home_from(mean, sd) -> np.ndarray:
    return norm_cdf(np.asarray(mean, float) / np.asarray(sd, float))


# ── training states from the play-by-play ──────────────────────────────────

def grid_states(tl: pd.DataFrame, step: int = GRID_STEP_S, secs=TRAIN_SECS) -> pd.DataFrame:
    """Each game's state every `step` s of regulation game time: the latest play
    (by game time) at or before it, keeping secs_left in [secs[0], secs[1]]."""
    s = tl.dropna(subset=["game_s"]).sort_values(["game_s", "wc", "play_no"], kind="stable")
    g = np.arange(step, int(REG_S), step, dtype=float)
    left = pd.DataFrame({"game_id": np.repeat(s["game_id"].unique(), len(g)),
                         "g": np.tile(g, s["game_id"].nunique())}).sort_values("g", kind="stable")
    x = pd.merge_asof(left, s, left_on="g", right_on="game_s", by="game_id", direction="backward")
    x = x.dropna(subset=["period"])
    x = x[x["period"] <= 4]
    x["secs_left"] = x["clock_s"] + PERIOD_S * (4 - x["period"])
    x = x[(x["secs_left"] >= secs[0]) & (x["secs_left"] <= secs[1])]
    return x.drop_duplicates(["game_id", "play_no"]).drop(columns="g").reset_index(drop=True)


def training_states(cache: Path = H.CACHE, seasons=(2021, 2022, 2023, 2024, 2025),
                    refresh: bool = False) -> tuple[pd.DataFrame, dict]:
    """Grid states with features and the official final margin, per season.
    Built by nba_ingame_data's own play, top-player and timeline functions."""
    if TRAIN_CACHE.exists() and not refresh:
        t = pd.read_parquet(TRAIN_CACHE)
        notes = json.loads((TRAIN_CACHE.with_suffix(".json")).read_text(encoding="utf-8"))
        return t, notes
    from scripts import nba_ingame_data as D
    games = H.load_games(cache)
    emap = D.espn_map(cache)
    prior = D.prior_minutes(seasons)
    mu = pregame_prior(cache)
    frames, notes = [], {}
    for s in seasons:
        t0 = time.time()
        want = emap[emap["game_id"].isin(set(games.loc[games["season"] == s, "game_id"]))]
        plays, box, n = D.season_plays(s, want, games)
        tl = D.timeline(plays, D.top_players(box, prior))
        fin = plays.groupby(["game_id", "team_side"])["points"].sum().unstack()
        gg = games.set_index("game_id").reindex(fin.index)
        ok = set(fin.index[(fin[D.HOME] == gg["home_score"]) & (fin[D.AWAY] == gg["away_score"])])
        st = grid_states(tl)
        n_games = st["game_id"].nunique()
        st = st[st["game_id"].isin(ok)]
        st = st.merge(mu[["game_id", "mu_pre"]], on="game_id", how="inner")
        g2 = games.set_index("game_id")
        st["season"] = s
        st["final_margin"] = st["game_id"].map(g2["home_score"] - g2["away_score"])
        frames.append(features(st))
        notes[str(s)] = {"games_pbp": int(plays["game_id"].nunique()), "games_grid": int(n_games),
                         "games_final_mismatch": int(n_games - len(ok & set(tl["game_id"]))),
                         "games_kept": int(st["game_id"].nunique()), "states": int(len(st)),
                         "seconds": round(time.time() - t0)}
        print(f"training states {s}: {notes[str(s)]}", flush=True)
    t = pd.concat(frames, ignore_index=True)
    keep = ["game_id", "season", "period", "clock_s", "secs_left", "h_pts", "a_pts", "mu_pre",
            "final_margin", "f", "m", *FEATURES]
    t = t[keep]
    t.to_parquet(TRAIN_CACHE, index=False)
    TRAIN_CACHE.with_suffix(".json").write_text(json.dumps(notes, indent=1), encoding="utf-8")
    return t, notes


def models_by_season(train: pd.DataFrame, cols=FEATURES, seasons=(FIT_FROM, *GRADED)) -> dict:
    """season -> StateModel fit on seasons before it (2021: on itself, in-sample)."""
    out = {}
    for S in seasons:
        prior = train[train["season"] < S]
        if len(prior):
            out[S] = StateModel(cols).fit(prior, S)
        else:
            out[S] = StateModel(cols).fit(train[train["season"] == S], S, allow_own_season=True)
    return out


def apply_model(df: pd.DataFrame, models: dict, prefix: str = "") -> pd.DataFrame:
    """mean / sd / p_home per row from its own season's model."""
    mean = np.full(len(df), np.nan)
    sd = np.full(len(df), np.nan)
    for S, mdl in models.items():
        k = (df["season"] == S).to_numpy()
        if k.any():
            mean[k], sd[k] = mdl.predict(df[k])
    return df.assign(**{f"{prefix}mean": mean, f"{prefix}sd": sd,
                        f"{prefix}p_home": p_home_from(mean, sd)})


# ── the information test ───────────────────────────────────────────────────

def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _expit(z):
    return 1.0 / (1.0 + np.exp(-np.asarray(z, float)))


def fit_logistic(X: np.ndarray, y: np.ndarray, iters: int = 50) -> np.ndarray:
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = _expit(X @ b)
        W = p * (1 - p)
        Hs = X.T @ (X * W[:, None]) + 1e-9 * np.eye(X.shape[1])
        step = np.linalg.solve(Hs, X.T @ (y - p))
        b = b + step
        if np.max(np.abs(step)) < 1e-10:
            break
    return b


def _design(df: pd.DataFrame, cols) -> np.ndarray:
    return np.column_stack([np.ones(len(df))] + [df[c].to_numpy(float) for c in cols])


def stacked_losses(rows: pd.DataFrame, kind: str, base: str, model: str, S: int) -> pd.DataFrame:
    """Season S rows with per-row losses of base and combined stacks, both fit on
    rows of seasons < S. kind 'll' (y, logit columns) or 'se' (y_margin)."""
    tr, te = rows[rows["season"] < S], rows[rows["season"] == S]
    if len(tr) < 50 or len(te) == 0:
        raise ValueError(f"season {S}: {len(tr)} training rows, {len(te)} test rows")
    if kind == "ll":
        y_tr, y_te = tr["y"].to_numpy(float), te["y"].to_numpy(float)
        bb = fit_logistic(_design(tr, [base]), y_tr)
        bc = fit_logistic(_design(tr, [base, model]), y_tr)
        pb = np.clip(_expit(_design(te, [base]) @ bb), 1e-6, 1 - 1e-6)
        pc = np.clip(_expit(_design(te, [base, model]) @ bc), 1e-6, 1 - 1e-6)
        praw = np.clip(_expit(te[base].to_numpy(float)), 1e-6, 1 - 1e-6)
        pm = np.clip(_expit(te[model].to_numpy(float)), 1e-6, 1 - 1e-6)
        ll = lambda p: -(y_te * np.log(p) + (1 - y_te) * np.log(1 - p))  # noqa: E731
        lb, lc, lraw, lm = ll(pb), ll(pc), ll(praw), ll(pm)
    else:
        y_tr, y_te = tr["y_margin"].to_numpy(float), te["y_margin"].to_numpy(float)
        bb = np.linalg.lstsq(_design(tr, [base]), y_tr, rcond=None)[0]
        bc = np.linalg.lstsq(_design(tr, [base, model]), y_tr, rcond=None)[0]
        lb = (y_te - _design(te, [base]) @ bb) ** 2
        lc = (y_te - _design(te, [base, model]) @ bc) ** 2
        lraw = (y_te - te[base].to_numpy(float)) ** 2
        lm = (y_te - te[model].to_numpy(float)) ** 2
    return te.assign(loss_base=lb, loss_comb=lc, loss_raw=lraw, loss_model=lm,
                     delta=lc - lb, coef_model=bc[-1])


def delta_ci(df: pd.DataFrame, col: str = "delta", n_boot: int = H.N_BOOT, seed: int = H.SEED) -> dict:
    """Mean of `col` per row and its whole-day bootstrap 95% interval."""
    if len(df) == 0:
        return {"n": 0, "mean": np.nan, "lo": np.nan, "hi": np.nan}
    s = df.groupby("game_date")[col].agg(["sum", "size"])
    rng = np.random.default_rng(seed)
    S_, N_ = s["sum"].to_numpy(), s["size"].to_numpy()
    out = np.empty(n_boot)
    step = max(1, 2_000_000 // max(len(s), 1))
    for i in range(0, n_boot, step):
        k = min(step, n_boot - i)
        idx = rng.integers(0, len(s), size=(k, len(s)))
        out[i:i + k] = S_[idx].sum(1) / N_[idx].sum(1)
    lo, hi = np.percentile(out, [2.5, 97.5])
    return {"n": int(len(df)), "games": int(df["game_id"].nunique()), "days": int(len(s)),
            "mean": float(df[col].mean()), "lo": float(lo), "hi": float(hi)}


def has_information(choose: dict, confirm: dict) -> bool:
    """The pre-declared reading: both intervals wholly below zero."""
    return bool(choose["hi"] < 0 and confirm["hi"] < 0)


def benchmark_columns(rows: pd.DataFrame, fa_col: str, line_col: str) -> pd.DataFrame:
    """y / y_margin, the benchmark's logit and implied margin, and the model's."""
    y_margin = (rows["final_home"] - rows["final_away"]).to_numpy(float)
    sp = (rows["market"] == "spreads").to_numpy()
    mu_b = np.full(len(rows), np.nan)
    if sp.any():
        r = rows[sp]
        mu_b[sp] = H.solve_any(threshold("spreads", r[line_col]), r[fa_col].to_numpy(float),
                               r["sd"].to_numpy(float))
    return rows.assign(y=(y_margin > 0).astype(float), y_margin=y_margin,
                       bench_logit=_logit(rows[fa_col]), bench_mu=mu_b,
                       model_logit=_logit(rows["p_home"]), model_mu=rows["mean"])


def run_stack(rows: pd.DataFrame, label: str) -> list[dict]:
    """Every season's stacked losses, then the pooled and 2026 intervals per market."""
    out = []
    for mk, kind, base, mdl in (("h2h", "ll", "bench_logit", "model_logit"),
                                ("spreads", "se", "bench_mu", "model_mu")):
        r = rows[rows["market"] == mk]
        per = pd.concat([stacked_losses(r, kind, base, mdl, S) for S in GRADED], ignore_index=True)
        for name, sub in (("choose 2022-2025", per[per["season"].isin(H.CHOOSE)]),
                          ("2026", per[per["season"] == H.CONFIRM])):
            d = delta_ci(sub)
            out.append({"test": label, "market": mk, "loss": "log loss" if kind == "ll" else "sq error",
                        "seasons": name, **d,
                        "loss_raw_pinnacle": float(sub["loss_raw"].mean()),
                        "loss_base": float(sub["loss_base"].mean()),
                        "loss_comb": float(sub["loss_comb"].mean()),
                        "loss_model_alone": float(sub["loss_model"].mean()),
                        "raw_minus_comb": float((sub["loss_comb"] - sub["loss_raw"]).mean())})
        for S in GRADED:
            sub = per[per["season"] == S]
            out.append({"test": label, "market": mk, "loss": "log loss" if kind == "ll" else "sq error",
                        "seasons": str(S), **delta_ci(sub, n_boot=1000),
                        "coef_model": float(sub["coef_model"].iloc[0]) if len(sub) else np.nan})
    return out


def load_table(path: Path = OUT) -> pd.DataFrame:
    q = pd.read_parquet(path)
    q = q[q["market"].isin(MARKETS)].copy()
    return with_pin_freshness(q).assign(phase_ig2=lambda d: phase_label(d))


def info_rows(q: pd.DataFrame, dec: pd.DataFrame) -> pd.DataFrame:
    """Pinnacle's own row for each decision (game, market, phase), state at its stamp."""
    k = dec[["game_id", "market", "phase_ig2", "fetch_at", "pin_stamp"]].drop_duplicates(
        ["game_id", "market", "phase_ig2"])
    pin = q[q["book"] == H.SHARP].drop(columns=["phase_ig2"])
    r = k.merge(pin, left_on=["game_id", "market", "fetch_at", "pin_stamp"],
                right_on=["game_id", "market", "fetch_at", "stamp"], how="inner")
    return r


def info_test(q: pd.DataFrame, train: pd.DataFrame, prior: pd.DataFrame) -> dict:
    el = eligible(q)
    dec = decision_quotes(el)
    dec = dec.merge(prior[["game_id", "mu_pre"]], on="game_id", how="inner")
    no_prior = ~el["game_id"].isin(set(prior["game_id"]))
    res = {"decisions": {f"{s}|{mk}|{ph}": int(n) for (s, mk, ph), n in
                         dec.drop_duplicates(["game_id", "market", "phase_ig2"])
                         .groupby(["season", "market", "phase_ig2"]).size().items()},
           "decisions_no_prior": int(el[no_prior].drop_duplicates(["game_id", "market", "phase_ig2"]).shape[0])}
    rows = []
    for label, cols in (("IG-2 model vs Pinnacle (the gate)", FEATURES),
                        ("(b) Stern core alone vs Pinnacle", CORE)):
        models = models_by_season(train, cols)
        ir = features(info_rows(q, dec).merge(prior[["game_id", "mu_pre"]], on="game_id", how="inner"))
        ir = benchmark_columns(apply_model(ir, models), "fa", "line")
        rows += run_stack(ir, label)
        if cols is FEATURES:
            res["info_rows"] = int(len(ir))
            res["model_coefs"] = {str(S): dict(zip(cols, np.round(m.beta, 4).tolist()))
                                  | {"s1": round(m.s1, 2), "s0": round(m.s0, 2), "n_train": m.n_train}
                                  for S, m in models.items()}
            ir["season"] = ir["season"].astype(int)
            cal = ir[ir["market"] == "h2h"].assign(bin=lambda d: pd.cut(d["p_home"], np.linspace(0, 1, 11)))
            res["calibration_h2h"] = (cal[cal["season"].isin(GRADED)].groupby("bin", observed=True)
                                      .agg(n=("y", "size"), model=("p_home", "mean"), won=("y", "mean"))
                                      .round(3).reset_index().astype({"bin": str}).to_dict("records"))
            dk = features(dec)
            dk = benchmark_columns(apply_model(dk, models), "fa", "line")
            rows += run_stack(dk, "(a) IG-2 model vs each deciding book's own no-vig")
    res["rows"] = rows
    return res


# ── the grid ───────────────────────────────────────────────────────────────

def offer_rows(dec: pd.DataFrame) -> pd.DataFrame:
    """Two rows per decision quote (home/away), with T = served_at and the
    points each side scored in the 120 s before the stamp."""
    base = dec.assign(T=dec["served_at"], pts120_h=dec["h_pts"] - dec["h_pts_m120"],
                      pts120_a=dec["a_pts"] - dec["a_pts_m120"])
    a = base.assign(side="home", price=base["price_a"])
    b = base.assign(side="away", price=base["price_b"])
    return pd.concat([a, b], ignore_index=True)


def priced(off: pd.DataFrame, mean, sd, p_home) -> pd.DataFrame:
    pw, pp = H.side_probs(off["market"].to_numpy(), off["side"].to_numpy(), off["line"].to_numpy(),
                          mu=np.asarray(mean, float), sigma=np.asarray(sd, float),
                          p_home=np.asarray(p_home, float))
    return H.with_ev(off.assign(p_win=pw, p_push=pp))


def with_side_pick(c: pd.DataFrame) -> pd.DataFrame:
    """side_pick per (game, market): the side whose best deciding offer has the
    higher EV under `c`'s own prices (the side the model favours)."""
    best = c[c["book"].isin(H.BETTABLE)].groupby(["game_id", "market", "side"])["ev"].max().unstack()
    pick = pd.Series(np.where(best["home"].fillna(-np.inf) >= best["away"].fillna(-np.inf), "home", "away"),
                     index=best.index, name="side_pick").reset_index()
    return c.drop(columns="side_pick", errors="ignore").merge(pick, on=["game_id", "market"], how="left")


def market_fair_inplay(off: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Pinnacle's live no-vig as (mean home margin, p_home) per offer row; the
    spread mean is solved at Pinnacle's own number with the row's model sd."""
    sp = (off["market"] == "spreads").to_numpy()
    mu = np.full(len(off), np.nan)
    if sp.any():
        r = off[sp]
        mu[sp] = H.solve_any(threshold("spreads", r["pin_line"]), r["pin_fa"].to_numpy(float),
                             r["sd"].to_numpy(float))
    ph = np.where(sp, np.nan, off["pin_fa"].to_numpy(float))
    return mu, ph


def grid_frames(dec: pd.DataFrame, models: dict, games: pd.DataFrame, n_placebo: int = N_PLACEBO):
    """(cand, neutral, placebo frames) for one phase's decisions."""
    d = apply_model(features(dec), models)
    off = offer_rows(d)
    mu_m, ph_m = market_fair_inplay(off)
    cand = with_side_pick(priced(off, off["mean"], off["sd"], off["p_home"]))
    neutral = priced(off, mu_m, off["sd"], ph_m).assign(mu=mu_m, p_home=ph_m)
    neutral = neutral.drop(columns="side_pick", errors="ignore").merge(
        cand[["game_id", "market", "side_pick"]].drop_duplicates(["game_id", "market"]),
        on=["game_id", "market"], how="left")
    # the model's disagreement with Pinnacle, per (game, market), at Pinnacle's state
    first = off.drop_duplicates(["game_id", "market"])
    dev = pd.DataFrame({"game_id": first["game_id"].to_numpy(), "market": first["market"].to_numpy()})
    mu_f, _ = market_fair_inplay(first.assign(sd=first["pin_sd"]))
    dev["strength"] = np.where(first["market"] == "spreads", first["pin_mean"] - mu_f,
                               _logit(first["pin_p_home"]) - _logit(first["pin_fa"]))
    placebo = []
    for r in range(n_placebo):
        sh = H.shuffle_within_date(dev, games, np.random.default_rng(r))
        s = off[["game_id", "market"]].merge(sh, on=["game_id", "market"], how="left")["strength"].to_numpy()
        mean_p = np.where(off["market"] == "spreads", mu_m + s, np.nan)
        ph_p = np.where(off["market"] == "spreads", np.nan, _expit(_logit(off["pin_fa"]) + s))
        placebo.append(with_side_pick(priced(off, mean_p, off["sd"], ph_p)))
    return cand, neutral, placebo


def pin_state_model(q: pd.DataFrame, dec: pd.DataFrame, models: dict, prior: pd.DataFrame) -> pd.DataFrame:
    """The model at Pinnacle's own state for each decision: pin_mean, pin_p_home."""
    ir = features(info_rows(q, dec).merge(prior[["game_id", "mu_pre"]], on="game_id", how="inner"))
    ir = apply_model(ir, models)
    return ir[["game_id", "market", "phase_ig2", "mean", "sd", "p_home"]].rename(
        columns={"mean": "pin_mean", "sd": "pin_sd", "p_home": "pin_p_home"})


def run_grid(q: pd.DataFrame, train: pd.DataFrame, prior: pd.DataFrame, markets,
             n_placebo: int = N_PLACEBO) -> pd.DataFrame:
    games = H.load_games(H.CACHE)
    empty_q = pd.DataFrame({c: pd.Series(dtype=object) for c in
                            ("game_id", "season", "game_date", "tip", "market", "book", "snapshot_at",
                             "line", "price_a", "price_b", "coherent")})
    empty_q["fetch_at"] = pd.Series(dtype="datetime64[ns, UTC]")
    empty_f = pd.DataFrame({"game_id": pd.Series(dtype=object), "tip": pd.Series(dtype="datetime64[ns, UTC]"),
                            "fetch_at": pd.Series(dtype="datetime64[ns, UTC]"),
                            "lead_min": pd.Series(dtype=float)})
    data = H.Data(games=games, quotes=empty_q, fetches=empty_f)
    models = models_by_season(train, FEATURES)
    dec_all = decision_quotes(eligible(q)).merge(prior[["game_id", "mu_pre"]], on="game_id", how="inner")
    dec_all = dec_all[dec_all["market"].isin(markets)]
    pin_m = pin_state_model(q, dec_all, models, prior)
    rows = []
    for ph in PHASES:
        dec = dec_all[dec_all["phase_ig2"] == ph].merge(pin_m, on=["game_id", "market", "phase_ig2"], how="inner")
        cand, neutral, placebo = grid_frames(dec, models, games, n_placebo)
        times = dec.drop_duplicates("game_id")[["game_id", "served_at"]].rename(columns={"served_at": "T"})
        sides = {mk: ["model"] for mk in markets}
        r = H.run_cells(data, FAMILY, ph, cand, neutral, CUTS, sides, close=None, sig=None,
                        placebo=placebo, times=times)
        rows += r
        print(f"phase {ph}: {len(r)} cells", flush=True)
    cells = pd.DataFrame(rows)
    for c in ("share_still_offered", "units_still_offered", "clv_median", "clv_share_positive",
              "pool_clv_median"):
        cells[c] = np.nan
    cells["clv_n"] = 0
    return cells


def passing_detail(q: pd.DataFrame, train: pd.DataFrame, prior: pd.DataFrame, passing: pd.DataFrame) -> list[dict]:
    """Price range and the 120-s split for each passing cell (bets rebuilt by the
    same choose/grade the cell used)."""
    games = H.load_games(H.CACHE)
    models = models_by_season(train, FEATURES)
    dec_all = decision_quotes(eligible(q)).merge(prior[["game_id", "mu_pre"]], on="game_id", how="inner")
    pin_m = pin_state_model(q, dec_all, models, prior)
    out = []
    for _, c in passing.iterrows():
        dec = dec_all[(dec_all["phase_ig2"] == c["point"]) & (dec_all["market"] == c["market"])].merge(
            pin_m, on=["game_id", "market", "phase_ig2"], how="inner")
        cand, _, _ = grid_frames(dec, models, games, n_placebo=0)
        b = H.grade(H.choose(cand, c["cut"], sides=["model"]), games)
        b = b[b["season"].isin(GRADED)].reset_index(drop=True)
        side_pts = np.where(b["side"] == "home", b["pts120_h"] - b["pts120_a"], b["pts120_a"] - b["pts120_h"])
        hot = side_pts > 0
        outl = H.outlier_flag(b, cand).to_numpy()
        dog = (b["price"] > 0).to_numpy()
        res = b["result"]
        out.append({"cell": f"{c['point']}|{c['market']}|ev>={c['cut']}", "bets": int(len(b)),
                    "units": float(b["units"].sum()), "roi": H.roi(b),
                    "won_lost_push": f"{int((res == 'W').sum())}-{int((res == 'L').sum())}-{int((res == 'P').sum())}",
                    "price_min": float(b["price"].min()), "price_median": float(b["price"].median()),
                    "price_max": float(b["price"].max()),
                    "units_side_outscored_last_120s": float(b.loc[hot, "units"].sum()), "n_hot": int(hot.sum()),
                    "units_otherwise": float(b.loc[~hot, "units"].sum()), "n_other": int((~hot).sum()),
                    "roi_hot": H.roi(b[hot]) if hot.any() else np.nan,
                    "roi_other": H.roi(b[~hot]) if (~hot).any() else np.nan,
                    "share_outlier": float(outl.mean()), "units_without_outliers": float(b.loc[~outl, "units"].sum()),
                    "n_underdog": int(dog.sum()), "units_underdog": float(b.loc[dog, "units"].sum()),
                    "units_by_book": {k: round(float(v), 2) for k, v in b.groupby("book")["units"].sum().items()},
                    "bets_by_book": {k: int(v) for k, v in b["book"].value_counts().items()}})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--info", action="store_true", help="the information test (section 7.3)")
    ap.add_argument("--grid", action="store_true", help="the 18 cells, for markets with information")
    ap.add_argument("--markets", default=None, help="override: comma list (default: from --info result)")
    ap.add_argument("--refresh", action="store_true", help="rebuild the training-state and prior caches")
    ap.add_argument("--detail", action="store_true",
                    help="beside-numbers for the cells that passed (reads the saved verdict)")
    a = ap.parse_args()
    H.check()
    pd.set_option("display.width", 250)
    prior = pregame_prior(H.CACHE, refresh=a.refresh)
    train, notes = training_states(H.CACHE, refresh=a.refresh)
    q = load_table()
    if a.info:
        res = info_test(q, train, prior)
        res["training"] = notes
        INFO_OUT.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
        t = pd.DataFrame(res["rows"])
        print(t.round(5).to_string(index=False))
        gate = t[t["test"].str.startswith("IG-2")]
        verdict = {}
        for mk in MARKETS:
            ch = gate[(gate["market"] == mk) & (gate["seasons"] == "choose 2022-2025")].iloc[0]
            cf = gate[(gate["market"] == mk) & (gate["seasons"] == "2026")].iloc[0]
            verdict[mk] = has_information(ch, cf)
        print("\nINFORMATION (both intervals wholly below zero):", verdict)
        print("calibration (moneyline, graded seasons):", res["calibration_h2h"])
        print("decisions:", res["decisions"], " without a pre-game prior:", res["decisions_no_prior"])
    if a.detail:
        h = pd.read_parquet(OUT_DIR / "verdict_house_IG-2.parquet")
        det = passing_detail(q, train, prior, h[h["house_passes"]])
        for d in det:
            print(json.dumps(d, default=float))
        (OUT_DIR / "ig2_passing_detail.json").write_text(json.dumps(det, indent=1, default=float),
                                                         encoding="utf-8")
    if a.grid:
        if a.markets:
            markets = tuple(a.markets.split(","))
        else:
            res = json.loads(INFO_OUT.read_text(encoding="utf-8"))
            t = pd.DataFrame(res["rows"])
            gate = t[t["test"].str.startswith("IG-2")]
            markets = tuple(mk for mk in MARKETS if has_information(
                gate[(gate["market"] == mk) & (gate["seasons"] == "choose 2022-2025")].iloc[0],
                gate[(gate["market"] == mk) & (gate["seasons"] == "2026")].iloc[0]))
        if not markets:
            print("no market has information: IG-2 is closed without a grid")
            return
        os.environ.setdefault("NBA_GAME2_BETS", str(BETS_DIR))
        cells = run_grid(q, train, prior, markets)
        cells.to_parquet(CELLS_OUT, index=False)
        from scripts.nba_game2_verdict import HOUSE_BARS, house_verdict
        h = house_verdict(cells)
        h.drop(columns=["placebo_rois"]).to_parquet(OUT_DIR / "verdict_house_IG-2.parquet", index=False)
        cols = ["point", "market", "cut", "pool_n", "pool_units", "pool_roi", "pool_ci95_lo", "pool_ci95_hi",
                "pool_seasons_counted", "pool_seasons_positive", "roi_choose", "roi_confirm", "n_confirm",
                "dk_roi_choose", "dk_roi_confirm", "blind_roi_choose", *HOUSE_BARS, "house_passes"]
        print(h[cols].round(4).to_string(index=False))
        print(f"\n{len(h)} cells; {int(h['house_passes'].sum())} pass the house standard")
        p = h[h["house_passes"]]
        if len(p):
            det = passing_detail(q, train, prior, p)
            print(pd.DataFrame(det).round(4).to_string(index=False))
            (OUT_DIR / "ig2_passing_detail.json").write_text(json.dumps(det, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
