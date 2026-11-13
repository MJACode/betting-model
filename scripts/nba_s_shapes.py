"""NBA search: the failed spread and moneyline families, re-graded with line-size result shapes.

docs/nba_search_shapes.md registers the families, cells, bands, bars, placebo and controls,
written and committed BEFORE this lab and before any cell was graded. This lab EMITS cells
through the shared harness (scripts/nba_game_harness.py, H.run_cells); the pass/fail script
judges them (python -m scripts.nba_game2_verdict --results DIR --house5, section 9.1's bars).
No cut, constant or rule here was chosen from a betting result.

THE CHANGE, AND THE ONLY ONE
  One result shape per (season, market), H.close_dist, becomes one shape per (season, size of
  the line, favoured team): scripts/nba_game6_alt.spread_shapes, the results around Pinnacle's
  close on the seasons before the graded one, for games whose closing line was 5 or less, 5 to
  10, or more than 10 points, signed toward the favourite and mirrored when the away team is
  favoured. A bucket with fewer than MIN_PRIOR earlier games, a level line, or a game with no
  number falls back to the one shape. Cuts, decision points and sides are the originals'.

WHAT THE SHAPE REACHES (the families, section 3 of the doc)
  S_F2   a spread becomes a win chance, the moneyline is priced on it.
  S_F6d  the same, each book's moneyline against that book's own spread.
  S_F1   the projection's own error, split the same way (the market's shape never priced F1).
  S_P1   the market-anchored centre and every offer priced around it (spreads).
  S_P2   off-number spreads: which qualifying offer is taken, the blind bets.
  Not reached, graded once as controls: P2's same-number cells and P1's moneylines.

EVERY NUMBER THIS SEARCH READS PASSES THE SAME RULE, IN BOTH ARMS (impossible_mask)
  a spread quote, Pinnacle's included, more than MAX_SPREAD_GAP points from the median of the
  deciding books' numbers at T, or a moneyline quote whose no-vig home chance is more than
  MAX_ML_GAP from their median, is not a price that can be read. It is dropped before pricing.

PLACEBO: 200 runs, seeds 1-200 (fast_placebo). Each game keeps its own market number and its own
  prices; what moves, between games on the same date, is the family's DISAGREEMENT with the
  market (S_F2, S_F6d, S_F1, S_P1), or the gap among the offers on a date and side (S_P2).
  Moving a whole number would hand a game another game's market price, which anything beats.

SPEED: 200 placebo runs reprice arrays built once (class Fast); one pre-grade of every offer,
  one sort per run. H.run_cells does the real cell. Fast is tested against the harness.

    PYTHONPATH=. python -m scripts.nba_s_shapes --smoke
    NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> NBA_GAME2_BETS=<folder>/bets \
        PYTHONPATH=. python -m scripts.nba_s_shapes --full
    PYTHONPATH=. python -m scripts.nba_game2_verdict --results <folder> --house5

--smoke runs the synthetic checks, then on the real cache prints counts, extremes, highest-EV
offers, placebo-differ shares and timings. It never grades a real bet: anything that needs a
result (the timing passes) is given scrambled scores. NBA_S_PROJ_DIR names a folder of projection
frames to reuse or fill (regenerable from the cache: the projection is deterministic).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from models.nba_book_numbers import main_rungs, visible_numbers  # noqa: E402
from scripts import nba_game2_luck as L  # noqa: E402
from scripts import nba_game2_market as M  # noqa: E402
from scripts import nba_game2_projection as P  # noqa: E402
from scripts import nba_game4_p1 as P1  # noqa: E402
from scripts import nba_game4_p2 as P2  # noqa: E402
from scripts import nba_game5 as G5  # noqa: E402
from scripts import nba_game6_alt as A  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402

GO_ENV, RESULTS_ENV, BETS_ENV = G5.GO_ENV, G5.RESULTS_ENV, G5.BETS_ENV
PROJ_ENV = "NBA_S_PROJ_DIR"
SEASONS = (H.REGIME, *H.CHOOSE, H.CONFIRM)        # 2020-21 .. 2025-26
MARKETS = ("h2h", "spreads")                      # section 10.7 measured no line-size shape for totals
MIN_PRIOR = 300                                   # spread_shapes' own floor, unchanged
N_PLACEBO = 200
SEEDS = tuple(range(1, N_PLACEBO + 1))
MAX_SPREAD_GAP = 2.5                              # points from the deciding books' median at T
MAX_ML_GAP = 0.08                                 # no-vig home chance from their median at T
MIN_BOOKS = 3                                     # fewer deciding quotes: no median to read against
P_CLIP = 1e-4

FAM_F2, FAM_F6D, FAM_F1, FAM_P1, FAM_P2 = "S_F2", "S_F6d", "S_F1", "S_P1", "S_P2"
FAMILIES = (FAM_F2, FAM_F6D, FAM_F1, FAM_P1, FAM_P2)
CONTROL_SAME, CONTROL_ML = "control_S_P2_same_number", "control_S_P1_moneyline"
F2_REFS = ("pinnacle", "consensus")
F2_LABELS = ("fav", "dog")
EV_CUTS = (0.0, 0.01, 0.02, 0.03, 0.05, 0.08)     # F2, F1 (section 6.3)
F6D_CUTS = (0.01, 0.03)                           # F6d (section 6.3)
P1_CUTS = (0.02, 0.04, 0.06, 0.08)                # P1 (section 8)
GAP_CUTS = (0.5, 1.0, 1.5, 2.0)                   # P2 off number (section 8.2)
SAME_CUTS = (0.0, 0.01, 0.02, 0.03)               # P2 same number (section 8.2)
POINTS_ALL = ("A", "B", "C", "D")
POINTS_P1 = ("A", "C", "D")
POINTS_F6D = ("C", "D")
LOWEST_EV_BAND = -0.01                            # the band below a cut of EV >= 0
HOME_AWAY = ("home", "away")
EXPECTED_CELLS = 256
TIMED_POINT = "D"                                 # --smoke times one whole group per family and market here
CONTROLS_AT_TIMED_POINT = 24                      # P2 same number 16, P1 moneyline 8


def oneshape(family: str) -> str:
    """A registered family's one-shape twin: the same cells, the original pricing, never judged."""
    return f"control_{family}_oneshape"


def cell_plan() -> list[tuple]:
    """(family, point, market, label, axis, cut_index, cut) for every registered cell."""
    out = []
    for p in POINTS_ALL:
        for ref in F2_REFS:
            for lab in F2_LABELS:
                out += [(FAM_F2, p, "h2h", lab, ref, k, c) for k, c in enumerate(EV_CUTS)]
    for p in POINTS_F6D:
        for lab in HOME_AWAY:
            out += [(FAM_F6D, p, "h2h", lab, "", k, c) for k, c in enumerate(F6D_CUTS)]
    for p in POINTS_ALL:
        for m in MARKETS:
            for lab in HOME_AWAY:
                out += [(FAM_F1, p, m, lab, "", k, c) for k, c in enumerate(EV_CUTS)]
    for p in POINTS_P1:
        for lab in HOME_AWAY:
            out += [(FAM_P1, p, "spreads", lab, "", k, c) for k, c in enumerate(P1_CUTS)]
    for p in POINTS_ALL:
        for lab in HOME_AWAY:
            out += [(FAM_P2, p, "spreads", lab, "off_number", k, c) for k, c in enumerate(GAP_CUTS)]
    return out


def control_plan() -> list[tuple]:
    """The cells the shape cannot reach, graded once: never candidates."""
    out = []
    for p in POINTS_ALL:
        for m in MARKETS:
            for lab in HOME_AWAY:
                out += [(CONTROL_SAME, p, m, lab, "same_number", k, c) for k, c in enumerate(SAME_CUTS)]
    for p in POINTS_P1:
        for lab in HOME_AWAY:
            out += [(CONTROL_ML, p, "h2h", lab, "", k, c) for k, c in enumerate(P1_CUTS)]
    return out


def check_plan() -> None:
    plan = cell_plan()
    assert len(plan) == EXPECTED_CELLS, len(plan)
    by = pd.Series([c[0] for c in plan]).value_counts().to_dict()
    assert by == {FAM_F2: 96, FAM_F6D: 8, FAM_F1: 96, FAM_P1: 24, FAM_P2: 32}, by
    assert len(control_plan()) == 88
    assert len(set(plan)) == len(plan)


check_plan()


# ── the rule for numbers that cannot be read ────────────────────────────────

def no_vig_a(vis: pd.DataFrame) -> np.ndarray:
    ia, ib = H.imp(vis["price_a"]), H.imp(vis["price_b"])
    return np.asarray(ia / (ia + ib), float)


def impossible_mask(vis: pd.DataFrame) -> np.ndarray:
    """True for a quote that cannot be read at T: a spread more than MAX_SPREAD_GAP points from the
    median of the deciding books' numbers (Pinnacle's own included: a Pinnacle number left over
    from before the news is the same fault), a moneyline more than MAX_ML_GAP in no-vig home chance
    from their median. Needs MIN_BOOKS deciding quotes. Never reads a result."""
    if vis.empty:
        return np.zeros(0, bool)
    num = np.where(vis["market"].to_numpy(object) == "spreads", vis["line"].to_numpy(float), no_vig_a(vis))
    x = pd.DataFrame({"game_id": vis["game_id"].to_numpy(), "market": vis["market"].to_numpy(),
                      "book": vis["book"].to_numpy(), "num": num,
                      "coh": vis["coherent"].to_numpy(bool)})
    dec = x[x["book"].isin(H.BETTABLE) & x["coh"]]
    grp = dec.groupby(["game_id", "market"])["num"]
    ref = pd.DataFrame({"_med": grp.median(), "_n": grp.size()}).reset_index()
    y = x.merge(ref, on=["game_id", "market"], how="left")     # a left merge keeps x's order
    lim = np.where(y["market"].to_numpy(object) == "spreads", MAX_SPREAD_GAP, MAX_ML_GAP)
    far = np.abs(y["num"].to_numpy(float) - y["_med"].to_numpy(float)) > lim + 1e-9
    return far & (y["_n"].to_numpy(float) >= MIN_BOOKS)


def clean(vis: pd.DataFrame, ledger: list | None = None, where: str = "") -> pd.DataFrame:
    """`vis` without the unreadable quotes; each one dropped is kept in `ledger` (counts in --smoke)."""
    far = impossible_mask(vis)
    if ledger is not None and far.any():
        ledger.append(vis.loc[far, ["game_id", "season", "market", "book", "line", "price_a", "price_b"]]
                      .assign(where=where))
    return vis.loc[~far].reset_index(drop=True)


