"""NBA search: the popular-team tax.

docs/nba_search_popular.md registers the cells and fixes every choice, written
and committed BEFORE any bet in this search was graded (2026-10-30). This lab
EMITS cells through the shared harness (scripts/nba_game_harness, H); the
pass/fail script judges them (scripts/nba_game2_verdict.py --house5, the bars of
docs/nba_models_2026.md 9.1). No cut, constant or rule below was chosen from a
betting result.

9 cells (asserted), decided at the newest fetch 60-180 minutes before tip
(decision point C), 2021-22 .. 2025-26 pooled, 2020-21 reported:

  TICKETS   nba_public_splits closing rows: archive_undated, endpoint v1,
            quality IS NULL. One number per side, known only after that game
            starts, so it is read for LATER games and never for its own.
  POPULARITY  the unweighted mean of a team's spread ticket share over its
            earlier games this season, dates strictly before today, at least 10
            such games. The gap is home minus away.
  POP       full-game spread and moneyline, AGAINST the more popular team (a
            per-game side, side_pick). Gap >= 5 / 10 / 15. A gap of 0 is no bet.
  OVER HABIT  the same mean of the game's over ticket share, minus the league's
            mean over the same season's earlier dates. The total's strength is
            the SMALLER of the two teams' habits.
  POPT      full-game total, UNDER. Smaller habit >= 1 / 2 / 3.
  PRICE     the side's best deciding offer at that book's own number under the
            market's fair line (H.market_fair), -200 floor.
  IMPOSSIBLE  a full-game total 40 or more points from the median of its game's
            stored totals is not a full-game total and is removed before any
            quote is placed (the sixth search's rule, IMPOSSIBLE_GAP).
  SWAPPED   a deciding book's spread 5 or more points from the median of the
            deciding books' spreads at the same fetch (3 or more books) has home
            and away swapped. That book's spread and moneyline at that fetch are
            not offers, at C and D, before the fair line is read (SWAPPED_GAP).
  BANDS     along the cut: [0, 5) [5, 10) [10, 15) 15+; [0, 1) [1, 2) [2, 3) 3+.
  PLACEBO   200 runs, seeds 1-200: every numbered game's four inputs (both
            teams' popularity and over share) moved together to ANOTHER numbered
            game on the same date, one permutation per date with no game left on
            its own inputs; each game keeps its own prices and the rule is
            recomputed. It shuffles over every game with a number, never over the
            games past a cut.
  CONTROLS  never judged: with the popular team; the underdog on the games the
            cell can bet (the credit line, --credit; a level market has no
            underdog and stays in the cell only); the over in the same games; the
            same cells at decision point D, the same fetch on 99.8% of games.
  REPORTS   never judged, written by --full: national television; POPT on each
            side of the 2024-25 change in the total tickets; the sweep's Step 1.

    PYTHONPATH=. python -m scripts.nba_s_popular --smoke
    NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> NBA_GAME2_BETS=<folder>/bets \\
        PYTHONPATH=. python -m scripts.nba_s_popular --full
    PYTHONPATH=. python -m scripts.nba_game2_verdict --results <folder> --house5
    PYTHONPATH=. python -m scripts.nba_s_popular --credit --results <folder>

--smoke runs the synthetic checks, then prints on the real cache only counts,
extremes of every number the search reads, the share of placebo bets that differ
from the real bets, and the timing. It never grades a real bet: the timing runs
the grade against made-up scores (dummy_games) and throws the answer away.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import nba_game2_luck as L  # noqa: E402
from scripts import nba_game2_projection as P  # noqa: E402
from scripts import nba_game5 as G5  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402

GO_ENV, RESULTS_ENV, BETS_ENV = G5.GO_ENV, G5.RESULTS_ENV, G5.BETS_ENV
FAMILY_POP, FAMILY_TOT = "POP", "POPT"
CONTROL_WITH, CONTROL_DOG, CONTROL_OVER = "control_POP_with", "control_POP_dog", "control_POPT_over"
CONTROL_POP_D, CONTROL_TOT_D = "control_POP_at_D", "control_POPT_at_D"
POINT, DIAG_POINT = "C", "D"
POP_MARKETS, TOTAL = ("spreads", "h2h"), "totals"
GAP_CUTS, HABIT_CUTS = (5.0, 10.0, 15.0), (1.0, 2.0, 3.0)
MIN_GAMES = 10
IMPOSSIBLE_GAP = 40.0
SWAPPED_GAP, SWAPPED_MIN_BOOKS = 5.0, 3
SIDE_AGAINST, SIDE_WITH, SIDE_DOG = "against_popular", "with_popular", "underdog"
SEASONS = (H.REGIME, *H.CHOOSE, H.CONFIRM)     # 2020-21 reported, 2021-22 .. 2025-26 pooled
EXPECTED_CELLS = 9
N_PLACEBO = 200
PLACEBO_SEEDS = tuple(range(1, N_PLACEBO + 1))
INPUT_COLS = ("h_pop", "a_pop", "h_over", "a_over")
TV_SEASONS = (2021, 2026)                       # the only seasons with national_tv filled
TV_NATIONAL, TV_NBA_TV, TV_NONE = "national_broadcast", "nba_tv_only", "none"
TOTAL_REGIMES = {"2021-22 to 2023-24": (2022, 2023, 2024), "2024-25 to 2025-26": (2025, 2026)}
THIN = 200                                      # bar 1: under this, "too few games to tell"
SPLIT_COLS = ["game_id", "market", "side", "tickets_pct", "endpoint", "capture_kind", "quality"]


# ── ticket rows ─────────────────────────────────────────────────────────────

def clean_splits(splits: pd.DataFrame) -> pd.DataFrame:
    """The closing rows this search reads: archive_undated, endpoint v1, quality
    IS NULL, a matched game, and a ticket share strictly between 0 and 100."""
    keep = (splits["capture_kind"].eq("archive_undated") & splits["endpoint"].eq("v1")
            & splits["quality"].isna() & splits["game_id"].notna()
            & splits["tickets_pct"].gt(0) & splits["tickets_pct"].lt(100))
    return splits.loc[keep, ["game_id", "market", "side", "tickets_pct"]].reset_index(drop=True)


def share_rows(g: pd.DataFrame, clean: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(one row per (game, team) with its spread ticket share and the game's
    over share; one row per game with its over share). `g` has a fresh index."""
    def side(market, name):
        x = clean[(clean["market"] == market) & (clean["side"] == name)]
        return x.drop_duplicates("game_id").set_index("game_id")["tickets_pct"]
    home, away, over = (g["game_id"].map(side(m, s)).to_numpy(float)
                        for m, s in (("spreads", "home"), ("spreads", "away"), (TOTAL, "over")))
    base = g[["game_id", "season", "game_date"]]
    rows = pd.concat([base.assign(team=g["home_team"].to_numpy(), share=home, over=over),
                      base.assign(team=g["away_team"].to_numpy(), share=away, over=over)],
                     ignore_index=True)
    return rows, base.assign(over=over)


def _asof(targets: pd.DataFrame, rows: pd.DataFrame, by: list[str], cols: list[str]) -> pd.DataFrame:
    """For each target the last `rows` row with game_date STRICTLY before the
    target's date (same `by` keys); targets keep their order. Built once per
    call on a merge, never a per-key lookup."""
    t = targets.assign(_d=pd.to_datetime(targets["game_date"]), _i=np.arange(len(targets)))
    r = rows.assign(_d=pd.to_datetime(rows["game_date"]))[["_d", *by, *cols]]
    out = pd.merge_asof(t.sort_values("_d"), r.sort_values("_d"), on="_d", by=by,
                        allow_exact_matches=False)
    return out.sort_values("_i").reset_index(drop=True)[cols]


