"""P2 of the fourth NBA search: the first search's market rules, re-graded on the shared harness, 256 cells.

docs/nba_models_2026.md section 8 registers the family; section 8.2 fixes every
choice the row leaves open, written and committed before any P2 cell was
graded. This lab EMITS cells through the shared harness
(scripts/nba_game_harness.py, H); scripts/nba_game2_verdict.py (house_verdict)
judges them. Every quote, decision time, market fair line, choice of bet and
grade is the harness's. The two rules are the first search's own code,
imported: scripts/nba_game_market_lab.sharp_pairs (Pinnacle against every
deciding book in ONE fetch) and gap_candidates (the side an off-market number
favours). No cut, constant or rule here was chosen from a betting result.

THE TWO RULES
  same number  (sharp_pairs, same_number=True) every deciding book quoting in
               the SAME fetch as Pinnacle, at Pinnacle's number (moneylines:
               any). The rule's probability is Pinnacle's proportional no-vig
               share of the side; EV = share x decimal - 1, the first search's
               two-way convention (a push returns the stake and leaves the
               harness's denominator, so the EV is per unit risked given no
               push). Cut: EV >= 0.00 / 0.01 / 0.02 / 0.03; the best-EV offer at
               a deciding book is taken (H.choose, -200 floor).
  off number   (sharp_pairs, same_number=False + gap_candidates) a deciding
               book in the same fetch as Pinnacle hangs a different spread or
               total. strength = the gap in the favoured side's favour (spread:
               the side getting the extra points; total: the under at a higher
               number, the over at a lower one); the other side of that quote
               carries minus the gap, a quote at Pinnacle's number 0. Cut: gap
               >= 0.5 / 1 / 1.5 / 2 (within 1e-9, as the first search). No EV
               floor (section 8 registers none). Among the qualifying offers
               the best EV is taken, every offer priced through the EMPIRICAL
               distribution of results centred on Pinnacle's number and price
               at T (H.market_fair -> H.fair_offers); the first search's normal
               model is not used.

WHICH QUOTE IS A BOOK'S NUMBER (ladders)
  Two deciding books (betrivers, betparx) hang 5-7 team-total rungs in one
  purchase, and three (betrivers, betparx, hardrockbet) list single first-half
  and first-quarter rungs 2+ points off every other book at lopsided prices.
    main rung     per (game, market, book, fetch): the rung whose two prices
                  are closest to even (the first search's `main`), coherent
                  first, ties to the lower number. Every frame reads it, except:
    same number   a book's rung at Pinnacle's number in that fetch, when it
                  hangs one (the first search's sharp_strict merged every rung
                  on the number), else its main rung.
    ladder rule   a first-half, first-quarter or team-total spread or total
                  quote more than 1 point (nba_derivative_lab.OFF_MED_PTS) from
                  the median of the deciding books' main numbers at T is an
                  alternate rung and is never a candidate, an offer or a blind
                  bet (the first search's off_med, extended to team totals).
                  Pinnacle is never dropped. Full-game quotes are not ladders.

PRICING (no look-ahead)
  full game    H.close_dist: results around Pinnacle's last pre-tip price on
               seasons before S (2020-21 its own: reported, never chosen).
  derivatives  per market, results around Pinnacle's number at the per-game
               purchase on DERIVATIVE seasons before S, when they hold >= 300
               games. The first derivative season has none, so it is priced
               on a proxy from seasons before S that needs no derivative
               price: the period result around its share of Pinnacle's
               full-game closing number (first half 0.5, first quarter 0.25,
               by minutes), team totals each team's score around the team
               total Pinnacle's full-game close implies
               (nba_game2_market.team_total_resid, both teams pooled, >= 300
               games). A season's own results never price it. Moneylines need
               no distribution. The rule's own numbers (same-number EV, the
               gap) never read a distribution; it orders offers at different
               numbers, prices the blind bets and names the favourite.

SEASONS AND POINTS
  full game    A, B, C, D (H.decision_times); choosing 2022-2025, confirmed and
               pooled with 2026; 2021 reported.
  derivatives  D only, the per-game purchase inside 45-75 minutes
               (H.per_event_times); every derivative season the cache holds is
               graded, the ones before 2026 choosing; the 95% gate reads the
               purchase times. No closing value (the purchase is the last
               price) and no still-offered check (no later purchase).
  team totals  one cell per side and cut over both teams' markets (H.run_cells
               market_groups); a game can carry a bet on each team.

PLACEBO: 20 runs, seed = run number. same number: Pinnacle's no-vig share is
  shuffled between games on the same date in the same market
  (H.shuffle_within_date; prices and numbers stay). off number: the strength
  (the gap) is permuted among the offers on the same date, market and side,
  so a placebo bets other offers at the same rate; prices stay at the market's
  fair line.

CELLS (256, asserted)
  same number  full game h2h, spreads, totals x 2 sides x A-D x 4 cuts      96
               h1, q1 h2h/spreads/totals x 2 x D x 4                         48
               team totals x over/under x D x 4                               8
  off number   full game spreads, totals x 2 x A-D x 4                        64
               h1, q1 spreads/totals x 2 x D x 4                              32
               team totals x over/under x D x 4                               8

    PYTHONPATH=. python -m scripts.nba_game4_p2 --smoke
    NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> PYTHONPATH=. python -m scripts.nba_game4_p2 --full

--smoke: the 160 full-game cells on 2020-21 alone (plumbing, never a result)
and the 96 derivative cells on synthetic games. Output <NBA_GAME2_RESULTS>/smoke/.
--full: every season; refuses without NBA_GAME2_GO=1, refuses a cache pricing
fewer than 90% of any season 2020-21 to 2025-26 (H.load require_seasons), and
lists the derivative seasons from ANY derivative row so a half-bought season
raises (H.load_per_event require_seasons). Writes <NBA_GAME2_RESULTS>/
cells_P2.parquet and population_P2.parquet; with NBA_GAME2_BETS set, each
rule's bets go to <NBA_GAME2_BETS>/P2_<rule>/.
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import nba_game_harness as H  # noqa: E402
from scripts.nba_derivative_lab import OFF_MED_PTS  # noqa: E402
from scripts.nba_game2_market import (  # noqa: E402
    MIN_PRIOR_GAMES, PLACEBO_RUNS, go_guard, population_rows, results_dir, team_total_resid,
    write_cells)
from scripts.nba_game_market_lab import gap_candidates, sharp_pairs  # noqa: E402

FAMILY = "P2"
RULES = ("same_number", "off_number")
FULL_POINTS = ("A", "B", "C", "D")
DERIV_POINT = "D"
CUTS = {"same_number": (0.0, 0.01, 0.02, 0.03), "off_number": (0.5, 1.0, 1.5, 2.0)}
FULL_MARKETS = ("h2h", "spreads", "totals")
PERIOD_MARKETS = ("h2h_h1", "spreads_h1", "totals_h1", "h2h_q1", "spreads_q1", "totals_q1")
TT_LABEL = "team_totals"
TT_MARKETS = ("team_totals_home", "team_totals_away")
MARKET_GROUPS = {TT_LABEL: TT_MARKETS}
DERIV_LABELS = PERIOD_MARKETS + (TT_LABEL,)
DERIV_PRICED = ("spreads_h1", "totals_h1", "spreads_q1", "totals_q1") + TT_MARKETS
PERIOD_SHARE = {"h1": 0.5, "q1": 0.25}
GAP_TOL = 1e-9
EXPECTED_CELLS = 256
SMOKE_SEASONS = (2021,)
FULL_SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)
NEED_DERIV = (2025, 2026)
RUNG_KEY = ["game_id", "market", "book", "fetch_at"]
OFFER_COLS = ["game_id", "season", "game_date", "tip", "market", "book", "snapshot_at", "fetch_at",
              "T", "line", "coherent", "side", "price"]


# ── the cells ───────────────────────────────────────────────────────────────

def label_kind(label: str) -> str:
    """ml / spread / total for a market or a pooled label."""
    return str(H.kind(list(MARKET_GROUPS.get(label, (label,))))[0])


def sides_for(label: str) -> tuple:
    return ("over", "under") if label_kind(label) == "total" else ("home", "away")


def rule_labels(rule: str, labels) -> tuple:
    """Moneylines have no number, so the off-number rule never reads them."""
    return tuple(m for m in labels if rule == "same_number" or label_kind(m) != "ml")


def cell_plan() -> list[tuple]:
    """(rule, point, label, side, cut_index, cut) for every registered cell."""
    out = []
    for rule in RULES:
        groups = [(p, m) for p in FULL_POINTS for m in rule_labels(rule, FULL_MARKETS)]
        groups += [(DERIV_POINT, m) for m in rule_labels(rule, DERIV_LABELS)]
        for point, m in groups:
            for side in sides_for(m):
                for k, cut in enumerate(CUTS[rule]):
                    out.append((rule, point, m, side, k, cut))
    return out


# ── which quote is a book's number ──────────────────────────────────────────

def even_gap(q: pd.DataFrame) -> np.ndarray:
    return np.abs(H.imp(q["price_a"]) - H.imp(q["price_b"]))


def _one_rung(x: pd.DataFrame, first: list[str]) -> pd.DataFrame:
    x = x.assign(_inc=~x["coherent"].astype(bool), _eg=even_gap(x), _ln=x["line"].fillna(0.0))
    x = x.sort_values(RUNG_KEY + first + ["_inc", "_eg", "_ln"], kind="mergesort")
    drop = ["_inc", "_eg", "_ln"] + first
    return x.drop_duplicates(RUNG_KEY).drop(columns=drop).reset_index(drop=True)


def main_rungs(q: pd.DataFrame) -> pd.DataFrame:
    """One quote per (game, market, book, fetch): the rung whose two prices are
    closest to even (the first search's `main`), coherent first, ties to the
    lower number."""
    return _one_rung(q, [])


def rungs_at_pinnacle(q: pd.DataFrame) -> pd.DataFrame:
    """The same-number rule's quote per (game, market, book, fetch): the rung at
    Pinnacle's main number in that fetch when the book hangs one, else its
    main rung."""
    pin = main_rungs(q[(q["book"] == H.SHARP) & q["coherent"]])
    pin = pin[["game_id", "market", "fetch_at", "line"]].rename(columns={"line": "_pl"})
    x = q.merge(pin, on=["game_id", "market", "fetch_at"], how="left")
    at = x["coherent"].astype(bool) & np.isclose(x["line"].to_numpy(float),
                                                 x["_pl"].to_numpy(float))
    return _one_rung(x.assign(_away=~at).drop(columns="_pl"), ["_away"])


def ladder_mask(vis: pd.DataFrame, vis_main: pd.DataFrame) -> np.ndarray:
    """True for a deciding book's first-half, first-quarter or team-total spread
    or total more than OFF_MED_PTS from the median of the deciding books' main
    numbers at T (vis_main): an alternate rung, not the number it hangs."""
    def deriv(v):
        return (H.scope(v["market"]) != "game") & (H.kind(v["market"]) != "ml")
    if vis.empty:
        return np.zeros(0, bool)
    m = vis_main[deriv(vis_main) & vis_main["book"].isin(H.BETTABLE).to_numpy()
                 & vis_main["coherent"].to_numpy(bool)]
    med = m.groupby(["game_id", "market"])["line"].median().rename("_med").reset_index()
    x = vis[["game_id", "market", "book", "line"]].merge(med, on=["game_id", "market"], how="left")
    far = (x["line"] - x["_med"]).abs().to_numpy() > OFF_MED_PTS
    return deriv(vis) & vis["book"].isin(H.BETTABLE).to_numpy() & far


@dataclass
class Point:
    times: pd.DataFrame
    vis_main: pd.DataFrame          # main rungs, ladders out: offers, the market's fair line
    vis_same: pd.DataFrame          # rungs at Pinnacle's number, ladders out: same-number pairs
    fair: pd.DataFrame              # H.market_fair on vis_main
    neutral: pd.DataFrame           # every offer priced at the market's fair line


def point_frames(q_main: pd.DataFrame, q_same: pd.DataFrame, times: pd.DataFrame,
                 sig: dict) -> Point:
    vm = H.visible(q_main, times)
    vs = H.visible(q_same, times)
    keep_s = ~ladder_mask(vs, vm)
    vm = vm[~ladder_mask(vm, vm)].reset_index(drop=True)
    vs = vs[keep_s].reset_index(drop=True)
    fair = H.market_fair(vm, sig)
    neutral = H.fair_offers(H.offers(vm), fair)
    return Point(times=times, vis_main=vm, vis_same=vs, fair=fair, neutral=neutral)


# ── the first search's rules, imported (an adapter, both ways) ──────────────

def to_first_search(vis: pd.DataFrame) -> pd.DataFrame:
    """One market's visible quotes as the frame sharp_pairs reads: its market
    named by the full-game market it settles like (h2h / spreads / totals),
    the fetch as `fid`, side-A and side-B prices in the first search's columns.
    No score is passed: the rules never see a result."""
    v = vis.reset_index(drop=True)
    k = H.kind(v["market"])
    tot = k == "total"
    pa, pb = v["price_a"].astype(float), v["price_b"].astype(float)
    return pd.DataFrame({
        "game_id": v["game_id"], "market": [H.KIND_MARKET[x] for x in k],
        "fid": v["fetch_at"], "bookmaker": v["book"], "line": v["line"].astype(float),
        "coherent": v["coherent"].astype(bool), "imp_a": H.imp(pa), "imp_b": H.imp(pb),
        "snap": v["snapshot_at"],
        "home_price": pa.where(~tot), "away_price": pb.where(~tot),
        "over_price": pa.where(tot), "under_price": pb.where(tot),
        "fetch_ts": v["fetch_at"], "req_ts": v["T"],
        "hours_to_tip": (v["tip"] - v["T"]).dt.total_seconds() / 3600.0,
        "season": v["season"], "game_date": v["game_date"], "tip": v["tip"],
        "home_score": np.nan, "away_score": np.nan})


def _pairable(o: pd.DataFrame, same_number: bool) -> bool:
    """Whether sharp_pairs would return a pair (it cannot be called on none)."""
    k = ["game_id", "market", "fid"]
    pin = o.loc[(o["bookmaker"] == H.SHARP) & o["coherent"], k + ["line"]]
    soft = o.loc[o["bookmaker"].isin(H.BETTABLE) & o["coherent"], k + ["line"]]
    j = soft.merge(pin, on=k, suffixes=("", "_ref"))
    if j.empty:
        return False
    if (j["market"] == "h2h").all():
        return same_number
    same = j["line"] == j["line_ref"]
    return bool(same.any()) if same_number else bool((~same).any())


PAIR_COLS = OFFER_COLS + ["ref_line", "fair", "ev"]


def _empty(cols) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series([], dtype=object) for c in cols})


def from_first_search(x: pd.DataFrame, market: str) -> pd.DataFrame:
    """sharp_pairs rows back in the harness's offer columns, real market name."""
    x = x.reset_index(drop=True)
    tz = lambda s: pd.to_datetime(s, utc=True)  # noqa: E731
    return pd.DataFrame({
        "game_id": x["game_id"], "season": x["season"], "game_date": x["game_date"],
        "tip": tz(x["tip"]), "market": market, "book": x["bookmaker"],
        "snapshot_at": tz(x["snap"]), "fetch_at": tz(x["fetch_ts"]), "T": tz(x["req_ts"]),
        "line": x["line"].astype(float), "coherent": True, "side": x["side"],
        "price": x["price"].astype(float), "ref_line": x["ref_line"].astype(float),
        "fair": x["fair_prop"].astype(float), "ev": x["ev_prop"].astype(float)})


def pairs(vis: pd.DataFrame, same_number: bool) -> pd.DataFrame:
    """sharp_pairs per real market: one row per (pair, side) -- a deciding book
    in Pinnacle's fetch -- with Pinnacle's proportional no-vig share of the
    side (`fair`) and the first search's EV at the book's price."""
    parts = []
    for m, sub in vis.groupby("market", sort=True):
        if not same_number and H.kind([m])[0] == "ml":
            continue
        o = to_first_search(sub)
        if not _pairable(o, same_number):
            continue
        x = sharp_pairs(o, ref=H.SHARP, books=list(H.BETTABLE), same_number=same_number)
        parts.append(from_first_search(x, m))
    return pd.concat(parts, ignore_index=True) if parts else _empty(PAIR_COLS)


def favoured(vis: pd.DataFrame) -> pd.DataFrame:
    """gap_candidates per real spread / total market: the side each off-market
    number favours, (game_id, market, book, fetch_at, side, abs_gap). Its own
    normal-model EV is discarded (given no spread, it is blank)."""
    parts = []
    for m, sub in vis.groupby("market", sort=True):
        if H.kind([m])[0] == "ml":
            continue
        o = to_first_search(sub)
        if not _pairable(o, same_number=False):
            continue
        with np.errstate(all="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            x = gap_candidates(o, {}, ref=H.SHARP, books=list(H.BETTABLE))
        x = x.reset_index(drop=True)
        parts.append(pd.DataFrame({"game_id": x["game_id"], "market": m, "book": x["bookmaker"],
                                   "fetch_at": pd.to_datetime(x["fetch_ts"], utc=True),
                                   "side": x["side"], "abs_gap": x["abs_gap"].astype(float)}))
    cols = ["game_id", "market", "book", "fetch_at", "side", "abs_gap"]
    return pd.concat(parts, ignore_index=True) if parts else _empty(cols)


def same_number_cand(pt: Point) -> pd.DataFrame:
    """Offers at Pinnacle's number in Pinnacle's fetch; p_win = Pinnacle's
    proportional no-vig share, no push mass (the two-way convention)."""
    x = pairs(pt.vis_same, same_number=True)
    return x.assign(p_win=x["fair"].astype(float), p_push=0.0, ev=x["ev"].astype(float))


def off_number_cand(pt: Point) -> pd.DataFrame:
    """Every spread / total offer paired with Pinnacle in its fetch, strength =
    the gap in this side's favour (+gap favoured, -gap the other side, 0 at
    Pinnacle's number), priced at the market's fair line centred on Pinnacle."""
    same = pairs(pt.vis_main, same_number=True)
    same = same[H.kind(same["market"]) != "ml"].assign(strength=0.0) if len(same) else same
    off = pairs(pt.vis_main, same_number=False)
    if len(off):
        fav = favoured(pt.vis_main)
        key = ["game_id", "market", "book", "fetch_at", "side"]
        off = off.merge(fav, on=key, how="left")
        gap = (off["line"] - off["ref_line"]).abs()
        off["strength"] = np.where(off["abs_gap"].notna(), off["abs_gap"] + GAP_TOL, -gap)
        off = off.drop(columns="abs_gap")
    rows = pd.concat([x for x in (same, off) if len(x)], ignore_index=True) if (len(same) or len(off)) \
        else _empty(PAIR_COLS + ["strength"])
    if rows.empty:
        return rows.assign(p_win=[], p_push=[], ev=[])
    ref = pt.fair.set_index(["game_id", "market"])["ref"]
    got = ref.reindex(pd.MultiIndex.from_frame(rows[["game_id", "market"]].drop_duplicates()))
    assert (got == "pinnacle").all(), "an off-number pair priced off a centre that is not Pinnacle's"
    return H.fair_offers(rows.drop(columns=["fair", "ev"]), pt.fair)


# ── placebos ────────────────────────────────────────────────────────────────

def same_number_placebo(cand: pd.DataFrame, games: pd.DataFrame, run: int) -> pd.DataFrame:
    """Pinnacle's side-A share moved between games on the same date in the same
    market; each game's two sides stay complementary; prices untouched."""
    a = cand["side"].isin(["home", "over"]).to_numpy()
    share = cand.assign(p_home=np.where(a, cand["p_win"], 1.0 - cand["p_win"]))
    share = share.drop_duplicates(["game_id", "market"])[["game_id", "market", "p_home"]]
    sh = H.shuffle_within_date(share, games, np.random.default_rng(run))
    pa = cand[["game_id", "market"]].merge(sh, on=["game_id", "market"], how="left")["p_home"]
    p = np.where(a, pa.to_numpy(float), 1.0 - pa.to_numpy(float))
    return cand.assign(p_win=p, ev=p * H.dec(cand["price"]) - 1.0)


def off_number_placebo(cand: pd.DataFrame, run: int) -> pd.DataFrame:
    """The strength permuted among the offers on the same date, market and side."""
    c = cand.reset_index(drop=True)
    rng = np.random.default_rng(run)
    s = c["strength"].to_numpy(float).copy()
    for _, idx in sorted(c.groupby(["game_date", "market", "side"], sort=True).indices.items()):
        s[idx] = s[idx][rng.permutation(len(idx))]
    return c.assign(strength=s)


# ── pricing ─────────────────────────────────────────────────────────────────

def proxy_resid(full_close: pd.DataFrame, games_p: pd.DataFrame) -> pd.DataFrame:
    """(season, market, resid) for every derivative spread / total, needing no
    derivative price: the first half's (quarter's) home margin and total around
    PERIOD_SHARE of Pinnacle's full-game closing spread and total; each team's
    score around the team total Pinnacle's full-game close implies
    (team_total_resid, both teams pooled, entered under both team markets)."""
    c = full_close[full_close["market"].isin(["spreads", "totals"])]
    w = c.pivot_table(index=["game_id", "season"], columns="market", values="close_line",
                      aggfunc="last")
    parts = []
    if not w.empty and {"spreads", "totals"} <= set(w.columns):
        w = w.dropna().reset_index().merge(games_p, on="game_id", suffixes=("", "_g"))
        for part, share in PERIOD_SHARE.items():
            h, a = w[f"home_{part}"], w[f"away_{part}"]
            for m, r in ((f"spreads_{part}", (h - a) + share * w["spreads"]),
                         (f"totals_{part}", (h + a) - share * w["totals"])):
                parts.append(pd.DataFrame({"season": w["season"].astype(int), "market": m,
                                           "resid": r.astype(float)}))
    tt = team_total_resid(full_close, games_p)
    for m in TT_MARKETS:
        parts.append(tt.assign(market=m))
    out = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        {"season": [], "market": [], "resid": []})
    return out[np.isfinite(out["resid"].astype(float))].reset_index(drop=True)


def derivative_pricing(dclose: pd.DataFrame, games_p: pd.DataFrame, full_close: pd.DataFrame,
                       seasons, min_games: int = MIN_PRIOR_GAMES) -> tuple[dict, dict]:
    """({(season, market): ResidDist}, {(season, market): source}) for the
    derivative spreads and totals: results around Pinnacle's number at the
    purchase on derivative seasons before S when they hold >= min_games games,
    else the proxy on seasons before S (team totals: 2 x min_games rows, two
    per game), else nothing. Never the season's own results."""
    real = H.close_resid(dclose[H.kind(dclose["market"]) != "ml"], games_p) if len(dclose) else \
        pd.DataFrame({"season": [], "market": [], "resid": []})
    proxy = proxy_resid(full_close, games_p)
    out, src = {}, {}
    for s in sorted(int(x) for x in seasons):
        for m in DERIV_PRICED:
            r = real[(real["market"] == m) & (real["season"] < s)]
            if len(r) >= min_games:
                out[(s, m)] = H.ResidDist(r["resid"].to_numpy(), f"{s} {m} (derivative seasons before)")
                src[(s, m)] = "derivative"
                continue
            p = proxy[(proxy["market"] == m) & (proxy["season"] < s)]
            need = 2 * min_games if m in TT_MARKETS else min_games
            if len(p) >= need:
                out[(s, m)] = H.ResidDist(p["resid"].to_numpy(), f"{s} {m} (proxy, seasons before)")
                src[(s, m)] = "proxy"
    return out, src


# ── one decision point ──────────────────────────────────────────────────────

@contextmanager
def bets_dir(rule: str):
    """Each rule's bet dump in its own folder under NBA_GAME2_BETS."""
    base = os.environ.get("NBA_GAME2_BETS")
    if not base:
        yield
        return
    os.environ["NBA_GAME2_BETS"] = str(Path(base) / f"{FAMILY}_{rule}")
    try:
        yield
    finally:
        os.environ["NBA_GAME2_BETS"] = base


def rule_cells(data: H.Data, point: str, pt: Point, rule: str, labels, close, sig,
               choose_seasons, runs: int) -> tuple[list[dict], pd.DataFrame]:
    labels = rule_labels(rule, labels)
    if rule == "same_number":
        cand = same_number_cand(pt)
        placebo = [same_number_placebo(cand, data.games, r) for r in range(runs)] if len(cand) else []
        strength = "ev"
    else:
        cand = off_number_cand(pt)
        placebo = [off_number_placebo(cand, r) for r in range(runs)] if len(cand) else []
        strength = "strength"
    with bets_dir(rule):
        rows = H.run_cells(data, FAMILY, point, cand, pt.neutral, CUTS[rule],
                           {m: list(sides_for(m)) for m in labels}, close=close, sig=sig,
                           placebo=placebo, strength=strength, choose_seasons=choose_seasons,
                           times=pt.times, market_groups=MARKET_GROUPS)
    for r in rows:
        r["axis_rule"] = rule
    return rows, cand


def point_cells(data: H.Data, point: str, pt: Point, labels, close, sig, choose_seasons,
                runs: int) -> tuple[list[dict], list[dict]]:
    rows, pop = [], []
    for rule in RULES:
        r, cand = rule_cells(data, point, pt, rule, labels, close, sig, choose_seasons, runs)
        rows += r
        for m in rule_labels(rule, labels):
            group = MARKET_GROUPS.get(m, (m,))
            nm = pt.neutral[pt.neutral["market"].isin(group)]
            built = {"times": pt.times,
                     "priced": set(nm.loc[nm["book"].isin(H.BETTABLE), "game_id"]),
                     "modelled": set(cand.loc[cand["market"].isin(group), "game_id"])}
            pop += population_rows(FAMILY, point, m, data.games, built,
                                   [x for x in r if x["market"] == m], {"axis_rule": rule})
    return rows, pop


# ── the full game and the derivative markets ────────────────────────────────

def full_game_cells(data: H.Data, runs: int = PLACEBO_RUNS) -> tuple[list[dict], list[dict]]:
    close = H.pinnacle_close(data)
    sig = H.close_dist(close, data.games)
    q_main, q_same = main_rungs(data.quotes), rungs_at_pinnacle(data.quotes)
    rows, pop = [], []
    for point in FULL_POINTS:
        t = H.decision_times(data.fetches, data.games, point)
        pt = point_frames(q_main, q_same, t, sig)
        r, p = point_cells(data, point, pt, FULL_MARKETS, close, sig, H.CHOOSE, runs)
        rows += r
        pop += p
        print(f"  full game {point}: {len(r)} cells", flush=True)
    return rows, pop


def derivative_data(games_p: pd.DataFrame, pe: pd.DataFrame) -> H.Data:
    seasons = set(int(s) for s in pe["season"].unique())
    f = pe[["game_id", "tip", "fetch_at"]].drop_duplicates(["game_id", "fetch_at"])
    f = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60.0)
    return H.Data(games=games_p[games_p["season"].isin(seasons)].reset_index(drop=True),
                  quotes=pe.reset_index(drop=True), fetches=f.reset_index(drop=True))


