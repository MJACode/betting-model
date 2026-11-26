"""NBA quarter and half lines before tip (data/ingestors/nba_period_lines_live.py, Matt 2026-11-26).

The feed exists for members asking the AI assistant. Real-money models decide on three of the same markets, so the
tests that matter most are the ones proving its rows cannot reach them: its own source, 'open' only, never a
model's source, never a close.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import data.ingestors.nba_period_lines_live as L

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 26, 17, 0, tzinfo=timezone.utc)
HOME, AWAY = "Portland Trail Blazers", "San Antonio Spurs"


def _o(name, price, point=None):
    d = {"name": name, "price": price}
    if point is not None:
        d["point"] = point
    return d


BODY = {
    "home_team": HOME, "away_team": AWAY,
    "bookmakers": [
        {"key": "draftkings", "last_update": "2026-11-26T16:58:00Z", "markets": [
            # Two numbers for one quarter: 2.5 is the even one, 3.5 the alternate.
            {"key": "spreads_q2", "last_update": "2026-11-26T16:57:00Z", "outcomes": [
                _o(HOME, -110, 2.5), _o(AWAY, -110, -2.5), _o(HOME, -135, 3.5), _o(AWAY, 105, -3.5)]},
            {"key": "totals_q1", "outcomes": [_o("Over", -115, 56.5), _o("Under", -105, 56.5)]},
            {"key": "h2h_q1", "outcomes": [_o(HOME, 140, None), _o(AWAY, -165, None)]},
            {"key": "spreads", "outcomes": [_o(HOME, -110, 3.5), _o(AWAY, -110, -3.5)]},   # not ours
        ]},
        {"key": "notabook", "markets": [
            {"key": "totals_q1", "outcomes": [_o("Over", -110, 50.5), _o("Under", -110, 50.5)]}]},
    ],
}


def test_rows_are_its_own_source_and_never_a_close():
    main, alt = L.event_rows(BODY, "NBA_2026-11-26_SAS_POR", NOW)
    for r in main + alt:
        assert r["source"] == L.SOURCE
        assert r["snapshot_type"] == "open"
        assert r["bookmaker"] in L.READ_BOOKS


def test_source_is_no_models_source():
    import data.ingestors.nba_first_half_odds as fh
    import models.nba_q1_trend as q1
    from scripts import nba_q1_trend_card as q1card
    assert L.SOURCE not in (q1.LIVE_SOURCE, q1.HISTORY_SOURCE, fh.SOURCE)
    assert L.SOURCE not in q1card.HISTORY_SOURCES


def test_spreads_keyed_on_home_number_and_main_is_closest_to_even():
    main, alt = L.event_rows(BODY, "G", NOW)
    q2 = [r for r in main if r["market"] == "spreads_q2"]
    assert len(q2) == 1 and float(q2[0]["spread_home"]) == 2.5
    assert q2[0]["home_price"] == -110 and q2[0]["away_price"] == -110
    alts = [r for r in alt if r["market"] == "spreads_q2_alternate"]
    assert len(alts) == 1 and float(alts[0]["spread_home"]) == 3.5
    assert alts[0]["home_price"] == -135 and alts[0]["away_price"] == 105
    # The market's own stamp, not the book's.
    assert q2[0]["snapshot_at"] == "2026-11-26T16:57:00Z"


def test_totals_and_moneyline_parse_and_unknown_markets_are_ignored():
    main, _ = L.event_rows(BODY, "G", NOW)
    by = {r["market"]: r for r in main}
    assert by["totals_q1"]["total_line"] == 56.5
    assert (by["totals_q1"]["over_price"], by["totals_q1"]["under_price"]) == (-115, -105)
    assert (by["h2h_q1"]["home_price"], by["h2h_q1"]["away_price"]) == (140, -165)
    assert "spreads" not in by
    assert all(r["bookmaker"] == "draftkings" for r in main)   # an unlisted book is never read


def test_a_one_sided_number_is_never_main():
    rows = L.book_rows([{"key": "totals_q3", "outcomes": [_o("Over", -110, 53.5)]}], HOME, AWAY)
    main, alt = L.split_main([{**r, "bookmaker": "fanduel"} for r in rows])
    assert main == [] and [r["market"] for r in alt] == ["totals_q3_alternate"]


def test_tie_goes_to_the_lower_number():
    rows = L.book_rows([{"key": "totals_q4", "outcomes": [
        _o("Over", -110, 52.5), _o("Under", -110, 52.5), _o("Over", -110, 53.5), _o("Under", -110, 53.5)]}],
        HOME, AWAY)
    main, _ = L.split_main([{**r, "bookmaker": "fanduel"} for r in rows])
    assert [r["total_line"] for r in main] == [52.5]


def test_pretip_skips_what_a_model_already_buys():
    assert set(L.MODEL_FETCHED) == {"spreads_q1", "h2h_q1", "totals_h1"}
    assert not set(L.PRETIP_MARKETS) & set(L.MODEL_FETCHED)
    assert set(L.PRETIP_MARKETS) | set(L.MODEL_FETCHED) == set(L.PERIOD_MARKETS)
    # The approved ceiling: at most 21 credits a game (one credit a market a call).
    assert len(L.markets_for("early")) + len(L.markets_for("pretip")) == 21
    assert L.markets_for("both") == L.PERIOD_MARKETS


def test_due_windows():
    g = {"far": NOW + timedelta(hours=9), "early": NOW + timedelta(hours=5),
         "pre": NOW + timedelta(minutes=60), "late": NOW + timedelta(minutes=50),
         "started": NOW - timedelta(minutes=1)}
    done = {"pre": {"early"}, "late": set()}
    d = L.due(g, done, NOW)
    assert d == {"early": "early", "pre": "pretip", "late": "both"}
    # Nothing is bought twice.
    assert L.due(g, {"early": {"early"}, "pre": {"early", "pretip"}, "late": {"early", "pretip"}}, NOW) == {}


def test_runs_on_every_refresh_pass():
    sh = (ROOT / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")
    assert "\npar nba-period-lines\n" in sh
    rp = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    assert '"nba-period-lines": lambda: step_nba_period_lines()' in rp


def test_the_assistant_view_reads_these_rows_as_periods():
    """mcp_stats.game_prices' period regex, on this feed's market names."""
    import re
    sql = (ROOT / "data" / "migrations" / "mcp_stats_all_markets_2026_11_25.sql").read_text(encoding="utf-8")
    pat = re.compile(re.search(r"substring\(o\.market FROM '([^']+)'\)", sql).group(1))
    for market, want in (("spreads_q2", "q2"), ("spreads_q2_alternate", "q2"), ("h2h_h1", "h1")):
        assert pat.search(market).group(1) == want
