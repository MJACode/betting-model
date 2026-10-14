"""Expected goals per team-game and per goalie-game, from nhl_shot_events.

Tables, definitions and the reason they exist:
data/migrations/add_nhl_xg_aggregates.sql.

Sums the shot frame data/nhl_xg.py already read from Supabase -- the 1.2M-row
table is not read a second time -- with the xG it stored. Before summing, the
local xG is checked against what Supabase holds, season by season (one grouped
query): a sum built from numbers that never landed would be a table of fiction.
nhl_team_game_log and nhl_goalie_game_log (small) supply the games and who
started; the goalie log's goals and shots against are a second check on the
goalie rows. Written 2,000 rows a batch under the ingest's load gate; a rebuild
overwrites (upsert on the key).

    python -m data.nhl_xg_aggregates             # build + checks, writes nothing
    python -m data.nhl_xg_aggregates --apply
"""
from __future__ import annotations

import argparse
import time

import numpy as np
import pandas as pd
from loguru import logger

from data.db import ConnectionLost, get_connection
from data.ingestors.nhl_shot_events import (BATCH_PAUSE, LOAD_CHECK_EVERY, UNBLOCKED,
                                            WRITE_BATCH, wait_for_quiet_db)
from data.nhl_xg import WORK_DIR, _obj, load_shot_frame

SOURCE = "nhl_shot_events"
FIVE_ON_FIVE = "1551"

TEAM_COLS = ("nhl_game_id", "team", "game_id", "season", "game_type", "game_date",
             "opponent", "is_home", "xgf", "xga", "xgf_5v5", "xga_5v5", "ff", "fa",
             "ff_5v5", "fa_5v5", "gf", "ga", "gf_5v5", "ga_5v5", "xg_unscored_for",
             "xg_unscored_against", "xg_model_version", "source")
GOALIE_COLS = ("nhl_game_id", "goalie_id", "game_id", "season", "game_type", "game_date",
               "team", "opponent", "is_home", "started", "unblocked_faced", "sog_faced",
               "goals_allowed", "xg_faced", "gsax", "unblocked_faced_5v5",
               "goals_allowed_5v5", "xg_faced_5v5", "gsax_5v5", "xg_unscored",
               "xg_model_version", "source")


def _read(sql: str, cols: list[str], params=None) -> pd.DataFrame:
    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        conn.commit()
    finally:
        conn.close()
    return pd.DataFrame(rows, columns=cols)


def stored_xg_by_season() -> pd.DataFrame:
    return _read("SELECT season, xg_model_version, count(*), sum(xg) FROM nhl_shot_events "
                 "WHERE xg IS NOT NULL GROUP BY season, xg_model_version ORDER BY season",
                 ["season", "version", "n", "xg_sum"])


def attempts_frame() -> tuple[pd.DataFrame, str]:
    """Unblocked, non-shootout attempts with their xG, checked against Supabase."""
    frame = load_shot_frame()
    pred = pd.read_parquet(WORK_DIR / "xg_pred.parquet")
    df = frame.merge(pred, on=["nhl_game_id", "event_id"], how="left", validate="1:1")
    stored = stored_xg_by_season()
    versions = stored["version"].unique()
    if len(versions) != 1:
        raise RuntimeError(f"stored xG carries {len(versions)} model versions: {versions}")
    local = df[df["xg"].notna()].groupby("season")["xg"].agg(["size", "sum"])
    chk = stored.set_index("season").join(local)
    chk["n_ok"] = chk["n"] == chk["size"]
    chk["sum_ok"] = (chk["xg_sum"] - chk["sum"]).abs() < 1e-6 * chk["n"]
    logger.info("stored vs local xG by season:\n" + chk.to_string())
    if not (chk["n_ok"].all() and chk["sum_ok"].all()) or len(chk) != len(local):
        raise RuntimeError("the xG stored in Supabase is not the xG in hand -- not summing it")
    kind = _obj(df["event_type"])
    keep = kind.isin(UNBLOCKED) & (_obj(df["period_type"]) != "SO")
    out = df[keep.astype(bool)].copy()
    out["goal"] = (_obj(out["event_type"]) == "goal").astype(int)
    out["on_goal"] = _obj(out["event_type"]).isin(("shot-on-goal", "goal")).astype(int)
    out["is_5v5"] = (_obj(out["situation_code"]) == FIVE_ON_FIVE).astype(int)
    out["unscored"] = out["xg"].isna().astype(int)
    out["xg0"] = out["xg"].fillna(0.0)
    return out, str(versions[0])


