"""NBA search: moneyline favourites shorter than -200.

docs/nba_search_fav200.md registers the cells and fixes every choice, committed
BEFORE this lab and before any cell was graded. This lab EMITS cells through the
shared harness (scripts/nba_game_harness, H); the pass/fail script judges them
(scripts/nba_game2_verdict.py --house5, record 9.1's bars). The same-number rule
and the market-anchored model are the fourth search's own code, imported
(scripts/nba_game4_p2, P2; scripts/nba_game4_p1, P1).

40 cells (asserted), every judged bet on the market's favourite at the decision time:

  FAVB    the favourite at its best deciding price, no model, by price band:
          -300 <= price < -200, -500 <= price < -300, price < -500. No floor.
          A, B, C, D. 12 cells.
  FAVP2   the same-number rule (sharp_pairs): Pinnacle's proportional no-vig
          chance x the deciding book's decimal price - 1, EV >= 0 / .01 / .02 / .03,
          -1000 <= price < -200. A, B, C, D. 16 cells.
  FAVP1   the market-anchored model, EV >= .02 / .04 / .06 / .08, the same range.
          A, C, D. 12 cells.

  RANGE   read on the one offer the cell would take. A game with one book at -190
          and another at -205 is never bet at -205 (best_in_range).
  FLOOR   H.choose reads H.PRICE_FLOOR when called; price_floor() sets it around
          each family's cells, so blind_side, blind_pool and the band columns go
          through the same floor as the cell.
  BAD     a quote more than 0.15 of no-vig chance from the median of its own fetch
          (four or more books) is dropped, whichever book; a price between -100
          and +100 is dropped; the harness's coherent rule stays (bad_moneyline).
          A spread more than 3 points from its fetch's median is dropped
          (bad_spread, the spread control only).
  PLACEBO 200 runs, seeds 1-200: each game's signal moves to another game in the
          same pool in the same ISO week (block_perm), its price, favourite and
          result staying with the game. FAVB: "in this band", among every
          favourite. FAVP2: the best offer's EV. FAVP1: the model's move toward the
          favourite, re-priced at the game's own offers. Built one frame at a time
          from small arrays (G5.LazyFrames): 200 kept frames would not fit.
  CONTROLS never judged: control_FAVB_dog, control_FAVB_spread, control_FAVP2_power.

    PYTHONPATH=. python -m scripts.nba_s_fav200 --smoke
    NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> NBA_GAME2_BETS=<folder>/bets \
        PYTHONPATH=. python -m scripts.nba_s_fav200 --full
    PYTHONPATH=. python -m scripts.nba_game2_verdict --results <folder> --house5

--smoke runs the synthetic checks, then counts on the real cache. It computes no
result of any bet: every grade inside it reads scores replaced by random numbers,
and only_random_scores() raises if any grade is handed a real frame. Only the
model's fit reads real scores, of seasons before the one it scores.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import nba_game2_luck as L  # noqa: E402
from scripts import nba_game2_projection as P  # noqa: E402
from scripts import nba_game4_p1 as P1  # noqa: E402
from scripts import nba_game4_p2 as P2  # noqa: E402
from scripts import nba_game5 as G5  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402
from scripts.nba_game_market_lab import sharp_pairs  # noqa: E402

GO_ENV, RESULTS_ENV, BETS_ENV = "NBA_GAME2_GO", "NBA_GAME2_RESULTS", "NBA_GAME2_BETS"
MARKET, SPREADS = "h2h", "spreads"
SIDE, DOG = "favourite", "underdog"
FAVB, FAVP2, FAVP1 = "FAVB", "FAVP2", "FAVP1"
C_DOG, C_SPREAD, C_POWER = "control_FAVB_dog", "control_FAVB_spread", "control_FAVP2_power"
ALL = "all"

NO_FLOOR, RULE_FLOOR, OLD_EDGE = -1e9, -1000.0, -200.0
# every band is lo <= price < hi, so -200 is in no new band and -300 is in the first
BANDS = {"200_300": (-300.0, OLD_EDGE), "300_500": (-500.0, -300.0), "500_up": (NO_FLOOR, -500.0)}
BELOW = (OLD_EDGE, -150.0)
RULE_RANGE = (RULE_FLOOR, OLD_EDGE)
REPORT_BANDS = {"200_300": BANDS["200_300"], "300_500": BANDS["300_500"],
                "500_1000": (RULE_FLOOR, -500.0), "1000_up": (NO_FLOOR, RULE_FLOOR)}
# bar 5: the band just below the cell's own, its own, and every band to the top
BLIND_BOUNDS = {"200_300": [BELOW, BANDS["200_300"], BANDS["300_500"], BANDS["500_up"]],
                "300_500": [BANDS["200_300"], BANDS["300_500"], BANDS["500_up"]],
                "500_up": [BANDS["300_500"], BANDS["500_up"]]}
FLAG = 1.0                                     # a blind cell's cut: "in this band"
BLIND_POINTS, P2_POINTS, P1_POINTS = ("A", "B", "C", "D"), P2.FULL_POINTS, P1.FULL_POINTS
P2_CUTS, P1_CUTS = P2.CUTS["same_number"], P1.CUTS
P2_LOWEST, P1_LOWEST = -0.01, 0.0              # the lowest cut's lower band starts here
N_PLACEBO = 200
PLACEBO_SEEDS = tuple(range(1, N_PLACEBO + 1))
EXPECTED_CELLS, EXPECTED_CONTROLS = 40, 40
MAX_DEV, MIN_BOOKS, MAX_SPREAD_DEV, LONE_BEST = 0.15, 4, 3.0, 0.02
FULL_SEASONS = (H.REGIME, *H.CHOOSE, H.CONFIRM)   # 2020-21 .. 2025-26
GRADED = (*H.CHOOSE, H.CONFIRM)                   # 2021-22 .. 2025-26
DIFFER_SEEDS = tuple(range(1, 21))
BLINDED = "scores_are_random"


def log(msg: str, t0: float | None = None) -> None:
    print(msg + (f" ({time.time() - t0:.0f}s)" if t0 is not None else ""), flush=True)


# ── the cells ───────────────────────────────────────────────────────────────

def cell_specs() -> list[tuple]:
    """(family, point, band, cut_index, cut) for every judged cell."""
    out = [(FAVB, p, b, 0, FLAG) for p in BLIND_POINTS for b in BANDS]
    out += [(FAVP2, p, ALL, k, c) for p in P2_POINTS for k, c in enumerate(P2_CUTS)]
    out += [(FAVP1, p, ALL, k, c) for p in P1_POINTS for k, c in enumerate(P1_CUTS)]
    return out


def control_specs() -> list[tuple]:
    out = [(C_DOG, p, b, 0, FLAG) for p in BLIND_POINTS for b in BANDS]
    out += [(C_SPREAD, p, b, 0, FLAG) for p in BLIND_POINTS for b in BANDS]
    out += [(C_POWER, p, ALL, k, c) for p in P2_POINTS for k, c in enumerate(P2_CUTS)]
    return out


def check_rows(rows: list[dict], specs: list[tuple], what: str) -> None:
    got = sorted((r["family"], r["point"], r["axis_band"], int(r["cut_index"]), float(r["cut"])) for r in rows)
    want = sorted((f, p, b, int(k), float(c)) for f, p, b, k, c in specs)
    assert got == want, f"{what}: the cells emitted are not the cells registered"


# ── the floor ───────────────────────────────────────────────────────────────

@contextmanager
def price_floor(floor: float):
    """H.choose reads H.PRICE_FLOOR when it is called, so everything inside runs at
    this floor: the cell, blind_side, blind_pool and the band columns."""
    old = H.PRICE_FLOOR
    H.PRICE_FLOOR = float(floor)
    try:
        yield
    finally:
        H.PRICE_FLOOR = old


@contextmanager
def bets_dir(name: str):
    """One folder per family and band: a blind cell's rows carry only cut 1.0."""
    base = os.environ.get(BETS_ENV)
    if not base:
        yield
        return
    os.environ[BETS_ENV] = str(Path(base) / name)
    try:
        yield
    finally:
        os.environ[BETS_ENV] = base


