"""The NCAAB in-play purchase: what it plans to buy, what it keeps, and that the
pruner cannot delete what it bought.

The failure this module exists for: the lines purchase bought every hour of six
seasons and its keeper dropped every in-play row (QuoteKeeper.wanted), so the
paid in-game prices were thrown away. These tests pin the opposite contract:
ONLY the in-play rows are kept, under their own source, in their own ledger.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from data import prune_odds
from data.ingestors import ncaab_inplay_history as H
from data.ingestors import ncaab_odds_history as L
from tests.test_ncaab_odds_history import GAMES, REGISTRY, UK_DUKE, _event


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_plan_takes_only_instants_with_a_game_in_progress():
    g = [{"game_id": "a", "commence_time": "2026-02-07T19:05:00Z"}]
    got = H.inplay_instants(g, 60)
    # 19:00 is before the tip; 20:00 and 21:00 are inside tip+2 .. tip+160 (21:45)
    assert got == [_t("2026-02-07T21:00:00Z"), _t("2026-02-07T20:00:00Z")]
    half = H.inplay_instants(g, 30)
    assert half == [_t(x) for x in ("2026-02-07T21:30:00Z", "2026-02-07T21:00:00Z",
                                    "2026-02-07T20:30:00Z", "2026-02-07T20:00:00Z",
                                    "2026-02-07T19:30:00Z")]
    # the hourly plan is nested in the half-hourly one, so both can be graded
    assert set(got) <= set(half)


def test_plan_shares_an_instant_between_games_and_skips_unknown_tips():
    g = [{"game_id": "a", "commence_time": "2026-02-07T19:05:00Z"},
         {"game_id": "b", "commence_time": "2026-02-07T19:30:00Z"},
         {"game_id": "c", "commence_time": None}]
    got = H.inplay_instants(g, 60)
    # b runs to 22:10, so 22:00 is bought once for it; the shared hours once
    assert got == [_t("2026-02-07T22:00:00Z"), _t("2026-02-07T21:00:00Z"),
                   _t("2026-02-07T20:00:00Z")]


def test_only_in_play_rows_are_kept_and_they_carry_the_source():
    tip = UK_DUKE["commence_time"]                       # 2025-11-19T00:30Z
    when = _t("2025-11-19T01:00:00Z")
    body = {"timestamp": "2025-11-19T00:55:38Z", "data": [
        # quoted after the tip: in play, kept
        _event("e1", "Duke Blue Devils", "Kentucky Wildcats", tip,
               last_update="2025-11-19T00:55:20Z"),
        # quoted before the tip, still on the board: a pre-game row, counted only
        _event("e1", "Duke Blue Devils", "Kentucky Wildcats", tip, book="betmgm",
               last_update="2025-11-19T00:20:00Z"),
    ]}
    resolver = L.EventResolver(REGISTRY, GAMES)
    tips = {g["game_id"]: g["commence_time"] for g in GAMES}
    part = H.split_snapshot(body, when, resolver, tips)
    assert part["rows"], "the in-play quote was dropped"
    assert {r["snapshot_type"] for r in part["rows"]} == {"in_play"}
    assert {r["source"] for r in part["rows"]} == {H.SOURCE}
    assert {r["bookmaker"] for r in part["rows"]} == {"fanduel"}
    assert part["pre_tip_rows"] == 3                     # betmgm's three markets
    assert part["served"] == _t("2025-11-19T00:55:38Z")


def test_the_pruner_protects_the_purchase_by_its_writers_own_name():
    assert H.SOURCE in prune_odds.PROTECTED_SOURCES


def test_its_ledger_is_not_the_lines_purchase_ledger():
    # odds_history_pulls already holds every hour, so a shared ledger would
    # skip every instant: the in-play purchase keeps its own
    assert H.LEDGER == "ncaab_inplay_fetches"
    assert "odds_history_pulls" not in H.LEDGER_DDL


class _Conn:
    """Answers the two reads check_resume makes."""

    def __init__(self, stored, ledgered):
        self.stored, self.ledgered = stored, ledgered

    def execute(self, sql, params=None):
        class R:
            def __init__(s, v):
                s.v = v

            def fetchone(s):
                return (s.v,)
        if "to_regclass" in sql:
            return R("ncaab_inplay_fetches")
        if "FROM odds" in sql:
            assert params == (H.SOURCE,)
            return R(self.stored)
        return R(self.ledgered)

    def commit(self):
        pass


def test_the_resume_refuses_when_the_ledger_does_not_cover_the_stored_rows():
    import pytest
    assert H.check_resume(_Conn(2752, 2752)) == (2752, 2752)
    with pytest.raises(H.LedgerMismatch):
        H.check_resume(_Conn(2752, 0))           # ledger lost: a re-run would re-buy
