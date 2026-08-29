"""
The gameday loop's polling cadence.

Context: the loop ran on ONE flat `time.sleep(45)` covering both feeds, so the
free state feed was throttled to the speed of the metered odds feed, and the
real interval was always 45s PLUS however long the feeds took. Moving to a
10-15s cadence is not a one-constant change - three things had to hold, and
each is pinned below:

  1. the sleep is the REMAINDER of the interval, not a flat sleep after work
  2. the metered odds feed keeps its own, slower cadence
  3. nothing ever prices against a line that stopped refreshing
"""

from __future__ import annotations

import ast
import time
from pathlib import Path

import pytest

from ncaaf_live import config
from ncaaf_live.feeds.odds_live import LiveOddsFeed

GAMEDAY = Path(__file__).parent.parent / "gameday.py"


# ── 1. cadence configuration ────────────────────────────────────────────────
def test_state_cadence_is_in_the_ten_to_fifteen_second_band():
    assert 10 <= config.POLL_STATE_SEC <= 15


def test_odds_cadence_is_independent_of_state_cadence():
    """State is free, odds are billed. Collapsing them is the bug this fixes:
    they must be separately settable."""
    assert config.POLL_ODDS_SEC >= config.POLL_STATE_SEC


def test_cadence_is_env_overridable_without_a_code_edit(monkeypatch):
    monkeypatch.setenv("NCAAF_LIVE_POLL_STATE_SEC", "12")
    monkeypatch.setenv("NCAAF_LIVE_POLL_ODDS_SEC", "20")
    import importlib
    reloaded = importlib.reload(config)
    try:
        assert reloaded.POLL_STATE_SEC == 12
        assert reloaded.POLL_ODDS_SEC == 20
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_credit_cap_covers_a_full_saturday_at_the_configured_cadence():
    """The cap was a flat 5000, sized for the old 60s debounce. At a faster
    cadence that is exhausted mid-afternoon - so it must scale with the
    cadence, or it silently stops the odds feed partway through the slate."""
    twelve_hours = 12 * 60 * 60
    fetches = twelve_hours / config.POLL_ODDS_SEC
    worst_case_credits = fetches * 4          # header-measured ~3-4 per fetch
    assert config.LIVE_ODDS_SESSION_CREDIT_CAP > worst_case_credits


# ── 2. the loop sleeps the remainder ────────────────────────────────────────
def _main_source() -> str:
    tree = ast.parse(GAMEDAY.read_text())
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "main")
    return ast.unparse(fn)


def test_loop_sleeps_the_remainder_not_a_flat_interval():
    """A flat sleep after the work makes the true cadence interval + work.
    At 45s that error was ~10%; at 10s it dominates."""
    src = _main_source()
    assert "time.monotonic()" in src, "no pass start timestamp"
    assert "max(0.0, a.interval - elapsed)" in src, (
        "the loop must sleep only the remaining time in the interval")


def test_loop_warns_when_a_pass_overruns_its_interval():
    """When the feeds are slower than the target, that must be visible rather
    than silent drift."""
    assert "elapsed > a.interval" in _main_source()


def test_odds_fetch_uses_the_odds_cadence_not_the_loop_cadence():
    assert "min_interval=a.odds_interval" in _main_source()


# ── 3. never price a line that stopped refreshing ───────────────────────────
def _feed_with_payload(age_sec: float) -> LiveOddsFeed:
    feed = LiveOddsFeed()
    feed.last_payload = [{"home_team": "TCU"}]
    feed.last_fetch_ts = time.time() - age_sec
    return feed


def test_cached_odds_are_served_while_fresh():
    feed = _feed_with_payload(age_sec=5)
    assert feed.fetch(min_interval=30) == [{"home_team": "TCU"}]


def test_credit_cap_reports_no_odds_rather_than_a_frozen_line():
    """The old code returned the cached payload forever once the cap was hit,
    so the loop would have gone on pricing a line frozen hours earlier."""
    feed = _feed_with_payload(age_sec=config.LIVE_ODDS_MAX_AGE_SEC + 60)
    feed.credits_used = config.LIVE_ODDS_SESSION_CREDIT_CAP
    assert feed.fetch(min_interval=0) is None


def test_credit_cap_still_serves_a_payload_that_is_still_fresh():
    """Hitting the cap mid-window shouldn't throw away a price that is still
    seconds old and perfectly bettable."""
    feed = _feed_with_payload(age_sec=5)
    feed.credits_used = config.LIVE_ODDS_SESSION_CREDIT_CAP
    assert feed.fetch(min_interval=0) == [{"home_team": "TCU"}]