# ── impossible numbers ──────────────────────────────────────────────────────

def no_vig_home(q: pd.DataFrame) -> pd.Series:
    ia, ib = H.imp(q["price_a"]), H.imp(q["price_b"])
    return pd.Series(ia / (ia + ib), index=q.index)


def bad_moneyline(q: pd.DataFrame) -> pd.Series:
    """True on a moneyline quote that cannot be a real number: not an American
    price, or more than MAX_DEV of no-vig chance from the median of its own fetch
    when MIN_BOOKS or more books quote the game there. Every book, Pinnacle too:
    Pinnacle sets the same-number rule's chance."""
    if q.empty:
        return pd.Series(np.zeros(0, bool), index=q.index)
    not_price = (q["price_a"].abs() < 100) | (q["price_b"].abs() < 100)
    fa = no_vig_home(q)
    grp = fa.groupby([q["game_id"], q["fetch_at"]], sort=False)
    far = (fa - grp.transform("median")).abs() > MAX_DEV
    return not_price | (far & (grp.transform("size") >= MIN_BOOKS))


def bad_spread(q: pd.DataFrame) -> pd.Series:
    """True on a spread more than MAX_SPREAD_DEV from its fetch's median number,
    MIN_BOOKS or more books. The number is the HOME number, so a flipped sign
    falls here too."""
    if q.empty:
        return pd.Series(np.zeros(0, bool), index=q.index)
    line = q["line"].astype(float)
    grp = line.groupby([q["game_id"], q["fetch_at"]], sort=False)
    return ((line - grp.transform("median")).abs() > MAX_SPREAD_DEV) & (grp.transform("size") >= MIN_BOOKS)


# ── the favourite and the price range ───────────────────────────────────────

OFFER_KEEP = ["game_id", "season", "game_date", "tip", "market", "book", "snapshot_at", "fetch_at",
              "T", "line", "coherent", "side", "price", "p_win", "p_push", "ev", "mu", "p_home"]


def slim(f: pd.DataFrame, extra=()) -> pd.DataFrame:
    """The columns the cells read. A pricing distribution (sigma) stays out: an
    object column parquet cannot store, and a cost on every placebo frame."""
    return f[[c for c in OFFER_KEEP + list(extra) if c in f]].reset_index(drop=True)


def favourites(neutral: pd.DataFrame) -> pd.DataFrame:
    """(game_id, fav, dog): the favourite by the MARKET's fair line at T, from
    the moneyline's own frame. Never from a result, never from the model."""
    return H.fav_sides(neutral[neutral["market"] == MARKET])[["game_id", "fav", "dog"]]


def on_side(frame: pd.DataFrame, fv: pd.DataFrame, col: str = "fav") -> pd.DataFrame:
    """Offers at deciding books on one game's favourite (or underdog), its real
    side kept as `side` and repeated as side_pick, the harness's per-game side."""
    x = frame.drop(columns="side_pick", errors="ignore").merge(
        fv[["game_id", col]].rename(columns={col: "side_pick"}), on="game_id")
    return x[(x["side"] == x["side_pick"]) & x["book"].isin(H.BETTABLE)].reset_index(drop=True)


def best_in_range(frame: pd.DataFrame, lo: float, hi: float) -> pd.DataFrame:
    """Every offer of the games whose BEST offer in `frame` lies in lo <= price <
    hi. Keeps a game's other offers, so choose() still takes that best one, and
    drops a game whose best offer is outside: a game with one book at -190 is
    not bet at another book's -205."""
    best = frame.groupby("game_id")["price"].transform("max")
    return frame[(best >= lo) & (best < hi)].reset_index(drop=True)


# ── the placebo's permutation ───────────────────────────────────────────────

def block_perm(block: np.ndarray, seed: int) -> np.ndarray:
    """A permutation that moves each item only inside its block: perm[i] is the
    item whose signal item i receives. One sort per run, no per-key lookup."""
    n = len(block)
    rng = np.random.default_rng(seed)
    order = np.lexsort((rng.random(n), block))
    base = np.argsort(block, kind="stable")
    perm = np.empty(n, dtype=np.int64)
    perm[base] = order
    return perm


@dataclass
class Keyed:
    """An offer frame with its games indexed once. codes: row -> game; week, date:
    game -> ISO week and date code. Every placebo reads these arrays."""
    frame: pd.DataFrame
    codes: np.ndarray
    week: np.ndarray
    date: np.ndarray

    @property
    def n_games(self) -> int:
        return len(self.week)

    def per_game_max(self, values: np.ndarray) -> np.ndarray:
        out = np.full(self.n_games, -np.inf)
        np.maximum.at(out, self.codes, values)
        return out

    def per_game_first(self, values: np.ndarray) -> np.ndarray:
        first = np.unique(self.codes, return_index=True)[1]
        return np.asarray(values, float)[first]


def keyed(frame: pd.DataFrame) -> Keyed:
    frame = frame.reset_index(drop=True)
    codes, _ = pd.factorize(frame["game_id"])
    first = np.unique(codes, return_index=True)[1]
    days = pd.to_datetime(pd.Series(frame["game_date"].to_numpy()[first]).astype(str))
    return Keyed(frame, codes, pd.factorize(days.dt.strftime("%G-%V"))[0],
                 pd.factorize(days.dt.strftime("%Y-%m-%d"))[0])


def band_flags(kf: Keyed, lo: float, hi: float) -> np.ndarray:
    """Per game: 1 when its best deciding price is in the band, else 0."""
    best = kf.per_game_max(kf.frame["price"].to_numpy(float))
    return ((best >= lo) & (best < hi)).astype(float)


def blind_cand(kf: Keyed, lo: float, hi: float) -> pd.DataFrame:
    return kf.frame.assign(strength=band_flags(kf, lo, hi)[kf.codes])


def blind_builder(kf: Keyed, lo: float, hi: float, block=None):
    """seed -> one FAVB placebo: "in this band" moved among every favourite in the
    week. The band's flags are built once; a run is one permutation."""
    flags = band_flags(kf, lo, hi)
    block = kf.week if block is None else block
    return lambda seed: kf.frame.assign(strength=flags[block_perm(block, seed)][kf.codes])


def ev_builder(kf: Keyed, block=None):
    """seed -> one FAVP2 placebo: each game's best EV moved to another in-range game
    in the week; every offer keeps its gap to its game's best offer."""
    ev = kf.frame["ev"].to_numpy(float)
    best = kf.per_game_max(ev)
    block = kf.week if block is None else block
    return lambda seed: kf.frame.assign(ev=ev + (best[block_perm(block, seed)] - best)[kf.codes])


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, float), P1.P_CLIP, 1 - P1.P_CLIP)
    return np.log(p / (1.0 - p))


def move_builder(kf: Keyed, block=None):
    """seed -> one FAVP1 placebo: the model's move toward the favourite moved to
    another in-range game in the week, added to the game's own market chance and
    re-priced at the game's own offers."""
    c = kf.frame
    move = kf.per_game_first(c["move_fav"].to_numpy(float))
    base = _logit(c["p_mkt"].to_numpy(float))
    d = H.dec(c["price"])
    block = kf.week if block is None else block

    def build(seed):
        p = 1.0 / (1.0 + np.exp(-(base + move[block_perm(block, seed)][kf.codes])))
        return c.assign(p_win=p, ev=p * d - 1.0)
    return build


def lazy(seeds, build):
    """G5.LazyFrames over the seeds: one frame at a time, none kept."""
    return G5.LazyFrames(seeds, build) if seeds else None


# ── the same-number rule ────────────────────────────────────────────────────

def same_number_frame(pt: P2.Point) -> pd.DataFrame:
    """The first search's pairs (a deciding book in Pinnacle's fetch) on the
    moneyline: proportional (fair, ev) and power (fair_pow, ev_pow) chances,
    assigned by position, because the adapter returns a fresh index."""
    vis = pt.vis_same[pt.vis_same["market"] == MARKET]
    o = P2.to_first_search(vis)
    if not P2._pairable(o, same_number=True):
        return P2._empty(P2.PAIR_COLS + ["fair_pow", "ev_pow"])
    x = sharp_pairs(o, ref=H.SHARP, books=list(H.BETTABLE), same_number=True)
    out = P2.from_first_search(x, MARKET)
    out["fair_pow"] = x["fair_pow"].to_numpy(float)
    out["ev_pow"] = x["ev_pow"].to_numpy(float)
    return out


