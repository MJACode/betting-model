"""
The feature list a model ADVERTISES must match the one it was TRAINED on.

WHY THIS EXISTS
---------------
Activating a new feature is a two-step change: add the column to the model's
``PROP_*_FEATURES`` list, then retrain and COMMIT the regenerated ``.pkl``.
Nothing in the repo forced the second step, and the first step alone is
invisible in production:

  * The prop scoring path reads ``artifact["feature_cols"]`` (models/scorer.py
    lines 2917 / 3149 / 3316), not the config list, and NaN-fills any column
    the frame is missing. So a list that names features the artifact never
    learned scores exactly as before -- silently, with no error and no log.
  * The TRAINING path reads the config list (features/prop_feature_engine.py
    lines 895 / 1677). So the next retrain of that model -- for any reason,
    by anyone -- quietly picks up the extra features. The model changes
    without a decision, which is precisely what CLAUDE.md 1b's
    ``Updated-By:`` trailer exists to prevent.

That gap is not hypothetical: two models are in it today (see _KNOWN_DRIFT),
and it is the exact failure mode waiting for the opposing-starter activation
documented in ``PENDING_RETRAIN_FEATURES`` and
``docs/activate_opp_starter_features.md``. This test turns a half-done
activation into a red test instead of a silent one.

WHAT IT DOES NOT DO
-------------------
It compares against the NEWEST artifact on disk, because the ACTIVE artifact
is chosen by a ``model_registry`` row and this suite runs without a database.
The two agree in practice (a retrain writes the file and registers it in the
same run), but a registry pointed at an older file would not be caught here.
Said plainly rather than implied.
"""

from __future__ import annotations

import glob
import os
import pickle
from pathlib import Path

import pytest

from features.prop_feature_engine import PROP_FEATURE_MAP

_ROOT = Path(__file__).resolve().parent.parent
_SAVED = _ROOT / "models" / "saved"


# Drift that predates this guard. Each entry is a model whose config list names
# features its artifact was never trained on -- harmless at serve time (the
# scorer uses the artifact), but a pending unrequested model change the moment
# anyone retrains it. Recorded rather than "fixed" by trimming the lists,
# because deleting a feature someone added on purpose is itself a model
# decision, and it is not this test's to make. Shrinking this dict is good;
# growing it needs a reason written next to it.
_KNOWN_DRIFT: dict[str, list[str]] = {
    # Added to the list at some point without a retrain. A real feature key the
    # builder produces, so a retrain WOULD pick it up.
    #
    # `mlb_prop_pitcher_hits` was here too, for opp_team_whiff_pct,
    # opp_team_k_pct and park_hr_factor. #454's retrain
    # (v20260903_230550) picked up all three, so the drift is gone and the
    # exception with it -- which is this dict working as intended: it records a
    # gap until a retrain closes it, and shrinking it is the good direction.
    "mlb_prop_batter_sb": ["opp_team_sb_allowed"],
}


class _Stub:
    """Stands in for a class this machine cannot import.

    The guard only needs ``feature_cols`` -- a list of plain strings -- so it
    must not require xgboost/sklearn to be installed, and must not SKIP when
    they are missing. A guard that skips on the machine where it matters is
    the health-check-gated-on-the-thing-that-breaks trap (CLAUDE.md 7).
    """

    def __init__(self, *a, **k):
        pass

    def __setstate__(self, state):
        if isinstance(state, dict):
            self.__dict__.update(state)


class _TolerantUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        try:
            return super().find_class(module, name)
        except Exception:  # noqa: BLE001 -- any import failure degrades to a stub
            return _Stub


def _newest_artifact(model_id: str) -> Path | None:
    paths = sorted(glob.glob(str(_SAVED / f"{model_id}_*.pkl")), key=os.path.getmtime)
    return Path(paths[-1]) if paths else None


def _load(path: Path) -> dict:
    with open(path, "rb") as fh:
        return _TolerantUnpickler(fh).load()


_MODEL_IDS = sorted(PROP_FEATURE_MAP)


