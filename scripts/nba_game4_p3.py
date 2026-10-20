"""NBA fourth search, P3: the second search's signals on the derivative markets.

docs/nba_models_2026.md section 8 registers the cells; section 8.3 fixes every
choice that row leaves open, written and committed BEFORE this lab existed.
This lab EMITS cells through the shared harness (scripts/nba_game_harness, H);
scripts/nba_game2_verdict.py (house_verdict) judges them. Nothing here grades a
bet itself, and no cut, constant or rule below was chosen from a betting result.

72 cells, all at decision point D: each game's ONE per-game purchase, kept only
when it falls 45-75 minutes before tip (H.per_event_times).

  P3_F4  SHOOTING LUCK (the second search's F4, scripts/nba_game2_luck), 24 cells
         first-half total, home team total, away team total x over / under x
         gap >= 1, 2, 3, 4 points.
         first-half total: F4's own full-game number, UNSCALED -- the
           luck-adjusted minus the raw projected game total, in full-game
           points, so the registered cuts keep their section 6.3 meaning.
         team totals: the team's own part of that number -- the luck in its
           OPPONENT's defence (opponent three-point and free-throw percentage
           replaced by the league's rate so far) times pace, in that team's
           points. Home part + away part = F4's total gap.
         A rule family: a side is bet where its gap >= the cut, at its best
         deciding offer under the market's fair line (run_cells strength=).
         F4's population rule is kept: both teams have >= 10 games this season.
  P3_F1  RATINGS PROJECTION (the second search's F1, scripts/nba_game2_projection),
         48 cells: first-half and first-quarter moneyline, spread, total x
         2 sides x EV >= 0.02, 0.04, 0.06, 0.08.
         The full-game projection at the purchase instant, scaled to the
         period: period home margin = a + b x projected margin, period total =
         a + b x projected total, least squares on the projection's walk-forward
         numbers of 2020-21 .. S-1 at tip - 60 (each calibrated by its own
         season's model). Priced through that same fit's residuals (the
         harness's empirical distribution, re-centred), never the market's.
         Moneyline: P(period home margin > 0) out of P(> 0) + P(< 0); a level
         period voids the bet, so the tie mass is removed.

THE MARKET'S OWN PRICING (the fair line that picks a side's best offer, the
  blind bets, the favourite). First-half and first-quarter spreads and totals:
  the spread of the period result around a + b x Pinnacle's full-game closing
  number (the home margin its spread implies, or its total), fit on the seasons
  before S from 2020-21, >= 300 earlier games, no fallback. Team totals: F6d's
  recorded definition (scripts.nba_game2_market.team_total_dist). Never the
  purchases' own prices: the first priced season has no earlier one, and
  would be priced on its own results. A missing (season, market) stops the run.

SEASONS: every season the cache holds a derivative price in, plus 2024-25 and
  2025-26 always; each must be priced on >= 90% of its games
  (H.load_per_event refuses otherwise). All graded and pooled. The harness's
  choosing seasons (the placebo bar's) are all of them but 2025-26. No
  closing-line value (one purchase per game, no later price); "still offered
  at the next purchase" reads 0 (there is no next purchase).

PLACEBO: 20 runs, seed = run number. F4: the gap shuffled between games on the
  same date in the same market. F1: its fair numbers shuffled the same way.
  Prices never move.

    PYTHONPATH=. python -m scripts.nba_game4_p3 --smoke
    PYTHONPATH=. python -m scripts.nba_game4_p3 --quality   # price-free, never 2025-26
    NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> NBA_GAME2_BETS=<folder>/bets PYTHONPATH=. python -m scripts.nba_game4_p3 --full

--smoke runs every cell on SYNTHETIC games only, then prints counts on the real
cache (seasons held, D coverage, games with a shooting-luck number, the
market-pricing table's size). --quality runs the projection's real path up to
2024-25 (the period fits and the projection at each purchase instant) and
prints coefficients and counts, never a price or a result of 2024-25.
--full writes <NBA_GAME2_RESULTS>/cells_P3_F4.parquet, cells_P3_F1.parquet and
their population_*.parquet.
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
from scripts import nba_game2_luck as L  # noqa: E402
from scripts import nba_game2_projection as P  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402
from scripts.nba_game2_market import team_total_dist  # noqa: E402
from models import nba_book_numbers as NB  # noqa: E402

RESULTS = Path(os.environ.get("NBA_GAME2_RESULTS",
                              "C:/Users/micha/AppData/Local/Temp/nba_game_edge/results"))
GO_ENV = "NBA_GAME2_GO"
RESULTS_ENV = "NBA_GAME2_RESULTS"
POINT = "D"
ALWAYS_GRADED = (2025, 2026)                         # 2024-25 and 2025-26 are bought
FULL_GAME_SEASONS = (H.REGIME, *H.CHOOSE, H.CONFIRM)  # 2021-2026: the closes the pricing reads
QUALITY_LAST = 2025                                   # --quality never builds 2025-26
N_PLACEBO = 20
MIN_PRIOR_GAMES = 300
F1_FIRST_FIT = 2021              # 2020-21: the first season whose projection is calibrated
PERIODS = ("h1", "q1")

F4_FAMILY, F1_FAMILY = "P3_F4", "P3_F1"
F4_CUTS = (1.0, 2.0, 3.0, 4.0)
F4_SIDES = {"totals_h1": ("over", "under"), "team_totals_home": ("over", "under"),
            "team_totals_away": ("over", "under")}
F1_CUTS = (0.02, 0.04, 0.06, 0.08)
F1_SIDES = {f"{k}_{p}": (("over", "under") if k == "totals" else ("home", "away"))
            for p in PERIODS for k in ("h2h", "spreads", "totals")}
FAMILIES = {F4_FAMILY: (F4_SIDES, F4_CUTS, "strength"), F1_FAMILY: (F1_SIDES, F1_CUTS, "ev")}
EXPECTED_CELLS = {F4_FAMILY: 24, F1_FAMILY: 48}
# the derivative markets priced through a distribution (moneylines need none)
PRICED_MARKETS = tuple(m for m in H.DERIVATIVE_MARKETS if H.kind([m])[0] != "ml")


def cell_specs(family: str | None = None) -> list[tuple]:
    """(family, market, side, cut_index, cut) for every cell section 8 lists."""
    out = []
    for fam, (sides, cuts, _) in FAMILIES.items():
        if family is not None and fam != family:
            continue
        for m, ss in sides.items():
            for s in ss:
                for k, c in enumerate(cuts):
                    out.append((fam, m, s, k, c))
    return out


assert {f: len(cell_specs(f)) for f in FAMILIES} == EXPECTED_CELLS, "section 8 registers 24 + 48"
assert len(cell_specs()) == 72


# ── seasons ─────────────────────────────────────────────────────────────────

def graded_seasons(found) -> tuple:
    """Every season holding a derivative price, plus 2024-25 and 2025-26."""
    return tuple(sorted({int(s) for s in found} | set(ALWAYS_GRADED)))


def choosing(graded) -> tuple:
    """The harness's choosing seasons: every graded season but 2025-26."""
    return tuple(int(s) for s in graded if int(s) != H.CONFIRM)


