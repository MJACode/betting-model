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

    PYTHONPATH=. python -m scripts.nba_game_harness --check
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
from scripts.nba_game_market_lab import (  # noqa: E402
    _assert_spread_sign, dec, imp, power_devig, probs_at, settle, solve_mu, threshold)

CACHE = ROOT / "data" / "local" / "nba"
MARKETS = ("h2h", "spreads", "totals")
SIDE_A = {"h2h": "home", "spreads": "home", "totals": "over"}
SIDE_B = {"h2h": "away", "spreads": "away", "totals": "under"}
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


def load(cache: Path = CACHE, seasons=None) -> Data:
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
    return Data(games=g.reset_index(drop=True), quotes=o, fetches=f.reset_index(drop=True),
                notes=notes)


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
    """Two rows per visible coherent quote, one per side: (side, line, price)."""
    v = vis[vis["coherent"]]
    a = v.assign(side=v["market"].map(SIDE_A), price=v["price_a"])
    b = v.assign(side=v["market"].map(SIDE_B), price=v["price_b"])
    out = pd.concat([a, b], ignore_index=True).drop(columns=["price_a", "price_b"])
    return out


# ── fair probabilities ──────────────────────────────────────────────────────

def side_probs(market, side, line, mu=None, sigma=None, p_home=None):
    """(P win, P push) for a side at a stored side-A number.

    spreads/totals: the side-A quantity (home margin, or the total) ~ Normal(mu,
    sigma), integer-continuity as in the first search. h2h: p_home."""
    market, side = np.asarray(market), np.asarray(side)
    a_side = (side == "home") | (side == "over")
    pw = np.full(market.shape, np.nan)
    pp = np.zeros(market.shape)
    ml = market == "h2h"
    if p_home is not None:
        ph = np.asarray(p_home, float)
        pw = np.where(ml, np.where(a_side, ph, 1.0 - ph), pw)
    if mu is not None:
        t = threshold(market, line)
        w, push, lose = probs_at(np.asarray(mu, float), np.asarray(sigma, float), t)
        pw = np.where(~ml, np.where(a_side, w, lose), pw)
        pp = np.where(~ml, push, pp)
    return pw, pp


def with_ev(off: pd.DataFrame) -> pd.DataFrame:
    """ev per unit risked from p_win / p_push columns."""
    d = dec(off["price"])
    p_lose = 1.0 - off["p_win"] - off["p_push"]
    return off.assign(ev=off["p_win"] * (d - 1.0) - p_lose)


def choose(cand: pd.DataFrame, cut: float, books=BETTABLE, sides=None) -> pd.DataFrame:
    """One bet per (game, market): the best-EV offer at an allowed book.

    `cand` holds offers with p_win, p_push (with_ev adds ev). Ties go to the
    earlier book in BEST_LINE_BOOKMAKERS."""
    c = cand[cand["book"].isin(books) & (cand["price"] >= PRICE_FLOOR)]
    if sides is not None:
        c = c[c["side"].isin(sides)]
    if "ev" not in c:
        c = with_ev(c)
    c = c[c["ev"] >= cut]
    c = c.assign(_r=c["book"].map(BOOK_RANK).fillna(99))
    c = c.sort_values(["game_id", "market", "ev", "_r"], ascending=[True, True, False, True])
    return c.drop_duplicates(["game_id", "market"]).drop(columns="_r").reset_index(drop=True)


# ── grading ─────────────────────────────────────────────────────────────────

