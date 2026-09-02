"""
wnba_points_rebuild.py — rebuild wnba_prop_player_points with tonight's
information (availability, role, usage, projected minutes) and evaluate it
against real pre-tip DraftKings prices on the 2026 holdout.

WHY THIS EXISTS
---------------
The 2026-07-19 retrain proved the OLD feature set cannot clear the vig: with
2026 held out, every cell of the prob x edge grid was negative against real DK
lines. The clean 2026 record (is_live excluded) is 101-93 / -3.7% — a winning
record 2pp short of its own breakeven, i.e. under-informed rather than broken.
This script is the pre-registered experiment for closing that gap with NEW
inputs, not another refit of the same 16 columns.

WHAT IS NEW
-----------
  1. Availability / role / usage context (features/wnba_availability.py):
     teammates-out workload, minutes-rank role (is_starter is 100% NULL for
     2019-2025 so the old role feature was a dead constant), and shot-volume
     rates from the fg_att/fg3_att/ft_att columns no model ever read.
  2. A MINUTES MODEL, validated on its own MAE against a naive last-5 baseline
     before its projection feeds the points model. Trained rows get
     season-wise OUT-OF-FOLD projections (never their own fold's), the holdout
     gets projections from a model fit only on train seasons — no leakage.
  3. A NEGATIVE-BINOMIAL head (model_type="nbinom", the NFL machinery in
     models/trainer.py). WNBA points are overdispersed (var ≈ 2-3x mean); the
     live model reads P(over) off a raw Poisson, which overstates both tails.

PRE-COMMITTED EVALUATION (do not renegotiate after seeing results)
------------------------------------------------------------------
  * Train 2019-2025, hold out 2026 — the only season with real DK lines.
  * Grade at the latest PRE-TIP DK snapshot (the session-106 leak guard,
    _is_pregame_snapshot, applied in Python — never a raw SQL string compare).
  * config.MODEL_MIN_ODDS blanket -140 floor applied, as production would.
  * Report the PLATEAU (neighbour-positive cells), never a lone peak.
  * KILL CRITERION: no plateau cell with >= 100 bets and positive flat ROI on
    the 2026 holdout → report that WNBA points is efficient for us and STOP.
    Sessions 74 / 87 / 106 each fitted noise; the tell was always a peak with
    negative neighbours.

AVAILABILITY MODES
------------------
Training presence comes from the box score (who logged minutes) — the only
source covering 2019-2025. Production would know availability from the injury
report instead, which sees less (a healthy DNP looks "in"). So the holdout is
evaluated BOTH ways:
  * box    — box-score presence: the upper bound of availability knowledge.
             If THIS fails, the approach is dead and we stop.
  * injury — presence = expected rotation minus players listed Out in the
             `injuries` table pre-game: what serve time actually sees.
             Shipping requires this mode to clear too.

USAGE (needs DB access — run on Matt's machine or the Railway worker):
    python -m scripts.wnba_points_rebuild                # full run, both modes
    python -m scripts.wnba_points_rebuild --trials 100   # heavier Optuna
    python -m scripts.wnba_points_rebuild --save-artifacts   # after a SHIP verdict

--save-artifacts writes the points + minutes .pkls but does NOT register them:
shipping also needs build_wnba_prop_scoring_rows to feed projected_min and the
injuries-out list at serve time, which is deliberately a separate reviewed step.
"""

import argparse
import pickle
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import optuna
import pandas as pd
from loguru import logger
from scipy import stats as scipy_stats
from sklearn.metrics import mean_absolute_error
from xgboost import XGBRegressor

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MODEL_MIN_ODDS, MODELS_DIR  # noqa: E402
from data.db import get_connection  # noqa: E402
from features.feature_engine import _is_pregame_snapshot, _parse_iso_ts  # noqa: E402
from features.wnba_availability import absence_features  # noqa: E402
from features.wnba_prop_feature_engine import (  # noqa: E402
    PROP_PLAYER_POINTS_V2_FEATURES,
    build_bulk_wnba_prop_lookups,
    build_wnba_prop_training_dataset,
)
from models.scorer import american_to_decimal, american_to_implied_prob  # noqa: E402
from models.trainer import (  # noqa: E402
    RANDOM_STATE,
    _nb_dispersion,
    _oof_predictions,
    _poisson_objective,
)