def same_cands(pt: P2.Point, fv: pd.DataFrame) -> tuple[Keyed, Keyed]:
    """(proportional, power): the favourite's offers in range, carrying the
    market's own fair line, so a blind bet can name the favourite from the frame."""
    x = same_number_frame(pt)
    x = best_in_range(on_side(x, fv), *RULE_RANGE)
    x = x.merge(pt.fair[["game_id", "market", "mu", "p_home"]], on=["game_id", "market"], how="left")
    base = x.drop(columns=["fair", "ev", "fair_pow", "ev_pow"])
    prop = base.assign(p_win=x["fair"].to_numpy(float), p_push=0.0, ev=x["ev"].to_numpy(float))
    powr = base.assign(p_win=x["fair_pow"].to_numpy(float), p_push=0.0, ev=x["ev_pow"].to_numpy(float))
    return keyed(slim(prop, ("side_pick",))), keyed(slim(powr, ("side_pick",)))


# ── the market-anchored model ───────────────────────────────────────────────

def model_cands(pt, moves: pd.DataFrame, fv: pd.DataFrame) -> tuple[Keyed, pd.DataFrame]:
    """(the model's favourite offers in range, keyed; the market-fair offers of
    the same games). p_mkt and move_fav read the market's chance and the model's
    home-oriented move toward the favourite, by game, once."""
    mf = P1.model_fair(pt.fair, moves)
    c = best_in_range(on_side(H.fair_offers(pt.off, mf), fv), *RULE_RANGE)
    k = pt.fair[["game_id", "p_home"]].rename(columns={"p_home": "_mkt_home"})
    m = moves[["game_id", "move"]].rename(columns={"move": "_move"})
    c = c.merge(k, on="game_id", how="left").merge(m, on="game_id", how="left")
    home = (c["side_pick"] == "home").to_numpy()
    mkt, mv = c["_mkt_home"].to_numpy(float), c["_move"].to_numpy(float)
    c = c.assign(p_mkt=np.where(home, mkt, 1.0 - mkt), move_fav=np.where(home, mv, -mv))
    nm = on_side(pt.neutral, fv)
    nm = nm[nm["game_id"].isin(set(c["game_id"]))]
    return keyed(slim(c, ("side_pick", "p_mkt", "move_fav"))), slim(nm, ("side_pick",))


# ── what is reported beside a cell ──────────────────────────────────────────

def n_roi(g: pd.DataFrame) -> tuple[int, float]:
    return int(len(g)), H.roi(g) if len(g) else np.nan


def lone_best(bets: pd.DataFrame, cand: pd.DataFrame) -> np.ndarray:
    """True where the bet's price beats the next deciding book by more than
    LONE_BEST of implied chance, or no second book quotes the side."""
    key = ["game_id", "market", "side"]
    c = cand.loc[cand["book"].isin(H.BETTABLE), [*key, "price"]].sort_values(
        [*key, "price"], ascending=[True, True, True, False], kind="mergesort")
    second = c[c.groupby(key, sort=False).cumcount() == 1].rename(columns={"price": "_p2"})
    x = bets[key].reset_index(drop=True).merge(second, on=key, how="left")
    gap = H.imp(x["_p2"].to_numpy(float)) - H.imp(bets["price"].to_numpy(float))
    return ~x["_p2"].notna().to_numpy() | (gap > LONE_BEST)


def report_columns(g: pd.DataFrame, cand: pd.DataFrame, early: set) -> dict:
    """Section 8's numbers for one cell's pooled bets. Reported, never a bar."""
    out = {}
    empty = len(g) == 0
    price = g["price"].to_numpy(float) if not empty else np.array([], float)
    out["price_min"] = float(price.min()) if not empty else np.nan
    out["price_median"] = float(np.median(price)) if not empty else np.nan
    out["price_max"] = float(price.max()) if not empty else np.nan
    for name, (lo, hi) in REPORT_BANDS.items():
        sub = g[(price >= lo) & (price < hi)] if not empty else g
        out[f"pb_{name}_n"], out[f"pb_{name}_roi"] = n_roi(sub)
    for s in ("home", "away"):
        sub = g[g["side"] == s] if not empty else g
        out[f"{s}_fav_n"], out[f"{s}_fav_roi"] = n_roi(sub)
    sub = g[g["game_id"].isin(early)] if not empty else g
    out["first10_n"], out["first10_roi"] = n_roi(sub)
    if empty:
        out.update(roi_no_cap=np.nan, share_lone_best=np.nan, units_without_lone_best=np.nan)
        return out
    risk = 1.0 / (H.dec(price) - 1.0)
    res = g["result"].to_numpy()
    units = np.where(res == "W", 1.0, np.where(res == "L", -risk, 0.0))
    denom = float(risk[res != "P"].sum())
    out["roi_no_cap"] = float(units.sum() / denom) if denom > 0 else np.nan
    lone = lone_best(g, cand)
    out["share_lone_best"] = float(lone.mean())
    out["units_without_lone_best"] = float(g["units"].to_numpy(float)[~lone].sum())
    return out


def price_band_columns(frame: pd.DataFrame, side: str, bounds, games: pd.DataFrame, pool) -> dict:
    """Bar 5 for a blind cell, in the band columns the verdict reads: the best
    offer of every favourite, split by its price. band0 is the band just below."""
    bets = H.choose(frame, -np.inf, sides=[side])
    out = {"band_slots": len(bounds)}
    for i in range(G5.BAND_SLOTS):
        out.update({f"band{i}_lo": np.nan, f"band{i}_hi": np.nan, f"band{i}_n": 0,
                    f"band{i}_units": np.nan, f"band{i}_roi": np.nan})
    for i, (lo, hi) in enumerate(bounds):
        b = bets[(bets["price"] >= lo) & (bets["price"] < hi)]
        g = H.grade(b, games) if len(b) else b
        g = g[g["season"].isin(pool)] if len(g) else g
        out.update({f"band{i}_lo": float(lo), f"band{i}_hi": float(hi), f"band{i}_n": int(len(g)),
                    f"band{i}_units": float(g["units"].sum()) if len(g) else np.nan,
                    f"band{i}_roi": H.roi(g) if len(g) else np.nan})
    return out


def decorate(rows: list[dict], cand: pd.DataFrame, games: pd.DataFrame, early: set, strength: str,
             band_fn, extra: dict) -> list[dict]:
    """Each row: its bands (bar 5) and section 8's report, on the cell's own pooled
    seasons as run_cells wrote them (a season gated out at D stays out)."""
    for r in rows:
        pool = tuple(int(s) for s in str(r["pool_seasons"]).split(",") if s)
        if band_fn is not None:
            r.update(band_fn(r, pool))
        b = G5._pick(cand, r["cut"], r["side"], strength)
        g = H.grade(b, games) if len(b) else b
        g = g[g["season"].isin(pool)] if len(g) else g
        r.update(report_columns(g, cand, early))
        r.update(extra)
    return rows


# ── the cells, family by family ─────────────────────────────────────────────

def emit_blind(data: H.Data, point: str, times: pd.DataFrame, kf: Keyed, close, seeds, early: set,
               bands=BANDS) -> list[dict]:
    rows = []
    for band in bands:
        lo, hi = BANDS[band]
        cand = blind_cand(kf, lo, hi)
        placebo = lazy(seeds, blind_builder(kf, lo, hi))
        with price_floor(NO_FLOOR), bets_dir(f"{FAVB}_{band}"):
            r = H.run_cells(data, FAVB, point, cand, cand, [FLAG], {MARKET: [SIDE]}, close=close, sig={},
                            placebo=placebo, strength="strength", choose_seasons=H.CHOOSE, times=times)
            rows += decorate(r, cand, data.games, early, "strength",
                             lambda row, pool, b=band: price_band_columns(kf.frame, SIDE, BLIND_BOUNDS[b],
                                                                          data.games, pool),
                             {"axis_band": band, "signal_meaning": "the favourite, no model, by price band"})
    return rows


