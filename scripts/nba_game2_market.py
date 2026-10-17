"""Second NBA game-market search, families F2, F6a and F6d: the market against itself.

docs/nba_models_2026.md §6.3 pre-registers these cells (and only these); the
shared harness scripts/nba_game_harness.py prices, chooses and grades every
one of them, and scripts/nba_game2_verdict.py judges them. This lab only builds
each family's fair numbers and emits its cells. It never reads a result to set
anything.

PRICING (§6.3, and the second 2026-10-17 amendment in §6.5). Every market
price this lab reads -- F2's spread-to-win mapping, F6a's market fair line,
both F6d comparisons, the blind bets and closing-line value -- goes through the
EMPIRICAL distribution of results around Pinnacle's closing number on the
seasons before S (H.close_dist, built in market_pricing). Team totals use their
own empirical distribution (team_total_dist below). No bell curve is used.

FAMILIES AND CELLS (120, asserted)

  F2   Spread-implied win probability against the moneyline (Moskowitz &
       Vasudevan 2020, comparing the win probability implied by a game's spread
       with its moneyline). The REFERENCE spread at T -- axis_ref "pinnacle":
       Pinnacle's own spread quote; "consensus": the median over the deciding
       books (config.BEST_LINE_BOOKMAKERS) of the home margin each book's spread
       implies -- is turned into the centre mu of the empirical home-margin
       distribution (H.market_fair: mu solved at the quote's no-vig price), and
       p_home = P(margin > 0) with the mass on a level margin removed (an NBA
       game cannot end level). Bet the moneyline side where EV under that
       p_home clears the cut.
       Sides fav / dog: the favourite is the team the REFERENCE makes more
       likely than not at T. A LEVEL reference has no favourite and its game is
       outside both cells: p_home within 1e-9 of 0.5, or a posted reference
       spread of 0 (Pinnacle's own number; for "consensus" the median of the
       deciding books' posted numbers). A game with no reference number at T
       is outside too.
       Points A, B, C, D x EV cuts 0, .01, .02, .03, .05, .08 x 2 sides x 2
       references = 96.
  F6a  Overtime tail on totals: bet the over when the POSTED spread at T is
       within k points: Pinnacle's spread_home where it quotes one coherently,
       else the median of the deciding books' posted spread_home. It is the
       posted number, never a centre solved from the price, so price skew does
       not move a game between cells and a home and an away favourite of the
       same size are treated alike. A RULE: offers are priced at the market's
       own fair total, strength = 1e-9 - abs(posted), cut = -k, so strength
       >= cut is abs(posted) <= k with a 1e-9 tolerance. A game with no
       posted spread at T has no rule number and is outside the cell's
       population, its blind bets included (§6.5). Points B, C x
       k = 1, 2, 3, 4 = 8.
  F6d  One book against itself. (i) moneyline: each deciding book's moneyline
       priced against THAT book's own spread (spread -> p_home as in F2). Both
       quotes must come from the SAME fetch (same fetch_at); a game where the
       book's visible moneyline and spread come from different fetches is
       dropped for that book, because the gap could be a line move.
       (ii) total: each deciding book's full-game total priced against THAT
       book's own team totals, fair total = mu(home team total) + mu(away team
       total), each solved at the team total's no-vig price through
       team_total_dist, the full total then priced through the market's
       totals distribution. Team totals are per-game purchases
       (H.load_per_event), 2024-25 on, and count only at D: only the
       purchase H.per_event_times keeps (inside 45-75 minutes) joins the
       quotes, so one bought 76-135 minutes out is never priced in a D cell
       even though it is under an hour old at T. They are a second purchase, so (ii) cannot share a fetch with the slate
       total and T is the later of the two. Markets moneyline, total x 2 sides
       x C, D x EV cuts .01, .03 = 16. The four total cells at C have no
       team-total quote by rule and are emitted empty. Total cells choose on
       2024-25 alone, and their 95% gate at D reads the team-total purchase
       times (run_cells times=).

SIDES. Every bet the harness grades carries its REAL side (home / away /
over / under). F2's fav and dog are per-game sides: each cell passes the label
"fav" or "dog" with a side_pick column naming that game's real side (the
reference's favourite or underdog at T), so the harness keeps the offer on
that side and settles, blind-bets and closes the real side.

INPUTS AND HOW EACH IS DATED (no look-ahead)

  Game-line quotes     H.visible at T: a fetch at or before T, no older than
                       60 minutes, before tip. T is the fetch instant from the
                       purchase ledgers (H.decision_times).
  Reference / own-book spreads, posted spreads, team totals: the same visible
                       quotes at T.
  Team totals          per-game purchase, dated by the feed's own snapshot,
                       used only when that purchase falls in D's 45-75-minute
                       window. The total cells' T at D is the LATER of the
                       slate's D fetch and the team-total purchase, so both
                       are in hand at T.
  Margin / total distribution  H.close_dist: results minus Pinnacle's close on
                       the seasons before S. 2020-21 has no earlier priced
                       season, so the harness falls back to 2020-21 itself:
                       2020-21's figures are IN-SAMPLE (reported season, never
                       chosen on).
  Team-total distribution  team_total_dist: team score minus the team total
                       implied by Pinnacle's closing spread and total, home and
                       away pooled, on the seasons before S
                       (H.dist_by_season); no entry with fewer than 300 earlier
                       games (the harness's own-season fallback is not used).

FIT SEASONS PER GRADED SEASON (walk-forward; nothing else is fitted)

  graded 2021  margin/total: 2021 itself (in-sample fallback); team totals: none
  graded 2022  margin/total and team totals: 2021
  graded 2023  2021-2022
  graded 2024  2021-2023
  graded 2025  2021-2024
  graded 2026  2021-2025

PLACEBO: 20 runs, run r shuffles the family's fair numbers between games on
the same date and market with H.shuffle_within_date(rng = default_rng(r)):
F2 the reference's favourite probability (each game keeps its own favourite
and underdog side; only the probability moves); F6a the strength column only
(prices stay at the market's fair line); F6d each book's own fair number,
book by book.

    PYTHONPATH=. python -m scripts.nba_game2_market --smoke
    NBA_GAME2_GO=1 PYTHONPATH=. python -m scripts.nba_game2_market --full

Writes <results>/cells_<family>.parquet (placebo_rois typed list<double>) and
<results>/population_<family>.parquet; <results> is NBA_GAME2_RESULTS (default
%TEMP%/nba_game_edge/results). --smoke writes under <results>/smoke and grades
2020-21 only. --full refuses to run unless NBA_GAME2_GO=1 (the owner runs it
after the price data is refreshed), and refuses a cache that prices fewer than
90% of games in any of 2020-21 to 2025-26 or whose rows match no purchase
record (H.load require_seasons).
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
F2_SIDES = ("fav", "dog")
F6A_POINTS = ("B", "C")
F6A_K = (1, 2, 3, 4)
F6A_CUTS = tuple(-float(k) for k in F6A_K)        # strength = 1e-9 - abs(posted) >= -k
F6D_POINTS = ("C", "D")
F6D_CUTS = (0.01, 0.03)
F6D_TT_CHOOSE = (2025,)                            # team totals start 2024-25
EXPECTED_CELLS = {"F2": 96, "F6a": 8, "F6d": 16}
PLACEBO_RUNS = 20
TT_MARKETS = ("team_totals_home", "team_totals_away")
SMOKE_SEASONS = (2021,)
FULL_SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)
MIN_PRIOR_GAMES = 300
LEVEL_TOL = 1e-9                                   # F2: a level reference has no favourite
F6A_TOL = 1e-9                                     # F6a: abs(posted) <= k, within 1e-9


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


def load_for(mode: str, cache: Path) -> H.Data:
    """The data a run grades. --full names every season it grades, so H.load
    refuses a cache that prices fewer than 90% of any season's games or whose
    rows match no purchase record, and the coverage is asserted again here
    before any cell is graded. --smoke reads 2020-21 only."""
    if mode == "full":
        data = H.load(cache=cache, require_seasons=FULL_SEASONS)
        share = data.notes.get("games_priced_share", {})
        short = {s: share.get(s, 0.0) for s in FULL_SEASONS
                 if share.get(s, 0.0) < H.MIN_PRICED_SHARE}
        assert not short, f"--full: the cache prices too few games in {short}"
        return data
    data = H.load(cache=cache, seasons=seasons_for(mode))
    assert set(data.games["season"]) == set(SMOKE_SEASONS), "smoke must read 2020-21 only"
    return data


# ── pricing: the empirical distributions ────────────────────────────────────

def market_pricing(close: pd.DataFrame, games: pd.DataFrame) -> dict:
    """(season, market) -> the empirical distribution of results around
    Pinnacle's close on the seasons before S. Every market price in this lab
    (F2, F6a, F6d, the blind bets, closing-line value) is read through it."""
    return H.close_dist(close, games)


def has_pricing(v) -> bool:
    """True for an empirical distribution or a finite float spread."""
    if isinstance(v, H.ResidDist):
        return True
    try:
        return v is not None and bool(np.isfinite(float(v)))
    except (TypeError, ValueError):
        return False


def team_total_resid(close: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """(season, market='team_totals', resid): each team's score minus the team
    total Pinnacle's close implies -- home = (total - spread_home) / 2, away =
    (total + spread_home) / 2 -- home and away pooled."""
    c = close[close["market"].isin(["spreads", "totals"])]
    w = c.pivot_table(index=["game_id", "season"], columns="market", values="close_line",
                      aggfunc="last").dropna().reset_index()
    if w.empty or not {"spreads", "totals"} <= set(w.columns):
        return pd.DataFrame({"season": pd.Series([], dtype=int), "market": pd.Series([], dtype=str),
                             "resid": pd.Series([], dtype=float)})
    w = w.merge(games[["game_id", "home_score", "away_score"]], on="game_id")
    home = w["home_score"] - (w["totals"] - w["spreads"]) / 2.0
    away = w["away_score"] - (w["totals"] + w["spreads"]) / 2.0
    return pd.DataFrame({"season": np.concatenate([w["season"], w["season"]]).astype(int),
                         "market": "team_totals",
                         "resid": np.concatenate([home, away]).astype(float)})


def team_total_dist(close: pd.DataFrame, games: pd.DataFrame,
                    min_games: int = MIN_PRIOR_GAMES) -> dict:
    """{(season, team_totals_home|away): ResidDist} on the seasons BEFORE S
    (H.dist_by_season), one pooled distribution under both keys. A season with
    fewer than `min_games` earlier games gets no entry: the harness's fallback
    to the season's own results would be look-ahead."""
    res = team_total_resid(close, games)
    if res.empty:
        return {}
    min_rows = 2 * min_games                    # two residuals per game
    seasons = [int(s) for s in sorted(games["season"].unique())
               if int((res["season"] < int(s)).sum()) >= min_rows]
    d = H.dist_by_season(res, seasons, min_prior=min_rows)
    return {(int(s), m): dist for (s, _), dist in d.items() for m in TT_MARKETS}


