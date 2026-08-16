"""
Tests for the NFL wind-card publisher's pure transforms (session 119).

The publisher mirrors the standalone nfl/ package's weekly wind card into the
platform's games + picks tables. These tests cover the card-row parsing — the
DB writes are plain inserts exercised in production.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.nfl_wind_publisher import (
    BOOK_ABBREV,
    NFL_WIND_MODEL_ID,
    build_rows,
    kick_fields,
    parse_matchup,
)


def _card_row(**over):
    row = {
        "game_id": "2026_02_NYJ_MIA",
        "matchup": "NYJ @ MIA",
        "kick_utc": "2026-09-20 17:00:00+00:00",
        "stadium_id": "MIA00",
        "lead_days": "3.1",
        "forecast_wind": "14.2",
        "exp_true_wind": "12.1",
        "total_line": "43.5",
        "book": "fanduel",
        "price": "-105",
        "model_prob": "0.5671",
        "market_prob": "0.5122",
        "edge": "0.0549",
        "stake_pct": "1.0",
        "ev_pct": "5.9",
        "stake_units": "100.0",
    }
    row.update(over)
    return row


class TestParseMatchup:
    def test_standard(self):
        assert parse_matchup("NYJ @ MIA") == ("NYJ", "MIA")

    def test_garbage_raises(self):
        import pytest
        with pytest.raises(ValueError):
            parse_matchup("NYJ vs MIA")


class TestKickFields:
    def test_afternoon_game_same_et_date(self):
        game_date, commence = kick_fields("2026-09-20 17:00:00+00:00")
        assert game_date == "2026-09-20"          # 1pm ET
        assert commence == "2026-09-20T17:00:00+00:00"

    def test_snf_utc_rollover_stays_on_et_date(self):
        # 8:20pm ET Sunday kickoff is 00:20 UTC Monday — must stay on Sunday's board.
        game_date, commence = kick_fields("2026-09-21 00:20:00+00:00")
        assert game_date == "2026-09-20"
        assert commence == "2026-09-21T00:20:00+00:00"


class TestBuildRows:
    def test_maps_card_row_to_game_and_pick(self):
        games, picks = build_rows([_card_row()], bankroll=1000.0)
        assert len(games) == 1 and len(picks) == 1
        g, p = games[0], picks[0]
        assert g["game_id"] == "NFL_2026_02_NYJ_MIA"
        assert g["sport"] == "NFL" and g["season"] == 2026
        assert (g["away_team"], g["home_team"]) == ("NYJ", "MIA")
        assert p["game_id"] == g["game_id"]
        assert p["model_id"] == NFL_WIND_MODEL_ID
        assert p["pick_side"] == "under"
        assert p["signal_type"] == "BET"
        assert p["scored_line"] == 43.5
        assert p["dk_odds"] == -105.0
        assert p["model_probability"] == 0.5671
        assert p["dk_implied_prob"] == 0.5122
        assert p["edge"] == 0.0549
        assert p["kelly_fraction"] == 0.01           # stake_pct 1.0 -> 1%
        assert p["recommended_bet"] == 10.0          # 1% of 1000
        assert p["bankroll_at_pick"] == 1000.0

    def test_label_names_line_wind_and_book(self):
        _, picks = build_rows([_card_row()], bankroll=1000.0)
        assert picks[0]["pick_label"] == "NYJ @ MIA Under 43.5 (Wind 14 mph, FD)"

    def test_integer_line_renders_without_decimal(self):
        _, picks = build_rows([_card_row(total_line="44.0")], bankroll=1000.0)
        assert "Under 44 (" in picks[0]["pick_label"]

    def test_unknown_book_falls_back_to_raw_key(self):
        _, picks = build_rows([_card_row(book="somefuturebook")], bankroll=1000.0)
        assert "somefuturebook" in picks[0]["pick_label"]

    def test_bad_row_skipped_not_fatal(self):
        rows = [_card_row(matchup="garbage"), _card_row()]
        games, picks = build_rows(rows, bankroll=1000.0)
        assert len(games) == 1 and len(picks) == 1

    def test_known_book_abbrevs(self):
        assert BOOK_ABBREV["draftkings"] == "DK"
        assert BOOK_ABBREV["williamhill_us"] == "CZR"
