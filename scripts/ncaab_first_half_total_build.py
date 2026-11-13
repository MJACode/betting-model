"""Build the NCAAB first-half total model's frozen numbers (models/ncaab_first_half_total.py),
and replay it on 2023-24 .. 2025-26 through the card's own functions.

Writes models/saved/ncaab_first_half_total_<season>.json: the first-half map
a + b x T (one least-squares fit of the first-half total on the closing
full-game consensus total, 2021 through the last finished season), the total
table's training sample (closing consensus total, first-half total, count), the
team term's tilt line alpha + beta x Tc and its shrinkage, and every team's
last-season residual sum and count.

THE REPLAY. For each season S of 2024..last, the same numbers are fitted on
2021..S-1 only (exactly as the research fitted them: r5_lib.season_models and
r5_prep.py), and every game with a bought tip-minus-60 first-half quote is
decided through models.ncaab_first_half_total: the as-of full-game consensus
total at the purchase stamp (asof_consensus), the team term as of the stamp
(team_game_residuals, team_effects), every bettable book's quote priced
(quote_offers), the best offer (best_offer: largest edge, ties to the
alphabetically first book, with or without the -200 floor), bet when its edge
is above the cut (decide). The purchase stamp (about 64 minutes before tip)
stands in for the live decision fetch's instant. Graded at the quote's own
price, to win one unit, risk capped at 3 (stake_for). --research-bets and
--research-scored compare the bets game by game with the research's own.

    python -m scripts.ncaab_first_half_total_build --cache DIR --quotes PATH --asof-fg DIR
        [--last-season 2026] [--out PATH] [--research-bets PATH] [--research-scored PATH]
        [--bets-out PATH]
    python -m scripts.ncaab_first_half_total_build --cache DIR --last-season 2026   # fit only
    python -m scripts.ncaab_first_half_total_build --store ABSOLUTE_PATH   # copy it into model_artifacts

DIR holds read-only copies of three Supabase reads, as parquet (the first-half
spread build's, scripts/ncaab_first_half_spread_build.py):
  games.parquet                SELECT game_id, season, game_date, commence_time, home_team,
                               away_team, home_score, away_score FROM games WHERE sport = 'NCAAB'
  ncaab_period_scores.parquet  SELECT game_id, period, home_points, away_points
                               FROM ncaab_period_scores                     (season by season)
  fg_odds.parquet              SELECT game_id, market, bookmaker, snapshot_at, spread_home,
                               total_line FROM odds WHERE market IN ('spreads', 'totals')
                               AND snapshot_type IS DISTINCT FROM 'in_play'  (NCAAB games, by
                               game_id chunks)
fg_odds is the copy the closing lines are read from: the research fitted its
map, table and team term on the closing consensus of its 2026-10-30 copy, and
the first-half spread build read the same copy (2026-11-02).
--asof-fg is a directory of parquet parts of the same fg_odds read taken later
(the research's round 5 took it on 2026-11-03, after the opener grid was
stored): the as-of full-game total at each purchase stamp is read from it, as
the research's headline did.
--quotes is the tip-minus-60 first-half totals, either the research's reduced
quotes (round 5 cache/quotes.parquet: game_id, market, book, snap, line, p1,
p2, ts) or the raw read
  SELECT game_id, market, bookmaker, snapshot_at, total_line, over_price, under_price
  FROM odds WHERE market = 'totals_h1' AND source = 'odds_api_ncaab_derivative_tip60'
which is reduced here by the research's rule (r5_reduce.py: rows stamped at or
after tip dropped; per game and book the number whose two raw implied
probabilities are closest, then the latest stamp).
Every row is in Supabase.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import models.ncaab_first_half_total as ft  # noqa: E402
from scripts.ncaab_first_half_spread_build import closing_lines, halves  # noqa: E402

FIRST_SEASON = 2021      # the first season with stored closing full-game lines
FIRST_REPLAY = 2024      # the first season with a bought tip-minus-60 first half
# The live cut, read from config so the artifact's replay is always graded at
# the cut the card bets on (0.02 at launch, 0.025 from 2026-11-06, mike).
# --research-scored compares at this cut (the research's scored quotes, cut
# here); --research-bets is the research's 0.02 cell and only matches at 0.02.
CUT = float(config.MODEL_EDGE_THRESHOLDS[ft.MODEL_ID])
MIN_PRICE = -200.0       # config.MODEL_MIN_ODDS (pinned); the research's AF1 floor
TIP60_SOURCE = "odds_api_ncaab_derivative_tip60"
CELL = "A_to|totals_h1|tip60|best|0.02"   # the research's registered cell (cut 0.02)


# ── loading ──────────────────────────────────────────────────────────────────

def _ts(s) -> pd.Series:
    return pd.to_datetime(s, utc=True, format="mixed")


def load(cache: Path):
    g = pd.read_parquet(cache / "games.parquet",
                        columns=["game_id", "season", "game_date", "commence_time", "home_team",
                                 "away_team", "home_score", "away_score"])
    g["tip"] = _ts(g["commence_time"])
    per = pd.read_parquet(cache / "ncaab_period_scores.parquet",
                          columns=["game_id", "period", "home_points", "away_points"])
    fg = pd.read_parquet(cache / "fg_odds.parquet",
                         columns=["game_id", "market", "bookmaker", "snapshot_at", "spread_home",
                                  "total_line"])
    fg["ts"] = _ts(fg["snapshot_at"])
    return g, per, fg


def load_asof_totals(path: Path) -> pd.DataFrame:
    """The full-game totals the as-of consensus reads: bettable books only."""
    files = sorted(glob.glob(str(path / "*.parquet"))) if path.is_dir() else [str(path)]
    parts = []
    for f in files:
        x = pd.read_parquet(f, columns=["game_id", "market", "bookmaker", "snapshot_at", "total_line"])
        x = x[(x["market"] == "totals") & x["bookmaker"].isin(ft.BOOKS) & x["total_line"].notna()]
        parts.append(x)
    fg = pd.concat(parts, ignore_index=True)
    fg["ts"] = _ts(fg["snapshot_at"])
    return fg


def _dec(a):
    return ft.dec(a)


def load_quotes(path: Path, games: pd.DataFrame) -> pd.DataFrame:
    """The tip-minus-60 first-half totals, one row per (game, book): bookmaker,
    total_line, over_price, under_price, ts, and each game's purchase stamp."""
    q = pd.read_parquet(path)
    if "snap" in q.columns:
        # The research's reduced quotes (r5_reduce.py). Its stamp is the max ts
        # over every row of the game's tip60 snapshot, every market and book
        # (r5_prep.py), one stamp per game x source.
        tip60 = q[q["snap"] == "tip60"].copy()
        tip60["ts"] = _ts(tip60["ts"])
        stamp = tip60.groupby("game_id")["ts"].max().rename("stamp")
        x = tip60[tip60["market"] == ft.MARKET].rename(columns={
            "book": "bookmaker", "line": "total_line", "p1": "over_price", "p2": "under_price"})
        x = x[["game_id", "bookmaker", "total_line", "over_price", "under_price", "ts"]]
        return x.merge(stamp, left_on="game_id", right_index=True)
    # A raw read of the purchase: reduce it as the research did.
    o = q[q["market"] == ft.MARKET].copy()
    if "source" in o.columns:
        o = o[o["source"] == TIP60_SOURCE]
    o["ts"] = _ts(o["snapshot_at"])
    o = o.merge(games[["game_id", "tip"]], on="game_id")
    o = o[o["ts"] < o["tip"]]
    stamp = o.groupby("game_id")["ts"].max().rename("stamp")
    o = o[o["over_price"].notna() & o["under_price"].notna()].copy()
    o["imb"] = np.abs(1 / _dec(o["over_price"]) - 1 / _dec(o["under_price"]))
    key = ["game_id", "bookmaker"]
    o = o.sort_values(key + ["imb", "ts"], ascending=[True, True, True, False])
    x = o.drop_duplicates(key)[["game_id", "bookmaker", "total_line", "over_price",
                                "under_price", "ts"]]
    return x.merge(stamp, left_on="game_id", right_index=True)


