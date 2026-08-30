"""
Regression: notify_discord_live raised KeyError and posted NOTHING, ever.

_new_live_signals built its dicts without a "commence" key while _signal_field
subscripted s["commence"]. Both callers (models/live_scorer.py and
ncaaf_live/gameday.py) wrap the call in swallow-and-log, so the failure was
invisible: `push_sent` carried zero 'discord_live' rows from the day Discord
shipped until this was found, across every sport.

The load-bearing test is test_producer_output_renders: it runs the REAL producer
against a fake cursor and feeds its REAL output to the renderer. A hand-written
fixture cannot catch this class of bug, because a hand-written fixture drifts
from the producer in exactly the way the renderer did.
"""

import pytest

from tracking import discord_notifier as dn


# One row in _new_live_signals' SELECT order. Kept as a tuple on purpose: if a
# column is added to the query without being added here the test fails loudly,
# which is the point.
_ROW = (
    "NCAAF_2026-08-29_north-carolina_tcu",   # game_id
    "ncaaf_live_total",                      # model_id
    "over",                                  # pick_side
    "North Carolina @ TCU Over 50.5 (live)", # pick_label
    "NCAAF",                                 # sport
    0.662,                                   # model_probability
    0.138,                                   # edge
    -110.0,                                  # dk_odds
    0.02,                                    # kelly_fraction
    None,                                    # inning_at_pick
    None,                                    # dk_bet_link
    "TCU",                                   # home_team
    "North Carolina",                        # away_team
    "2026-08-29T16:00:00Z",                  # commence_time
    "2026-08-29T16:14:38.528378+00:00",      # created_at (written to the DB)
)


class _FakeConn:
    """Minimal stand-in: execute(...).fetchall() -> the rows we hand it."""

    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        self._sql = sql
        return self

    def fetchall(self):
        return self._rows


def test_producer_output_renders():
    """THE regression. Real producer -> real renderer, no hand-written dict."""
    signals = dn._new_live_signals(_FakeConn([_ROW]), "2026-08-29")
    assert len(signals) == 1
    field = dn._signal_field(signals[0])     # KeyError('commence') before the fix
    assert field["name"] == "North Carolina @ TCU Over 50.5 (live)"
    assert "North Carolina @ TCU" in field["value"]
    assert "-110" in field["value"]


def test_producer_output_builds_a_live_embed():
    signals = dn._new_live_signals(_FakeConn([_ROW]), "2026-08-29")
    embed = dn._picks_embed("NCAAF", signals, "2026-08-29", live=True)
    assert "LIVE" in embed["title"]
    assert embed["color"] == dn._COLOR_LIVE
    assert len(embed["fields"]) == 1


def test_producer_select_and_dict_stay_in_step():
    """The query must not grow a column the dict literal ignores, or shrink one
    it reads — the failure mode that produced the bug in the first place."""
    conn = _FakeConn([_ROW])
    dn._new_live_signals(conn, "2026-08-29")
    # 15 columns projected, 15 tuple slots consumed.
    assert conn._sql.count("p.") + conn._sql.count("g.") >= 15
    with pytest.raises(IndexError):
        dn._new_live_signals(_FakeConn([_ROW[:-1]]), "2026-08-29")


@pytest.mark.parametrize("missing", ["commence", "home", "away", "sport"])
def test_renderer_survives_a_missing_context_field(missing):
    """Belt and braces: a future producer that forgets a context key degrades to
    a shorter card, it does not stop the post."""
    s = dn._new_live_signals(_FakeConn([_ROW]), "2026-08-29")[0]
    del s[missing]
    field = dn._signal_field(s)              # must not raise
    assert field["name"]
    assert "-110" in field["value"]


def test_unpriced_live_signal_still_renders():
    row = list(_ROW)
    row[7] = None                            # dk_odds
    row[8] = None                            # kelly_fraction
    s = dn._new_live_signals(_FakeConn([tuple(row)]), "2026-08-29")[0]
    assert "N/A" in dn._signal_field(s)["value"]


def test_a_live_price_is_stamped_with_when_it_was_taken():
    """An in-play number is only the number it was when we wrote it down.
    Without the stamp the post reads as "available now" and sends someone to a
    book that has already moved -- the CWS@MIN 9.5 -> 10.5 case.

    SECONDS, not minutes: a live total moves a full run on one scoring play, so
    the age of an in-play number matters at a resolution a pre-game one never
    does."""
    s = dn._new_live_signals(_FakeConn([_ROW]), "2026-08-29")[0]
    value = dn._signal_field(s)["value"]
    assert "posted" in value and "12:14:38 PM ET" in value


def test_a_pick_with_no_write_time_renders_without_a_stamp():
    """A missing created_at must simply drop the note, never raise."""
    s = dn._new_live_signals(_FakeConn([_ROW]), "2026-08-29")[0]
    s.pop("posted_at")
    assert "posted" not in dn._signal_field(s)["value"]
