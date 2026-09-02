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
def test_state_cadence_is_fast_enough_to_react_to_a_drive():
    """Upper bound only. The lower bound is a BILL, not a correctness property
    -- CFBD charges per call -- so it is documented at the constant rather than
    asserted here, where a future tier change would read as a test failure."""
    assert 1 <= config.POLL_STATE_SEC <= 15


def test_odds_cadence_is_independent_of_state_cadence():
    """State is free, odds are billed. Collapsing them into one number is the
    bug this fixes: they must be SEPARATELY settable.

    This used to assert odds >= state, which read as "billed must never be
    faster than free". That is not the real relationship. The odds fetch lives
    inside the state loop, so the PASS is the hard bound: any odds value at or
    below POLL_STATE_SEC simply means "fetch every pass", and nothing below it
    buys anything. Setting odds to 5 against a 10s state poll is therefore
    every-pass, not a 5s cadence -- so the invariant is that they are distinct
    knobs, not that one is larger."""
    assert config.POLL_ODDS_SEC > 0 and config.POLL_STATE_SEC > 0
    src = open(Path(__file__).parent.parent / "config.py").read()
    assert "NCAAF_LIVE_POLL_ODDS_SEC" in src and "NCAAF_LIVE_POLL_STATE_SEC" in src


def test_the_effective_odds_cadence_is_bounded_by_the_pass():
    """The number that matters is max(odds, state) -- documenting it here so a
    future 'drop odds to 2s' change is understood as a no-op without also
    dropping the state poll (which is what actually costs CFBD calls)."""
    effective = max(config.POLL_ODDS_SEC, config.POLL_STATE_SEC)
    assert effective == config.POLL_STATE_SEC, (
        "odds is now the slower knob; the pass no longer bounds it and the "
        "comment in config.py needs revisiting")


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
    tree = ast.parse(GAMEDAY.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "main")
    return ast.unparse(fn)


def test_loop_sleeps_the_remainder_not_a_flat_interval():
    """A flat sleep after the work makes the true cadence interval + work.
    At 45s that error was ~10%; at 10s it dominates."""
    src = _main_source()
    assert "time.monotonic()" in src, "no pass start timestamp"
    assert "max(0.0, target - elapsed)" in src, (
        "the loop must sleep only the remaining time in the interval")


def test_loop_warns_when_a_pass_overruns_its_interval():
    """When the feeds are slower than the target, that must be visible rather
    than silent drift."""
    assert "elapsed > target" in _main_source()


def test_odds_fetch_uses_the_odds_cadence_not_the_loop_cadence():
    """State is free and odds are billed, so the odds fetch must be paced by
    --odds-interval, never by the (much faster) state cadence.

    #272 put a score-change trigger in front of it: the ceiling is still
    a.odds_interval, but a scoring play collapses that pass to the trigger
    floor. So the assertion is on the ceiling and the floor, not on the
    literal call site it used to read."""
    src = _main_source()
    assert "min_interval=interval" in src, "odds fetch is not paced at all"
    assert "a.odds_interval" in src, "the odds cadence is not the ceiling"
    assert "min(POLL_ODDS_TRIGGER_SEC, a.odds_interval)" in src, (
        "a score change must lower the odds cadence, never raise it")
    assert "min_interval=a.interval" not in src, (
        "the odds fetch must not be paced by the free state cadence")


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


# ── 6. the idle path is what the CFBD quota actually pays for ───────────────
def test_idle_cadence_is_slower_than_the_live_cadence():
    """CFBD bills per call (free tier is 1,000/MONTH). The loop does not stop
    polling between games, so without a backoff the fast cadence is charged
    all day whether or not anything is live."""
    assert config.POLL_IDLE_SEC > config.POLL_STATE_SEC


def test_loop_polls_at_the_idle_cadence_when_nothing_is_live():
    src = _main_source()
    assert "a.interval if live else a.idle_interval" in src


