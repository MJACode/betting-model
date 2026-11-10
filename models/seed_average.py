"""
Several fits of one regressor behind one `predict`: the mean of theirs.

WHY. A boosted-tree fit that subsamples rows and columns is a draw: the same
data fitted under another random seed predicts a different number. For the
NCAAF totals regression that is about 1.5 points for one game (standard
deviation across 11 seeds, docs/ncaaf_market_audit.md section 4) against a
betting gate of 8, where most bets lock within a point of the gate, so about
3 games in 10 at the gate were there because of the seed. Averaging the fits
removes most of that draw and changes nothing else about the model.

WHY HERE, AND WHY SO SMALL. `models.trainer.load_model` and the artifact health
check open an artifact with a bare `pickle.load`, and pickle stores a class by
its module path. The fit runs as `python -m scripts.ncaaf_margin_eval`, so a
class defined in that script would be stored as `__main__.<name>` and would
load on the machine that fitted it and nowhere else. This module imports numpy
only, so loading it costs the worker nothing it does not already have.

The scorer needs no change: its `total_regression` branch calls
`float(clf.predict(x)[0])` on one row, and this answers that call.
"""

from __future__ import annotations

import numpy as np


def _predict_on_one_thread(members) -> None:
    """Set each boosted-tree member to predict on one thread.

    The scorer predicts ONE row per game, and a member fitted with `n_jobs=-1`
    starts a thread pool for that one row, once per member per game. Measured
    2026-11-10 on the eleven-member NCAAF totals artifact, first predict after
    a load: 62 ms as fitted, 17 ms on one thread. It cannot change a value:
    threads split ROWS between them, and one row's prediction is the same sum
    over its trees either way (tests/test_seed_average.py compares to the last
    bit). The fit is not affected: this runs after the members are fitted.

    A member with no `get_booster` (anything that is not xgboost) is left alone.
    """
    for member in members:
        get_booster = getattr(member, "get_booster", None)
        if get_booster is None:
            continue
        try:
            get_booster().set_param({"nthread": 1})
        except Exception:                      # noqa: BLE001 - a speed setting only
            continue


class SeedAverage:
    """N fitted regressors whose `predict` is the mean of the members'.

    `members` are fitted objects with a `predict(X)` returning one number per
    row. `seeds` records the random seed each was fitted under, in the same
    order: provenance for whoever opens the artifact later, never read at
    predict time.
    """

    def __init__(self, members, seeds=None):
        members = list(members)
        if not members:
            raise ValueError("SeedAverage needs at least one fitted member")
        seeds = None if seeds is None else [int(s) for s in seeds]
        if seeds is not None and len(seeds) != len(members):
            raise ValueError(
                f"{len(seeds)} seeds for {len(members)} members: one seed per member")
        self.members = members
        self.seeds = seeds
        _predict_on_one_thread(self.members)

    def __setstate__(self, state: dict) -> None:
        """Unpickling. Applies the one-thread setting to artifacts pickled
        before it existed, whose members still carry the fit's `n_jobs=-1`."""
        self.__dict__.update(state)
        _predict_on_one_thread(self.members)

    def __len__(self) -> int:
        return len(self.members)

    def __repr__(self) -> str:
        return f"SeedAverage({len(self.members)} members, seeds={self.seeds})"

    def member_predictions(self, X) -> np.ndarray:
        """Each member's prediction, shape (members, rows). What the seed-to-seed
        spread is measured from."""
        return np.array([np.asarray(m.predict(X), dtype=float).ravel()
                         for m in self.members], dtype=float)

    def predict(self, X) -> np.ndarray:
        """The mean of the members' predictions, one number per row."""
        return self.member_predictions(X).mean(axis=0)
