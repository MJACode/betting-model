"""The recorder must keep RAW rungs, and must never break a scheduler pass.

A reference cannot be graded until a record exists. Kalshi's NFL prop settled
history reaches back only to 2026 preseason, so this table IS the future
evidence -- and the two ways it can quietly fail are storing the wrong thing
(interpolated output rather than raw prices) and stopping without anyone
noticing.
"""
from __future__ import annotations

import scheduler
from data.ingestors import kalshi_prop_ingestor as kpi


def test_the_recorder_is_scheduled_on_the_pipeline_role():
    """A job absent from every role set is scheduled by nothing."""
    assert "kalshi_ladders" in scheduler._PIPELINE_JOBS
    assert scheduler.owns("kalshi_ladders") or not scheduler.owns("daily_pipeline")


def test_a_kalshi_outage_cannot_break_the_pass(monkeypatch):
    """It is a research recorder. If it throws, the scheduler tick that also
    fetches odds and publishes picks must still complete."""
    def _boom(*a, **k):
        raise RuntimeError("kalshi down")

    monkeypatch.setattr(kpi, "record_ladders", _boom)
    monkeypatch.setattr(
        "data.ingestors.kalshi_prop_ingestor.record_ladders", _boom)
    scheduler.run_kalshi_ladder_record()          # must not raise


def test_every_recorded_series_maps_to_one_of_our_markets():
    for series, market in kpi.SERIES_MARKET.items():
        assert market.startswith("player_"), (series, market)


def test_the_recorder_keeps_raw_prices_not_a_filtered_ladder(monkeypatch):
    """RAW RUNGS, NOT LADDERS. The spread gate and the monotone repair are
    choices models/prop_ladder makes today; freezing them into the stored
    history would stop a later analysis from varying them. So a one-sided rung
    -- which the Ladder drops -- must still be written."""
    captured = {}

    class _Conn:
        def execute(self, sql, params=None):
            captured.setdefault("sql", []).append(sql)
            captured.setdefault("params", []).append(params)
            return self
        def commit(self): captured["committed"] = True
        def close(self): pass

    one_sided = {
        "event_ticker": "KXNFLPASSYDS-26SEP13ATLPIT",
        "ticker": "KXNFLPASSYDS-26SEP13ATLPIT-X-400",
        "title": "Tua Tagovailoa: 400+ passing yards",
        "floor_strike": 399.5,
        "yes_bid_dollars": "0.00", "yes_ask_dollars": "0.11",
    }
    monkeypatch.setattr(kpi, "fetch_series",
                        lambda s, status="open": [one_sided] if "PASSYDS" in s else [])

    out = kpi.record_ladders(conn=_Conn(), series_map={"KXNFLPASSYDS": "player_pass_yds"})

    assert out["rungs"] == 1, "a one-sided rung is still a fact about the market"
    assert out["propositions"] == 1
    assert captured.get("committed")
    flat = captured["params"][0]
    assert 399.5 in flat and 0.0 in flat and 0.11 in flat


def test_a_run_is_idempotent_within_its_snapshot():
    """The insert must carry the ON CONFLICT clause, or a retry doubles every
    ladder and every later reconstruction is wrong."""
    import inspect
    src = inspect.getsource(kpi.record_ladders)
    assert "ON CONFLICT (market_ticker, snapshot_at) DO NOTHING" in src


def test_one_snapshot_timestamp_for_the_whole_run(monkeypatch):
    """A ladder is only meaningful as prices that existed TOGETHER. Per-row
    timestamps would make one player's 174.5 and 349.5 strikes look like
    different observations."""
    rows = []

    class _Conn:
        def execute(self, sql, params=None):
            rows.append(params); return self
        def commit(self): pass
        def close(self): pass

    mk = lambda strike, tick: {
        "event_ticker": "KXNFLPASSYDS-26SEP13ATLPIT",
        "ticker": tick, "title": "Tua Tagovailoa: x+ passing yards",
        "floor_strike": strike,
        "yes_bid_dollars": "0.40", "yes_ask_dollars": "0.44",
    }
    monkeypatch.setattr(kpi, "fetch_series",
                        lambda s, status="open": [mk(199.5, "A"), mk(249.5, "B")])
    kpi.record_ladders(conn=_Conn(), series_map={"KXNFLPASSYDS": "player_pass_yds"})

    flat = rows[0]
    stamps = {v for v in flat if hasattr(v, "tzinfo")}
    assert len(stamps) == 1, f"expected one snapshot_at, got {stamps}"
