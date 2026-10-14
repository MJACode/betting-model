"""Walk-forward expected goals: every season scored by an xG model that never saw it.

RESEARCH ONLY. Reads the local shot frame (data/nhl_xg.py's disposable copy of
nhl_shot_events) and, for the one comparison, nhl_team_game_xg once; writes
nothing to the database.

WHY. The xG stored on nhl_shot_events (nhl_xg_v1_lightgbm_fit2019-2022) has two
problems for a model input:
  1. 2018-19 .. 2021-22 are scored by a model fit on those same seasons
     (in sample), so any training row built from them leaks;
  2. the level drifts: league xG / goals is 1.00 in the fit seasons and
     1.065 .. 1.144 for 2022-23 .. 2025-26.

WHAT THIS DOES.
  --fit        For each season S from 2020-21 on, fit data/nhl_xg.py's model
               (BoostedXG, same inputs, same mask) on the seasons before S and
               score S. 2018-19 and 2019-20 (EWMA warm-up only) are cross-fit:
               each scored by a model fit on the other. Penalty shots get the
               fit's own training-season conversion rate; the four 2018-19
               attempts with no coordinates get the fit's training base rate.
               Then the level is corrected AS OF the season: season S's xG is
               multiplied by goals / xG of the most recent completed season,
               measured on that season's own walk-forward xG (2018-19 has no
               completed season before it: factor 1.0).
  --aggregate  Sum the corrected xG per team-game (xGF, xGA, all situations and
               5-on-5, goals, unblocked attempts) and per goalie-game (unblocked
               shots faced, xG faced, goals allowed; empty net and shootouts
               excluded), and check the team-game attempt counts against
               nhl_team_game_xg row by row.

Outputs go to NHL_XG_TEST_DIR (default %TEMP%/nhl_xg_test), never the repo.

    python -m scripts.nhl_xg_walkforward --fit
    python -m scripts.nhl_xg_walkforward --aggregate
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

from data.ingestors.nhl_shot_events import UNBLOCKED  # noqa: E402
from data.nhl_xg import FRAME_PATH, WORK_DIR, BoostedXG, _obj, build_features, model_mask  # noqa: E402

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)

OUT = Path(os.environ.get("NHL_XG_TEST_DIR", r"C:/Users/micha/AppData/Local/Temp/nhl_xg_test"))
REBUILD_CACHE = Path(os.environ.get("NHL_REBUILD_CACHE",
                                    r"C:/Users/micha/AppData/Local/Temp/nhl_ml_rebuild_cache"))
CLIP = 1 - 1e-6
FIVE_ON_FIVE = "1551"
EXPECTED_ROWS, EXPECTED_GAMES = 1_238_808, 10_604     # the table, per the brief


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_frame() -> pd.DataFrame:
    if not FRAME_PATH.exists():
        raise SystemExit(f"{FRAME_PATH} missing -- not re-reading nhl_shot_events from here")
    df = pd.read_parquet(FRAME_PATH)
    log(f"shot frame {FRAME_PATH}: {len(df):,} rows, {df.nhl_game_id.nunique():,} games "
        f"(table: {EXPECTED_ROWS:,} rows, {EXPECTED_GAMES:,} games)")
    if len(df) != EXPECTED_ROWS or df.nhl_game_id.nunique() != EXPECTED_GAMES:
        raise SystemExit("the local shot frame is not the table's row set")
    return df


def kinds(df: pd.DataFrame) -> dict:
    kind = _obj(df["event_type"])
    unb = kind.isin(UNBLOCKED).astype(bool)
    so = (_obj(df["period_type"]) == "SO").astype(bool)
    ps = (_obj(df["strength"]) == "PS").astype(bool)
    mod = model_mask(df)
    return {"goal": (kind == "goal").astype(bool), "attempt": unb & ~so, "modelled": mod,
            "ps": unb & ~so & ps, "nocoord": unb & ~so & ~ps & ~mod}


def fit_plan(seasons: list[int]) -> list[tuple[int, list[int]]]:
    """(scored season, training seasons). The two first seasons cross-fit."""
    first, second = seasons[0], seasons[1]
    plan = [(first, [second]), (second, [first])]
    plan += [(s, [t for t in seasons if t < s]) for s in seasons[2:]]
    return plan


def metrics(season: pd.Series, y: np.ndarray, p: np.ndarray) -> pd.DataFrame:
    from sklearn.metrics import log_loss, roc_auc_score
    f = pd.DataFrame({"season": season.to_numpy(), "y": y, "p": p})
    rows = []
    for s, g in list(f.groupby("season")) + [("all", f)]:
        rows.append({"season": s, "shots": len(g), "goals": int(g.y.sum()),
                     "xg": round(float(g.p.sum()), 1),
                     "xg/goals": round(float(g.p.sum() / g.y.sum()), 4),
                     "auc": round(float(roc_auc_score(g.y, g.p)), 4),
                     "log_loss": round(float(log_loss(g.y, g.p, labels=[0, 1])), 5)})
    return pd.DataFrame(rows)


def run_fit() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_frame()
    k = kinds(df)
    mod = df[k["modelled"]]
    feats = build_features(mod)
    y = k["goal"][k["modelled"]].to_numpy().astype("int8")
    season = mod["season"].to_numpy()
    games = mod["nhl_game_id"].to_numpy()
    seasons = sorted(int(s) for s in np.unique(season))
    log(f"modelled attempts {len(mod):,}; penalty shots {int(k['ps'].sum())}; "
        f"no coordinates {int(k['nocoord'].sum())}; seasons {seasons}")

    raw = np.full(len(mod), np.nan)
    ps_xg = pd.Series(np.nan, index=df.index[k["ps"]])
    nc_xg = pd.Series(np.nan, index=df.index[k["nocoord"]])
    fits = []
    for target, train_seasons in fit_plan(seasons):
        tr = np.isin(season, train_seasons)
        te = season == target
        t0 = time.time()
        model = BoostedXG().fit(feats[tr], y[tr], groups=games[tr])
        raw[te] = model.predict(feats[te])
        ps_tr = k["ps"] & df["season"].isin(train_seasons)
        ps_rate = float(k["goal"][ps_tr].mean())
        base = float(y[tr].mean())
        ps_xg[df.index[k["ps"] & (df["season"] == target)]] = ps_rate
        nc_xg[df.index[k["nocoord"] & (df["season"] == target)]] = base
        fits.append({"scored": target, "trained on": train_seasons, "train shots": int(tr.sum()),
                     "trees": model.n_trees, "penalty-shot rate": round(ps_rate, 4),
                     "base rate": round(base, 5), "seconds": round(time.time() - t0)})
        log(f"season {target}: fit on {train_seasons} ({int(tr.sum()):,} shots, {model.n_trees} trees, "
            f"{time.time() - t0:.0f}s)")
        with open(OUT / f"xg_wf_model_{target}.pkl", "wb") as fh:
            pickle.dump(model, fh)
    assert not np.isnan(raw).any()

    # The level, as of each season: goals / xG of the most recent completed season,
    # on that season's own walk-forward xG. The first season has none: 1.0.
    by = pd.DataFrame({"season": season, "y": y, "p": raw}).groupby("season").agg(g=("y", "sum"), x=("p", "sum"))
    factor = {seasons[0]: 1.0}
    for prev, s in zip(seasons[:-1], seasons[1:]):
        factor[s] = float(by.loc[prev, "g"] / by.loc[prev, "x"])
    corr = raw * pd.Series(season).map(factor).to_numpy()
    clipped = int((corr > CLIP).sum())
    corr = np.minimum(corr, CLIP)
    log(f"level factors {json.dumps({int(k_): round(v, 4) for k_, v in factor.items()})}; "
        f"{clipped} shots clipped at {CLIP}")

    before = metrics(mod["season"], y, raw)
    after = metrics(mod["season"], y, corr)
    stored = pd.read_parquet(WORK_DIR / "xg_pred.parquet")
    st = mod[["nhl_game_id", "event_id"]].merge(stored, on=["nhl_game_id", "event_id"], how="left",
                                                validate="1:1")["xg"].to_numpy()
    stored_m = metrics(mod["season"], y, st)
    print("\n### Walk-forward xG, BEFORE the level correction (each season scored by a model that never saw it)\n")
    print(before.to_string(index=False))
    print("\n### Walk-forward xG, AFTER the as-of level correction "
          f"(factor by season: {', '.join(f'{s}: {factor[s]:.4f}' for s in seasons)})\n")
    print(after.to_string(index=False))
    print("\n### For comparison: the STORED xG (nhl_xg_v1_lightgbm_fit2019-2022; in sample for 2019-2022)\n")
    print(stored_m.to_string(index=False))
    same = mod["season"].to_numpy() == 2023
    print(f"\nsame model, same training seasons (2019-2022) -> season 2023: "
          f"max |walk-forward raw - stored| = {np.abs(raw[same] - st[same]).max():.2e}")
    print("\n### The fits\n")
    print(pd.DataFrame(fits).to_string(index=False))

    out = df.loc[k["attempt"], ["nhl_game_id", "event_id", "season"]].copy()
    out["xg_raw"] = np.nan
    out["xg"] = np.nan
    out.loc[mod.index, "xg_raw"] = raw
    out.loc[mod.index, "xg"] = corr
    out.loc[ps_xg.index, ["xg_raw", "xg"]] = np.c_[ps_xg.to_numpy(), ps_xg.to_numpy()]
    nc = nc_xg.to_numpy() * pd.Series(df.loc[nc_xg.index, "season"]).map(factor).to_numpy()
    out.loc[nc_xg.index, "xg_raw"] = nc_xg.to_numpy()
    out.loc[nc_xg.index, "xg"] = nc
    assert out.xg.notna().all(), "an attempt without xG"
    out.to_parquet(OUT / "xg_wf_attempts.parquet", index=False)
    (OUT / "xg_wf_fit.json").write_text(json.dumps(
        {"factor": {str(s): v for s, v in factor.items()}, "clipped": clipped, "fits": fits,
         "before": before.to_dict("records"), "after": after.to_dict("records"),
         "stored": stored_m.to_dict("records")}, indent=1, default=str), encoding="utf-8")
    log(f"wrote {OUT / 'xg_wf_attempts.parquet'} ({len(out):,} attempts)")


# ── aggregates ───────────────────────────────────────────────────────────────

def _db_quiet(conn, label: str) -> None:
    """The brief's gate: wait 2 minutes while > 5 queries are active or one has run > 60 s."""
    for _ in range(15):
        n, longest = conn.execute(
            "SELECT count(*) FILTER (WHERE state='active'), "
            "coalesce(extract(epoch FROM max(now()-query_start) FILTER (WHERE state='active')), 0) "
            "FROM pg_stat_activity WHERE datname=current_database()").fetchone()
        conn.commit()
        if int(n) <= 5 and float(longest) <= 60:
            log(f"{label}: {int(n)} active, longest {float(longest):.0f}s -- reading")
            return
        log(f"{label}: {int(n)} active, longest {float(longest):.0f}s -- waiting 120s")
        time.sleep(120)
    raise SystemExit("database stayed busy -- not reading")


