"""The model's own inputs refresh intraday, and do so without hammering anyone.

WHY. The refresh pass re-read the MARKET every 10-60 minutes -- odds, prop
odds, lineups, public splits -- but re-read the MODEL'S INPUTS only at 6am. So
a price could drift all day against a view of who was hurt, and what the
weather would be, that was frozen at breakfast.

mike, 2026-08-30: "shouldnt we be modeling on datapoints like pitchers and
injuries and the like? I would think this is a model assessment." He is right,
and it is a PREREQUISITE rather than a parallel improvement: taking a pick that
crosses late, on inputs that are hours stale, is betting against information we
chose not to re-read.

The guard is a MAX AGE, not a cadence. 42 passes a day must not become 42 ESPN
sweeps -- ESPN has IP-blocked this worker twice (sessions 112, 115) -- and a
guard expressed in minutes holds however often the pass runs.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
import run_pipeline as rp


def _age(monkeypatch, minutes):
    """Pin the observed age. monkeypatch restores it, so one case cannot leak
    into the next."""
    monkeypatch.setattr(rp, "_minutes_since", lambda *a, **k: minutes)


def test_fresh_data_is_skipped(monkeypatch):
    _age(monkeypatch, 10.0)
    assert rp._is_fresh("Injuries", "sql", (), 45) is True


def test_stale_data_is_refetched(monkeypatch):
    _age(monkeypatch, 90.0)
    assert rp._is_fresh("Injuries", "sql", (), 45) is False


def test_an_unknown_age_refetches_rather_than_skipping(monkeypatch):
    """None means "no rows, unparseable stamp, or the query failed". Every one
    of those must cause an EXTRA fetch, never a skipped one -- being wrong about
    the age must not silently freeze an input for a day."""
    _age(monkeypatch, None)
    assert rp._is_fresh("Injuries", "sql", (), 45) is False


def test_the_boundary_refetches(monkeypatch):
    _age(monkeypatch, 45.0)
    assert rp._is_fresh("Injuries", "sql", (), 45) is False


def test_the_6am_pipeline_is_never_throttled():
    """The daily run passes no max age, so it always fetches. A guard meant for
    the intraday cadence must not be able to skip the one run that seeds the
    day."""
    import inspect
    for fn in (rp.step_injuries, rp.step_weather):
        sig = inspect.signature(fn)
        assert sig.parameters["max_age_min"].default is None, fn.__name__


def test_the_refresh_pass_runs_both():
    chain = (Path(__file__).parent.parent / "scripts/refresh_pass.sh").read_text(encoding="utf-8")
    assert "step injuries-refresh" in chain
    assert "step weather-refresh" in chain
    # and must still run BEFORE scoring, or the fresher inputs miss the pass
    assert chain.index("step injuries-refresh") < chain.index("step scoring")
    assert chain.index("step weather-refresh") < chain.index("step scoring")


def test_the_max_ages_are_sane_and_overridable():
    """Env-overridable on purpose: ESPN has blocked this worker twice, and the
    cadence must be dialable back without a deploy."""
    assert 5 <= config.REFRESH_INJURY_MAX_AGE_MIN <= 24 * 60
    assert 5 <= config.REFRESH_WEATHER_MAX_AGE_MIN <= 24 * 60
    src = (Path(__file__).parent.parent / "config.py").read_text(encoding="utf-8")
    assert 'os.environ.get("REFRESH_INJURY_MAX_AGE_MIN"' in src
    assert 'os.environ.get("REFRESH_WEATHER_MAX_AGE_MIN"' in src


def test_both_steps_are_dispatchable():
    src = (Path(__file__).parent.parent / "run_pipeline.py").read_text(encoding="utf-8")
    for step in ("injuries-refresh", "weather-refresh"):
        assert f'"{step}"' in src, f"{step} missing from choices/dispatch"