def clean_close(data: H.Data) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(H.pinnacle_close without an unreadable close, the rows dropped): the same rule, against the
    deciding books at the game's last pre-tip fetch. The shapes and closing value read this."""
    close = H.pinnacle_close(data)
    last = P.close_times(data)
    q = data.quotes[data.quotes["book"].isin(H.BETTABLE) & data.quotes["market"].isin(MARKETS)]
    vis = H.visible(q, last)
    vis = vis[vis["coherent"]]
    num = np.where(vis["market"].to_numpy(object) == "spreads", vis["line"].to_numpy(float), no_vig_a(vis))
    grp = vis.assign(num=num).groupby(["game_id", "market"])["num"]
    ref = pd.DataFrame({"_med": grp.median(), "_n": grp.size()}).reset_index()
    x = close.merge(ref, on=["game_id", "market"], how="left")
    c_num = np.where(x["market"].to_numpy(object) == "spreads", x["close_line"].to_numpy(float),
                     x["close_fa"].to_numpy(float))
    lim = np.where(x["market"].to_numpy(object) == "spreads", MAX_SPREAD_GAP, MAX_ML_GAP)
    far = (np.abs(c_num - x["_med"].to_numpy(float)) > lim + 1e-9) & (x["_n"].to_numpy(float) >= MIN_BOOKS)
    kept = x.loc[~far].drop(columns=["_med", "_n"]).reset_index(drop=True)
    return kept, x.loc[far].drop(columns=["_n"]).reset_index(drop=True)


# ── pricing: one shape, or the shape for the size of the line ───────────────

@dataclass
class Pricing:
    """An arm of the search. `shapes` empty: the one shape per (season, market), the originals'."""
    arm: str
    sig: dict
    shapes: dict = field(default_factory=dict)

    def sigma(self, season, market, number):
        return A.game_sigma(season, market, number, self.sig, self.shapes)


def build_pricing(close: pd.DataFrame, games: pd.DataFrame, seasons=SEASONS,
                  min_prior: int = MIN_PRIOR) -> tuple[Pricing, Pricing]:
    """(line-size arm, one-shape arm). Both read the seasons before the graded one; 2020-21, which
    has none, is priced on its own season's one shape in both (H.close_dist's fallback: reported,
    never chosen on, as in the originals)."""
    sig = H.close_dist(close, games)
    shapes = A.spread_shapes(close, games, seasons=seasons, min_prior=min_prior)
    return Pricing("line", sig, {"spreads": shapes}), Pricing("one", sig, {})


def shaped_fair(vis: pd.DataFrame, pr: Pricing) -> pd.DataFrame:
    """H.market_fair with the shape read per game: the size and sign of the game's number at T
    (Pinnacle's coherent spread where it quotes, else the median of the deciding books',
    M.posted_spread, among the rows given). The one-shape arm returns H.market_fair's numbers."""
    v = vis[vis["coherent"] & vis["book"].isin((H.SHARP, *H.BETTABLE))].copy()
    if v.empty:
        return pd.DataFrame(columns=["game_id", "market", "mu", "sigma", "p_home", "ref"])
    ia, ib = H.imp(v["price_a"]), H.imp(v["price_b"])
    v["fa"] = ia / (ia + ib)
    k = H.kind(v["market"])
    number = v["game_id"].map(M.posted_spread(v)).to_numpy(float)
    seen, sigma = {}, []
    for se, m, kk, n in zip(v["season"].to_numpy(int), v["market"].to_numpy(object), k, number):
        if kk == "ml":
            sigma.append(np.nan)
            continue
        key = (int(se), m, None if not np.isfinite(n) else float(n))
        if key not in seen:
            got = pr.sigma(int(se), m, n)
            seen[key] = np.nan if got is None else got
        sigma.append(seen[key])
    v["sigma"] = pd.Series(sigma, index=v.index, dtype=object)
    sp = k != "ml"
    mu = np.full(len(v), np.nan)
    if sp.any():
        x = v[sp]
        mu[sp] = H.solve_any(H.threshold(x["market"], x["line"]), x["fa"].to_numpy(), x["sigma"].to_numpy())
    v["mu"] = mu
    sharp = v[v["book"] == H.SHARP].drop_duplicates(["game_id", "market"])
    rest = v[v["book"] != H.SHARP].groupby(["game_id", "market"]).agg(
        mu=("mu", "median"), fa=("fa", "median"), sigma=("sigma", "first")).reset_index()
    have = set(zip(sharp["game_id"], sharp["market"]))
    rest = rest[[kk not in have for kk in zip(rest["game_id"], rest["market"])]]
    out = pd.concat([sharp[["game_id", "market", "mu", "fa", "sigma"]].assign(ref="pinnacle"),
                     rest.assign(ref="consensus")], ignore_index=True)
    out["p_home"] = np.where(H.kind(out["market"]) == "ml", out["fa"], np.nan)
    return out.drop(columns="fa")


def own_error_shapes(proj: pd.DataFrame, cons: pd.Series, games: pd.DataFrame, seasons=SEASONS,
                     min_prior: int = MIN_PRIOR) -> dict:
    """spread_shapes for a projection: {(season, bucket, home_favoured): ResidDist} of the home margin
    around the projection at this decision point, from games whose number at T (`cons`, game_id ->
    the HOME number) had the same size, on the seasons before `season`. Signed toward the favourite,
    mirrored when the away team is favoured, exactly as spread_shapes."""
    x = proj[["game_id", "season", "margin"]].dropna().copy()
    x["cons"] = x["game_id"].map(cons).to_numpy(float)
    x = x[np.isfinite(x["cons"]) & (x["cons"].abs() > 1e-9)]
    x = x.merge(games[["game_id", "home_score", "away_score"]], on="game_id")
    r_home = (x["home_score"] - x["away_score"]).to_numpy(float) - x["margin"].to_numpy(float)
    fav_home = x["cons"].to_numpy(float) < 0
    r_fav = np.where(fav_home, r_home, -r_home)
    df = pd.DataFrame({"season": x["season"].astype(int).to_numpy(), "b": A.spread_bucket(x["cons"]), "r": r_fav})
    out = {}
    for s in seasons:
        for b in range(len(A.SPREAD_BUCKETS) + 1):
            prior = df[(df["season"] < s) & (df["b"] == b)]["r"].to_numpy(float)
            if len(prior) < min_prior:
                continue
            out[(s, b, True)] = H.ResidDist(prior, f"{s} projection bucket {b} home favoured")
            out[(s, b, False)] = H.ResidDist(-prior, f"{s} projection bucket {b} away favoured")
    return out


def own_fair(proj: pd.DataFrame, dist: dict, shapes: dict, cons: pd.Series) -> pd.DataFrame:
    """P.fair_frame's spread and moneyline rows with the shape read per game (`shapes` empty: the
    projection's one shape, P.fair_frame's numbers). The moneyline is P(home margin > 0) with the
    tie mass removed. `cons`: game_id -> the game's number at T; none, or level: the one shape."""
    p = proj[["game_id", "season", "margin", "total"]].dropna().reset_index(drop=True)
    number = p["game_id"].map(cons).to_numpy(float)
    sh = {"spreads": shapes} if shapes else {}
    dsp = np.empty(len(p), dtype=object)
    for i, (se, n) in enumerate(zip(p["season"].astype(int).to_numpy(), number)):
        dsp[i] = A.game_sigma(int(se), "spreads", n, dist, sh)
    mar = p["margin"].to_numpy(float)
    w, _, lose = H.probs_any(mar, dsp, np.zeros(len(p)))
    ph = w / np.where(w + lose > 0, w + lose, np.nan)
    f = pd.concat([
        pd.DataFrame({"game_id": p["game_id"], "market": "spreads", "mu": mar,
                      "sigma": pd.Series(list(dsp), index=p.index, dtype=object), "p_home": np.nan}),
        pd.DataFrame({"game_id": p["game_id"], "market": "h2h", "mu": np.nan,
                      "sigma": pd.Series([None] * len(p), index=p.index, dtype=object), "p_home": ph}),
    ], ignore_index=True)
    ok = np.where(f["market"] == "h2h", f["p_home"].notna(), f["mu"].notna() & f["sigma"].notna())
    return f[ok].reset_index(drop=True)


# ── the fast placebo: arrays built once, one sort per run ───────────────────

def _logit(p) -> np.ndarray:
    p = np.clip(np.asarray(p, float), P_CLIP, 1.0 - P_CLIP)
    return np.log(p / (1.0 - p))


def _expit(x) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.asarray(x, float)))


def permute_within(groups: list[np.ndarray], n: int, seed: int) -> np.ndarray:
    """A permutation of 0..n-1 moving each index only inside its group, one seed, one pass."""
    rng = np.random.default_rng(seed)
    perm = np.arange(n)
    for g in groups:
        perm[g] = g[rng.permutation(len(g))]
    return perm


class Fast:
    """The offers of one group (ONE market) as arrays, each offer graded once.

    `masks`: {label: bool per row}, the offers a cell label may bet. Mirrors H.choose: a deciding
    book, the price floor, the best EV per game with ties to the earlier book, a NaN EV never
    chosen. Everything a run needs is here, so a run is one sort and some sums."""

    def __init__(self, pool: pd.DataFrame, masks: dict, games: pd.DataFrame, choose_seasons):
        self.n = len(pool)
        ok = pool["book"].isin(H.BETTABLE).to_numpy() & (pool["price"].to_numpy(float) >= H.PRICE_FLOOR)
        self.gid = pd.factorize(pool["game_id"])[0]
        self.rank = pool["book"].map(H.BOOK_RANK).fillna(99).to_numpy(float)
        self.choosing = pool["season"].isin(list(choose_seasons)).to_numpy()
        self.units, self.risk = np.zeros(self.n), np.zeros(self.n)
        rows = np.flatnonzero(ok)
        self.graded = np.zeros(self.n, bool)
        if len(rows):
            g = H.grade(pool.iloc[rows][["game_id", "market", "side", "line", "price"]].assign(_i=rows), games)
            i = g["_i"].to_numpy()
            self.units[i], self.risk[i], self.graded[i] = g["units"].to_numpy(float), g["risk"].to_numpy(float), True
        self.idx = {lab: np.flatnonzero(np.asarray(m, bool) & self.graded) for lab, m in masks.items()}

    def best(self, ev: np.ndarray, lab: str) -> np.ndarray:
        """Row of the best offer per game, among this label's rows."""
        idx = self.idx[lab]
        if not len(idx):
            return idx
        e = np.where(np.isnan(ev[idx]), -np.inf, ev[idx])
        order = np.lexsort((self.rank[idx], -e, self.gid[idx]))
        g = self.gid[idx][order]
        return idx[order[np.r_[True, g[1:] != g[:-1]]]]

    def at_cut(self, ev: np.ndarray, best: np.ndarray, cut: float) -> np.ndarray:
        return best[ev[best] >= cut]                    # NaN compares False

    def best_with_strength(self, ev: np.ndarray, strength: np.ndarray, lab: str, cut: float) -> np.ndarray:
        """A rule's choice at one cut: the best EV among the offers whose strength clears it."""
        idx = self.idx[lab]
        idx = idx[(strength[idx] >= cut) & ~np.isnan(ev[idx])]
        if not len(idx):
            return idx
        order = np.lexsort((self.rank[idx], -ev[idx], self.gid[idx]))
        g = self.gid[idx][order]
        return idx[order[np.r_[True, g[1:] != g[:-1]]]]

    def roi(self, chosen: np.ndarray) -> float:
        c = chosen[self.choosing[chosen]]
        r = self.risk[c].sum()
        return float(self.units[c].sum() / r) if r > 0 else np.nan


