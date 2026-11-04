"""A 0% same-book close is a CLV push. It is not a loss.

Beat rate = beats / (beats + losses). The average still includes the zero.
"""
from decimal import Decimal
from pathlib import Path

import pytest

from tracking.clv_math import (
    CLV_PCT_PUSH_EPS,
    clv_beat_counts,
    clv_beat_rate,
    clv_outcome,
    same_book_clv,
)
from tracking.discord_notifier import _tally, clv_line, snapshot_rows

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "data" / "migrations" / "clv_push_beat_rate_2026_11_04.sql"


def _row(clv, live=False):
    return ("NCAAB", "ncaab_spread", "WIN", 0.02, -110, clv, live)


def test_the_stored_percent_grain_is_a_push_and_a_hundredth_is_not():
    assert clv_outcome(None) is None
    assert clv_outcome(float("nan")) is None
    assert clv_outcome(0) == "push"
    assert clv_outcome(0.0) == "push"
    assert clv_outcome(-0.0) == "push"
    assert clv_outcome(Decimal("0.00")) == "push"
    assert clv_outcome(1e-12) == "push"
    assert clv_outcome(0.004) == "push"
    assert clv_outcome(-0.004) == "push"
    assert clv_outcome(CLV_PCT_PUSH_EPS) == "beat"
    assert clv_outcome(-CLV_PCT_PUSH_EPS) == "loss"
    assert clv_outcome(0.01) == "beat"
    assert clv_outcome(-0.01) == "loss"


def test_equal_american_prices_are_a_push():
    pct, pp = same_book_clv(-160, -160)
    assert pct == 0.0
    assert pp == 0.0
    assert clv_outcome(pct) == "push"


def test_a_push_is_out_of_the_denominator_and_a_loss_is_in_it():
    rows = [_row(1.5), _row(-2.0), *[_row(0.0) for _ in range(7)]]
    t = _tally(rows)
    assert (t["clv_beat"], t["clv_n"], t["clv_push"]) == (1, 2, 7)
    assert clv_line(t) == "50% beat close (1/2, 7 push)"
    assert " · 50% beat close (1/2, 7 push)" in __import__(
        "tracking.discord_notifier", fromlist=["_tally_line"]
    )._tally_line(t, with_clv=True)


def test_one_beat_and_seven_pushes_reads_one_of_one():
    """Nov 3 NCAAB shape: one real beat, seven closes that matched."""
    t = _tally([_row(4.2), *[_row(0.0) for _ in range(7)]])
    assert (t["clv_beat"], t["clv_n"], t["clv_push"]) == (1, 1, 7)
    assert clv_line(t) == "100% beat close (1/1, 7 push)"


def test_zero_pushes_omit_the_push_clause():
    t = _tally([_row(1.0), _row(-1.0)])
    assert t["clv_push"] == 0
    assert clv_line(t) == "50% beat close (1/2)"


def test_an_all_push_day_does_not_divide():
    t = _tally([_row(0.0) for _ in range(7)])
    assert t["clv_n"] == 0 and t["clv_beat"] == 0 and t["clv_push"] == 7
    assert clv_line(t) == "0 measured, 7 push"
    stored = snapshot_rows(
        "2026-11-03", "ts", t, {"NCAAB": [_row(0.0)]}, t, {"NCAAB": [_row(0.0)]},
        7, 7,
    )
    assert all(row[12] is None for row in stored)
    assert all(row[10] == 0 and row[11] == 0 for row in stored)


def test_nothing_measured_stays_blank():
    t = _tally([_row(None)])
    assert clv_line(t) == ""


def test_in_play_and_a_missing_close_stay_out():
    t = _tally([
        _row(1.5),
        _row(0.0),
        _row(None),
        _row(9.9, live=True),
        _row(0.0, live=True),
    ])
    assert (t["clv_beat"], t["clv_n"], t["clv_push"]) == (1, 1, 1)
    assert clv_line(t) == "100% beat close (1/1, 1 push)"


def test_the_rate_helper_matches_the_recap():
    values = [1.5, -2.0, 0.0, 0.0, None, float("nan")]
    assert clv_beat_counts(values) == (1, 1, 2)
    assert clv_beat_rate(values) == pytest.approx(0.5)
    assert clv_beat_rate([0.0, 0.0]) is None


def test_model_quality_keeps_zero_in_the_mean_only():
    from tracking.model_quality import detect_clv_degradation
    recent = (
        [{"clv_method": "standard_v2", "clv_pct": 2.0, "clv_beat_close": True}] * 10
        + [{"clv_method": "standard_v2", "clv_pct": -2.0, "clv_beat_close": False}] * 10
        + [{"clv_method": "standard_v2", "clv_pct": 0.0, "clv_beat_close": False}] * 10
    )
    finding = detect_clv_degradation(recent, recent, min_n=15)
    assert finding["metrics"]["recent_n"] == 30
    assert finding["metrics"]["recent_mean_clv_pp"] == pytest.approx(0.0)
    assert finding["metrics"]["recent_beat_rate"] == pytest.approx(0.5)


def test_an_all_push_quality_window_does_not_divide():
    from tracking.model_quality import detect_clv_degradation
    rows = [{"clv_method": "standard_v2", "clv_pct": 0.0, "clv_beat_close": False}] * 20
    finding = detect_clv_degradation(rows, rows, min_n=15)
    assert finding["metrics"]["recent_beat_rate"] is None
    assert finding["metrics"]["recent_mean_clv_pp"] == pytest.approx(0.0)
    assert "n/a" in finding["detail"]


def test_the_migration_skips_and_does_not_lock_picks():
    from data.db import _adapt_sql
    from data.view_migrations import ACTIVE_MIGRATIONS
    text = MIG.read_text(encoding="utf-8")
    assert "AS clv_push" in text
    assert "abs(clv_pct) < 0.005" in text
    assert "to_regclass('public.v_opening_vs_live')" in text
    assert "CREATE OR REPLACE VIEW" in text
    assert "ALTER TABLE " not in text
    assert "UPDATE public.picks" not in text
    assert "UPDATE public.results_snapshots" not in text
    assert "pg_get_function_identity_arguments" not in text
    # _adapt_sql strips surrounding whitespace. The body itself must not change.
    assert _adapt_sql(text) == text.strip()
    assert MIG.name in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS.index(MIG.name) < ACTIVE_MIGRATIONS.index(
        "published_pick_units_2026_10_17.sql")
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"
