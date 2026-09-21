"""
Guards on the pass-attempt lane, after the 2026-09-21 re-measurement.

THE LANE NO LONGER PRICES. The bias it existed to harvest was re-derived on the
same archive and is -0.12 attempts, 95% CI (-0.42, +0.18) clustered on game --
not the -2.33 it shipped on. Graded at real posted prices the old rule returned
-8.47% over 3,794 bets and got WORSE as the threshold tightened, because a
constant probability plus a price filter selects the cheapest overs and the
book's price is calibrated (slope +1.22). See the module docstring and
docs/nfl_live_prop_assessment.md.

So these guards now pin two things: the sanity gates still classify unusable
quotes correctly, and A DEPLOYED BIAS MUST LIE INSIDE ITS OWN MEASURED
INTERVAL. That last one is the guard that would have caught this -- both 1.50
and 2.33 sit outside (-0.42, +0.18).
"""
from __future__ import annotations

import pytest

from live_model.models import pass_attempt_bias as pab
from live_model.workers.gameday import GamedayWorker, GameTracker


def test_a_deployed_bias_must_sit_inside_its_measured_interval():
    """THE GUARD THAT WOULD HAVE CAUGHT THIS.

    The lane shipped DEPLOY_BIAS = 1.50 as a "haircut" below a MEASURED_BIAS of
    2.33. Re-measured, the interval is (-0.42, +0.18) and BOTH numbers sit
    outside it. A bias the data does not support is not a conservative bet, it
    is a fabricated one, and it is what produced an all-overs card.
    """
    lo, hi = pab.MEASURED_BIAS_CI
    assert lo <= pab.MEASURED_BIAS <= hi, "point estimate outside its own CI"
    assert lo <= pab.DEPLOY_BIAS <= hi, (
        f"DEPLOY_BIAS={pab.DEPLOY_BIAS} is outside the measured interval "
        f"({lo}, {hi}) -- it is not backed by the measurement")
    for dead in (1.50, 2.33):
        assert not (lo <= dead <= hi), (
            f"{dead} was the shipped claim and must not be re-derivable")


def test_the_interval_spans_zero_so_the_lane_declines_to_price():
    """With no measured bias there is no edge, and asserting 0.50 into a priced
    market just donates the hold. None means 'no opinion', and the caller
    already writes no pick on it."""
    lo, hi = pab.MEASURED_BIAS_CI
    assert lo < 0 < hi
    assert pab.DEPLOY_BIAS == 0.0
    r = pab.over_prob(32.5, 17.0, 1800)
    assert r.over_prob is None
    assert r.reason == "no_measured_bias"


def test_the_sanity_gates_still_classify_unusable_quotes():
    """Each refusal keeps its OWN reason, so 'no opinion' stays distinguishable
    from 'this quote was unusable'."""
    assert pab.over_prob(32.5, 30.0, 60).reason.startswith("too_late")
    assert pab.over_prob(32.5, 30.0, 239).reason.startswith("too_late")
    assert pab.over_prob(0.0, 30.0, 1800).reason == "no_line"
    assert pab.over_prob(30.0, 31.0, 1800).reason == "line_at_or_below_accrued"
    assert pab.over_prob(30.0, 30.0, 1800).reason == "line_at_or_below_accrued"
    assert pab.over_prob(32.5, 17.0, 1800, sigma=0).reason == "degenerate_sigma"


def test_the_gates_are_checked_before_the_no_bias_decline():
    """A quote that is unusable AND unpriced reports why it was unusable."""
    assert pab.over_prob(32.5, 30.0, 60).reason != "no_measured_bias"


def test_the_constants_are_read_at_call_time_not_import_time():
    """The old signature bound `bias=DEPLOY_BIAS` as a DEFAULT VALUE, so
    rebinding the constant changed nothing and the function kept using the
    number captured at import. A hotfix or a replay that set it would have
    silently done nothing."""
    import live_model.models.pass_attempt_bias as m
    before = m.DEPLOY_BIAS
    try:
        m.DEPLOY_BIAS = 1.50
        assert m.over_prob(32.5, 17.0, 1800).over_prob is not None
    finally:
        m.DEPLOY_BIAS = before
    assert m.over_prob(32.5, 17.0, 1800).over_prob is None