@dataclass
class Model:
    """A family's numbers per key (a game, or a game and book). Run `perm`: each key keeps its own
    market number `base` and takes another key's disagreement `value - base`, read toward `orient`
    (+1 the home side, -1 the away side: F2's favourite)."""
    kind: str                       # "ml": logit of the home chance; "spread": the home margin's centre
    key: np.ndarray                 # per row: its key
    value: np.ndarray               # per key
    base: np.ndarray                # per key
    orient: np.ndarray              # per key
    groups: list                    # keys that may trade
    a_side: np.ndarray              # per row: home
    dec: np.ndarray                 # per row: decimal price
    t: np.ndarray                   # per row: the threshold (spreads)
    shape_groups: list              # (rows, ResidDist) (spreads)
    shared: tuple | None = None     # keyed by game and book: one shuffle of games, read by every book

    def values_at(self, perm: np.ndarray) -> np.ndarray:
        """A perm of -1: no such key to read from, so no opinion in this run."""
        moved = (self.orient * (self.value - self.base))[perm]
        return self.base + self.orient * np.where(perm < 0, np.nan, moved)

    def perm(self, seed: int) -> np.ndarray:
        if self.shared is None:
            return permute_within(self.groups, len(self.value), seed)
        game, book, dates, table = self.shared
        rng = np.random.default_rng(seed)
        moved = np.arange(table.shape[0])
        for ids in dates:
            moved[ids] = ids[rng.permutation(len(ids))]
        return table[moved[game], book]

    def ev(self, v: np.ndarray) -> np.ndarray:
        if self.kind == "ml":
            p = _expit(v)[self.key]
            pw = np.where(self.a_side, p, 1.0 - p)
            return pw * (self.dec - 1.0) - (1.0 - pw)
        mu = v[self.key]
        w, lose = np.full(len(mu), np.nan), np.full(len(mu), np.nan)
        push = np.zeros(len(mu))
        for rows, dist in self.shape_groups:
            w[rows], push[rows], lose[rows] = dist.probs(mu[rows], self.t[rows])
        pw = np.where(self.a_side, w, lose)
        return pw * (self.dec - 1.0) - (1.0 - pw - push)


def build_model(pool: pd.DataFrame, market: pd.DataFrame, key_cols, kind: str, orient: pd.Series | None = None,
                by_book: bool = False) -> Model:
    """`pool` carries the family's own mu / sigma or p_home; `market` the market's number per key
    (key_cols + mu or p_home). Built with merges, once. `by_book`: the keys are a game at a book, and
    a run shuffles the games of a date once, so every book reads the same other game (§10.1)."""
    key_cols = list(key_cols)
    group_cols = ("game_date",)
    keys = pool[list(dict.fromkeys(key_cols + list(group_cols)))].drop_duplicates(key_cols).reset_index(drop=True)
    keys["_k"] = np.arange(len(keys))
    row_key = pool[key_cols].merge(keys[key_cols + ["_k"]], on=key_cols, how="left")["_k"].to_numpy()
    col = "p_home" if kind == "ml" else "mu"
    first = pool.drop_duplicates(key_cols)[key_cols + [col]]
    x = keys.merge(first, on=key_cols, how="left", validate="one_to_one")
    y = x.merge(market[key_cols + [col]].drop_duplicates(key_cols).rename(columns={col: "_b"}),
                on=key_cols, how="left")
    conv = _logit if kind == "ml" else (lambda s: np.asarray(s, float))
    value, base = conv(y[col]), conv(y["_b"])
    value = np.where(np.isfinite(y[col].to_numpy(float)), value, np.nan)
    base = np.where(np.isfinite(y["_b"].to_numpy(float)), base, np.nan)
    finite = np.isfinite(value) & np.isfinite(base)
    o = np.ones(len(keys))
    if orient is not None:
        o = y["game_id"].map(orient).fillna(1.0).to_numpy(float)
    groups = [g[finite[g]] for _, g in sorted(y.groupby(list(group_cols), sort=True).indices.items())]
    groups = [g for g in groups if len(g)]
    t, shape_groups = np.zeros(len(pool)), []
    if kind == "spread":
        t = H.threshold(pool["market"], pool["line"])
        shape_groups = [(np.flatnonzero(m), dist) for m, dist, _ in H._groups(pool["sigma"].to_numpy(dtype=object))
                        if dist is not None]
    shared = None
    if by_book:
        game, games = pd.factorize(keys["game_id"])
        book, books = pd.factorize(keys["book"])
        table = np.full((len(games), len(books)), -1, int)
        table[game, book] = keys["_k"].to_numpy()
        shared = (game, book, [np.unique(game[g]) for g in groups], table)
    return Model(kind, row_key, value, base, o, groups, pool["side"].isin(["home", "over"]).to_numpy(),
                 np.asarray(H.dec(pool["price"]), float), np.asarray(t, float), shape_groups, shared)


def run_model(fast: Fast, model: Model, cuts, seed: int | None) -> dict:
    """{(label, cut_index): chosen rows} for one run; `seed` None: the real numbers."""
    n = len(model.value)
    perm = np.arange(n) if seed is None else model.perm(seed)
    ev = model.ev(model.values_at(perm))
    out = {}
    for lab in fast.idx:
        best = fast.best(ev, lab)
        for k, cut in enumerate(cuts):
            out[(lab, k)] = fast.at_cut(ev, best, cut)
    return out


@dataclass
class Gap:
    """A rule's strength per offer, moved among the offers on the same date, market and side
    (P2.off_number_placebo's rule and random stream). EV stays at the market's fair line."""
    strength: np.ndarray
    ev: np.ndarray
    groups: list


def build_gap(pool: pd.DataFrame) -> Gap:
    c = pool.reset_index(drop=True)
    groups = [idx for _, idx in sorted(c.groupby(["game_date", "market", "side"], sort=True).indices.items())]
    return Gap(c["strength"].to_numpy(float), c["ev"].to_numpy(float), groups)


def run_gap(fast: Fast, gap: Gap, cuts, seed: int | None) -> dict:
    s = gap.strength
    if seed is not None:
        s = gap.strength[permute_within(gap.groups, len(gap.strength), seed)]
    return {(lab, k): fast.best_with_strength(gap.ev, s, lab, cut)
            for lab in fast.idx for k, cut in enumerate(cuts)}


def fast_placebo(fast: Fast, spec, cuts, seeds=SEEDS) -> dict:
    """{(label, cut_index): [ROI per seed on the choosing seasons]}; NaN when a run bet nothing."""
    run = run_model if isinstance(spec, Model) else run_gap
    out = {(lab, k): [] for lab in fast.idx for k in range(len(cuts))}
    for s in seeds:
        for key, chosen in run(fast, spec, cuts, s).items():
            out[key].append(fast.roi(chosen))
    return out


def differ_shares(fast: Fast, spec, cuts, seeds) -> pd.DataFrame:
    """Per cut: the share of placebo bets that are not the real bets, by offer and by game on the
    same label. Counts only."""
    run = run_model if isinstance(spec, Model) else run_gap
    real = run(fast, spec, cuts, None)
    rows = []
    tot = {}
    for s in seeds:
        for key, chosen in run(fast, spec, cuts, s).items():
            r = real[key]
            t = tot.setdefault(key, [0, 0, 0])
            t[0] += len(chosen)
            t[1] += int((~np.isin(chosen, r)).sum())
            t[2] += int((~np.isin(fast.gid[chosen], fast.gid[r])).sum())
    for (lab, k), (n, d_offer, d_game) in tot.items():
        games = len(np.unique(fast.gid[fast.idx[lab]]))
        rows.append({"label": lab, "cut": cuts[k], "real_bets": int(len(real[(lab, k)])),
                     "placebo_bets_per_run": n / max(len(seeds), 1),
                     "differ_offer": d_offer / n if n else np.nan, "differ_game": d_game / n if n else np.nan,
                     # a shuffle with no tie to the real bets lands on a game the cell bets this often by
                     # chance alone, so a cell that bets most games cannot reach a high share
                     "differ_game_if_independent": 1.0 - len(real[(lab, k)]) / games if games else np.nan})
    return pd.DataFrame(rows)


def kept_own_share(spec, seeds) -> float:
    """The share of opinions (or of a rule's gaps) a run leaves on their own game or offer. If most
    candidates were alone on their date this would be near 1 and the placebo would repeat the bets."""
    idx = np.concatenate(spec.groups) if spec.groups else np.zeros(0, int)
    if not len(idx) or not seeds:
        return np.nan
    if isinstance(spec, Model):
        return float(np.mean([(spec.perm(s)[idx] == idx).mean() for s in seeds]))
    return float(np.mean([(permute_within(spec.groups, len(spec.strength), s)[idx] == idx).mean() for s in seeds]))


# ── one group of cells: the same cells, the two arms ────────────────────────

@dataclass
class Group:
    """One market at one decision point (and reference, for F2), the two arms' frames per label."""
    family: str
    point: str
    market: str
    labels: tuple
    cuts: tuple
    lowest: float
    strength: str
    times: pd.DataFrame
    line: dict                      # label -> candidate frame, line-size arm
    one: dict                       # label -> candidate frame, one-shape arm
    neutral_line: dict
    neutral_one: dict
    pool: pd.DataFrame
    masks: dict
    spec_args: dict
    axis: dict = field(default_factory=dict)

    def name(self) -> str:
        return " ".join(str(x) for x in (self.family, self.point, self.market, *self.axis.values()))


def _both(frame: pd.DataFrame, labels) -> dict:
    return {lab: frame for lab in labels}


def _side_masks(pool: pd.DataFrame, labels) -> dict:
    return {lab: (pool["side"] == lab).to_numpy() for lab in labels}