MODEL_ID       = "wnba_prop_player_points"
TRAIN_SEASONS  = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
HOLDOUT_SEASON = 2026
MIN_ODDS_FLOOR = MODEL_MIN_ODDS.get(MODEL_ID, -140)

# The points model's inputs: the v2 context set plus the minutes projection.
POINTS_FEATURES = PROP_PLAYER_POINTS_V2_FEATURES + ["projected_min"]

# The minutes model's inputs — rotation history, role, absences, schedule.
# Deliberately NO scoring stats: minutes are an opportunity quantity and mixing
# production into the projection would launder the target into its own feature.
MINUTES_FEATURES = [
    "min_last3_avg", "min_last5_avg", "season_min_avg",
    "rotation_rank", "is_starter_tier",
    "teammates_out", "teammate_minutes_out",
    "rest_days", "is_home", "is_early_season",
]

# Sweep grid. Coarse on purpose: a 2pp-wide cell is the resolution at which a
# ~250-bet holdout can distinguish anything at all.
PROB_FLOORS = [round(p, 2) for p in np.arange(0.50, 0.73, 0.02)]
EDGE_FLOORS = [round(e, 2) for e in np.arange(0.00, 0.17, 0.02)]
MIN_CELL_BETS = 25          # below this a cell is noise (WNBA sweep house rule)
SHIP_MIN_BETS = 100         # the pre-committed volume bar for the verdict

# Injury statuses that mean "will not play tonight". 'Questionable'/'Day-To-Day'
# players usually play; counting them absent would overstate vacated minutes.
OUT_STATUSES = {"out", "injured reserve", "suspension", "10-day il", "60-day il"}


# ── small helpers ─────────────────────────────────────────────────────────────

def _norm_name(name: str) -> str:
    """Accent/punctuation/suffix-insensitive join key for DK vs game-log names."""
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z ]", "", s)
    parts = [p for p in s.split() if p not in {"jr", "sr", "ii", "iii", "iv"}]
    return " ".join(parts)


def _nb_probs(mu: float, line: float, nb_r: float) -> tuple[float, float, float]:
    """(p_over, p_under, p_push) off the negative-binomial head."""
    mu = max(float(mu), 1e-6)
    r = float(nb_r)
    sf = lambda x: float(scipy_stats.nbinom.sf(x, r, r / (r + mu)))   # noqa: E731
    pmf = lambda x: float(scipy_stats.nbinom.pmf(x, r, r / (r + mu)))  # noqa: E731
    if float(line).is_integer():
        n = int(line)
        p_push = pmf(n)
        p_over = sf(n)
        return p_over, max(1.0 - p_over - p_push, 0.0), p_push
    p_over = sf(int(np.floor(line)))
    return p_over, 1.0 - p_over, 0.0


def _flat_profit(won: bool, pushed: bool, price: float) -> float:
    if pushed:
        return 0.0
    if won:
        return 100.0 * (american_to_decimal(price) - 1.0)
    return -100.0


# ── Phase A: dataset ──────────────────────────────────────────────────────────

def build_dataset() -> tuple[pd.DataFrame, dict]:
    seasons = TRAIN_SEASONS + [HOLDOUT_SEASON]
    conn = get_connection()
    try:
        bulk = build_bulk_wnba_prop_lookups(conn, seasons)
    finally:
        conn.close()
    df = build_wnba_prop_training_dataset(
        MODEL_ID, seasons,
        feature_cols=PROP_PLAYER_POINTS_V2_FEATURES,
        extra_keep=["target_minutes"],
        bulk=bulk,
    )
    if df.empty:
        raise SystemExit("Dataset came back empty — check DB connectivity.")
    n_hold = int((df["season"] == HOLDOUT_SEASON).sum())
    logger.success(f"Dataset: {len(df)} rows ({len(df) - n_hold} train / {n_hold} holdout)")
    return df, bulk