def to_date(rows: pd.DataFrame, col: str, targets: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """(games counted, mean of `col`) for each target (team, season, game_date):
    this season's games on dates strictly before the target's. The mean is NaN
    under MIN_GAMES. Positional arrays: `targets` may carry any index."""
    r = rows[rows[col].notna()].sort_values(["team", "season", "game_date"]).copy()
    grp = r.groupby(["team", "season"])
    r["_n"], r["_s"] = grp.cumcount() + 1, grp[col].cumsum()
    x = _asof(targets, r, ["team", "season"], ["_n", "_s"])
    n = x["_n"].fillna(0).to_numpy(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = x["_s"].to_numpy(float) / n
    return n, np.where(n >= MIN_GAMES, mean, np.nan)


def league_to_date(by_game: pd.DataFrame, targets: pd.DataFrame) -> np.ndarray:
    """The league's mean over share, each game once, over the same season's
    dates strictly before each target's date."""
    d = by_game[by_game["over"].notna()].groupby(["season", "game_date"], as_index=False).agg(
        _s=("over", "sum"), _n=("over", "size")).sort_values(["season", "game_date"])
    d["_s"], d["_n"] = d.groupby("season")["_s"].cumsum(), d.groupby("season")["_n"].cumsum()
    x = _asof(targets, d, ["season"], ["_s", "_n"])
    return x["_s"].to_numpy(float) / x["_n"].to_numpy(float)


def game_inputs(games: pd.DataFrame, clean: pd.DataFrame) -> pd.DataFrame:
    """One row per game, in `games` order: both teams' popularity (h_pop, a_pop)
    and over share (h_over, a_over) with their counts, and the league's over
    share (lg_over), all from dates strictly before the game's."""
    g = games[["game_id", "season", "game_date", "home_team", "away_team"]].reset_index(drop=True)
    g["season"] = g["season"].astype(int)
    rows, by_game = share_rows(g, clean)
    out = g[["game_id", "season", "game_date"]].copy()
    for pre, col in (("h", "home_team"), ("a", "away_team")):
        t = g[["season", "game_date"]].assign(team=g[col].to_numpy())
        out[f"{pre}_n"], out[f"{pre}_pop"] = to_date(rows, "share", t)
        out[f"{pre}_on"], out[f"{pre}_over"] = to_date(rows, "over", t)
    out["lg_over"] = league_to_date(by_game, g[["season", "game_date"]])
    return out


def signals(inp: pd.DataFrame) -> pd.DataFrame:
    """Per game: gap (home minus away popularity), gap_size, side_against (the
    real side against the more popular team; None on a tie or no number),
    side_with, and habit (the smaller of the two teams' over habits)."""
    gap = inp["h_pop"].to_numpy(float) - inp["a_pop"].to_numpy(float)
    lg = inp["lg_over"].to_numpy(float)
    habit = np.minimum(inp["h_over"].to_numpy(float) - lg, inp["a_over"].to_numpy(float) - lg)
    return pd.DataFrame({
        "game_id": inp["game_id"].to_numpy(), "season": inp["season"].to_numpy(),
        "game_date": inp["game_date"].to_numpy(), "gap": gap, "gap_size": np.abs(gap),
        "side_against": np.where(gap > 0, "away", np.where(gap < 0, "home", None)).astype(object),
        "side_with": np.where(gap > 0, "home", np.where(gap < 0, "away", None)).astype(object),
        "habit": habit})


# ── impossible numbers ──────────────────────────────────────────────────────

def impossible_totals(quotes: pd.DataFrame) -> np.ndarray:
    """True on a full-game total IMPOSSIBLE_GAP or more points from the median of
    its game's stored totals."""
    out = np.zeros(len(quotes), bool)
    tot = quotes["market"].eq(TOTAL).to_numpy()
    if tot.any():
        med = quotes.loc[tot].groupby("game_id")["line"].transform("median").to_numpy(float)
        out[tot] = np.abs(quotes["line"].to_numpy(float)[tot] - med) >= IMPOSSIBLE_GAP
    return out


def drop_impossible(quotes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(the quotes without the impossible rows, those rows)."""
    bad = impossible_totals(quotes)
    return quotes[~bad].reset_index(drop=True), quotes[bad].reset_index(drop=True)


def spread_distances(vis: pd.DataFrame) -> pd.DataFrame:
    """Each deciding book's coherent spread at the decision, with the median of
    the deciding books' spreads on that game, how many quote it, and the distance."""
    sp = vis[vis["market"].eq("spreads") & vis["book"].isin(H.BETTABLE) & vis["coherent"]]
    grp = sp.groupby("game_id")["line"]
    med = grp.transform("median")
    return sp[["game_id", "season", "book", "line", "price_a", "price_b"]].assign(
        median=med, books=grp.transform("size"), distance=(sp["line"] - med).abs())


def drop_swapped(vis: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(what each book shows at the decision without its swapped rows, those rows).
    A swapped row is a book's spread and moneyline on a game where that spread is
    SWAPPED_GAP or more from the deciding books' median; its total stays."""
    d = spread_distances(vis)
    bad = d.loc[(d["distance"] >= SWAPPED_GAP) & (d["books"] >= SWAPPED_MIN_BOOKS), ["game_id", "book"]]
    hit = vis[["game_id", "book"]].merge(bad.assign(_bad=True), on=["game_id", "book"], how="left")["_bad"]
    gone = hit.notna().to_numpy() & vis["market"].isin(POP_MARKETS).to_numpy()
    return vis[~gone].reset_index(drop=True), vis[gone].reset_index(drop=True)


# ── offers and candidate frames ─────────────────────────────────────────────

def point_frames(data: H.Data, point: str, pricing: dict) -> dict:
    """The decision times and the market-fair offers at one point, swapped rows
    out before the fair line is read. The pricing objects are dropped from the
    offers: a bet frame must be storable."""
    times = H.decision_times(data.fetches, data.games, point)
    seen = H.visible(data.quotes, times)
    vis, swapped = drop_swapped(seen)
    fair = H.market_fair(vis, pricing)
    return {"times": times, "neutral": H.fair_offers(H.offers(vis), fair).drop(columns="sigma"),
            "swapped": swapped, "farthest": spread_distances(seen).nlargest(6, "distance")}


def _rule_frame(sig: pd.DataFrame, strength: str, pick) -> pd.DataFrame:
    s = pd.DataFrame({"game_id": sig["game_id"].to_numpy(), "strength": sig[strength].to_numpy(float),
                      "side_pick": pick})
    return s[np.isfinite(s["strength"].to_numpy()) & s["side_pick"].notna().to_numpy()]


def pop_cand(base: pd.DataFrame, sig: pd.DataFrame, pick_col: str = "side_against") -> pd.DataFrame:
    """One market's offers on games with a popularity gap, carrying the gap's
    size as `strength` and the rule's real side as side_pick (both sides of a
    game carry the same two, F6c's shape)."""
    return base.merge(_rule_frame(sig, "gap_size", sig[pick_col].to_numpy(object)), on="game_id")


def dog_cand(base: pd.DataFrame, sig: pd.DataFrame) -> pd.DataFrame:
    """The credit line's control: the market's underdog at T on the games the cell
    can bet, those where the side against the popular team has a deciding offer at
    or above the floor (at any cut: the choice at strength 0 is every gap). A level
    market has no underdog, so the cell bets it and this control does not."""
    same = set(pick(pop_cand(base, sig), 0.0, SIDE_AGAINST)["game_id"])
    fv = H.fav_sides(base)[["game_id", "dog"]]
    x = _rule_frame(sig, "gap_size", sig["side_against"].to_numpy(object)).drop(columns="side_pick")
    x = x[x["game_id"].isin(same)]
    x = x.merge(fv, on="game_id").rename(columns={"dog": "side_pick"})
    return base.merge(x, on="game_id")


def total_cand(base: pd.DataFrame, sig: pd.DataFrame) -> pd.DataFrame:
    """Total offers, both real sides, on games with a habit number."""
    s = pd.DataFrame({"game_id": sig["game_id"].to_numpy(), "strength": sig["habit"].to_numpy(float)})
    return base.merge(s[np.isfinite(s["strength"].to_numpy())], on="game_id")


def best_offers(base: pd.DataFrame) -> pd.DataFrame:
    """Each (game, market, side)'s best deciding offer in H.choose's own order
    (EV, then BEST_LINE_BOOKMAKERS rank), the columns a grade reads. A rule picks
    one real side per game, so choosing from these gives the bets choosing from
    every offer gives, on about a sixth of the rows. Placebo frames only."""
    c = base[base["book"].isin(H.BETTABLE) & (base["price"] >= H.PRICE_FLOOR)]
    c = c.assign(_r=c["book"].map(H.BOOK_RANK).fillna(99))
    c = c.sort_values(["game_id", "market", "side", "ev", "_r"], ascending=[True, True, True, False, True])
    c = c.drop_duplicates(["game_id", "market", "side"])
    return c[["game_id", "season", "game_date", "T", "market", "side", "book", "line", "price",
              "p_win", "p_push", "ev"]].reset_index(drop=True)


def pick(c: pd.DataFrame, cut: float, side: str, books=H.BETTABLE) -> pd.DataFrame:
    """H.run_cells' own choice for a rule family (its pick closure)."""
    return H.choose(c[c["strength"] >= cut], -np.inf, books=books, sides=[side])


# ── placebo ─────────────────────────────────────────────────────────────────

def date_groups(inp: pd.DataFrame) -> dict:
    """date -> positions of the games with any number on that date. Built once."""
    ok = ((inp["h_pop"].notna() & inp["a_pop"].notna()) | (inp["h_over"].notna() & inp["a_over"].notna()))
    dates = inp["game_date"].to_numpy()
    out: dict = {}
    for i in np.flatnonzero(ok.to_numpy()):
        out.setdefault(dates[i], []).append(i)
    return {d: np.asarray(out[d]) for d in sorted(out)}


def no_fixed_points(n: int, rng) -> np.ndarray:
    """A uniform permutation of n with nothing left in its place (rejection, about
    2.7 draws on average). One game alone on its date has nowhere to go."""
    if n < 2:
        return np.arange(n)
    while True:
        p = rng.permutation(n)
        if not (p == np.arange(n)).any():
            return p


def shuffle_inputs(inp: pd.DataFrame, rng, groups: dict | None = None) -> pd.DataFrame:
    """INPUT_COLS moved together to ANOTHER numbered game on the same date, one
    permutation per date (no_fixed_points). A game with no number neither gives
    nor takes. game_id, season, date and the league's mean stay."""
    groups = date_groups(inp) if groups is None else groups
    cols = list(INPUT_COLS)
    vals = inp[cols].to_numpy(float)
    new = vals.copy()
    for idx in groups.values():
        new[idx] = vals[idx][no_fixed_points(len(idx), rng)]
    out = inp.copy()
    out[cols] = new
    return out


def placebo_signals(inp: pd.DataFrame, seeds=PLACEBO_SEEDS) -> list[pd.DataFrame]:
    """One signal frame per seed (small: one row per game, no offers)."""
    groups = date_groups(inp)
    return [signals(shuffle_inputs(inp, np.random.default_rng(s), groups)) for s in seeds]


class _Counted(G5.LazyFrames):
    """G5.LazyFrames with a progress line: run_cells walks it once per cut."""

    def __init__(self, items, build, label: str = "", log: Callable | None = None):
        super().__init__(items, build)
        self.label, self.log, self.walks = label, log, 0

    def __iter__(self):
        for i, x in enumerate(self.items, start=1):
            yield self.build(x)
            if self.log is not None and i % 50 == 0:
                self.log(f"{self.label}: cut {self.walks + 1}, placebo {i}/{len(self.items)}")
        self.walks += 1


# ── cell groups: the one place the cells are listed ─────────────────────────

@dataclass
class Group:
    family: str
    point: str
    market: str
    side: str
    cuts: tuple
    cand: pd.DataFrame
    rebuild: Callable | None         # signal frame -> candidate frame
    meaning: str


def cell_groups(prep: dict, point: str = POINT, family_pop: str = FAMILY_POP,
                family_tot: str = FAMILY_TOT) -> list[Group]:
    neutral, sig = prep["frames"][point]["neutral"], prep["signal"]
    out = []
    for market in POP_MARKETS:
        base = neutral[neutral["market"] == market]
        best = best_offers(base)
        out.append(Group(family_pop, point, market, SIDE_AGAINST, GAP_CUTS, pop_cand(base, sig),
                         lambda s, b=best: pop_cand(b, s),
                         "against the team more popular in its earlier games"))
    base = neutral[neutral["market"] == TOTAL]
    best = best_offers(base)
    out.append(Group(family_tot, point, TOTAL, "under", HABIT_CUTS, total_cand(base, sig),
                     lambda s, b=best: total_cand(b, s),
                     "under when both teams' earlier games drew more over tickets than the league's"))
    return out


def control_groups(prep: dict) -> list[Group]:
    neutral, sig = prep["frames"][POINT]["neutral"], prep["signal"]
    out = []
    for market in POP_MARKETS:
        base = neutral[neutral["market"] == market]
        out.append(Group(CONTROL_WITH, POINT, market, SIDE_WITH, GAP_CUTS, pop_cand(base, sig, "side_with"),
                         None, "control: with the popular team"))
        out.append(Group(CONTROL_DOG, POINT, market, SIDE_DOG, GAP_CUTS, dog_cand(base, sig), None,
                         "control: the market's underdog in the same games"))
    base = neutral[neutral["market"] == TOTAL]
    out.append(Group(CONTROL_OVER, POINT, TOTAL, "over", HABIT_CUTS, total_cand(base, sig), None,
                     "control: the over in the same games"))
    return out + cell_groups(prep, DIAG_POINT, CONTROL_POP_D, CONTROL_TOT_D)


def emit(prep: dict, g: Group, placebo=None) -> list[dict]:
    """One group's cells through H.run_cells, each row with its bands."""
    data = prep["data"]
    rows = H.run_cells(data, g.family, g.point, g.cand, g.cand, list(g.cuts), {g.market: [g.side]},
                       close=prep["close"], sig=prep["pricing"], placebo=placebo, strength="strength",
                       times=prep["frames"][g.point]["times"])
    for r in rows:
        bounds = G5.band_bounds(g.cuts, r["cut_index"], lowest=0.0)
        pool = tuple(int(s) for s in str(r["pool_seasons"]).split(",") if s)
        r.update(G5.band_columns(g.cand, r["side"], "strength", bounds, data.games, pool))
        r["signal_meaning"] = g.meaning
    return rows


def all_cells(prep: dict, plc: list | None, log: Callable | None = None) -> tuple[list[dict], list[dict], dict]:
    """(the 9 registered rows, the control rows, candidate frames by group).
    `plc`: placebo signal frames (None or empty: no placebo)."""
    log = log or (lambda *_: None)
    rows, ctl, cands = [], [], {}
    for g in cell_groups(prep):
        label = f"{g.family} {g.market} {g.point}"
        lazy = _Counted(plc, g.rebuild, label, log) if plc else None
        rows += emit(prep, g, lazy)
        cands[(g.family, g.market, g.side)] = g
        log(f"{label}: done, {len(rows)} of {EXPECTED_CELLS} registered cells")
    for g in control_groups(prep):
        ctl += emit(prep, g)
        log(f"{g.family} {g.market} {g.point}: control done")
    assert len(rows) == EXPECTED_CELLS, len(rows)
    return rows, ctl, cands


# ── reports (graded, so --full only; never a bar) ───────────────────────────

def tv_groups(schedule: pd.DataFrame) -> pd.DataFrame:
    """(game_id, season, tv) on the seasons with the flag filled. National
    broadcast: any listed network other than NBA TV. An empty flag on those
    seasons is no national broadcast."""
    s = schedule[schedule["season"].astype(int).isin(TV_SEASONS)][["game_id", "season", "national_tv"]].copy()

    def group(v):
        if pd.isna(v) or not str(v).strip():
            return TV_NONE
        return TV_NBA_TV if {p.strip() for p in str(v).split(",")} == {"NBA TV"} else TV_NATIONAL
    s["tv"] = s["national_tv"].map(group)
    s["season"] = s["season"].astype(int)
    return s[["game_id", "season", "tv"]].dropna(subset=["game_id"]).reset_index(drop=True)


def _summary(g: pd.DataFrame) -> dict:
    lo, hi = H.ci95(g)
    n = int(len(g))
    return {"bets": n, "units": float(g["units"].sum()) if n else 0.0, "roi": H.roi(g) if n else np.nan,
            "ci95_lo": lo, "ci95_hi": hi, "note": "too few games to tell" if n < THIN else ""}


def national_tv_report(groups: dict, games: pd.DataFrame, tv: pd.DataFrame) -> pd.DataFrame:
    """Each registered cell's bets by television group on the flagged seasons."""
    out = []
    for g in groups.values():
        for cut in g.cuts:
            b = H.grade(pick(g.cand, cut, g.side), games)
            if not len(b):
                continue
            x = b.merge(tv[["game_id", "tv"]], on="game_id")
            for (season, group), part in x.groupby(["season", "tv"]):
                out.append({"family": g.family, "market": g.market, "side": g.side, "cut": cut,
                            "season": int(season), "tv": group, **_summary(part)})
    return pd.DataFrame(out)


def total_regime_report(groups: dict, games: pd.DataFrame) -> pd.DataFrame:
    """Each POPT cell either side of the 2024-25 change in the total tickets."""
    out = []
    for g in groups.values():
        if g.family != FAMILY_TOT:
            continue
        for cut in g.cuts:
            b = H.grade(pick(g.cand, cut, g.side), games)
            for name, seasons in TOTAL_REGIMES.items():
                part = b[b["season"].isin(seasons)] if len(b) else b
                out.append({"family": g.family, "market": g.market, "side": g.side, "cut": cut,
                            "seasons": name, **_summary(part)})
    return pd.DataFrame(out)


def step1_rows(signal: pd.DataFrame, close: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Per (game, market): the popular side's (or the under's) result at Pinnacle's
    closing number, its no-vig price there, and the rule's number. A push is left
    out. Reads results, so it runs only under --full."""
    c = close[close["market"].isin((*POP_MARKETS, TOTAL))].drop(columns="season", errors="ignore")
    x = c.merge(games[["game_id", "season", "game_date", "home_score", "away_score"]], on="game_id")
    x = x.merge(signal[["game_id", "gap_size", "side_against", "habit"]], on="game_id")
    hs, a_s = x["home_score"].to_numpy(float), x["away_score"].to_numpy(float)
    line = x["close_line"].to_numpy(float)
    m = x["market"].to_numpy(object)
    # the side-A margin at the close: above 0 is side A (home, over) winning
    edge = np.where(m == TOTAL, (hs + a_s) - line, np.where(m == "spreads", (hs - a_s) + line, hs - a_s))
    won_a = np.where(edge > 0, 1.0, np.where(edge < 0, 0.0, np.nan))
    fa = x["close_fa"].to_numpy(float)
    popular_home = x["side_against"].to_numpy(object) == "away"
    is_total = m == TOTAL
    y = np.where(is_total, 1.0 - won_a, np.where(popular_home, won_a, 1.0 - won_a))
    p = np.where(is_total, 1.0 - fa, np.where(popular_home, fa, 1.0 - fa))
    strength = np.where(is_total, x["habit"].to_numpy(float), x["gap_size"].to_numpy(float))
    keep = np.isfinite(y) & np.isfinite(p) & np.isfinite(strength) & (is_total | pd.notna(x["side_against"]).to_numpy())
    out = x.loc[keep, ["game_id", "season", "game_date", "market"]].reset_index(drop=True)
    return out.assign(strength=strength[keep], result=y[keep], close_p=p[keep], resid=(y - p)[keep])


def _day_boot(days, x, y, n_boot: int = 2000, seed: int = H.SEED) -> tuple[np.ndarray, np.ndarray]:
    """Whole-day bootstrap (mean of y, slope of y on x)."""
    d = pd.DataFrame({"d": days, "x": x, "y": y, "xx": x * x, "xy": x * y, "n": 1.0}).groupby("d").sum()
    arr = d[["x", "y", "xx", "xy", "n"]].to_numpy(float)
    rng = np.random.default_rng(seed)
    s = arr[rng.integers(0, len(arr), size=(n_boot, len(arr)))].sum(1)
    mean = s[:, 1] / s[:, 4]
    with np.errstate(invalid="ignore", divide="ignore"):
        slope = (s[:, 3] - s[:, 0] * s[:, 1] / s[:, 4]) / (s[:, 2] - s[:, 0] ** 2 / s[:, 4])
    return mean, slope


def step1_report(rows: pd.DataFrame, seasons=(*H.CHOOSE, H.CONFIRM)) -> pd.DataFrame:
    """The sweep's Step 1, per market on the pooled seasons: the mean of (result
    minus the close's no-vig price) per band, and its slope per ticket point."""
    out = []
    r = rows[rows["season"].isin(seasons)]
    for market, x in r.groupby("market"):
        edges = HABIT_CUTS if market == TOTAL else GAP_CUTS
        bands = [(0.0, edges[0]), *zip(edges, (*edges[1:], np.inf))]
        for lo, hi in bands:
            part = x[(x["strength"] >= lo) & (x["strength"] < hi)]
            if not len(part):
                continue
            mean, _ = _day_boot(part["game_date"].to_numpy(), part["strength"].to_numpy(float),
                                part["resid"].to_numpy(float))
            out.append({"market": market, "row": "band", "lo": lo, "hi": hi, "n": int(len(part)),
                        "value": float(part["resid"].mean()), "ci95_lo": float(np.percentile(mean, 2.5)),
                        "ci95_hi": float(np.percentile(mean, 97.5))})
        xs, ys = x["strength"].to_numpy(float), x["resid"].to_numpy(float)
        _, slope = _day_boot(x["game_date"].to_numpy(), xs, ys)
        out.append({"market": market, "row": "slope per point", "lo": np.nan, "hi": np.nan, "n": int(len(x)),
                    "value": float(np.polyfit(xs, ys, 1)[0]), "ci95_lo": float(np.nanpercentile(slope, 2.5)),
                    "ci95_hi": float(np.nanpercentile(slope, 97.5))})
    return pd.DataFrame(out)


def population(rows: list[dict], g: Group, prep: dict) -> pd.DataFrame:
    """Per cell and season: games, games decided, games with a deciding price,
    games with the rule's number, and bets. Counts only."""
    games = prep["data"].games
    season = games.drop_duplicates("game_id").set_index("game_id")["season"].astype(int)

    def count(ids):
        return season.reindex(pd.unique(np.asarray(ids, dtype=object))).value_counts()
    n_games = season.value_counts()
    n_time = count(prep["frames"][g.point]["times"]["game_id"])
    priced = count(g.cand.loc[g.cand["book"].isin(H.BETTABLE) & (g.cand["price"] >= H.PRICE_FLOOR), "game_id"])
    numbered = count(g.cand["game_id"])
    out = []
    for r in rows:
        for s in SEASONS:
            bets = {H.REGIME: r["n_2021"], H.CONFIRM: r["n_confirm"]}.get(s, r.get(f"n_{s}", 0))
            out.append({"family": g.family, "point": g.point, "season": int(s), "market": g.market,
                        "side": g.side, "cut_index": r["cut_index"], "cut": r["cut"],
                        "games": int(n_games.get(s, 0)), "games_with_time": int(n_time.get(s, 0)),
                        "games_priced": int(priced.get(s, 0)), "games_with_number": int(numbered.get(s, 0)),
                        "bets": int(bets or 0)})
    return pd.DataFrame(out)


def write_outputs(out: Path, prep: dict, rows: list[dict], ctl: list[dict], cands: dict) -> None:
    """cells_*.parquet (every registered cell and control), the population, the
    per-game inputs and signals. A signal frame's sides are text or None; no
    pricing object reaches a file (point_frames drops them)."""
    out.mkdir(parents=True, exist_ok=True)
    for fam in (FAMILY_POP, FAMILY_TOT):
        L.write_cells([r for r in rows if r["family"] == fam], out / f"cells_{fam}.parquet")
    for fam in (CONTROL_WITH, CONTROL_DOG, CONTROL_OVER, CONTROL_POP_D, CONTROL_TOT_D):
        L.write_cells([r for r in ctl if r["family"] == fam], out / f"cells_{fam}.parquet")
    pops = [population([r for r in rows if r["family"] == g.family and r["market"] == g.market], g, prep)
            for g in cands.values()]
    pd.concat(pops, ignore_index=True).to_parquet(out / "population_POP.parquet")
    prep["inp"].to_parquet(out / "inputs_POP.parquet")
    prep["signal"].to_parquet(out / "signals_POP.parquet")


def write_reports(out: Path, prep: dict, cands: dict) -> dict:
    games = prep["data"].games
    tv = prep["tv"] if prep.get("tv") is not None else pd.DataFrame(columns=["game_id", "season", "tv"])
    reports = {"national_tv": national_tv_report(cands, games, tv),
               "total_regimes": total_regime_report(cands, games),
               "step1": step1_report(step1_rows(prep["signal"], prep["close"], games))}
    for name, df in reports.items():
        df.to_parquet(out / f"report_{name}.parquet")
    return reports


def credit_table(results: Path) -> pd.DataFrame:
    """The credit line in docs/nba_search_popular.md 7: a POP cell that passes
    the verdict is credited to popularity only when its pooled return beats the
    underdog in the same games (a control with no bet counts as 0). POPT has no
    such control; its verdict stands."""
    v = pd.read_parquet(results / "verdict_house5.parquet")
    v = v[v["family"].isin((FAMILY_POP, FAMILY_TOT))].copy()
    d = pd.read_parquet(results / f"cells_{CONTROL_DOG}.parquet", columns=["market", "cut", "pool_roi"])
    v = v.merge(d.rename(columns={"pool_roi": "dog_pool_roi"}), on=["market", "cut"], how="left")
    beats = v["pool_roi"].to_numpy(float) > np.nan_to_num(v["dog_pool_roi"].to_numpy(float), nan=0.0)
    v["credited_popularity"] = v["house5_passes"].to_numpy(bool) & np.where(v["family"].eq(FAMILY_POP), beats, True)
    return v


# ── a synthetic world (random, never real) ──────────────────────────────────

def synthetic_splits(games: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """Rows with the stored columns. Clean v1 closing rows for every game, plus
    every kind of row this search must not read, each carrying a share that would
    move a team's mean if it were read: v2 rows, pre-tip polls, a reversed slate,
    a late rewrite, and a listing with no game id."""
    rng = np.random.default_rng(seed)
    teams = sorted(set(games["home_team"]) | set(games["away_team"]))
    pop = dict(zip(teams, rng.normal(0.0, 8.0, len(teams))))
    hab = dict(zip(teams, rng.normal(0.0, 4.0, len(teams))))
    rows = []
    for i, g in enumerate(games.itertuples(index=False)):
        home = float(np.clip(50 + pop[g.home_team] - pop[g.away_team] + rng.normal(0, 5), 5, 95))
        over = float(np.clip(60 + hab[g.home_team] + hab[g.away_team] + rng.normal(0, 5), 5, 95))
        base = {"game_id": g.game_id, "game_date": g.game_date, "endpoint": "v1",
                "capture_kind": "archive_undated", "quality": None}
        rows += [{**base, "market": m, "side": s, "tickets_pct": round(v)}
                 for m, s, v in (("spreads", "home", home), ("spreads", "away", 100 - home),
                                 ("h2h", "home", 90.0), ("h2h", "away", 10.0),
                                 (TOTAL, "over", over), (TOTAL, "under", 100 - over))]
        rows += [{**base, "market": "spreads", "side": "home", "tickets_pct": 99, "endpoint": "v2"},
                 {**base, "market": "spreads", "side": "home", "tickets_pct": 99, "capture_kind": "pregame_poll"}]
    df = pd.DataFrame(rows)
    # a whole slate reversed at the source; one listing rewritten late: flagged, values swapped
    slate = games["game_date"].iloc[len(games) // 3]
    rev = df["game_date"].eq(slate) & df["endpoint"].eq("v1") & df["capture_kind"].eq("archive_undated")
    df.loc[rev, "quality"] = "reversed_at_source"
    df.loc[rev & df["side"].isin(["home", "over"]), "tickets_pct"] = 98
    late = df["game_id"].eq(games["game_id"].iloc[len(games) // 2]) & df["endpoint"].eq("v1")
    df.loc[late, "quality"] = "late_rewrite"
    orphan = df[df["market"].eq("spreads") & df["endpoint"].eq("v1")].head(2).assign(game_id=None, tickets_pct=99)
    return pd.concat([df, orphan], ignore_index=True)


def with_swapped_book(q: pd.DataFrame, sig: pd.DataFrame, book: str = "fanduel") -> pd.DataFrame:
    """One book's spread and moneyline on one game with home and away swapped, the
    shape of NBA_2021-12-10_BOS_PHX: the home team is a favourite of 3 or more, so
    the row lies 6 or more from the median, and home is the side against the popular
    team under the first cut, so without the rule the row is that band's bet. G5's
    world holds no such game past the first cut: its popular teams are its strong ones.
    Home's moneyline is above the floor, so the other books' offers remain a bet."""
    x = sig[(sig["side_against"] == "home") & (sig["gap_size"] < GAP_CUTS[0]) & sig["season"].isin(H.CHOOSE)]
    priced = set(q.loc[q["market"].eq("h2h") & q["price_a"].ge(H.PRICE_FLOOR), "game_id"])
    sp = q[q["market"].eq("spreads") & q["book"].eq(book) & (q["line"] <= -3.0)
           & q["game_id"].isin(set(x["game_id"]) & priced)]
    rows = q["game_id"].eq(sp["game_id"].iloc[0]) & q["book"].eq(book) & q["market"].isin(POP_MARKETS)
    q = q.copy()
    q.loc[rows, ["price_a", "price_b"]] = q.loc[rows, ["price_b", "price_a"]].to_numpy()
    spread = rows & q["market"].eq("spreads")
    q.loc[spread, "line"] = -q.loc[spread, "line"]
    return q


def with_heavy_favourites(q: pd.DataFrame, sig: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """On n games past the top cut, the team bet against the public is priced beyond
    the floor at every book, so the cell has no moneyline bet there and the market's
    underdog is the popular team. G5's world holds none of these past the first cut."""
    x = sig[(sig["gap_size"] >= GAP_CUTS[-1]) & sig["season"].isin(H.CHOOSE)].head(n)
    side = dict(zip(x["game_id"], x["side_against"]))
    rows = q["market"].eq("h2h") & q["game_id"].isin(set(side))
    home = q.loc[rows, "game_id"].map(side).eq("home").to_numpy()
    q = q.copy()
    q.loc[rows, "price_a"] = np.where(home, -300.0, 250.0)
    q.loc[rows, "price_b"] = np.where(home, 250.0, -300.0)
    return q


def synthetic_prep(seed: int = 0, bad_rung: bool = True) -> dict:
    """G5's synthetic world (games, h2h / spreads / totals quotes, closes), these
    splits, one impossible total rung, one book with home and away swapped, three
    favourites beyond the floor, a television flag on the flagged seasons."""
    w = G5.synthetic_world(seed=seed)
    data, close = w["data"], w["close"]
    h2h = close[close["market"] == "spreads"].assign(market="h2h", close_line=np.nan)
    close = pd.concat([close, h2h], ignore_index=True)
    q = data.quotes
    if bad_rung:
        row = q[(q["market"] == TOTAL) & (q["book"] == "fanduel") & (q["season"] == 2023)].iloc[[120]].copy()
        q = pd.concat([q, row.assign(line=9.5, price_a=-110.0, price_b=-110.0, book="betmgm",
                                     snapshot_at=row["snapshot_at"] + pd.Timedelta(minutes=1))],
                      ignore_index=True)
    sig = signals(game_inputs(data.games, clean_splits(synthetic_splits(data.games, seed))))
    q = with_heavy_favourites(with_swapped_book(q, sig), sig)
    kept, removed = drop_impossible(q)
    d = H.Data(games=data.games, quotes=kept, fetches=data.fetches, notes={})
    pricing = H.close_dist(close, d.games)
    gm = d.games[["game_id", "season"]].reset_index(drop=True)
    gm["national_tv"] = np.where(gm.index % 4 == 0, "ESPN,TNT", np.where(gm.index % 5 == 0, "NBA TV", None)).astype(object)
    return build_prep(d, close, pricing, clean_splits(synthetic_splits(d.games, seed)), tv_groups(gm), removed)


def synthetic_checks(n_placebo: int = 2) -> dict:
    """Every cell and control through H.run_cells on synthetic games, before any
    real data is read. NBA_GAME2_BETS is unset while they run: run_cells writes
    every cell's bets wherever it points (the 2026-10-20 incident)."""
    H.check()
    with no_bet_files():
        prep = synthetic_prep()
        plc = placebo_signals(prep["inp"], seeds=range(1, n_placebo + 1))
        rows, ctl, _ = all_cells(prep, plc)
    q = prep["data"].quotes
    assert set(q["market"]) == {"h2h", "spreads", TOTAL}, set(q["market"])
    assert len(prep["removed"]) == 1 and (q.loc[q["market"] == TOTAL, "line"] > 100).all()
    for pt in (POINT, DIAG_POINT):
        sw = prep["frames"][pt]["swapped"]
        assert set(sw["market"]) == set(POP_MARKETS) and len(sw) == 2 and sw["game_id"].nunique() == 1, pt
    assert sum(r["games_beyond_floor"] for r in credit_games(prep) if r["market"] == "h2h") > 0
    per_family = pd.Series([r["family"] for r in rows + ctl]).value_counts().to_dict()
    assert per_family == {FAMILY_POP: 6, FAMILY_TOT: 3, CONTROL_WITH: 6, CONTROL_DOG: 6, CONTROL_OVER: 3,
                          CONTROL_POP_D: 6, CONTROL_TOT_D: 3}, per_family
    for r in rows:
        assert len(r["placebo_rois"]) == n_placebo, r["family"]
    for market in (*POP_MARKETS, TOTAL):
        assert sum(r["pool_n"] for r in rows if r["market"] == market) > 0, f"no synthetic {market} bet"
    return {"synthetic_checks": "pass", "cells": len(rows), "controls": len(ctl)}


@contextlib.contextmanager
def no_bet_files():
    saved = os.environ.pop(BETS_ENV, None)
    try:
        yield
    finally:
        if saved is not None:
            os.environ[BETS_ENV] = saved


# ── real data ───────────────────────────────────────────────────────────────

def build_prep(data: H.Data, close: pd.DataFrame, pricing: dict, clean: pd.DataFrame, tv, removed) -> dict:
    inp = game_inputs(data.games, clean)
    frames = {pt: point_frames(data, pt, pricing) for pt in (POINT, DIAG_POINT)}
    return {"data": data, "close": close, "pricing": pricing, "clean": clean, "inp": inp,
            "signal": signals(inp), "frames": frames, "tv": tv, "removed": removed}


def prepare(cache: Path, require: bool) -> dict:
    """Every frame the cells read, on the real cache (no grade). H.close_dist
    reads earlier seasons' results around Pinnacle's close: market pricing, the
    harness's rule, never a bet of this search."""
    data = H.load(cache, seasons=list(SEASONS), require_seasons=list(SEASONS) if require else None)
    kept, removed = drop_impossible(data.quotes)
    d = H.Data(games=data.games, quotes=kept, fetches=data.fetches, notes=data.notes)
    close = H.pinnacle_close(d)
    pricing = H.close_dist(close, d.games)
    splits = pd.read_parquet(cache / "nba_public_splits.parquet", columns=SPLIT_COLS)
    sched = pd.read_parquet(cache / "nba_schedule.parquet", columns=["game_id", "season", "game_type", "national_tv"])
    tv = tv_groups(sched[sched["game_type"].eq("regular")])
    return build_prep(d, close, pricing, clean_splits(splits), tv, removed)


def dummy_games(games: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """The same games with made-up scores: what --smoke grades, to time the grade
    without computing any real result."""
    rng = np.random.default_rng(seed)
    return games.assign(home_score=rng.integers(90, 131, len(games)).astype(float),
                        away_score=rng.integers(90, 131, len(games)).astype(float))


def extremes(prep: dict) -> dict:
    """The extremes of every line, price and ticket number the search reads, the
    rows the swapped rule removes, and the spreads farthest from their median."""
    out = {"impossible_rows_removed": int(len(prep["removed"]))}
    if len(prep["removed"]):
        out["impossible_rows"] = (prep["removed"].groupby(["game_id", "book", "line"]).size()
                                  .reset_index(name="rows").to_dict("records"))
    c = prep["clean"]
    out["tickets_clean_rows"] = {f"{m} {s}": [float(v["tickets_pct"].min()), float(v["tickets_pct"].max()), int(len(v))]
                                 for (m, s), v in c.groupby(["market", "side"])}
    inp, sig = prep["inp"], prep["signal"]
    for name, x in (("popularity", pd.concat([inp["h_pop"], inp["a_pop"]])), ("gap_size", sig["gap_size"]),
                    ("over_share_mean", pd.concat([inp["h_over"], inp["a_over"]])), ("habit", sig["habit"])):
        out[name] = [round(float(x.min()), 2), round(float(x.max()), 2)]
    for pt, fr in prep["frames"].items():
        out[f"swapped_rows_{pt}"] = fr["swapped"][["game_id", "book", "market", "line", "price_a", "price_b"]].to_dict("records")
        out[f"farthest_spreads_{pt}"] = fr["farthest"].to_dict("records")
        n = fr["neutral"]
        d = n[n["book"].isin(H.BETTABLE) & (n["price"] >= H.PRICE_FLOOR)]
        out[f"deciding_offers_{pt}"] = {
            m: {"offers": int(len(x)), "line": [float(x["line"].min()), float(x["line"].max())],
                "price": [float(x["price"].min()), float(x["price"].max())],
                "ev_top": round(float(x["ev"].max()), 3)} for m, x in d.groupby("market")}
    return out


def top_offers(prep: dict, n: int = 12) -> pd.DataFrame:
    x = prep["frames"][POINT]["neutral"]
    x = x[x["book"].isin(H.BETTABLE) & (x["price"] >= H.PRICE_FLOOR)]
    return x.sort_values("ev", ascending=False).head(n)[
        ["game_id", "market", "book", "side", "line", "price", "mu", "p_home", "ev"]].reset_index(drop=True)


def read_gap_hours(prep: dict) -> dict:
    """The hours from the latest tip a rule reads to the decision. Above 0 means no
    rule reads a game that has not started by T."""
    games = prep["data"].games
    g = games[["game_id", "season", "game_date", "tip", "home_team", "away_team"]].reset_index(drop=True)
    g["season"] = g["season"].astype(int)
    rows, _ = share_rows(g, prep["clean"])
    rows = rows[rows["share"].notna()].merge(g[["game_id", "tip"]], on="game_id")
    t = prep["frames"][POINT]["times"].set_index("game_id")["T"]
    worst = []
    for col in ("home_team", "away_team"):
        tgt = g[["season", "game_date"]].assign(team=g[col].to_numpy())
        last = _asof(tgt, rows, ["team", "season"], ["tip"])["tip"]
        hours = (g["game_id"].map(t).reset_index(drop=True) - last.reset_index(drop=True)).dt.total_seconds() / 3600.0
        worst.append(hours.dropna())
    all_h = pd.concat(worst)
    return {"min_hours": round(float(all_h.min()), 2), "p01_hours": round(float(all_h.quantile(0.01)), 2),
            "median_hours": round(float(all_h.median()), 2)}


def band_counts(g: Group, cut_index: int) -> list[dict]:
    """Bets in each band around a cut, counted from the choice."""
    out = []
    for lo, hi in G5.band_bounds(g.cuts, cut_index, lowest=0.0):
        b = pick(g.cand, lo, g.side)
        if np.isfinite(hi) and len(b):
            gone = set(pick(g.cand, hi, g.side)["game_id"])
            b = b[~b["game_id"].isin(gone)]
        pooled = b[b["season"].isin((*H.CHOOSE, H.CONFIRM))] if len(b) else b
        out.append({"lo": lo, "hi": hi, "bets": int(len(pooled))})
    return out


def counts(prep: dict) -> dict:
    """Games with a number and the bets each cell would place (counted from the
    choice, never the grade), with its prices, band sizes and television split."""
    sig, tv = prep["signal"], prep.get("tv")
    season_n = {
        "games": sig.groupby("season")["game_id"].size().to_dict(),
        "games_with_gap": sig[sig["gap_size"].notna()].groupby("season").size().to_dict(),
        "games_with_habit": sig[sig["habit"].notna()].groupby("season").size().to_dict()}
    tc = prep["frames"][POINT]["times"]
    td = prep["frames"][DIAG_POINT]["times"]
    both = tc.merge(td, on="game_id", suffixes=("_c", "_d"))
    fetch = {"games_at_C": int(len(tc)), "games_at_D": int(len(td)), "both": int(len(both)),
             "same_fetch": int((both["T_c"] == both["T_d"]).sum())}
    cells = []
    for pt, fams in ((POINT, (FAMILY_POP, FAMILY_TOT)), (DIAG_POINT, (CONTROL_POP_D, CONTROL_TOT_D))):
        for g in cell_groups(prep, pt, *fams):
            fav = H.fav_sides(g.cand) if g.family in (FAMILY_POP, CONTROL_POP_D) else None
            for k, cut in enumerate(g.cuts):
                b = pick(g.cand, cut, g.side)
                by = b["season"].value_counts().to_dict()
                pooled = b[b["season"].isin((*H.CHOOSE, H.CONFIRM))]
                row = {"family": g.family, "point": pt, "market": g.market, "side": g.side, "cut": cut,
                       **{f"bets_{s}": int(by.get(s, 0)) for s in SEASONS}, "bets_pooled": int(len(pooled)),
                       "price_min": float(pooled["price"].min()) if len(pooled) else np.nan,
                       "price_median": float(pooled["price"].median()) if len(pooled) else np.nan,
                       "price_max": float(pooled["price"].max()) if len(pooled) else np.nan,
                       "line_min": float(pooled["line"].min()) if len(pooled) else np.nan,
                       "line_max": float(pooled["line"].max()) if len(pooled) else np.nan,
                       "ev_top": float(pooled["ev"].max()) if len(pooled) else np.nan}
                if fav is not None and len(pooled):
                    x = pooled.merge(fav, on=["game_id", "market"])
                    row["underdog_share"] = float((x["side"] == x["dog"]).mean())
                if pt == POINT:
                    row["bands"] = ", ".join(f"[{d['lo']:g},{d['hi']:g}): {d['bets']}" for d in band_counts(g, k))
                    if tv is not None and len(tv):
                        t = b.merge(tv[["game_id", "tv"]], on="game_id")
                        for (s, grp), v in t.groupby(["season", "tv"]):
                            row[f"tv_{s}_{grp}"] = int(len(v))
                cells.append(row)
    return {"seasons": season_n, "fetch": fetch, "cells": cells}


def credit_games(prep: dict, pool=(*H.CHOOSE, H.CONFIRM)) -> list[dict]:
    """The credit line's games, pooled and counted from the choice: per market and
    cut the cell's bets, the underdog control's, and the games only one of them
    bets. Stops on a control game the cell cannot bet, or on a game only the cell
    bets that is not a level market: the comparison would not be the registered one.
    games_beyond_floor counts the games the floor keeps out at that cut."""
    neutral, sig = prep["frames"][POINT]["neutral"], prep["signal"]
    out = []
    for market in POP_MARKETS:
        base = neutral[neutral["market"] == market]
        cell, ctl = pop_cand(base, sig), dog_cand(base, sig)
        level = set(cell["game_id"]) - set(H.fav_sides(cell)["game_id"])
        for cut in GAP_CUTS:
            a, b = pick(cell, cut, SIDE_AGAINST), pick(ctl, cut, SIDE_DOG)
            a, b = a[a["season"].isin(pool)], b[b["season"].isin(pool)]
            ga, gb = set(a["game_id"]), set(b["game_id"])
            past = cell[(cell["strength"] >= cut) & cell["season"].isin(pool) & cell["book"].isin(H.BETTABLE)]
            r = {"market": market, "cut": cut, "cell_bets": len(a), "control_bets": len(b),
                 "control_only": len(gb - ga), "cell_only": len(ga - gb), "cell_only_level": len((ga - gb) & level),
                 "games_beyond_floor": len(set(past["game_id"]) - ga)}
            if r["control_only"] or r["cell_only"] != r["cell_only_level"]:
                raise RuntimeError(f"the credit line does not compare the same games: {r}")
            out.append(r)
    return out


def placebo_null(prep: dict, seeds=(1, 2, 3)) -> list[dict]:
    """For each registered cell, the share of placebo bets that are NOT real bets,
    the share of real bets a placebo repeats, and each side's underdog share. On
    the real data, counted from the choice. A placebo that repeats the real bets
    cannot be beaten, so its share must be high."""
    plc = placebo_signals(prep["inp"], seeds=seeds)
    out = []
    for g in cell_groups(prep):
        fav = H.fav_sides(g.cand) if g.family == FAMILY_POP else None
        for cut in g.cuts:
            real = pick(g.cand, cut, g.side)
            real_keys = set(zip(real["game_id"], real["side"]))
            differ, repeat, n, dog = [], [], [], []
            for s in plc:
                b = pick(g.rebuild(s), cut, g.side)
                keys = set(zip(b["game_id"], b["side"]))
                differ.append(1.0 - len(keys & real_keys) / max(len(keys), 1))
                repeat.append(len(keys & real_keys) / max(len(real_keys), 1))
                n.append(len(b))
                if fav is not None and len(b):
                    x = b.merge(fav, on=["game_id", "market"])
                    dog.append(float((x["side"] == x["dog"]).mean()))
            row = {"family": g.family, "market": g.market, "cut": cut, "real_bets": int(len(real)),
                   "placebo_bets_mean": round(float(np.mean(n)), 1),
                   "placebo_bets_differing": round(float(np.mean(differ)), 3),
                   "real_bets_repeated": round(float(np.mean(repeat)), 3)}
            if fav is not None and len(real):
                x = real.merge(fav, on=["game_id", "market"])
                row["underdog_share_real"] = round(float((x["side"] == x["dog"]).mean()), 3)
                row["underdog_share_placebo"] = round(float(np.mean(dog)), 3) if dog else np.nan
            out.append(row)
    return out


def timing(prep: dict, t_prep: float, seed: int = 1) -> dict:
    """One placebo run across the 9 cells on the real offers, and one group of
    cells with its report, each graded against made-up scores. No real result is
    computed. Prints the projected --full time and the memory in use."""
    fake = H.Data(games=dummy_games(prep["data"].games), quotes=prep["data"].quotes,
                  fetches=prep["data"].fetches, notes={})
    p_fake = {**prep, "data": fake}
    groups = cell_groups(prep)
    sig_one = placebo_signals(prep["inp"], seeds=(seed,))[0]
    t0 = time.perf_counter()
    for g in groups:
        for cut in g.cuts:
            b = H.grade(pick(g.rebuild(sig_one), cut, g.side), fake.games)
            if len(b):
                H.roi(b[b["season"].isin(H.CHOOSE)])
    t_placebo = time.perf_counter() - t0
    t0 = time.perf_counter()
    with no_bet_files():
        emit(p_fake, groups[0])
    t_group = time.perf_counter() - t0
    n_groups = len(groups) + len(control_groups(prep))
    t0 = time.perf_counter()
    cands = {(g.family, g.market, g.side): g for g in groups}
    national_tv_report(cands, fake.games, prep["tv"] if prep.get("tv") is not None else pd.DataFrame(columns=["game_id", "tv"]))
    total_regime_report(cands, fake.games)
    step1_report(step1_rows(prep["signal"], prep["close"], fake.games))
    t_reports = time.perf_counter() - t0
    projected = t_prep + N_PLACEBO * t_placebo + n_groups * t_group + t_reports
    mem = {}
    with contextlib.suppress(ImportError, AttributeError):
        import psutil
        info = psutil.Process().memory_info()
        mem = {"rss_gb": round(info.rss / 2**30, 2)}
        with contextlib.suppress(AttributeError):
            mem["peak_gb"] = round(info.peak_wset / 2**30, 2)
    return {"seconds_prepare": round(t_prep, 1), "seconds_one_placebo_all_cells": round(t_placebo, 2),
            "seconds_one_group_no_placebo": round(t_group, 1), "groups": n_groups,
            "seconds_reports": round(t_reports, 1),
            "projected_full_minutes": round(projected / 60.0, 1), **mem}


def smoke_report(prep: dict, t_prep: float = 0.0, out=print) -> dict:
    """Everything --smoke prints from the real cache. Counts, extremes, the
    placebo's null share and the timing; no real bet is graded."""
    pd.set_option("display.width", 250, "display.max_columns", 60, "display.max_rows", 200)
    ex = extremes(prep)
    out("EXTREMES\n" + json.dumps(ex, indent=1, default=str))
    out("HIGHEST-EV OFFERS AT C\n" + top_offers(prep).to_string(index=False))
    gap = read_gap_hours(prep)
    out("HOURS FROM THE LATEST TIP READ TO THE DECISION " + json.dumps(gap))
    if gap["min_hours"] <= 0:
        raise RuntimeError(f"a rule reads a game not started by the decision: {gap}")
    c = counts(prep)
    out("GAMES " + json.dumps(c["seasons"], default=str))
    out("FETCHES " + json.dumps(c["fetch"]))
    out("CELLS, COUNTED FROM THE CHOICE, NO GRADE\n" + pd.DataFrame(c["cells"]).to_string(index=False))
    cg = credit_games(prep)
    out("CREDIT LINE GAMES, POOLED, COUNTED FROM THE CHOICE\n" + pd.DataFrame(cg).to_string(index=False))
    nul = placebo_null(prep)
    out("PLACEBO NULL ON THE REAL DATA (seeds 1-3)\n" + pd.DataFrame(nul).to_string(index=False))
    tm = timing(prep, t_prep)
    out("TIMING " + json.dumps(tm))
    return {"extremes": ex, "read_gap": gap, "counts": c, "credit_games": cg, "placebo_null": nul, "timing": tm}


def refuse_full(cache: Path) -> list[str]:
    why = []
    if os.environ.get(GO_ENV) != "1":
        why.append(f"{GO_ENV}=1 is not set: the owner runs --full")
    if not os.environ.get(RESULTS_ENV):
        why.append(f"{RESULTS_ENV} is not set: name this search's results folder")
    if not os.environ.get(BETS_ENV):
        why.append(f"{BETS_ENV} is not set: a passing cell's figures read its bets")
    for name in (P.LEDGER_FILE, "nba_public_splits.parquet", "nba_schedule.parquet"):
        if not (Path(cache) / name).exists():
            why.append(f"{Path(cache) / name} does not exist: refresh the cache")
    return why


def smoke(cache: Path = H.CACHE) -> dict:
    print(json.dumps(synthetic_checks()), flush=True)
    t0 = time.perf_counter()
    prep = prepare(cache, require=False)
    return smoke_report(prep, time.perf_counter() - t0, out=lambda s: print(s, flush=True))


def print_results(rows: list[dict]) -> None:
    show = ["family", "market", "side", "cut", "pool_n", "pool_units", "pool_roi", "pool_ci95_lo", "pool_ci95_hi",
            "pool_seasons_counted", "pool_seasons_positive", "dk_roi_choose", "dk_roi_confirm", "pool_clv_median"]
    df = pd.DataFrame(rows)[show]
    df["note"] = np.where(df["pool_n"] < THIN, "too few games to tell", "")
    print(df.to_string(index=False), flush=True)


def full(cache: Path = H.CACHE, out: Path | None = None) -> None:
    why = refuse_full(cache)
    if why:
        P.refuse(why)
    out = Path(os.environ[RESULTS_ENV]) if out is None else out
    t0 = time.perf_counter()

    def log(msg: str) -> None:
        print(f"[{(time.perf_counter() - t0) / 60:6.1f} min] {msg}", flush=True)
    log("synthetic checks")
    synthetic_checks()
    log("loading the cache")
    try:
        prep = prepare(cache, require=True)
    except RuntimeError as e:
        P.refuse([str(e)])
    credit_games(prep)
    log(f"prepared: {len(prep['removed'])} impossible rows, "
        f"{len(prep['frames'][POINT]['swapped'])} swapped rows removed; building {N_PLACEBO} placebo signals")
    plc = placebo_signals(prep["inp"])
    assert len(plc) == N_PLACEBO, len(plc)
    rows, ctl, cands = all_cells(prep, plc, log)
    write_outputs(out, prep, rows, ctl, cands)
    log(f"cells written to {out}: {len(rows)} registered, {len(ctl)} controls")
    reports = write_reports(out, prep, cands)
    print_results(rows)
    print_results(ctl)
    for name, df in reports.items():
        print(f"REPORT {name}\n{df.to_string(index=False)}", flush=True)
    log("done")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true", help="synthetic checks, then real counts only")
    g.add_argument("--full", action="store_true", help=f"every season (needs {GO_ENV}=1)")
    g.add_argument("--credit", action="store_true", help="apply the credit line to a verdict's file")
    ap.add_argument("--results", type=Path, help="with --credit: the results folder")
    a = ap.parse_args(argv)
    if a.full:
        full(H.CACHE)
    elif a.credit:
        if a.results is None:
            ap.error("--credit needs --results")
        v = credit_table(a.results)
        print(v[["family", "market", "side", "cut", "pool_n", "pool_roi", "dog_pool_roi", "house5_passes",
                 "house5_failed", "credited_popularity"]].to_string(index=False))
    else:
        smoke(H.CACHE)


if __name__ == "__main__":
    main()
