"""The shared grading harness for the second NBA game-market search.

docs/nba_models_2026.md §6.2 fixes the rules every cell is graded under; this
module is those rules, once, so no family's lab can drift from another's. A lab
supplies a FAIR model per (game, decision point, market) -- a margin or total
distribution, or a home win probability -- or a list of sides to bet; the
harness supplies what a bettor could see at that moment, chooses the bet,
grades it in units and reports every bar the section names.

DEFINITIONS (stated once, used everywhere):

  FETCH      one purchase of the whole slate. Its instant is the time it was
             ASKED FOR, from the two purchase ledgers (`odds_history_pulls` on
             the hour, `odds_history_fetches` off it); a stored row joins its
             fetch on created_at = pulled_at, which one transaction writes.
             A quote's snapshot_at is the book's last update, minutes before
             the fetch, and never names the window.
  DECISION   A: the 15Z fetch on the game date. B: the newest fetch 180-360
  POINTS     minutes before tip. C: newest 60-180. D: newest 45-75. Never a
             fetch inside the last 15 minutes. One decision per game per cell.
  VISIBLE    at decision time T, per (game, market, book): the newest quote
             from a fetch at or before T, no older than 60 minutes, pre-game
             (`open`, snapshot_at before tip).
  COHERENT   a two-way quote whose implied probabilities sum to 1.00-1.15.
  DECIDING   config.BEST_LINE_BOOKMAKERS only (Pinnacle and Bovada never), at
             the number that book hangs; price floor config.DEFAULT_MIN_ODDS.
             DraftKings alone is graded beside every cell.
  UNITS      one unit to win, risk = 1/(decimal-1) capped at 3. A PUSH returns
             the stake: 0 units, and its risk LEAVES the denominator (§6.2.4).
             ROI with the push stake kept is reported beside.
  SPREAD     spread_home is the HOME number; home covers when
             (home - away) + spread_home > 0. `line` below is always the stored
             side-A number (spread_home, or the total), whatever the side.
  SEASONS    ending-year labels. Cuts chosen on 2022-2025, confirmed on 2026;
             2021 (2020-21) reported, never chosen on.
  DERIVATIVE first half (h2h_h1, spreads_h1, totals_h1), first quarter (_q1)
  MARKETS    and team totals (team_totals_home / _away), bought one game at a
             time (load_per_event). Same rules as the full game, settled on
             what the books settle them on (docs/nba_models_2026.md §4.2, §8;
             scripts/nba_derivative_lab.py): first half = Q1 + Q2 points,
             first quarter = Q1 points, both from nba_period_scores
             (with_periods); a team total on that team's own final score,
             overtime included. A level first half or first quarter VOIDS a
             two-way moneyline at every book: graded "P", stake back, out of
             the denominator, exactly like a push. Side A is home for h2h_* and
             spreads_* (spread_home is the home number for the period), over
             for totals_* and team totals.

    PYTHONPATH=. python -m scripts.nba_game_harness --check
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
from scripts.nba_derivative_lab import build_outcomes  # noqa: E402
from scripts.nba_game_market_lab import (  # noqa: E402
    _assert_spread_sign, dec, imp, power_devig, probs_at, settle, solve_mu)

# NBA_RESEARCH_CACHE points a lab in another worktree at the one shared cache
# (scripts/nba_research_cache.py writes it; it is a cache of Supabase).
CACHE = Path(os.environ.get("NBA_RESEARCH_CACHE", str(ROOT / "data" / "local" / "nba")))
MARKETS = ("h2h", "spreads", "totals")                 # the full game; load() keeps only these
DERIVATIVE_MARKETS = ("h2h_h1", "spreads_h1", "totals_h1", "h2h_q1", "spreads_q1", "totals_q1",
                      "team_totals_home", "team_totals_away")
# market -> (kind, what settles it). kind: ml (two-way winner), spread (home
# number), total (over / under). Settles on: the full game, the first half,
# the first quarter, or one team's own final score.
MARKET_SPEC = {
    "h2h": ("ml", "game"), "spreads": ("spread", "game"), "totals": ("total", "game"),
    "h2h_h1": ("ml", "h1"), "spreads_h1": ("spread", "h1"), "totals_h1": ("total", "h1"),
    "h2h_q1": ("ml", "q1"), "spreads_q1": ("spread", "q1"), "totals_q1": ("total", "q1"),
    "team_totals_home": ("total", "home_team"), "team_totals_away": ("total", "away_team"),
}
_KIND = {m: k for m, (k, _) in MARKET_SPEC.items()}
_SCOPE = {m: s for m, (_, s) in MARKET_SPEC.items()}
KIND_MARKET = {"ml": "h2h", "spread": "spreads", "total": "totals"}   # settled like this full-game market
SIDE_A = {m: ("over" if k == "total" else "home") for m, k in _KIND.items()}
SIDE_B = {m: ("under" if k == "total" else "away") for m, k in _KIND.items()}
# per-team points that settle the first half and first quarter (with_periods)
PERIOD_COLS = ("home_q1", "away_q1", "home_h1", "away_h1")
_PERIOD_OF = {"h1": ("home_h1", "away_h1"), "q1": ("home_q1", "away_q1")}
BETTABLE = tuple(config.BEST_LINE_BOOKMAKERS)
BOOK_RANK = {b: i for i, b in enumerate(BETTABLE)}
DK, SHARP = "draftkings", "pinnacle"
PRICE_FLOOR = float(config.DEFAULT_MIN_ODDS)          # -200
COHERENT = (1.00, 1.15)
MAX_RISK = 3.0
STALE_MIN = 60
MIN_LEAD = 15
POINTS = {"A": None, "B": (180, 360), "C": (60, 180), "D": (45, 75)}
CHOOSE = (2022, 2023, 2024, 2025)
CONFIRM = 2026
REGIME = 2021
N_BOOT, SEED = 4000, 7
# Benjamini-Hochberg at m = 4,172 asks the best cell for p <= 0.05/4172 =
# 1.2e-5, finer than 4,000 resamples can resolve (1/4000 = 2.5e-4). A p under
# P_REFINE_BELOW is recomputed with P_REFINE_N resamples, same seed.
P_REFINE_BELOW, P_REFINE_N = 0.01, 400_000
OUTLIER_CENTS = 20


# ── prices ──────────────────────────────────────────────────────────────────

def cents(american):
    """American odds on one continuous scale: -110 -> -10, +110 -> +10."""
    a = np.asarray(american, float)
    return np.where(a >= 100, a - 100.0, a + 100.0)


def risk_win(price):
    d = dec(price)
    r = np.minimum(1.0 / (d - 1.0), MAX_RISK)
    return r, r * (d - 1.0)


# ── markets ─────────────────────────────────────────────────────────────────

def _lookup(market, table: dict) -> np.ndarray:
    m = pd.Series(np.asarray(market, dtype=object), dtype=object)
    out = m.map(table)
    if out.isna().any():
        raise KeyError(f"unknown market(s) {sorted(set(m[out.isna()].astype(str)))}: "
                       "name each in MARKET_SPEC before pricing or grading it")
    return out.to_numpy(dtype=object)


def kind(market) -> np.ndarray:
    """ml / spread / total per row, for every market the harness grades."""
    return _lookup(market, _KIND)


def scope(market) -> np.ndarray:
    """game / h1 / q1 / home_team / away_team: what settles each row."""
    return _lookup(market, _SCOPE)


def threshold(market, side_a_line):
    """t for side A from the stored number, any market: side A wins when its
    quantity (the home margin, or the total) is above t. A spread's stored
    number is the HOME number, so t = -spread_home; a total's t is the number."""
    line = np.asarray(side_a_line, float)
    return np.where(kind(market) == "spread", -line, line)