# ── Phase B: minutes model ────────────────────────────────────────────────────

def minutes_model(df: pd.DataFrame) -> tuple[pd.DataFrame, XGBRegressor, dict]:
    """
    Season-wise out-of-fold minutes projections for train rows, a train-only
    model's projections for the holdout, and MAE vs the naive last-5 baseline.
    Season-wise folds (not KFold) so a player's own contemporaneous games can
    never inform their projection.
    """
    params = dict(n_estimators=300, max_depth=4, learning_rate=0.05,
                  subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
                  random_state=RANDOM_STATE, n_jobs=-1, verbosity=0)

    work = df.dropna(subset=MINUTES_FEATURES + ["target_minutes"]).copy()
    is_train = work["season"].isin(TRAIN_SEASONS)
    X_all = work[MINUTES_FEATURES].values.astype(float)
    y_all = work["target_minutes"].values.astype(float)

    proj = pd.Series(np.nan, index=work.index)
    for s in TRAIN_SEASONS:
        tr = is_train & (work["season"] != s)
        te = work["season"] == s
        if te.sum() == 0:
            continue
        m = XGBRegressor(**params)
        m.fit(X_all[tr.values], y_all[tr.values])
        proj.loc[te] = m.predict(X_all[te.values])

    final = XGBRegressor(**params)
    final.fit(X_all[is_train.values], y_all[is_train.values])
    hold = work["season"] == HOLDOUT_SEASON
    if hold.sum():
        proj.loc[hold] = final.predict(X_all[hold.values])

    work["projected_min"] = proj

    # Validation gate: the projection must beat the naive baseline or it is
    # noise dressed as a feature and must not feed the points model.
    naive_mae = mean_absolute_error(y_all[is_train.values],
                                    work.loc[is_train, "min_last5_avg"].values)
    model_mae = mean_absolute_error(y_all[is_train.values],
                                    proj.loc[is_train].values)
    hold_mae = (mean_absolute_error(y_all[hold.values], proj.loc[hold].values)
                if hold.sum() else float("nan"))
    hold_naive = (mean_absolute_error(y_all[hold.values],
                                      work.loc[hold, "min_last5_avg"].values)
                  if hold.sum() else float("nan"))
    metrics = dict(oof_mae=round(model_mae, 3), naive_mae=round(naive_mae, 3),
                   holdout_mae=round(hold_mae, 3), holdout_naive_mae=round(hold_naive, 3))
    logger.info(f"Minutes model — OOF MAE {model_mae:.3f} vs naive last-5 {naive_mae:.3f}; "
                f"holdout MAE {hold_mae:.3f} vs naive {hold_naive:.3f}")
    if model_mae >= naive_mae:
        logger.warning("Minutes model does NOT beat the naive baseline — "
                       "projected_min will be dropped from the points features.")
        work["projected_min"] = np.nan
    df = df.join(work[["projected_min"]])
    return df, final, metrics


# ── Phase C: points model ─────────────────────────────────────────────────────