def build_team_rows(att: pd.DataFrame, log: pd.DataFrame, version: str) -> pd.DataFrame:
    a = att.assign(xg5=att["xg0"] * att["is_5v5"], g5=att["goal"] * att["is_5v5"])
    by = a.groupby(["nhl_game_id", "shooting_team"]).agg(
        xg=("xg0", "sum"), xg5=("xg5", "sum"), f=("goal", "size"), f5=("is_5v5", "sum"),
        g=("goal", "sum"), g5=("g5", "sum"), uns=("unscored", "sum"))
    by.index = by.index.set_names(["nhl_game_id", "team"])
    t = log.set_index(["nhl_game_id", "team"])
    mine = by.reindex(t.index).fillna(0)
    theirs = by.reindex(pd.MultiIndex.from_arrays(
        [t.index.get_level_values(0), t["opponent"]])).fillna(0)
    theirs.index = t.index
    out = t.reset_index()[["nhl_game_id", "team", "game_id", "season", "game_type",
                           "game_date", "opponent", "is_home"]].copy()
    for col, src, frame in (("xgf", "xg", mine), ("xga", "xg", theirs),
                            ("xgf_5v5", "xg5", mine), ("xga_5v5", "xg5", theirs),
                            ("ff", "f", mine), ("fa", "f", theirs),
                            ("ff_5v5", "f5", mine), ("fa_5v5", "f5", theirs),
                            ("gf", "g", mine), ("ga", "g", theirs),
                            ("gf_5v5", "g5", mine), ("ga_5v5", "g5", theirs),
                            ("xg_unscored_for", "uns", mine),
                            ("xg_unscored_against", "uns", theirs)):
        out[col] = frame[src].to_numpy()
    for c in ("ff", "fa", "ff_5v5", "fa_5v5", "gf", "ga", "gf_5v5", "ga_5v5",
              "xg_unscored_for", "xg_unscored_against"):
        out[c] = out[c].astype(int)
    out["xg_model_version"], out["source"] = version, SOURCE
    return out[list(TEAM_COLS)]


def build_goalie_rows(att: pd.DataFrame, log: pd.DataFrame, goalie_log: pd.DataFrame,
                      version: str) -> pd.DataFrame:
    a = att[att["goalie_id"].notna()].copy()
    a["goalie_id"] = a["goalie_id"].astype("int64")
    a = a.assign(xg5=a["xg0"] * a["is_5v5"], g5=a["goal"] * a["is_5v5"])
    by = a.groupby(["nhl_game_id", "goalie_id"]).agg(
        shooters=("shooting_team", "nunique"), shooting_team=("shooting_team", "first"),
        unblocked_faced=("goal", "size"), sog_faced=("on_goal", "sum"),
        goals_allowed=("goal", "sum"), xg_faced=("xg0", "sum"),
        unblocked_faced_5v5=("is_5v5", "sum"), goals_allowed_5v5=("g5", "sum"),
        xg_faced_5v5=("xg5", "sum"), xg_unscored=("unscored", "sum")).reset_index()
    two = by[by["shooters"] > 1]
    if len(two):
        logger.warning(f"{len(two)} goalie-games face shots from both teams: "
                       f"{two[['nhl_game_id', 'goalie_id']].head(10).values.tolist()}")
    # The goalie's team is the opponent of the team shooting at him.
    lg = log.rename(columns={"team": "shooting_team", "opponent": "team",
                             "is_home": "shooter_is_home"})
    out = by.merge(lg[["nhl_game_id", "shooting_team", "team", "shooter_is_home", "game_id",
                       "season", "game_type", "game_date"]],
                   on=["nhl_game_id", "shooting_team"], how="left", validate="m:1")
    out["opponent"] = out["shooting_team"]
    out["is_home"] = 1 - out["shooter_is_home"]
    gl = goalie_log.rename(columns={"player_id": "goalie_id"})
    out = out.merge(gl[["nhl_game_id", "goalie_id", "started", "goals_against",
                        "shots_against"]], on=["nhl_game_id", "goalie_id"], how="left",
                    validate="1:1")
    out["gsax"] = out["xg_faced"] - out["goals_allowed"]
    out["gsax_5v5"] = out["xg_faced_5v5"] - out["goals_allowed_5v5"]
    out["xg_model_version"], out["source"] = version, SOURCE
    return out


