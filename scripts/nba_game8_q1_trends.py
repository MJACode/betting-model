"""NBA eighth search: mike's first-quarter trend method.

docs/nba_models_2026.md section 12 registers the cells and fixes every choice,
written BEFORE any cell was graded (2026-10-28). This lab EMITS cells through
the shared harness (scripts/nba_game_harness, H); the pass/fail script judges
them (scripts/nba_game2_verdict.py --house5: section 9.1's bars). Nothing here
grades a bet itself, and no cut, constant or rule below was chosen from a
betting result.

64 cells (asserted), decided at each game's per-game purchase 45-75 minutes
before tip (decision point D, H.per_event_times), 2023-24 .. 2025-26 pooled:

  NUMBER    the game's first-quarter number at its purchase: Pinnacle's main
            spread (the HOME number) or total, else the median of the deciding
            books' main numbers (NB.visible_numbers), rounded to the nearest
            half point (a quarter rounds up).
  RESULT    a team's first-quarter margin against that number: cover +1, fail
            -1, push 0; the total: over +1, under -1, push 0.
  RECORD    net over the team's last N games at TODAY's venue (home games for
            the home team, road games for the away team) with a number and
            trustworthy first-quarter scores (H.with_periods), strictly before
            today's date, reaching into the previous season. Fewer than N such
            games: no record, no bet.
  Q1A       first-quarter spread, the HOT team (a per-game side, side_pick):
            the team with the higher venue net; a tie is no bet.
            k = min(hot net, -cold net). Last 5: k >= 1 / 3 / 5 (mike's 4-1 or
            5-0 against 1-4 or 0-5 is k >= 3). Last 10: k >= 2 / 4 / 6. The
            step ("bump it out to L10"): a last-5 hot team at net >= 3 against
            an opponent at net -1 or -2; the last-5 hot team is bet when
            k = min(its last-10 net, -the opponent's last-10 net) >= 2 / 4.
            Checks: none; the spread check (the season-to-date projected
            first-quarter margin covers the number from the hot team's side).
  Q1T       first-quarter total, over and under. Over: k = min(home net, away
            net); under: k = min(-home net, -away net). Last 5: k >= 1 / 3 / 5;
            last 10: k >= 2 / 4 / 6. Checks: none; scoring (the season-to-date
            projected total beyond the number on the side bet); pace (the two
            teams' season-to-date possessions per game above / below the
            league's); both.
  AVERAGES  season-to-date first-quarter points scored and allowed and
            possessions per game, this season's games before today at every
            venue, at least 5 games each.
  PRICE     the side's best deciding offer at that book's own main number,
            under the first-quarter market's fair line (H.market_fair priced by
            P3.market_pricing): the rule mechanism F4 and F7 used.
  BANDS     along k within one window, side and check: last 5 from -1 (edges
            1, 3, 5), last 10 from 0 (2, 4, 6), the step from 0 (2, 4).
  PLACEBO   200 runs, seeds 1-200: every game's trend inputs (both teams'
            venue records, season-to-date averages and pace) moved together to
            another game on the same date; each game keeps its own number and
            prices, and the rule is recomputed.
  CONTROLS  the fade of every unchecked cell (the cold team; the other total
            side), graded and reported, never judged (control_* families).

    PYTHONPATH=. python -m scripts.nba_game8_q1_trends --smoke
    NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> NBA_GAME2_BETS=<folder>/bets \
        PYTHONPATH=. python -m scripts.nba_game8_q1_trends --full

--smoke runs the synthetic checks, then prints on the real cache only counts
(games with a record, games each cell would bet with a deciding offer). It
never grades a real bet. --full writes <NBA_GAME2_RESULTS>/cells_*.parquet,
population_*.parquet and the per-game inputs and signals.
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
from models import nba_book_numbers as NB  # noqa: E402
from scripts import nba_game2_luck as L  # noqa: E402
from scripts import nba_game2_projection as P  # noqa: E402
from scripts import nba_game4_p3 as P3  # noqa: E402
from scripts import nba_game5 as G5  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402

GO_ENV, RESULTS_ENV, BETS_ENV = G5.GO_ENV, G5.RESULTS_ENV, G5.BETS_ENV
SPREAD, TOTAL = "spreads_q1", "totals_q1"
FAMILY_A, FAMILY_T = "Q1A", "Q1T"
CONTROL_A, CONTROL_T = "control_Q1A_fade", "control_Q1T_fade"
GRADED = (2024, 2025, 2026)                    # 2023-24 .. 2025-26
POINT = "D"
MIN_AVG_GAMES = 5
N_PLACEBO = 200
PLACEBO_SEEDS = tuple(range(1, N_PLACEBO + 1))
# window -> (record length, cuts on k, the lowest band's floor)
WINDOWS = {"L5": (5, (1.0, 3.0, 5.0), -1.0), "L10": (10, (2.0, 4.0, 6.0), 0.0)}
STEP = "L5to10"
STEP_CUTS, STEP_FLOOR = (2.0, 4.0), 0.0
STEP_HOT_MIN, STEP_COLD = 3.0, (-1.0, -2.0)
SPREAD_CHECKS = ("none", "spread")
TOTAL_CHECKS = ("none", "scoring", "pace", "both")
EXPECTED_CELLS = 64
SIDE_HOT, SIDE_COLD = "hot", "cold"
FADE_SIDES = {"fade_over": "under", "fade_under": "over"}   # control label -> the real side bet


# ── the game's number and each team's result ────────────────────────────────

def half_round(x) -> np.ndarray:
    """Nearest half point, a quarter rounding up (-1.25 -> -1.0, 1.25 -> 1.5)."""
    return np.floor(np.asarray(x, float) * 2.0 + 0.5) / 2.0


def game_numbers(vis: pd.DataFrame) -> pd.DataFrame:
    """(game_id, market, number): Pinnacle's coherent main first-quarter number
    at the game's purchase, else the median of the deciding books' coherent
    main numbers, rounded to the nearest half point."""
    v = vis[vis["market"].isin([SPREAD, TOTAL]) & vis["coherent"].astype(bool)]
    pin = v[v["book"] == H.SHARP].groupby(["game_id", "market"])["line"].median()
    dec = v[v["book"].isin(H.BETTABLE)].groupby(["game_id", "market"])["line"].median()
    num = pin.combine_first(dec)
    return pd.DataFrame({"game_id": num.index.get_level_values(0),
                         "market": num.index.get_level_values(1),
                         "number": half_round(num.to_numpy())}).reset_index(drop=True)


def team_games(games_p: pd.DataFrame, numbers: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, team) with trustworthy first-quarter scores: venue,
    first-quarter points for and against, and the team's result against the
    game's spread (ats) and total (ou) numbers, NaN where the game has none."""
    g = games_p.dropna(subset=["home_q1", "away_q1"]).copy()
    w = numbers.pivot_table(index="game_id", columns="market", values="number", aggfunc="first")
    w = w.reindex(columns=[SPREAD, TOTAL]).reset_index()
    g = g.merge(w, on="game_id", how="left")
    hq, aq = g["home_q1"].astype(float), g["away_q1"].astype(float)
    ats_home = np.sign((hq - aq) + g[SPREAD].astype(float))   # spread_home is the HOME number
    ou = np.sign((hq + aq) - g[TOTAL].astype(float))
    base = g[["game_id", "season", "game_date", "tip"]]
    home = base.assign(team=g["home_team"], venue="home", ats=ats_home, ou=ou, pf=hq, pa=aq)
    away = base.assign(team=g["away_team"], venue="away", ats=-ats_home, ou=ou, pf=aq, pa=hq)
    out = pd.concat([home, away], ignore_index=True)
    out["season"] = out["season"].astype(int)
    return out


