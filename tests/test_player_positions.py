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
    index = {norm_player_name("Paolo Banchero"): [("1631094", "ORL")]}
    assert match_to_log("Paolo Banchero", "ORL", index) == "1631094"
    # Accents, suffixes and punctuation normalise the way the WNBA results
    # ingestor already matches ESPN names to nba_api ids.
    index = {norm_player_name("Nikola Jokic"): [("203999", "DEN")]}
    assert match_to_log("Nikola Jokić", None, index) == "203999"


def test_a_shared_name_is_settled_by_team_or_skipped():
    index = {"jalen williams": [("1631114", "OKC"), ("1631116", "DEN")]}
    assert match_to_log("Jalen Williams", "OKC", index) == "1631114"
    assert match_to_log("Jalen Williams", None, index) is None
    assert match_to_log("Jalen Williams", "BOS", index) is None


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
    from data.anon_readable import VIEW_BASE_TABLES
    from data.view_migrations import ACTIVE_MIGRATIONS

    code = MIG.read_text(encoding="utf-8")
    sql = "\n".join(ln for ln in code.splitlines() if not ln.lstrip().startswith("--"))
    assert MIG.name in ACTIVE_MIGRATIONS
    # Read through the security-invoker functions, never a direct .from().
    assert "player_positions" in VIEW_BASE_TABLES
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
