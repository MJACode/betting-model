"""The FBS gate trusts SP+, not the registry — and an unrated school is named.

THE BUG (2026-09-12, found from the board, not the code). `_is_fbs` consulted
`sp_overall` only as a FALLBACK, when `classification` was NULL. Its own
docstring calls SP+ the proof of FBS membership — SP+ is FBS-only — so whenever
a classification existed the proof was never reached.

The case that found it: **North Dakota State** and **Sacramento State** carry
`fbs` in `ncaaf_teams` and in all 15 of their 2026 `ncaaf_team_stats`
snapshots, and SP+ has rated neither. Their two DK-priced games that Saturday
(NDSU @ Air Force, Sac State @ Fresno State) produced NO pick row at all —
`picks_log` held zero rows for either id, because the gate passed them and four
models then each returned an empty list.

WHY, CORRECTED 2026-09-13. The first version of this file said the registry was
wrong: a bad ingest default writing `fbs` over an FCS school. That was a theory,
and it was tested rather than believed. A `ncaaf_teams_refresh` for 2026 ran on
the worker (job 82908, 683 rows — the whole table), and `_TEAM_UPSERT`
overwrites classification and conference unconditionally from CFBD. Both
schools came back `fbs`; the FBS count stayed 138. **CFBD asserts they are FBS
programs for 2026** — newly promoted ones — so the registry is right and
CLAUDE.md section 4's "136" was the stale number.

The gate is still correct, for a different reason than first claimed: a school
SP+ has not rated cannot be MODELLED whatever division it plays in, because
`sp_overall` is itself a feature (`d_sp_overall`) and a missing feature is not
0.0.

WHY THEY ARE UNRATED, CORRECTED 2026-10-12. Not "SP+ lags a promotion": a
season's `sp_overall` is CFBD's PRIOR season's final SP+, held constant all year,
and both schools were FCS in 2025, which SP+ does not rate. So they are blank
for the whole of 2026 by design; a rating can first appear on the first run on
or after 2027-03-01, and only if CFBD rates them. Precedent in the data: Delaware
and Missouri State (FBS from 2025) unrated in 2025, rated in 2026; Kennesaw
State (FBS from 2024) unrated in 2024, rated in 2025. `config.
NCAAF_PROMOTED_TO_FBS` lists them, and the health check reports a listed school
as OK in its promotion season only — the games stay refused at the gate.
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


def _promoted(monkeypatch, mapping):
    """Pin the promoted-schools list for one test.

    Never lean on the real entries here: they name 2026, and `_SEASON` follows
    today's date, so a test built on them would flip on 2027-03-01.
    """
    import config
    # raising=False: on code without the list the behaviour assertions, not
    # this setup line, are what fail.
    monkeypatch.setattr(config, "NCAAF_PROMOTED_TO_FBS", dict(mapping),
                        raising=False)


def _alarm_part(detail):
    """The STALE text before the note about exempt schools, i.e. the part that
    claims something is wrong."""
    return detail.split("Separately,")[0]


class TestRegistryHealthCheck:
    # REWRITTEN 2026-10-12. These two used North Dakota State and Sacramento
    # State as the unrated school and asserted "not OK". Those two are now
    # EXPECTED to be unrated in their first FBS season (config.
    # NCAAF_PROMOTED_TO_FBS) and the check reports them OK with the reason, so
    # the alarm cases use an established school instead — the property pinned
    # (an unrated FBS school is named; a missing row counts as unrated) is
    # unchanged.
    def test_an_unrated_fbs_school_is_reported_by_name(self, hdb, monkeypatch):
        """An established FBS school with no SP+ rating."""
        _promoted(monkeypatch, {})
        _team(hdb, "Boise State", "Mountain West", "fbs")
        _team(hdb, "Air Force", "Mountain West", "fbs")
        _rating(hdb, "Air Force", -3.2)
        _rating(hdb, "Boise State", None)
        hdb.commit()
        res = _registry_check(hdb)
        assert res["status"] != "OK"
        assert "Boise State" in res["detail"]
        # The school that IS rated must not be dragged in with it.
        assert "Air Force" not in res["detail"]

    def test_a_school_with_no_stats_row_at_all_is_reported(self, hdb, monkeypatch):
        """Absence of a snapshot is absence of a rating — the check must not
        require the row to exist and merely be NULL."""
        _promoted(monkeypatch, {})
        _team(hdb, "Boise State", "Mountain West", "fbs")
        hdb.commit()
        assert _registry_check(hdb)["status"] != "OK"

    # ── newly promoted schools (2026-10-12) ─────────────────────────────────
    def test_a_school_in_its_promotion_season_is_ok_and_says_why(self, hdb,
                                                                  monkeypatch):
        """THE FIX. North Dakota State and Sacramento State were FCS the season
        before, and a season's SP+ is the PRIOR season's, so they cannot have
        one this season. STALE here posted to the ops channel every 12 hours
        for something nobody can act on. OK, with the reason and the earliest
        date it can change — and both games stay refused at the gate."""
        _promoted(monkeypatch, {"North Dakota State": _SEASON,
                                "Sacramento State": _SEASON})
        _team(hdb, "North Dakota State", "Mountain West", "fbs")
        _team(hdb, "Sacramento State", "Mid-American", "fbs")
        _team(hdb, "Air Force", "Mountain West", "fbs")
        _rating(hdb, "Air Force", -3.2)
        _rating(hdb, "North Dakota State", None)    # a row, NULL rating
        hdb.commit()                                 # Sac State: no row at all
        res = _registry_check(hdb)
        assert res["status"] == "OK", res["detail"]
        detail = res["detail"]
        assert "North Dakota State" in detail and "Sacramento State" in detail
        assert "newly promoted" in detail
        assert f"{_SEASON + 1}-03-01" in detail
        assert "only if CFBD rates them" in detail
        assert "Air Force" not in detail

    def test_a_promoted_school_still_unrated_a_season_later_is_stale(
            self, hdb, monkeypatch):
        """The exemption EXPIRES by itself. North Dakota State listed as
        promoted LAST season and still unrated now is not the by-design case
        any more — something is wrong. Sacramento State, in its first season,
        stays excused in the same run, so the alarm counts one school."""
        _promoted(monkeypatch, {"North Dakota State": _SEASON - 1,
                                "Sacramento State": _SEASON})
        _team(hdb, "North Dakota State", "Mountain West", "fbs")
        _team(hdb, "Sacramento State", "Mid-American", "fbs")
        _rating(hdb, "North Dakota State", None)
        hdb.commit()
        res = _registry_check(hdb)
        assert res["status"] == "STALE"
        assert res["detail"].startswith("1 FBS school(s)"), res["detail"]
        alarm = _alarm_part(res["detail"])
        assert "North Dakota State" in alarm
        assert f"promoted in {_SEASON - 1}, no longer exempt" in alarm
        assert "Sacramento State" not in alarm

    def test_an_established_school_losing_its_rating_is_stale(self, hdb,
                                                               monkeypatch):
        """The list excuses only the schools on it, in their season. An
        established school whose rating disappears is an alarm even while a
        promoted school is excused in the same run."""
        _promoted(monkeypatch, {"North Dakota State": _SEASON})
        _team(hdb, "North Dakota State", "Mountain West", "fbs")
        _team(hdb, "Air Force", "Mountain West", "fbs")
        _rating(hdb, "North Dakota State", None)
        _rating(hdb, "Air Force", None)
        hdb.commit()
        res = _registry_check(hdb)
        assert res["status"] == "STALE"
        assert res["detail"].startswith("1 FBS school(s)"), res["detail"]
        alarm = _alarm_part(res["detail"])
        assert "Air Force" in alarm
        assert "North Dakota State" not in alarm

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


def test_the_promoted_list_names_the_2026_schools():
    """The real list. Both moved up to FBS for 2026 (CFBD lists them as FBS,
    re-pulled 2026-09-13), and their first FBS season is the one they cannot
    be rated in."""
    import config
    assert config.NCAAF_PROMOTED_TO_FBS["North Dakota State"] == 2026
    assert config.NCAAF_PROMOTED_TO_FBS["Sacramento State"] == 2026


# ── the refusal log (2026-10-12) ────────────────────────────────────────────
#
# The pre-game refusal was documented as logging at WARNING for a school the
# registry calls FBS but SP+ has not rated. It never did: the live snapshot
# read selects `_STAT_COLS`, which carries no `classification` (and must not —
# `_is_fbs` would then veto on it in training and backtests), so the claim
# always saw None and every refusal went to debug. The scorer now reads the
# registry once per pass and hands it to the LOG only.

def _live_db():
    from data.db_setup import SCHEMA_SQL
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA_SQL)
    return c


def _snapshot(c, team, sp, conference="Mountain West"):
    c.execute("INSERT INTO ncaaf_team_stats (team, season, as_of_date, "
              "games_played, sp_overall, conference, classification) "
              "VALUES (?, ?, ?, 3, ?, ?, 'fbs')",
              (team, _SEASON, f"{_SEASON}-09-01", sp, conference))


def _warnings_from(fn):
    from loguru import logger
    seen: list[str] = []
    sink = logger.add(lambda m: seen.append(str(m)), level="WARNING",
                      format="{message}")
    try:
        result = fn()
    finally:
        logger.remove(sink)
    return result, seen


class TestRefusalLog:
    def test_an_unrated_school_the_registry_calls_fbs_is_logged_by_name(
            self, monkeypatch):
        """With the registry handed in, the refusal is a WARNING that names
        the school and says why — and the game is still refused (None).
        An ordinary FCS opponent in the same pass stays off the WARNING log."""
        from features.ncaaf_feature_engine import build_ncaaf_game_features
        _promoted(monkeypatch, {"North Dakota State": _SEASON})
        c = _live_db()
        _snapshot(c, "Nevada", -8.0)
        _snapshot(c, "North Dakota State", None)
        c.commit()
        registry = {"Nevada": "fbs", "North Dakota State": "fbs",
                    "Colgate": "fcs"}
        res, seen = _warnings_from(lambda: build_ncaaf_game_features(
            c, "g1", f"{_SEASON}-10-17", "North Dakota State", "Nevada",
            _SEASON, fbs_registry=registry))
        assert res is None, "the gate must still refuse the game"
        assert len(seen) == 1, seen
        assert "North Dakota State" in seen[0]
        assert "newly promoted to FBS" in seen[0]
        assert f"{_SEASON + 1}-03-01" in seen[0]

        res, seen = _warnings_from(lambda: build_ncaaf_game_features(
            c, "g2", f"{_SEASON}-10-17", "Nevada", "Colgate",
            _SEASON, fbs_registry=registry))
        assert res is None
        assert seen == [], "an FCS opponent is expected and must not warn"

    def test_an_unlisted_unrated_fbs_school_warns_without_the_excuse(
            self, monkeypatch):
        from features.ncaaf_feature_engine import fbs_refusal_claims
        _promoted(monkeypatch, {})
        claims = fbs_refusal_claims(
            (("Boise State", {"sp_overall": None}),
             ("Air Force", {"sp_overall": -3.2})),
            _SEASON, {"Boise State": "fbs", "Air Force": "fbs"})
        assert len(claims) == 1 and claims[0].startswith("Boise State")
        assert "newly promoted" not in claims[0]

    def test_without_the_registry_nothing_changes(self, monkeypatch):
        """Fail-open: if the scorer could not read the registry it passes
        None, and the refusal logs at debug exactly as before."""
        from features.ncaaf_feature_engine import build_ncaaf_game_features
        _promoted(monkeypatch, {"North Dakota State": _SEASON})
        c = _live_db()
        _snapshot(c, "Nevada", -8.0)
        _snapshot(c, "North Dakota State", None)
        c.commit()
        res, seen = _warnings_from(lambda: build_ncaaf_game_features(
            c, "g1", f"{_SEASON}-10-17", "North Dakota State", "Nevada",
            _SEASON, fbs_registry=None))
        assert res is None
        assert seen == []


def test_the_scorer_reads_the_registry_once_per_pass_and_only_for_the_log():
    """Source pin. The registry read sits BEFORE the per-game loop (once per
    pass, never per refused game) and reaches build_ncaaf_game_features as
    the log-only keyword; it is never added to the feature engine's
    _STAT_COLS, which would turn the classification veto on in training."""
    root = Path(__file__).resolve().parent.parent
    src = (root / "models" / "scorer.py").read_text(encoding="utf-8")
    read_at = src.index("SELECT school, classification FROM ncaaf_teams")
    loop_at = src.index("from features.ncaaf_feature_engine import "
                        "build_ncaaf_game_features")
    assert read_at < loop_at
    assert src.count("SELECT school, classification FROM ncaaf_teams") == 1
    assert "fbs_registry=ncaaf_fbs_registry" in src[loop_at:loop_at + 400]

    from features.ncaaf_feature_engine import _STAT_COLS
    assert "classification" not in _STAT_COLS


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
