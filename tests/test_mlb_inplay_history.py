"""The in-play history puller writes only in-progress DK totals, keyed on the
SERVED snapshot, with DK's last_update carried in the source marker that the
backtest reads back."""
from datetime import datetime, timezone

from data.ingestors.mlb_inplay_history import rows_for, planned_calls, STEP
from scripts.inplay_history_backtest import _lu

SERVED = datetime(2025, 6, 18, 1, 0, 37, tzinfo=timezone.utc)


def _event(commence, book="draftkings", markets=None):
    return {"commence_time": commence, "home_team": "Detroit Tigers",
            "away_team": "Pittsburgh Pirates",
            "bookmakers": [{"key": book, "markets": markets if markets is not None else [
                {"key": "totals", "last_update": "2025-06-18T00:59:46Z",
                 "outcomes": [{"name": "Over", "price": 1040, "point": 10.5},
                              {"name": "Under", "price": -4200, "point": 10.5}]}]}]}


def test_only_in_progress_dk_totals_are_written():
    events = [
        _event("2025-06-17T22:41:00Z"),                       # in progress
        _event("2025-06-18T01:05:00Z"),                       # not started yet
        _event("2025-06-17T22:41:00Z", book="fanduel"),       # not DK
        _event("2025-06-17T22:41:00Z", markets=[]),           # DK, no totals
    ]
    rows = rows_for(events, "2025-06-18T01:05:00Z", SERVED)
    assert len(rows) == 1
    r = rows[0]
    assert r["game_id"] == "MLB_2025-06-17_PIT_DET"
    assert r["snapshot_type"] == "in_play" and r["bookmaker"] == "draftkings"
    assert r["snapshot_at"] == "2025-06-18T01:00:37Z"        # served, not requested
    assert (r["total_line"], r["over_price"], r["under_price"]) == (10.5, 1040, -4200)
    assert r["source"] == ("historical_inplay|req=2025-06-18T01:05:00Z"
                           "|served=2025-06-18T01:00:37Z|lu=2025-06-18T00:59:46Z")
    assert _lu(r["source"]) == "2025-06-18T00:59:46Z"


def test_missing_last_update_reads_back_as_none():
    assert _lu("historical_inplay|req=x|served=y|lu=None") is None
    assert _lu(None) is None


def test_planned_calls_counts_every_five_minute_step_inclusive():
    lo = datetime(2025, 6, 17, 22, 35, tzinfo=timezone.utc)
    assert planned_calls([("2025-06-17", lo, lo + 3 * STEP)]) == 4


def test_event_missing_from_games_is_counted_not_written():
    skipped = {}
    rows = rows_for([_event("2025-06-17T22:41:00Z")], "2025-06-18T01:05:00Z", SERVED,
                    known_games={"MLB_2025-06-17_XXX_YYY"}, skipped=skipped)
    assert rows == []
    assert skipped == {"MLB_2025-06-17_PIT_DET": 1}
