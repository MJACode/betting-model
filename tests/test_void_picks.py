"""Voiding a pick that should never have been official, without deleting it.

THE RULE THIS SITS BESIDE. CLAUDE.md §1c says a BET is never deleted, and that
rule is about LINE MOVEMENT -- the number moved, the bet still happened. It is
not about a row the model should never have produced, and §1c carves those out
("rows that were never a pick"). But deleting one still throws away the evidence
that it happened, which is usually how the bug was found in the first place.

So the contract under test is: the row SURVIVES, stops counting, carries its
reason, and can never be quietly re-graded when the game finally plays.

First use was the six nfl_wind_totals Week 1 picks that fired at 7.2-8.7 day
leads before #517 landed the firing gate (mike, 2026-09-07).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.void_picks import GRADED, VOID_RESULT, VOID_STATUS, plan_voids, void

REASON = "fired outside the validated lead window (pre-#517)"


def _row(pick_id=1, result=None, label="CLE @ JAX Under 40.5", signal="BET"):
    return {"pick_id": pick_id, "game_id": "NFL_2026_01_CLE_JAX",
            "model_id": "nfl_wind_totals", "pick_label": label,
            "signal_type": signal, "result": result,
            "created_at": "2026-09-05 00:00:19+00"}


class TestWhatMayBeVoided:
    def test_an_unsettled_bet_is_voidable(self):
        to_void, refused = plan_voids([_row()], REASON)
        assert len(to_void) == 1 and not refused

    def test_a_graded_pick_is_refused(self):
        """The line §1c will not let this cross.

        Voiding a WIN or a LOSS is not correcting a bug, it is rewriting a
        settled result. The tool must refuse rather than trust the caller's
        filter -- a --model flag matches settled picks too.
        """
        for result in GRADED:
            to_void, refused = plan_voids([_row(result=result)], REASON)
            assert not to_void, f"{result} was voidable"
            assert result in refused[0]["why"]

    def test_re_running_is_a_no_op_not_a_refusal(self):
        """Idempotent: the same command twice must be safe and say so."""
        to_void, refused = plan_voids([_row(result=VOID_RESULT)], REASON)
        assert not to_void
        assert "no-op" in refused[0]["why"]

    def test_an_empty_reason_is_refused(self):
        """A void with no reason is indistinguishable from data loss later."""
        to_void, refused = plan_voids([_row()], "   ")
        assert not to_void and "reason" in refused[0]["why"]

    def test_a_mixed_batch_splits_rather_than_failing_whole(self):
        rows = [_row(1), _row(2, result="WIN"), _row(3), _row(4, result=VOID_RESULT)]
        to_void, refused = plan_voids(rows, REASON)
        assert [r["pick_id"] for r in to_void] == [1, 3]
        assert [r["pick_id"] for r in refused] == [2, 4]


class _FakeConn:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        return self

    def fetchall(self):
        return []


class TestWhatTheVoidWrites:
    def test_it_updates_and_never_deletes(self):
        """The whole point. A DELETE here would be the §1c violation."""
        conn = _FakeConn()
        void(conn, [_row()], REASON, now="2026-09-07T13:00:00+00:00")
        sql = conn.calls[0][0].upper()
        assert sql.startswith("UPDATE PICKS")
        assert "DELETE" not in sql

    def test_it_sets_the_result_settlement_bounds_on(self):
        """Every settlement query in paper_tracker is `WHERE p.result IS NULL`.

        Setting a non-null result is what makes the void permanent: when these
        games actually play, nothing re-grades them back into the record.
        """
        conn = _FakeConn()
        void(conn, [_row()], REASON, now="2026-09-07T13:00:00+00:00")
        _, params = conn.calls[0]
        assert params[0] == VOID_RESULT

    def test_it_records_the_reason(self):
        conn = _FakeConn()
        void(conn, [_row()], REASON, now="2026-09-07T13:00:00+00:00")
        _, params = conn.calls[0]
        assert VOID_STATUS in params
        assert REASON in params

    def test_it_zeroes_profit_rather_than_leaving_it(self):
        """`profit_flat` FABRICATES -110 for a pick with no DK price (§6).

        A void left carrying a stale profit is exactly that trap: it would read
        as a real result to anything that does not also check `result`.
        """
        conn = _FakeConn()
        void(conn, [_row()], REASON, now="2026-09-07T13:00:00+00:00")
        sql = " ".join(conn.calls[0][0].split()).lower()
        # literals in the statement, not bound params -- same shape
        # paper_tracker's own NO_ACTION path uses.
        assert "profit_flat = 0" in sql and "profit_kelly = 0" in sql

    def test_it_does_not_touch_created_at_or_the_bet_itself(self):
        """Timing is data, not metadata (§1c). The line and price stand too."""
        conn = _FakeConn()
        void(conn, [_row()], REASON, now="2026-09-07T13:00:00+00:00")
        sql = conn.calls[0][0].lower()
        for col in ("created_at", "scored_line", "dk_odds", "model_probability",
                    "pick_label", "signal_type"):
            assert f"{col} " not in sql.split("where")[0], f"the void rewrote {col}"


class TestTheToolRefusesToMatchEverything:
    def test_a_bare_run_is_rejected(self):
        """No filter must not mean "every pick in the table"."""
        src = (ROOT / "scripts" / "void_picks.py").read_text(encoding="utf-8")
        assert "refusing to match every pick" in src

    def test_writing_requires_an_explicit_flag(self):
        src = (ROOT / "scripts" / "void_picks.py").read_text(encoding="utf-8")
        assert '"--apply"' in src and "DRY RUN" in src


class TestAPostedSignalIsLocked:
    """Matt, 2026-09-28: "if a bet is posted as a signal it should be locked".

    Ailin Perez ML (pick 2482412) was posted to Discord on 2026-09-19, voided by
    the EV-floor sweep three hours later, stayed on the board (a VOID never
    retracts the post), won on 2026-09-26 -- and the recap said no UFC pick
    cleared the bar that day. A void cannot un-send a message, so it must not
    be allowed to un-count one.
    """

    def test_a_posted_pick_is_refused(self):
        to_void, refused = plan_voids([{**_row(), "posted": True}], REASON)
        assert not to_void
        assert "posted as a signal" in refused[0]["why"]

    def test_an_unposted_pick_is_still_voidable(self):
        """The lock is on the post, not on voiding: phantom-game rows that
        never reached the channel (pick 661) still void."""
        to_void, _ = plan_voids([{**_row(), "posted": False}], REASON)
        assert len(to_void) == 1

    def test_the_select_reads_the_discord_ledger_on_the_shared_key(self):
        """Both callers (the script and the worker's void_picks job) go
        through _select, so the posted flag must be computed THERE, from the
        one lock_key definition -- not retyped."""
        from scripts.void_picks import POSTED_SQL, _select
        from tracking.publish_keys import live_lock_key_sql, lock_key_sql, posted_sql

        assert POSTED_SQL == posted_sql("p")

        assert "push_sent" in POSTED_SQL
        assert "'discord_signal'" in POSTED_SQL and "'discord_live'" in POSTED_SQL
        assert lock_key_sql("p") in POSTED_SQL
        assert live_lock_key_sql("p") in POSTED_SQL

        conn = _FakeConn()
        _select(conn, [2482412], None, None, None)
        sql = conn.calls[0][0]
        assert "AS posted" in sql and "push_sent" in sql

    def test_the_worker_job_uses_the_same_plan(self):
        src = (ROOT / "tracking" / "job_queue.py").read_text(encoding="utf-8")
        assert "from scripts.void_picks import _select, plan_voids, void" in src


class TestVoidingAPostedPickIsAnExplicitOptIn:
    """mike, 2026-10-09: "Change the rule, void them".

    Eight NCAAF unders were posted to members and decided on DraftKings
    prices 15 to 28 days old: the odds feed had stopped listing those games
    on 2026-09-05, so the number was not one the book was offering. Matt's
    lock (2026-09-28) still holds by default. A posted pick is voided only
    when the caller opts in, and a graded pick is never voided, opt-in or not.
    """

    def test_a_posted_pick_is_refused_by_default_and_told_how_to_opt_in(self):
        to_void, refused = plan_voids([{**_row(), "posted": True}], REASON)
        assert not to_void
        why = refused[0]["why"]
        assert "posted as a signal" in why
        assert "--allow-posted" in why and "allow_posted" in why

    def test_a_posted_pick_is_voided_with_the_opt_in(self):
        to_void, refused = plan_voids([{**_row(), "posted": True}], REASON,
                                      allow_posted=True)
        assert [r["pick_id"] for r in to_void] == [1] and not refused

    def test_a_graded_pick_is_refused_with_or_without_the_opt_in(self):
        for allow in (False, True):
            for result in GRADED:
                rows = [{**_row(result=result), "posted": True},
                        {**_row(2, result=result), "posted": False}]
                to_void, refused = plan_voids(rows, REASON, allow_posted=allow)
                assert not to_void, f"{result} voided with allow_posted={allow}"
                assert all(f"already graded {result}" == r["why"] for r in refused)

    def test_the_opt_in_does_not_skip_the_other_checks(self):
        """An already-void pick stays a no-op and an empty reason is refused."""
        to_void, refused = plan_voids([{**_row(result=VOID_RESULT), "posted": True}],
                                      REASON, allow_posted=True)
        assert not to_void and "no-op" in refused[0]["why"]
        to_void, refused = plan_voids([{**_row(), "posted": True}], "  ",
                                      allow_posted=True)
        assert not to_void and "reason" in refused[0]["why"]

    def test_the_command_line_has_the_flag(self):
        src = (ROOT / "scripts" / "void_picks.py").read_text(encoding="utf-8")
        assert '"--allow-posted"' in src
        assert "allow_posted=a.allow_posted" in src
