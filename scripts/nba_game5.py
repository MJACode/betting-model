"""NBA fifth search: team period tendencies (F7) and the early season (F8).

docs/nba_models_2026.md section 9 registers the cells and fixes every choice,
written BEFORE any F7 or F8 cell was graded (2026-10-20). This lab EMITS cells
through the shared harness (scripts/nba_game_harness, H); the pass/fail script
judges them (scripts/nba_game2_verdict.py, house_verdict_bands: the house
standard of section 6.7 with section 9's two fixes). Nothing here grades a bet
itself, and no cut, constant or rule below was chosen from a betting result.

54 cells (asserted), plus 48 controls, judged too since section 9.8:

  F7  TEAM PERIOD TENDENCIES, 48 cells: first-quarter and first-half spread,
      total and moneyline x 2 sides x 4 cuts, decided at each game's per-game
      purchase 45-75 minutes before tip (decision point D, H.per_event_times),
      each book's main number (models/nba_book_numbers), 2023-24 .. 2025-26
      pooled.
        shares    per team, venue (home / away) and period: its SCORING share
                  (its own points in the period over its own final points) and
                  its ALLOWED share (its opponents' period points over their
                  final points), each a ratio of sums over the team's games at
                  that venue in the previous regular season plus this season
                  dated before the game, shrunk toward the league's ratio over
                  the same window: (n x share + k x league) / (n + k), n the
                  games in the window. Its MARGIN share is scoring minus
                  allowed. k per period: fit_shrinkage, on 2019-20 .. 2022-23.
        projection  from the market's full-game numbers at T -- the home
                  margin M and the total T (H.market_fair: Pinnacle's no-vig
                  centre, else the deciding books' median; full_game_visible:
                  staleness judged on the fetch instant) -- home points
                  H = (T + M) / 2, away A = (T - M) / 2, and
                    home share in this game  s_home + a_away - L_home
                    away share in this game  s_away + a_home - L_away
                  (each team's deviation from the league added once; L the
                  league's own-points share at that venue). Period home points
                  = H x home share, away = A x away share.
        spread / total   strength = projected period centre minus the period
                  market's fair centre at T (H.market_fair on the period
                  quotes, priced by scripts/nba_game4_p3.market_pricing), a
                  rule: the side's best deciding offer under the market's fair
                  line. Cuts in points: first half 0.5 / 1 / 1.5 / 2, first
                  quarter 0.25 / 0.5 / 0.75 / 1 (the full game's 1-4 scaled by
                  the period's share of the game).
        moneyline  P(period home margin > 0), the tie mass removed, through
                  the period spread market's own distribution (P3's
                  market_pricing) centred on the projected margin; EV cuts
                  0.02 / 0.04 / 0.06 / 0.08.
        placebo   200 runs, seeds 1-200: every team-share deviation of a game
                  moved together to another game on the same date
                  (H.shuffle_within_date), each game keeping its own full-game
                  numbers and its own prices; the projection is recomputed.
  F8  THE EARLY SEASON, 6 cells: the two live shooting-luck signals
      (models/nba_total_luck: full-game total OVER, gap >= 3, decision point C;
      models/nba_team_total_luck: home team total UNDER, the home part of the
      gap <= -2, the per-game purchase at D) on games where either team has
      fewer than 10 games this season, with every rating blended
        (n x this season + k x the previous season's final) / (n + k)
      for k = 5, 10, 20 (axis_blend). Full-game totals graded 2021-22 ..
      2025-26 (2020-21 reported); team totals 2023-24 .. 2025-26. Placebo:
      200 runs, seeds 1-200, the gap shuffled within date and market.
  control_F7_league  F7's 48 cells with every team's share set to the
      league's: the first search's `derived` idea (the market's full-game
      number scaled league-wide), never judged under the house standard.
      Section 9.8 (2026-10-20, before grading): judged under the same bars,
      placebo 200 runs, seeds 1-200, its gap from the period market shuffled
      within date and market (control_shuffles); an F7 cell is credited to
      team tendencies only if it also beats its control's pooled return.

BANDS (section 9's first fix to the house standard). Every cell row carries
the pooled bets, units and return of the bands around its cut: band 0 the band
just below the cut, bands 1.. from the cut to the top (F7: between its four
cuts, the lowest cut's lower band starting at 0; F8: gap 1-2, 2-3, 3-4, 4+).
The verdict reads them.

    PYTHONPATH=. python -m scripts.nba_game5 --smoke
    NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> NBA_GAME2_BETS=<folder>/bets PYTHONPATH=. python -m scripts.nba_game5 --full

--smoke runs every cell on SYNTHETIC games, then prints on the real cache only
what section 9 allows before grading: the persistence of team period shares
and the shrinkage fit (period scores, no price), and counts (games with a
decision, a number, a price; F8's qualifying games and the bets each cell
would place per season). It never grades a real bet.
--full writes <NBA_GAME2_RESULTS>/cells_F7.parquet, cells_F8.parquet,
cells_control_F7_league.parquet, their population_*.parquet and shares.json.
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
import models.nba_total_luck as tl  # noqa: E402
from models import nba_book_numbers as NB  # noqa: E402
from models import nba_team_total_luck as TT  # noqa: E402
from scripts import nba_game2_luck as L  # noqa: E402
from scripts import nba_game2_projection as P  # noqa: E402
from scripts import nba_game4_p3 as P3  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402

GO_ENV, RESULTS_ENV, BETS_ENV = "NBA_GAME2_GO", "NBA_GAME2_RESULTS", "NBA_GAME2_BETS"
F7_FAMILY, F7_CONTROL, F8_FAMILY = "F7", "control_F7_league", "F8"
PERIODS = ("q1", "h1")
F7_GRADED = (2024, 2025, 2026)                 # 2023-24 .. 2025-26, the derivative purchases
FULL_GAME_SEASONS = (H.REGIME, *H.CHOOSE, H.CONFIRM)   # 2020-21 .. 2025-26: closes and C decisions
SHARE_FIT_SEASONS = (2020, 2021, 2022, 2023)   # 2019-20 .. 2022-23: the shrinkage, never 2023-24 on
FIRST_GRADED = min(F7_GRADED)
K_GRID = (0.0, 5.0, 10.0, 20.0, 40.0, 80.0, 160.0, 320.0, 640.0, np.inf)
# section 9.3's registered fit; --full refuses a refit that returns anything else (9.8)
REGISTERED_K = {"q1": 160.0, "h1": 40.0}
POINT_CUTS = {"h1": (0.5, 1.0, 1.5, 2.0), "q1": (0.25, 0.5, 0.75, 1.0)}
EV_CUTS = (0.02, 0.04, 0.06, 0.08)
F7_SIDES = {f"{k}_{p}": (("over", "under") if k == "totals" else ("home", "away"))
            for p in PERIODS for k in ("spreads", "totals", "h2h")}

F8_BLENDS = (5.0, 10.0, 20.0)
EARLY_GAMES = tl.MIN_GAMES                     # 10: the live models' rule, CLAUDE.md section 3
F8_EDGES = (1.0, 2.0, 3.0, 4.0)
# (market, side, live cut, decision point), each imported from its live model (9.8)
F8_SIGNALS = ((tl.MARKET, tl.SIDE, float(tl.GAP_CUT), "C"),
              (TT.MARKET, TT.SIDE, float(TT.GAP_CUT), "D"))
F8_TT_GRADED = (2024, 2025, 2026)

N_PLACEBO = 200
PLACEBO_SEEDS = tuple(range(1, N_PLACEBO + 1))
EXPECTED_CELLS = {F7_FAMILY: 48, F8_FAMILY: 6}
BAND_SLOTS = 5                                  # band 0 below the cut + up to 4 from the cut


def f7_cuts(market: str) -> tuple:
    if H.kind([market])[0] == "ml":
        return EV_CUTS
    return POINT_CUTS[market.rsplit("_", 1)[1]]


def cell_specs(family: str | None = None) -> list[tuple]:
    """(family, market, side, cut_index, cut, blend) for every cell section 9 lists."""
    out = []
    if family in (None, F7_FAMILY):
        for m, sides in F7_SIDES.items():
            for s in sides:
                for k, c in enumerate(f7_cuts(m)):
                    out.append((F7_FAMILY, m, s, k, c, None))
    if family in (None, F8_FAMILY):
        for m, s, cut, _ in F8_SIGNALS:
            for b in F8_BLENDS:
                out.append((F8_FAMILY, m, s, 0, cut, b))
    return out


assert {f: len(cell_specs(f)) for f in EXPECTED_CELLS} == EXPECTED_CELLS, "section 9 registers 48 + 6"
assert len(cell_specs()) == 54


# ── F7: team period shares ──────────────────────────────────────────────────

SUMS = ("n", "own_f", "opp_f", "own_q1", "opp_q1", "own_h1", "opp_h1")


def team_period_rows(games_p: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, team) with trusted period scores (H.with_periods):
    the team's own and its opponent's final and period points, and its venue."""
    g = games_p[np.isfinite(games_p[list(H.PERIOD_COLS)].to_numpy(float)).all(axis=1)]
    base = g[["game_id", "season", "game_date"]]
    home = base.assign(team=g["home_team"], venue="home", own_f=g["home_score"], opp_f=g["away_score"],
                       own_q1=g["home_q1"], opp_q1=g["away_q1"], own_h1=g["home_h1"], opp_h1=g["away_h1"])
    away = base.assign(team=g["away_team"], venue="away", own_f=g["away_score"], opp_f=g["home_score"],
                       own_q1=g["away_q1"], opp_q1=g["home_q1"], own_h1=g["away_h1"], opp_h1=g["home_h1"])
    out = pd.concat([home, away], ignore_index=True).assign(n=1.0)
    out["season"] = out["season"].astype(int)
    out["game_date"] = out["game_date"].astype(str).str[:10]
    return out


