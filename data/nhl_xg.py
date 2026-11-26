"""Expected goals (xG) for every unblocked NHL shot attempt, and the model behind it.

Reads nhl_shot_events ONCE (season by season, the columns needed; a disposable
parquet copy in %TEMP%/nhl_xg serves the later steps), fits two models on
2018-19 -> 2021-22, scores both on 2022-23 onward, keeps the one with the lower
out-of-sample log loss, and writes its xG onto every unblocked attempt
(nhl_shot_events.xg + xg_model_version), 2,000 rows a statement under the same
load gate as the ingest.

WHAT IS MODELLED. Unblocked attempts -- shots on goal, misses and goals
("Fenwick"). A blocked shot is left out: its coordinates are where it was
BLOCKED, not where it was taken. Also left out of the fit: shootout attempts,
penalty shots (they get one constant, the training seasons' penalty-shot
conversion rate), and attempts with no coordinates.

INPUTS. Distance and angle to the net the shooter attacks; shot type; strength
(skaters each side, the empty net, the shooter's own goalie pulled); rebound
(the event just before, same period, was a shot attempt by the same team <= 3 s
earlier); rush (the event just before, <= 4 s earlier, was in another zone than
the shot, zones read off the coordinates from the shooter's side); period;
score state (shooter minus opponent, capped at +/-3).

    python -m data.nhl_xg --fit                  # fit + out-of-sample report, writes nothing
    python -m data.nhl_xg --fit --write          # ... and stores xG on every unblocked attempt
    python -m data.nhl_xg --refresh-frame        # re-read nhl_shot_events
"""
from __future__ import annotations

import argparse
import json
import math
import os
import pickle
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

from data.db import ConnectionLost, get_connection
from data.ingestors.nhl_shot_events import (BATCH_PAUSE, BLUE_LINE_X, LOAD_CHECK_EVERY,
                                            NET_X, UNBLOCKED, WRITE_BATCH,
                                            wait_for_quiet_db)

WORK_DIR = Path(os.environ.get("NHL_XG_WORK_DIR") or Path(tempfile.gettempdir()) / "nhl_xg")
FRAME_PATH = WORK_DIR / "shot_frame.parquet"
TRAIN_SEASONS = (2019, 2020, 2021, 2022)     # ENDING years: 2018-19 .. 2021-22
FIRST_TEST_SEASON = 2023                     # 2022-23 onward is out of sample
MODEL_TAG = "nhl_xg_v1"

FRAME_COLS = (
    "nhl_game_id", "event_id", "season", "game_type", "game_date", "period",
    "period_type", "period_seconds", "event_type", "shot_type", "reason",
    "x", "y", "zone_code", "home_defending_side", "attacking_net_x", "side_source",
    "x_norm", "y_norm", "situation_code", "shooting_skaters", "defending_skaters",
    "empty_net", "shooting_goalie_pulled", "strength", "strength_state",
    "shooting_team", "is_home", "event_owner_team", "shooter_id", "goalie_id",
    "blocker_id", "home_score_before", "away_score_before",
    "prev_event_type", "prev_team", "prev_zone_code", "prev_x", "prev_y",
    "prev_seconds_since",
)
STRING_FRAME_COLS = ("game_date", "period_type", "event_type", "shot_type", "reason",
                     "zone_code", "home_defending_side", "side_source", "situation_code",
                     "strength", "strength_state", "shooting_team", "event_owner_team",
                     "prev_event_type", "prev_team", "prev_zone_code")
NUMERIC_FRAME_COLS = tuple(c for c in FRAME_COLS if c not in STRING_FRAME_COLS)
SHOT_KINDS = ("shot-on-goal", "missed-shot", "blocked-shot", "goal")
SHOT_TYPES = ("wrist", "snap", "slap", "backhand", "tip-in", "deflected", "wrap-around")
STATES = ("5v5", "5v4", "4v5", "4v4", "3v3", "5v3", "3v5", "4v3", "3v4",
          "6v5", "5v6", "6v4", "4v6", "6v3", "3v6")


# ── the one read ─────────────────────────────────────────────────────────────