# ── the fit ──────────────────────────────────────────────────────────────────

def fit(team_games: pd.DataFrame, season: int) -> dict:
    """The artifact for `season`: every number fitted on 2021..season-1
    (r5_lib.season_models for the map and table, r5_prep.py for the team term)."""
    tr = team_games[team_games["season"].between(FIRST_SEASON, season - 1)
                    & team_games["h1_home"].notna()]
    tr = tr.assign(h1_total=tr["h1_home"] + tr["h1_away"])
    x = tr.dropna(subset=["total_close"])
    b, a = np.polyfit(x["total_close"].astype(float), x["h1_total"].astype(float), 1)
    t = tr.dropna(subset=["spread_close", "total_close"])
    sample = (t.groupby(["total_close", "h1_total"]).size().reset_index(name="count")
              .sort_values(["total_close", "h1_total"]))
    tg = tr.dropna(subset=["h2_home", "h2_away", "spread_close", "total_close"])
    dt = (tg["h1_home"] + tg["h1_away"]) - (tg["h2_home"] + tg["h2_away"])
    beta, alpha = np.polyfit(tg["total_close"].astype(float), dt.astype(float), 1)
    res = ft.team_game_residuals(team_games[team_games["season"] == season - 1], alpha, beta)
    return {
        "kind": ft.ARTIFACT_KIND, "model_id": ft.MODEL_ID,
        "season": int(season), "prior_season": int(season - 1),
        "books": list(ft.BOOKS), "cut": CUT, "min_price": MIN_PRICE,
        "map": {"a": float(a), "b": float(b), "n": int(len(x)),
                "train_seasons": [FIRST_SEASON, int(season - 1)],
                "what": "first-half total = a + b x T, T = the closing full-game consensus "
                        "total (median of the bettable books' last pre-tip total)"},
        "table": {"grid": list(ft.GRID), "support": list(ft.SUPPORT), "h0": ft.H0,
                  "nmin": ft.NMIN, "n": int(len(t)),
                  "what": "rows [closing consensus total, first-half total, games]; the table's "
                          "key is a + b x the total",
                  "sample": [[float(r.total_close), int(r.h1_total), int(r.count)]
                             for r in sample.itertuples(index=False)]},
        "tilt": {"alpha": float(alpha), "beta": float(beta), "k": ft.K_TOTAL, "w_prev": ft.W_PREV,
                 "game_len_h": 2.5, "n": int(len(tg)),
                 "train_seasons": [FIRST_SEASON, int(season - 1)],
                 "what": "dt = (h1 total - period-2 total) - (alpha + beta x Tc), both teams; tau = "
                         "(this season's ended dt + w_prev x last season's) / (games + w_prev x "
                         "last season's games + k)"},
        "prior_team_sums": ft.prior_sums(res, season - 1),
    }


