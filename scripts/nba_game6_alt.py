"""Sixth NBA game-market search: every book's alternate ladder (docs/nba_models_2026.md section 10).

Section 10.4 fixes the rules, 10.5 the 30 cells and their controls, 10.6 the bars. This lab
prices, chooses and grades every cell with the shared harness (scripts/nba_game_harness.py)
and writes rows the pass/fail script reads (scripts/nba_game2_verdict.py --house5).

  DECISION   the alternate purchase, one per game, 60 minutes before tip; its stored stamp
             is the moment the prices were available (fetch_at = snapshot_at, as for the
             per-game derivative purchase, H.load_per_event).
  RUNG       one stored row of source nba_odds_history.ALT_SOURCE: a book's two prices at
             one number. alternate_spreads -> market "spreads" (spread_home, the HOME
             number); alternate_totals -> "totals"; alternate_team_totals_home / _away ->
             team_totals_home / _away. Every bet keeps that real market, which pricing and
             settlement read.
  BOOK MAIN  per (game, market, book): the rung whose prices are closest to even, coherent
             first, ties to the lower number (models/nba_book_numbers.main_rungs).
  FAIR       Pinnacle's main rung, proportional no-vig. Spreads and totals: Pinnacle's rung
             in the SAME alternate purchase. Team totals: Pinnacle's main team-total rung in
             the derivative purchase (H.load_per_event) stamped within TT_MATCH_MIN minutes.
             The centre is solved through the empirical distribution of results around
             Pinnacle's number on the seasons BEFORE the graded one: H.close_dist for spreads
             and totals; for team totals nba_game4_p2.derivative_pricing (derivative seasons
             before S once they hold 300 games, else the full-game proxy).
  ELIGIBLE   a deciding book (H.BETTABLE), coherent, at least MIN_OFF_MAIN points from that
             book's main rung, that book's main rung within MAX_LADDER_GAP of Pinnacle's
             main number, the side's price in [PRICE_MIN, PRICE_MAX].
  CHOICE     the eligible rung with the highest EV on the cell's side, one per (game,
             market): H.choose (ties to the book order).
  POOL       2023-24, 2024-25, 2025-26 (labels 2024-2026); nothing is fitted on these
             prices, so every season is graded and pooled. The verdict's placebo bar reads
             `roi_choose`: here it is the pooled return (there are no choosing seasons).
  BANDS      [0, .02), [.02, .04), [.04, .06), [.06, .08), [.08, .10), [.10, inf): the
             cell's choice at the band's lower edge less the games still chosen at its upper
             edge. band0 is the band just below the cut, band1.. from the cut up (up to 6
             slots: the verdict is run with BAND_SLOTS = 6).
  BLIND      the same side at the best deciding price at each book's MAIN rung, every game
             in the cell's population (the games with an eligible rung in that market).
  PLACEBO    200 runs, seeds 1-200: the fair centre shuffled between games on the same date
             in the same market; prices and rungs stay.

    PYTHONPATH=. python -m scripts.nba_game6_alt --synthetic        # the plumbing, no data
    PYTHONPATH=. python -m scripts.nba_game6_alt --cache-alt        # Supabase -> local cache
    PYTHONPATH=. python -m scripts.nba_game6_alt --full --results DIR
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import nba_game_harness as H  # noqa: E402
from models.nba_book_numbers import main_rungs  # noqa: E402

ALT_SOURCE = "odds_api_nba_alt_history"           # data/ingestors/nba_odds_history.ALT_SOURCE
ALT_TO_MARKET = {"alternate_spreads": "spreads", "alternate_totals": "totals",
                 "alternate_team_totals_home": "team_totals_home",
                 "alternate_team_totals_away": "team_totals_away"}
TT_MARKETS = ("team_totals_home", "team_totals_away")
FAMILIES = {"A1": ("spreads",), "A2": ("totals",), "A3": TT_MARKETS}
FAMILY_LABEL = {"A1": "alt_spreads", "A2": "alt_totals", "A3": "alt_team_totals"}
SIDES = {"A1": ("home", "away"), "A2": ("over", "under"), "A3": ("over", "under")}
CUTS = (0.02, 0.04, 0.06, 0.08, 0.10)
EDGES = (0.0,) + CUTS + (np.inf,)
MIN_OFF_MAIN, MAX_LADDER_GAP = 1.5, 1.0
PRICE_MIN, PRICE_MAX = -200.0, 400.0
TT_MATCH_MIN = 10
SEASONS = (2024, 2025, 2026)
PLACEBO_RUNS = 200
EXPECTED_CELLS = 30
ALT_CACHE = "nba_alt_odds.parquet"


# ── loading ─────────────────────────────────────────────────────────────────

def cache_alt(cache: Path = H.CACHE) -> pd.DataFrame:
    """Every stored alternate rung, read once by game id (indexed), into the local cache."""
    from data.db import get_connection
    g = pd.read_parquet(cache / "nba_games.parquet", columns=["game_id", "game_date"])
    ids = g.loc[g["game_date"].astype(str) >= "2023-10-01", "game_id"].tolist()
    conn = get_connection()
    parts = []
    try:
        for i in range(0, len(ids), 100):
            cur = conn.execute(
                "SELECT game_id, market, bookmaker, snapshot_at, source, spread_home, total_line, "
                "home_price, away_price, over_price, under_price FROM odds "
                "WHERE game_id = ANY(%s) AND market LIKE 'alternate%%' AND source = %s",
                (ids[i:i + 100], ALT_SOURCE))
            rows = cur.fetchall()
            raw = getattr(cur, "_cur", cur)
            parts.append(pd.DataFrame(rows, columns=[d[0] for d in raw.description]))
    finally:
        conn.close()
    df = pd.concat(parts, ignore_index=True)
    for c in ("spread_home", "total_line", "home_price", "away_price", "over_price", "under_price"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df.to_parquet(cache / ALT_CACHE)
    print(f"cached {len(df):,} alternate rungs on {df['game_id'].nunique():,} games")
    return df


def frame_alt(o: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Stored alternate rows -> the harness's quote frame (H.QUOTE_COLS), one row per rung."""
    o = o[o["market"].isin(ALT_TO_MARKET)].copy()
    o["alt_market"] = o["market"]
    o["market"] = o["market"].map(ALT_TO_MARKET)
    o["snapshot_at"] = pd.to_datetime(o["snapshot_at"], utc=True)
    o = o.merge(games[["game_id", "season", "game_date", "tip"]], on="game_id")
    o = o[o["snapshot_at"] < o["tip"]].rename(columns={"bookmaker": "book"})
    o["fetch_at"] = o["snapshot_at"]
    k = H.kind(o["market"])
    o["line"] = np.where(k == "spread", o["spread_home"], o["total_line"]).astype(float)
    o["price_a"] = np.where(k == "total", o["over_price"], o["home_price"]).astype(float)
    o["price_b"] = np.where(k == "total", o["under_price"], o["away_price"]).astype(float)
    o = o[o["price_a"].notna() & o["price_b"].notna() & o["line"].notna()]
    s = H.imp(o["price_a"]) + H.imp(o["price_b"])
    o["coherent"] = (s >= H.COHERENT[0]) & (s <= H.COHERENT[1])
    return o[H.QUOTE_COLS + ["alt_market"]].reset_index(drop=True)


