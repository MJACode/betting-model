"""
Guards on the one lane that survived validation.

The measured edge is the BOOK's centring, not the model's accuracy, so the
lane must price the bias and must refuse the states where the bias has no room
to express itself. It must also never price a game off a defaulted pregame
number, which is the shortcut that produced three wrong answers in the session
that built this.
"""
from __future__ import annotations

import pytest

from live_model.models import pass_attempt_bias as pab
from live_model.workers.gameday import GamedayWorker, GameTracker


def test_prices_the_haircut_not_the_measured_bias():
    """Deploying the full measured bias leaves no room for it to tighten."""
    r = pab.over_prob(32.5, 17.0, 1800)
    full = pab.over_prob(32.5, 17.0, 1800, bias=pab.MEASURED_BIAS)
    assert pab.DEPLOY_BIAS < pab.MEASURED_BIAS
    assert r.over_prob < full.over_prob
    # Still a real edge over a -115 breakeven of about 0.535.
    assert 0.57 < r.over_prob < 0.63


def test_refuses_the_end_of_the_game():
    assert pab.over_prob(32.5, 30.0, 60).over_prob is None
    assert pab.over_prob(32.5, 30.0, 239).over_prob is None
    assert pab.over_prob(32.5, 30.0, 241).over_prob is not None


def test_refuses_a_line_already_beaten():
    """A number below what the player has thrown is a pulled market."""
    assert pab.over_prob(30.0, 31.0, 1800).over_prob is None
    assert pab.over_prob(30.0, 30.0, 1800).over_prob is None


def test_missing_accrued_does_not_block_the_read():
    """ESPN state carries no per player accrual; the guard degrades, not fails."""
    assert pab.over_prob(32.5, None, 1800).over_prob is not None


def test_blind_arm_is_the_measured_over_rate():
    assert pab.blind_over_prob() == pytest.approx(0.642, abs=1e-3)


class _Q:
    def __init__(self, market, side, line, game_id="g1"):
        self.game_id, self.market, self.side = game_id, market, side
        self.line, self.price, self.player = line, -115.0, "Some QB"
        self.bookmaker, self.ts = "draftkings", None

    def age_seconds(self, now=None) -> float:
        # Fresh by construction: staleness is the executor's own concern and
        # has its own tests; this fixture is about the core feed path.
        return 0.0


def test_state_is_never_built_from_a_defaulted_anchor():
    """
    No anchor means no prop decision, not a decision priced off a default.

    from_espn's own docstring forbids defaults, and a lane that quietly
    invents a pregame total prices every game off it.
    """
    w = GamedayWorker(dry_run=True)
    tr = GameTracker("e1", "SEA", "NE")
    tr.payload = {"anything": True}
    assert w._state_from(tr, "e1") is None          # no anchor quotes at all

    w._anchor_quotes = [_Q("spreads", "home", -3.5)]
    assert w._state_from(tr, "e1") is None          # spread but no total


def test_no_payload_means_no_state():
    w = GamedayWorker(dry_run=True)
    assert w._state_from(GameTracker("e1", "SEA", "NE"), "e1") is None


def test_pricing_skips_when_there_is_no_state():
    """A tick without a usable state records nothing rather than guessing."""
    w = GamedayWorker(dry_run=True)
    tr = GameTracker("e1", "SEA", "NE")
    summary = {}
    w._price_props([_Q(pab.MARKET, "over", 32.5)], tr, summary)
    assert summary == {}
    assert w.executor.decisions == []


def test_pricing_ignores_other_markets_and_the_under():
    w = GamedayWorker(dry_run=True)
    tr = GameTracker("e1", "SEA", "NE")
    tr.state = object()
    summary = {}
    w._price_props([_Q("player_rush_yds", "over", 40.5),
                    _Q(pab.MARKET, "under", 32.5)], tr, summary)
    assert w.executor.decisions == []


# ------------------------------------------------- the core path end to end
CORE_EVENT = {
    # HALFTIME on purpose: it is the canonical hunt state, so the fixture
    # actually reaches the prop poll rather than proving only that a state got
    # built. is_hunt_state returns False mid drive and _poll_for never fires.
    "event_id": "e1", "period": 2, "clock_seconds": 0,
    "home_score": 14, "away_score": 10, "possession": "home",
    "down": 2, "distance": 7, "yardline_100": 55,
    "home_timeouts": 3, "away_timeouts": 3,
    "plays_run": 40, "home_plays": 22, "away_plays": 18,
    "home_pass_plays": 13, "away_pass_plays": 9,
    "state": "in", "state_name": "halftime",
    "home_abbrev": "SEA", "away_abbrev": "NE", "home": "SEA", "away": "NE",
    "season_type": "preseason",
}


