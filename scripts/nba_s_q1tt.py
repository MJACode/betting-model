"""NBA search: first-quarter and first-half TEAM totals.

docs/nba_search_q1tt.md registers the cells and fixes every choice, written and
committed BEFORE this lab and before any cell was graded (2026-11-03). This lab
EMITS cells through the shared harness (scripts/nba_game_harness, H); the
pass/fail script judges them (scripts/nba_game2_verdict.py --house5), and
`--judge` adds this search's one stricter line (both graded seasons positive).
Nothing here grades a bet by itself before --full, and no cut, constant or rule
below was chosen from a betting result.

26 cells (asserted), decided at each game's one purchase 45-75 minutes before
tip (decision point D, H.per_event_times), 2024-25 and 2025-26 pooled:

  QUOTES      the bought period team totals (odds, source TT_SOURCE), each
              book's MAIN number per (game, market): both prices present,
              coherent first, prices closest to even, ties to the lower line
              (models/nba_book_numbers.main_rungs, the rule split_main_rungs
              applies at write time); every other rung is filed and never bet.
              Then the house's ladder rule (NB.visible_numbers): no deciding
              book more than 1 point from the deciding books' median main number.
  IMPLIED     a book's period spread and total at the same purchase, each
              solved to a centre through the period's market pricing
              (P3.period_market_pricing), give each team's period points:
              home = (total + home margin) / 2, away = (total - home margin) / 2,
              the home margin being the side-A centre of the HOME number.
              Reference (i) the same book's own; (ii) the median of the deciding
              books' centres (the consensus).
  SHAPE       a team's period points around its implied number, from every
              season before the graded one from 2020-21: the consensus implied
              number where period prices exist (2023-24 on), else the team's
              points implied by Pinnacle's full-game close times the period's
              minutes (12/48, 24/48). Home and away pooled, re-centred
              (H.ResidDist).
  FAMILY A    every team-total offer priced at its reference's implied number
              through the shape; the best deciding offer at EV >= .02/.04/.06
              (q1, h1 x over, under x same book, consensus).
  FAMILY B    the live home team-total rule (models/nba_team_total_luck: the
              home part of the shooting-luck gap <= -GAP_CUT, under, LIVE_MIN_GAMES)
              on the HOME first-half and first-quarter team totals; the period's
              share scales the gap and the cut alike, so it moves no bet.
  SETTLEMENT  the team's own first-quarter or first-half points (H.with_periods,
              whose check is that the periods, overtime included, sum to the
              final); a game failing it is left out and counted.
  PLACEBO     200 runs, seeds 1-200. A: each game's disagreement (implied number
              minus the quote's own team-total centre) moved to another game on
              the same date, same period and team role, added to that game's own
              centre; prices stay. B: the home part moved the same way.

    PYTHONPATH=. python C:/Users/micha/AppData/Local/Temp/q1trend/run_with_db.py scripts.nba_s_q1tt --pull
    NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_q1tt --smoke
    NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> NBA_GAME2_BETS=<folder>/bets \
        NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_q1tt --full
    PYTHONPATH=. python -m scripts.nba_game2_verdict --results <folder> --house5
    PYTHONPATH=. python -m scripts.nba_s_q1tt --judge --results <folder>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import models.nba_team_total_luck as tt  # noqa: E402
import models.nba_total_luck as tl  # noqa: E402
from models import nba_book_numbers as NB  # noqa: E402
from scripts import nba_game2_luck as L  # noqa: E402
from scripts import nba_game2_projection as P  # noqa: E402
from scripts import nba_game2_verdict as V  # noqa: E402
from scripts import nba_game4_p3 as P3  # noqa: E402
from scripts import nba_game5 as G5  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402
from scripts import nba_s_starters as S  # noqa: E402
from scripts.nba_derivative_lab import build_outcomes  # noqa: E402

GO_ENV, RESULTS_ENV, BETS_ENV = G5.GO_ENV, G5.RESULTS_ENV, G5.BETS_ENV
SCRATCH_ENV = "NBA_S_Q1TT_SCRATCH"
DEFAULT_SCRATCH = "C:/Users/micha/AppData/Local/Temp/nba_s/q1tt"

TT_SOURCE = "odds_api_nba_period_team_total_history"
TT_MARKETS = ("team_totals_q1_home", "team_totals_q1_away", "team_totals_h1_home", "team_totals_h1_away")
TT_FILE = "period_team_totals.parquet"
TT_COLS = ["game_id", "market", "bookmaker", "snapshot_type", "snapshot_at", "source", "created_at",
           "total_line", "over_price", "under_price"]
PULL_SEASONS = (2024, 2025, 2026)          # 2023-24 is asked for too, to measure that it holds none
PULL_CHUNK, PULL_PAUSE_S = 60, 0.5

POINT = "D"
GRADED = (2025, 2026)                      # 2024-25 and 2025-26: the seasons the team totals were bought for
CHOOSE = (2025,)                           # P3.choosing: every graded season but 2025-26 (the placebo's seasons)
PERIOD_SEASONS = (2024, 2025, 2026)        # the period spread and total purchases (2023-24 is history only)
SHAPE_FIRST = 2021                         # 2020-21: the first season with Pinnacle's full-game close
FULL_GAME_SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)
PERIODS = ("q1", "h1")
TEAMS = ("home", "away")
SPREAD_OF = {"q1": "spreads_q1", "h1": "spreads_h1"}
TOTAL_OF = {"q1": "totals_q1", "h1": "totals_h1"}
PERIOD_MARKETS = tuple(m for p in PERIODS for m in (SPREAD_OF[p], TOTAL_OF[p]))
LIVE_MARKETS = (tt.MARKET, "totals_h1")    # the live models' own markets, for the overlap only
RAW_TT = {(p, t): f"team_totals_{p}_{t}" for p in PERIODS for t in TEAMS}
HARNESS_TT = {"home": "team_totals_home", "away": "team_totals_away"}
MINUTE_SHARE = {"q1": 12.0 / 48.0, "h1": 24.0 / 48.0}
PERIOD_PTS = {"q1": ("home_q1", "away_q1"), "h1": ("home_h1", "away_h1")}

FAM_SAME, FAM_CONS, FAM_B = "A_same", "A_consensus", "B"
REFERENCE = {FAM_SAME: "same_book", FAM_CONS: "consensus"}
A_SIDES = ("over", "under")
EV_CUTS = (0.02, 0.04, 0.06)
A_LABEL = {"q1": "q1_team_totals", "h1": "h1_team_totals"}
B_LABEL = {"q1": "q1_home_team_total", "h1": "h1_home_team_total"}
B_SIDE, B_CUT = tt.SIDE, float(tt.GAP_CUT)  # imported, never typed: the live rule
B_EDGES = (1.0, 2.0, 3.0, 4.0)             # the fifth search's F8 bands: 1-2, 2-3, 3-4, 4+
B_CUT_INDEX = B_EDGES.index(B_CUT)
B_MIN_GAMES = tl.LIVE_MIN_GAMES            # the live rule: one game this season (mike, 2026-11-02)
EARLY_GAMES = tl.MIN_GAMES                 # the graded evidence's 10: bets inside it are counted beside
EXPECTED_CELLS = {FAM_SAME: 12, FAM_CONS: 12, FAM_B: 2}
MIN_SHAPE_ROWS = 600                       # two teams a game, 300 games: the live team-total model's bar
N_PLACEBO = 200
PLACEBO_SEEDS = tuple(range(1, N_PLACEBO + 1))
# No board hangs these. A row outside is filed wrong: dropped before anything is
# computed, and counted. The two team-total ranges do not overlap, so a number
# filed under the other period cannot pass. The period spread and total ranges are
# the starters search's (docs/nba_search_starters.md 4.7).
TT_RANGE = {"q1": (10.0, 41.0), "h1": (42.0, 90.0)}
IMPOSSIBLE = {m: S.IMPOSSIBLE[m] for m in PERIOD_MARKETS}
MAX_MAIN_PRICE = S.MAX_MAIN_PRICE          # a visible main number priced past +-250 is not a main number

assert sum(EXPECTED_CELLS.values()) == 26
assert B_SIDE == "under" and tt.MARKET == "team_totals_home"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def scratch_dir() -> Path:
    return Path(os.environ.get(SCRATCH_ENV, DEFAULT_SCRATCH))


def cell_specs() -> list[tuple]:
    """(family, period, side, cut_index, cut) for every registered cell."""
    a = [(f, p, s, k, c) for f in (FAM_SAME, FAM_CONS) for p in PERIODS for s in A_SIDES
         for k, c in enumerate(EV_CUTS)]
    return a + [(FAM_B, p, B_SIDE, 0, B_CUT) for p in PERIODS]


# ── the pull (read-only, Supabase -> scratch) ───────────────────────────────

def pull(cache: Path = H.CACHE, out: Path | None = None) -> pd.DataFrame:
    """The bought period team-total rows, read-only from Supabase, into the
    scratch folder: a cache of the `odds` table, regenerable by running this
    again. Indexed reads only (game_id = ANY(...), market = ANY(...), source),
    PULL_CHUNK games at a time with a pause, in read-only transactions."""
    import psycopg2
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set (run through run_with_db.py)")
    g = H.load_games(cache)
    ids = sorted(g.loc[g["season"].isin(PULL_SEASONS), "game_id"].astype(str))
    out = scratch_dir() if out is None else Path(out)
    out.mkdir(parents=True, exist_ok=True)
    sql = (f"select {', '.join(TT_COLS)} from odds where game_id = any(%s) and market = any(%s) "
           "and source = %s")
    parts = []
    conn = psycopg2.connect(url)
    try:
        conn.set_session(readonly=True, autocommit=False)
        for i in range(0, len(ids), PULL_CHUNK):
            chunk = ids[i:i + PULL_CHUNK]
            with conn.cursor() as cur:
                cur.execute("set local statement_timeout = '30s'")
                cur.execute(sql, (chunk, list(TT_MARKETS), TT_SOURCE))
                rows = cur.fetchall()
            conn.rollback()
            parts.append(pd.DataFrame(rows, columns=TT_COLS))
            if (i // PULL_CHUNK) % 10 == 0:
                log(f"pull: {i + len(chunk)} of {len(ids)} games, {sum(len(p) for p in parts):,} rows")
            time.sleep(PULL_PAUSE_S)
    finally:
        conn.close()
    df = pd.concat(parts, ignore_index=True)
    for c in ("total_line", "over_price", "under_price"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    df.to_parquet(out / TT_FILE)
    season = g.set_index("game_id")["season"]
    by = df.assign(season=df["game_id"].map(season)).groupby(["season", "market"]).agg(
        rows=("game_id", "size"), games=("game_id", "nunique"))
    manifest = {"source": TT_SOURCE, "markets": list(TT_MARKETS), "pulled_at": pd.Timestamp.utcnow().isoformat(),
                "games_asked": len(ids), "rows": int(len(df)),
                "by_season_market": {f"{s}|{m}": {"rows": int(r.rows), "games": int(r.games)}
                                     for (s, m), r in by.iterrows()}}
    (out / "period_team_totals_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    log(f"pull: {len(df):,} rows written to {out / TT_FILE}")
    print(by.to_string())
    return df


# ── the team-total quotes ───────────────────────────────────────────────────

def tt_quotes(raw: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Stored period team-total rows -> the harness's quote frame, as
    H.load_per_event shapes a per-game purchase: fetch_at = snapshot_at (the
    purchase asked for tip - 60 and stored the feed's snapshot time), side A the
    over, both prices required, `coherent` the 1.00-1.15 test. `market` is the
    harness's team_totals_home / _away (what settles on that team's own points);
    `period`, `team` and `tt_market` (the stored name) say which."""
    o = raw[(raw["source"] == TT_SOURCE) & (raw["snapshot_type"] != "in_play")
            & raw["market"].isin(TT_MARKETS)].copy()
    o["snapshot_at"] = pd.to_datetime(o["snapshot_at"], utc=True, format="mixed")
    o = o.merge(games[["game_id", "season", "game_date", "tip"]], on="game_id")
    o = o[o["snapshot_at"] < o["tip"]]
    o["fetch_at"] = o["snapshot_at"]
    o["tt_market"] = o["market"]
    o["period"] = o["tt_market"].str.slice(12, 14)
    o["team"] = np.where(o["tt_market"].str.endswith("_home"), "home", "away")
    o["market"] = o["team"].map(HARNESS_TT)
    o = o.rename(columns={"bookmaker": "book"})
    o["line"] = o["total_line"].astype(float)
    o["price_a"], o["price_b"] = o["over_price"].astype(float), o["under_price"].astype(float)
    o = o[o["price_a"].notna() & o["price_b"].notna()]
    s = H.imp(o["price_a"]) + H.imp(o["price_b"])
    o["coherent"] = (s >= H.COHERENT[0]) & (s <= H.COHERENT[1])
    return o[H.QUOTE_COLS + ["period", "team", "tt_market"]].reset_index(drop=True)