# ── fair line, eligibility, offers ──────────────────────────────────────────

def pinnacle_mains(q: pd.DataFrame, pe_tt: pd.DataFrame | None) -> pd.DataFrame:
    """(game_id, market, pin_line, pin_fa, pin_at): Pinnacle's main number and no-vig side-A
    chance. Spreads / totals from the alternate purchase itself; team totals from the
    derivative purchase within TT_MATCH_MIN minutes of the alternate purchase."""
    p = q[(q["book"] == H.SHARP) & q["coherent"] & ~q["market"].isin(TT_MARKETS)]
    p = main_rungs(p)
    parts = [p]
    if pe_tt is not None and len(pe_tt):
        t = pe_tt[(pe_tt["book"] == H.SHARP) & pe_tt["coherent"] & pe_tt["market"].isin(TT_MARKETS)]
        t = main_rungs(t)
        at = q[q["market"].isin(TT_MARKETS)].groupby("game_id")["fetch_at"].first().rename("alt_at")
        t = t.merge(at, left_on="game_id", right_index=True)
        t = t[(t["fetch_at"] - t["alt_at"]).abs() <= pd.Timedelta(minutes=TT_MATCH_MIN)]
        parts.append(t.drop(columns="alt_at"))
    m = pd.concat(parts, ignore_index=True)
    ia, ib = H.imp(m["price_a"]), H.imp(m["price_b"])
    m = m.assign(pin_line=m["line"], pin_fa=ia / (ia + ib), pin_at=m["fetch_at"])
    return m.drop_duplicates(["game_id", "market"])[["game_id", "market", "pin_line", "pin_fa", "pin_at"]]


