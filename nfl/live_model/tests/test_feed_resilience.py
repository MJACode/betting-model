"""
Feed host selection, the sports.core parser, and the worker self check.

The reason this file exists: the first version of the live feed used
site.api.espn.com for everything. That host has returned HTTP 403 to this
project's Railway worker every day since early August, which the platform's own
health check records daily. The live model runs on that worker, so the feed as
originally written would never have returned a single state in production, and
nothing in the test suite would have noticed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from live_model.feeds import espn, espn_core  # noqa: E402
from live_model.feeds.odds_live import CreditMeter  # noqa: E402
from live_model.workers.gameday import (  # noqa: E402
    GamedayWorker, check_feed_assumptions,
)

HEALTHY = {
    "period": 3, "clock_seconds": 412, "home_score": 21, "away_score": 17,
    "possession": "home", "yardline_100": 65, "home_timeouts": 2,
    "away_timeouts": 3, "down": 2,
}


def _core_docs():
    return {
        "https://x/score/h": {"value": 21.0},
        "https://x/score/a": {"value": 17.0},
        "https://x/team/12": {"abbreviation": "KC", "id": "12"},
        "https://x/team/33": {"abbreviation": "BAL", "id": "33"},
        "https://x/status": {"period": 3, "clock": 412.0,
                             "type": {"state": "in", "description": "In Progress"}},
        "https://x/situation": {"down": 2, "distance": 7, "yardLine": 35,
                                "homeTimeouts": 2, "awayTimeouts": 3,
                                "possession": {"$ref": "http://x/team/12"}},
    }


def _core_event():
    return {"id": "401", "competitions": [{
        "status": {"$ref": "http://x/status"},
        "situation": {"$ref": "http://x/situation"},
        "competitors": [
            {"homeAway": "home", "score": {"$ref": "http://x/score/h"},
             "team": {"$ref": "http://x/team/12"}},
            {"homeAway": "away", "score": {"$ref": "http://x/score/a"},
             "team": {"$ref": "http://x/team/33"}},
        ]}]}


def _fetch(docs):
    return lambda url: docs.get(espn_core._https(url), {})


# ------------------------------------------------------------ core parser
def test_core_parser_chases_refs_and_emits_the_site_api_shape():
    """Both parsers must emit the same keys, or state.from_espn silently
    behaves differently depending on which host answered."""
    parsed = espn_core.parse_core_event(_core_event(), _fetch(_core_docs()))
    assert parsed is not None
    for key in ("period", "clock_seconds", "home_score", "away_score",
                "possession", "down", "distance", "yardline_100",
                "home_timeouts", "away_timeouts", "plays_run", "state",
                "home_abbrev", "away_abbrev"):
        assert key in parsed, key
    assert parsed["home_score"] == 21 and parsed["away_score"] == 17
    assert parsed["possession"] == "home"
    assert parsed["yardline_100"] == 65        # own 35 means 65 to go


def test_core_http_refs_are_forced_to_https():
    """Core mixes schemes. Following an http ref is an unnecessary downgrade
    and some proxies drop it outright."""
    assert espn_core._https("http://a/b") == "https://a/b"
    assert espn_core._https("https://a/b") == "https://a/b"


def test_core_normalises_halftime():
    docs = _core_docs()
    docs["https://x/status"] = {"period": 2, "clock": 0.0,
                                "type": {"state": "in", "description": "Halftime"}}
    parsed = espn_core.parse_core_event(_core_event(), _fetch(docs))
    assert parsed["period"] == 2 and parsed["clock_seconds"] == 0


def test_core_refuses_rather_than_defaulting_a_missing_score():
    broken = {"id": "x", "competitions": [{
        "status": {"$ref": "http://x/status"},
        "competitors": [{"homeAway": "home", "team": {}},
                        {"homeAway": "away", "team": {}}]}]}
    assert espn_core.parse_core_event(broken, _fetch(_core_docs())) is None


def test_core_drops_an_out_of_range_yardline_instead_of_clamping():
    """A wrong field position is worse for the model than a missing one."""
    assert espn_core._yardline_from_core({"yardLine": 350}, "home") is None
    assert espn_core._yardline_from_core({"yardLine": 35}, "home") == 65


# --------------------------------------------------------- host selection
def test_core_is_tried_first(monkeypatch):
    """site.api is measured as blocked from the worker. Defaulting to it would
    mean every live poll fails before it starts."""
    order = []
    monkeypatch.setattr(espn_core, "make_fetcher", lambda **k: (lambda u: {}))
    monkeypatch.setattr(espn_core, "fetch_live_events",
                        lambda f, now=None: order.append("core") or [])
    monkeypatch.setattr(espn, "fetch_scoreboard",
                        lambda **k: order.append("site") or {"events": []})
    _, host = espn.live_events()
    assert order == ["core"]
    assert host == "sports.core"


def test_site_api_is_the_fallback_when_core_fails(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("core 403")
    monkeypatch.setattr(espn_core, "make_fetcher", lambda **k: (lambda u: {}))
    monkeypatch.setattr(espn_core, "fetch_live_events", boom)
    monkeypatch.setattr(espn, "fetch_scoreboard", lambda **k: {"events": []})
    _, host = espn.live_events()
    assert host == "site.api"


def test_both_hosts_failing_raises_rather_than_returning_nothing(monkeypatch):
    """An empty list would read as 'no games are live', which on a Sunday is a
    silent outage. A raise is what makes the worker alert."""
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(espn_core, "make_fetcher", lambda **k: (lambda u: {}))
    monkeypatch.setattr(espn_core, "fetch_live_events", boom)
    monkeypatch.setattr(espn, "fetch_scoreboard", boom)
    with pytest.raises(RuntimeError):
        espn.live_events()


# ------------------------------------------------------------- self check
def test_a_healthy_payload_raises_no_problems():
    assert check_feed_assumptions(HEALTHY) == []


@pytest.mark.parametrize("mutation,expect", [
    ({"clock_seconds": None}, "clock"),
    ({"clock_seconds": 4000}, "clock"),          # milliseconds, not seconds
    ({"period": 99}, "period"),
    ({"possession": "12"}, "possession"),        # raw team id, not a side
    ({"yardline_100": 350}, "yardline"),
    ({"home_score": "21"}, "home_score"),        # arrives as a string
    ({"down": 7}, "down"),
    ({"home_timeouts": 9}, "home_timeouts"),
])
def test_each_realistic_shape_break_is_caught(mutation, expect):
    problems = check_feed_assumptions({**HEALTHY, **mutation})
    assert problems and any(expect in p for p in problems)


def test_the_worker_self_checks_once_and_alerts_on_a_broken_feed(monkeypatch):
    """
    The whole point of running this in the worker rather than as a script
    someone remembers: a shape change surfaces as an alert on the first poll of
    the day instead of as a quiet losing Sunday.
    """
    broken = {"event_id": "e1", "home": "KC", "away": "BAL", "state": "in",
              "state_name": "", "period": 3, "clock_seconds": None,
              "home_score": 14, "away_score": 10, "possession": "12",
              "down": None, "distance": None, "yardline_100": None,
              "home_timeouts": 3, "away_timeouts": 3, "plays_run": 0,
              "home_plays": 0, "away_plays": 0, "home_pass_plays": 0,
              "away_pass_plays": 0}
    monkeypatch.setattr(espn_core, "make_fetcher", lambda **k: (lambda u: {}))
    monkeypatch.setattr(espn_core, "fetch_live_events", lambda f, now=None: [broken])

    ops = []

    class FakeOdds:
        def fetch_anchor(self, **k):
            return []

        def fetch_event_markets(self, eid, markets, **k):
            return []

    w = GamedayWorker(odds_client=FakeOdds(), meter=CreditMeter(),
                      alerter=ops.append)
    s = w.tick(now=1000.0)
    assert "feed_assumptions" in s["errors"]
    assert ops and "BROKEN" in ops[0]["ops"]

    # Once per run, not once per game: a nine game slate must not fire nine
    # identical alerts.
    ops.clear()
    w.tick(now=1100.0)
    assert ops == []


def test_a_host_switch_is_alerted(monkeypatch):
    """Losing the primary path is how the WNBA feed silently lost a week of
    finals. A switch must be visible, not merely survivable."""
    monkeypatch.setattr(espn_core, "make_fetcher", lambda **k: (lambda u: {}))
    monkeypatch.setattr(espn_core, "fetch_live_events", lambda f, now=None: [])
    monkeypatch.setattr(espn, "fetch_scoreboard", lambda **k: {"events": []})
    ops = []
    w = GamedayWorker(dry_run=True, alerter=ops.append)
    w.tick(now=1000.0)
    assert ops == []                      # first observation is not a change

    def boom(*a, **k):
        raise RuntimeError("core down")
    monkeypatch.setattr(espn_core, "fetch_live_events", boom)
    w.tick(now=2000.0)
    assert any("host changed" in o["ops"] for o in ops)


# --------------------------------------------------------------- idle exit
class _ScriptedTick:
    """A worker whose tick() replays a fixed sequence of summaries."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def tick(self, now=None):
        i = min(self.calls, len(self.script) - 1)
        self.calls += 1
        live, hunting = self.script[i]
        return {"live": live, "hunting": hunting, "anchor_polls": 0,
                "deriv_polls": 0, "prop_polls": 0, "errors": []}


