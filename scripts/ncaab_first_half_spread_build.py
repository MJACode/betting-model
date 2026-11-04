"""Build the NCAAB first-half spread model's frozen numbers (models/ncaab_first_half_spread.py),
and replay it on 2023-24 .. 2025-26 through the card's own functions.

Writes models/saved/ncaab_first_half_spread_<season>.json: the first-half map
a + b x M (one least-squares fit of the first-half home margin on the closing
full-game consensus, 2021 through the last finished season), the margin
table's training sample (closing consensus, first-half margin, count), the
team term's tilt line alpha + beta x Mc and its shrinkage, and every team's
last-season residual sum and count.

THE REPLAY. For each season S of 2024..last, the same numbers are fitted on
2021..S-1 only (exactly as the research fitted them, fh_score.py and
fh_prep.py), and every game with a bought first-half close is decided through
models.ncaab_first_half_spread: the as-of full-game consensus at the purchase
stamp (asof_consensus), the team term as of the stamp (team_game_residuals,
team_effects), every bettable book's quote priced (quote_offers), the best
offer (best_offer: largest edge, ties to the alphabetically first book), bet
when its edge is above the cut. The purchase stamp (tip minus 10 minutes)
stands in for the live decision fetch's instant. Graded at the quote's own
price, to win one unit, risk capped at 3 (stake_for). --research compares the
bets game by game with the research's own scored quotes.

    python -m scripts.ncaab_first_half_spread_build --cache DIR [--last-season 2026]
        [--out PATH] [--research SCORED_PARQUET] [--bets-out PATH]
    python -m scripts.ncaab_first_half_spread_build --store ABSOLUTE_PATH   # copy it into model_artifacts

DIR holds read-only copies of four Supabase reads, as parquet:
  games.parquet                SELECT game_id, season, game_date, commence_time, home_team,
                               away_team, home_score, away_score FROM games WHERE sport = 'NCAAB'
  ncaab_period_scores.parquet  SELECT game_id, period, home_points, away_points
                               FROM ncaab_period_scores                     (season by season)
  fg_odds.parquet              SELECT game_id, market, bookmaker, snapshot_at, spread_home,
                               total_line FROM odds WHERE market IN ('spreads', 'totals')
                               AND snapshot_type IS DISTINCT FROM 'in_play'  (NCAAB games, by
                               game_id chunks)
  fh_quotes.parquet            SELECT game_id, market, bookmaker, snapshot_at, spread_home,
                               home_price, away_price, total_line, over_price, under_price
                               FROM odds WHERE market IN ('h2h_h1', 'spreads_h1', 'totals_h1')
                               AND source = 'odds_api_ncaab_derivative_close'
Every row is in Supabase. The 2026-11-02 build read the copies the research
took that day (games, odds and the first-half purchase); its period scores were
read from ncaab_period_scores the same day and agree with the research's ESPN
halves on every one of the 35,307 games it graded.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.ncaab_first_half_spread as fh  # noqa: E402

FIRST_SEASON = 2021      # the first season with stored closing full-game lines
FIRST_REPLAY = 2024      # the first season with a bought first-half close
CUT = 0.02
K_MARGIN = 782.2         # the research's tilt_reliability.csv (2021-2023), frozen
W_PREV = 0.5
CLOSE_SOURCE = "odds_api_ncaab_derivative_close"


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
    q = pd.read_parquet(cache / "fh_quotes.parquet")
    q["ts"] = _ts(q["snapshot_at"])
    return g, per, fg, q


def halves(g: pd.DataFrame, per: pd.DataFrame) -> pd.DataFrame:
    """Per game: both halves, the card's rule (fh.valid_halves)."""
    return fh.valid_halves(per, g[["game_id", "home_score", "away_score"]])


def closing_lines(g: pd.DataFrame, fg: pd.DataFrame) -> pd.DataFrame:
    """Per game: spread_close and total_close, each the median over the
    bettable books of the book's last line at or before the tip (fh.asof_consensus)."""
    cut = g[["game_id", "tip"]].rename(columns={"tip": "cutoff"}).dropna()
    out = g[["game_id"]].copy()
    for mk, col, name in (("spreads", "spread_home", "spread_close"),
                          ("totals", "total_line", "total_close")):
        rows = fg[fg["market"] == mk][["game_id", "bookmaker", "ts", col]].rename(columns={col: "line"})
        c = fh.asof_consensus(rows, cut, market=mk)
        out = out.merge(c.rename(columns={"cons": name, "nb": name + "_nb"}), on="game_id", how="left")
    return out


# ── the fit ──────────────────────────────────────────────────────────────────

