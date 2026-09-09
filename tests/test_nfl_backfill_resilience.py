"""A paid backfill must survive a dropped connection and must be resumable.

BOTH FAILURES HAPPENED, on 2026-09-08, in that order. The alternate-line
backfill died 53 dates into the 2024 season on a single
`requests.exceptions.ReadTimeout` -- forty minutes and 243,770 rows in. Then
re-running the range would have silently RE-BOUGHT all 53 completed dates at
341 credits each, because the NFL backfill had no resume.

The identical pair of fixes already existed in data/ingestors/prop_odds_ingestor,
written earlier the SAME DAY for the MLB backfill after the identical timeout,
and neither was carried across. That is what CLAUDE.md §1b's cross-model rule
exists to catch, so these tests are named for the behaviour rather than for NFL.
"""
from __future__ import annotations

import requests

from data.ingestors import nfl_prop_odds_ingestor as ing


def test_a_dropped_connection_is_retried(monkeypatch):
    calls = {"n": 0}

    class _OK:
        status_code = 200
        headers: dict = {}
        def json(self): return {}

    def _flaky(url, params=None, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.exceptions.ReadTimeout("boom")
        return _OK()

    monkeypatch.setattr(ing.requests, "get", _flaky)
    monkeypatch.setattr(ing.time, "sleep", lambda *_a: None)
    monkeypatch.setattr(ing, "record_quota_headers", lambda *_a, **_k: None)

    resp = ing._get("http://x", {})
    assert resp is not None, "a transient timeout must not end the run"
    assert calls["n"] == 3


def test_it_gives_up_rather_than_looping_forever(monkeypatch):
    def _always(url, params=None, timeout=None):
        raise requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(ing.requests, "get", _always)
    monkeypatch.setattr(ing.time, "sleep", lambda *_a: None)
    assert ing._get("http://x", {}) is None


def test_an_http_error_is_NOT_retried(monkeypatch):
    """A non-200 is an ANSWER -- rate limit, no coverage at that snapshot --
    and retrying it spends credits to be told the same thing again."""
    calls = {"n": 0}

    class _Err:
        status_code = 422
        headers: dict = {}
        def json(self): return {}

    def _err(url, params=None, timeout=None):
        calls["n"] += 1
        return _Err()

    monkeypatch.setattr(ing.requests, "get", _err)
    monkeypatch.setattr(ing.time, "sleep", lambda *_a: None)
    monkeypatch.setattr(ing, "record_quota_headers", lambda *_a, **_k: None)

    resp = ing._get("http://x", {})
    assert resp is not None and resp.status_code == 422
    assert calls["n"] == 1, "an HTTP error must cost exactly one call"


def test_resume_probes_ONE_market_not_any_row():
    """The dates being resumed already hold STANDARD rows from an earlier
    backfill. A generic "any row for that date" check would report every date
    as done and skip the whole run -- failing by doing nothing."""
    import inspect

    src = inspect.getsource(ing.backfilled_dates)
    assert "market = %s" in src, (
        "the resume probe must name a market; an any-row check skips everything")


def test_resume_with_no_probe_market_skips_nothing():
    """Defaulting to 'skip everything' on a missing probe would silently turn a
    paid backfill into a no-op."""
    class _Conn:
        def execute(self, *a, **k):
            raise AssertionError("must not query without a probe market")

    assert ing.backfilled_dates(_Conn(), ["2024-09-05"], "open", "") == set()
    assert ing.backfilled_dates(_Conn(), [], "open", "x") == set()