def settling_scores(market, frame: pd.DataFrame):
    """(settled like, home, away) per row: the full-game market each row
    settles like and the two numbers it settles on.

    full game: the final scores (overtime counted). First half: each team's
    Q1 + Q2 points; first quarter: its Q1 points (with_periods). Team total:
    that team's own final score (overtime counted) as `home` and 0 as `away`,
    so the "total" it settles on is that team's points alone."""
    m = np.asarray(market, dtype=object)
    sc = scope(m)
    home = frame["home_score"].to_numpy(float).copy()
    away = frame["away_score"].to_numpy(float).copy()
    for part, (hc, ac) in _PERIOD_OF.items():
        sel = sc == part
        if not sel.any():
            continue
        if hc not in frame or ac not in frame:
            raise KeyError(f"{part} markets settle on period scores and the games carry none: "
                           "pass the games through H.with_periods first")
        home[sel] = frame[hc].to_numpy(float)[sel]
        away[sel] = frame[ac].to_numpy(float)[sel]
    at = sc == "away_team"
    home[at] = frame["away_score"].to_numpy(float)[at]
    away[at | (sc == "home_team")] = 0.0
    return _lookup(kind(m), KIND_MARKET), home, away


# ── loading ─────────────────────────────────────────────────────────────────

@dataclass
class Data:
    games: pd.DataFrame
    quotes: pd.DataFrame            # full-game, pre-game, every book, with fetch_at
    fetches: pd.DataFrame           # (game_id, fetch_at, lead_min): fetches listing the game
    notes: dict = field(default_factory=dict)


def load_games(cache: Path = CACHE) -> pd.DataFrame:
    g = pd.read_parquet(cache / "nba_games.parquet")
    g = g[g["home_score"].notna() & g["commence_time"].notna()].copy()
    g["tip"] = pd.to_datetime(g["commence_time"], utc=True)
    g["season"] = g["season"].astype(int)
    return g[["game_id", "season", "game_date", "tip", "home_team", "away_team",
              "home_score", "away_score"]].reset_index(drop=True)


def with_periods(games: pd.DataFrame, cache: Path = CACHE,
                 periods: pd.DataFrame | None = None) -> pd.DataFrame:
    """`games` plus home_q1, away_q1, home_h1, away_h1: the points that settle
    the first-quarter and first-half markets (nba_period_scores rows:
    game_id, period, home_points, away_points).

    The first search's rule for trusting a game's periods is kept, by calling
    it (scripts/nba_derivative_lab.build_outcomes): the periods sum to the
    stored final score, are numbered 1..n with n >= 4, and periods 1 and 2 are
    both there. A game that fails it gets no period points (NaN), and grade()
    refuses its first-half and first-quarter bets rather than guess."""
    per = pd.read_parquet(cache / "nba_period_scores.parquet") if periods is None else periods
    g = games.drop(columns=[c for c in PERIOD_COLS if c in games])
    # went_to_ot only feeds build_outcomes' own report column, never its rule
    o = build_outcomes(g[["game_id", "season", "home_score", "away_score"]].assign(went_to_ot=np.nan),
                       per, {})
    names = {"hq1": "home_q1", "aq1": "away_q1", "hh1": "home_h1", "ah1": "away_h1"}
    o = o.loc[o["ok"].astype(bool), ["game_id", *names]].rename(columns=names)
    return g.merge(o.astype({c: float for c in PERIOD_COLS}), on="game_id", how="left")


def attach_fetch(quotes: pd.DataFrame, ledger: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """fetch_at for every row: the ledger instant whose pulled_at = created_at.

    A row with no ledger match (a snapshot re-bought later moves pulled_at) is
    given the first ledger instant at or after its own snapshot_at -- the fetch
    that could have returned it -- and counted."""
    q = quotes.copy()
    led = ledger[["requested_at", "pulled_at"]].dropna().copy()
    led["pulled_at"] = pd.to_datetime(led["pulled_at"], utc=True)
    led["requested_at"] = pd.to_datetime(led["requested_at"], utc=True)
    by_pull = led.drop_duplicates("pulled_at").set_index("pulled_at")["requested_at"]
    q["created_at"] = pd.to_datetime(q["created_at"], utc=True, format="mixed")
    q["fetch_at"] = q["created_at"].map(by_pull)
    miss = q["fetch_at"].isna()
    if miss.any():
        inst = np.sort(led["requested_at"].unique())
        snap = q.loc[miss, "snapshot_at"].to_numpy(dtype="datetime64[ns]")
        i = np.searchsorted(inst.astype("datetime64[ns]"), snap, side="left")
        ok = i < len(inst)
        fill = pd.Series(pd.NaT, index=q.index[miss], dtype="datetime64[ns, UTC]")
        fill[ok] = pd.to_datetime(inst[i[ok]], utc=True)
        q.loc[miss, "fetch_at"] = fill
    notes = {"rows": int(len(q)), "rows_matched_on_created_at": int((~miss).sum()),
             "rows_placed_by_snapshot": int(miss.sum())}
    return q, notes


MIN_PRICED_SHARE, MAX_PLACED_SHARE = 0.90, 0.05


def load(cache: Path = CACHE, seasons=None, require_seasons=None) -> Data:
    """Games, full-game quotes and the fetches that bought them.

    `require_seasons`: a graded run names the seasons it needs; the load
    refuses when any of them has a price on fewer than 90% of its games, or
    when more than 5% of rows match no purchase record (both mean the cache
    predates the purchases or the ledger)."""
    g = load_games(cache)
    if seasons is not None:
        g = g[g["season"].isin(list(seasons))]
    o = pd.read_parquet(cache / "nba_odds.parquet")
    o = o[o["market"].isin(MARKETS) & (o["source"] == "odds_api_historical")
          & (o["snapshot_type"] != "in_play")].copy()
    o["snapshot_at"] = pd.to_datetime(o["snapshot_at"], utc=True)
    o = o.merge(g[["game_id", "season", "game_date", "tip"]], on="game_id")
    led = pd.read_parquet(cache / "nba_fetch_ledger.parquet")
    o, notes = attach_fetch(o, led)
    o = o[o["fetch_at"].notna() & (o["snapshot_at"] < o["tip"]) & (o["fetch_at"] < o["tip"])]
    o = o.rename(columns={"bookmaker": "book"})
    o["line"] = np.where(o["market"] == "spreads", o["spread_home"],
                         np.where(o["market"] == "totals", o["total_line"], np.nan))
    o["price_a"] = np.where(o["market"] == "totals", o["over_price"], o["home_price"])
    o["price_b"] = np.where(o["market"] == "totals", o["under_price"], o["away_price"])
    o = o[o["price_a"].notna() & o["price_b"].notna()]
    s = imp(o["price_a"]) + imp(o["price_b"])
    o["coherent"] = (s >= COHERENT[0]) & (s <= COHERENT[1])
    keep = ["game_id", "season", "game_date", "tip", "market", "book", "snapshot_at",
            "fetch_at", "line", "price_a", "price_b", "coherent"]
    o = o[keep].reset_index(drop=True)
    f = o[["game_id", "tip", "fetch_at"]].drop_duplicates(["game_id", "fetch_at"]).copy()
    f["lead_min"] = (f["tip"] - f["fetch_at"]).dt.total_seconds() / 60.0
    notes["games"] = int(g["game_id"].nunique())
    priced = g["game_id"].isin(set(o["game_id"])).groupby(g["season"]).mean()
    notes["games_priced_share"] = {int(k): round(float(v), 4) for k, v in priced.items()}
    notes["placed_by_snapshot_share"] = (notes["rows_placed_by_snapshot"] / notes["rows"]
                                         if notes["rows"] else 0.0)
    if require_seasons is not None:
        # A stale or partial cache (a ledger that misses a season) drops that
        # season's quotes without a sound; a graded run must refuse instead.
        short = {int(s): notes["games_priced_share"].get(int(s), 0.0) for s in require_seasons
                 if notes["games_priced_share"].get(int(s), 0.0) < MIN_PRICED_SHARE}
        if short:
            raise RuntimeError(f"cache prices too few games in {short} (need {MIN_PRICED_SHARE:.0%}); "
                               "refresh it with scripts.nba_research_cache --only lines")
        if notes["placed_by_snapshot_share"] > MAX_PLACED_SHARE:
            raise RuntimeError(f"{notes['placed_by_snapshot_share']:.1%} of rows matched no purchase "
                               f"record (limit {MAX_PLACED_SHARE:.0%}): the ledger cache is stale")
    return Data(games=g.reset_index(drop=True), quotes=o, fetches=f.reset_index(drop=True),
                notes=notes)


PER_EVENT_SOURCE = "odds_api_nba_derivative_history"


def load_per_event(games: pd.DataFrame, cache: Path = CACHE,
                   source: str = PER_EVENT_SOURCE, require_seasons=None) -> pd.DataFrame:
    """Rows bought ONE GAME AT A TIME (first half, first quarter, team totals).

    These have no slate ledger: the per-game purchase asked for tip - 60 and
    stored the feed's own snapshot time as snapshot_at, so that stamp IS the
    moment the price was available and fetch_at = snapshot_at. Same columns as
    load().quotes; `market` keeps its stored name (team_totals_home, ...); the
    over / under (or home / away) prices are price_a / price_b. Only the
    markets in DERIVATIVE_MARKETS are kept.

    `require_seasons`: as in load(), a graded run names the seasons it needs
    and the load refuses when any of them has a derivative price on fewer than
    90% of its games (a purchase still running, or a cache that predates it)."""
    o = pd.read_parquet(cache / "nba_odds.parquet")
    o = o[(o["source"] == source) & (o["snapshot_type"] != "in_play")
          & o["market"].isin(DERIVATIVE_MARKETS)].copy()
    o["snapshot_at"] = pd.to_datetime(o["snapshot_at"], utc=True)
    o = o.merge(games[["game_id", "season", "game_date", "tip"]], on="game_id")
    o = o[o["snapshot_at"] < o["tip"]].rename(columns={"bookmaker": "book"})
    o["fetch_at"] = o["snapshot_at"]
    ou = o["over_price"].notna()
    o["line"] = np.where(o["spread_home"].notna(), o["spread_home"], o["total_line"])
    o["price_a"] = np.where(ou, o["over_price"], o["home_price"])
    o["price_b"] = np.where(ou, o["under_price"], o["away_price"])
    o = o[o["price_a"].notna() & o["price_b"].notna()]
    sm = imp(o["price_a"]) + imp(o["price_b"])
    o["coherent"] = (sm >= COHERENT[0]) & (sm <= COHERENT[1])
    if require_seasons is not None:
        share = games["game_id"].isin(set(o["game_id"])).groupby(games["season"]).mean()
        short = {int(s): round(float(share.get(int(s), 0.0)), 4) for s in require_seasons
                 if share.get(int(s), 0.0) < MIN_PRICED_SHARE}
        if short:
            raise RuntimeError(f"derivative prices on too few games in {short} "
                               f"(need {MIN_PRICED_SHARE:.0%}); refresh the cache after the purchase")
    return o[["game_id", "season", "game_date", "tip", "market", "book", "snapshot_at",
              "fetch_at", "line", "price_a", "price_b", "coherent"]].reset_index(drop=True)


def per_event_times(pe: pd.DataFrame, point: str = "D") -> pd.DataFrame:
    """(game_id, T, lead_min): each game's per-game purchase, kept only when it
    falls inside the decision point's window (D: 45-75 minutes before tip)."""
    f = pe[["game_id", "tip", "fetch_at"]].drop_duplicates(["game_id", "fetch_at"])
    f = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60.0)
    lo, hi = POINTS[point]
    f = f[(f["lead_min"] >= lo) & (f["lead_min"] <= hi)]
    f = f.sort_values(["game_id", "fetch_at"]).drop_duplicates("game_id", keep="last")
    return f.rename(columns={"fetch_at": "T"})[["game_id", "T", "lead_min"]].reset_index(drop=True)


