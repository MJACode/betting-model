"""Weather lands for every date the prop scorer prices, at the game's own hour.

Three things were wrong on 2026-09-10 (docs/sessions/2026-09.md, session 276):

1. ``step_weather`` fetched ``run_date`` only, while ``step_prop_scoring``
   priced ``run_date`` through ``GAME_SCORE_AHEAD_DAYS``. Tomorrow's game had
   no weather row, the scorer filled the gap with 0.0, and two picks went out
   priced for a 0°F game.
2. ``_fetch_open_meteo`` asked the forecast endpoint for
   ``forecast_days = min(days_old + 2, 16)``, which for a FUTURE date is one
   day -- today only. Measured live: ``forecast_days=1`` returned
   2026-09-10T00:00..23:00 for a 2026-09-11 game. The matcher then took the
   last hour at or before the target and returned yesterday evening's weather
   for tomorrow's game. A recent past date did the mirror image: the forecast
   window starts today, so a 2-day-old game got today's 00:00 hour.
3. The target hour was 7pm local by longitude, not the game's start.

Now: the window is fetched, the request always covers the target hour (
``past_days`` for recent past, enough ``forecast_days`` for the future, one
extra archive day for the UTC roll-over of a late West Coast start), the hour
comes from ``games.commence_time`` when known, and a series that does not
contain that hour returns None rather than the wrong day.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

ROOT = Path(__file__).parent.parent


class _Resp:
    def __init__(self, times: list[str]):
        self._times = times

    def raise_for_status(self):
        pass

    def json(self):
        n = len(self._times)
        return {"hourly": {
            "time": self._times,
            # temperature encodes the hour index so a test can tell WHICH hour came back
            "temperature_2m": [float(i) for i in range(n)],
            "windspeed_10m": [5.0] * n,
            "winddirection_10m": [180.0] * n,
            "precipitation": [0.0] * n,
        }}


def _hours(start: date, days: int) -> list[str]:
    return [f"{(start + timedelta(days=d)).isoformat()}T{h:02d}:00"
            for d in range(days) for h in range(24)]


@pytest.fixture
def captured(monkeypatch):
    """Patch requests.get inside the ingestor; the fake answers with a
    series covering exactly what the request asked for."""
    from data.ingestors import weather_ingestor as w
    calls: list[dict] = []

    def fake_get(url, params=None, timeout=None):
        calls.append({"url": url, "params": dict(params or {})})
        today = date.today()
        if url == w._HISTORICAL_API:
            start = date.fromisoformat(params["start_date"])
            end = date.fromisoformat(params["end_date"])
            return _Resp(_hours(start, (end - start).days + 1))
        past = int(params.get("past_days", 0))
        fwd = int(params.get("forecast_days", 1))
        return _Resp(_hours(today - timedelta(days=past), past + fwd))

    monkeypatch.setattr(w.requests, "get", fake_get)
    return calls


class TestTheRequestCoversTheTargetHour:
    def test_a_future_date_asks_for_enough_forecast_days(self, captured):
        from data.ingestors import weather_ingestor as w
        target = date.today() + timedelta(days=3)
        wx = w._fetch_open_meteo(47.59, -122.33, target.isoformat(),
                                 commence_time=f"{target.isoformat()}T02:10:00+00:00")
        p = captured[-1]["params"]
        assert captured[-1]["url"] == w._FORECAST_API
        assert p["forecast_days"] >= 5, p          # today .. target+1 at least
        assert wx is not None

    def test_a_recent_past_date_asks_for_past_days(self, captured):
        from data.ingestors import weather_ingestor as w
        target = date.today() - timedelta(days=2)
        wx = w._fetch_open_meteo(47.59, -122.33, target.isoformat(),
                                 commence_time=f"{target.isoformat()}T23:10:00+00:00")
        p = captured[-1]["params"]
        assert p["past_days"] >= 2, p
        assert wx is not None

    def test_the_archive_window_covers_the_utc_rollover(self, captured):
        """A 7:10pm Pacific start is 02:10 UTC the NEXT calendar day."""
        from data.ingestors import weather_ingestor as w
        target = date.today() - timedelta(days=40)
        nxt = target + timedelta(days=1)
        wx = w._fetch_open_meteo(47.59, -122.33, target.isoformat(),
                                 commence_time=f"{nxt.isoformat()}T02:10:00+00:00")
        p = captured[-1]["params"]
        assert captured[-1]["url"] == w._HISTORICAL_API
        assert p["start_date"] == target.isoformat()
        assert p["end_date"] >= nxt.isoformat(), p
        assert wx is not None


class TestTheHourIsTheGamesOwn:
    def test_commence_time_picks_that_exact_hour(self, captured):
        from data.ingestors import weather_ingestor as w
        target = date.today() + timedelta(days=1)
        wx = w._fetch_open_meteo(47.59, -122.33, target.isoformat(),
                                 commence_time=f"{target.isoformat()}T02:10:00+00:00")
        # temperature_2m encodes the index; the series starts today 00:00, so
        # tomorrow 02:00 is index 26.
        assert wx is not None
        assert wx["temp_f"] == w._celsius_to_f(26.0)

    def test_minutes_round_to_the_nearest_hour(self, captured):
        from data.ingestors import weather_ingestor as w
        target = date.today() + timedelta(days=1)
        wx = w._fetch_open_meteo(47.59, -122.33, target.isoformat(),
                                 commence_time=f"{target.isoformat()}T02:41:00+00:00")
        assert wx["temp_f"] == w._celsius_to_f(27.0)

    def test_without_a_start_time_the_local_evening_default_still_works(self, captured):
        from data.ingestors import weather_ingestor as w
        target = date.today() + timedelta(days=1)
        wx = w._fetch_open_meteo(47.59, -122.33, target.isoformat())
        assert wx is not None

    def test_a_series_without_the_hour_returns_none_not_another_day(self, monkeypatch):
        """THE 2026-09-10 FAILURE. The old matcher took the last hour at or
        before the target, which for a series that stops today is 23:00
        tonight -- reported as tomorrow's game-time weather."""
        from data.ingestors import weather_ingestor as w
        today = date.today()
        monkeypatch.setattr(w.requests, "get",
                            lambda url, params=None, timeout=None: _Resp(_hours(today, 1)))
        target = today + timedelta(days=1)
        wx = w._fetch_open_meteo(47.59, -122.33, target.isoformat(),
                                 commence_time=f"{target.isoformat()}T02:10:00+00:00")
        assert wx is None