def _ev_bands(cand: pd.DataFrame, cuts, lowest: float, games: pd.DataFrame):
    return lambda row, pool: G5.band_columns(cand, row["side"], "ev",
                                             G5.band_bounds(cuts, int(row["cut_index"]), lowest=lowest),
                                             games, pool)


def emit_same(data: H.Data, point: str, times: pd.DataFrame, kf: Keyed, close, seeds, early: set,
              cuts=P2_CUTS) -> list[dict]:
    placebo = lazy(seeds, ev_builder(kf))
    with price_floor(RULE_FLOOR), bets_dir(FAVP2):
        r = H.run_cells(data, FAVP2, point, kf.frame, kf.frame, list(cuts), {MARKET: [SIDE]}, close=close,
                        sig={}, placebo=placebo, strength="ev", choose_seasons=H.CHOOSE, times=times)
        return decorate(r, kf.frame, data.games, early, "ev",
                        _ev_bands(kf.frame, P2_CUTS, P2_LOWEST, data.games),
                        {"axis_band": ALL, "signal_meaning": "same number against Pinnacle, proportional"})


def emit_model(data: H.Data, point: str, times: pd.DataFrame, kf: Keyed, nm: pd.DataFrame, close, seeds,
               early: set, cuts=P1_CUTS) -> list[dict]:
    placebo = lazy(seeds, move_builder(kf))
    with price_floor(RULE_FLOOR), bets_dir(FAVP1):
        r = H.run_cells(data, FAVP1, point, kf.frame, nm, list(cuts), {MARKET: [SIDE]}, close=close, sig={},
                        placebo=placebo, strength="ev", choose_seasons=H.CHOOSE, times=times)
        return decorate(r, kf.frame, data.games, early, "ev",
                        _ev_bands(kf.frame, P1_CUTS, P1_LOWEST, data.games),
                        {"axis_band": ALL, "signal_meaning": "market-anchored model on the favourite"})


def emit_power(data: H.Data, point: str, times: pd.DataFrame, kf: Keyed, close, early: set) -> list[dict]:
    with price_floor(RULE_FLOOR), bets_dir(C_POWER):
        r = H.run_cells(data, C_POWER, point, kf.frame, kf.frame, list(P2_CUTS), {MARKET: [SIDE]}, close=close,
                        sig={}, placebo=None, strength="ev", choose_seasons=H.CHOOSE, times=times)
        return decorate(r, kf.frame, data.games, early, "ev", None,
                        {"axis_band": ALL, "signal_meaning": "control: same number, power no-vig"})


def in_band_cand(frame: pd.DataFrame, kf: Keyed, lo: float, hi: float) -> pd.DataFrame:
    """`frame` limited to the games with their favourite's best deciding moneyline
    price in the band, strength 1 (a control's offers, any market)."""
    best = kf.per_game_max(kf.frame["price"].to_numpy(float))
    first = np.unique(kf.codes, return_index=True)[1]
    ids = kf.frame["game_id"].to_numpy()[first][(best >= lo) & (best < hi)]
    return frame[frame["game_id"].isin(set(ids))].assign(strength=FLAG).reset_index(drop=True)


def emit_dog(data: H.Data, point: str, times: pd.DataFrame, neutral: pd.DataFrame, fv: pd.DataFrame, kf: Keyed,
             close, early: set) -> list[dict]:
    rows = []
    dogs = on_side(neutral, fv, "dog")
    for band, (lo, hi) in BANDS.items():
        cand = in_band_cand(dogs, kf, lo, hi)
        with bets_dir(f"{C_DOG}_{band}"):
            r = H.run_cells(data, C_DOG, point, cand, cand, [FLAG], {MARKET: [DOG]}, close=close, sig={},
                            placebo=None, strength="strength", choose_seasons=H.CHOOSE, times=times)
            rows += decorate(r, cand, data.games, early, "strength", None,
                             {"axis_band": band, "signal_meaning": "control: the underdog in the same games"})
    return rows


def spread_neutral(q_sp: pd.DataFrame, times: pd.DataFrame, sig: dict, fv: pd.DataFrame) -> pd.DataFrame:
    """The favourite's spread offers at the market's fair line. The stored number
    is the HOME number: an away favourite's -5.5 is stored +5.5, and the harness
    settles it that way."""
    vis = H.visible(q_sp, times)
    fair = H.market_fair(vis, sig)
    return slim(on_side(H.fair_offers(H.offers(vis), fair), fv), ("side_pick",))


def emit_spread(data_sp: H.Data, point: str, times: pd.DataFrame, offers: pd.DataFrame, sig: dict, close_sp, kf: Keyed,
                early: set) -> list[dict]:
    rows = []
    for band, (lo, hi) in BANDS.items():
        cand = in_band_cand(offers, kf, lo, hi)
        with bets_dir(f"{C_SPREAD}_{band}"):
            r = H.run_cells(data_sp, C_SPREAD, point, cand, cand, [FLAG], {SPREADS: [SIDE]}, close=close_sp, sig=sig,
                            placebo=None, strength="strength", choose_seasons=H.CHOOSE, times=times)
            rows += decorate(r, cand, data_sp.games, early, "strength", None,
                             {"axis_band": band, "signal_meaning": "control: the favourite's spread in the same games"})
    return rows


# ── the frames every family reads at one decision point ─────────────────────

@dataclass
class Prep:
    ml: H.Data                      # moneyline quotes, impossible numbers out, main rungs
    q_same: pd.DataFrame            # the same-number rule's quote per fetch
    sp: H.Data | None               # spreads, the control only
    close: pd.DataFrame
    dropped_ml: pd.DataFrame
    dropped_sp: pd.DataFrame


def prep_from(data: H.Data) -> Prep:
    """Split the loaded quotes, drop impossible numbers and take each book's one
    number per fetch. Everything below reads the result. The ledger's fetches stay."""
    q = data.quotes
    ml, sp = q[q["market"] == MARKET].reset_index(drop=True), q[q["market"] == SPREADS].reset_index(drop=True)
    bad_m, bad_s = bad_moneyline(ml).to_numpy(), bad_spread(sp).to_numpy()
    dropped_ml, dropped_sp = ml[bad_m], sp[bad_s]
    ml, sp = ml[~bad_m].reset_index(drop=True), sp[~bad_s].reset_index(drop=True)
    data_ml = H.Data(games=data.games, quotes=P2.main_rungs(ml), fetches=data.fetches, notes=data.notes)
    data_sp = (H.Data(games=data.games, quotes=P2.main_rungs(sp), fetches=data.fetches, notes=data.notes)
               if len(sp) else None)
    return Prep(data_ml, P2.rungs_at_pinnacle(ml), data_sp, H.pinnacle_close(data_ml), dropped_ml, dropped_sp)


@dataclass
class Frames:
    point: str
    times: pd.DataFrame
    pt: P2.Point
    neutral: pd.DataFrame
    fv: pd.DataFrame
    blind: Keyed
    same: Keyed
    power: Keyed


def frames_at(prep: Prep, point: str) -> Frames:
    t = H.decision_times(prep.ml.fetches, prep.ml.games, point)
    pt = P2.point_frames(prep.ml.quotes, prep.q_same, t, {})
    neutral = slim(pt.neutral)
    fv = favourites(neutral)
    same, power = same_cands(pt, fv)
    return Frames(point, t, pt, neutral, fv, keyed(slim(on_side(neutral, fv), ("side_pick",))), same, power)


# ── counts, extremes, the placebo's differing share (no result) ─────────────

def _season_counts(season: pd.Series, bets: pd.DataFrame) -> dict:
    by = season.reindex(bets["game_id"]).value_counts().to_dict() if len(bets) else {}
    return {**{f"bets_{s}": int(by.get(s, 0)) for s in FULL_SEASONS},
            "bets_pooled": int(sum(by.get(s, 0) for s in GRADED))}


