"""Does the injury report carry anything the DraftKings line has not priced?

The one classic prop edge the eleven's features never touch is NEWS: a
player's own designation, and the designations of the teammates whose
absence would hand him volume. nflverse publishes the weekly report with a
modification timestamp, so it can be bounded at the row's snapshot rather
than read after the fact.

Per DraftKings row (the backtest dump plus market features), for the row's
player and his team in that week:

  own_q        the player himself is Questionable / Doubtful
  mates_out    teammates in the SAME position group reported Out / Doubtful
  mates_q      teammates in the same group reported Questionable
  qb_out       the team's QB carries any designation (pass-catchers only)

Each is graded as a one-sided bet at the DK price per season with an
interval, both directions, so the reader sees whether the book has already
moved the number. Reports modified AFTER the row's snapshot are dropped.

    python -m scripts.nfl_prop_injury_signal --feats <dk cache dir>
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from data import local_store
from data.ingestors.nfl_props_data_ingestor import norm_player_name
from scripts.nfl_prop_dk_signal_sweep import _bet, _grade

GROUP = {"WR": "REC", "TE": "REC", "RB": "RB", "FB": "RB", "QB": "QB",
         "LB": "DEF", "ILB": "DEF", "OLB": "DEF", "MLB": "DEF", "S": "DEF", "SS": "DEF",
         "FS": "DEF", "CB": "DEF", "DB": "DEF", "DE": "DEF", "DT": "DEF", "NT": "DEF", "DL": "DEF"}
MARKET_GROUP = {"pass": "QB", "rush": "RB", "rec": "REC", "receptions": "REC",
                "anytime": None, "tackles": "DEF", "sacks": "DEF"}


def load_injuries(seasons) -> pd.DataFrame:
    import nfl_data_py as nfl
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        inj = nfl.import_injuries(list(seasons))
    inj = inj[inj.game_type == "REG"].copy()
    inj["norm"] = inj.full_name.map(norm_player_name)
    inj["grp"] = inj.position.map(GROUP)
    inj["modified"] = pd.to_datetime(inj.date_modified, utc=True, errors="coerce")
    inj["status"] = inj.report_status.fillna("").str.lower()
    return inj[["season", "week", "team", "norm", "grp", "status", "modified"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--feats", required=True)
    a = ap.parse_args()
    rng = np.random.default_rng(42)
    local_store.activate()
    gl = local_store.read_table("nfl_player_game_log",
                                columns=["game_id", "norm_name", "team", "week", "pos"])
    gl = gl[["game_id", "norm_name", "team", "week", "pos"]].drop_duplicates(["game_id", "norm_name"])
    inj = load_injuries([2023, 2024, 2025])
    print(f"injury rows {len(inj)}, with timestamp {inj.modified.notna().mean():.0%}")

    for f in sorted(Path(a.feats).glob("nfl_prop_*.parquet")):
        if f.stem.endswith("_soft"):
            continue
        df = pd.read_parquet(f)
        df = df[df.actual != df.line].copy()
        df["norm"] = df.player.map(norm_player_name)
        df["ts"] = pd.to_datetime(df.snapshot_at, utc=True, format="mixed")
        df = df.merge(gl.rename(columns={"norm_name": "norm"}), on=["game_id", "norm"], how="left")
        stem = f.stem.replace("nfl_prop_", "")
        grp = MARKET_GROUP.get(stem.split("_")[0])
        own_q, mates_out, mates_q, qb_out = [], [], [], []
        for r in df.itertuples(index=False):
            rep = inj[(inj.season == r.season) & (inj.week == r.week) & (inj.team == r.team)]
            rep = rep[rep.modified.isna() | (rep.modified <= r.ts)]
            me = rep[rep.norm == r.norm]
            own_q.append(int(me.status.isin(["questionable", "doubtful"]).any()))
            mates = rep[(rep.norm != r.norm) & (rep.grp == grp)] if grp else rep.iloc[0:0]
            mates_out.append(int(mates.status.isin(["out", "doubtful"]).sum()))
            mates_q.append(int((mates.status == "questionable").sum()))
            qb_out.append(int((rep.grp == "QB").any()) if grp == "REC" else 0)
        df["own_q"], df["mates_out"], df["mates_q"], df["qb_out"] = own_q, mates_out, mates_q, qb_out
        print(f"\n=== {stem}  rows {len(df)}  own_q {df.own_q.mean():.1%}  "
              f"mates_out>0 {(df.mates_out > 0).mean():.1%}  mates_q>0 {(df.mates_q > 0).mean():.1%}  "
              f"qb flagged {(df.qb_out > 0).mean():.1%}")
        print(f"{'signal':28s} {'seas':>4} {'bets':>5} {'win%':>6} {'units':>9} {'ROI':>8}  90% CI")
        sigs = {
            "own Q/D -> under": -df.own_q,
            "own Q/D -> over": df.own_q,
            "mate(s) out -> over": (df.mates_out > 0).astype(int),
            "mate(s) out -> under": -(df.mates_out > 0).astype(int),
            "mate(s) Q -> over": (df.mates_q > 0).astype(int),
            "mate(s) Q -> under": -(df.mates_q > 0).astype(int),
            "QB flagged -> under": -(df.qb_out > 0).astype(int),
            "QB flagged -> over": (df.qb_out > 0).astype(int),
        }
        for name, side in sigs.items():
            for season, g in df.groupby("season"):
                print(f"{name:28s} {season:>4} {_grade(_bet(g, side.loc[g.index]), rng)}")


if __name__ == "__main__":
    main()
