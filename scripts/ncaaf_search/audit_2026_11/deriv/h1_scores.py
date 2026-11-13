"""Half-time scores for NCAAF games, built from the stored play-by-play (`ncaaf_plays`).

There is no NCAAF period-score table. `ncaaf_plays` (CFBD, pulled on the worker by the
`ncaaf_pbp_pull` job) carries the period and both teams' scores on every play, so a game's
half-time score is each team's highest score on a play of period 1 or 2. Checked two ways
before it is used: the same rule over ALL periods must reproduce the stored final, and a
sample of dates is compared with ESPN's quarter scores (h1_check_espn.py).

Reads the mirror by default; `--plays PATH` reads a parquet of plays pulled some other way.
Writes CACHE/h1_scores.parquet: one row per scored `games` row that a play-by-play game matched.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR  # noqa: E402

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)


def load_plays(path=None) -> pd.DataFrame:
    cols = ["play_id", "game_id_cfbd", "period", "clock_minutes", "clock_seconds", "offense", "defense",
            "home", "away", "offense_score", "defense_score", "season", "week", "season_type", "wallclock"]
    src = Path(path) if path else MIRROR / "public.ncaaf_plays"
    p = ds.dataset(str(src), format="parquet", exclude_invalid_files=True).to_table(columns=cols).to_pandas()
    for c in ("period", "offense_score", "defense_score", "season", "week"):
        p[c] = pd.to_numeric(p[c], errors="coerce")
    return p


def per_game(p: pd.DataFrame) -> pd.DataFrame:
    """One row per CFBD game, with the half-time score read two independent ways.

    A play row carries the score AFTER the play. Rows are not reliably ordered by id (a field goal at
    0:00 of the second period can carry an id from early in the period) and a score can appear and be
    taken back (a touchdown overturned on review), so a maximum over the half is wrong. The two reads:
      end2   the score on the plays with the least time left in period 2
      start3 the score on the plays with the most time left in period 3 (the lower one, so an
             opening-kickoff touchdown does not count)
    A half-time score is used only when the two agree.
    """
    p = p[p.period.notna() & p.offense_score.notna() & p.defense_score.notna()].copy()
    p = p[(p.offense == p.home) | (p.offense == p.away)].copy()
    p["hs"] = np.where(p.offense == p.home, p.offense_score, p.defense_score)
    p["as_"] = np.where(p.offense == p.home, p.defense_score, p.offense_score)
    p["left"] = pd.to_numeric(p.clock_minutes, errors="coerce").fillna(0) * 60 + \
        pd.to_numeric(p.clock_seconds, errors="coerce").fillna(0)
    p["day"] = pd.to_datetime(p.wallclock, utc=True, errors="coerce")
    key = ["game_id_cfbd", "season", "week", "season_type", "home", "away"]

    def edge(period, least):
        x = p[p.period == period]
        pick = x.groupby("game_id_cfbd").left.transform("min" if least else "max")
        x = x[x.left == pick]
        how = "max" if least else "min"
        return x.groupby("game_id_cfbd").agg(h=("hs", how), a=("as_", how))

    e2, s3, s2 = edge(2, True), edge(3, False), edge(2, False)
    lastp = p.groupby("game_id_cfbd").period.transform("max")
    x = p[p.period == lastp]
    x = x[x.left == x.groupby("game_id_cfbd").left.transform("min")]
    fin = x.groupby("game_id_cfbd").agg(end_home=("hs", "max"), end_away=("as_", "max"))
    allp = p.groupby(key).agg(mx_home=("hs", "max"), mx_away=("as_", "max"), max_period=("period", "max"),
                              n_plays=("hs", "size"), day=("day", "median")).reset_index()
    out = (allp.merge(e2.rename(columns={"h": "e2_home", "a": "e2_away"}), on="game_id_cfbd", how="left")
           .merge(s3.rename(columns={"h": "s3_home", "a": "s3_away"}), on="game_id_cfbd", how="left")
           .merge(s2.rename(columns={"h": "q1_home", "a": "q1_away"}), on="game_id_cfbd", how="left")
           .merge(fin, on="game_id_cfbd", how="left"))
    out["h1_agree"] = (out.e2_home == out.s3_home) & (out.e2_away == out.s3_away)
    return out


def attach(pg: pd.DataFrame, g: pd.DataFrame) -> pd.DataFrame:
    """Match each play-by-play game to the scored `games` row with the same season and the same two
    schools; a rematch is told apart by the stored final."""
    sc = g[g.margin.notna() & g.twin_of.isna()].copy()
    sc["home_score"] = pd.to_numeric(sc.home_score)
    sc["away_score"] = pd.to_numeric(sc.away_score)
    idx = {}
    for r in sc.itertuples(index=False):
        idx.setdefault((int(r.season), frozenset((r.home_team, r.away_team))), []).append(r)
    rows, why = [], {"no games row": 0, "rematch not told apart": 0, "matched": 0, "matched flipped": 0}
    for r in pg.itertuples(index=False):
        cands = idx.get((int(r.season), frozenset((r.home, r.away))), [])
        if not cands:
            why["no games row"] += 1
            continue

        def fin_of(c):
            return (c.home_score, c.away_score) if c.home_team == r.home else (c.away_score, c.home_score)
        if len(cands) > 1:
            ends = {(r.end_home, r.end_away), (r.mx_home, r.mx_away)}
            cands = [c for c in cands if fin_of(c) in ends]
            if len(cands) != 1:
                why["rematch not told apart"] += 1
                continue
        c = cands[0]
        flip = c.home_team != r.home
        why["matched flipped" if flip else "matched"] += 1
        fh, fa = fin_of(c)

        def o(h, a):
            return (a, h) if flip else (h, a)
        h1h, h1a = o(r.e2_home, r.e2_away)
        q1h, q1a = o(r.q1_home, r.q1_away)
        rows.append(dict(game_id=c.game_id, season=int(r.season), game_id_cfbd=r.game_id_cfbd,
                         h1_home=h1h, h1_away=h1a, q1_home=q1h, q1_away=q1a,
                         fin_home=c.home_score, fin_away=c.away_score, max_period=r.max_period,
                         h1_agree=bool(r.h1_agree), end_is_final=(r.end_home, r.end_away) == (fh, fa),
                         max_is_final=(r.mx_home, r.mx_away) == (fh, fa), n_plays=r.n_plays))
    print("play-by-play games:", len(pg), "|", why)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plays", help="a parquet of plays instead of the mirror's table")
    a = ap.parse_args()
    p = load_plays(a.plays)
    print("plays", len(p), "| seasons", sorted(p.season.dropna().unique().astype(int).tolist()))
    pg = per_game(p)
    print(pg.groupby("season").agg(games=("game_id_cfbd", "size"), two_reads_agree=("h1_agree", "sum"),
                                   plays=("n_plays", "median")).to_string())
    g = pd.read_parquet(CACHE / "g.parquet")
    h = attach(pg, g)
    h["ok"] = h.h1_agree & h.h1_home.notna() & (h.h1_home <= h.fin_home) & (h.h1_away <= h.fin_away)
    print(h.groupby("season").agg(matched=("game_id", "size"), usable=("ok", "sum"),
                                  end_is_final=("end_is_final", "sum"), max_is_final=("max_is_final", "sum")).to_string())
    h = h[h.ok].drop(columns=["ok"])
    h["h1_margin"] = h.h1_home - h.h1_away
    h["h1_total"] = h.h1_home + h.h1_away
    print("half-time: mean total", round(h.h1_total.mean(), 2), "| mean home margin", round(h.h1_margin.mean(), 2),
          "| tied at the half", round((h.h1_margin == 0).mean(), 4),
          "| first-half share of points", round(h.h1_total.sum() / (h.fin_home + h.fin_away).sum(), 4))
    h.to_parquet(CACHE / "h1_scores.parquet")
    print("wrote", CACHE / "h1_scores.parquet", len(h))


if __name__ == "__main__":
    main()