# ── decision points ─────────────────────────────────────────────────────────

def decision_times(fetches: pd.DataFrame, games: pd.DataFrame, point: str) -> pd.DataFrame:
    """(game_id, T, lead_min) for one decision point; a game with none is absent."""
    f = fetches[fetches["lead_min"] >= MIN_LEAD]
    if point == "A":
        day = games.set_index("game_id")["game_date"].astype(str)
        want = pd.to_datetime(f["game_id"].map(day) + "T15:00:00", utc=True)
        f = f[f["fetch_at"] == want]
    else:
        lo, hi = POINTS[point]
        f = f[(f["lead_min"] >= lo) & (f["lead_min"] <= hi)]
    f = f.sort_values(["game_id", "fetch_at"]).drop_duplicates("game_id", keep="last")
    return f.rename(columns={"fetch_at": "T"})[["game_id", "T", "lead_min"]].reset_index(drop=True)


def visible(quotes: pd.DataFrame, times: pd.DataFrame) -> pd.DataFrame:
    """The quote each (game, market, book) shows at its game's T."""
    x = quotes.merge(times[["game_id", "T"]], on="game_id")
    x = x[(x["fetch_at"] <= x["T"])
          & (x["snapshot_at"] >= x["T"] - pd.Timedelta(minutes=STALE_MIN))]
    x = x.sort_values(["game_id", "market", "book", "snapshot_at", "fetch_at"])
    return x.drop_duplicates(["game_id", "market", "book"], keep="last").reset_index(drop=True)


def offers(vis: pd.DataFrame) -> pd.DataFrame:
    """Two rows per visible coherent quote, one per side: (side, line, price).
    Sides per market: home / away for h2h_* and spreads_*, over / under for
    totals_* and team totals (SIDE_A, SIDE_B)."""
    v = vis[vis["coherent"]]
    kind(v["market"])                                   # an unnamed market stops here
    a = v.assign(side=v["market"].map(SIDE_A), price=v["price_a"])
    b = v.assign(side=v["market"].map(SIDE_B), price=v["price_b"])
    out = pd.concat([a, b], ignore_index=True).drop(columns=["price_a", "price_b"])
    return out


# ── fair probabilities ──────────────────────────────────────────────────────

class ResidDist:
    """The EMPIRICAL distribution of a side-A quantity around its centre (§6.3:
    "priced ... through the empirical margin/total distribution").

    Built from residuals r = result - centre on seasons BEFORE the graded one,
    re-centred on zero (the spread, not the average miss):
    for the market's own pricing (market_fair, the blind bet, closing value,
    F2, F6a, F6d) the centre is Pinnacle's closing number (close_dist); for a
    market-independent projection (F1, F1b, F5) it is that projection, so the
    model is priced with its own error, never the market's (dist_by_season).

    The result is an integer; a centre is not. Each residual placed at mu + r
    is split between the two integers around it in proportion to distance,
    which keeps push mass at whole-number lines and none at half-point ones.
    P(win) depends only on d = t - mu (whole t and half t tabulated apart), so
    both are tabulated once on a 0.01 grid and read by interpolation."""

    STEP, LIM = 0.01, 80.0

    def __init__(self, resid, label: str = ""):
        r = np.asarray(resid, float)
        r = r[np.isfinite(r)]
        if len(r) < 50:
            raise ValueError(f"{label}: {len(r)} residuals is too few for an empirical distribution")
        # The SPREAD of results around the centre, not their earlier average
        # miss: uncentred, a projection's past bias would move its centre a
        # second time (it is already in the calibration). For market pricing
        # the centre is solved from the price, so centring changes nothing there.
        self.mean = float(r.mean())
        r = r - self.mean
        self.n, self.sd, self.label = len(r), float(r.std()), label
        self.d = np.arange(-self.LIM, self.LIM + self.STEP / 2, self.STEP)
        self.win_whole, self.push_whole = self._table(r, 0.0)
        self.win_half, _ = self._table(r, 0.5)

    def _table(self, r, t):
        win, push = np.empty(len(self.d)), np.empty(len(self.d))
        for i in range(0, len(self.d), 400):
            mu = t - self.d[i:i + 400, None]
            x = mu + r[None, :]
            lo = np.floor(x)
            fr = x - lo
            win[i:i + 400] = ((1 - fr) * (lo > t) + fr * (lo + 1 > t)).mean(1)
            push[i:i + 400] = ((1 - fr) * (lo == t) + fr * (lo + 1 == t)).mean(1)
        return win, push

    def probs(self, mu, t):
        """(P side A wins, P push, P side A loses) at threshold t, centre mu."""
        mu, t = np.asarray(mu, float), np.asarray(t, float)
        d = t - mu
        whole = np.isclose(t, np.round(t))
        win = np.where(whole, np.interp(d, self.d, self.win_whole), np.interp(d, self.d, self.win_half))
        push = np.where(whole, np.interp(d, self.d, self.push_whole), 0.0)
        return win, push, np.clip(1.0 - win - push, 0.0, 1.0)

    def __repr__(self):
        return f"ResidDist({self.label}, n={self.n}, sd={self.sd:.2f})"


