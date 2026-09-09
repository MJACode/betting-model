"""A prop pick may not be written days before kickoff.

WHY THIS EXISTS (2026-09-08, mike's call). `models/nfl_prop_market` is the one
construction in this repo with a placebo-validated positive record: +9.83% over
648 bets, CI (+3.6, +16.0), positive in all three seasons. That record was
measured entirely on the `open` backfill series -- a single snapshot per game at
13:55 UTC on game day, whose lead times run 0.6h to 36.1h with a median around
seven hours.

Production was nowhere near it. `NFL_PROP_WINDOW_HOURS` was widened to 240 on
2026-09-07 and the card had a started-game FLOOR but no CEILING, so every NFL
prop BET written in the 21 days to 2026-09-08 was taken past 48h -- and
nfl_prop_market's three at 137.6-179.8h, five to seven days out. Under the §1c
first-signal lock those are permanent. The lane was locking its bets at a lead
time where nothing has ever measured positive, and would have gone on doing it
silently, because a card that prices a Sunday game on Wednesday looks exactly
like a card that prices it on Sunday.

THE TWO CONSTANTS ARE DIFFERENT ON PURPOSE and the tests below pin the
difference: `NFL_PROP_WINDOW_HOURS` (240) is how far ahead we BUY the board,
`NFL_PROP_MAX_LEAD_HOURS` (24) is how close to kickoff a pick may be WRITTEN.
Buying early is free information; betting early is not. Collapsing them back
into one number would silently restore the bug.

WHAT THIS IS NOT: a claim that earlier is always worse. T-72h beats T-48h, so
the decay is not monotone (docs/nfl_prop_offset_evidence.md). The ceiling keeps
the lane near the only offset that clears every bar, which is a narrower claim
and the one the evidence supports.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import config
import scripts.nfl_prop_market_card as card_mod


NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)


def _games(*leads_h):
    """One scheduled game per lead time, in hours from NOW."""
    out = {}
    for i, h in enumerate(leads_h):
        ko = NOW + timedelta(hours=h)
        out[f"NFL_2026_W2_G{i}_{h}h"] = {
            "kickoff": ko.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date": ko.date().isoformat(),
        }
    return out


@pytest.fixture()
def captured(monkeypatch):
    """Record which games actually reach the quote loader."""
    seen: dict = {}

    def _fake_load(conn, game_ids, markets, **kw):
        seen["games"] = list(game_ids)
        return {}

    monkeypatch.setattr(card_mod, "load_nfl_prop_quotes", _fake_load)
    return seen


def test_a_game_beyond_the_ceiling_is_never_priced(captured):
    """The bug, directly: a game a week out must not reach the pricer."""
    games = _games(6, 30, 170)          # in-range, just past, a week out
    bets, diag, _names = card_mod.card(
        None, "2026-09-13", "2026-09-23", 0.05, games=games, now=NOW)

    priced = captured["games"]
    assert len(priced) == 1, f"expected only the 6h game, got {priced}"
    assert priced[0].endswith("_6h")
    assert diag["too_early"] == 2
    assert diag["games"] == 1


def test_the_started_game_floor_still_holds(captured):
    """The ceiling must not displace the floor -- a kicked-off game is still
    excluded, and for a different reason (§1c: the reader cannot take it)."""
    games = _games(-3, 6, 100)
    bets, diag, _names = card_mod.card(
        None, "2026-09-13", "2026-09-23", 0.05, games=games, now=NOW)

    assert diag["started_skipped"] == 1
    assert diag["too_early"] == 1
    assert [g for g in captured["games"]] == [
        g for g in games if g.endswith("_6h")]


def test_a_slate_entirely_out_of_range_says_WHY(captured):
    """"No qualifying edges" and "not allowed to bet these yet" are different
    facts, and a thin card that conflates them reads as a quiet market."""
    games = _games(100, 170)
    bets, diag, _names = card_mod.card(
        None, "2026-09-13", "2026-09-23", 0.05, games=games, now=NOW)

    assert bets == []
    assert diag["too_early"] == 2
    assert "further than" in diag["reason"], diag["reason"]
    assert "games" not in captured, "nothing should have been priced"


def test_the_boundary_is_inclusive_at_the_ceiling(captured):
    """Exactly at the ceiling is still bettable -- the gate is `>`, so a game
    landing precisely on 24h is not silently dropped."""
    games = _games(config.NFL_PROP_MAX_LEAD_HOURS)
    card_mod.card(None, "2026-09-13", "2026-09-23", 0.05, games=games, now=NOW)
    assert len(captured["games"]) == 1


def test_buying_the_board_and_betting_it_are_different_numbers():
    """If these ever collapse into one constant, the bug is back: the lane
    would either stop buying the board it measures offsets from, or resume
    betting ten days out."""
    assert config.NFL_PROP_MAX_LEAD_HOURS < config.NFL_PROP_WINDOW_HOURS, (
        "the bet ceiling must be tighter than the fetch window")
    assert config.NFL_PROP_MAX_LEAD_HOURS <= 36, (
        "36.1h is the measured maximum of the `open` series the rule's record "
        "comes from; a ceiling above it bets where nothing was measured")