def _asof(targets: pd.DataFrame, rows: pd.DataFrame, by: list[str], cols: list[str]) -> pd.DataFrame:
    """For each target the last `rows` row with game_date STRICTLY before the
    target's date (same `by` keys); targets keep their order."""
    t = targets.assign(_d=pd.to_datetime(targets["game_date"]), _i=np.arange(len(targets)))
    r = rows.assign(_d=pd.to_datetime(rows["game_date"]))[["_d", *by, *cols]]
    out = pd.merge_asof(t.sort_values("_d"), r.sort_values("_d"), on="_d", by=by,
                        allow_exact_matches=False)
    return out.sort_values("_i").reset_index(drop=True)[cols]


def last_n(tg: pd.DataFrame, targets: pd.DataFrame, col: str, n: int) -> np.ndarray:
    """Each target's (team, venue, game_date) net of `col` over that team's
    last n games at that venue with a result, strictly before the date; NaN
    with fewer than n such games."""
    r = tg[tg[col].notna()].sort_values(["team", "venue", "tip"]).copy()
    r["net"] = r.groupby(["team", "venue"])[col].transform(lambda s: s.rolling(n).sum())
    return _asof(targets, r, ["team", "venue"], ["net"])["net"].to_numpy(float)


def season_averages(tg: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """Each target's (team, season, game_date) season-to-date first-quarter
    points for and against per game and games counted, every venue."""
    r = tg.sort_values(["team", "season", "tip"]).copy()
    grp = r.groupby(["team", "season"])
    r["n"] = grp.cumcount() + 1
    r["pf_sum"], r["pa_sum"] = grp["pf"].cumsum(), grp["pa"].cumsum()
    x = _asof(targets, r, ["team", "season"], ["n", "pf_sum", "pa_sum"])
    n = x["n"].fillna(0).to_numpy(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return pd.DataFrame({"n": n, "pf": x["pf_sum"].to_numpy(float) / n,
                             "pa": x["pa_sum"].to_numpy(float) / n})


def pace_inputs(tb: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """Each target's season-to-date possessions per game (and games counted),
    and the league's per team game over the same season's games before the
    date."""
    r = tb[["game_id", "team", "season", "game_date", "poss"]].dropna(subset=["poss"]).copy()
    r["season"] = r["season"].astype(int)
    r = r.sort_values(["team", "season", "game_date"])
    grp = r.groupby(["team", "season"])
    r["pn"], r["poss_sum"] = grp.cumcount() + 1, grp["poss"].cumsum()
    x = _asof(targets, r, ["team", "season"], ["pn", "poss_sum"])
    lg = r.groupby(["season", "game_date"], as_index=False).agg(lg_sum=("poss", "sum"),
                                                                 lg_n=("poss", "size"))
    lg = lg.sort_values(["season", "game_date"])
    lg["lg_sum"], lg["lg_n"] = lg.groupby("season")["lg_sum"].cumsum(), lg.groupby("season")["lg_n"].cumsum()
    y = _asof(targets, lg, ["season"], ["lg_sum", "lg_n"])
    pn = x["pn"].fillna(0).to_numpy(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return pd.DataFrame({"pn": pn, "pace": x["poss_sum"].to_numpy(float) / pn,
                             "lg_pace": y["lg_sum"].to_numpy(float) / y["lg_n"].to_numpy(float)})


# ── the per-game inputs and the rule ────────────────────────────────────────

RECORD_COLS = tuple(f"{h}_{m}{n}" for h in ("h", "a") for m in ("ats", "ou") for n in (5, 10))
AVG_COLS = ("h_n", "h_pf", "h_pa", "a_n", "a_pf", "a_pa", "h_pn", "h_pace", "a_pn", "a_pace", "lg_pace")
INPUT_COLS = RECORD_COLS + AVG_COLS


def game_inputs(games: pd.DataFrame, tg: pd.DataFrame, tb: pd.DataFrame) -> pd.DataFrame:
    """One row per game in `games`: both teams' venue records (h_ = the home
    team's home games, a_ = the away team's road games), season-to-date
    averages and pace, all from before the game's date."""
    g = games[["game_id", "season", "game_date", "home_team", "away_team"]].reset_index(drop=True)
    g["season"] = g["season"].astype(int)
    out = g[["game_id", "season", "game_date"]].copy()
    for pre, team_col, venue in (("h", "home_team", "home"), ("a", "away_team", "away")):
        t = g[["season", "game_date"]].assign(team=g[team_col].to_numpy(), venue=venue)
        for m in ("ats", "ou"):
            for n in (5, 10):
                out[f"{pre}_{m}{n}"] = last_n(tg, t, m, n)
        # positional (.to_numpy()): the helpers return a fresh index
        av = season_averages(tg, t)
        for c in ("n", "pf", "pa"):
            out[f"{pre}_{c}"] = av[c].to_numpy(float)
        pc = pace_inputs(tb, t)
        out[f"{pre}_pn"], out[f"{pre}_pace"] = pc["pn"].to_numpy(float), pc["pace"].to_numpy(float)
        if pre == "h":
            out["lg_pace"] = pc["lg_pace"].to_numpy(float)
    return out.reset_index(drop=True)


def _pick_k(h, a):
    """(pick, k) for a pair of venue nets: the hot side and min(hot, -cold)."""
    h, a = np.asarray(h, float), np.asarray(a, float)
    home_hot, away_hot = h > a, a > h                     # NaN compares False: no pick
    pick = np.where(home_hot, "home", np.where(away_hot, "away", None)).astype(object)
    hot = np.where(home_hot, h, np.where(away_hot, a, np.nan))
    cold = np.where(home_hot, a, np.where(away_hot, h, np.nan))
    return pick, np.minimum(hot, -cold)


def step_k(h5, a5, h10, a10):
    """mike's "bump it out to L10": a last-5 hot team at net >= 3 against an
    opponent at net -1 or -2; the last-5 hot team is bet, and k is
    min(its last-10 net, -the opponent's last-10 net)."""
    h5, a5, h10, a10 = (np.asarray(x, float) for x in (h5, a5, h10, a10))
    home = (h5 >= STEP_HOT_MIN) & np.isin(a5, STEP_COLD)
    away = (a5 >= STEP_HOT_MIN) & np.isin(h5, STEP_COLD)
    pick = np.where(home, "home", np.where(away, "away", None)).astype(object)
    k = np.where(home, np.minimum(h10, -a10), np.where(away, np.minimum(a10, -h10), np.nan))
    return pick, k


def signals(inp: pd.DataFrame, numbers: pd.DataFrame) -> pd.DataFrame:
    """Per game, every registered rule's number from the inputs and the game's
    own first-quarter numbers: pick_<w> / k_<w> / chk_<w> for the spread
    (w = L5, L10, L5to10), kover_<w> / kunder_<w> for the total (L5, L10), and
    the total checks scoring_over/_under, pace_over/_under."""
    w = numbers.pivot_table(index="game_id", columns="market", values="number", aggfunc="first")
    w = w.reindex(columns=[SPREAD, TOTAL]).reset_index()
    x = inp.merge(w, on="game_id", how="left")
    out = x[["game_id", "season", "game_date"]].copy()
    spread, total = x[SPREAD].to_numpy(float), x[TOTAL].to_numpy(float)
    have_avg = (x["h_n"] >= MIN_AVG_GAMES) & (x["a_n"] >= MIN_AVG_GAMES)
    proj_home = (((x["h_pf"] + x["a_pa"]) - (x["a_pf"] + x["h_pa"])) / 2.0).to_numpy(float)
    rules = {w_: _pick_k(x[f"h_ats{n}"], x[f"a_ats{n}"]) for w_, (n, _, _) in WINDOWS.items()}
    rules[STEP] = step_k(x["h_ats5"], x["a_ats5"], x["h_ats10"], x["a_ats10"])
    for w_, (pick, k) in rules.items():
        home = pick == "home"
        hot_number = np.where(home, spread, -spread)       # the hot team's own number
        proj_hot = np.where(home, proj_home, -proj_home)
        out[f"pick_{w_}"], out[f"k_{w_}"] = pick, k
        out[f"chk_{w_}"] = (have_avg.to_numpy() & (pick != None) & np.isfinite(spread)  # noqa: E711
                            & (proj_hot + hot_number > 0))
    for w_, (n, _, _) in WINDOWS.items():
        ho, ao = x[f"h_ou{n}"].to_numpy(float), x[f"a_ou{n}"].to_numpy(float)
        out[f"kover_{w_}"], out[f"kunder_{w_}"] = np.minimum(ho, ao), np.minimum(-ho, -ao)
    proj_total = ((x["h_pf"] + x["a_pa"]) / 2.0 + (x["a_pf"] + x["h_pa"]) / 2.0).to_numpy(float)
    ok_t = have_avg.to_numpy() & np.isfinite(total)
    out["scoring_over"] = ok_t & (proj_total > total)
    out["scoring_under"] = ok_t & (proj_total < total)
    have_pace = ((x["h_pn"] >= MIN_AVG_GAMES) & (x["a_pn"] >= MIN_AVG_GAMES)
                 & x["lg_pace"].notna()).to_numpy()
    pace = ((x["h_pace"] + x["a_pace"]) / 2.0).to_numpy(float)
    lg = x["lg_pace"].to_numpy(float)
    out["pace_over"] = have_pace & (pace > lg)
    out["pace_under"] = have_pace & (pace < lg)
    return out


def total_check(sig: pd.DataFrame, check: str, side: str) -> np.ndarray:
    """Games passing a total check on the side bet (over / under)."""
    sc, pc = sig[f"scoring_{side}"].to_numpy(bool), sig[f"pace_{side}"].to_numpy(bool)
    return {"none": np.ones(len(sig), bool), "scoring": sc, "pace": pc, "both": sc & pc}[check]


# ── candidate offers ────────────────────────────────────────────────────────

def spread_cand(neutral_s: pd.DataFrame, sig: pd.DataFrame, window: str, check: str,
                fade: bool = False) -> pd.DataFrame:
    """Market-fair first-quarter spread offers carrying the rule's k as
    `strength` and the hot (or, fading, the cold) team's REAL side as
    side_pick, on games with a pick (and, under the check, passing it). Both
    sides of a game carry the same strength and side_pick (F6c's shape)."""
    pick = sig[f"pick_{window}"].to_numpy(object)
    if fade:
        pick = np.where(pick == "home", "away", np.where(pick == "away", "home", None)).astype(object)
    keep = (pick != None) & np.isfinite(sig[f"k_{window}"].to_numpy(float))  # noqa: E711
    if check == "spread":
        keep &= sig[f"chk_{window}"].to_numpy(bool)
    s = pd.DataFrame({"game_id": sig["game_id"].to_numpy()[keep], "market": SPREAD,
                      "strength": sig[f"k_{window}"].to_numpy(float)[keep], "side_pick": pick[keep]})
    base = neutral_s.drop(columns=[c for c in ("strength", "side_pick") if c in neutral_s])
    return base.merge(s, on=["game_id", "market"], how="inner")


def total_cand(neutral_t: pd.DataFrame, sig: pd.DataFrame, window: str, check: str) -> pd.DataFrame:
    """Market-fair first-quarter total offers, each REAL side carrying its own
    k (over: kover, under: kunder), on games passing that side's check."""
    parts = []
    for side in ("over", "under"):
        k = sig[f"k{side}_{window}"].to_numpy(float)
        keep = np.isfinite(k) & total_check(sig, check, side)
        parts.append(pd.DataFrame({"game_id": sig["game_id"].to_numpy()[keep], "market": TOTAL,
                                   "side": side, "strength": k[keep]}))
    s = pd.concat(parts, ignore_index=True)
    base = neutral_t.drop(columns=[c for c in ("strength", "side_pick") if c in neutral_t])
    return base.merge(s, on=["game_id", "market", "side"], how="inner")


def total_fade_cand(neutral_t: pd.DataFrame, sig: pd.DataFrame, window: str, label: str) -> pd.DataFrame:
    """The control: on games where the over (fade_over) or under (fade_under)
    rule fires, the OTHER side, as a per-game side carrying that rule's k."""
    trig = "over" if label == "fade_over" else "under"
    k = sig[f"k{trig}_{window}"].to_numpy(float)
    keep = np.isfinite(k)
    s = pd.DataFrame({"game_id": sig["game_id"].to_numpy()[keep], "market": TOTAL,
                      "strength": k[keep], "side_pick": FADE_SIDES[label]})
    base = neutral_t.drop(columns=[c for c in ("strength", "side_pick") if c in neutral_t])
    return base.merge(s, on=["game_id", "market"], how="inner")


# ── placebo ─────────────────────────────────────────────────────────────────

def shuffle_inputs(inp: pd.DataFrame, rng) -> pd.DataFrame:
    """Every game's trend inputs (INPUT_COLS, together) moved to another game
    on the same date by one permutation per date; game_id, season and date
    stay, so each game keeps its own number when the rule is recomputed."""
    out = inp.copy()
    cols = [c for c in INPUT_COLS if c in inp]
    vals = inp[cols].to_numpy(float)
    new = vals.copy()
    for idx in inp.groupby("game_date", sort=False).indices.values():
        new[idx] = vals[idx][rng.permutation(len(idx))]
    out[cols] = new
    return out


def placebo_signals(inp: pd.DataFrame, numbers: pd.DataFrame, seeds=PLACEBO_SEEDS) -> list[pd.DataFrame]:
    return [signals(shuffle_inputs(inp, np.random.default_rng(s)), numbers) for s in seeds]


# ── cells ───────────────────────────────────────────────────────────────────

def emit(dd: H.Data, family: str, market: str, sides, cuts, floor: float, cand: pd.DataFrame,
         neutral: pd.DataFrame, placebo, choose, times, extra: dict) -> list[dict]:
    """One group's cells through H.run_cells, each row with its bands."""
    rows = H.run_cells(dd, family, POINT, cand, neutral, list(cuts), {market: list(sides)},
                       placebo=placebo, strength="strength", choose_seasons=choose, times=times)
    for r in rows:
        bounds = G5.band_bounds(cuts, r["cut_index"], lowest=floor)
        pool = tuple(int(s) for s in str(r["pool_seasons"]).split(",") if s)
        r.update(G5.band_columns(cand, r["side"], "strength", bounds, dd.games, pool))
        r.update(extra)
    return rows


def all_cells(dd: H.Data, times, neutral: pd.DataFrame, sig: pd.DataFrame, plc: list | None,
              choose) -> tuple[list[dict], list[dict], dict]:
    """(the 64 registered rows, the control rows, candidate frames by cell
    group). `plc`: placebo signal frames (None: no placebo, the smoke run)."""
    ns, nt = neutral[neutral["market"] == SPREAD], neutral[neutral["market"] == TOTAL]
    lazy = (lambda build: G5.LazyFrames(plc, build) if plc else None)
    rows, ctl, cands = [], [], {}
    spread_groups = [(w_, n_c[1], n_c[2]) for w_, n_c in WINDOWS.items()] + [(STEP, STEP_CUTS, STEP_FLOOR)]
    for window, cuts, floor in spread_groups:
        for check in SPREAD_CHECKS:
            cand = spread_cand(ns, sig, window, check)
            cands[(FAMILY_A, window, check)] = cand
            rows += emit(dd, FAMILY_A, SPREAD, [SIDE_HOT], cuts, floor, cand, cand,
                         lazy(lambda s, w=window, c=check: spread_cand(ns, s, w, c)), choose, times,
                         {"axis_window": window, "axis_check": check,
                          "signal_meaning": "the hot team's first-quarter spread on venue cover records"})
        fade = spread_cand(ns, sig, window, "none", fade=True)
        ctl += emit(dd, CONTROL_A, SPREAD, [SIDE_COLD], cuts, floor, fade, fade, None, choose, times,
                    {"axis_window": window, "axis_check": "none",
                     "signal_meaning": "control: the cold team"})
    for window, (_, cuts, floor) in WINDOWS.items():
        for check in TOTAL_CHECKS:
            cand = total_cand(nt, sig, window, check)
            cands[(FAMILY_T, window, check)] = cand
            rows += emit(dd, FAMILY_T, TOTAL, ["over", "under"], cuts, floor, cand, nt,
                         lazy(lambda s, w=window, c=check: total_cand(nt, s, w, c)), choose, times,
                         {"axis_window": window, "axis_check": check,
                          "signal_meaning": "first-quarter total on both teams' venue over/under records"})
        for label in FADE_SIDES:
            fade = total_fade_cand(nt, sig, window, label)
            ctl += emit(dd, CONTROL_T, TOTAL, [label], cuts, floor, fade, fade, None, choose, times,
                        {"axis_window": window, "axis_check": "none",
                         "signal_meaning": "control: the other total side"})
    assert len(rows) == EXPECTED_CELLS, len(rows)
    return rows, ctl, cands


# ── synthetic checks (each watched failing when its rule is broken) ─────────

def synthetic_checks() -> dict:
    """Arithmetic the cells depend on, on hand-built games. Raises on a fault."""
    # rounding: a quarter rounds up; the home number keeps its sign
    assert np.allclose(half_round([-1.25, 1.25, -0.5, 2.74]), [-1.0, 1.5, -0.5, 2.5])
    # one team, alternating venues, five home games then a sixth on the target date
    d = pd.to_datetime("2024-01-01") + pd.to_timedelta(np.arange(12), unit="D")
    tg = pd.DataFrame({"game_id": [f"g{i}" for i in range(12)], "season": 2024,
                       "game_date": d.strftime("%Y-%m-%d"), "tip": d, "team": "AAA",
                       "venue": ["home", "away"] * 6,
                       "ats": [1, -1, 1, -1, -1, -1, 1, -1, 1, -1, 0, 1],
                       "ou": 1.0, "pf": 30.0, "pa": 25.0})
    tgt = pd.DataFrame({"season": [2024, 2024, 2024], "team": "AAA",
                        "venue": ["home", "home", "away"],
                        "game_date": ["2024-01-11", "2024-01-09", "2024-01-12"]})
    # home games before 01-11: g0 g2 g4 g6 g8 -> +1 +1 -1 +1 +1 = 3; the target's own day excluded
    # home games before 01-09: only four (g0 g2 g4 g6) -> no record
    # away games before 01-12: g1 g3 g5 g7 g9 -> -5 (g11 is on the target date, excluded)
    got = last_n(tg, tgt, "ats", 5)
    assert got[0] == 3.0 and np.isnan(got[1]) and got[2] == -5.0, got
    av = season_averages(tg, tgt.assign(venue="home"))
    assert av["n"].tolist() == [10.0, 8.0, 11.0] and np.allclose(av["pf"], 30.0), av
    # the hot side and k
    pick, k = _pick_k([3, -3, 1, 5, np.nan], [-3, 5, 1, -1, -5])
    assert list(pick) == ["home", "away", None, "home", None], pick
    assert np.allclose(k[[0, 1, 3]], [3.0, 3.0, 1.0]) and np.isnan(k[2]) and np.isnan(k[4]), k
    # the step: L5 hot >= 3 against -1/-2 only, k from the last 10 of the same two teams
    sp, sk = step_k([3, -1, 3, 5], [-1, 4, -3, -2], [4, -2, 6, 2], [-2, 6, -6, 0])
    assert list(sp) == ["home", "away", None, "home"] and np.allclose(sk[[0, 1, 3]], [2.0, 2.0, 0.0])
    # the spread check, each side: home hot at -1.5 projected +2 covers; away hot at
    # +1.5 projected -1 for home (+1 for away) covers; home hot at -2.5 projected +2 does not
    inp = pd.DataFrame({"game_id": ["x", "y", "z"], "season": 2024, "game_date": "2024-02-01",
                        "h_ats5": [3, -3, 3], "a_ats5": [-3, 3, -3], "h_ats10": np.nan, "a_ats10": np.nan,
                        "h_ou5": [3, -3, 1], "a_ou5": [5, -1, -1], "h_ou10": np.nan, "a_ou10": np.nan,
                        "h_n": 10, "a_n": 10, "h_pf": [31, 28, 31], "h_pa": [27, 28, 27],
                        "a_pf": [27, 28, 27], "a_pa": [31, 30, 31],
                        "h_pn": 10, "a_pn": 10, "h_pace": [100, 96, 100], "a_pace": [102, 96, 98],
                        "lg_pace": 99.0})
    nums = pd.DataFrame({"game_id": ["x", "x", "y", "y", "z", "z"],
                         "market": [SPREAD, TOTAL] * 3, "number": [-1.5, 57.5, -1.5, 57.5, -4.5, 57.5]})
    s = signals(inp, nums)
    # x: proj home margin ((31+31)-(27+27))/2 = 4 -> covers -1.5. y: proj ((28+30)-(28+28))/2 = 1,
    # away hot at +1.5 projects -1 -> -1 + 1.5 > 0 covers. z: 4 - 4.5 < 0 fails.
    assert s["pick_L5"].tolist() == ["home", "away", "home"] and s["chk_L5"].tolist() == [True, True, False], s
    # totals: x over k = min(3, 5) = 3, under k = -5; projected (31+31)/2 + (27+27)/2 = 58 > 57.5
    assert s.loc[0, "kover_L5"] == 3.0 and s.loc[0, "kunder_L5"] == -5.0 and bool(s.loc[0, "scoring_over"])
    assert bool(s.loc[0, "pace_over"]) and bool(s.loc[1, "pace_under"]) and not s.loc[2, "pace_over"]
    # the placebo moves inputs within a date only, and keeps each game's number
    many = pd.concat([inp.assign(game_id=lambda f, i=i: f["game_id"] + str(i),
                                 game_date=f"2024-02-0{1 + i % 2}") for i in range(4)], ignore_index=True)
    sh = shuffle_inputs(many, np.random.default_rng(1))
    for dte, grp in many.groupby("game_date"):
        a = sorted(map(tuple, grp[list(RECORD_COLS)].fillna(-99).to_numpy()))
        b = sorted(map(tuple, sh.loc[grp.index, list(RECORD_COLS)].fillna(-99).to_numpy()))
        assert a == b, "a shuffled input left its date"
    assert (sh["game_id"] == many["game_id"]).all()
    return {"synthetic_checks": "pass"}


# ── real data ───────────────────────────────────────────────────────────────

def prepare(cache: Path, require: bool) -> dict:
    """Every frame the cells read, on the real cache (no grade)."""
    real = G5.load_real(cache, require)
    data, games_p, pe, graded = real["data"], real["games_p"], real["pe"], real["graded"]
    if tuple(graded) != GRADED:
        raise RuntimeError(f"derivative seasons {graded}, section 12 grades exactly {GRADED}")
    close = H.pinnacle_close(data)
    times = H.per_event_times(pe, POINT)
    vis = NB.visible_numbers(pe, times)
    gp_full = games_p[games_p["season"].isin(data.games["season"])]
    pricing = P3.market_pricing(close, gp_full, graded)
    P3.require_pricing(pricing, graded, (SPREAD, TOTAL), "the market's own pricing")
    neutral = P3.neutral_offers(vis[vis["market"].isin([SPREAD, TOTAL])], pricing)
    numbers = game_numbers(vis)
    gp = games_p[games_p["season"].isin(graded)]
    tg = team_games(gp, numbers)
    tb = real["tb"][real["tb"]["season"].astype(int).isin(graded)]
    dd = P3.derivative_data(gp, pe)
    decided = gp[gp["game_id"].isin(set(times["game_id"]))]
    inp = game_inputs(decided, tg, tb)
    sig = signals(inp, numbers)
    return {"dd": dd, "times": times, "vis": vis, "neutral": neutral, "numbers": numbers,
            "tg": tg, "inp": inp, "sig": sig, "graded": tuple(graded)}


def counts(prep: dict) -> dict:
    """Games per season with each record, and the games each cell would bet
    with a deciding offer at or above the floor (counted, never graded)."""
    sig, neutral = prep["sig"], prep["neutral"]
    season = prep["dd"].games.drop_duplicates("game_id").set_index("game_id")["season"].astype(int)
    inp = prep["inp"]
    rec = {c: inp.groupby("season")[c].apply(lambda s: int(s.notna().sum())).to_dict() for c in RECORD_COLS}
    ns, nt = neutral[neutral["market"] == SPREAD], neutral[neutral["market"] == TOTAL]
    out = []
    groups = [(FAMILY_A, w_, c, cuts) for w_, (_, cuts, _) in WINDOWS.items() for c in SPREAD_CHECKS]
    groups += [(FAMILY_A, STEP, c, STEP_CUTS) for c in SPREAD_CHECKS]
    groups += [(FAMILY_T, w_, c, cuts) for w_, (_, cuts, _) in WINDOWS.items() for c in TOTAL_CHECKS]
    for fam, window, check, cuts in groups:
        if fam == FAMILY_A:
            cand, sides = spread_cand(ns, sig, window, check), [SIDE_HOT]
        else:
            cand, sides = total_cand(nt, sig, window, check), ["over", "under"]
        for side in sides:
            for cut in cuts:
                b = H.choose(cand[cand["strength"] >= cut], -np.inf, sides=[side])
                by = season.reindex(b["game_id"]).value_counts().to_dict()
                out.append({"family": fam, "window": window, "check": check, "side": side, "cut": cut,
                            **{f"bets_{s}": int(by.get(s, 0)) for s in GRADED},
                            "bets_pooled": int(len(b))})
    return {"games_with_a_decision": season.reindex(prep["times"]["game_id"]).value_counts().sort_index().to_dict(),
            "games_with_a_record": rec, "cells": out}


def refuse_full(cache: Path) -> list[str]:
    why = []
    if os.environ.get(GO_ENV) != "1":
        why.append(f"{GO_ENV}=1 is not set: the owner runs --full")
    if not os.environ.get(RESULTS_ENV):
        why.append(f"{RESULTS_ENV} is not set: name the eighth search's results folder")
    if not os.environ.get(BETS_ENV):
        why.append(f"{BETS_ENV} is not set: a passing cell's figures read its bets")
    if not (Path(cache) / P.LEDGER_FILE).exists():
        why.append(f"{Path(cache) / P.LEDGER_FILE} does not exist: refresh the cache")
    return why


def smoke(cache: Path = H.CACHE) -> dict:
    print(json.dumps(synthetic_checks()))
    prep = prepare(cache, require=False)
    c = counts(prep)
    print(json.dumps({k: v for k, v in c.items() if k != "cells"}, indent=1, default=str))
    print(pd.DataFrame(c["cells"]).to_string(index=False))
    return c


def full(cache: Path = H.CACHE, out: Path | None = None) -> None:
    why = refuse_full(cache)
    if why:
        P.refuse(why)
    out = Path(os.environ[RESULTS_ENV]) if out is None else out
    synthetic_checks()
    try:
        prep = prepare(cache, require=True)
    except RuntimeError as e:
        P.refuse([str(e)])
    choose = P3.choosing(prep["graded"])
    print("graded", prep["graded"], "choosing", choose)
    plc = placebo_signals(prep["inp"], prep["numbers"])
    rows, ctl, cands = all_cells(prep["dd"], prep["times"], prep["neutral"], prep["sig"], plc, choose)
    off = H.offers(prep["vis"])
    pops = []
    for (fam, window, check), cand in cands.items():
        grp = [r for r in rows if r["family"] == fam and r["axis_window"] == window and r["axis_check"] == check]
        pops.append(P3.population(fam, grp, prep["dd"], prep["times"], off, cand, "strength", prep["graded"])
                    .assign(axis_window=window, axis_check=check))
    out.mkdir(parents=True, exist_ok=True)
    L.write_cells([r for r in rows if r["family"] == FAMILY_A], out / f"cells_{FAMILY_A}.parquet")
    L.write_cells([r for r in rows if r["family"] == FAMILY_T], out / f"cells_{FAMILY_T}.parquet")
    L.write_cells([r for r in ctl if r["family"] == CONTROL_A], out / f"cells_{CONTROL_A}.parquet")
    L.write_cells([r for r in ctl if r["family"] == CONTROL_T], out / f"cells_{CONTROL_T}.parquet")
    pd.concat(pops, ignore_index=True).to_parquet(out / "population_Q1.parquet")
    prep["inp"].to_parquet(out / "inputs_Q1.parquet")
    prep["sig"].to_parquet(out / "signals_Q1.parquet")
    prep["numbers"].to_parquet(out / "numbers_Q1.parquet")
    print(f"cells written to {out}: {len(rows)} registered, {len(ctl)} controls")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true", help="synthetic checks, then real counts only")
    g.add_argument("--full", action="store_true", help=f"every graded season (needs {GO_ENV}=1)")
    a = ap.parse_args(argv)
    if a.full:
        full(H.CACHE)
    else:
        smoke(H.CACHE)


if __name__ == "__main__":
    main()