@pytest.mark.parametrize("model_id", _MODEL_IDS)
def test_config_list_matches_the_trained_artifact(model_id):
    """The config list equals the artifact's feature_cols, in the same order.

    Order matters: both the trainer and the scorer index the frame by this
    list positionally, so a reordering is a different model even with the same
    column set.
    """
    path = _newest_artifact(model_id)
    assert path is not None, (
        f"{model_id} is registered in PROP_FEATURE_MAP but has no artifact in "
        f"{_SAVED}. An uncommitted .pkl is a silent outage (CLAUDE.md 7)."
    )
    artifact = _load(path)
    trained = list(artifact.get("feature_cols") or [])
    listed = list(PROP_FEATURE_MAP[model_id])

    expected_drift = _KNOWN_DRIFT.get(model_id, [])
    if expected_drift:
        assert [c for c in listed if c not in trained] == expected_drift, (
            f"{model_id}: the drift against {path.name} is no longer the "
            f"recorded one. Either it was fixed (drop the _KNOWN_DRIFT entry) "
            f"or new features were added without a retrain (retrain and commit "
            f"the .pkl)."
        )
        assert [c for c in trained if c not in listed] == [], (
            f"{model_id}: the artifact was trained on features the config list "
            f"does not name -- the list cannot rebuild this model."
        )
        return

    assert listed == trained, (
        f"{model_id}: PROP_FEATURE_MAP lists {len(listed)} features but "
        f"{path.name} was trained on {len(trained)}.\n"
        f"  list-only: {[c for c in listed if c not in trained]}\n"
        f"  artifact-only: {[c for c in trained if c not in listed]}\n"
        "If you just activated features: retrain the model and COMMIT the "
        "regenerated .pkl in the same change (docs/activate_opp_starter_features.md)."
    )


@pytest.mark.parametrize("model_id", _MODEL_IDS)
def test_artifact_width_matches_its_own_feature_cols(model_id):
    """The estimator's input width equals the artifact's declared feature_cols.

    feature_cols is metadata written beside the estimator; n_features_in_ is
    what the estimator will actually accept. If they disagree the artifact is
    corrupt, and every score off it is wrong rather than merely stale.
    """
    path = _newest_artifact(model_id)
    assert path is not None
    artifact = _load(path)
    model = artifact.get("model")
    width = getattr(model, "n_features_in_", None)
    if width is None:
        pytest.skip(f"{model_id}: estimator exposes no n_features_in_")
    assert width == len(artifact.get("feature_cols") or []), (
        f"{model_id}: {path.name} declares "
        f"{len(artifact.get('feature_cols') or [])} feature_cols but the "
        f"estimator takes {width}."
    )


def test_known_drift_only_names_real_models():
    """A stale _KNOWN_DRIFT entry would silence a model that no longer exists."""
    unknown = sorted(set(_KNOWN_DRIFT) - set(PROP_FEATURE_MAP))
    assert not unknown, f"_KNOWN_DRIFT names models not in PROP_FEATURE_MAP: {unknown}"


def test_pending_features_are_not_live_without_a_retrain():
    """PENDING_RETRAIN_FEATURES must stay OUT of the live lists until retrained.

    This is the specific case the guard was written for. It fails the moment
    someone merges the pending lists in, which is correct: that merge is only
    half of the activation, and the other half is a retrained .pkl. Once the
    retrain lands, this assertion is the one to delete -- deliberately, in the
    same commit as the artifact.
    """
    from features.prop_feature_engine import PENDING_RETRAIN_FEATURES

    live_but_untrained: dict[str, list[str]] = {}
    for model_id, pending in PENDING_RETRAIN_FEATURES.items():
        path = _newest_artifact(model_id)
        trained = list(_load(path).get("feature_cols") or []) if path else []
        listed = PROP_FEATURE_MAP.get(model_id, [])
        leaked = [c for c in pending if c in listed and c not in trained]
        if leaked:
            live_but_untrained[model_id] = leaked

    assert not live_but_untrained, (
        "These pending features are named in the live feature list but no "
        f"artifact was trained on them: {live_but_untrained}. Retrain and "
        "commit the .pkl, then drop them from PENDING_RETRAIN_FEATURES."
    )