# ── the replay ───────────────────────────────────────────────────────────────

def replay(art: dict, games: pd.DataFrame, team_games: pd.DataFrame, fg_asof: pd.DataFrame,
           q: pd.DataFrame, cut: float = CUT, min_price: float | None = MIN_PRICE) -> pd.DataFrame:
    """Decide every game of art['season'] that has a bought tip-minus-60 first
    half, through the model's own functions. One row per decided game."""
    S = int(art["season"])
    art = ft.with_table(art)
    gS = games[games["season"] == S].set_index("game_id")
    qq = q[q["game_id"].isin(gS.index)]
    stamp = qq.drop_duplicates("game_id")[["game_id", "stamp"]]
    rows = fg_asof[fg_asof["game_id"].isin(stamp["game_id"])][["game_id", "bookmaker", "ts",
                                                                "total_line"]] \
        .rename(columns={"total_line": "line"})
    cons = ft.asof_consensus(rows, stamp.rename(columns={"stamp": "cutoff"}),
                             market="totals").set_index("game_id")
    res = ft.team_game_residuals(team_games[team_games["season"] == S],
                                 art["tilt"]["alpha"], art["tilt"]["beta"])
    targets = stamp.merge(gS[["home_team", "away_team"]], left_on="game_id", right_index=True)
    tau = ft.team_effects(res, S, art["prior_team_sums"], targets,
                          art["tilt"]["k"], art["tilt"]["w_prev"]).set_index("game_id")
    by_game = {gid: z for gid, z in qq.groupby("game_id")}
    out = []
    for r in targets.itertuples(index=False):
        quotes = by_game.get(r.game_id, qq.iloc[0:0])
        fgc = ({"cons": float(cons.at[r.game_id, "cons"]), "nb": int(cons.at[r.game_id, "nb"])}
               if r.game_id in cons.index else None)
        t = tau.loc[r.game_id].to_dict() if r.game_id in tau.index else None
        d = ft.decide(r.game_id, quotes, fgc, t, art, cut, min_price=min_price)
        row = {"game_id": r.game_id, "season": S, "stamp": r.stamp, "status": d.status,
               "mu": d.mu, "fg_total": d.fg_total, "fg_books": d.fg_books,
               "tau_home": d.tau_home, "tau_away": d.tau_away, "n_offers": len(d.offers)}
        if d.best is not None:
            row.update(book=d.best.book, side=d.best.side, line=d.best.line, price=d.price,
                       edge=d.best.edge, prob=d.best.prob)
        out.append(row)
    return pd.DataFrame(out)


