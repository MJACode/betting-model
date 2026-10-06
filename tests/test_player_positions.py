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
from datetime import datetime
from pathlib import Path

import pytest

from data.ingestors.player_positions_ingestor import (
    FOOTBALL_GROUP,
    EspnClient,
    _upsert,
    basketball_group,
    basketball_season_start,
    coverage_from_games,
    espn_basketball_season,
    ingest_player_positions,
    match_to_log,
    ncaaf_season_or_derived,
    normalize_team,
    parse_athlete,
    parse_cfbd_roster,
    roster_url,
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


def test_the_job_defaults_to_a_dry_run_and_one_sport():
    from tracking.job_queue import JOBS

    _, validate = JOBS["player_positions"]
    assert validate({})["dry_run"] is True
    assert validate({"dry_run": False})["dry_run"] is False
    # One sport per job. Omitting the list is NBA, not every league.
    assert validate({})["sports"] == ["NBA"]
    assert validate({"sport": "wnba"})["sports"] == ["WNBA"]
    assert validate({"sports": ["NCAAF"]})["sports"] == ["NCAAF"]
    with pytest.raises(ValueError):
        validate({"sports": ["NBA", "WNBA"]})
    with pytest.raises(ValueError):
        validate({"sports": ["MLB"]})
    with pytest.raises(ValueError):
        validate({"dry_run": "no"})


# Already worker_jobs rows from #889. Editing declared_jobs.json does not
# change 406072 (running) or 406073 (pending 12:30Z). They stay in the file
# so the dedupe key is not queued again, and they are outside the one-sport
# dry-run rule that governs every declaration after them.
HISTORICAL_PLAYER_POSITION_JOBS = {
    "player-positions-basketball-dry-run-2-2026-10-06",
    "player-positions-ncaaf-2026-10-06",
}


def test_every_declared_player_positions_job_is_a_dry_run():
    """WNBA is not declared (offseason). NCAAF waits on run_after so it
    does not start the moment the NBA ESPN pass ends.

    The two #889 keys are kept and exempt. This branch's NBA dry run and
    the NCAAF dry run at 18:00Z are not.
    """
    jobs = json.loads((ROOT / "jobs/declared_jobs.json").read_text(encoding="utf-8"))
    ours = [j for j in jobs if j["job_type"] == "player_positions"]
    historical = [j for j in ours if j["key"] in HISTORICAL_PLAYER_POSITION_JOBS]
    assert {j["key"] for j in historical} == HISTORICAL_PLAYER_POSITION_JOBS
    current = [j for j in ours if j["key"] not in HISTORICAL_PLAYER_POSITION_JOBS]
    assert len(current) >= 1
    sports = []
    for job in current:
        assert job["args"].get("dry_run") is True, job["key"]
        assert job["args"].get("sports") and len(job["args"]["sports"]) == 1, job["key"]
        sports.append(job["args"]["sports"][0])
    assert "WNBA" not in sports
    assert "player-positions-dry-run-wnba-2026-10-06" not in {j["key"] for j in current}
    nba = next(j for j in current if j["key"] == "player-positions-dry-run-nba-2026-10-06")
    ncaaf = next(j for j in current if j["key"] == "player-positions-dry-run-ncaaf-2026-10-06")
    assert nba["args"]["sports"] == ["NBA"]
    assert "run_after" not in nba
    assert ncaaf["args"]["sports"] == ["NCAAF"]
    # A timezone offset is what enqueue requires. A few hours after a
    # 2026-10-06 morning merge, not the same instant as the NBA job.
    start = datetime.fromisoformat(ncaaf["run_after"])
    assert start.tzinfo is not None
    assert start == datetime.fromisoformat("2026-10-06T18:00:00+00:00")


# ── review fixes: burst, match, coverage, isolation ──────────────────────────

class _Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code = status
        self._body = {} if body is None else body
        self.headers = headers or {}

    def json(self):
        return self._body


def _transport(docs, statuses=None):
    """docs: url → body. statuses: url → HTTP status (default 200)."""
    calls = []
    sleeps = []
    statuses = statuses or {}

    def get(url, headers=None, timeout=None):
        calls.append(url)
        status = statuses.get(url, 200)
        return _Resp(status, docs.get(url), headers=statuses.get(url + "#h"))

    def sleep(seconds):
        sleeps.append(seconds)

    return get, sleep, calls, sleeps


def _client(docs, statuses=None, **kw):
    get, sleep, calls, sleeps = _transport(docs, statuses)
    # Retry-After lives on the response headers, keyed separately.
    headers = kw.pop("headers", {})

    def get_with_headers(url, headers=None, timeout=None):
        calls.append(url)
        status = (statuses or {}).get(url, 200)
        return _Resp(status, docs.get(url), headers=headers_for(url))

    def headers_for(url):
        return headers.get(url, {})

    client = EspnClient(cold=True, pause=0, get=get_with_headers, sleep=sleep,
                        docs=kw.get("cached"), cap=kw.get("cap", 50))
    return client, calls, sleeps


def test_position_ref_is_fetched_once_per_distinct_url():
    """Two athletes, one position document. The $ref is a single HTTP call."""
    pos = "https://sports.core.api.espn.com/v2/positions/5"
    a1 = "https://sports.core.api.espn.com/v2/athletes/1"
    a2 = "https://sports.core.api.espn.com/v2/athletes/2"
    docs = {
        a1: {"id": "1", "displayName": "A", "position": {"$ref": pos}},
        a2: {"id": "2", "displayName": "B", "position": {"$ref": pos}},
        pos: {"abbreviation": "PG"},
    }
    client, calls, _ = _client(docs)
    from data.ingestors.player_positions_ingestor import resolve_person
    first, fetched = resolve_person({"$ref": a1}, client)
    second, _ = resolve_person({"$ref": a2}, client)
    assert fetched is True
    assert first["position"] == "PG" and second["position"] == "PG"
    assert calls.count(pos) == 1
    assert calls.count(a1) == 1 and calls.count(a2) == 1


def test_inline_roster_position_does_not_fetch_the_athlete():
    """A roster item that already carries the position is not a second GET.
    A shared position $ref is still one call, not one per athlete."""
    pos = "https://sports.core.api.espn.com/v2/positions/7"
    docs = {pos: {"abbreviation": "C"}}
    client, calls, _ = _client(docs)
    from data.ingestors.player_positions_ingestor import resolve_person
    roster = [
        {"id": "10", "displayName": "One", "position": {"$ref": pos}},
        {"id": "11", "displayName": "Two", "position": {"abbreviation": "PF"}},
    ]
    people = [resolve_person(item, client) for item in roster]
    assert [p[0]["position"] for p in people] == ["C", "PF"]
    assert all(fetched is False for _, fetched in people)
    assert calls == [pos]


def test_espn_season_year_is_the_nba_end_year_and_the_wnba_calendar_year():
    """2026-10-06 is the NBA 2026-27 season (ESPN 2027). WNBA stays 2026."""
    assert espn_basketball_season("NBA", "2026-10-06") == 2027
    assert espn_basketball_season("NBA", "2026-04-12") == 2026
    assert espn_basketball_season("NBA", "2025-12-15") == 2026
    assert espn_basketball_season("WNBA", "2026-10-06") == 2026
    assert espn_basketball_season("WNBA", "2026-07-25") == 2026
    url, via = roster_url(
        {}, "nba", "1", espn_basketball_season("NBA", "2026-10-06"))
    assert via == "season_path"
    assert "/seasons/2027/teams/1/athletes?limit=200" in url
    wnba, _ = roster_url(
        {}, "wnba", "5", espn_basketball_season("WNBA", "2026-10-06"))
    assert "/seasons/2026/teams/5/athletes?limit=200" in wnba


def test_roster_url_uses_the_team_doc_link_not_the_path_that_404d():
    """worker_jobs 405765: /teams/{id}/athletes 404'd for every team."""
    bare = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/teams/1/athletes?limit=200"
    ref = "http://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/seasons/2026/teams/1/athletes"
    url, via = roster_url({"athletes": {"$ref": ref}}, "nba", "1", 2026)
    assert via == "team_ref"
    assert url.startswith("https://")
    assert "limit=200" in url
    assert url != bare
    assert "/teams/1/athletes?limit=200" not in url or "/seasons/" in url
    fallback, via2 = roster_url({}, "nba", "1", 2026)
    assert via2 == "season_path"
    assert "/seasons/2026/teams/1/athletes" in fallback
    # The derived year, not the job's NCAAF season. 2026-10-06 is 2026-27.
    derived, via3 = roster_url(
        {}, "nba", "1", espn_basketball_season("NBA", "2026-10-06"))
    assert via3 == "season_path"
    assert "/seasons/2027/teams/1/athletes" in derived
    assert fallback != bare
    bumped, _ = roster_url(
        {"athletes": {"$ref": "https://x/athletes?limit=25"}}, "nba", "1", 2026)
    assert "limit=200" in bumped and "limit=25" not in bumped


def test_request_cap_stops_the_sport_with_a_warning():
    docs = {}
    client, calls, _ = _client(docs, cap=2)
    # Three distinct URLs. The third must not leave the machine.
    client.get_json("https://example.test/a")
    client.get_json("https://example.test/b")
    client.get_json("https://example.test/c")
    assert calls == ["https://example.test/a", "https://example.test/b"]
    assert client.aborted_reason is not None
    assert "cap" in client.aborted_reason
    assert client.calls == 2


def test_three_consecutive_403s_stop_the_sport():
    seen = []

    def get(url, headers=None, timeout=None):
        seen.append(url)
        return _Resp(403, {})

    client = EspnClient(cold=True, pause=0, cap=20, get=get, sleep=lambda s: None)
    for i in range(5):
        client.get_json(f"https://example.test/{i}")
    assert len(seen) == 3
    assert client.aborted_reason is not None
    assert "403" in client.aborted_reason


def test_429_backs_off_on_retry_after_then_continues():
    url = "https://example.test/roster"
    n = {"n": 0}

    def get(url, headers=None, timeout=None):
        n["n"] += 1
        if n["n"] == 1:
            return _Resp(429, {}, headers={"Retry-After": "5"})
        return _Resp(200, {"items": []})

    slept = []
    client = EspnClient(cold=True, pause=0, cap=10, get=get, sleep=slept.append)
    body = client.get_json(url)
    assert body == {"items": []}
    assert 5 in slept or 5.0 in slept
    assert client.aborted_reason is None
    assert client.consecutive_block == 0


def test_team_codes_normalize_to_the_log():
    assert normalize_team("NBA", "GS") == "GSW"
    assert normalize_team("NBA", "NO") == "NOP"
    assert normalize_team("NBA", "NY") == "NYK"
    assert normalize_team("NBA", "SA") == "SAS"
    assert normalize_team("NBA", "UTAH") == "UTA"
    assert normalize_team("NBA", "WSH") == "WAS"
    assert normalize_team("WNBA", "CONN") == "CON"
    assert normalize_team("WNBA", "GS") == "GSV"
    assert normalize_team("WNBA", "WSH") == "WAS"
    assert normalize_team("WNBA", "LVA") == "LV"
    assert normalize_team("WNBA", "NYL") == "NY"
    assert normalize_team("WNBA", "COOP") == "COOP"
    assert normalize_team("WNBA", "SPO") == "SPO"
    # Tiebreak uses the normalised code, so ESPN "GS" hits the log's GSW.
    index = {norm_player_name("Stephen Curry"): [("201939", "GSW")]}
    assert match_to_log("Stephen Curry", "GS", index, sport="NBA") == "201939"
    wnba = {norm_player_name("A'ja Wilson"): [("162", "LV", ["LV", "SPO"])]}
    assert match_to_log("A'ja Wilson", "LVA", wnba, sport="WNBA") == "162"


def test_a_unique_name_on_the_wrong_team_is_not_a_match():
    """No game date: a team mismatch cannot be shown to be a prior season."""
    index = {norm_player_name("John Smith"): [("999", "LAL")]}
    how: dict = {}
    assert match_to_log("John Smith", "BOS", index, how) is None
    assert how["method"] == "team_conflict"
    assert match_to_log("John Smith", "LAL", index) == "999"
    # No ESPN team: nothing to conflict with. The Jokic case stays a match.
    assert match_to_log("John Smith", None, index) == "999"


def test_a_summer_mover_matches_under_prior_season_team_change():
    """NBA log ends 2026-04-12. On 2026-10-06 that game is last season.

    The shared-name path would still pick someone. A unique name must too,
    and say it was a prior-season team change.
    """
    assert basketball_season_start("NBA", "2026-10-06") == "2026-10-01"
    index = {norm_player_name("Paul George"): [("202331", "LAC", "2026-04-12")]}
    how: dict = {}
    assert match_to_log(
        "Paul George", "PHI", index, how, sport="NBA", as_of="2026-10-06",
    ) == "202331"
    assert how["method"] == "prior_season_team_change"
    # WNBA is a calendar year: a 2025 game is prior on 2026-10-06.
    assert basketball_season_start("WNBA", "2026-10-06") == "2026-01-01"
    wnba = {norm_player_name("A'ja Wilson"): [("162", "LV", "2025-09-15")]}
    how = {}
    assert match_to_log(
        "A'ja Wilson", "NY", wnba, how, sport="WNBA", as_of="2026-10-06",
    ) == "162"
    assert how["method"] == "prior_season_team_change"


def test_a_team_change_inside_the_current_season_stays_unmatched():
    index = {norm_player_name("Paul George"): [("202331", "PHI", "2026-10-22")]}
    how: dict = {}
    assert match_to_log(
        "Paul George", "LAC", index, how, sport="NBA", as_of="2026-10-25",
    ) is None
    assert how["method"] == "team_conflict"
    # Same calendar year is the WNBA current season, even in October.
    wnba = {norm_player_name("A'ja Wilson"): [("162", "LV", "2026-07-25")]}
    how = {}
    assert match_to_log(
        "A'ja Wilson", "NY", wnba, how, sport="WNBA", as_of="2026-10-06",
    ) is None
    assert how["method"] == "team_conflict"


def test_a_rookie_with_no_history_does_not_inherit_a_veteran():
    """No log row means method none, not the only other id in the index."""
    index = {norm_player_name("John Smith"): [("999", "LAL", "2026-04-12")]}
    how: dict = {}
    assert match_to_log(
        "Brand New", "BOS", index, how, sport="NBA", as_of="2026-10-06",
    ) is None
    assert how["method"] == "none"
    assert match_to_log("Brand New", "BOS", {}) is None


def test_shared_name_team_rule_uses_the_espn_to_log_map():
    """The shared-name team rule compares log codes, not ESPN's spelling.

    Chris Paul on GSW played earlier than the other Chris Paul on LAL. ESPN
    says GS. Without the map, GS matches nobody and the later LAL game wins.
    """
    index = {norm_player_name("Chris Paul"): [
        ("101", "GSW", "2026-01-01"),
        ("202", "LAL", "2026-04-12"),
    ]}
    how: dict = {}
    assert match_to_log("Chris Paul", "GS", index, how, sport="NBA") == "101"
    assert how["method"] == "team"
    for espn, code, pid in (
        ("NO", "NOP", "n1"),
        ("NY", "NYK", "n2"),
        ("SA", "SAS", "n3"),
        ("UTAH", "UTA", "n4"),
        ("WSH", "WAS", "n5"),
    ):
        idx = {norm_player_name("Pat Player"): [
            (pid, code, "2026-01-01"),
            ("other", "LAL", "2026-06-01"),
        ]}
        how = {}
        assert match_to_log("Pat Player", espn, idx, how, sport="NBA") == pid
        assert how["method"] == "team", espn
    wnba = {norm_player_name("A'ja Wilson"): [
        ("162", "LV", "2026-01-01"),
        ("999", "NY", "2026-09-01"),
    ]}
    how = {}
    assert match_to_log("A'ja Wilson", "LVA", wnba, how, sport="WNBA") == "162"
    assert how["method"] == "team"
    # WNBA NY is New York. The NBA map must not turn it into NYK.
    ny = {norm_player_name("Pat Player"): [
        ("1", "NY", "2026-01-01"),
        ("2", "LV", "2026-06-01"),
    ]}
    how = {}
    assert match_to_log("Pat Player", "NY", ny, how, sport="WNBA") == "1"
    assert how["method"] == "team"


def test_coverage_is_player_count_and_games_weighted():
    games = {"a": 10, "b": 5, "c": 3, "d": 2}
    cov = coverage_from_games(games, ["a", "b"])
    assert cov["log_players"] == 4
    assert cov["log_games"] == 20
    assert cov["players_with_position"] == 2
    assert cov["games_with_position"] == 15
    assert cov["player_coverage"] == 0.5
    assert cov["games_coverage"] == 0.75
    assert coverage_from_games({}, [])["player_coverage"] is None


def test_ncaaf_season_is_derived_and_not_only_the_calendar_year():
    assert ncaaf_season_or_derived(2024) == 2024
    assert ncaaf_season_or_derived(None, "2026-10-06") == 2026
    # January bowls belong to the prior fall, not datetime.now().year.
    assert ncaaf_season_or_derived(None, "2027-01-15") == 2026


class _Conn:
    """Enough of DBConnection to prove a failed sport does not poison the next."""

    def __init__(self, fail_sql):
        self.fail_sql = fail_sql
        self.aborted = False
        self.rollbacks = 0
        self.commits = 0
        self.queries = []

    def execute(self, sql, params=None):
        if self.aborted:
            raise RuntimeError("current transaction is aborted")
        self.queries.append(sql)
        if self.fail_sql in sql:
            self.aborted = True
            raise RuntimeError("relation blew up")
        return _Rows([])

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.aborted = False
        self.rollbacks += 1

    def close(self):
        pass


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


def test_one_sports_sql_error_does_not_abort_the_next(monkeypatch):
    # "nba_player_game_log" is a substring of "wnba_player_game_log".
    conn = _Conn(fail_sql="FROM nba_player_game_log")
    calls = []

    def factory(sport):
        calls.append(sport)

        class C:
            aborted_reason = None
            calls = 0
            cache_hits = 0
            mem = {}
            fetched = set()

            def get_json(self, url):
                return {"items": []}

        return C()

    summary = ingest_player_positions(
        sports=["NBA", "WNBA"], dry_run=True, conn=conn,
        client_factory=factory, cache_path=None)
    assert "error" in summary["NBA"]
    assert "error" not in summary["WNBA"]
    assert summary["WNBA"]["teams"] == 0
    assert conn.rollbacks == 1
    assert any("wnba_player_game_log" in q for q in conn.queries)


def test_basketball_dry_run_reports_coverage_duplicates_and_cache(tmp_path):
    """Inline roster, two athletes, one log player. Coverage and duplicate_ids
    land on the summary, and the HTTP cache is what a later run reads."""
    from data.ingestors.player_positions_ingestor import _basketball

    pos = "https://sports.core.api.espn.com/positions/pg"
    team_ref = "https://sports.core.api.espn.com/teams/1"
    roster_ref = "https://sports.core.api.espn.com/seasons/2026/teams/1/athletes?limit=200"
    teams_url = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/teams?limit=50"
    docs = {
        teams_url: {"items": [{"$ref": team_ref}]},
        team_ref: {"id": "1", "abbreviation": "GS",
                   "athletes": {"$ref": roster_ref}},
        roster_ref: {"items": [
            {"id": "10", "displayName": "Stephen Curry",
             "position": {"$ref": pos}},
            {"id": "11", "displayName": "Stephen Curry",
             "position": {"abbreviation": "PG"}},
            {"id": "12", "displayName": "Nobody Rookie",
             "position": {"abbreviation": "C"}},
        ]},
        pos: {"abbreviation": "PG"},
    }
    client, calls, _ = _client(docs, cap=20)
    log_rows = [("201939", "Stephen Curry", "GSW", 70, ["GSW"])]

    class Conn:
        def execute(self, sql, params=None):
            if "nba_player_game_log" in sql:
                return _Rows(log_rows)
            return _Rows([])

        def commit(self):
            raise AssertionError("dry run must not commit")

        def rollback(self):
            pass

    cache = tmp_path / "cache.json"
    stats = _basketball(Conn(), "NBA", True, season=2026, client=client,
                        cache_path=cache)
    assert stats["matched"] == 1
    assert stats["duplicate_ids"] == 1
    assert stats["unmatched"] == 1
    assert stats["athletes_fetched"] == 0
    assert stats["coverage"]["log_players"] == 1
    assert stats["coverage"]["log_games"] == 70
    assert stats["coverage"]["players_with_position"] == 1
    assert stats["coverage"]["games_coverage"] == 1.0
    assert stats["sample"][0]["team"] == "GSW"
    assert stats["written"] == 0
    assert calls.count(pos) == 1
    assert not any(u.endswith("/teams/1/athletes?limit=200") and "/seasons/" not in u
                   for u in calls)
    assert cache.exists()
    saved = json.loads(cache.read_text(encoding="utf-8"))
    assert pos in saved["docs"]
    assert "unmatched" not in saved


def test_ncaaf_maps_the_requested_season_and_the_one_before(monkeypatch):
    from data.ingestors import cfbd_ingestor

    def fake_get(path, **params):
        year = params["year"]
        if year == 2025:
            return [{"id": 7, "firstName": "Old", "lastName": "Hand",
                     "team": "Alabama", "position": "wr"}]
        if year == 2026:
            return [{"id": 7, "firstName": "Old", "lastName": "Hand",
                     "team": "Alabama", "position": "rb"},
                    {"id": 8, "firstName": "New", "lastName": "Kid",
                     "team": "Alabama", "position": "qb"}]
        raise AssertionError(year)

    monkeypatch.setattr(cfbd_ingestor, "_get", fake_get)

    class Conn:
        def execute(self, sql, params=None):
            assert "ncaaf_player_game_log" in sql
            assert 2025 in params[0] and 2026 in params[0]
            return _Rows([("7", 12), ("9", 4)])

        def commit(self):
            raise AssertionError("dry run")

    from data.ingestors.player_positions_ingestor import _ncaaf
    stats = _ncaaf(Conn(), 2026, True)
    assert stats["seasons"] == [2025, 2026]
    assert stats["matched"] == 1
    assert stats["coverage"]["log_players"] == 2
    assert stats["coverage"]["log_games"] == 16
    assert stats["coverage"]["players_with_position"] == 1
    assert stats["coverage"]["games_with_position"] == 12
    # 2026's position wins over 2025's for the same athlete.
    assert stats["sample"][0]["position"] == "RB"


def test_a_real_run_stores_unmatched_athletes_for_the_seven_day_skip():
    """An athlete with no log row is still a row, so the next pass skips him."""
    from data.ingestors.player_positions_ingestor import _basketball

    inserts = []

    class Conn:
        def execute(self, sql, params=None):
            if sql.lstrip().upper().startswith("INSERT"):
                inserts.append(params)
            if "nba_player_game_log" in sql:
                return _Rows([("201939", "Stephen Curry", "GSW", 10, ["GSW"])])
            if "player_positions" in sql and "SELECT" in sql.upper():
                return _Rows([])
            return _Rows([])

        def commit(self):
            self.committed = True

        def rollback(self):
            pass

    client, _, _ = _client({
        "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/teams?limit=50":
            {"items": [{"$ref": "https://sports.core.api.espn.com/teams/1"}]},
        "https://sports.core.api.espn.com/teams/1": {
            "id": "1", "abbreviation": "BOS",
            "athletes": {"$ref": "https://sports.core.api.espn.com/roster?limit=200"},
        },
        "https://sports.core.api.espn.com/roster?limit=200": {"items": [
            {"id": "55", "displayName": "Rookie Nobody",
             "position": {"abbreviation": "SG"}},
        ]},
    }, cap=10)
    conn = Conn()
    stats = _basketball(conn, "NBA", False, season=2026, client=client,
                        cache_path=None)
    assert stats["unmatched"] == 1
    assert stats["written"] == 1
    assert conn.committed
    row = inserts[0]
    assert row[1].startswith("unmatched:")
    assert row[6] == "espn_core_unmatched"
    assert row[7] == "55"


def test_a_tiebreak_guess_does_not_overwrite_a_claimed_id():
    """ESPN team matches neither Bob, so the most recent Bob is a guess.

    That guess is Alice's id. Whichever roster is walked first, the row
    written for that id is Alice's name match, and the collision is
    duplicate_ids. _upsert would otherwise keep whichever INSERT ran last.
    """
    from data.ingestors.player_positions_ingestor import _basketball

    teams_url = ("https://sports.core.api.espn.com/v2/sports/basketball/"
                 "leagues/nba/teams?limit=50")
    bos = "https://sports.core.api.espn.com/teams/1"
    lal = "https://sports.core.api.espn.com/teams/2"
    bos_roster = "https://sports.core.api.espn.com/seasons/2026/teams/1/athletes?limit=200"
    lal_roster = "https://sports.core.api.espn.com/seasons/2026/teams/2/athletes?limit=200"
    log_rows = [
        ("111", "Alice Smith", "BOS", 40, ["BOS"], "2026-04-01"),
        ("222", "Bob Jones", "DEN", 5, ["DEN"], "2026-01-01"),
        ("111", "Bob Jones", "MIA", 8, ["MIA"], "2026-04-20"),
    ]

    def run(order):
        inserts = []

        class Conn:
            def execute(self, sql, params=None):
                if sql.lstrip().upper().startswith("INSERT"):
                    inserts.append(params)
                if "nba_player_game_log" in sql:
                    return _Rows(log_rows)
                return _Rows([])

            def commit(self):
                self.committed = True

            def rollback(self):
                pass

        docs = {
            teams_url: {"items": [{"$ref": ref} for ref in order]},
            bos: {"id": "1", "abbreviation": "BOS",
                  "athletes": {"$ref": bos_roster}},
            lal: {"id": "2", "abbreviation": "LAL",
                  "athletes": {"$ref": lal_roster}},
            bos_roster: {"items": [
                {"id": "9001", "displayName": "Alice Smith",
                 "position": {"abbreviation": "PG"}},
            ]},
            lal_roster: {"items": [
                {"id": "9002", "displayName": "Bob Jones",
                 "position": {"abbreviation": "SF"}},
            ]},
        }
        client, _, _ = _client(docs, cap=20)
        stats = _basketball(Conn(), "NBA", False, season=2026, client=client,
                            cache_path=None)
        return stats, inserts

    for order in ((bos, lal), (lal, bos)):
        stats, inserts = run(order)
        assert stats["duplicate_ids"] == 1, order
        assert stats["matched"] == 1, order
        assert stats["match_method"]["name"] == 1
        assert stats["match_method"]["tiebreak_recent"] == 1
        owned = [p for p in inserts if p[1] == "111"]
        assert len(owned) == 1, order
        assert owned[0][2] == "Alice Smith"
        assert owned[0][4] == "PG"
        assert owned[0][7] == "9001"
        assert all(p[7] != "9002" for p in inserts)


def test_dry_run_counts_a_mover_and_a_current_season_conflict():
    from data.ingestors.player_positions_ingestor import _basketball

    teams_url = ("https://sports.core.api.espn.com/v2/sports/basketball/"
                 "leagues/nba/teams?limit=50")
    team = "https://sports.core.api.espn.com/teams/1"
    roster = "https://sports.core.api.espn.com/seasons/2027/teams/1/athletes?limit=200"
    docs = {
        teams_url: {"items": [{"$ref": team}]},
        team: {"id": "1", "abbreviation": "PHI",
               "athletes": {"$ref": roster}},
        roster: {"items": [
            {"id": "1", "displayName": "Paul George",
             "position": {"abbreviation": "SF"}},
            {"id": "2", "displayName": "In Season",
             "position": {"abbreviation": "PG"}},
        ]},
    }
    log_rows = [
        ("202331", "Paul George", "LAC", 60, ["LAC"], "2026-04-12"),
        ("999", "In Season", "LAL", 10, ["LAL"], "2026-10-04"),
    ]

    class Conn:
        def execute(self, sql, params=None):
            if "nba_player_game_log" in sql:
                return _Rows(log_rows)
            return _Rows([])

        def commit(self):
            raise AssertionError("dry run")

        def rollback(self):
            pass

    client, _, _ = _client(docs, cap=10)
    stats = _basketball(Conn(), "NBA", True, client=client, cache_path=None,
                        as_of="2026-10-06")
    assert stats["espn_season"] == 2027
    assert stats["prior_season_team_change"] == 1
    assert stats["team_conflict"] == 1
    assert stats["match_method"]["prior_season_team_change"] == 1
    assert stats["match_method"]["team_conflict"] == 1
    assert stats["matched"] == 1
    assert stats["unmatched"] == 1
    assert stats["written"] == 0


def test_a_later_match_deletes_the_unmatched_sentinel_before_commit():
    """Same transaction: the DELETE is after the INSERT and before COMMIT."""
    statements = []

    class Conn:
        def execute(self, sql, params=None):
            statements.append((sql.strip().split()[0].upper(), params))

        def commit(self):
            statements.append(("COMMIT", None))

    _upsert(Conn(), [{
        "sport": "NBA", "player_id": "201939", "player_name": "Stephen Curry",
        "team": "GSW", "position": "PG", "pos_group": "G",
        "source": "espn_core", "source_athlete_id": "55",
    }])
    kinds = [s[0] for s in statements]
    assert kinds == ["INSERT", "DELETE", "COMMIT"]
    assert statements[1][1] == ("NBA", "unmatched:55")
    # An unmatched row does not delete itself.
    statements.clear()
    _upsert(Conn(), [{
        "sport": "NBA", "player_id": "unmatched:55", "player_name": "Nobody",
        "team": "BOS", "position": "SG", "pos_group": "G",
        "source": "espn_core_unmatched", "source_athlete_id": "55",
    }])
    assert [s[0] for s in statements] == ["INSERT", "COMMIT"]


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


def test_a_same_name_rookie_inherits_the_prior_season_id():
    """A unique name whose only log game is last season is a summer move
    and a same-name rookie at once. The log has no rookie flag, so the
    id is returned."""
    index = {norm_player_name("John Smith"): [("999", "LAL", "2026-04-12")]}
    how: dict = {}
    assert match_to_log(
        "John Smith", "BOS", index, how, sport="NBA", as_of="2026-10-06",
    ) == "999"
    assert how["method"] == "prior_season_team_change"


def test_basketball_falls_back_to_one_season_url_and_counts_empty_teams():
    """Team-doc $ref first. An empty ref is followed by the single season
    path from espn_basketball_season (2026-10-06 → 2027). A team whose
    every candidate URL lists no athletes is counted. Neighbouring years
    are not requested."""
    from data.ingestors.player_positions_ingestor import _basketball

    teams_url = ("https://sports.core.api.espn.com/v2/sports/basketball/"
                 "leagues/nba/teams?limit=50")
    t1 = "https://sports.core.api.espn.com/teams/1"
    t2 = "https://sports.core.api.espn.com/teams/2"
    empty_ref = "https://sports.core.api.espn.com/roster/empty?limit=200"
    also_empty = "https://sports.core.api.espn.com/roster/also-empty?limit=200"
    season_1 = ("https://sports.core.api.espn.com/v2/sports/basketball/"
                "leagues/nba/seasons/2027/teams/1/athletes?limit=200")
    season_2 = ("https://sports.core.api.espn.com/v2/sports/basketball/"
                "leagues/nba/seasons/2027/teams/2/athletes?limit=200")
    docs = {
        teams_url: {"items": [{"$ref": t1}, {"$ref": t2}]},
        t1: {"id": "1", "abbreviation": "GS",
             "athletes": {"$ref": empty_ref}},
        t2: {"id": "2", "abbreviation": "BOS",
             "athletes": {"$ref": also_empty}},
        empty_ref: {"items": []},
        also_empty: {"items": []},
        season_1: {"items": [
            {"id": "10", "displayName": "Stephen Curry",
             "position": {"abbreviation": "PG"}},
        ]},
        season_2: {"items": []},
    }
    log_rows = [("201939", "Stephen Curry", "GSW", 70, ["GSW"], "2026-04-10")]

    class Conn:
        def execute(self, sql, params=None):
            if "nba_player_game_log" in sql:
                return _Rows(log_rows)
            return _Rows([])

        def commit(self):
            raise AssertionError("dry run")

        def rollback(self):
            pass

    client, calls, _ = _client(docs, cap=20)
    stats = _basketball(Conn(), "NBA", True, client=client, cache_path=None,
                        as_of="2026-10-06")
    assert stats["espn_season"] == 2027
    assert calls.index(empty_ref) < calls.index(season_1)
    assert season_2 in calls
    assert stats["roster_via"] == {"season_path": 1}
    assert stats["teams_all_roster_urls_empty"] == 1
    assert stats["matched"] == 1
    assert stats["sample"][0]["player_id"] == "201939"
    joined = " ".join(calls)
    assert "/seasons/2026/" not in joined
    assert "/seasons/2025/" not in joined
    assert not any(u.endswith("/teams/1/athletes?limit=200") and "/seasons/" not in u
                   for u in calls)
