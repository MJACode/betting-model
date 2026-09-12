"""The credit guards on a paid backfill, and the 2026-09-11 bug they replace.

THE BUG, because the tests below only mean something next to it. The NCAAF
in-play ingestor shipped with `--max-credits 400_000` and `--floor 2_000_000`,
both chosen by hand and both reported as though they bounded the run:

  * the budget was built inside `main()`, so it was per PROCESS. Four shards
    were launched -> four independent 400,000 ceilings against a 373,240 plan.
  * the refuse-to-start check compared the whole season's plan against one
    shard's ceiling, so the ceiling had to exceed the season total for any
    shard to start. 400,000 was picked because the plan came out at 373,240.
  * the floor sat below where the run would land, so it could not fire.

Every test here fails on that shape by construction: the per-shard ceiling and
the measured reserve did not exist in it.
"""
from __future__ import annotations

import pytest

from data.ingestors import ncaaf_inplay_history as ing
from data.ingestors.odds_quota import (
    MIN_BURN_OBSERVATIONS, CreditBudget, daily_burn, latest_remaining,
    plan_credit_budget)


class _Conn:
    """Answers the two quota queries by shape, like the real table."""

    def __init__(self, used_by_day=None, remaining=None):
        self.used_by_day = used_by_day or []
        self.remaining = remaining
        self._last = None

    def execute(self, sql, params=None):
        self._last = "burn" if "requests_used" in sql else "remaining"
        return self

    def fetchall(self):
        # newest first, the way the real query returns it
        return [(d, u) for d, u in reversed(self.used_by_day)]

    def fetchone(self):
        return None if self.remaining is None else (self.remaining,)


# ── the measured burn rate ───────────────────────────────────────────────────

def test_burn_is_the_median_so_one_backfill_day_cannot_set_the_reserve():
    """2026-09-08 burned 838,907 against a ~120k baseline. On a MEAN that one
    day claims the platform needs ~250k/day, and a reserve built on it refuses
    every future backfill."""
    days = [("2026-09-05", 100_000), ("2026-09-06", 220_000),
            ("2026-09-07", 340_000), ("2026-09-08", 1_178_907),
            ("2026-09-09", 1_298_907), ("2026-09-10", 1_418_907)]
    assert daily_burn(_Conn(days)) == 120_000


def test_a_billing_reset_is_not_a_refund():
    """requests_used dropping is a period reset or a top-up. Counting it as a
    negative day drags the median toward zero and the reserve with it."""
    days = [("2026-08-30", 700_000), ("2026-08-31", 820_000),
            ("2026-09-01", 30_000),          # reset
            ("2026-09-02", 150_000), ("2026-09-03", 270_000),
            ("2026-09-04", 390_000)]
    assert daily_burn(_Conn(days)) == 120_000


def test_too_few_days_is_i_do_not_know_not_a_number():
    days = [("2026-09-09", 10), ("2026-09-10", 20)]
    assert len(days) - 1 < MIN_BURN_OBSERVATIONS
    assert daily_burn(_Conn(days)) is None


def test_latest_remaining_reads_the_table():
    assert latest_remaining(_Conn(remaining=2_467_254)) == 2_467_254
    assert latest_remaining(_Conn()) is None


# ── the ceiling ──────────────────────────────────────────────────────────────

def _burn_conn():
    days = [(f"2026-09-{d:02d}", 120_000 * i)
            for i, d in enumerate(range(1, 8), start=1)]
    return _Conn(days, remaining=3_000_000)


def _plan(shard_calls, total_calls=18_662, **kw):
    budget, problems = plan_credit_budget(
        _burn_conn(), shard_calls=shard_calls, total_calls=total_calls,
        credits_per_call=20, **kw)
    return budget, problems


def test_shards_sum_to_the_plan_they_do_not_multiply_it():
    """THE BUG. Four processes must not mean four times the budget."""
    per_shard = [4_666, 4_666, 4_665, 4_665]          # 18,662 calls, split 4 ways
    budgets = [_plan(c)[0] for c in per_shard]
    total_planned = 18_662 * 20
    assert sum(b.ceiling for b in budgets) == total_planned
    assert all(b.ceiling < total_planned for b in budgets)
    # and the old number is nowhere near any of them
    assert all(b.ceiling < 400_000 for b in budgets)


def test_the_default_ceiling_is_the_plan_that_was_approved():
    """A ceiling defaulting to the run's own printed plan cannot be quietly
    fitted to let a bigger job through -- raising it means typing a number."""
    budget, _ = _plan(18_662)
    assert budget.ceiling == budget.total_planned == 373_240


