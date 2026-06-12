"""
Unit tests for DraftKings betslip deep-link extraction (The Odds API
includeLinks / includeSids).

Pure-function tests — no network, no DB. They confirm the odds parsers and the
player-prop parser carry each outcome's `link` (betslip deep link) and `sid`
(bookmaker selection id) through to the row that gets stored, and that a missing
link/sid resolves to None rather than raising.
"""

from data.ingestors.odds_ingestor import (
    _parse_outcomes,
    _parse_spread_outcomes,
    _parse_total_outcomes,
)
from data.ingestors.prop_odds_ingestor import _parse_prop_markets


def test_h2h_outcomes_carry_link_and_sid():
    out = _parse_outcomes(
        [
            {"name": "NYY", "price": -150, "link": "L_H", "sid": "S_H"},
            {"name": "BOS", "price": 130, "link": "L_A", "sid": "S_A"},
            {"name": "Draw", "price": 200, "link": "L_D", "sid": "S_D"},
        ],
        "MLB",
        "NYY",
    )
    assert out["home_link"] == "L_H" and out["home_sid"] == "S_H"
    assert out["away_link"] == "L_A" and out["away_sid"] == "S_A"
    assert out["draw_link"] == "L_D" and out["draw_sid"] == "S_D"


def test_h2h_missing_link_is_none():
    out = _parse_outcomes(
        [{"name": "NYY", "price": -150}, {"name": "BOS", "price": 130}],
        "MLB",
        "NYY",
    )
    assert out["home_link"] is None and out["home_sid"] is None
    assert out["away_link"] is None and out["away_sid"] is None


def test_spread_outcomes_carry_link_and_sid():
    out = _parse_spread_outcomes(
        [
            {"name": "NYY", "price": -110, "point": -1.5, "link": "SL_H", "sid": "SS_H"},
            {"name": "BOS", "price": -110, "point": 1.5, "link": "SL_A"},
        ],
        "NYY",
    )
    assert out["spread_home"] == -1.5
    assert out["home_link"] == "SL_H" and out["home_sid"] == "SS_H"
    assert out["away_link"] == "SL_A" and out["away_sid"] is None


def test_total_outcomes_carry_link_and_sid():
    out = _parse_total_outcomes(
        [
            {"name": "Over", "price": -105, "point": 8.5, "link": "OL", "sid": "OS"},
            {"name": "Under", "price": -115, "point": 8.5, "link": "UL", "sid": "US"},
        ]
    )
    assert out["total_line"] == 8.5
    assert out["over_link"] == "OL" and out["over_sid"] == "OS"
    assert out["under_link"] == "UL" and out["under_sid"] == "US"


def test_prop_over_under_carry_link_and_sid():
    markets = [
        {
            "key": "pitcher_strikeouts",
            "outcomes": [
                {"name": "Over", "description": "Gerrit Cole", "price": -130,
                 "point": 7.5, "link": "OVR", "sid": "OS"},
                {"name": "Under", "description": "Gerrit Cole", "price": 110,
                 "point": 7.5, "link": "UND", "sid": "US"},
            ],
        }
    ]
    rows = _parse_prop_markets(
        markets, "MLB_2026-06-10_BOS_NYY", "2026-06-10", "open", "t",
        allowed_markets={"pitcher_strikeouts"},
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["player_name"] == "Gerrit Cole"
    assert r["over_link"] == "OVR" and r["over_sid"] == "OS"
    assert r["under_link"] == "UND" and r["under_sid"] == "US"