def count_rows(family: str, point: str, band: str, cand: pd.DataFrame, cuts, side: str, strength: str,
               season: pd.Series, floor: float) -> list[dict]:
    """The games a cell would bet, per season, from prices alone."""
    out = []
    with price_floor(floor):
        for k, cut in enumerate(cuts):
            b = G5._pick(cand, cut, side, strength)
            out.append({"family": family, "point": point, "band": band, "cut": cut,
                        **_season_counts(season, b)})
    return out


def differ_share(real: pd.DataFrame, runs) -> float:
    """Of the placebo bets on the graded seasons, the share on a game the cell
    itself does not bet. Near 0 means the shuffle repeats the real bets and is no
    null; the bar could never pass."""
    ids = set(real.loc[real["season"].isin(GRADED), "game_id"])
    total, same = 0, 0
    for b in runs:
        x = b[b["season"].isin(GRADED)]
        total += len(x)
        same += int(x["game_id"].isin(ids).sum())
    return 1.0 - same / total if total else np.nan


def _picks(frames, cut, side, strength, floor):
    with price_floor(floor):
        for pc in frames:
            yield G5._pick(pc, cut, side, strength)


def differ_rows(fr: Frames, seeds=DIFFER_SEEDS) -> list[dict]:
    """Blind and same-number cells, the registered week shuffle against a date
    shuffle in the same pool."""
    out = []
    kf = fr.blind
    for band, (lo, hi) in BANDS.items():
        real = _pick_real(blind_cand(kf, lo, hi), FLAG, "strength", NO_FLOOR)
        wk = differ_share(real, _picks(map(blind_builder(kf, lo, hi), seeds), FLAG, SIDE, "strength", NO_FLOOR))
        dt = differ_share(real, _picks(map(blind_builder(kf, lo, hi, kf.date), seeds), FLAG, SIDE, "strength", NO_FLOOR))
        out.append({"family": FAVB, "point": fr.point, "band": band, "cut": FLAG, "real_bets": int(real["season"].isin(GRADED).sum()),
                    "differ_week": wk, "differ_date": dt})
    kf = fr.same
    if len(kf.frame):
        for cut in P2_CUTS:
            real = _pick_real(kf.frame, cut, "ev", RULE_FLOOR)
            wk = differ_share(real, _picks(map(ev_builder(kf), seeds), cut, SIDE, "ev", RULE_FLOOR))
            dt = differ_share(real, _picks(map(ev_builder(kf, kf.date), seeds), cut, SIDE, "ev", RULE_FLOOR))
            out.append({"family": FAVP2, "point": fr.point, "band": ALL, "cut": cut, "real_bets": int(real["season"].isin(GRADED).sum()),
                        "differ_week": wk, "differ_date": dt})
    return out


def model_differ_rows(kf: Keyed, point: str, seeds=DIFFER_SEEDS) -> list[dict]:
    out = []
    for cut in P1_CUTS:
        real = _pick_real(kf.frame, cut, "ev", RULE_FLOOR)
        wk = differ_share(real, _picks(map(move_builder(kf), seeds), cut, SIDE, "ev", RULE_FLOOR))
        dt = differ_share(real, _picks(map(move_builder(kf, kf.date), seeds), cut, SIDE, "ev", RULE_FLOOR))
        out.append({"family": FAVP1, "point": point, "band": ALL, "cut": cut, "real_bets": int(real["season"].isin(GRADED).sum()),
                    "differ_week": wk, "differ_date": dt})
    return out


def _pick_real(cand: pd.DataFrame, cut: float, strength: str, floor: float) -> pd.DataFrame:
    with price_floor(floor):
        return G5._pick(cand, cut, SIDE, strength)


def alone_rows(fr: Frames) -> list[dict]:
    """Of the games in each band, the share alone in that band on their date."""
    kf = fr.blind
    best = kf.per_game_max(kf.frame["price"].to_numpy(float))
    out = []
    for name, (lo, hi) in REPORT_BANDS.items():
        d = kf.date[(best >= lo) & (best < hi)]
        n = np.bincount(d)
        out.append({"point": fr.point, "band": name, "games": int(len(d)),
                    "alone_on_date": float((n == 1).sum() / len(d)) if len(d) else np.nan})
    return out


def extremes(prep: Prep) -> dict:
    """The extremes of every price and line the search reads, by season, and what
    the impossible-number rules dropped."""
    q = prep.ml.quotes
    ex = {"moneyline_price": q.groupby("season")[["price_a", "price_b"]].agg(["min", "max"]).to_string(),
          "moneyline_quotes": int(len(q)), "moneyline_incoherent": int((~q["coherent"].astype(bool)).sum()),
          "dropped_moneyline_rows": int(len(prep.dropped_ml)),
          "dropped_moneyline_games": int(prep.dropped_ml["game_id"].nunique())}
    if prep.sp is not None:
        s = prep.sp.quotes
        ex["spread_line"] = s.groupby("season")["line"].agg(["min", "max"]).to_string()
        ex["spread_price"] = s.groupby("season")[["price_a", "price_b"]].agg(["min", "max"]).to_string()
        ex["spread_quotes"] = int(len(s))
        ex["dropped_spread_rows"] = int(len(prep.dropped_sp))
        ex["dropped_spread_games"] = int(prep.dropped_sp["game_id"].nunique())
    return ex


def top_offers(frame: pd.DataFrame, n: int = 10) -> str:
    """The highest-EV offer of each game, highest first (prices only)."""
    x = frame.sort_values("ev", ascending=False).drop_duplicates("game_id").head(n)
    cols = [c for c in ("game_id", "book", "side", "line", "price", "p_win", "ev", "fetch_at", "T") if c in x]
    return x[cols].to_string(index=False)


# ── guards for a run that must not read a result ────────────────────────────

def blind_scores(games: pd.DataFrame, seed: int = 20261031) -> pd.DataFrame:
    """The games with their scores replaced by random numbers, marked, so a run
    can time and exercise every grade without computing the result of any bet."""
    rng = np.random.default_rng(seed)
    g = games.copy()
    home = rng.integers(90, 130, len(g)).astype(float)
    away = rng.integers(90, 130, len(g)).astype(float)
    g["home_score"], g["away_score"] = home + (home == away), away
    g.attrs[BLINDED] = True
    return g


@contextmanager
def only_random_scores():
    """Inside, a grade handed real scores stops the run. Used by --smoke."""
    real = H.grade

    def guarded(bets, games):
        if not games.attrs.get(BLINDED):
            raise RuntimeError("a grade was handed real scores inside a no-result run")
        return real(bets, games)
    H.grade = guarded
    try:
        yield
    finally:
        H.grade = real


# ── a synthetic world (each check watched failing with its rule broken) ─────

SYN_BOOKS = ("pinnacle", "fanduel", "draftkings", "betmgm", "betrivers")
SYN_FAV = (-120.0, -150.0, -180.0, -210.0, -240.0, -280.0, -350.0, -450.0, -650.0, -800.0, -1400.0)


def _quote(game, fetch_at, market, book, line, pa, pb) -> dict:
    return {"game_id": game["game_id"], "season": game["season"], "game_date": game["game_date"],
            "tip": game["tip"], "market": market, "book": book, "fetch_at": fetch_at,
            "snapshot_at": fetch_at - pd.Timedelta(minutes=5), "line": line, "price_a": pa, "price_b": pb}


