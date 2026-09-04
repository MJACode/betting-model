"""
The two published record views must agree, and must start at the live date.

WHY. On 2026-09-04 the Track Record screen published two different windows at
once: the hero card read v_public_track_record (2026-09-01 onward — 70 settled
MLB picks, 43-27, +12.02u) and the equity curve under it read
v_public_track_record_daily, which was still the pre-migration definition
gated at 2026-04-14 and ended at +64.1u. Both numbers were live to members and
nothing in the system flagged the contradiction.

tracking/system_health.py now runs this reconciliation every morning. The
comparison is factored out as a pure function so it can be tested on the actual
numbers that were in production on both sides of the fix.

Every case below was watched failing against a deliberately broken copy of
_published_record_problems (each docstring names what was broken).
"""
from __future__ import annotations

from tracking.system_health import _published_record_problems

LIVE = "2026-09-01"

# Production, measured 2026-09-04 BEFORE the fix. profit is profit_flat in
# cents, as both views store it; the third element is the earliest game_date.
BROKEN_REC = {
    "MLB":   (70, 1202.0, "2026-09-01"),
    "NCAAF": (6,   -31.0, "2026-09-03"),
    "UFC":   (0,     0.0, "2026-09-05"),
}
BROKEN_DAILY = {
    "MLB":   (1184, 6405.0, "2026-04-17"),
    "NCAAF": (10,    -64.0, "2026-08-29"),
    "UFC":   (21,   -129.0, "2026-06-20"),
    "WNBA":  (341,  1094.0, "2026-06-01"),
}

# The same two views, measured after the daily half was applied.
FIXED_REC = {
    "MLB":   (70, 1202.0, "2026-09-01"),
    "NCAAF": (6,   -31.0, "2026-09-03"),
    "UFC":   (0,     0.0, "2026-09-05"),
}
FIXED_DAILY = {
    "MLB":   (70, 1202.0, "2026-09-01"),
    "NCAAF": (6,   -31.0, "2026-09-03"),
}


def test_the_real_production_drift_is_caught():
    """The case that shipped. Broken copy: the reconciliation loop removed —
    the drift then goes unreported."""
    problems = _published_record_problems(BROKEN_REC, BROKEN_DAILY, LIVE)
    assert problems
    joined = " | ".join(problems)
    assert "v_public_track_record_daily publishes games before the live date" in joined
    assert "MLB" in joined and "1184 picks" in joined and "+64.05u" in joined


def test_the_fixed_production_numbers_reconcile():
    """The state the fix leaves behind — no problems, no false alarm from UFC's
    0-pick row, which the daily view's HAVING clause legitimately omits."""
    assert _published_record_problems(FIXED_REC, FIXED_DAILY, LIVE) == []


def test_a_sport_missing_from_the_daily_view_is_caught():
    """The equity curve silently dropping a sport the hero card counts. Broken
    copy: the `continue` replaced by a bare pass — the sport is then compared
    against a KeyError instead of reported."""
    rec = {"MLB": (70, 1202.0, LIVE)}
    problems = _published_record_problems(rec, {}, LIVE)
    assert problems == ["MLB: 70 settled pick(s) in the per-model view, "
                        "absent from the daily view"]


def test_same_picks_but_different_money_is_caught():
    """The subtler half: an equal pick count says nothing about the units. A
    broken copy comparing only picks passes this population and misses it."""
    rec = {"MLB": (70, 1202.0, LIVE)}
    daily = {"MLB": (70, 1533.0, LIVE)}
    problems = _published_record_problems(rec, daily, LIVE)
    assert problems == ["MLB: per-model 70 picks / +12.02u vs daily 70 picks / +15.33u"]


def test_a_pick_before_the_live_date_is_caught_in_either_view():
    """The window itself, checked on both sides — the per-model view drifting
    is just as publishable as the daily one."""
    early = {"MLB": (70, 1202.0, "2026-08-31")}
    assert any("v_public_track_record publishes games before the live date"
               in p for p in _published_record_problems(early, {"MLB": (70, 1202.0, LIVE)}, LIVE))
    assert any("v_public_track_record_daily publishes games before the live date"
               in p for p in _published_record_problems({"MLB": (70, 1202.0, LIVE)}, early, LIVE))


def test_an_empty_record_is_not_a_problem():
    """Day one of a new window holds no settled pick. That is reported by the
    health check as SKIPPED, never as a reconciliation failure."""
    assert _published_record_problems({}, {}, LIVE) == []


def test_cent_level_agreement_is_required():
    """One cent apart is still two different numbers on one screen."""
    rec = {"MLB": (70, 1202.0, LIVE)}
    assert _published_record_problems(rec, {"MLB": (70, 1202.01, LIVE)}, LIVE)
    assert _published_record_problems(rec, {"MLB": (70, 1202.0, LIVE)}, LIVE) == []
