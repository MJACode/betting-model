"""A round-level HAZARD model for UFC fight duration — the rebuild, and its result.

WHY (2026-09-07). mike: "rebuild it properly", after a straight retrain of
`ufc_total_rounds` came back worse at its own cut (#539). The diagnosis behind
this attempt: a binary "over the line?" classifier has to learn one threshold at
a time, and half its training labels are graded against a SYNTHETIC line
(`synthetic_round_total` fills 2.5 / 4.5 when DK never posted one), so the model
is partly fitted to a bet nobody could take.

THE SHAPE. Model when a fight ENDS, not whether it beats a number:

    h_r = P(ends in round r | it reached round r)      -- the hazard
    q_r = P(it ended before 2:30 | it ended in round r) -- the within-round split

    P(over N-0.5) = product(1 - h_r for r < N) x (1 - h_N * q_N)

That is coherent for every line DraftKings posts (1.5 / 2.5 / 3.5 / 4.5) out of
ONE model, needs no line to train, and lets the risk of a finish differ by round
instead of being averaged into a single threshold. A decision contributes every
round entered and no ending, which is exactly the censoring a hazard wants.
Recency weighting is `0.5 ** ((2026 - season) / 4)` -- a four-season half-life,
fixed a priori and never tuned against the 2026 holdout.

THE RESULT: IT IS WORSE, AND IT IS NOT REGISTERED. On the 2026 holdout (193
fights), against the live 20260619 model and the 20260907 retrain:

    live 20260619   cal_error 0.0368   -9.2% over 7 bets at the live cut
    retrain         cal_error 0.0548  -40.0% over 6
    hazard (this)   cal_error 0.0420  -38.3% over 21, acc 0.596, AUC 0.572

It is confidently long of overs (mean p 0.593 against a 0.539 base rate), so it
fires three times as often and loses three times as much.

WHY THE REBUILD COULD NOT WIN, MEASURED THE SAME DAY. Neither constraint on this
model is in the model:

  * TRAINING POPULATION DID NOT GROW. The hazard needs no line, but the binding
    constraint was never the line -- it is fighter history. Both formulations
    train on the same 3,179 fights, because a fight is skipped when either
    fighter has under three prior bouts in `ufc_fight_log`. Of 916 distinct
    fighters on 2026 cards, **315 have no history rows at all**, and only 12 of
    those are name-matching artifacts -- 303 are genuinely absent. Roughly a
    third of every card cannot be modelled by anything built on these features.
  * THE MONEY TEST CANNOT DISCRIMINATE. DraftKings UFC totals have only been
    STORED since 2026-06-11, so the evaluable population is 56 priced fights and
    a cut selects 3-21 bets. At n=7 the noise band is about +/-40 ROI points --
    wider than any difference between these three models.

So the honest reading is that UFC round totals are limited by DATA, not by
model form, and the next real move is fight-history coverage rather than a
fourth model. Run: python -m scripts.ufc_rounds_hazard
"""

import warnings, sys, math, pickle; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, psycopg2
from dotenv import dotenv_values
sys.path.insert(0, ".")
from features.feature_engine import build_training_dataset, FEATURE_MAP
from data.ingestors.ufc_stats_ingestor import rounds_completed

FIGHTER_FEATS = [f for f in FEATURE_MAP["ufc_total_rounds"] if f != "total_line"]
TRAIN = list(range(2012, 2026)); HOLD = [2026]

def load(seasons):
    df = build_training_dataset("ufc_total_rounds", seasons=seasons)
    c = psycopg2.connect(dotenv_values(".env")["DATABASE_URL"], connect_timeout=30)
    log = pd.read_sql("""select distinct on (game_id) game_id, end_round, end_time_sec,
                         scheduled_rounds from ufc_fight_log""", c)
    c.close()
    df = df.merge(log, on="game_id", how="left")
    df["rc"] = [rounds_completed(er, et, sr) for er, et, sr in
                zip(df.end_round, df.end_time_sec, df.scheduled_rounds)]
    df["sched"] = df.scheduled_rounds.fillna(df.is_five_rounds.map({1: 5, 0: 3})).astype(float)
    return df.dropna(subset=["rc"]).reset_index(drop=True)

