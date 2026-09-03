"""Hyperparameters are tuned on folds that respect time.

mike, 2026-09-03: "why holdout an entire season? why not hold out various
intervals of all seasons?"

The season holdout was never the weak part. The final evaluation has always
been train-on-past / predict-future, which is the job. But the hyperparameters
were chosen with StratifiedKFold(shuffle=True) -- randomly shuffled folds -- so
the tuner was scoring a DIFFERENT task: interpolating between games it had
already seen.

That matters here more than it would elsewhere, because every feature is a
rolling window (d_runs_last_5, d_runs_last_10, d_starter_era_last3). A shuffled
fold puts a game's own neighbourhood on both sides of the split, the validation
score comes back flattering, and 100 Optuna trials optimise toward it.

And random INTERVALS -- the other half of the question -- would be the same
mistake with extra steps, for the same reason.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import models.trainer as trainer  # noqa: E402

SRC = (Path(__file__).parent.parent / "models" / "trainer.py").read_text(
    encoding="utf-8")


def test_every_validation_fold_is_later_than_its_training_fold():
    """The property the whole change exists for."""
    n = 500
    cv = trainer._time_ordered_cv(n)
    folds = list(cv.split(np.zeros((n, 3)), np.zeros(n)))
    assert folds, "no folds produced"
    for train_idx, val_idx in folds:
        assert train_idx.max() < val_idx.min(), (
            "a validation row precedes a training row — this is a shuffled "
            "split wearing a time-series name")


def test_the_training_window_expands():
    """Expanding window, not a sliding one: later folds should see more history,
    which is how the tuner's choice reflects the data the model will have."""
    n = 500
    sizes = [len(tr) for tr, _ in trainer._time_ordered_cv(n).split(
        np.zeros((n, 3)), np.zeros(n))]
    assert sizes == sorted(sizes) and sizes[0] < sizes[-1], sizes


@pytest.mark.parametrize("fn", ["_xgb_objective", "_xgb_multiclass_objective"])
def test_no_objective_shuffles_its_folds(fn):
    body = inspect.getsource(getattr(trainer, fn))
    assert "shuffle=True" not in body, f"{fn} still shuffles its CV folds"
    assert "_time_ordered_cv" in body, f"{fn} does not use time-ordered folds"


def test_training_rows_are_date_ordered_before_the_split():
    """_time_ordered_cv splits on POSITIONAL index. Without this sort the split
    is an arbitrary partition that merely looks principled — the failure mode
    is silent and flattering, which is the worst kind."""
    i = SRC.index("def train_model(")
    body = SRC[i:SRC.index("\ndef ", i + 10)]
    sort_at = body.index('sort_values("game_date"')
    build_at = body.index("X_train = df_train[feature_cols]")
    assert sort_at < build_at, (
        "the frame is sorted after the arrays are built, which sorts nothing")


def test_the_holdout_is_still_a_whole_season():
    """The answer to 'why not random intervals': a rolling-window feature
    computed for a held-out June game reads May games that would sit in the
    training set. Season holdout avoids that by construction, and it is the
    deployment condition. This change fixes the TUNING, not the holdout."""
    sig = inspect.signature(trainer.train_model)
    assert "holdout_season" in sig.parameters