def team_rows(att: pd.DataFrame, team_log: pd.DataFrame) -> pd.DataFrame:
    a = att.assign(xg5=att.xg * att.is5, g5=att.goal * att.is5)
    by = a.groupby(["nhl_game_id", "shooting_team"]).agg(
        xg=("xg", "sum"), xg5=("xg5", "sum"), f=("goal", "size"), f5=("is5", "sum"),
        g=("goal", "sum"), g5=("g5", "sum"))
    t = team_log[team_log.nhl_game_id.isin(att.nhl_game_id.unique())][
        ["nhl_game_id", "team", "opponent", "season", "game_date", "goals_for", "goals_against"]].copy()
    mine = by.reindex(pd.MultiIndex.from_arrays([t.nhl_game_id, t.team])).fillna(0).to_numpy()
    theirs = by.reindex(pd.MultiIndex.from_arrays([t.nhl_game_id, t.opponent])).fillna(0).to_numpy()
    cols = list(by.columns)
    for name, src, frame in (("xgf", "xg", mine), ("xga", "xg", theirs), ("xgf_5v5", "xg5", mine),
                             ("xga_5v5", "xg5", theirs), ("ff", "f", mine), ("fa", "f", theirs),
                             ("ff_5v5", "f5", mine), ("fa_5v5", "f5", theirs), ("gf", "g", mine),
                             ("ga", "g", theirs), ("gf_5v5", "g5", mine), ("ga_5v5", "g5", theirs)):
        t[name] = frame[:, cols.index(src)]
    for c in ("ff", "fa", "ff_5v5", "fa_5v5", "gf", "ga", "gf_5v5", "ga_5v5"):
        t[c] = t[c].astype(int)
    return t