def load_derivatives(games_p: pd.DataFrame, cache: Path = H.CACHE) -> tuple[pd.DataFrame, tuple]:
    """(per-event rows of the graded seasons, graded seasons). A season with
    any derivative row is graded, so a purchase still running (priced on
    fewer than 90% of its games) makes H.load_per_event refuse."""
    found = H.load_per_event(games_p, cache)["season"].unique()
    graded = graded_seasons(found)
    pe = H.load_per_event(games_p, cache, require_seasons=graded)
    return pe[pe["season"].isin(graded)].reset_index(drop=True), graded


def derivative_data(games_p: pd.DataFrame, pe: pd.DataFrame) -> H.Data:
    """The H.Data run_cells grades on: games with period scores, the per-event
    quotes, and their purchases as the fetches (one per game: there is no next
    purchase, so "still offered" reads 0)."""
    f = pe[["game_id", "tip", "fetch_at"]].drop_duplicates(["game_id", "fetch_at"])
    f = f.assign(lead_min=(f["tip"] - f["fetch_at"]).dt.total_seconds() / 60.0)
    return H.Data(games=games_p, quotes=pe, fetches=f.reset_index(drop=True))


# ── period results ──────────────────────────────────────────────────────────

def period_results(games_p: pd.DataFrame) -> pd.DataFrame:
    """Per game: the home margin and the total of the first half and first
    quarter (H.with_periods; NaN where the periods fail its check)."""
    g = games_p
    out = g[["game_id", "season"]].copy()
    for p in PERIODS:
        h, a = g[f"home_{p}"].astype(float), g[f"away_{p}"].astype(float)
        out[f"margin_{p}"], out[f"total_{p}"] = (h - a).to_numpy(), (h + a).to_numpy()
    return out


def _line_fit(x, y) -> tuple[float, float]:
    b = P.ols(np.column_stack([np.ones(len(x)), np.asarray(x, float)]), np.asarray(y, float))
    return float(b[0]), float(b[1])