def _groups(sigma):
    """Row groups by pricing model: (mask, None, float sigmas) for the normal
    model, (mask, ResidDist, None) for each empirical distribution present."""
    s = np.asarray(sigma, dtype=object)
    emp = np.array([isinstance(v, ResidDist) for v in s], bool)
    out = []
    if (~emp).any():
        fl = np.array([np.nan if (v is None or isinstance(v, ResidDist)) else float(v) for v in s])
        out.append((~emp, None, fl))
    if emp.any():
        ids = np.array([id(v) if isinstance(v, ResidDist) else 0 for v in s])
        for i in np.unique(ids[emp]):
            m = ids == i
            out.append((m, s[np.argmax(m)], None))
    return out


def probs_any(mu, sigma, t):
    """probs_at for float sigmas, the empirical table where sigma is a ResidDist."""
    mu, t = np.asarray(mu, float), np.asarray(t, float)
    w, p, l = (np.full(mu.shape, np.nan) for _ in range(3))
    for m, dist, fl in _groups(sigma):
        if dist is None:
            w[m], p[m], l[m] = probs_at(mu[m], fl[m], t[m])
        else:
            w[m], p[m], l[m] = dist.probs(mu[m], t[m])
    return w, p, l


def solve_any(t, p_cond, sigma, iters: int = 60):
    """The centre mu at which side A's no-push win share is p_cond, either model."""
    t, p_cond = np.asarray(t, float), np.asarray(p_cond, float)
    out = np.full(t.shape, np.nan)
    for m, dist, fl in _groups(sigma):
        if dist is None:
            out[m] = solve_mu(t[m], p_cond[m], fl[m])
            continue
        lo, hi = t[m] - 60.0, t[m] + 60.0
        for _ in range(iters):
            mid = 0.5 * (lo + hi)
            w, _, l = dist.probs(mid, t[m])
            c = w / np.maximum(w + l, 1e-12)
            lo = np.where(c < p_cond[m], mid, lo)
            hi = np.where(c >= p_cond[m], mid, hi)
        out[m] = 0.5 * (lo + hi)
    return out


def dist_by_season(resid: pd.DataFrame, seasons, min_prior: int = 300) -> dict:
    """(season, market) -> ResidDist from `resid` (season, market, resid) on the
    seasons BEFORE each one; the season's own rows only when fewer than
    `min_prior` earlier rows exist (2020-21, which is reported, never chosen)."""
    out = {}
    for s in sorted(int(x) for x in seasons):
        for m in sorted(set(resid["market"])):
            rm = resid[resid["market"] == m]
            prior = rm[rm["season"] < s]
            src = "prior"
            if len(prior) < min_prior:
                prior, src = rm[rm["season"] == s], "own season"
            if len(prior) >= 50:
                out[(s, m)] = ResidDist(prior["resid"].to_numpy(), f"{s} {m} ({src})")
    return out


def side_probs(market, side, line, mu=None, sigma=None, p_home=None):
    """(P win, P push) for a side at a stored side-A number.

    spreads/totals (any period, team totals): the side-A quantity (home margin,
    or the total) ~ Normal(mu, sigma) or the empirical distribution in sigma,
    integer-continuity as in the first search. Moneylines (any period): p_home.
    A first-half or first-quarter p_home is the home side's share of the
    decided outcomes (a level period voids, as the two-way no-vig price
    reads), so its EV is per unit risked given no void."""
    market, side = np.asarray(market), np.asarray(side)
    a_side = (side == "home") | (side == "over")
    pw = np.full(market.shape, np.nan)
    pp = np.zeros(market.shape)
    ml = kind(market) == "ml"
    if p_home is not None:
        ph = np.asarray(p_home, float)
        pw = np.where(ml, np.where(a_side, ph, 1.0 - ph), pw)
    if mu is not None:
        t = threshold(market, line)
        w, push, lose = probs_any(np.asarray(mu, float), sigma, t)
        pw = np.where(~ml, np.where(a_side, w, lose), pw)
        pp = np.where(~ml, push, pp)
    return pw, pp


def with_ev(off: pd.DataFrame) -> pd.DataFrame:
    """ev per unit risked from p_win / p_push columns."""
    d = dec(off["price"])
    p_lose = 1.0 - off["p_win"] - off["p_push"]
    return off.assign(ev=off["p_win"] * (d - 1.0) - p_lose)


REAL_SIDES = ("home", "away", "over", "under")


def side_mask(c: pd.DataFrame, sides) -> pd.Series:
    """Offers on the requested sides. A real side (home/away/over/under) keeps
    that side. Any other label -- a rule's "fade", "favourite", "against" --
    is a PER-GAME side: it keeps the offers whose real `side` equals the row's
    `side_pick` (a rule family's column; shuffle_within_date moves it with the
    rule's strength). The real side stays on every row, so pricing and
    settlement never see the label."""
    real = [s for s in sides if s in REAL_SIDES]
    keep = c["side"].isin(real)
    if len(real) < len(sides):
        if "side_pick" not in c:
            raise KeyError(f"per-game side {sorted(set(sides) - set(real))} needs a side_pick column")
        keep = keep | c["side"].eq(c["side_pick"])
    return keep


def choose(cand: pd.DataFrame, cut: float, books=BETTABLE, sides=None) -> pd.DataFrame:
    """One bet per (game, market): the best-EV offer at an allowed book.

    `cand` holds offers with p_win, p_push (with_ev adds ev). Ties go to the
    earlier book in BEST_LINE_BOOKMAKERS. `sides`: see side_mask."""
    c = cand[cand["book"].isin(books) & (cand["price"] >= PRICE_FLOOR)]
    if sides is not None:
        c = c[side_mask(c, sides)]
    if "ev" not in c:
        c = with_ev(c)
    c = c[c["ev"] >= cut]
    c = c.assign(_r=c["book"].map(BOOK_RANK).fillna(99))
    c = c.sort_values(["game_id", "market", "ev", "_r"], ascending=[True, True, False, True])
    return c.drop_duplicates(["game_id", "market"]).drop(columns="_r").reset_index(drop=True)


# ── grading ─────────────────────────────────────────────────────────────────