def fair_centres(pins: pd.DataFrame, games: pd.DataFrame, sig: dict) -> pd.DataFrame:
    """mu per (game, market): the side-A quantity's centre at which Pinnacle's main number
    carries its no-vig price, through sig[(season, market)] (a ResidDist)."""
    f = pins.merge(games[["game_id", "season", "game_date"]], on="game_id")
    f["sigma"] = pd.Series([sig.get((int(s), m)) for s, m in zip(f["season"], f["market"])],
                           index=f.index, dtype=object)
    f = f[f["sigma"].notna()]
    f["mu"] = H.solve_any(H.threshold(f["market"], f["pin_line"]), f["pin_fa"].to_numpy(),
                          f["sigma"].to_numpy())
    return f


def eligible_offers(q: pd.DataFrame, pins: pd.DataFrame) -> pd.DataFrame:
    """Two offers per eligible rung (section 10.4.4), with the book's main and the distance."""
    bm = main_rungs(q)[["game_id", "market", "book", "line"]].rename(columns={"line": "book_main"})
    x = q.merge(bm, on=["game_id", "market", "book"]).merge(
        pins[["game_id", "market", "pin_line"]], on=["game_id", "market"])
    x = x[x["book"].isin(H.BETTABLE) & x["coherent"]]
    x = x.assign(off_main=(x["line"] - x["book_main"]).abs(),
                 ladder_gap=(x["book_main"] - x["pin_line"]).abs())
    x = x[(x["off_main"] >= MIN_OFF_MAIN - 1e-9) & (x["ladder_gap"] <= MAX_LADDER_GAP + 1e-9)]
    off = H.offers(x)
    off = off.assign(T=off["fetch_at"])
    return off


def main_offers(q: pd.DataFrame, pins: pd.DataFrame) -> pd.DataFrame:
    """Every deciding book's MAIN rung as two offers: the blind bet and the main-rung control."""
    bm = main_rungs(q[q["book"].isin(H.BETTABLE)])
    bm = bm.merge(pins[["game_id", "market"]], on=["game_id", "market"])
    off = H.offers(bm)
    return off.assign(T=off["fetch_at"])


def priced(off: pd.DataFrame, fair: pd.DataFrame) -> pd.DataFrame:
    return H.fair_offers(off, fair.assign(p_home=np.nan))


def in_band(off: pd.DataFrame, lo: float, hi: float) -> pd.DataFrame:
    return off[(off["price"] >= lo) & (off["price"] <= hi)]


# ── one cell ────────────────────────────────────────────────────────────────

def _pick(cand: pd.DataFrame, cut: float, side: str, books=H.BETTABLE) -> pd.DataFrame:
    return H.choose(cand, cut, books=books, sides=[side], floor=PRICE_MIN)


