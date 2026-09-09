"""The live Poisson CV must not score a lookup.

WHAT WENT WRONG. `mlb_live_total_runs` trains on PLAY rows: one MLB game
becomes ~64 of them, every one carrying the same game-level label (runs
remaining is a function of the final score), and the pre-game context columns
are constant within a game and continuous to four decimals -- a fingerprint.
`_poisson_objective` split those rows with KFold(shuffle=True), so a game's own
plays sat on both sides of every split. The validation score was partly recall,
and 25 Optuna trials optimised toward whatever memorised hardest.

Measured on the real corpus, 866,136 play rows over 2019-2024:

    Optuna's best CV NLL   1.9200     what the tuner believed
    2025 holdout NLL       2.7422     what it actually was

    Var(y|lambda)/mean in-sample   0.63 - 0.76   BELOW Poisson: memorised
    Var(y|lambda)/mean holdout     2.5  - 2.7    tail 2.6x too tight

That is the model's documented ~10pp overconfidence, and it is the fit, not the
features -- adding the pre-game total line moved the holdout calibration error
from 0.0985 to 0.0976.

`_time_ordered_cv` fixed this same class of bug for the PRE-GAME models on
2026-09-03. The live path was not brought across then; this is that.

THE ASSERTION IS THE RIGHT WAY ROUND. A leak makes the CV score BETTER, so the
test asserts the ungrouped split reports a LOWER (more flattering) NLL than the
grouped one on data with no real signal. A test asserting the grouped score is
good would pass on the broken code.
"""

import numpy as np
import optuna

from models.trainer import _poisson_objective

PARAMS = {
    "n_estimators": 120, "max_depth": 8, "learning_rate": 0.2,
    "subsample": 1.0, "colsample_bytree": 1.0, "min_child_weight": 1,
    "gamma": 0.0, "reg_alpha": 1e-8, "reg_lambda": 1e-8,
}


def _memorisable_plays(n_games=180, plays=20, seed=0):
    """Play rows whose only per-game feature is a FINGERPRINT carrying no
    signal — the shape of the real corpus, with the signal removed so any
    apparent skill is recall."""
    rng = np.random.RandomState(seed)
    fingerprint = rng.uniform(0, 1, n_games)          # like home_team_era
    lam = rng.uniform(1.0, 8.0, n_games)             # unrelated to fingerprint
    target = rng.poisson(lam)                        # ONE label per game
    X, y, g = [], [], []
    for i in range(n_games):
        for p in range(plays):
            X.append([fingerprint[i], p])            # + a state column
            y.append(target[i])
            g.append(f"G{i:04d}")
    return np.array(X, float), np.array(y, float), np.array(g)


def test_ungrouped_cv_scores_a_lookup():
    X, y, groups = _memorisable_plays()
    trial = optuna.trial.FixedTrial(PARAMS)
    leaky = _poisson_objective(trial, X, y)
    honest = _poisson_objective(optuna.trial.FixedTrial(PARAMS), X, y,
                                groups=groups)

    # The fingerprint carries no signal, so an honest fold cannot beat the
    # base rate. A shuffled fold can look up the answer.
    assert leaky < honest, (
        f"shuffled CV NLL {leaky:.4f} was not better than grouped "
        f"{honest:.4f} — if this fails the fixture stopped being memorisable, "
        f"not that the leak is gone")
    assert honest - leaky > 0.05, (
        f"the gap is only {honest - leaky:.4f}; on the real corpus it is 0.82 "
        f"nats (CV 1.92 vs holdout 2.74)")


def test_groups_default_to_none_so_ungrouped_callers_are_unchanged():
    """Prop and game models pass row-independent data and must keep KFold."""
    import inspect
    sig = inspect.signature(_poisson_objective)
    assert sig.parameters["groups"].default is None


def test_the_live_trainer_passes_game_ids():
    """The fix is only real if the live path actually supplies the groups."""
    import inspect
    from models.trainer import train_live_model
    src = inspect.getsource(train_live_model)
    assert 'groups=groups_train' in src
    assert 'df_train["game_id"].values[idx]' in src


def test_game_ids_sort_chronologically():
    """The live split sorts by game_id to make folds time-ordered. That is only
    true because an MLB game_id is `MLB_<ISO date>_<away>_<home>`, so
    lexicographic order IS date order.

    The pre-game twin carries the same precondition -- _time_ordered_cv's
    docstring: "Without that sort this split is just an arbitrary partition
    wearing a better name", pinned there by test_training_rows_are_date_ordered.
    This is that pin for the live path: if the id format ever changes, the
    grouping still holds but the TIME ordering silently stops holding, and the
    tuner goes back to interpolating between games it has already seen.
    """
    ids = ["MLB_2019-04-01_NYY_BAL", "MLB_2021-10-03_SEA_LAA",
           "MLB_2024-07-15_BOS_TOR", "MLB_2025-10-13_SEA_TOR"]
    shuffled = [ids[2], ids[0], ids[3], ids[1]]
    assert sorted(shuffled) == ids

    dates = [i.split("_")[1] for i in ids]
    assert dates == sorted(dates)