def test_an_explicit_whole_run_budget_is_split_by_share_not_handed_to_each():
    budgets = [_plan(c, max_credits=200_000)[0] for c in (9_331, 9_331)]
    assert [b.ceiling for b in budgets] == [100_000, 100_000]


def test_the_ceiling_stops_the_run_and_says_so():
    budget, _ = _plan(10)                              # 200 credits
    for _ in range(10):
        assert budget.can_afford(20)
        budget.charge(assumed=20)
    assert budget.spent == 200
    assert not budget.can_afford(20)
    assert budget.stop and "ceiling" in budget.stopped_reason


def test_a_call_is_billed_at_what_the_api_says_it_cost():
    class _R:
        headers = {"x-requests-last": "40"}
    budget, _ = _plan(100)
    budget.charge(_R(), assumed=20)
    assert budget.spent == 40                          # not the assumed 20

    class _NoHeader:
        headers: dict = {}
    budget.charge(_NoHeader(), assumed=20)
    assert budget.spent == 60                          # falls back, never free


# ── the floor ────────────────────────────────────────────────────────────────

def test_the_floor_is_days_of_measured_burn_not_a_number_someone_picked():
    budget, problems = _plan(18_662, reserve_days=7)
    assert budget.burn_per_day == 120_000
    assert budget.floor == 840_000
    assert not problems


def test_a_run_that_would_starve_the_platform_is_refused_before_it_spends():
    """The check the old shape never had: remaining MINUS the plan has to clear
    the reserve. The old floor sat below the landing point, so it could not."""
    budget, problems = plan_credit_budget(
        _Conn([(f"2026-09-{d:02d}", 120_000 * i)
               for i, d in enumerate(range(1, 8), start=1)],
              remaining=1_000_000),
        shard_calls=18_662, total_calls=18_662, credits_per_call=20,
        reserve_days=7)
    assert problems and "under the" in problems[0]
    assert budget.runway_days() < 7


def test_the_floor_fires_on_whoever_drains_the_account():
    budget, _ = _plan(18_662, reserve_days=7)
    assert budget.check_remaining(900_000)
    assert not budget.check_remaining(839_999)
    assert budget.stop and "reserve" in budget.stopped_reason


def test_a_missing_quota_header_does_not_stop_a_run():
    """No header is not evidence of trouble; the ceiling still bounds it."""
    budget, _ = _plan(18_662)
    assert budget.check_remaining(None)
    assert budget.check_remaining("")
    assert not budget.stop


def test_no_burn_rate_on_record_refuses_rather_than_inventing_one():
    budget, problems = plan_credit_budget(
        _Conn([("2026-09-10", 10)], remaining=3_000_000),
        shard_calls=10, total_calls=10, credits_per_call=20)
    assert any("no measured burn rate" in p for p in problems)
    assert budget.floor == 0


def test_no_quota_reading_on_record_refuses_too():
    _, problems = plan_credit_budget(
        _Conn([(f"2026-09-{d:02d}", 120_000 * i)
               for i, d in enumerate(range(1, 8), start=1)]),
        shard_calls=10, total_calls=10, credits_per_call=20)
    assert any("no x-requests-remaining" in p for p in problems)


# ── the ingestor wiring ──────────────────────────────────────────────────────

_WINDOWS = [(f"2025-09-{d:02d}", None, None) for d in range(1, 21)]


def test_shard_parsing_and_splitting_is_round_robin_and_total():
    assert ing.parse_shard("0/4") == (0, 4)
    seen = []
    for i in range(4):
        mine = ing.shard_windows(_WINDOWS, f"{i}/4")
        seen.extend(mine)
    assert sorted(seen) == sorted(_WINDOWS)            # every day, exactly once


def test_a_bad_shard_spec_is_refused():
    for spec in ("0/0", "4/4", "-1/4", "x/4", "1"):
        with pytest.raises(ValueError):
            ing.parse_shard(spec)


def test_each_shard_is_budgeted_for_its_OWN_work():
    """The old refuse-to-start check measured the SEASON's plan against one
    shard's ceiling, which is why the ceiling had to be inflated past the
    season total for anything to start."""
    budgets = [
        ing.budget_for(_burn_conn(), _WINDOWS, f"{i}/4", ("h2h", "totals"),
                       calls_per_day=lambda w: 100)[0]
        for i in range(4)
    ]
    # 20 slate days / 4 shards = 5 days each, 100 calls a day, 20 credits a call
    assert [b.shard_planned for b in budgets] == [10_000] * 4
    assert all(b.ceiling == b.shard_planned for b in budgets)
    assert sum(b.ceiling for b in budgets) == budgets[0].total_planned == 40_000
