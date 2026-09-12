"""
Odds API credit-quota telemetry.

The Odds API returns `x-requests-used` / `x-requests-remaining` headers on
every response. Both odds ingestors logged them at DEBUG and threw them away —
which is why the 2026-08-14 quota exhaustion (odds feed dead for 2.5 days, no
MLB/WNBA picks) was only diagnosable after the fact. This module persists the
latest observation into `odds_api_quota` (one row per UTC day, last write
wins), so:

  * the daily health check can WARN while credits are running low, BEFORE the
    feed dies (`odds_api_credits` in tracking/system_health.py)
  * the daily burn rate is answerable from Supabase directly
    ("how fast am I spending credits?" = day-over-day diff of requests_used)

Semantics: LAST observation per day, not peak/floor. A mid-day credit top-up
(or a billing-period reset) is reflected immediately instead of the day's
pre-top-up floor generating false warnings for the rest of the day.

Usage: call `record_quota_headers(resp)` right after any Odds API
`requests.get` (headers are present even on 401/429 error responses, so a
quota-dead key still updates the table), then `persist_quota(conn)` once per
ingest run. Both swallow all errors — telemetry must never break an ingest.
"""

from datetime import datetime, timezone

from loguru import logger

# Latest observation seen by this process (updated per response, written once
# per ingest run). Module-level on purpose: the fetch helpers don't carry a DB
# connection, the run_* entrypoints do.
_LATEST: dict | None = None