def derivative_cells(games_p: pd.DataFrame, pe: pd.DataFrame, full_close: pd.DataFrame,
                     runs: int = PLACEBO_RUNS, min_games: int = MIN_PRIOR_GAMES
                     ) -> tuple[list[dict], list[dict], dict]:
    """The 96 derivative cells at D. games_p: every season's games with period
    points (the proxy reads the seasons before the first derivative season)."""
    seasons = sorted(int(s) for s in pe["season"].unique())
    data = derivative_data(games_p, pe)
    q_main, q_same = main_rungs(pe), rungs_at_pinnacle(pe)
    dclose = H.pinnacle_close(H.Data(games=data.games, quotes=q_main, fetches=data.fetches))
    sig, src = derivative_pricing(dclose, games_p, full_close, seasons, min_games=min_games)
    t = H.per_event_times(pe, DERIV_POINT)
    pt = point_frames(q_main, q_same, t, sig)
    choose = tuple(s for s in seasons if s != H.CONFIRM)
    rows, pop = point_cells(data, DERIV_POINT, pt, DERIV_LABELS, None, None, choose, runs)
    print(f"  derivatives {DERIV_POINT}: {len(rows)} cells (seasons {seasons}, choosing {choose})",
          flush=True)
    return rows, pop, {f"{s} {m}": v for (s, m), v in src.items()}