def f2_arm(vis: pd.DataFrame, off: pd.DataFrame, pr: Pricing, ref: str) -> dict:
    """F2 at one (point, reference) under one pricing: M.f2_point's frames, the reference priced
    through shaped_fair. Offers keep their real side; each label carries side_pick."""
    sp = vis[vis["market"] == "spreads"]
    sp = sp[sp["book"] == H.SHARP] if ref == "pinnacle" else sp[sp["book"].isin(H.BETTABLE)]
    f = shaped_fair(sp, pr)
    f = f[f["market"] == "spreads"][["game_id", "mu", "sigma"]].copy()
    if f.empty:
        f = f.assign(p_home=pd.Series([], dtype=float), posted=pd.Series([], dtype=float))
    else:
        f["p_home"] = M.p_home_from_margin(f["mu"], f["sigma"])
        f["posted"] = f["game_id"].map(M.posted_spread(sp)).astype(float)
    rf = f[np.isfinite(f["p_home"].to_numpy(float))].reset_index(drop=True)
    fav = M.favourite_home(rf)
    gids, fav_home = fav.index.to_numpy(), fav.to_numpy().astype(bool)
    p_home = rf.set_index("game_id").loc[gids, "p_home"].to_numpy(dtype=float)
    model = pd.DataFrame({"game_id": gids, "market": "h2h", "mu": np.nan, "sigma": np.nan, "p_home": p_home})
    picks = pd.DataFrame({"game_id": gids, "fav": np.where(fav_home, "home", "away"),
                          "dog": np.where(fav_home, "away", "home")})
    base = H.fair_offers(off, model)
    return {"base": base, "picks": picks, "fav_home": pd.Series(fav_home, index=gids)}


def _with_pick(x: pd.DataFrame, picks: pd.DataFrame, lab: str, how: str = "inner") -> pd.DataFrame:
    return x.merge(picks[["game_id", lab]].rename(columns={lab: "side_pick"}), on="game_id", how=how)


def f2_group(point: str, ref: str, times, vis, off, neutral0, mkt, line: Pricing, one: Pricing) -> Group:
    a, b = f2_arm(vis, off, line, ref), f2_arm(vis, off, one, ref)
    pool = a["base"].merge(a["picks"], on="game_id")
    masks = {lab: (pool["side"] == pool[lab]).to_numpy() for lab in F2_LABELS}
    orient = pd.Series(np.where(a["fav_home"].to_numpy(), 1.0, -1.0), index=a["fav_home"].index)
    return Group(FAM_F2, point, "h2h", F2_LABELS, EV_CUTS, LOWEST_EV_BAND, "ev", times,
                 {lab: _with_pick(a["base"], a["picks"], lab) for lab in F2_LABELS},
                 {lab: _with_pick(b["base"], b["picks"], lab) for lab in F2_LABELS},
                 {lab: _with_pick(neutral0, a["picks"], lab, "left") for lab in F2_LABELS},
                 {lab: _with_pick(neutral0, b["picks"], lab, "left") for lab in F2_LABELS},
                 pool, masks, {"market": mkt, "key_cols": ("game_id",), "kind": "ml", "orient": orient},
                 {"axis_ref": ref})


def own_book_fairs(vis: pd.DataFrame, pr: Pricing) -> dict:
    """M.own_book_ml_fair with the shape read from that book's own number at T."""
    out = {}
    for b in H.BETTABLE:
        sp = vis[(vis["book"] == b) & (vis["market"] == "spreads")]
        ml = vis[(vis["book"] == b) & (vis["market"] == "h2h")]
        same = set(sp.merge(ml[["game_id", "fetch_at"]], on=["game_id", "fetch_at"])["game_id"])
        sp = sp[sp["game_id"].isin(same)]
        if sp.empty:
            continue
        f = shaped_fair(sp, pr)
        f = f[f["market"] == "spreads"]
        p = M.p_home_from_margin(f["mu"], f["sigma"])
        fr = pd.DataFrame({"game_id": f["game_id"].to_numpy(), "market": "h2h", "mu": np.nan,
                           "sigma": np.nan, "p_home": p})
        out[b] = fr[np.isfinite(fr["p_home"])].reset_index(drop=True)
    return out


def own_book_ml(vis: pd.DataFrame) -> pd.DataFrame:
    """(game_id, book, p_home): each deciding book's own moneyline, no-vig, at T."""
    ml = vis[(vis["market"] == "h2h") & vis["book"].isin(H.BETTABLE) & vis["coherent"]]
    return pd.DataFrame({"game_id": ml["game_id"].to_numpy(), "book": ml["book"].to_numpy(),
                         "p_home": no_vig_a(ml)}).drop_duplicates(["game_id", "book"])


def f6d_group(point: str, times, vis, off, neutral0, line: Pricing, one: Pricing) -> Group:
    empty = neutral0.iloc[0:0]
    a = M.price_own_book(off, own_book_fairs(vis, line), empty)
    b = M.price_own_book(off, own_book_fairs(vis, one), empty)
    return Group(FAM_F6D, point, "h2h", HOME_AWAY, F6D_CUTS, 0.0, "ev", times, _both(a, HOME_AWAY),
                 _both(b, HOME_AWAY), _both(neutral0, HOME_AWAY), _both(neutral0, HOME_AWAY), a,
                 _side_masks(a, HOME_AWAY),
                 {"market": own_book_ml(vis), "key_cols": ("game_id", "book"), "kind": "ml", "by_book": True})


def f1_groups(point: str, times, vis, off, proj, games, line: Pricing, one: Pricing,
              min_prior: int = MIN_PRIOR) -> list[Group]:
    """F1's spread and moneyline at one point. The market's number (consensus at T) names the size
    of the line; the projection's own error at this point is what is split."""
    c = P.consensus(vis)
    cons = c[c["market"] == "spreads"].set_index("game_id")["cons"].astype(float)
    dist = P.projection_dist(games, proj)
    shapes = own_error_shapes(proj, cons, games, min_prior=min_prior)
    fair_l, fair_o = own_fair(proj, dist, shapes, cons), own_fair(proj, dist, {}, cons)
    mkt_l, mkt_o = shaped_fair(vis, line), shaped_fair(vis, one)
    neu_l, neu_o = H.fair_offers(off, mkt_l), H.fair_offers(off, mkt_o)
    out = []
    for m in MARKETS:
        a = H.fair_offers(off[off["market"] == m], fair_l)
        b = H.fair_offers(off[off["market"] == m], fair_o)
        kind = "ml" if m == "h2h" else "spread"
        out.append(Group(FAM_F1, point, m, HOME_AWAY, EV_CUTS, LOWEST_EV_BAND, "ev", times, _both(a, HOME_AWAY),
                         _both(b, HOME_AWAY), _both(neu_l[neu_l["market"] == m], HOME_AWAY),
                         _both(neu_o[neu_o["market"] == m], HOME_AWAY), a, _side_masks(a, HOME_AWAY),
                         {"market": mkt_l[mkt_l["market"] == m], "key_cols": ("game_id",), "kind": kind}))
    return out


def p1_cand(off: pd.DataFrame, fair: pd.DataFrame, base: pd.DataFrame, games: pd.DataFrame, label: str,
            min_train: int) -> pd.DataFrame:
    rows = P1.model_rows(label, fair, base, games)
    # Above zero only on a neutral-site game's designated home team. Five rows of about 6,000 would
    # otherwise move all five such games of 2025-26 by 9 to 20 points (§10.1).
    rows["h_road_no"] = 0.0
    mv, _ = P1.walk_forward(rows, label, P1.FULL_GRADED, None, min_train=min_train)
    return H.fair_offers(off[off["market"] == label], P1.model_fair(fair, mv))


def p1_groups(point: str, times, vis, base, games, line: Pricing, one: Pricing,
              min_train: int = P1.MIN_TRAIN) -> tuple[Group, pd.DataFrame, pd.DataFrame]:
    """(S_P1's spread group, the moneyline candidates, their neutral frame). A moneyline's offset
    is the no-vig log-odds, so no shape reaches it: one run."""
    off = H.offers(vis)
    fair_l, fair_o = shaped_fair(vis, line), shaped_fair(vis, one)
    neu_l, neu_o = H.fair_offers(off, fair_l), H.fair_offers(off, fair_o)
    a = p1_cand(off, fair_l, base, games, "spreads", min_train)
    b = p1_cand(off, fair_o, base, games, "spreads", min_train)
    g = Group(FAM_P1, point, "spreads", HOME_AWAY, P1_CUTS, 0.0, "ev", times, _both(a, HOME_AWAY),
              _both(b, HOME_AWAY), _both(neu_l[neu_l["market"] == "spreads"], HOME_AWAY),
              _both(neu_o[neu_o["market"] == "spreads"], HOME_AWAY), a, _side_masks(a, HOME_AWAY),
              {"market": fair_l[fair_l["market"] == "spreads"], "key_cols": ("game_id",), "kind": "spread"})
    ml = p1_cand(off, fair_o, base, games, "h2h", min_train)
    return g, ml, neu_o[neu_o["market"] == "h2h"]


def p2_point(q_main, q_same, times, pr: Pricing, ledger=None) -> P2.Point:
    """P2.point_frames with the rule for unreadable numbers, priced through shaped_fair."""
    vm = clean(H.visible(q_main, times), ledger, f"P2 {pr.arm}")
    vs = clean(H.visible(q_same, times), None)
    fair = shaped_fair(vm, pr)
    return P2.Point(times=times, vis_main=vm, vis_same=vs, fair=fair, neutral=H.fair_offers(H.offers(vm), fair))


def p2_group(point: str, times, q_main, q_same, line: Pricing, one: Pricing, ledger=None
             ) -> tuple[Group, pd.DataFrame, pd.DataFrame]:
    """(S_P2's off-number spread group, the same-number candidates, their neutral frame)."""
    pl, po = p2_point(q_main, q_same, times, line, ledger), p2_point(q_main, q_same, times, one)
    a, b = P2.off_number_cand(pl), P2.off_number_cand(po)
    a = a[a["market"] == "spreads"].reset_index(drop=True)
    b = b[b["market"] == "spreads"].reset_index(drop=True)
    nl, no = pl.neutral[pl.neutral["market"] == "spreads"], po.neutral[po.neutral["market"] == "spreads"]
    g = Group(FAM_P2, point, "spreads", HOME_AWAY, GAP_CUTS, 0.0, "strength", times, _both(a, HOME_AWAY),
              _both(b, HOME_AWAY), _both(nl, HOME_AWAY), _both(no, HOME_AWAY), a, _side_masks(a, HOME_AWAY),
              {}, {"axis_rule": "off_number"})
    return g, P2.same_number_cand(pl), pl.neutral


