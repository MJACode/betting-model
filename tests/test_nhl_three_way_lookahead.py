"""
Two NHL faults that both cost work every single pass, and both hid behind a
message that named the wrong cause.

1. `nhl_stats_ingestor` opened with a try/except importing `nhl_api` /
   `nhl_api_py` and warned "nhl-api-py not installed" on ImportError. The
   package was installed the whole time — its module is `nhlpy` — and neither
   handle was ever read. Dead code whose only output was a false daily error.

2. The per-event h2h_3way fetch walked the entire NHL event list out of
   season, 422-ing on all ~32 of them, ~1,300 round trips a day.
"""
import io
from datetime import datetime, timedelta, timezone
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _src(rel: str) -> str:
    # encoding is explicit on purpose: this repo's source carries box-drawing
    # characters and read_text() uses the PLATFORM default, which is cp1252 on
    # the machine that actually runs this suite.
    return io.open(REPO / rel, encoding="utf-8").read()


class TestTheDeadNhlApiImport:
    def test_the_ingestor_does_not_import_a_wrapper_that_does_not_exist(self):
        src = _src("data/ingestors/nhl_stats_ingestor.py")
        for bad in ("from nhl_api import", "import nhl_api_py"):
            assert bad not in src, (
                f"{bad!r} is back. The package's module is `nhlpy`; these "
                f"spellings always raise ImportError.")

    def test_the_false_not_installed_warning_is_gone(self):
        src = _src("data/ingestors/nhl_stats_ingestor.py")
        warn = [ln for ln in src.splitlines()
                if "logger.warning" in ln and "nhl-api-py not installed" in ln]
        assert warn == [], (
            "the ingestor still warns that nhl-api-py is not installed; it is, "
            f"and nothing imports it. Found: {warn}")

    def test_the_unused_flag_is_gone_rather_than_left_dangling(self):
        src = _src("data/ingestors/nhl_stats_ingestor.py")
        assert "NHL_API_AVAILABLE" not in src, (
            "NHL_API_AVAILABLE is set but read nowhere in the repo")

    def test_the_unused_requirement_is_dropped(self):
        req = _src("requirements.txt")
        active = [ln for ln in req.splitlines()
                  if ln.strip() and not ln.lstrip().startswith("#")]
        assert not any("nhl-api-py" in ln for ln in active), (
            "nhl-api-py is pinned but nothing imports it")

    def test_nothing_in_the_repo_imports_the_wrapper(self):
        """If this ever fails, the requirement must go back before the import."""
        offenders = []
        for py in REPO.rglob("*.py"):
            if "node_modules" in py.parts or ".git" in py.parts:
                continue
            body = io.open(py, encoding="utf-8").read()
            if re.search(r"^\s*(from|import)\s+nhlpy\b", body, re.M):
                offenders.append(str(py.relative_to(REPO)))
        assert offenders == [], (
            f"these import nhlpy, so requirements.txt must pin it: {offenders}")


class TestTheThreeWayLookaheadWindow:
    """Drives the real loop with a stubbed transport, not a hand-written fixture."""

    def _run(self, monkeypatch, events, offered_for=frozenset()):
        from data.ingestors import odds_ingestor as oi

        calls = []
        monkeypatch.setattr(oi, "_list_events", lambda sk: events)
        monkeypatch.setattr(oi, "REQUEST_SLEEP", 0)
        monkeypatch.setattr(oi, "_process_events", lambda *a, **k: ([], []))

        def fake_event_odds(sport_key, event_id, markets):
            calls.append(event_id)
            return {"id": event_id} if event_id in offered_for else None

        monkeypatch.setattr(oi, "_get_event_odds", fake_event_odds)
        oi._fetch_nhl_3way_per_event("icehockey_nhl", "open", "2026-09-03T00:00:00Z")
        return calls

    @staticmethod
    def _events(days_out):
        now = datetime.now(timezone.utc)
        return [{"id": f"ev{i}",
                 "commence_time": (now + timedelta(days=d)).isoformat().replace(
                     "+00:00", "Z")}
                for i, d in enumerate(days_out)]

    def test_out_of_season_it_makes_no_calls_at_all(self, monkeypatch):
        """The whole point: 32 future events, none near, zero round trips."""
        events = self._events([30 + i for i in range(32)])
        assert self._run(monkeypatch, events) == []

    def test_in_season_it_walks_the_near_slate(self, monkeypatch):
        from data.ingestors import odds_ingestor as oi
        events = self._events([0, 0, 1, 2] + [40, 50, 60])
        calls = self._run(monkeypatch, events)
        assert calls == ["ev0", "ev1", "ev2", "ev3"], (
            f"expected the four near games only, got {calls}")

    def test_a_near_game_is_never_skipped_because_the_market_was_absent_earlier(
            self, monkeypatch):
        """
        The safety property. Giving up on a market that IS offered is the
        failure that hid h2h_3way for months. Every in-window event must be
        called regardless of how many earlier ones came back empty.
        """
        events = self._events([0] * 12)
        calls = self._run(monkeypatch, events, offered_for={"ev11"})
        assert len(calls) == 12, (
            f"stopped after {len(calls)} of 12 near games; the market was "
            f"offered on the last one")

    def test_a_missing_commence_time_fails_open(self, monkeypatch):
        calls = self._run(monkeypatch, [{"id": "ev0"}])
        assert calls == ["ev0"], "an event with no commence_time must not be dropped"

    def test_an_unparseable_commence_time_fails_open(self, monkeypatch):
        calls = self._run(monkeypatch, [{"id": "ev0", "commence_time": "not-a-date"}])
        assert calls == ["ev0"], "an unparseable commence_time must not be dropped"

    def test_a_naive_timestamp_is_treated_as_utc_not_compared_as_a_string(
            self, monkeypatch):
        far = (datetime.now(timezone.utc) + timedelta(days=40))
        events = [{"id": "ev0", "commence_time": far.replace(tzinfo=None).isoformat()}]
        assert self._run(monkeypatch, events) == [], (
            "a naive far-future timestamp should still be out of the window")

    def test_an_offset_timestamp_is_parsed_not_string_matched(self, monkeypatch):
        from data.ingestors import odds_ingestor as oi
        soon = datetime.now(timezone.utc) + timedelta(hours=6)
        events = [{"id": "ev0",
                   "commence_time": soon.astimezone(
                       timezone(timedelta(hours=-4))).isoformat()}]
        assert self._run(monkeypatch, events) == ["ev0"], (
            "a -04:00 offset timestamp inside the window must be kept")