def test_restoring_a_bias_is_one_constant():
    """The decline is reversible, and this documents how -- mike's call, not
    the model's. Passing a bias explicitly prices as it always did."""
    r = pab.over_prob(32.5, 17.0, 1800, bias=1.50)
    assert r.over_prob == pytest.approx(0.6017, abs=1e-3)
    assert r.reason == "measured_bias"


def test_the_old_rule_was_a_constant_not_a_model():
    """Why the card was identical in every game: the output never depended on
    the line, the accrued total or the clock. Pinned so nobody rebuilds it."""
    probs = {pab.over_prob(line, acc, secs, bias=1.50).over_prob
             for line, acc, secs in ((25.5, 5.0, 2700), (32.5, 17.0, 1800),
                                     (44.5, 30.0, 600), (19.5, 1.0, 3500))}
    assert len(probs) == 1, "the shipped construction had no discrimination"


def test_blind_arm_no_longer_asserts_a_rate():
    """Betting every over was the honest comparison arm and it has an answer:
    -8.23% on 4,071 real quotes, 90% CI (-12.1, -4.4). 2025 went over 45.7% of
    the time, not the 64.2% this used to return."""
    assert pab.blind_over_prob() is None


class _Q:
    # The book's OWN event id and the book's FULL team names, deliberately
    # unlike ESPN's id and abbreviations. An earlier version of this fake gave
    # the anchor the ESPN event id, which is a matchup that cannot occur in
    # production and is precisely what hid the bug where no game ever resolved
    # to a spread or a total.
    def __init__(self, market, side, line, game_id="bk_7f3a91c",
                 home_team="Seattle Seahawks", away_team="New England Patriots"):
        self.game_id, self.market, self.side = game_id, market, side
        self.line, self.price, self.player = line, -115.0, "Some QB"
        self.bookmaker, self.ts = "draftkings", None
        self.home_team, self.away_team = home_team, away_team

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

    w.trackers["e1"] = tr
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
        return [_Q("spreads", "home", -3.5), _Q("totals", "over", 44.5)]

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
    _with_a_restored_bias(monkeypatch)
    w = _core_worker(monkeypatch)
    w.tick()
    tr = w.trackers["e1"]
    assert tr.state is not None, "core path built no GameState"
    assert w.executor.decisions, "a prop quote reached no decision"


def test_core_decisions_carry_the_season_type(monkeypatch):
    """A preseason rep must not be readable later as a track record."""
    _with_a_restored_bias(monkeypatch)
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


def _with_a_restored_bias(monkeypatch, bias: float = 1.50):
    """Exercise the PLUMBING with a bias injected.

    The lane declines to price at the measured bias of zero, so these
    integration tests would otherwise assert on an empty card and quietly stop
    testing the wiring they exist to test. Injecting a bias keeps them honest
    about the path without re-asserting the disproven edge.
    """
    monkeypatch.setattr(pab, "DEPLOY_BIAS", bias)
    monkeypatch.setattr(pab, "blind_over_prob", lambda: 0.642)


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
    _with_a_restored_bias(monkeypatch)
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


# ------------------------------------------------ book id vs scoreboard id
def test_anchor_matches_on_the_matchup_not_the_event_id():
    """
    The book and ESPN each mint their own event ids and the two are unrelated
    strings, so an id comparison can never match. In production that meant
    every game came back with no spread and no total, _state_from correctly
    refused to build a state rather than default one, and not one prop could
    be priced. The matchup is the only key the two feeds share.
    """
    w = GamedayWorker(dry_run=True)
    tr = GameTracker("401772938", "SEA", "NE")      # ESPN id and abbreviations
    w.trackers["401772938"] = tr
    w._anchor_quotes = [                            # book id and full names
        _Q("spreads", "home", -3.5, game_id="bk_7f3a91c"),
        _Q("totals", "over", 44.5, game_id="bk_7f3a91c"),
    ]
    assert w._anchor_value("401772938", "spreads") == -3.5
    assert w._anchor_value("401772938", "totals") == 44.5