def goalie_rows(att: pd.DataFrame) -> pd.DataFrame:
    g = att[att.goalie_id.notna() & (att.empty_net.fillna(0) != 1)].copy()
    g["player_id"] = g.goalie_id.astype("int64")
    return g.groupby(["nhl_game_id", "player_id"]).agg(
        unblocked_faced=("goal", "size"), xg_faced=("xg", "sum"), goals_allowed=("goal", "sum"),
        shooters=("shooting_team", "nunique")).reset_index()


def run_aggregate() -> None:
    df = load_frame()
    k = kinds(df)
    xg = pd.read_parquet(OUT / "xg_wf_attempts.parquet")
    att = df.loc[k["attempt"], ["nhl_game_id", "event_id", "season", "shooting_team", "goalie_id",
                                "empty_net", "situation_code"]].copy()
    att = att.merge(xg[["nhl_game_id", "event_id", "xg"]], on=["nhl_game_id", "event_id"], how="left",
                    validate="1:1")
    assert att.xg.notna().all()
    att["goal"] = k["goal"][k["attempt"]].to_numpy().astype(int)
    att["is5"] = (_obj(att["situation_code"]) == FIVE_ON_FIVE).to_numpy().astype(int)
    att["shooting_team"] = att.shooting_team.astype(str)
    log(f"attempts summed: {len(att):,} (unblocked, not a shootout attempt; empty-net and "
        f"penalty shots included for teams)")

    with open(REBUILD_CACHE / "module_logs_v1.pkl", "rb") as fh:
        logs = pickle.load(fh)
    team_log = logs["team"].copy()
    team_log["team"], team_log["opponent"] = team_log.team.astype(str), team_log.opponent.astype(str)
    t = team_rows(att, team_log)
    g = goalie_rows(att)
    gl = logs["goalie"][["nhl_game_id", "player_id", "started", "shots_against", "goals_against"]]
    g = g.merge(gl, on=["nhl_game_id", "player_id"], how="left", validate="1:1")

    # Check 1: the attempt counts against nhl_team_game_xg, row by row (one read).
    from data.db import get_connection
    cols = ["nhl_game_id", "team", "ff", "fa", "ff_5v5", "fa_5v5", "gf", "ga", "xgf", "xga"]
    conn = get_connection()
    try:
        _db_quiet(conn, "nhl_team_game_xg")
        t0 = time.time()
        rows = conn.execute(f"SELECT {', '.join(cols)} FROM nhl_team_game_xg").fetchall()
        conn.commit()
    finally:
        conn.close()
    tab = pd.DataFrame(rows, columns=cols)
    tab["team"] = tab.team.astype(str)
    log(f"nhl_team_game_xg: {len(tab):,} rows in {time.time() - t0:.1f}s")
    j = t.merge(tab, on=["nhl_game_id", "team"], how="outer", suffixes=("", "_tab"), indicator=True)
    print("\n### Team-game sums vs nhl_team_game_xg (rows, and team-games whose counts differ)\n")
    print(f"rows here {len(t):,}; rows in the table {len(tab):,}; joined: "
          f"{j._merge.value_counts().to_dict()}")
    both = j[j._merge == "both"]
    rep = {c: int((both[c] != both[f"{c}_tab"]).sum()) for c in ("ff", "fa", "ff_5v5", "fa_5v5", "gf", "ga")}
    print(f"team-games with a different count: {rep}")
    print(f"sum of attempts here {int(t.ff.sum()):,} vs table {int(tab.ff.sum()):,}; "
          f"5-on-5 {int(t.ff_5v5.sum()):,} vs {int(tab.ff_5v5.sum()):,}")
    bys = both.assign(xgf_tab=both.xgf_tab.astype(float)).groupby("season").agg(
        team_games=("team", "size"), gf=("gf", "sum"), xgf_walkforward=("xgf", "sum"),
        xgf_stored=("xgf_tab", "sum"))
    bys["walkforward/goals"] = (bys.xgf_walkforward / bys.gf).round(4)
    bys["stored/goals"] = (bys.xgf_stored / bys.gf).round(4)
    print("\nxGF summed by season, walk-forward corrected vs the stored xG (goals = play-by-play goals):\n")
    print(bys.round({"xgf_walkforward": 1, "xgf_stored": 1}).to_string())

    # Check 2: play-by-play goals against the team log; goalie goals against the goalie log.
    print(f"\nteam-games whose play-by-play goals equal the team log's goals_for: "
          f"{int((t.gf == t.goals_for).sum()):,} of {len(t):,}")
    gs = g[g.started.notna()]
    print(f"goalie-games: {len(g):,} with an attempt faced; in nhl_goalie_game_log {len(gs):,}; "
          f"starts {int((gs.started == 1).sum()):,}; goals allowed equal to the log's goals_against: "
          f"{int((gs.goals_allowed == gs.goals_against).sum()):,}; goalie-games facing both teams: "
          f"{int((g.shooters > 1).sum())}")
    lg = logs["goalie"]
    lg_s = lg[(lg.started == 1) & lg.nhl_game_id.isin(att.nhl_game_id.unique())]
    have = set(zip(g.nhl_game_id, g.player_id))
    print(f"starts in the goalie log (shot seasons) with no attempt faced here: "
          f"{sum((a, b) not in have for a, b in zip(lg_s.nhl_game_id, lg_s.player_id))} of {len(lg_s):,}")
    lgs = g.merge(t[["nhl_game_id", "season"]].drop_duplicates(), on="nhl_game_id")
    lg_by = lgs.groupby("season").agg(goals=("goals_allowed", "sum"), xg=("xg_faced", "sum"))
    lg_by["goals saved above expected (league)"] = (lg_by.xg - lg_by.goals).round(1)
    print("\nleague goals saved above expected by season, goalies in net (empty net and shootouts out):\n")
    print(lg_by.round(1).to_string())

    # game_date rides along so the scoring path's cut (logs dated before the game
    # day) applies to these frames exactly as it does to the logs.
    t[["nhl_game_id", "team", "game_date", "season", "xgf", "xga", "xgf_5v5", "xga_5v5", "gf", "ga",
       "ff", "fa", "ff_5v5", "fa_5v5"]].to_parquet(OUT / "team_game_xg_wf.parquet", index=False)
    g = g.merge(t[["nhl_game_id", "game_date"]].drop_duplicates(), on="nhl_game_id", how="left",
                validate="m:1")
    assert g.game_date.notna().all()
    g[["nhl_game_id", "player_id", "game_date", "unblocked_faced", "xg_faced", "goals_allowed"]].to_parquet(
        OUT / "goalie_game_xg_wf.parquet", index=False)
    log(f"wrote team_game_xg_wf.parquet ({len(t):,}) and goalie_game_xg_wf.parquet ({len(g):,})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fit", action="store_true")
    ap.add_argument("--aggregate", action="store_true")
    a = ap.parse_args()
    if a.fit:
        run_fit()
    if a.aggregate:
        run_aggregate()
