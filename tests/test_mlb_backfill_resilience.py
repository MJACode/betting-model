"""A long paid backfill must survive a dropped connection and never re-buy.

BOTH OF THESE COST A REAL RUN on 2026-09-06. The first version of
backfill_mlb_prop_odds had no retry and no resume:

  * a single `requests.exceptions.ReadTimeout` nineteen dates into the 2026
    season backfill raised straight out of the loop and ended the job; and
  * re-running the same range would have silently re-fetched -- and re-paid for
    -- every date already stored, because the table is append-only by design.

Together those turn one network hiccup into a repeat purchase. These tests pin
the two properties that stop it.
"""
from __future__ import annotations

import inspect

import pytest
import requests

import data.ingestors.prop_odds_ingestor as ing


def test_a_transient_network_error_is_retried(monkeypatch):
    calls = {"n": 0}

    def flaky(url, params=None, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.exceptions.ReadTimeout("boom")
        return "ok"

    monkeypatch.setattr(ing.requests, "get", flaky)
    monkeypatch.setattr(ing.time, "sleep", lambda _s: None)
    assert ing._get_with_retry("u", {}) == "ok"
    assert calls["n"] == 3


def test_it_gives_up_rather_than_looping_forever(monkeypatch):
    """None, not an exception — the caller turns that into a skipped event, so
    one unreachable board does not end the run either."""
    def always(url, params=None, timeout=None):
        raise requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(ing.requests, "get", always)
    monkeypatch.setattr(ing.time, "sleep", lambda _s: None)
    assert ing._get_with_retry("u", {}, attempts=3) is None


def test_an_http_error_is_NOT_retried(monkeypatch):
    """A non-200 is an ANSWER — rate limit, no coverage at that snapshot — and
    retrying it spends credits to be told the same thing again. Only the network
    layer is retried."""
    class _Resp:
        status_code = 429

    calls = {"n": 0}

    def once(url, params=None, timeout=None):
        calls["n"] += 1
        return _Resp()

    monkeypatch.setattr(ing.requests, "get", once)
    ing._get_with_retry("u", {})
    assert calls["n"] == 1


def test_a_failed_date_does_not_end_the_run_and_is_left_unmarked():
    """Source guard on the two halves of resumability: the per-date call is
    wrapped, and a failure rolls back so the date carries NO rows — which is
    what makes backfilled_dates a truthful marker rather than a half-truth."""
    src = inspect.getsource(ing.backfill_mlb_prop_odds)
    assert "except Exception as exc:" in src, src
    assert "conn.rollback()" in src, src
    assert "continue" in src, src
    # and the commit is per date, not once at the end
    assert src.index("conn.commit()") > src.index("_backfill_one_date"), src


def test_skip_existing_is_on_by_default():
    """The default has to be the safe one: an operator re-running a range after
    a crash is the exact moment nobody wants to think about a flag."""
    sig = inspect.signature(ing.backfill_mlb_prop_odds)
    assert sig.parameters["skip_existing"].default is True


def test_the_resume_marker_distinguishes_historical_from_live_rows():
    """It keys on the snapshot_at shape: the historical writer stamps the API's
    served timestamp ('...Z'), the live ingestor stamps ET with a numeric
    offset. This test exists to make that a stated contract — a future writer
    that stamps 'Z' on live rows would make a re-run skip dates it should buy."""
    src = inspect.getsource(ing.backfilled_dates)
    assert "LIKE '%%Z'" in src or "LIKE '%Z'" in src, src
    assert "bookmaker = %s" in src, src