def build_spec(g: Group):
    return build_gap(g.pool) if g.strength == "strength" else build_model(g.pool, **g.spec_args)


# ── the cells ───────────────────────────────────────────────────────────────

def placebo_seasons(dd: H.Data, g: Group, choose_seasons) -> tuple:
    """The seasons the cell's own choosing return reads: H.run_cells drops a season the decision point
    reaches on too few games (section 6.5), and the placebo return it is compared with must drop it too."""
    return H.gated_seasons(H.point_coverage(dd, g.point, g.times), choose_seasons, g.point)[0]


def run_group(dd: H.Data, g: Group, close, sig, games, arm: str = "line", seeds=SEEDS,
              choose_seasons=H.CHOOSE) -> list[dict]:
    """One group's cells under one arm through H.run_cells. The line arm carries its placebo runs
    (fast_placebo) and its bands. The one-shape twin carries neither: it is never judged."""
    rows = []
    family = g.family if arm == "line" else oneshape(g.family)
    cands, neutral = (g.line, g.neutral_line) if arm == "line" else (g.one, g.neutral_one)
    placebo = None
    if arm == "line":
        fast = Fast(g.pool, g.masks, games, placebo_seasons(dd, g, choose_seasons))
        placebo = fast_placebo(fast, build_spec(g), g.cuts, seeds)
    with bets_folder(family, g.axis):
        for lab in g.labels:
            part = H.run_cells(dd, family, g.point, cands[lab], neutral[lab], list(g.cuts), {g.market: [lab]},
                               close=close, sig=sig, placebo=None, strength=g.strength,
                               choose_seasons=choose_seasons, times=g.times)
            for r in part:
                k = r["cut_index"]
                r["placebo_rois"] = list(placebo[(lab, k)]) if placebo is not None else []
                r.update(g.axis)
                r["pricing_arm"] = arm
                if arm == "line":
                    bounds = G5.band_bounds(g.cuts, k, lowest=g.lowest)
                    pool = tuple(int(s) for s in str(r["pool_seasons"]).split(",") if s)
                    r.update(G5.band_columns(cands[lab], lab, g.strength, bounds, games, pool))
            rows += part
    return rows


class bets_folder:
    """Each family and axis writes its bets to its own folder under NBA_GAME2_BETS."""

    def __init__(self, family: str, axis: dict):
        self.sub = "_".join([family, *[str(v) for v in axis.values()]])

    def __enter__(self):
        self.base = os.environ.get(BETS_ENV)
        if self.base:
            os.environ[BETS_ENV] = str(Path(self.base) / self.sub)

    def __exit__(self, *exc):
        if self.base:
            os.environ[BETS_ENV] = self.base


def pick(c: pd.DataFrame, cut: float, lab: str, strength: str) -> pd.DataFrame:
    if strength == "ev":
        return H.choose(c, cut, sides=[lab])
    return H.choose(c[c[strength] >= cut], -np.inf, sides=[lab])


BET_KEY = ["game_id", "market", "side", "book", "line", "price"]


def compare_group(g: Group, games: pd.DataFrame | None) -> list[dict]:
    """The two arms bet for bet, per cell and per cut. With `games` None (--smoke): counts only, no
    grade. A SIDE FLIP is a game bet on one real side under the one shape and on the other under
    the line-size shape, at the same cut."""
    out = []
    for k, cut in enumerate(g.cuts):
        side_l, side_o = {}, {}
        for lab in g.labels:
            a, b = pick(g.line[lab], cut, lab, g.strength), pick(g.one[lab], cut, lab, g.strength)
            ka = a[BET_KEY].fillna({"line": 0.0}).merge(b[BET_KEY].fillna({"line": 0.0}), on=BET_KEY, how="inner")
            row = {"family": g.family, "point": g.point, "market": g.market, "side": lab, "cut_index": k,
                   "cut": cut, **g.axis, "n_line": len(a), "n_one": len(b), "n_same_bet": len(ka),
                   "n_games_only_line": len(set(a["game_id"]) - set(b["game_id"])),
                   "n_games_only_one": len(set(b["game_id"]) - set(a["game_id"])),
                   "n_games_other_offer": len(set(a["game_id"]) & set(b["game_id"])) - len(ka)}
            for side, gid in zip(a["side"], a["game_id"]):
                side_l.setdefault(gid, set()).add(side)
            for side, gid in zip(b["side"], b["game_id"]):
                side_o.setdefault(gid, set()).add(side)
            if games is not None:
                pooled = (*H.CHOOSE, H.CONFIRM)
                ga, gb = H.grade(a, games), H.grade(b, games)
                ga, gb = ga[ga["season"].isin(pooled)], gb[gb["season"].isin(pooled)]
                only_a = set(ga["game_id"]) - set(gb["game_id"])
                only_b = set(gb["game_id"]) - set(ga["game_id"])
                other = (set(ga["game_id"]) & set(gb["game_id"])) - set(ka["game_id"])
                row.update({"pool_seasons": ",".join(str(s) for s in pooled),
                            "units_only_line": float(ga.loc[ga["game_id"].isin(only_a), "units"].sum()),
                            "units_only_one": float(gb.loc[gb["game_id"].isin(only_b), "units"].sum()),
                            "units_other_offer_line": float(ga.loc[ga["game_id"].isin(other), "units"].sum()),
                            "units_other_offer_one": float(gb.loc[gb["game_id"].isin(other), "units"].sum()),
                            "units_line": float(ga["units"].sum()), "units_one": float(gb["units"].sum()),
                            "roi_line": H.roi(ga) if len(ga) else np.nan,
                            "roi_one": H.roi(gb) if len(gb) else np.nan})
            out.append(row)
        flip = [gid for gid, s in side_l.items() if gid in side_o and not (s & side_o[gid])]
        for r in out[-len(g.labels):]:
            r["n_side_flips_at_cut"] = len(flip)
    return out


def count_bets(g: Group) -> list[dict]:
    """Bets per cell and season under the line-size arm, at or above the floor, counted, not graded."""
    out = []
    for lab in g.labels:
        for k, cut in enumerate(g.cuts):
            b = pick(g.line[lab], cut, lab, g.strength)
            by = b["season"].value_counts().to_dict()
            out.append({"family": g.family, "point": g.point, "market": g.market, "label": lab, "cut": cut,
                        **{str(a): v for a, v in g.axis.items()},
                        **{f"bets_{s}": int(by.get(s, 0)) for s in SEASONS},
                        "bets_pooled": int(sum(by.get(s, 0) for s in (*H.CHOOSE, H.CONFIRM)))})
    return out


def groups_plan(groups: list[Group]) -> set:
    """The cells these groups will emit, in cell_plan's shape: checked in --smoke, before any run."""
    got = set()
    for g in groups:
        axis = g.axis.get("axis_ref") or g.axis.get("axis_rule") or ""
        for lab in g.labels:
            got |= {(g.family, g.point, g.market, lab, axis, k, c) for k, c in enumerate(g.cuts)}
    return got


