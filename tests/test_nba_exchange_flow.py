"""data/ingestors/nba_exchange_flow: which team a trade's money went to, and when.

The test the import exists for (does exchange money before tip say anything the
sportsbook close does not?) is only as good as the sign of each trade. These pin it:
a Kalshi NO on one team's market is money on the other team, a Polymarket SELL of an
outcome is money on the other outcome, and nothing at or after the listed start is kept.
"""
from datetime import datetime, timedelta, timezone

from data.ingestors import nba_exchange_flow as f

OURS = {"UTA", "LAC", "GSW", "MEM", "NOP", "WAS", "POR", "PHI", "TOR", "LAL"}
TIP = datetime(2026, 1, 2, 3, 0, tzinfo=timezone.utc)


def test_kalshi_event_ticker_gives_the_date_and_the_codes():
    assert f.kalshi_event("KXNBAGAME-26JAN01UTALAC") == ("2026-01-01", "UTALAC")
    assert f.kalshi_event("KXNBAGAME-25APR15MEMGSW") == ("2025-04-15", "MEMGSW")
    assert f.kalshi_event("KXNBASPREAD-26JAN01UTALAC") is None
    assert f.kalshi_event("KXNBAGAME-26XXX01UTALAC") is None


def test_an_alternate_code_is_used_only_when_it_lands_on_one_of_ours():
    assert f.our_code("GSW", OURS) == "GSW"
    assert f.our_code("GS", OURS) == "GSW"
    assert f.our_code("NO", OURS) == "NOP"
    assert f.our_code("XYZ", OURS) is None


def test_polymarket_outcome_names_map_to_our_codes():
    nick = f.nickname_map()
    assert f.team_for_outcome("Pelicans", nick) == "NOP"
    assert f.team_for_outcome("Trail Blazers", nick) == "POR"
    assert f.team_for_outcome("76ers", nick) == "PHI"
    assert f.team_for_outcome("Clippers", nick) == "LAC"


def test_a_kalshi_no_is_money_on_the_other_team_at_the_other_price():
    yes = {"taker_side": "yes", "yes_price_dollars": "0.6200", "count_fp": "10.00",
           "created_time": "2026-01-02T01:00:00Z"}
    no = {**yes, "taker_side": "no"}
    assert f.kalshi_leg(yes, "LAC", "UTA")[:3] == ("LAC", 0.62, 10.0)
    assert f.kalshi_leg(no, "LAC", "UTA")[:3] == ("UTA", 0.38, 10.0)


def test_a_polymarket_sell_is_money_on_the_other_outcome():
    buy = {"side": "BUY", "price": 0.7, "size": 100, "timestamp": int(TIP.timestamp()) - 600}
    sell = {**buy, "side": "SELL"}
    assert f.poly_leg(buy, "NOP", "WAS")[:3] == ("NOP", 0.7, 100.0)
    assert f.poly_leg(sell, "NOP", "WAS")[:3] == ("WAS", 0.3, 100.0)


def test_buckets_keep_only_trades_before_the_listed_start():
    legs = [("LAC", 0.60, 10.0, TIP - timedelta(minutes=31)),
            ("LAC", 0.62, 30.0, TIP - timedelta(minutes=29)),
            ("UTA", 0.40, 5.0, TIP - timedelta(minutes=20)),
            ("LAC", 0.65, 99.0, TIP),                                   # at the start: not pre-game
            ("UTA", 0.30, 50.0, TIP + timedelta(minutes=5))]
    rows = f.bucket_rows("kalshi", "G", TIP, legs, ("LAC", "UTA"))
    by = {(r["team"], r["minutes_to_tip"]): r for r in rows}
    assert sum(r["buy_contracts"] for r in rows) == 45.0
    # 02:29 falls in the 02:15 bucket (45 min out), 02:31 and 02:40 in the 02:30 bucket (30 out)
    assert by[("LAC", 45)]["buy_contracts"] == 10.0
    assert by[("LAC", 30)]["buy_contracts"] == 30.0 and by[("UTA", 30)]["buy_contracts"] == 5.0
    assert by[("LAC", 30)]["vwap"] == 0.62
    # the 02:30 bucket's last trade bought UTA at 0.40, so LAC's implied price is 0.60
    assert by[("UTA", 30)]["last_price"] == 0.40 and by[("LAC", 30)]["last_price"] == 0.60


def test_the_polymarket_slug_is_away_home_and_the_et_date():
    g = {"game_id": "NBA_2025-01-05_NOP_WAS", "home": "WAS", "away": "NOP"}
    assert f.poly_slug(g, "2025-01-05") == "nba-nop-was-2025-01-05"


def test_the_next_page_cursor_is_read_from_the_body_or_a_header():
    assert f.next_cursor({"data": [], "next_cursor": "abc"}, {}) == "abc"
    assert f.next_cursor({"data": [], "nextCursor": "xyz"}, {}) == "xyz"
    assert f.next_cursor({"data": []}, {"X-Next-Cursor": "h1"}) == "h1"
    assert f.next_cursor({"data": [], "next_cursor": "LTE="}, {}) is None
    assert f.next_cursor({"data": []}, {}) is None


def test_a_full_page_with_no_cursor_is_refused_not_kept(monkeypatch):
    import pytest

    class R:
        status_code = 200
        headers = {}

        def json(self):
            return {"data": [{"side": "BUY"}] * 500}
    monkeypatch.setattr(f, "_get", lambda pace, url, params: R())
    monkeypatch.setattr(f, "_POLY_TAKER_PARAM", [{}])
    with pytest.raises(RuntimeError):
        f.poly_trades(None, "0xabc")
