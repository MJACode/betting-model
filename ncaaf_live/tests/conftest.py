"""Every model decides on its promoted calibration map since 2026-09-19
(models/probability_calibration.py PHASE 3), and the NCAAF loop reads it
through models.scorer._calibrated. Held at identity here so these tests
exercise the engine and its guards, not whatever production's map table holds
today. tests/test_global_ev_floor.py is where the map's effect is tested.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _identity_maps(monkeypatch):
    import models.scorer as sc
    monkeypatch.setattr(sc, "_CAL_CACHE", {})
