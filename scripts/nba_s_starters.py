"""NBA search: the starters and the first quarter.

docs/nba_search_starters.md registers the cells and fixes every choice, written
and committed BEFORE this lab and before any cell was graded (2026-10-31). This
lab EMITS cells through the shared harness (scripts/nba_game_harness, H); the
pass/fail script judges them (scripts/nba_game2_verdict.py --house5). Nothing
here grades a bet by itself, and no cut, constant or rule below was chosen from
a betting result.

32 cells (asserted), decided at each game's per-game purchase 45-75 minutes
before tip (decision point D, H.per_event_times), 2023-24 .. 2025-26 pooled:

  MINUTES   per player, from nba_stints: his first-quarter and first-half
            minutes in every game he played, time-weighted over his earlier
            games with the rating engine's minutes half-life. Expected minutes
            = P(plays) from the injury report as of T x those minutes, rescaled
            to 60 player-minutes (first quarter, nobody above 12) and 120
            (first half, nobody above 24). Never the game's own box score or
            lineup: who starts is not known at T.
  RATINGS   the second search's engine (scripts/nba_game2_projection): each
            player's offence and defence as of T, box score plus adjusted
            plus-minus from lineup segments, walk-forward.
  TILT      a team's period-weighted rating minus its full-game-weighted
            rating, offence and defence apart (D positive = good defence, the
            engine's convention: eff_home = L + O_home - D_away).
            margin tilt = (tO_h - tD_a) - (tO_a - tD_h); total tilt = (tO_h -
            tD_a) + (tO_a - tD_h); each x period possessions / 100, the
            possessions being the engine's as-of pace x the period's share of
            48 minutes.
  BASE      section 9's league-share projection (G5.f7_projection, league_only):
            the market's full-game fair centres at T split into team points,
            each times the league's period share at that venue.
  PROJECTED base + beta x tilt points. beta per market and graded season, fit on
            the seasons before it from 2020-21, at T = tip - 60, intercept
            fitted and not used, no floor.
  GAP       projected minus the period market's fair centre at T (H.market_fair
            priced by P3.period_market_pricing). A rule: the side's best
            deciding offer under the market's fair line (H.run_cells strength=).
  CELLS     first-quarter spread and total x 2 sides x gap >= .25/.5/.75/1;
            first-half spread and total x 2 sides x gap >= .5/1/1.5/2.
  CONTROL   S1_league: the same 32 cells on the base alone. It carries no
            "control_" prefix so the verdict's --house5 judges it like a cell;
            the credit rule is read by `--credit` (a spread cell counts for the
            starters only if it passes AND beats its control; a total cell never
            does, and its pass reads as the league-share idea's).
  PLACEBO   200 runs, seeds 1-200: each game's whole gap moved to another game
            on the same date in the same market; offers and prices stay. The
            same runs with only the tilt moved are reported beside, not judged.

    NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_starters --smoke
    NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> NBA_GAME2_BETS=<folder>/bets \
        NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_starters --full
    PYTHONPATH=. python -m scripts.nba_game2_verdict --results <folder> --house5
    PYTHONPATH=. python -m scripts.nba_s_starters --credit --results <folder>

--smoke runs the synthetic checks, then on the real cache prints only counts and
inputs: never a graded real bet. Everything the rating engine costs is saved
under NBA_S_STARTERS_SCRATCH (regenerable from the cache) so a re-run repeats
none of it.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import models.nba_total_luck as tl  # noqa: E402
from models import nba_book_numbers as NB  # noqa: E402
from scripts import nba_game2_luck as L  # noqa: E402
from scripts import nba_game2_projection as P  # noqa: E402
from scripts import nba_game2_verdict as V  # noqa: E402
from scripts import nba_game4_p3 as P3  # noqa: E402
from scripts import nba_game5 as G5  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402

GO_ENV, RESULTS_ENV, BETS_ENV = G5.GO_ENV, G5.RESULTS_ENV, G5.BETS_ENV
SCRATCH_ENV = "NBA_S_STARTERS_SCRATCH"
DEFAULT_SCRATCH = "C:/Users/micha/AppData/Local/Temp/nba_s/starters"
FAMILY, CONTROL = "S1", "S1_league"
POINT = "D"
GRADED = (2024, 2025, 2026)                    # 2023-24 .. 2025-26, the derivative purchases
FIT_FIRST = 2021                               # 2020-21: the first season with full-game prices
LAST_SEASON = max(GRADED)
PERIODS = ("q1", "h1")
PLAYER_CAP = {"q1": 12.0, "h1": 24.0}          # a player's minutes in the period
TEAM_MINUTES = {"q1": 60.0, "h1": 120.0}       # five players x the period
SHARE_OF_GAME = {"q1": 12.0 / 48.0, "h1": 24.0 / 48.0}
MARKETS = ("spreads_q1", "totals_q1", "spreads_h1", "totals_h1")
SIDES = {m: (("over", "under") if m.startswith("totals") else ("home", "away")) for m in MARKETS}
CUTS = {m: G5.POINT_CUTS[m.rsplit("_", 1)[1]] for m in MARKETS}
EXPECTED_CELLS = 32
MIN_FIT_GAMES = 300
N_PLACEBO = 200
PLACEBO_SEEDS = tuple(range(1, N_PLACEBO + 1))
# The doc's section 8, added before any cell was graded: a total cell's bets are
# nearly all its control's, so beating the control there says nothing about the starters.
NO_CREDIT_MARKETS = ("totals_q1", "totals_h1")
STARTERS_IDEA, LEAGUE_IDEA = "the starters", "the league-share idea"
NOT_THE_STARTERS = "not the starters: it did not beat its control"
TEAM_MINUTE_SLACK = 1.0                        # a team-game whose segments miss the period by more is unread
# No such number exists on an NBA board. A row outside these is filed wrong: it
# is dropped before anything is computed, and counted. The total ranges do not
# overlap, so a number filed under another period's market cannot pass.
IMPOSSIBLE = {"spreads": (-40.0, 40.0), "totals": (175.0, 320.0),
              "spreads_h1": (-25.0, 25.0), "totals_h1": (85.0, 170.0),
              "spreads_q1": (-15.0, 15.0), "totals_q1": (35.0, 80.0)}
# a book's main number is the rung closest to even; one priced past this is not
# a main number, whatever the book's ladder held
MAX_MAIN_PRICE = 250.0
ENGINE_DIR = "engine"
ENGINE_NAME = "engine_models"
FRAMES_VERSION = 2
# Fit before any cell was graded and registered in the doc's counts section; a
# refit that returns anything else stops --full.
REGISTERED_BETA: dict = {
    (2024, "spreads_h1"): 0.9411084472871227, (2024, "spreads_q1"): 2.107162026982248,
    (2024, "totals_h1"): -1.68714999789803, (2024, "totals_q1"): -0.098573933763044,
    (2025, "spreads_h1"): 0.7863756878703179, (2025, "spreads_q1"): 2.203032914132867,
    (2025, "totals_h1"): -0.5410796090850172, (2025, "totals_q1"): 0.06025273111144231,
    (2026, "spreads_h1"): 1.3755058880342714, (2026, "spreads_q1"): 2.0280488442860056,
    (2026, "totals_h1"): -0.3293699607192663, (2026, "totals_q1"): 0.4173753654979911}
BETA_TOLERANCE = 1e-6

assert len(MARKETS) * 2 * 4 == EXPECTED_CELLS


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def scratch_dir() -> Path:
    return Path(os.environ.get(SCRATCH_ENV, DEFAULT_SCRATCH))


def cell_specs() -> list[tuple]:
    """(market, side, cut_index, cut) for every registered cell."""
    return [(m, s, k, c) for m in MARKETS for s in SIDES[m] for k, c in enumerate(CUTS[m])]


# ── impossible numbers (stated before anything is read) ─────────────────────

def impossible_mask(q: pd.DataFrame) -> pd.Series:
    """True for a row whose number no board could hang. A market with no range
    (a moneyline) is untouched; a missing line is not read here."""
    bad = pd.Series(False, index=q.index)
    for m, (lo, hi) in IMPOSSIBLE.items():
        sel = q["market"] == m
        if sel.any():
            bad |= sel & ((q["line"] < lo) | (q["line"] > hi))
    return bad


def drop_impossible(q: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """(rows without an impossible number, {market: rows dropped})."""
    bad = impossible_mask(q)
    return q[~bad].reset_index(drop=True), {str(k): int(v) for k, v in q.loc[bad, "market"].value_counts().items()}


def drop_unpriceable(vis: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Visible main numbers without a price past MAX_MAIN_PRICE on either side."""
    bad = (vis["price_a"].abs() > MAX_MAIN_PRICE) | (vis["price_b"].abs() > MAX_MAIN_PRICE)
    return vis[~bad].reset_index(drop=True), int(bad.sum())


# ── period minutes from the lineup segments ─────────────────────────────────

STINT_COLS = ["game_id", "season_type", "period", "duration_s", "home_team", "away_team",
              "home_player_ids", "away_player_ids", "n_home", "n_away"]


