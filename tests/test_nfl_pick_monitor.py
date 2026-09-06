"""
Tests for locked-NFL-pick history and the condition flag.

The contract under test is the one that matters operationally: a pick is
IMMUTABLE once locked, and everything observed afterwards is recorded beside it
rather than applied to it. A collapsed forecast must never delete a bet.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.nfl_pick_monitor import classify, latest_per_pick


def _row(qualifies, reason, observed_at="2026-09-18T12:00:00+00:00", **kw):
    base = dict(game_id="2026_03_NYJ_BUF", model_id="nfl_wind_totals",
                observed_at=observed_at, qualifies="1" if qualifies else "0",
                reason=reason)
    base.update(kw)
    return base


class TestClassify:
    def test_still_qualifying_is_ok(self):
        still, status, _ = classify(_row(True, "wind 14.2 mph, edge +6.10pp, 1.05 units"))
        assert (still, status) == (True, "OK")

    def test_forecast_collapse_is_gone(self):
        # The case the whole mechanism exists for.
        still, status, reason = classify(
            _row(False, "forecast wind 8.4 mph below the 11 mph threshold"))
        assert still is False
        assert status == "GONE"
        assert "8.4" in reason

    def test_deviation_corrected_is_gone(self):
        still, status, _ = classify(
            _row(False, "deviation +0.50 below the 1.0 pt threshold",
                 model_id="nfl_opener_spread"))
        assert (still, status) == (False, "GONE")

    def test_juice_eating_the_edge_is_only_degraded(self):
        # The premise still holds; the price moved. That is not the same thing
        # as the wind dying, and it must not be reported as though it were.
        still, status, _ = classify(
            _row(False, "wind 13.0 mph but edge +1.20pp below 3pp"))
        assert (still, status) == (False, "DEGRADED")

    def test_uncalibrated_lead_is_gone(self):
        still, status, _ = classify(
            _row(False, "wind 12.0 mph but lead 8.4d is beyond the 7-day calibration"))
        assert (still, status) == (False, "GONE")

    def test_waiting_on_pinnacle_is_degraded_not_gone(self):
        # Pinnacle not being up yet is the model waiting, not the model
        # declining — a locked pick should not read GONE because of it.
        still, status, _ = classify(
            _row(False, "waiting on Pinnacle (posts ~T-6.5 days)",
                 model_id="nfl_opener_spread"))
        assert (still, status) == (False, "DEGRADED")


class TestLatestPerPick:
    def test_newest_observation_wins(self):
        rows = [
            _row(True, "early", observed_at="2026-09-18T10:00:00+00:00"),
            _row(False, "later", observed_at="2026-09-18T16:00:00+00:00"),
            _row(True, "middle", observed_at="2026-09-18T13:00:00+00:00"),
        ]
        latest = latest_per_pick(rows)
        assert len(latest) == 1
        assert latest[("2026_03_NYJ_BUF", "nfl_wind_totals")]["reason"] == "later"

    def test_models_are_tracked_separately(self):
        rows = [
            _row(True, "wind view", model_id="nfl_wind_totals"),
            _row(False, "opener view", model_id="nfl_opener_spread"),
        ]
        latest = latest_per_pick(rows)
        assert len(latest) == 2
        assert latest[("2026_03_NYJ_BUF", "nfl_opener_spread")]["reason"] == "opener view"

    def test_every_tick_is_retained_as_history(self):
        # latest_per_pick collapses for the FLAG; the caller still writes one
        # history row per tick. Guard the input is not deduped upstream.
        rows = [_row(True, f"tick {i}", observed_at=f"2026-09-18T{10+i:02d}:00:00+00:00")
                for i in range(5)]
        assert len(rows) == 5
        assert len(latest_per_pick(rows)) == 1


class TestImmutabilityContract:
    def test_monitor_never_writes_to_bet_columns(self):
        # A regression guard with teeth: if someone later "fixes" a stale pick
        # by updating its line or price here, this fails. The bet is placed;
        # only the description of its conditions may change.
        src = (ROOT / "scripts" / "nfl_pick_monitor.py").read_text(encoding="utf-8")
        update_sql = src[src.index("UPDATE picks"):src.index("WHERE pick_id = %s")]
        for forbidden in ("scored_line", "dk_odds", "model_probability", "edge",
                          "recommended_bet", "kelly_fraction", "pick_side",
                          "pick_label", "signal_type"):
            assert forbidden not in update_sql, f"monitor must not update picks.{forbidden}"
        assert "condition_status" in update_sql
        # No SQL delete anywhere in the monitor. Checked as a statement, not as
        # a word: the docstring legitimately talks about picks being deleted.
        assert "DELETE FROM" not in src.upper()


class TestWindPublisherLock:
    """Wind switched from delete-and-replace to insert-once on 2026-08-22."""

    def test_wind_publish_no_longer_deletes_unstarted_picks(self):
        src = (ROOT / "scripts" / "nfl_wind_publisher.py").read_text(encoding="utf-8")
        wind = src[src.index("def publish("):src.index("def publish_opener(")]
        assert "DELETE FROM picks" not in wind.upper(), (
            "wind must not clear unstarted picks — a locked bet stands and a "
            "collapsed forecast is flagged, not deleted")

    def test_wind_publish_skips_already_locked_games(self):
        src = (ROOT / "scripts" / "nfl_wind_publisher.py").read_text(encoding="utf-8")
        wind = src[src.index("def publish("):src.index("def publish_opener(")]
        assert "locked" in wind and "SELECT DISTINCT game_id FROM picks" in wind

    def test_opener_lock_is_unchanged(self):
        # The opener already worked this way; make sure the wind change did not
        # disturb it.
        src = (ROOT / "scripts" / "nfl_wind_publisher.py").read_text(encoding="utf-8")
        opener = src[src.index("def publish_opener("):]
        assert "INSERT-ONCE LOCK" in opener
        assert "DELETE FROM picks" not in opener.upper()


class TestTheJoinKeyMatchesPicks:
    """The monitor wrote NOTHING for its whole life, and exited 0 doing it.

    Measured 2026-09-06: `nfl_pick_status_history` held 0 rows for every model
    and `condition_status` was NULL on all five live wind picks, while the
    worker logged

        NFL pick monitor 2026-09-06: 0 locked pick(s) observed

    on every hourly tick. Not a missing dump and not a schema problem -- the
    post-loop message only prints when the CSV was read and had rows.

    `pick_eval.eval_row` wrote the BARE nflverse id and its field comment called
    it "the join key to picks". Both publishers write `NFL_{nflverse_id}`. So
    `latest_per_pick` keys the dump on `2026_01_CLE_JAX`, the monitor looks up
    `NFL_2026_01_CLE_JAX`, misses every time, and reports a clean run.

    It is load-bearing: the 2026-08-22 insert-once lock is justified in
    scheduler.py by "every later tick records whether the conditions still
    hold", and that had never once happened.
    """

    def test_eval_row_emits_the_id_the_publisher_writes(self):
        import sys as _sys
        nfl = str(ROOT / "nfl")
        _sys.path.insert(0, nfl)
        try:
            from data_ingest.pick_eval import eval_row
        finally:
            _sys.path.remove(nfl)
        row = eval_row(game_id="2026_01_CLE_JAX", model_id="nfl_wind_totals",
                       kick_utc="2026-09-13T17:00:00+00:00", lead_hours=96.0,
                       qualifies=True, reason="wind 14.0 mph")
        assert row["game_id"] == "NFL_2026_01_CLE_JAX", (
            "the eval dump's game_id must be the one picks.game_id holds, or "
            "the monitor's lookup misses every row and exits 0")

    def test_an_already_prefixed_id_is_not_double_prefixed(self):
        import sys as _sys
        nfl = str(ROOT / "nfl")
        _sys.path.insert(0, nfl)
        try:
            from data_ingest.pick_eval import eval_row
        finally:
            _sys.path.remove(nfl)
        row = eval_row(game_id="NFL_2026_01_CLE_JAX", model_id="nfl_wind_totals",
                       kick_utc="2026-09-13T17:00:00+00:00", lead_hours=96.0,
                       qualifies=False, reason="indoor")
        assert row["game_id"] == "NFL_2026_01_CLE_JAX"

    def test_the_monitor_lookup_actually_resolves(self):
        """The failure end to end, at the shape the monitor uses.

        `latest_per_pick` keys on (game_id, model_id) and the monitor looks the
        pick's own game_id up in it. Asserting on that dict is what makes this a
        test of the JOIN rather than of a string format.
        """
        import sys as _sys
        nfl = str(ROOT / "nfl")
        _sys.path.insert(0, nfl)
        try:
            from data_ingest.pick_eval import eval_row
        finally:
            _sys.path.remove(nfl)
        dump = [eval_row(game_id="2026_01_CLE_JAX", model_id="nfl_wind_totals",
                         kick_utc="2026-09-13T17:00:00+00:00", lead_hours=96.0,
                         qualifies=True, reason="wind 14.0 mph")]
        latest = latest_per_pick(dump)
        # what scripts/nfl_wind_publisher.py put in picks.game_id
        assert ("NFL_2026_01_CLE_JAX", "nfl_wind_totals") in latest

    def test_the_publisher_still_writes_the_prefix_this_assumes(self):
        """If the publisher ever drops the prefix, fix eval_row, not this."""
        src = (ROOT / "scripts" / "nfl_wind_publisher.py").read_text(encoding="utf-8")
        assert 'f"NFL_{nflverse_id}"' in src

    def test_the_opener_dump_gets_the_same_id(self):
        """Both models feed eval_row, which is why the fix lives there.

        `opener_spread.evaluate_board` passes a bare `g.game_id` exactly as the
        wind model does, and `nfl_wind_publisher.publish_opener` writes the same
        `NFL_` prefix. Without this the "fixes both at once" claim is asserted
        in a commit message and tested nowhere.
        """
        import sys as _sys
        nfl = str(ROOT / "nfl")
        _sys.path.insert(0, nfl)
        try:
            from data_ingest.pick_eval import eval_row
        finally:
            _sys.path.remove(nfl)
        row = eval_row(game_id="2026_02_NYJ_BUF", model_id="nfl_opener_spread",
                       kick_utc="2026-09-20T17:00:00+00:00", lead_hours=120.0,
                       qualifies=False, reason="no clean soft book quoting")
        assert row["game_id"] == "NFL_2026_02_NYJ_BUF"
        assert ("NFL_2026_02_NYJ_BUF", "nfl_opener_spread") in latest_per_pick([row])
