"""The FBS gate trusts SP+, not the registry — and a disagreement is reported.

THE BUG (2026-09-12, found from the board, not the code). `_is_fbs` consulted
`sp_overall` only as a FALLBACK, when `classification` was NULL. Its own
docstring calls SP+ the proof of FBS membership — SP+ is FBS-only — so a row
whose classification WRONGLY said "fbs" sailed through the gate and the proof
was never looked at.

Measured against production that day:

  * `ncaaf_teams` held 138 schools classified `fbs`; 136 carried a 2026 SP+
    rating, and 136 is the FBS count CLAUDE.md section 4 states.
  * The two extras — North Dakota State [Mountain West] and Sacramento State
    [Mid-American] — were both written in ONE 2026-08-29 pass, and neither is
    in the conference named. All 15 of each team's 2026 `ncaaf_team_stats`
    snapshots said `fbs` with `sp_overall` NULL.
  * Their two DK-priced games that Saturday (NDSU @ Air Force, Sac State @
    Fresno State) produced NO pick row at all — `picks_log` held zero rows for
    either game_id, so no model ever wrote and nothing was there to delete.
    The gate passed them, and four models each returned an empty list.

Nothing that could be priced is lost by requiring SP+: `sp_overall` is itself a
feature (`d_sp_overall`), so a team without it yields a NULL the scorer must not
impute. What moves is WHERE the decline happens — at the gate, with a name.

The same shape appears in every season the registry covers, always on a school
moving between FCS and FBS: 2025 Delaware, Idaho, Missouri State; 2024 those
three plus Kennesaw State.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import today_et
from data.ingestors.cfbd_ingestor import ncaaf_season_for_date
from features.ncaaf_feature_engine import _is_fbs, unrated_fbs_claim

# The check asks for the CURRENT season (calendar year of the fall), so
# the fixtures must be written under the same label or it reads empty.
_SEASON = ncaaf_season_for_date(today_et())


# ── the gate ────────────────────────────────────────────────────────────────

class TestFbsGate:
    def test_registry_says_fbs_but_sp_has_no_rating_is_not_fbs(self):
        """The bug, in one assertion. This is the North Dakota State row."""
        assert _is_fbs({"classification": "fbs", "sp_overall": None}) is False

    def test_missing_sp_key_entirely_is_not_fbs(self):
        """Sacramento State's snapshots carry no SP+ column value at all."""
        assert _is_fbs({"classification": "fbs"}) is False

    def test_a_real_fbs_team_still_passes(self):
        """The control. Without it, 'return False' passes every test above and
        takes the whole NCAAF board down — 44 games on the Saturday this was
        found."""
        assert _is_fbs({"classification": "fbs", "sp_overall": -3.2}) is True

    def test_sp_rating_alone_still_passes_when_classification_was_never_set(self):
        """The original fallback is preserved: 2024 and 2025 carry 135-138
        snapshots a season with a NULL classification, and SP+ is what says
        those are FBS."""
        assert _is_fbs({"sp_overall": 12.4}) is True
        assert _is_fbs({"classification": None, "sp_overall": 12.4}) is True

    def test_another_division_vetoes_even_with_a_rating(self):
        """classification may only ever NARROW. A stray SP+ value must not
        promote a school the registry places elsewhere."""
        assert _is_fbs({"classification": "fcs", "sp_overall": 1.0}) is False
        assert _is_fbs({"classification": "ii", "sp_overall": 1.0}) is False

    def test_no_snapshot_at_all_is_not_fbs(self):
        assert _is_fbs({}) is False
        assert _is_fbs(None) is False


# ── naming the surprising decline ───────────────────────────────────────────

class TestUnratedFbsClaim:
    def test_the_disagreement_is_named(self):
        assert unrated_fbs_claim({"classification": "fbs"}) is not None

    def test_an_ordinary_fcs_opponent_is_not_reported(self):
        """33 of the 98 games on 2026-09-12 were FBS-vs-FCS and every one of
        them is expected. Reporting those would bury the two that matter."""
        assert unrated_fbs_claim({"classification": "fcs"}) is None
        assert unrated_fbs_claim({"sp_overall": None}) is None
        assert unrated_fbs_claim({}) is None

    def test_a_rated_fbs_team_is_not_reported(self):
        assert unrated_fbs_claim({"classification": "fbs", "sp_overall": 3.0}) is None


# ── the health check ────────────────────────────────────────────────────────