# ── the rules (small, so each has its own test) ─────────────────────────────

def p_home_from_margin(mu, sigma) -> np.ndarray:
    """P(home wins) from the home margin's centre and its pricing model (an
    empirical distribution, or a float spread): the mass on margin 0 is removed
    (no NBA game ends level), P(win) / (P(win) + P(lose))."""
    mu = np.asarray(mu, float)
    n = mu.shape
    pw, pp = H.side_probs(np.full(n, "spreads"), np.full(n, "home"), np.zeros(n),
                          mu=mu, sigma=np.asarray(sigma, dtype=object))
    return pw / (1.0 - pp)


def posted_spread(vis: pd.DataFrame) -> pd.Series:
    """game_id -> the spread_home posted at T: Pinnacle's coherent quote where
    it has one, else the median of the deciding books' coherent quotes."""
    sp = vis[(vis["market"] == "spreads") & vis["coherent"]]
    pin = sp[sp["book"] == H.SHARP].drop_duplicates("game_id").set_index("game_id")["line"]
    med = sp[sp["book"].isin(H.BETTABLE)].groupby("game_id")["line"].median()
    return pin.combine_first(med).astype(float)


def reference_fair(vis: pd.DataFrame, sig: dict, ref: str) -> pd.DataFrame:
    """(game_id, mu, sigma, p_home, posted) from the reference spread visible at T."""
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
    f["posted"] = f["game_id"].map(posted_spread(sp)).astype(float)
    return f[np.isfinite(f["p_home"])].reset_index(drop=True)