def test_anchor_does_not_match_a_different_game():
    """A slate-wide anchor carries every game; the wrong one must not match."""
    w = GamedayWorker(dry_run=True)
    tr = GameTracker("401772938", "SEA", "NE")
    w.trackers["401772938"] = tr
    w._anchor_quotes = [
        _Q("spreads", "home", -7.0, home_team="Dallas Cowboys",
           away_team="Philadelphia Eagles"),
    ]
    assert w._anchor_value("401772938", "spreads") is None


def test_espn_abbreviations_that_differ_from_ours_still_match():
    """WSH and LAR are ESPN's spellings of WAS and LA. Two teams, silent miss."""
    from live_model.workers.gameday import _abbrev
    assert _abbrev("WSH") == _abbrev("Washington Commanders") == "WAS"
    assert _abbrev("LAR") == _abbrev("Los Angeles Rams") == "LA"

    w = GamedayWorker(dry_run=True)
    w.trackers["e9"] = GameTracker("e9", "WSH", "LAR")
    w._anchor_quotes = [_Q("totals", "over", 41.5,
                           home_team="Washington Commanders",
                           away_team="Los Angeles Rams")]
    assert w._anchor_value("e9", "totals") == 41.5


# ------------------------------------------------- why nothing could be priced
def test_empty_anchor_is_reported_as_the_book_having_no_market(monkeypatch, caplog):
    """states=0 has two opposite causes and the tick line cannot tell them apart."""
    class _NoAnchor(_FakeOdds):
        def fetch_anchor(self):
            return []

    w = _core_worker(monkeypatch, odds=_NoAnchor(), event=FIRST_QUARTER)
    with caplog.at_level("WARNING"):
        w.tick()
    assert "anchor came back EMPTY" in caplog.text


def test_unmatched_anchor_names_both_sides(monkeypatch, caplog):
    class _OtherGame(_FakeOdds):
        def fetch_anchor(self):
            return [_Q("spreads", "home", -7.0, home_team="Dallas Cowboys",
                       away_team="Philadelphia Eagles"),
                    _Q("totals", "over", 41.5, home_team="Dallas Cowboys",
                       away_team="Philadelphia Eagles")]

    w = _core_worker(monkeypatch, odds=_OtherGame(), event=FIRST_QUARTER)
    with caplog.at_level("WARNING"):
        w.tick()
    assert "none match" in caplog.text
    assert "NE@SEA" in caplog.text and "PHI@DAL" in caplog.text


def test_the_explanation_is_printed_once_not_every_tick(monkeypatch, caplog):
    class _NoAnchor(_FakeOdds):
        def fetch_anchor(self):
            return []

    w = _core_worker(monkeypatch, odds=_NoAnchor(), event=FIRST_QUARTER)
    with caplog.at_level("WARNING"):
        w.tick()
        w.tick()
    assert caplog.text.count("anchor came back EMPTY") == 1


# -------------------------------------- do not pay for an unmatchable board
def test_anchor_backs_off_when_the_book_does_not_carry_the_slate(monkeypatch):
    """
    Preseason, measured: the board is the full regular season and none of the
    five games being played are on it. Refetching that every minute at 3
    credits burns roughly 540 credits a night to re-read the same unusable
    schedule.
    """
    from live_model.workers import gameday as gd

    class _WrongSlate(_FakeOdds):
        def fetch_anchor(self):
            return [_Q("spreads", "home", -7.0, home_team="Dallas Cowboys",
                       away_team="Arizona Cardinals"),
                    _Q("totals", "over", 41.5, home_team="Dallas Cowboys",
                       away_team="Arizona Cardinals")]

    odds = _WrongSlate()
    w = _core_worker(monkeypatch, odds=odds, event=FIRST_QUARTER)

    now = 10_000.0
    polls = 0
    for i in range(12):                       # twelve minutes of slate
        s = w.tick(now + i * gd.POLL_ANCHOR_SEC)
        polls += s["anchor_polls"]
    # Three at the fast cadence, then it stops paying every minute.
    assert polls <= gd.ANCHOR_MISS_LIMIT + 1, f"kept paying: {polls} polls"


