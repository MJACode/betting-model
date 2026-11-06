"""Sentry -> Supabase copy (data/ingestors/sentry_events.py, 2026-11-06).

Matt: Sentry in the app, and everything in Supabase (CLAUDE.md §1b). The job
copies each Sentry event into sentry_events once, keyed on its event id. The
event shape is Sentry's published OpenAPI schema example
(getsentry/sentry-api-schema, read 2026-11-06), plus the tags the app sets.
"""

import json
from pathlib import Path

from data.ingestors.sentry_events import (
    CONNECT_TIMEOUT_S,
    READ_TIMEOUT_S,
    TICK_BUDGET_S,
    next_cursor,
    row_for,
    sync_sentry_events,
)

ROOT = Path(__file__).parent.parent
ENV = {"SENTRY_AUTH_TOKEN": "tok", "SENTRY_ORG": "org", "SENTRY_PROJECT": "app"}


def _event(eid, **tags):
    base = {"key": "level", "value": "fatal"}
    return {
        "eventID": eid, "id": "x" + eid, "groupID": "1889724436",
        "title": "App Hanging for at least 2000 ms.", "message": "",
        "dateCreated": "2026-11-06T17:46:36Z", "platform": "cocoa",
        "event.type": "error", "culprit": "", "location": None,
        "tags": [base] + [{"key": k, "value": v} for k, v in tags.items()],
        "metadata": {"type": "App Hanging"}, "crashFile": None, "user": None,
    }


class Resp:
    def __init__(self, body, link=None, status=200):
        self._body, self.status_code = body, status
        self.headers = {"Link": link} if link else {}
        self.text = json.dumps(body)

    def json(self):
        return self._body


def _link(cursor, more):
    return (f'<https://sentry.io/x/?cursor=prev>; rel="previous"; results="false"; cursor="prev", '
            f'<https://sentry.io/x/?cursor={cursor}>; rel="next"; results="{str(more).lower()}"; cursor="{cursor}"')


class FakeConn:
    def __init__(self, stored=()):
        self.stored = {e: None for e in stored}
        self.commits = 0

    def execute(self, sql, params):
        conn = self

        class Cur:
            def fetchall(self_inner):
                return [(e,) for e in params[0] if e in conn.stored]
        if sql.strip().startswith("SELECT"):
            return Cur()
        assert "ON CONFLICT (event_id) DO NOTHING" in sql
        self.stored[params[0]] = params
        return Cur()

    def commit(self):
        self.commits += 1

    def close(self):
        pass


def test_not_configured_writes_nothing_and_does_not_raise():
    called = []
    out = sync_sentry_events(FakeConn(), get=lambda *a, **k: called.append(1), env={})
    assert out == {"status": "not_configured", "inserted": 0, "seen": 0}
    assert called == []


def test_row_carries_the_app_tags():
    r = row_for(_event("e1", device_id="dev-12345678", screen="Settings", release="1.3.0"))
    assert r[0] == "e1" and r[1] == "1889724436" and r[3] == "error" and r[4] == "fatal"
    assert r[9] == "dev-12345678" and r[10] == "Settings" and r[11] == "1.3.0"
    assert json.loads(r[14])["metadata"]["type"] == "App Hanging"


def test_next_cursor_reads_the_next_link_only():
    assert next_cursor(_link("abc", True)) == "abc"
    assert next_cursor(_link("abc", False)) is None
    assert next_cursor(None) is None


def test_pages_until_a_page_is_all_known_and_never_duplicates():
    pages = {
        None: Resp([_event("e3"), _event("e2")], _link("c1", True)),
        "c1": Resp([_event("e1")], _link("c2", True)),
        "c2": Resp([_event("e0")], _link("c3", False)),
    }
    seen_cursors = []

    def get(url, headers, params, timeout):
        assert url == "https://sentry.io/api/0/projects/org/app/events/"
        assert headers == {"Authorization": "Bearer tok"}
        assert params["full"] == "true"
        assert timeout == (CONNECT_TIMEOUT_S, READ_TIMEOUT_S)
        seen_cursors.append(params.get("cursor"))
        return pages[params.get("cursor")]

    conn = FakeConn(stored=["e1", "e0"])
    out = sync_sentry_events(conn, get=get, env=ENV)
    assert out["inserted"] == 2
    assert set(conn.stored) == {"e0", "e1", "e2", "e3"}
    # e1's page was all known: no read of the page after it.
    assert seen_cursors == [None, "c1"]
    # A second run inserts nothing.
    assert sync_sentry_events(conn, get=get, env=ENV)["inserted"] == 0


def test_an_api_error_raises_for_the_scheduler_wrapper_to_log():
    import pytest
    with pytest.raises(RuntimeError, match="401"):
        sync_sentry_events(FakeConn(), get=lambda *a, **k: Resp({"detail": "bad"}, status=401), env=ENV)


def test_a_hung_sentry_cannot_outlive_the_tick():
    seen = []

    def get(url, headers, params, timeout):
        seen.append(timeout)
        return Resp([_event("e9")], _link("next", True))

    # deadline = 0 + 45. The second page is asked for at t=100, past the budget.
    times = iter([0.0, 0.0, 100.0])
    out = sync_sentry_events(
        FakeConn(), get=get, env=ENV, clock=lambda: next(times), budget_s=TICK_BUDGET_S,
    )
    assert out["inserted"] == 1
    assert seen == [(CONNECT_TIMEOUT_S, READ_TIMEOUT_S)]

    # Near the end of the budget the read timeout shrinks to what is left.
    seen.clear()

    def get_once(url, headers, params, timeout):
        seen.append(timeout)
        return Resp([], None)

    times = iter([0.0, 40.0])
    sync_sentry_events(
        FakeConn(), get=get_once, env=ENV, clock=lambda: next(times), budget_s=TICK_BUDGET_S,
    )
    assert seen == [(CONNECT_TIMEOUT_S, 5)]
    assert TICK_BUDGET_S < 15 * 60


def test_scheduler_runs_it_and_swallows_failures():
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    fn = src.split("def run_sentry_events_sync", 1)[1].split("\ndef ", 1)[0]
    assert "except Exception" in fn and "sync_sentry_events()" in fn
    assert 'id="sentry_events_sync"' in src
    # The name contains "(every 15 min)", so the job ends at the closing line, not the first ")".
    job = src.split('id="sentry_events_sync"', 1)[1].split("\n    )", 1)[0]
    assert "max_instances=1" in job and "coalesce=True" in job
    pipeline = src.split("_PIPELINE_JOBS = {", 1)[1].split("\n_POLLER_JOBS", 1)[0]
    assert '"sentry_events_sync"' in pipeline


def test_the_table_is_closed_to_the_app():
    sql = (ROOT / "data" / "migrations" / "add_sentry_events.sql").read_text(encoding="utf-8")
    assert "event_id     TEXT PRIMARY KEY" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON TABLE sentry_events FROM anon, authenticated" in sql
