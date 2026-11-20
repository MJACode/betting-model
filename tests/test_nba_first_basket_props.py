"""The NBA first-basket markets are fetched and stored (2026-11-20).

The feed serves them Yes-only with no `point` (Hard Rock adds a No row), the shape the
parser drops unless the market defaults its line to 0.5. Without that default every row
is discarded and the market looks unsold, which is how `player_anytime_td` first read.
The outcome shapes below are copied from a bought snapshot (DET v PHX, 2026-01-15).
"""
import config
from data.ingestors import prop_odds_ingestor as poi

MARKETS = ("player_first_basket", "player_first_team_basket")


def _rows(book_markets, market):
    return poi._parse_prop_markets(book_markets, "NBA_2026-01-15_PHX_DET", "2026-01-15", "open",
                                   "2026-01-15T22:56:00+00:00", allowed_markets={market},
                                   bookmaker="draftkings")


def test_both_markets_are_fetched_for_nba():
    for m in MARKETS:
        assert m in config.PROP_MARKETS_NBA
        assert m in poi.PROP_MARKETS_BY_SPORT["NBA"]   # the list the response is filtered on


def test_yes_only_quote_is_kept_at_half_a_point():
    mk = [{"key": "player_first_basket", "last_update": "2026-01-15T22:55:56Z", "outcomes": [
        {"name": "Yes", "description": "Cade Cunningham", "price": 559},
        {"name": "Yes", "description": "Mark Williams", "price": 650},
    ]}]
    rows = _rows(mk, "player_first_basket")
    assert sorted(r["player_name"] for r in rows) == ["Cade Cunningham", "Mark Williams"]
    for r in rows:
        assert r["line"] == 0.5 and r["under_price"] is None
    assert {r["player_name"]: r["over_price"] for r in rows}["Cade Cunningham"] == 559


def test_yes_and_no_quote_lands_on_one_row():
    mk = [{"key": "player_first_team_basket", "outcomes": [
        {"name": "Yes", "description": "Duncan Robinson", "price": 1000},
        {"name": "No", "description": "Duncan Robinson", "price": -2500},
    ]}]
    rows = _rows(mk, "player_first_team_basket")
    assert len(rows) == 1
    assert (rows[0]["over_price"], rows[0]["under_price"], rows[0]["line"]) == (1000, -2500, 0.5)
