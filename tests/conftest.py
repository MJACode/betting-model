"""
conftest.py — Shared pytest fixtures for the betting model test suite.
"""

import sys
import sqlite3
from pathlib import Path
import pytest

# Add project root to sys.path so all modules resolve correctly
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.db_setup import SCHEMA_SQL


@pytest.fixture
def db_conn():
    """In-memory SQLite database with the full schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _platform_gates_at_identity(monkeypatch):
    """Two platform-wide things arrived on 2026-09-19 that would otherwise move
    every fixture in this directory: the global EV floor (config.GLOBAL_MIN_EV)
    and the promoted calibration map every model now carries
    (models/probability_calibration.py PHASE 3, read through
    models.scorer._CAL_CACHE). Both are held at identity here so a test
    exercises the mechanics it names, and so the suite never reads production's
    map table -- a promotion must not be able to move a fixture. The floor and
    the map are tested on their own in tests/test_global_ev_floor.py, which
    sets both explicitly; a test that wants either sets it the same way.
    """
    import config
    import models.scorer as sc
    # -1.0, not 0.0: a model whose stored probability IS the price's implied
    # (mlb_total_public_fade) has a negative EV at any price, so 0.0 would
    # still refuse it; -1.0 is "the floor cannot bind".
    #
    # config.MODEL_OWN_EV_FLOOR is DELIBERATELY NOT held at identity. Since
    # 2026-09-20 nearly every model carries an entry there, and min_ev_for
    # checks it BEFORE the global floor, so a model's own floor still binds
    # inside a test even with GLOBAL_MIN_EV at -1.0. Emptying it here would
    # make the tests that assert the floors (tests/test_config.py) vacuous. A
    # test whose fixture trips a floor it does not mean to exercise clears the
    # dict itself, in one line, where a reader can see it:
    #     monkeypatch.setattr(config, "MODEL_OWN_EV_FLOOR", {})
    monkeypatch.setattr(config, "GLOBAL_MIN_EV", -1.0)
    monkeypatch.setattr(sc, "_CAL_CACHE", {})


@pytest.fixture(autouse=True)
def _no_live_mlb_schedule(monkeypatch):
    """data/mlb_game_id.py reads the MLB Stats API schedule to tell a
    doubleheader's game 2 from game 1. No test may reach the network for it,
    so it returns no games here -- every game is game 1, the pre-2026-09-25 id
    -- and a test that means to exercise a doubleheader replaces
    `_fetch_schedule` itself (tests/test_mlb_doubleheader_ids.py)."""
    import data.mlb_game_id as mgi
    mgi.clear_cache()
    monkeypatch.setattr(mgi, "_fetch_schedule", lambda game_date: [])
    yield
    mgi.clear_cache()