def period_minutes(s: pd.DataFrame) -> pd.DataFrame:
    """(game_id, team, player_id, q1, h1): each player's minutes in the first
    quarter and first half of each regular-season game, from five-a-side
    segments. Garbage-time rows count: minutes are minutes. A player with no
    row played neither period."""
    s = s[(pd.to_numeric(s["season_type"], errors="coerce") == P.REGULAR_SEASON_TYPE)
          & (s["n_home"] == 5) & (s["n_away"] == 5) & s["period"].isin([1, 2])]
    if s.empty:
        return pd.DataFrame(columns=["game_id", "team", "player_id", "q1", "h1"])
    parts = []
    for side in ("home", "away"):
        ids = np.concatenate([np.asarray(v, dtype=object) for v in s[f"{side}_player_ids"].to_numpy()])
        parts.append(pd.DataFrame({"game_id": np.repeat(s["game_id"].to_numpy(), 5),
                                   "team": np.repeat(s[f"{side}_team"].to_numpy(), 5),
                                   "period": np.repeat(s["period"].to_numpy(int), 5),
                                   "sec": np.repeat(s["duration_s"].to_numpy(float), 5),
                                   "player_id": ids}))
    x = pd.concat(parts, ignore_index=True)
    # the engine's own id form, each distinct id once (a dict, not a per-row call)
    norm = {v: P._norm_id(v) for v in pd.unique(x["player_id"])}
    x["player_id"] = x["player_id"].map(norm)
    w = x.groupby(["game_id", "team", "player_id", "period"])["sec"].sum().unstack("period", fill_value=0.0)
    w = w.reindex(columns=[1, 2], fill_value=0.0)
    out = pd.DataFrame({"q1": w[1].to_numpy() / 60.0, "h1": (w[1] + w[2]).to_numpy() / 60.0}, index=w.index)
    return out.reset_index()


def trusted_team_games(pm: pd.DataFrame) -> pd.DataFrame:
    """(game_id, team) whose segments fill the period: within TEAM_MINUTE_SLACK
    of 60 player-minutes in the first quarter and 120 in the first half."""
    t = pm.groupby(["game_id", "team"], as_index=False)[["q1", "h1"]].sum()
    ok = ((t["q1"] - TEAM_MINUTES["q1"]).abs() <= TEAM_MINUTE_SLACK) & (
        (t["h1"] - TEAM_MINUTES["h1"]).abs() <= TEAM_MINUTE_SLACK)
    return t.loc[ok, ["game_id", "team"]].reset_index(drop=True)


def period_history(panel: pd.DataFrame, pm: pd.DataFrame, min_hl: float) -> pd.DataFrame:
    """Per game a player played, in date order: his time-weighted first-quarter
    and first-half minutes AFTER that game (the shape of P.minutes_history). A
    game he played without touching the period counts 0: he played and sat. A
    team-game whose segments cannot be trusted gives no reading (NaN), so a
    missing file never reads as a benched player."""
    pl = panel.loc[panel["played"], ["game_id", "team", "player_id", "day"]]
    x = pl.merge(pm, on=["game_id", "team", "player_id"], how="left")
    good = trusted_team_games(pm).assign(_ok=True)
    x = x.merge(good, on=["game_id", "team"], how="left")
    ok = x["_ok"].fillna(False).astype(bool)
    x["q1"] = x["q1"].fillna(0.0).where(ok)
    x["h1"] = x["h1"].fillna(0.0).where(ok)
    x = x.sort_values(["player_id", "day"]).reset_index(drop=True)
    e = x.groupby("player_id")[["q1", "h1"]].ewm(halflife=min_hl).mean()
    e = e.reset_index(level=0, drop=True).reindex(x.index)
    return x[["player_id", "day"]].assign(m_q1=e["q1"].to_numpy(), m_h1=e["h1"].to_numpy())


# ── the expected minutes and ratings at T ───────────────────────────────────

def player_rows(w: P.World, st: P.State, model: P.Model, gm: pd.DataFrame, last: P.Last) -> pd.DataFrame:
    """One row per (game, team, player) at the game's T: the engine's as-of
    rating, P(plays), its full-game minutes (P.project's own arithmetic; the
    smoke run and a test hold them equal), and expected first-quarter and
    first-half minutes rescaled to 60 and 120. `gm` as P.project's. Columns are
    assigned by position: Last.asof and P.availability hand back fresh indexes."""
    st = model.st or st
    gm = gm.reset_index(drop=True)
    av = P.availability(w, st, P.sides_of(gm))
    o, d = P.box_rating(model.box, av)
    av["o"], av["d"] = o, d
    if model.rapm is not None and len(model.rapm):
        refits = np.sort(model.rapm["refit_day"].unique())
        j = np.searchsorted(refits, av["day"].to_numpy(np.int64), side="right") - 1
        av["refit_day"] = np.where(j >= 0, refits[np.maximum(j, 0)], -1)
        dev = av[["player_id", "refit_day"]].merge(model.rapm, on=["player_id", "refit_day"], how="left")
        av["o"] = av["o"].to_numpy() + dev["do"].fillna(0.0).to_numpy()
        av["d"] = av["d"].to_numpy() + dev["dd"].fillna(0.0).to_numpy()
    av["p_play"] = P.play_prob(model.play, av["status"], av["role"], av["bucket"])
    av["e_min"] = av["p_play"].to_numpy() * av["m"].to_numpy()
    av["min_fg"] = P.reallocate(av, ["game_id", "team"], "e_min", model.cap)
    x = last.asof(av[["player_id", "day"]])
    key = ["game_id", "team"]
    for p in PERIODS:
        av[f"m_{p}"] = x[f"m_{p}"].fillna(0.0).to_numpy(float)
        av[f"e_{p}"] = av["p_play"].to_numpy() * av[f"m_{p}"].to_numpy()
        av[f"min_{p}"] = P.reallocate(av, key, f"e_{p}", PLAYER_CAP[p], total=TEAM_MINUTES[p])
    return av[["game_id", "season", "team", "is_home", "player_id", "status", "covered", "o", "d",
               "p_play", "m", "m_q1", "m_h1", "min_fg", "min_q1", "min_h1"]].copy()


def team_ratings(pr: pd.DataFrame) -> pd.DataFrame:
    """Per (game, team): O_fg, D_fg (the engine's O and D), O_q1, D_q1, O_h1,
    D_h1 and the minutes each sums to. Every set of weights sums to five
    players, so a difference between two of them is a pure reweighting."""
    agg = {"is_home": ("is_home", "first"), "n_players": ("player_id", "size")}
    x = pr[["game_id", "team", "is_home", "player_id"]].copy()
    for label, minutes, per in (("fg", "min_fg", 48.0), ("q1", "min_q1", 12.0), ("h1", "min_h1", 24.0)):
        wgt = pr[minutes].to_numpy(float) / per
        x[f"O_{label}"] = wgt * pr["o"].to_numpy(float)
        x[f"D_{label}"] = wgt * pr["d"].to_numpy(float)
        x[minutes] = pr[minutes].to_numpy(float)
        agg.update({f"O_{label}": (f"O_{label}", "sum"), f"D_{label}": (f"D_{label}", "sum"),
                    minutes: (minutes, "sum")})
    return x.groupby(["game_id", "team"], as_index=False).agg(**agg)


def game_frame(w: P.World, st: P.State, model: P.Model, gm: pd.DataFrame, pr: pd.DataFrame) -> pd.DataFrame:
    """One row per game at T: both teams' ratings (_h, _a), the engine's as-of
    pace (pace_h x pace_a / league), and `ok`: the engine's box guard held and
    both teams' minutes reached all three totals (60, 120, 240). A team of
    exactly five fills both periods and stops at 5 x the cap over the game: its
    tilt would be a level error, not a change of who plays."""
    st = model.st or st
    gm = gm.reset_index(drop=True)
    t = team_ratings(pr)
    cols = [c for c in t.columns if c not in ("game_id", "team", "is_home")]
    hm = t[t["is_home"] == 1.0][["game_id", "team", *cols]].rename(columns={c: f"{c}_h" for c in cols})
    aw = t[t["is_home"] == 0.0][["game_id", "team", *cols]].rename(columns={c: f"{c}_a" for c in cols})
    out = gm[["game_id", "season", "day", "T", "home_team", "away_team"]].merge(
        hm.drop(columns="team"), on="game_id", how="left").merge(aw.drop(columns="team"), on="game_id", how="left")
    pace = lambda team: (lambda e: (e["pw"] / e["one"].replace(0, np.nan)).to_numpy())(  # noqa: E731
        st.team_pace.asof(pd.DataFrame({"team": out[team].to_numpy(), "day": out["day"].to_numpy()})))
    lg = P.league_asof(st, out["day"])
    out["pace"] = pace("home_team") * pace("away_team") / lg["pace_lg"].to_numpy()
    full = np.ones(len(out), bool)
    # a player with no rating would sum to a team of 0 and read as a tilt
    unrated = set(pr.loc[~np.isfinite(pr[["o", "d"]].to_numpy(float)).all(axis=1), "game_id"])
    full &= ~out["game_id"].isin(unrated).to_numpy()
    for s in ("h", "a"):
        for p in PERIODS:
            full &= ((out[f"min_{p}_{s}"] - TEAM_MINUTES[p]).abs() <= TEAM_MINUTE_SLACK).to_numpy()
        full &= ((out[f"min_fg_{s}"] - P.TEAM_MINUTES).abs() <= TEAM_MINUTE_SLACK).to_numpy()
        full &= out[f"n_players_{s}"].fillna(0).to_numpy() > 0
    out["box_ok"] = P.box_guard(w, out)
    out["ok"] = out["box_ok"].to_numpy() & full & np.isfinite(out["pace"].to_numpy(float))
    return out.drop(columns=["home_team", "away_team", "day"])


# ── the tilt, the base, beta, the projection, the gap ───────────────────────

def tilt_points(fr: pd.DataFrame) -> pd.DataFrame:
    """Per game with `ok`: xm_<p>, the margin tilt in period points toward the
    home team, and xt_<p>, the total tilt in period points. Tilt = period-weighted
    minus full-game-weighted; eff_h = L + O_h - D_a, eff_a = L + O_a - D_h."""
    f = fr[fr["ok"].astype(bool)].reset_index(drop=True)
    out = f[["game_id", "season"]].copy()
    pace = f["pace"].to_numpy(float)
    for p in PERIODS:
        t_oh, t_dh = (f[f"{c}_{p}_h"].to_numpy(float) - f[f"{c}_fg_h"].to_numpy(float) for c in ("O", "D"))
        t_oa, t_da = (f[f"{c}_{p}_a"].to_numpy(float) - f[f"{c}_fg_a"].to_numpy(float) for c in ("O", "D"))
        poss = pace * SHARE_OF_GAME[p]
        out[f"xm_{p}"] = ((t_oh - t_da) - (t_oa - t_dh)) * poss / 100.0
        out[f"xt_{p}"] = ((t_oh - t_da) + (t_oa - t_dh)) * poss / 100.0
    return out


