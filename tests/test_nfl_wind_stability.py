"""The live wind check does not lock on the first 11 mph reading.

The threshold is unchanged. On a live poll the number it compares is the
minimum kickoff-hour forecast over a covered 12-hour window. One issued
forecast — the replay path, which omits `wind_reads` — is still compared
directly, because that is the population the probability table was built on.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

NFL_ROOT = Path(__file__).resolve().parents[1] / "nfl"
ROOT = Path(__file__).resolve().parents[1]
GAME = "2026_01_CLE_JAX"


@pytest.fixture(scope="module")
def wind():
    sys.path.insert(0, str(NFL_ROOT))
    try:
        from _nfl_models import load_nfl_model
        yield load_nfl_model("wind_totals")
    finally:
        if str(NFL_ROOT) in sys.path:
            sys.path.remove(str(NFL_ROOT))


def _slate(forecast_wind: float = 14.0, lead_days: float = 2.0) -> pd.DataFrame:
    kick = pd.Timestamp.now("UTC") + pd.Timedelta(days=lead_days)
    return pd.DataFrame([{
        "game_id": GAME, "matchup": "CLE @ JAX",
        "kick_utc": kick.isoformat(), "stadium_id": "JAX00", "roof": "outdoors",
        "lead_days": lead_days, "forecast_wind": forecast_wind, "exp_true_wind": 13.0,
        "best_book": "draftkings", "best_total": 40.5,
        "best_under_px": -105, "best_over_px": -105,
    }])


def _series(*hours_ago_mph, now=None) -> dict:
    now = pd.Timestamp("2026-10-11 16:00", tz="UTC") if now is None else now
    return {GAME: [(now - pd.Timedelta(hours=h), mph) for h, mph in hours_ago_mph]}


def test_constants_are_the_twelve_hour_window(wind):
    assert wind.STABLE_SPAN_HOURS == 12.0
    assert wind.STABLE_LOOKBACK_HOURS == 13.0
    assert wind.STABLE_MIN_READS == 3
    assert wind.MAX_FIRE_LEAD == 4.0


def test_one_reading_is_not_a_covered_window(wind):
    now = pd.Timestamp("2026-10-11 16:00", tz="UTC")
    assert wind.ruling_wind([(now, 16.0)], now=now) is None


def test_two_readings_twelve_hours_apart_are_not_enough(wind):
    reads = _series((0, 14.0), (12, 14.0))
    assert wind.ruling_wind(reads[GAME]) is None


def test_three_readings_spanning_twelve_hours_return_the_minimum(wind):
    reads = _series((0, 14.0), (6, 12.4), (12, 15.0))
    assert wind.ruling_wind(reads[GAME]) == 12.4


def test_a_dip_inside_the_window_is_the_number_the_check_sees(wind):
    reads = _series((0, 14.0), (4, 10.4), (12, 15.0))
    assert wind.ruling_wind(reads[GAME]) == 10.4


def test_a_dip_older_than_the_lookback_does_not_count(wind):
    reads = _series((0, 14.0), (6, 13.0), (12, 12.5), (20, 8.0))
    assert wind.ruling_wind(reads[GAME]) == 12.5


def test_a_single_issued_forecast_still_fires(wind):
    """Replay and calibration pass one number and no `wind_reads`."""
    bets = wind.select_bets(_slate(14.0))
    assert len(bets) == 1
    assert bets.iloc[0].forecast_wind == 14.0


def test_the_first_live_reading_does_not_fire(wind):
    now = pd.Timestamp("2026-10-11 16:00", tz="UTC")
    reads = {GAME: [(now, 16.0)]}
    assert wind.select_bets(_slate(16.0), wind_reads=reads).empty
    row = wind.evaluate_board(_slate(16.0), wind_reads=reads)[0]
    assert row["qualifies"] == "0"
    assert "not stable yet" in row["reason"]
    from scripts.nfl_pick_monitor import classify
    _, status, _ = classify({"qualifies": row["qualifies"], "reason": row["reason"]})
    assert status != "GONE", row["reason"]


def test_a_covered_window_at_or_above_11_fires_and_records_the_minimum(wind):
    reads = _series((0, 14.0), (6, 12.4), (12, 15.0))
    bets = wind.select_bets(_slate(14.0), wind_reads=reads)
    assert len(bets) == 1
    assert bets.iloc[0].forecast_wind == 12.4
    row = wind.evaluate_board(_slate(14.0), wind_reads=reads)[0]
    assert row["qualifies"] == "1"
    assert "12.4" in row["reason"]


def test_a_covered_window_whose_minimum_is_under_11_does_not_fire(wind):
    reads = _series((0, 14.0), (4, 10.4), (12, 15.0))
    assert wind.select_bets(_slate(14.0), wind_reads=reads).empty
    row = wind.evaluate_board(_slate(14.0), wind_reads=reads)[0]
    assert row["qualifies"] == "0"
    assert "below the 11 mph threshold" in row["reason"]
    assert "10.4" in row["reason"]


def test_the_card_and_the_board_agree_on_a_live_series(wind):
    for reads in (
        {GAME: []},
        _series((0, 16.0)),
        _series((0, 14.0), (6, 12.0), (12, 13.0)),
        _series((0, 14.0), (6, 9.0), (12, 13.0)),
    ):
        slate = _slate(14.0)
        fired = not wind.select_bets(slate, wind_reads=reads).empty
        row = wind.evaluate_board(slate, wind_reads=reads)[0]
        assert bool(int(row["qualifies"])) == fired, row["reason"]


def test_an_empty_read_dict_locks_nothing(wind):
    """The live card always passes a dict. Empty means there is no history."""
    assert wind.select_bets(_slate(14.0), wind_reads={}).empty


def test_the_live_card_passes_the_series_and_the_replay_does_not(wind):
    card = (NFL_ROOT / "scripts" / "weekly_wind_card.py").read_text(encoding="utf-8")
    assert "attach_live_wind_reads" in card
    assert "wind_reads=wind_reads" in card
    replay = (NFL_ROOT / "scripts" / "replay_wind_card.py").read_text(encoding="utf-8")
    assert "wind_reads" not in replay


def test_the_read_store_is_not_a_pick_ledger():
    src = (NFL_ROOT / "data_ingest" / "kickoff_wind_reads.py").read_text(encoding="utf-8")
    assert "INSERT INTO nfl_kickoff_wind_reads" in src or "INSERT INTO {TABLE}" in src
    assert "signal_type" not in src
    assert "would_have" not in src
    assert "INSERT INTO picks" not in src
    sql = (ROOT / "data" / "migrations" / "add_nfl_kickoff_wind_reads.sql").read_text(
        encoding="utf-8")
    assert "to_regclass('public.nfl_kickoff_wind_reads') IS NULL" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql and "REVOKE ALL" in sql
    from data import view_migrations
    assert "add_nfl_kickoff_wind_reads.sql" in view_migrations.ACTIVE_MIGRATIONS


def test_a_database_miss_returns_only_the_current_reading(wind, monkeypatch):
    import data_ingest.kickoff_wind_reads as reads

    def _boom():
        raise RuntimeError("no database")

    monkeypatch.setattr(reads, "_connect", _boom)
    now = pd.Timestamp("2026-10-11 16:00", tz="UTC")
    out = reads.attach_live_wind_reads(_slate(14.2), now=now)
    assert list(out) == [GAME]
    assert len(out[GAME]) == 1
    assert out[GAME][0][1] == 14.2
    assert wind.ruling_wind(out[GAME], now=now) is None
