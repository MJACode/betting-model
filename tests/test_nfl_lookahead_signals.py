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
the same outcome with more moving parts. These tests pin both.

NCAAF JOINED NFL ON 2026-08-30, and this file's original premise is why it took
a bug to notice. It used to read "the widening is NFL-only -- UFC/GOLF/NCAAF
delete-and-rescore until game morning, so for them 'wait for game day' is
correct". That was true when written and stopped being true the morning #311
made the pick lock general: a BET now freezes its (game, model) pair the moment
it crosses, in EVERY sport, so an NCAAF look-ahead BET is as immutable as an
NFL one and has the same reason to post immediately.

The cost of the gap was a real pick. A Florida Atlantic +27.5 (-115) BET locked
2026-08-29 for a 2026-09-05 kickoff had no opening_signals row at all and could
not have reached Discord for seven days.

The property being pinned is therefore NOT "NFL only" but "the look-ahead
window covers exactly the sports whose picks are locked when they land". UFC
stays out of the DISPLAY path deliberately -- it captures under a ':early' key
that is measurement, never published -- and GOLF is not captured ahead at all.
"""

import config
from tracking import discord_notifier as dn


def test_lookahead_horizon_matches_the_capture_window():
    assert dn._lookahead_horizon("2026-09-06") == "2026-09-13"
    assert config.NFL_LOCK_AHEAD_DAYS == 7
    assert config.NCAAF_SCORE_AHEAD_DAYS == 7


def test_the_horizon_covers_the_furthest_reaching_sport():
    """
    One horizon serves both look-ahead sports, so it must be the MAX. Taking
    the min (or just NFL's) would orphan the other sport's rows the moment the
    two constants diverge -- captured, locked, and never postable, which is the
    exact bug this file exists about.
    """
    import inspect
    src = inspect.getsource(dn._lookahead_horizon)
    assert "max(" in src
    assert "NCAAF_SCORE_AHEAD_DAYS" in src and "NFL_LOCK_AHEAD_DAYS" in src


def test_capture_reaches_forward_for_the_locked_lookahead_sports():
    """Future UFC (shadow), future NFL and future NCAAF -- and nothing else.

    MLB and WNBA are same-day boards with no look-ahead to capture; GOLF has
    its own scorer and is deliberately not widened here.
    """
    import inspect
    from tracking import opening_signals as osig

    src = inspect.getsource(osig.capture_opening_signals)
    for included in ("'NFL'", "'UFC'", "'NCAAF'"):
        assert f"p.sport = {included}" in src
    for other in ("'GOLF'", "'MLB'", "'WNBA'"):
        assert f"p.sport = {other}" not in src


def test_poster_reaches_forward_for_exactly_the_captured_sports():
    """
    The poster's window must match capture's DISPLAY set. UFC is captured ahead
    but under ':early', which never displays, so it must NOT appear here --
    posting a UFC shadow row would publish a measurement as a bet.
    """
    import inspect

    src = inspect.getsource(dn._new_signals)
    assert "os.sport IN ('NFL', 'NCAAF')" in src
    for other in ("'UFC'", "'GOLF'"):
        assert f"os.sport = {other}" not in src


def test_ncaaf_lookahead_is_only_safe_because_the_lock_is_general():
    """
    The load-bearing dependency, pinned so removing the lock cannot silently
    leave this widening in place. If a look-ahead BET could be re-priced, then
    posting it days early would publish a number that later changes -- the
    exact thing §1c forbids.
    """
    assert config.LOCK_GAME_PICKS_AT_FIRST_RUN, (
        "NCAAF look-ahead signals may only post early while a BET is frozen "
        "at its first cross")


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