def _spec(market: str) -> tuple[str, str]:
    """(the base's column, the tilt's column) of a market."""
    kind, p = market.rsplit("_", 1)
    return (f"margin_{p}", f"xm_{p}") if kind == "spreads" else (f"total_{p}", f"xt_{p}")


def fit_betas(base_ref: pd.DataFrame, x_ref: pd.DataFrame, results: pd.DataFrame, seasons=GRADED,
              first: int = FIT_FIRST, min_games: int = MIN_FIT_GAMES) -> tuple[dict, pd.DataFrame]:
    """({(graded season, market): beta}, the fit table). Least squares of the
    period result minus the base on the tilt points, over seasons `first` to
    S - 1 only; an intercept is fitted so a level bias in the base cannot lean
    on the slope, and it is not used in the projection. No floor: the sign is
    what was measured. Fewer than `min_games` stops the run."""
    d = base_ref.merge(x_ref.drop(columns="season"), on="game_id").merge(
        results.drop(columns="season"), on="game_id")
    betas, table = {}, []
    for S in sorted(int(s) for s in seasons):
        prior = d[(d["season"] >= first) & (d["season"] < S)]
        for m in MARKETS:
            bcol, xcol = _spec(m)
            res = bcol                                         # period_results names it the same
            x, y = prior[xcol].to_numpy(float), (prior[f"{res}_r"] - prior[bcol]).to_numpy(float)
            ok = np.isfinite(x) & np.isfinite(y)
            if ok.sum() < min_games:
                raise RuntimeError(f"beta for {S} {m}: {int(ok.sum())} earlier games, need {min_games}")
            a, b = P3._line_fit(x[ok], y[ok])
            e = y[ok] - a - b * x[ok]
            sxx = float(((x[ok] - x[ok].mean()) ** 2).sum())
            se = float(np.sqrt(e.var(ddof=2) / sxx)) if sxx > 0 else np.nan
            betas[(S, m)] = float(b)
            table.append({"season": S, "market": m, "beta": float(b), "se": se, "intercept": float(a),
                          "games": int(ok.sum()), "fit_seasons": f"{first}-{S - 1}",
                          "sd_x": float(x[ok].std())})
    return betas, pd.DataFrame(table)


def period_results_r(games_p: pd.DataFrame) -> pd.DataFrame:
    """P3.period_results with each result named <column>_r (the base holds the
    same names)."""
    r = P3.period_results(games_p)
    return r.rename(columns={c: f"{c}_r" for c in r.columns if c not in ("game_id", "season")})


def project_with_tilt(base: pd.DataFrame, x: pd.DataFrame, betas: dict) -> pd.DataFrame:
    """Per game: margin_<p>, total_<p> = base + beta x tilt points, and tilt_<market>,
    beta x tilt points alone (the part the tilt-only placebo moves)."""
    d = base.merge(x.drop(columns="season"), on="game_id")
    out = d[["game_id", "season"]].copy()
    seasons = d["season"].astype(int).to_numpy()
    for m in MARKETS:
        bcol, xcol = _spec(m)
        b = np.array([betas[(int(s), m)] for s in np.unique(seasons)])
        beta = b[np.searchsorted(np.unique(seasons), seasons)]
        part = beta * d[xcol].to_numpy(float)
        out[bcol] = d[bcol].to_numpy(float) + part
        out[f"tilt_{m}"] = part
    return out


def gap_frame(proj: pd.DataFrame, fair: pd.DataFrame) -> pd.DataFrame:
    """(game_id, market, strength): the projected centre minus the period
    market's fair centre at T, toward side A (the home team, the over)."""
    parts = []
    for m in MARKETS:
        col, _ = _spec(m)
        x = proj[["game_id", col]].merge(fair.loc[fair["market"] == m, ["game_id", "mu"]], on="game_id")
        parts.append(pd.DataFrame({"game_id": x["game_id"].to_numpy(), "market": m,
                                   "strength": x[col].to_numpy(float) - x["mu"].to_numpy(float)}))
    s = pd.concat(parts, ignore_index=True)
    return s[np.isfinite(s["strength"].to_numpy(float))].reset_index(drop=True)


# ── the placebo ─────────────────────────────────────────────────────────────

class ShuffledGaps:
    """One market's placebo runs, each a candidate frame for H.run_cells: the
    market's offers untouched, each carrying strength = own + moved[src], src
    one permutation per date per seed. The permutation and the offers are built
    once, as arrays, so a run costs a lookup and a date loop.

    Whole gap: own = 0, moved = the gap. Tilt only: own = the gap less the
    tilt's part, moved = the tilt's part. A game alone on its date keeps its
    number (that case is what `share_differs` exists to catch)."""

    def __init__(self, nm: pd.DataFrame, game_ids, own, moved, game_dates: pd.Series, seeds):
        ids = np.asarray(game_ids, dtype=object)
        pos = {g: i for i, g in enumerate(ids)}
        self.pos = pos
        self.own, self.moved = np.asarray(own, float), np.asarray(moved, float)
        self.base = nm[nm["game_id"].isin(pos)].drop(columns="strength", errors="ignore").reset_index(drop=True)
        self.codes = self.base["game_id"].map(pos).to_numpy(int)
        self.sign = np.where(self.base["side"].isin(["home", "over"]).to_numpy(), 1.0, -1.0)
        dates = game_dates.reindex(ids).to_numpy(dtype=object)
        self.groups = list(pd.Series(np.arange(len(ids))).groupby(dates, sort=False).indices.values())
        self.seeds = tuple(seeds)
        self.n = len(ids)

    def source(self, seed: int) -> np.ndarray:
        rng = np.random.default_rng(seed)
        src = np.arange(self.n)
        for idx in self.groups:
            src[idx] = idx[rng.permutation(len(idx))]
        return src

    def values(self, seed: int) -> np.ndarray:
        """Each game's number in this run, toward side A, in game_ids' order."""
        return self.own + self.moved[self.source(seed)]

    def frame(self, seed: int) -> pd.DataFrame:
        return self.base.assign(strength=self.sign * self.values(seed)[self.codes])

    def __iter__(self):
        return (self.frame(s) for s in self.seeds)

    def __len__(self):
        return len(self.seeds)


def _pick(c: pd.DataFrame, side: str, cut: float, books=H.BETTABLE) -> pd.DataFrame:
    """run_cells' own choice at a rule family's cut."""
    return H.choose(c[c["strength"] >= cut], -np.inf, books=books, sides=[side])


def share_differs(cand: pd.DataFrame, runs: ShuffledGaps, side: str, cut: float, n_runs: int = 10) -> dict:
    """For one cell, read on real or synthetic prices with no result: the share
    of its placebo bets that are not its real bets, over the first `n_runs`
    runs. `ceiling` is what a random draw of the same size would give, 1 minus
    the share of the market's games the cell bets: a cell that bets half of all
    games repeats half its games under ANY shuffle."""
    real = set(_pick(cand, side, cut)["game_id"])
    shares, sizes = [], []
    for s in runs.seeds[:n_runs]:
        b = set(_pick(runs.frame(s), side, cut)["game_id"])
        sizes.append(len(b))
        shares.append(1.0 - len(b & real) / len(b) if b else np.nan)
    pop = int(cand["game_id"].nunique())
    return {"real_bets": len(real), "placebo_bets": float(np.mean(sizes)) if sizes else 0.0,
            "share_differs": float(np.nanmean(shares)) if len(shares) and np.isfinite(shares).any() else np.nan,
            "ceiling": 1.0 - len(real) / pop if pop else np.nan}


# ── cells ───────────────────────────────────────────────────────────────────

def _dates(games: pd.DataFrame) -> pd.Series:
    return games.drop_duplicates("game_id").set_index("game_id")["game_date"].astype(str)


def whole_gap_runs(nm: pd.DataFrame, g: pd.DataFrame, dates: pd.Series, seeds) -> ShuffledGaps:
    v = g["strength"].to_numpy(float)
    return ShuffledGaps(nm, g["game_id"].to_numpy(), np.zeros(len(v)), v, dates, seeds)


def tilt_only_runs(nm: pd.DataFrame, g: pd.DataFrame, tilt: pd.Series, dates: pd.Series, seeds) -> ShuffledGaps:
    """`tilt`: the market's beta x tilt points by game_id."""
    v = g["strength"].to_numpy(float)
    part = tilt.reindex(g["game_id"]).to_numpy(float)
    return ShuffledGaps(nm, g["game_id"].to_numpy(), v - part, part, dates, seeds)


def tilt_series(proj: pd.DataFrame, market: str) -> pd.Series:
    return pd.Series(proj[f"tilt_{market}"].to_numpy(float), index=proj["game_id"].to_numpy())


def side_table(nm: pd.DataFrame, side: str, games: pd.DataFrame) -> pd.DataFrame:
    """The bet a side would place on each game, graded once: (game_id, season,
    units, risk). A rule's strength is the same for every offer of a side, so a
    cut keeps or drops a game's offers together and the chosen offer never
    depends on the cut or the run. That is what lets a placebo run be a lookup."""
    g = H.grade(H.choose(nm, -np.inf, sides=[side]), games)
    return g[["game_id", "season", "units", "risk"]].reset_index(drop=True)