def grade(bets: pd.DataFrame, team_games: pd.DataFrame) -> pd.DataFrame:
    """Each bet's first-half result at its own number and price (stake_for)."""
    x = bets.merge(team_games[["game_id", "h1_home", "h1_away"]], on="game_id", how="left")
    x = x[x["h1_home"].notna()].copy()
    over = (x["h1_home"] + x["h1_away"]) - x["line"]
    res = np.where(x["side"] == "over", over, -over)
    d = ft.dec(x["price"])
    risk = np.minimum(1.0 / (d - 1.0), 3.0)
    x["risk"] = risk
    x["units"] = np.select([res > 0, res < 0], [risk * (d - 1.0), -risk], 0.0)
    x["result"] = np.select([res > 0, res < 0], ["W", "L"], "P")
    return x


def date_ci(gr: pd.DataFrame, nboot: int = 2000, seed: int = 7) -> tuple[float, float]:
    """The research's interval (fh_lib.date_ci): game dates resampled with
    replacement, ROI = units / risk, 2.5 and 97.5 percentiles."""
    g = gr.groupby("game_date").agg(u=("units", "sum"), r=("risk", "sum"))
    rng = np.random.default_rng(seed)
    j = rng.integers(0, len(g), size=(nboot, len(g)))
    roi = g.u.values[j].sum(1) / g.r.values[j].sum(1) * 100
    lo, hi = np.percentile(roi, [2.5, 97.5])
    return round(float(lo), 2), round(float(hi), 2)


