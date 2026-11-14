"""How often a tennis player retires after the first set, and what moves it.

Why it matters: DraftKings voids a moneyline bet on a player who retires after
the first set, where Pinnacle grades it a loss (models/tennis_common.py). The
rate is what that rule is worth on a bet. docs/sports/tennis.md, "How much the
option is worth", holds the table this prints.

READS tennis_archive_matches (Supabase) once, or the identical spooled archive
files with --spool. Tour-level matches only (men: Grand Slams, 1000s, the tour
level, Finals; women: Grand Slams, 1000s, 500s, 250s, Finals), from 2015,
walkovers out. WRITES nothing.

    python -m scripts.tennis_retirement_rates
    python -m scripts.tennis_retirement_rates --spool C:/Users/micha/tennis_research/spool
"""
from __future__ import annotations

import argparse
import glob

import pandas as pd

from models.tennis_common import from_archive_score
from models.tennis_ratings import run_elo

TOUR_LEVELS = {"ATP": {"G", "M", "A", "F"}, "WTA": {"G", "PM", "P", "I", "F"}}
FIRST_SEASON = 2015


def load(spool: str | None) -> pd.DataFrame:
    if spool:
        frames = []
        for tour, pre in (("ATP", "atp"), ("WTA", "wta")):
            fs = (glob.glob(f"{spool}/sackmann__{pre}__{pre}_matches_[12]*.csv")
                  + glob.glob(f"{spool}/sackmann__{pre}__{pre}_matches_q*.csv"))
            df = pd.concat([pd.read_csv(f, dtype={"tourney_level": str, "winner_id": str,
                                                  "loser_id": str}, low_memory=False) for f in fs])
            if tour == "WTA":
                df = df[~df.tourney_level.isin(["10", "15", "25"])]
            frames.append(df.assign(tour=tour))
        d = pd.concat(frames)
        d["tourney_date"] = pd.to_datetime(d.tourney_date.astype(str), format="%Y%m%d")
    else:
        from data.db import get_connection
        conn = get_connection()
        try:
            cols = ("tour", "tourney_id", "tourney_name", "surface", "tourney_level",
                    "tourney_date", "match_num", "winner_id", "loser_id", "winner_age",
                    "loser_age", "score", "best_of", "round", "minutes")
            rows = conn.execute(f"SELECT {', '.join(cols)} FROM tennis_archive_matches").fetchall()
        finally:
            conn.close()
        d = pd.DataFrame(rows, columns=cols)
        d["tourney_date"] = pd.to_datetime(d.tourney_date)
        d["winner_id"] = d.winner_id.astype(str)
        d["loser_id"] = d.loser_id.astype(str)
    return d.dropna(subset=["winner_id", "loser_id"])


def rated_tour_matches(d: pd.DataFrame) -> pd.DataFrame:
    out = []
    for tour, g in d.groupby("tour"):
        out.append(run_elo(g).assign(tour=tour))
    t = pd.concat(out)
    t["season"] = t.tourney_id.str[:4].astype(int)
    t = t[t.season >= FIRST_SEASON]
    res = t.score.astype(str).map(from_archive_score)
    t["wo"] = [r is not None and r.status == "walkover" for r in res]
    t["ret_after1"] = [r is not None and r.status == "retired" and r.first_set_complete for r in res]
    keep = pd.Series([lvl in TOUR_LEVELS[tour] for tour, lvl in zip(t.tour, t.tourney_level)],
                     index=t.index)
    return t[keep & ~t.wo]


def player_matches(t: pd.DataFrame) -> pd.DataFrame:
    t = t.sort_values(["tourney_date", "tourney_id", "match_num"])
    rows = []
    for side in ("winner", "loser"):
        rows.append(pd.DataFrame({
            "tour": t.tour, "pid": t[f"{side}_id"], "date": t.tourney_date, "tid": t.tourney_id,
            "minutes": t.minutes, "surface": t.surface, "age": t[f"{side}_age"],
            "best_of": t.best_of, "retired": t.ret_after1 & (side == "loser"),
            "order": t.match_num}))
    pm = pd.concat(rows).sort_values(["tour", "pid", "date", "order"]).reset_index(drop=True)
    g = pm.groupby(["tour", "pid"])
    pm["prev_minutes"] = g.minutes.shift(1)
    pm["same_event"] = g.tid.shift(1) == pm.tid
    pm["ret_date"] = pm.date.where(pm.retired)
    pm["last_ret"] = g.ret_date.transform(lambda s: s.shift(1).ffill())
    pm["days_since_ret"] = (pm.date - pm.last_ret).dt.days
    return pm


def report(t: pd.DataFrame, pm: pd.DataFrame) -> None:
    print(f"tour-level matches {len(t):,}, player-matches {len(pm):,}")
    for (tour, lvl), g in t.groupby(["tour", "tourney_level"]):
        if len(g) >= 500:
            print(f"  {tour} {lvl:3s} matches {len(g):6,}  per side {g.ret_after1.mean() / 2:.4f}")
    rr = t[t.ret_after1]
    print(f"  retiring player was the rating underdog in {(rr.p_winner > 0.5).mean():.3f} "
          f"of {len(rr):,}")
    cells = {
        "all": pm.index == pm.index,
        "previous match in the event over 210 min": pm.same_event & (pm.prev_minutes > 210),
        "previous match in the event 150-210 min": pm.same_event & pm.prev_minutes.between(150, 210, inclusive="right"),
        "previous match in the event under 90 min": pm.same_event & (pm.prev_minutes < 90),
        "retired after a set within 30 days": pm.days_since_ret <= 30,
        "no such retirement within 180 days": ~(pm.days_since_ret <= 180),
        "men's best of five": (pm.tour == "ATP") & (pm.best_of == 5),
        "aged 30 to 33": pm.age.between(30, 33, inclusive="left"),
        "aged under 22": pm.age < 22,
        "grass": pm.surface == "Grass",
    }
    for name, m in cells.items():
        x = pm[m]
        print(f"  {name:45s} {x.retired.mean():.4f}  n {len(x):7,}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spool")
    a = ap.parse_args(argv)
    t = rated_tour_matches(load(a.spool))
    report(t, player_matches(t))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