def fit(team_games: pd.DataFrame, season: int) -> dict:
    """The artifact for `season`: every number fitted on 2021..season-1."""
    tr = team_games[team_games["season"].between(FIRST_SEASON, season - 1)
                    & team_games["h1_home"].notna()]
    tr = tr.assign(h1_margin=tr["h1_home"] - tr["h1_away"])
    x = tr.dropna(subset=["spread_close"])
    b, a = np.polyfit(-x["spread_close"].astype(float), x["h1_margin"].astype(float), 1)
    t = tr.dropna(subset=["spread_close", "total_close"])
    sample = (t.groupby(["spread_close", "h1_margin"]).size().reset_index(name="count")
              .sort_values(["spread_close", "h1_margin"]))
    tg = tr.dropna(subset=["h2_home", "h2_away", "spread_close", "total_close"])
    dm = (tg["h1_home"] - tg["h1_away"]) - (tg["h2_home"] - tg["h2_away"])
    beta, alpha = np.polyfit(-tg["spread_close"].astype(float), dm.astype(float), 1)
    res = fh.team_game_residuals(team_games[team_games["season"] == season - 1], alpha, beta)
    return {
        "kind": fh.ARTIFACT_KIND, "model_id": fh.MODEL_ID,
        "season": int(season), "prior_season": int(season - 1),
        "books": list(fh.BOOKS), "cut": CUT,
        "map": {"a": float(a), "b": float(b), "n": int(len(x)),
                "train_seasons": [FIRST_SEASON, int(season - 1)],
                "what": "first-half home margin = a + b x M, M = minus the closing full-game "
                        "consensus spread (median of the bettable books' last pre-tip spread)"},
        "table": {"grid": list(fh.GRID), "support": list(fh.SUPPORT), "h0": fh.H0, "nmin": fh.NMIN,
                  "n": int(len(t)),
                  "what": "rows [closing consensus home spread, first-half home margin, games]; "
                          "the table's key is a + b x (minus the spread)",
                  "sample": [[float(r.spread_close), int(r.h1_margin), int(r.count)]
                             for r in sample.itertuples(index=False)]},
        "tilt": {"alpha": float(alpha), "beta": float(beta), "k": K_MARGIN, "w_prev": W_PREV,
                 "game_len_h": 2.5, "n": int(len(tg)),
                 "train_seasons": [FIRST_SEASON, int(season - 1)],
                 "what": "dm = (h1 margin - period-2 margin) - (alpha + beta x Mc); tau = (this "
                         "season's ended dm + w_prev x last season's) / (games + w_prev x last "
                         "season's games + k)"},
        "prior_team_sums": fh.prior_sums(res, season - 1),
    }


# ── the replay ───────────────────────────────────────────────────────────────

