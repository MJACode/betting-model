"""The DK payload parser, pinned against the real shape.

Written from an actual response (2026-08-30), not from documentation -- DK
publishes none. Two details in here are the ones that bite: the American odds
carry a UNICODE minus, and a live market's two selections do not arrive in a
guaranteed order, so the quote key would otherwise be unstable and every poll
would look like a new line.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.dk_freshness_compare import _american, parse_dk_payload


def _payload(**over):
    """A minimal but structurally real league response: one live game and one
    that has not started."""
    body = {
        "events": [
            {"id": "34586029", "name": "BAL Orioles @ Athletics",
             "status": "STARTED",
             "liveGameState": {"period": "3rd"}},
            {"id": "34586030", "name": "NYY Yankees @ BOS Red Sox",
             "status": "NOT_STARTED"},
        ],
        "markets": [
            {"id": "3_86074929", "eventId": "34586029", "name": "Total",
             "main": True},
            {"id": "3_86074930", "eventId": "34586029", "name": "Moneyline",
             "main": True},
            {"id": "3_86074931", "eventId": "34586030", "name": "Total",
             "main": True},
        ],
        "selections": [
            # Under listed FIRST on purpose -- payload order is not guaranteed.
            {"marketId": "3_86074929", "label": "Under 8.5", "points": 8.5,
             "outcomeType": "Under", "decimal": 1.7634,
             "displayOdds": {"american": "−131"}},
            {"marketId": "3_86074929", "label": "Over 8.5", "points": 8.5,
             "outcomeType": "Over", "decimal": 2.01,
             "displayOdds": {"american": "+101"}},
            {"marketId": "3_86074930", "label": "Athletics",
             "outcomeType": "Home", "decimal": 1.5,
             "displayOdds": {"american": "−200"}},
            {"marketId": "3_86074930", "label": "BAL Orioles",
             "outcomeType": "Away", "decimal": 2.6,
             "displayOdds": {"american": "+160"}},
            {"marketId": "3_86074931", "label": "Over 9", "points": 9.0,
             "outcomeType": "Over", "decimal": 1.91,
             "displayOdds": {"american": "−110"}},
            {"marketId": "3_86074931", "label": "Under 9", "points": 9.0,
             "outcomeType": "Under", "decimal": 1.91,
             "displayOdds": {"american": "−110"}},
        ],
    }
    body.update(over)
    return body


def test_unicode_minus_is_parsed_not_crashed():
    assert _american({"displayOdds": {"american": "−131"}}) == -131
    assert _american({"displayOdds": {"american": "+101"}}) == 101


def test_decimal_is_the_fallback_when_the_display_string_is_unusable():
    # A missing or non-numeric display string must not lose the price.
    assert _american({"displayOdds": {"american": "EVEN"}, "decimal": 2.0}) == 100
    assert _american({"decimal": 1.5}) == -200
    assert _american({}) is None
    # decimal 1.0 is not a price; refuse rather than emit a divide-by-zero.
    assert _american({"decimal": 1.0}) is None


def test_live_markets_only():
    rows = parse_dk_payload(_payload(), "MLB")
    names = {r["event_name"] for r in rows}
    assert names == {"BAL Orioles @ Athletics"}, \
        "a NOT_STARTED event must not be collected -- the question is in-play"


def test_totals_row_is_over_first_regardless_of_payload_order():
    rows = parse_dk_payload(_payload(), "MLB")
    tot = [r for r in rows if r["market"] == "totals"][0]
    assert tot["line"] == 8.5
    assert tot["side_a"] == "Over 8.5" and tot["price_a"] == 101
    assert tot["side_b"] == "Under 8.5" and tot["price_b"] == -131
    assert tot["period"] == "3rd"


def test_quote_key_is_stable_across_polls_and_moves_with_the_line():
    a = parse_dk_payload(_payload(), "MLB")
    b = parse_dk_payload(_payload(), "MLB")
    assert [r["quote_key"] for r in a] == [r["quote_key"] for r in b], \
        "an unchanged line must not read as a new quote -- that IS the metric"

    moved = _payload()
    for s in moved["selections"]:
        if s["marketId"] == "3_86074929":
            s["points"] = 9.5
    c = parse_dk_payload(moved, "MLB")
    keys_before = {r["quote_key"] for r in a}
    assert not ({r["quote_key"] for r in c if r["market"] == "totals"}
                & keys_before), "a moved line must be a new quote"


def test_moneyline_maps_and_orders_home_first():
    rows = parse_dk_payload(_payload(), "MLB")
    ml = [r for r in rows if r["market"] == "h2h"][0]
    assert ml["side_a"] == "Athletics" and ml["price_a"] == -200
    assert ml["side_b"] == "BAL Orioles" and ml["price_b"] == 160
    assert ml["line"] is None


def test_non_main_and_unknown_markets_are_skipped():
    p = _payload()
    p["markets"].append({"id": "x", "eventId": "34586029",
                         "name": "Total", "main": False})
    p["markets"].append({"id": "y", "eventId": "34586029",
                         "name": "First Inning Total", "main": True})
    p["selections"] += [
        {"marketId": "y", "label": "Over 0.5", "points": 0.5,
         "outcomeType": "Over", "decimal": 1.9},
        {"marketId": "y", "label": "Under 0.5", "points": 0.5,
         "outcomeType": "Under", "decimal": 1.9},
    ]
    rows = parse_dk_payload(p, "MLB")
    assert len(rows) == 2, "only the two main, mapped markets survive"


def test_a_half_priced_market_is_dropped_rather_than_half_recorded():
    p = _payload()
    p["selections"] = [s for s in p["selections"]
                       if not (s["marketId"] == "3_86074929"
                               and s["outcomeType"] == "Over")]
    rows = parse_dk_payload(p, "MLB")
    assert all(r["market"] != "totals" for r in rows)


def test_an_event_with_no_markets_yields_nothing_rather_than_raising():
    assert parse_dk_payload({"events": [], "markets": [], "selections": []},
                            "MLB") == []
    assert parse_dk_payload({}, "MLB") == []