def report(team: pd.DataFrame, goalie: pd.DataFrame, log: pd.DataFrame) -> None:
    t = team.merge(log[["nhl_game_id", "team", "goals_for"]], on=["nhl_game_id", "team"])
    by = t.groupby("season").agg(team_games=("team", "size"), xgf=("xgf", "sum"),
                                 gf=("gf", "sum"),
                                 xgf_5v5=("xgf_5v5", "sum"), gf_5v5=("gf_5v5", "sum"),
                                 unscored=("xg_unscored_for", "sum"))
    by["gf_vs_log"] = t.assign(ok=t["gf"] == t["goals_for"]).groupby("season")["ok"].mean().round(4)
    by["xgf_over_gf"] = (by["xgf"] / by["gf"]).round(4)
    logger.info("team-game sums by season (gf_vs_log = share of team-games whose "
                "play-by-play goals equal the log's goals_for):\n" + by.round(1).to_string())

    g = goalie.copy()
    has = g["goals_against"].notna()
    chk = g[has].assign(ga_ok=lambda d: d["goals_allowed"] == d["goals_against"],
                        sa_ok=lambda d: d["sog_faced"] == d["shots_against"])
    gb = chk.groupby("season").agg(goalie_games=("ga_ok", "size"),
                                   goals_match=("ga_ok", "mean"),
                                   shots_match=("sa_ok", "mean")).round(4)
    gb["not_in_goalie_log"] = g[~has].groupby("season").size()
    gb["starts"] = g[g["started"] == 1].groupby("season").size()
    logger.info("goalie-game rows vs nhl_goalie_game_log (goals_against, shots_against):\n"
                + gb.fillna(0).to_string())
    worst = chk[~chk["ga_ok"] | ~chk["sa_ok"]].head(12)
    logger.info("goalie mismatches (first 12):\n" + worst[[
        "nhl_game_id", "goalie_id", "season", "goals_allowed", "goals_against",
        "sog_faced", "shots_against"]].to_string(index=False))


def write(table: str, key: tuple[str, ...], cols: tuple[str, ...], df: pd.DataFrame) -> int:
    sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in key)
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) "
           f"VALUES ({', '.join(f'%({c})s' for c in cols)}) "
           f"ON CONFLICT ({', '.join(key)}) DO UPDATE SET {sets}, built_at = NOW()")
    recs = df[list(cols)].astype(object).where(df[list(cols)].notna(), None)
    rows = [{k: (v.item() if isinstance(v, np.generic) else v) for k, v in r.items()}
            for r in recs.to_dict("records")]
    conn = get_connection()
    try:
        for b, i in enumerate(range(0, len(rows), WRITE_BATCH)):
            chunk = rows[i:i + WRITE_BATCH]
            if b % LOAD_CHECK_EVERY == 0:
                wait_for_quiet_db(conn)
            try:
                conn.executemany(sql, chunk)
                conn.commit()
            except ConnectionLost:
                logger.warning(f"{table}: connection lost mid-batch -- re-running it")
                conn.executemany(sql, chunk)
                conn.commit()
            time.sleep(BATCH_PAUSE)
    finally:
        conn.close()
    logger.success(f"{table}: {len(rows):,} rows written")
    return len(rows)


def run(apply: bool) -> None:
    att, version = attempts_frame()
    log = _read("SELECT nhl_game_id, team, opponent, is_home, game_id, season, game_type, "
                "game_date, goals_for FROM nhl_team_game_log WHERE season >= 2019",
                ["nhl_game_id", "team", "opponent", "is_home", "game_id", "season",
                 "game_type", "game_date", "goals_for"])
    log = log[log["nhl_game_id"].isin(att["nhl_game_id"].unique())]
    goalie_log = _read("SELECT nhl_game_id, player_id, started, goals_against, shots_against "
                       "FROM nhl_goalie_game_log WHERE season >= 2019",
                       ["nhl_game_id", "player_id", "started", "goals_against", "shots_against"])
    team = build_team_rows(att, log, version)
    goalie = build_goalie_rows(att, log, goalie_log, version)
    report(team, goalie, log)
    if goalie["team"].isna().any():
        raise RuntimeError("goalie rows without a team -- not writing")
    if apply:
        write("nhl_team_game_xg", ("nhl_game_id", "team"), TEAM_COLS, team)
        write("nhl_goalie_game_xg", ("nhl_game_id", "goalie_id"), GOALIE_COLS, goalie)
    team.to_parquet(WORK_DIR / "team_game_xg.parquet", index=False)
    goalie.to_parquet(WORK_DIR / "goalie_game_xg.parquet", index=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write to Supabase")
    run(ap.parse_args().apply)
