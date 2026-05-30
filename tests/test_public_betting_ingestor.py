"""
Unit tests for the Action Network public betting parser.

Pure-function tests — no network, no DB. They exercise the JSON parsing path
against a synthetic scoreboard payload shaped like Action Network's v2
scoreboard response (games[] → markets[bookId].event → moneyline/spread/total
arrays with bet_info.tickets.percent and bet_info.money.percent).
"""

from data.ingestors.public_betting_ingestor import (
    _pct,
    _select_book,
    parse_public_betting,
)

SNAPSHOT = "2026-05-30T11:00:00-04:00"


def _make_game():
    """A single Yankees @ Red Sox game with full splits under book id 15."""
    return {
        "id": 123456,
        "start_time": "2026-05-30T23:05:00Z",
        "home_team_id": 1,
        "away_team_id": 2,
        "teams": [
            {"id": 1, "full_name": "Boston Red Sox", "abbr": "BOS"},
            {"id": 2, "full_name": "New York Yankees", "abbr": "NYY"},
        ],
        "markets": {
            "15": {
                "event": {
                    "moneyline": [
                        {"side": "home",
                         "bet_info": {"tickets": {"percent": 40, "value": 4000},
                                      "money": {"percent": 55, "value": 550000}}},
                        {"side": "away",
                         "bet_info": {"tickets": {"percent": 60, "value": 6000},
                                      "money": {"percent": 45, "value": 450000}}},
                    ],
                    "spread": [
                        {"side": "home",
                         "bet_info": {"tickets": {"percent": 52}, "money": {"percent": 61}}},
                        {"side": "away",
                         "bet_info": {"tickets": {"percent": 48}, "money": {"percent": 39}}},
                    ],
                    "total": [
                        {"side": "over",
                         "bet_info": {"tickets": {"percent": 70}, "money": {"percent": 66}}},
                        {"side": "under",
                         "bet_info": {"tickets": {"percent": 30}, "money": {"percent": 34}}},
                    ],
                }
            }
        },
    }


# ── _pct ──────────────────────────────────────────────────────────────────────

def test_pct_integer_scale():
    assert _pct({"tickets": {"percent": 65}}, "tickets") == 65.0


def test_pct_fractional_scaled_to_100():
    assert _pct({"money": {"percent": 0.83}}, "money") == 83.0


def test_pct_missing_returns_none():
    assert _pct({"tickets": {"value": 100}}, "tickets") is None
    assert _pct({}, "money") is None
    assert _pct(None, "tickets") is None


# ── _select_book ──────────────────────────────────────────────────────────────

def test_select_book_prefers_configured_id():
    markets = _make_game()["markets"]
    period = _select_book(markets, ["15"])
    assert period is not None
    assert "moneyline" in period


def test_select_book_falls_back_to_any_book():
    markets = {"999": {"event": {"total": [{"side": "over", "bet_info": {}}]}}}
    period = _select_book(markets, ["15"])  # 15 absent → fall back to 999
    assert period is not None and "total" in period


def test_select_book_handles_top_level_markets():
    # Some payloads omit the "event" wrapper and put arrays at the top level.
    markets = {"15": {"moneyline": [{"side": "home", "bet_info": {}}]}}
    period = _select_book(markets, ["15"])
    assert period is not None and "moneyline" in period


def test_select_book_empty_returns_none():
    assert _select_book({}, ["15"]) is None
    assert _select_book(None, ["15"]) is None


# ── parse_public_betting ──────────────────────────────────────────────────────

def test_parse_emits_six_rows():
    rows = parse_public_betting(_make_game(), ["15"], SNAPSHOT)
    # 3 markets × 2 sides
    assert len(rows) == 6
    markets = {r["market"] for r in rows}
    assert markets == {"h2h", "spreads", "totals"}


def test_parse_game_id_and_sides():
    rows = parse_public_betting(_make_game(), ["15"], SNAPSHOT)
    by_key = {(r["market"], r["side"]): r for r in rows}
    # game_id built as MLB_{date}_{away}_{home}; start_time 23:05Z → still 5/30 ET
    assert rows[0]["game_id"] == "MLB_2026-05-30_NYY_BOS"
    assert by_key[("h2h", "home")]["public_bet_pct"] == 40.0
    assert by_key[("h2h", "home")]["public_money_pct"] == 55.0
    assert by_key[("totals", "over")]["public_bet_pct"] == 70.0
    assert by_key[("totals", "under")]["public_money_pct"] == 34.0


def test_parse_marks_source_and_snapshot():
    rows = parse_public_betting(_make_game(), ["15"], SNAPSHOT)
    assert all(r["source"] == "action_network" for r in rows)
    assert all(r["snapshot_at"] == SNAPSHOT for r in rows)
    assert all(r["book"] == "consensus" for r in rows)


def test_parse_skips_entries_without_any_percent():
    game = _make_game()
    game["markets"]["15"]["event"]["moneyline"] = [
        {"side": "home", "bet_info": {"tickets": {"value": 10}}},  # no percent
        {"side": "away", "bet_info": {"tickets": {"percent": 60}}},
    ]
    rows = parse_public_betting(game, ["15"], SNAPSHOT)
    ml = [r for r in rows if r["market"] == "h2h"]
    assert len(ml) == 1 and ml[0]["side"] == "away"


def test_parse_missing_teams_returns_empty():
    game = _make_game()
    game["teams"] = []
    assert parse_public_betting(game, ["15"], SNAPSHOT) == []


def test_parse_no_markets_returns_empty():
    game = _make_game()
    game["markets"] = {}
    assert parse_public_betting(game, ["15"], SNAPSHOT) == []