def train_points(df: pd.DataFrame, trials: int) -> tuple[XGBRegressor, float, list[str], pd.DataFrame]:
    feature_cols = list(POINTS_FEATURES)
    if df["projected_min"].isna().all():
        feature_cols.remove("projected_min")

    fit_df = df.dropna(subset=feature_cols + ["target"]).copy()
    train = fit_df[fit_df["season"].isin(TRAIN_SEASONS)]
    hold  = fit_df[fit_df["season"] == HOLDOUT_SEASON]
    logger.info(f"Points matrix: {len(train)} train / {len(hold)} holdout rows, "
                f"{len(feature_cols)} features")

    X_tr = train[feature_cols].values.astype(float)
    y_tr = train["target"].values.astype(float)

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="minimize",
                                sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))
    study.optimize(lambda t: _poisson_objective(t, X_tr, y_tr),
                   n_trials=trials, show_progress_bar=False)
    best = study.best_params
    logger.success(f"Best CV Poisson NLL: {study.best_value:.4f}")

    model = XGBRegressor(**best, objective="count:poisson",
                         eval_metric="poisson-nloglik",
                         random_state=RANDOM_STATE, n_jobs=-1, verbosity=0)
    model.fit(X_tr, y_tr)

    # NB dispersion from honest out-of-fold residuals — never in-sample, which
    # understates variance and would re-inflate tail confidence.
    oof = np.clip(_oof_predictions(best, X_tr, y_tr, "count:poisson"), 1e-6, None)
    nb_r = _nb_dispersion(y_tr, oof)
    vm = float(np.mean((y_tr - oof) ** 2) / max(np.mean(oof), 1e-6))
    logger.info(f"NB dispersion r={nb_r:.2f} (OOF residual var/mean={vm:.2f}; r→∞ is Poisson)")

    if len(hold):
        mu = np.clip(model.predict(hold[feature_cols].values.astype(float)), 1e-6, None)
        logger.info(f"Holdout MAE {mean_absolute_error(hold['target'], mu):.3f}")

    imp = sorted(zip(feature_cols, model.feature_importances_),
                 key=lambda kv: -kv[1])[:10]
    logger.info("Top features: " + ", ".join(f"{k} {v:.1%}" for k, v in imp))
    return model, nb_r, feature_cols, fit_df


# ── Phase D: holdout evaluation at real pre-tip DK prices ─────────────────────