def summarize(gr: pd.DataFrame, games: pd.DataFrame | None = None) -> dict:
    def one(z):
        if not len(z):
            return {"bets": 0}
        return {"bets": int(len(z)),
                "record": f"{(z.result == 'W').sum()}-{(z.result == 'L').sum()}-{(z.result == 'P').sum()}",
                "units": round(float(z.units.sum()), 2),
                "roi_pct": round(float(z.units.sum() / z.risk.sum() * 100), 2),
                "price_min": float(z.price.min()), "price_max": float(z.price.max())}
    out = {"pooled": one(gr)}
    for s, z in gr.groupby("season"):
        out[str(int(s))] = one(z)
    if len(gr):
        if games is not None:
            z = gr.merge(games[["game_id", "game_date"]], on="game_id", how="left")
            out["pooled"]["ci95"] = list(date_ci(z))
        ev = gr["prob"] * ft.dec(gr["price"]) - 1
        out["min_ev"] = round(float(ev.min()), 4)
        out["median_ev"] = round(float(ev.median()), 4)
        out["under_share"] = round(float((gr["side"] == "under").mean()), 3)
        out["books"] = {k: int(v) for k, v in gr["book"].value_counts().items()}
    return out


def research_floor_bets(scored: Path, cut: float = CUT, floor: float = MIN_PRICE) -> pd.DataFrame:
    """The research's -200 floor version of the cell (after_fact.py AF1): every
    tip-minus-60 A_to quote whose bet side is shorter than the floor is set
    aside, then the best book is chosen and cut."""
    sc = pd.read_parquet(scored, columns=["game_id", "season", "book", "line", "side", "edge",
                                          "price", "units", "risk", "family", "fsnap"],
                         filters=[("family", "==", "A_to"), ("fsnap", "==", "tip60")])
    sc = sc.copy()
    sc.loc[sc["price"] < floor, "edge"] = -np.inf
    best = sc.sort_values(["edge", "book"], ascending=[False, True]).drop_duplicates("game_id")
    return best[best["edge"] > cut]


def compare(bets: pd.DataFrame, research: pd.DataFrame) -> dict:
    """Game by game against the research's bets of the cell (side 1 = over)."""
    rb = research.set_index("game_id")
    mine = bets.set_index("game_id")
    both = rb.index.intersection(mine.index)
    only_r, only_m = rb.index.difference(mine.index), mine.index.difference(rb.index)
    side_r = np.where(rb.loc[both, "side"] == 1, "over", "under")
    same = ((side_r == mine.loc[both, "side"].values)
            & (rb.loc[both, "book"].values == mine.loc[both, "book"].values)
            & np.isclose(rb.loc[both, "line"].values, mine.loc[both, "line"].values)
            & np.isclose(rb.loc[both, "price"].values, mine.loc[both, "price"].values))
    edge_gap = np.abs(rb.loc[both, "edge"].values - mine.loc[both, "edge"].values)
    units_r = float(rb["units"].sum()) if "units" in rb else None
    return {"research_bets": int(len(rb)), "replay_bets": int(len(mine)),
            "research_units": round(units_r, 2) if units_r is not None else None,
            "in_both": int(len(both)), "identical_game_side_book_line_price": int(same.sum()),
            "differ": sorted(both[~same].tolist())[:20],
            "only_research": sorted(only_r.tolist())[:20], "n_only_research": int(len(only_r)),
            "only_replay": sorted(only_m.tolist())[:20], "n_only_replay": int(len(only_m)),
            "max_edge_gap": float(edge_gap.max()) if len(both) else None}


