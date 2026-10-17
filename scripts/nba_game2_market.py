"""Second NBA game-market search, families F2, F6a and F6d: the market against itself.

docs/nba_models_2026.md §6.3 pre-registers these cells (and only these); the
shared harness scripts/nba_game_harness.py prices, chooses and grades every
one of them, and scripts/nba_game2_verdict.py judges them. This lab only builds
each family's fair numbers and emits its cells. It never reads a result to set
anything.

FAMILIES AND CELLS (120, asserted)

  F2   Spread-implied win probability against the moneyline (Moskowitz &
       Vasudevan 2020, comparing the win probability implied by a game's spread
       with its moneyline). The REFERENCE spread at T -- axis_ref "pinnacle":
       Pinnacle's own spread quote; "consensus": the median over the deciding
       books (config.BEST_LINE_BOOKMAKERS) of the home margin each book's spread
       implies -- is turned into the centre mu of a normal home-margin model
       (H.market_fair: mu solved at the quote's no-vig price, sigma =
       H.close_sigma for the season), and p_home = P(margin > 0) with the
       integer tie mass removed (an NBA game cannot end level).
       Bet the moneyline side where EV under that p_home clears the cut.
       Sides fav / dog: the favourite is the side the REFERENCE makes more
       likely than not at T; a game where it says exactly 0.5, or has no
       reference number at T, has no favourite and is outside both cells.
       Points A, B, C, D x EV cuts 0, .01, .02, .03, .05, .08 x 2 sides x 2
       references = 96.
  F6a  Overtime tail on totals: bet the over when the market's fair home
       margin at T (H.market_fair on the spreads: Pinnacle's no-vig, else the
       deciding-book median) is within k points. A RULE: offers are priced at
       the market's own fair total, strength = -abs(margin), cut = -k, so
       strength >= cut is abs(margin) <= k. Points B, C x k = 1, 2, 3, 4 = 8.
  F6d  One book against itself. (i) moneyline: each deciding book's moneyline
       priced against THAT book's own spread (spread -> p_home as in F2).
       (ii) total: each deciding book's full-game total priced against THAT
       book's own team totals, fair total = mu(home team total) + mu(away
       team total), each solved at the team total's no-vig price, spread of
       the full total = H.close_sigma's totals sigma. Team totals are per-game
       purchases (H.load_per_event), 2024-25 on, and count only at D
       (H.per_event_times). Markets moneyline, total x 2 sides x C, D x EV
       cuts .01, .03 = 16. The four total cells at C have no team-total quote
       by rule and are emitted empty. Total cells choose on 2024-25 alone.

THE FAV / DOG MAPPING (F2). H.run_cells grades sides "home" / "away" and
settles them on the games' scores. For each (decision point, reference) the
lab builds an ORIENTED copy of the data: on every game where the reference
makes the away team the favourite, the two teams' scores are swapped in the
games and the two moneyline prices are swapped in the quotes. In that copy
"home" is always the favourite and "away" the underdog, so the harness grades,
blind-bets (bar 9: the favourite on every game) and closes (Pinnacle's no-vig
close of the favourite) the right side. The emitted rows map home -> "fav",
away -> "dog". Only moneyline quotes are kept in the oriented copy.

INPUTS AND HOW EACH IS DATED (no look-ahead)

  Game-line quotes     H.visible at T: a fetch at or before T, no older than
                       60 minutes, before tip. T is the fetch instant from the
                       purchase ledgers (H.decision_times).
  Reference / own-book spreads, team totals: the same visible quotes at T.
  Team totals          per-game purchase, dated by the feed's own snapshot,
                       used only when that purchase falls in D's 45-75-minute
                       window. The total cells' T at D is the LATER of the
                       slate's D fetch and the team-total purchase, so both
                       are in hand at T.
  sigma (margin, total) H.close_sigma: SD of (result - Pinnacle close) on the
                       seasons before S. 2020-21 has no earlier priced season,
                       so the harness falls back to 2020-21 itself (reported
                       season, never chosen on).
  sigma (team total)   team_sigma: SD of (team score - the team total implied by
                       Pinnacle's closing spread and total) on the seasons
                       before S, NaN with fewer than 300 earlier games.

FIT SEASONS PER GRADED SEASON (walk-forward; nothing else is fitted)

  graded 2021  margin/total sigma: 2021 itself (harness fallback); team sigma: none
  graded 2022  sigmas: 2021
  graded 2023  sigmas: 2021-2022
  graded 2024  sigmas: 2021-2023
  graded 2025  sigmas: 2021-2024 (team-total sigma: 2021-2024)
  graded 2026  sigmas: 2021-2025 (team-total sigma: 2021-2025)

PLACEBO: 20 runs, run r shuffles the family's fair numbers between games on
the same date and market with H.shuffle_within_date(rng = default_rng(r)):
F2 the reference's favourite probability (within the oriented copy, so the
cell keeps its side); F6a the strength column only (prices stay at the
market's fair line); F6d each book's own fair number, book by book.

    PYTHONPATH=. python -m scripts.nba_game2_market --smoke
    NBA_GAME2_GO=1 PYTHONPATH=. python -m scripts.nba_game2_market --full

Writes <results>/cells_<family>.parquet and <results>/population_<family>.parquet;
<results> is NBA_GAME2_RESULTS (default %TEMP%/nba_game_edge/results). --smoke
writes under <results>/smoke and grades 2020-21 only. --full refuses to run
unless NBA_GAME2_GO=1 (the owner runs it after the price data is refreshed).
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import nba_game_harness as H  # noqa: E402

DEFAULT_RESULTS = Path("C:/Users/micha/AppData/Local/Temp/nba_game_edge/results")

F2_POINTS = ("A", "B", "C", "D")
F2_CUTS = (0.0, 0.01, 0.02, 0.03, 0.05, 0.08)
F2_REFS = ("pinnacle", "consensus")
F6A_POINTS = ("B", "C")
F6A_K = (1, 2, 3, 4)
F6A_CUTS = tuple(-float(k) for k in F6A_K)        # strength = -abs(margin) >= -k
F6D_POINTS = ("C", "D")
F6D_CUTS = (0.01, 0.03)
F6D_TT_CHOOSE = (2025,)                            # team totals start 2024-25
EXPECTED_CELLS = {"F2": 96, "F6a": 8, "F6d": 16}
PLACEBO_RUNS = 20
TT_MARKETS = ("team_totals_home", "team_totals_away")
FAV_DOG = {"home": "fav", "away": "dog"}
SMOKE_SEASONS = (2021,)
MIN_PRIOR_GAMES = 300


# ── guards ──────────────────────────────────────────────────────────────────

def results_dir(env=os.environ) -> Path:
    return Path(env.get("NBA_GAME2_RESULTS", str(DEFAULT_RESULTS)))


def go_guard(full: bool, env=os.environ) -> None:
    """--full grades every season, 2025-26 included; only the owner starts it."""
    if full and env.get("NBA_GAME2_GO") != "1":
        raise SystemExit("--full refuses to run: set NBA_GAME2_GO=1 (the owner runs it "
                         "after the price data is refreshed)")


def seasons_for(mode: str):
    """smoke: 2020-21 only. full: every season the cache holds."""
    if mode == "smoke":
        return list(SMOKE_SEASONS)
    if mode == "full":
        return None
    raise ValueError(mode)


def cache_for(mode: str, ledger: Path | None, results: Path) -> Path:
    """The cache H.load reads. The shared cache is never written: when it has
    no purchase ledger yet, --smoke may build a private overlay (copies of the
    games and odds files plus a ledger read from Supabase); --full may not."""
    cache = H.CACHE
    if (cache / "nba_fetch_ledger.parquet").exists():
        return cache
    if mode == "full":
        raise SystemExit(f"{cache} has no nba_fetch_ledger.parquet: refresh the cache "
                         "(python -m scripts.nba_research_cache --only lines) before --full")
    if ledger is None or not Path(ledger).exists():
        raise SystemExit("the cache has no purchase ledger; pass --ledger <parquet>")
    ov = results / "cache_overlay"
    ov.mkdir(parents=True, exist_ok=True)
    for f in ("nba_games.parquet", "nba_odds.parquet"):
        shutil.copyfile(cache / f, ov / f)
    shutil.copyfile(ledger, ov / "nba_fetch_ledger.parquet")
    return ov


# ── the rules (small, so each has its own test) ─────────────────────────────

def p_home_from_margin(mu, sigma) -> np.ndarray:
    """P(home wins) under the harness's integer normal margin model: the mass on
    margin 0 is removed (no NBA game ends level), P(win) / (P(win) + P(lose))."""
    mu = np.asarray(mu, float)
    n = mu.shape
    pw, pp = H.side_probs(np.full(n, "spreads"), np.full(n, "home"), np.zeros(n),
                          mu=mu, sigma=np.asarray(sigma, float))
    return pw / (1.0 - pp)


def reference_fair(vis: pd.DataFrame, sig: dict, ref: str) -> pd.DataFrame:
    """(game_id, mu, sigma, p_home) from the reference spread visible at T."""
    sp = vis[vis["market"] == "spreads"]
    if ref == "pinnacle":
        sp = sp[sp["book"] == H.SHARP]
    elif ref == "consensus":
        sp = sp[sp["book"].isin(H.BETTABLE)]
    else:
        raise ValueError(ref)
    f = H.market_fair(sp, sig)
    f = f[f["market"] == "spreads"][["game_id", "mu", "sigma"]].copy()
    f["p_home"] = p_home_from_margin(f["mu"], f["sigma"])
    return f[np.isfinite(f["p_home"])].reset_index(drop=True)


def favourite_home(ref: pd.DataFrame) -> pd.Series:
    """game_id -> True when the reference makes the HOME team the favourite.
    Exactly 0.5 has no favourite and is left out."""
    r = ref[ref["p_home"] != 0.5]
    return pd.Series((r["p_home"] > 0.5).to_numpy(), index=r["game_id"].to_numpy())


def orient_games(games: pd.DataFrame, fav_home: pd.Series) -> pd.DataFrame:
    """Games with a favourite, teams swapped where the favourite is away."""
    g = games[games["game_id"].isin(fav_home.index)].copy()
    swap = ~g["game_id"].map(fav_home).astype(bool)
    for a, b in (("home_score", "away_score"), ("home_team", "away_team")):
        g.loc[swap, [a, b]] = g.loc[swap, [b, a]].to_numpy()
    return g.reset_index(drop=True)


def orient_h2h(q: pd.DataFrame, fav_home: pd.Series) -> pd.DataFrame:
    """Moneyline quotes of games with a favourite, prices swapped where the
    favourite is away (price_a is then always the favourite's price)."""
    x = q[(q["market"] == "h2h") & q["game_id"].isin(fav_home.index)].copy()
    swap = ~x["game_id"].map(fav_home).astype(bool)
    x.loc[swap, ["price_a", "price_b"]] = x.loc[swap, ["price_b", "price_a"]].to_numpy()
    return x.reset_index(drop=True)


def f6a_strength(fair: pd.DataFrame) -> pd.DataFrame:
    """(game_id, strength): minus the absolute fair home margin at T."""
    s = fair[(fair["market"] == "spreads") & np.isfinite(fair["mu"].astype(float))]
    return pd.DataFrame({"game_id": s["game_id"].to_numpy(),
                         "strength": -np.abs(s["mu"].astype(float).to_numpy())})


def f6a_placebo(neutral: pd.DataFrame, st: pd.DataFrame, games: pd.DataFrame,
                run: int) -> pd.DataFrame:
    """Placebo run `run`: the strength column shuffled between games on the same
    date; every offer keeps its price at the market's own fair line."""
    sh = H.shuffle_within_date(st.assign(market="totals"), games, np.random.default_rng(run))
    return neutral.merge(sh[["game_id", "strength"]], on="game_id", how="left")


def team_sigma(close: pd.DataFrame, games: pd.DataFrame,
               min_games: int = MIN_PRIOR_GAMES) -> dict:
    """{(season, team_totals_home|away): sigma}, fit on seasons BEFORE S.

    The team total Pinnacle's close implies: home = (total - spread_home) / 2,
    away = (total + spread_home) / 2. sigma = SD of (team score - that), home
    and away pooled. NaN where fewer than `min_games` earlier games exist."""
    c = close[close["market"].isin(["spreads", "totals"])]
    w = c.pivot_table(index=["game_id", "season"], columns="market", values="close_line",
                      aggfunc="last").dropna().reset_index()
    w = w.merge(games[["game_id", "home_score", "away_score"]], on="game_id")
    home = w["home_score"] - (w["totals"] - w["spreads"]) / 2.0
    away = w["away_score"] - (w["totals"] + w["spreads"]) / 2.0
    res = pd.DataFrame({"season": np.concatenate([w["season"], w["season"]]),
                        "resid": np.concatenate([home, away])})
    out = {}
    for s in sorted(games["season"].unique()):
        prior = res[res["season"] < s]
        v = float(prior["resid"].std()) if len(prior) >= 2 * min_games else np.nan
        for m in TT_MARKETS:
            out[(int(s), m)] = v
    return out


def combine_times(t_slate: pd.DataFrame, t_pe: pd.DataFrame) -> pd.DataFrame:
    """One T per game for the team-total cells: the LATER of the slate's D fetch
    and the per-game team-total purchase (both are then in hand at T)."""
    x = t_slate[["game_id", "T"]].merge(t_pe[["game_id", "T"]], on="game_id", how="outer",
                                        suffixes=("_slate", "_pe"))
    x["T"] = x[["T_slate", "T_pe"]].max(axis=1)
    return x[["game_id", "T"]].reset_index(drop=True)


def own_book_ml_fair(vis: pd.DataFrame, sig: dict) -> dict:
    """{book: (game_id, market='h2h', p_home)} from THAT book's spread at T."""
    out = {}
    for b in H.BETTABLE:
        sp = vis[(vis["book"] == b) & (vis["market"] == "spreads")]
        if sp.empty:
            continue
        f = H.market_fair(sp, sig)
        f = f[f["market"] == "spreads"]
        p = p_home_from_margin(f["mu"], f["sigma"])
        fr = pd.DataFrame({"game_id": f["game_id"].to_numpy(), "market": "h2h",
                           "mu": np.nan, "sigma": np.nan, "p_home": p})
        out[b] = fr[np.isfinite(fr["p_home"])].reset_index(drop=True)
    return out


def own_book_total_fair(vis: pd.DataFrame, sig: dict, sig_tt: dict) -> dict:
    """{book: (game_id, market='totals', mu, sigma)}: fair full-game total =
    mu(home team total) + mu(away team total) from THAT book's team totals,
    sigma = the season's full-game totals sigma."""
    out = {}
    s2 = {**sig, **sig_tt}
    season = vis.drop_duplicates("game_id").set_index("game_id")["season"]
    for b in H.BETTABLE:
        tt = vis[(vis["book"] == b) & vis["market"].isin(TT_MARKETS)]
        if tt.empty:
            continue
        f = H.market_fair(tt, s2)
        w = f.pivot_table(index="game_id", columns="market", values="mu", aggfunc="first")
        if not set(TT_MARKETS) <= set(w.columns):
            continue
        w = w.dropna(subset=list(TT_MARKETS))
        sg =[sig.get((int(season[g]), "totals"), np.nan) for g in w.index]
        fr = pd.DataFrame({"game_id": w.index.to_numpy(), "market": "totals",
                           "mu": (w["team_totals_home"] + w["team_totals_away"]).to_numpy(),
                           "sigma": sg, "p_home": np.nan})
        out[b] = fr[np.isfinite(fr["mu"]) & np.isfinite(fr["sigma"])].reset_index(drop=True)
    return out


def price_own_book(off: pd.DataFrame, fairs: dict, empty: pd.DataFrame) -> pd.DataFrame:
    """Each book's offers priced ONLY under that book's own fair number."""
    parts = [H.fair_offers(off[off["book"] == b], f) for b, f in fairs.items() if len(f)]
    parts = [p for p in parts if len(p)]
    return pd.concat(parts, ignore_index=True) if parts else empty


def shuffled_own_book(fairs: dict, games: pd.DataFrame, run: int) -> dict:
    rng = np.random.default_rng(run)
    return {b: (H.shuffle_within_date(f, games, rng) if len(f) else f)
            for b, f in sorted(fairs.items())}


# ── one decision point of each family ───────────────────────────────────────

def f2_point(data: H.Data, point: str, ref: str, sig: dict, runs: int = PLACEBO_RUNS) -> dict:
    t = H.decision_times(data.fetches, data.games, point)
    vis = H.visible(data.quotes, t)
    rf = reference_fair(vis, sig, ref)
    fav = favourite_home(rf)
    od = H.Data(games=orient_games(data.games, fav), quotes=orient_h2h(data.quotes, fav),
                fetches=data.fetches)
    ovis = orient_h2h(vis, fav)
    off = H.offers(ovis)
    p_fav = np.where(fav.to_numpy(), rf.set_index("game_id").loc[fav.index, "p_home"].to_numpy(),
                     1.0 - rf.set_index("game_id").loc[fav.index, "p_home"].to_numpy())
    model = pd.DataFrame({"game_id": fav.index.to_numpy(), "market": "h2h",
                          "mu": np.nan, "sigma": np.nan, "p_home": p_fav})
    cand = H.fair_offers(off, model)
    neutral = H.fair_offers(off, H.market_fair(ovis, sig))
    placebo = [H.fair_offers(off, H.shuffle_within_date(model, od.games, np.random.default_rng(r)))
               for r in range(runs)]
    all_off = H.offers(vis)
    priced = set(all_off.loc[(all_off["market"] == "h2h") & all_off["book"].isin(H.BETTABLE), "game_id"])
    return {"times": t, "od": od, "cand": cand, "neutral": neutral, "placebo": placebo,
            "model": model, "priced": priced, "modelled": set(model["game_id"])}


def f6a_point(data: H.Data, point: str, sig: dict, runs: int = PLACEBO_RUNS) -> dict:
    t = H.decision_times(data.fetches, data.games, point)
    vis = H.visible(data.quotes, t)
    mf = H.market_fair(vis, sig)
    st = f6a_strength(mf)
    off = H.offers(vis)
    off = off[off["market"] == "totals"]
    neutral = H.fair_offers(off, mf)
    cand = neutral.merge(st, on="game_id", how="left")
    placebo = [f6a_placebo(neutral, st, data.games, r) for r in range(runs)]
    priced = set(neutral.loc[neutral["book"].isin(H.BETTABLE), "game_id"])
    return {"times": t, "cand": cand, "neutral": neutral, "placebo": placebo,
            "priced": priced, "modelled": set(st["game_id"]) & set(neutral["game_id"])}


def f6d_ml_point(data: H.Data, point: str, sig: dict, runs: int = PLACEBO_RUNS) -> dict:
    t = H.decision_times(data.fetches, data.games, point)
    vis = H.visible(data.quotes, t)
    off = H.offers(vis)
    off = off[off["market"] == "h2h"]
    neutral = H.fair_offers(off, H.market_fair(vis, sig))
    empty = neutral.iloc[0:0]
    fairs = own_book_ml_fair(vis, sig)
    cand = price_own_book(off, fairs, empty)
    placebo = [price_own_book(off, shuffled_own_book(fairs, data.games, r), empty)
               for r in range(runs)]
    priced = set(neutral.loc[neutral["book"].isin(H.BETTABLE), "game_id"])
    return {"times": t, "cand": cand, "neutral": neutral, "placebo": placebo,
            "priced": priced, "modelled": set(cand["game_id"])}


def f6d_total_point(data: H.Data, point: str, sig: dict, sig_tt: dict, pe: pd.DataFrame,
                    runs: int = PLACEBO_RUNS) -> dict:
    t_slate = H.decision_times(data.fetches, data.games, point)
    tt = pe[pe["market"].isin(TT_MARKETS)] if len(pe) else pe
    if point == "D" and len(tt):
        t = combine_times(t_slate, H.per_event_times(tt, "D"))
        quotes = pd.concat([data.quotes, tt], ignore_index=True)
    else:                    # team totals count only at D (§6.4 amendment)
        t, quotes = t_slate, data.quotes
    vis = H.visible(quotes, t)
    full = vis[vis["market"].isin(H.MARKETS)]
    off = H.offers(full)
    off = off[off["market"] == "totals"]
    neutral = H.fair_offers(off, H.market_fair(full, sig))
    empty = neutral.iloc[0:0]
    fairs = own_book_total_fair(vis, sig, sig_tt) if point == "D" and len(tt) else {}
    cand = price_own_book(off, fairs, empty)
    placebo = [price_own_book(off, shuffled_own_book(fairs, data.games, r), empty)
               for r in range(runs)]
    priced = set(neutral.loc[neutral["book"].isin(H.BETTABLE), "game_id"])
    return {"times": t, "cand": cand, "neutral": neutral, "placebo": placebo,
            "priced": priced, "modelled": set(cand["game_id"])}


# ── families ────────────────────────────────────────────────────────────────

def _season_bets(row: dict, season: int) -> int:
    if season == H.REGIME:
        return int(row.get("n_2021", 0))
    if season == H.CONFIRM:
        return int(row.get("n_confirm", 0))
    return int(row.get(f"n_{season}", 0))


def population_rows(family: str, point: str, market: str, games: pd.DataFrame, built: dict,
                    rows: list[dict], axis: dict | None = None) -> list[dict]:
    """Per season: games, games reaching the decision point, games with a
    deciding price in the market, games with a model number; and bets per cell."""
    out = []
    at = set(built["times"]["game_id"])
    for s, gs in games.groupby("season"):
        ids = set(gs["game_id"])
        base = {"family": family, "point": point, "market": market, "season": int(s),
                **(axis or {}), "games": len(ids), "games_at_point": len(ids & at),
                "games_priced": len(ids & built["priced"]),
                "games_model": len(ids & built["modelled"])}
        for r in rows:
            out.append({**base, "side": r["side"], "cut_index": r["cut_index"], "cut": r["cut"],
                        "bets": _season_bets(r, int(s))})
    return out


def f2_cells(data, point, ref, sig, runs=PLACEBO_RUNS) -> tuple[list[dict], dict]:
    """The 12 F2 cells of one (decision point, reference), graded on the
    oriented copy; rows say fav / dog."""
    b = f2_point(data, point, ref, sig, runs)
    r = H.run_cells(b["od"], "F2", point, b["cand"], b["neutral"], F2_CUTS,
                    {"h2h": ["home", "away"]}, close=H.pinnacle_close(b["od"]), sig=sig,
                    placebo=b["placebo"])
    for x in r:
        x["side"] = FAV_DOG[x["side"]]
        x["axis_ref"] = ref
    return r, b


def run_f2(data, close, sig, runs=PLACEBO_RUNS):
    rows, pop = [], []
    for point in F2_POINTS:
        for ref in F2_REFS:
            r, b = f2_cells(data, point, ref, sig, runs)
            rows += r
            pop += population_rows("F2", point, "h2h", data.games, b, r, {"axis_ref": ref})
    return rows, pop


def run_f6a(data, close, sig, runs=PLACEBO_RUNS):
    rows, pop = [], []
    for point in F6A_POINTS:
        b = f6a_point(data, point, sig, runs)
        r = H.run_cells(data, "F6a", point, b["cand"], b["neutral"], F6A_CUTS,
                        {"totals": ["over"]}, close=close, sig=sig, placebo=b["placebo"],
                        strength="strength")
        rows += r
        pop += population_rows("F6a", point, "totals", data.games, b, r)
    return rows, pop


def run_f6d(data, close, sig, pe, runs=PLACEBO_RUNS):
    rows, pop = [], []
    sig_tt = team_sigma(close, data.games)
    for point in F6D_POINTS:
        b = f6d_ml_point(data, point, sig, runs)
        r = H.run_cells(data, "F6d", point, b["cand"], b["neutral"], F6D_CUTS,
                        {"h2h": ["home", "away"]}, close=close, sig=sig, placebo=b["placebo"])
        rows += r
        pop += population_rows("F6d", point, "h2h", data.games, b, r)
    for point in F6D_POINTS:
        b = f6d_total_point(data, point, sig, sig_tt, pe, runs)
        r = H.run_cells(data, "F6d", point, b["cand"], b["neutral"], F6D_CUTS,
                        {"totals": ["over", "under"]}, close=close, sig=sig, placebo=b["placebo"],
                        choose_seasons=F6D_TT_CHOOSE)
        rows += r
        pop += population_rows("F6d", point, "totals", data.games, b, r)
    return rows, pop


def check_cells(family: str, rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    assert len(df) == EXPECTED_CELLS[family], (family, len(df), EXPECTED_CELLS[family])
    axes = ["point", "market", "side", "cut"] + [c for c in df.columns if c.startswith("axis_")]
    assert not df.duplicated(axes).any(), f"{family}: duplicate cell"
    if family == "F2":
        assert set(df["side"]) <= {"fav", "dog"}
    # float arrays, so a column whose placebo ROIs are all NaN (no choosing
    # season graded) is stored as list<double>, not list<null> read back as None
    df["placebo_rois"] = df["placebo_rois"].apply(lambda v: np.asarray(v, dtype=float))
    return df


# ── synthetic checks (run by --smoke before the real season) ────────────────

def synthetic_checks() -> None:
    H.check()
    p = p_home_from_margin([0.0, 4.0, -4.0], [12.0, 12.0, 12.0])
    assert abs(p[0] - 0.5) < 1e-12 and p[1] > 0.5 and abs(p[1] + p[2] - 1.0) < 1e-12
    g = pd.DataFrame({"game_id": ["a", "b"], "home_score": [100, 90], "away_score": [90, 100],
                      "home_team": ["X", "Y"], "away_team": ["Z", "W"]})
    og = orient_games(g, pd.Series([True, False], index=["a", "b"]))
    assert og["home_score"].tolist() == [100, 100] and og["home_team"].tolist() == ["X", "W"]
    st = f6a_strength(pd.DataFrame({"game_id": ["a", "b"], "market": "spreads", "mu": [-1.5, 3.0]}))
    assert st["strength"].tolist() == [-1.5, -3.0]
    assert sum(EXPECTED_CELLS.values()) == 120
    assert len(F2_POINTS) * len(F2_CUTS) * 2 * len(F2_REFS) == 96
    assert len(F6A_POINTS) * len(F6A_CUTS) == 8
    assert 2 * 2 * len(F6D_POINTS) * len(F6D_CUTS) == 16
    print("synthetic checks pass")


# ── main ────────────────────────────────────────────────────────────────────

def run(mode: str, ledger: Path | None = None, runs: int = PLACEBO_RUNS) -> dict:
    go_guard(mode == "full")
    res = results_dir()
    out = res / "smoke" if mode == "smoke" else res
    out.mkdir(parents=True, exist_ok=True)
    if mode == "smoke":
        synthetic_checks()
    cache = cache_for(mode, ledger, out)
    seasons = seasons_for(mode)
    data = H.load(cache=cache, seasons=seasons)
    if mode == "smoke":
        assert set(data.games["season"]) == set(SMOKE_SEASONS), "smoke must read 2020-21 only"
    pe = H.load_per_event(data.games, cache=cache)
    close = H.pinnacle_close(data)
    sig = H.close_sigma(close, data.games)
    summary = {"seasons": sorted(int(s) for s in data.games["season"].unique()),
               "load": data.notes, "cells": {}}
    for fam, fn in (("F2", lambda: run_f2(data, close, sig, runs)),
                    ("F6a", lambda: run_f6a(data, close, sig, runs)),
                    ("F6d", lambda: run_f6d(data, close, sig, pe, runs))):
        rows, pop = fn()
        cells = check_cells(fam, rows)
        cells.to_parquet(out / f"cells_{fam}.parquet")
        pd.DataFrame(pop).to_parquet(out / f"population_{fam}.parquet")
        summary["cells"][fam] = len(cells)
        print(f"{fam}: {len(cells)} cells -> {out / f'cells_{fam}.parquet'}", flush=True)
    assert sum(summary["cells"].values()) == 120
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true", help="2020-21 only, plus synthetic checks")
    g.add_argument("--full", action="store_true", help="every season (needs NBA_GAME2_GO=1)")
    ap.add_argument("--ledger", type=Path, default=None,
                    help="--smoke only: a purchase ledger parquet when the cache has none")
    a = ap.parse_args()
    warnings.filterwarnings("ignore", message="no explicit representation of timezones")
    s = run("smoke" if a.smoke else "full", ledger=a.ledger)
    print(s)


if __name__ == "__main__":
    main()
