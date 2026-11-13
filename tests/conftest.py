"""
conftest.py — Shared pytest fixtures for the betting model test suite.
"""

import sys
import sqlite3
from pathlib import Path
import pytest

# Add project root to sys.path so all modules resolve correctly
sys.path.insert(0, str(Path(__file__).parent.parent))

# The call logger, installed BEFORE anything imports config. config.py installs
# it in every process (so a paid call is logged however the process started),
# and its writer would send each recorded call to DATABASE_URL -- which on a
# machine with the main checkout's .env is production. Installed here first,
# with no writer, the suite's calls stay on the in-memory queue the probe's
# own tests read (tests/test_monitoring.py), and nothing a test does reaches
# api_call_log. tests/test_odds_call_log_everywhere.py runs the real writer
# in child processes against a sqlite stand-in instead.
from monitoring import probe as _api_call_log                       # noqa: E402
_api_call_log.install("pytest", start_writer=False)

from data.db_setup import SCHEMA_SQL                                 # noqa: E402


def _refuse_real_odds_api_calls() -> None:
    """A test that forgets to mock fails here instead of spending credits.

    The suite writes no call to api_call_log (above), so a real Odds API call
    from a test would be the one paid call the log could not have. On a machine
    with the main checkout's .env, ODDS_API_KEY is loaded and the call bills.
    So the transport refuses the host: nothing goes out, nothing is billed, and
    the test that tried says so. Below Session.request, so the probe's own
    wrapper still sees and records the attempt, and a test that patches
    Session.request or a module's requests.get never reaches this.
    """
    import requests.adapters as _adapters
    from monitoring import registry as _registry
    original = _adapters.HTTPAdapter.send
    if getattr(original, "_refuses_odds_api", False):
        return

    def send(self, request, *args, **kwargs):
        if _registry.classify(getattr(request, "url", "") or "")[1] == "The Odds API":
            raise RuntimeError(
                "a test sent a real request to the Odds API; mock it "
                "(tests/conftest.py refuses the host so no test can bill credits)")
        return original(self, request, *args, **kwargs)

    send._refuses_odds_api = True
    _adapters.HTTPAdapter.send = send


_refuse_real_odds_api_calls()


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
def _morning_disk_clock_outside_the_window(monkeypatch):
    """Pin the morning-disk clock to 15:00 ET.

    The scheduler wrapper asks tracking.morning_disk.now_et() before a job
    runs. A test that calls a wrapped job while CI itself is inside
    05:40-07:15 ET would otherwise be turned away, or beat "skipped", for a
    reason that has nothing to do with the test. A test of the window sets
    now_et itself.
    """
    from datetime import datetime
    from tracking import morning_disk
    monkeypatch.setattr(
        morning_disk, "now_et",
        lambda: datetime(2026, 11, 12, 15, 0, tzinfo=morning_disk.ET),
    )