def load_shot_frame(refresh: bool = False, seasons: tuple[int, int] = (2019, 2027)) -> pd.DataFrame:
    """Every stored shot event, read from Supabase once (a season per
    statement) and kept as a disposable parquet copy for the later steps."""
    if FRAME_PATH.exists() and not refresh:
        df = pd.read_parquet(FRAME_PATH)
        logger.info(f"shot frame from {FRAME_PATH}: {len(df):,} rows")
        return df
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    parts = []
    try:
        for s in range(seasons[0], seasons[1] + 1):
            t = time.time()
            rows = conn.execute(f"SELECT {', '.join(FRAME_COLS)} FROM nhl_shot_events "
                                "WHERE season = ?", (s,)).fetchall()
            conn.commit()
            parts.append(pd.DataFrame.from_records(rows, columns=FRAME_COLS))
            logger.info(f"season {s}: {len(rows):,} rows in {time.time() - t:.1f}s")
    finally:
        conn.close()
    df = _finish_frame(pd.concat(parts, ignore_index=True))
    df.to_parquet(FRAME_PATH, index=False)
    logger.info(f"shot frame: {len(df):,} rows -> {FRAME_PATH}")
    return df


# ── features (pure) ──────────────────────────────────────────────────────────

def _obj(s: pd.Series) -> pd.Series:
    """A string column as plain objects with None for missing, so == and isin
    give True/False and never pd.NA."""
    return s.astype("object").where(s.notna(), None)


def _zone(xn: pd.Series) -> np.ndarray:
    return np.select([xn > BLUE_LINE_X, xn < -BLUE_LINE_X], ["O", "D"], "N")


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """One row of model inputs per shot event (any type; callers filter)."""
    xn = df["x_norm"].astype("float64")
    yn = df["y_norm"].astype("float64")
    dx = NET_X - xn
    out = pd.DataFrame(index=df.index)
    out["distance"] = np.hypot(dx, yn)
    out["angle"] = np.degrees(np.arctan2(np.abs(yn), dx))   # 0 = straight on, >90 = from behind the line
    st = _obj(df["shot_type"])
    out["shot_type"] = np.where(st.isin(SHOT_TYPES), st, "other")
    ss = _obj(df["strength_state"])
    out["state"] = np.where(ss.isin(STATES), ss, "other")
    out["shooting_skaters"] = df["shooting_skaters"].astype("float64")
    out["defending_skaters"] = df["defending_skaters"].astype("float64")
    out["empty_net"] = df["empty_net"].fillna(0).astype("int8")
    out["goalie_pulled"] = df["shooting_goalie_pulled"].fillna(0).astype("int8")

    gap = df["prev_seconds_since"].astype("float64")
    prev_kind = _obj(df["prev_event_type"])
    same_team = (_obj(df["prev_team"]) == _obj(df["shooting_team"])).astype(bool)
    out["rebound"] = (prev_kind.isin(("shot-on-goal", "missed-shot", "blocked-shot"))
                      & same_team & gap.between(0, 3)).astype("int8")
    sign = np.sign(df["attacking_net_x"].astype("float64"))
    prev_xn = df["prev_x"].astype("float64") * sign
    out["rush"] = (gap.between(0, 4) & prev_xn.notna()
                   & (_zone(prev_xn) != _zone(xn))).astype("int8")
    out["period"] = df["period"].clip(upper=4).astype("int8")
    home = df["is_home"] == 1
    own = np.where(home, df["home_score_before"], df["away_score_before"]).astype("float64")
    opp = np.where(home, df["away_score_before"], df["home_score_before"]).astype("float64")
    out["score_diff"] = np.clip(own - opp, -3, 3)
    return out


def model_mask(df: pd.DataFrame) -> pd.Series:
    """The attempts a model is fitted on and scores: unblocked, not a shootout
    attempt, not a penalty shot, with coordinates and a known end."""
    return (_obj(df["event_type"]).isin(UNBLOCKED) & (_obj(df["period_type"]) != "SO")
            & (_obj(df["strength"]) != "PS") & df["x_norm"].notna()
            & df["y_norm"].notna()).astype(bool)


# ── the two models ───────────────────────────────────────────────────────────

NUMERIC_GBM = ("distance", "angle", "shooting_skaters", "defending_skaters", "empty_net",
               "goalie_pulled", "rebound", "rush", "period", "score_diff")