def impossible_mask(q: pd.DataFrame) -> pd.Series:
    """True for a row whose number no board could hang: a team total outside its
    period's range (TT_RANGE, by the row's `period`), or a period spread or total
    outside IMPOSSIBLE. Other markets are untouched."""
    bad = pd.Series(False, index=q.index)
    if "period" in q:
        for p, (lo, hi) in TT_RANGE.items():
            sel = q["market"].isin(HARNESS_TT.values()) & (q["period"] == p)
            bad |= sel & ((q["line"] < lo) | (q["line"] > hi))
    for m, (lo, hi) in IMPOSSIBLE.items():
        sel = q["market"] == m
        bad |= sel & ((q["line"] < lo) | (q["line"] > hi))
    return bad


def drop_impossible(q: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    bad = impossible_mask(q)
    key = q["tt_market"] if "tt_market" in q else q["market"]
    return q[~bad].reset_index(drop=True), {str(k): int(v) for k, v in key[bad].value_counts().items()}


def ladder_table(q: pd.DataFrame) -> pd.DataFrame:
    """Per book and season: how many (game, market) quotes, how often the book
    listed more than one line in the one purchase, the most lines, the mean."""
    n = q.groupby(["season", "book", "game_id", "tt_market", "fetch_at"])["line"].nunique().rename("n").reset_index()
    return n.groupby(["season", "book"]).agg(
        quotes=("n", "size"), more_than_one=("n", lambda x: float((x > 1).mean())),
        most_lines=("n", "max"), mean_lines=("n", "mean")).reset_index()


def period_numbers(q: pd.DataFrame, times: pd.DataFrame, books=None) -> tuple[pd.DataFrame, dict]:
    """Each book's visible main number at T for ONE period's team totals
    (NB.visible_numbers), then no main number priced past MAX_MAIN_PRICE.
    Both periods share the harness's market names, so a frame holding two
    periods is refused rather than mixed. Returns the counts of what was cut."""
    per = set(q["period"]) if len(q) else set()
    if len(per) > 1:
        raise ValueError(f"period_numbers takes one period at a time, got {sorted(per)}")
    vm = H.visible(NB.main_rungs(q), times)
    masked = NB.ladder_mask(vm, vm, books)
    vis = vm[~masked].reset_index(drop=True)
    vis, past = S.drop_unpriceable(vis)
    return vis, {"rungs_read": int(len(q)), "main_numbers": int(len(vm)), "ladder_masked": int(masked.sum()),
                 "priced_past_limit": past}


# ── the implied period points ───────────────────────────────────────────────

def quote_centres(vis: pd.DataFrame, pricing: dict, books=H.BETTABLE) -> pd.DataFrame:
    """Each coherent quote's centre: the side-A quantity (the home margin for a
    spread -- the stored number is the HOME number, so its threshold is
    -spread_home -- the points for a total) at which the quote's no-vig
    chance holds at its own number, through pricing[(season, market)]
    (H.solve_any). A quote with no pricing has no centre."""
    v = vis[vis["coherent"].astype(bool) & vis["book"].isin(tuple(books))].copy()
    sig = [pricing.get((int(s), m)) for s, m in zip(v["season"], v["market"])]
    v = v.assign(sigma=pd.Series(sig, index=v.index, dtype=object))
    v = v[v["sigma"].notna()]
    if v.empty:
        return v.assign(mu=pd.Series([], dtype=float))
    ia, ib = np.asarray(H.imp(v["price_a"]), float), np.asarray(H.imp(v["price_b"]), float)
    mu = H.solve_any(H.threshold(v["market"], v["line"]), ia / (ia + ib), v["sigma"].to_numpy())
    return v.assign(mu=mu).drop(columns="sigma")


def implied_numbers(cent: pd.DataFrame, period: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(same book, consensus) implied period points, long: one row per team
    (game_id, team[, book], mu). home = (total + margin) / 2, away = (total -
    margin) / 2, margin the home margin's centre. Same book: that book's own
    spread and total. Consensus: the median of the deciding books' spread
    centres and, apart, of their total centres."""
    sp = cent[cent["market"] == SPREAD_OF[period]][["game_id", "book", "mu"]].rename(columns={"mu": "m"})
    to = cent[cent["market"] == TOTAL_OF[period]][["game_id", "book", "mu"]].rename(columns={"mu": "t"})
    same = sp.merge(to, on=["game_id", "book"])
    cons = sp.groupby("game_id")["m"].median().to_frame().join(
        to.groupby("game_id")["t"].median(), how="inner").reset_index()
    cons = cons.merge(sp.groupby("game_id").size().rename("n_spread").reset_index(), on="game_id").merge(
        to.groupby("game_id").size().rename("n_total").reset_index(), on="game_id")

    def long(x, keys):
        h = x[keys].assign(team="home", mu=(x["t"] + x["m"]).to_numpy(float) / 2.0)
        a = x[keys].assign(team="away", mu=(x["t"] - x["m"]).to_numpy(float) / 2.0)
        return pd.concat([h, a], ignore_index=True)
    return long(same, ["game_id", "book"]), long(cons, ["game_id"])


# ── the result shape ────────────────────────────────────────────────────────

def stand_in_points(close: pd.DataFrame, period: str) -> pd.DataFrame:
    """(game_id, season, team, mu): each team's points implied by Pinnacle's
    full-game close (home = (total - spread_home) / 2, away = (total +
    spread_home) / 2) times the period's minutes. For seasons with no period
    price only (the shape's stand-in, as docs/nba_models_2026.md 8.2 priced the
    first period season)."""
    c = close[close["market"].isin(["spreads", "totals"])]
    w = c.pivot_table(index=["game_id", "season"], columns="market", values="close_line",
                      aggfunc="last").reset_index()
    if w.empty or not {"spreads", "totals"} <= set(w.columns):
        return pd.DataFrame(columns=["game_id", "season", "team", "mu"])
    w = w.dropna(subset=["spreads", "totals"])
    k = MINUTE_SHARE[period]
    h = w[["game_id", "season"]].assign(team="home", mu=k * (w["totals"] - w["spreads"]).to_numpy(float) / 2.0)
    a = w[["game_id", "season"]].assign(team="away", mu=k * (w["totals"] + w["spreads"]).to_numpy(float) / 2.0)
    return pd.concat([h, a], ignore_index=True)


def team_points(games_p: pd.DataFrame, period: str) -> pd.DataFrame:
    """(game_id, season, team, pts): each team's period points, trusted games only."""
    hc, ac = PERIOD_PTS[period]
    g = games_p[np.isfinite(games_p[hc].to_numpy(float)) & np.isfinite(games_p[ac].to_numpy(float))]
    h = g[["game_id", "season"]].assign(team="home", pts=g[hc].to_numpy(float))
    a = g[["game_id", "season"]].assign(team="away", pts=g[ac].to_numpy(float))
    return pd.concat([h, a], ignore_index=True)


def shape_residuals(games_p: pd.DataFrame, close: pd.DataFrame, cons_hist: dict,
                    before: int = max(GRADED)) -> pd.DataFrame:
    """(season, period, kind, resid): a team's period points minus its implied
    number, seasons SHAPE_FIRST .. before-1 only (the last graded season's
    results price nothing, so they are never read). kind 'implied': the
    consensus implied number at the period purchase, every season with period
    prices (`cons_hist[period]`, long, with season). kind 'stand_in': the
    full-game stand-in, every season with no period price."""
    parts = []
    for p in PERIODS:
        pts = team_points(games_p, p)
        pts = pts[(pts["season"] >= SHAPE_FIRST) & (pts["season"] < before)]
        ci = cons_hist[p]
        priced = set(ci["season"].astype(int)) if len(ci) else set()
        x = pts.merge(ci[["game_id", "team", "mu"]], on=["game_id", "team"])
        parts.append(pd.DataFrame({"season": x["season"].astype(int), "period": p, "kind": "implied",
                                   "resid": x["pts"].to_numpy(float) - x["mu"].to_numpy(float)}))
        si = stand_in_points(close, p)
        si = si[(si["season"].astype(int) >= SHAPE_FIRST) & ~si["season"].astype(int).isin(priced)]
        y = pts.merge(si[["game_id", "team", "mu"]], on=["game_id", "team"])
        parts.append(pd.DataFrame({"season": y["season"].astype(int), "period": p, "kind": "stand_in",
                                   "resid": y["pts"].to_numpy(float) - y["mu"].to_numpy(float)}))
    r = pd.concat(parts, ignore_index=True)
    return r[np.isfinite(r["resid"].to_numpy(float))].reset_index(drop=True)


def period_shapes(resid: pd.DataFrame, seasons=GRADED, min_rows: int = MIN_SHAPE_ROWS) -> dict:
    """{(S, period): ResidDist} from the residuals of seasons SHAPE_FIRST .. S-1.
    Fewer than `min_rows` stops: there is no fallback to S's own results."""
    out = {}
    for S_ in sorted(int(s) for s in seasons):
        for p in PERIODS:
            r = resid[(resid["period"] == p) & (resid["season"] >= SHAPE_FIRST) & (resid["season"] < S_)]
            if len(r) < min_rows:
                raise RuntimeError(f"{S_} {p}: {len(r)} earlier residuals (need {min_rows}); "
                                   "no fallback to the season itself")
            yrs = sorted(int(s) for s in r["season"].unique())
            out[(S_, p)] = H.ResidDist(r["resid"].to_numpy(float),
                                       f"{S_} {p} team points around the implied number, {yrs[0]}-{yrs[-1]} "
                                       f"({len(r)} rows)")
    return out


def tt_sig(shapes: dict, period: str) -> dict:
    """The shape under the harness's team-total names, for H.market_fair."""
    return {(s, HARNESS_TT[t]): d for (s, p), d in shapes.items() if p == period for t in TEAMS}


# ── family A: the book's own numbers ────────────────────────────────────────

def price_offers(off: pd.DataFrame, implied: pd.DataFrame, keys, shapes: dict, period: str) -> pd.DataFrame:
    """Offers at deciding books priced at their reference's implied number:
    p_win, p_push and ev through the period's shape for the offer's season."""
    o = off[off["book"].isin(H.BETTABLE)]
    x = o.merge(implied[list(keys) + ["mu"]], on=list(keys))
    x = x[np.isfinite(x["mu"].to_numpy(float))].reset_index(drop=True)
    sig = np.array([shapes[(int(s), period)] for s in x["season"]], dtype=object)
    pw, pp = H.side_probs(x["market"].to_numpy(), x["side"].to_numpy(), x["line"].to_numpy(),
                          mu=x["mu"].to_numpy(float), sigma=sig)
    return H.with_ev(x.assign(p_win=pw, p_push=pp))


def a_keys(family: str) -> list[str]:
    return ["game_id", "team", "book"] if family == FAM_SAME else ["game_id", "team"]


class CentrePlacebo:
    """Family A's placebo runs for one period and reference, as arrays.

    Each offer keeps its line and price. Its centre in a run is `base` (the
    team-total quote's own centre: the book's own for the same-book reference,
    the market's fair centre for the consensus) plus the disagreement `delta`
    (implied number minus that centre) of the game this game draws: one
    permutation of the games per date per seed, the same team role, the same
    book for the same-book reference. An offer whose donor has no disagreement
    at its book is not priced in that run. ev is recomputed through the
    offer's season's shape; run_cells' choice (best ev per game and market at
    a deciding book, the price floor, ties to the earlier book) is then a
    group arg-max, and a cut keeps the groups whose best ev reaches it."""

    def __init__(self, cand: pd.DataFrame, base, delta: pd.DataFrame, keys, game_dates: pd.Series,
                 shapes: dict, period: str, seeds=PLACEBO_SEEDS):
        c = cand.reset_index(drop=True)
        self.cand = c
        ids = pd.unique(c["game_id"].to_numpy(dtype=object))
        self.ids, self.pos = ids, {g: i for i, g in enumerate(ids)}
        self.g = c["game_id"].map(self.pos).to_numpy(int)
        self.t = (c["team"] == "away").to_numpy(int)
        self.by_book = "book" in keys
        books = list(H.BETTABLE)
        self.b = (c["book"].map({b: i for i, b in enumerate(books)}).to_numpy(int) if self.by_book
                  else np.zeros(len(c), int))
        nb = len(books) if self.by_book else 1
        self.D = np.full((len(ids), 2, nb), np.nan)
        d = delta[delta["game_id"].isin(self.pos)]
        gi = d["game_id"].map(self.pos).to_numpy(int)
        ti = (d["team"] == "away").to_numpy(int)
        bi = d["book"].map({b: i for i, b in enumerate(books)}).to_numpy(int) if self.by_book else np.zeros(len(d), int)
        self.D[gi, ti, bi] = d["delta"].to_numpy(float)
        self.base = np.asarray(base, float)
        dates = game_dates.reindex(ids).to_numpy(dtype=object)
        self.groups = list(pd.Series(np.arange(len(ids))).groupby(dates, sort=False).indices.values())
        self.seeds = tuple(seeds)
        self.line = c["line"].to_numpy(float)
        self.over = (c["side"] == "over").to_numpy()
        self.dec = np.asarray(H.dec(c["price"].to_numpy(float)), float)
        self.seasons = c["season"].astype(int).to_numpy()
        self.dist = {int(s): shapes[(int(s), period)] for s in np.unique(self.seasons)}
        self.rank = c["book"].map(H.BOOK_RANK).fillna(99).to_numpy(float)
        self.group = self.g * 2 + self.t           # one bet per (game, team market)
        self.ok_book = (c["book"].isin(H.BETTABLE) & (c["price"] >= H.PRICE_FLOOR)).to_numpy()

    def source(self, seed: int) -> np.ndarray:
        rng = np.random.default_rng(seed)
        src = np.arange(len(self.ids))
        for idx in self.groups:
            src[idx] = idx[rng.permutation(len(idx))]
        return src

    def priced(self, mu: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        pw, pp = np.full(len(mu), np.nan), np.zeros(len(mu))
        for s, dist in self.dist.items():
            m = (self.seasons == s) & np.isfinite(mu)
            if m.any():
                w, push, lose = dist.probs(mu[m], self.line[m])
                pw[m] = np.where(self.over[m], w, lose)
                pp[m] = push
        ev = pw * (self.dec - 1.0) - (1.0 - pw - pp)
        return pw, pp, ev

    def mu(self, seed: int | None) -> np.ndarray:
        """Each offer's centre in run `seed` (None: no move, the real centre)."""
        src = np.arange(len(self.ids)) if seed is None else self.source(seed)
        return self.base + self.D[src[self.g], self.t, self.b]

    def frame(self, seed: int | None) -> pd.DataFrame:
        """Run `seed` as a candidate frame run_cells reads (the slow path)."""
        mu = self.mu(seed)
        pw, pp, ev = self.priced(mu)
        keep = np.isfinite(ev)
        return self.cand.assign(mu=mu, p_win=pw, p_push=pp, ev=ev)[keep].reset_index(drop=True)

    def best(self, ev: np.ndarray, side: str) -> tuple[np.ndarray, np.ndarray]:
        """(offer index, its ev) of each group's choice on `side`."""
        m = self.ok_book & (self.over if side == "over" else ~self.over) & np.isfinite(ev)
        idx = np.flatnonzero(m)
        if not len(idx):
            return idx, np.array([], float)
        order = idx[np.lexsort((self.rank[idx], -ev[idx], self.group[idx]))]
        first = np.r_[True, self.group[order][1:] != self.group[order][:-1]]
        pick = order[first]
        return pick, ev[pick]

    def rois(self, units: np.ndarray, risk: np.ndarray, cells, seasons) -> dict:
        """{(side, cut): [ROI on `seasons` per run]}: what run_cells computes from
        its `placebo` frames. A run with no bet is NaN, as there."""
        keep_s = np.isin(self.seasons, list(seasons))
        out = {c: [] for c in cells}
        for s in self.seeds:
            _, _, ev = self.priced(self.mu(s))
            for side in {c[0] for c in cells}:
                pick, bev = self.best(ev, side)
                for (sd, cut) in cells:
                    if sd != side:
                        continue
                    sel = pick[(bev >= cut) & keep_s[pick]]
                    r = risk[sel].sum()
                    out[(sd, cut)].append(float(units[sel].sum() / r) if r > 0 else float("nan"))
        return out

    def chosen(self, seed: int | None, side: str, cut: float) -> set:
        _, _, ev = self.priced(self.mu(seed))
        pick, bev = self.best(ev, side)
        sel = pick[bev >= cut]
        return set(zip(self.cand["game_id"].to_numpy()[sel], self.cand["market"].to_numpy()[sel]))


def a_placebo(cand: pd.DataFrame, family: str, tt_centres: pd.DataFrame, game_dates: pd.Series,
              shapes: dict, period: str, seeds=PLACEBO_SEEDS) -> CentrePlacebo:
    """The placebo for one family A cell group. The quote's own centre: the
    book's own team-total centre (same book) or the market's fair centre
    (consensus); `tt_centres` holds (game_id, team, book, mu_tt) and, under
    book '*', the fair centre."""
    keys = a_keys(family)
    if family == FAM_SAME:
        tc = tt_centres[tt_centres["book"] != "*"]
    else:
        tc = tt_centres[tt_centres["book"] == "*"].drop(columns="book")
    x = cand[keys + ["mu"]].merge(tc[keys + ["mu_tt"]], on=keys, how="left")
    base = x["mu_tt"].to_numpy(float)
    delta = x.assign(delta=x["mu"] - x["mu_tt"]).drop_duplicates(keys)[keys + ["delta"]]
    delta = delta[np.isfinite(delta["delta"].to_numpy(float))]
    return CentrePlacebo(cand, base, delta, keys, game_dates, shapes, period, seeds)


def tt_centres_frame(vis_tt: pd.DataFrame, fair_tt: pd.DataFrame, sig: dict) -> pd.DataFrame:
    """(game_id, team, book, mu_tt): each deciding book's team-total quote's own
    centre, and the market's fair centre under book '*'."""
    c = quote_centres(vis_tt, sig)
    c = c.assign(team=np.where(c["market"] == HARNESS_TT["home"], "home", "away"))[
        ["game_id", "team", "book", "mu"]].rename(columns={"mu": "mu_tt"})
    f = fair_tt.assign(team=np.where(fair_tt["market"] == HARNESS_TT["home"], "home", "away"), book="*")[
        ["game_id", "team", "book", "mu"]].rename(columns={"mu": "mu_tt"})
    return pd.concat([c, f], ignore_index=True)


def graded_offers(cand: pd.DataFrame, games: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """(units, risk) of every offer as if bet, aligned with `cand`'s rows: graded
    once, so a placebo run is a lookup. --full and the clock only."""
    g = H.grade(cand.reset_index(drop=True).assign(_i=np.arange(len(cand))), games)
    u, r = np.full(len(cand), np.nan), np.full(len(cand), np.nan)
    u[g["_i"].to_numpy(int)] = g["units"].to_numpy(float)
    r[g["_i"].to_numpy(int)] = g["risk"].to_numpy(float)
    return u, r


# ── family B: the live home team-total rule ─────────────────────────────────

def b_signal(proj: pd.DataFrame) -> pd.DataFrame:
    """(game_id, market, strength) toward the over: the live model's own home
    part (tt.home_part), in full-game points. The period's share would scale it
    and the cut alike, so it is left unscaled and the cut stays B_CUT."""
    s = proj[["game_id"]].assign(market=tt.MARKET, strength=tt.home_part(proj).to_numpy(float))
    return s[np.isfinite(s["strength"].to_numpy(float))].reset_index(drop=True)


def live_rule_games(games: pd.DataFrame, tt_raw: pd.DataFrame, box: pd.DataFrame, art: dict,
                    times: pd.DataFrame, period: str, seasons=GRADED, min_games: int = B_MIN_GAMES) -> dict:
    """{season: game ids} the LIVE decision function, models.nba_team_total_luck.decide,
    bets when it is handed one period's home team-total quotes in place of the
    full-game ones, at the lab's decision instants, with the live games rule.
    The check that family B is the live rule and not a copy of it. decide reads
    no result of a game it decides; `art` only prices the offer (bucket_uplift 0)."""
    rows = tt_raw[tt_raw["market"] == RAW_TT[(period, "home")]].copy()
    rows["market"] = tt.MARKET
    rows["created_at"] = rows["snapshot_at"]
    out = {}
    for s in seasons:
        g = games[games["season"] == s]
        t = times[times["game_id"].isin(set(g["game_id"]))]
        targets = g[g["game_id"].isin(set(t["game_id"]))][["game_id", "season", "game_date", "home_team", "away_team"]]
        final = g[g["home_score"].notna()][["game_id", "season", "game_date", "home_team", "away_team",
                                            "home_score", "away_score"]]
        sched = g[["game_id", "game_date", "home_team", "away_team"]]
        bets, _, _ = tt.decide(targets, tt.quote_frame(rows, g), box[box["game_id"].isin(set(final["game_id"]))],
                               final, t, art, scheduled=sched, bucket_uplift=0.0, min_games=min_games)
        out[int(s)] = {b.game_id for b in bets}
    return out


def period_share(games_p: pd.DataFrame, period: str, season: int) -> float:
    """The period's share of full-game points (both teams, final scores with
    overtime), over trusted games of seasons SHAPE_FIRST .. season-1."""
    hc, ac = PERIOD_PTS[period]
    g = games_p[(games_p["season"] >= SHAPE_FIRST) & (games_p["season"] < season)]
    g = g[np.isfinite(g[hc].to_numpy(float)) & np.isfinite(g[ac].to_numpy(float))]
    return float((g[hc] + g[ac]).sum() / (g["home_score"] + g["away_score"]).sum())


# ── settlement ──────────────────────────────────────────────────────────────

def period_games(games_p: pd.DataFrame, period: str) -> pd.DataFrame:
    """The games frame run_cells grades a period's team totals on: home_score and
    away_score replaced by each team's points in the period, so the harness's
    team_totals_home / _away (settled on that team's own score) settle on the
    period. A game whose periods fail H.with_periods' check carries NaN and has
    no bet (H.grade would stop on it)."""
    hc, ac = PERIOD_PTS[period]
    g = games_p[["game_id", "season", "game_date", "tip", "home_team", "away_team"]].copy()
    g["home_score"] = games_p[hc].to_numpy(float)
    g["away_score"] = games_p[ac].to_numpy(float)
    return g.reset_index(drop=True)


def settlement_check(games: pd.DataFrame, per: pd.DataFrame, seasons) -> tuple[pd.DataFrame, list]:
    """The first search's check (build_outcomes, which H.with_periods applies):
    the periods, overtime included, sum to the stored final, are numbered 1..n
    with n >= 4, and periods 1 and 2 are present. Per season, and the failing
    game ids."""
    g = games[games["season"].isin(list(seasons))]
    checks = {}
    if "went_to_ot" not in g:
        g = g.assign(went_to_ot=np.nan)
    o = build_outcomes(g[["game_id", "season", "home_score", "away_score", "went_to_ot"]], per, checks)
    bad = o.loc[~o["ok"].astype(bool), "game_id"].tolist()
    return checks["outcomes"], bad


# ── the overlap with the two live models (counts only) ──────────────────────

def live_games(pe: pd.DataFrame, proj: pd.DataFrame) -> dict:
    """{model: set of game_ids it would bet} on the cache's period purchase at
    D: the live home team-total model (home part <= -GAP_CUT, an under offer at
    a deciding book at the floor or better) and the live first-half total model
    (full-game gap >= its GAP_CUT, an over offer). Both read each book's main
    number (NB.visible_numbers). No result is read."""
    import models.nba_first_half_total_luck as fh
    t = H.per_event_times(pe, POINT)
    out = {}
    for model, market, side, sig in ((tt.MODEL_ID, tt.MARKET, tt.SIDE, tt.signal(proj)),
                                     (fh.MODEL_ID, fh.MARKET, fh.SIDE, fh.signal(proj))):
        cut = tt.GAP_CUT if model == tt.MODEL_ID else fh.GAP_CUT
        q = pe[pe["market"] == market]
        off = H.offers(NB.visible_numbers(q, t))
        off = off[(off["side"] == side) & off["book"].isin(H.BETTABLE) & (off["price"] >= H.PRICE_FLOOR)]
        s = tl.side_strength(off, sig)
        out[model] = set(s.loc[s["strength"] >= cut, "game_id"])
    return out


# ── building every frame the cells read ─────────────────────────────────────

def build(games: pd.DataFrame, games_p: pd.DataFrame, close: pd.DataFrame, pe: pd.DataFrame,
          tt_raw: pd.DataFrame, tb: pd.DataFrame, graded=GRADED, say=log) -> dict:
    """Every frame the cells read, from frames (the real cache or a synthetic
    world). Reads earlier seasons' results for the shape and the period
    pricing, and the graded games' period points only to know which have a
    settlement. No bet is graded here."""
    t0 = time.time()
    q_all = tt_quotes(tt_raw, games)
    bad_tt = q_all[impossible_mask(q_all)]
    q_tt, drop_tt = drop_impossible(q_all)
    found = tuple(sorted(int(s) for s in q_tt["season"].unique()))
    pe4_raw = pe[pe["market"].isin(PERIOD_MARKETS)].reset_index(drop=True)
    bad_p = pe4_raw[impossible_mask(pe4_raw)]
    pe4, drop_p = drop_impossible(pe4_raw)
    ladders = ladder_table(q_tt)
    times = H.per_event_times(q_tt[q_tt["season"].isin(list(graded))], POINT)
    times_pe = H.per_event_times(pe4, POINT)
    gp_close = games_p[games_p["season"].isin(sorted(set(close["season"].astype(int))))]
    pricing = P3.period_market_pricing(close, gp_close, sorted(set(PERIOD_SEASONS) | set(graded)))
    P3.require_pricing(pricing, sorted(set(PERIOD_SEASONS) | set(graded)), PERIOD_MARKETS,
                       "the period markets' pricing")
    say(f"quotes and period pricing ({time.time() - t0:.0f}s)")
    vis_ref, drop_ref = {}, {}
    out = {"periods": {}}
    cons_hist = {}
    for p in PERIODS:
        q_ref = pe4[pe4["market"].isin([SPREAD_OF[p], TOTAL_OF[p]])]
        v_hist, n_hist = S.drop_unpriceable(NB.visible_numbers(q_ref, times_pe))
        _, cons_h = implied_numbers(quote_centres(v_hist, pricing), p)
        cons_hist[p] = cons_h.merge(games[["game_id", "season"]], on="game_id")
        v, n = S.drop_unpriceable(NB.visible_numbers(q_ref, times))
        vis_ref[p], drop_ref[p] = v, n
    resid = shape_residuals(games_p, close, cons_hist)
    shapes = period_shapes(resid, graded)
    say(f"shapes ({time.time() - t0:.0f}s)")
    settled = set(games_p.loc[np.isfinite(games_p[list(H.PERIOD_COLS)].to_numpy(float)).all(axis=1), "game_id"])
    dates = S._dates(games)
    for p in PERIODS:
        cent = quote_centres(vis_ref[p], pricing)
        same, cons = implied_numbers(cent, p)
        qp = q_tt[(q_tt["period"] == p) & q_tt["season"].isin(list(graded))].reset_index(drop=True)
        vis_tt, cut_counts = period_numbers(qp, times)
        sig = tt_sig(shapes, p)
        fair_tt = H.market_fair(vis_tt, sig)
        off = H.offers(vis_tt)
        off = off[off["game_id"].isin(settled)].reset_index(drop=True)
        neutral = H.fair_offers(off, fair_tt)
        cands = {FAM_SAME: price_offers(off, same, a_keys(FAM_SAME), shapes, p),
                 FAM_CONS: price_offers(off, cons, a_keys(FAM_CONS), shapes, p)}
        centres = tt_centres_frame(vis_tt, fair_tt, sig)
        dd = H.Data(games=period_games(games_p[games_p["season"].isin(list(graded))], p), quotes=qp,
                    fetches=P3.derivative_data(games_p, qp).fetches)
        out["periods"][p] = {"vis_tt": vis_tt, "cut_counts": cut_counts, "fair_tt": fair_tt, "off": off,
                             "neutral": neutral, "cands": cands, "same": same, "cons": cons, "cent": cent,
                             "centres": centres, "dd": dd, "sig": sig, "q": qp}
    say(f"family A frames ({time.time() - t0:.0f}s)")
    gr = games[games["season"].isin(list(graded))]
    proj = tl.f4_projections(gr, tb, min_games=B_MIN_GAMES)
    signal = b_signal(proj)
    early = set(proj.loc[(proj["h_n"] < EARLY_GAMES) | (proj["a_n"] < EARLY_GAMES), "game_id"])
    for p in PERIODS:
        nb = out["periods"][p]["neutral"]
        nb = nb[nb["market"] == tt.MARKET].reset_index(drop=True)
        out["periods"][p]["neutral_b"] = nb
        out["periods"][p]["cand_b"] = tl.side_strength(nb, signal)
        out["periods"][p]["share"] = {int(s): period_share(games_p, p, int(s)) for s in graded}
    pe_live = pe[pe["market"].isin(LIVE_MARKETS) & pe["season"].isin(list(graded))].reset_index(drop=True)
    live = live_games(pe_live, tl.f4_projections(gr, tb, min_games=tl.LIVE_MIN_GAMES))
    out.update({"games": games, "games_p": games_p, "times": times, "times_pe": times_pe, "pricing": pricing,
                "shapes": shapes, "resid": resid, "ladders": ladders, "q_tt": q_tt, "pe4": pe4,
                "pe4_raw": pe4_raw, "q_all": q_all, "vis_ref": vis_ref, "proj": proj, "signal": signal,
                "early": early, "live": live, "settled": settled, "dates": dates, "found": found,
                "graded": tuple(graded),
                "dropped": {"team totals": drop_tt, "period markets": drop_p,
                            "reference main numbers priced past the limit": drop_ref},
                "bad_rows": pd.concat([bad_tt, bad_p], ignore_index=True), "cons_hist": cons_hist,
                "seconds": time.time() - t0})
    say(f"family B frames and the overlap ({time.time() - t0:.0f}s)")
    return out


# ── the cells ───────────────────────────────────────────────────────────────

def run_group(dd: H.Data, family: str, label: str, sides, cuts, cand: pd.DataFrame, neutral: pd.DataFrame,
              strength: str, times: pd.DataFrame, edges, lowest: float, cut_index=None, extra=None) -> list[dict]:
    """One market group's cells through H.run_cells (both teams' markets in one
    group for family A, the home market alone for B), each row with its bands
    (G5.band_columns: the band just below the cut and each band from it up)."""
    members = tuple(sorted(set(cand["market"]))) or (tt.MARKET,)
    rows = H.run_cells(dd, family, POINT, cand, neutral, list(cuts), {label: list(sides)},
                       strength=strength, choose_seasons=CHOOSE, times=times, market_groups={label: members})
    for r in rows:
        k = r["cut_index"] if cut_index is None else cut_index
        bounds = G5.band_bounds(edges, k, lowest)
        pool = tuple(int(s) for s in str(r["pool_seasons"]).split(",") if s)
        r.update(G5.band_columns(cand, r["side"], strength, bounds, dd.games, pool))
        r.update(extra or {})
    return rows


def _picks(cand: pd.DataFrame, side: str, cut: float, strength: str) -> pd.DataFrame:
    return G5._pick(cand, cut, side, strength)


def dk_pool_columns(cand: pd.DataFrame, side: str, cut: float, strength: str, games: pd.DataFrame) -> dict:
    """DraftKings alone, both graded seasons pooled: reported beside, never a bar
    (run_cells writes the two seasons apart)."""
    c = cand[cand[strength] >= cut] if strength != "ev" else cand
    b = H.choose(c, cut if strength == "ev" else -np.inf, books=(H.DK,), sides=[side])
    g = H.grade(b, games) if len(b) else b
    g = g[g["season"].isin(list(GRADED))] if len(g) else g
    return {"dk_pool_n": int(len(g)), "dk_pool_units": float(g["units"].sum()) if len(g) else np.nan,
            "dk_pool_roi": H.roi(g) if len(g) else np.nan}


def overlap_columns(bets: pd.DataFrame, live: dict, early: set | None = None) -> dict:
    """Beside each cell, never judged: how many of its bets fall on games each
    live model would bet (and, for B, inside either team's first 10 games)."""
    ids = bets["game_id"].tolist()
    n = len(ids)
    out = {"bets_counted": n}
    for model, games in live.items():
        k = sum(1 for g in ids if g in games)
        out[f"overlap_{model}_n"] = k
        out[f"overlap_{model}_share"] = k / n if n else np.nan
    if early is not None:
        k = sum(1 for g in ids if g in early)
        out["early_season_n"] = k
    return out


def emit_a(prep: dict, family: str, period: str, n_placebo: int = N_PLACEBO, say=None) -> tuple[list[dict], dict]:
    """One family A group's six cells (2 sides x 3 cuts), placebo filled from
    CentrePlacebo (run_cells is called without one)."""
    pp = prep["periods"][period]
    cand = pp["cands"][family]
    t0 = time.time()
    rows = run_group(pp["dd"], family, A_LABEL[period], A_SIDES, EV_CUTS, cand, pp["neutral"], "ev",
                     prep["times"], EV_CUTS, 0.0,
                     extra={"period": period, "reference": REFERENCE[family],
                            "signal_meaning": ("each team-total offer priced at the team's period points implied by "
                                               + ("the same book's own period spread and total"
                                                  if family == FAM_SAME else
                                                  "the deciding books' median period spread and total"))})
    if n_placebo:
        pl = a_placebo(cand, family, pp["centres"], prep["dates"], prep["shapes"], period,
                       PLACEBO_SEEDS[:n_placebo])
        u, r = graded_offers(cand, pp["dd"].games)
        got = pl.rois(u, r, [(x["side"], x["cut"]) for x in rows], CHOOSE)
        for x in rows:
            x["placebo_rois"] = got[(x["side"], x["cut"])]
    else:
        for x in rows:
            x["placebo_rois"] = []
    for x in rows:
        x.update(overlap_columns(_picks(cand, x["side"], x["cut"], "ev"), prep["live"]))
        x.update(dk_pool_columns(cand, x["side"], x["cut"], "ev", pp["dd"].games))
    if say:
        say(f"{family} {period}: {len(rows)} cells in {time.time() - t0:.0f}s")
    return rows, {"cand": cand}


def emit_b(prep: dict, period: str, n_placebo: int = N_PLACEBO, say=None) -> tuple[list[dict], dict]:
    """Family B's cell on one period's home team total: the live cut and side,
    bands 1-2, 2-3, 3-4, 4+ (in full-game points, scaled alike), placebo the
    home part moved within date (S.ShuffledGaps, a lookup)."""
    pp = prep["periods"][period]
    cand, nb = pp["cand_b"], pp["neutral_b"]
    t0 = time.time()
    shares = pp["share"]
    rows = run_group(pp["dd"], FAM_B, B_LABEL[period], [B_SIDE], [B_CUT], cand, nb, "strength", prep["times"],
                     B_EDGES, B_EDGES[0], cut_index=B_CUT_INDEX,
                     extra={"period": period, "reference": "live_rule",
                            "signal_meaning": ("the live home team-total model's home part of the shooting-luck gap "
                                               "(models/nba_team_total_luck), cut and side unchanged"),
                            **{f"period_share_{s}": v for s, v in shares.items()},
                            **{f"cut_in_period_points_{s}": B_CUT * v for s, v in shares.items()}})
    g = prep["signal"][prep["signal"]["game_id"].isin(set(cand["game_id"]))].reset_index(drop=True)
    if n_placebo:
        runs = S.whole_gap_runs(nb, g, prep["dates"], PLACEBO_SEEDS[:n_placebo])
        table = S.side_table(nb[nb["game_id"].isin(set(g["game_id"]))], B_SIDE, pp["dd"].games)
        for x in rows:
            x["placebo_rois"] = S.placebo_rois(runs, table, B_SIDE, x["cut"], CHOOSE)
    else:
        for x in rows:
            x["placebo_rois"] = []
    for x in rows:
        x.update(overlap_columns(_picks(cand, B_SIDE, B_CUT, "strength"), prep["live"], prep["early"]))
        x.update(dk_pool_columns(cand, B_SIDE, B_CUT, "strength", pp["dd"].games))
    if say:
        say(f"{FAM_B} {period}: {len(rows)} cell in {time.time() - t0:.0f}s")
    return rows, {"cand": cand, "signal": g}


def emit_all(prep: dict, n_placebo: int = N_PLACEBO, say=None) -> dict:
    rows = {FAM_SAME: [], FAM_CONS: [], FAM_B: []}
    for p in PERIODS:
        for fam in (FAM_SAME, FAM_CONS):
            rows[fam] += emit_a(prep, fam, p, n_placebo, say)[0]
        rows[FAM_B] += emit_b(prep, p, n_placebo, say)[0]
    n = {f: len(r) for f, r in rows.items()}
    assert n == EXPECTED_CELLS, n
    return rows


# ── a synthetic world (the only place a cell is run before --full) ──────────

def synthetic_tt(world: dict, seed: int = 5, graded=GRADED, noise: float = 1.2) -> pd.DataFrame:
    """Made-up period team-total rows in the pull's shape, for the graded seasons
    of G5.synthetic_world: draftkings and fanduel one line each, betmgm a
    five-rung ladder whose middle rung is even (hardrockbet until 2026-11-13,
    when it left the bettable books). Lines sit near the team's period
    points the world's period lines imply, plus noise, so offers cross every cut."""
    rng = np.random.default_rng(seed)
    pe = world["pe"]
    g = world["games"].set_index("game_id")
    rows = []
    half = lambda v: float(np.floor(v)) + 0.5  # noqa: E731
    for p in PERIODS:
        sp = pe[(pe["market"] == SPREAD_OF[p]) & (pe["book"] == "pinnacle")].set_index("game_id")
        to = pe[(pe["market"] == TOTAL_OF[p]) & (pe["book"] == "pinnacle")].set_index("game_id")
        for gid in sp.index.intersection(to.index):
            if int(g.loc[gid, "season"]) not in graded:
                continue
            snap = pd.Timestamp(sp.loc[gid, "snapshot_at"]).strftime("%Y-%m-%dT%H:%M:%SZ")
            m = -float(sp.loc[gid, "line"])
            tot = float(to.loc[gid, "line"])
            for t, mu in (("home", (tot + m) / 2.0), ("away", (tot - m) / 2.0)):
                base = {"game_id": gid, "market": RAW_TT[(p, t)], "snapshot_type": "open", "snapshot_at": snap,
                        "source": TT_SOURCE, "created_at": "2026-11-03 21:00:00+00"}
                for b in ("draftkings", "fanduel"):
                    j = float(rng.integers(-1, 2))
                    rows.append({**base, "bookmaker": b, "total_line": half(mu + rng.normal(0.0, noise)),
                                 "over_price": -110.0 + 6 * j, "under_price": -110.0 - 6 * j})
                main = half(mu + rng.normal(0.0, noise))
                for k, (po, pu) in zip((-2, -1, 0, 1, 2), ((-190, 150), (-145, 115), (-110, -110), (115, -145),
                                                           (150, -190))):
                    rows.append({**base, "bookmaker": "betmgm", "total_line": main + k,
                                 "over_price": float(po), "under_price": float(pu)})
    return pd.DataFrame(rows)[TT_COLS]


def synthetic_box(world: dict) -> pd.DataFrame:
    """Player-log-shaped rows (one per team-game) from G5.synthetic_world's team
    sums, so the live decision function, which builds its ratings from player
    rows (models.nba_total_luck.team_box), can read the world: offensive
    rebounds and turnovers 0, field-goal attempts set so a team's possessions
    estimate is its own `poss`."""
    tb = world["tb"]
    return pd.DataFrame({"game_id": tb["game_id"], "team": tb["team"], "points": tb["pts"],
                         "fg_att": tb["poss"] - tl.FTA_POSS * tb["fta"], "fg3_made": tb["fg3m"],
                         "fg3_att": tb["fg3a"], "ft_made": tb["ftm"], "ft_att": tb["fta"],
                         "offensive_reb": 0.0, "turnovers": 0.0})


def synthetic_prep(world: dict | None = None, say=lambda *_: None) -> dict:
    w = G5.synthetic_world() if world is None else world
    raw = synthetic_tt(w)
    return build(w["games"], w["games_p"], w["close"], w["pe"], raw, w["tb"], say=say)


def synthetic_run(world: dict | None = None, n_placebo: int = 2) -> dict:
    prep = synthetic_prep(world)
    rows = emit_all(prep, n_placebo)
    return {"prep": prep, "rows": rows}


def synthetic_checks(n_placebo: int = 2) -> dict:
    """Before any real data is read (--smoke, --full): the harness's sign
    checks, every cell through run_cells on synthetic games, every family
    betting, and a true null under each placebo. NBA_GAME2_BETS is unset while
    they run, so no made-up bet lands in a graded run's folder."""
    H.check()
    saved = os.environ.pop(BETS_ENV, None)
    try:
        out = synthetic_run(n_placebo=n_placebo)
    finally:
        if saved is not None:
            os.environ[BETS_ENV] = saved
    for fam, rr in out["rows"].items():
        t = pd.DataFrame(rr)
        assert len(rr) == EXPECTED_CELLS[fam] and set(t["family"]) == {fam}
        assert (t.groupby("period")["pool_n"].max() > 0).all(), f"{fam}: a period placed no bet"
        assert all(len(r["placebo_rois"]) == n_placebo for r in rr)
    d = placebo_null(out["prep"], n_runs=5)
    assert (d["share_differs"] > 0.3).all(), d
    print(f"synthetic: {sum(len(r) for r in out['rows'].values())} cells; every family bets in both periods; "
          f"placebo bets differing {d['share_differs'].min():.2f} to {d['share_differs'].max():.2f}; nothing written")
    return out


# ── the placebo's null, on real or synthetic prices with no result ──────────

def placebo_null(prep: dict, n_runs: int = 10) -> pd.DataFrame:
    """Per cell: the share of placebo bets that are not the real bets, over the
    first `n_runs` runs, and the ceiling (1 - the share of the population the
    cell bets). Prices only: no result is read."""
    out = []
    seeds = PLACEBO_SEEDS[:n_runs]
    for p in PERIODS:
        pp = prep["periods"][p]
        for fam in (FAM_SAME, FAM_CONS):
            cand = pp["cands"][fam]
            pl = a_placebo(cand, fam, pp["centres"], prep["dates"], prep["shapes"], p, seeds)
            pop = int(cand[["game_id", "market"]].drop_duplicates().shape[0])
            for side in A_SIDES:
                for cut in EV_CUTS:
                    real = pl.chosen(None, side, cut)
                    sh, sizes = [], []
                    for s in seeds:
                        b = pl.chosen(s, side, cut)
                        sizes.append(len(b))
                        sh.append(1.0 - len(b & real) / len(b) if b else np.nan)
                    out.append({"family": fam, "period": p, "side": side, "cut": cut, "real_bets": len(real),
                                "placebo_bets": float(np.mean(sizes)),
                                "share_differs": float(np.nanmean(sh)) if np.isfinite(sh).any() else np.nan,
                                "ceiling": 1.0 - len(real) / pop if pop else np.nan})
        nb = pp["neutral_b"]
        g = prep["signal"][prep["signal"]["game_id"].isin(set(pp["cand_b"]["game_id"]))].reset_index(drop=True)
        runs = S.whole_gap_runs(nb, g, prep["dates"], seeds)
        d = S.share_differs(pp["cand_b"], runs, B_SIDE, B_CUT, n_runs)
        out.append({"family": FAM_B, "period": p, "side": B_SIDE, "cut": B_CUT, "real_bets": d["real_bets"],
                    "placebo_bets": d["placebo_bets"], "share_differs": d["share_differs"], "ceiling": d["ceiling"]})
    return pd.DataFrame(out)


# ── real data ───────────────────────────────────────────────────────────────

PRICE_FILES = ("nba_games.parquet", "nba_odds.parquet", "nba_fetch_ledger.parquet")


def _fingerprint(cache: Path, files) -> dict:
    return {f: [(Path(cache) / f).stat().st_size, int((Path(cache) / f).stat().st_mtime)] for f in files}


def pinnacle_close(cache: Path, scratch: Path, require: bool, say=log) -> pd.DataFrame:
    """Pinnacle's last pre-tip full-game quotes (H.pinnacle_close on H.load),
    saved in the scratch folder with a fingerprint of the cache files: a cache
    of a cache, rebuilt when they change. `require` refuses a season priced
    on fewer than 90% of its games (H.load)."""
    d = Path(scratch)
    fp = {**_fingerprint(cache, PRICE_FILES), "seasons": list(FULL_GAME_SEASONS), "require": bool(require)}
    stamp, f = d / "pinnacle_close_fingerprint.json", d / "pinnacle_close.parquet"
    if stamp.exists() and f.exists() and json.loads(stamp.read_text(encoding="utf-8")) == fp:
        say("close: reading the saved Pinnacle closes")
        return pd.read_parquet(f)
    say("close: loading the full-game prices (H.load)")
    data = H.load(cache, seasons=FULL_GAME_SEASONS, require_seasons=FULL_GAME_SEASONS if require else None)
    close = H.pinnacle_close(data)
    del data
    d.mkdir(parents=True, exist_ok=True)
    close.to_parquet(f)
    stamp.write_text(json.dumps(fp), encoding="utf-8")
    return close


def load_tt_raw(scratch: Path) -> pd.DataFrame:
    f = Path(scratch) / TT_FILE
    if not f.exists():
        raise RuntimeError(f"{f} does not exist: run `--pull` through run_with_db.py first")
    return pd.read_parquet(f)


def prepare(cache: Path, require: bool, scratch: Path, say=log) -> dict:
    t0 = time.time()
    games = H.load_games(cache)
    games_p = H.with_periods(games, cache)
    close = pinnacle_close(cache, scratch, require, say)
    pe = H.load_per_event(games_p, cache, require_seasons=PERIOD_SEASONS if require else None)
    pe = pe[pe["market"].isin(PERIOD_MARKETS + LIVE_MARKETS)].reset_index(drop=True)
    box, _ = L._load_box(cache)
    tb = tl.team_box(box, games)
    del box
    raw = load_tt_raw(scratch)
    say(f"cache read ({time.time() - t0:.0f}s)")
    prep = build(games, games_p, close, pe, raw, tb, say=say)
    per = pd.read_parquet(Path(cache) / "nba_period_scores.parquet")
    gfull = pd.read_parquet(Path(cache) / "nba_games.parquet", columns=["game_id", "season", "home_score",
                                                                         "away_score", "went_to_ot"])
    prep["settlement"], prep["settlement_bad"] = settlement_check(
        gfull[gfull["home_score"].notna()], per, (SHAPE_FIRST - 1, *FULL_GAME_SEASONS))
    prep["raw_rows"] = int(len(raw))
    prep["seconds"] = time.time() - t0
    return prep


def coverage(prep: dict) -> pd.DataFrame:
    """Per graded season: games, a team-total purchase at all, one 45-75 minutes
    before tip (D), a trusted period score, and per period: games with team-total
    offers at a deciding book, with a consensus number, with any same-book number."""
    g = prep["games"]
    rows = []
    for s in prep["graded"]:
        ids = set(g.loc[g["season"] == s, "game_id"])
        r = {"season": s, "games": len(ids),
             "with_a_team_total_row": len(ids & set(prep["q_tt"]["game_id"])),
             "purchase_at_D": len(ids & set(prep["times"]["game_id"])),
             "trusted_period_score": len(ids & prep["settled"])}
        for p in PERIODS:
            pp = prep["periods"][p]
            r[f"{p}_offers"] = len(ids & set(pp["off"]["game_id"]))
            r[f"{p}_consensus"] = len(ids & set(pp["cands"][FAM_CONS]["game_id"]))
            r[f"{p}_same_book"] = len(ids & set(pp["cands"][FAM_SAME]["game_id"]))
            r[f"{p}_home_part"] = len(ids & set(pp["cand_b"]["game_id"]))
        rows.append(r)
    return pd.DataFrame(rows)


def _ext(d: pd.DataFrame, by: str) -> pd.DataFrame:
    return d.groupby(by).agg(rows=("line", "size"), line_min=("line", "min"), line_max=("line", "max"),
                             over_min=("price_a", "min"), over_max=("price_a", "max"),
                             under_min=("price_b", "min"), under_max=("price_b", "max")).round(2)


def extremes(prep: dict) -> None:
    """Every line and price read, the impossible-number rule's catch, and the
    highest-EV offers, so a row filed wrong shows before it can look like an edge."""
    print("\nEXTREMES. Impossible-number rule: team totals", TT_RANGE, "period markets", IMPOSSIBLE,
          "main price past +-", MAX_MAIN_PRICE)
    print("rows dropped by the rule:", json.dumps(prep["dropped"]))
    if len(prep["bad_rows"]):
        print(prep["bad_rows"][["game_id", "market", "book", "line", "price_a", "price_b"]].to_string(index=False))
    print("team totals, every stored rung (both prices):\n", _ext(prep["q_all"], "tt_market").to_string())
    vt = pd.concat([prep["periods"][p]["vis_tt"].assign(tt=lambda x, p=p: p + "_" + x["market"]) for p in PERIODS])
    print("team totals, the main numbers visible at T:\n", _ext(vt, "tt").to_string())
    print("period spreads and totals, every stored quote:\n", _ext(prep["pe4_raw"], "market").to_string())
    vr = pd.concat(prep["vis_ref"].values())
    print("period spreads and totals visible at T:\n", _ext(vr, "market").to_string())
    for p in PERIODS:
        pp = prep["periods"][p]
        print(f"{p} implied points, consensus: ", pp["cons"]["mu"].describe().round(2).to_dict())
        print(f"{p} implied points, same book: ", pp["same"]["mu"].describe().round(2).to_dict())
        print(f"{p} team-total market fair centres: ", pp["fair_tt"]["mu"].describe().round(2).to_dict())
        for fam in (FAM_SAME, FAM_CONS):
            c = pp["cands"][fam]
            c = c[c["price"] >= H.PRICE_FLOOR]
            cols = ["game_id", "market", "side", "book", "line", "price", "mu", "ev"]
            print(f"{p} {fam}: EV of every deciding offer:", c["ev"].describe().round(3).to_dict())
            print(f"{p} {fam}: the 8 highest-EV offers (no result read):\n",
                  c.sort_values("ev", ascending=False).head(8)[cols].round(3).to_string(index=False))
        top = pp["cands"][FAM_CONS].sort_values("ev", ascending=False).head(1)
        if len(top):
            gid, mk = top["game_id"].iloc[0], top["market"].iloc[0]
            print(f"{p}: every book's main number on the highest-EV consensus game ({gid}, {mk}):")
            v = pp["vis_tt"]
            print(v[(v["game_id"] == gid) & (v["market"] == mk)][["book", "line", "price_a", "price_b"]].to_string(index=False))
            r = prep["vis_ref"][p]
            print(r[r["game_id"] == gid][["book", "market", "line", "price_a", "price_b"]].to_string(index=False))


def reference_table(prep: dict) -> pd.DataFrame:
    """Per period and deciding book: how often its period spread and total are
    both visible main numbers at T (a same-book number), against the games where
    it quotes a team total."""
    out = []
    for p in PERIODS:
        pp = prep["periods"][p]
        same = pp["same"]
        for b in sorted(set(pp["off"]["book"])):
            tg = set(pp["off"].loc[pp["off"]["book"] == b, "game_id"])
            sg = set(same.loc[same["book"] == b, "game_id"])
            for s in prep["graded"]:
                ids = set(prep["games"].loc[prep["games"]["season"] == s, "game_id"])
                out.append({"period": p, "book": b, "season": s, "team_total_games": len(tg & ids),
                            "with_own_spread_and_total": len(tg & sg & ids)})
    return pd.DataFrame(out)


def disagreement_table(prep: dict) -> pd.DataFrame:
    """How far each reference's implied number sits from the team-total
    market's own fair centre, in points (prices only, no result)."""
    out = []
    for p in PERIODS:
        pp = prep["periods"][p]
        c = pp["centres"]
        fair = c[c["book"] == "*"].drop(columns="book")
        x = pp["cons"].merge(fair, on=["game_id", "team"])
        d = (x["mu"] - x["mu_tt"])
        out.append({"period": p, "reference": "consensus", "n": len(d), "mean": d.mean(), "sd": d.std(),
                    "p01": d.quantile(.01), "p99": d.quantile(.99)})
        y = pp["same"].merge(c[c["book"] != "*"], on=["game_id", "team", "book"])
        e = (y["mu"] - y["mu_tt"])
        out.append({"period": p, "reference": "same_book", "n": len(e), "mean": e.mean(), "sd": e.std(),
                    "p01": e.quantile(.01), "p99": e.quantile(.99)})
    return pd.DataFrame(out)


def shape_table(prep: dict) -> pd.DataFrame:
    """Rows and spread of the shape's residuals by period, season and kind. The
    average is not printed: for 2024-25, a graded season that is also history
    for 2025-26's shape, it would read like a blind over or under."""
    r = prep["resid"]
    return r.groupby(["period", "season", "kind"])["resid"].agg(["size", "std"]).reset_index()


def stand_in_check(prep: dict) -> pd.DataFrame:
    """On 2023-24 (history, never graded), the spread of a team's period points
    around the implied number against around the stand-in: whether the shape's
    two kinds of residual are the same width."""
    out = []
    close = prep.get("close")
    for p in PERIODS:
        pts = team_points(prep["games_p"], p)
        pts = pts[pts["season"] == min(PERIOD_SEASONS)]
        ci = prep["cons_hist"][p]
        a = pts.merge(ci[["game_id", "team", "mu"]], on=["game_id", "team"])
        row = {"period": p, "season": min(PERIOD_SEASONS), "implied_n": len(a),
               "implied_sd": float((a["pts"] - a["mu"]).std())}
        if close is not None:
            si = stand_in_points(close, p)
            b = pts.merge(si[["game_id", "team", "mu"]], on=["game_id", "team"])
            row.update({"stand_in_n": len(b), "stand_in_sd": float((b["pts"] - b["mu"]).std())})
        out.append(row)
    return pd.DataFrame(out)


def counts(prep: dict) -> pd.DataFrame:
    """The bets each cell would place (an offer at a deciding book at -200 or
    better that clears the cell's cut), per season, with the overlap. Counted,
    never graded."""
    season = prep["games"].set_index("game_id")["season"].astype(int)
    out = []
    for fam, p, side, k, cut in cell_specs():
        pp = prep["periods"][p]
        if fam == FAM_B:
            b = _picks(pp["cand_b"], side, cut, "strength")
            ov = overlap_columns(b, prep["live"], prep["early"])
        else:
            b = _picks(pp["cands"][fam], side, cut, "ev")
            ov = overlap_columns(b, prep["live"])
        by = season.reindex(b["game_id"]).value_counts()
        out.append({"family": fam, "period": p, "side": side, "cut": cut,
                    **{f"bets_{s}": int(by.get(s, 0)) for s in prep["graded"]}, "pooled": int(len(b)),
                    "games": int(b["game_id"].nunique()) if len(b) else 0, **ov})
    return pd.DataFrame(out)


def band_counts(prep: dict) -> pd.DataFrame:
    """Bets per band (bar 5's bands), each side, pooled; counted, never graded."""
    out = []
    for fam, p, side, k, cut in cell_specs():
        pp = prep["periods"][p]
        if fam == FAM_B:
            bounds, cand, st = G5.band_bounds(B_EDGES, B_CUT_INDEX, B_EDGES[0]), pp["cand_b"], "strength"
        else:
            bounds, cand, st = G5.band_bounds(EV_CUTS, k, 0.0), pp["cands"][fam], "ev"
        r = {"family": fam, "period": p, "side": side, "cut": cut}
        for i, (lo, hi) in enumerate(bounds):
            b = _picks(cand, side, lo, st)
            if np.isfinite(hi) and len(b):
                gone = set(zip(*[_picks(cand, side, hi, st)[c] for c in ("game_id", "market")]))
                b = b[[x not in gone for x in zip(b["game_id"], b["market"])]]
            r[f"band{i}"] = f"[{lo:g},{hi:g}): {len(b)}"
        out.append(r)
    return pd.DataFrame(out)


def ev_per_point(prep: dict) -> pd.DataFrame:
    """Through each shape used: the expected value of an over at -110 when the
    centre sits 0 to 1 point above its line, and the points it takes to reach
    EV 0.02. What a disagreement has to be worth before family A bets."""
    out = []
    dec = float(np.asarray(H.dec(np.array([-110.0])), float)[0])
    for (s, p), d in sorted(prep["shapes"].items()):
        line = 28.5 if p == "q1" else 57.5

        def ev(shift):
            w, push, _ = d.probs(np.array([line + shift]), np.array([line]))
            return float(w[0] * (dec - 1.0) - (1.0 - w[0] - push[0]))
        grid = np.arange(0.0, 3.0, 0.01)
        need = next((round(float(x), 2) for x in grid if ev(x) >= 0.02), np.nan)
        out.append({"season": s, "period": p, **{f"ev_at_+{x:g}": round(ev(x), 4) for x in (0, 0.25, 0.5, 1.0)},
                    "points_for_ev_0.02": need})
    return pd.DataFrame(out)


def b_games(prep: dict) -> dict:
    """Family B's bet games per period, and whether they are one set, and the
    live home team-total model's."""
    sets = {p: set(_picks(prep["periods"][p]["cand_b"], B_SIDE, B_CUT, "strength")["game_id"]) for p in PERIODS}
    return {"q1": len(sets["q1"]), "h1": len(sets["h1"]), "the same games": sets["q1"] == sets["h1"],
            "equal to the live home team-total model's games": sets["q1"] == prep["live"][tt.MODEL_ID]}


def time_cells(prep: dict) -> dict:
    """The clock on real offers with made-up results: the period games carry
    random scores, so every merge and settlement costs what it will cost and no
    real bet is graded. One placebo run of each family is timed and held equal
    to run_cells' own frame-by-frame path on two runs. NBA_GAME2_BETS is unset."""
    saved = os.environ.pop(BETS_ENV, None)
    rng = np.random.default_rng(0)
    try:
        res = {}
        fake_prep = dict(prep)
        fake_prep["periods"] = {}
        for p in PERIODS:
            pp = dict(prep["periods"][p])
            fg = pp["dd"].games.copy()
            fg["home_score"] = rng.integers(10, 75, len(fg)).astype(float)
            fg["away_score"] = rng.integers(10, 75, len(fg)).astype(float)
            pp["dd"] = H.Data(games=fg, quotes=pp["dd"].quotes, fetches=pp["dd"].fetches)
            fake_prep["periods"][p] = pp
        p = "q1"
        pp = fake_prep["periods"][p]
        for fam in (FAM_SAME, FAM_CONS):
            cand = pp["cands"][fam]
            t0 = time.time()
            u, r = graded_offers(cand, pp["dd"].games)
            t_grade = time.time() - t0
            pl = a_placebo(cand, fam, pp["centres"], prep["dates"], prep["shapes"], p, PLACEBO_SEEDS[:N_PLACEBO])
            cells = [(s, c) for s in A_SIDES for c in EV_CUTS]
            t0 = time.time()
            fast = pl.rois(u, r, cells, CHOOSE)
            per_run = (time.time() - t0) / N_PLACEBO
            t0 = time.time()
            for seed in PLACEBO_SEEDS[:2]:
                fr = pl.frame(seed)
                for (side, cut) in cells:
                    gp = H.grade(H.choose(fr, cut, sides=[side]), pp["dd"].games)
                    gp = gp[gp["season"].isin(CHOOSE)] if len(gp) else gp
                    slow = H.roi(gp) if len(gp) else float("nan")
                    f = fast[(side, cut)][seed - 1]
                    if not (np.isclose(slow, f) or (np.isnan(slow) and np.isnan(f))):
                        raise RuntimeError(f"{fam} {side} {cut} seed {seed}: arrays {f}, run_cells' path {slow}")
            per_slow = (time.time() - t0) / 2.0
            res[fam] = {"one_placebo_run_s": round(per_run, 4), "same_run_frame_by_frame_s": round(per_slow, 2),
                        "grade_every_offer_s": round(t_grade, 2), "the_two_paths_agree": True}
        t0 = time.time()
        emit_a(fake_prep, FAM_CONS, p, n_placebo=0)
        res["one_group_of_six_cells_without_placebo_s"] = round(time.time() - t0, 1)
        t0 = time.time()
        emit_b(fake_prep, p, n_placebo=N_PLACEBO)
        res["family_B_one_cell_with_200_placebo_s"] = round(time.time() - t0, 1)
        a_group = res["one_group_of_six_cells_without_placebo_s"] + max(
            res[f]["grade_every_offer_s"] + N_PLACEBO * res[f]["one_placebo_run_s"] for f in (FAM_SAME, FAM_CONS))
        cells_s = 4 * a_group + 2 * res["family_B_one_cell_with_200_placebo_s"]
        res["projected_cells_minutes"] = round(cells_s / 60.0, 1)
        res["setup_minutes_this_run"] = round(prep["seconds"] / 60.0, 1)
        res["projected_full_minutes"] = round((cells_s + prep["seconds"]) / 60.0, 1)
        return res
    finally:
        if saved is not None:
            os.environ[BETS_ENV] = saved


def smoke(cache: Path = H.CACHE) -> dict:
    """Synthetic cells, then on the real cache only what the record allows
    before grading: counts, extremes, the placebo's null on real prices, the clock."""
    t_all = time.time()
    synthetic_checks()
    scratch = scratch_dir()
    prep = prepare(cache, False, scratch)
    prep["close"] = pd.read_parquet(scratch / "pinnacle_close.parquet")
    print("\nTHE PURCHASE:", prep["raw_rows"], "rows; seasons holding team totals:", prep["found"])
    print("\nLADDERS: per book and season, how often a book listed more than one line for one team and period:")
    print(prep["ladders"].round(3).to_string(index=False))
    for p in PERIODS:
        print(f"{p}: main-number rule and ladder rule:", prep["periods"][p]["cut_counts"])
    print("\nSETTLEMENT CHECK (periods incl. overtime sum to the final; numbered 1..n, n >= 4; periods 1, 2):")
    print(prep["settlement"].to_string(index=False))
    print("failing games:", len(prep["settlement_bad"]), prep["settlement_bad"][:20])
    print("\nCOVERAGE:\n", coverage(prep).to_string(index=False))
    print("\nSAME-BOOK NUMBERS: games where a book quotes a team total and its own period spread and total:\n",
          reference_table(prep).to_string(index=False))
    print("\nTHE SHAPE (residuals by season and kind):\n", shape_table(prep).round(3).to_string(index=False))
    print("the shapes used:", {f"{k[0]} {k[1]}": repr(v) for k, v in prep["shapes"].items()})
    print("2023-24, implied against stand-in:\n", stand_in_check(prep).round(3).to_string(index=False))
    print("\nTHE PERIOD'S SHARE OF FULL-GAME POINTS (family B; scales the gap and the cut alike):",
          {p: prep["periods"][p]["share"] for p in PERIODS})
    print("\nDISAGREEMENT, implied number minus the team-total market's own centre (points):\n",
          disagreement_table(prep).round(3).to_string(index=False))
    extremes(prep)
    c = counts(prep)
    print("\nBETS EACH CELL WOULD PLACE (counted, never graded):\n", c.round(3).to_string(index=False))
    print("\nBETS PER BAND (counted, never graded):\n", band_counts(prep).to_string(index=False))
    print("\nLIVE MODELS' GAMES on the graded seasons:", {k: len(v) for k, v in prep["live"].items()})
    print("family B's games:", b_games(prep))
    print("\nWHAT A DISAGREEMENT IS WORTH (an over at -110, its centre above its line):\n",
          ev_per_point(prep).to_string(index=False))
    t = placebo_null(prep)
    print("\nTHE PLACEBO ON REAL DATA: share of placebo bets that are not the real bets (10 runs each).")
    print("ceiling = 1 - the share of the population the cell bets.\n", t.round(3).to_string(index=False))
    print("mean share differing:", round(float(t["share_differs"].mean()), 3), "by family:",
          t.groupby("family")["share_differs"].agg(["min", "mean", "max"]).round(3).to_dict())
    tc = time_cells(prep)
    print("\nTHE CLOCK (real offers, made-up results):", json.dumps(tc, indent=1))
    print(f"peak memory this process: {S.peak_gb():.1f} GB; this smoke took {(time.time() - t_all) / 60.0:.1f} minutes")
    return {"prep": prep, "counts": c, "placebo": t, "clock": tc}


# ── the graded run, and the judge ───────────────────────────────────────────

def refuse_full(cache: Path, scratch: Path) -> list[str]:
    why = []
    if os.environ.get(GO_ENV) != "1":
        why.append(f"{GO_ENV}=1 is not set: the owner runs --full")
    if not os.environ.get(RESULTS_ENV):
        why.append(f"{RESULTS_ENV} is not set: name this search's results folder")
    if not os.environ.get(BETS_ENV):
        why.append(f"{BETS_ENV} is not set: a passing cell's figures read its bets")
    for f in ("nba_fetch_ledger.parquet", "nba_period_scores.parquet"):
        if not (Path(cache) / f).exists():
            why.append(f"{Path(cache) / f} does not exist: refresh the cache")
    if not (Path(scratch) / TT_FILE).exists():
        why.append(f"{Path(scratch) / TT_FILE} does not exist: run --pull first")
    return why


def coverage_refusals(prep: dict) -> list[str]:
    """A graded run refuses team totals in any season but the graded two, and a
    graded season whose purchases reach fewer than 90% of its games at D."""
    why = []
    if prep["found"] != tuple(GRADED):
        why.append(f"team totals held for seasons {prep['found']}, this search grades exactly {GRADED}")
    cov = coverage(prep).set_index("season")
    for s in GRADED:
        share = cov.loc[s, "purchase_at_D"] / cov.loc[s, "games"] if s in cov.index else 0.0
        if share < H.MIN_PRICED_SHARE:
            why.append(f"{s}: a purchase at D on {share:.1%} of games (need {H.MIN_PRICED_SHARE:.0%})")
    return why


def tag_bets(bets_dir: Path, family: str, label: str, period: str, before: set) -> None:
    """Name the period on the bets run_cells just wrote: its `market` column is
    the harness's team_totals_home / _away, settled here on period points."""
    for f in sorted(Path(bets_dir).glob(f"bets_{family}_{POINT}_{label}_*.parquet")):
        if f in before:
            continue
        b = pd.read_parquet(f)
        b["period"] = period
        b["tt_market"] = [RAW_TT[(period, "home" if m == HARNESS_TT["home"] else "away")] for m in b["market"]]
        b.to_parquet(f)


def full(cache: Path = H.CACHE, out: Path | None = None) -> None:
    scratch = scratch_dir()
    why = refuse_full(cache, scratch)
    if why:
        P.refuse(why)
    out = Path(os.environ[RESULTS_ENV]) if out is None else out
    t0 = time.time()
    synthetic_checks()
    try:
        prep = prepare(cache, True, scratch)
    except RuntimeError as e:
        P.refuse([str(e)])
    bad = coverage_refusals(prep)
    if bad:
        P.refuse(bad)
    log(f"graded {GRADED}, choosing {CHOOSE}; prepared in {prep['seconds'] / 60.0:.1f} minutes")
    bets_dir = Path(os.environ[BETS_ENV])
    rows = {FAM_SAME: [], FAM_CONS: [], FAM_B: []}
    for p in PERIODS:
        for fam in (FAM_SAME, FAM_CONS):
            before = set(bets_dir.glob("*.parquet")) if bets_dir.exists() else set()
            rows[fam] += emit_a(prep, fam, p, N_PLACEBO, log)[0]
            tag_bets(bets_dir, fam, A_LABEL[p], p, before)
        before = set(bets_dir.glob("*.parquet")) if bets_dir.exists() else set()
        rows[FAM_B] += emit_b(prep, p, N_PLACEBO, log)[0]
        tag_bets(bets_dir, FAM_B, B_LABEL[p], p, before)
    n = {f: len(r) for f, r in rows.items()}
    if n != EXPECTED_CELLS:
        P.refuse([f"cells built {n}, registered {EXPECTED_CELLS}"])
    out.mkdir(parents=True, exist_ok=True)
    for fam, rr in rows.items():
        L.write_cells(rr, out / f"cells_{fam}.parquet")
    pd.DataFrame([{**r, "placebo_rois": None} for rr in rows.values() for r in rr]).drop(
        columns="placebo_rois").to_parquet(out / "rows_flat.parquet")
    for p in PERIODS:
        pp = prep["periods"][p]
        pd.concat([pp["same"].assign(reference="same_book"), pp["cons"].assign(reference="consensus", book="*")],
                  ignore_index=True).assign(period=p).to_parquet(out / f"implied_{p}.parquet")
    shape_table(prep).to_parquet(out / "shape_residuals_summary.parquet")
    log(f"cells written to {out}: {sum(n.values())}; {(time.time() - t0) / 60.0:.1f} minutes; "
        f"peak memory {S.peak_gb():.1f} GB")
    print(f"next: python -m scripts.nba_game2_verdict --results {out} --house5")
    print(f"then: python -m scripts.nba_s_q1tt --judge --results {out}")


def judge_table(cells: pd.DataFrame) -> pd.DataFrame:
    """Section 9.1's bars from the verdict's own function, then this search's
    one stricter line: with two graded seasons, "mostly positive" means both,
    each with 30 or more bets. A cell under 200 pooled bets reads "too few games
    to tell", not "it loses"."""
    c = V.house_verdict_bands(cells, judge_controls=(), credit={})
    # indexed, never .get with a default: a column lost on the way through parquet
    # must stop the judge, not read every cell as a fail
    n1, r1 = c[f"n_{CHOOSE[0]}"], c[f"roi_{CHOOSE[0]}"]
    n2, r2 = c["n_confirm"], c["roi_confirm"]
    c["both_seasons_positive"] = ((n1 >= V.MIN_SEASON_BETS) & (r1 > 0) & (n2 >= V.MIN_SEASON_BETS) & (r2 > 0))
    c["passes"] = c["house5_passes"] & c["both_seasons_positive"]
    c["reading"] = np.where(c["pool_n"] < V.MIN_BETS, "too few games to tell",
                            np.where(c["passes"], "passes", "fails"))
    return c


def judge(results: Path) -> None:
    c = judge_table(V.load_cells(results))
    print(f"{len(c)} cells; {int(c['house5_passes'].sum())} pass section 9.1's bars; "
          f"{int(c['passes'].sum())} also have both seasons positive; "
          f"{int((c['pool_n'] < V.MIN_BETS).sum())} too few games to tell; "
          f"{int(c['h2_ci95'].sum())} clear the 95% interval alone (about {0.025 * len(c):.2f} by chance)")
    cols = ["family", "market", "side", "cut", "pool_n", "pool_units", "pool_roi", "pool_ci95_lo", "pool_ci95_hi",
            f"roi_{CHOOSE[0]}", "roi_confirm", "dk_roi_choose", "dk_roi_confirm", "blind_pool_over",
            "blind_pool_under", "reading", "house5_failed"]
    print(c[cols].to_string(index=False))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pull", action="store_true", help="read the bought rows from Supabase (read-only)")
    g.add_argument("--smoke", action="store_true", help="synthetic checks, then real counts only")
    g.add_argument("--full", action="store_true", help=f"the graded run (needs {GO_ENV}=1)")
    g.add_argument("--judge", action="store_true", help="the bars plus both seasons positive, on a graded run")
    ap.add_argument("--results", type=Path, help="the graded run's folder, for --judge")
    a = ap.parse_args(argv)
    if a.pull:
        pull(H.CACHE)
    elif a.judge:
        if a.results is None:
            ap.error("--judge needs --results")
        judge(a.results)
    elif a.full:
        full(H.CACHE)
    else:
        smoke(H.CACHE)


if __name__ == "__main__":
    main()
