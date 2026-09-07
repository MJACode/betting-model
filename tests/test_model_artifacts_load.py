"""Every committed model artifact must actually deserialise.

WHY THIS EXISTS. All twelve `nfl_prop_*` artifacts committed in #215 on
2026-08-23 were unloadable: `pickle.load` raised
`XGBoostError: input stream corrupted` inside `XGBoosterUnserializeFromBuffer`.
They sat in master for two weeks and nothing noticed, because:

  * the family was in PAUSED_MODELS, so no scorer ever called load_model on
    them — a paused model is never opened; and
  * tracking/system_health's `model_registry` check asks only whether an ACTIVE
    REGISTRY ROW EXISTS. A row pointing at a corrupt file passes it. The check
    stats the registry, not the bytes.

It was found only when the models were unpaused (2026-09-06) and the scorer
tried to load one for real. This test is the missing tripwire: it opens the
bytes, which is the only thing that distinguishes a model from a file.

Not a version-skew guard. On the interpreter that found this, 31 other xgboost
artifacts — including five declaring the SAME xgboost 3.4.1 as the broken NFL
ones — loaded fine on the same run.
"""
from __future__ import annotations

import pickle
import warnings
from collections import defaultdict
from pathlib import Path

import pytest

SAVED = Path(__file__).resolve().parent.parent / "models" / "saved"


def _newest_per_model() -> list[Path]:
    """One artifact per model id — the newest, which is the one a fresh
    registry row points at. Loading all ~43 would spend most of the runtime
    re-proving superseded versions that nothing will ever open again."""
    by_stem: dict[str, list[Path]] = defaultdict(list)
    for p in SAVED.glob("*.pkl"):
        # "<model_id>_<YYYYmmdd>_<HHMMSS>.pkl" -> model_id
        parts = p.stem.rsplit("_", 2)
        if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
            by_stem[parts[0]].append(p)
    return [max(v, key=lambda q: q.stem) for v in by_stem.values()]


ARTIFACTS = sorted(_newest_per_model())


def test_there_are_artifacts_to_check():
    """A glob that silently matches nothing would make every case below pass."""
    assert len(ARTIFACTS) > 20, f"only found {len(ARTIFACTS)} artifacts in {SAVED}"


@pytest.mark.parametrize("path", ARTIFACTS, ids=lambda p: p.stem)
def test_artifact_deserialises(path: Path):
    """The bytes must round-trip into a real object.

    sklearn's InconsistentVersionWarning is expected and tolerated — it means
    the estimator loaded. An xgboost buffer that cannot be parsed RAISES, and
    that is what this catches.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with open(path, "rb") as fh:
            artifact = pickle.load(fh)
    assert artifact is not None
    if isinstance(artifact, dict):
        assert "model" in artifact, f"{path.name} has no 'model' key"
        # A NULL `model` is legitimate for a RULE. ncaaf_spread and
        # ncaaf_spread_premium are kind='cross_book_opener': there is no fitted
        # estimator, the artifact carries the rule's parameters (d_threshold,
        # model_prob) and that IS the model. Asserting a non-None estimator here
        # failed both of them on the first run of this file — a false positive
        # that would have blocked every merge while both artifacts were fine.
        #
        # So the property is "carries something usable", not "carries an
        # estimator": a rule must still bring the numbers that make it a rule.
        if artifact["model"] is None:
            assert artifact.get("kind"), (
                f"{path.name} has model=None and no `kind` — that is a broken "
                f"artifact, not a rule")
            assert any(artifact.get(k) is not None
                       for k in ("d_threshold", "model_prob", "prob_at_threshold")), (
                f"{path.name} is a {artifact['kind']} rule carrying no parameters")


@pytest.mark.parametrize(
    "model_id",
    ["nfl_prop_pass_yards", "nfl_prop_pass_attempts", "nfl_prop_pass_completions",
     "nfl_prop_pass_tds", "nfl_prop_rush_yards", "nfl_prop_rush_attempts",
     "nfl_prop_rec_yards", "nfl_prop_receptions", "nfl_prop_rush_rec_yards",
     "nfl_prop_anytime_td", "nfl_prop_tackles_assists", "nfl_prop_sacks"],
)
def test_every_unpaused_nfl_prop_model_has_a_loadable_artifact(model_id):
    """Named individually rather than globbed: these twelve went live on
    2026-09-06 off placeholder thresholds, so an unloadable one is a model
    that silently scores nothing on a slate someone is betting."""
    matches = [p for p in ARTIFACTS if p.stem.rsplit("_", 2)[0] == model_id]
    assert matches, f"no committed artifact for {model_id}"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with open(matches[0], "rb") as fh:
            artifact = pickle.load(fh)
    assert artifact["model"] is not None
    assert artifact["feature_cols"], f"{model_id} artifact carries no feature_cols"


def test_the_health_check_opens_the_artifact_not_just_the_registry_row():
    """The production-side twin of this file.

    tracking/system_health's `model_registry` check asks whether an ACTIVE ROW
    exists. A row pointing at a corrupt file passes it, which is precisely how
    twelve dead nfl_prop_* models reported healthy for two weeks — nothing else
    opens a paused model either. The `model_artifacts_load` check added
    2026-09-06 deserialises each active artifact; on the run that introduced it,
    against production, it reported:

        [WARN] model_registry:       OK    — 51 expected models all active
        [CRIT] model_artifacts_load: STALE — 10 active artifact(s) will not
               deserialise — the model is registered and DEAD: ...

    Two checks, same models, opposite verdicts. That gap is the thing.
    """
    import inspect

    from tracking import system_health

    src = inspect.getsource(system_health.run_system_health)
    assert "model_artifacts_load" in src, src
    assert "pickle.load" in src, "the check must OPEN the file, not stat it"
    # CRIT, not WARN: a registered model that cannot load is silently betting
    # nothing on a slate someone is watching.
    assert '"model_artifacts_load", STALE, "CRIT"' in src, src
