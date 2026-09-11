"""The eleven distributional NFL prop models get the same lead ceiling as the card.

WHY THIS EXISTS (2026-09-11, mike: "we revised prop models or should have,
that was my earlier guidance"). #610 put a 24h ceiling on how early a prop
pick may be WRITTEN -- but only in `scripts/nfl_prop_market_card.py`. The
eleven `nfl_prop_*` models are scored by `models/scorer.run_nfl_prop_scorer`,
which had the started-game FLOOR and no ceiling, so on 2026-09-07 it wrote
seventeen Week-1 picks five to six days before kickoff. Those were deleted on
2026-09-11 on his instruction, and without this the next hourly tick would
have written them straight back.

Same constant as the card (`config.NFL_PROP_MAX_LEAD_HOURS`), on purpose: two
lanes that disagree about when a prop is bettable is the bug, not the fix
(CLAUDE.md 1b, the shared-constant rule). `tests/test_nfl_prop_lead_ceiling.py`
covers the card; this covers the scorer.

A game beyond the ceiling is SKIPPED, never dropped: it comes back into range
on a later tick. No pick is deleted or re-priced, so the first-signal lock is
untouched.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config
from models import scorer

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
REPO = Path(__file__).resolve().parent.parent


def _iso(hours_ahead: float, z: bool = False) -> str:
    ko = NOW + timedelta(hours=hours_ahead)
    return ko.strftime("%Y-%m-%dT%H:%M:%SZ") if z else ko.isoformat()


def test_a_kickoff_beyond_the_ceiling_is_too_early():
    assert scorer._nfl_prop_too_early(_iso(config.NFL_PROP_MAX_LEAD_HOURS + 1), now=NOW)
    assert scorer._nfl_prop_too_early(_iso(130), now=NOW)          # the 09-07 case


def test_the_boundary_is_inclusive_at_the_ceiling():
    # Exactly at the ceiling is bettable, matching the card's `>` test.
    assert not scorer._nfl_prop_too_early(_iso(config.NFL_PROP_MAX_LEAD_HOURS), now=NOW)
    assert not scorer._nfl_prop_too_early(_iso(1), now=NOW)


def test_a_started_or_unknown_kickoff_is_not_too_early():
    # The floor (_game_started) owns the past; the ceiling must not double up
    # on it, and an unknown kickoff must not silently block the whole slate.
    assert not scorer._nfl_prop_too_early(_iso(-2), now=NOW)
    assert not scorer._nfl_prop_too_early(None, now=NOW)
    assert not scorer._nfl_prop_too_early("", now=NOW)
    assert not scorer._nfl_prop_too_early("not a timestamp", now=NOW)


def test_the_z_suffix_parses_like_the_offset_form():
    assert scorer._nfl_prop_too_early(_iso(48, z=True), now=NOW)
    assert not scorer._nfl_prop_too_early(_iso(2, z=True), now=NOW)


def test_the_scorer_and_the_card_read_ONE_constant(monkeypatch):
    # Env-overridable on the card; the scorer must move with it, not carry a
    # literal 24 of its own.
    monkeypatch.setattr(config, "NFL_PROP_MAX_LEAD_HOURS", 6.0)
    monkeypatch.setattr(scorer, "NFL_PROP_MAX_LEAD_HOURS", 6.0)
    assert scorer._nfl_prop_too_early(_iso(7), now=NOW)
    assert not scorer._nfl_prop_too_early(_iso(5), now=NOW)


def test_the_scorer_loop_actually_applies_the_ceiling():
    """A guard that dead code can satisfy is not a guard (CLAUDE.md 1b).

    run_nfl_prop_scorer needs a database and eleven artifacts, so the wiring
    is pinned at the source: inside that function, the ceiling check sits
    between the started-game floor and the price read, on the SCHEDULED
    kickoff (`kickoffs`), so a game days out is skipped before a quote is
    ever fetched for it.
    """
    src = (REPO / "models" / "scorer.py").read_text(encoding="utf-8")
    start = src.index("def run_nfl_prop_scorer(")
    end = src.index("\ndef ", start + 1)
    body = src[start:end]
    floor = body.index("_game_started(cutoffs.get(game_id))")
    ceiling = body.index("_nfl_prop_too_early(kickoffs.get(game_id))")
    price = body.index("_get_prop_dk_odds(")
    assert floor < ceiling < price
    # and it is a skip, not a delete
    assert re.search(r"_nfl_prop_too_early\(kickoffs\.get\(game_id\)\):\s*\n\s*continue", body)
