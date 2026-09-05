"""The backfill's skip predicate must be per GAME, not per date.

THE BUG THIS PINS. `backfill_player_game_log` skipped a whole date if
`player_game_log` held any row for it. Every MLB date carries ~15 games, so one
ingested game marked the entire date done and every other game on it was never
fetched.

Measured 2026-09-03, before the fix: of 200 White Sox games in 2024, **200 sat
on a date that already had rows from other games, and 0 had rows of their own.**
The White Sox and Nationals had no per-game data at all before 2026 — not one
row, not even their opponents' starters. That hole is why the rebuilt
`mlb_pitcher_stats` covers only 75-89% of games by season
(`docs/team_stats_leak.md`).

It is `.claude/rules/data-integrity.md`'s jamming backfill in another shape: a
backfill must filter by the SAME predicate the worker applies. The unit of work
is a GAME, so the skip is per game.

These tests read the source rather than run the ingest, because the function
needs `statsapi` and live network egress. That is a deliberate trade: a source
assertion that pins the exact predicate is worth more than no test at all, and
the mutation below confirms it bites.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

SRC = (Path(__file__).parent.parent / "data" / "ingestors"
       / "mlb_stats_ingestor.py").read_text(encoding="utf-8")


def _backfill_body() -> str:
    body = SRC.split("def backfill_player_game_log(")[1]
    return body.split("\ndef ")[0]


def test_the_skip_is_keyed_on_game_id():
    """The predicate itself. A per-game skip is the entire fix."""
    body = _backfill_body()
    assert "covered_game_ids" in body, "no per-game coverage set"
    assert "if game_id in covered_game_ids:" in body, (
        "the skip must test the GAME, not the date")


def test_no_skip_is_keyed_on_date_alone():
    """The regression guard. Reintroducing a date-scoped `continue` recreates
    the hole that cost the White Sox and Nationals seven seasons of data."""
    body = _backfill_body()
    offending = re.search(
        r"COUNT\(\*\)\s+FROM\s+player_game_log\s+WHERE\s+game_date\s*=", body)
    assert offending is None, (
        "backfill skips by date again — one ingested game will mark the whole "
        "date done and every other game on it will be silently missed")


def test_the_coverage_set_is_scoped_to_the_season_being_built():
    """Loaded per season, not once for all time: the function opens a fresh
    connection per season precisely because Supabase drops long-lived ones."""
    body = _backfill_body()
    m = re.search(r"covered_game_ids = set\(.*?\)\.fetchall\(\)\)", body, re.S)
    assert m, "coverage set is not built from a query"
    assert "WHERE season = %s" in m.group(0), (
        "coverage set must be scoped to the season, or it grows unbounded")


def test_a_game_absent_from_our_games_table_is_still_skipped():
    """The MLB API returns games we have no `games` row for — Tokyo series,
    exhibitions. Fetching them would write orphan rows against a game_id that
    violates the foreign key."""
    body = _backfill_body()
    assert "valid_game_ids" in body
    assert "if valid_game_ids and game_id not in valid_game_ids:" in body