def _cum_before(rows: pd.DataFrame, targets: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """SUMS over the same season's rows dated strictly before each target, per `by`."""
    day = rows.groupby([*by, "game_date"], as_index=False)[list(SUMS)].sum()
    day = day.sort_values([*by, "game_date"])
    day[list(SUMS)] = day.groupby(by)[list(SUMS)].cumsum()
    x = tl._before(targets, day, by)
    x[list(SUMS)] = x[list(SUMS)].fillna(0.0)
    return x


def window_sums(rows: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """For targets (season, game_date, team, venue): w_* = the team's sums at
    that venue over the PREVIOUS season's games and this season's games dated
    before game_date; lg_* = the same window for every team at that venue."""
    t = targets[["season", "game_date", "team", "venue"]].drop_duplicates().copy()
    t["season"] = t["season"].astype(int)
    t["game_date"] = t["game_date"].astype(str).str[:10]
    cur = _cum_before(rows, t, ["season", "team", "venue"])
    prev = rows.groupby(["season", "team", "venue"], as_index=False)[list(SUMS)].sum()
    prev = prev.assign(season=prev["season"] + 1)
    x = cur.merge(prev, on=["season", "team", "venue"], how="left", suffixes=("", "_prev"))
    for c in SUMS:
        x[f"w_{c}"] = x[c] + x[f"{c}_prev"].fillna(0.0)
    x = x[["season", "game_date", "team", "venue", *[f"w_{c}" for c in SUMS]]]
    lcur = _cum_before(rows, x[["season", "game_date", "venue"]].drop_duplicates(), ["season", "venue"])
    lprev = rows.groupby(["season", "venue"], as_index=False)[list(SUMS)].sum()
    lprev = lprev.assign(season=lprev["season"] + 1)
    lg = lcur.merge(lprev, on=["season", "venue"], how="left", suffixes=("", "_prev"))
    for c in SUMS:
        lg[f"lg_{c}"] = lg[c] + lg[f"{c}_prev"].fillna(0.0)
    lg = lg[["season", "game_date", "venue", *[f"lg_{c}" for c in SUMS]]]
    return x.merge(lg, on=["season", "game_date", "venue"], how="left")


def shrink(num, den, n, lg_num, lg_den, k: float) -> np.ndarray:
    """(n x num/den + k x league) / (n + k); the league's ratio where n is 0 or k infinite."""
    num, den, n = (np.asarray(v, float) for v in (num, den, n))
    lgr = np.asarray(lg_num, float) / np.where(np.asarray(lg_den, float) > 0, lg_den, np.nan)
    if not np.isfinite(k):
        return lgr
    own = num / np.where(den > 0, den, np.nan)
    return np.where(n > 0, (n * own + k * lgr) / (n + k), lgr)


def share_windows(games: pd.DataFrame, rows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(games, window sums for both teams of each): what game_shares shrinks.
    Independent of k, so the shrinkage fit builds it once."""
    g = games[["game_id", "season", "game_date", "home_team", "away_team"]].copy()
    g["season"] = g["season"].astype(int)
    g["game_date"] = g["game_date"].astype(str).str[:10]
    tg = pd.concat([g.assign(team=g["home_team"], venue="home"),
                    g.assign(team=g["away_team"], venue="away")], ignore_index=True)
    return g, window_sums(rows, tg)


def game_shares(games: pd.DataFrame, rows: pd.DataFrame, k: dict, windows=None) -> pd.DataFrame:
    """Per game, per period p: s_home_p, a_home_p (the home team's scoring and
    allowed shares at home), s_away_p, a_away_p (the away team's on the road),
    L_home_p, L_away_p (the league's own-points share at each venue), and the
    window sizes n_home, n_away. Every input is dated before the game."""
    g, ws = share_windows(games, rows) if windows is None else windows
    ws = ws.copy()
    for p in PERIODS:
        ws[f"s_{p}"] = shrink(ws[f"w_own_{p}"], ws["w_own_f"], ws["w_n"], ws[f"lg_own_{p}"], ws["lg_own_f"], k[p])
        ws[f"a_{p}"] = shrink(ws[f"w_opp_{p}"], ws["w_opp_f"], ws["w_n"], ws[f"lg_opp_{p}"], ws["lg_opp_f"], k[p])
        ws[f"L_{p}"] = ws[f"lg_own_{p}"] / ws["lg_own_f"].where(ws["lg_own_f"] > 0)
    keep = ["season", "game_date", "team", "w_n", *[f"{c}_{p}" for p in PERIODS for c in ("s", "a", "L")]]
    out = g
    for v, col in (("home", "home_team"), ("away", "away_team")):
        side = ws[ws["venue"] == v][keep].rename(columns={"team": col, "w_n": f"n_{v}",
                                                          **{f"{c}_{p}": f"{c}_{v}_{p}" for p in PERIODS
                                                             for c in ("s", "a", "L")}})
        out = out.merge(side, on=["season", "game_date", col], how="left")
    return out


SHARE_COLS = tuple(f"{c}_{v}_{p}" for p in PERIODS for v in ("home", "away") for c in ("s", "a"))


def period_points(H_pts, A_pts, sh: pd.DataFrame, p: str, league_only: bool = False):
    """(period home points, period away points) from each team's full-game
    points and the shares: home share = s_home + a_away - L_home, away share =
    s_away + a_home - L_away; the league's own share at each venue when
    league_only (the control)."""
    if league_only:
        sig_h, sig_a = sh[f"L_home_{p}"].to_numpy(float), sh[f"L_away_{p}"].to_numpy(float)
    else:
        sig_h = (sh[f"s_home_{p}"] + sh[f"a_away_{p}"] - sh[f"L_home_{p}"]).to_numpy(float)
        sig_a = (sh[f"s_away_{p}"] + sh[f"a_home_{p}"] - sh[f"L_away_{p}"]).to_numpy(float)
    return np.asarray(H_pts, float) * sig_h, np.asarray(A_pts, float) * sig_a


def fit_shrinkage(games_p: pd.DataFrame, seasons=SHARE_FIT_SEASONS, grid=K_GRID) -> tuple[dict, pd.DataFrame]:
    """k per period: the grid value with the smallest squared error predicting
    each team's period points as its realised final points x its share in that
    game, over every game of `seasons` (2019-20 .. 2022-23). Reads no game of a
    season after max(seasons): rows are cut there first. Ties go to the
    smaller k (the grid's order)."""
    last = max(int(s) for s in seasons)
    gp = games_p[games_p["season"].astype(int) <= last]
    rows = team_period_rows(gp)
    tgt = gp[gp["season"].astype(int).isin([int(s) for s in seasons])]
    tgt = tgt[np.isfinite(tgt[list(H.PERIOD_COLS)].to_numpy(float)).all(axis=1)]
    table, best = [], {}
    windows = share_windows(tgt, rows)
    for p in PERIODS:
        sse = []
        for k in grid:
            sh = game_shares(tgt, rows, {q: k for q in PERIODS}, windows)
            sh = tgt[["game_id", "home_score", "away_score", f"home_{p}", f"away_{p}"]].merge(sh, on="game_id")
            hp, ap = period_points(sh["home_score"], sh["away_score"], sh, p)
            e = (sh[f"home_{p}"] - hp) ** 2 + (sh[f"away_{p}"] - ap) ** 2
            sse.append(float(e.sum()))
            table.append({"period": p, "k": k, "sse": float(e.sum()), "games": int(e.notna().sum())})
        best[p] = float(grid[int(np.argmin(sse))])
    return best, pd.DataFrame(table)


def persistence(games_p: pd.DataFrame) -> pd.DataFrame:
    """Season-to-season and split-half correlation of each team's full-season
    shares (both venues pooled), from period scores alone (no price): scoring
    share, allowed share, margin share (scoring minus allowed) and the share of
    the game's points (both teams). The split-half halves are each team's
    odd- and even-numbered games of the season."""
    rows = team_period_rows(games_p).sort_values(["season", "team", "game_date"])
    rows["half"] = rows.groupby(["season", "team"]).cumcount() % 2

    def shares(grp_cols):
        s = rows.groupby(grp_cols)[list(SUMS)].sum()
        out = {}
        for p in PERIODS:
            sc, al = s[f"own_{p}"] / s["own_f"], s[f"opp_{p}"] / s["opp_f"]
            out[(p, "scoring")] = sc
            out[(p, "allowed")] = al
            out[(p, "margin")] = sc - al
            out[(p, "game")] = (s[f"own_{p}"] + s[f"opp_{p}"]) / (s["own_f"] + s["opp_f"])
        return out, s["n"]

    season, n_games = shares(["season", "team"])
    halves, _ = shares(["season", "team", "half"])
    seasons = sorted(rows["season"].unique())
    out = []
    for key, v in season.items():
        v = v.unstack("team")                                   # season x team
        rs, xs, ys = [], [], []
        for a, b in zip(seasons[:-1], seasons[1:]):
            x, y = v.loc[a], v.loc[b]
            ok = x.notna() & y.notna()
            rs.append(float(np.corrcoef(x[ok], y[ok])[0, 1]))
            xs.append((x[ok] - x[ok].mean()).to_numpy())
            ys.append((y[ok] - y[ok].mean()).to_numpy())
        pooled = float(np.corrcoef(np.concatenate(xs), np.concatenate(ys))[0, 1])
        hv = halves[key].unstack("half")
        hr = []
        for s in seasons:
            h = hv.loc[s].dropna()
            hr.append(float(np.corrcoef(h[0], h[1])[0, 1]))
        split = float(np.mean(hr))
        dev = v.sub(v.mean(axis=1), axis=0).stack()
        out.append({"period": key[0], "share": key[1], "pairs": len(rs),
                    "r_next_season_pooled": pooled, "r_next_season_min": min(rs),
                    "r_next_season_max": max(rs), "r_split_half_mean": split,
                    "reliability_full_season": 2 * split / (1 + split),
                    "sd_across_teams": float(dev.std()),
                    "sd_in_points_at_112": float(dev.std() * 112.0)})
    return pd.DataFrame(out)


# ── F7 at the decision ──────────────────────────────────────────────────────

def full_game_numbers(vis_full: pd.DataFrame, sig: dict) -> pd.DataFrame:
    """(game_id, M, Tot): the market's full-game fair centres at T -- the home
    margin and the total -- from H.market_fair (Pinnacle's no-vig where it
    quotes coherently, else the deciding books' median), priced through
    H.close_dist (`sig`)."""
    f = H.market_fair(vis_full[vis_full["market"].isin(["spreads", "totals"])], sig)
    w = f.pivot_table(index="game_id", columns="market", values="mu", aggfunc="first")
    w = w.reindex(columns=["spreads", "totals"])
    return pd.DataFrame({"game_id": w.index, "M": w["spreads"].to_numpy(float),
                         "Tot": w["totals"].to_numpy(float)}).dropna().reset_index(drop=True)


def full_game_visible(quotes: pd.DataFrame, times: pd.DataFrame) -> pd.DataFrame:
    """The full-game quotes the market's numbers at T are read from: each
    book's main number (NB.visible_numbers) at the newest slate fetch at or
    before T, counted when that FETCH is at most 60 minutes before T -- the
    live team-total model's staleness rule (section 9.3, a line added
    2026-10-20 before any cell was graded). H.visible alone judges staleness on
    the book's own last update, minutes before the fetch, and left 209
    purchases 64 minutes before tip with no full-game number although their
    newest slate fetch was 56 minutes old. Nothing after T is read."""
    return NB.visible_numbers(quotes.assign(snapshot_at=quotes["fetch_at"]), times)


def f7_projection(full: pd.DataFrame, sh: pd.DataFrame, league_only: bool = False) -> pd.DataFrame:
    """Per game: margin_<p>, total_<p>, the projected period home margin and total."""
    x = full.merge(sh, on="game_id")
    Hp, Ap = (x["Tot"] + x["M"]) / 2.0, (x["Tot"] - x["M"]) / 2.0
    out = x[["game_id", "season"]].copy()
    for p in PERIODS:
        hp, ap = period_points(Hp, Ap, x, p, league_only)
        out[f"margin_{p}"], out[f"total_{p}"] = hp - ap, hp + ap
    return out.dropna().reset_index(drop=True)


def f7_signals(proj: pd.DataFrame, period_fair: pd.DataFrame, pricing: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(strength, ml_fair). strength: (game_id, market, strength) for the four
    period spread and total markets, the projected centre minus the market's
    fair centre at T, toward side A (home, over). ml_fair: (game_id, market,
    mu, sigma, p_home) for the two period moneylines, P(period home margin > 0)
    with the tie mass removed, through the period spread market's own pricing
    for the season, centred on the projected margin."""
    pf = period_fair[["game_id", "market", "mu"]]
    parts, ml = [], []
    for p in PERIODS:
        for kind_, col in (("spreads", f"margin_{p}"), ("totals", f"total_{p}")):
            m = f"{kind_}_{p}"
            x = proj[["game_id", col]].merge(pf[pf["market"] == m], on="game_id", how="left")
            parts.append(pd.DataFrame({"game_id": x["game_id"], "market": m,
                                       "strength": x[col].to_numpy(float) - x["mu"].to_numpy(float)}))
        dist = np.array([pricing.get((int(s), f"spreads_{p}")) for s in proj["season"]], dtype=object)
        # a control placebo run leaves a game with no period spread centre without a margin
        have = np.array([d is not None for d in dist]) & np.isfinite(proj[f"margin_{p}"].to_numpy(float))
        ph = np.full(len(proj), np.nan)
        if have.any():
            w, _, lo = H.probs_any(proj.loc[have, f"margin_{p}"].to_numpy(float), dist[have],
                                   np.zeros(int(have.sum())))
            ph[have] = w / np.where(w + lo > 0, w + lo, np.nan)
        ml.append(pd.DataFrame({"game_id": proj["game_id"], "market": f"h2h_{p}", "mu": np.nan,
                                "sigma": pd.Series([None] * len(proj), dtype=object), "p_home": ph}))
    s = pd.concat(parts, ignore_index=True)
    f = pd.concat(ml, ignore_index=True)
    return (s[np.isfinite(s["strength"].to_numpy(float))].reset_index(drop=True),
            f[np.isfinite(f["p_home"].to_numpy(float))].reset_index(drop=True))


def f7_cand(market: str, neutral: pd.DataFrame, off: pd.DataFrame, strength: pd.DataFrame,
            ml_fair: pd.DataFrame) -> pd.DataFrame:
    """One market's candidate offers: a rule's market-fair offers carrying the
    gap in each side's favour (spread, total), or the moneyline's offers priced
    at the projection's own probability."""
    if H.kind([market])[0] == "ml":
        return H.fair_offers(off[off["market"] == market], ml_fair[ml_fair["market"] == market])
    nm = neutral[neutral["market"] == market]
    return tl.side_strength(nm, strength[strength["market"] == market])


def share_shuffles(sh: pd.DataFrame, games: pd.DataFrame, seeds=PLACEBO_SEEDS) -> list[pd.DataFrame]:
    """One frame per seed: every game's team-share columns (SHARE_COLS and the
    league values with them) taken from another game on the same date, by the
    harness's own within-date shuffle (H.shuffle_within_date moves a row index
    the way it moves any number). Season and game_id stay; so do the game's
    own full-game numbers and prices, which f7_projection reads elsewhere."""
    cols = [c for c in sh.columns if c.startswith(("s_", "a_", "L_"))]
    base = sh[["game_id"]].assign(market="shares", strength=np.arange(len(sh), dtype=float))
    vals = sh[cols].to_numpy(float)
    pos = {g: i for i, g in enumerate(sh["game_id"])}
    out = []
    for seed in seeds:
        m = H.shuffle_within_date(base, games, np.random.default_rng(seed))
        src = np.arange(len(sh))            # a game alone on its date keeps its own
        src[m["game_id"].map(pos).to_numpy(int)] = m["strength"].to_numpy(int)
        out.append(sh.assign(**{c: vals[src, j] for j, c in enumerate(cols)}))
    return out


def control_shuffles(proj: pd.DataFrame, period_fair: pd.DataFrame, games: pd.DataFrame,
                     seeds=PLACEBO_SEEDS) -> list[pd.DataFrame]:
    """The control's placebo (section 9.8): one projection frame per seed with
    each game's GAP from the period market's fair centre (margin_p against
    spreads_p, total_p against totals_p) shuffled between games on the same
    date in the same market (H.shuffle_within_date), then added back to the
    game's OWN fair centre. f7_signals on it gives the shuffled gap as the
    spread and total strength, and prices the moneyline from the shuffled
    margin (section 8.1's shape). A game with no period centre gets no number
    in that market. Season and game_id stay; prices are never touched."""
    pf = period_fair[["game_id", "market", "mu"]]
    parts = []
    for p in PERIODS:
        for kind_, col in (("spreads", f"margin_{p}"), ("totals", f"total_{p}")):
            m = f"{kind_}_{p}"
            x = proj[["game_id", col]].merge(pf[pf["market"] == m], on="game_id")
            parts.append(pd.DataFrame({"game_id": x["game_id"], "market": m, "col": col,
                                       "fair": x["mu"].to_numpy(float),
                                       "strength": x[col].to_numpy(float) - x["mu"].to_numpy(float)}))
    gaps = pd.concat(parts, ignore_index=True)
    gaps = gaps[np.isfinite(gaps["strength"].to_numpy(float))].reset_index(drop=True)
    base = proj[["game_id", "season"]]
    out = []
    for seed in seeds:
        s = H.shuffle_within_date(gaps[["game_id", "market", "strength"]], games, np.random.default_rng(seed))
        x = s.merge(gaps[["game_id", "market", "col", "fair"]], on=["game_id", "market"])
        x["v"] = x["fair"] + x["strength"]
        w = x.pivot_table(index="game_id", columns="col", values="v", aggfunc="first")
        w = w.reindex(columns=[f"{c}_{p}" for p in PERIODS for c in ("margin", "total")])
        out.append(base.merge(w.reset_index(), on="game_id", how="left"))
    return out


class LazyFrames:
    """A re-iterable list of frames built on demand. run_cells walks its
    placebo list once per side and cut; 200 built frames per market would not
    fit in memory, so each is rebuilt from its (small) shuffled numbers."""

    def __init__(self, items, build):
        self.items, self.build = list(items), build

    def __iter__(self):
        return (self.build(x) for x in self.items)

    def __len__(self):
        return len(self.items)


# ── bands around a cut (section 9's neighbourhood bar) ─────────────────────

def _pick(c: pd.DataFrame, lo: float, side: str, strength: str) -> pd.DataFrame:
    """run_cells' own choice at cut `lo` (its pick closure, for one side)."""
    if strength == "ev":
        return H.choose(c, lo, sides=[side])
    return H.choose(c[c[strength] >= lo], -np.inf, sides=[side])


def band_bounds(edges, k: int, lowest: float = 0.0) -> list[tuple[float, float]]:
    """[band just below cut k] + [each band from cut k to the top]; the lowest
    cut's lower band starts at `lowest`; the top band is open."""
    e = list(edges)
    below = (e[k - 1] if k > 0 else lowest, e[k])
    up = [(e[j], e[j + 1] if j + 1 < len(e) else np.inf) for j in range(k, len(e))]
    return [below, *up]


def band_columns(cand: pd.DataFrame, side: str, strength: str, bounds, games: pd.DataFrame,
                 pool_seasons) -> dict:
    """band<i>_lo/_hi/_n/_units/_roi for each band: the bets whose number falls
    in [lo, hi) -- those picked at lo and not at hi -- graded and pooled."""
    out = {"band_slots": len(bounds)}
    for i in range(BAND_SLOTS):
        out.update({f"band{i}_lo": np.nan, f"band{i}_hi": np.nan, f"band{i}_n": 0,
                    f"band{i}_units": np.nan, f"band{i}_roi": np.nan})
    for i, (lo, hi) in enumerate(bounds):
        b = _pick(cand, lo, side, strength)
        if np.isfinite(hi) and len(b):
            above = _pick(cand, hi, side, strength)
            gone = set(zip(above["game_id"], above["market"]))
            b = b[[k not in gone for k in zip(b["game_id"], b["market"])]]
        g = H.grade(b, games) if len(b) else b
        g = g[g["season"].isin(pool_seasons)] if len(g) else g
        out.update({f"band{i}_lo": float(lo), f"band{i}_hi": float(hi), f"band{i}_n": int(len(g)),
                    f"band{i}_units": float(g["units"].sum()) if len(g) else np.nan,
                    f"band{i}_roi": H.roi(g) if len(g) else np.nan})
    return out


def run_market(dd: H.Data, family: str, point: str, market: str, sides, cuts, cand, neutral,
               placebo, strength: str, choose, times, close=None, sig=None, edges=None,
               cut_index=None, extra=None) -> list[dict]:
    """One market's cells through H.run_cells, each row with its bands."""
    rows = H.run_cells(dd, family, point, cand, neutral, list(cuts), {market: list(sides)},
                       close=close, sig=sig, placebo=placebo, strength=strength,
                       choose_seasons=choose, times=times)
    for r in rows:
        k = r["cut_index"] if cut_index is None else cut_index
        bounds = band_bounds(edges if edges is not None else cuts, k)
        # the cell's own pooled seasons, as run_cells wrote them: a choosing
        # season gated out at D (H.gated_seasons) is out of the bands too
        pool = tuple(int(s) for s in str(r["pool_seasons"]).split(",") if s)
        r.update(band_columns(cand, r["side"], strength, bounds, dd.games, pool))
        r.update(extra or {})
    return rows


# ── F7 end to end on prepared inputs ────────────────────────────────────────

def emit_f7(dd: H.Data, times, off, neutral, full, sh, period_fair, pricing, choose,
            n_placebo: int = N_PLACEBO, league_only: bool = False) -> tuple[list[dict], dict]:
    """The 48 cells (or the 48 controls). Placebo: the team shares moved within
    date (share_shuffles), the projection recomputed; for the control, its gap
    from the period market moved within date and market (control_shuffles)."""
    family = F7_CONTROL if league_only else F7_FAMILY
    proj = f7_projection(full, sh, league_only)
    strength, ml_fair = f7_signals(proj, period_fair, pricing)
    plc = []
    if n_placebo:
        seeds = PLACEBO_SEEDS[:n_placebo]
        runs = (control_shuffles(proj, period_fair, dd.games, seeds) if league_only else
                (f7_projection(full, shs) for shs in share_shuffles(sh, dd.games, seeds)))
        plc = [f7_signals(r, period_fair, pricing) for r in runs]
    rows, cands = [], {}
    for market, sides in F7_SIDES.items():
        cand = f7_cand(market, neutral, off, strength, ml_fair)
        cands[market] = cand
        st = "ev" if H.kind([market])[0] == "ml" else "strength"
        lazy = (LazyFrames(plc, lambda x, m=market: f7_cand(m, neutral, off, x[0], x[1]))
                if plc else None)
        rows += run_market(dd, family, "D", market, sides, f7_cuts(market), cand,
                           neutral[neutral["market"] == market], lazy, st, choose, times,
                           extra={"signal_meaning": ("league shares only (the control)" if league_only else
                                                     "team period shares x the market's full-game numbers, "
                                                     "against the period market's fair centre")})
    assert len(rows) == EXPECTED_CELLS[F7_FAMILY], len(rows)
    return rows, cands


# ── F8: the early season ────────────────────────────────────────────────────

VALUE_COLS = [c for c in tl.RATING_COLS if c != "n"]


def season_end_ratings(tb: pd.DataFrame) -> pd.DataFrame:
    """(season, team, *_prev): each team's ratings over its whole regular
    season (tl.as_of_ratings at a date after the season), filed under the NEXT
    season, the one it is carried into."""
    t = tb[["season", "team"]].drop_duplicates().copy()
    t["game_date"] = t["season"].astype(int).astype(str) + "-12-31"
    r = tl.as_of_ratings(tb, t)
    r = r.assign(season=r["season"].astype(int) + 1)
    return r[["season", "team", *VALUE_COLS]].rename(columns={c: f"{c}_prev" for c in VALUE_COLS})


def blended_ratings(tb: pd.DataFrame, games: pd.DataFrame, k_blend: float) -> pd.DataFrame:
    """Ratings shaped like tl.as_of_ratings' (n = this season's games before
    the date), every value (n x this season + k x the previous season's final)
    / (n + k); the previous season's alone at n = 0. A team with no previous
    regular season has no blended rating (its games get no number)."""
    cur = tl.as_of_ratings(tb, tl.team_targets(games))
    cur["season"] = cur["season"].astype(int)
    x = cur.merge(season_end_ratings(tb), on=["season", "team"], how="inner")
    n = x["n"].to_numpy(float)
    den = n + float(k_blend)
    w = np.divide(n, den, out=np.zeros_like(n), where=den > 0)
    for c in VALUE_COLS:
        now, prev = x[c].to_numpy(float), x[f"{c}_prev"].to_numpy(float)
        x[c] = np.where(n > 0, w * now + (1.0 - w) * prev, prev)
    return x[["season", "team", "game_date", *tl.RATING_COLS]]


def f8_projection(tb: pd.DataFrame, games: pd.DataFrame, k_blend: float) -> pd.DataFrame:
    """The live models' gaps on blended ratings (tl.project_ratings), for the
    games where either team has fewer than EARLY_GAMES games this season."""
    g = games.assign(season=games["season"].astype(int))
    x = tl.pair_ratings(g, blended_ratings(tb, g, k_blend))
    x = x[(x["h_n"] < EARLY_GAMES) | (x["a_n"] < EARLY_GAMES)]
    return tl.project_ratings(x)


def f8_signal(proj: pd.DataFrame, market: str) -> pd.DataFrame:
    """(game_id, market, strength) toward side A (over): the full-game gap
    (tl.f4_signal) or the home team's part (P3.f4_signal), imported."""
    s = tl.f4_signal(proj) if market == "totals" else P3.f4_signal(proj)
    return s[s["market"] == market].reset_index(drop=True)


def gap_shuffles(signal: pd.DataFrame, games: pd.DataFrame, seeds=PLACEBO_SEEDS) -> list[pd.DataFrame]:
    """The gap moved between games on the same date in the same market."""
    return [H.shuffle_within_date(signal[["game_id", "market", "strength"]], games,
                                  np.random.default_rng(s)) for s in seeds]


def emit_f8(dd: H.Data, point: str, market: str, side: str, cut: float, neutral: pd.DataFrame,
            proj: pd.DataFrame, k_blend: float, choose, times=None, close=None, sig=None,
            n_placebo: int = N_PLACEBO) -> tuple[list[dict], pd.DataFrame]:
    """One F8 cell: the signal's side bet at its live cut on the early-season
    games, every graded season pooled; bands at gap 1-2, 2-3, 3-4, 4+."""
    signal = f8_signal(proj, market)
    nm = neutral[(neutral["market"] == market) & neutral["game_id"].isin(set(signal["game_id"]))]
    cand = tl.side_strength(nm, signal)
    lazy = LazyFrames(gap_shuffles(signal, dd.games, PLACEBO_SEEDS[:n_placebo]),
                      lambda sh: tl.side_strength(nm, sh)) if n_placebo else None
    rows = run_market(dd, F8_FAMILY, point, market, [side], [cut], cand, nm, lazy, "strength",
                      choose, times, close=close, sig=sig, edges=F8_EDGES,
                      cut_index=F8_EDGES.index(cut),
                      extra={"axis_blend": float(k_blend),
                             "signal_meaning": (f"{market} {side}, live cut {cut:g}, games where a team has "
                                                f"< {EARLY_GAMES} games; ratings blended n/(n+{k_blend:g})")})
    return rows, cand


# ── a synthetic world (the only place a cell is run before --full) ──────────

def american(p: float) -> float:
    """A win chance as an American price (synthetic quotes only)."""
    p = float(np.clip(p, 0.02, 0.98))
    return float(round(-100.0 * p / (1.0 - p)) if p >= 0.5 else round(100.0 * (1.0 - p) / p))


def synthetic_world(seed: int = 0, seasons=(2021, 2022, 2023, 2024, 2025, 2026), days: int = 40,
                    n_teams: int = 8) -> dict:
    """Random, never real. n_teams teams play every day in random pairs; each
    team has a strength and its own first-quarter scoring and allowed tilt.
    Games carry quarter scores, Pinnacle closes, team box sums for the luck
    ratings, the full-game slate (one fetch 60 minutes before tip, so it is
    decision point C) from the second season on, and the per-game purchase of
    the eight derivative markets 55 minutes before tip in the last three."""
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(n_teams)]
    strength = dict(zip(teams, rng.normal(0.0, 4.0, n_teams)))
    tilt_own = dict(zip(teams, rng.normal(0.0, 0.012, n_teams)))
    tilt_alw = dict(zip(teams, rng.normal(0.0, 0.012, n_teams)))
    books = ("pinnacle", "fanduel", "draftkings", "betmgm")
    games, per, close, tb, quotes, pe = [], [], [], [], [], []
    deriv_seasons = tuple(seasons[-3:])
    half = lambda v: float(np.floor(v)) + 0.5  # noqa: E731
    for s in seasons:
        for d in range(days):
            day = pd.Timestamp(f"{s - 1}-11-01") + pd.Timedelta(days=d)
            perm = rng.permutation(teams)
            for j in range(0, n_teams, 2):
                h, a = str(perm[j]), str(perm[j + 1])
                gid = f"S{s}_{d}_{h}_{a}"
                tip = (day + pd.Timedelta(hours=24)).tz_localize("UTC")
                he = 112.0 + (strength[h] - strength[a]) / 2.0 + 1.5
                ae = 112.0 - (strength[h] - strength[a]) / 2.0 - 1.5
                sh_h = 0.25 + tilt_own[h] + tilt_alw[a]
                sh_a = 0.25 + tilt_own[a] + tilt_alw[h]
                qh = rng.poisson([he * sh_h, he * 0.25, he * 0.25, he * (0.5 - sh_h)]).astype(float)
                qa = rng.poisson([ae * sh_a, ae * 0.25, ae * 0.25, ae * (0.5 - sh_a)]).astype(float)
                if qh.sum() == qa.sum():
                    qh[3] += 1.0
                hs, as_ = float(qh.sum()), float(qa.sum())
                date = day.strftime("%Y-%m-%d")
                games.append({"game_id": gid, "season": s, "game_date": date, "tip": tip,
                              "home_team": h, "away_team": a, "home_score": hs, "away_score": as_})
                per += [{"game_id": gid, "period": i + 1, "home_points": qh[i], "away_points": qa[i]}
                        for i in range(4)]
                spread = -half(he - ae)
                total = half(he + ae + rng.normal(0.0, 3.0))
                for m, line in (("spreads", spread), ("totals", total)):
                    close.append({"game_id": gid, "season": s, "market": m, "close_line": line,
                                  "close_fa": 0.5, "close_at": tip - pd.Timedelta(minutes=5)})
                for team, opp, pts, opts in ((h, a, hs, as_), (a, h, as_, hs)):
                    f3a, o3a = float(rng.integers(28, 40)), float(rng.integers(28, 40))
                    tb.append({"game_id": gid, "season": s, "game_date": date, "team": team, "opp": opp,
                               "pts": pts, "fg3m": float(rng.binomial(int(f3a), 0.36)), "fg3a": f3a,
                               "ftm": float(rng.binomial(22, 0.78)), "fta": 22.0,
                               "opp_pts": opts, "opp_fg3m": float(rng.binomial(int(o3a), 0.36)),
                               "opp_fg3a": o3a, "opp_ftm": float(rng.binomial(22, 0.78)), "opp_fta": 22.0,
                               "poss": float(rng.normal(100.0, 3.0))})
                if s == seasons[0]:
                    continue
                at = tip - pd.Timedelta(minutes=60)
                base = {"game_id": gid, "season": s, "game_date": date, "tip": tip,
                        "snapshot_at": at - pd.Timedelta(minutes=2), "fetch_at": at, "coherent": True}
                p_h = 1.0 / (1.0 + np.exp(-(he - ae) / 6.0))
                for b in books:
                    jg = float(rng.integers(-1, 2))
                    quotes += [
                        {**base, "book": b, "market": "h2h", "line": np.nan,
                         "price_a": american(p_h + 0.02), "price_b": american(1.0 - p_h + 0.02)},
                        {**base, "book": b, "market": "spreads", "line": spread, "price_a": -110.0, "price_b": -110.0},
                        {**base, "book": b, "market": "totals", "line": total, "price_a": -110.0 + 5 * jg,
                         "price_b": -110.0 - 5 * jg}]
                if s not in deriv_seasons:
                    continue
                at2 = tip - pd.Timedelta(minutes=55)
                b2 = {**base, "snapshot_at": at2, "fetch_at": at2}
                for b in books:
                    j = float(rng.integers(-1, 2))
                    pe += [
                        {**b2, "book": b, "market": "h2h_h1", "line": np.nan, "price_a": -118.0 + 6 * j, "price_b": -102.0 - 6 * j},
                        {**b2, "book": b, "market": "h2h_q1", "line": np.nan, "price_a": -115.0 + 6 * j, "price_b": -105.0 - 6 * j},
                        {**b2, "book": b, "market": "spreads_h1", "line": half(spread / 2) + 0.5 * j, "price_a": -110.0, "price_b": -110.0},
                        {**b2, "book": b, "market": "spreads_q1", "line": half(spread / 4) + 0.5 * j, "price_a": -110.0, "price_b": -110.0},
                        {**b2, "book": b, "market": "totals_h1", "line": half(total / 2) + 0.5 * j, "price_a": -110.0, "price_b": -110.0},
                        {**b2, "book": b, "market": "totals_q1", "line": half(total / 4) + 0.5 * j, "price_a": -110.0, "price_b": -110.0},
                        {**b2, "book": b, "market": "team_totals_home", "line": half((total - spread) / 2) + j, "price_a": -110.0, "price_b": -110.0},
                        {**b2, "book": b, "market": "team_totals_away", "line": half((total + spread) / 2) + j, "price_a": -110.0, "price_b": -110.0}]
    g = pd.DataFrame(games)
    games_p = H.with_periods(g, periods=pd.DataFrame(per))
    q = pd.DataFrame(quotes)
    fetches = q[["game_id", "tip", "fetch_at"]].drop_duplicates(["game_id", "fetch_at"])
    fetches = fetches.assign(lead_min=(fetches["tip"] - fetches["fetch_at"]).dt.total_seconds() / 60.0)
    data = H.Data(games=g, quotes=q[H.QUOTE_COLS].reset_index(drop=True),
                  fetches=fetches.reset_index(drop=True))
    return {"games": g, "games_p": games_p, "data": data, "pe": pd.DataFrame(pe)[H.QUOTE_COLS],
            "close": pd.DataFrame(close), "tb": pd.DataFrame(tb), "f7_graded": deriv_seasons,
            "f7_choose": deriv_seasons[:-1], "full_choose": tuple(x for x in seasons[1:-1]),
            "share_fit": tuple(seasons[:3]), "truth": {"own": tilt_own, "allowed": tilt_alw}}


def run_world(world: dict, n_placebo: int = 2, min_prior: int = 300, k: dict | None = None) -> dict:
    """F7, its controls and F8 end to end on a world (synthetic_world's keys)."""
    games_p, data, pe = world["games_p"], world["data"], world["pe"]
    graded, choose = world["f7_graded"], world["f7_choose"]
    if k is None:
        k, _ = fit_shrinkage(games_p, world["share_fit"])
    sig = H.close_dist(world["close"], data.games)
    times = H.per_event_times(pe, "D")
    vis = NB.visible_numbers(pe, times)
    off = H.offers(vis)
    pricing = P3.market_pricing(world["close"], games_p, graded, min_prior)
    P3.require_pricing(pricing, graded, P3.PRICED_MARKETS, "the market's own pricing")
    neutral = P3.neutral_offers(vis, pricing)
    period_fair = H.market_fair(vis, pricing)
    dd = P3.derivative_data(games_p, pe)
    full = full_game_numbers(full_game_visible(data.quotes, times), sig)
    rows_tp = team_period_rows(games_p)
    sh = game_shares(games_p[games_p["season"].isin(graded)], rows_tp, k)
    f7, cand7 = emit_f7(dd, times, off, neutral, full, sh, period_fair, pricing, choose, n_placebo)
    ctl, _ = emit_f7(dd, times, off, neutral, full, sh, period_fair, pricing, choose, n_placebo,
                     league_only=True)
    f8, cand8 = [], {}
    tC, neutral_c = L.market_offers(data, "C", sig, ["totals"])
    for market, side, cut, point in F8_SIGNALS:
        for b in F8_BLENDS:
            proj = f8_projection(world["tb"], data.games, b)
            if point == "C":
                rows, cand = emit_f8(data, "C", market, side, cut, neutral_c, proj, b,
                                     world["full_choose"], close=None, sig=None, n_placebo=n_placebo)
            else:
                rows, cand = emit_f8(dd, "D", market, side, cut, neutral, proj, b, choose,
                                     times=times, n_placebo=n_placebo)
            f8 += rows
            cand8[(market, b)] = cand
    assert len(f8) == EXPECTED_CELLS[F8_FAMILY], len(f8)
    return {"rows": {F7_FAMILY: f7, F7_CONTROL: ctl, F8_FAMILY: f8}, "cand": {F7_FAMILY: cand7, F8_FAMILY: cand8},
            "times": times, "off": off, "neutral": neutral, "pricing": pricing, "full": full, "sh": sh,
            "period_fair": period_fair, "k": k, "dd": dd, "sig": sig}


def synthetic_checks(n_placebo: int = 2) -> dict:
    """Before any real data is read (--smoke, --full): the harness's sign
    checks, and all 54 cells and the 48 controls through run_cells on
    synthetic games. NBA_GAME2_BETS is unset while they run: run_cells writes
    every cell's bets wherever it points, and the first graded run (2026-10-20)
    found 18 files of synthetic bets beside the real ones."""
    H.check()
    saved = os.environ.pop(BETS_ENV, None)
    try:
        out = run_world(synthetic_world(), n_placebo=n_placebo)
    finally:
        if saved is not None:
            os.environ[BETS_ENV] = saved
    n = {f: len(r) for f, r in out["rows"].items()}
    assert n == {F7_FAMILY: 48, F7_CONTROL: 48, F8_FAMILY: 6}, n
    for fam in (F7_FAMILY, F8_FAMILY):
        assert sum(r["pool_n"] for r in out["rows"][fam]) > 0, f"{fam}: no synthetic bets"
    print(f"synthetic: {n} cells (48 + 6 registered, 48 controls); nothing written")
    return out


# ── real data: loading, counts, the graded run ──────────────────────────────

def load_real(cache: Path, require: bool) -> dict:
    """Everything both families read from the cache. `require`: a graded run
    refuses a season priced on fewer than 90% of its games (H.load,
    H.load_per_event) and a derivative cache that is not exactly 2023-24 ..
    2025-26."""
    data = H.load(cache, seasons=FULL_GAME_SEASONS, require_seasons=FULL_GAME_SEASONS if require else None)
    all_games = H.load_games(cache)
    games_p = H.with_periods(all_games, cache)
    if require:
        pe, graded = P3.load_derivatives(games_p[games_p["season"].isin(data.games["season"])], cache)
    else:
        pe = H.load_per_event(games_p, cache)
        graded = P3.graded_seasons(pe["season"].unique())
    if tuple(graded) != F7_GRADED:
        raise RuntimeError(f"derivative seasons {graded}, section 9 grades exactly {F7_GRADED}")
    pe = pe[pe["season"].isin(graded)].reset_index(drop=True)
    box, _ = L._load_box(cache)
    tb = tl.team_box(box, all_games)
    return {"data": data, "all_games": all_games, "games_p": games_p, "pe": pe, "graded": tuple(graded),
            "tb": tb}


def prepare(real: dict, k: dict) -> dict:
    """The decision-time frames on real data (no grading)."""
    data, games_p, pe, graded = real["data"], real["games_p"], real["pe"], real["graded"]
    close = H.pinnacle_close(data)
    sig = H.close_dist(close, data.games)
    times = H.per_event_times(pe, "D")
    vis = NB.visible_numbers(pe, times)
    off = H.offers(vis)
    gp_full = games_p[games_p["season"].isin(data.games["season"])]
    pricing = P3.market_pricing(close, gp_full, graded)
    P3.require_pricing(pricing, graded, P3.PRICED_MARKETS, "the market's own pricing")
    neutral = P3.neutral_offers(vis, pricing)
    period_fair = H.market_fair(vis, pricing)
    full = full_game_numbers(full_game_visible(data.quotes, times), sig)
    sh = game_shares(games_p[games_p["season"].isin(graded)], team_period_rows(games_p), k)
    dd = P3.derivative_data(gp_full[gp_full["season"].isin(graded)], pe)
    return {"close": close, "sig": sig, "times": times, "vis": vis, "off": off, "pricing": pricing,
            "neutral": neutral, "period_fair": period_fair, "full": full, "sh": sh, "dd": dd}


def early_games(tb: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """(game_id, season): games where either team has fewer than EARLY_GAMES
    games this season before the date, from the unblended ratings' n."""
    g = games.assign(season=games["season"].astype(int))
    r = tl.as_of_ratings(tb, tl.team_targets(g))
    r["season"] = r["season"].astype(int)
    x = tl.pair_ratings(g, r)
    return x.loc[(x["h_n"] < EARLY_GAMES) | (x["a_n"] < EARLY_GAMES), ["game_id", "season"]]


def f8_counts(real: dict, prep: dict) -> list[dict]:
    """Per F8 cell and season: the early-season games, those with a blended
    number, those at or past the live cut (no price read), and the bets the
    cell would place (an offer at a deciding book at or above the floor;
    counted, never graded)."""
    data, tb = real["data"], real["tb"]
    tC, neutral_c = L.market_offers(data, "C", prep["sig"], ["totals"])
    early = early_games(tb, data.games)
    out = []
    for market, side, cut, point in F8_SIGNALS:
        for b in F8_BLENDS:
            games = data.games if point == "C" else data.games[data.games["season"].isin(F8_TT_GRADED)]
            proj = f8_projection(tb, games, b)
            s = f8_signal(proj, market)
            s = s.assign(side_strength=np.where(side in ("over", "home"), s["strength"], -s["strength"]))
            nm = neutral_c if point == "C" else prep["neutral"]
            nm = nm[(nm["market"] == market) & nm["game_id"].isin(set(s["game_id"]))]
            bets = H.choose(tl.side_strength(nm, s)[lambda c: c["strength"] >= cut], -np.inf, sides=[side])
            for se in sorted(set(games["season"].astype(int))):
                ids = set(games.loc[games["season"].astype(int) == se, "game_id"])
                out.append({"market": market, "side": side, "cut": cut, "point": point, "blend": b,
                            "season": se, "early_games": int(early["game_id"].isin(ids).sum()),
                            "early_games_with_number": int(s["game_id"].isin(ids).sum()),
                            "games_at_or_past_cut": int((s["game_id"].isin(ids) & (s["side_strength"] >= cut)).sum()),
                            "bets_with_an_offer": int(bets["game_id"].isin(ids).sum())})
    return out


def f7_counts(prep: dict, graded) -> dict:
    """Games per season with a decision, the full-game numbers, the shares, and
    per market the games whose number falls in each band (no result read)."""
    dd = prep["dd"]
    season = dd.games.drop_duplicates("game_id").set_index("game_id")["season"].astype(int)

    def by_season(ids):
        return season.reindex(pd.unique(np.asarray(list(ids), dtype=object))).value_counts().sort_index().to_dict()

    proj = f7_projection(prep["full"], prep["sh"])
    strength, ml_fair = f7_signals(proj, prep["period_fair"], prep["pricing"])
    bands = {}
    for m in F7_SIDES:
        cuts = f7_cuts(m)
        if H.kind([m])[0] == "ml":
            c = f7_cand(m, prep["neutral"], prep["off"], strength, ml_fair)
            best = c[c["book"].isin(H.BETTABLE) & (c["price"] >= H.PRICE_FLOOR)].groupby(["game_id", "side"])["ev"].max()
            vals = {sd: best.xs(sd, level="side").to_numpy() for sd in F7_SIDES[m]}
        else:
            v = strength[strength["market"] == m]["strength"].to_numpy(float)
            a, b = F7_SIDES[m]
            vals = {a: v, b: -v}
        edges = (0.0, *cuts, np.inf)
        bands[m] = {sd: [int(((x >= lo) & (x < hi)).sum()) for lo, hi in zip(edges[:-1], edges[1:])]
                    for sd, x in vals.items()}
    return {"games": season.value_counts().sort_index().to_dict(),
            "with_a_decision_at_D": by_season(prep["times"]["game_id"]),
            "with_full_game_numbers": by_season(prep["full"]["game_id"]),
            "with_shares": by_season(prep["sh"].dropna(subset=list(SHARE_COLS))["game_id"]),
            "with_a_projection": by_season(proj["game_id"]),
            "band_edges": {m: [0.0, *f7_cuts(m)] for m in F7_SIDES},
            "games_per_band_from_0": bands}


def smoke(cache: Path = H.CACHE) -> dict:
    """Synthetic cells, then on the real cache only what section 9 allows
    before grading. No real cell is run and no real bet is graded."""
    synthetic_checks()
    games_p = H.with_periods(H.load_games(cache), cache)
    pers = persistence(games_p)
    k, fit = fit_shrinkage(games_p)
    print("PERSISTENCE (period scores only):")
    print(pers.round(3).to_string(index=False))
    print("SHRINKAGE FIT 2019-20 .. 2022-23 (period scores only): k =", k)
    print(fit.to_string(index=False))
    real = load_real(cache, require=False)
    prep = prepare(real, k)
    summary = {"graded_seasons": list(real["graded"]), "k": k,
               "f7": f7_counts(prep, real["graded"]), "f8": f8_counts(real, prep)}
    print(json.dumps(summary, indent=1, default=str))
    return summary


def refuse_full(cache: Path) -> list[str]:
    """The go flag, a named results folder and bets folder (as P1-P3 require),
    and the fetch ledger the full-game closes read. Section 9 needs no lineup
    segments, so the projection lab's stints check is not asked."""
    why = []
    if os.environ.get(GO_ENV) != "1":
        why.append(f"{GO_ENV}=1 is not set: the owner runs --full")
    if not os.environ.get(RESULTS_ENV):
        why.append(f"{RESULTS_ENV} is not set: name the fifth search's results folder")
    if not os.environ.get(BETS_ENV):
        why.append(f"{BETS_ENV} is not set: a passing cell's figures read its bets")
    if not (Path(cache) / P.LEDGER_FILE).exists():
        why.append(f"{Path(cache) / P.LEDGER_FILE} does not exist: refresh the cache")
    return why


def full(cache: Path = H.CACHE, out: Path | None = None) -> None:
    why = refuse_full(cache)
    if why:
        P.refuse(why)
    out = Path(os.environ[RESULTS_ENV]) if out is None else out
    synthetic_checks()
    try:
        real = load_real(cache, require=True)
    except RuntimeError as e:
        P.refuse([str(e)])
    k, fit = fit_shrinkage(real["games_p"])
    if k != REGISTERED_K:
        P.refuse([f"the shrinkage refit returned k = {k}; section 9.3 registered {REGISTERED_K}"])
    prep = prepare(real, k)
    graded, choose = real["graded"], P3.choosing(real["graded"])
    print("F7 graded", graded, "choosing", choose, "k", k)
    f7, cand7 = emit_f7(prep["dd"], prep["times"], prep["off"], prep["neutral"], prep["full"], prep["sh"],
                        prep["period_fair"], prep["pricing"], choose)
    ctl, cand_c = emit_f7(prep["dd"], prep["times"], prep["off"], prep["neutral"], prep["full"], prep["sh"],
                          prep["period_fair"], prep["pricing"], choose, N_PLACEBO, league_only=True)
    data = real["data"]
    tC, neutral_c = L.market_offers(data, "C", prep["sig"], ["totals"])
    f8, pop8 = [], []
    for market, side, cut, point in F8_SIGNALS:
        for b in F8_BLENDS:
            if point == "C":
                proj = f8_projection(real["tb"], data.games, b)
                rows, cand = emit_f8(data, "C", market, side, cut, neutral_c, proj, b, H.CHOOSE,
                                     close=prep["close"], sig=prep["sig"])
                pop = L.population(data.games, "C", neutral_c[neutral_c["market"] == market],
                                   cand[["game_id", "market"]].drop_duplicates(), rows)
            else:
                proj = f8_projection(real["tb"], data.games[data.games["season"].isin(F8_TT_GRADED)], b)
                rows, cand = emit_f8(prep["dd"], "D", market, side, cut, prep["neutral"], proj, b, choose,
                                     times=prep["times"])
                pop = P3.population(F8_FAMILY, rows, prep["dd"], prep["times"], prep["off"], cand,
                                    "strength", F8_TT_GRADED)
            f8 += rows
            pop8.append(pop.assign(blend=b, signal=f"{market} {side}"))
    assert len(f7) == 48 and len(ctl) == 48 and len(f8) == 6
    pop7 = pd.concat([P3.population(F7_FAMILY, [r for r in f7 if r["market"] == m], prep["dd"], prep["times"],
                                    prep["off"], c, "ev" if H.kind([m])[0] == "ml" else "strength", graded)
                      for m, c in cand7.items()], ignore_index=True)
    # every table is written only once all three are built
    out.mkdir(parents=True, exist_ok=True)
    L.write_cells(f7, out / "cells_F7.parquet")
    L.write_cells(f8, out / "cells_F8.parquet")
    L.write_cells(ctl, out / f"cells_{F7_CONTROL}.parquet")
    pop7.to_parquet(out / "population_F7.parquet")
    pd.concat(pop8, ignore_index=True).to_parquet(out / "population_F8.parquet")
    (out / "shares.json").write_text(json.dumps({"k": k, "fit": fit.to_dict("records")}, default=str),
                                     encoding="utf-8")
    print(f"cells written to {out}: F7 {len(f7)}, F8 {len(f8)}, controls {len(ctl)}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true", help="synthetic cells, then real counts only")
    g.add_argument("--full", action="store_true", help=f"every graded season (needs {GO_ENV}=1)")
    a = ap.parse_args(argv)
    if a.full:
        full(H.CACHE)
    else:
        smoke(H.CACHE)


if __name__ == "__main__":
    main()
