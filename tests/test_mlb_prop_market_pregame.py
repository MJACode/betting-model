"""models/mlb_prop_market.load_quotes must read a PRE-GAME price.

THE BUG, found 2026-09-06 while grading the rule for the first time. The loader
excluded snapshot_type='in_play' and stopped there, then took the newest row per
proposition. But the prop ingestor keeps snapshotting after first pitch and
labels those rows 'open' — measured, 5,583 of 24,034 DraftKings
batter_total_bases rows over ten dates (23%) carry a snapshot_at after their own
game started. Ordering by snapshot_at DESC then preferentially selects exactly
those, because they are the newest thing in the table.

It is the same defect as pick 107657 (tests/test_prop_price_pregame_bound.py),
fixed for the prop SCORER on 2026-09-03 and never applied to this module.

WHAT IT DID TO THE NUMBERS. Against DraftKings' own de-vigged probability, over
ten dates of Pinnacle coverage:

    unbounded    n=1585   actual over 24.7%   DK says 34.9%   -10.1pp
    pre-game     n=1116   actual over 41.6%   DK says 41.7%    -0.2pp

The first grading of the rule on MLB came back negative at every threshold and
this was the reason: an in-play DraftKings price differenced against a pre-game
Pinnacle price is a manufactured edge, not a soft line. Qualifying bets at a 5pp
cut fell from 291 to 37 once bounded — i.e. seven of every eight "edges" the
rule would have bet were this bug.

Why it matters even though the rule has never published: it is wired for the
first time in this release, and a leak that inflates edge is exactly what an
edge threshold selects FOR rather than protects against.
"""
from __future__ import annotations

import inspect

import models.mlb_prop_market as mk
import models.wnba_prop_market as wk


class _Conn:
    """Answers with whatever the query asks for, and records the SQL."""

    def __init__(self, rows):
        self.rows, self.sql = rows, ""

    def execute(self, sql, params=None):
        self.sql = " ".join(sql.split())
        return self

    def fetchall(self):
        return self.rows


# (game_id, player, market, book, line, over, under, snapshot_at, cutoff)
_CUT = "2026-09-05T23:10:00+00:00"
PREGAME = ("MLB_x", "Kurtz", "batter_total_bases", "draftkings",
           1.5, -150, 120, "2026-09-05T22:00:00+00:00", _CUT)
IN_PLAY = ("MLB_x", "Kurtz", "batter_total_bases", "draftkings",
           1.5, 400, -600, "2026-09-05T23:55:00+00:00", _CUT)


def test_the_post_first_pitch_quote_is_dropped_even_though_it_is_newest():
    """The whole bug in one assertion: IN_PLAY is newer, so an ORDER BY
    snapshot_at DESC picks it. It must not survive."""
    q = mk.load_quotes(_Conn([PREGAME, IN_PLAY]), "2026-09-05")
    assert q, "everything was dropped — the loader is now too strict"
    got = q[("MLB_x", "Kurtz", "batter_total_bases", "draftkings")]
    assert got["over_price"] == -150.0, (
        f"priced off the in-play quote: got {got['over_price']}, expected -150")


def test_the_newest_qualifying_quote_still_wins():
    """Bounding must not turn this into an OPENING-line reader. Among rows that
    are pre-game, the latest is still the price a bet would be placed at."""
    earlier = (*PREGAME[:4], 1.5, -110, -110, "2026-09-05T18:00:00+00:00", _CUT)
    q = mk.load_quotes(_Conn([earlier, PREGAME]), "2026-09-05")
    assert q[("MLB_x", "Kurtz", "batter_total_bases", "draftkings")]["over_price"] == -150.0


def test_a_game_with_no_cutoff_fails_open():
    """Synthetic and historical rows carry no usable timing. Guards fail open on
    a missing timestamp (§7) or seventeen seasons vanish."""
    no_cut = (*PREGAME[:8], None)
    q = mk.load_quotes(_Conn([no_cut]), "2026-09-05")
    assert len(q) == 1


def test_it_joins_games_and_uses_the_shared_cutoff():
    """Source guard. The bound must come from pregame_cutoff_sql — the actual
    first pitch, clamped — not from commence_time, which runs ~19 minutes late
    and would readmit a quarter-hour of in-play quotes."""
    src = inspect.getsource(mk.load_quotes)
    assert "pregame_cutoff_sql(" in src, src
    assert "JOIN games g" in src, src


def test_it_compares_parsed_timestamps_not_strings():
    """snapshot_at and commence_time are TEXT in mixed 'Z'/offset shapes, so
    string order is not chronological order — the session-106 leak that
    invalidated a whole WNBA threshold sweep."""
    src = inspect.getsource(mk.load_quotes)
    assert "_parse_iso_ts(" in src, src


def test_both_market_relative_loaders_bound_on_the_cutoff():
    """§1b: the maths is shared precisely so a fix in one copy is a fix in all.
    WNBA had this guard from the start and MLB did not, which is how a six-day
    hole opened. If a third sport is added, it lands here."""
    for loader in (mk.load_quotes, wk.load_wnba_prop_quotes):
        src = inspect.getsource(loader)
        assert "pregame_cutoff_sql(" in src, f"{loader.__qualname__} is unbounded"
        assert "_parse_iso_ts(" in src, f"{loader.__qualname__} compares strings"