def fetch_pretip_lines(market: str = "player_points",
                       season: int = HOLDOUT_SEASON) -> dict:
    """
    {(game_id, norm_name): {"line","over_price","under_price"}} — latest
    strictly PRE-TIP DK snapshot per player. The pre-tip test runs in Python
    (_is_pregame_snapshot) because snapshot_at/commence_time are TEXT in mixed
    'Z'/offset shapes and a raw SQL compare silently keeps leaked rows — the
    exact session-106 failure this market's history already contains.
    """
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT o.game_id, o.player_name, o.line, o.over_price, o.under_price,
                   o.snapshot_at, g.commence_time
            FROM player_prop_odds o
            JOIN games g ON g.game_id = o.game_id
            WHERE g.sport = 'WNBA' AND g.season = %s
              AND o.market = %s AND o.bookmaker = 'draftkings'
            ORDER BY o.snapshot_at
        """, (season, market)).fetchall()
    finally:
        conn.close()

    out: dict = {}
    best_ts: dict = {}
    dropped = 0
    for game_id, pname, line, over_p, under_p, snap, tip in rows:
        if not _is_pregame_snapshot(snap, tip):
            dropped += 1
            continue
        # "latest pre-tip wins" decided on PARSED timestamps, never on the raw
        # TEXT ordering — 'Z' and offset shapes do not sort chronologically as
        # strings (session 106). An unparseable snapshot loses to any parsed one.
        key = (game_id, _norm_name(pname))
        ts = _parse_iso_ts(snap)
        if key in best_ts:
            prev = best_ts[key]
            newer = (ts is not None) and (prev is None or ts > prev)
            if not newer:
                continue
        best_ts[key] = ts
        out[key] = {
            "line": float(line), "over_price": over_p, "under_price": under_p,
        }
    logger.info(f"Pre-tip DK lines: {len(out)} player-games "
                f"({dropped} post-tip snapshots excluded)")
    return out


def fetch_injury_out_map() -> dict:
    """
    {(team, game_date): set(player_id)} for players whose latest report on or
    before that date says they will not play. Names resolve to ids through the
    game log. Only meaningful from 2026-06-07 (first WNBA injury rows).
    """
    conn = get_connection()
    try:
        inj = conn.execute("""
            SELECT team, player_name, status, report_date
            FROM injuries WHERE sport = 'WNBA'
            ORDER BY report_date
        """).fetchall()
        name_rows = conn.execute("""
            SELECT DISTINCT player_id, player_name, team FROM wnba_player_game_log
            WHERE season = %s
        """, (HOLDOUT_SEASON,)).fetchall()
        game_rows = conn.execute("""
            SELECT game_id, home_team, away_team, game_date FROM games
            WHERE sport = 'WNBA' AND season = %s
        """, (HOLDOUT_SEASON,)).fetchall()
    finally:
        conn.close()

    pid_by_name = {(_norm_name(n), t): str(p) for p, n, t in name_rows}
    # latest status per (team, norm name) as of each report date
    reports: dict = {}
    for team, pname, status, rdate in inj:
        reports.setdefault((team, _norm_name(pname)), []).append((rdate, (status or "").lower()))

    out_map: dict = {}
    for _gid, home, away, gdate in game_rows:
        for team in (home, away):
            outs = set()
            for (t, nname), hist in reports.items():
                if t != team:
                    continue
                latest = [s for d, s in hist if d <= gdate]
                if latest and latest[-1] in OUT_STATUSES:
                    pid = pid_by_name.get((nname, team))
                    if pid:
                        outs.add(pid)
            if outs:
                out_map[(team, gdate)] = outs
    logger.info(f"Injury-mode out lists: {len(out_map)} team-dates with >=1 Out player")
    return out_map


def side_rows(hold: pd.DataFrame, model, nb_r: float, feature_cols: list[str],
              lines: dict, label: str) -> pd.DataFrame:
    """One row per bettable SIDE of every priced holdout player-game."""
    mu = np.clip(model.predict(hold[feature_cols].values.astype(float)), 1e-6, None)
    rows = []
    for (idx, r), m in zip(hold.iterrows(), mu):
        key = (r["game_id"], _norm_name(r["player_name"]))
        dk = lines.get(key)
        if dk is None:
            continue
        line = dk["line"]
        p_over, p_under, p_push = _nb_probs(m, line, nb_r)
        actual = float(r["target"])
        for side, prob, price in (("over", p_over, dk["over_price"]),
                                  ("under", p_under, dk["under_price"])):
            if price is None:
                continue
            price = float(price)
            if price < MIN_ODDS_FLOOR:          # blanket -140 prop floor
                continue
            implied = american_to_implied_prob(price)
            pushed = actual == line
            won = (actual > line) if side == "over" else (actual < line)
            rows.append({
                "mode": label, "game_id": r["game_id"], "player": r["player_name"],
                "game_date": r["game_date"], "month": str(r["game_date"])[:7],
                "side": side, "line": line, "price": price, "mu": round(float(m), 3),
                "prob": prob, "implied": implied, "edge": prob - implied,
                "actual": actual, "won": won, "pushed": pushed,
                "profit": _flat_profit(won, pushed, price),
                "breakeven": implied,
            })
    df = pd.DataFrame(rows)
    logger.info(f"[{label}] {len(df)} bettable sides across "
                f"{df['game_id'].nunique() if len(df) else 0} games")
    return df


def sweep(sides: pd.DataFrame, label: str) -> pd.DataFrame:
    cells = []
    for pf in PROB_FLOORS:
        for ef in EDGE_FLOORS:
            sel = sides[(sides["prob"] >= pf) & (sides["edge"] >= ef)]
            n = len(sel)
            if n == 0:
                cells.append(dict(prob=pf, edge=ef, bets=0, roi=np.nan))
                continue
            decided = sel[~sel["pushed"]]
            w = int(decided["won"].sum())
            l = len(decided) - w
            profit = float(sel["profit"].sum())
            cells.append(dict(
                prob=pf, edge=ef, bets=n, w=w, l=l,
                win_pct=round(100 * w / max(len(decided), 1), 1),
                breakeven=round(100 * float(sel["breakeven"].mean()), 1),
                roi=round(100 * profit / (100 * n), 2),
                units=round(profit / 100, 1),
                over_share=round(float((sel["side"] == "over").mean()), 2),
            ))
    grid = pd.DataFrame(cells)

    # plateau score: how many of a cell's 8 neighbours are also ROI-positive
    # with real volume. A lone positive peak is the documented noise signature.
    def _plateau(row):
        if not (row["bets"] >= MIN_CELL_BETS and row.get("roi", np.nan) > 0):
            return 0
        score = 0
        for dp in (-0.02, 0, 0.02):
            for de in (-0.02, 0, 0.02):
                if dp == 0 and de == 0:
                    continue
                nb = grid[(abs(grid["prob"] - (row["prob"] + dp)) < 1e-9)
                          & (abs(grid["edge"] - (row["edge"] + de)) < 1e-9)]
                if len(nb) and nb.iloc[0]["bets"] >= MIN_CELL_BETS and nb.iloc[0]["roi"] > 0:
                    score += 1
        return score
    grid["plateau"] = grid.apply(_plateau, axis=1)

    printable = grid[grid["bets"] >= MIN_CELL_BETS].sort_values(
        ["plateau", "bets"], ascending=False)
    logger.info(f"\n[{label}] sweep — cells with >= {MIN_CELL_BETS} bets "
                f"(top 15 by plateau, then volume):\n"
                + printable.head(15).to_string(index=False))
    return grid


def verdict(grid: pd.DataFrame, sides: pd.DataFrame, label: str) -> dict | None:
    """
    The pre-committed decision: a plateau cell (>= 5 of 8 neighbours positive)
    with >= SHIP_MIN_BETS bets and positive ROI, or STOP. The chosen cut is the
    plateau CENTRE — the qualifying cell with the most positive neighbours,
    volume as the tiebreak — never the best-ROI cell.
    """
    ok = grid[(grid["bets"] >= SHIP_MIN_BETS) & (grid["roi"] > 0) & (grid["plateau"] >= 5)]
    if ok.empty:
        logger.warning(f"[{label}] VERDICT: STOP — no plateau cell clears "
                       f">= {SHIP_MIN_BETS} bets at positive ROI. Do not re-cut.")
        return None
    pick = ok.sort_values(["plateau", "bets"], ascending=False).iloc[0]
    sel = sides[(sides["prob"] >= pick["prob"]) & (sides["edge"] >= pick["edge"])]
    monthly = sel.groupby("month").agg(
        bets=("won", "size"),
        w=("won", "sum"),
        units=("profit", lambda s: round(float(s.sum()) / 100, 1)),
    )
    logger.success(f"[{label}] VERDICT: candidate SHIP cut prob>={pick['prob']} "
                   f"edge>={pick['edge']}: {int(pick['bets'])} bets "
                   f"{int(pick['w'])}-{int(pick['l'])} ({pick['win_pct']}% vs "
                   f"breakeven {pick['breakeven']}%), ROI {pick['roi']:+.2f}%, "
                   f"plateau {int(pick['plateau'])}/8")
    logger.info(f"[{label}] per-month at that cut:\n{monthly.to_string()}")
    neg_months = int((monthly["units"] < 0).sum())
    if neg_months > len(monthly) / 2:
        logger.warning(f"[{label}] {neg_months}/{len(monthly)} months negative — "
                       "the assists failure mode. Treat as STOP unless volume says otherwise.")
    return dict(prob=float(pick["prob"]), edge=float(pick["edge"]),
                bets=int(pick["bets"]), roi=float(pick["roi"]))


# ── injury-mode feature swap ──────────────────────────────────────────────────

def injury_mode_holdout(fit_df: pd.DataFrame, bulk: dict, out_map: dict) -> pd.DataFrame:
    """
    Holdout rows with the absence block recomputed from what serve time would
    know: expected rotation minus the injuries-table Out list, NOT the box
    score. Rank / usage / rolling features are identical in both modes.
    """
    hold = fit_df[fit_df["season"] == HOLDOUT_SEASON].copy()
    cache = bulk.get("_rotation_cache", {})
    abs_cols = ["teammates_out", "teammate_minutes_out", "teammate_fga_out",
                "teammate_points_out", "top_teammate_out"]
    for idx, r in hold.iterrows():
        rot = cache.get((r["team"], r["game_date"]))
        if rot is None:
            continue
        outs = out_map.get((r["team"], r["game_date"]), set())
        present = set(rot) - outs
        feats = absence_features(rot, present, str(r["player_id"]))
        for c in abs_cols:
            hold.at[idx, c] = feats[c]
    return hold


# ── artifacts ─────────────────────────────────────────────────────────────────

def save_artifacts(points_model, nb_r, feature_cols, minutes_final, minutes_metrics):
    version = datetime.now().strftime("%Y%m%d_%H%M%S")
    pts_path = Path(MODELS_DIR) / f"{MODEL_ID}_{version}.pkl"
    with open(pts_path, "wb") as f:
        pickle.dump({
            "model_id": MODEL_ID, "version": version, "sport": "WNBA",
            "market": "player_points", "model_type": "nbinom",
            "feature_cols": feature_cols, "model": points_model, "nb_r": nb_r,
            "train_seasons": TRAIN_SEASONS,
            "trained_at": datetime.now().isoformat(),
        }, f)
    min_path = Path(MODELS_DIR) / f"wnba_minutes_projection_{version}.pkl"
    with open(min_path, "wb") as f:
        pickle.dump({
            "model_id": "wnba_minutes_projection", "version": version,
            "sport": "WNBA", "feature_cols": MINUTES_FEATURES,
            "model": minutes_final, "metrics": minutes_metrics,
            "trained_at": datetime.now().isoformat(),
        }, f)
    logger.success(f"Saved {pts_path.name} + {min_path.name} — NOT registered. "
                   "Shipping needs the serve-time wiring (projected_min + "
                   "injuries-out in build_wnba_prop_scoring_rows) first.")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--trials", type=int, default=50)
    ap.add_argument("--availability", choices=["box", "injury", "both"], default="both")
    ap.add_argument("--save-artifacts", action="store_true")
    ap.add_argument("--csv", default=None, help="dump side rows for offline analysis")
    args = ap.parse_args()

    df, bulk = build_dataset()
    df, minutes_final, minutes_metrics = minutes_model(df)
    model, nb_r, feature_cols, fit_df = train_points(df, args.trials)

    lines = fetch_pretip_lines()
    hold = fit_df[fit_df["season"] == HOLDOUT_SEASON]

    all_sides = []
    if args.availability in ("box", "both"):
        s = side_rows(hold, model, nb_r, feature_cols, lines, "box")
        all_sides.append(s)
        grid = sweep(s, "box")
        box_verdict = verdict(grid, s, "box")
    else:
        box_verdict = None

    if args.availability in ("injury", "both"):
        out_map = fetch_injury_out_map()
        hold_inj = injury_mode_holdout(fit_df, bulk, out_map)
        s = side_rows(hold_inj, model, nb_r, feature_cols, lines, "injury")
        all_sides.append(s)
        grid = sweep(s, "injury")
        inj_verdict = verdict(grid, s, "injury")
    else:
        inj_verdict = None

    if args.csv and all_sides:
        pd.concat(all_sides).to_csv(args.csv, index=False)
        logger.info(f"Side rows written to {args.csv}")

    logger.info("── FINAL ──────────────────────────────────────────────")
    if box_verdict is None and args.availability in ("box", "both"):
        logger.warning("Box mode (availability upper bound) FAILED the kill "
                       "criterion → WNBA points is efficient for us. STOP.")
    elif args.availability == "both":
        if inj_verdict is None:
            logger.warning("Box mode clears but INJURY mode (what serve time "
                           "sees) does not → do not ship; the edge lives in "
                           "information production doesn't have.")
        else:
            logger.success("Both modes clear. Next: serve-time wiring, then "
                           "register from the injury-mode plateau centre.")

    if args.save_artifacts:
        save_artifacts(model, nb_r, feature_cols, minutes_final, minutes_metrics)


if __name__ == "__main__":
    main()