# ── the market's own pricing ────────────────────────────────────────────────

def period_market_pricing(close: pd.DataFrame, games_p: pd.DataFrame, seasons,
                          min_prior: int = MIN_PRIOR_GAMES) -> dict:
    """{(S, spreads_h1 | totals_h1 | spreads_q1 | totals_q1): ResidDist}: the
    period result around a + b x Pinnacle's full-game closing number (the home
    margin its spread implies, -spread_home; or its total), a and b and the
    residuals from the seasons BEFORE S. Fewer than `min_prior` earlier games:
    no entry (no fallback to S's own results)."""
    c = close[close["market"].isin(["spreads", "totals"])]
    w = c.pivot_table(index=["game_id", "season"], columns="market", values="close_line",
                      aggfunc="last").reset_index()
    if w.empty or not {"spreads", "totals"} <= set(w.columns):
        return {}
    x = w.merge(period_results(games_p).drop(columns="season"), on="game_id")
    out = {}
    for S in sorted(int(s) for s in seasons):
        prior = x[x["season"] < S]
        for p in PERIODS:
            for kind, market in (("margin", f"spreads_{p}"), ("total", f"totals_{p}")):
                xv = (-prior["spreads"] if kind == "margin" else prior["totals"]).to_numpy(float)
                yv = prior[f"{kind}_{p}"].to_numpy(float)
                ok = np.isfinite(xv) & np.isfinite(yv)
                if ok.sum() < min_prior:
                    continue
                a, b = _line_fit(xv[ok], yv[ok])
                out[(S, market)] = H.ResidDist(
                    yv[ok] - (a + b * xv[ok]),
                    f"{S} {market}: result around {a:.2f} + {b:.3f} x Pinnacle's full-game close, "
                    f"seasons < {S} ({int(ok.sum())} games)")
    return out


def market_pricing(close: pd.DataFrame, games_p: pd.DataFrame, seasons,
                   min_prior: int = MIN_PRIOR_GAMES) -> dict:
    """The market's own pricing for every priced derivative market, seasons
    before S only: the period map above, and F6d's team-total distribution."""
    seasons = tuple(int(s) for s in seasons)
    out = period_market_pricing(close, games_p, seasons, min_prior)
    tt = team_total_dist(close, games_p, min_games=min_prior)
    out.update({k: v for k, v in tt.items() if int(k[0]) in seasons})
    return out


def require_pricing(pricing: dict, seasons, markets, what: str) -> None:
    """Stop before any cell when a (season, market) has no distribution: the
    harness would read its centre as missing and drop every offer silently."""
    missing = [(int(s), m) for s in seasons for m in markets if (int(s), m) not in pricing]
    if missing:
        raise RuntimeError(f"{what}: no distribution for {missing[:6]}{' ...' if len(missing) > 6 else ''}")


def neutral_offers(vis: pd.DataFrame, pricing: dict) -> pd.DataFrame:
    """Every derivative offer at T priced at the market's own fair line."""
    return H.fair_offers(H.offers(vis), H.market_fair(vis, pricing))


# ── P3_F4: the shooting-luck gap ────────────────────────────────────────────

def f4_signal(proj: pd.DataFrame) -> pd.DataFrame:
    """(game_id, market, strength) toward side A (over), from L.f4_projections.

    totals_h1: F4's full-game total gap itself (unscaled). team_totals_home:
    the home team scores against the AWAY defence, so its gap is pace x the
    away defence's luck (drtg adjusted - raw); team_totals_away the reverse.
    pace is F4's: the mean of the two teams' possessions per game, per 100."""
    pace = 0.5 * (proj["h_pace"] + proj["a_pace"]) / 100.0
    home = pace * (proj["a_drtg_adj"] - proj["a_drtg_raw"])
    away = pace * (proj["h_drtg_adj"] - proj["h_drtg_raw"])
    parts = [proj[["game_id"]].assign(market="totals_h1", strength=proj["gap_total"].to_numpy()),
             proj[["game_id"]].assign(market="team_totals_home", strength=home.to_numpy()),
             proj[["game_id"]].assign(market="team_totals_away", strength=away.to_numpy())]
    s = pd.concat(parts, ignore_index=True)
    return s[np.isfinite(s["strength"].to_numpy(float))].reset_index(drop=True)


def shuffled(frame: pd.DataFrame, games: pd.DataFrame, n: int) -> list[pd.DataFrame]:
    """n copies of a per-(game, market) frame, its numbers shuffled within date
    and market (H.shuffle_within_date), seed = run number."""
    return [H.shuffle_within_date(frame, games, np.random.default_rng(r)) for r in range(n)]