def _lr_design(f: pd.DataFrame) -> pd.DataFrame:
    """Logistic regression needs the curvature spelled out."""
    d = f["distance"].clip(upper=200)
    a = f["angle"]
    x = pd.DataFrame({
        "distance": d, "log_distance": np.log1p(d), "distance_sq": d ** 2 / 100,
        "angle": a, "angle_sq": a ** 2 / 100, "distance_x_angle": d * a / 100,
        "behind_net": (a > 90).astype("int8"),
        "empty_net": f["empty_net"], "empty_net_x_distance": f["empty_net"] * d,
        "goalie_pulled": f["goalie_pulled"], "rebound": f["rebound"],
        "rebound_x_angle": f["rebound"] * a, "rush": f["rush"],
        "rush_x_distance": f["rush"] * d,
    }, index=f.index)
    dummies = pd.get_dummies(
        f[["shot_type", "state"]].astype(str).assign(
            period=f["period"].astype(str), score_diff=f["score_diff"].astype(int).astype(str)),
        prefix=["shot", "state", "period", "score"], dtype="int8")
    return pd.concat([x, dummies], axis=1)


class LogitXG:
    name = "logit"

    def fit(self, f: pd.DataFrame, y: np.ndarray, groups=None) -> "LogitXG":
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        x = _lr_design(f)
        self.columns = list(x.columns)
        self.scaler = StandardScaler().fit(x.values.astype("float64"))
        self.clf = LogisticRegression(C=1.0, max_iter=5000)
        self.clf.fit(self.scaler.transform(x.values.astype("float64")), y)
        return self

    def predict(self, f: pd.DataFrame) -> np.ndarray:
        x = _lr_design(f).reindex(columns=self.columns, fill_value=0)
        return self.clf.predict_proba(self.scaler.transform(x.values.astype("float64")))[:, 1]


