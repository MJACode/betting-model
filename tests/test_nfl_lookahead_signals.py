"""
NFL picks are written days ahead and never reach Discord.

Both §28 rules publish with a FUTURE game_date and are INSERT-ONCE: an
nfl_opener_spread pick locks in the T-7..T-2 window and is never re-priced,
because the edge IS the stale soft-book number. But capture_opening_signals was
same-day-only (except a UFC shadow window), and _new_signals filtered
`os.game_date = today` -- so an NFL pick locked on Tuesday for Sunday could only
be captured and posted on SUNDAY, after the book has corrected and the bet no
longer exists.

The two windows must stay in step: capture reaching forward without the poster
reaching forward would lock rows that then sit unposted until kickoff, which is
the same outcome with more moving parts. These tests pin both, and pin that the
widening is NFL-only -- UFC/GOLF/NCAAF delete-and-rescore until game morning, so
for them "wait for game day" is correct and must not change.
"""

import config
from tracking import discord_notifier as dn


def test_nfl_horizon_matches_the_capture_window():
    assert dn._nfl_horizon("2026-09-06") == "2026-09-13"
    assert config.NFL_LOCK_AHEAD_DAYS == 7


def test_capture_reaches_forward_for_nfl_only():
    """The capture predicate admits future UFC and future NFL, nothing else."""
    import inspect
    from tracking import opening_signals as osig

    src = inspect.getsource(osig.capture_opening_signals)
    assert "p.sport = 'NFL'" in src
    assert "p.sport = 'UFC'" in src
    for other in ("'GOLF'", "'NCAAF'", "'MLB'"):
        assert f"p.sport = {other}" not in src


def test_poster_reaches_forward_for_nfl_only():
    import inspect

    src = inspect.getsource(dn._new_signals)
    assert "os.sport = 'NFL'" in src
    for other in ("'UFC'", "'GOLF'", "'NCAAF'"):
        assert f"os.sport = {other}" not in src


def test_early_suffix_stays_ufc_only():
    """A UFC look-ahead lock gets ':early' (measurement, never displayed); an
    NFL look-ahead lock must get the NORMAL key or it can never post."""
    import inspect
    from tracking import opening_signals as osig

    src = inspect.getsource(osig.capture_opening_signals)
    assert "p.sport = 'UFC' AND p.game_date > %s" in src
    # the ':early' CASE is guarded by sport, not by date alone
    assert "THEN ':early'" in src
    case = src.split("THEN ':early'")[0]
    assert case.rstrip().endswith("p.sport = 'UFC' AND p.game_date > %s")


def test_new_signals_binds_three_date_params():
    """Three placeholders in the date predicate, three args -- a mismatch here
    is a psycopg2 error at runtime, not a test failure, so pin it."""
    captured = {}

    class _Conn:
        def execute(self, sql, params=None):
            captured["sql"] = sql
            captured["params"] = params
            return self

        def fetchall(self):
            return []

    dn._new_signals(_Conn(), "2026-09-06")
    date_pred = captured["sql"].split("WHERE (")[1].split("AND os.lock_key")[0]
    assert date_pred.count("%s") == 3
    assert captured["params"] == ("2026-09-06", "2026-09-06", "2026-09-13")