def emit_f4(dd: H.Data, times: pd.DataFrame, neutral: pd.DataFrame, signal: pd.DataFrame,
            choose, n_placebo: int = N_PLACEBO) -> tuple[list[dict], pd.DataFrame]:
    """The 24 shooting-luck cells (run_cells rows) and their candidate offers."""
    nm = neutral[neutral["market"].isin(list(F4_SIDES))].reset_index(drop=True)
    sig = signal.merge(nm[["game_id", "market"]].drop_duplicates(), on=["game_id", "market"])
    cand = L.side_strength(nm, sig)
    placebo = [L.side_strength(nm, sh) for sh in
               shuffled(sig[["game_id", "market", "strength"]], dd.games, n_placebo)]
    rows = H.run_cells(dd, F4_FAMILY, POINT, cand, nm, list(F4_CUTS),
                       {m: list(s) for m, s in F4_SIDES.items()}, placebo=placebo,
                       strength="strength", choose_seasons=choose, times=times)
    assert len(rows) == EXPECTED_CELLS[F4_FAMILY], len(rows)
    for r in rows:
        r["signal_meaning"] = ("first-half total: F4's full-game total gap, unscaled; team totals: "
                               "the team's own part (its opponent's defensive luck x pace)")
    return rows, cand


# ── P3_F1: the ratings projection, scaled to the period ─────────────────────

def period_maps(refs: pd.DataFrame, games_p: pd.DataFrame, seasons, first: int = F1_FIRST_FIT,
                min_prior: int = MIN_PRIOR_GAMES) -> tuple[dict, dict]:
    """(maps, dists) per graded season S, from the projection's walk-forward
    numbers `refs` (game_id, season, margin, total) of seasons first .. S-1:

      maps[(S, period, "margin" | "total")] = (a, b): period number = a + b x
          the full-game projection, least squares;
      dists[(S, spreads_<period> | totals_<period>)] = the same fit's residuals
          as an empirical distribution (H.ResidDist re-centres them).

    Fewer than `min_prior` earlier games refuses: there is no fallback to S."""
    x = refs[["game_id", "season", "margin", "total"]].merge(
        period_results(games_p).drop(columns="season"), on="game_id")
    maps, dists = {}, {}
    for S in sorted(int(s) for s in seasons):
        prior = x[(x["season"] >= first) & (x["season"] < S)]
        for p in PERIODS:
            for kind, market in (("margin", f"spreads_{p}"), ("total", f"totals_{p}")):
                xv, yv = prior[kind].to_numpy(float), prior[f"{kind}_{p}"].to_numpy(float)
                ok = np.isfinite(xv) & np.isfinite(yv)
                if ok.sum() < min_prior:
                    raise RuntimeError(f"{S} {market}: {int(ok.sum())} earlier projected games with period "
                                       f"scores (need {min_prior}); no fallback to the season itself")
                a, b = _line_fit(xv[ok], yv[ok])
                yrs = sorted(int(s) for s in prior.loc[ok, "season"].unique())
                maps[(S, p, kind)] = (a, b)
                dists[(S, market)] = H.ResidDist(
                    yv[ok] - (a + b * xv[ok]),
                    f"{S} {market}: projection error, fit {yrs[0]}-{yrs[-1]} ({int(ok.sum())} games)")
    return maps, dists


def period_projection(proj: pd.DataFrame, maps: dict) -> pd.DataFrame:
    """game_id, season, margin_<p>, total_<p> from each season's own map."""
    out = proj[["game_id", "season"]].copy()
    s = proj["season"].astype(int).to_numpy()
    for p in PERIODS:
        for kind in ("margin", "total"):
            ab = np.array([maps.get((int(v), p, kind), (np.nan, np.nan)) for v in s], float).reshape(-1, 2)
            out[f"{kind}_{p}"] = ab[:, 0] + ab[:, 1] * proj[kind].to_numpy(float)
    return out


def f1_fair(proj: pd.DataFrame, maps: dict, dists: dict) -> pd.DataFrame:
    """(game_id, market, mu, sigma, p_home) for the six period markets, through
    the projection's OWN period error (P.fair_frame: the moneyline is P(margin
    > 0) with the tie mass removed)."""
    pp = period_projection(proj, maps)
    parts = []
    for p in PERIODS:
        d = {}
        for (s, m), v in dists.items():
            if m == f"spreads_{p}":
                d[(int(s), "spreads")] = v
            elif m == f"totals_{p}":
                d[(int(s), "totals")] = v
        f = P.fair_frame(pp, d, f"margin_{p}", f"total_{p}")
        f["market"] = f["market"].map({"spreads": f"spreads_{p}", "totals": f"totals_{p}",
                                       "h2h": f"h2h_{p}"})
        parts.append(f)
    return pd.concat(parts, ignore_index=True)