def replay(art: dict, games: pd.DataFrame, team_games: pd.DataFrame, fg: pd.DataFrame,
           q: pd.DataFrame, cut: float = CUT) -> pd.DataFrame:
    """Decide every game of art['season'] that has a bought first-half close,
    through the model's own functions. One row per decided game."""
    S = int(art["season"])
    art = fh.with_table(art)
    gS = games[games["season"] == S].set_index("game_id")
    qq = q[q["game_id"].isin(gS.index) & q["bookmaker"].isin(fh.BOOKS)].copy()
    qq = qq.merge(gS[["tip"]], left_on="game_id", right_index=True)
    qq = qq[qq["ts"] <= qq["tip"]]
    # The stamp: the purchase's snapshot time of the game's first-half rows at
    # the bettable books (fh_prep.py: one stamp per game, every book's the same).
    stamp = qq.groupby("game_id")["ts"].max().rename("stamp").reset_index()
    sp = qq[qq["market"] == fh.MARKET]
    # FG consensus at the stamp.
    rows = fg[fg["market"] == "spreads"][["game_id", "bookmaker", "ts", "spread_home"]] \
        .rename(columns={"spread_home": "line"})
    cons = fh.asof_consensus(rows[rows["game_id"].isin(stamp["game_id"])],
                             stamp.rename(columns={"stamp": "cutoff"}), market="spreads")
    cons = cons.set_index("game_id")
    res = fh.team_game_residuals(team_games[team_games["season"] == S],
                                 art["tilt"]["alpha"], art["tilt"]["beta"])
    targets = stamp.merge(gS[["home_team", "away_team"]], left_on="game_id", right_index=True)
    tau = fh.team_effects(res, S, art["prior_team_sums"], targets,
                          art["tilt"]["k"], art["tilt"]["w_prev"]).set_index("game_id")
    by_game = {gid: z for gid, z in sp.groupby("game_id")}
    out = []
    for r in targets.itertuples(index=False):
        quotes = by_game.get(r.game_id, sp.iloc[0:0])
        fgc = ({"cons": float(cons.at[r.game_id, "cons"]), "nb": int(cons.at[r.game_id, "nb"])}
               if r.game_id in cons.index else None)
        t = tau.loc[r.game_id].to_dict() if r.game_id in tau.index else None
        d = fh.decide(r.game_id, quotes, fgc, t, art, cut)
        row = {"game_id": r.game_id, "season": S, "stamp": r.stamp, "status": d.status,
               "mu": d.mu, "fg_spread": d.fg_spread, "fg_books": d.fg_books,
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
    cover = (x["h1_home"] - x["h1_away"]) + x["line"]
    res = np.where(x["side"] == "home", cover, -cover)
    d = fh.dec(x["price"])
    risk = np.minimum(1.0 / (d - 1.0), 3.0)
    x["risk"] = risk
    x["units"] = np.select([res > 0, res < 0], [risk * (d - 1.0), -risk], 0.0)
    x["result"] = np.select([res > 0, res < 0], ["W", "L"], "P")
    return x


def summarize(gr: pd.DataFrame) -> dict:
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
        ev = gr["prob"] * fh.dec(gr["price"]) - 1
        out["min_ev"] = round(float(ev.min()), 4)
        out["median_ev"] = round(float(ev.median()), 4)
        out["books"] = {k: int(v) for k, v in gr["book"].value_counts().items()}
    return out


def compare(bets: pd.DataFrame, research: Path, cut: float = CUT) -> dict:
    """Game by game against the research's scored quotes (family A,
    spreads_h1, close, best book, edge > cut, every game)."""
    sc = pd.read_parquet(research)
    sc = sc[(sc.family == "A") & (sc.fmarket == "spreads_h1") & (sc.fsnap == "close")]
    best = sc.sort_values(["edge", "book"], ascending=[False, True]).drop_duplicates("game_id")
    rb = best[best.edge > cut].set_index("game_id")
    mine = bets.set_index("game_id")
    both = rb.index.intersection(mine.index)
    only_r, only_m = rb.index.difference(mine.index), mine.index.difference(rb.index)
    side_r = np.where(rb.loc[both, "side"] == 1, "home", "away")
    same = ((side_r == mine.loc[both, "side"].values)
            & (rb.loc[both, "book"].values == mine.loc[both, "book"].values)
            & np.isclose(rb.loc[both, "line"].values, mine.loc[both, "line"].values)
            & np.isclose(rb.loc[both, "price"].values, mine.loc[both, "price"].values))
    edge_gap = np.abs(rb.loc[both, "edge"].values - mine.loc[both, "edge"].values)
    return {"research_bets": int(len(rb)), "replay_bets": int(len(mine)),
            "in_both": int(len(both)), "identical_game_side_book_line_price": int(same.sum()),
            "only_research": sorted(only_r.tolist())[:20], "n_only_research": int(len(only_r)),
            "only_replay": sorted(only_m.tolist())[:20], "n_only_replay": int(len(only_m)),
            "max_edge_gap": float(edge_gap.max()) if len(both) else None}


def store(path: Path) -> None:
    """Copy the artifact into Supabase's model_artifacts (the trainer's restore
    source, as the NBA first-half build does). A production write: run it
    deliberately, after the merge, never from a test."""
    from data.db import get_connection
    from models.trainer import _store_artifact
    conn = get_connection()
    try:
        _store_artifact(conn, fh.MODEL_ID, path.stem.split(fh.MODEL_ID + "_")[-1], path)
    finally:
        conn.close()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--store", type=Path, help="copy this artifact into model_artifacts")
    ap.add_argument("--cache", type=Path)
    ap.add_argument("--last-season", type=int, default=2026)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--research", type=Path, default=None,
                    help="the research's cache/scored.parquet, to compare the bets game by game")
    ap.add_argument("--bets-out", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.store:
        store(a.store.resolve())
        return
    if a.cache is None:
        ap.error("--cache is required to build")
    t0 = time.time()
    last = a.last_season
    games, per, fg, q = load(a.cache)
    h = halves(games, per)
    cl = closing_lines(games, fg)
    team_games = games[["game_id", "season", "tip", "home_team", "away_team"]] \
        .merge(h, on="game_id", how="left").merge(cl, on="game_id", how="left")
    team_games = team_games[team_games["season"] <= last]
    print(f"games {len(team_games)}, with both halves {int(team_games.h1_home.notna().sum())}, "
          f"with a closing spread {int(team_games.spread_close.notna().sum())}")
    decided, bets_all = [], []
    for S in range(FIRST_REPLAY, last + 1):
        art = fit(team_games, S)
        d = replay(art, games, team_games, fg, q[q["source"] == CLOSE_SOURCE] if "source" in q else q)
        decided.append(d)
        b = d[d["status"] == "bets"]
        bets_all.append(b)
        print(f"  {S}: a {art['map']['a']:+.4f} b {art['map']['b']:.4f} (n {art['map']['n']}); "
              f"alpha {art['tilt']['alpha']:+.4f} beta {art['tilt']['beta']:.4f}; "
              f"{len(d)} games decided, {len(b)} bets, statuses {d.status.value_counts().to_dict()}",
              flush=True)
    bets = pd.concat(bets_all, ignore_index=True)
    gr = grade(bets, team_games)
    summary = {"cut": CUT, "rule": "every game, no games-played wait; best book; edge > cut",
               "ungradable_bets": int(len(bets) - len(gr)), **summarize(gr)}
    if a.research:
        summary["vs_research"] = compare(gr, a.research)
    print("replay:", json.dumps(summary, indent=1))
    if a.bets_out:
        pd.concat(decided, ignore_index=True).to_parquet(a.bets_out, index=False)
    art = fit(team_games, last + 1)
    art["built_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    art["command"] = (f"python -m scripts.ncaab_first_half_spread_build --cache <copy of the four "
                      f"reads> --last-season {last}")
    art["replay"] = summary
    out = a.out or fh.artifact_path(last + 1)
    out.write_text(json.dumps(art, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