def store(path: Path) -> None:
    """Copy the artifact into Supabase's model_artifacts (the trainer's restore
    source, as the first-half spread build does). A production write: run it
    deliberately, after the merge, never from a test."""
    from data.db import get_connection
    from models.trainer import _store_artifact
    conn = get_connection()
    try:
        _store_artifact(conn, ft.MODEL_ID, path.stem.split(ft.MODEL_ID + "_")[-1], path)
    finally:
        conn.close()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--store", type=Path, help="copy this artifact into model_artifacts")
    ap.add_argument("--cache", type=Path)
    ap.add_argument("--quotes", type=Path, default=None)
    ap.add_argument("--asof-fg", type=Path, default=None,
                    help="parquet file or directory of parts: the full-game rows the as-of "
                         "consensus total reads (default: the cache's fg_odds.parquet)")
    ap.add_argument("--last-season", type=int, default=2026)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--research-bets", type=Path, default=None,
                    help="the research's bets_cells.parquet (the no-floor cell)")
    ap.add_argument("--research-scored", type=Path, default=None,
                    help="the research's cache/scored_db.parquet (the -200 floor version)")
    ap.add_argument("--bets-out", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.store:
        store(a.store.resolve())
        return
    if a.cache is None:
        ap.error("--cache is required to build")
    t0 = time.time()
    last = a.last_season
    games, per, fg = load(a.cache)
    h = halves(games, per)
    cl = closing_lines(games, fg)
    team_games = games[["game_id", "season", "tip", "home_team", "away_team"]] \
        .merge(h, on="game_id", how="left").merge(cl, on="game_id", how="left")
    team_games = team_games[team_games["season"] <= last]
    print(f"games {len(team_games)}, with both halves {int(team_games.h1_home.notna().sum())}, "
          f"with a closing total {int(team_games.total_close.notna().sum())}")
    summary: dict = {"cut": CUT, "rule": "every game, no games-played wait; best book; edge > cut"}
    if a.quotes is not None:
        fg_asof = (load_asof_totals(a.asof_fg) if a.asof_fg is not None else
                   fg[(fg["market"] == "totals") & fg["bookmaker"].isin(ft.BOOKS)
                      & fg["total_line"].notna()])
        q = load_quotes(a.quotes, games)
        print(f"quotes {len(q)} on {q.game_id.nunique()} games; as-of full-game totals {len(fg_asof)}")
        maps, decided = [], {"floor": [], "none": []}
        for S in range(FIRST_REPLAY, last + 1):
            art = fit(team_games, S)
            maps.append({"season": S, "a": art["map"]["a"], "b": art["map"]["b"],
                         "n": art["map"]["n"], "alpha": art["tilt"]["alpha"],
                         "beta": art["tilt"]["beta"]})
            for lab, floor in (("floor", MIN_PRICE), ("none", None)):
                d = replay(art, games, team_games, fg_asof, q, min_price=floor)
                decided[lab].append(d)
                print(f"  {S} [{lab}]: a {art['map']['a']:+.6f} b {art['map']['b']:.6f} "
                      f"(n {art['map']['n']}); alpha {art['tilt']['alpha']:+.4f} beta "
                      f"{art['tilt']['beta']:.4f}; {len(d)} games decided, statuses "
                      f"{d.status.value_counts().to_dict()}", flush=True)
        summary["maps"] = maps
        for lab in ("floor", "none"):
            d = pd.concat(decided[lab], ignore_index=True)
            bets = d[d["status"] == "bets"]
            gr = grade(bets, team_games)
            key = "with_floor" if lab == "floor" else "without_floor"
            summary[key] = {"ungradable_bets": int(len(bets) - len(gr)), **summarize(gr, games)}
            if lab == "none" and a.research_bets is not None:
                rb = pd.read_parquet(a.research_bets)
                rb = rb[rb["cell"] == CELL]
                summary[key]["vs_research"] = compare(gr, rb)
            if lab == "floor" and a.research_scored is not None:
                summary[key]["vs_research"] = compare(gr, research_floor_bets(a.research_scored))
            if lab == "floor" and a.bets_out:
                d.to_parquet(a.bets_out, index=False)
        print("replay:", json.dumps({k: v for k, v in summary.items() if k != "maps"}, indent=1))
    art = fit(team_games, last + 1)
    art["built_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    art["command"] = (f"python -m scripts.ncaab_first_half_total_build --cache <copy of the three "
                      f"reads> --quotes <tip60 first-half totals> --asof-fg <later fg_odds parts> "
                      f"--last-season {last}")
    art["replay"] = summary
    out = a.out or ft.artifact_path(last + 1)
    out.write_text(json.dumps(art, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