@pytest.fixture
def hdb(monkeypatch):
    """A schema-complete SQLite DB wired into system_health.

    The whole health pass runs, so the schema has to be the real one — the
    first version of this fixture created only the two tables the check reads
    and every other check blew up on `no such table: games`.
    """
    import tracking.system_health as sh
    from data.db_setup import SCHEMA_SQL, _MIGRATIONS

    path = tempfile.mktemp(suffix=".db")
    c = sqlite3.connect(path)
    c.executescript(SCHEMA_SQL)
    for tbl, col, defn in _MIGRATIONS:
        try:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {defn}")
        except sqlite3.OperationalError:
            pass
    # Postgres-only table other checks join.
    c.execute("""
        CREATE TABLE IF NOT EXISTS model_action_thresholds (
            model_id TEXT PRIMARY KEY, min_prob REAL NOT NULL,
            min_edge REAL NOT NULL DEFAULT 0, prob_only BOOLEAN NOT NULL DEFAULT 0,
            paused BOOLEAN NOT NULL DEFAULT 0, min_odds REAL)
    """)
    c.commit()

    class _Shim:
        def __init__(self, p):
            self._c = sqlite3.connect(p)

        def execute(self, sql, params=()):
            return self._c.execute(sql, tuple(params))

        def commit(self):
            self._c.commit()

        def rollback(self):
            self._c.rollback()

        def close(self):
            self._c.close()

    monkeypatch.setattr(sh, "get_connection", lambda: _Shim(path))
    yield c
    c.close()


def _registry_check(hdb):
    import tracking.system_health as sh
    return {r["check_name"]: r
            for r in sh.run_system_health()["results"]}["ncaaf_fbs_registry"]


def _team(hdb, school, conference, classification):
    hdb.execute("INSERT INTO ncaaf_teams (school, conference, classification) "
                "VALUES (?, ?, ?)", (school, conference, classification))


def _rating(hdb, team, sp_overall):
    hdb.execute("INSERT INTO ncaaf_team_stats (team, season, as_of_date, sp_overall) "
                "VALUES (?, ?, ?, ?)", (team, _SEASON, today_et(), sp_overall))


class TestRegistryHealthCheck:
    def test_an_unrated_fbs_school_is_reported_by_name(self, hdb):
        """North Dakota State, as production held it on 2026-09-12."""
        _team(hdb, "North Dakota State", "Mountain West", "fbs")
        _team(hdb, "Air Force", "Mountain West", "fbs")
        _rating(hdb, "Air Force", -3.2)
        _rating(hdb, "North Dakota State", None)
        hdb.commit()
        res = _registry_check(hdb)
        assert res["status"] != "OK"
        assert "North Dakota State" in res["detail"]
        # The school that IS rated must not be dragged in with it.
        assert "Air Force" not in res["detail"]

    def test_a_school_with_no_stats_row_at_all_is_reported(self, hdb):
        """Absence of a snapshot is absence of a rating — the check must not
        require the row to exist and merely be NULL."""
        _team(hdb, "Sacramento State", "Mid-American", "fbs")
        hdb.commit()
        assert _registry_check(hdb)["status"] != "OK"

    def test_a_fully_rated_registry_is_ok(self, hdb):
        """The control: the check has to be able to go green, or it is a
        permanent red nobody reads."""
        _team(hdb, "Air Force", "Mountain West", "fbs")
        _rating(hdb, "Air Force", -3.2)
        hdb.commit()
        assert _registry_check(hdb)["status"] == "OK"

    def test_an_fcs_school_without_a_rating_is_not_reported(self, hdb):
        """126 FCS schools carry snapshots with no SP+ — that is what FCS
        looks like, and reporting it would make the check useless."""
        _team(hdb, "Colgate", "Patriot", "fcs")
        _team(hdb, "Air Force", "Mountain West", "fbs")
        _rating(hdb, "Air Force", -3.2)
        hdb.commit()
        assert _registry_check(hdb)["status"] == "OK"


# ── the declared job that fixes the data ────────────────────────────────────

def test_the_registry_refresh_is_declared_and_validates():
    """A declared job reaches the worker as-is; a typo in job_type or args is
    only discovered when the worker rejects it, hours later and silently."""
    import json

    from tracking.job_queue import JOBS

    path = Path(__file__).resolve().parent.parent / "jobs" / "declared_jobs.json"
    declared = json.loads(path.read_text(encoding="utf-8"))
    entry = next(e for e in declared
                 if e["key"] == "ncaaf-teams-refresh-2026-fbs-registry")
    assert entry["job_type"] in JOBS
    cleaned = JOBS[entry["job_type"]][1](entry["args"])
    assert cleaned["season"] == 2026
    # The probe is the verification half: it re-resolves the names in question
    # against the registry the worker actually holds after the re-pull.
    assert any("North Dakota State" in p for p in cleaned["probe"])
    assert any("Sacramento State" in p for p in cleaned["probe"])