class _FakeOdds:
    """Anchor carries both required numbers; the prop card carries one over."""

    def __init__(self):
        self.event_calls = []

    def fetch_anchor(self):
        return [_Q("spreads", "home", -3.5, game_id="e1"),
                _Q("totals", "over", 44.5, game_id="e1")]

    def fetch_event_markets(self, eid, markets):
        self.event_calls.append(tuple(markets))
        if pab.MARKET in markets:
            return [_Q(pab.MARKET, "over", 32.5)]
        return []


def _core_worker(monkeypatch, odds=None, event=None):
    from live_model.feeds import espn
    ev = dict(event or CORE_EVENT)
    monkeypatch.setattr(espn, "live_events",
                        lambda *a, **k: ([dict(ev)], "sports.core"))
    w = GamedayWorker(odds_client=odds or _FakeOdds())
    w.dry_run = False
    return w


def test_core_path_reaches_a_priced_decision(monkeypatch):
    """
    The regression that made the whole lane dead in production.

    The core listing already carries the full state, so the core branch has no
    second document to fetch and used to `continue` without ever assigning
    tr.state. _price_props returns immediately on a None state, so the worker
    would poll props, spend the credits, and discard every quote. core is the
    only ESPN host that answers the Railway worker, so that was the entire
    lane. The suite passed throughout.
    """
    w = _core_worker(monkeypatch)
    w.tick()
    tr = w.trackers["e1"]
    assert tr.state is not None, "core path built no GameState"
    assert w.executor.decisions, "a prop quote reached no decision"


def test_core_decisions_carry_the_season_type(monkeypatch):
    """A preseason rep must not be readable later as a track record."""
    w = _core_worker(monkeypatch)
    w.tick()
    assert {d.context.get("season_type") for d in w.executor.decisions} == {
        "preseason"}


def test_core_path_still_refuses_a_missing_anchor(monkeypatch):
    """No anchor is still no decision, on core as on site."""
    class _NoAnchor(_FakeOdds):
        def fetch_anchor(self):
            return []

    w = _core_worker(monkeypatch, odds=_NoAnchor())
    w.tick()
    assert w.trackers["e1"].state is None
    assert w.executor.decisions == []


# ------------------------------------------- continuous coverage, not halftime
FIRST_QUARTER = {**CORE_EVENT, "period": 1, "clock_seconds": 780,
                 "home_score": 0, "away_score": 0, "state_name": "1st quarter"}


def test_props_poll_from_the_first_snap_not_only_at_halftime(monkeypatch):
    """
    The gate used to be a hunt state, which meant halftime or a ten point
    lead in the second half. That deployed something other than what was
    validated: the surviving lane is the book's centring of the pass attempt
    line, measured across quotes taken all through games, so sampling only at
    halftime tests a different population than the one that cleared the kill
    criterion.
    """
    odds = _FakeOdds()
    w = _core_worker(monkeypatch, odds=odds, event=FIRST_QUARTER)
    summary = w.tick()

    assert summary["hunting"] == 0, "fixture must NOT be in a hunt state"
    assert summary["prop_polls"] == 1, "first quarter bought no prop card"
    assert w.executor.decisions, "a first quarter quote reached no decision"


def test_only_the_deployed_market_is_bought(monkeypatch):
    """
    Nine markets are listed; one lane is deployed and _price_props bins the
    rest. The Odds API charges per market per event call, so asking for all
    nine paid nine times over for eight markets nothing scores.
    """
    odds = _FakeOdds()
    w = _core_worker(monkeypatch, odds=odds, event=FIRST_QUARTER)
    w.tick()
    assert odds.event_calls == [(pab.MARKET,)]


def test_the_underived_lane_stays_hunt_gated(monkeypatch):
    """
    Derivative markets are not a deployed lane, and their premise IS a hunt
    state: a quote that has failed to keep up with a repriced main line.
    """
    odds = _FakeOdds()
    w = _core_worker(monkeypatch, odds=odds, event=FIRST_QUARTER)
    summary = w.tick()
    assert summary["deriv_polls"] == 0