def emit_f1(dd: H.Data, times: pd.DataFrame, off: pd.DataFrame, neutral: pd.DataFrame,
            fair: pd.DataFrame, choose, n_placebo: int = N_PLACEBO) -> tuple[list[dict], pd.DataFrame]:
    """The 48 projection cells. Offers priced at the projection's own fair
    numbers; the placebo shuffles those numbers within date and market."""
    o = off[off["market"].isin(list(F1_SIDES))].reset_index(drop=True)
    cand = H.fair_offers(o, fair)
    placebo = [H.fair_offers(o, sh) for sh in shuffled(fair, dd.games, n_placebo)]
    nm = neutral[neutral["market"].isin(list(F1_SIDES))].reset_index(drop=True)
    rows = H.run_cells(dd, F1_FAMILY, POINT, cand, nm, list(F1_CUTS),
                       {m: list(s) for m, s in F1_SIDES.items()}, placebo=placebo,
                       strength="ev", choose_seasons=choose, times=times)
    assert len(rows) == EXPECTED_CELLS[F1_FAMILY], len(rows)
    return rows, cand


def calibrated_refs(refs: dict, models: dict, first: int = F1_FIRST_FIT) -> pd.DataFrame:
    """The projection's walk-forward reference numbers (tip - 60), each season
    calibrated by ITS OWN model (P.build_models returns them raw), from the
    first calibrated season on."""
    parts = []
    for s in sorted(refs):
        if s < first or models[s].calib is None:
            continue
        r = P.apply_models(refs[s], models[s])
        parts.append(r[["game_id", "season", "margin", "total"]])
    if not parts:
        raise RuntimeError("no calibrated reference projections")
    return pd.concat(parts, ignore_index=True)


def project_at(w, st, models: dict, games: pd.DataFrame, times: pd.DataFrame) -> pd.DataFrame:
    """The projection (game_id, season, margin, total) at each game's decision
    time T, by its own season's model (P.project: every input at or before T)."""
    gm = games.merge(times[["game_id", "T"]], on="game_id").merge(w.games[["game_id", "day"]],
                                                                   on="game_id")
    parts = [P.project(w, st, models[int(s)], g) for s, g in gm.groupby("season")
             if int(s) in models and len(g)]
    if not parts:
        return pd.DataFrame(columns=["game_id", "season", "margin", "total"])
    out = pd.concat(parts, ignore_index=True)
    return out[["game_id", "season", "margin", "total"]]


# ── population counts ───────────────────────────────────────────────────────

def population(family: str, rows: list[dict], dd: H.Data, times: pd.DataFrame,
               off: pd.DataFrame, cand: pd.DataFrame, strength: str, seasons) -> pd.DataFrame:
    """Per cell and season: games, games with a decision, games with a deciding
    price in the market, games with the signal's number, and bets. Counts only."""
    season = dd.games.drop_duplicates("game_id").set_index("game_id")["season"].astype(int)

    def count(ids):
        return season.reindex(pd.unique(np.asarray(ids, dtype=object))).value_counts()

    n_games, n_time = season.value_counts(), count(times["game_id"])
    out = []
    for r in rows:
        m = r["market"]
        priced = count(off.loc[(off["market"] == m) & off["book"].isin(H.BETTABLE), "game_id"])
        numbered = count(cand.loc[(cand["market"] == m) & cand[strength].notna(), "game_id"])
        for s in seasons:
            bets = r["n_confirm"] if s == H.CONFIRM else r.get(f"n_{s}", 0)
            out.append({"family": family, "point": POINT, "season": int(s), "market": m,
                        "side": r["side"], "cut_index": r["cut_index"], "cut": r["cut"],
                        "games": int(n_games.get(s, 0)), "games_with_time": int(n_time.get(s, 0)),
                        "games_priced": int(priced.get(s, 0)),
                        "games_with_number": int(numbered.get(s, 0)), "bets": int(bets or 0)})
    return pd.DataFrame(out)


# ── a synthetic world (the only place a P3 cell is run before --full) ───────