def placebo_rois(runs: ShuffledGaps, table: pd.DataFrame, side: str, cut: float, seasons) -> list[float]:
    """Each run's return on `seasons` at this cut: what H.run_cells computes from
    its `placebo` frames, by arrays built once (a test holds the two equal, and
    the smoke run does on real offers with made-up scores). A run with no bet is
    NaN, as there; the verdict counts it as 0."""
    pos = table["game_id"].map(runs.pos).to_numpy(int)
    sign = 1.0 if side in ("home", "over") else -1.0
    keep = table["season"].isin(list(seasons)).to_numpy()
    u, r = table["units"].to_numpy(float), table["risk"].to_numpy(float)
    out = []
    for s in runs.seeds:
        sel = keep & (sign * runs.values(s)[pos] >= cut)
        risk = r[sel].sum()
        out.append(float(u[sel].sum() / risk) if risk > 0 else float("nan"))
    return out


def _row_seasons(row: dict) -> list[int]:
    return [int(s) for s in str(row["choose_seasons"]).split(",") if s]


def emit_family(dd: H.Data, family: str, gap: pd.DataFrame, neutral: pd.DataFrame, choose, times,
                n_placebo: int = N_PLACEBO, proj: pd.DataFrame | None = None, say=None) -> tuple[list[dict], dict]:
    """The family's 32 cells through H.run_cells, each row with its bands. The
    placebo moves the whole gap; `proj` given (the starters' family), the runs
    that move the tilt alone are reported beside each row."""
    seeds = PLACEBO_SEEDS[:n_placebo]
    dates = _dates(dd.games)
    rows, cands = [], {}
    for market in MARKETS:
        nm = neutral[neutral["market"] == market]
        g = gap[gap["market"] == market].reset_index(drop=True)
        cand = tl.side_strength(nm, g)
        cands[market] = cand
        t0 = time.time()
        got = G5.run_market(dd, family, POINT, market, SIDES[market], CUTS[market], cand, nm, None,
                            "strength", choose, times,
                            extra={"signal_meaning": ("the league's period share plus the starters' tilt, "
                                                      "against the period market's fair centre")
                                   if family == FAMILY else
                                   "the league's period share alone (the control)"})
        numbered = nm[nm["game_id"].isin(set(g["game_id"]))]
        tables = {sd: side_table(numbered, sd, dd.games) for sd in SIDES[market]}
        whole = whole_gap_runs(nm, g, dates, seeds)
        only = tilt_only_runs(nm, g, tilt_series(proj, market), dates, seeds) if proj is not None else None
        for r in got:
            r["placebo_rois"] = placebo_rois(whole, tables[r["side"]], r["side"], r["cut"], _row_seasons(r))
            if only is not None:
                # reported beside, never a bar; a run with no bet counts as 0, as the verdict counts it
                a = np.nan_to_num(np.array(placebo_rois(only, tables[r["side"]], r["side"], r["cut"],
                                                        _row_seasons(r)), float))
                r.update({"tilt_placebo_runs": int(len(a)),
                          "tilt_placebo_mean": float(a.mean()) if len(a) else np.nan,
                          "tilt_placebo_p95": float(np.percentile(a, 95)) if len(a) else np.nan})
        rows += got
        if say:
            say(f"{family} {market}: {len(got)} cells in {time.time() - t0:.0f}s")
    assert len(rows) == EXPECTED_CELLS, len(rows)
    return rows, cands


def credit_table(cells: pd.DataFrame) -> pd.DataFrame:
    """Section 9's bars with this search's credit rule: a spread cell counts for
    the starters only if it passes and its pooled return beats the control's at
    the same market, side and cut (a control with no bet counts as 0). A total
    cell is never creditable, whatever the two returns are. `counts_for` says
    whose idea each pass reads as; a row that fails reads as nobody's."""
    c = V.house_verdict_bands(cells, judge_controls=(), credit={FAMILY: CONTROL})
    s1 = (c["family"].astype(str) == FAMILY).to_numpy()
    c["creditable"] = ~(s1 & c["market"].astype(str).isin(NO_CREDIT_MARKETS).to_numpy())
    c["credited"] = c["credited"].to_numpy() & c["creditable"].to_numpy()
    c["counts_for"] = np.select(
        [~c["house5_passes"].to_numpy(bool), c["credited"].to_numpy(bool) & s1, ~c["creditable"].to_numpy() | ~s1],
        ["", STARTERS_IDEA, LEAGUE_IDEA], default=NOT_THE_STARTERS)
    return c


# ── a synthetic world (the only place a cell is run before --full) ──────────

def synthetic_tilts(games: pd.DataFrame, seed: int = 11, sd: float = 1.0) -> pd.DataFrame:
    """Made-up tilt points per game, large enough to cross every cut."""
    rng = np.random.default_rng(seed)
    out = games[["game_id", "season"]].drop_duplicates("game_id").reset_index(drop=True)
    for c in ("xm_q1", "xt_q1", "xm_h1", "xt_h1"):
        out[c] = rng.normal(0.0, sd, len(out))
    return out


def synthetic_run(world: dict | None = None, n_placebo: int = 2) -> dict:
    """All 32 cells and 32 controls on G5.synthetic_world, with the lab's own
    functions from the quotes on, and its beta fit on made-up tilts."""
    w = G5.synthetic_world() if world is None else world
    games_p, data, pe = w["games_p"], w["data"], w["pe"]
    graded, choose = w["f7_graded"], w["f7_choose"]
    pe4 = pe[pe["market"].isin(MARKETS)].reset_index(drop=True)
    assert set(pe4["market"]) == set(MARKETS), "the synthetic world lacks a market this search bets"
    times = H.per_event_times(pe4, POINT)
    vis = NB.visible_numbers(pe4, times)
    pricing = P3.period_market_pricing(w["close"], games_p, graded)
    P3.require_pricing(pricing, graded, MARKETS, "synthetic pricing")
    neutral = P3.neutral_offers(vis, pricing)
    fair = H.market_fair(vis, pricing)
    sig = H.close_dist(w["close"], data.games)
    full = G5.full_game_numbers(G5.full_game_visible(data.quotes, times), sig)
    sh = G5.game_shares(games_p[games_p["season"].isin(graded)], G5.team_period_rows(games_p), G5.REGISTERED_K)
    base = G5.f7_projection(full, sh, league_only=True)
    # the fit: the world's slate fetch sits at tip - 60, the fit's own T
    g = data.games[data.games["season"].isin(sorted(set(data.quotes["season"])))]
    ref = g.assign(T=g["tip"] - P.REF_LEAD)[["game_id", "T"]]
    full_ref = G5.full_game_numbers(G5.full_game_visible(data.quotes, ref), sig)
    sh_ref = G5.game_shares(games_p[games_p["game_id"].isin(ref["game_id"])], G5.team_period_rows(games_p),
                            G5.REGISTERED_K)
    base_ref = G5.f7_projection(full_ref, sh_ref, league_only=True)
    x_all = synthetic_tilts(games_p)
    betas, table = fit_betas(base_ref, x_all, period_results_r(games_p), seasons=graded,
                             first=min(int(s) for s in base_ref["season"]))
    # a fixed slope for the cells, so the tilt reaches them whatever the fit read
    proj = project_with_tilt(base, x_all, {k: 1.0 for k in betas})
    dd = P3.derivative_data(games_p[games_p["season"].isin(graded)], pe4)
    gap = gap_frame(proj, fair)
    gap_c = gap_frame(base, fair)
    rows, cands = emit_family(dd, FAMILY, gap, neutral, choose, times, n_placebo, proj=proj)
    ctl, cands_c = emit_family(dd, CONTROL, gap_c, neutral, choose, times, n_placebo)
    return {"rows": rows, "control": ctl, "gap": gap, "gap_control": gap_c, "betas": betas, "fit": table,
            "proj": proj, "base": base, "neutral": neutral, "dd": dd, "times": times, "choose": choose,
            "cands": cands, "cands_control": cands_c, "fair": fair, "world": w, "x": x_all}


def synthetic_checks(n_placebo: int = 2) -> dict:
    """Before any real data is read (--smoke, --full): the harness's sign
    checks, every market present and betting at its lowest cut, a true null
    under the placebo. NBA_GAME2_BETS is unset while they run, so no made-up
    bet lands in a graded run's folder."""
    H.check()
    saved = os.environ.pop(BETS_ENV, None)
    try:
        out = synthetic_run(n_placebo=n_placebo)
    finally:
        if saved is not None:
            os.environ[BETS_ENV] = saved
    for fam, rows in ((FAMILY, out["rows"]), (CONTROL, out["control"])):
        assert len(rows) == EXPECTED_CELLS and {r["family"] for r in rows} == {fam}
        t = pd.DataFrame(rows)
        got = t[t["cut_index"] == 0].groupby("market")["pool_n"].sum()
        assert set(got.index) == set(MARKETS) and (got > 0).all(), f"{fam}: a market placed no bet: {got.to_dict()}"
        assert all(len(r["placebo_rois"]) == n_placebo for r in rows)
    m = MARKETS[0]
    g = out["gap"][out["gap"]["market"] == m]
    runs = whole_gap_runs(out["neutral"][out["neutral"]["market"] == m], g, _dates(out["dd"].games), PLACEBO_SEEDS[:5])
    d = share_differs(out["cands"][m], runs, "home", CUTS[m][0], 5)
    assert d["share_differs"] > 0.3, d
    print(f"synthetic: {EXPECTED_CELLS} + {EXPECTED_CELLS} cells; every market bets; placebo bets differing {d['share_differs']:.2f}; nothing written")
    return out


# ── the engine, saved so a re-run repeats none of it ────────────────────────

ENGINE_FILES = ("nba_games.parquet", "nba_player_game_adv.parquet", "nba_player_game_log.parquet",
                "nba_game_inactives.parquet", "nba_injury_report.parquet", "nba_stints.parquet")
