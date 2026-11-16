"""What reaches the ops channel, and what waits for the 7:15 digest."""
from datetime import datetime, timedelta, timezone

from tracking.system_health import (
    CREDIT_PAGE_REMAINING,
    CREDIT_PAGE_RUNWAY_DAYS,
    classify_missing_finals,
    credit_should_page,
)
from tracking.watch_util import alert_state_path, read_alert_state, write_alert_state

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def test_credits_page_on_runway_or_the_absolute_floor():
    assert credit_should_page(40_000, None) is True
    assert credit_should_page(CREDIT_PAGE_REMAINING - 1, 1_000) is True
    # 1.86M left, ~576k/day: about 3 days. That day pages.
    assert credit_should_page(1_863_957, 576_440) is True
    # 1.6M left, ~18k/day: months of runway. Percent-of-plan must not page.
    assert credit_should_page(1_596_688, 17_731) is False
    assert credit_should_page(1_596_688, None) is False
    assert CREDIT_PAGE_RUNWAY_DAYS == 5
    assert CREDIT_PAGE_REMAINING == 50_000


def test_ufc_finals_are_not_an_outage():
    rows = [("UFC", "2026-11-14", "2026-11-14T23:00:00+00:00")] * 11
    status, _sev, detail = classify_missing_finals(rows, NOW)
    assert status == "OK"
    assert "UFC" in detail


def test_a_college_final_past_36_hours_pages():
    old = (NOW - timedelta(hours=40)).isoformat()
    status, sev, detail = classify_missing_finals(
        [("NCAAB", "2026-11-14", old)], NOW)
    assert status == "STALE" and sev == "CRIT"
    assert "NCAAB" in detail


def test_a_college_final_inside_36_hours_is_a_digest_line():
    recent = (NOW - timedelta(hours=10)).isoformat()
    status, sev, _detail = classify_missing_finals(
        [("NBA", "2026-11-16", recent)], NOW)
    assert status == "STALE" and sev == "WARN"


def test_two_worker_owned_finals_past_36_hours_page():
    old = (NOW - timedelta(hours=40)).isoformat()
    rows = [("NHL", "2026-11-14", old), ("NHL", "2026-11-14", old)]
    status, sev, _detail = classify_missing_finals(rows, NOW)
    assert status == "STALE" and sev == "CRIT"


def test_one_worker_owned_final_is_a_postponement():
    old = (NOW - timedelta(hours=40)).isoformat()
    status, sev, _detail = classify_missing_finals(
        [("MLB", "2026-11-14", old)], NOW)
    assert status == "STALE" and sev == "WARN"


def test_alert_state_lives_on_the_railway_volume(monkeypatch, tmp_path):
    """A redeploy wipes container disk. The stamp has to be on the volume."""
    monkeypatch.delenv("WATCHDOG_STATE_DIR", raising=False)
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(tmp_path))
    write_alert_state("failure_alerter_state.json",
                      {"health:odds_dk_lines": {"armed": True, "paged": True}})
    path = alert_state_path("failure_alerter_state.json")
    assert path.parent == tmp_path
    assert read_alert_state("failure_alerter_state.json")[
        "health:odds_dk_lines"]["paged"] is True
