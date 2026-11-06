"""Copy the mobile app's Sentry events into Supabase (`sentry_events`).

Matt, 2026-11-06: add Sentry to the app, and keep everything in Supabase
(CLAUDE.md §1b: "EVERYTHING GOES IN SUPABASE"). Sentry sees what the app's own
`app_errors` cannot -- native crashes and iOS app hangs -- but stores them on
its own servers. This job makes Supabase the system of record and Sentry a
second copy: every event is written here, keyed on Sentry's event id, so a
re-run inserts nothing already stored.

API (read from Sentry's published OpenAPI schema, getsentry/sentry-api-schema,
2026-11-06 -- docs.sentry.io does not resolve from the dev sandbox):
  GET {SENTRY_URL}/api/0/projects/{org}/{project}/events/?full=true&statsPeriod=..
  Authorization: Bearer <token with project:read>
  Each event: id, eventID, groupID, title, message, dateCreated, platform,
  culprit, location, "event.type", tags=[{key, value}], metadata, crashFile.
  Newest first; the next page is in the Link header (rel="next";
  results="true"; cursor="...").

Needs SENTRY_AUTH_TOKEN, SENTRY_ORG, SENTRY_PROJECT on the worker. Without
them it reports "not configured" and writes nothing -- it never raises, so a
missing key cannot take a scheduler tick down with it.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Callable, Iterable

log = logging.getLogger(__name__)

DEFAULT_URL = "https://sentry.io"
# First run, or after an outage: how far back to read.
LOOKBACK = "14d"
MAX_PAGES = 20
# One request, then the whole tick. The job runs at minutes 7, 22, 37, 52.
# A dead socket must end well before the next of those, or max_instances=1
# spends the following tick skipping a copy that is still hung.
CONNECT_TIMEOUT_S = 5
READ_TIMEOUT_S = 10
TICK_BUDGET_S = 45

_INSERT = """
INSERT INTO sentry_events (
    event_id, issue_id, occurred_at, event_type, level, title, message,
    culprit, platform, device_id, screen, release, environment, update_id,
    raw
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
ON CONFLICT (event_id) DO NOTHING
"""

_KNOWN = "SELECT event_id FROM sentry_events WHERE event_id = ANY(%s)"


def config_from_env(env: dict[str, str] | None = None) -> dict[str, str] | None:
    env = os.environ if env is None else env
    token = (env.get("SENTRY_AUTH_TOKEN") or "").strip()
    org = (env.get("SENTRY_ORG") or "").strip()
    project = (env.get("SENTRY_PROJECT") or "").strip()
    if not (token and org and project):
        return None
    url = (env.get("SENTRY_URL") or DEFAULT_URL).strip().rstrip("/")
    return {"token": token, "org": org, "project": project, "url": url}


def next_cursor(link_header: str | None) -> str | None:
    """The cursor of the rel="next" link, or None when there is no next page."""
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' not in part:
            continue
        if 'results="false"' in part:
            return None
        m = re.search(r'cursor="([^"]+)"', part)
        return m.group(1) if m else None
    return None


def _tags(event: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for t in event.get("tags") or []:
        if isinstance(t, dict) and "key" in t:
            out[str(t["key"])] = "" if t.get("value") is None else str(t["value"])
    return out


def row_for(event: dict[str, Any]) -> tuple:
    """One INSERT row. Pure."""
    tags = _tags(event)
    event_id = event.get("eventID") or event.get("id")
    return (
        event_id,
        event.get("groupID"),
        event.get("dateCreated"),
        event.get("event.type"),
        tags.get("level"),
        (event.get("title") or "")[:500],
        (event.get("message") or "")[:2000],
        (event.get("culprit") or "")[:500],
        event.get("platform"),
        tags.get("device_id"),
        tags.get("screen"),
        tags.get("release"),
        tags.get("environment"),
        tags.get("update_id"),
        json.dumps(event, default=str),
    )


def fetch_pages(cfg: dict[str, str], get: Callable[..., Any], *, lookback: str = LOOKBACK,
                max_pages: int = MAX_PAGES, clock: Callable[[], float] | None = None,
                budget_s: float = TICK_BUDGET_S) -> Iterable[list[dict[str, Any]]]:
    """Yield pages of events, newest first. Stops when the tick budget is used."""
    tick = clock or time.monotonic
    deadline = tick() + budget_s
    path = f"{cfg['url']}/api/0/projects/{cfg['org']}/{cfg['project']}/events/"
    headers = {"Authorization": f"Bearer {cfg['token']}"}
    cursor: str | None = None
    for _ in range(max_pages):
        now = tick()
        if now >= deadline:
            log.warning("sentry_events: stopped, tick budget of %ss used", budget_s)
            return
        params = {"full": "true", "statsPeriod": lookback}
        if cursor:
            params["cursor"] = cursor
        resp = get(path, headers=headers, params=params,
                   timeout=(CONNECT_TIMEOUT_S, min(READ_TIMEOUT_S, deadline - now)))
        if resp.status_code != 200:
            raise RuntimeError(f"Sentry events API returned {resp.status_code}: {resp.text[:300]}")
        page = resp.json()
        if not isinstance(page, list):
            raise RuntimeError(f"Sentry events API returned {type(page).__name__}, not a list")
        yield page
        cursor = next_cursor(resp.headers.get("Link"))
        if not cursor or not page:
            return


def sync_sentry_events(conn=None, *, get: Callable[..., Any] | None = None,
                       env: dict[str, str] | None = None,
                       clock: Callable[[], float] | None = None,
                       budget_s: float = TICK_BUDGET_S) -> dict[str, Any]:
    """Copy new Sentry events into sentry_events. Returns a summary dict.

    Stops paging at the first page whose events are all already stored: the
    API is newest first, so everything after it was copied by an earlier run.
    """
    cfg = config_from_env(env)
    if cfg is None:
        return {"status": "not_configured", "inserted": 0, "seen": 0}
    if get is None:
        import requests
        get = requests.get
    own = conn is None
    if own:
        from data.db import get_connection
        conn = get_connection()
    inserted = seen = 0
    try:
        for page in fetch_pages(cfg, get, clock=clock, budget_s=budget_s):
            rows = [row_for(e) for e in page if isinstance(e, dict)]
            rows = [r for r in rows if r[0]]
            seen += len(rows)
            if not rows:
                break
            ids = [r[0] for r in rows]
            known = {r[0] for r in conn.execute(_KNOWN, (ids,)).fetchall()}
            new = [r for r in rows if r[0] not in known]
            for r in new:
                conn.execute(_INSERT, r)
            conn.commit()
            inserted += len(new)
            if not new:
                break
    finally:
        if own:
            conn.close()
    log.info("sentry_events: %d new of %d seen", inserted, seen)
    return {"status": "ok", "inserted": inserted, "seen": seen}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(sync_sentry_events())