def grade(bets: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """W / L / P, units and risk per bet, by market (settling_scores).

    Full game: the final scores, as the first search settled them. First half,
    first quarter: the period points `games` carries (with_periods); a level
    period voids a two-way moneyline (P: stake back, out of the denominator).
    Team totals: that team's final score. A derivative bet whose numbers are
    missing (no trustworthy period scores) stops the grade."""
    if len(bets) == 0:
        return bets.assign(result=[], units=[], risk=[], risk_kept=[])
    sc = scope(bets["market"])
    periods = [c for c in PERIOD_COLS if c in games] if np.isin(sc, ("h1", "q1")).any() else []
    b = bets.drop(columns=[c for c in ("home_score", "away_score", *periods) if c in bets]).merge(
        games[["game_id", "home_score", "away_score", *periods]], on="game_id")
    if periods or (sc != "game").any():
        base, home, away = settling_scores(b["market"], b)
        deriv = scope(b["market"]) != "game"
        bad = deriv & ~(np.isfinite(home) & np.isfinite(away))
        if bad.any():
            raise ValueError(f"{int(bad.sum())} derivative bets have no settling score "
                             f"(games {sorted(set(b.loc[bad, 'game_id']))[:5]}): their period "
                             "scores fail with_periods' check or are missing")
        res = settle(base, b["side"].to_numpy(), b["line"].to_numpy(), home, away)
        # a level first half or first quarter voids the two-way moneyline
        void = deriv & (kind(b["market"]) == "ml") & (home == away)
        res[void] = "P"
        b = b.drop(columns=periods)
    else:
        res = settle(b["market"].to_numpy(), b["side"].to_numpy(), b["line"].to_numpy(),
                     b["home_score"].to_numpy(), b["away_score"].to_numpy())
    r, w = risk_win(b["price"])
    units = np.where(res == "W", w, np.where(res == "L", -r, 0.0))
    return b.assign(result=res, units=units, risk=np.where(res == "P", 0.0, r), risk_kept=r)


def roi(b: pd.DataFrame, kept: bool = False) -> float:
    r = b["risk_kept" if kept else "risk"].sum()
    return float(b["units"].sum() / r) if r > 0 else np.nan


def boot(b: pd.DataFrame, n: int = N_BOOT, seed: int = SEED) -> np.ndarray:
    """Whole-day bootstrap ROIs (units over non-push risk)."""
    d = b.groupby("game_date").agg(u=("units", "sum"), r=("risk", "sum"))
    U, R = d["u"].to_numpy(), d["r"].to_numpy()
    rng = np.random.default_rng(seed)
    out = np.empty(n)
    step = max(1, 2_000_000 // max(len(d), 1))
    for i in range(0, n, step):
        k = min(step, n - i)
        idx = rng.integers(0, len(d), size=(k, len(d)))
        rs = R[idx].sum(1)
        out[i:i + k] = np.where(rs > 0, U[idx].sum(1) / np.where(rs > 0, rs, 1), 0.0)
    return out


def p_one_sided(b: pd.DataFrame) -> float:
    """P(ROI <= 0) under the whole-day bootstrap; refined where BH needs it."""
    if len(b) == 0 or b["risk"].sum() == 0:
        return 1.0
    p = float((boot(b) <= 0).mean())
    if p < P_REFINE_BELOW:
        p = float((boot(b, n=P_REFINE_N) <= 0).mean())
    return p


def ci95(b: pd.DataFrame) -> tuple[float, float]:
    """Whole-day bootstrap 95% interval of ROI (the house standard, §6.7)."""
    if len(b) == 0 or b["risk"].sum() == 0:
        return (np.nan, np.nan)
    x = boot(b)
    return float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))


def ci90(b: pd.DataFrame) -> tuple[float, float]:
    if len(b) == 0 or b["risk"].sum() == 0:
        return (np.nan, np.nan)
    x = boot(b)
    return float(np.percentile(x, 5)), float(np.percentile(x, 95))


def bh_pass(p_cells: dict, m_total: int, q: float = 0.05) -> set:
    """Benjamini-Hochberg over m_total tests; cells not given are entered at p = 1."""
    items = sorted(p_cells.items(), key=lambda kv: kv[1])
    k_max = 0
    for k, (_, p) in enumerate(items, start=1):
        if p <= k * q / m_total:
            k_max = k
    return {name for name, _ in items[:k_max]}


# ── robustness and closing-line value ───────────────────────────────────────

def next_fetch_check(bets: pd.DataFrame, data: Data) -> pd.Series:
    """True where the same book shows the same number at the next fetch at a
    price at least as good (the bet was still there to be had)."""
    if len(bets) == 0:
        return pd.Series([], dtype=bool)
    f = data.fetches[data.fetches["lead_min"] >= 0].sort_values(["game_id", "fetch_at"])
    nxt = bets[["game_id", "T"]].drop_duplicates().merge(f[["game_id", "fetch_at"]], on="game_id")
    nxt = nxt[nxt["fetch_at"] > nxt["T"]].sort_values("fetch_at").drop_duplicates(
        ["game_id", "T"], keep="first").rename(columns={"fetch_at": "T_next"})
    if nxt.empty:
        return pd.Series(False, index=bets.index)
    t2 = nxt.rename(columns={"T_next": "Tn"})[["game_id", "T", "Tn"]]
    vis = visible(data.quotes, t2[["game_id", "Tn"]].rename(columns={"Tn": "T"}).drop_duplicates("game_id"))
    off = offers(vis)[["game_id", "market", "book", "side", "line", "price"]].rename(
        columns={"price": "price_next", "line": "line_next"})
    x = bets.reset_index().merge(off, on=["game_id", "market", "book", "side"], how="left")
    same = np.where(kind(x["market"]) == "ml", True,
                    np.isclose(x["line"].fillna(0), x["line_next"].fillna(np.inf)))
    ok = same & (x["price_next"].fillna(-1e9) >= x["price"])
    return pd.Series(ok, index=x["index"]).groupby(level=0).any().reindex(bets.index, fill_value=False)


def outlier_flag(bets: pd.DataFrame, cand: pd.DataFrame) -> pd.Series:
    """True where no second deciding book hangs the same number on the side, or
    the bet's price beats the next book's by more than OUTLIER_CENTS."""
    if len(bets) == 0:
        return pd.Series([], dtype=bool)
    c = cand[cand["book"].isin(BETTABLE)]
    key = ["game_id", "market", "side"]
    x = bets.reset_index()[["index", *key, "line", "book", "price"]].merge(
        c[[*key, "line", "book", "price"]].rename(columns={"book": "b2", "price": "p2", "line": "l2"}),
        on=key, how="left")
    same = (pd.Series(kind(x["market"]) == "ml", index=x.index)
            | np.isclose(x["line"].fillna(0), x["l2"].fillna(np.inf)))
    x = x[same & (x["b2"] != x["book"])]
    best_other = x.groupby("index")["p2"].max()
    gap = cents(bets["price"]) - cents(best_other.reindex(bets.index).fillna(-1e9))
    return pd.Series(gap > OUTLIER_CENTS, index=bets.index)


def pinnacle_close(data: Data) -> pd.DataFrame:
    """Pinnacle's last pre-tip coherent quote per (game, market), no-vig."""
    p = data.quotes[(data.quotes["book"] == SHARP) & data.quotes["coherent"]]
    p = p.sort_values(["fetch_at", "snapshot_at"]).drop_duplicates(["game_id", "market"], keep="last")
    ia, ib = imp(p["price_a"]), imp(p["price_b"])
    return p.assign(close_line=p["line"], close_fa=ia / (ia + ib))[
        ["game_id", "season", "market", "close_line", "close_fa", "fetch_at"]].rename(
        columns={"fetch_at": "close_at"})


def close_sigma(close: pd.DataFrame, games: pd.DataFrame) -> dict:
    """SD of (result - Pinnacle close number) per market, fit on seasons before S."""
    c = close_resid(close, games)
    markets = ("spreads", "totals") + tuple(sorted(set(c["market"]) - {"spreads", "totals"}))
    sig = {}
    for s in sorted(games["season"].unique()):
        for m in markets:
            prior = c[(c["market"] == m) & (c["season"] < s)]
            if len(prior) < 300:
                prior = c[(c["market"] == m) & (c["season"] == s)]
            sig[(int(s), m)] = float(prior["resid"].std())
    return sig


