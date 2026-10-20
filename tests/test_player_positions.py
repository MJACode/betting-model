"""NBA / WNBA / NCAAF positions for the position-vs-opponent card (phase 3).

Matt, 2026-10-05: "Yes for basketball. But show the players name" — G / F / C,
from data/ingestors/player_positions_ingestor.py into `player_positions`.

The sources (ESPN core, CFBD /roster) are unreachable from the dev sandbox, so
these pin what can be pinned without them: the parsers on the shapes the module
documents, the name match that maps an ESPN athlete onto OUR nba_api id, the
groups, and that the first run is a DRY RUN declared for the worker. The real
shapes are confirmed by that run's worker_jobs.result, not by these fixtures.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from data.ingestors.player_positions_ingestor import (
    FOOTBALL_GROUP,
    basketball_group,
    match_to_log,
    parse_athlete,
    parse_cfbd_roster,
)
from data.ingestors.wnba_results_ingestor import norm_player_name

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "data/migrations/add_player_positions.sql"


def test_athlete_with_inline_position():
    a = parse_athlete({"id": "4277905", "displayName": "Paolo Banchero",
                       "position": {"abbreviation": "PF", "name": "Power Forward"}})
    assert a == {"espn_id": "4277905", "name": "Paolo Banchero", "position": "PF"}


def test_athlete_whose_position_is_a_ref_uses_the_followed_doc():
    doc = {"id": "1", "displayName": "X", "position": {"$ref": "https://x/positions/3"}}
    assert parse_athlete(doc) is None
    assert parse_athlete(doc, {"abbreviation": "c"})["position"] == "C"


@pytest.mark.parametrize("doc", [None, {}, {"id": "1"}, {"displayName": "X"},
                                 {"id": "1", "displayName": "X", "position": "G"}])
def test_an_unexpected_athlete_shape_is_skipped_not_raised(doc):
    assert parse_athlete(doc) is None


@pytest.mark.parametrize("pos,grp", [("PG", "G"), ("SG", "G"), ("G", "G"),
                                     ("SF", "F"), ("PF", "F"), ("F", "F"),
                                     ("C", "C"), ("G-F", "G"), ("F-C", "F"),
                                     ("", None), (None, None), ("XX", None)])
def test_basketball_groups_are_guard_forward_center(pos, grp):
    assert basketball_group(pos) == grp


def test_a_unique_name_matches_its_log_id():
    index = {norm_player_name("Paolo Banchero"): [("1631094", "ORL", "2026-04-12")]}
    how: dict = {}
    assert match_to_log("Paolo Banchero", "ORL", index, how) == "1631094"
    assert how["method"] == "name"
    # Accents, suffixes and punctuation normalise the way the WNBA results
    # ingestor already matches ESPN names to nba_api ids.
    index = {norm_player_name("Nikola Jokic"): [("203999", "DEN", "2026-04-12")]}
    assert match_to_log("Nikola Jokić", None, index) == "203999"


def test_a_shared_name_is_settled_by_team_then_by_most_recent_game():
    """Matt, 2026-10-06: "don't skip names". Team first; a name still shared
    after that goes to whoever played most recently, and says so."""
    index = {"jalen williams": [("1631114", "OKC", "2026-04-10"),
                                ("1631116", "DEN", "2026-04-12")]}
    how: dict = {}
    assert match_to_log("Jalen Williams", "OKC", index, how) == "1631114"
    assert how["method"] == "team"
    assert match_to_log("Jalen Williams", None, index, how) == "1631116"
    assert how["method"] == "tiebreak_recent"
    # A team that matches neither: still decided, never skipped.
    assert match_to_log("Jalen Williams", "BOS", index, how) == "1631116"
    assert how["method"] == "tiebreak_recent"
    # Two on the SAME team: the tiebreak runs among them only.
    index = {"x y": [("1", "OKC", "2026-01-01"), ("2", "OKC", "2026-02-01"),
                     ("3", "DEN", "2026-03-01")]}
    assert match_to_log("X Y", "OKC", index, how) == "2"


def test_no_log_history_is_no_match():
    assert match_to_log("Rookie Nobody", "ORL", {}) is None


def test_cfbd_roster_rows_keep_cfbd_ids():
    rows = parse_cfbd_roster([
        {"id": 4683210, "firstName": "Brady", "lastName": "Hunt",
         "team": "South Carolina", "position": "wr"},
        {"id": None, "team": "X", "position": "QB"},
        {"id": 5, "team": "X"},
        "junk",
    ])
    assert rows == [{"player_id": "4683210", "name": "Brady Hunt",
                     "team": "South Carolina", "position": "WR"}]


def test_ncaaf_groups_match_the_nfl_card():
    """The two football cards bucket positions alike."""
    sql = (ROOT / "data/migrations/add_position_vs_opponent_nfl.sql").read_text(encoding="utf-8")
    nfl: dict[str, str] = {}
    for single, many, grp in re.findall(
            r"WHEN n\.pos (?:= '(\w+)'|IN \(([^)]*)\)) THEN '(\w+)'", sql):
        for p in [single] if single else re.findall(r"'(\w+)'", many):
            nfl[p] = grp
    assert nfl
    for pos, grp in nfl.items():
        assert FOOTBALL_GROUP.get(pos) == grp, pos


def test_the_table_is_migrated_guarded_and_read_only_to_anon():
    from data.anon_readable import ANON_READABLE
    from data.view_migrations import ACTIVE_MIGRATIONS

    code = MIG.read_text(encoding="utf-8")
    sql = "\n".join(ln for ln in code.splitlines() if not ln.lstrip().startswith("--"))
    assert MIG.name in ACTIVE_MIGRATIONS
    # The player page reads one row by key; the card functions join it.
    assert "player_positions" in ANON_READABLE
    assert sql.strip().startswith("DO $mig$") and sql.strip().endswith("$mig$;")
    assert "IF to_regclass('public.player_positions') IS NOT NULL THEN" in code
    assert "REVOKE ALL ON public.player_positions FROM anon, authenticated;" in code
    assert "GRANT SELECT ON public.player_positions TO anon, authenticated;" in code
    assert "PRIMARY KEY (sport, player_id)" in code


def test_the_ingestor_does_no_ddl_at_write_time():
    """The table is the migration's; a write-time CREATE would 503 the app
    on every pass (tests/test_ddl_guard.py)."""
    src = (ROOT / "data/ingestors/player_positions_ingestor.py").read_text(encoding="utf-8")
    assert not re.search(r"\b(CREATE|ALTER|DROP)\s+(TABLE|INDEX|POLICY)", src)


def test_the_job_defaults_to_a_dry_run_and_rejects_unknown_sports():
    from tracking.job_queue import JOBS

    _, validate = JOBS["player_positions"]
    assert validate({})["dry_run"] is True
    assert validate({"dry_run": False})["dry_run"] is False
    assert validate({})["sports"] == ["NBA", "WNBA", "NCAAF"]
    with pytest.raises(ValueError):
        validate({"sports": ["MLB"]})
    with pytest.raises(ValueError):
        validate({"dry_run": "no"})


def test_the_first_run_declared_for_the_worker_is_a_dry_run():
    jobs = json.loads((ROOT / "jobs/declared_jobs.json").read_text(encoding="utf-8"))
    ours = [j for j in jobs if j["job_type"] == "player_positions"]
    assert ours, "declare the dry run so the worker runs it"
    assert all(j["args"].get("dry_run") is True for j in ours[:1])


def test_rosters_are_read_under_a_season():
    """The season-less roster URL answered 404 for every team on the worker
    (job 405765, 2026-10-06); the season-scoped one is tried, likeliest year
    first, with the neighbours as fallbacks."""
    from datetime import datetime, timezone

    from data.ingestors.player_positions_ingestor import roster_candidates

    oct_2026 = datetime(2026, 10, 6, tzinfo=timezone.utc)
    nba = roster_candidates("nba", "13", oct_2026)
    assert [u.split("/seasons/")[1].split("/")[0] for u in nba] == ["2027", "2026", "2025"]
    assert all("/teams/13/athletes?limit=200" in u for u in nba)
    wnba = roster_candidates("wnba", "3", oct_2026)
    assert [u.split("/seasons/")[1].split("/")[0] for u in wnba] == ["2026", "2027", "2025"]
    assert not any("/leagues/nba/teams/" in u for u in nba)


def test_a_real_run_before_the_table_exists_fails_so_it_is_retried(monkeypatch):
    """A job that returns a per-sport error inside a 'done' result is never
    retried; a missing table must raise instead."""
    import data.db as db
    from data.ingestors import player_positions_ingestor as ppi

    class _Cur:
        def fetchone(self):
            return (None,)

    class _Conn:
        closed = False

        def execute(self, *a, **k):
            return _Cur()

        def close(self):
            self.closed = True

    conn = _Conn()
    monkeypatch.setattr(db, "get_connection", lambda: conn)
    with pytest.raises(RuntimeError, match="does not exist yet"):
        ppi.ingest_player_positions(sports=["NCAAF"], dry_run=False)
    assert conn.closed


def test_a_shared_updated_at_does_not_expire_on_one_morning():
    """Skipped-fresh rows are not rewritten. The window is 7 days plus a
    0–6 day hash of the id, so a cohort stored on one morning falls due
    across the next week instead of all on the seventh morning."""
    from datetime import datetime, timedelta, timezone

    from data.ingestors import player_positions_ingestor as ppi

    updated = datetime(2026, 10, 1, 11, tzinfo=timezone.utc)
    ids = [f"ath-{i}" for i in range(840)]
    windows = [ppi.refresh_window_days(i) for i in ids]
    assert min(windows) == ppi.REFRESH_DAYS
    assert max(windows) == ppi.REFRESH_DAYS + ppi.JITTER_DAYS - 1
    # The day before the shortest window lapses, nobody is due.
    day_before = updated + timedelta(days=ppi.REFRESH_DAYS) - timedelta(seconds=1)
    assert all(ppi.is_within_window(updated, i, day_before) for i in ids)
    first_morning = updated + timedelta(days=ppi.REFRESH_DAYS)
    due = [i for i in ids if not ppi.is_within_window(updated, i, first_morning)]
    assert due
    assert len(due) < len(ids) / 4
    last_morning = updated + timedelta(days=ppi.REFRESH_DAYS + ppi.JITTER_DAYS - 1)
    assert all(not ppi.is_within_window(updated, i, last_morning) for i in ids)


def _espn_stub(monkeypatch, athlete_ids):
    """One NBA club whose roster is `athlete_ids`. Returns the URL list."""
    import re

    from data.ingestors import player_positions_ingestor as ppi

    calls: list[str] = []
    team = ("https://sports.core.api.espn.com/v2/sports/basketball/leagues/"
            "nba/teams/1?lang=en")

    def fake_get(url):
        calls.append(url)
        if "teams?limit=50" in url:
            return {"items": [{"$ref": team}]}
        if "/seasons/" in url and "/athletes" in url:
            return {"items": [{
                "$ref": "https://sports.core.api.espn.com/v2/sports/basketball/"
                        f"leagues/nba/athletes/{i}",
            } for i in athlete_ids]}
        am = re.search(r"/athletes/(\d+)", url)
        if am:
            aid = am.group(1)
            return {"id": aid, "displayName": f"Rookie {aid}",
                    "position": {"abbreviation": "PG"}}
        if "/teams/" in url:
            return {"abbreviation": "ORL", "id": "1"}
        raise AssertionError(url)

    monkeypatch.setattr(ppi, "_get_json", fake_get)
    monkeypatch.setattr(ppi, "_name_index", lambda conn, sport: {})
    monkeypatch.setattr(ppi, "_upsert", lambda conn, rows: len(rows))
    return calls


def test_unmatched_ids_are_cached_and_not_refetched_within_the_ttl(monkeypatch):
    from data.ingestors import player_positions_ingestor as ppi

    calls = _espn_stub(monkeypatch, ["10", "11"])
    remembered: list[list[str]] = []
    monkeypatch.setattr(ppi, "_fresh_source_ids", lambda conn, sport: set())
    monkeypatch.setattr(ppi, "_cached_unmatched_ids", lambda conn, sport: set())
    monkeypatch.setattr(
        ppi, "_remember_unmatched",
        lambda conn, sport, ids: remembered.append(list(ids)) or len(ids))

    first = ppi._basketball(object(), "NBA", dry_run=False)
    assert first["athletes_fetched"] == 2
    assert first["unmatched"] == 2
    assert remembered == [["10", "11"]]
    assert [u for u in calls if re.search(r"/athletes/\d+", u)]

    calls.clear()
    remembered.clear()
    monkeypatch.setattr(ppi, "_cached_unmatched_ids", lambda conn, sport: {"10", "11"})
    second = ppi._basketball(object(), "NBA", dry_run=False)
    assert second["athletes_fetched"] == 0
    assert second["cached_unmatched"] == 2
    assert [u for u in calls if re.search(r"/athletes/\d+", u)] == []
    assert remembered == [[]]


def test_cached_unmatched_ids_drop_out_after_the_window(monkeypatch):
    """A rookie who later has game rows is fetched again once the window
    lapses. Inside it, both ids are skipped."""
    from datetime import datetime, timedelta, timezone

    from data.ingestors import player_positions_ingestor as ppi

    seen = datetime(2026, 10, 1, tzinfo=timezone.utc)

    class Conn:
        def execute(self, sql, params=None):
            class Cur:
                def fetchall(self_inner):
                    return [("10", seen), ("11", seen)]

                def fetchone(self_inner):
                    return None
            return Cur()

    monkeypatch.setattr(ppi, "_relation_exists", lambda conn, name: True)
    inside = seen + timedelta(days=3)
    assert ppi._cached_unmatched_ids(Conn(), "NBA", inside) == {"10", "11"}
    lapsed = seen + timedelta(days=ppi.REFRESH_DAYS + ppi.JITTER_DAYS - 1)
    assert ppi._cached_unmatched_ids(Conn(), "NBA", lapsed) == set()


def test_remember_unmatched_upserts_and_skips_a_missing_table(monkeypatch):
    from data.ingestors import player_positions_ingestor as ppi

    sqls: list[str] = []

    class Conn:
        def execute(self, sql, params=None):
            sqls.append(" ".join(sql.split()))

            class Cur:
                def fetchone(self_inner):
                    return None
            return Cur()

        def commit(self):
            self.committed = True

    conn = Conn()
    monkeypatch.setattr(ppi, "_relation_exists", lambda c, name: False)
    assert ppi._remember_unmatched(conn, "NBA", ["10"]) == 0
    assert sqls == []

    monkeypatch.setattr(ppi, "_relation_exists", lambda c, name: True)
    assert ppi._remember_unmatched(conn, "NBA", ["10", "10", "11"]) == 2
    joined = "\n".join(sqls)
    assert "INSERT INTO player_position_unmatched" in joined
    assert "ON CONFLICT (sport, source_athlete_id)" in joined
    assert conn.committed


def test_the_per_run_cap_stops_a_cold_roster(monkeypatch):
    from data.ingestors import player_positions_ingestor as ppi

    calls = _espn_stub(monkeypatch, ["1", "2", "3", "4", "5"])
    monkeypatch.setattr(ppi, "MAX_ATHLETE_HTTP", 2)
    monkeypatch.setattr(ppi, "_fresh_source_ids", lambda conn, sport: set())
    monkeypatch.setattr(ppi, "_cached_unmatched_ids", lambda conn, sport: set())
    monkeypatch.setattr(ppi, "_remember_unmatched", lambda conn, sport, ids: len(ids))

    stats = ppi._basketball(object(), "NBA", dry_run=False)
    athlete_urls = [u for u in calls if re.search(r"/athletes/\d+", u)]
    assert stats["athletes_fetched"] == 2
    assert stats["deferred_cap"] == 3
    assert stats["cap_hit"] is True
    assert len(athlete_urls) == 2
    assert stats["athlete_http"] == 2
    assert stats["espn_calls"] == len(calls)


def test_fresh_athletes_are_not_fetched(monkeypatch):
    from data.ingestors import player_positions_ingestor as ppi

    calls = _espn_stub(monkeypatch, ["10", "11"])
    monkeypatch.setattr(ppi, "_fresh_source_ids", lambda conn, sport: {"10", "11"})
    monkeypatch.setattr(ppi, "_cached_unmatched_ids", lambda conn, sport: set())
    monkeypatch.setattr(ppi, "_remember_unmatched", lambda conn, sport, ids: 0)

    stats = ppi._basketball(object(), "NBA", dry_run=False)
    assert stats["skipped_fresh"] == 2
    assert stats["athletes_fetched"] == 0
    assert [u for u in calls if re.search(r"/athletes/\d+", u)] == []


def test_january_and_february_use_the_previous_ncaaf_fall(monkeypatch):
    """The daily step used to pass the calendar year, so a January or
    February run asked CFBD for a season that has no games yet. January
    through July belong to the previous fall (2025 runs 2025-08-23 →
    2026-01-20)."""
    import data.db as db
    from data.ingestors import player_positions_ingestor as ppi

    assert ppi.ncaaf_roster_season("2026-01-20") == 2025
    assert ppi.ncaaf_roster_season("2026-02-01") == 2025
    assert ppi.ncaaf_roster_season("2026-07-31") == 2025
    assert ppi.ncaaf_roster_season("2025-08-23") == 2025
    assert ppi.ncaaf_roster_season("2026-08-01") == 2026

    seen: dict = {}

    def fake_ncaaf(conn, season, dry_run):
        seen["season"] = season
        return {"season": season}

    class Conn:
        def close(self):
            self.closed = True

    monkeypatch.setattr(ppi, "_ncaaf", fake_ncaaf)
    monkeypatch.setattr(db, "get_connection", lambda: Conn())
    ppi.ingest_player_positions(sports=["NCAAF"], dry_run=True, run_date="2026-02-01")
    assert seen["season"] == 2025
    ppi.ingest_player_positions(
        sports=["NCAAF"], dry_run=True, run_date="2026-02-01", season=2024)
    assert seen["season"] == 2024

    src = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    assert "ingest_player_positions(dry_run=False, run_date=run_date)" in src


def test_unmatched_cache_migration_is_guarded_and_closed():
    from data.anon_readable import VIEW_BASE_TABLES
    from data.view_migrations import ACTIVE_MIGRATIONS

    mig = ROOT / "data/migrations/add_player_position_unmatched.sql"
    code = mig.read_text(encoding="utf-8")
    sql = "\n".join(ln for ln in code.splitlines() if not ln.lstrip().startswith("--"))
    assert mig.name in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS.index(mig.name) > ACTIVE_MIGRATIONS.index("add_player_positions.sql")
    assert sql.strip().startswith("DO $mig$") and sql.strip().endswith("$mig$;")
    assert "IF to_regclass('public.player_position_unmatched') IS NOT NULL THEN" in code
    assert "PRIMARY KEY (sport, source_athlete_id)" in code
    assert "REVOKE ALL ON public.player_position_unmatched FROM PUBLIC, anon, authenticated;" in code
    assert "ENABLE ROW LEVEL SECURITY" in code
    assert "GRANT " not in sql
    assert "player_position_unmatched" not in VIEW_BASE_TABLES
