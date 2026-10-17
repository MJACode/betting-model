"""HT-1: the halftime rest-of-game total and spread (docs/nba_models_2026.md 7.2, 7.3).

Twelve cells: full-game live total and spread at halftime x 2 sides x model
gap >= 1.5 / 3 / 4.5 points. The method was written into section 7.3 ("How
HT-1 is scored", 2026-10-17) and committed before any number below existed.
This module is that method; nothing in it was chosen by looking at a result.

ORDER OF WORK (7.3): the INFORMATION TEST runs first, per market. A market
whose interval covers zero is closed: its six cells are never graded, and this
script has no switch that grades them anyway.

DEFINITIONS (stated once, used everywhere):

  DECISION   per game, the first purchase (fetch) holding a deciding book's
             spread or total quote that is: stamped inside the halftime break
             (phase 'halftime' in the shared table, scripts/nba_ingame_data.py);
             coherent; with a coherent Pinnacle quote in the same purchase
             stamped within 60 s; and FRESH -- no point scored between the
             quote's stamp and its serving, for the quote and for its Pinnacle
             quote (7.1's rule). Every such deciding-book quote in that purchase
             is an offer. Both teams must have played MIN_GAMES games this
             season (CLAUDE.md section 3, as F4 applied it).
  STATE      at a decision: the shared table's state at the earliest stamp of
             the game's decision quotes (plays logged at or before it). For the
             model FIT: every regular-season game of earlier seasons, from its
             plays in periods 1-2 (game_halves).
  LUCK       luck points of a team = 3 x (3PM - 3PA x r3) + (FTM - FTA x rft),
             r3 / rft its own 3P% and FT% over its EARLIER games this season
             (game dates strictly before). Rates and counts both come from the
             play-by-play, whose 3PA leaves missed end-of-period heaves out
             (nba_ingame_data.is_heave), so the two use one definition.
  CLOSE      Pinnacle's last pre-tip coherent quote (H.pinnacle_close): the
             close total and the close home spread.
  MODEL      least squares on the REST-OF-GAME number, fit on seasons before
             S (2020-21 on itself, reported only):
               totals : final total - first-half points ~ close total, pace
                        (first-half points - close total / 2), luck points of
                        both teams, first-half personal fouls of both teams,
                        |halftime margin|
               spreads: final home margin - halftime margin ~ e (= -close
                        home spread), e x (first-half points / (close total
                        / 2) - 1), halftime margin, luck home - away, personal
                        fouls home - away
             The model's number = first-half part + the fitted rest of game.
  PINNACLE   Pinnacle's live price as a number: the centre of the final total
  CENTRE     (or home margin) at which its no-vig probability holds at its
             number, solved through the EMPIRICAL distribution of (final -
             Pinnacle's halftime number) on earlier seasons' decision games
             (H.dist_by_season with min_prior = 150; 2020-21 on itself).
  INFO TEST  per market and season S: base = centre + a; with the model =
             centre + a + b x (model - centre); a, b by least squares on
             earlier seasons' decision games. Statistic: the drop in mean
             squared error of the final number (points squared), whole-day
             bootstrap 95% (4,000 resamples, seed 7), on 2021-22 -> 2024-25
             pooled and 2025-26 alone. Information = BOTH intervals wholly
             above zero.
  GRID       strength = model - Pinnacle's centre (points, side A = home /
             over; the other side its negative), the same for every book. A
             side is bet when strength >= cut, at its best deciding offer under
             Pinnacle's halftime fair price (H.run_cells, strength="strength").

    PYTHONPATH=. python -m scripts.nba_ingame_ht1 --halves     # build the per-game first halves (cached)
    PYTHONPATH=. python -m scripts.nba_ingame_ht1              # the information test; the grid if it passes
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import nba_game_harness as H  # noqa: E402
from scripts import nba_ingame_data as D  # noqa: E402
from scripts.nba_game_market_lab import threshold  # noqa: E402

OUT_DIR = D.OUT_DIR
HALVES = OUT_DIR / "ht1_game_halves.parquet"
CELLS = OUT_DIR / "cells_HT-1.parquet"
FAMILY, POINT = "HT-1", "HT"
MARKETS = ("totals", "spreads")
SIDES = {"totals": ["over", "under"], "spreads": ["home", "away"]}
CUTS = (1.5, 3.0, 4.5)
MIN_GAMES = 10
MIN_PRIOR_DIST = 150
N_PLACEBO = 20
LAST_Q2_S = 300.0            # the staleness diagnostic: points in Q2's last 5 minutes
SEASONS = D.SEASONS
CHOOSE, CONFIRM, REGIME = H.CHOOSE, H.CONFIRM, H.REGIME
STATE = ["h_pts", "a_pts", "h_fg3a", "h_fg3m", "h_fta", "h_ftm", "h_pf",
         "a_fg3a", "a_fg3m", "a_fta", "a_ftm", "a_pf"]

FEATS = {"totals": ["close_total", "pace_pts", "luck_sum", "pf_sum", "abs_margin"],
         "spreads": ["e_margin", "e_pace", "margin", "luck_diff", "pf_diff"]}
SCORE_ONLY = {"totals": ["close_total", "pace_pts"], "spreads": ["e_margin", "margin"]}


# ── per-game first halves (the model's fit population) ──────────────────────

def halves_from_plays(plays: pd.DataFrame) -> pd.DataFrame:
    """One row per game: first-half (periods 1-2) points, 3PA, 3PM, FTA, FTM,
    personal fouls per side; whole-game 3PA, 3PM, FTA, FTM per side (the rates'
    inputs); points in Q2's last LAST_Q2_S seconds per side (a diagnostic).
    3PA is the play-by-play's, missed heaves left out (nba_ingame_data)."""
    p = plays[plays["team_side"].isin([D.HOME, D.AWAY])]
    h1 = p[p["period"] <= 2]
    late = p[(p["period"] == 2) & (p["clock_s"] <= LAST_Q2_S)]
    parts = []
    for frame, cols, suf in ((h1, ["points", "fg3a", "fg3m", "fta", "ftm", "pf"], "h1"),
                             (p, ["fg3a", "fg3m", "fta", "ftm"], "game"),
                             (late, ["points"], "q2l5")):
        s = frame.groupby(["game_id", "team_side"])[cols].sum().unstack("team_side")
        s.columns = [f"{'h' if side == D.HOME else 'a'}_{c}_{suf}" for c, side in s.columns]
        parts.append(s)
    out = pd.concat(parts, axis=1).fillna(0.0).reset_index()
    return out