def close_resid(close: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """(season, market, resid): result minus Pinnacle's closing number, side A
    -- the home margin plus the home number for a spread, the total minus the
    number for a total -- each settled on its own scores (settling_scores:
    the first half's for spreads_h1, the team's own for a team total). A row
    with no settling score (a game whose periods fail with_periods) is left out."""
    c = close[kind(close["market"]) != "ml"]
    sc = scope(c["market"])
    periods = [p for p in PERIOD_COLS if p in games] if np.isin(sc, ("h1", "q1")).any() else []
    c = c.merge(games[["game_id", "home_score", "away_score", *periods]], on="game_id")
    base, home, away = settling_scores(c["market"], c)
    x = np.where(base == "spreads", home - away, home + away)
    resid = x - threshold(c["market"], c["close_line"])
    ok = np.isfinite(resid)
    return pd.DataFrame({"season": c["season"].astype(int).to_numpy()[ok],
                         "market": c["market"].to_numpy()[ok], "resid": resid[ok]})


def close_dist(close: pd.DataFrame, games: pd.DataFrame) -> dict:
    """(season, market) -> the EMPIRICAL distribution of the result around
    Pinnacle's close, from seasons before S: the market's own pricing (§6.3).
    A drop-in for close_sigma wherever a `sig` dict is taken."""
    return dist_by_season(close_resid(close, games), games["season"].unique())


def clv(bets: pd.DataFrame, close: pd.DataFrame, sig: dict) -> pd.Series:
    """EV of the bet's price at Pinnacle's no-vig close (moved number: the
    pricing model in `sig`, normal or empirical)."""
    if len(bets) == 0:
        return pd.Series([], dtype=float)
    x = bets.reset_index().merge(close.drop(columns="season"), on=["game_id", "market"], how="left")
    x = x[x["close_at"] > x["T"]]
    a_side = x["side"].isin(["home", "over"])
    p_a = x["close_fa"].to_numpy()
    sigma = np.array([sig.get((int(s), m), 1.0) for s, m in zip(x["season"], x["market"])],
                     dtype=object)
    ml = kind(x["market"]) == "ml"
    same = ml | np.isclose(x["line"].fillna(0), x["close_line"].fillna(np.inf))
    tc = threshold(x["market"], x["close_line"])
    mu = solve_any(tc, p_a, sigma)
    w, push, lose = probs_any(mu, sigma, threshold(x["market"], x["line"]))
    pw_same = np.where(a_side, p_a, 1 - p_a)
    pw = np.where(same, pw_same, np.where(a_side, w, lose))
    pp = np.where(same, 0.0, push)
    d = dec(x["price"])
    ev = pw * (d - 1.0) - (1.0 - pw - pp)
    return pd.Series(ev, index=x["index"]).reindex(bets.index)


# ── one cell, every bar the section names ───────────────────────────────────

def summarise(b: pd.DataFrame) -> dict:
    """Bets, units, ROI (push risk out / kept), per season, CI and halves."""
    out = {"bets": int(len(b)), "pushes": int((b.get("result") == "P").sum()) if len(b) else 0,
           "units": float(b["units"].sum()) if len(b) else 0.0,
           "roi": roi(b) if len(b) else np.nan, "roi_kept": roi(b, kept=True) if len(b) else np.nan}
    for s in sorted(set(b["season"])) if len(b) else []:
        bs = b[b["season"] == s]
        out[f"n_{s}"], out[f"u_{s}"], out[f"roi_{s}"] = int(len(bs)), float(bs["units"].sum()), roi(bs)
    return out


def cell_report(bets_all: pd.DataFrame, data: Data, cand: pd.DataFrame | None = None,
                close: pd.DataFrame | None = None, sig: dict | None = None,
                choose_seasons=CHOOSE) -> dict:
    """Everything §6.2/§6.4 asks of one cell. `bets_all` is graded, every season.
    `choose_seasons`: the seasons cuts are chosen on (F6b and F6d have fewer)."""
    ch = bets_all[bets_all["season"].isin(choose_seasons)]
    cf = bets_all[bets_all["season"] == CONFIRM]
    r = {"choose": summarise(ch), "confirm": summarise(cf),
         "regime_2021": summarise(bets_all[bets_all["season"] == REGIME])}
    r["choose"]["ci90"] = ci90(ch)
    r["confirm"]["ci90"] = ci90(cf)
    r["p_confirm"] = p_one_sided(cf)
    r["p_choose"] = p_one_sided(ch)
    if len(ch):
        days = np.sort(ch["game_date"].unique())
        mid = days[len(days) // 2]
        r["half_early_roi"] = roi(ch[ch["game_date"] < mid])
        r["half_late_roi"] = roi(ch[ch["game_date"] >= mid])
        r["seasons_positive"] = all(
            (roi(ch[ch["season"] == s]) > 0) for s in choose_seasons
            if (ch["season"] == s).sum() >= 30)
        sides = ch["side"].value_counts(normalize=True)
        r["top_side"], r["top_share"] = str(sides.index[0]), float(sides.iloc[0])
    # §6.7: every graded season pooled (the choosing seasons and 2025-26).
    pool_seasons = tuple(choose_seasons) + (CONFIRM,)
    pl = bets_all[bets_all["season"].isin(pool_seasons)]
    r["pool"] = summarise(pl)
    r["pool"]["ci95"] = ci95(pl)
    per = [(s, pl[pl["season"] == s]) for s in pool_seasons]
    counted = [(s, x) for s, x in per if len(x) >= 30]
    r["pool"]["seasons_counted"] = len(counted)
    r["pool"]["seasons_positive"] = sum(1 for _, x in counted if roi(x) > 0)
    if close is not None and sig is not None and len(pl):
        ev = clv(pl, close, sig)
        r["pool"]["clv_median"] = float(np.nanmedian(ev)) if ev.notna().any() else np.nan
    if len(bets_all):
        still = next_fetch_check(bets_all, data)
        r["units_still_offered"] = float(bets_all.loc[still, "units"].sum())
        r["share_still_offered"] = float(still.mean())
        if cand is not None:
            out = outlier_flag(bets_all, cand)
            r["units_without_outliers"] = float(bets_all.loc[~out, "units"].sum())
            r["share_outlier"] = float(out.mean())
        if close is not None and sig is not None and len(ch):
            ev = clv(ch, close, sig)
            r["clv_median"] = float(np.nanmedian(ev)) if ev.notna().any() else np.nan
            r["clv_share_positive"] = float((ev > 0).mean()) if ev.notna().any() else np.nan
            r["clv_n"] = int(ev.notna().sum())
    return r


# ── the market's own fair price, placebo, blind side, and the cell runner ────

def market_fair(vis: pd.DataFrame, sig: dict) -> pd.DataFrame:
    """The market's fair line at T per (game, market): Pinnacle's no-vig when it
    quotes coherently, else the median over the deciding books. It ranks a
    rule's offers (which number and price is best) and is the blind baseline's
    chooser; it is never a model's own probability.

    spreads/totals (any period, team totals): mu of the side-A quantity solved
    from each quote's no-vig probability at its own number, through sig[(season,
    market)]; moneylines (any period): p_home."""
    v = vis[vis["coherent"] & vis["book"].isin((SHARP, *BETTABLE))].copy()
    if v.empty:
        return pd.DataFrame(columns=["game_id", "market", "mu", "sigma", "p_home", "ref"])
    ia, ib = imp(v["price_a"]), imp(v["price_b"])
    v["fa"] = ia / (ia + ib)
    k = kind(v["market"])
    v["sigma"] = pd.Series([sig.get((int(se), m), np.nan) if kk != "ml" else np.nan
                            for se, m, kk in zip(v["season"], v["market"], k)],
                           index=v.index, dtype=object)
    sp = k != "ml"
    mu = np.full(len(v), np.nan)
    if sp.any():
        x = v[sp]
        mu[sp] = solve_any(threshold(x["market"], x["line"]), x["fa"].to_numpy(),
                           x["sigma"].to_numpy())
    v["mu"] = mu
    sharp = v[v["book"] == SHARP].drop_duplicates(["game_id", "market"])
    rest = v[v["book"] != SHARP].groupby(["game_id", "market"]).agg(
        mu=("mu", "median"), fa=("fa", "median"), sigma=("sigma", "first")).reset_index()
    have = set(zip(sharp["game_id"], sharp["market"]))
    rest = rest[[k not in have for k in zip(rest["game_id"], rest["market"])]]
    out = pd.concat([sharp[["game_id", "market", "mu", "fa", "sigma"]].assign(ref="pinnacle"),
                     rest.assign(ref="consensus")], ignore_index=True)
    out["p_home"] = np.where(kind(out["market"]) == "ml", out["fa"], np.nan)
    return out.drop(columns="fa")


def fair_offers(off: pd.DataFrame, fair: pd.DataFrame) -> pd.DataFrame:
    """Offers with p_win / p_push / ev under `fair` (game_id, market, mu, sigma, p_home)."""
    x = off.merge(fair[["game_id", "market", "mu", "sigma", "p_home"]], on=["game_id", "market"])
    pw, pp = side_probs(x["market"].to_numpy(), x["side"].to_numpy(), x["line"].to_numpy(),
                        mu=x["mu"].to_numpy(), sigma=x["sigma"].to_numpy(),
                        p_home=x["p_home"].to_numpy())
    return with_ev(x.assign(p_win=pw, p_push=pp))


def shuffle_within_date(fair: pd.DataFrame, games: pd.DataFrame, rng) -> pd.DataFrame:
    """Placebo (bar 10): each game's fair parameters swapped with another game's
    on the same date in the same market; prices and results untouched."""
    f = fair.merge(games[["game_id", "game_date"]], on="game_id")
    cols = [c for c in ("mu", "sigma", "p_home", "strength", "side_pick") if c in f]
    out = []
    for _, grp in f.groupby(["game_date", "market"], sort=False):
        g2 = grp.copy()
        perm = rng.permutation(len(grp))
        # one permutation for every column (a game's numbers move together),
        # applied column by column so each keeps its own dtype and an
        # empirical distribution is moved by reference, never copied
        for c in cols:
            g2[c] = grp[c].to_numpy()[perm]
        out.append(g2)
    return pd.concat(out, ignore_index=True).drop(columns="game_date") if out else fair


def blind_side(neutral: pd.DataFrame, side: str, games: pd.DataFrame) -> pd.DataFrame:
    """Bar 9's comparison: the side bet on EVERY game in the population, at the
    best deciding offer under the market's own fair price (no model, no cut)."""
    return grade(choose(neutral, cut=-np.inf, sides=[side]), games)


GATE_POINT, GATE_MIN = "D", 0.95


def point_coverage(data: Data, point: str, times: pd.DataFrame | None = None) -> dict:
    """season -> share of the season's games with a decision at `point`."""
    t = decision_times(data.fetches, data.games, point) if times is None else times
    has = data.games["game_id"].isin(set(t["game_id"]))
    return {int(s): float(v) for s, v in has.groupby(data.games["season"]).mean().items()}


def gated_seasons(cov: dict, choose_seasons, point: str) -> tuple[tuple, list]:
    """§6.5 amendment: at D, a choosing season reached on fewer than 95% of its
    games is reported and not chosen on. (kept, dropped)."""
    if point != GATE_POINT:
        return tuple(choose_seasons), []
    kept = tuple(s for s in choose_seasons if cov.get(int(s), 0.0) >= GATE_MIN)
    return kept, [s for s in choose_seasons if s not in kept]


SPLITS = {"home": ("home", "away"), "fav": ("fav", "dog"), "over": ("over", "under")}


def fav_sides(neutral: pd.DataFrame) -> pd.DataFrame:
    """(game_id, market, fav, dog): the favourite by the MARKET's fair line at T
    (moneylines: p_home > 0.5; spreads: the home margin's centre above 0, any
    period). Totals, of any period, and team totals have none. Read from
    `neutral`, never from a result."""
    f = neutral.drop_duplicates(["game_id", "market"])[["game_id", "market", "mu", "p_home"]]
    f = f[kind(f["market"]) != "total"]
    ml = kind(f["market"]) == "ml"
    home_fav = np.where(ml, f["p_home"] > 0.5, f["mu"] > 0)
    level = np.where(ml, np.isclose(f["p_home"], 0.5), np.isclose(f["mu"], 0.0))
    f = f.assign(fav=np.where(home_fav, "home", "away"), dog=np.where(home_fav, "away", "home"))
    return f[~level][["game_id", "market", "fav", "dog"]]


def blind_by_real_side(nm: pd.DataFrame, population: set, games: pd.DataFrame,
                       seasons) -> dict:
    """Bar 9 as §1 words it: for each real side, that side bet on every game in
    the cell's own priced population at that point (no model, no cut), at the
    best deciding offer under the market's fair line. ROI on `seasons`.

    A per-game rule passes its own frame, side_pick included, as `nm` (its
    blind_side needs it). That column is the RULE's side; the favourite split
    sets its own from the market, so the rule's is dropped first -- left in,
    the merge below would suffix both and choose() would find neither."""
    pop = nm[nm["game_id"].isin(population)].drop(columns="side_pick", errors="ignore")
    out = {}
    if pop.empty:
        return out
    fv = fav_sides(pop)
    for split, (a, b) in SPLITS.items():
        for s in (a, b):
            if split == "fav":
                if fv.empty:
                    continue
                c = pop.merge(fv[["game_id", "market", s]].rename(columns={s: "side_pick"}),
                              on=["game_id", "market"])
                bets = choose(c, -np.inf, sides=[s])
            else:
                bets = choose(pop, -np.inf, sides=[s])
            g = grade(bets, games)
            g = g[g["season"].isin(seasons)] if len(g) else g
            if len(g):
                out[s] = roi(g)
    return out


def blind_pool(nm: pd.DataFrame, population: set, games: pd.DataFrame, seasons,
               close=None, sig=None) -> dict:
    """Pooled blind bets per real side (§6.7): ROI and, where a close exists,
    the median closing-line value, so a cell's own late drift can be told from
    the market's."""
    pop = nm[nm["game_id"].isin(population)].drop(columns="side_pick", errors="ignore")
    out = {}
    if pop.empty:
        return out
    fv = fav_sides(pop)
    for split, (a, b) in SPLITS.items():
        for side in (a, b):
            if split == "fav":
                if fv.empty:
                    continue
                c = pop.merge(fv[["game_id", "market", side]].rename(columns={side: "side_pick"}),
                              on=["game_id", "market"])
                bets = choose(c, -np.inf, sides=[side])
            else:
                bets = choose(pop, -np.inf, sides=[side])
            g = grade(bets, games)
            g = g[g["season"].isin(seasons)] if len(g) else g
            if not len(g):
                continue
            out[f"blind_pool_{side}"] = roi(g)
            if close is not None and sig is not None:
                ev = clv(g, close, sig)
                out[f"blind_pool_clv_{side}"] = (float(np.nanmedian(ev))
                                                 if ev.notna().any() else np.nan)
    return out


_BET_FILES = [0]


def real_side_shares(bets: pd.DataFrame, neutral: pd.DataFrame) -> dict:
    """Shares of a cell's bets on the first side of each split, real sides."""
    out = {}
    if bets.empty:
        return out
    sides = bets["side"]
    ha = sides.isin(["home", "away"])
    if ha.any():
        out["home"] = float((sides[ha] == "home").mean())
    ou = sides.isin(["over", "under"])
    if ou.any():
        out["over"] = float((sides[ou] == "over").mean())
    fv = fav_sides(neutral[neutral["game_id"].isin(set(bets["game_id"]))])
    x = bets[ha].merge(fv, on=["game_id", "market"])
    if len(x):
        out["fav"] = float((x["side"] == x["fav"]).mean())
    return out


def run_cells(data: Data, family: str, point: str, cand: pd.DataFrame, neutral: pd.DataFrame,
              cuts, sides_by_market: dict, close=None, sig=None, placebo=None,
              strength: str = "ev", choose_seasons=CHOOSE,
              times: pd.DataFrame | None = None, market_groups: dict | None = None) -> list[dict]:
    """Grade one family at one decision point over its cut axis and sides.

    `cand`: offers with p_win / p_push / ev. A model family leaves strength="ev"
    (the cut is an EV floor on its own probabilities). A rule family passes
    offers priced at the MARKET's fair line plus a `strength` column; the cut
    then applies to strength, and the best market-fair offer is taken.
    `placebo`: re-priced `cand` frames graded at the same cuts.
    `times`: the decision times the cells used (default: the slate fetches);
    at D any choosing season they reach on fewer than 95% of games is dropped
    from `choose_seasons` and named in the row (§6.5 amendment).
    `market_groups`: {label: (market, ...)} pools several real markets into one
    cell group (§8: team totals, both teams' markets, as one cell per side and
    cut). A `sides_by_market` key that names a group takes every member's
    offers; the row's `market` is the label, while every bet keeps its real
    market, which pricing and settlement read. Keys not named run alone.
    One row per (market, side, cut) with every number section 6 reports."""
    rows = []
    cov = point_coverage(data, point, times)
    asked = tuple(choose_seasons)
    choose_seasons, dropped = gated_seasons(cov, asked, point)
    groups = market_groups or {}
    for market, sides in sides_by_market.items():
        members = tuple(groups.get(market, (market,)))
        if market in groups:
            kind(list(members))                         # a group's members must be real markets
        cm = cand[cand["market"].isin(members)]
        nm = neutral[neutral["market"].isin(members)]
        population = set(cm["game_id"])
        blinds = blind_by_real_side(nm, population, data.games, choose_seasons)
        bpool = blind_pool(nm, population, data.games, tuple(choose_seasons) + (CONFIRM,),
                           close, sig)
        dump = []
        for side in sides:
            blind = blind_side(nm, side, data.games)
            blind_ch = (roi(blind[blind["season"].isin(choose_seasons)])
                        if len(blind) else np.nan)
            for k, cut in enumerate(cuts):
                def pick(c, books=BETTABLE, cut=cut, side=side):
                    if strength == "ev":
                        return choose(c, cut, books=books, sides=[side])
                    return choose(c[c[strength] >= cut], -np.inf, books=books, sides=[side])
                g = grade(pick(cm), data.games)
                rep = cell_report(g, data, cm, close, sig, choose_seasons=choose_seasons)
                dk = grade(pick(cm, books=(DK,)), data.games)
                pl = []
                for pc in placebo or []:
                    gp = grade(pick(pc[pc["market"].isin(members)]), data.games)
                    pl.append(roi(gp[gp["season"].isin(choose_seasons)]) if len(gp) else np.nan)
                ch, cf = rep["choose"], rep["confirm"]
                shares = real_side_shares(g[g["season"].isin(choose_seasons)] if len(g) else g, nm)
                pool_shares = real_side_shares(
                    g[g["season"].isin(tuple(choose_seasons) + (CONFIRM,))] if len(g) else g, nm)
                if os.environ.get("NBA_GAME2_BETS") and len(g):
                    dump.append(g.assign(family=family, point=point, cell_side=side,
                                         cut_index=k, cut=cut))
                po = rep["pool"]
                rows.append({
                    "family": family, "point": point, "market": market, "side": side,
                    "cut_index": k, "cut": cut,
                    "choose_seasons_asked": ",".join(str(x) for x in asked),
                    "gate_dropped": ",".join(str(x) for x in dropped),
                    **{f"gate_cov_{s}": cov.get(s, 0.0) for s in (REGIME, *CHOOSE, CONFIRM)},
                    "population_games": len(population),
                    **{f"share_{k2}": shares.get(k2, np.nan) for k2 in SPLITS},
                    **{f"blind_{s}": blinds.get(s, np.nan)
                       for pair in SPLITS.values() for s in pair},
                    "n_choose": ch["bets"], "units_choose": ch["units"], "roi_choose": ch["roi"],
                    "roi_kept_choose": ch["roi_kept"],
                    "ci_lo_choose": ch["ci90"][0], "ci_hi_choose": ch["ci90"][1],
                    "n_confirm": cf["bets"], "units_confirm": cf["units"], "roi_confirm": cf["roi"],
                    "ci_lo_confirm": cf["ci90"][0], "ci_hi_confirm": cf["ci90"][1],
                    "p_confirm": rep["p_confirm"], "p_choose": rep["p_choose"],
                    "n_2021": rep["regime_2021"]["bets"], "roi_2021": rep["regime_2021"]["roi"],
                    **{f"roi_{s}": ch.get(f"roi_{s}", np.nan) for s in CHOOSE},
                    **{f"n_{s}": ch.get(f"n_{s}", 0) for s in CHOOSE},
                    "choose_seasons": ",".join(str(x) for x in choose_seasons),
                    "half_early_roi": rep.get("half_early_roi", np.nan),
                    "half_late_roi": rep.get("half_late_roi", np.nan),
                    "seasons_positive": rep.get("seasons_positive", False),
                    "blind_roi_choose": blind_ch, "placebo_rois": pl,
                    "dk_n_choose": int(dk["season"].isin(choose_seasons).sum()) if len(dk) else 0,
                    "dk_roi_choose": (roi(dk[dk["season"].isin(choose_seasons)])
                                      if len(dk) else np.nan),
                    "dk_roi_confirm": roi(dk[dk["season"] == CONFIRM]) if len(dk) else np.nan,
                    "share_still_offered": rep.get("share_still_offered", np.nan),
                    "units_still_offered": rep.get("units_still_offered", np.nan),
                    "share_outlier": rep.get("share_outlier", np.nan),
                    "units_without_outliers": rep.get("units_without_outliers", np.nan),
                    "clv_median": rep.get("clv_median", np.nan),
                    "clv_share_positive": rep.get("clv_share_positive", np.nan),
                    "clv_n": rep.get("clv_n", 0),
                    # §6.7, the house standard: every graded season pooled
                    "pool_seasons": ",".join(str(x) for x in tuple(choose_seasons) + (CONFIRM,)),
                    "pool_n": po["bets"], "pool_units": po["units"], "pool_roi": po["roi"],
                    "pool_ci95_lo": po["ci95"][0], "pool_ci95_hi": po["ci95"][1],
                    "pool_seasons_counted": po["seasons_counted"],
                    "pool_seasons_positive": po["seasons_positive"],
                    "pool_clv_median": po.get("clv_median", np.nan),
                    **{f"pool_share_{k2}": pool_shares.get(k2, np.nan) for k2 in SPLITS},
                    **{k2: bpool.get(k2, np.nan) for k2 in
                       [f"blind_pool_{s2}" for pair in SPLITS.values() for s2 in pair]
                       + [f"blind_pool_clv_{s2}" for pair in SPLITS.values() for s2 in pair]},
                })
        if dump:
            d = Path(os.environ["NBA_GAME2_BETS"])
            d.mkdir(parents=True, exist_ok=True)
            _BET_FILES[0] += 1
            keep = [c for c in ("game_id", "season", "game_date", "T", "market", "side", "book",
                                "line", "price", "ev", "p_win", "result", "units", "risk",
                                "family", "point", "cell_side", "cut_index", "cut") if c in dump[0]]
            pd.concat([x[keep] for x in dump], ignore_index=True).to_parquet(
                d / f"bets_{family}_{point}_{market}_{_BET_FILES[0]:04d}.parquet")
    return rows


def point_offers(data: Data, point: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(times, offers) at one decision point; offers carry T."""
    t = decision_times(data.fetches, data.games, point)
    return t, offers(visible(data.quotes, t))


def check() -> None:
    """Sign and arithmetic checks that must hold before any cell is read."""
    _assert_spread_sign()
    assert np.allclose(cents([-110, 110, -105, 105, 150, -200]), [-10, 10, -5, 5, 50, -100])
    r, w = risk_win([-110, 150, -400])
    assert np.allclose(r, [1.1, 1 / 1.5, 3.0]) and np.allclose(w[:2], [1.0, 1.0])
    # a period spread's stored number is the home number too
    assert np.allclose(threshold(["spreads_h1", "spreads_q1", "totals_h1", "team_totals_away"],
                                 [-3.5, 1.0, 110.5, 112.5]), [3.5, -1.0, 110.5, 112.5])
    # first half 55-55 voids both moneyline sides; the home -0.5 first-quarter spread on 30-20 wins
    g = pd.DataFrame({"game_id": ["G"], "home_score": [110.0], "away_score": [100.0],
                      "home_q1": [30.0], "away_q1": [20.0], "home_h1": [55.0], "away_h1": [55.0]})
    b = pd.DataFrame({"game_id": "G", "market": ["h2h_h1", "h2h_h1", "spreads_q1"],
                      "side": ["home", "away", "home"], "line": [np.nan, np.nan, -0.5],
                      "price": [-110.0, -110.0, -110.0]})
    assert grade(b, g)["result"].tolist() == ["P", "P", "W"]
    print("checks pass")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="arithmetic checks only")
    ap.add_argument("--coverage", action="store_true",
                    help="decision-point coverage per season (the gate before D is graded)")
    a = ap.parse_args()
    check()
    if a.coverage:
        d = load()
        print(d.notes)
        rows = []
        for pt in POINTS:
            t = decision_times(d.fetches, d.games, pt)
            cov = d.games.assign(has=d.games["game_id"].isin(t["game_id"])).groupby("season")["has"].mean()
            rows.append(cov.rename(pt))
        print(pd.concat(rows, axis=1).round(3))


if __name__ == "__main__":
    main()