def synthetic_world(seed: int = 11, seasons=FULL_SEASONS, dates: int = 36, per_date: int = 6,
                    plant: dict | None = None, swapped: int = 5) -> H.Data:
    """Made-up games holding full-game moneylines and spreads at decision points
    A to D, favourites at every band of the search. `plant`: {favourite's fair
    price: extra win chance}, a planted edge. `swapped`: games where one book's
    two prices are swapped (a bad row). Results are drawn from each game's fair
    chance, so with no plant there is nothing to find."""
    rng = np.random.default_rng(seed)
    plant = plant or {}
    games, rows = [], []
    bad_left = swapped
    for s in seasons:
        start = pd.Timestamp(f"{s - 1}-11-01T00:00:00Z")
        for d in range(dates):
            day = start + pd.Timedelta(days=2 * d)
            for j in range(per_date):
                gid = f"SYN{s}_{d:03d}_{j}"
                fav_price = SYN_FAV[(d * per_date + j + d) % len(SYN_FAV)]
                home_fav = (d + j) % 3 != 0
                p = float(H.imp(np.array([fav_price]))[0])
                wins = rng.random() < p + plant.get(fav_price, 0.0)
                margin = float(rng.integers(1, 25))
                home_won = wins if home_fav else not wins
                tip = day + pd.Timedelta(hours=24, minutes=15 * j)
                game = {"game_id": gid, "season": s, "game_date": day.strftime("%Y-%m-%d"), "tip": tip,
                        "home_team": "HOM", "away_team": "AWY",
                        "home_score": 105.0 + (margin if home_won else 0.0),
                        "away_score": 105.0 + (0.0 if home_won else margin)}
                games.append(game)
                soft = rng.random() < 0.15
                bad_here = bad_left > 0 and fav_price <= -350.0
                bad_left -= int(bad_here)
                fetches = (day + pd.Timedelta(hours=15), tip - pd.Timedelta(minutes=240),
                           tip - pd.Timedelta(minutes=120), tip - pd.Timedelta(minutes=60))
                line = float(np.round(np.log(p / (1 - p)) * 6.5)) + 0.5
                home_number = -line if home_fav else line      # the HOME number
                for book in SYN_BOOKS:
                    vig = 0.012 if book == "pinnacle" else 0.022
                    noise = 0.0 if book == "pinnacle" else float(rng.normal(0.0, 0.004))
                    i_f = p + vig + noise
                    if soft and book == "betrivers":
                        i_f = p - 0.012                        # a soft price above Pinnacle's chance
                    pf, pd_ = G5.american(i_f), G5.american(1.0 - p + vig - noise)
                    pa, pb = (pf, pd_) if home_fav else (pd_, pf)
                    if bad_here and book == "fanduel":
                        pa, pb = pb, pa                        # the bad row: two prices swapped
                    for f in fetches:
                        rows.append(_quote(game, f, MARKET, book, np.nan, pa, pb))
                        rows.append(_quote(game, f, SPREADS, book, home_number, -110.0, -110.0))
    q = pd.DataFrame(rows)
    q["coherent"] = H.imp(q["price_a"]) + H.imp(q["price_b"]) >= H.COHERENT[0]
    q["coherent"] &= H.imp(q["price_a"]) + H.imp(q["price_b"]) <= H.COHERENT[1]
    g = pd.DataFrame(games)
    f = q[["game_id", "tip", "fetch_at"]].drop_duplicates(["game_id", "fetch_at"]).copy()
    f["lead_min"] = (f["tip"] - f["fetch_at"]).dt.total_seconds() / 60.0
    return H.Data(games=g, quotes=q[H.QUOTE_COLS], fetches=f.reset_index(drop=True))


def synthetic_base(games: pd.DataFrame, seed: int = 5) -> pd.DataFrame:
    """Per-game inputs in P1's columns on made-up games."""
    rng = np.random.default_rng(seed)
    n = len(games)
    base = pd.DataFrame({"game_id": games["game_id"].to_numpy(),
                         "margin": (games["home_score"] - games["away_score"]).to_numpy(float) * 0.2 + rng.normal(0, 6, n),
                         "total": rng.normal(225, 8, n), "pace_h": rng.normal(99, 2, n), "pace_a": rng.normal(99, 2, n),
                         "gap_margin": rng.normal(0, 1, n), "gap_total": rng.normal(0, 1, n),
                         "altitude": (rng.random(n) < 0.1).astype(float)})
    for f in P1.F5:
        base[f"{f}_h"], base[f"{f}_a"] = rng.random(n), rng.random(n)
    for s in ("h", "a"):
        for k in P1.SCHED:
            base[f"{s}_{k}"] = rng.random(n)
    return base


def run_world(data: H.Data, seeds=(1, 2), min_train: int = 100, points=BLIND_POINTS) -> dict:
    """Every cell and control of `data`, the path --full takes (P1's inputs made up)."""
    prep = prep_from(data)
    sig = H.close_dist(H.pinnacle_close(prep.sp), data.games)
    close_sp = H.pinnacle_close(prep.sp)
    base = synthetic_base(data.games)
    early = set(data.games["game_id"].iloc[:30])
    rows, ctl, fits = [], [], []
    for point in points:
        fr = frames_at(prep, point)
        rows += emit_blind(prep.ml, point, fr.times, fr.blind, prep.close, seeds, early)
        rows += emit_same(prep.ml, point, fr.times, fr.same, prep.close, seeds, early)
        ctl += emit_dog(prep.ml, point, fr.times, fr.neutral, fr.fv, fr.blind, prep.close, early)
        ctl += emit_spread(prep.sp, point, fr.times, spread_neutral(prep.sp.quotes, fr.times, sig, fr.fv), sig, close_sp,
                           fr.blind, early)
        ctl += emit_power(prep.ml, point, fr.times, fr.power, prep.close, early)
        if point in P1_POINTS:
            pt = P1.make_point(prep.ml, point, fr.times, {}, base)
            mv, f = P1.walk_forward(P1.model_rows(MARKET, pt.fair, pt.base, data.games), MARKET, GRADED, {},
                                    fold="season", min_train=min_train)
            fits += f
            kf, nm = model_cands(pt, mv, fr.fv)
            rows += emit_model(prep.ml, point, fr.times, kf, nm, prep.close, seeds, early)
    return {"rows": rows, "controls": ctl, "fits": fits, "prep": prep}


def synthetic_checks() -> dict:
    """Arithmetic and rules the cells depend on. Raises on a fault."""
    H.check()
    assert len(cell_specs()) == EXPECTED_CELLS and len(control_specs()) == EXPECTED_CONTROLS
    # the cap, as section 2 states it
    r, w = H.risk_win(np.array([-200.0, -300.0, -500.0, -1000.0]))
    assert np.allclose(r, [2.0, 3.0, 3.0, 3.0]) and np.allclose(w, [1.0, 1.0, 0.6, 0.3])
    # the floor reaches the harness's choice, and comes back
    f = pd.DataFrame({"game_id": "g", "market": MARKET, "book": H.DK, "side": "home", "side_pick": "home",
                      "price": [-600.0], "line": [np.nan], "p_win": [0.9], "p_push": [0.0], "ev": [0.05]})
    assert H.choose(f, 0.0, sides=[SIDE]).empty
    with price_floor(RULE_FLOOR):
        assert len(H.choose(f, 0.0, sides=[SIDE])) == 1
    assert H.PRICE_FLOOR == float(H.config.DEFAULT_MIN_ODDS)
    # the week shuffle keeps each item in its block and is a permutation
    block = np.array([0, 0, 0, 1, 1, 2, 2, 2, 2])
    perm = block_perm(block, 1)
    assert sorted(perm) == list(range(9)) and (block[perm] == block).all()
    # a synthetic world holds what the checks claim: favourites in every band, a swap, spreads
    data = synthetic_world(seasons=(2025, 2026), dates=12)
    assert bad_moneyline(data.quotes[data.quotes["market"] == MARKET]).any(), "no bad row in the world"
    fr = frames_at(prep_from(data), "C")
    best = fr.blind.per_game_max(fr.blind.frame["price"].to_numpy(float))
    for name, (lo, hi) in BANDS.items():
        assert ((best >= lo) & (best < hi)).sum() > 0, f"no favourite in band {name}"
    assert (data.quotes["market"] == SPREADS).any()
    return {"synthetic_checks": "pass"}


# ── real data ───────────────────────────────────────────────────────────────

def prepare(cache: Path, require: bool) -> Prep:
    t0 = time.time()
    data = H.load(cache, seasons=list(FULL_SEASONS), require_seasons=FULL_SEASONS if require else None)
    log(f"prices loaded: {data.notes}", t0)
    data.quotes = data.quotes[data.quotes["market"].isin([MARKET, SPREADS])].reset_index(drop=True)
    prep = prep_from(data)
    log(f"moneyline quotes {len(prep.ml.quotes):,}, spread quotes {len(prep.sp.quotes):,}", t0)
    return prep


