"""P1 of the fourth NBA search: the market-anchored model (the NHL recipe), 128 cells.

docs/nba_models_2026.md section 8 registers the family; section 8.1 fixes every
choice the row leaves open, written and committed before any P1 cell was graded.
This lab EMITS cells through the shared harness (scripts/nba_game_harness.py,
H); scripts/nba_game2_verdict.py (house_verdict) judges them. Every quote,
decision time, market fair line, choice of bet and grade is the harness's.
No penalty, cut or rule here was chosen from a betting result.

THE MODEL (models/nhl_moneyline_anchored.py's recipe)
  The market's own no-vig number at the decision time T is an UNPENALISED
  offset; an L2 model on prior-game inputs can only move it, and with nothing
  to say it returns the market's fair line exactly.
  moneylines (full game, first half, first quarter)
      OffsetLogit and choose_C, imported unchanged: offset = log-odds of the
      market's no-vig home price. Period moneylines train on decided periods
      only (a level period voids the two-way bet).
  spreads, totals, team totals (the centre)
      OffsetRidge below, the same fit on squared error: target (result -
      market centre) / its spread on the training rows, inputs standardised,
      intercept unpenalised, penalty |w|^2 / (2 C n) as in OffsetLogit, C
      chosen by choose_C_linear (choose_C's rule scored on mean squared
      error). The model's centre = the market's centre + the fitted move, in
      points, priced through the SAME distribution the market's centre was
      solved through (H.market_fair's sigma).
  One model per market per decision point, fit on that point's rows of the
  seasons before the graded one. Team totals: one model over both teams'
  markets, one row per team.

THE INPUTS (each dated at or before T; the same code for training and graded rows)
  ratings       the second search's projected home margin and total at T
                (scripts/nba_game2_projection.project: box-score plus-minus and
                adjusted plus-minus from lineup segments x projected minutes)
  availability  that projection's absence terms at T (F5_FEATURES), home - away
                for margin models, home + away for totals; missing reads 0
  luck          the second search's shooting-luck gap (scripts/nba_game2_luck),
                games before the date; 0 until both teams have 10 games
  pace          the projection's as-of team pace, home + away
  schedule      features/nba_schedule_features: rest days, back-to-back, third
                game in four nights, game number on the current road trip,
                miles travelled (thousands), time-zone shift, per team; the
                venue at altitude
  team totals   the team's own projected points (total +- margin) / 2 and luck
                gap, own and opponent absences and schedule, both paces, home
  the period    first half / first quarter: the inputs in points (POINT_FEATS)
                times the period's share of full-game points, from period scores
                of seasons before the graded one (a constant within one fit)

CELLS (section 8)
  full game   h2h, spreads, totals x 2 sides x A, C, D x EV >= .02 .04 .06 .08   72
  periods     h2h, spreads, totals of h1 and q1 x 2 sides x D x the same cuts    48
  team totals both teams' markets pooled x over / under x D x the same cuts       8

SEASONS
  full game: graded 2022-2026 (2021, the first priced season, only fits).
  first half, first quarter, team totals: every season the cache prices except
  the first, which only fits. Cuts reported on the harness's choosing seasons,
  confirmed on 2026, every graded season pooled (section 6.7).

    PYTHONPATH=. python -m scripts.nba_game4_p1 --smoke
    NBA_GAME2_GO=1 PYTHONPATH=. python -m scripts.nba_game4_p1 --full

--smoke: 2020-21 only, full-game cells, an in-season split (fit before
2021-03-10, grade from it): plumbing, never a result; the derivative cells run
on synthetic games only. Output to <NBA_GAME2_RESULTS>/smoke/. --full writes
<NBA_GAME2_RESULTS>/cells_P1.parquet, population_P1.parquet, fits_P1.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from features import nba_schedule_features as NSF  # noqa: E402
from models.nhl_moneyline_anchored import C_GRID, OffsetLogit, choose_C, market_logit  # noqa: E402
from scripts import nba_game2_luck as L  # noqa: E402
from scripts import nba_game2_projection as P  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402

RESULTS = Path(os.environ.get("NBA_GAME2_RESULTS",
                              "C:/Users/micha/AppData/Local/Temp/nba_game_edge/results"))
GO_ENV = "NBA_GAME2_GO"

FAMILY = "P1"
CUTS = (0.02, 0.04, 0.06, 0.08)
FULL_POINTS = ("A", "C", "D")
DERIV_POINT = "D"
FULL_LABELS = ("h2h", "spreads", "totals")
PERIOD_LABELS = ("h2h_h1", "spreads_h1", "totals_h1", "h2h_q1", "spreads_q1", "totals_q1")
TEAM_TOTALS = "team_totals"
GROUPS = {TEAM_TOTALS: ("team_totals_home", "team_totals_away")}
DERIV_LABELS = PERIOD_LABELS + (TEAM_TOTALS,)
SIDES = {"ml": ["home", "away"], "spread": ["home", "away"], "total": ["over", "under"]}

FIRST_PRICED = 2021                       # the first season with full-game prices
FULL_SEASONS = (H.REGIME, *H.CHOOSE, H.CONFIRM)   # 2021-2026: loaded and required
FULL_GRADED = (*H.CHOOSE, H.CONFIRM)               # 2022-2026: 2021 only fits
DERIV_CANDIDATES = (2024, 2025, 2026)     # seasons a derivative purchase can cover
MIN_TRAIN = 300                           # fewer training rows: no model, no bet
LUCK_MIN_GAMES = L.MIN_GAMES              # the luck gap reads 0 before this
EARLY_GAMES = 10                          # bets in a team's first 10 games are counted apart
N_PLACEBO = 20
SMOKE_SEASONS = (2021,)
SMOKE_SPLIT = "2021-03-10"                # 2020-21's second half began this day
SMOKE_PLACEBO = 2
P_CLIP = 1e-4

F5 = tuple(P.F5_FEATURES)
SCHED = {"rest": "rest_days", "b2b": "b2b", "3in4": "is_3in4", "road_no": "road_game_no",
         "travel": "travel_mi", "tz": "tz_shift"}
POINT_FEATS = ("proj", "luck")            # the inputs measured in points
MARGIN_FEATS = (*POINT_FEATS, *[f"d_{f}" for f in F5], "pace",
                *[f"h_{s}" for s in SCHED], *[f"a_{s}" for s in SCHED], "altitude")
TOTAL_FEATS = (*POINT_FEATS, *[f"s_{f}" for f in F5], "pace",
               *[f"h_{s}" for s in SCHED], *[f"a_{s}" for s in SCHED], "altitude")
TEAM_FEATS = (*POINT_FEATS, *[f"own_{f}" for f in F5], *[f"opp_{f}" for f in F5], "pace_own",
              "pace_opp", *[f"own_{s}" for s in SCHED], *[f"opp_{s}" for s in SCHED], "altitude",
              "is_home")


# ── the cells ───────────────────────────────────────────────────────────────

def members(label: str) -> tuple:
    """The real markets a cell label covers (team totals: both teams')."""
    return tuple(GROUPS.get(label, (label,)))


def label_kind(label: str) -> str:
    k = set(H.kind(list(members(label))))
    assert len(k) == 1, (label, k)
    return k.pop()


def cell_specs() -> list[tuple]:
    """(point, label, side, cut_index, cut) for every cell section 8 lists."""
    out = []
    for p, labels in [(p, FULL_LABELS) for p in FULL_POINTS] + [(DERIV_POINT, DERIV_LABELS)]:
        for lab in labels:
            for s in SIDES[label_kind(lab)]:
                for k, c in enumerate(CUTS):
                    out.append((p, lab, s, k, c))
    return out


EXPECTED_CELLS = 128
EXPECTED_FULL, EXPECTED_DERIV = 72, 56


def check_cell_count() -> None:
    specs = cell_specs()
    assert len(specs) == EXPECTED_CELLS, len(specs)
    assert sum(1 for s in specs if s[1] in FULL_LABELS) == EXPECTED_FULL
    assert sum(1 for s in specs if s[1] in DERIV_LABELS) == EXPECTED_DERIV
    assert sum(1 for s in specs if s[1] == TEAM_TOTALS) == 8


check_cell_count()


# ── the centre's model: OffsetLogit's fit on squared error ──────────────────

class OffsetRidge:
    """L2 linear regression around a fixed offset (the market's centre), the
    squared-error twin of models.nhl_moneyline_anchored.OffsetLogit.

    The target is u = (y - offset) / s, s the spread of y - offset on the
    training rows, so the fit is the normal log-likelihood's and the penalty
    reads on the same scale as OffsetLogit's: minimise
        mean((u - b0 - Z w)^2) / 2 + |w|^2 / (2 C n),
    Z the inputs standardised on the training rows, b0 unpenalised. The offset
    is not a coefficient: the inputs can only move the market's number, and
    with no signal they shrink to it."""

    def __init__(self, C: float):
        self.C = C

    def fit(self, X, y, offset):
        X, y, offset = np.asarray(X, float), np.asarray(y, float), np.asarray(offset, float)
        self.mu, self.sd = X.mean(axis=0), X.std(axis=0) + 1e-9
        Z = (X - self.mu) / self.sd
        r = y - offset
        self.scale = float(r.std()) + 1e-9
        u = r / self.scale
        b0 = float(u.mean())
        k = Z.shape[1]
        w = np.linalg.solve(Z.T @ Z + np.eye(k) / self.C, Z.T @ (u - b0))
        self.w = np.r_[b0, w]
        return self

    def move(self, X) -> np.ndarray:
        """The fitted move off the offset, in the target's units (points)."""
        Z = (np.asarray(X, float) - self.mu) / self.sd
        return self.scale * (self.w[0] + Z @ self.w[1:])

    def predict(self, X, offset) -> np.ndarray:
        return np.asarray(offset, float) + self.move(X)


def _mse(y, p) -> float:
    return float(np.mean((np.asarray(y, float) - np.asarray(p, float)) ** 2))


def choose_C_linear(train: pd.DataFrame, feats) -> float:
    """choose_C's rule for the centre: each of the last three training seasons
    that has 800 or more earlier rows is scored by a fit on the seasons before
    it; the mean squared error decides. No such season: the grid's first C."""
    feats = list(feats)
    seasons = sorted(train.season.unique())
    vals = [v for v in seasons[-3:] if len(train[train.season < v]) >= 800]
    if not vals:
        return C_GRID[0]
    scores = {}
    for C in C_GRID:
        errs = []
        for v in vals:
            a, b = train[train.season < v], train[train.season == v]
            m = OffsetRidge(C).fit(a[feats].values, a.y.values, a.offset.values)
            errs.append(_mse(b.y.values, m.predict(b[feats].values, b.offset.values)))
        scores[C] = float(np.mean(errs))
    return min(scores, key=scores.get)


def fit_one(train: pd.DataFrame, feats, kind: str, min_train: int = MIN_TRAIN):
    """(model, C, rows used) on rows carrying every input, the offset and the
    result; (None, None, n) below `min_train` rows."""
    feats = list(feats)
    use = train.dropna(subset=feats + ["offset", "y"])
    if len(use) < min_train:
        return None, None, len(use)
    if kind == "ml":
        t = use.rename(columns={"offset": "mkt_logit"})
        C = choose_C(t, feats)
        return OffsetLogit(C).fit(t[feats].values, t.y.values, t.mkt_logit.values), C, len(use)
    C = choose_C_linear(use, feats)
    return OffsetRidge(C).fit(use[feats].values, use.y.values, use.offset.values), C, len(use)


def model_move(model, X, kind: str) -> np.ndarray:
    """The model's move off the market: log-odds for a moneyline, points otherwise."""
    if kind == "ml":
        p0 = np.clip(model.predict_proba(X, np.zeros(len(X)))[:, 1], 1e-12, 1 - 1e-12)
        return np.log(p0 / (1.0 - p0))
    return model.move(X)


# ── inputs ──────────────────────────────────────────────────────────────────

def schedule_inputs(sched: pd.DataFrame) -> pd.DataFrame:
    """Per game: each team's schedule inputs (h_*, a_*), the venue at altitude,
    and each team's game number this season (for the early-window count).
    Built from the schedule alone (features/nba_schedule_features)."""
    gf = NSF.game_schedule_features(sched)
    out = pd.DataFrame({"game_id": gf["game_id"]})
    for k, c in SCHED.items():
        out[f"h_{k}"] = gf[f"home_{c}"].astype(float)
        out[f"a_{k}"] = gf[f"away_{c}"].astype(float)
    for s in ("h", "a"):
        out[f"{s}_travel"] = out[f"{s}_travel"] / 1000.0
    out["altitude"] = gf["at_altitude"].astype(float)
    out["h_game_no"] = gf["home_game_no"].astype(float)
    out["a_game_no"] = gf["away_game_no"].astype(float)
    return out


def luck_inputs(games: pd.DataFrame, tb: pd.DataFrame) -> pd.DataFrame:
    """Per game: the shooting-luck gap (margin, total). f4_projections drops a
    game until both teams have LUCK_MIN_GAMES this season; those read 0 here."""
    assert LUCK_MIN_GAMES == L.MIN_GAMES
    pr = L.f4_projections(games, tb)[["game_id", "gap_margin", "gap_total"]]
    out = games[["game_id"]].merge(pr, on="game_id", how="left")
    return out.fillna({"gap_margin": 0.0, "gap_total": 0.0})


def base_inputs(proj: pd.DataFrame, luck: pd.DataFrame, sched_in: pd.DataFrame) -> pd.DataFrame:
    """One row per game at T: every input before orientation. `proj` is the
    projection at T (P.project): margin, total, pace_t_h/_a, F5 terms _h/_a."""
    keep = ["game_id", "margin", "total", "pace_t_h", "pace_t_a",
            *[f"{f}_h" for f in F5], *[f"{f}_a" for f in F5]]
    b = proj[keep].rename(columns={"pace_t_h": "pace_h", "pace_t_a": "pace_a"})
    b = b[np.isfinite(b["margin"].astype(float)) & np.isfinite(b["total"].astype(float))]
    for f in F5:
        b[f"{f}_h"] = b[f"{f}_h"].astype(float).fillna(0.0)
        b[f"{f}_a"] = b[f"{f}_a"].astype(float).fillna(0.0)
    b = b.merge(luck, on="game_id", how="left").fillna({"gap_margin": 0.0, "gap_total": 0.0})
    return b.merge(sched_in, on="game_id", how="inner").reset_index(drop=True)


def oriented(b: pd.DataFrame, market: str) -> pd.DataFrame:
    """The model's inputs for one real market, from base_inputs rows."""
    k, sc = H.kind([market])[0], H.scope([market])[0]
    x = pd.DataFrame({"game_id": b["game_id"].to_numpy()})
    sched = {f"{s}_{k2}": b[f"{s}_{k2}"].to_numpy(float) for s in ("h", "a") for k2 in SCHED}
    if sc in ("home_team", "away_team"):
        own, opp = ("h", "a") if sc == "home_team" else ("a", "h")
        sign = 1.0 if sc == "home_team" else -1.0
        x["proj"] = (b["total"] + sign * b["margin"]).to_numpy(float) / 2.0
        x["luck"] = (b["gap_total"] + sign * b["gap_margin"]).to_numpy(float) / 2.0
        for f in F5:
            x[f"own_{f}"] = b[f"{f}_{own}"].to_numpy(float)
            x[f"opp_{f}"] = b[f"{f}_{opp}"].to_numpy(float)
        x["pace_own"], x["pace_opp"] = b[f"pace_{own}"].to_numpy(float), b[f"pace_{opp}"].to_numpy(float)
        for k2 in SCHED:
            x[f"own_{k2}"], x[f"opp_{k2}"] = sched[f"{own}_{k2}"], sched[f"{opp}_{k2}"]
        x["altitude"] = b["altitude"].to_numpy(float)
        x["is_home"] = 1.0 if sc == "home_team" else 0.0
        return x
    margin_like = k in ("ml", "spread")
    x["proj"] = b["margin" if margin_like else "total"].to_numpy(float)
    x["luck"] = b["gap_margin" if margin_like else "gap_total"].to_numpy(float)
    for f in F5:
        h, a = b[f"{f}_h"].to_numpy(float), b[f"{f}_a"].to_numpy(float)
        if margin_like:
            x[f"d_{f}"] = h - a
        else:
            x[f"s_{f}"] = h + a
    x["pace"] = (b["pace_h"] + b["pace_a"]).to_numpy(float)
    for key, v in sched.items():
        x[key] = v
    x["altitude"] = b["altitude"].to_numpy(float)
    return x


def features_of(label: str) -> tuple:
    if label == TEAM_TOTALS:
        return TEAM_FEATS
    return MARGIN_FEATS if label_kind(label) in ("ml", "spread") else TOTAL_FEATS


def outcome(market: str, frame: pd.DataFrame) -> np.ndarray:
    """What the model is fit to, settled exactly as the harness settles the
    market (H.settling_scores): the home win (NaN for a level period), the
    home margin, or the total (a team total: that team's own points)."""
    m = np.array([market] * len(frame), dtype=object)
    base, home, away = H.settling_scores(m, frame)
    k = H.kind([market])[0]
    if k == "ml":
        return np.where(home > away, 1.0, np.where(home < away, 0.0, np.nan))
    if k == "spread":
        return home - away
    return home + away


def model_rows(label: str, fair: pd.DataFrame, base: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Training and graded rows for one cell label: per (game, real market) the
    market's offset at T, the oriented inputs and the result."""
    k = label_kind(label)
    parts = []
    for m in members(label):
        f = fair[fair["market"] == m][["game_id", "market", "mu", "p_home"]]
        x = f.merge(oriented(base, m), on="game_id")
        x = x.merge(games[[c for c in ("game_id", "season", "game_date", "home_score", "away_score",
                                       *H.PERIOD_COLS) if c in games]], on="game_id")
        if k == "ml":
            x["offset"] = market_logit(np.clip(x["p_home"].astype(float), P_CLIP, 1 - P_CLIP))
        else:
            x["offset"] = x["mu"].astype(float)
        x["y"] = outcome(m, x) if len(x) else np.array([], float)
        parts.append(x.drop(columns=["mu", "p_home"]))
    out = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    return out.drop(columns=[c for c in ("home_score", "away_score", *H.PERIOD_COLS) if c in out])


# ── the period's share of full-game points ──────────────────────────────────

def period_shares(games_p: pd.DataFrame, seasons) -> dict:
    """(S, "h1" / "q1") -> the period's points over full-game points, summed over
    every game of the seasons BEFORE S with trusted period scores (no price)."""
    out = {}
    have = [c for c in H.PERIOD_COLS if c in games_p]
    for S in seasons:
        g = games_p[games_p["season"] < S]
        if len(have) == len(H.PERIOD_COLS):
            g = g[np.isfinite(g[list(H.PERIOD_COLS)].to_numpy(float)).all(axis=1)]
        full = float((g["home_score"] + g["away_score"]).sum()) if len(have) else 0.0
        for part in ("h1", "q1"):
            if full > 0:
                out[(int(S), part)] = float((g[f"home_{part}"] + g[f"away_{part}"]).sum()) / full
            else:
                out[(int(S), part)] = np.nan
    return out


def scaler(label: str, shares: dict):
    """S -> the factor on POINT_FEATS for a fit graded on S (1 for full-game and
    team-total markets; the period's share for the first half and quarter)."""
    sc = set(H.scope(list(members(label))))
    part = sc.pop() if len(sc) == 1 else None
    if part not in ("h1", "q1"):
        return lambda S: 1.0

    def f(S):
        v = shares.get((int(S), part), np.nan)
        if not np.isfinite(v):
            raise ValueError(f"no period share for {part} before season {S}")
        return v
    return f


# ── the walk-forward ────────────────────────────────────────────────────────

def walk_forward(rows: pd.DataFrame, label: str, graded, shares: dict | None = None,
                 fold: str = "season", min_train: int = MIN_TRAIN) -> tuple[pd.DataFrame, list]:
    """The model's move for every row of each graded fold S, from a model fit
    on the rows of folds before S only. `fold` is the season (the smoke run's
    in-season split names its own column). Returns (moves, fits): moves are
    (game_id, market, season, move); fits the penalty and row counts per S."""
    feats = list(features_of(label))
    kind = label_kind(label)
    scale = scaler(label, shares or {})
    out, fits = [], []
    if rows.empty:
        return pd.DataFrame(columns=["game_id", "market", "season", "move"]), fits
    w = rows.assign(season=rows[fold].to_numpy())
    for S in graded:
        k = scale(S)
        x = w.copy()
        for c in POINT_FEATS:
            x[c] = x[c] * k
        train, test = x[x["season"] < S], x[x["season"] == S]
        model, C, n = fit_one(train, feats, kind, min_train=min_train)
        info = {"label": label, "fold": int(S) if float(S).is_integer() else float(S), "C": C,
                "n_train": int(n), "n_scored": 0, "share": float(k)}
        if model is not None:
            test = test.dropna(subset=feats + ["offset"])
            if len(test):
                mv = model_move(model, test[feats].values, kind)
                out.append(pd.DataFrame({"game_id": test["game_id"].to_numpy(),
                                         "market": test["market"].to_numpy(),
                                         "season": rows.loc[test.index, "season"].to_numpy(),
                                         "move": mv}))
                info["n_scored"] = int(len(test))
        fits.append(info)
    mv = pd.concat(out, ignore_index=True) if out else pd.DataFrame(
        columns=["game_id", "market", "season", "move"])
    return mv, fits


def model_fair(fair: pd.DataFrame, moves: pd.DataFrame) -> pd.DataFrame:
    """The market's fair line moved by the model: a moneyline's log-odds plus the
    move, a centre plus the move in points; sigma (the pricing distribution) is
    the market's own. Only (game, market) rows with a move are kept."""
    x = fair.merge(moves[["game_id", "market", "move"]], on=["game_id", "market"], how="inner")
    ml = H.kind(x["market"]) == "ml"
    p = np.clip(x["p_home"].astype(float).to_numpy(), P_CLIP, 1 - P_CLIP)
    mv = x["move"].astype(float).to_numpy()
    p_new = 1.0 / (1.0 + np.exp(-(np.log(p / (1 - p)) + mv)))
    x["p_home"] = np.where(ml, p_new, np.nan)
    x["mu"] = np.where(ml, np.nan, x["mu"].astype(float).to_numpy() + mv)
    return x.drop(columns="move").reset_index(drop=True)


def placebo_fairs(fair: pd.DataFrame, moves: pd.DataFrame, games: pd.DataFrame, n: int) -> list:
    """Bar 10's placebo for an anchored model: the MOVE shuffled between games on
    the same date in the same market (seed = run number), each added to its own
    game's market number. Shuffling whole probabilities would hand a game
    another game's market price."""
    mv = moves[["game_id", "market", "move"]].rename(columns={"move": "mu"})
    out = []
    for r in range(n):
        sh = H.shuffle_within_date(mv, games, np.random.default_rng(r)).rename(columns={"mu": "move"})
        out.append(model_fair(fair, sh))
    return out


# ── one decision point ──────────────────────────────────────────────────────

@dataclass
class Point:
    point: str
    times: pd.DataFrame
    off: pd.DataFrame
    fair: pd.DataFrame
    neutral: pd.DataFrame
    base: pd.DataFrame


def make_point(data: H.Data, point: str, times: pd.DataFrame, sig: dict, base: pd.DataFrame) -> Point:
    """What a bettor sees at each game's T and the market's own fair line there."""
    vis = H.visible(data.quotes, times)
    off = H.offers(vis)
    fair = H.market_fair(vis, sig)
    return Point(point, times, off, fair, H.fair_offers(off, fair), base)


def project_at(w, st, models: dict, games: pd.DataFrame, times: pd.DataFrame) -> pd.DataFrame:
    """The second search's projection for every game at ITS decision time T."""
    gm = games.merge(times[["game_id", "T"]], on="game_id").merge(w.games[["game_id", "day"]], on="game_id")
    parts = [P.project(w, st, models[int(s)], g) for s, g in gm.groupby("season") if int(s) in models and len(g)]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def point_inputs(data: H.Data, point: str, times: pd.DataFrame, w, st, models: dict,
                 luck: pd.DataFrame, sched_in: pd.DataFrame, sig: dict) -> Point:
    """One decision point on real data: the projection at each game's own T,
    every input, the offers and the market's fair line there."""
    base = base_inputs(project_at(w, st, models, data.games, times), luck, sched_in)
    return make_point(data, point, times, sig, base)


def derivative_times(dd: H.Data) -> pd.DataFrame:
    """The derivative markets decide at the per-game purchase (tip - 60, inside
    D's 45-75 minutes), never at the full-game slate's D fetch."""
    return H.per_event_times(dd.quotes, DERIV_POINT)


def emit_point(data: H.Data, pt: Point, labels, close, sig, graded, choose_seasons, shares,
               fold_col: str = "season", fold_of=None, n_placebo: int = N_PLACEBO,
               min_train: int = MIN_TRAIN, early=None) -> tuple[list, list, pd.DataFrame]:
    """Every cell of `labels` at one decision point: (rows, fits, population).
    `fold_of`: game_id -> fold (the smoke split); default the season."""
    games = data.games
    moves, fits = [], []
    for lab in labels:
        r = model_rows(lab, pt.fair, pt.base, games)
        if fold_of is not None and len(r):
            r[fold_col] = r["game_id"].map(fold_of)
        mv, f = walk_forward(r, lab, graded, shares, fold=fold_col, min_train=min_train)
        moves.append(mv)
        fits += [{**x, "point": pt.point} for x in f]
    mv = pd.concat([m for m in moves if len(m)], ignore_index=True) if any(len(m) for m in moves) \
        else pd.DataFrame(columns=["game_id", "market", "season", "move"])
    cand = H.fair_offers(pt.off, model_fair(pt.fair, mv))
    placebo = [H.fair_offers(pt.off, f) for f in placebo_fairs(pt.fair, mv, games, n_placebo)]
    sides = {lab: list(SIDES[label_kind(lab)]) for lab in labels}
    rows = H.run_cells(data, FAMILY, pt.point, cand, pt.neutral, list(CUTS), sides, close=close,
                       sig=sig, placebo=placebo, strength="ev", choose_seasons=choose_seasons,
                       times=pt.times, market_groups=GROUPS)
    return rows, fits, population(pt, data, cand, labels, early)


def population(pt: Point, data: H.Data, cand: pd.DataFrame, labels, early) -> pd.DataFrame:
    """Per season and cell: games, games with a decision time, with a deciding
    price, with a model number, and bets per cut (the harness's own choose()),
    and the bets in either team's first EARLY_GAMES games. Counts only."""
    season = data.games.set_index("game_id")["season"].astype(int)
    seasons = sorted(season.unique())

    def count(ids):
        return pd.Series(season.reindex(pd.unique(np.asarray(ids))).value_counts()).reindex(
            seasons, fill_value=0)

    early = set() if early is None else set(early)
    priced = pt.off[pt.off["book"].isin(H.BETTABLE)]
    n_games, n_time = count(season.index), count(pt.times["game_id"])
    out = []
    for lab in labels:
        mem = members(lab)
        cm = cand[cand["market"].isin(mem)]
        n_priced = count(priced.loc[priced["market"].isin(mem), "game_id"])
        n_model = count(cm["game_id"])
        for side in SIDES[label_kind(lab)]:
            for k, cut in enumerate(CUTS):
                b = H.choose(cm, cut, sides=[side])
                n_bets = season.reindex(b["game_id"]).value_counts().reindex(seasons, fill_value=0)
                e = b[b["game_id"].isin(early)]
                n_early = season.reindex(e["game_id"]).value_counts().reindex(seasons, fill_value=0)
                for s in seasons:
                    out.append({"family": FAMILY, "point": pt.point, "season": int(s), "market": lab,
                                "side": side, "cut_index": k, "cut": cut, "games": int(n_games[s]),
                                "games_with_time": int(n_time[s]), "games_priced": int(n_priced[s]),
                                "games_with_model": int(n_model[s]), "bets": int(n_bets[s]),
                                "bets_first_10_games": int(n_early[s])})
    return pd.DataFrame(out)


def early_games(sched_in: pd.DataFrame) -> set:
    """Games inside either team's first EARLY_GAMES games of its season."""
    m = (sched_in["h_game_no"] <= EARLY_GAMES) | (sched_in["a_game_no"] <= EARLY_GAMES)
    return set(sched_in.loc[m, "game_id"])


# ── derivative data ─────────────────────────────────────────────────────────

def derivative_seasons(pe: pd.DataFrame, candidates=DERIV_CANDIDATES) -> tuple:
    """The derivative seasons the cache holds, read from row counts: every
    candidate season with any row. All eight markets must hold the same set."""
    cand = {int(s) for s in candidates}
    by = {m: {int(s) for s in pe.loc[pe["market"] == m, "season"].unique()} & cand
          for m in H.DERIVATIVE_MARKETS}
    sets = {frozenset(v) for v in by.values()}
    if len(sets) != 1:
        raise RuntimeError(f"the derivative markets hold different seasons: {by}")
    return tuple(sorted(sets.pop()))


def derivative_plan(held: tuple) -> tuple[tuple, tuple]:
    """(graded, choosing) seasons for the derivative cells: every held season but
    the first, which only fits; choosing = graded without the confirmation season."""
    graded = tuple(held[1:])
    return graded, tuple(s for s in graded if s != H.CONFIRM)


def derivative_data(games_p: pd.DataFrame, pe: pd.DataFrame, held) -> H.Data:
    g = games_p[games_p["season"].isin(list(held))].reset_index(drop=True)
    q = pe[pe["game_id"].isin(set(g["game_id"]))].reset_index(drop=True)
    f = q[["game_id", "tip", "fetch_at"]].drop_duplicates(["game_id", "fetch_at"])
    f = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60.0)
    return H.Data(games=g, quotes=q, fetches=f.reset_index(drop=True))


# ── synthetic world (no real data) ──────────────────────────────────────────

def synthetic_world(seed: int = 3, seasons=(2021, 2022, 2023, 2024, 2025, 2026), per_season: int = 40):
    """A priced synthetic world: full-game quotes at every decision point
    (nba_game2_projection.synthetic_market), period scores, the eight
    derivative markets at tip - 60, and per-game inputs. Nothing real is read."""
    rng = np.random.default_rng(seed)
    data = P.synthetic_market(seed=seed, seasons=seasons, per_season=per_season)
    g = data.games.copy()
    hq = rng.integers(20, 34, len(g)).astype(float)
    aq = rng.integers(20, 34, len(g)).astype(float)
    hh = hq + rng.integers(20, 34, len(g))
    ah = aq + rng.integers(20, 34, len(g))
    g = g.assign(home_q1=hq, away_q1=aq, home_h1=hh, away_h1=ah,
                 home_score=(hh + rng.integers(45, 65, len(g))).astype(float),
                 away_score=(ah + rng.integers(45, 65, len(g))).astype(float))
    g.loc[::7, "away_h1"] = g.loc[::7, "home_h1"]          # some level first halves
    data.games = g
    rows = []
    for r in g.itertuples():
        at = r.tip - pd.Timedelta(minutes=60)
        for book in ("fanduel", "draftkings", "pinnacle"):
            base = {"game_id": r.game_id, "season": r.season, "game_date": r.game_date, "tip": r.tip,
                    "book": book, "snapshot_at": at, "fetch_at": at, "coherent": True}
            for mk, line in (("spreads_h1", float(rng.choice([-2.5, -1.5]))),
                             ("totals_h1", float(rng.choice([109.5, 110.5]))),
                             ("spreads_q1", float(rng.choice([-1.5, -0.5]))),
                             ("totals_q1", float(rng.choice([54.5, 55.5]))),
                             ("team_totals_home", float(rng.choice([112.5, 113.5]))),
                             ("team_totals_away", float(rng.choice([108.5, 109.5])))):
                rows.append({**base, "market": mk, "line": line, "price_a": -110.0, "price_b": -110.0})
            for mk in ("h2h_h1", "h2h_q1"):
                rows.append({**base, "market": mk, "line": np.nan, "price_a": -125.0, "price_b": 105.0})
    pe = pd.DataFrame(rows)
    n = len(g)
    margin = (g["home_score"] - g["away_score"]).to_numpy() * 0.5 + rng.normal(0, 6, n)
    total = (g["home_score"] + g["away_score"]).to_numpy() * 0.5 + 110 + rng.normal(0, 6, n)
    base = pd.DataFrame({"game_id": g["game_id"], "margin": margin, "total": total,
                         "pace_h": rng.normal(99, 2, n), "pace_a": rng.normal(99, 2, n),
                         "gap_margin": rng.normal(0, 1, n), "gap_total": rng.normal(0, 1, n),
                         "altitude": (rng.random(n) < 0.1).astype(float),
                         "h_game_no": np.tile(np.arange(1, per_season + 1), len(seasons))[:n],
                         "a_game_no": np.tile(np.arange(1, per_season + 1), len(seasons))[:n]})
    for f in F5:
        base[f"{f}_h"], base[f"{f}_a"] = rng.random(n), rng.random(n)
    for s in ("h", "a"):
        for k in SCHED:
            base[f"{s}_{k}"] = rng.random(n)
    return data, pe, base


def synthetic_cells_check(n_placebo: int = 1, min_train: int = 20, per_season: int = 40) -> dict:
    """All 128 cells through the harness on synthetic games: counts only."""
    data, pe, base = synthetic_world(per_season=per_season)
    held = derivative_seasons(pe.merge(data.games[["game_id"]], on="game_id"),
                              candidates=tuple(sorted(data.games["season"].unique())))
    sig = {(int(s), m): 12.0 if H.kind([m])[0] == "spread" else 18.0
           for s in data.games["season"].unique() for m in ("spreads", "totals", *H.DERIVATIVE_MARKETS)
           if H.kind([m])[0] != "ml"}
    close = H.pinnacle_close(data)
    shares = period_shares(data.games, data.games["season"].unique())
    graded = tuple(sorted(int(s) for s in data.games["season"].unique()))[1:]
    rows, fits = [], []
    for p in FULL_POINTS:
        t = H.decision_times(data.fetches, data.games, p)
        pt = make_point(data, p, t, sig, base)
        r, f, pop = emit_point(data, pt, FULL_LABELS, close, sig, graded, H.CHOOSE, shares,
                               n_placebo=n_placebo, min_train=min_train, early=early_games(base))
        rows += r
        fits += f
    dd = derivative_data(data.games, pe, held)
    dg, dch = derivative_plan(held)
    pt = make_point(dd, DERIV_POINT, derivative_times(dd), sig, base)
    r, f, dpop = emit_point(dd, pt, DERIV_LABELS, H.pinnacle_close(dd), sig, dg, dch, shares,
                            n_placebo=n_placebo, min_train=min_train, early=early_games(base))
    rows += r
    assert len(rows) == EXPECTED_CELLS, len(rows)
    tt = [x for x in rows if x["market"] == TEAM_TOTALS]
    assert len(tt) == 8
    assert sum(x["n_choose"] + x["n_confirm"] for x in tt) > 0, "team totals graded no bet"
    assert pop["bets"].sum() > 0 and dpop["bets"].sum() > 0
    return {"cells": len(rows), "full_bets": int(pop["bets"].sum()),
            "derivative_bets": int(dpop["bets"].sum()), "derivative_graded": dg}


# ── modes ───────────────────────────────────────────────────────────────────

def refuse(lines: list[str]) -> None:
    for x in lines:
        print("REFUSED:", x)
    raise SystemExit(2)


def full_refusals(cache: Path) -> list[str]:
    """The cheap refusals before the hour-long projection: the go flag, the
    lineup segments the ratings read, the fetch ledger (P.refuse_full)."""
    return P.refuse_full(cache)


def load_inputs(cache: Path):
    sched = pd.read_parquet(cache / "nba_schedule.parquet")
    box, _ = L._load_box(cache)
    return schedule_inputs(sched), box


def smoke(cache: Path) -> dict:
    """2020-21 only, full-game cells, an in-season split; synthetic derivative
    cells. Counts printed, never a return."""
    H.check()
    syn = synthetic_cells_check()
    print(f"synthetic: {syn['cells']} cells (128 expected), bets {syn['full_bets']} full game / "
          f"{syn['derivative_bets']} derivative (synthetic games only); nothing written")
    w = P.load_world(cache, max_season=max(SMOKE_SEASONS))
    hp, st, models, _, _ = P.run_projection_setup(w, max(SMOKE_SEASONS))
    price_cache, note = P.smoke_price_cache(cache)
    data = H.load(price_cache, seasons=list(SMOKE_SEASONS))
    print("prices:", note, data.notes)
    sched_in, box = load_inputs(cache)
    luck = luck_inputs(data.games, L.team_box(box, data.games))
    close = H.pinnacle_close(data)
    sig = H.close_dist(close, data.games)
    fold_of = pd.Series(np.where(data.games["game_date"].astype(str) >= SMOKE_SPLIT, 1, 0),
                        index=data.games["game_id"])
    out = RESULTS / "smoke"
    out.mkdir(parents=True, exist_ok=True)
    rows, fits, pops, counts = [], [], [], {}
    for p in FULL_POINTS:
        t = H.decision_times(data.fetches, data.games, p)
        pt = point_inputs(data, p, t, w, st, models, luck, sched_in, sig)
        r, f, pop = emit_point(data, pt, FULL_LABELS, close, sig, graded=(1,),
                               choose_seasons=H.CHOOSE, shares={}, fold_col="smoke_fold",
                               fold_of=fold_of, n_placebo=SMOKE_PLACEBO, early=early_games(sched_in))
        rows += r
        fits += f
        pops.append(pop)
        counts[p] = {"games_with_time": int(len(t)), "with_every_input": int(len(pt.base)),
                     "fair_rows": int(len(pt.fair)),
                     "graded_after_split": int(fold_of.reindex(pt.base["game_id"]).eq(1).sum())}
    assert len(rows) == EXPECTED_FULL, len(rows)
    L.write_cells(rows, out / "cells_P1.parquet")
    pop = pd.concat(pops, ignore_index=True)
    pop.to_parquet(out / "population_P1.parquet")
    (out / "fits_P1.json").write_text(json.dumps(fits, indent=1, default=str), encoding="utf-8")
    # derivative purchases the cache holds: game counts only, no price read into a result
    games_p = H.with_periods(H.load_games(cache), cache)
    pe = H.load_per_event(games_p, cache)
    held = derivative_seasons(pe)
    dcounts = pe.groupby(["market", "season"])["game_id"].nunique().unstack(1).to_dict()
    summary = {"points": counts, "cells_written": len(rows), "fits": fits,
               "bets_2021_after_split": pop.groupby(["point", "market", "side", "cut"])["bets"].sum()
               .reset_index().to_dict("records"),
               "derivative_seasons_held": held, "derivative_plan": derivative_plan(held),
               "derivative_games_by_season": dcounts}
    print(json.dumps(summary, indent=1, default=str))
    return summary


def full(cache: Path) -> None:
    why = full_refusals(cache)
    if why:
        refuse(why)
    try:
        data = H.load(cache, seasons=list(FULL_SEASONS), require_seasons=FULL_SEASONS)
    except RuntimeError as e:
        refuse([str(e)])
    print("price rows:", data.notes)
    short = P.stints_short(cache)
    if short:
        refuse([f"lineup segments on too few games in {short}"])
    games_p = H.with_periods(H.load_games(cache), cache)
    held = derivative_seasons(H.load_per_event(games_p, cache))
    if not {2025, H.CONFIRM} <= set(held):
        refuse([f"derivative seasons held {held}: need 2025 and {H.CONFIRM} at least"])
    try:
        pe = H.load_per_event(games_p, cache, require_seasons=held)
    except RuntimeError as e:
        refuse([str(e)])
    dgraded, dchoose = derivative_plan(held)
    print(f"derivative seasons held {held}: graded {dgraded}, choosing {dchoose}")
    t0 = time.time()
    w = P.load_world(cache, max_season=H.CONFIRM)
    hp, st, models, _, _ = P.run_projection_setup(w, H.CONFIRM)
    print(f"projection set up ({time.time() - t0:.0f}s)")
    sched_in, box = load_inputs(cache)
    early = early_games(sched_in)
    luck = luck_inputs(data.games, L.team_box(box, data.games))
    close = H.pinnacle_close(data)
    sig = H.close_dist(close, data.games)
    shares = period_shares(games_p, sorted(set(FULL_GRADED) | set(held)))
    rows, fits, pops = [], [], []
    for p in FULL_POINTS:
        t = H.decision_times(data.fetches, data.games, p)
        pt = point_inputs(data, p, t, w, st, models, luck, sched_in, sig)
        r, f, pop = emit_point(data, pt, FULL_LABELS, close, sig, FULL_GRADED, H.CHOOSE, shares,
                               early=early)
        rows += r
        fits += f
        pops.append(pop)
        print(f"full game at {p}: {len(r)} cells ({time.time() - t0:.0f}s)")
    dd = derivative_data(games_p, pe, held)
    dclose = H.pinnacle_close(dd)
    dsig = H.close_dist(dclose, dd.games)
    dluck = luck_inputs(dd.games, L.team_box(box, dd.games))
    pt = point_inputs(dd, DERIV_POINT, derivative_times(dd), w, st, models, dluck, sched_in, dsig)
    r, f, pop = emit_point(dd, pt, DERIV_LABELS, dclose, dsig, dgraded, dchoose, shares, early=early)
    rows += r
    fits += f
    pops.append(pop)
    assert len(rows) == EXPECTED_CELLS, len(rows)
    RESULTS.mkdir(parents=True, exist_ok=True)
    L.write_cells(rows, RESULTS / "cells_P1.parquet")
    pd.concat(pops, ignore_index=True).to_parquet(RESULTS / "population_P1.parquet")
    (RESULTS / "fits_P1.json").write_text(json.dumps(fits, indent=1, default=str), encoding="utf-8")
    print(f"P1: {len(rows)} cells written to {RESULTS} ({time.time() - t0:.0f}s)")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true", help="2020-21 split, plus the synthetic 128 cells")
    g.add_argument("--full", action="store_true", help=f"every season; needs {GO_ENV}=1")
    a = ap.parse_args(argv)
    if a.full:
        full(H.CACHE)
    else:
        smoke(H.CACHE)


if __name__ == "__main__":
    main()
