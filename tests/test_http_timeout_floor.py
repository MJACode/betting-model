"""
Every outbound request gets a deadline, or a pass can lose its whole slot.

On 2026-08-30 refresh passes were routinely running 13-18 minutes against a
10-minute evening cadence, and 10 of 32 passes in a 30-hour window never
recorded a finish. The worker was at 1.1GB of 8GB and 1.4 of 8 CPU throughout,
so it was neither memory nor compute -- it was blocked on a socket.

Our own ingestors all pass an explicit timeout. The libraries we do not own do
not: MLB-StatsAPI (which settle_picks calls five times per run), nba_api and
pybaseball all hand `requests` no timeout at all, and `requests` then waits
forever. The floor lives in the probe because that is already the one place
every library's calls pass through.

The property that actually matters is the second test: a deliberate timeout is
never overridden. A floor that quietly re-times existing calls would be a
behaviour change dressed as a safety net.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

requests_sessions = pytest.importorskip("requests.sessions")

from monitoring import probe  # noqa: E402


@pytest.fixture
def clean_requests(monkeypatch):
    """Restore Session.request and the module's install flags around each test."""
    original = requests_sessions.Session.request
    monkeypatch.setattr(probe, "_installed", False)
    monkeypatch.setattr(probe, "_timeout_floor_installed", False)
    seen: list[dict] = []

    def fake(self, method, url, *args, **kwargs):
        seen.append(dict(kwargs))
        raise RuntimeError("no network in tests")

    requests_sessions.Session.request = fake
    try:
        yield seen
    finally:
        requests_sessions.Session.request = original
        probe._installed = False
        probe._timeout_floor_installed = False


def _call(**kwargs):
    try:
        requests_sessions.Session.request(
            requests_sessions.Session(), "GET", "https://example.test/x", **kwargs)
    except RuntimeError:
        pass


def test_a_call_with_no_timeout_gets_one(clean_requests):
    assert probe.install_timeout_floor() is True
    _call()
    assert clean_requests[-1]["timeout"] == probe._DEFAULT_TIMEOUT


def test_an_explicit_timeout_is_never_overridden(clean_requests):
    """
    The whole repo's deliberate choices run from 5s to 300s. The floor exists to
    catch calls that set NOTHING; silently re-timing the rest would be a
    behaviour change, not a safety net.
    """
    probe.install_timeout_floor()
    for explicit in (5, 30, 300, (3.05, 27)):
        _call(timeout=explicit)
        assert clean_requests[-1]["timeout"] == explicit


def test_the_floor_is_looser_than_every_deliberate_timeout_in_the_repo():
    """
    A floor tighter than a real call would break it. 300s is the largest
    timeout anyone in this repo has chosen on purpose, so the read deadline
    must clear it -- the floor may only ever catch a hang.
    """
    connect, read = probe._DEFAULT_TIMEOUT
    assert connect <= 30, "a connect that slow is never legitimate"
    assert read >= 120, "must not undercut a slow-but-working call"


def test_the_deadline_survives_telemetry_being_turned_off(clean_requests, monkeypatch):
    """
    The kill switch turns off the dashboard, not the reliability guarantee. An
    unbounded socket wait is precisely the failure that leaves nothing to
    observe, so it must not be the thing that disappears with observability.
    """
    monkeypatch.setenv("PIPELINE_TELEMETRY", "0")
    assert probe.install("pipeline") is False          # telemetry declined...
    _call()
    assert clean_requests[-1]["timeout"] == probe._DEFAULT_TIMEOUT   # ...deadline held


def test_the_full_probe_also_applies_the_deadline(clean_requests, monkeypatch):
    monkeypatch.setenv("PIPELINE_TELEMETRY", "1")
    assert probe.install("pipeline", start_writer=False) is True
    _call()
    assert clean_requests[-1]["timeout"] == probe._DEFAULT_TIMEOUT


def test_the_floor_and_the_probe_do_not_stack(clean_requests, monkeypatch):
    """Two wrappers would double every call's frames to apply one default."""
    monkeypatch.setenv("PIPELINE_TELEMETRY", "1")
    probe.install_timeout_floor()
    probe.install("pipeline", start_writer=False)
    unwrapped = getattr(requests_sessions.Session.request, "__wrapped__", None)
    assert unwrapped is not None
    assert getattr(unwrapped, "__wrapped__", None) is None, (
        "the probe wrapped the floor instead of replacing it")


def test_installing_twice_is_a_no_op(clean_requests):
    assert probe.install_timeout_floor() is True
    assert probe.install_timeout_floor() is False


def test_the_deadline_is_env_overridable():
    """So a slow feed can be given room without a deploy."""
    src = (Path(__file__).parent.parent / "monitoring" / "probe.py").read_text()
    assert 'os.environ.get("HTTP_CONNECT_TIMEOUT"' in src
    assert 'os.environ.get("HTTP_READ_TIMEOUT"' in src