def expand(df):
    """One row per (fight, round entered): did the fight END in this round, and
    if so was it before 2:30? A decision is every round entered and none ended."""
    rows = []
    for i, r in df.iterrows():
        rc, sched = float(r["rc"]), int(r["sched"])
        ended_in = None if abs(rc - sched) < 1e-9 else int(math.floor(rc)) + 1
        for rnd in range(1, sched + 1):
            if rc <= rnd - 1:                       # never reached this round
                break
            rec = {f: r[f] for f in FIGHTER_FEATS}
            rec.update(round_index=rnd, is_five=int(sched == 5),
                       ended=int(ended_in == rnd), game_id=r["game_id"],
                       season=r["season"])
            if ended_in == rnd:                     # within-round timing
                rec["early_stop"] = int((rc - (rnd - 1)) <= 0.5)
            rows.append(rec)
    return pd.DataFrame(rows)

def survival(hz, qm, X, line, sched):
    """P(rounds_completed > line) from the hazard chain. line is N-0.5."""
    N = int(math.floor(line)) + 1
    out = np.ones(len(X))
    for rnd in range(1, min(N, sched) + 1):
        Z = X.copy(); Z["round_index"] = rnd
        h = hz.predict_proba(Z[HZ_COLS])[:, 1]
        if rnd < N:
            out *= (1 - h)
        else:
            q = qm.predict_proba(Z[HZ_COLS])[:, 1]     # P(early | ended)
            out *= (1 - h * q)
    return out

if __name__ == "__main__":
    from xgboost import XGBClassifier
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
    from models.trainer import RANDOM_STATE

    tr, ho = load(TRAIN), load(HOLD)
    print(f"fights: train {len(tr)}, holdout {len(ho)}")
    etr, eho = expand(tr), expand(ho)
    HZ_COLS = FIGHTER_FEATS + ["round_index", "is_five"]
    globals()["HZ_COLS"] = HZ_COLS
    print(f"round-level rows: train {len(etr)}, holdout {len(eho)} "
          f"({etr.ended.mean():.1%} of entered rounds end the fight)")

    # RECENCY WEIGHT: half-life 4 seasons, chosen a priori, never tuned on 2026.
    w = 0.5 ** ((2026 - etr.season) / 4.0)

    hz = CalibratedClassifierCV(
        XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05,
                      subsample=0.85, colsample_bytree=0.8, min_child_weight=5,
                      random_state=RANDOM_STATE, n_jobs=-1, verbosity=0),
        method="sigmoid", cv=5)
    hz.fit(etr[HZ_COLS], etr.ended, sample_weight=w)

    fin = etr[etr.ended == 1]
    qm = CalibratedClassifierCV(
        XGBClassifier(n_estimators=200, max_depth=3, learning_rate=0.05,
                      subsample=0.85, colsample_bytree=0.8, min_child_weight=5,
                      random_state=RANDOM_STATE, n_jobs=-1, verbosity=0),
        method="sigmoid", cv=5)
    qm.fit(fin[HZ_COLS], fin.early_stop,
           sample_weight=0.5 ** ((2026 - fin.season) / 4.0))

    # Holdout: P(over the actual line) vs the actual outcome
    p = np.zeros(len(ho))
    for i in range(len(ho)):
        row = ho.iloc[[i]][FIGHTER_FEATS].copy()
        row["is_five"] = int(ho.sched.iloc[i] == 5); row["round_index"] = 1
        p[i] = survival(hz, qm, row, float(ho.total_line.iloc[i]), int(ho.sched.iloc[i]))[0]
    y = ho.target.values
    print(f"\nHAZARD holdout 2026 ({len(y)} fights): acc={(np.round(p)==y).mean():.3f} "
          f"AUC={roc_auc_score(y,p):.3f} Brier={brier_score_loss(y,p):.4f} "
          f"logloss={log_loss(y,p):.4f}")
    with open("/tmp/hazard_model.pkl", "wb") as fh:
        pickle.dump({"hazard": hz, "within": qm, "cols": HZ_COLS,
                     "fighter_feats": FIGHTER_FEATS}, fh)
    np.save("/tmp/hazard_p.npy", p); ho.to_pickle("/tmp/hazard_holdout.pkl")