def favourite_home(ref: pd.DataFrame) -> pd.Series:
    """game_id -> True when the reference makes the HOME team the favourite.
    A level reference has no favourite and is left out: p_home within 1e-9 of
    0.5, or a posted reference spread of 0."""
    level = ((ref["p_home"] - 0.5).abs() < LEVEL_TOL) | (ref["posted"].abs() < LEVEL_TOL)
    r = ref[~level]
    return pd.Series((r["p_home"] > 0.5).to_numpy(), index=r["game_id"].to_numpy())


def f6a_strength(vis: pd.DataFrame) -> pd.DataFrame:
    """(game_id, strength): 1e-9 minus the absolute POSTED spread at T, so
    strength >= -k is abs(posted) <= k within the tolerance."""
    p = posted_spread(vis)
    p = p[np.isfinite(p)]
    return pd.DataFrame({"game_id": p.index.to_numpy(),
                         "strength": F6A_TOL - np.abs(p.to_numpy())})


def f6a_placebo(neutral: pd.DataFrame, st: pd.DataFrame, games: pd.DataFrame,
                run: int) -> pd.DataFrame:
    """Placebo run `run`: the strength column shuffled between games on the same
    date; every offer keeps its price at the market's own fair line."""
    sh = H.shuffle_within_date(st.assign(market="totals"), games, np.random.default_rng(run))
    return neutral.merge(sh[["game_id", "strength"]], on="game_id", how="inner")