def check_cells(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    got = set()
    for r in rows:
        axis = r.get("axis_ref") or r.get("axis_rule") or ""
        got.add((r["family"], r["point"], r["market"], r["side"], axis, r["cut_index"], r["cut"]))
    assert got == set(cell_plan()), (len(got), len(cell_plan()))
    assert len(df) == EXPECTED_CELLS, len(df)
    return df


# ── real data ───────────────────────────────────────────────────────────────

def load_real(cache: Path, require: bool) -> H.Data:
    data = H.load(cache, seasons=list(SEASONS), require_seasons=SEASONS if require else None)
    data.quotes = data.quotes[data.quotes["market"].isin(MARKETS)].reset_index(drop=True)
    return data


def scrambled(games: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """Made-up scores for the timing passes of --smoke, so nothing there can read a real result."""
    rng = np.random.default_rng(seed)
    return games.assign(home_score=rng.integers(80, 140, len(games)).astype(float),
                        away_score=rng.integers(80, 140, len(games)).astype(float))


def _log(msg: str) -> None:
    print(msg, flush=True)


def reports_without_refined_p() -> None:
    """H.p_one_sided recomputes any p under 0.01 with 400,000 resamples, for the first search's
    multiple-testing bar. Section 9.1's bars read the pooled interval and never a p, so here a p stays
    at the 4,000 resamples of every other number. Timed on scrambled scores no p comes under 0.01, so a
    real run with many such cells would otherwise run for hours past its projection."""
    H.P_REFINE_BELOW = 0.0


def frame_matches(frame: pd.DataFrame, times: pd.DataFrame) -> bool:
    """A saved projection belongs to this point only if every game in it was projected at the time
    this run decides that game. Anything else is another run's frame."""
    x = frame[["game_id", "T"]].merge(times[["game_id", "T"]], on="game_id", how="left", suffixes=("", "_now"))
    return len(x) == len(frame) and bool((x["T"] == x["T_now"]).all())


def projections(data: H.Data, cache: Path, points, work: Path | None) -> dict:
    """The second search's projection at every decision time. Reads each point's frame from `work`
    when it is there, else builds the engine once, and writes the frames there when named."""
    out, need = {}, []
    for p in points:
        f = work / f"proj_{p}.parquet" if work else None
        frame = pd.read_parquet(f) if f is not None and f.exists() else None
        if frame is not None and frame_matches(frame, H.decision_times(data.fetches, data.games, p)):
            out[p] = frame
            _log(f"projection {p}: read {len(frame):,} rows from {f}")
        else:
            if frame is not None:
                _log(f"projection {p}: {f} was made at other decision times, rebuilding it")
            need.append(p)
    if need:
        t0 = time.time()
        w = P.load_world(cache, max_season=H.CONFIRM)
        _, st, models, _, _ = P.run_projection_setup(w, H.CONFIRM, log=_log)
        _log(f"projection engine rebuilt ({time.time() - t0:.0f}s)")
        for p in need:
            t = H.decision_times(data.fetches, data.games, p)
            pr = P1.project_at(w, st, models, data.games, t)
            keep = [c for c in pr.columns if pr[c].dtype != object or c == "game_id"]
            out[p] = pr[keep]
            if work is not None:
                work.mkdir(parents=True, exist_ok=True)
                out[p].to_parquet(work / f"proj_{p}.parquet")
            _log(f"projection {p}: {len(pr):,} rows ({time.time() - t0:.0f}s)")
    return out


def p1_inputs(data: H.Data, cache: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    sched_in, box = P1.load_inputs(cache)
    return P1.luck_inputs(data.games, L.team_box(box, data.games)), sched_in


def groups_at(point: str, data: H.Data, close, line: Pricing, one: Pricing, proj: pd.DataFrame, base: pd.DataFrame,
              q_main, q_same, ledger: list, min_prior: int = MIN_PRIOR,
              min_train: int = P1.MIN_TRAIN) -> tuple[list[Group], dict]:
    """Every registered group at one decision point, and the control frames there. `proj`: the
    projection at this point; `base`: P1's inputs at this point (P1.base_inputs)."""
    t = H.decision_times(data.fetches, data.games, point)
    vis = clean(H.visible(data.quotes, t), ledger, "plain")
    off = H.offers(vis)
    off_ml = off[off["market"] == "h2h"]
    mkt = H.market_fair(vis[vis["market"] == "h2h"], line.sig)
    neutral0 = H.fair_offers(off_ml, mkt)
    groups = [f2_group(point, ref, t, vis, off_ml, neutral0, mkt, line, one) for ref in F2_REFS]
    if point in POINTS_F6D:
        groups.append(f6d_group(point, t, vis, off_ml, neutral0, line, one))
    groups += f1_groups(point, t, vis, off, proj, data.games, line, one, min_prior)
    extra = {"times": t, "vis": vis}
    if point in POINTS_P1:
        vn = clean(visible_numbers(data.quotes, t), ledger, "P1")
        g, ml, nml = p1_groups(point, t, vn, base, data.games, line, one, min_train)
        groups.append(g)
        extra["p1_ml"] = (ml, nml)
    g, same, nsame = p2_group(point, t, q_main, q_same, line, one, ledger)
    groups.append(g)
    extra["p2_same"] = (same, nsame)
    return groups, extra


def slim(data: H.Data, market: str, times: pd.DataFrame) -> H.Data:
    """The data H.run_cells needs for one group. It reads the quotes for one report only, whether a
    bet was still offered at the next fetch (H.next_fetch_check), so it is handed that fetch's
    quotes, once, instead of re-reading 880,000 rows per cell. A test holds the report unchanged."""
    f = data.fetches[data.fetches["lead_min"] >= 0][["game_id", "fetch_at"]]
    nxt = times[["game_id", "T"]].merge(f, on="game_id")
    nxt = nxt[nxt["fetch_at"] > nxt["T"]].sort_values("fetch_at").drop_duplicates("game_id", keep="first")
    q = data.quotes[data.quotes["market"] == market]
    vis = H.visible(q, nxt[["game_id", "fetch_at"]].rename(columns={"fetch_at": "T"}))
    return H.Data(games=data.games, quotes=vis.drop(columns="T"), fetches=data.fetches)


def control_cells(data: H.Data, point: str, extra: dict, close, sig) -> list[dict]:
    """P2's same-number cells and P1's moneylines: no shape reaches their bets. Graded once."""
    rows = []
    same, nsame = extra["p2_same"]
    with bets_folder(CONTROL_SAME, {}):
        for m in MARKETS:
            part = H.run_cells(slim(data, m, extra["times"]), CONTROL_SAME, point, same[same["market"] == m],
                               nsame[nsame["market"] == m], list(SAME_CUTS), {m: list(HOME_AWAY)}, close=close,
                               sig=sig, placebo=None, strength="ev", times=extra["times"])
            for r in part:
                r.update({"axis_rule": "same_number", "placebo_rois": [], "pricing_arm": "none"})
            rows += part
    if "p1_ml" in extra:
        ml, nml = extra["p1_ml"]
        with bets_folder(CONTROL_ML, {}):
            part = H.run_cells(slim(data, "h2h", extra["times"]), CONTROL_ML, point, ml, nml, list(P1_CUTS), {"h2h": list(HOME_AWAY)},
                               close=close, sig=sig, placebo=None, strength="ev", times=extra["times"])
        for r in part:
            r.update({"placebo_rois": [], "pricing_arm": "none"})
        rows += part
    return rows


def write_rows(rows: list[dict], out: Path) -> None:
    for fam, part in pd.DataFrame(rows).groupby("family", sort=False):
        L.write_cells(part.to_dict("records"), out / f"cells_{fam}.parquet")


def refuse_full(cache: Path, env=os.environ) -> list[str]:
    """The cheap refusals before anything heavy: the go flag, the folders, the files, and a results
    folder already holding another search's cells (the verdict reads every cells_*.parquet)."""
    why = []
    if env.get(GO_ENV) != "1":
        why.append(f"{GO_ENV}=1 is not set: the owner runs --full")
    if not env.get(RESULTS_ENV):
        why.append(f"{RESULTS_ENV} is not set: name this search's own results folder")
    if not env.get(BETS_ENV):
        why.append(f"{BETS_ENV} is not set: a passing cell's figures read its bets")
    if not (Path(cache) / P.LEDGER_FILE).exists():
        why.append(f"{Path(cache) / P.LEDGER_FILE} does not exist: refresh the cache")
    if not (Path(cache) / P.STINTS_FILE).exists():
        why.append(f"{Path(cache) / P.STINTS_FILE} does not exist: the projection reads lineup segments")
    if env.get(RESULTS_ENV):
        names = [f.name for f in Path(env[RESULTS_ENV]).glob("cells_*.parquet")
                 if not f.name.startswith(("cells_S_", "cells_control_S_"))]
        if names:
            why.append(f"{env[RESULTS_ENV]} already holds another search's cells: {names[:3]}")
    return why


def full(cache: Path = H.CACHE) -> None:
    why = refuse_full(cache)
    if why:
        P.refuse(why)
    sys.stdout.reconfigure(line_buffering=True)
    out = Path(os.environ[RESULTS_ENV])
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    reports_without_refined_p()
    synthetic_checks(run_cells=False)
    try:
        data = load_real(cache, require=True)
    except RuntimeError as e:
        P.refuse([str(e)])
    short = P.stints_short(cache)
    if short:
        P.refuse([f"lineup segments on too few games in {short}"])
    _log(f"loaded {len(data.quotes):,} spread and moneyline rows ({time.time() - t0:.0f}s)")
    close, dropped = clean_close(data)
    line, one = build_pricing(close, data.games)
    _log(f"shapes built; {len(dropped)} closes dropped by the rule ({time.time() - t0:.0f}s)")
    proj = projections(data, cache, POINTS_ALL, Path(os.environ[PROJ_ENV]) if os.environ.get(PROJ_ENV) else None)
    luck, sched_in = p1_inputs(data, cache)
    q_main, q_same = main_rungs(data.quotes), P2.rungs_at_pinnacle(data.quotes)
    games = data.games
    rows, controls, twins, compare, ledger = [], [], [], [], []
    done, total = 0, EXPECTED_CELLS
    for p in POINTS_ALL:
        base = P1.base_inputs(proj[p], luck, sched_in)
        groups, extra = groups_at(p, data, close, line, one, proj[p], base, q_main, q_same, ledger)
        _log(f"point {p}: {len(groups)} groups built ({time.time() - t0:.0f}s)")
        for g in groups:
            dd = slim(data, g.market, g.times)
            rows += run_group(dd, g, close, line.sig, games, "line")
            twins += run_group(dd, g, close, line.sig, games, "one")
            compare += compare_group(g, games)
            done += sum(len(g.cuts) for _ in g.labels)
            el = time.time() - t0
            _log(f"{g.name()}: {done}/{total} cells, {el:.0f}s, about {el / done * (total - done):.0f}s left")
            write_rows(rows + twins, out)
        controls += control_cells(data, p, extra, close, line.sig)
        write_rows(controls, out)
        _log(f"point {p}: controls written ({time.time() - t0:.0f}s)")
    pd.DataFrame(compare).to_parquet(out / "compare_S.parquet")
    if ledger:
        pd.concat(ledger, ignore_index=True).to_parquet(out / "dropped_quotes_S.parquet")
    dropped.drop(columns=["close_at"], errors="ignore").to_parquet(out / "dropped_closes_S.parquet")
    check_cells(rows)
    _log(f"cells written to {out}: {len(rows)} registered, {len(twins)} one-shape twins, "
         f"{len(controls)} controls ({time.time() - t0:.0f}s)")


# ── synthetic world: three sizes of line, every bad number the rule names ───

def _american(p: float) -> float:
    return float(round(-100.0 * p / (1.0 - p)) if p >= 0.5 else round(100.0 * (1.0 - p) / p))


def _phi(z) -> float:
    return 0.5 * (1.0 + np.tanh(z * 0.9))              # a rough normal CDF, for made-up prices


def synthetic_world(seed: int = 11, seasons=SEASONS, per_season: int = 240, per_date: int = 8) -> dict:
    """Priced, played, made-up games at every decision point. Lines come in all three sizes and
    every 37th is level. Big favourites' results have a thin underdog tail, which one pooled shape
    cannot show. Bad numbers are planted: a sign-flipped book, a stale Pinnacle spread and moneyline."""
    rng = np.random.default_rng(seed)
    games, quotes, base = [], [], []
    books = ("pinnacle", "draftkings", "fanduel", "betmgm", "betrivers")
    for s in seasons:
        for i in range(per_season):
            day = pd.Timestamp(f"{s - 1}-11-01") + pd.Timedelta(days=i // per_date)
            tip = (day + pd.Timedelta(hours=24)).tz_localize("UTC")      # 00:00Z, 15Z the morning before
            gid = f"SYN{s}_{i:04d}"
            bucket = i % 3
            size = round({0: rng.uniform(0.5, 4.5), 1: rng.uniform(5.5, 9.5), 2: rng.uniform(10.5, 16.0)}[bucket] * 2) / 2
            home_fav = rng.random() < 0.6
            line = 0.0 if i % 37 == 0 else (-size if home_fav else size)
            if bucket == 2:
                r = abs(rng.normal(0, 16.0)) if rng.random() < 0.5 else -abs(rng.normal(0, 9.0))
            else:
                r = rng.normal(0, 12.0)
            margin = -line + (r if line <= 0 else -r)
            margin = int(np.round(margin)) or 1
            away = 108
            games.append({"game_id": gid, "season": s, "game_date": day.strftime("%Y-%m-%d"), "tip": tip,
                          "home_team": "HOM", "away_team": "AWY", "home_score": float(away + margin),
                          "away_score": float(away)})
            ph = float(np.clip(_phi(-line / 12.0), 0.03, 0.97))
            for lead in (540, 240, 120, 60, 20):
                f = tip - pd.Timedelta(minutes=lead)
                for book in books:
                    b = {"game_id": gid, "season": s, "game_date": games[-1]["game_date"], "tip": tip, "book": book,
                         "fetch_at": f, "snapshot_at": f - pd.Timedelta(minutes=5)}
                    shift = float(rng.choice([0.0, 0.0, 0.0, 0.5, -0.5])) if book != "pinnacle" else 0.0
                    n = line + shift
                    pa, pb = float(rng.choice([-105, -108, -110, -112])), float(rng.choice([-105, -108, -110, -112]))
                    if book == "fanduel" and i % 50 == 1:
                        n = -n if abs(n) > 3 else n + 7.0                # the sign-flipped book
                    if book == "pinnacle" and i % 60 == 2:
                        n = n + 5.0                                       # a Pinnacle number left behind
                    q = ph + rng.normal(0, 0.012)
                    if book == "pinnacle" and i % 70 == 3:
                        q = ph + 0.15                                     # a stale moneyline
                    q = float(np.clip(q, 0.03, 0.97))
                    quotes += [{**b, "market": "spreads", "line": n, "price_a": pa, "price_b": pb},
                               {**b, "market": "h2h", "line": np.nan, "price_a": _american(min(q + 0.015, 0.98)),
                                "price_b": _american(min(1.0 - q + 0.015, 0.98))}]
            base.append({"game_id": gid, "season": s, "margin": -line + rng.normal(0, 6.0),
                         "total": 224.0 + rng.normal(0, 6.0), "pace_h": rng.normal(99, 2), "pace_a": rng.normal(99, 2),
                         "gap_margin": rng.normal(0, 1), "gap_total": rng.normal(0, 1),
                         "altitude": float(rng.random() < 0.1), "h_game_no": 11.0, "a_game_no": 11.0})
    g = pd.DataFrame(games)
    q = pd.DataFrame(quotes)
    s_ = H.imp(q["price_a"]) + H.imp(q["price_b"])
    q["coherent"] = (s_ >= H.COHERENT[0]) & (s_ <= H.COHERENT[1])
    f = q[["game_id", "tip", "fetch_at"]].drop_duplicates(["game_id", "fetch_at"])
    f = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60.0)
    b = pd.DataFrame(base)
    for fx in P1.F5:
        b[f"{fx}_h"], b[f"{fx}_a"] = rng.random(len(b)), rng.random(len(b))
    for side in ("h", "a"):
        for k in P1.SCHED:
            b[f"{side}_{k}"] = rng.random(len(b))
    return {"data": H.Data(games=g, quotes=q, fetches=f.reset_index(drop=True)), "base": b}


def synthetic_groups(world: dict, points=("C",), min_prior: int = 60, min_train: int = 20) -> dict:
    """Every family's frames at `points` on the synthetic world, by the code --full runs."""
    data, base = world["data"], world["base"]
    close, dropped = clean_close(data)
    line, one = build_pricing(close, data.games, min_prior=min_prior)
    q_main, q_same = main_rungs(data.quotes), P2.rungs_at_pinnacle(data.quotes)
    groups, ledger, extras = [], [], {}
    proj = base[["game_id", "season", "margin", "total"]]
    for p in points:
        g, extras[p] = groups_at(p, data, close, line, one, proj, base, q_main, q_same, ledger,
                                 min_prior=min_prior, min_train=min_train)
        groups += g
    return {"close": close, "dropped": dropped, "line": line, "one": one, "groups": groups, "extras": extras,
            "ledger": ledger, "q_main": q_main, "q_same": q_same}


def underdog_gap(vis: pd.DataFrame, line: Pricing, one: Pricing, min_season: int = 2023) -> dict:
    """The underdog's outright chance from Pinnacle's spread, under each arm, on games with a line
    over 10 from `min_season` on (read at the number each game's shape is chosen by)."""
    off = H.offers(vis)
    off = off[off["market"] == "h2h"]
    a, b = f2_arm(vis, off, line, "pinnacle"), f2_arm(vis, off, one, "pinnacle")
    posted = M.posted_spread(vis[(vis["market"] == "spreads") & (vis["book"] == H.SHARP)])
    def dog(x):
        p = x["base"].drop_duplicates("game_id").set_index("game_id")["p_home"]
        fav = x["fav_home"].reindex(p.index)
        return pd.Series(np.where(fav.to_numpy(bool), 1.0 - p.to_numpy(float), p.to_numpy(float)), index=p.index)
    d = pd.DataFrame({"line": dog(a), "one": dog(b)}).dropna()
    season = vis.drop_duplicates("game_id").set_index("game_id")["season"]
    big = d.index[(posted.reindex(d.index).abs() > A.SPREAD_BUCKETS[1]) & (season.reindex(d.index) >= min_season)]
    return {"games": len(big), "line_mean": float(d.loc[big, "line"].mean()), "one_mean": float(d.loc[big, "one"].mean())}


def synthetic_checks(run_cells: bool = True, world: dict | None = None, built: dict | None = None) -> dict:
    """Plumbing on made-up games; raises on a fault. Run first by --smoke and --full, on a 0.05-point
    table in place of 0.01: the same arithmetic, five times faster, and no real number is priced here."""
    step = H.ResidDist.STEP
    H.ResidDist.STEP = 0.05
    try:
        return _synthetic_checks(run_cells, world, built)
    finally:
        H.ResidDist.STEP = step


def _synthetic_checks(run_cells: bool, world: dict | None, built: dict | None) -> dict:
    H.check()
    world = synthetic_world() if world is None else world
    data = world["data"]
    assert set(data.quotes["market"]) == set(MARKETS), "the synthetic world must hold both markets"
    s = synthetic_groups(world) if built is None else built
    assert len(s["ledger"]) > 0, "the synthetic world's bad numbers were not dropped"
    # the big-line shape must exist, or nothing below tests it
    keys = s["line"].shapes["spreads"]
    assert all((S, 2, True) in keys and (S, 2, False) in keys for S in (2023, 2024, 2025, 2026))
    # the mechanism: on big lines the line-size arm gives the underdog less chance than one shape
    gap = underdog_gap(s["extras"]["C"]["vis"], s["line"], s["one"])
    assert gap["games"] > 50 and gap["line_mean"] < gap["one_mean"] - 0.01, gap
    # the one-shape arm is the original pricing, number for number
    t = s["extras"]["C"]["times"]
    vis = s["extras"]["C"]["vis"]
    a, b = shaped_fair(vis, s["one"]), H.market_fair(vis, s["one"].sig)
    x = a.merge(b, on=["game_id", "market"], suffixes=("", "_h"))
    assert len(x) == len(b) and np.nanmax(np.abs(x["mu"].to_numpy(float) - x["mu_h"].to_numpy(float))) < 1e-9
    assert len(t) > 0
    # every group: the fast chooser picks the harness's bets, and the identity repeats them
    for g in s["groups"]:
        fast = Fast(g.pool, g.masks, data.games, H.CHOOSE)
        spec = build_spec(g)
        real = (run_model if isinstance(spec, Model) else run_gap)(fast, spec, g.cuts, None)
        for lab in g.labels:
            for k, cut in enumerate(g.cuts):
                h = pick(g.line[lab], cut, lab, g.strength)
                got = g.pool.iloc[real[(lab, k)]]
                assert set(zip(h["game_id"], h["book"], h["side"])) == set(zip(got["game_id"], got["book"], got["side"])), (
                    g.name(), lab, cut)
    out = {"synthetic_checks": "pass", "groups": len(s["groups"])}
    if run_cells:
        g = next(x for x in s["groups"] if x.family == FAM_P2)
        rows = run_group(slim(data, g.market, g.times), g, s["close"], s["line"].sig, data.games, "line", seeds=(1, 2))
        assert len(rows) == len(g.labels) * len(g.cuts) and all(len(r["placebo_rois"]) == 2 for r in rows)
        assert all("band0_n" in r for r in rows)
        out["cells"] = len(rows)
    return out


# ── smoke: everything but a grade ───────────────────────────────────────────

def smoke(cache: Path = H.CACHE) -> dict:
    sys.stdout.reconfigure(line_buffering=True)
    t0 = time.time()
    stage: dict = {}
    reports_without_refined_p()
    print(json.dumps(synthetic_checks()), flush=True)
    stage["synthetic_checks_s"] = time.time() - t0
    t1 = time.time()
    data = load_real(cache, require=True)
    fake = scrambled(data.games)
    stage["load_s"] = time.time() - t1
    report: dict = {"seasons": data.notes.get("games_priced_share")}
    _log(f"loaded {len(data.quotes):,} spread and moneyline rows ({time.time() - t0:.0f}s)")
    t1 = time.time()
    close, dropped = clean_close(data)
    line, one = build_pricing(close, data.games)
    stage["shapes_s"] = time.time() - t1
    _log(f"shapes built ({time.time() - t0:.0f}s); closes dropped by the rule: "
         f"{dropped.groupby(['season', 'market']).size().to_dict()}")
    shape_coverage(close, data, line)
    t1 = time.time()
    proj = projections(data, cache, POINTS_ALL, Path(os.environ[PROJ_ENV]) if os.environ.get(PROJ_ENV) else None)
    stage["projection_s"] = time.time() - t1
    t1 = time.time()
    luck, sched_in = p1_inputs(data, cache)
    q_main, q_same = main_rungs(data.quotes), P2.rungs_at_pinnacle(data.quotes)
    stage["inputs_s"] = time.time() - t1
    stage["groups_s"], controls_s, plan = 0.0, np.nan, set()
    ledger, counts, compare, shares, tops, timing, reads, whole = [], [], [], [], [], [], [], []
    for p in POINTS_ALL:
        t1 = time.time()
        base = P1.base_inputs(proj[p], luck, sched_in)
        groups, extra = groups_at(p, data, close, line, one, proj[p], base, q_main, q_same, ledger)
        stage["groups_s"] += time.time() - t1
        plan |= groups_plan(groups)
        reads.append(extra["vis"])
        cov = H.point_coverage(data, p, extra["times"])
        _log(f"point {p}: share of each season's games decided here {({k: round(v, 3) for k, v in cov.items()})}; "
             f"choosing seasons dropped for too few games {H.gated_seasons(cov, H.CHOOSE, p)[1]}")
        _log(f"point {p}: {len(groups)} groups built ({time.time() - t0:.0f}s)")
        for g in groups:
            got = smoke_group(g, data, fake, close, line.sig)
            counts += got["counts"]
            compare += got["compare"]
            shares.append(got["shares"])
            timing.append(got["timing"])
            tops.append(got["top"])
            _log(f"  {g.name()}: {len(g.pool):,} offers, one placebo run {got['timing']['one_run_s']:.3f}s "
                 f"({time.time() - t0:.0f}s)")
            if p == TIMED_POINT and (g.family, g.market) not in {(w["family"], w["market"]) for w in whole}:
                whole.append(time_group(data, g, close, line.sig, fake))
                _log(f"  timed whole: {whole[-1]} ({time.time() - t0:.0f}s)")
        if p == TIMED_POINT:
            controls_s = time_controls(data, p, extra, close, line.sig, fake)
            _log(f"  timed the {CONTROLS_AT_TIMED_POINT} controls at {p}: {controls_s:.1f}s ({time.time() - t0:.0f}s)")
    assert plan == set(cell_plan()), (len(plan), len(cell_plan()))
    print(f"\nthe groups built emit the registered cells: {len(plan)}")
    print_extremes(pd.concat(reads, ignore_index=True), ledger)
    print("\nHIGHEST-EV OFFERS UNDER THE LINE-SIZE ARM")
    top = pd.concat(tops, ignore_index=True)
    for fam, x in top.groupby(top["group"].str.split().str[0]):
        print(fam)
        print(x.sort_values("ev", ascending=False).drop_duplicates(["game_id", "book", "side"]).head(10).to_string(index=False))
    sh = pd.concat(shares, ignore_index=True)
    print("\nSHARE OF PLACEBO BETS THAT ARE NOT THE REAL BETS (seeds 1-5)")
    print("differ_game_if_independent: the share a shuffle with no tie to the real bets would show, because a")
    print("cell that bets half its games lands on one of them half the time by chance")
    wt = sh.assign(w=sh["placebo_bets_per_run"], o=sh["differ_offer"] * sh["placebo_bets_per_run"],
                   g=sh["differ_game"] * sh["placebo_bets_per_run"],
                   i=sh["differ_game_if_independent"] * sh["placebo_bets_per_run"])
    tab = wt.groupby(["family", "cut"]).agg(real_bets=("real_bets", "sum"), placebo_bets_per_run=("w", "sum"),
                                            o=("o", "sum"), g=("g", "sum"), i=("i", "sum")).reset_index()
    w_ = tab["placebo_bets_per_run"]
    tab["differ_offer"], tab["differ_game"], tab["differ_game_if_independent"] = tab["o"] / w_, tab["g"] / w_, tab["i"] / w_
    print(tab.drop(columns=["o", "g", "i"]).round(3).to_string(index=False))
    fam = wt.groupby("family").agg(w=("w", "sum"), o=("o", "sum"), g=("g", "sum"), i=("i", "sum"))
    print("by family, by game:", (fam["g"] / fam["w"]).round(3).to_dict(), "by offer:", (fam["o"] / fam["w"]).round(3).to_dict(),
          "if independent:", (fam["i"] / fam["w"]).round(3).to_dict())
    print("share of opinions a run leaves on their own game:",
          pd.DataFrame(timing).groupby("family")["kept_own"].mean().round(3).to_dict())
    print("\nCOUNTS BEFORE GRADING: bets per cell and season, line-size arm")
    cdf = pd.DataFrame(counts)
    print(cdf.to_string(index=False))
    print("\nTHE TWO ARMS, BET FOR BET, NO RESULT READ")
    cmp_ = pd.DataFrame(compare)
    print(cmp_.groupby(["family", "cut"])[["n_line", "n_one", "n_same_bet", "n_games_only_line", "n_games_only_one",
                                           "n_games_other_offer"]].sum().to_string())
    first = cmp_[cmp_["side"].isin(["fav", "home"])]
    print("games whose real side flips, summed over cuts:", first.groupby("family")["n_side_flips_at_cut"].sum().to_dict())
    tdf = pd.DataFrame(timing)
    wdf = pd.DataFrame(whole)
    print("\nTIMING (scrambled scores)")
    print(tdf.to_string(index=False))
    print(wdf.to_string(index=False))
    got = projected_full(stage, tdf, wdf, controls_s)
    got.update({"peak_memory_gb": peak_gb(), "smoke_s": round(time.time() - t0, 1)})
    print(json.dumps(got, indent=1))
    report.update({"cells": len(cdf)})
    return report


def projected_full(stage: dict, per_group: pd.DataFrame, whole: pd.DataFrame, controls_s: float) -> dict:
    """--full's seconds from what this run measured, on this machine at this load. Each group's cells
    take their family and market's measured seconds per cell. Everything --full does is here except
    writing the parquet files, and rebuilding the projection if its saved frames are gone."""
    x = per_group.merge(whole.drop(columns="cells"), on=["family", "market"], how="left")
    assert x["line_cell_s"].notna().all(), "a family and market was never timed"
    out = {k: round(float(v), 1) for k, v in stage.items()}
    out["placebo_run_all_groups_s"] = round(float(x["one_run_s"].sum()), 3)
    out["placebo_200_runs_s"] = round(float((x["one_run_s"] * N_PLACEBO + x["build_s"]).sum()), 1)
    out["registered_cells_s"] = round(float((x["line_cell_s"] * x["cells"]).sum()), 1)
    out["twins_s"] = round(float((x["one_cell_s"] * x["cells"]).sum()), 1)
    out["compare_s"] = round(float(x["compare_s"].sum()), 1)
    out["controls_s"] = round(float(controls_s) * len(control_plan()) / CONTROLS_AT_TIMED_POINT, 1)
    total = sum(float(stage[k]) for k in stage) + sum(out[k] for k in ("placebo_200_runs_s", "registered_cells_s",
                                                                        "twins_s", "compare_s", "controls_s"))
    out.update({"projected_full_s": round(total, 1), "projected_full_h": round(total / 3600.0, 2)})
    return out


def smoke_group(g: Group, data: H.Data, fake: pd.DataFrame, close, sig) -> dict:
    """One group's counts, placebo-differ shares and timings. `fake`: scrambled scores. Everything
    here that needs a result reads those, so no real bet is graded."""
    t1 = time.time()
    fast = Fast(g.pool, g.masks, fake, H.CHOOSE)
    spec = build_spec(g)
    t2 = time.time()
    fast_placebo(fast, spec, g.cuts, seeds=(1,))
    t3 = time.time()
    d = differ_shares(fast, spec, g.cuts, seeds=(1, 2, 3, 4, 5))
    d = d.assign(family=g.family, point=g.point, market=g.market, **g.axis)
    ok = g.pool["book"].isin(H.BETTABLE) & (g.pool["price"] >= H.PRICE_FLOOR)
    top = g.pool[ok].nlargest(6, "ev")[["game_id", "book", "side", "line", "price", "ev", "p_win"]]
    return {"counts": count_bets(g), "compare": compare_group(g, None), "shares": d,
            "top": top.assign(group=g.name()),
            "timing": {"group": g.name(), "family": g.family, "market": g.market, "cells": len(g.labels) * len(g.cuts),
                       "offers": len(g.pool), "build_s": round(t2 - t1, 3), "one_run_s": round(t3 - t2, 4),
                       "kept_own": kept_own_share(spec, (1, 2, 3, 4, 5))}}


class no_bets_written:
    """The timing passes grade scrambled scores: nothing of theirs belongs in a bets folder."""

    def __enter__(self):
        self.saved = os.environ.pop(BETS_ENV, None)

    def __exit__(self, *exc):
        if self.saved is not None:
            os.environ[BETS_ENV] = self.saved


def time_group(data: H.Data, g: Group, close, sig, fake: pd.DataFrame) -> dict:
    """Seconds per cell of a whole group through H.run_cells and its bands, under each arm, and its
    compare table, as --full runs them but with no placebo run (timed apart) and scrambled scores."""
    t0 = time.time()
    dd = slim(data, g.market, g.times)
    dd.games = fake
    with no_bets_written():
        t1 = time.time()
        run_group(dd, g, close, sig, fake, "line", seeds=())
        t2 = time.time()
        run_group(dd, g, close, sig, fake, "one", seeds=())
        t3 = time.time()
        compare_group(g, fake)
        t4 = time.time()
    n = len(g.labels) * len(g.cuts)
    return {"family": g.family, "market": g.market, "cells": n, "slim_s": round(t1 - t0, 1),
            "line_cell_s": round((t2 - t1) / n, 2), "one_cell_s": round((t3 - t2) / n, 2), "compare_s": round(t4 - t3, 1)}


def time_controls(data: H.Data, point: str, extra: dict, close, sig, fake: pd.DataFrame) -> float:
    """Seconds for the control cells at one point, scrambled scores."""
    dd = H.Data(games=fake, quotes=data.quotes, fetches=data.fetches)
    t = time.time()
    with no_bets_written():
        rows = control_cells(dd, point, extra, close, sig)
    assert len(rows) == CONTROLS_AT_TIMED_POINT, len(rows)
    return time.time() - t


def shape_coverage(close: pd.DataFrame, data: H.Data, line: Pricing) -> None:
    """Per season and size of line: earlier games the shape reads, whether it exists or the one shape
    prices those games, and how many games that is."""
    sp = close[close["market"] == "spreads"]
    b = A.spread_bucket(sp["close_line"])
    rows = []
    games = sp.assign(b=b).groupby(["season", "b"]).size()
    prior = games.groupby("b").cumsum() - games
    for (s, k), n in games.items():
        rows.append({"season": int(s), "line": ("5 or less", "5 to 10", "over 10")[int(k)], "games": int(n),
                     "earlier_games": int(prior.loc[(s, k)]),
                     "priced_by": "its own shape" if (int(s), int(k), True) in line.shapes["spreads"] else "the one shape"})
    print("\nSHAPE COVERAGE")
    print(pd.DataFrame(rows).to_string(index=False))


def print_extremes(vis: pd.DataFrame, ledger: list) -> None:
    v = vis[vis["book"].isin((H.SHARP, *H.BETTABLE))]
    print("\nEXTREMES OF EVERY LINE AND PRICE READ, AFTER THE RULE, EVERY DECISION POINT")
    for m in MARKETS:
        x = v[v["market"] == m]
        print(m, {"rows": len(x), "line_min": float(x["line"].min()), "line_max": float(x["line"].max()),
                  "price_a_min": float(x["price_a"].min()), "price_a_max": float(x["price_a"].max()),
                  "price_b_min": float(x["price_b"].min()), "price_b_max": float(x["price_b"].max())})
    if ledger:
        d = pd.concat(ledger, ignore_index=True)
        d = d[d["where"] == "plain"]
        print("quotes dropped by the rule (plain frames), by season, market and book")
        print(d.groupby(["season", "market", "book"]).size().unstack(fill_value=0).to_string())
        print(d.sort_values("season").head(12).to_string(index=False))


def peak_gb() -> float | str:
    try:
        import psutil
        m = psutil.Process().memory_info()
        return round(getattr(m, "peak_wset", m.rss) / 2 ** 30, 2)
    except ImportError:
        return "psutil not installed"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true", help="synthetic checks, then real counts only")
    g.add_argument("--full", action="store_true", help=f"every graded season (needs {GO_ENV}=1)")
    a = ap.parse_args(argv)
    if a.full:
        full(H.CACHE)
    else:
        print(json.dumps(smoke(H.CACHE), default=str))


if __name__ == "__main__":
    main()