def pooled(g: pd.DataFrame) -> dict:
    if not len(g):
        return {"pool_n": 0, "pool_units": 0.0, "pool_roi": np.nan, "pool_ci95_lo": np.nan,
                "pool_ci95_hi": np.nan, "pool_seasons_counted": 0, "pool_seasons_positive": 0}
    lo, hi = H.ci95(g)
    counted = positive = 0
    out = {}
    for s in SEASONS:
        gs = g[g["season"] == s]
        out[f"n_{s}"], out[f"roi_{s}"] = int(len(gs)), (H.roi(gs) if len(gs) else np.nan)
        if len(gs) >= 30:
            counted += 1
            positive += int(H.roi(gs) > 0)
    return {"pool_n": int(len(g)), "pool_units": float(g["units"].sum()), "pool_roi": H.roi(g),
            "pool_ci95_lo": lo, "pool_ci95_hi": hi, "pool_seasons_counted": counted,
            "pool_seasons_positive": positive, **out}


def band_cols(cand: pd.DataFrame, side: str, k: int, games: pd.DataFrame) -> dict:
    """band0 = [edge below the cut, cut), band1.. = [cut, next), ... [last, inf)."""
    cut_edge = 1 + k                               # EDGES index of this cell's cut
    out = {}
    for slot, lo_i in enumerate(range(cut_edge - 1, len(EDGES) - 1)):
        lo, hi = EDGES[lo_i], EDGES[lo_i + 1]
        at_lo = _pick(cand, lo, side)
        at_hi = _pick(cand, hi, side) if np.isfinite(hi) else at_lo.iloc[0:0]
        keys = set(zip(at_hi["game_id"], at_hi["market"]))
        b = at_lo[[k2 not in keys for k2 in zip(at_lo["game_id"], at_lo["market"])]]
        g = H.grade(b, games)
        out[f"band{slot}_lo"], out[f"band{slot}_n"] = lo, int(len(g))
        out[f"band{slot}_roi"] = H.roi(g) if len(g) else np.nan
    return out


def shares(g: pd.DataFrame, fair: pd.DataFrame) -> dict:
    if not len(g):
        return {}
    out = {}
    sp = g[H.kind(g["market"]) == "spread"]
    tt = g[H.kind(g["market"]) == "total"]
    if len(sp):
        out["pool_share_home"] = float((sp["side"] == "home").mean())
        f = fair.set_index(["game_id", "market"])["mu"]
        mu = np.array([f.get(k, np.nan) for k in zip(sp["game_id"], sp["market"])])
        fav = np.where(mu > 0, "home", "away")
        out["pool_share_fav"] = float((sp["side"].to_numpy() == fav).mean())
    if len(tt):
        out["pool_share_over"] = float((tt["side"] == "over").mean())
    return out


def blinds(main_priced: pd.DataFrame, population: set, games: pd.DataFrame, fair: pd.DataFrame) -> dict:
    pop = main_priced[main_priced["game_id"].isin(population)]
    out = {}
    for side in ("home", "away", "over", "under"):
        b = H.choose(pop, -np.inf, sides=[side], floor=PRICE_MIN)
        g = H.grade(b, games)
        if len(g):
            out[f"blind_pool_{side}"] = H.roi(g)
    sp = pop[H.kind(pop["market"]) == "spread"]
    if len(sp):
        f = fair.set_index(["game_id", "market"])["mu"]
        mu = np.array([f.get(k, np.nan) for k in zip(sp["game_id"], sp["market"])])
        sp = sp.assign(side_pick=np.where(mu > 0, "home", "away"))
        for lab, pick in (("fav", sp["side_pick"]), ("dog", np.where(sp["side_pick"] == "home", "away", "home"))):
            c = sp.assign(side_pick=pick)
            g = H.grade(H.choose(c, -np.inf, sides=["per_game"], floor=PRICE_MIN), games)
            if len(g):
                out[f"blind_pool_{lab}"] = H.roi(g)
    return out


def shuffle_fair(fair: pd.DataFrame, run: int) -> pd.DataFrame:
    """Placebo: mu (with its sigma) swapped between games on the same date in the same market."""
    rng = np.random.default_rng(run)
    f = fair.copy()
    for _, idx in f.groupby(["game_date", "market"]).groups.items():
        idx = np.asarray(list(idx))
        if len(idx) > 1:
            perm = rng.permutation(idx)
            f.loc[idx, "mu"] = f.loc[perm, "mu"].to_numpy()
    return f


