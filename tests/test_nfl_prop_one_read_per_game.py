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