PRICE_FILES = ("nba_games.parquet", "nba_odds.parquet", "nba_fetch_ledger.parquet", "nba_period_scores.parquet")


def _fingerprint(cache: Path, files=ENGINE_FILES, code=None) -> dict:
    """What a saved output depends on: the cache files it reads and the code
    that built it. A different fingerprint rebuilds rather than reuses."""
    out = {f: [(Path(cache) / f).stat().st_size, int((Path(cache) / f).stat().st_mtime)] for f in files}
    for m in (code if code is not None else (P,)):
        out[Path(m.__file__).name] = hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
    return out


def _saved(d: Path, name: str, fp: dict, build, say=log):
    """<d>/<name>.pkl when its fingerprint matches, else built once and saved."""
    path, stamp = Path(d) / f"{name}.pkl", Path(d) / f"{name}_fingerprint.json"
    if path.exists() and stamp.exists() and json.loads(stamp.read_text(encoding="utf-8")) == fp:
        say(f"{name}: reading {path}")
        with open(path, "rb") as f:
            return pickle.load(f)
    say(f"{name}: building (saved after, so this runs once)")
    t0 = time.time()
    out = build()
    Path(d).mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(out, f)
    stamp.write_text(json.dumps(fp), encoding="utf-8")
    (Path(d) / f"{name}_seconds.json").write_text(json.dumps({"seconds": time.time() - t0}), encoding="utf-8")
    say(f"{name}: built in {time.time() - t0:.0f}s, saved to {path}")
    return out


def build_engine(w: P.World, say=log) -> dict:
    """The second search's setup (P.run_projection_setup), what it fitted."""
    hp, st, models, _, _ = P.run_projection_setup(w, LAST_SEASON, log=say)
    return {"first_hp": {k: v for k, v in hp.items() if k != "mse"},
            "models": {s: {"season": m.season, "box": m.box, "play": m.play, "cap": m.cap, "rapm": m.rapm,
                           "info": m.info, "hp": {k: v for k, v in m.st.hp.items() if k != "mse"}}
                       for s, m in models.items()}}


def engine(cache: Path, w: P.World, scratch: Path, say=log) -> dict:
    return _saved(Path(scratch) / ENGINE_DIR, ENGINE_NAME, _fingerprint(cache), lambda: build_engine(w, say), say)


def market_pricing(cache: Path, scratch: Path, data: H.Data, games_p: pd.DataFrame, graded, say=log) -> dict:
    """{"sig": the full game's pricing, "pricing": the period markets'}
    (H.close_dist, P3.period_market_pricing). Reads earlier seasons' results
    only. It took most of the setup's clock, so it is saved too."""
    fp = {**_fingerprint(cache, PRICE_FILES, (H, P3)), "impossible": repr(IMPOSSIBLE), "graded": repr(tuple(graded))}

    def build():
        close = H.pinnacle_close(data)
        gp = games_p[games_p["season"].isin(data.games["season"])]
        return {"sig": H.close_dist(close, data.games), "pricing": P3.period_market_pricing(close, gp, graded)}
    return _saved(Path(scratch) / ENGINE_DIR, "market_pricing", fp, build, say)


def models_from(eng: dict, w: P.World) -> dict:
    """P.Model per season, each state rebuilt from its saved half-lives (the
    state is arrays over the world; it is seconds to build, gigabytes to keep)."""
    states, out = {}, {}
    for s, m in eng["models"].items():
        key = tuple(sorted((k, str(v)) for k, v in m["hp"].items()))
        if key not in states:
            states[key] = P.build_state(w, m["hp"])
        out[s] = P.Model(season=m["season"], box=m["box"], play=m["play"], cap=m["cap"], rapm=m["rapm"],
                         info=m["info"], st=states[key])
    return out


def frames_at(w: P.World, models: dict, gm: pd.DataFrame, last: P.Last, say=log) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(player rows, game frame) at each game's T, each season by its own model."""
    prs, frs = [], []
    for S in sorted(int(s) for s in gm["season"].unique()):
        t0 = time.time()
        g = gm[gm["season"] == S]
        pr = player_rows(w, models[S].st, models[S], g, last)
        prs.append(pr)
        frs.append(game_frame(w, models[S].st, models[S], g, pr))
        say(f"  {S}: {len(pr):,} player rows, {len(g):,} games ({time.time() - t0:.0f}s)")
    return pd.concat(prs, ignore_index=True), pd.concat(frs, ignore_index=True)


def frames_fingerprint(cache: Path, times: pd.DataFrame) -> dict:
    """What the saved frames depend on: the cache, the engine's code, the lab's
    own functions that build them, and each game's T. A saved frame built by
    other code must not pass for this code's: the betas would be read from it."""
    src = "".join(inspect.getsource(f) for f in (period_minutes, trusted_team_games, period_history, player_rows,
                                                 team_ratings, game_frame, frames_at))
    return {**_fingerprint(cache), "frames": FRAMES_VERSION, "lab": hashlib.sha256(src.encode("utf-8")).hexdigest(),
            "times": hashlib.sha256(times[["game_id", "T"]].astype(str).sort_values("game_id")
                                    .to_csv(index=False).encode()).hexdigest()}


def saved_frames(cache: Path, scratch: Path, times: pd.DataFrame, say=log) -> dict:
    """The per-player and per-game frames at the purchase instant (graded
    seasons) and at tip - 60 (the beta fit's seasons), read when their
    fingerprint matches, else built and saved. Numbers and strings only."""
    d = Path(scratch) / ENGINE_DIR
    fp = frames_fingerprint(cache, times)
    stamp = d / "frames_fingerprint.json"
    names = ("players_T", "games_T", "players_ref", "games_ref")
    if stamp.exists() and json.loads(stamp.read_text(encoding="utf-8")) == fp and all(
            (d / f"{n}.parquet").exists() for n in names):
        say("frames: reading the saved per-player frames")
        return {n: pd.read_parquet(d / f"{n}.parquet") for n in names}
    say("frames: building")
    w = P.load_world(cache, max_season=LAST_SEASON)
    eng = engine(cache, w, scratch, say)
    models = models_from(eng, w)
    pm = period_minutes(pd.read_parquet(Path(cache) / P.STINTS_FILE, columns=STINT_COLS))
    last = P.Last(period_history(w.panel, pm, eng["first_hp"]["min_hl"]), "player_id", ["m_q1", "m_h1"])
    gm_t = w.games.merge(times[["game_id", "T"]], on="game_id")
    pl_t, fr_t = frames_at(w, models, gm_t, last, say)
    ref = w.games[(w.games["season"] >= FIT_FIRST) & (w.games["season"] < LAST_SEASON)]
    pl_r, fr_r = frames_at(w, models, ref.assign(T=ref["tip"] - P.REF_LEAD), last, say)
    d.mkdir(parents=True, exist_ok=True)
    out = {"players_T": pl_t, "games_T": fr_t, "players_ref": pl_r, "games_ref": fr_r}
    for n, f in out.items():
        f.to_parquet(d / f"{n}.parquet")
    stamp.write_text(json.dumps(fp), encoding="utf-8")
    return out


# ── real data ───────────────────────────────────────────────────────────────

def near_t(q: pd.DataFrame, times: pd.DataFrame) -> pd.DataFrame:
    """The slate quotes that can show at each game's T: its fetch at or before
    T and within the hour (G5.full_game_visible's own rule), cut first so the
    main-rung sort runs on a fraction of the file."""
    x = q.merge(times[["game_id", "T"]], on="game_id")
    x = x[(x["fetch_at"] <= x["T"]) & (x["fetch_at"] >= x["T"] - pd.Timedelta(minutes=H.STALE_MIN))]
    return x.drop(columns="T").reset_index(drop=True)