def without_best_book(cand, cut, side, g, games):
    if not len(g):
        return np.nan
    top = g.groupby("book")["units"].sum().idxmax()
    g2 = H.grade(_pick(cand, cut, side, books=tuple(b for b in H.BETTABLE if b != top)), games)
    return H.roi(g2) if len(g2) else np.nan


def family_cells(fam: str, off: pd.DataFrame, fair: pd.DataFrame, main_priced: pd.DataFrame,
                 games: pd.DataFrame, close, sig, runs: int, label: str | None = None,
                 band: tuple = (PRICE_MIN, PRICE_MAX)) -> tuple[list[dict], pd.DataFrame]:
    markets = FAMILIES[fam]
    o = in_band(off[off["market"].isin(markets)], *band)
    cand = priced(o, fair)
    placebos = [priced(o, shuffle_fair(fair, r)) for r in range(1, runs + 1)]
    population = set(cand["game_id"])
    bl = blinds(main_priced[main_priced["market"].isin(markets)], population, games, fair)
    rows, bets = [], []
    for side in SIDES[fam]:
        for k, cut in enumerate(CUTS):
            g = H.grade(_pick(cand, cut, side), games)
            row = {"family": label or fam, "point": "alt60", "market": FAMILY_LABEL[fam], "side": side,
                   "cut_index": k, "cut": cut, "population_games": len(population),
                   **pooled(g), **shares(g, fair), **bl, **band_cols(cand, side, k, games)}
            row["roi_choose"] = row["pool_roi"]
            pl = []
            for pc in placebos:
                gp = H.grade(_pick(pc, cut, side), games)
                pl.append(H.roi(gp) if len(gp) else np.nan)
            row["placebo_rois"] = pl
            dk = H.grade(_pick(cand, cut, side, books=(H.DK,)), games)
            row["dk_n"], row["dk_roi"] = int(len(dk)), (H.roi(dk) if len(dk) else np.nan)
            row["roi_without_best_book"] = without_best_book(cand, cut, side, g, games)
            if len(g):
                for lo, hi, lab in ((PRICE_MIN, 150, "price_short"), (150.0001, PRICE_MAX, "price_long")):
                    gg = g[(g["price"] >= lo) & (g["price"] <= hi)]
                    row[f"{lab}_n"], row[f"{lab}_roi"] = int(len(gg)), (H.roi(gg) if len(gg) else np.nan)
            if len(g) and "off_main" in cand:
                gm = g.merge(cand[["game_id", "market", "book", "side", "line", "price", "off_main"]]
                             .drop_duplicates(["game_id", "market", "book", "side", "line", "price"]),
                             on=["game_id", "market", "book", "side", "line", "price"], how="left")
                for lo, hi, lab in ((1.5, 4, "dist_near"), (4, 8, "dist_mid"), (8, 99, "dist_far")):
                    gg = gm[(gm["off_main"] >= lo) & (gm["off_main"] < hi)]
                    row[f"{lab}_n"], row[f"{lab}_roi"] = int(len(gg)), (H.roi(gg) if len(gg) else np.nan)
            if len(g):
                if close is not None and sig is not None:
                    ev = H.clv(g.assign(T=g["T"]), close, sig)
                    row["clv_n"] = int(ev.notna().sum())
                    row["clv_median"] = float(np.nanmedian(ev)) if ev.notna().any() else np.nan
                    row["clv_mean"] = float(np.nanmean(ev)) if ev.notna().any() else np.nan
                bets.append(g.assign(family=label or fam, cell_side=side, cut=cut))
            rows.append(row)
    return rows, (pd.concat(bets, ignore_index=True) if bets else pd.DataFrame())


# ── the run ─────────────────────────────────────────────────────────────────