class TestTheStoreReadsTheStartTime:
    def test_the_games_query_selects_commence_time(self):
        import inspect
        from data.ingestors.weather_ingestor import fetch_and_store_weather_for_date
        src = inspect.getsource(fetch_and_store_weather_for_date)
        assert "commence_time" in src

    def test_only_missing_skips_games_that_already_have_a_row(self):
        import inspect
        from data.ingestors.weather_ingestor import fetch_and_store_weather_for_date
        src = inspect.getsource(fetch_and_store_weather_for_date)
        assert "only_missing" in src and "w.game_id IS NULL" in src


class TestTheWeatherStepWalksTheWindow:
    def _run(self, monkeypatch, ahead: int):
        import run_pipeline as rp
        from data.ingestors import weather_ingestor as w
        seen: list[str] = []

        class _Conn:
            def commit(self):
                pass

            def close(self):
                pass

        monkeypatch.setattr(w, "fetch_and_store_weather_for_date",
                            lambda d, conn=None: seen.append(d) or 1)
        monkeypatch.setattr("data.db.get_connection", lambda: _Conn())
        monkeypatch.setattr(rp, "_is_fresh", lambda *a, **k: False)
        assert rp.step_weather("2026-09-10", ahead_days=ahead) is True
        return seen

    def test_it_fetches_run_date_through_the_lookahead(self, monkeypatch):
        seen = self._run(monkeypatch, ahead=2)
        assert seen == ["2026-09-10", "2026-09-11", "2026-09-12"]

    def test_zero_ahead_is_today_only(self, monkeypatch):
        assert self._run(monkeypatch, ahead=0) == ["2026-09-10"]

    def test_the_default_window_is_the_scorers(self):
        import inspect
        import run_pipeline as rp
        assert "GAME_SCORE_AHEAD_DAYS" in inspect.getsource(rp.step_weather)

    def test_one_bad_date_does_not_cost_the_others(self, monkeypatch):
        import run_pipeline as rp
        from data.ingestors import weather_ingestor as w
        seen: list[str] = []

        class _Conn:
            def commit(self):
                pass

            def close(self):
                pass

        def fetch(d, conn=None):
            seen.append(d)
            if d == "2026-09-11":
                raise RuntimeError("rate limited")
            return 1

        monkeypatch.setattr(w, "fetch_and_store_weather_for_date", fetch)
        monkeypatch.setattr("data.db.get_connection", lambda: _Conn())
        monkeypatch.setattr(rp, "_is_fresh", lambda *a, **k: False)
        assert rp.step_weather("2026-09-10", ahead_days=2) is False
        assert seen == ["2026-09-10", "2026-09-11", "2026-09-12"]

    def test_freshness_is_checked_per_date(self, monkeypatch):
        """Tomorrow being fresh must not skip today, and vice versa."""
        import run_pipeline as rp
        from data.ingestors import weather_ingestor as w
        seen: list[str] = []
        asked: list[tuple] = []

        class _Conn:
            def commit(self):
                pass

            def close(self):
                pass

        monkeypatch.setattr(w, "fetch_and_store_weather_for_date",
                            lambda d, conn=None: seen.append(d) or 1)
        monkeypatch.setattr("data.db.get_connection", lambda: _Conn())
        monkeypatch.setattr(rp, "_is_fresh",
                            lambda label, sql, params, max_age: asked.append(params) or params == ("2026-09-11",))
        rp.step_weather("2026-09-10", max_age_min=60, ahead_days=1)
        assert asked == [("2026-09-10",), ("2026-09-11",)]
        assert seen == ["2026-09-10"]


class TestTheUmpireLandsOnEveryPass:
    def test_the_refresh_pass_runs_the_umpire_step(self):
        src = (ROOT / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")
        assert "par umpires" in src