def check_cells(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    assert len(df) == EXPECTED_CELLS, (len(df), EXPECTED_CELLS)
    axes = ["axis_rule", "point", "market", "side", "cut"]
    assert not df.duplicated(axes).any(), "P2: duplicate cell"
    got = set(map(tuple, df[["axis_rule", "point", "market", "side", "cut_index", "cut"]]
                  .itertuples(index=False, name=None)))
    assert got == set(cell_plan()), "P2: the cells emitted are not the cells registered"
    assert (df["family"] == FAMILY).all()
    return df


# ── loading ─────────────────────────────────────────────────────────────────

def derivative_seasons(games: pd.DataFrame, cache: Path = H.CACHE) -> list[int]:
    """Every season with ANY derivative row in the cache, so a season bought
    part-way is named and H.load_per_event refuses it."""
    o = pd.read_parquet(cache / "nba_odds.parquet", columns=["game_id", "source", "market"])
    ids = set(o.loc[(o["source"] == H.PER_EVENT_SOURCE) & o["market"].isin(H.DERIVATIVE_MARKETS),
                    "game_id"])
    return sorted(int(s) for s in games.loc[games["game_id"].isin(ids), "season"].unique())


def load_full(cache: Path = H.CACHE) -> tuple[H.Data, pd.DataFrame]:
    data = H.load(cache=cache, require_seasons=FULL_SEASONS)
    share = data.notes.get("games_priced_share", {})
    short = {s: share.get(s, 0.0) for s in FULL_SEASONS if share.get(s, 0.0) < H.MIN_PRICED_SHARE}
    assert not short, f"--full: the cache prices too few games in {short}"
    data.games = H.with_periods(data.games, cache=cache)
    held = derivative_seasons(data.games, cache)
    missing = [s for s in NEED_DERIV if s not in held]
    if missing:
        raise SystemExit(f"--full: the cache holds no derivative prices for {missing}")
    pe = H.load_per_event(data.games, cache=cache, require_seasons=held)
    return data, pe


def load_smoke(cache: Path = H.CACHE) -> H.Data:
    data = H.load(cache=cache, seasons=SMOKE_SEASONS)
    assert set(data.games["season"]) == set(SMOKE_SEASONS), "smoke must read 2020-21 only"
    data.games = H.with_periods(data.games, cache=cache)
    return data


# ── synthetic games (the derivative cells' smoke, and the tests) ────────────

def _american(p: float) -> float:
    """American odds whose implied probability is p."""
    return float(round(-100.0 * p / (1.0 - p)) if p >= 0.5 else round(100.0 * (1.0 - p) / p))


def synthetic_world(seed: int = 5, per_season: int = 330, seasons=(2024, 2025, 2026)):
    """(games with period points, Pinnacle's full-game close, per-game
    derivative purchases) on made-up games. The first season has no
    derivative purchase (it feeds the proxy); later seasons are bought at
    tip - 60 at Pinnacle, fanduel, draftkings and betrivers. betrivers hangs a
    five-rung team-total ladder and lists one first-half spread rung far off
    the others, so both ladder rules are exercised. Results are noise."""
    rng = np.random.default_rng(seed)
    games, per, close, quotes = [], [], [], []
    t0 = {s: pd.Timestamp(f"{s - 1}-11-01T00:00:00Z") for s in seasons}
    for s in seasons:
        for i in range(per_season):
            gid = f"SYN{s}_{i:04d}"
            tip = t0[s] + pd.Timedelta(days=i // 8, hours=(i % 8) // 3)
            hq = rng.integers(20, 36, 4)
            aq = rng.integers(20, 36, 4)
            if hq.sum() == aq.sum():
                hq[3] += 1
            games.append({"game_id": gid, "season": s,
                          "game_date": (tip - pd.Timedelta(hours=5)).strftime("%Y-%m-%d"), "tip": tip,
                          "home_team": "HOM", "away_team": "AWY",
                          "home_score": float(hq.sum()), "away_score": float(aq.sum())})
            per += [{"game_id": gid, "period": p + 1, "home_points": int(hq[p]),
                     "away_points": int(aq[p])} for p in range(4)]
            sp = round(rng.normal(-2.0, 5.0) * 2) / 2
            tot = round(rng.normal(224.0, 7.0) * 2) / 2
            close += [{"game_id": gid, "season": s, "market": "spreads", "close_line": sp,
                       "close_fa": 0.5, "close_at": tip - pd.Timedelta(minutes=10)},
                      {"game_id": gid, "season": s, "market": "totals", "close_line": tot,
                       "close_fa": 0.5, "close_at": tip - pd.Timedelta(minutes=10)}]
            if s == seasons[0]:
                continue
            at = tip - pd.Timedelta(minutes=60)
            base = {"game_id": gid, "season": s, "game_date": games[-1]["game_date"], "tip": tip,
                    "snapshot_at": at, "fetch_at": at, "coherent": True}
            nums = {"spreads_h1": round(sp / 2 * 2) / 2, "totals_h1": round(tot / 2 * 2) / 2 + 0.5,
                    "spreads_q1": round(sp / 4 * 2) / 2, "totals_q1": round(tot / 4 * 2) / 2 + 0.5,
                    "team_totals_home": round((tot - sp) / 2 * 2) / 2 + 0.5,
                    "team_totals_away": round((tot + sp) / 2 * 2) / 2 + 0.5}
            for book in ("pinnacle", "fanduel", "draftkings", "betrivers"):
                for m in ("h2h_h1", "h2h_q1"):
                    ph = float(np.clip(0.5 - sp / 40 + rng.normal(0, 0.03), 0.2, 0.8))
                    quotes.append({**base, "market": m, "book": book, "line": np.nan,
                                   "price_a": _american(ph + 0.02), "price_b": _american(1.02 - ph)})
                ladder = (-105, -110, -115) if book == "pinnacle" else (100, -102, -105, -110, -115)
                for m, n in nums.items():
                    shift = 0.0 if book == "pinnacle" else float(rng.choice([0.0, 0.0, 0.5, -0.5, 1.0]))
                    pa, pb = float(rng.choice(ladder)), float(rng.choice(ladder))
                    if book == "betrivers" and m in TT_MARKETS:
                        for j, (xa, xb) in enumerate(((-160, 125), (-135, 105), (-112, -112),
                                                      (105, -135), (125, -160))):
                            quotes.append({**base, "market": m, "book": book,
                                           "line": n + shift + (j - 2), "price_a": float(xa),
                                           "price_b": float(xb)})
                        continue
                    if book == "betrivers" and m == "spreads_h1":
                        shift, pa, pb = 3.0, -165.0, 130.0
                    quotes.append({**base, "market": m, "book": book, "line": n + shift,
                                   "price_a": pa, "price_b": pb})
    g = pd.DataFrame(games)
    g = H.with_periods(g, periods=pd.DataFrame(per))
    pe = pd.DataFrame(quotes)
    sm = H.imp(pe["price_a"]) + H.imp(pe["price_b"])
    pe["coherent"] = (sm >= H.COHERENT[0]) & (sm <= H.COHERENT[1])
    return g, pd.DataFrame(close), pe


def synthetic_checks() -> None:
    H.check()
    plan = cell_plan()
    assert len(plan) == EXPECTED_CELLS == 256
    assert sum(1 for c in plan if c[0] == "same_number") == 152
    assert not any(label_kind(c[2]) == "ml" for c in plan if c[0] == "off_number")
    lad = pd.DataFrame({"game_id": "g", "market": "team_totals_home", "book": "betrivers",
                        "fetch_at": pd.Timestamp("2025-01-01T00:00:00Z"), "coherent": True,
                        "line": [110.5, 111.5, 112.5], "price_a": [-139.0, -112.0, 105.0],
                        "price_b": [108.0, -112.0, -135.0]})
    assert main_rungs(lad)["line"].tolist() == [111.5]
    print("synthetic checks pass")


# ── main ────────────────────────────────────────────────────────────────────

def results_guard(full: bool, env=os.environ) -> None:
    """--full needs its results folder NAMED: the default is the second
    search's, where the verdict would read P2's cells beside its 422."""
    if full and not env.get("NBA_GAME2_RESULTS"):
        raise SystemExit("--full refuses to run: set NBA_GAME2_RESULTS to the fourth search's "
                         "results folder")


def run(mode: str, runs: int = PLACEBO_RUNS) -> dict:
    go_guard(mode == "full")
    results_guard(mode == "full")
    res = results_dir()
    out = res / "smoke" if mode == "smoke" else res
    out.mkdir(parents=True, exist_ok=True)
    if mode == "smoke":
        synthetic_checks()
        data = load_smoke()
        g, fc, pe = synthetic_world()
        full_rows, full_pop = full_game_cells(data, runs)
        d_rows, d_pop, src = derivative_cells(g, pe, fc, runs)
    elif mode == "full":
        data, pe = load_full()
        full_rows, full_pop = full_game_cells(data, runs)
        d_rows, d_pop, src = derivative_cells(data.games, pe, H.pinnacle_close(data), runs)
    else:
        raise ValueError(mode)
    cells = check_cells(full_rows + d_rows)
    write_cells(cells, out / f"cells_{FAMILY}.parquet")
    pd.DataFrame(full_pop + d_pop).to_parquet(out / f"population_{FAMILY}.parquet")
    print(f"{FAMILY}: {len(cells)} cells -> {out / f'cells_{FAMILY}.parquet'}", flush=True)
    return {"mode": mode, "cells": len(cells), "derivative_pricing": src,
            "full_game_seasons": sorted(int(s) for s in data.games["season"].unique()),
            "derivative_seasons": sorted(int(s) for s in pe["season"].unique())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true",
                   help="2020-21 full-game cells and synthetic derivative cells")
    g.add_argument("--full", action="store_true", help="every season (needs NBA_GAME2_GO=1)")
    a = ap.parse_args()
    warnings.filterwarnings("ignore", message="no explicit representation of timezones")
    # the first search's imp() evaluates both branches of a where at -100 / +100
    warnings.filterwarnings("ignore", message="divide by zero encountered in divide")
    print(run("smoke" if a.smoke else "full"))


if __name__ == "__main__":
    main()