def prepare(cache: Path, require: bool, scratch: Path, say=log) -> dict:
    """Every frame the cells read, on the real cache. No grade."""
    t0 = time.time()
    real = G5.load_real(cache, require)
    data, games_p, pe, graded = real["data"], real["games_p"], real["pe"], real["graded"]
    if tuple(graded) != GRADED:
        raise RuntimeError(f"derivative seasons {graded}, this search grades exactly {GRADED}")
    say(f"prices loaded ({time.time() - t0:.0f}s)")
    pe_raw = pe[pe["market"].isin(MARKETS)].reset_index(drop=True)
    q_raw = data.quotes[data.quotes["market"].isin(["spreads", "totals"])].reset_index(drop=True)
    real.clear()                                    # the moneylines and team totals are not read again
    del pe
    bad_rows = pd.concat([pe_raw[impossible_mask(pe_raw)], q_raw[impossible_mask(q_raw)]], ignore_index=True)
    pe4, drop_p = drop_impossible(pe_raw)
    q, drop_f = drop_impossible(q_raw)
    data = H.Data(games=data.games, quotes=q, fetches=data.fetches, notes=data.notes)
    mp = market_pricing(cache, scratch, data, games_p, graded, say)
    sig, pricing = mp["sig"], mp["pricing"]
    say(f"pricing ({time.time() - t0:.0f}s)")
    times = H.per_event_times(pe4, POINT)
    vis, drop_vis = drop_unpriceable(NB.visible_numbers(pe4, times))
    gp_priced = games_p[games_p["season"].isin(data.games["season"])]
    P3.require_pricing(pricing, graded, MARKETS, "the market's own pricing")
    neutral = P3.neutral_offers(vis, pricing)
    fair = H.market_fair(vis, pricing)
    say(f"offers ({time.time() - t0:.0f}s)")
    vis_f = G5.full_game_visible(near_t(q, times), times)
    full = G5.full_game_numbers(vis_f, sig)
    g_ref = data.games[(data.games["season"] >= FIT_FIRST) & (data.games["season"] < LAST_SEASON)]
    ref = g_ref.assign(T=g_ref["tip"] - P.REF_LEAD)[["game_id", "T"]]
    vis_r = G5.full_game_visible(near_t(q, ref), ref)
    full_ref = G5.full_game_numbers(vis_r, sig)
    tp = G5.team_period_rows(games_p)
    sh = G5.game_shares(games_p[games_p["season"].isin(graded)], tp, G5.REGISTERED_K)
    sh_ref = G5.game_shares(games_p[games_p["game_id"].isin(ref["game_id"])], tp, G5.REGISTERED_K)
    base = G5.f7_projection(full, sh, league_only=True)
    base_ref = G5.f7_projection(full_ref, sh_ref, league_only=True)
    say(f"full-game numbers and league shares ({time.time() - t0:.0f}s)")
    fr = saved_frames(cache, scratch, times, say)
    x, x_ref = tilt_points(fr["games_T"]), tilt_points(fr["games_ref"])
    betas, fit = fit_betas(base_ref, x_ref, period_results_r(games_p))
    say(f"tilts and betas ({time.time() - t0:.0f}s)")
    proj = project_with_tilt(base, x, betas)
    # A game with no trusted period score has no settlement: no bet (H.grade would stop).
    gp = gp_priced[gp_priced["season"].isin(graded)]
    settled = set(gp.loc[np.isfinite(gp[list(H.PERIOD_COLS)].to_numpy(float)).all(axis=1), "game_id"])
    no_settlement = int((~gp["game_id"].isin(settled)).sum())
    neutral = neutral[neutral["game_id"].isin(settled)].reset_index(drop=True)
    gap = gap_frame(proj, fair)
    gap = gap[gap["game_id"].isin(settled)].reset_index(drop=True)
    # the control sits on the same games as the cells, so the two compare like with like
    gap_c = gap_frame(base, fair).merge(gap[["game_id", "market"]], on=["game_id", "market"])
    dd = P3.derivative_data(gp, pe4)
    return {"dd": dd, "times": times, "vis": vis, "vis_f": vis_f, "vis_r": vis_r, "neutral": neutral,
            "fair": fair, "full": full, "base": base, "base_ref": base_ref, "x": x, "x_ref": x_ref,
            "betas": betas, "fit": fit, "proj": proj, "gap": gap, "gap_control": gap_c, "frames": fr,
            "pe_raw": pe_raw, "q_raw": q_raw, "dropped": {**drop_p, **drop_f, "visible_price": drop_vis},
            "no_settlement": no_settlement, "bad_rows": bad_rows, "graded": tuple(graded),
            "seconds": time.time() - t0}


def _extremes(d: pd.DataFrame, line: str = "line") -> pd.DataFrame:
    return d.groupby("market").agg(rows=(line, "size"), line_min=(line, "min"), line_max=(line, "max"),
                                   a_min=("price_a", "min"), a_max=("price_a", "max"),
                                   b_min=("price_b", "min"), b_max=("price_b", "max")).round(2)


def extremes(prep: dict) -> None:
    """Every line and price this search reads, and the highest-EV offers, so a
    row filed wrong shows before it can look like an edge."""
    print("\nEXTREMES. Impossible-number rule:", IMPOSSIBLE, "main price past +-", MAX_MAIN_PRICE)
    print("rows dropped by the rule:", prep["dropped"] or "none")
    bad = prep.get("bad_rows")
    if bad is not None and len(bad):
        print(bad.sort_values("line")[["game_id", "market", "book", "fetch_at", "line", "price_a", "price_b"]].to_string(index=False))
    print("period markets, every stored rung:\n", _extremes(prep["pe_raw"]).to_string())
    print("period markets, the main numbers visible at T:\n", _extremes(prep["vis"]).to_string())
    print("full game, every stored quote:\n", _extremes(prep["q_raw"]).to_string())
    print("full game, visible at T:\n", _extremes(prep["vis_f"]).to_string())
    print("full game, visible at the fit's tip - 60:\n", _extremes(prep["vis_r"]).to_string())
    print("the market's fair centres:\n", prep["fair"].groupby("market")["mu"].describe().round(2).to_string())
    n = prep["neutral"]
    c = n[n["book"].isin(H.BETTABLE) & (n["price"] >= H.PRICE_FLOOR)]
    cols = ["game_id", "market", "side", "book", "line", "price", "mu", "ev"]
    print("the 12 highest-EV deciding offers under the market's own fair line (no result read):\n",
          c.sort_values("ev", ascending=False).head(12)[cols].round(3).to_string(index=False))
    print("EV by market:\n", c.groupby("market")["ev"].describe().round(3).to_string())
    g = prep["gap"]
    top = g.assign(a=g["strength"].abs()).sort_values("a", ascending=False).groupby("market").head(3)
    print("the largest gaps per market:\n", top[["game_id", "market", "strength"]].round(2).to_string(index=False))
    print("how far the reference strays: Pinnacle's main number minus the deciding books' median, at T:\n",
          reference_gaps(prep["vis"]).round(3).to_string())
    best = c.sort_values("ev", ascending=False).drop_duplicates(["game_id", "market"]).head(3)
    v = prep["vis"].merge(best[["game_id", "market"]], on=["game_id", "market"])
    print("every book's main number on the three highest-EV games:\n",
          v.sort_values(["game_id", "market", "book"])[["game_id", "market", "book", "fetch_at", "line", "price_a", "price_b"]]
          .to_string(index=False))


def reference_gaps(vis: pd.DataFrame) -> pd.DataFrame:
    """Per market: the spread of (Pinnacle's main number - the deciding books'
    median main number) at T. The market's fair centre leans on Pinnacle, so a
    stale or misfiled Pinnacle row would show here first."""
    v = vis[vis["coherent"].astype(bool)]
    pin = v[v["book"] == H.SHARP].groupby(["game_id", "market"])["line"].first()
    med = v[v["book"].isin(H.BETTABLE)].groupby(["game_id", "market"])["line"].median()
    d = (pin - med).dropna().rename("diff").reset_index()
    return d.groupby("market")["diff"].describe(percentiles=[.001, .01, .5, .99, .999])


def starter_minutes(cache: Path) -> pd.DataFrame:
    """Starters' share of first-quarter, first-half and full-game player-minutes
    by season, from the box score's starter flag and the segments. A description
    of the idea only: the flag is never an input to a number at T."""
    pm = period_minutes(pd.read_parquet(Path(cache) / P.STINTS_FILE, columns=STINT_COLS))
    adv = pd.read_parquet(Path(cache) / "nba_player_game_adv.parquet",
                          columns=["game_id", "player_id", "team", "is_starter", "played", "minutes_exact",
                                   "season", "game_type"])
    adv = adv[(adv["game_type"] == "regular") & (adv["played"] == True)].copy()  # noqa: E712
    adv["player_id"] = adv["player_id"].astype(str)
    adv["fg"] = pd.to_numeric(adv["minutes_exact"], errors="coerce").fillna(0.0)
    adv["st"] = pd.to_numeric(adv["is_starter"], errors="coerce").fillna(0.0) == 1
    x = adv.merge(pm, on=["game_id", "team", "player_id"], how="left").fillna({"q1": 0.0, "h1": 0.0})
    x = x.merge(trusted_team_games(pm).assign(_ok=True), on=["game_id", "team"])
    rows = []
    for s, d in x.groupby("season"):
        st = d[d["st"]]
        rows.append({"season": int(s), "team_games": int(d[["game_id", "team"]].drop_duplicates().shape[0]),
                     "starters_q1_share": st["q1"].sum() / d["q1"].sum(),
                     "starters_h1_share": st["h1"].sum() / d["h1"].sum(),
                     "starters_game_share": st["fg"].sum() / d["fg"].sum(),
                     "starter_q1_minutes": st["q1"].mean(), "starter_h1_minutes": st["h1"].mean(),
                     "starter_game_minutes": st["fg"].mean()})
    return pd.DataFrame(rows)


def minutes_accuracy(pr: pd.DataFrame, cache: Path) -> pd.DataFrame:
    """How close the expected first-quarter minutes at T are to what happened,
    by season, against a flat share of the full-game minutes (a quarter of his
    expected game). Minutes only: no price, no bet."""
    pm = period_minutes(pd.read_parquet(Path(cache) / P.STINTS_FILE, columns=STINT_COLS))
    good = trusted_team_games(pm).assign(_ok=True)
    x = pr[["game_id", "season", "team", "player_id", "min_q1", "min_h1", "min_fg"]].merge(
        good, on=["game_id", "team"]).merge(pm, on=["game_id", "team", "player_id"], how="left").fillna({"q1": 0.0, "h1": 0.0})
    rows = []
    for s, d in x.groupby("season"):
        rows.append({"season": int(s), "rows": len(d),
                     "rmse_q1_tilted": float(np.sqrt(((d["min_q1"] - d["q1"]) ** 2).mean())),
                     "rmse_q1_flat": float(np.sqrt(((d["min_fg"] / 4.0 - d["q1"]) ** 2).mean())),
                     "rmse_h1_tilted": float(np.sqrt(((d["min_h1"] - d["h1"]) ** 2).mean())),
                     "rmse_h1_flat": float(np.sqrt(((d["min_fg"] / 2.0 - d["h1"]) ** 2).mean()))})
    return pd.DataFrame(rows)


