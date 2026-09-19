"""A prop pick is written on ONE pass per game, not on every hourly pass.

WHY THIS EXISTS (2026-09-19, mike: "there's way too many as per usual like a
million on this lions game and every single one is an under").

`scripts/nfl_prop_market_card` is run HOURLY by the scheduler, because the
board it fetches is the same board the twelve distributional models score off
in the same tick. `publish()` is insert-once per proposition, so nothing was
ever re-priced and no lock was broken -- but anything that had newly crossed
the cut since the previous pass was ADDED. A game alone in its 24h window
therefore collected a bet or two an hour, all day.

Measured on production picks the week this was found:

    NFL_2026_01_DEN_KC   14 bets, accumulated over 11 separate hourly passes
    NFL_2026_02_DET_BUF  12 bets, all unders, over 6 passes on one game day
    NFL_2026_01_GB_MIN    2 bets, one pass (crowded Sunday window)

    week of 2026-09-07:  16 bets / 12 games  (1.3 per game)  56% under
    week of 2026-09-14:  26 bets /  2 games (13.0 per game)  96% under

The bet count was tracking HOW MANY TIMES WE LOOKED, not how much the books
disagreed. The graded record is 1,248 bets over three seasons at 72% under
(898 of them) -- production ran 96% under, because the under floor is 5pp and
the over floor 6pp (config.NFL_PROP_MARKET_SIDE_EDGE) and repeated looks cross
the lower bar far more often. The over-lean is real and measured; 96% is not
it.

THE FIX IS A PUBLISH HOUR, NOT A LEAD. The record is one board read per game,
and every one of the 1,900,449 `open` rows in the local cache is stamped
13:55 UTC -- one wall-clock time, not one lead offset. Exactly one 13:xx pass
falls inside a game's 24h ceiling, so this gives one publish per game and keeps
no state.

WHAT THIS DOES NOT TOUCH: the 5pp/6pp cuts, the soft books, the markets, the
24h ceiling, the started-game floor, or the §1c lock on anything already
written. It decides when the card may publish, so the bets it writes are the
bets the +13.3% describes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import config
import scripts.nfl_prop_market_card as card_mod


def _games(now: datetime, *leads_h):
    """One scheduled game per lead time, in hours from `now`."""
    out = {}
    for i, h in enumerate(leads_h):
        ko = now + timedelta(hours=h)
        out[f"NFL_2026_W3_G{i}"] = {
            "kickoff": ko.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date": ko.date().isoformat(),
        }
    return out


def _at(hour: int, minute: int = 25) -> datetime:
    """A scheduler pass. The cron fires at minute 25 of every hour."""
    return datetime(2026, 9, 17, hour, minute, tzinfo=timezone.utc)


# ── The core guarantee ───────────────────────────────────────────────────────

def test_only_the_publish_hour_may_write():
    """Every other hourly pass publishes nothing, however good the card is.

    THIS IS THE TEST THAT FAILS WITHOUT THE FIX. Before 2026-09-19 the card
    published on every pass, so all 24 of these hours returned the game.
    """
    published_at = []
    for hour in range(24):
        now = _at(hour)
        # A game 10h out at the 13:xx pass -- DET_BUF's actual geometry, a
        # Thursday night kickoff read on Thursday morning.
        ko = _at(13) + timedelta(hours=10)
        games = {"NFL_2026_02_DET_BUF": {
            "kickoff": ko.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date": ko.date().isoformat()}}
        if card_mod.publishable_games(games, now):
            published_at.append(hour)

    assert published_at == [config.NFL_PROP_PUBLISH_HOUR_UTC], (
        f"expected exactly one publishing pass per game day, got {published_at}")


def test_a_game_is_publishable_on_exactly_one_pass_in_its_window():
    """The 24h ceiling and a wall-clock hour intersect exactly once.

    Walk every hourly pass across three days for a Sunday 17:00 UTC kickoff and
    count the passes that may publish. More than one means bets can still
    accumulate; zero means the game would never be bet.
    """
    kickoff = datetime(2026, 9, 20, 17, 0, tzinfo=timezone.utc)
    games = {"NFL_2026_03_AAA_BBB": {
        "kickoff": kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": kickoff.date().isoformat()}}

    eligible = []
    start = kickoff - timedelta(hours=48)
    for i in range(72):
        now = start + timedelta(hours=i)
        lead = (kickoff - now).total_seconds() / 3600.0
        # The card only ever offers games inside the ceiling and not started;
        # mirror those two existing gates so this counts publish passes only.
        if not (0 < lead <= config.NFL_PROP_MAX_LEAD_HOURS):
            continue
        if card_mod.publishable_games(games, now):
            eligible.append(now)

    assert len(eligible) == 1, (
        f"a game must be publishable on exactly one pass, got {len(eligible)}: "
        f"{[d.isoformat() for d in eligible]}")


# ── The lead floor ───────────────────────────────────────────────────────────

def test_a_kickoff_inside_the_lead_floor_is_not_published():
    """A 13:30 UTC London kickoff is not bet from the 13:25 pass.

    The grader dropped those quotes as post-kickoff (13:55 UTC is after a 13:30
    kickoff), so no measured band describes a bet taken there.
    """
    now = _at(config.NFL_PROP_PUBLISH_HOUR_UTC, 25)
    inside = _games(now, config.NFL_PROP_PUBLISH_MIN_LEAD_HOURS - 0.5)
    assert card_mod.publishable_games(inside, now) == set()


def test_domestic_slots_clear_the_lead_floor():
    """Every normal kickoff slot is hours from the publish pass, so the floor
    only ever touches the early international window."""
    now = _at(config.NFL_PROP_PUBLISH_HOUR_UTC, 25)
    #                      Sun 1pm ET  Sun 4pm ET  Thu/Sun/Mon night
    games = _games(now, 3.6, 6.6, 10.8)
    assert len(card_mod.publishable_games(games, now)) == 3


# ── What must NOT have changed ───────────────────────────────────────────────

def test_the_cuts_are_untouched():
    """This was a cadence fix. A cut moving with it would be a second,
    unmeasured change riding along (§1b: a threshold is measured per model)."""
    assert config.NFL_PROP_MARKET_SIDE_EDGE == {"over": 0.06, "under": 0.05}
    assert card_mod.MIN_EDGE == 0.05
    assert config.NFL_PROP_MAX_LEAD_HOURS == 24


# ── The catch-up, and why it does not reopen the harvest ─────────────────────

class _Conn:
    """A connection that answers the one question publish_hour_missed asks."""

    def __init__(self, tick_rows):
        self.tick_rows = tick_rows
        self.args = None

    def execute(self, sql, params=None):
        self.args = params
        return self

    def fetchone(self):
        return self.tick_rows


class _Log:
    """api_call_log ticks, filtered to the window publish_hour_missed asks for."""

    def __init__(self, ticks):
        self.ticks = list(ticks)
        self.args = None

    def execute(self, sql, params=None):
        self.args = params
        return self

    def fetchone(self):
        start, end = self.args
        return (1,) if any(start <= ts < end for ts in self.ticks) else None


def test_a_missed_publish_pass_is_caught_up_by_the_next_one():
    """ONE PASS MEANS NO SECOND CHANCE, so a skipped tick is a whole slate.

    Measured over 2026-09-13..19: the worker ticked 24/24 hours on six of seven
    days and missed exactly ONE hour all week -- 13:00 UTC on 2026-09-18, the
    one hour this gate depends on. Without this, that day's entire slate is
    written off with no pick and no error.
    """
    now = _at(config.NFL_PROP_PUBLISH_HOUR_UTC + 1)
    games = _games(now, 6.0)
    # no api_call_log row in the publish hour => the pass never ran
    assert card_mod.publish_hour_missed(_Conn(None), now) is True
    assert card_mod.publishable_games(games, now, is_catch_up=True) == set(games)


def test_no_catch_up_when_the_publish_pass_did_run():
    """If the pass ran it already published, so no later pass may add to it.
    This is what keeps the exactly-once guarantee intact."""
    now = _at(config.NFL_PROP_PUBLISH_HOUR_UTC + 1)
    assert card_mod.publish_hour_missed(_Conn((1,)), now) is False
    assert card_mod.publishable_games(_games(now, 6.0), now,
                                      is_catch_up=False) == set()


def test_no_catch_up_before_the_publish_hour_has_arrived():
    """At 09:xx the 13:xx pass has not been missed — it has not happened yet.
    Treating 'not yet' as 'skipped' would publish every game hours early."""
    now = _at(config.NFL_PROP_PUBLISH_HOUR_UTC - 4)
    assert card_mod.publish_hour_missed(_Conn(None), now) is False


def test_no_catch_up_during_the_publish_hour_itself():
    """At 13:xx this IS the publish pass, not a catch-up — even if this hour's
    fetch logs have not flushed yet. Calling it a miss would log a false
    WARNING on the one hour that is supposed to publish."""
    now = _at(config.NFL_PROP_PUBLISH_HOUR_UTC)
    assert card_mod.publish_hour_missed(_Log([]), now) is False


def test_miss_at_13_catch_up_at_14_later_hours_stay_closed():
    """13:xx missed → 14:xx catches up once → 15:xx+ do not catch up again.

    THE FAILURE MODE THIS PINS. publish_hour_missed used to ask only whether
    [13:00, 14:00) had a tick. A 14:xx catch-up logs at 14:xx, so that window
    stayed empty and every later hour stayed catch_up=True — newly crossed
    props harvested all afternoon, the exact defect the publish hour exists
    to stop. The 14:xx tick is the durable one-shot marker.
    """
    ticks = []
    at_13 = _at(config.NFL_PROP_PUBLISH_HOUR_UTC)
    at_14 = _at(config.NFL_PROP_PUBLISH_HOUR_UTC + 1)
    at_15 = _at(config.NFL_PROP_PUBLISH_HOUR_UTC + 2)
    at_16 = _at(config.NFL_PROP_PUBLISH_HOUR_UTC + 3)
    at_22 = _at(22)

    assert card_mod.publish_hour_missed(_Log(ticks), at_13) is False
    assert card_mod.publishable_games(_games(at_13, 6.0), at_13)

    assert card_mod.publish_hour_missed(_Log(ticks), at_14) is True
    assert card_mod.publishable_games(_games(at_14, 6.0), at_14,
                                      is_catch_up=True) == set(_games(at_14, 6.0))

    ticks.append(at_14)
    for later in (at_15, at_16, at_22):
        assert card_mod.publish_hour_missed(_Log(ticks), later) is False, later
        assert card_mod.publishable_games(
            _games(later, 6.0), later, is_catch_up=False) == set()


def test_the_current_hour_tick_does_not_hide_a_miss():
    """--fetch writes api_call_log rows BEFORE publish_hour_missed runs.
    Those rows are this hour and must not count as 'the day's read already
    happened', or a 14:xx catch-up would see its own fetch and stay closed.
    """
    at_14 = _at(config.NFL_PROP_PUBLISH_HOUR_UTC + 1)
    assert card_mod.publish_hour_missed(_Log([at_14]), at_14) is True


def test_catch_up_window_runs_from_publish_hour_to_this_hour():
    """The marker is any tick after 13:00, not only one inside [13:00, 14:00)."""
    log = _Log([])
    now = _at(config.NFL_PROP_PUBLISH_HOUR_UTC + 2)
    assert card_mod.publish_hour_missed(log, now) is True
    start, end = log.args
    assert start == datetime(2026, 9, 17, config.NFL_PROP_PUBLISH_HOUR_UTC, 0,
                             tzinfo=timezone.utc)
    assert end == datetime(2026, 9, 17, config.NFL_PROP_PUBLISH_HOUR_UTC + 2, 0,
                           tzinfo=timezone.utc)


def test_the_catch_up_is_keyed_on_the_tick_not_on_having_no_picks():
    """A publish pass that legitimately found nothing looks identical to one
    that never ran. Keying the catch-up on 'this game has no pick yet' would
    let every later pass publish, which is the hourly harvest coming back in
    through the fallback."""
    import inspect
    src = inspect.getsource(card_mod.publish_hour_missed)
    assert "api_call_log" in src, "the catch-up must ask whether the TICK ran"
    assert "FROM picks" not in src, (
        "keying the catch-up on existing picks reopens hourly accumulation")


def test_the_catch_up_still_respects_the_lead_floor():
    """A catch-up is the day's first read, not a licence to bet a game that is
    about to kick off."""
    now = _at(config.NFL_PROP_PUBLISH_HOUR_UTC + 1)
    late = _games(now, config.NFL_PROP_PUBLISH_MIN_LEAD_HOURS - 0.5)
    assert card_mod.publishable_games(late, now, is_catch_up=True) == set()


def test_catch_up_is_off_by_default():
    """The normal path must be the exactly-once path: a caller that forgets the
    flag gets the strict rule, not the loose one."""
    now = _at(config.NFL_PROP_PUBLISH_HOUR_UTC + 1)
    assert card_mod.publishable_games(_games(now, 6.0), now) == set()


def test_publish_hour_missed_is_a_noop_without_a_database():
    """--offline has no connection and cannot publish anyway; it must not
    crash, and it must not claim the pass was missed."""
    assert card_mod.publish_hour_missed(
        None, _at(config.NFL_PROP_PUBLISH_HOUR_UTC + 1)) is False


def test_main_reads_the_clock_once_for_the_whole_pass():
    """card() and the publish gate must agree about what time it is.

    A pass that starts at 13:59 would build its card inside the publish hour
    and then evaluate the gate at 14:00 — silently skipping that game's ONLY
    publish window for the week, and leaving no pick and no error. Reading
    `datetime.now()` twice in main() is what makes that possible, so pin the
    single read.
    """
    import inspect
    src = inspect.getsource(card_mod.main)
    assert src.count("datetime.now(") <= 1, (
        "main() reads the wall clock more than once; card() and "
        "publishable_games() can then straddle the publish hour boundary")
    assert "publishable_games(games, now" in src, (
        "the publish gate must use the same `now` the card was built with")
    assert "publish_hour_missed(conn, now)" in src, (
        "the catch-up check must use that same `now` too")
    assert "now=now" in src and "now=as_of" not in src, (
        "card() must receive the same `now`; passing as_of (None on a live "
        "run) re-reads the clock inside card()")
    assert "replay=as_of is not None" in src, (
        "a live pass supplies now but is not a replay — the quote filter "
        "would otherwise clip to the pass start and drop the --fetch")


def test_a_game_with_no_kickoff_is_never_published():
    """No kickoff means the lead is unknowable, and an unknown lead is exactly
    what the ceiling exists to stop."""
    now = _at(config.NFL_PROP_PUBLISH_HOUR_UTC)
    assert card_mod.publishable_games({"G": {"date": "2026-09-20"}}, now) == set()


@pytest.mark.parametrize("hour", [h for h in range(24)
                                  if h != config.NFL_PROP_PUBLISH_HOUR_UTC])
def test_no_other_hour_publishes_even_at_a_perfect_lead(hour):
    """The hour is the gate. A game at the ideal 6h lead is still not bet on
    the 09:xx pass, because it will be offered again at 13:xx."""
    now = _at(hour)
    assert card_mod.publishable_games(_games(now, 6.0), now) == set()
