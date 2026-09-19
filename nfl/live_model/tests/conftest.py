"""The executor's own tests are about its guards, sizing and audit trail.

Two platform-wide things arrived on 2026-09-19 that would otherwise change
what every fixture here does: the global EV floor (config.GLOBAL_MIN_EV, tested
in tests/test_global_ev_floor.py) and the promoted calibration maps every model
now carries (models/probability_calibration.py PHASE 3). Both are held at
identity here so a lane's OWN threshold is what these tests exercise, and so
the suite does not read production's map table.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _platform_gates_off(monkeypatch):
    import importlib
    config = importlib.import_module("config")
    sc = importlib.import_module("models.scorer")   # the platform's, on purpose
    monkeypatch.setattr(config, "GLOBAL_MIN_EV", -1.0)   # cannot bind
    monkeypatch.setattr(sc, "_CAL_CACHE", {})
