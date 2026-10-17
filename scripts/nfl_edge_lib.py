"""
Shared helpers for the NFL edge search (docs/nfl_edge_search.md).

Every backtest in that search reads the local cache built by
`python -m scripts.nfl_edge_cache` (default %TEMP%/nfl_edge) and grades with
the functions here, so price maths, de-vig, grading and intervals are the same
in every table. No database, no network, no Odds API credits.

Conventions (CLAUDE.md §4):
  * results are UNITS: one unit = one flat bet; a win at +150 pays +1.5u.
  * spreads are HOME-relative: `point` is the home team's number, so the home
    side covers when (home_score - away_score) + point > 0.
  * `result` = home_score - away_score (nflverse convention), `total` = sum.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(os.environ.get("NFL_EDGE_CACHE",
                            Path(os.environ.get("TEMP", "/tmp")) / "nfl_edge"))

# config.BETTABLE_BOOKS, resolved 2026-10-11. Pinnacle and Bovada are references,
# not venues. Kept literal so a backtest does not import config (and its env).
BETTABLE = ["draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics",
            "betrivers", "hardrockbet", "betparx"]
# Historical names for the same venues in the 2020-2025 Odds API archive.
BETTABLE_HIST = BETTABLE + ["barstool", "espnbet", "pointsbetus", "unibet_us",
                            "superbook", "wynnbet", "twinspires", "betfred"]
SHARP = ["pinnacle", "betonlineag", "lowvig", "circasports"]
# nfl/README.md book-integrity screen: confirmed bad quotes, never use.
EXCLUDED = {"betanysports", "betsson", "nordicbet", "tipico_de", "matchbook"}


# ─── prices ────────────────────────────────────────────────────────────────

def am_to_dec(a):
    a = np.asarray(a, dtype=float)
    return np.where(a > 0, 1 + a / 100.0, 1 + 100.0 / np.abs(a))


def am_to_prob(a):
    return 1.0 / am_to_dec(a)


def devig2(p1_am, p2_am, method: str = "proportional"):
    """Fair probabilities of a two-way market from two American prices."""
    q1, q2 = am_to_prob(p1_am), am_to_prob(p2_am)
    if method == "proportional":
        s = q1 + q2
        return q1 / s, q2 / s
    if method == "power":                      # q^k sums to 1
        k = np.ones_like(q1)
        for _ in range(60):
            f = q1 ** k + q2 ** k - 1
            df = q1 ** k * np.log(q1) + q2 ** k * np.log(q2)
            k = k - f / df
        return q1 ** k, q2 ** k
    raise ValueError(method)


def profit_units(won, price_am, push=None):
    """Units won on a 1-unit bet. won: 1/0 array; push: 1 where stake returned."""
    won = np.asarray(won, dtype=float)
    d = am_to_dec(price_am)
    out = np.where(won == 1, d - 1, -1.0)
    if push is not None:
        out = np.where(np.asarray(push) == 1, 0.0, out)
    return out


def ev(p, price_am):
    return p * am_to_dec(price_am) - 1


# ─── data ──────────────────────────────────────────────────────────────────

def games() -> pd.DataFrame:
    """nflverse schedules with results and closing lines, 1999-2026.
    spread_line is the HOME-favoured-positive nflverse number (home -3 => 3.0),
    so the home-relative point convention used by the odds tables is -spread_line."""
    g = pd.read_parquet(CACHE / "nflverse_games.parquet")
    g["kick"] = pd.to_datetime(g["gameday"] + " " + g["gametime"].fillna("13:00"),
                               errors="coerce").dt.tz_localize(
        "America/New_York", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    g["home_point_close"] = -g["spread_line"]
    return g


def odds_hist(markets=None) -> pd.DataFrame:
    """Game-line history 2020-2025 (Odds API snapshots every few hours), numeric."""
    d = pd.read_parquet(CACHE / "odds_hist_2020_2025.parquet")
    for c in ("point", "price_home", "price_away", "lead_hours"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d[~d["bookmaker"].isin(EXCLUDED)]
    if markets:
        d = d[d["market"].isin(markets)]
    return d


def odds_2026(markets=None, pregame_only: bool = True) -> pd.DataFrame:
    """2026 per-minute game-line archive (NFL_ prefix stripped to nflverse ids).
    pregame_only bounds on snapshot_at <= commence_time: the archive also holds
    in-play ticks (CLAUDE.md §6)."""
    d = pd.read_parquet(CACHE / "odds_2026.parquet")
    for c in ("point", "price_home", "price_away"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["game_id"] = d["game_id"].str.replace("^NFL_", "", regex=True)
    d["lead_hours"] = (d["commence_time"] - d["snapshot_at"]).dt.total_seconds() / 3600
    if pregame_only:
        d = d[d["lead_hours"] >= 0]
    d = d[~d["bookmaker"].isin(EXCLUDED)]
    if markets:
        d = d[d["market"].isin(markets)]
    return d


def at_lead(d: pd.DataFrame, lead_h: float, keys=("game_id", "bookmaker", "market")) -> pd.DataFrame:
    """Latest quote per key at or before kickoff - lead_h hours (no look-ahead)."""
    x = d[d["lead_hours"] >= lead_h]
    return x.sort_values("snapshot_at").groupby(list(keys), as_index=False).tail(1)


def props_hist() -> pd.DataFrame:
    """Prop quotes 2023 - 2026-09-09 (the main checkout's parquet, which holds
    history Supabase has pruned). snapshot_type 'open' rows include in-play
    quotes; bound on kickoff before use."""
    d = pd.read_parquet(CACHE / "local_nfl_prop_odds.parquet")
    d["snapshot_at"] = pd.to_datetime(d["snapshot_at"], utc=True, errors="coerce", format="mixed")
    return d


def props_market(market: str) -> pd.DataFrame:
    """props_hist() for ONE market (e.g. 'player_pass_yds'), from the per-market
    split under props_by_market/. Same rows, a fraction of the memory."""
    return pd.read_parquet(CACHE / "props_by_market" / f"{market}.parquet")


def props_2026() -> pd.DataFrame:
    """2026 prop board by lead label (scripts.nfl_edge_cache.props_2026)."""
    return pd.read_parquet(CACHE / "props_2026.parquet")


def player_log() -> pd.DataFrame:
    a = pd.read_parquet(CACHE / "local_nfl_player_game_log.parquet")
    b = pd.read_parquet(CACHE / "player_game_log_2025_2026.parquet")
    b = b[[c for c in a.columns if c in b.columns]]
    out = pd.concat([a[a["season"] < 2025], b], ignore_index=True)
    return out


def pbp(seasons) -> pd.DataFrame:
    return pd.concat([pd.read_parquet(CACHE / f"pbp_{s}.parquet") for s in seasons],
                     ignore_index=True)


# ─── grading / inference ───────────────────────────────────────────────────

def boot_ci(profit, cluster, n: int = 4000, alpha: float = 0.10, seed: int = 7):
    """ROI and a (1-alpha) bootstrap CI resampling CLUSTERS (games or weeks),
    never individual bets: same-game bets are not independent."""
    profit = np.asarray(profit, dtype=float)
    cluster = np.asarray(cluster)
    if len(profit) == 0:
        return np.nan, (np.nan, np.nan)
    uniq, inv = np.unique(cluster, return_inverse=True)
    sums = np.bincount(inv, weights=profit)
    cnts = np.bincount(inv)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(uniq), size=(n, len(uniq)))
    roi = sums[idx].sum(1) / cnts[idx].sum(1)
    lo, hi = np.quantile(roi, [alpha / 2, 1 - alpha / 2])
    return profit.sum() / len(profit), (lo, hi)


def summarize(df: pd.DataFrame, profit="profit", cluster="game_id", by=None) -> pd.DataFrame:
    """bets, units, ROI, 90% CI (cluster bootstrap), win rate — optionally by group."""
    def one(x):
        roi, (lo, hi) = boot_ci(x[profit], x[cluster])
        return pd.Series({"bets": len(x), "units": round(x[profit].sum(), 2),
                          "roi_pct": round(100 * roi, 2),
                          "ci90_lo": round(100 * lo, 1), "ci90_hi": round(100 * hi, 1),
                          "win_pct": round(100 * (x[profit] > 0).mean(), 1)})
    if by is None:
        return one(df).to_frame().T
    return df.groupby(by).apply(one).reset_index()