def record_quota_headers(resp) -> None:
    """Capture x-requests-used / x-requests-remaining off an Odds API response."""
    global _LATEST
    try:
        used      = resp.headers.get("x-requests-used")
        remaining = resp.headers.get("x-requests-remaining")
        if used in (None, "") and remaining in (None, ""):
            return
        _LATEST = {
            "used":        float(used) if used not in (None, "") else None,
            "remaining":   float(remaining) if remaining not in (None, "") else None,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception:
        # Never let telemetry interfere with the fetch path.
        pass


def persist_quota(conn) -> None:
    """Upsert the latest observation into odds_api_quota (one row per UTC day).

    Commits on its own so it works from a `finally:` block even after the
    caller's transaction rolled back. All failures are swallowed (DEBUG log).
    """
    if _LATEST is None:
        return
    try:
        day = _LATEST["observed_at"][:10]
        conn.execute("""
            INSERT INTO odds_api_quota (quota_date, requests_used, requests_remaining, observed_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (quota_date) DO UPDATE SET
                requests_used      = EXCLUDED.requests_used,
                requests_remaining = EXCLUDED.requests_remaining,
                observed_at        = EXCLUDED.observed_at
        """, (day, _LATEST["used"], _LATEST["remaining"], _LATEST["observed_at"]))
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.debug(f"odds_api_quota persist skipped: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Credit budgets for PAID backfills
# ─────────────────────────────────────────────────────────────────────────────
#
# WHY THIS IS HERE AND NOT IN EACH INGESTOR. On 2026-09-11 the NCAAF in-play
# backfill shipped with two hand-picked guards -- `--max-credits 400_000` and
# `--floor 2_000_000` -- and they were reported to mike as though they bounded
# the run. Neither did:
#
#   * the budget was built inside main(), so it was PER PROCESS. Four shards
#     were launched, which is four independent 400,000 ceilings: 1,600,000.
#   * the refuse-to-start check compared the WHOLE season's plan against ONE
#     shard's ceiling, so the ceiling had to sit above the season total for any
#     shard to start at all. 400,000 was chosen because the plan came out at
#     373,240 -- the guard was fitted to let the job through, which is
#     backwards.
#   * the floor sat BELOW where the run was expected to land (2,490,486 at the
#     start, minus 373,240, is ~2,117,000), so it could never fire on a normal
#     run. The MLB backfill's 2,600,000 was picked against that day's quota and
#     was a real brake; copying the shape without the reasoning lost that.
#
# The rule that follows, and the reason this lives in the shared module:
# A CREDIT GUARD IS DERIVED FROM A MEASUREMENT OR IT IS DECORATION. Both halves
# below come from numbers the system already knows -- the run's own printed
# plan, and the burn rate in `odds_api_quota` -- so neither can be quietly
# tuned to fit the job it is supposed to bound. The one judgement left is
# `reserve_days`, which is NAMED, exposed as a flag, and multiplied by a
# measured burn rate rather than standing in for one.
#
# CLAUDE.md section 1b: the ceiling on SPEND is mike's to set. This helper does
# not decide what may be spent. It makes a run cost no more than the number it
# put in front of him, and refuse to start if that number would starve the
# platform.

import statistics
from dataclasses import dataclass, field

# Fewer day-over-day observations than this is not a burn rate, it is an
# anecdote -- `daily_burn` returns None instead, and the caller then REFUSES
# rather than defaulting to a number nobody measured.
MIN_BURN_OBSERVATIONS = 3
# Days of normal operation the account must keep after a backfill. A judgement
# call, deliberately small, and the only one in this module -- it is multiplied
# by the MEASURED burn rate, so it scales with what the platform actually costs
# instead of standing in for it.
DEFAULT_RESERVE_DAYS = 7
BURN_LOOKBACK_DAYS = 14


def daily_burn(conn, lookback_days: int = BURN_LOOKBACK_DAYS):
    """MEDIAN credits/day actually spent, from `odds_api_quota`.

    MEDIAN, not mean: a paid backfill day (2026-09-08 burned 838,907 against a
    ~120k baseline) drags a mean into claiming the platform needs six times
    what it needs, and a reserve built on that refuses every future backfill.
    The median rides the ordinary days.

    A NEGATIVE day-over-day diff is a billing-period reset or a top-up, not a
    refund, and is dropped (2026-09-01 reads -676,908). Returns None when
    fewer than MIN_BURN_OBSERVATIONS usable days exist -- "I do not know" is an
    answer; a made-up burn rate is not.
    """
    try:
        rows = conn.execute("""
            SELECT quota_date, MAX(CAST(requests_used AS DOUBLE PRECISION))
            FROM odds_api_quota
            WHERE requests_used IS NOT NULL
            GROUP BY quota_date
            ORDER BY quota_date DESC
            LIMIT %s
        """, (lookback_days + 1,)).fetchall()
    except Exception as exc:                                   # noqa: BLE001
        logger.debug(f"daily_burn unavailable: {exc}")
        return None
    used = [float(r[1]) for r in reversed(rows) if r[1] is not None]
    diffs = [b - a for a, b in zip(used, used[1:]) if b - a > 0]
    if len(diffs) < MIN_BURN_OBSERVATIONS:
        return None
    return int(statistics.median(diffs))


def latest_remaining(conn):
    """The newest `x-requests-remaining` the system has on record."""
    try:
        row = conn.execute("""
            SELECT requests_remaining FROM odds_api_quota
            WHERE requests_remaining IS NOT NULL
            ORDER BY observed_at DESC LIMIT 1
        """).fetchone()
    except Exception as exc:                                   # noqa: BLE001
        logger.debug(f"latest_remaining unavailable: {exc}")
        return None
    return None if row is None or row[0] is None else int(float(row[0]))


@dataclass
class CreditBudget:
    """What ONE process of a paid backfill may spend, and when to stop.

    `ceiling` is this SHARD's share of the run's plan, so N shards sum to the
    plan rather than multiplying it. `floor` is the account reserve: the level
    below which the rest of the platform starts to starve, so it fires on
    whoever is draining the account, this pull or anything else.

    KNOWN LIMIT, stated rather than papered over. The ceiling bounds ONE
    PROCESS's spend and starts at zero, so it does not know what an earlier,
    interrupted run of the same pull already spent: restart a pull that is
    half done and its ceiling is the whole plan again. What actually keeps a
    resumed run honest is the resume itself -- already-stored snapshots are
    skipped, so the work left shrinks even though the ceiling does not. The
    ceiling is an upper bound on a process, NOT an accounting of a job across
    restarts. The `floor` is the guard that does span restarts, because it is
    read off the account rather than off this process.
    """
    ceiling: int
    floor: int
    shard_planned: int
    total_planned: int
    remaining_at_start: object
    burn_per_day: object
    reserve_days: int
    spent: int = 0
    stopped_reason: object = None

    @property
    def stop(self) -> bool:
        return self.stopped_reason is not None

    def can_afford(self, cost: int) -> bool:
        """False (and latches `stop`) when one more call breaches the ceiling."""
        if self.spent + cost > self.ceiling:
            self.stopped_reason = (
                f"ceiling {self.ceiling:,} reached (spent {self.spent:,}, "
                f"next call {cost:,})")
            return False
        return True

    def charge(self, resp=None, *, assumed: int) -> None:
        """Bill this call at what the API SAYS it cost.

        `x-requests-last` is the authority; `assumed` is the fallback when the
        header is absent or unparseable, so a missing header over-counts
        against our own ceiling rather than spending unbilled.
        """
        last = None
        if resp is not None:
            try:
                last = resp.headers.get("x-requests-last")
            except Exception:                                  # noqa: BLE001
                last = None
        try:
            self.spent += int(last)
        except (TypeError, ValueError):
            self.spent += assumed

    def check_remaining(self, remaining) -> bool:
        """False (and latches `stop`) when the ACCOUNT is under the reserve.

        An absent or unparseable header is not evidence of trouble and does not
        stop the run -- the ceiling still bounds it.
        """
        try:
            left = int(float(remaining))
        except (TypeError, ValueError):
            return True
        if self.floor and left < self.floor:
            self.stopped_reason = (
                f"quota {left:,} under the {self.floor:,} reserve "
                f"({self.reserve_days} days at {self.burn_per_day:,}/day)")
            return False
        return True

    def runway_days(self, after_pull: bool = True):
        """Days of operation left at the measured burn, optionally after this
        pull has spent its whole plan."""
        if not self.burn_per_day or self.remaining_at_start is None:
            return None
        left = self.remaining_at_start - (self.total_planned if after_pull else 0)
        return left / self.burn_per_day

    def describe(self) -> str:
        def _n(v):
            return "unknown" if v is None else f"{v:,}"
        lines = [
            f"  quota remaining now : {_n(self.remaining_at_start)}",
            f"  this run plans      : {self.total_planned:,} credits "
            f"({self.shard_planned:,} for this shard)",
            f"  measured burn       : {_n(self.burn_per_day)} credits/day "
            f"(median over {BURN_LOOKBACK_DAYS}d of odds_api_quota)",
            f"  reserve floor       : {_n(self.floor)} "
            f"= {self.reserve_days} days of that burn",
            f"  shard ceiling       : {self.ceiling:,} "
            f"(N shards sum to the plan, they do not multiply it)",
        ]
        runway = self.runway_days()
        if runway is not None:
            lines.append(f"  runway after this   : {runway:.1f} days at the "
                         f"measured burn")
        return "\n".join(lines)


def plan_credit_budget(conn, *, shard_calls: int, total_calls: int,
                       credits_per_call: int, max_credits=None,
                       reserve_days: int = DEFAULT_RESERVE_DAYS,
                       burn_per_day=None, remaining=None):
    """Build this process's budget, and every reason it must not start.

    `max_credits` is the budget for the WHOLE pull across every shard, not for
    one process -- it is split in proportion to this shard's share of the work.
    Left None it defaults to the run's own printed plan, which is the point:
    the default ceiling IS the number the operator approved, so it cannot be
    raised to fit a job without someone typing the larger number themselves.

    Returns (budget, problems). A non-empty `problems` means REFUSE; the caller
    prints them and exits rather than deciding for itself.
    """
    total_planned = total_calls * credits_per_call
    shard_planned = shard_calls * credits_per_call
    if max_credits is None:
        ceiling = shard_planned
    else:
        share = (shard_calls / total_calls) if total_calls else 0.0
        ceiling = int(round(max_credits * share))

    burn = burn_per_day if burn_per_day is not None else daily_burn(conn)
    left = remaining if remaining is not None else latest_remaining(conn)
    floor = burn * reserve_days if burn else 0

    problems = []
    if burn is None:
        problems.append(
            f"no measured burn rate in odds_api_quota (need "
            f"{MIN_BURN_OBSERVATIONS} usable days) - cannot size a reserve; "
            f"pass --burn-per-day to state it explicitly")
    if left is None:
        problems.append(
            "no x-requests-remaining on record in odds_api_quota - cannot "
            "tell what is left; pass --remaining to state it explicitly")
    if burn is not None and left is not None and left - total_planned < floor:
        problems.append(
            f"this run would leave {left - total_planned:,} credits, under the "
            f"{floor:,} reserve ({reserve_days} days at {burn:,}/day). "
            f"Lower --reserve-days, shrink the pull, or top up the plan.")
    if ceiling <= 0 and shard_calls > 0:
        problems.append("computed a zero ceiling for a shard that has work to do")

    return CreditBudget(
        ceiling=ceiling, floor=floor, shard_planned=shard_planned,
        total_planned=total_planned, remaining_at_start=left,
        burn_per_day=burn, reserve_days=reserve_days), problems