def test_a_sustained_feed_outage_degrades_to_no_odds(monkeypatch):
    """Repeated fetch failures must age out too, not pin a stale line."""
    feed = _feed_with_payload(age_sec=config.LIVE_ODDS_MAX_AGE_SEC + 1)
    monkeypatch.setattr(config, "ODDS_API_KEY", "k", raising=False)
    import ncaaf_live.feeds.odds_live as ol
    monkeypatch.setattr(ol, "ODDS_API_KEY", "k")

    def boom(*_a, **_k):
        raise RuntimeError("odds api down")
    monkeypatch.setattr(ol.requests, "get", boom)
    assert feed.fetch(min_interval=0) is None


# ── 4. per-game state fan-out ───────────────────────────────────────────────
@pytest.fixture()
def gameday_mod():
    import ncaaf_live.gameday as gd
    return gd


def _ev(home, away, event_id="1"):
    return {"event_id": event_id, "home_location": home, "away_location": away}


class _Ctx:
    def __init__(self, gid):
        self.game_id = gid


def test_unknown_matchups_never_cost_a_fetch(gameday_mod, monkeypatch):
    """A game the platform has no row for can't be priced, so fetching its
    summary is pure waste - and at a fast cadence, waste we repeat all day."""
    calls = []
    monkeypatch.setattr(gameday_mod, "fetch_summary",
                        lambda eid: calls.append(eid) or {})
    out = gameday_mod.resolve_live_states(
        [_ev("Nowhere State", "Elsewhere")], {}, False, {})
    assert out == []
    assert calls == []


def test_espn_states_are_fetched_in_parallel_and_stay_aligned(
        gameday_mod, monkeypatch):
    """Order matters: a state paired with the wrong game would price one
    game's clock against another's line."""
    fold = gameday_mod._fold
    ctx_map = {(fold(h), fold(a)): _Ctx(f"NCAAF_{h}")
               for h, a in [("TCU", "North Carolina"), ("Ohio State", "Texas")]}
    live = [_ev("TCU", "North Carolina", "e1"), _ev("Ohio State", "Texas", "e2")]

    monkeypatch.setattr(gameday_mod, "fetch_summary",
                        lambda eid: {"id": eid})
    monkeypatch.setattr(gameday_mod, "extract_summary_state",
                        lambda sm: {"from": sm["id"]})

    out = gameday_mod.resolve_live_states(live, ctx_map, False, {}, workers=4)
    assert [(c.game_id, st["from"]) for _e, _k, c, st in out] == [
        ("NCAAF_TCU", "e1"), ("NCAAF_Ohio State", "e2")]


def test_cfbd_mode_does_no_per_game_fetching(gameday_mod, monkeypatch):
    """CFBD carries every game's state in one scoreboard call - that is why it
    scales to a fast cadence regardless of how many games are live."""
    fold = gameday_mod._fold
    key = (fold("TCU"), fold("North Carolina"))
    monkeypatch.setattr(gameday_mod, "fetch_summary",
                        lambda eid: pytest.fail("CFBD mode must not fetch"))
    out = gameday_mod.resolve_live_states(
        [_ev("TCU", "North Carolina")], {key: _Ctx("NCAAF_TCU")},
        True, {key: {"period": 2}})
    assert [st for _e, _k, _c, st in out] == [{"period": 2}]


def test_a_single_failed_summary_does_not_drop_the_other_games(
        gameday_mod, monkeypatch):
    fold = gameday_mod._fold
    ctx_map = {(fold(h), fold(a)): _Ctx(h)
               for h, a in [("TCU", "North Carolina"), ("Ohio State", "Texas")]}
    live = [_ev("TCU", "North Carolina", "e1"), _ev("Ohio State", "Texas", "e2")]
    monkeypatch.setattr(gameday_mod, "fetch_summary",
                        lambda eid: None if eid == "e1" else {"id": eid})
    monkeypatch.setattr(gameday_mod, "extract_summary_state",
                        lambda sm: {"from": sm["id"]})
    out = gameday_mod.resolve_live_states(live, ctx_map, False, {})
    assert [st for _e, _k, _c, st in out] == [None, {"from": "e2"}]


# ── 5. a rate-limited feed is not an empty slate ────────────────────────────
def test_an_unanswered_state_feed_does_not_look_like_the_slate_ending():
    """The loop exits ~30 min after the last live game. A failed fetch returns
    an empty list exactly like a genuinely empty slate, so a rate-limited feed
    would have looked like 'the slate is over' - the loop exits, the
    supervisor restarts it, and it rate-limits again. Polling faster makes a
    429 likelier, so the two cases must be distinguishable."""
    src = _main_source()
    assert "feed_answered" in src
    assert "elif not feed_answered:" in src, (
        "the idle-exit clock must not advance when the feed never answered")
