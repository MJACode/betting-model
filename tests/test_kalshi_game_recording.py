"""The NCAAF game-market recorder keeps RAW contracts and never breaks a pass.

Session 280 (2026-09-10). Same contract as tests/test_kalshi_ladder_recording:
a research recorder that is scheduled, cannot take a scheduler tick down, and
stores what the exchange printed rather than a derived object.
"""
from __future__ import annotations

import scheduler
from data.ingestors import kalshi_game_ingestor as kgi


def test_the_recorder_is_scheduled_on_the_pipeline_role():
    assert "kalshi_game_markets" in scheduler._PIPELINE_JOBS
    assert scheduler.owns("kalshi_game_markets") or not scheduler.owns("daily_pipeline")


def test_a_kalshi_outage_cannot_break_the_pass(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("kalshi down")

    monkeypatch.setattr(kgi, "record_game_markets", _boom)
    monkeypatch.setattr(
        "data.ingestors.kalshi_game_ingestor.record_game_markets", _boom)
    scheduler.run_kalshi_game_record()            # must not raise


def test_event_date_is_searched_not_anchored():
    """The event ticker carries the series prefix; anchoring at ^ parsed
    nothing on the prop recorder's first run and looked like an empty market."""
    assert kgi.event_date("KXNCAAFTOTAL-26SEP12ARKUTAH") == "2026-09-12"
    assert kgi.event_date("KXNCAAFGAME-26SEP24LIBCCAR") == "2026-09-24"
    assert kgi.event_date("garbage") is None


def test_every_series_is_a_game_proposition():
    assert set(kgi.SERIES_KIND.values()) == {"winner", "total", "spread"}


def test_the_recorder_keeps_raw_contracts(monkeypatch):
    """A one-sided total rung and a winner contract with no strike are both
    facts about the market and both get written."""
    captured = {}

    class _Conn:
        def execute(self, sql, params=None):
            captured.setdefault("sql", []).append(sql)
            captured.setdefault("params", []).append(params)
            return self
        def commit(self): captured["committed"] = True
        def close(self): pass

    rung = {
        "event_ticker": "KXNCAAFTOTAL-26SEP12ULLUSC",
        "ticker": "KXNCAAFTOTAL-26SEP12ULLUSC-81",
        "title": "Over 80.5 points scored", "floor_strike": 80.5,
        "yes_bid_dollars": "0.09", "yes_ask_dollars": None,
        "volume_fp": "0.00", "status": "active",
    }
    winner = {
        "event_ticker": "KXNCAAFGAME-26SEP12ARKUTAH",
        "ticker": "KXNCAAFGAME-26SEP12ARKUTAH-UTAH",
        "title": "Utah wins", "yes_sub_title": "Utah", "floor_strike": None,
        "yes_bid_dollars": "0.60", "yes_ask_dollars": "0.62", "status": "active",
    }

    def _fetch(series, status="open"):
        return {"KXNCAAFTOTAL": [rung], "KXNCAAFGAME": [winner]}.get(series, [])

    monkeypatch.setattr(kgi, "fetch_series", _fetch)
    out = kgi.record_game_markets(conn=_Conn())

    assert out["contracts"] == 2
    assert out["events"] == 2
    assert captured.get("committed")
    flat = captured["params"][0]
    assert 80.5 in flat and 0.09 in flat and "Utah" in flat
    assert "ON CONFLICT (market_ticker, snapshot_at) DO NOTHING" in captured["sql"][0]


def test_the_migration_is_registered():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert "add_kalshi_game_markets.sql" in ACTIVE_MIGRATIONS