class BoostedXG:
    name = "lightgbm"
    PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=31,
                  min_child_samples=200, subsample=0.8, subsample_freq=1,
                  colsample_bytree=0.8, reg_lambda=1.0, n_estimators=3000,
                  random_state=7, verbose=-1)

    def _x(self, f: pd.DataFrame) -> pd.DataFrame:
        x = f[list(NUMERIC_GBM)].copy()
        x["shot_type"] = pd.Categorical(f["shot_type"], categories=(*SHOT_TYPES, "other"))
        x["state"] = pd.Categorical(f["state"], categories=(*STATES, "other"))
        return x

    def fit(self, f: pd.DataFrame, y: np.ndarray, groups=None) -> "BoostedXG":
        """Early stopping on a fifth of the TRAINING games (never a test
        season), then a refit on all training games at that many trees."""
        import lightgbm as lgb
        x = self._x(f)
        rng = np.random.default_rng(7)
        games = np.unique(groups)
        val_games = set(rng.choice(games, size=len(games) // 5, replace=False))
        val = np.isin(groups, list(val_games))
        probe = lgb.LGBMClassifier(**self.PARAMS)
        probe.fit(x[~val], y[~val], eval_set=[(x[val], y[val])], eval_metric="binary_logloss",
                  callbacks=[lgb.early_stopping(100, verbose=False)])
        self.n_trees = int(probe.best_iteration_ or self.PARAMS["n_estimators"])
        self.clf = lgb.LGBMClassifier(**{**self.PARAMS, "n_estimators": self.n_trees})
        self.clf.fit(x, y)
        return self

    def predict(self, f: pd.DataFrame) -> np.ndarray:
        return self.clf.predict_proba(self._x(f))[:, 1]


# ── evaluation ───────────────────────────────────────────────────────────────

def season_metrics(seasons: pd.Series, y: np.ndarray, p: np.ndarray) -> pd.DataFrame:
    from sklearn.metrics import log_loss, roc_auc_score
    rows = []
    frame = pd.DataFrame({"season": seasons.values, "y": y, "p": p})
    for s, g in list(frame.groupby("season")) + [("all", frame)]:
        rows.append({"season": s, "shots": len(g), "goals": int(g.y.sum()),
                     "xg": round(float(g.p.sum()), 1),
                     "xg_over_goals": round(float(g.p.sum() / max(g.y.sum(), 1)), 4),
                     "auc": round(float(roc_auc_score(g.y, g.p)), 4),
                     "log_loss": round(float(log_loss(g.y, g.p, labels=[0, 1])), 5)})
    return pd.DataFrame(rows)


def fit_and_compare(df: pd.DataFrame) -> dict:
    mask = model_mask(df)
    feats = build_features(df[mask])
    data = df[mask]
    y = (_obj(data["event_type"]) == "goal").to_numpy().astype("int8")
    train = data["season"].isin(TRAIN_SEASONS).to_numpy()
    test = (data["season"] >= FIRST_TEST_SEASON).to_numpy()
    logger.info(f"modelled attempts: {mask.sum():,} of {len(df):,} events; "
                f"train {train.sum():,} ({y[train].sum():,} goals), "
                f"test {test.sum():,} ({y[test].sum():,} goals)")

    # A feature that is constant in a season is not a feature there.
    nun = feats.assign(season=data["season"].values).groupby("season").nunique()
    logger.info("distinct values per feature per season:\n" + nun.to_string())

    results, models = {}, {}
    for model in (LogitXG(), BoostedXG()):
        t = time.time()
        model.fit(feats[train], y[train], groups=data["nhl_game_id"].to_numpy()[train])
        p = model.predict(feats)
        models[model.name] = (model, p)
        oos = season_metrics(data["season"][test], y[test], p[test])
        ins = season_metrics(data["season"][train], y[train], p[train])
        results[model.name] = {"out_of_sample": oos, "in_sample": ins,
                               "fit_seconds": round(time.time() - t, 1)}
        extra = f", {model.n_trees} trees" if hasattr(model, "n_trees") else ""
        logger.info(f"\n== {model.name}{extra} (fit {time.time() - t:.0f}s)\n"
                    f"out of sample:\n{oos.to_string(index=False)}\n"
                    f"in sample:\n{ins.to_string(index=False)}")

    pooled = {k: float(v["out_of_sample"].query("season == 'all'")["log_loss"].iloc[0])
              for k, v in results.items()}
    winner = min(pooled, key=pooled.get)
    logger.success(f"out-of-sample log loss {pooled} -> keeping {winner}")

    # Penalty shots: one constant, the training seasons' conversion rate.
    ps = df[((_obj(df["strength"]) == "PS") & (_obj(df["period_type"]) != "SO")
             & _obj(df["event_type"]).isin(UNBLOCKED)).astype(bool)]
    ps_train = ps[ps["season"].isin(TRAIN_SEASONS)]
    ps_rate = float((ps_train["event_type"] == "goal").mean()) if len(ps_train) else None
    logger.info(f"penalty shots: {len(ps):,} unblocked ({len(ps_train):,} in training, "
                f"converted {ps_rate}); out of sample "
                f"{len(ps) - len(ps_train):,} with {(ps[~ps['season'].isin(TRAIN_SEASONS)]['event_type'] == 'goal').sum()} goals")
    return {"winner": winner, "pooled_log_loss": pooled, "results": results,
            "models": models, "mask": mask, "ps_rate": ps_rate, "ps_index": ps.index}


def model_version(winner: str) -> str:
    return f"{MODEL_TAG}_{winner}_fit{TRAIN_SEASONS[0]}-{TRAIN_SEASONS[-1]}"


def xg_column(df: pd.DataFrame, out: dict) -> pd.Series:
    """The xG to store for every event: the kept model on the modelled attempts,
    the constant on penalty shots, NULL on everything else."""
    xg = pd.Series(np.nan, index=df.index)
    xg[out["mask"]] = out["models"][out["winner"]][1]
    if out["ps_rate"] is not None:
        xg[out["ps_index"]] = out["ps_rate"]
    return xg


# ── write-back ───────────────────────────────────────────────────────────────

# Rows the stored model never scores, so a daily pass must not refit just
# because they are still NULL: blocked shots, shootout attempts, and the
# handful of unblocked attempts with no coordinates.
UNSCORED_WHERE = (
    "xg IS NULL AND event_type IN ('shot-on-goal', 'missed-shot', 'goal') "
    "AND period_type <> 'SO' AND x_norm IS NOT NULL AND y_norm IS NOT NULL"
)
MODEL_VERSION = "nhl_xg_v1_lightgbm_fit2019-2022"
# Bit-identical to the xG already stored. Wider than this, the refit is a
# different fit and is stamped so, not written over the stored version.
MATCH_ABS = 1e-4
# A refit this far from the stored xG is not the model. Refuse to write it.
REFUSE_ABS = 0.05
SAVED_MODEL = (Path(__file__).resolve().parents[1] / "models" / "saved"
               / f"{MODEL_VERSION}.pkl")


def _finish_frame(df: pd.DataFrame) -> pd.DataFrame:
    for c in NUMERIC_FRAME_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in STRING_FRAME_COLS:
        df[c] = df[c].astype("string")
    return df


def write_xg(df: pd.DataFrame, xg: pd.Series, version: str, only_null: bool = False) -> int:
    """UPDATE nhl_shot_events, WRITE_BATCH rows a statement, under the load
    gate. Idempotent: it sets the value, it does not add to it.

    only_null leaves a stored xG alone. The daily catch-up scores the shots
    it just inserted and does not rewrite the 1.2M rows already scored.
    """
    todo = df.loc[xg.notna(), ["nhl_game_id", "event_id"]].assign(xg=xg[xg.notna()])
    assert "'" not in version
    null_guard = " AND s.xg IS NULL" if only_null else ""
    conn = get_connection()
    n = 0
    try:
        for b, i in enumerate(range(0, len(todo), WRITE_BATCH)):
            chunk = todo.iloc[i:i + WRITE_BATCH]
            values = ",".join(f"({int(g)},{int(e)},{float(x)!r})"
                              for g, e, x in chunk.itertuples(index=False))
            sql = (f"UPDATE nhl_shot_events AS s SET xg = v.xg::double precision, "
                   f"xg_model_version = '{version}' "
                   f"FROM (VALUES {values}) AS v(g, e, xg) "
                   f"WHERE s.nhl_game_id = v.g AND s.event_id = v.e{null_guard}")
            if b % LOAD_CHECK_EVERY == 0:
                wait_for_quiet_db(conn)
            try:
                conn.execute(sql)
                conn.commit()
            except ConnectionLost:
                logger.warning("connection lost mid-batch -- re-running it")
                conn.execute(sql)
                conn.commit()
            n += len(chunk)
            if (b + 1) % 50 == 0:
                logger.info(f"xg written: {n:,} / {len(todo):,}")
            time.sleep(BATCH_PAUSE)
    finally:
        conn.close()
    logger.success(f"xg written on {n:,} events as {version}")
    return n


def _ps_rate(df: pd.DataFrame) -> float | None:
    ps = df[((_obj(df["strength"]) == "PS") & (_obj(df["period_type"]) != "SO")
             & _obj(df["event_type"]).isin(UNBLOCKED)).astype(bool)]
    ps_train = ps[ps["season"].isin(TRAIN_SEASONS)]
    if len(ps_train) == 0:
        return None
    return float((ps_train["event_type"] == "goal").mean())


def _predict(df: pd.DataFrame, model: BoostedXG, ps_rate: float | None) -> pd.Series:
    xg = pd.Series(np.nan, index=df.index)
    mask = model_mask(df)
    if bool(mask.any()):
        xg.loc[mask] = model.predict(build_features(df.loc[mask]))
    if ps_rate is not None:
        ps = ((_obj(df["strength"]) == "PS") & (_obj(df["period_type"]) != "SO")
              & _obj(df["event_type"]).isin(UNBLOCKED) & df["x_norm"].notna()
              & df["y_norm"].notna())
        xg.loc[ps.astype(bool)] = ps_rate
    return xg


def _model_path() -> Path | None:
    for path in (SAVED_MODEL, WORK_DIR / f"{MODEL_VERSION}.pkl"):
        if path.exists():
            return path
    return None


def load_or_fit_model() -> tuple[BoostedXG, str, float | None]:
    """The committed artifact, else the one this machine already fit, else a
    refit on 2018-19 through 2021-22.

    The original fit lived in a temp directory and was never committed, which
    is why a new machine cannot score a shot without fitting again. A refit
    whose sample of stored xG matches is the same model. One that drifts a
    little is stamped with a _rerun suffix. One that misses by more than
    REFUSE_ABS is not written.
    """
    path = _model_path()
    if path is not None:
        with path.open("rb") as fh:
            blob = pickle.load(fh)
        logger.info(f"xG model from {path}: {blob['version']}")
        return blob["model"], blob["version"], blob.get("ps_rate")

    train = load_shot_frame(refresh=True, seasons=(TRAIN_SEASONS[0], TRAIN_SEASONS[-1]))
    mask = model_mask(train)
    data = train[mask]
    y = (_obj(data["event_type"]) == "goal").to_numpy().astype("int8")
    model = BoostedXG().fit(
        build_features(data), y, groups=data["nhl_game_id"].to_numpy())
    ps_rate = _ps_rate(train)
    pred = _predict(train, model, ps_rate)
    conn = get_connection()
    try:
        sample = conn.execute(
            "SELECT nhl_game_id, event_id, xg FROM nhl_shot_events "
            "WHERE season BETWEEN ? AND ? AND xg IS NOT NULL "
            "AND event_type IN ('shot-on-goal', 'missed-shot', 'goal') "
            "AND period_type <> 'SO' AND COALESCE(strength, '') <> 'PS' "
            "AND x_norm IS NOT NULL "
            "ORDER BY nhl_game_id, event_id LIMIT 400",
            (TRAIN_SEASONS[0], TRAIN_SEASONS[-1])).fetchall()
        conn.commit()
    finally:
        conn.close()
    got = train[["nhl_game_id", "event_id"]].assign(pred=pred)
    chk = pd.DataFrame(sample, columns=["nhl_game_id", "event_id", "xg"]).merge(
        got, on=["nhl_game_id", "event_id"], how="left")
    if chk["pred"].isna().any():
        raise RuntimeError("the refit has no prediction for a stored training shot")
    gap = (chk["pred"] - chk["xg"]).abs()
    worst = float(gap.max())
    logger.info(f"refit vs stored xG on {len(chk)} training shots: "
                f"max abs {worst:.6g}, median {float(gap.median()):.6g}")
    if worst <= MATCH_ABS:
        version = MODEL_VERSION
    elif worst <= REFUSE_ABS:
        version = MODEL_VERSION + "_rerun"
        logger.warning(f"refit is not bit-identical (max abs {worst:.6g}); "
                       f"new shots will be stamped {version}")
    else:
        raise RuntimeError(
            f"refit disagrees with stored xG by {worst:.4f} on a training shot; "
            "not writing it")
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    out = WORK_DIR / f"{MODEL_VERSION}.pkl"
    with out.open("wb") as fh:
        pickle.dump({"model": model, "version": version, "ps_rate": ps_rate}, fh)
    logger.info(f"saved {out}")
    return model, version, ps_rate


def score_unscored(apply: bool) -> dict:
    """Score shots that have no xG yet. Blocked shots and shootout attempts
    stay NULL. Writes nothing on a row that already has an xG."""
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT {', '.join(FRAME_COLS)} FROM nhl_shot_events WHERE {UNSCORED_WHERE}"
        ).fetchall()
        conn.commit()
    finally:
        conn.close()
    if not rows:
        logger.info("nhl xG: no unscored modelable shots")
        return {"written": 0, "candidates": 0, "version": None}
    df = _finish_frame(pd.DataFrame.from_records(rows, columns=list(FRAME_COLS)))
    model, version, ps_rate = load_or_fit_model()
    xg = _predict(df, model, ps_rate)
    n = int(xg.notna().sum())
    if apply and n:
        write_xg(df, xg, version, only_null=True)
    logger.success(f"nhl xG: {n:,} of {len(df):,} unscored shots as {version}"
                   + ("" if apply else " (dry run)"))
    return {"written": n if apply else 0, "candidates": len(df), "version": version}


def save_artifacts(out: dict, xg: pd.Series, df: pd.DataFrame, version: str) -> None:
    """The fitted model and the metrics, in the work dir: NOT committed."""
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    with open(WORK_DIR / f"{version}.pkl", "wb") as fh:
        pickle.dump(out["models"][out["winner"]][0], fh)
    metrics = {k: {"out_of_sample": v["out_of_sample"].to_dict("records"),
                   "in_sample": v["in_sample"].to_dict("records")}
               for k, v in out["results"].items()}
    (WORK_DIR / f"{version}_metrics.json").write_text(
        json.dumps({"winner": out["winner"], "pooled_log_loss": out["pooled_log_loss"],
                    "ps_rate": out["ps_rate"], "metrics": metrics}, indent=1, default=str),
        encoding="utf-8")
    df[["nhl_game_id", "event_id"]].assign(xg=xg).to_parquet(WORK_DIR / "xg_pred.parquet",
                                                              index=False)
    (WORK_DIR / "latest_fit.json").write_text(
        json.dumps({"version": version, "winner": out["winner"]}), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh-frame", action="store_true")
    ap.add_argument("--fit", action="store_true", help="fit, report, save predictions")
    ap.add_argument("--write", action="store_true",
                    help="store the SAVED predictions of the last --fit in nhl_shot_events")
    a = ap.parse_args()
    frame = load_shot_frame(refresh=a.refresh_frame)
    if a.fit:
        res = fit_and_compare(frame)
        save_artifacts(res, xg_column(frame, res), frame, model_version(res["winner"]))
    if a.write:
        # What is written is exactly what the last --fit reported, not a refit.
        latest = json.loads((WORK_DIR / "latest_fit.json").read_text(encoding="utf-8"))
        pred = pd.read_parquet(WORK_DIR / "xg_pred.parquet")
        merged = frame[["nhl_game_id", "event_id"]].merge(pred, how="left", validate="1:1")
        write_xg(merged, merged["xg"], latest["version"])