def build_halves(cache: Path = H.CACHE, seasons=SEASONS) -> pd.DataFrame:
    games = H.load_games(cache)
    games = games[games["season"].isin(list(seasons))]
    emap = D.espn_map(cache)
    frames = []
    for s in seasons:
        t0 = time.time()
        want = emap[emap["game_id"].isin(set(games.loc[games["season"] == s, "game_id"]))]
        plays, _, notes = D.season_plays(s, want, games)
        hv = halves_from_plays(plays)
        frames.append(hv)
        print(f"halves {s}: {len(hv)} games ({notes['games_clock_broken']} dropped for the clock; "
              f"{time.time() - t0:.0f}s)", flush=True)
    return pd.concat(frames, ignore_index=True)


def rates_before(halves: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Per (game, side): the team's 3P% and FT% over its games this season with
    game_date strictly before this game's, and how many such games."""
    g = games[["game_id", "season", "game_date", "home_team", "away_team"]]
    x = halves.merge(g, on="game_id")
    long = []
    for pre, team in (("h", "home_team"), ("a", "away_team")):
        long.append(pd.DataFrame({
            "game_id": x["game_id"], "season": x["season"], "game_date": x["game_date"].astype(str),
            "team": x[team], "side": pre,
            "fg3a": x[f"{pre}_fg3a_game"], "fg3m": x[f"{pre}_fg3m_game"],
            "fta": x[f"{pre}_fta_game"], "ftm": x[f"{pre}_ftm_game"]}))
    t = pd.concat(long, ignore_index=True).sort_values(["season", "team", "game_date", "game_id"])
    grp = t.groupby(["season", "team"])
    for c in ("fg3a", "fg3m", "fta", "ftm"):
        t[f"cum_{c}"] = grp[c].cumsum() - t[c]           # strictly earlier games
    t["n_before"] = grp.cumcount()
    same_day = t.duplicated(["season", "team", "game_date"], keep=False)
    if same_day.any():                                   # never two games a day; refuse if so
        raise ValueError(f"{int(same_day.sum())} team-dates with two games")
    t["r3"] = t["cum_fg3m"] / t["cum_fg3a"].where(t["cum_fg3a"] > 0)
    t["rft"] = t["cum_ftm"] / t["cum_fta"].where(t["cum_fta"] > 0)
    w = t.pivot_table(index="game_id", columns="side", values=["r3", "rft", "n_before"], aggfunc="first")
    w.columns = [f"{side}_{c}" for c, side in w.columns]
    return w.reset_index()


def luck_points(fg3m, fg3a, ftm, fta, r3, rft):
    """3 x (3PM - 3PA x r3) + (FTM - FTA x rft): points above expectation."""
    return 3.0 * (np.asarray(fg3m, float) - np.asarray(fg3a, float) * np.asarray(r3, float)) + (
        np.asarray(ftm, float) - np.asarray(fta, float) * np.asarray(rft, float))


def add_features(x: pd.DataFrame) -> pd.DataFrame:
    """Model inputs and targets from first-half state columns (h_pts, a_pts,
    h_fg3a, ... STATE), rates (h_r3, ...), the close (close_total,
    close_spread) and the final score."""
    x = x.copy()
    h1 = x["h_pts"] + x["a_pts"]
    x["h1_total"] = h1
    x["margin"] = x["h_pts"] - x["a_pts"]
    x["abs_margin"] = x["margin"].abs()
    x["pace_pts"] = h1 - x["close_total"] / 2.0
    x["e_margin"] = -x["close_spread"]
    x["e_pace"] = x["e_margin"] * (h1 / (x["close_total"] / 2.0) - 1.0)
    lh = luck_points(x["h_fg3m"], x["h_fg3a"], x["h_ftm"], x["h_fta"], x["h_r3"], x["h_rft"])
    la = luck_points(x["a_fg3m"], x["a_fg3a"], x["a_ftm"], x["a_fta"], x["a_r3"], x["a_rft"])
    x["luck_sum"], x["luck_diff"] = lh + la, lh - la
    x["pf_sum"], x["pf_diff"] = x["h_pf"] + x["a_pf"], x["h_pf"] - x["a_pf"]
    if "final_home" in x:
        x["final_total"] = x["final_home"] + x["final_away"]
        x["final_margin"] = x["final_home"] - x["final_away"]
        x["rest_totals"] = x["final_total"] - h1
        x["rest_spreads"] = x["final_margin"] - x["margin"]
    return x


def first_part(x: pd.DataFrame, market: str) -> pd.Series:
    """What the first half already settled: points (totals) or margin (spreads)."""
    return x["h1_total"] if market == "totals" else x["margin"]


def fit_population(halves: pd.DataFrame, rates: pd.DataFrame, games: pd.DataFrame,
                   close: pd.DataFrame) -> pd.DataFrame:
    """Every game with first halves, rates, both teams >= MIN_GAMES before the
    date, a Pinnacle close total and spread, and a final score."""
    h = halves.rename(columns={f"{p}_{c}_h1": f"{p}_{c if c != 'points' else 'pts'}"
                               for p in ("h", "a") for c in ("points", "fg3a", "fg3m", "fta", "ftm", "pf")})
    x = h.merge(rates, on="game_id").merge(
        games[["game_id", "season", "game_date", "home_score", "away_score"]], on="game_id")
    x = x.rename(columns={"home_score": "final_home", "away_score": "final_away"})
    x = attach_close(x, close)
    keep = (x["h_n_before"] >= MIN_GAMES) & (x["a_n_before"] >= MIN_GAMES)
    x = x[keep & x["close_total"].notna() & x["close_spread"].notna()]
    return add_features(x).reset_index(drop=True)


def attach_close(x: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    c = close[close["market"].isin(MARKETS)].pivot_table(index="game_id", columns="market",
                                                         values="close_line", aggfunc="first")
    c = c.rename(columns={"totals": "close_total", "spreads": "close_spread"}).reset_index()
    return x.merge(c, on="game_id", how="left")


def ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    A = np.column_stack([np.ones(len(X)), X])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    return coef


def model_numbers(train: pd.DataFrame, test: pd.DataFrame, market: str, feats=None,
                  seasons=SEASONS) -> tuple[pd.Series, dict]:
    """The model's final number for every row of `test`, walk-forward: rows of
    season S from a fit on train rows of seasons < S (2020-21: on itself).
    Returns (numbers, {season: (n_train, source)})."""
    feats = FEATS[market] if feats is None else feats
    out = pd.Series(np.nan, index=test.index)
    info = {}
    for s in sorted(set(test["season"])):
        tr = train[train["season"] < s]
        src = "earlier seasons"
        if tr.empty:
            if s != REGIME:
                raise ValueError(f"season {s} has no earlier season to fit on")
            tr, src = train[train["season"] == s], "own season (reported only)"
        tr = tr.dropna(subset=[*feats, f"rest_{market}"])
        coef = ols(tr[feats].to_numpy(float), tr[f"rest_{market}"].to_numpy(float))
        te = test[test["season"] == s]
        rest = coef[0] + te[feats].to_numpy(float) @ coef[1:]
        out.loc[te.index] = first_part(te, market).to_numpy(float) + rest
        info[int(s)] = (int(len(tr)), src, np.round(coef, 4).tolist())
    return out, info


# ── the halftime decision set ───────────────────────────────────────────────

def fresh_pinnacle(q: pd.DataFrame, d: pd.DataFrame) -> pd.Series:
    """Points scored between Pinnacle's attached quote's stamp and its serving
    (NaN where the Pinnacle row is missing), aligned to `d`."""
    pin = q[q["book"] == H.SHARP].drop_duplicates(["game_id", "market", "fetch_at", "stamp"])
    pin = pin.set_index(["game_id", "market", "fetch_at", "stamp"])["pts_since_stamp"]
    key = pd.MultiIndex.from_frame(d[["game_id", "market", "fetch_at", "pin_stamp"]])
    return pd.Series(pin.reindex(key).to_numpy(), index=d.index)


def decision_quotes(q: pd.DataFrame) -> pd.DataFrame:
    """The deciding-book offers of each game's decision purchase (DECISION)."""
    h = q[(q["phase"] == "halftime") & q["market"].isin(MARKETS)
          & q["book"].isin(H.BETTABLE) & q["coherent"] & q["pin_fa"].notna()].copy()
    h["pin_pts_since"] = fresh_pinnacle(q, h)
    h = h[(h["pts_since_stamp"] == 0) & (h["pin_pts_since"] == 0)]
    first = h.groupby("game_id")["fetch_at"].transform("min")
    return h[h["fetch_at"] == first].reset_index(drop=True)


def decision_games(dq: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, market): Pinnacle's quote and the game state at the
    earliest decision stamp of the game."""
    earliest = dq.sort_values("stamp").drop_duplicates("game_id")[["game_id", "stamp", *STATE]]
    pin = dq.sort_values("stamp").drop_duplicates(["game_id", "market"])[
        ["game_id", "season", "game_date", "tip", "market", "fetch_at", "pin_stamp", "pin_line",
         "pin_fa", "pin_price_a", "pin_price_b", "final_home", "final_away"]]
    n_pin = dq.groupby(["game_id", "market"])["pin_stamp"].nunique()
    if (n_pin > 1).any():
        raise ValueError("a decision purchase attaches two Pinnacle quotes to one game and market")
    return pin.merge(earliest.rename(columns={"stamp": "state_at"}), on="game_id")


# ── Pinnacle's centre ───────────────────────────────────────────────────────

def ht_dists(dg: pd.DataFrame, seasons) -> dict:
    """(season, market) -> the empirical distribution of (final - Pinnacle's
    halftime number), side A, from earlier seasons' decision games."""
    margin = dg["final_home"] - dg["final_away"]
    total = dg["final_home"] + dg["final_away"]
    r = pd.DataFrame({"season": dg["season"].astype(int), "market": dg["market"],
                      "resid": np.where(dg["market"] == "spreads", margin + dg["pin_line"],
                                        total - dg["pin_line"])})
    dist = H.dist_by_season(r, seasons, min_prior=MIN_PRIOR_DIST)
    for (s, m), v in dist.items():
        if s != REGIME and "(prior)" not in v.label:
            raise ValueError(f"{s} {m}: fewer than {MIN_PRIOR_DIST} earlier games for the distribution")
    return dist


def centre(market, line, fa, season, dists) -> np.ndarray:
    """Side-A centre (final total, or home margin) at which `fa` holds at `line`."""
    market, season = np.asarray(market), np.asarray(season)
    sig = np.array([dists.get((int(s), m)) for s, m in zip(season, market)], dtype=object)
    return H.solve_any(threshold(market, line), np.asarray(fa, float), sig)


# ── the information test ────────────────────────────────────────────────────

def mse_drop_rows(rows: pd.DataFrame, ref: str = "mu_ref", model: str = "mu_model") -> pd.DataFrame:
    """Per row of each season S: d = (y - base)^2 - (y - with model)^2, base =
    ref + a and with model = ref + a + b x (model - ref), a and b fit on rows
    of seasons < S (S = 2020-21: on itself, reported only). Columns: season,
    game_date, d, n_fit, beta."""
    out = []
    for s in sorted(set(rows["season"])):
        tr = rows[rows["season"] < s]
        own = tr.empty
        if own:
            tr = rows[rows["season"] == s]
        te = rows[rows["season"] == s]
        yt, gt = (tr["y"] - tr[ref]).to_numpy(float), (tr[model] - tr[ref]).to_numpy(float)
        a0 = yt.mean()
        a1, b = ols(gt[:, None], yt)
        y, g = (te["y"] - te[ref]).to_numpy(float), (te[model] - te[ref]).to_numpy(float)
        d = (y - a0) ** 2 - (y - a1 - b * g) ** 2
        out.append(pd.DataFrame({"season": te["season"].to_numpy(), "game_date": te["game_date"].to_numpy(),
                                 "d": d, "n_fit": len(tr), "beta": b, "own_season": own}))
    return pd.concat(out, ignore_index=True)


def day_ci(df: pd.DataFrame, col: str = "d", n_boot: int = H.N_BOOT, seed: int = H.SEED) -> dict:
    """Mean of `col` and its whole-day bootstrap 95% interval."""
    if df.empty:
        return {"n": 0, "mean": np.nan, "lo": np.nan, "hi": np.nan}
    s = df.groupby("game_date")[col].agg(["sum", "size"])
    rng = np.random.default_rng(seed)
    S, N = s["sum"].to_numpy(), s["size"].to_numpy()
    out = np.empty(n_boot)
    step = max(1, 2_000_000 // max(len(s), 1))
    for i in range(0, n_boot, step):
        k = min(step, n_boot - i)
        idx = rng.integers(0, len(s), size=(k, len(s)))
        out[i:i + k] = S[idx].sum(1) / N[idx].sum(1)
    lo, hi = np.percentile(out, [2.5, 97.5])
    return {"n": int(len(df)), "days": int(len(s)), "mean": float(df[col].mean()),
            "lo": float(lo), "hi": float(hi)}


def info_summary(d: pd.DataFrame) -> dict:
    """The test's two intervals and its verdict (INFO TEST)."""
    ch = day_ci(d[d["season"].isin(CHOOSE)])
    cf = day_ci(d[d["season"] == CONFIRM])
    rg = day_ci(d[d["season"] == REGIME])
    return {"choose": ch, "confirm": cf, "regime_2021_in_sample": rg,
            "information": bool(ch["lo"] > 0 and cf["lo"] > 0),
            "beta": {int(s): round(float(b), 3) for s, b in d.groupby("season")["beta"].first().items()}}


def side_a_outcome(market, line, home, away) -> np.ndarray:
    """1 / 0 for side A at `line`, NaN on a push (the staleness diagnostic)."""
    from scripts.nba_game_market_lab import settle
    side = np.where(np.asarray(market) == "totals", "over", "home")
    r = settle(np.asarray(market), side, np.asarray(line, float), np.asarray(home, float),
               np.asarray(away, float))
    return np.where(r == "W", 1.0, np.where(r == "L", 0.0, np.nan))


# ── the grid (a market with information only) ───────────────────────────────

def harness_quotes(dq: pd.DataFrame, q: pd.DataFrame) -> pd.DataFrame:
    """The decision offers plus their Pinnacle quote, in the harness's quote
    columns, with T = the decision purchase's earliest stamp."""
    pin_keys = dq[["game_id", "market", "fetch_at", "pin_stamp"]].drop_duplicates()
    pin = q[q["book"] == H.SHARP].merge(pin_keys.rename(columns={"pin_stamp": "stamp"}),
                                        on=["game_id", "market", "fetch_at", "stamp"])
    cols = ["game_id", "season", "game_date", "tip", "market", "book", "stamp", "fetch_at", "line",
            "price_a", "price_b", "coherent"]
    v = pd.concat([dq[cols], pin[cols]], ignore_index=True).rename(columns={"stamp": "snapshot_at"})
    t = dq.groupby("game_id")["stamp"].min().rename("T")
    return v.merge(t.reset_index(), on="game_id")


def strength_signal(dg: pd.DataFrame) -> pd.DataFrame:
    """(game_id, market, strength): model - Pinnacle's centre toward side A."""
    return dg[["game_id", "market"]].assign(strength=(dg["mu_model"] - dg["mu_pin"]).to_numpy())


def run_grid(market: str, dq: pd.DataFrame, q: pd.DataFrame, dg: pd.DataFrame, games: pd.DataFrame,
             dists: dict) -> list[dict]:
    from scripts.nba_game2_luck import placebo_frames, side_strength
    vis = harness_quotes(dq[dq["market"] == market], q)
    fair = H.market_fair(vis, dists)
    off = H.offers(vis[vis["book"].isin(H.BETTABLE)])
    neutral = H.fair_offers(off, fair)
    sig = strength_signal(dg[dg["market"] == market])
    cand = side_strength(neutral, sig)
    pl = placebo_frames(neutral, sig, games)
    times = vis[["game_id", "T"]].drop_duplicates().assign(lead_min=np.nan)
    data = H.Data(games=games, quotes=vis,
                  fetches=pd.DataFrame(columns=["game_id", "tip", "fetch_at", "lead_min"]), notes={})
    rows = H.run_cells(data, FAMILY, POINT, cand, neutral, CUTS, {market: SIDES[market]},
                       close=None, sig=None, placebo=pl, strength="strength", times=times)
    for r in rows:      # not measurable at halftime (7.3): never read a 0 as a fact
        r["share_still_offered"] = r["units_still_offered"] = np.nan
    return rows, cand


# ── main ────────────────────────────────────────────────────────────────────

def fmt_ci(r: dict, scale: float = 1.0) -> str:
    return (f"{r['mean'] * scale:+.3f} ({r['lo'] * scale:+.3f} to {r['hi'] * scale:+.3f}), "
            f"{r['n']} games, {r.get('days', 0)} days")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--halves", action="store_true", help="(re)build the per-game first halves")
    ap.add_argument("--quotes", default=str(D.OUT))
    a = ap.parse_args()
    pd.set_option("display.width", 220)
    if a.halves or not HALVES.exists():
        hv = build_halves()
        HALVES.parent.mkdir(parents=True, exist_ok=True)
        hv.to_parquet(HALVES, index=False)
        print(f"wrote {HALVES} ({len(hv):,} games)")
        if a.halves:
            return
    hv = pd.read_parquet(HALVES)
    games = H.load_games(H.CACHE)
    games = games[games["season"].isin(list(SEASONS))].reset_index(drop=True)
    data = H.load(H.CACHE, seasons=SEASONS)
    close = H.pinnacle_close(data)
    rates = rates_before(hv, games)
    fit = fit_population(hv, rates, games, close)
    print("fit population (games per season):", fit.groupby("season").size().to_dict())

    q = pd.read_parquet(a.quotes)
    dq = decision_quotes(q)
    dg = decision_games(dq)
    dg = dg.merge(rates, on="game_id", how="left")
    dg = attach_close(dg, close)
    ok = (dg["h_n_before"] >= MIN_GAMES) & (dg["a_n_before"] >= MIN_GAMES) & dg["close_total"].notna() \
        & dg["close_spread"].notna() & dg["h_r3"].notna() & dg["a_r3"].notna()
    print("decision games per season x market, before the 10-game rule:")
    print(dg.groupby(["season", "market"]).size().unstack().to_string())
    dg = add_features(dg[ok].reset_index(drop=True))
    dq = dq[dq.set_index(["game_id", "market"]).index.isin(dg.set_index(["game_id", "market"]).index)]
    print("after it (the population):")
    print(dg.groupby(["season", "market"]).size().unstack().to_string())

    # the table's state at the stamp against the game's own first half (a check, filters nothing)
    chk = dg.drop_duplicates("game_id").merge(hv[["game_id", "h_points_h1", "a_points_h1", "h_fg3a_h1",
                                                  "a_fg3a_h1", "h_pf_h1", "a_pf_h1"]], on="game_id")
    agree = ((chk["h_pts"] == chk["h_points_h1"]) & (chk["a_pts"] == chk["a_points_h1"])
             & (chk["h_fg3a"] == chk["h_fg3a_h1"]) & (chk["a_fg3a"] == chk["a_fg3a_h1"])
             & (chk["h_pf"] == chk["h_pf_h1"]) & (chk["a_pf"] == chk["a_pf_h1"]))
    print(f"state at the stamp equals the game's periods 1-2 (points, 3PA, fouls): "
          f"{int(agree.sum())} of {len(chk)} games")

    dists = ht_dists(dg, SEASONS)
    dg["mu_pin"] = centre(dg["market"], dg["pin_line"], dg["pin_fa"], dg["season"], dists)
    dg["y"] = np.where(dg["market"] == "totals", dg["final_total"], dg["final_margin"])
    dg["mu_raw"] = np.where(dg["market"] == "totals", dg["pin_line"], -dg["pin_line"])
    # the deciding books' own median centre (reported beside)
    dq2 = dq.merge(dg[["game_id", "market"]], on=["game_id", "market"])
    dq2 = dq2.assign(mu_book=centre(dq2["market"], dq2["line"], dq2["fa"], dq2["season"], dists))
    dg = dg.merge(dq2.groupby(["game_id", "market"])["mu_book"].median().rename("mu_books").reset_index(),
                  on=["game_id", "market"], how="left")

    results = {}
    for market in MARKETS:
        rows = dg[dg["market"] == market].copy()
        fm = fit
        rows["mu_model"], finfo = model_numbers(fm, rows, market)
        rows["mu_score"], _ = model_numbers(fm, rows, market, feats=SCORE_ONLY[market])
        dg.loc[rows.index, "mu_model"] = rows["mu_model"]
        dg.loc[rows.index, "mu_score"] = rows["mu_score"]
        print(f"\n=== {market} === model fits (season: rows, source, coefficients "
              f"[const, {', '.join(FEATS[market])}]): {finfo}")
        test = info_summary(mse_drop_rows(rows.assign(mu_ref=rows["mu_pin"])))
        results[market] = test
        print(f"INFORMATION TEST, drop in mean squared error (points^2) when the model is added to "
              f"Pinnacle's live centre:\n  2021-22 to 2024-25: {fmt_ci(test['choose'])}\n"
              f"  2025-26:            {fmt_ci(test['confirm'])}\n"
              f"  2020-21 (in sample, reported only): {fmt_ci(test['regime_2021_in_sample'])}\n"
              f"  beta by season: {test['beta']}\n  INFORMATION: {test['information']}")
        print("beside, never the gate:")
        for label, ref, mod in (("score-only model vs Pinnacle's centre", "mu_pin", "mu_score"),
                                ("the model vs the deciding books' median centre", "mu_books", "mu_model"),
                                ("the model vs Pinnacle's raw number", "mu_raw", "mu_model")):
            r = rows.dropna(subset=[ref, mod])
            t = info_summary(mse_drop_rows(r.assign(mu_ref=r[ref]), model=mod))
            print(f"  {label}: choose {fmt_ci(t['choose'])}; 2025-26 {fmt_ci(t['confirm'])}; "
                  f"beta {t['beta']}")
        base_mse = {int(s): round(float(((g["y"] - g["mu_pin"]) ** 2).mean()), 1)
                    for s, g in rows.groupby("season")}
        print(f"  mean squared error of Pinnacle's centre by season (points^2): {base_mse}")

    # staleness at halftime (diagnostic): points in Q2's last 5 minutes
    from scripts.nba_ingame_staleness import slope_ci
    st = dg.merge(hv[["game_id", "h_points_q2l5", "a_points_q2l5"]], on="game_id")
    st["x"] = np.where(st["market"] == "totals", st["h_points_q2l5"] + st["a_points_q2l5"],
                       st["h_points_q2l5"] - st["a_points_q2l5"])
    st["yb"] = side_a_outcome(st["market"], st["pin_line"], st["final_home"], st["final_away"])
    print("\nstaleness at halftime: slope of (result - Pinnacle's no-vig) on points in Q2's last 5 min, "
          "toward side A")
    for market in MARKETS:
        s1 = st[(st["market"] == market) & st["yb"].notna()]
        r1 = slope_ci(s1.assign(resid=s1["yb"] - s1["pin_fa"]))
        s2 = st[st["market"] == market]
        r2 = slope_ci(s2.assign(resid=s2["y"] - s2["mu_pin"]))
        print(f"  {market}: probability {r1['slope']:+.4f} ({r1['lo']:+.4f} to {r1['hi']:+.4f}), n {r1['n']}; "
              f"points {r2['slope']:+.3f} ({r2['lo']:+.3f} to {r2['hi']:+.3f})")

    dg.to_parquet(OUT_DIR / "ht1_decisions.parquet", index=False)
    opened = [m for m in MARKETS if results[m]["information"]]
    if not opened:
        print("\nHT-1 CLOSED: no market shows information beyond Pinnacle's live price. No grid.")
        return
    from scripts.nba_game2_luck import write_cells
    from scripts.nba_game2_verdict import house_verdict
    rows_all = []
    for market in opened:
        got, _ = run_grid(market, dq, q, dg, games, dists)
        rows_all += got
    write_cells(rows_all, CELLS)
    v = house_verdict(pd.read_parquet(CELLS))
    show = ["market", "side", "cut", "pool_n", "pool_units", "pool_roi", "pool_ci95_lo", "pool_ci95_hi",
            "pool_seasons_counted", "pool_seasons_positive", "house_passes", "house_failed"]
    print(f"\ncells written to {CELLS}:")
    print(v[show].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
