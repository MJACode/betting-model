"""Pins for the 2026-09-14 nfl_prop_market remeasure.

The measurement is in docs/nfl_prop_market_2026.md. These tests exist so a
later session cannot silently: move the 6/5 side floors, widen or tighten
the 24h ceiling off a still-thin sample, or start grading Kalshi through
the historical two-sharps path that has no Kalshi settlements.
"""
from __future__ import annotations

from pathlib import Path

import config
import scripts.nfl_prop_two_sharps as ts

REPO = Path(__file__).resolve().parent.parent


def test_the_2026_remeasure_did_not_move_the_side_floors():
    """docs/nfl_prop_market_2026.md: 15 settled BETs, over curve not monotone.

    A later edit that 'just tightens overs a bit more' is re-fitting 6 off
    a 4-bet cell. The under keeps the pre-committed 5pp.
    """
    side = config.NFL_PROP_MARKET_SIDE_EDGE
    assert side["under"] == 0.05
    assert side["over"] == 0.06
    assert config.ACTION_THRESHOLDS["nfl_prop_market"]["min_edge"] == 0.05


def test_the_2026_remeasure_did_not_move_the_24h_ceiling():
    """Last-four-hours still the weakest populated 2026 band; 36+ worse.

    Tightening to 12h would keep that weak band. Widening to 36h adds a
    band that is negative on the games that were graded in-band.
    """
    assert config.NFL_PROP_MAX_LEAD_HOURS == 24


def test_season_of_reads_the_game_id_token():
    assert ts.season_of("NFL_2026_01_NE_SEA") == "2026"
    assert ts.season_of("NFL_2025_18_KC_BUF") == "2025"
    assert ts.season_of("broken") == "?"


def test_hourly_lead_buckets_cover_the_24h_ceiling_and_the_saturday_band():
    assert ts.LEAD_HOURLY[0] == (0.0, 1.0)
    assert ts.LEAD_HOURLY[23] == (23.0, 24.0)
    assert ts.LEAD_HOURLY[-1] == (24.0, 48.0)
    assert len(ts.LEAD_HOURLY) == 25


def test_the_historical_grader_does_not_read_kalshi():
    """Kalshi is a live reference. It is not a settled book.

    kalshi_prop_ladders has no outcome column. Putting it on this path
    would grade a mid against a future that does not exist yet.
    """
    src = (REPO / "scripts" / "nfl_prop_two_sharps.py").read_text(encoding="utf-8")
    assert ts.REF_A == "pinnacle" and ts.REF_B == "betonlineag"
    assert "kalshi_prop_ingestor" not in src
    assert "from_kalshi" not in src
    # The comment that says why must stay, so a deletion of the guard
    # cannot hide behind a rename. Case-insensitive on purpose.
    assert "kalshi" in src.lower()
