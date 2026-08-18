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
