"""The backtest must grade the hyperparameters that are actually deployed.

`models/nfl_prop_backtest` reads `models/saved/nfl_prop_params.json` rather
than the active artifact, and nothing wrote that file when the twelve models
were retrained on 2026-09-07. For two days every prop backtest -- the −40.53u
table, the information test -- graded the 2026-08-23 hyperparameters while the
worker scored with the 09-07 ones. Gate 2 of the backtest says it must run
what the deployed path runs; this pins the file to the newest committed
artifact of each model, which is the one the registry activates.
"""
from __future__ import annotations

import json
import pickle
import re
from pathlib import Path

import pytest

SAVED = Path(__file__).resolve().parent.parent / "models" / "saved"
PARAMS = SAVED / "nfl_prop_params.json"


def _newest_artifact(model_id: str) -> Path | None:
    files = sorted(SAVED.glob(f"{model_id}_*.pkl"))
    return files[-1] if files else None


def _models():
    return sorted(json.loads(PARAMS.read_text(encoding="utf-8")).keys())


@pytest.mark.parametrize("model_id", _models())
def test_params_file_carries_the_newest_artifacts_hyperparameters(model_id):
    entry = json.loads(PARAMS.read_text(encoding="utf-8"))[model_id]
    art_path = _newest_artifact(model_id)
    assert art_path is not None, f"{model_id}: no committed artifact"
    version = re.search(r"_(\d{8}_\d{6})\.pkl$", art_path.name).group(1)
    assert entry.get("version") == version, (
        f"{model_id}: params.json is at {entry.get('version')} but the newest "
        f"artifact is {version} -- the backtest is grading stale hyperparameters")
    with open(art_path, "rb") as fh:
        art = pickle.load(fh)
    assert entry["best_params"] == art["best_params"]
