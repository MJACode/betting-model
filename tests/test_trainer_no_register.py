"""
A training run ACTIVATES what it trains. --no-register is how you measure
without shipping.

Every trainer path calls _register_model, which deactivates the live version
and activates the new one. That is right for a real retrain and wrong for a
comparison run -- and the comparison run is the dangerous one, because the
person doing it believes they are only measuring. The artifact it leaves is
uncommitted, so the worker cannot load the path the registry now points at:
the "an uncommitted .pkl is a silent outage" failure, reached by someone who
never intended to change anything.

These tests pin both halves of the flag: no registry write, and the artifact
kept out of models/saved/ where it could be committed or mistaken for real.
"""

from __future__ import annotations

import pytest

import models.trainer as trainer
from config import MODELS_DIR


@pytest.fixture
def registering():
    original = trainer.REGISTER_TRAINED_MODELS
    trainer.REGISTER_TRAINED_MODELS = True
    yield
    trainer.REGISTER_TRAINED_MODELS = original


@pytest.fixture
def not_registering():
    original = trainer.REGISTER_TRAINED_MODELS
    trainer.REGISTER_TRAINED_MODELS = False
    yield
    trainer.REGISTER_TRAINED_MODELS = original
    try:
        (MODELS_DIR / "_baseline").rmdir()
    except OSError:
        pass


def test_default_is_to_register():
    """The flag is opt-in. A plain `--model X` run must behave as it always has."""
    assert trainer.REGISTER_TRAINED_MODELS is True


def test_real_runs_write_into_models_saved(registering):
    assert trainer._output_dir() == MODELS_DIR


def test_baseline_runs_write_somewhere_else(not_registering):
    """Not just a different filename -- a different directory.

    tests/test_feature_artifact_agreement.py compares each model against the
    NEWEST models/saved/<id>_*.pkl. A baseline artifact sitting there would be
    newer than the real one and would silently become the thing every feature
    guard compares against.
    """
    out = trainer._output_dir()
    assert out != MODELS_DIR
    assert out.parent == MODELS_DIR
    assert out.name == "_baseline"


def test_no_register_opens_no_database_connection(not_registering, monkeypatch):
    """The skip happens BEFORE the connection, not after.

    Returning early after get_connection() would still deactivate nothing but
    would still fail on a machine with no database -- and would still be one
    edit away from writing.
    """
    def _explode():
        raise AssertionError("--no-register must not touch the database")

    monkeypatch.setattr(trainer, "get_connection", _explode)
    trainer._register_model("mlb_prop_batter_hits", "vtest",
                            [2020], 2025, {}, "models/saved/_baseline/x.pkl")


def test_a_normal_run_DOES_register(registering, monkeypatch):
    """The mutation guard: if this passed with the flag off, the flag would be
    doing nothing and the test above would be vacuous."""
    calls = []

    def _explode():
        calls.append(1)
        raise RuntimeError("connection attempted, as expected")

    monkeypatch.setattr(trainer, "get_connection", _explode)
    with pytest.raises(RuntimeError):
        trainer._register_model("mlb_prop_batter_hits", "vtest",
                                [2020], 2025, {}, "models/saved/x.pkl")
    assert calls == [1]


def test_baseline_artifacts_are_not_committable():
    """git must refuse to track models/saved/_baseline/.

    The flag stops the registry write; this stops the other half of the
    accident -- a `git add models/saved/...` sweeping a throwaway artifact into
    the repo, where the next reader cannot tell it from a real one.
    """
    import subprocess

    probe = MODELS_DIR / "_baseline" / "probe.pkl"
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_bytes(b"")
    try:
        out = subprocess.run(
            ["git", "check-ignore", str(probe)],
            capture_output=True, text=True,
        )
        assert out.returncode == 0, (
            "models/saved/_baseline/ is not gitignored — a comparison run's "
            "artifact can be committed as though it were real"
        )
    finally:
        probe.unlink(missing_ok=True)
        try:
            probe.parent.rmdir()
        except OSError:
            pass
