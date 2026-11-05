"""NHL game bets on the builder (Matt, 2026-11-05: "Yes go")."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_nhl_season_is_the_ending_year():
    from byom.season import current_nhl_season
    assert current_nhl_season(date(2026, 11, 5)) == 2027
    assert current_nhl_season(date(2027, 3, 1)) == 2027
    assert current_nhl_season(date(2027, 9, 30)) == 2027
    assert current_nhl_season(date(2027, 10, 1)) == 2028


def test_jobs_accept_nhl_games_and_not_nhl_props():
    from byom.constants import NHL_DK_HISTORY_START_SEASON
    from tracking.job_queue import (
        _validate_byom_game_facts, _validate_byom_prop_facts, _validate_byom_refresh)
    assert NHL_DK_HISTORY_START_SEASON == 2021
    assert _validate_byom_game_facts({"sport": "nhl", "apply": True})["sport"] == "NHL"
    with pytest.raises(ValueError):
        _validate_byom_game_facts({"sport": "NHL", "season": 2020})
    assert _validate_byom_refresh({"sport": "NHL"})["sport"] == "NHL"
    with pytest.raises(ValueError):
        _validate_byom_prop_facts({"sport": "NHL"})


def test_the_backfill_is_declared_and_the_daily_refresh_queues_nhl():
    declared = json.loads((ROOT / "jobs/declared_jobs.json").read_text(encoding="utf-8"))
    nhl = [e for e in declared if e["key"] == "byom-nhl-game-facts"]
    assert len(nhl) == 1
    assert nhl[0]["enabled"] is True and nhl[0]["args"] == {"sport": "NHL", "apply": True}
    sched = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    assert 'for sport in ("NFL", "NBA", "NHL"):' in sched


def test_nhl_writes_official_candidates_and_starts_in_2021():
    from byom.load import _dk_history_floor
    from byom.official import OFFICIAL_SPORTS
    assert "NHL" in OFFICIAL_SPORTS
    assert _dk_history_floor("NHL") == 2021


class _Conn:
    def __init__(self, games, facts):
        self.games, self.facts = games, facts

    def execute(self, sql, params=None):
        rows = []
        if "FROM games" in sql:
            rows = [g for g in self.games if (g[8], g[1]) == (params[0], params[1])]
        elif "FROM byom_game_facts" in sql:
            rows = [f for f in self.facts if params == ("NHL", 2027)]

        class _R:
            def fetchall(self_inner):
                return rows
        return _R()


def test_a_past_nhl_game_is_never_due_for_props():
    """NHL has no props. Without this, every past game is due every day."""
    from byom.refresh import due_games
    stale = datetime(2026, 10, 24, tzinfo=timezone.utc)
    games = [
        ("NHL_2026-10-20_BOS_TOR", 2027, "2026-10-20", "TOR", "BOS", 3, 2, None, "NHL", None),
        ("NHL_2026-10-28_NYR_PHI", 2027, "2026-10-28", "PHI", "NYR", 4, 1, None, "NHL", None),
        ("NHL_2026-11-04_EDM_VAN", 2027, "2026-11-04", "VAN", "EDM", 2, 5, None, "NHL", None),
    ]
    facts = [
        ("NHL_2026-10-20_BOS_TOR", 3, 2, stale, None),     # complete, never prop-scanned
        ("NHL_2026-10-28_NYR_PHI", None, None, stale, None),  # built before the score
    ]
    due = due_games(_Conn(games, facts), today=date(2026, 11, 5), sport="NHL")
    assert {r["canonical_key"]: r["reason"] for r in due} == {
        "NHL_2026-10-28_NYR_PHI": "incomplete",
        "NHL_2026-11-04_EDM_VAN": "window",
    }


def test_the_migration_is_registered_and_accepts_nhl():
    from data.view_migrations import ACTIVE_MIGRATIONS
    name = "byom_nhl_2026_11_05.sql"
    assert name in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS.index(name) > ACTIVE_MIGRATIONS.index("byom_prop_lookup_2026_11_04.sql")
    text = (ROOT / "data/migrations" / name).read_text(encoding="utf-8")
    assert text.count("IN ('NFL', 'NBA', 'NHL')") == 2
    assert text.count("IN ('NBA', 'NHL')") == 2
