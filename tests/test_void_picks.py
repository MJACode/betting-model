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