def pricing(data: H.Data, games_p: pd.DataFrame, pe: pd.DataFrame | None) -> dict:
    """{(season, market): ResidDist} for spreads, totals and both team totals."""
    close = H.pinnacle_close(data)
    sig = dict(H.close_dist(close, data.games))
    if pe is not None and len(pe):
        from scripts.nba_game4_p2 import derivative_pricing
        q_main = main_rungs(pe[pe["market"].isin(TT_MARKETS)])
        dd = H.Data(games=games_p, quotes=q_main, fetches=pd.DataFrame(columns=["game_id", "fetch_at"]))
        dclose = H.pinnacle_close(dd)
        tt, _src = derivative_pricing(dclose, games_p, close, SEASONS)
        sig.update({k: v for k, v in tt.items() if k[1] in TT_MARKETS})
    return sig


def run(alt: pd.DataFrame, data: H.Data, pe: pd.DataFrame | None, runs: int = PLACEBO_RUNS,
        sig: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    games = data.games
    q = frame_alt(alt, games)
    q = q[q["season"].isin(SEASONS)]
    sig = pricing(data, games, pe) if sig is None else sig
    close = H.pinnacle_close(data) if len(data.quotes) else None
    pins = pinnacle_mains(q, pe)
    fair = fair_centres(pins, games, sig)
    off = eligible_offers(q, fair)
    main_priced = priced(main_offers(q, fair), fair)
    rows, bets = [], []
    for fam in FAMILIES:
        r, b = family_cells(fam, off, fair, main_priced, games, close, sig, runs)
        rows += r
        bets.append(b)
        # controls are reported, never judged (section 10.5), so they carry no placebo runs
        r, _ = family_cells(fam, off, fair, main_priced, games, close, sig, 0,
                            label=f"control_{fam}_long", band=(PRICE_MAX + 1e-9, np.inf))
        rows += r
        mo = main_offers(q, fair)
        r, _ = family_cells(fam, mo, fair, main_priced, games, close, sig, 0,
                            label=f"control_{fam}_main")
        rows += r
        print(f"  {fam}: graded", flush=True)
    cells = pd.DataFrame(rows)
    cand = cells[~cells["family"].astype(str).str.startswith("control_")]
    assert len(cand) == EXPECTED_CELLS, (len(cand), EXPECTED_CELLS)
    return cells, pd.concat([b for b in bets if len(b)], ignore_index=True) if any(len(b) for b in bets) else pd.DataFrame()


# ── synthetic world: the plumbing, with a planted mispricing ────────────────

def _american(p: float) -> float:
    p = min(max(p, 0.005), 0.995)
    return -100 * p / (1 - p) if p >= 0.5 else 100 * (1 - p) / p


def synthetic_world(seed: int = 3, n_days: int = 300, per_day: int = 6, soft_sd: float = 10.5):
    """Games with home margins ~ Normal(mu, 13). Pinnacle's main rung is priced exactly; book
    'fanduel' prices its spread ladder from a THINNER curve (soft_sd) with 4% hold, so its far
    rungs on both sides are mispriced; 'draftkings' prices its ladder from the true curve with
    the same hold. Totals and team totals are left out. Returns (alt rows, Data, sig)."""
    from math import erf, sqrt
    rng = np.random.default_rng(seed)
    cdf = lambda z: 0.5 * (1 + erf(z / sqrt(2)))
    rows, games = [], []
    day0 = pd.Timestamp("2023-11-01", tz="UTC")
    for d in range(n_days):
        season = 2024 if d < n_days / 3 else 2025 if d < 2 * n_days / 3 else 2026
        for j in range(per_day):
            gid = f"SYN_{d:03d}_{j}"
            tip = day0 + pd.Timedelta(days=d, hours=23 + j % 3)
            mu = float(rng.normal(0, 6))
            margin = int(np.round(rng.normal(mu, 13.0)))
            if margin == 0:
                margin = 1
            hs = 110 + max(margin, 0)
            games.append({"game_id": gid, "season": season, "game_date": str(tip.date()), "tip": tip,
                          "home_team": "H", "away_team": "A", "home_score": hs, "away_score": hs - margin})
            snap = (tip - pd.Timedelta(minutes=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
            main = -np.round(mu * 2) / 2
            for book, sd, hold in (("pinnacle", 13.0, 0.02), ("draftkings", 13.0, 0.04), ("fanduel", soft_sd, 0.04)):
                offs = (0.0,) if book == "pinnacle" else tuple(np.arange(-12, 12.5, 1.0))
                for o in offs:
                    line = main + o
                    p_home = 1 - cdf((-line - mu) / sd)       # P(margin > -line)
                    pa, pb = p_home * (1 + hold / 2), (1 - p_home) * (1 + hold / 2)
                    if max(pa, pb) > 0.97:
                        continue
                    rows.append({"game_id": gid, "market": "alternate_spreads", "bookmaker": book,
                                 "snapshot_at": snap, "source": ALT_SOURCE, "spread_home": float(line),
                                 "total_line": np.nan, "home_price": _american(pa),
                                 "away_price": _american(pb), "over_price": np.nan, "under_price": np.nan})
    g = pd.DataFrame(games)
    data = H.Data(games=g, quotes=pd.DataFrame(columns=H.QUOTE_COLS), fetches=pd.DataFrame())
    resid = rng.normal(0, 13.0, 6000)
    dist = H.ResidDist(resid, "synthetic spreads")
    sig = {(s, "spreads"): dist for s in SEASONS}
    return pd.DataFrame(rows), data, sig


def synthetic_checks() -> None:
    alt, data, sig = synthetic_world()
    games = data.games
    q = frame_alt(alt, games)
    pins = pinnacle_mains(q, None)
    fair = fair_centres(pins, games, sig)
    # the fair centre recovers the game's own centre (home number sign)
    f = fair.set_index("game_id")["mu"]
    true_mu = -pins.set_index("game_id")["pin_line"]
    assert np.nanmax(np.abs(f - true_mu.reindex(f.index))) < 0.6, "fair centre off: the home-number sign"
    off = eligible_offers(q, fair)
    cand = priced(off, fair)
    assert (cand["off_main"] >= MIN_OFF_MAIN).all()
    for side in ("home", "away"):
        soft = H.grade(_pick(cand, 0.04, side, books=("fanduel",)), games)
        fairbook = H.grade(_pick(cand, 0.04, side, books=("draftkings",)), games)
        print(f"  synthetic {side}: thin-curve book {len(soft)} bets ROI {H.roi(soft):+.3f}; "
              f"true-curve book {len(fairbook)} bets")
        assert len(soft) > 200 and H.roi(soft) > 0.02, "a planted mispricing was not found"
        assert len(fairbook) < 0.05 * len(soft), "a correctly priced ladder produced EV >= 0.04"
    print("synthetic checks pass")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--cache-alt", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--results", type=Path)
    ap.add_argument("--runs", type=int, default=PLACEBO_RUNS)
    a = ap.parse_args()
    if a.synthetic:
        synthetic_checks()
        return
    if a.cache_alt:
        cache_alt()
        return
    if a.full:
        if a.results is None:
            ap.error("--full needs --results DIR")
        synthetic_checks()
        data = H.load(require_seasons=SEASONS)
        alt = pd.read_parquet(H.CACHE / ALT_CACHE)
        have = data.games.loc[data.games["game_id"].isin(set(alt["game_id"]))].groupby("season").size()
        allg = data.games.groupby("season").size()
        short = {int(s): round(float(have.get(s, 0) / allg[s]), 3) for s in SEASONS
                 if have.get(s, 0) / allg[s] < H.MIN_PRICED_SHARE}
        if short:
            raise SystemExit(f"alternate prices on too few games: {short}")
        pe = H.load_per_event(data.games)
        pe = pe[pe["market"].isin(TT_MARKETS)]
        cells, bets = run(alt, data, pe, runs=a.runs)
        a.results.mkdir(parents=True, exist_ok=True)
        cells.to_parquet(a.results / "cells_A.parquet")
        if len(bets):
            bets.to_parquet(a.results / "bets_A.parquet")
        print(f"wrote {len(cells)} rows to {a.results}")
        return
    ap.error("give --synthetic, --cache-alt or --full")


if __name__ == "__main__":
    main()
