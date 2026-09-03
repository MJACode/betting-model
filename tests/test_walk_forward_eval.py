"""Walk-forward evaluation: many honest reads instead of one.

mike, 2026-09-03: "why holdout an entire season? why not hold out various
intervals of all seasons?"

Random intervals would be the same leak as shuffled CV: every feature is a
rolling window, so a held-out June game is described by May games that sit in
the training set. The answer is not smaller slices, it is MORE season-shaped
folds -- train <= T, test T+1, walked forward.

What that bought immediately, on mlb_f5_moneyline: AUC 0.636 / 0.628 / 0.640 /
0.633 across 2022-2025 and then 0.560 in 2026. A single 2026 holdout said "this
model has no signal". Five folds say "this model worked for four seasons and
broke in 2026" -- a completely different problem with a completely different
fix.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import walk_forward_eval as wf  # noqa: E402


class _Frame(dict):
    """Minimal stand-in for the feature frame the engine returns."""
    @property
    def empty(self):
        return len(self["target"]) == 0

    @property
    def columns(self):
        return list(self.keys())

    def __getitem__(self, k):
        if isinstance(k, list):
            return _Cols([[self[c][i] for c in k] for i in range(len(self["target"]))])
        return dict.__getitem__(self, k)


class _Cols(list):
    @property
    def values(self):
        return np.array(self, dtype=float)


def _fake(seed, n=200):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    return _Frame({"target": _Cols((x > 0).astype(int).tolist()),
                   "f1": _Cols(x.tolist()),
                   "game_date": _Cols([float(i) for i in range(n)])})


def test_every_fold_trains_only_on_earlier_seasons(monkeypatch):
    seen = []

    def _frame(model_id, seasons):
        seen.append(tuple(seasons))
        return _fake(sum(seasons))

    monkeypatch.setattr(wf, "_frame", _frame)
    rows = wf.walk_forward("m", [2021, 2022, 2023, 2024], first_test=2023,
                           features=["f1"])
    assert [r["test_season"] for r in rows] == [2023, 2024]
    # Each test season is preceded by a train call covering only earlier ones.
    for train_seasons, test_seasons in zip(seen[0::2], seen[1::2]):
        assert max(train_seasons) < min(test_seasons), (train_seasons, test_seasons)


def test_a_fold_with_too_little_history_is_skipped(monkeypatch):
    """Testing on the second season would train on one, which is not a model."""
    monkeypatch.setattr(wf, "_frame", lambda m, s: _fake(sum(s)))
    rows = wf.walk_forward("m", [2021, 2022, 2023], first_test=2022,
                           features=["f1"])
    assert [r["test_season"] for r in rows] == [2023]


def test_a_single_class_test_season_is_skipped(monkeypatch):
    """AUC is undefined when every outcome is the same — skip, never crash."""
    def _frame(model_id, seasons):
        f = _fake(sum(seasons))
        if seasons == [2024]:
            f["target"] = _Cols([1] * len(f["target"]))
        return f

    monkeypatch.setattr(wf, "_frame", _frame)
    rows = wf.walk_forward("m", [2021, 2022, 2023, 2024], first_test=2023,
                           features=["f1"])
    assert [r["test_season"] for r in rows] == [2023]


def test_the_params_are_fixed_across_folds():
    """The question is whether the SIGNAL is stable. Re-tuning inside each fold
    adds a second moving part and turns a clean comparison into a noisy one."""
    src = (Path(__file__).parent.parent / "scripts"
           / "walk_forward_eval.py").read_text(encoding="utf-8")
    assert "BASELINE_PARAMS" in src
    # The IMPORT and the study call, not the word: the docstring explains why
    # Optuna is deliberately absent, and a test that forbids naming a thing
    # also forbids explaining why it was left out.
    assert "import optuna" not in src
    assert "create_study" not in src, "the harness tunes inside folds"


def test_it_reports_the_spread_not_just_the_mean():
    """A mean AUC hides a model that only worked once, which is what most of
    this repo's false positives looked like (§7: plateau, not peak)."""
    src = (Path(__file__).parent.parent / "scripts"
           / "walk_forward_eval.py").read_text(encoding="utf-8")
    assert "min / max" in src and "mean AUC" in src
