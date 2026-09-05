"""A pick reaches Discord and the phone exactly when the app shows it.

ORIGINAL PREMISE (2026-08-30), now retired. NFL and NCAAF picks are written days
ahead and are INSERT-ONCE: an `nfl_opener_spread` pick locks in the T-7..T-2
window and is never re-priced, because the edge IS the stale soft-book number.
The publishing path read `opening_signals`, so a look-ahead pick could only post
once `capture_opening_signals` had locked it -- and capture reached forward a
fixed number of days. This file used to pin "the capture window and the poster's
window stay in step", because a capture reaching further than the poster locks
rows that sit unposted until kickoff, and the reverse orphans them entirely.

WHY THAT PREMISE WAS THE BUG. Keeping two windows in sync is a thing you can
only fail at quietly. On 2026-09-05 both Week 1 `nfl_wind_totals` picks were
written for a 2026-09-13 kickoff -- 9 days out, against a 7-day window -- so
they were never captured, never posted, and never pushed, while the app showed
them the whole time. `config.NFL_LOCK_AHEAD_DAYS` even carried a comment saying
"the wind card never reaches further than ~4 days out"; `scheduler`'s poll
horizon is 10.

Measured over every eligible BET from the first Discord signal (2026-08-23
22:42 ET) to 2026-09-05: 125 eligible, 119 posted, 6 missed -- and every one of
the 6 was never CAPTURED, none were captured-then-unposted. Capture was the
whole leak, and it was a gate the app never had.

Matt, 2026-09-05: "the app and discord should always show the same picks. They
should be identical."

So the property pinned here is no longer "the two windows agree". It is that
there is only ONE window, because the publishers read the same table the app
reads. `opening_signals` keeps its own horizon for the CLV / opening-signal
shadow track (docs/opening_signals.md) and no longer gates display.
"""

import config
from tracking import discord_notifier as dn
from tracking import push_notifier as pn


class _Conn:
    """Captures the statement and binds; returns no rows."""

    def __init__(self):
        self.sql = None
        self.params = None

    def execute(self, sql, params=None):
        self.sql, self.params = sql, params
        return self

    def fetchall(self):
        return []


def _sql_for(producer):
    conn = _Conn()
    producer(conn, "2026-09-06")
    return conn


# ── the parity property ──────────────────────────────────────────────────────

def test_both_publishers_read_the_table_the_app_reads():
    """`picks`, not `opening_signals`.

    The app queries `picks` directly (mobile/src/lib/queries.ts) and never
    mentions `opening_signals`. A publisher reading the capture table is reading
    a strict SUBSET of what the app shows -- capture can only ever lose rows,
    never add one -- so the two surfaces cannot agree by construction.
    """
    for producer in (dn._new_signals, pn._new_bet_signals):
        sql = _sql_for(producer).sql
        assert "FROM picks p" in sql, f"{producer.__name__} must read picks"
        assert "opening_signals" not in sql, (
            f"{producer.__name__} still reads the capture table, so a pick the "
            f"app shows can still fail to publish")


def test_neither_publisher_has_a_lookahead_horizon():
    """The 9-day pick is the regression. No horizon means nothing to fall outside of.

    Pinned as the ABSENCE of the constants that used to build the window: a test
    that only checked "a 9-day pick survives" would pass against a 10-day window
    and fail again at 11.
    """
    for producer in (dn._new_signals, pn._new_bet_signals):
        sql = _sql_for(producer).sql
        assert "NFL_LOCK_AHEAD_DAYS" not in sql
        assert "NCAAF_SCORE_AHEAD_DAYS" not in sql
        # The only date bind left is the NULL-commence_time floor.
        assert sql.count("%s") == 1, (
            f"{producer.__name__} binds {sql.count('%s')} date params; the "
            f"publisher should have exactly one (the no-start-time floor)")
    assert not hasattr(dn, "_lookahead_horizon"), (
        "the horizon helper is retired, not merely unused -- leaving it invites "
        "a future producer to reach for it")


def test_the_publishers_bind_exactly_what_they_declare():
    """A placeholder/arg mismatch is a psycopg2 error at runtime, not a test
    failure, so pin the count against the bind tuple."""
    for producer in (dn._new_signals, pn._new_bet_signals):
        conn = _sql_for(producer)
        assert conn.params == ("2026-09-06",), (
            f"{producer.__name__} bound {conn.params!r}")


def test_a_started_game_is_still_never_published():
    """The one guard that SHOULD bound the set, kept on both surfaces.

    Removing the date horizon must not remove this: the pick is a legitimate bet
    of record, but announcing it once the game is under way sends the reader to
    a bet they cannot take.
    """
    for producer in (dn._new_signals, pn._new_bet_signals):
        sql = _sql_for(producer).sql
        assert "g.commence_time::timestamptz > NOW()" in sql
        assert "g.commence_time IS NULL" in sql, (
            "an unknown start time must not silently suppress a signal (golf)")