def combine_times(t_slate: pd.DataFrame, t_pe: pd.DataFrame) -> pd.DataFrame:
    """One T per game for the team-total cells: the LATER of the slate's D fetch
    and the per-game team-total purchase (both are then in hand at T)."""
    x = t_slate[["game_id", "T"]].merge(t_pe[["game_id", "T"]], on="game_id", how="outer",
                                        suffixes=("_slate", "_pe"))
    x["T"] = x[["T_slate", "T_pe"]].max(axis=1)
    return x[["game_id", "T"]].reset_index(drop=True)


def in_window_purchases(tt: pd.DataFrame, t_pe: pd.DataFrame) -> pd.DataFrame:
    """The team-total rows of the purchases H.per_event_times kept (one per
    game, inside D's 45-75-minute window), matched on the purchase instant.
    A purchase outside the window is dropped before it joins the quotes: left
    in, a total bought 76-135 minutes out is still visible at T (under an hour
    old) and would be priced in a D cell the gate counts as not reaching D."""
    keep = t_pe[["game_id", "T"]].rename(columns={"T": "fetch_at"})
    return tt.merge(keep, on=["game_id", "fetch_at"]).reset_index(drop=True)


def own_book_ml_fair(vis: pd.DataFrame, sig: dict) -> dict:
    """{book: (game_id, market='h2h', p_home)} from THAT book's spread at T,
    only where the book's visible spread and moneyline come from one fetch."""
    out = {}
    for b in H.BETTABLE:
        sp = vis[(vis["book"] == b) & (vis["market"] == "spreads")]
        ml = vis[(vis["book"] == b) & (vis["market"] == "h2h")]
        same = set(sp.merge(ml[["game_id", "fetch_at"]], on=["game_id", "fetch_at"])["game_id"])
        sp = sp[sp["game_id"].isin(same)]
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
    mu(home team total) + mu(away team total) from THAT book's team totals
    (solved through sig_tt), priced through the season's full-game totals
    distribution in sig."""
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
        sg = pd.Series([sig.get((int(season[g]), "totals")) for g in w.index], dtype=object)
        fr = pd.DataFrame({"game_id": w.index.to_numpy(), "market": "totals",
                           "mu": (w["team_totals_home"] + w["team_totals_away"]).to_numpy(),
                           "sigma": sg.to_numpy(), "p_home": np.nan})
        ok = np.isfinite(fr["mu"].astype(float)) & fr["sigma"].map(has_pricing).astype(bool)
        out[b] = fr[ok].reset_index(drop=True)
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
    """F2 at one (decision point, reference). Offers keep their real side; per
    side ("fav", "dog") the frames carry side_pick = that game's real side."""
    t = H.decision_times(data.fetches, data.games, point)
    vis = H.visible(data.quotes, t)
    rf = reference_fair(vis, sig, ref)
    fav = favourite_home(rf)
    gids = fav.index.to_numpy()
    fav_home = fav.to_numpy().astype(bool)
    p_home = rf.set_index("game_id").loc[gids, "p_home"].to_numpy(dtype=float)
    model = pd.DataFrame({"game_id": gids, "market": "h2h", "mu": np.nan, "sigma": np.nan,
                          "p_home": p_home})
    picks = pd.DataFrame({"game_id": gids, "fav": np.where(fav_home, "home", "away"),
                          "dog": np.where(fav_home, "away", "home")})
    off = H.offers(vis)
    off = off[off["market"] == "h2h"]
    base = H.fair_offers(off, model)
    neutral0 = H.fair_offers(off, H.market_fair(vis[vis["market"] == "h2h"], sig))
    # placebo: the favourite's probability moves between games on a date; each
    # game keeps its own favourite and underdog
    p_fav = pd.DataFrame({"game_id": gids, "market": "h2h",
                          "p_home": np.where(fav_home, p_home, 1.0 - p_home)})
    placebo0 = []
    for r in range(runs):
        sh = H.shuffle_within_date(p_fav, data.games, np.random.default_rng(r))
        pf = sh.set_index("game_id")["p_home"].reindex(gids).to_numpy(dtype=float)
        placebo0.append(H.fair_offers(off, model.assign(p_home=np.where(fav_home, pf, 1.0 - pf))))

    def with_pick(x, side, how="inner"):
        return x.merge(picks[["game_id", side]].rename(columns={side: "side_pick"}),
                       on="game_id", how=how)

    priced = set(off.loc[off["book"].isin(H.BETTABLE), "game_id"])
    return {"times": t, "model": model, "picks": picks,
            "cand": {s: with_pick(base, s) for s in F2_SIDES},
            "neutral": {s: with_pick(neutral0, s, how="left") for s in F2_SIDES},
            "placebo": {s: [with_pick(p, s) for p in placebo0] for s in F2_SIDES},
            "priced": priced, "modelled": set(gids)}