def test_loop_exits_early_when_no_kickoff_is_near(gameday_mod):
    """A loop launched hours before the first kickoff used to sit polling a
    paid API for 30 minutes to learn what its own context map already knew."""
    assert "seconds_to_next_kickoff" in _main_source()

    now = __import__("datetime").datetime(2026, 9, 5, 15, 0,
                                          tzinfo=__import__("datetime").timezone.utc)
    class C:
        def __init__(self, ct): self.commence_time = ct
    # earliest of several kickoffs, all ahead of us
    m = {"a": C("2026-09-05T19:00:00Z"), "b": C("2026-09-05T17:30:00Z")}
    assert gameday_mod.seconds_to_next_kickoff(m, now) == 2.5 * 3600


def test_kickoffs_already_past_are_not_counted_as_upcoming(gameday_mod):
    import datetime as dt
    now = dt.datetime(2026, 9, 5, 20, 0, tzinfo=dt.timezone.utc)
    class C:
        def __init__(self, ct): self.commence_time = ct
    assert gameday_mod.seconds_to_next_kickoff(
        {"a": C("2026-09-05T17:00:00Z")}, now) is None


def test_unparseable_kickoffs_never_cause_an_early_exit(gameday_mod):
    """Unknown must mean 'stay up'. Being wrong about a kickoff cannot be
    allowed to cost us a game."""
    import datetime as dt
    now = dt.datetime(2026, 9, 5, 15, 0, tzinfo=dt.timezone.utc)
    class C:
        def __init__(self, ct): self.commence_time = ct
    assert gameday_mod.seconds_to_next_kickoff({"a": C("not a date")}, now) is None
    assert gameday_mod.seconds_to_next_kickoff({"a": C(None)}, now) is None
    assert gameday_mod.seconds_to_next_kickoff({}, now) is None


def test_naive_kickoff_timestamps_are_treated_as_utc(gameday_mod):
    import datetime as dt
    now = dt.datetime(2026, 9, 5, 15, 0, tzinfo=dt.timezone.utc)
    class C:
        def __init__(self, ct): self.commence_time = ct
    assert gameday_mod.seconds_to_next_kickoff(
        {"a": C("2026-09-05T16:00:00")}, now) == 3600


# ── 7. the cadence must fit the plan we are actually on ────────────────────
def _modelled_monthly_cfbd_calls(state_sec: float) -> float:
    """One /scoreboard call per pass. A realistic in-season month: 5 Saturdays
    of ~12h continuous football, ~5 weeknight days of ~4h, plus idle ticks."""
    per_hour = 3600 / state_sec
    live_hours = 5 * 12 + 5 * 4
    idle_ticks = 6 * 13 * 20          # supervisor tick on non-game days
    return live_hours * per_hour + idle_ticks


def test_configured_cadence_fits_the_cfbd_plan():
    """The bug this pins: 5s was chosen against a comment claiming a 75k plan
    the account was not on, which is ~60k/month against a 30k cap -- and the
    failure mode is CFBD cutting the key off mid-season, taking the live state
    feed and NCAAF live betting down with it. Raise CFBD_MONTHLY_CALL_ALLOWANCE
    when the plan actually changes; do not loosen this test."""
    modelled = _modelled_monthly_cfbd_calls(config.POLL_STATE_SEC)
    assert modelled <= config.CFBD_MONTHLY_CALL_ALLOWANCE, (
        f"POLL_STATE_SEC={config.POLL_STATE_SEC}s models to "
        f"{modelled:,.0f} CFBD calls/month, over the configured allowance of "
        f"{config.CFBD_MONTHLY_CALL_ALLOWANCE:,}. Either slow the poll or "
        f"raise the plan (and CFBD_MONTHLY_CALL_ALLOWANCE with it).")


def test_the_allowance_is_a_number_not_a_comment():
    assert isinstance(config.CFBD_MONTHLY_CALL_ALLOWANCE, int)
    assert config.CFBD_MONTHLY_CALL_ALLOWANCE >= 1000   # the free tier floor