def counts(prep: dict) -> dict:
    """Games per season; the gap's size with and without the tilt; games per
    band; the bets each cell and control would place with a deciding offer at
    or above the floor. Counted, never graded."""
    dd, gap, gap_c, neutral = prep["dd"], prep["gap"], prep["gap_control"], prep["neutral"]
    season = dd.games.drop_duplicates("game_id").set_index("game_id")["season"].astype(int)

    def by_season(ids):
        return {int(k): int(v) for k, v in season.reindex(pd.unique(np.asarray(list(ids), dtype=object)))
                .value_counts().sort_index().items()}

    ok_t = prep["frames"]["games_T"]
    pop = {"games": by_season(season.index), "with_a_decision": by_season(prep["times"]["game_id"]),
           "with_full_game_numbers": by_season(prep["full"]["game_id"]),
           "with_a_tilt": by_season(ok_t.loc[ok_t["ok"].astype(bool), "game_id"]),
           "with_a_number": by_season(gap["game_id"]),
           "report_known_at_T": by_season(prep["frames"]["players_T"].loc[
               prep["frames"]["players_T"]["covered"].astype(bool), "game_id"])}
    sizes, bands, cells = [], [], []
    dates = _dates(dd.games)
    for m in MARKETS:
        s1 = gap[gap["market"] == m].set_index("game_id")["strength"]
        c0 = gap_c[gap_c["market"] == m].set_index("game_id")["strength"].reindex(s1.index)
        part = tilt_series(prep["proj"], m).reindex(s1.index)
        # how much of the tilt the books' number already holds: the slope of
        # (market's centre - base) on the tilt points, over the same games; no result read
        _, xcol = _spec(m)
        x = prep["x"].set_index("game_id")[xcol].reindex(s1.index).to_numpy(float)
        ok = np.isfinite(x) & np.isfinite(c0.to_numpy(float))
        sizes.append({"market": m, "gap_sd": s1.std(), "control_gap_sd": c0.std(), "tilt_part_sd": part.std(),
                      "tilt_points_sd": float(np.nanstd(x)), "corr_control_gap_tilt_part": float(c0.corr(part)),
                      "books_hold_slope": float(P3._line_fit(x[ok], -c0.to_numpy(float)[ok])[1]) if ok.sum() > 2 else np.nan,
                      "gap_mean": s1.mean(), "control_gap_mean": c0.mean(), "tilt_part_mean": part.mean()})
        edges = (0.0, *CUTS[m], np.inf)
        for sd, v in ((SIDES[m][0], s1.to_numpy()), (SIDES[m][1], -s1.to_numpy())):
            bands.append({"market": m, "side": sd, **{f"band_{lo:g}": int(((v >= lo) & (v < hi)).sum())
                                                       for lo, hi in zip(edges[:-1], edges[1:])}})
        nm = neutral[neutral["market"] == m]
        cand = tl.side_strength(nm, gap[gap["market"] == m])
        cand_c = tl.side_strength(nm, gap_c[gap_c["market"] == m])
        for side in SIDES[m]:
            for k, cut in enumerate(CUTS[m]):
                b, bc = _pick(cand, side, cut), _pick(cand_c, side, cut)
                by = season.reindex(b["game_id"]).value_counts()
                both = len(set(b["game_id"]) & set(bc["game_id"]))
                cells.append({"market": m, "side": side, "cut": cut,
                              **{f"bets_{s}": int(by.get(s, 0)) for s in GRADED},
                              "bets_pooled": int(len(b)), "control_bets": int(len(bc)),
                              "share_also_control": both / len(b) if len(b) else np.nan,
                              "only_cell": int(len(b) - both), "only_control": int(len(bc) - both)})
    return {"population": pop, "sizes": pd.DataFrame(sizes), "bands": pd.DataFrame(bands),
            "cells": pd.DataFrame(cells), "alone_on_date": float(
                (gap.assign(d=gap["game_id"].map(dates)).groupby(["market", "d"])["game_id"]
                 .transform("size") == 1).mean())}


def placebo_null(prep: dict, n_runs: int = 10) -> pd.DataFrame:
    """Per cell, on the real prices with no result read: the share of placebo
    bets differing from the real bets, for the registered whole-gap shuffle and
    for moving the tilt alone (the fifth search's pattern, the alternative)."""
    dates = _dates(prep["dd"].games)
    out = []
    seeds = PLACEBO_SEEDS[:n_runs]
    for m in MARKETS:
        nm = prep["neutral"][prep["neutral"]["market"] == m]
        g = prep["gap"][prep["gap"]["market"] == m].reset_index(drop=True)
        cand = tl.side_strength(nm, g)
        whole = whole_gap_runs(nm, g, dates, seeds)
        only = tilt_only_runs(nm, g, tilt_series(prep["proj"], m), dates, seeds)
        gc = prep["gap_control"][prep["gap_control"]["market"] == m].reset_index(drop=True)
        cand_c = tl.side_strength(nm, gc)
        whole_c = whole_gap_runs(nm, gc, dates, seeds)
        for side in SIDES[m]:
            for cut in CUTS[m]:
                a, b, c = (share_differs(cand, whole, side, cut, n_runs), share_differs(cand, only, side, cut, n_runs),
                           share_differs(cand_c, whole_c, side, cut, n_runs))
                out.append({"market": m, "side": side, "cut": cut, "real_bets": a["real_bets"],
                            "whole_gap_differs": a["share_differs"], "ceiling": a["ceiling"],
                            "tilt_only_differs": b["share_differs"], "control_bets": c["real_bets"],
                            "control_differs": c["share_differs"]})
    return pd.DataFrame(out)


def peak_gb() -> float:
    try:
        import psutil
        m = psutil.Process().memory_info()
        return float(getattr(m, "peak_wset", m.rss)) / 2 ** 30
    except Exception:  # noqa: BLE001  (a report line, never a reason to stop)
        return float("nan")


def time_cells(prep: dict) -> dict:
    """The clock on real offers with made-up results: the games frame carries
    random scores of the same shape, so every merge and settlement costs what it
    will cost and no real bet is graded. Nothing it computes is printed or kept
    but the seconds. NBA_GAME2_BETS is unset while it runs."""
    saved = os.environ.pop(BETS_ENV, None)
    try:
        dd = prep["dd"]
        rng = np.random.default_rng(0)
        fake = dd.games.copy()
        for c in ("home_score", "away_score", *H.PERIOD_COLS):
            fake[c] = rng.integers(10, 140, len(fake)).astype(float)
        dd_fake = H.Data(games=fake, quotes=dd.quotes, fetches=dd.fetches)
        dates = _dates(dd.games)
        choose = P3.choosing(prep["graded"])
        results = {}
        for m, side, k in (("spreads_q1", "home", 0), ("totals_h1", "under", 0)):
            nm = prep["neutral"][prep["neutral"]["market"] == m]
            g = prep["gap"][prep["gap"]["market"] == m].reset_index(drop=True)
            cand = tl.side_strength(nm, g)
            cut = CUTS[m][k]
            t0 = time.time()
            tbl = side_table(nm[nm["game_id"].isin(set(g["game_id"]))], side, fake)
            per_table = time.time() - t0
            runs = whole_gap_runs(nm, g, dates, PLACEBO_SEEDS[:N_PLACEBO])
            t0 = time.time()
            fast = placebo_rois(runs, tbl, side, cut, choose)
            per_run = (time.time() - t0) / N_PLACEBO
            # the array path against run_cells' own frame-by-frame path, two runs
            slow_runs = whole_gap_runs(nm, g, dates, PLACEBO_SEEDS[:2])
            t0 = time.time()
            slow = []
            for pc in slow_runs:
                gp = H.grade(_pick(pc, side, cut), fake)
                gp = gp[gp["season"].isin(choose)] if len(gp) else gp
                slow.append(H.roi(gp) if len(gp) else float("nan"))
            per_slow = (time.time() - t0) / 2.0
            if not np.allclose(slow, fast[:2], equal_nan=True):
                raise RuntimeError(f"the array placebo and run_cells' path disagree on {m}: {slow} {fast[:2]}")
            t0 = time.time()
            G5.run_market(dd_fake, FAMILY, POINT, m, [side], list(CUTS[m]), cand, nm, None, "strength",
                          choose, prep["times"])
            per_cell = (time.time() - t0) / len(CUTS[m])
            results[m] = {"one_placebo_run_s": round(per_run, 5), "same_run_frame_by_frame_s": round(per_slow, 3),
                          "the_two_paths_agree": True, "one_cell_without_placebo_s": round(per_cell, 3),
                          "one_side_table_s": round(per_table, 3)}
        run = float(np.mean([v["one_placebo_run_s"] for v in results.values()]))
        cell = float(np.mean([v["one_cell_without_placebo_s"] for v in results.values()]))
        tab = float(np.mean([v["one_side_table_s"] for v in results.values()]))
        # both families' cells, the whole-gap runs of both and the tilt-only runs of S1
        cells_s = 2 * EXPECTED_CELLS * (cell + N_PLACEBO * run) + EXPECTED_CELLS * N_PLACEBO * run + 16 * tab
        return {**results, "projected_cells_minutes": round(cells_s / 60.0, 1),
                "setup_minutes_this_run": round(prep["seconds"] / 60.0, 1),
                "projected_full_minutes": round((cells_s + prep["seconds"]) / 60.0, 1)}
    finally:
        if saved is not None:
            os.environ[BETS_ENV] = saved


def engine_check(cache: Path, scratch: Path, prep: dict, n_games: int = 40) -> dict:
    """The lab's full-game-weighted team ratings against the engine's own
    P.project on a sample of real games at their T: they must be the same
    numbers, or the tilt is measured against something else."""
    w = P.load_world(cache, max_season=LAST_SEASON)
    eng = engine(cache, w, scratch, lambda *_: None)
    models = models_from(eng, w)
    out = {}
    fr = prep["frames"]["games_T"].set_index("game_id")
    for S in GRADED:
        ids = fr[(fr["season"] == S) & fr["ok"].astype(bool)].index[:n_games]
        gm = w.games[w.games["game_id"].isin(ids)].merge(prep["times"][["game_id", "T"]], on="game_id")
        pj = P.project(w, models[S].st, P.raw_model(models[S]), gm).set_index("game_id")
        f = fr.loc[pj.index]
        out[S] = {c: float(np.max(np.abs(f[a].to_numpy(float) - pj[b].to_numpy(float))))
                  for c, a, b in (("O home", "O_fg_h", "O_h"), ("D home", "D_fg_h", "D_h"),
                                  ("O away", "O_fg_a", "O_a"), ("D away", "D_fg_a", "D_a"))}
        pace = pj["pace_t_h"].to_numpy(float) * pj["pace_t_a"].to_numpy(float) / pj["pace_lg"].to_numpy(float)
        out[S]["pace"] = float(np.max(np.abs(f["pace"].to_numpy(float) - pace)))
    return out