def _run_scripted(script, idle_exit_ticks=4, max_ticks=None):
    w = GamedayWorker(dry_run=True)
    scripted = _ScriptedTick(script)
    w.tick = scripted.tick
    ticks = w.run(max_ticks=max_ticks, sleep_sec=0,
                  idle_exit_ticks=idle_exit_ticks)
    return ticks, scripted.calls


def test_run_exits_when_the_slate_is_idle():
    """
    The scheduler runs this every 10 minutes with max_instances=1 and relaunches
    after it ends. A run() that never returned would turn that cron into a
    launch-once, so a wedged process would cost the season rather than one gap.
    """
    ticks, _ = _run_scripted([(0, 0)], idle_exit_ticks=4)
    assert ticks == 4


def test_a_live_game_resets_the_idle_counter():
    # three idle, then a live game, then idle again: it must not exit at the
    # first run of three, and must need a fresh four in a row afterwards.
    script = [(0, 0), (0, 0), (0, 0), (1, 0)] + [(0, 0)] * 10
    ticks, _ = _run_scripted(script, idle_exit_ticks=4)
    assert ticks == 8


def test_a_hunted_game_counts_as_busy():
    script = [(0, 0), (0, 1)] + [(0, 0)] * 10
    ticks, _ = _run_scripted(script, idle_exit_ticks=4)
    assert ticks == 6


def test_idle_exit_can_be_disabled_for_a_bounded_run():
    ticks, _ = _run_scripted([(0, 0)], idle_exit_ticks=None, max_ticks=7)
    assert ticks == 7