@dataclass
class P1Setup:
    w: object
    st: object
    models: dict
    luck: pd.DataFrame
    sched_in: pd.DataFrame
    early: set


def p1_setup(cache: Path, games: pd.DataFrame) -> P1Setup:
    """The fourth search's projection, its own walk-forward (about 10 minutes)."""
    t0 = time.time()
    w = P.load_world(cache, max_season=H.CONFIRM)
    _, st, models, _, _ = P.run_projection_setup(w, H.CONFIRM)
    sched_in, box = P1.load_inputs(cache)
    luck = P1.luck_inputs(games, L.team_box(box, games))
    log("projection set up", t0)
    return P1Setup(w, st, models, luck, sched_in, P1.early_games(sched_in))


def model_point(prep: Prep, point: str, fr: Frames, s: P1Setup) -> tuple[Keyed, pd.DataFrame, list, pd.DataFrame]:
    """The market-anchored model at one point, on real games, walk-forward: fit on
    seasons before the graded one. It reads real scores of those earlier seasons."""
    pt = P1.point_inputs(prep.ml, point, fr.times, s.w, s.st, s.models, s.luck, s.sched_in, {})
    mv, fits = P1.walk_forward(P1.model_rows(MARKET, pt.fair, pt.base, prep.ml.games), MARKET, P1.FULL_GRADED, {},
                               fold="season")
    kf, nm = model_cands(pt, mv, fr.fv)
    return kf, nm, fits, mv


def refuse_full(cache: Path) -> list[str]:
    why = []
    if os.environ.get(GO_ENV) != "1":
        why.append(f"{GO_ENV}=1 is not set: the owner runs --full")
    if not os.environ.get(RESULTS_ENV):
        why.append(f"{RESULTS_ENV} is not set: name this search's own results folder")
    if not os.environ.get(BETS_ENV):
        why.append(f"{BETS_ENV} is not set: a passing cell's figures read its bets")
    for name in (P.LEDGER_FILE, P.STINTS_FILE):
        if not (Path(cache) / name).exists():
            why.append(f"{Path(cache) / name} does not exist: refresh the cache")
    return why


def write_family(rows: list[dict], family: str, out: Path) -> None:
    sel = [r for r in rows if r["family"] == family]
    if sel:
        L.write_cells(sel, out / f"cells_{family}.parquet")


def full(cache: Path = H.CACHE, out: Path | None = None) -> None:
    why = refuse_full(cache)
    if why:
        P.refuse(why)
    out = Path(os.environ[RESULTS_ENV]) if out is None else out
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print(json.dumps(synthetic_checks()), flush=True)
    try:
        prep = prepare(cache, require=True)
    except RuntimeError as e:
        P.refuse([str(e)])
    games = prep.ml.games
    sig = H.close_dist(H.pinnacle_close(prep.sp), games)
    close_sp = H.pinnacle_close(prep.sp)
    season = games.set_index("game_id")["season"].astype(int)
    early = P1.early_games(P1.load_inputs(cache)[0])
    rows, ctl, pops, fits = [], [], [], []
    for point in BLIND_POINTS:
        fr = frames_at(prep, point)
        rows += emit_blind(prep.ml, point, fr.times, fr.blind, prep.close, PLACEBO_SEEDS, early)
        rows += emit_same(prep.ml, point, fr.times, fr.same, prep.close, PLACEBO_SEEDS, early)
        ctl += emit_dog(prep.ml, point, fr.times, fr.neutral, fr.fv, fr.blind, prep.close, early)
        offers = spread_neutral(prep.sp.quotes, fr.times, sig, fr.fv)
        ctl += emit_spread(prep.sp, point, fr.times, offers, sig, close_sp, fr.blind, early)
        ctl += emit_power(prep.ml, point, fr.times, fr.power, prep.close, early)
        pops += point_counts(fr, season, offers)
        log(f"{point}: blind, same number and controls done: {len(rows)} cells, {len(ctl)} controls so far", t0)
    for fam in (FAVB, FAVP2):
        write_family(rows, fam, out)
    for fam in (C_DOG, C_SPREAD, C_POWER):
        write_family(ctl, fam, out)
    log("the model's inputs and walk-forward next, the longest step", t0)
    setup = p1_setup(cache, games)
    for point in P1_POINTS:
        fr = frames_at(prep, point)
        kf, nm, f, _ = model_point(prep, point, fr, setup)
        fits += [{**x, "point": point} for x in f]
        rows += emit_model(prep.ml, point, fr.times, kf, nm, prep.close, PLACEBO_SEEDS, setup.early)
        pops += count_rows(FAVP1, point, ALL, kf.frame, P1_CUTS, SIDE, "ev", season, RULE_FLOOR)
        log(f"{point}: model done, {len(rows)} cells", t0)
    check_rows(rows, cell_specs(), "judged")
    check_rows(ctl, control_specs(), "controls")
    write_family(rows, FAVP1, out)
    pd.DataFrame(pops).to_parquet(out / "population_FAV.parquet")
    (out / "fits_FAVP1.json").write_text(json.dumps(fits, indent=1, default=str), encoding="utf-8")
    log(f"cells written to {out}: {len(rows)} judged, {len(ctl)} controls", t0)


def point_counts(fr: Frames, season: pd.Series, spread_offers: pd.DataFrame) -> list[dict]:
    """Prices only: the bets of every judged blind and same-number cell and every
    control at one decision point. The controls run at the harness's own floor."""
    out = []
    dogs = on_side(fr.neutral, fr.fv, "dog")
    for band, (lo, hi) in BANDS.items():
        out += count_rows(FAVB, fr.point, band, blind_cand(fr.blind, lo, hi), [FLAG], SIDE, "strength", season, NO_FLOOR)
        out += count_rows(C_DOG, fr.point, band, in_band_cand(dogs, fr.blind, lo, hi), [FLAG], DOG, "strength", season,
                          H.PRICE_FLOOR)
        out += count_rows(C_SPREAD, fr.point, band, in_band_cand(spread_offers, fr.blind, lo, hi), [FLAG], SIDE, "strength",
                          season, H.PRICE_FLOOR)
    if len(fr.same.frame):
        out += count_rows(FAVP2, fr.point, ALL, fr.same.frame, P2_CUTS, SIDE, "ev", season, RULE_FLOOR)
        out += count_rows(C_POWER, fr.point, ALL, fr.power.frame, P2_CUTS, SIDE, "ev", season, RULE_FLOOR)
    return out


def placebo_cost(run, cells: int, extra: int = 30) -> float:
    """Seconds for one placebo run of one cell, on the path --full takes: the same
    cells with 1 + extra seeds against one seed. The longer call goes first, so what
    the first call pays once falls on the high side."""
    t = time.perf_counter()
    run(tuple(range(1, extra + 2)))
    many = time.perf_counter() - t
    t = time.perf_counter()
    run((1,))
    return max(many - (time.perf_counter() - t), 0.0) / extra / cells