def f6a_point(data: H.Data, point: str, sig: dict, runs: int = PLACEBO_RUNS) -> dict:
    t = H.decision_times(data.fetches, data.games, point)
    vis = H.visible(data.quotes, t)
    mf = H.market_fair(vis, sig)
    st = f6a_strength(vis)
    off = H.offers(vis)
    off = off[off["market"] == "totals"]
    fair = H.fair_offers(off, mf)
    priced = set(fair.loc[fair["book"].isin(H.BETTABLE), "game_id"])
    # §6.5: the population is the games the rule produced a number for (a
    # posted spread at T); like the move lab, that one frame is both the
    # candidate and the neutral frame, so every blind bet reads it too.
    cand = fair.merge(st, on="game_id", how="inner")
    placebo = [f6a_placebo(fair, st, data.games, r) for r in range(runs)]
    return {"times": t, "cand": cand, "neutral": cand, "placebo": placebo,
            "priced": priced, "modelled": set(st["game_id"]) & set(fair["game_id"])}


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


NO_TIMES = pd.DataFrame({"game_id": pd.Series([], dtype=object),
                         "T": pd.Series([], dtype="datetime64[ns, UTC]"),
                         "lead_min": pd.Series([], dtype=float)})


def f6d_total_point(data: H.Data, point: str, sig: dict, sig_tt: dict, pe: pd.DataFrame,
                    runs: int = PLACEBO_RUNS) -> dict:
    """`gate_times`: the decision times the 95% gate reads -- at D the
    team-total purchases inside the D window (none bought: no game reaches
    D); at C none (the gate is D's alone)."""
    t_slate = H.decision_times(data.fetches, data.games, point)
    tt = pe[pe["market"].isin(TT_MARKETS)] if len(pe) else pe
    gate_times = None
    if point == "D":
        t_pe = H.per_event_times(tt, "D") if len(tt) else NO_TIMES
        gate_times = t_pe
        if len(tt):
            tt = in_window_purchases(tt, t_pe)
    if point == "D" and len(tt):
        t = combine_times(t_slate, t_pe)
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
    return {"times": t, "gate_times": gate_times, "cand": cand, "neutral": neutral,
            "placebo": placebo, "priced": priced, "modelled": set(cand["game_id"])}


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


def f2_cells(data, point, ref, sig, close=None, runs=PLACEBO_RUNS) -> tuple[list[dict], dict]:
    """The 12 F2 cells of one (decision point, reference): one run_cells call
    per side, each on that side's per-game pick."""
    b = f2_point(data, point, ref, sig, runs)
    close = H.pinnacle_close(data) if close is None else close
    rows = []
    for side in F2_SIDES:
        r = H.run_cells(data, "F2", point, b["cand"][side], b["neutral"][side], F2_CUTS,
                        {"h2h": [side]}, close=close, sig=sig, placebo=b["placebo"][side])
        for x in r:
            x["axis_ref"] = ref
        rows += r
    return rows, b


def run_f2(data, close, sig, runs=PLACEBO_RUNS):
    rows, pop = [], []
    for point in F2_POINTS:
        for ref in F2_REFS:
            r, b = f2_cells(data, point, ref, sig, close=close, runs=runs)
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