def smoke(cache: Path = H.CACHE) -> dict:
    """Synthetic cells, then only what the record allows before grading."""
    t_all = time.time()
    synthetic_checks()
    scratch = scratch_dir()
    prep = prepare(cache, False, scratch)
    print("\nSTARTERS' SHARE OF MINUTES (a description; the flag is no input):")
    print(starter_minutes(cache).round(3).to_string(index=False))
    print("\nEXPECTED MINUTES AT T AGAINST WHAT HAPPENED (root mean square error, player minutes):")
    print(minutes_accuracy(prep["frames"]["players_T"], cache).round(3).to_string(index=False))
    print("\nGAMES WITH NO TILT BECAUSE A TEAM'S FULL-GAME MINUTES MISS 240 (section 4.3):")
    for name, key in (("graded games at T", "games_T"), ("the slope fit's games", "games_ref")):
        f = prep["frames"][key]
        miss = (f["min_fg_h"] - P.TEAM_MINUTES).abs().gt(TEAM_MINUTE_SLACK) | (f["min_fg_a"] - P.TEAM_MINUTES).abs().gt(TEAM_MINUTE_SLACK)
        print(f"  {name}: {int(miss.sum())} of {len(f)}", f.loc[miss, "game_id"].tolist()[:10])
    print("\nBETAS (each fit on the seasons before the one it serves; period result minus base, on tilt points):")
    print(prep["fit"].round(4).to_string(index=False))
    print("as registered:", repr({k: v for k, v in sorted(prep["betas"].items())}),
          "\nthe registered fit in the lab:", "matches" if not beta_mismatch(prep["betas"]) else beta_mismatch(prep["betas"])[:3])
    extremes(prep)
    c = counts(prep)
    print("\nPOPULATION:", json.dumps(c["population"], indent=1), "\nshare of market-game rows alone on their date:",
          round(c["alone_on_date"], 4), "\ngames with no trusted period score (no settlement, no bet):",
          prep["no_settlement"])
    print("\nHOW FAR THE PROJECTION SITS FROM THE PERIOD MARKET (points):\n", c["sizes"].round(3).to_string(index=False))
    print("\nGAMES PER BAND OF THE GAP, EACH SIDE:\n", c["bands"].to_string(index=False))
    print("\nBETS EACH CELL WOULD PLACE (counted, never graded):\n", c["cells"].round(3).to_string(index=False))
    t = placebo_null(prep)
    print("\nTHE PLACEBO ON REAL DATA: share of placebo bets that are not the real bets (10 runs each).")
    print("ceiling = 1 - the share of the market's games the cell bets, what any shuffle could reach.\n",
          t.round(3).to_string(index=False))
    print("by market:\n", t.groupby("market")[["whole_gap_differs", "ceiling", "tilt_only_differs", "control_differs"]]
          .agg(["min", "mean", "max"]).round(3).to_string())
    print("mean whole-gap", round(float(t["whole_gap_differs"].mean()), 3), "mean tilt-only",
          round(float(t["tilt_only_differs"].mean()), 3), "mean control", round(float(t["control_differs"].mean()), 3))
    print("\nENGINE CHECK (largest difference from P.project on a sample of games at T):")
    print(json.dumps(engine_check(cache, scratch, prep), indent=1))
    tc = time_cells(prep)
    print("\nTHE CLOCK (real offers, made-up results):", json.dumps(tc, indent=1))
    d = scratch / ENGINE_DIR
    eng_s = d / f"{ENGINE_NAME}_seconds.json"
    built = json.loads(eng_s.read_text(encoding="utf-8"))["seconds"] if eng_s.exists() else float("nan")
    print(f"engine setup, as measured when it was built: {built:.0f} s. --full with the saved engine: "
          f"{tc['projected_full_minutes']} minutes; with it gone: {tc['projected_full_minutes'] + built / 60.0:.0f} minutes")
    print(f"peak memory this process: {peak_gb():.1f} GB; this smoke took {(time.time() - t_all) / 60.0:.1f} minutes")
    return {"counts": c, "placebo": t, "clock": tc, "fit": prep["fit"]}


def refuse_full(cache: Path) -> list[str]:
    why = []
    if os.environ.get(GO_ENV) != "1":
        why.append(f"{GO_ENV}=1 is not set: the owner runs --full")
    if not os.environ.get(RESULTS_ENV):
        why.append(f"{RESULTS_ENV} is not set: name this search's results folder")
    if not os.environ.get(BETS_ENV):
        why.append(f"{BETS_ENV} is not set: a passing cell's figures read its bets")
    for f in (P.LEDGER_FILE, P.STINTS_FILE):
        if not (Path(cache) / f).exists():
            why.append(f"{Path(cache) / f} does not exist: refresh the cache")
    return why


def beta_mismatch(betas: dict, registered: dict = None, tol: float = BETA_TOLERANCE) -> list[str]:
    """The registered fit against a refit: any difference, or a registered fit
    that is empty, stops --full."""
    registered = REGISTERED_BETA if registered is None else registered
    if not registered:
        return ["no beta is registered: run --smoke and register the fit in the doc first"]
    bad = []
    for k in sorted(set(betas) | set(registered)):
        a, b = betas.get(k), registered.get(k)
        if a is None or b is None or abs(a - b) > tol:
            bad.append(f"{k}: refit {a}, registered {b}")
    return bad


def full(cache: Path = H.CACHE, out: Path | None = None) -> None:
    why = refuse_full(cache)
    if why:
        P.refuse(why)
    out = Path(os.environ[RESULTS_ENV]) if out is None else out
    t0 = time.time()
    synthetic_checks()
    try:
        prep = prepare(cache, True, scratch_dir())
    except RuntimeError as e:
        P.refuse([str(e)])
    bad = beta_mismatch(prep["betas"])
    if bad:
        P.refuse(bad)
    choose = P3.choosing(prep["graded"])
    log(f"graded {prep['graded']}, choosing {choose}; prepared in {prep['seconds'] / 60.0:.1f} minutes")
    rows, cands = emit_family(prep["dd"], FAMILY, prep["gap"], prep["neutral"], choose, prep["times"],
                              proj=prep["proj"], say=log)
    ctl, cands_c = emit_family(prep["dd"], CONTROL, prep["gap_control"], prep["neutral"], choose, prep["times"],
                               say=log)
    off = H.offers(prep["vis"])
    pops = []
    for fam, rr, cc in ((FAMILY, rows, cands), (CONTROL, ctl, cands_c)):
        for m in MARKETS:
            pops.append(P3.population(fam, [r for r in rr if r["market"] == m], prep["dd"], prep["times"], off,
                                      cc[m], "strength", prep["graded"]))
    # every table is written only once both families are built
    out.mkdir(parents=True, exist_ok=True)
    L.write_cells(rows, out / f"cells_{FAMILY}.parquet")
    L.write_cells(ctl, out / f"cells_{CONTROL}.parquet")
    pd.concat(pops, ignore_index=True).to_parquet(out / "population_S1.parquet")
    prep["gap"].assign(family=FAMILY).to_parquet(out / "gaps_S1.parquet")
    prep["gap_control"].assign(family=CONTROL).to_parquet(out / f"gaps_{CONTROL}.parquet")
    prep["fit"].to_parquet(out / "betas_S1.parquet")
    log(f"cells written to {out}: {len(rows)} registered, {len(ctl)} controls judged; "
        f"{(time.time() - t0) / 60.0:.1f} minutes; peak memory {peak_gb():.1f} GB")
    print(f"next: python -m scripts.nba_game2_verdict --results {out} --house5")
    print(f"then: python -m scripts.nba_s_starters --credit --results {out}")


def credit(results: Path) -> None:
    """The credit rule on a graded run: bars from the verdict's own function."""
    c = credit_table(V.load_cells(results))
    s = c[c["family"] == FAMILY]
    k = c[c["family"] == CONTROL]
    print(f"{FAMILY}: {len(s)} cells, {int(s['house5_passes'].sum())} pass, {int(s['credited'].sum())} credited "
          f"(spread cells that pass and beat the control); "
          f"{int((s['house5_passes'] & ~s['creditable']).sum())} total cells pass and read as the league-share idea's; "
          f"{CONTROL}: {len(k)} cells, {int(k['house5_passes'].sum())} pass")
    cols = ["family", "market", "side", "cut", "pool_n", "pool_units", "pool_roi", "pool_ci95_lo", "pool_ci95_hi",
            "control_pool_roi", "beats_control", "house5_passes", "credited", "counts_for", "house5_failed"]
    print(c[c["house5_passes"]][cols].to_string(index=False) if c["house5_passes"].any() else "no cell passes")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true", help="synthetic checks, then real counts only")
    g.add_argument("--full", action="store_true", help=f"every graded season (needs {GO_ENV}=1)")
    g.add_argument("--credit", action="store_true", help="the credit rule on a graded run's cells")
    ap.add_argument("--results", type=Path, help="the graded run's folder, for --credit")
    a = ap.parse_args(argv)
    if a.credit:
        if a.results is None:
            ap.error("--credit needs --results")
        credit(a.results)
    elif a.full:
        full(H.CACHE)
    else:
        smoke(H.CACHE)


if __name__ == "__main__":
    main()