def test_a_matching_board_keeps_the_fast_cadence(monkeypatch):
    """The backoff must never slow down a night the book actually carries."""
    from live_model.workers import gameday as gd

    odds = _FakeOdds()                        # SEA/NE, which the fixture plays
    w = _core_worker(monkeypatch, odds=odds, event=FIRST_QUARTER)

    now = 10_000.0
    polls = 0
    for i in range(6):
        s = w.tick(now + i * gd.POLL_ANCHOR_SEC)
        polls += s["anchor_polls"]
    assert polls == 6, f"backed off on a live board: {polls} polls"


def test_one_miss_does_not_trigger_the_backoff(monkeypatch):
    """A single miss can be one line briefly pulled, not an absent slate."""
    from live_model.workers import gameday as gd
    w = _core_worker(monkeypatch, odds=_FakeOdds(), event=FIRST_QUARTER)
    w._anchor_misses = 1
    assert w._anchor_misses < gd.ANCHOR_MISS_LIMIT


# ── The prop poll asks the BOOK for the BOOK's event id (2026-09-09) ─────────
# First live regular-season game, NE @ SEA: anchor matched, state built, and
# every prop poll answered 422 INVALID_EVENT_ID, because the worker passed
# ESPN's event id to The Odds API's per-event endpoint. dec=0 for the whole
# game. The fakes above never caught it because they ignore the id argument.

class _IdRecordingOdds(_FakeOdds):
    def fetch_event_markets(self, eid, markets):
        self.event_ids = getattr(self, "event_ids", []) + [eid]
        return super().fetch_event_markets(eid, markets)


def test_the_prop_poll_uses_the_books_event_id_not_espns(monkeypatch):
    odds = _IdRecordingOdds()
    w = _core_worker(monkeypatch, odds=odds, event=FIRST_QUARTER)
    summary = w.tick()
    assert summary["prop_polls"] == 1
    assert odds.event_ids == ["bk_7f3a91c"], \
        f"the per-event call must carry the book's id, got {odds.event_ids}"
    assert "e1" not in odds.event_ids, "ESPN's id is not a book event id"


def test_no_anchor_row_for_the_matchup_means_no_prop_poll(monkeypatch):
    """A call that cannot succeed is a credit spent on nothing; skip it and
    say so on the tick line rather than paying for a 422 every minute."""
    class _OtherGame(_IdRecordingOdds):
        def fetch_anchor(self):
            return [_Q("spreads", "home", -3.5, game_id="bk_other",
                       home_team="Dallas Cowboys", away_team="New York Giants"),
                    _Q("totals", "over", 44.5, game_id="bk_other",
                       home_team="Dallas Cowboys", away_team="New York Giants")]

    odds = _OtherGame()
    w = _core_worker(monkeypatch, odds=odds, event=FIRST_QUARTER)
    summary = w.tick()
    assert getattr(odds, "event_ids", []) == [], "must not call the book with a guessed id"
    assert summary["prop_polls"] == 0
    assert "no_book_event_id" in summary.get("prop_skips", [])


def test_the_hunt_gated_derivative_poll_uses_the_books_id_too(monkeypatch):
    odds = _IdRecordingOdds()
    w = _core_worker(monkeypatch, odds=odds)          # CORE_EVENT is halftime
    summary = w.tick()
    assert summary["hunting"] == 1
    assert set(odds.event_ids) == {"bk_7f3a91c"}


def test_at_the_measured_bias_the_wiring_reaches_no_decision(monkeypatch):
    """The end-to-end consequence of the re-measurement: the card is empty and
    every quote is recorded as skipped with a reason, rather than silently
    vanishing."""
    w = _core_worker(monkeypatch)
    summary = w.tick()
    assert w.executor.decisions == []
    assert summary.get("prop_skips"), "skips must be recorded, not swallowed"
    assert set(summary["prop_skips"]) == {"no_measured_bias"}