def grade(bets: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    if len(bets) == 0:
        return bets.assign(result=[], units=[], risk=[], risk_kept=[])
    b = bets.drop(columns=[c for c in ("home_score", "away_score") if c in bets]).merge(
        games[["game_id", "home_score", "away_score"]], on="game_id")
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
    t2 = nxt.rename(columns={"T_next": "Tn"})[["game_id", "T", "Tn"]]
    vis = visible(data.quotes, t2[["game_id", "Tn"]].rename(columns={"Tn": "T"}).drop_duplicates("game_id"))
    off = offers(vis)[["game_id", "market", "book", "side", "line", "price"]].rename(
        columns={"price": "price_next", "line": "line_next"})
    x = bets.reset_index().merge(off, on=["game_id", "market", "book", "side"], how="left")
    same = np.where(x["market"] == "h2h", True,
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
    same = (x["market"] == "h2h") | np.isclose(x["line"].fillna(0), x["l2"].fillna(np.inf))
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
    c = close[close["market"] != "h2h"].merge(games[["game_id", "home_score", "away_score"]],
                                               on="game_id")
    margin, total = c["home_score"] - c["away_score"], c["home_score"] + c["away_score"]
    c = c.assign(resid=np.where(c["market"] == "spreads", margin + c["close_line"],
                                total - c["close_line"]))
    sig = {}
    for s in sorted(games["season"].unique()):
        for m in ("spreads", "totals"):
            prior = c[(c["market"] == m) & (c["season"] < s)]
            if len(prior) < 300:
                prior = c[(c["market"] == m) & (c["season"] == s)]
            sig[(int(s), m)] = float(prior["resid"].std())
    return sig


def clv(bets: pd.DataFrame, close: pd.DataFrame, sig: dict) -> pd.Series:
    """EV of the bet's price at Pinnacle's no-vig close (moved number: normal model)."""
    if len(bets) == 0:
        return pd.Series([], dtype=float)
    x = bets.reset_index().merge(close.drop(columns="season"), on=["game_id", "market"], how="left")
    x = x[x["close_at"] > x["T"]]
    a_side = x["side"].isin(["home", "over"])
    p_a = x["close_fa"].to_numpy()
    sigma = np.array([sig.get((int(s), m), np.nan) for s, m in zip(x["season"], x["market"])])
    ml = (x["market"] == "h2h").to_numpy()
    same = ml | np.isclose(x["line"].fillna(0), x["close_line"].fillna(np.inf))
    tc = threshold(x["market"], x["close_line"])
    mu = solve_mu(tc, p_a, np.where(np.isnan(sigma), 1.0, sigma))
    w, push, lose = probs_at(mu, np.where(np.isnan(sigma), 1.0, sigma), threshold(x["market"], x["line"]))
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
                close: pd.DataFrame | None = None, sig: dict | None = None) -> dict:
    """Everything §6.2/§6.4 asks of one cell. `bets_all` is graded, every season."""
    ch = bets_all[bets_all["season"].isin(CHOOSE)]
    cf = bets_all[bets_all["season"] == CONFIRM]
    r = {"choose": summarise(ch), "confirm": summarise(cf),
         "regime_2021": summarise(bets_all[bets_all["season"] == REGIME])}
    r["choose"]["ci90"] = ci90(ch)
    r["confirm"]["ci90"] = ci90(cf)
    r["p_confirm"] = p_one_sided(cf)
    if len(ch):
        days = np.sort(ch["game_date"].unique())
        mid = days[len(days) // 2]
        r["half_early_roi"] = roi(ch[ch["game_date"] < mid])
        r["half_late_roi"] = roi(ch[ch["game_date"] >= mid])
        r["seasons_positive"] = all(
            (roi(ch[ch["season"] == s]) > 0) for s in CHOOSE if (ch["season"] == s).sum() >= 30)
        sides = ch["side"].value_counts(normalize=True)
        r["top_side"], r["top_share"] = str(sides.index[0]), float(sides.iloc[0])
    if len(bets_all):
        still = next_fetch_check(bets_all, data)
        r["units_still_offered"] = float(bets_all.loc[still, "units"].sum())
        r["share_still_offered"] = float(still.mean())
        if cand is not None:
            out = outlier_flag(bets_all, cand)
            r["units_without_outliers"] = float(bets_all.loc[~out, "units"].sum())
            r["share_outlier"] = float(out.mean())
        if close is not None and sig is not None:
            ev = clv(bets_all, close, sig)
            r["clv_median"] = float(np.nanmedian(ev)) if ev.notna().any() else np.nan
            r["clv_share_positive"] = float((ev > 0).mean()) if ev.notna().any() else np.nan
            r["clv_n"] = int(ev.notna().sum())
    return r


def check() -> None:
    """Sign and arithmetic checks that must hold before any cell is read."""
    _assert_spread_sign()
    assert np.allclose(cents([-110, 110, -105, 105, 150, -200]), [-10, 10, -5, 5, 50, -100])
    r, w = risk_win([-110, 150, -400])
    assert np.allclose(r, [1.1, 1 / 1.5, 3.0]) and np.allclose(w[:2], [1.0, 1.0])
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