def synthetic_world(seed: int = 0, prior=(2021, 2022, 2023, 2024), graded=(2025, 2026),
                    prior_games: int = 320, graded_games: int = 60) -> dict:
    """Games with period scores, Pinnacle full-game closes, the projection's
    reference numbers, per-game purchases of the eight derivative markets at
    tip - 55, an F4 number and a graded projection. Random, never real."""
    rng = np.random.default_rng(seed)
    games, per, close, refs, quotes = [], [], [], [], []
    books = ("fanduel", "draftkings", "betmgm", "pinnacle")
    for s in (*prior, *graded):
        n = prior_games if s in prior else graded_games
        for i in range(n):
            day = pd.Timestamp(f"{s - 1}-11-01") + pd.Timedelta(days=i // 4)
            tip = (day + pd.Timedelta(hours=24)).tz_localize("UTC")
            gid = f"S{s}_{i}"
            strength = rng.normal(0.0, 6.0)
            qh = rng.poisson(28.0 + strength / 8.0, 4).astype(float)
            qa = rng.poisson(28.0 - strength / 8.0, 4).astype(float)
            if qh.sum() == qa.sum():
                qh[3] += 1.0
            games.append({"game_id": gid, "season": s, "game_date": day.strftime("%Y-%m-%d"), "tip": tip,
                          "home_team": "AAA", "away_team": "BBB",
                          "home_score": float(qh.sum()), "away_score": float(qa.sum())})
            per += [{"game_id": gid, "period": k + 1, "home_points": qh[k], "away_points": qa[k]}
                    for k in range(4)]
            spread = -round(strength * 2.0) / 2.0 - 0.5
            total = round(224.0 + rng.normal(0.0, 4.0)) + 0.5
            close += [{"game_id": gid, "season": s, "market": "spreads", "close_line": spread,
                       "close_fa": 0.5, "close_at": tip - pd.Timedelta(minutes=5)},
                      {"game_id": gid, "season": s, "market": "totals", "close_line": total,
                       "close_fa": 0.5, "close_at": tip - pd.Timedelta(minutes=5)}]
            refs.append({"game_id": gid, "season": s, "margin": strength + rng.normal(0, 4),
                         "total": total + rng.normal(0, 6)})
            if s not in graded:
                continue
            at = tip - pd.Timedelta(minutes=55)
            base = {"game_id": gid, "season": s, "game_date": day.strftime("%Y-%m-%d"), "tip": tip,
                    "snapshot_at": at, "fetch_at": at, "coherent": True}
            half = lambda v: float(np.floor(v)) + 0.5  # noqa: E731
            for b in books:
                j = float(rng.integers(-1, 2))
                quotes += [
                    {**base, "book": b, "market": "h2h_h1", "line": np.nan, "price_a": -125.0, "price_b": 105.0},
                    {**base, "book": b, "market": "h2h_q1", "line": np.nan, "price_a": -120.0, "price_b": 100.0},
                    {**base, "book": b, "market": "spreads_h1", "line": half(spread / 2) + j, "price_a": -110.0, "price_b": -110.0},
                    {**base, "book": b, "market": "spreads_q1", "line": half(spread / 4) + j, "price_a": -110.0, "price_b": -110.0},
                    {**base, "book": b, "market": "totals_h1", "line": half(total / 2) + j, "price_a": -110.0, "price_b": -110.0},
                    {**base, "book": b, "market": "totals_q1", "line": half(total / 4) + j, "price_a": -110.0, "price_b": -110.0},
                    {**base, "book": b, "market": "team_totals_home", "line": half((total - spread) / 2) + j, "price_a": -110.0, "price_b": -110.0},
                    {**base, "book": b, "market": "team_totals_away", "line": half((total + spread) / 2) + j, "price_a": -110.0, "price_b": -110.0}]
    g = pd.DataFrame(games)
    games_p = H.with_periods(g, periods=pd.DataFrame(per))
    pe = pd.DataFrame(quotes)
    gr = g[g["season"].isin(graded)]
    signal = pd.concat([gr[["game_id"]].assign(market=m, strength=rng.normal(0.0, 2.5, len(gr)))
                        for m in F4_SIDES], ignore_index=True)
    proj = pd.DataFrame(refs)
    proj = proj[proj["season"].isin(graded)].assign(margin=lambda d: d["margin"] + rng.normal(0, 3, len(d)))
    return {"games_p": games_p, "pe": pe, "close": pd.DataFrame(close), "refs": pd.DataFrame(refs),
            "signal": signal, "proj": proj.reset_index(drop=True), "graded": tuple(graded),
            "choose": choosing(graded)}


def decision_quotes(pe: pd.DataFrame, times: pd.DataFrame) -> pd.DataFrame:
    """The quotes both families see at T: one number per book, a deciding
    book's alternate line never bet, never a blind bet and never the market's
    fair line (P2's rule, section 8.3, 2026-10-18; models/nba_book_numbers.py,
    the one copy the live nba_team_total_luck also reads)."""
    return NB.visible_numbers(pe, times)


def run_world(world: dict, n_placebo: int = 2, min_prior: int = MIN_PRIOR_GAMES) -> dict:
    """Both families end to end on a world (synthetic_world's keys)."""
    games_p, pe, graded, choose = world["games_p"], world["pe"], world["graded"], world["choose"]
    times = H.per_event_times(pe, POINT)
    vis = decision_quotes(pe, times)
    off = H.offers(vis)
    pricing = market_pricing(world["close"], games_p, graded, min_prior)
    require_pricing(pricing, graded, PRICED_MARKETS, "the market's own pricing")
    neutral = neutral_offers(vis, pricing)
    dd = derivative_data(games_p, pe)
    rows4, cand4 = emit_f4(dd, times, neutral, world["signal"], choose, n_placebo)
    maps, dists = period_maps(world["refs"], games_p, graded, min_prior=min_prior)
    fair = f1_fair(world["proj"], maps, dists)
    rows1, cand1 = emit_f1(dd, times, off, neutral, fair, choose, n_placebo)
    return {"rows": {F4_FAMILY: rows4, F1_FAMILY: rows1}, "cand": {F4_FAMILY: cand4, F1_FAMILY: cand1},
            "times": times, "off": off, "neutral": neutral, "pricing": pricing, "maps": maps,
            "dists": dists, "fair": fair, "dd": dd}


def synthetic_checks() -> dict:
    """Run before any real data is read, by --smoke and --full: the harness's
    sign checks, and all 72 cells through run_cells on synthetic games."""
    H.check()
    out = run_world(synthetic_world())
    n = {f: len(r) for f, r in out["rows"].items()}
    assert n == EXPECTED_CELLS, n
    for fam, rows in out["rows"].items():
        assert sum(r["pool_n"] for r in rows) > 0, f"{fam}: no synthetic bets"
        assert all(r["pool_seasons"] == "2025,2026" and r["choose_seasons"] == "2025" for r in rows)
    print(f"synthetic: {n} cells (72 expected); nothing written")
    return out


# ── modes ───────────────────────────────────────────────────────────────────

def write_rows(rows: list[dict], pop: pd.DataFrame, family: str, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    L.write_cells(rows, out / f"cells_{family}.parquet")
    pop.to_parquet(out / f"population_{family}.parquet")
    print(f"{family}: {len(rows)} cells written to {out}")


def refuse_full(cache: Path) -> list[str]:
    """The go flag, the lineup segments (F1's ratings) and the fetch ledger
    (the full-game closes the market pricing reads): P.refuse_full's checks.
    And a NAMED results folder, as P1 and P2 require: the default is the
    second search's, where the verdict would read P3's cells beside its 422."""
    why = P.refuse_full(cache)
    if not os.environ.get(RESULTS_ENV):
        why.append(f"{RESULTS_ENV} is not set: name the fourth search's results folder")
    if not os.environ.get("NBA_GAME2_BETS"):
        why.append("NBA_GAME2_BETS is not set: a passing cell's figures read its bets")
    return why


def full(cache: Path = H.CACHE, out: Path | None = None) -> None:
    why = refuse_full(cache)
    if why:
        P.refuse(why)
    out = Path(os.environ[RESULTS_ENV]) if out is None else out
    synthetic_checks()
    try:
        data = H.load(cache, seasons=FULL_GAME_SEASONS, require_seasons=FULL_GAME_SEASONS)
        games_p = H.with_periods(data.games, cache)
        pe, graded = load_derivatives(games_p, cache)
    except RuntimeError as e:
        P.refuse([str(e)])
    short = P.stints_short(cache)
    if short:
        P.refuse([f"{cache / P.STINTS_FILE} has segments on too few regular-season games in {short}"])
    choose = choosing(graded)
    print("graded seasons", graded, "choosing", choose, "| full-game rows:", data.notes)
    times = H.per_event_times(pe, POINT)
    vis = decision_quotes(pe, times)
    off = H.offers(vis)
    close = H.pinnacle_close(data)
    pricing = market_pricing(close, games_p, graded)
    require_pricing(pricing, graded, PRICED_MARKETS, "the market's own pricing")
    neutral = neutral_offers(vis, pricing)
    dd = derivative_data(games_p, pe)
    graded_games = data.games[data.games["season"].isin(graded)]

    box, _ = L._load_box(cache)
    proj4 = L.f4_projections(graded_games, L.team_box(box, data.games))
    rows4, cand4 = emit_f4(dd, times, neutral, f4_signal(proj4), choose)
    pop4 = population(F4_FAMILY, rows4, dd, times, off, cand4, "strength", graded)

    w = P.load_world(cache, max_season=H.CONFIRM)
    _, st, models, refs, _ = P.run_projection_setup(w, H.CONFIRM)
    maps, dists = period_maps(calibrated_refs(refs, models), games_p, graded)
    fair = f1_fair(project_at(w, st, models, graded_games, times), maps, dists)
    rows1, cand1 = emit_f1(dd, times, off, neutral, fair, choose)
    pop1 = population(F1_FAMILY, rows1, dd, times, off, cand1, "ev", graded)
    assert len(rows4) + len(rows1) == 72
    # both families written only once both are built: a failed projection
    # leaves no half set for the verdict to read
    write_rows(rows4, pop4, F4_FAMILY, out)
    write_rows(rows1, pop1, F1_FAMILY, out)


def smoke(cache: Path = H.CACHE) -> dict:
    """Synthetic cells, then counts on the real cache. No real cell is run."""
    synthetic_checks()
    games = H.load_games(cache)
    games_p = H.with_periods(games, cache)
    pe = H.load_per_event(games_p, cache)
    graded = graded_seasons(pe["season"].unique())
    in_g = games_p["season"].isin(graded)
    times = H.per_event_times(pe, POINT)
    by = games_p[in_g].groupby("season")
    box, _ = L._load_box(cache)
    proj4 = L.f4_projections(games[games["season"].isin(graded)], L.team_box(box, games))
    data = H.load(cache, seasons=FULL_GAME_SEASONS)
    pricing = market_pricing(H.pinnacle_close(data), H.with_periods(data.games, cache), graded)
    summary = {
        "graded_seasons": list(graded), "choosing_seasons": list(choosing(graded)),
        "games": by.size().to_dict(),
        "share_with_a_derivative_price": by["game_id"].apply(lambda s: float(s.isin(set(pe["game_id"])).mean())).round(4).to_dict(),
        "share_with_a_decision_at_D": by["game_id"].apply(lambda s: float(s.isin(set(times["game_id"])).mean())).round(4).to_dict(),
        "share_with_period_scores": by["home_h1"].apply(lambda s: float(s.notna().mean())).round(4).to_dict(),
        "games_with_a_shooting_luck_number": proj4.groupby("season").size().to_dict(),
        "market_pricing_games": {f"{s} {m}": v.n for (s, m), v in sorted(pricing.items())},
    }
    require_pricing(pricing, graded, PRICED_MARKETS, "the market's own pricing (real cache)")
    print(json.dumps(summary, indent=1, default=str))
    return summary


def quality(cache: Path = H.CACHE, last: int = QUALITY_LAST) -> dict:
    """Price-free: the projection's real path up to 2024-25. The period fits
    (on 2020-21 .. 2023-24) and the 2024-25 projection at each purchase
    instant (its timestamp only). Prints coefficients and counts; never a
    price, a bet or a 2024-25 result."""
    assert last < H.CONFIRM, "2025-26 is never built here"
    games = H.load_games(cache)
    games = games[games["season"] <= last]
    games_p = H.with_periods(games, cache)
    seasons = tuple(s for s in graded_seasons(H.load_per_event(games_p, cache)["season"].unique())
                    if s <= last)
    pe = H.load_per_event(games_p, cache)
    times = H.per_event_times(pe[pe["season"].isin(seasons)], POINT)
    w = P.load_world(cache, max_season=last)
    _, st, models, refs, _ = P.run_projection_setup(w, last)
    maps, dists = period_maps(calibrated_refs(refs, models), games_p, seasons)
    proj = project_at(w, st, models, games[games["season"].isin(seasons)], times)
    res = {"seasons": list(seasons),
           "maps": {f"{s} {p} {k}": [round(a, 3), round(b, 4)] for (s, p, k), (a, b) in sorted(maps.items())},
           "error_distributions": {f"{s} {m}": {"n": d.n, "sd": round(d.sd, 2), "from": d.label}
                                   for (s, m), d in sorted(dists.items())},
           "games_with_a_decision": int(len(times)),
           "games_projected": int(proj["margin"].notna().sum()) if len(proj) else 0}
    print(json.dumps(res, indent=1, default=str))
    return res


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true", help="synthetic cells, then real counts only")
    g.add_argument("--quality", action="store_true", help="price-free projection path, never 2025-26")
    g.add_argument("--full", action="store_true", help=f"every graded season (needs {GO_ENV}=1)")
    a = ap.parse_args(argv)
    if a.full:
        full(H.CACHE)
    elif a.quality:
        quality(H.CACHE)
    else:
        smoke(H.CACHE)


if __name__ == "__main__":
    main()