def f6d_total_cells(data, point, sig, sig_tt, pe, close=None, runs=PLACEBO_RUNS):
    """The 4 F6d total cells at one point; the D gate reads the team-total
    purchase times, not the slate's."""
    b = f6d_total_point(data, point, sig, sig_tt, pe, runs)
    r = H.run_cells(data, "F6d", point, b["cand"], b["neutral"], F6D_CUTS,
                    {"totals": ["over", "under"]}, close=close, sig=sig, placebo=b["placebo"],
                    choose_seasons=F6D_TT_CHOOSE, times=b["gate_times"])
    return r, b


def run_f6d(data, close, sig, pe, runs=PLACEBO_RUNS):
    rows, pop = [], []
    sig_tt = team_total_dist(close, data.games)
    for point in F6D_POINTS:
        b = f6d_ml_point(data, point, sig, runs)
        r = H.run_cells(data, "F6d", point, b["cand"], b["neutral"], F6D_CUTS,
                        {"h2h": ["home", "away"]}, close=close, sig=sig, placebo=b["placebo"])
        rows += r
        pop += population_rows("F6d", point, "h2h", data.games, b, r)
    for point in F6D_POINTS:
        r, b = f6d_total_cells(data, point, sig, sig_tt, pe, close=close, runs=runs)
        rows += r
        pop += population_rows("F6d", point, "totals", data.games, b, r)
    return rows, pop


def check_cells(family: str, rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    assert len(df) == EXPECTED_CELLS[family], (family, len(df), EXPECTED_CELLS[family])
    axes = ["point", "market", "side", "cut"] + [c for c in df.columns if c.startswith("axis_")]
    assert not df.duplicated(axes).any(), f"{family}: duplicate cell"
    if family == "F2":
        assert set(df["side"]) <= set(F2_SIDES)
    return df


def write_cells(cells: pd.DataFrame, path: Path) -> None:
    """The cell table as parquet, placebo_rois typed list<double>: left to
    pandas, a column whose lists are all NaN (no placebo run bet on a choosing
    season) is stored as list<null> and reads back as None."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    t = pa.Table.from_pandas(cells.drop(columns="placebo_rois"), preserve_index=False)
    pl = pa.array([[float(x) for x in v] for v in cells["placebo_rois"]],
                  type=pa.list_(pa.float64()), from_pandas=False)
    pq.write_table(t.append_column("placebo_rois", pl), path)


# ── synthetic checks (run by --smoke before the real season) ────────────────

def synthetic_checks() -> None:
    H.check()
    p = p_home_from_margin([0.0, 4.0, -4.0], [12.0, 12.0, 12.0])
    assert abs(p[0] - 0.5) < 1e-12 and p[1] > 0.5 and abs(p[1] + p[2] - 1.0) < 1e-12
    skew = H.ResidDist(np.r_[np.full(700, 4.0), np.full(300, -9.0)], "skew")
    assert abs(p_home_from_margin([0.0], [skew])[0] - 0.7) < 1e-9
    lv = favourite_home(pd.DataFrame({"game_id": ["a", "b", "c"], "p_home": [0.6, 0.55, 0.5 - 1e-12],
                                      "posted": [-2.0, 0.0, -1.0]}))
    assert lv.to_dict() == {"a": True}
    vis = pd.DataFrame({"game_id": ["a", "b"], "market": "spreads", "book": H.SHARP,
                        "coherent": True, "line": [-2.0, 2.0]})
    st = f6a_strength(vis).set_index("game_id")["strength"]
    assert (st >= -2.0).all() and not (st >= -1.0).any()
    assert sum(EXPECTED_CELLS.values()) == 120
    assert len(F2_POINTS) * len(F2_CUTS) * len(F2_SIDES) * len(F2_REFS) == 96
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
    data = load_for(mode, cache)
    pe = H.load_per_event(data.games, cache=cache)
    close = H.pinnacle_close(data)
    sig = market_pricing(close, data.games)
    summary = {"seasons": sorted(int(s) for s in data.games["season"].unique()),
               "load": data.notes, "pricing": {f"{k[0]} {k[1]}": repr(v) for k, v in sig.items()},
               "cells": {}}
    for fam, fn in (("F2", lambda: run_f2(data, close, sig, runs)),
                    ("F6a", lambda: run_f6a(data, close, sig, runs)),
                    ("F6d", lambda: run_f6d(data, close, sig, pe, runs))):
        rows, pop = fn()
        cells = check_cells(fam, rows)
        write_cells(cells, out / f"cells_{fam}.parquet")
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