def test_both_publishers_apply_the_apps_action_filter():
    """Same cut, same source row. If one surface gates differently from the
    other they diverge again, just more subtly than a date window."""
    for producer in (dn._new_signals, pn._new_bet_signals):
        sql = _sql_for(producer).sql
        assert "model_action_thresholds" in sql
        assert "t.paused = FALSE" in sql
        assert "p.model_probability >= t.min_prob" in sql
        assert "t.prob_only = TRUE OR p.edge >= COALESCE(t.min_edge, 0)" in sql
        assert "p.dk_odds >= t.min_odds" in sql, (
            "min_odds was missing from the push producer until 2026-09-05, so "
            "the phone could buzz on a price the app filtered out")


def test_the_first_bet_is_the_one_published():
    """§1c: the bet of record is the FIRST cross, not the latest re-price.

    `picks` can hold more than one BET per (game, model, player) from before
    #311 made the pick lock general, so reading the table directly has to pick
    the earliest deliberately -- otherwise dropping `opening_signals` would
    quietly start publishing a later number than the one that was locked.
    """
    for producer in (dn._new_signals, pn._new_bet_signals):
        sql = _sql_for(producer).sql
        assert "DISTINCT ON (p.game_id, p.model_id, COALESCE(p.player_id, ''))" in sql
        order = sql[sql.index("ORDER BY p.game_id"):]
        assert order.startswith(
            "ORDER BY p.game_id, p.model_id, COALESCE(p.player_id, ''),\n"
            "                     p.created_at"), (
            f"{producer.__name__} must break the DISTINCT ON tie by created_at")


def test_the_ledger_key_matches_the_one_capture_minted():
    """Nothing already published may publish twice.

    `push_sent` rows were written against `opening_signals.lock_key`
    (`game:model[:player]`). Reading `picks` has to synthesise the identical
    key, or every pick ever posted looks new on the first run after deploy.
    """
    for producer, kind in ((dn._new_signals, "discord_signal"),
                           (pn._new_bet_signals, "new_bet")):
        sql = _sql_for(producer).sql
        assert ("p.game_id || ':' || p.model_id\n"
                "                       || COALESCE(':' || p.player_id, '') AS lock_key") in sql
        assert f"s.kind = '{kind}'" in sql


def test_the_two_surfaces_never_suppress_each_other():
    """Independent ledger kinds. One key, two kinds -- so a Discord post cannot
    consume the phone's notification or the reverse."""
    assert "s.kind = 'discord_signal'" in _sql_for(dn._new_signals).sql
    assert "s.kind = 'new_bet'" in _sql_for(pn._new_bet_signals).sql


# ── capture still has a horizon, and it now covers what the poller writes ─────

def test_capture_reaches_as_far_as_the_poller_can_write():
    """`opening_signals` is no longer the display gate, but it still feeds the
    CLV / opening-signal track, and at 7 days that track was silently dropping
    NFL look-ahead picks. 10 matches scheduler.NFL_POLL_HORIZON_DAYS, so capture
    covers everything the poller can produce."""
    import scheduler
    assert config.NFL_LOCK_AHEAD_DAYS == 10
    assert config.NFL_LOCK_AHEAD_DAYS >= int(scheduler.NFL_POLL_HORIZON_DAYS), (
        "capture must reach at least as far as the NFL poller writes picks")


def test_capture_reaches_forward_for_the_locked_lookahead_sports():
    """Future UFC, NFL and NCAAF -- and nothing else.

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


def test_ncaaf_lookahead_is_only_safe_because_the_lock_is_general():
    """The load-bearing dependency, pinned so removing the lock cannot silently
    leave the early publishing in place. If a look-ahead BET could be re-priced,
    publishing it days early would publish a number that later changes -- the
    exact thing §1c forbids. This matters MORE now that the publishers read
    `picks` with no horizon at all.
    """
    assert config.LOCK_GAME_PICKS_AT_FIRST_RUN, (
        "look-ahead signals may only publish early while a BET is frozen at "
        "its first cross")


def test_the_early_suffix_is_retired_not_merely_unused():
    """
    UFC look-ahead signals publish as of 2026-08-30 (mike: "UFC: publish").

    The suffix has to be REMOVED from the key expression, not just stop being
    filtered. Leaving it would keep minting ':early' keys while the publishers
    ledger against the plain one -- the same pick under two keys, published
    under one and suppressed under the other.
    """
    import inspect
    from tracking import opening_signals as osig

    src = inspect.getsource(osig.capture_opening_signals)
    assert "THEN ':early'" not in src, "the suffix must not still be minted"
    assert "COALESCE(':' || p.player_id, '')," in src, "plain key expression"