def smoke(cache: Path = H.CACHE, skip_model: bool = False) -> dict:
    """Synthetic checks, then counts on the real cache. No result of any bet: grades
    read random scores, guarded by only_random_scores, and no bets are written."""
    t0 = time.time()
    os.environ.pop(BETS_ENV, None)
    print(json.dumps(synthetic_checks()), flush=True)
    log("synthetic checks done", t0)
    prep = prepare(cache, require=False)
    log(f"the fetch-median rule dropped {len(prep.dropped_ml)} moneyline rows and {len(prep.dropped_sp)} spread rows")
    print(prep.dropped_ml[["game_id", "book", "price_a", "price_b", "fetch_at"]].to_string(index=False))
    print(prep.dropped_sp[["game_id", "book", "line", "price_a", "price_b", "fetch_at"]].to_string(index=False))
    ex = extremes(prep)
    for k, v in ex.items():
        print(f"\n{k}:\n{v}")
    games = prep.ml.games
    season = games.set_index("game_id")["season"].astype(int)
    blinded = blind_scores(games)
    data_b = H.Data(games=blinded, quotes=prep.ml.quotes, fetches=prep.ml.fetches)
    data_sp_b = H.Data(games=blinded, quotes=prep.sp.quotes, fetches=prep.sp.fetches)
    # pricing distribution for the spread control: results around Pinnacle's close on earlier
    # seasons, no bet's result (a signal from earlier games)
    close_sp = H.pinnacle_close(prep.sp)
    sig = H.close_dist(close_sp, games)
    counts, differs, alone, cover, times = [], [], [], {}, {}
    frames, spread_offers = {}, {}
    r_blind, r_same, r_ctl = 0, 0, 0
    with only_random_scores():
        for point in BLIND_POINTS:
            t1 = time.time()
            fr = frames_at(prep, point)
            frames[point] = fr
            times[f"frames_{point}"] = time.time() - t1
            cover[point] = H.point_coverage(prep.ml, point, fr.times)
            offers = spread_neutral(prep.sp.quotes, fr.times, sig, fr.fv)
            spread_offers[point] = offers
            counts += point_counts(fr, season, offers)
            alone += alone_rows(fr)
            differs += differ_rows(fr)
            print(f"\nHIGHEST-EV, same number, proportional, at {point}:\n{top_offers(fr.same.frame)}")
            print(f"HIGHEST-EV, same number, power, at {point}:\n{top_offers(fr.power.frame)}")
            short = best_in_range(fr.blind.frame, NO_FLOOR, OLD_EDGE)
            print(f"HIGHEST-EV, every favourite shorter than -200 at the market's fair line, at {point}:\n{top_offers(short)}")
            print(f"HIGHEST-EV, those favourites' spreads at the market's fair line, at {point}:\n"
                  f"{top_offers(in_band_cand(offers, fr.blind, NO_FLOOR, OLD_EDGE))}")
            log(f"{point}: counted", t0)
        fr = frames["C"]
        # the whole path through the harness on real prices and random scores, one placebo
        t1 = time.perf_counter()
        r = emit_blind(data_b, "C", fr.times, fr.blind, prep.close, (1,), set(), bands=("300_500",))
        times["blind_cell_with_1_placebo"] = time.perf_counter() - t1
        r_blind = len(r)
        t1 = time.perf_counter()
        r = emit_same(data_b, "C", fr.times, fr.same, prep.close, (1,), set())
        times["same_4_cells_with_1_placebo"] = time.perf_counter() - t1
        r_same = len(r)
        t1 = time.perf_counter()
        r = emit_dog(data_b, "C", fr.times, fr.neutral, fr.fv, fr.blind, prep.close, set())
        r += emit_spread(data_sp_b, "C", fr.times, spread_offers["C"], sig, close_sp, fr.blind, set())
        r += emit_power(data_b, "C", fr.times, fr.power, prep.close, set())
        times["controls_at_one_point"] = time.perf_counter() - t1
        r_ctl = len(r)
        assert all(x["pool_n"] > 0 for x in r), "a control placed no bet on the real prices"
        times["placebo_blind"] = placebo_cost(
            lambda seeds: emit_blind(data_b, "C", fr.times, fr.blind, prep.close, seeds, set(), bands=("300_500",)), 1)
        times["placebo_same"] = placebo_cost(
            lambda seeds: emit_same(data_b, "C", fr.times, fr.same, prep.close, seeds, set()), len(P2_CUTS))
        mv_extremes = {}
        if not skip_model:
            t1 = time.time()
            setup = p1_setup(cache, games)
            times["model_setup"] = time.time() - t1
            kf_last = None
            for point in P1_POINTS:
                t1 = time.time()
                kf, nm, fits, mv = model_point(prep, point, frames[point], setup)
                times[f"model_point_{point}"] = time.time() - t1
                counts += count_rows(FAVP1, point, ALL, kf.frame, P1_CUTS, SIDE, "ev", season, RULE_FLOOR)
                differs += model_differ_rows(kf, point)
                mv_extremes[point] = {"move_min": float(mv["move"].min()), "move_max": float(mv["move"].max()),
                                      "chance_min": float(kf.frame["p_win"].min()), "chance_max": float(kf.frame["p_win"].max()),
                                      "games_in_range": int(kf.n_games),
                                      "penalties": sorted({str(x["C"]) for x in fits})}
                print(f"\nHIGHEST-EV, market-anchored model, at {point}:\n{top_offers(kf.frame)}")
                kf_last, nm_last, pt_last = kf, nm, point
            t1 = time.perf_counter()
            emit_model(data_b, pt_last, frames[pt_last].times, kf_last, nm_last, prep.close, (1,), set())
            times["model_4_cells_with_1_placebo"] = time.perf_counter() - t1
            times["placebo_model"] = placebo_cost(
                lambda seeds: emit_model(data_b, pt_last, frames[pt_last].times, kf_last, nm_last, prep.close, seeds, set()),
                len(P1_CUTS))
            print("\nmodel extremes:", json.dumps(mv_extremes, indent=1))
    assert r_blind == 1 and r_same == 4 and r_ctl == 2 * len(BANDS) + len(P2_CUTS), (r_blind, r_same, r_ctl)
    print("\nCOVERAGE (share of a season's games with a decision):", json.dumps(cover))
    print("\nCOUNTS (bets per season, from prices alone; pooled = 2021-22 to 2025-26):")
    print(pd.DataFrame(counts).to_string(index=False))
    print("\nALONE IN THEIR BAND ON THEIR DATE:")
    print(pd.DataFrame(alone).pivot(index="band", columns="point", values="alone_on_date").round(3).to_string())
    d = pd.DataFrame(differs)
    print(f"\nPLACEBO: share of placebo bets on a game the cell does not bet ({len(DIFFER_SEEDS)} seeds):")
    print(d.round(3).to_string(index=False))
    thin = d[(d["real_bets"] >= 30) & (d["differ_week"] < 0.5)]
    print("cells with 30+ real bets under 50%:", "none" if thin.empty else thin.to_string(index=False))
    p = projection(times, skip_model)
    print("\nTIMES (seconds):", json.dumps({k: round(v, 3) for k, v in times.items()}))
    print("PROJECTION:", json.dumps(p))
    log("smoke done", t0)
    return {"counts": counts, "differ": differs, "times": times, "projection": p}


def projection(times: dict, skip_model: bool) -> dict:
    """The projected --full from this run's measured times: each judged cell's
    report plus 200 placebo runs; controls have no placebo."""
    n_blind = len(BLIND_POINTS) * len(BANDS)
    n_same = len(P2_POINTS) * len(P2_CUTS)
    frames = sum(v for k, v in times.items() if k.startswith("frames_"))
    blind = n_blind * (times["blind_cell_with_1_placebo"] + N_PLACEBO * times["placebo_blind"])
    same = len(P2_POINTS) * times["same_4_cells_with_1_placebo"] + n_same * N_PLACEBO * times["placebo_same"]
    controls = len(BLIND_POINTS) * times["controls_at_one_point"]
    sec = frames + blind + same + controls
    out = {"frames_s": frames, "blind_s": blind, "same_s": same, "controls_s": controls}
    if not skip_model:
        n_model = len(P1_POINTS) * len(P1_CUTS)
        pts = sum(v for k, v in times.items() if k.startswith("model_point_"))
        model = (times["model_setup"] + pts + len(P1_POINTS) * times["model_4_cells_with_1_placebo"]
                 + n_model * N_PLACEBO * times["placebo_model"])
        out["model_s"] = model
        sec += model
    out["load_and_checks_s_excluded"] = True
    out["total_minutes"] = sec / 60.0
    try:
        import psutil
        info = psutil.Process().memory_info()
        out["peak_working_set_gb"] = getattr(info, "peak_wset", info.rss) / 1e9
    except ImportError:
        out["peak_working_set_gb"] = None
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true", help="synthetic checks, then real counts only")
    g.add_argument("--full", action="store_true", help=f"every graded season (needs {GO_ENV}=1)")
    ap.add_argument("--skip-model", action="store_true", help="--smoke without the 10-minute model setup")
    a = ap.parse_args(argv)
    if a.full:
        full(H.CACHE)
    else:
        smoke(H.CACHE, skip_model=a.skip_model)


if __name__ == "__main__":
    main()
