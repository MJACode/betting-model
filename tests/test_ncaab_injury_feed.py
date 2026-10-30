"""NCAAB pre-tip injury feed: parsers, change rows, names, tags, the job.

Fixtures, not the network. The RotoWire rows are the JSON shape returned on
2026-10-30 (the Nov 15 return date is in the fixture so a plain date is
covered; the live rows that day said Subscribers Only). The Covers markup is
the team block from the NCAAB page that day, which listed nobody, plus the
player-row markup measured the same day on Covers' NBA injury page, because
the NCAAB page had zero listed players.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from data.anon_readable import WORKER_ONLY_TABLES
from data.ingestors import ncaab_injury_feed as feed
from data.view_migrations import ACTIVE_MIGRATIONS

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ncaab_injury"
MIGRATION = "add_ncaab_injury_changes_2026_10_30.sql"
NOW = datetime(2026, 11, 1, 16, 0, tzinfo=timezone.utc)
TIP = "2026-11-01T18:00:00+00:00"

REGISTRY = [
    {"espn_id": 2439, "school": "UNLV", "slug": "unlv", "mascot": "Rebels",
     "display_name": "UNLV Rebels", "short_name": "UNLV", "abbreviation": "UNLV",
     "is_d1": True, "alt": []},
    {"espn_id": 150, "school": "Duke", "slug": "duke", "mascot": "Blue Devils",
     "display_name": "Duke Blue Devils", "short_name": "Duke", "abbreviation": "DUKE",
     "is_d1": True, "alt": []},
    {"espn_id": 6, "school": "South Alabama", "slug": "south-alabama", "mascot": "Jaguars",
     "display_name": "South Alabama Jaguars", "short_name": "South Alabama",
     "abbreviation": "USA", "is_d1": True, "alt": []},
]


def _rotowire():
    return (FIXTURE / "rotowire_injury_report.json").read_text(encoding="utf-8")


def _covers():
    return (FIXTURE / "covers_injuries.html").read_text(encoding="utf-8")


class Conn:
    def __init__(self):
        self.calls = []
        self.committed = False

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        return self

    def executemany(self, sql, rows):
        self.calls.append((" ".join(sql.split()), list(rows)))

    def fetchall(self):
        return []

    def commit(self):
        self.committed = True

    def rollback(self):
        self.calls.append(("ROLLBACK", None))


def _listing(**kw) -> feed.Listing:
    base = dict(source="rotowire", team_raw="UNLV", team_query="UNLV",
                player_raw="Terrance Ford", status="Out", injury_type="Knee",
                note=None, return_date=None, vendor_player_id="25899")
    base.update(kw)
    return feed.Listing(**base)


def _open(**kw) -> dict:
    row = feed._resolved(
        _listing(), 2439, "UNLV", "terrance ford", None, "matched")
    row["received_at"] = NOW - timedelta(minutes=10)
    row.update(kw)
    return row


# ── parsers ──────────────────────────────────────────────────────────────────

def test_rotowire_fixture_parses_status_injury_and_drops_the_subscriber_date():
    rows = {r.player_raw: r for r in feed.parse_rotowire(_rotowire())}
    ford = rows["Terrance Ford"]
    assert ford.team_raw == "UNLV"
    assert ford.status == "Questionable"          # Game Time Decision
    assert ford.injury_type == "Concussion"
    assert ford.return_date is None
    assert ford.vendor_player_id == "25899"
    assert rows["Peyton Law"].status == "Out"
    assert rows["Peyton Law"].return_date == "Nov 15"
    assert rows["Peyton Law"].injury_type == "Knee"
    assert rows["Logan Duncomb"].status == "Questionable"


def test_rotowire_rejects_a_non_list():
    with pytest.raises(feed.ParseError):
        feed.parse_rotowire('{"Players": []}')
    with pytest.raises(feed.ParseError):
        feed.parse_rotowire("not json")


def test_covers_fixture_skips_empty_teams_and_keeps_the_note():
    rows = {r.player_raw: r for r in feed.parse_covers(_covers())}
    assert "Abilene Christian" not in " ".join(rows)
    flagg = rows["Cooper Flagg"]
    assert flagg.team_query == "Duke Blue Devils"
    assert flagg.status == "Out" and flagg.injury_type == "Foot"
    assert flagg.return_date == "Tue, Jul 14"
    assert flagg.note == "Flagg is out with a sore foot."
    assert rows["Khaman Maluach"].status == "Questionable"
    assert rows["Khaman Maluach"].injury_type == "Ankle"


def test_covers_without_a_team_block_is_a_parse_error_not_zero_rows():
    with pytest.raises(feed.ParseError):
        feed.parse_covers("<html>blocked</html>")


def test_an_unknown_status_is_stored_as_printed():
    status, injury = feed.classify_status("Limited", "Hamstring")
    assert status == "Limited" and injury == "Hamstring"
    assert status not in feed.ABSENCE_STATUSES


def test_suspension_is_out_with_that_injury_type():
    status, injury = feed.classify_status("SUSP", "")
    assert status == "Out" and injury == "Suspension"
    assert feed.tag_label(status, injury) == "SUSP"


# ── names: the existing resolvers, plus the override maps, never a guess ────

def test_a_feed_team_resolves_through_the_ncaab_registry():
    espn_id, state = feed.resolve_team("UNLV", REGISTRY, {})
    assert espn_id == 2439 and state == "matched"
    assert feed.school_name(2439, REGISTRY) == "UNLV"


def test_two_teams_for_one_string_resolve_to_nothing():
    twin = json.loads(json.dumps(REGISTRY[1]))
    twin["espn_id"] = 999
    espn_id, state = feed.resolve_team("Duke Blue Devils", REGISTRY + [twin], {})
    assert espn_id is None and state == "team_miss"


def test_the_override_map_is_exact_and_a_missing_school_is_still_a_miss():
    espn_id, state = feed.resolve_team("Mystery", REGISTRY, {"Mystery": 150})
    assert espn_id == 150 and state == "matched"
    assert feed.school_name(150, REGISTRY) == "Duke"
    resolved = feed.resolve_listing(
        _listing(team_raw="Mystery", team_query="Mystery"), REGISTRY, set(),
        {"Mystery": 404}, {})
    assert resolved["match_status"] == "team_miss"
    assert resolved["espn_team_id"] is None and resolved["team"] is None


def test_a_roster_key_matches_and_an_unknown_name_is_not_given_someone_elses():
    key, state = feed.resolve_player("Terrance Ford", 2439, {"terrance ford"}, {})
    assert key == "terrance ford" and state == "matched"
    key, state = feed.resolve_player("Brand New Freshman", 2439, {"terrance ford"}, {})
    assert state == "player_unconfirmed"
    assert key == "brand new freshman"
    assert key != "terrance ford"


def test_a_player_override_is_used_only_when_that_key_is_on_the_roster():
    maps = {"2439|johnny davis": "john davis"}
    key, state = feed.resolve_player("Johnny Davis", 2439, {"john davis"}, maps)
    assert key == "john davis" and state == "matched"
    key, state = feed.resolve_player("Johnny Davis", 2439, {"terrance ford"}, maps)
    assert state == "player_unconfirmed"
    assert key == "johnny davis"


def test_a_team_miss_is_logged_and_left_out_of_the_current_tags():
    resolved = feed.resolve_listing(
        _listing(team_raw="Nope", team_query="Nope", player_raw="Nope Guy"),
        REGISTRY, set(), {}, {})
    assert resolved["match_status"] == "team_miss"
    misses = feed.misses_for([resolved], NOW)
    assert misses[0]["reason"] == "team_miss"
    assert feed.absence_rows([resolved]) == []


# ── change rows, including cleared ───────────────────────────────────────────

def test_the_first_report_is_a_change_and_an_unchanged_reread_is_not():
    resolved = [feed.resolve_listing(_listing(), REGISTRY, {"terrance ford"}, {}, {})]
    changes, opened = feed.diff_report([], resolved, NOW)
    assert len(changes) == 1 and changes[0]["status"] == "Out"
    again, opened2 = feed.diff_report(opened, resolved, NOW + timedelta(minutes=10))
    assert again == []
    assert len(opened2) == 1


def test_a_player_who_leaves_a_non_empty_report_is_cleared():
    previous = [_open()]
    staying = feed.resolve_listing(
        _listing(player_raw="Peyton Law", team_raw="South Alabama",
                 team_query="South Alabama"),
        REGISTRY, set(), {}, {})
    changes, opened = feed.diff_report(previous, [staying], NOW)
    cleared = [c for c in changes if c["status"] == feed.STATUS_CLEARED]
    assert len(cleared) == 1
    assert cleared[0]["player_raw"] == "Terrance Ford"
    assert cleared[0]["team"] == "UNLV"
    assert {r["player_raw"] for r in opened} == {"Peyton Law"}
    assert feed.absence_rows(opened)[0]["player_raw"] == "Peyton Law"


def test_a_zero_player_poll_does_not_clear():
    previous = [_open()]
    changes, opened = feed.diff_report(previous, [], NOW)
    assert changes == []
    assert opened == previous


def test_two_printed_names_on_one_key_are_not_tagged():
    a = _open(player_raw="A Guy")
    b = _open(player_raw="B Guy", status="Questionable")
    assert feed.absence_rows([a, b]) == []


def test_probable_is_not_an_absence_tag():
    row = _open(status="Probable")
    assert feed.absence_rows([row]) == []
    assert feed.tag_label("Probable", None) is None
    assert feed.tag_label("Out", "Injured Reserve") == "IR"
    assert feed.tag_label("Questionable", None) == "Q"


# ── cadence, backoff, game-day alert ─────────────────────────────────────────

def test_rotowire_is_every_ten_minutes_and_every_five_near_a_tip():
    state = feed.PollState("rotowire", last_success_at=NOW - timedelta(minutes=6))
    assert feed.source_due("rotowire", state, NOW, near_tip=False) == "cadence"
    assert feed.source_due("rotowire", state, NOW, near_tip=True) == "poll"
    state.last_success_at = NOW - timedelta(minutes=11)
    assert feed.source_due("rotowire", state, NOW, near_tip=False) == "poll"


def test_covers_is_about_every_thirty_minutes():
    state = feed.PollState("covers", last_success_at=NOW - timedelta(minutes=29))
    assert feed.source_due("covers", state, NOW, near_tip=True) == "cadence"
    state.last_success_at = NOW - timedelta(minutes=30)
    assert feed.source_due("covers", state, NOW, near_tip=False) == "poll"


def test_a_403_or_429_backs_off_and_the_wait_doubles():
    assert feed.backoff_after(1) == timedelta(minutes=10)
    assert feed.backoff_after(2) == timedelta(minutes=20)
    assert feed.backoff_after(8) == timedelta(hours=2)
    state = feed.PollState("rotowire", backoff_until=NOW + timedelta(minutes=5),
                           last_error="HTTP 403")
    assert feed.source_due("rotowire", state, NOW, near_tip=True) == "backoff"


def test_a_game_within_three_hours_is_near_tip_and_a_game_day():
    game_day, near = feed.slate_flags([("2026-11-01", TIP)], NOW)
    assert game_day and near
    later = NOW + timedelta(hours=5)
    game_day, near = feed.slate_flags([("2026-11-01", TIP)], later)
    assert game_day and not near
    game_day, near = feed.slate_flags([], NOW)
    assert not game_day and not near


class Fetch:
    def __init__(self, body="", status=200, error=None):
        self.body, self.status, self.error = body, status, error
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        return feed.FetchResult(self.status, self.body, self.error)


def _wire(monkeypatch, slate, opens=None):
    polls = {}
    opens = opens if opens is not None else {s: [] for s in feed.SOURCES}
    monkeypatch.setattr(feed, "ensure_tables", lambda conn: None)
    monkeypatch.setattr(feed, "load_polls", lambda conn: {
        s: polls.get(s, feed.PollState(s)) for s in feed.SOURCES})
    monkeypatch.setattr(feed, "load_slate", lambda conn, now: slate)
    monkeypatch.setattr(feed, "load_open", lambda conn, source: list(opens.get(source, [])))

    def save_poll(conn, state):
        polls[state.source] = state
    monkeypatch.setattr(feed, "save_poll", save_poll)
    monkeypatch.setattr(feed, "load_roster", lambda conn, espn, seasons: {"terrance ford", "cooper flagg"})
    return polls, opens


def test_a_403_alerts_sets_backoff_and_does_not_clear(monkeypatch):
    previous = [_open()]
    polls, opens = _wire(monkeypatch, [("2026-11-01", TIP)],
                         {"rotowire": previous, "covers": []})
    conn = Conn()
    fetch = Fetch(status=403)
    monkeypatch.setattr(feed, "fetch_url", fetch)
    # Covers is also due (never polled). Give it a player so the fallback can
    # hold the tags while RotoWire is backing off.
    bodies = {feed.ROTOWIRE_URL: ("", 403), feed.COVERS_URL: (_covers(), 200)}

    def fetch_both(url):
        body, status = bodies[url]
        return feed.FetchResult(status, body, None)
    result = feed.run(conn, now=NOW, fetch=fetch_both, registry=REGISTRY)
    assert any("rotowire poll error HTTP 403" in a for a in result.alerts)
    assert polls["rotowire"].backoff_until == NOW + timedelta(minutes=10)
    assert polls["rotowire"].consecutive_failures == 1
    cleared = [c for sql, rows in conn.calls if "ncaab_injury_changes" in sql
               for c in (rows or []) if isinstance(c, dict) and c.get("status") == "cleared"]
    assert cleared == []
    assert any(sql.startswith("DELETE FROM injury_status_current") and params == ("NCAAB",)
               for sql, params in conn.calls)
    assert conn.committed


def test_zero_rows_on_a_game_day_alerts_and_writes_no_clearance(monkeypatch):
    polls, _opens = _wire(monkeypatch, [("2026-11-01", TIP)],
                          {"rotowire": [_open()], "covers": []})
    conn = Conn()
    # The first Covers block in the fixture is a team with nobody listed.
    empty_covers = _covers().split("covers-CoversSeasonInjuries-blockContainer")[0]
    empty_covers += "covers-CoversSeasonInjuries-blockContainer" + _covers().split(
        "covers-CoversSeasonInjuries-blockContainer")[1]

    def fetch_empty(url):
        body = "[]" if url == feed.ROTOWIRE_URL else empty_covers
        return feed.FetchResult(200, body, None)

    result = feed.run(conn, now=NOW, fetch=fetch_empty, registry=REGISTRY)
    assert "rotowire returned 0 rows on a game day" in result.alerts
    assert "covers returned 0 rows on a game day" in result.alerts
    assert not any("ncaab_injury_changes" in sql for sql, _ in conn.calls)
    assert not any("injury_status_current" in sql for sql, _ in conn.calls)
    assert polls["rotowire"].last_row_count == 0


def test_zero_rows_off_a_game_day_is_not_an_alert(monkeypatch):
    _wire(monkeypatch, [])
    conn = Conn()

    def fetch(url):
        body = "[]" if "rotowire" in url else (
            "covers-CoversSeasonInjuries-blockContainer<tbody>No injuries to report.</tbody>")
        return feed.FetchResult(200, body, None)

    july = datetime(2026, 7, 1, 16, 0, tzinfo=timezone.utc)
    result = feed.run(conn, now=july, fetch=fetch, registry=REGISTRY)
    assert result.alerts == []
    assert result.ok


def test_a_rotowire_report_writes_a_change_and_the_ncaab_current_row(monkeypatch):
    _wire(monkeypatch, [("2026-11-01", TIP)])
    conn = Conn()
    body = json.dumps([{
        "ID": "25899", "player": "Terrance Ford", "team": "UNLV",
        "injury": "Concussion", "status": "Out", "rDate": "Nov 15",
    }])

    def fetch(url):
        if url == feed.ROTOWIRE_URL:
            return feed.FetchResult(200, body, None)
        return feed.FetchResult(200, "[]", None)

    # Covers "[]" is a parse error (not HTML). That alerts. Use an empty
    # covers block so the fallback parses and, on a game day, also alerts
    # for zero. This test only needs RotoWire's write. Stub covers as not due
    # by giving it a recent success via the poll store inside _wire... _wire
    # starts empty, so covers is due. Point covers at a one-team empty page
    # and accept its game-day alert; the current row must still be RotoWire's.
    def fetch_ok(url):
        if url == feed.ROTOWIRE_URL:
            return feed.FetchResult(200, body, None)
        page = ("x covers-CoversSeasonInjuries-blockContainer "
                "<div class='covers-CoversMatchups-teamName'><a>Duke<br><span>Blue Devils</span></a></div>"
                "<tbody>No injuries to report.</tbody>")
        return feed.FetchResult(200, page, None)

    result = feed.run(conn, now=NOW, fetch=fetch_ok, registry=REGISTRY)
    assert any("covers returned 0 rows" in a for a in result.alerts)
    changes = [row for sql, rows in conn.calls if "INSERT INTO ncaab_injury_changes" in sql
               for row in rows]
    assert any(r["player_raw"] == "Terrance Ford" and r["status"] == "Out" for r in changes)
    current = [row for sql, rows in conn.calls if "INSERT INTO injury_status_current" in sql
               for row in rows]
    assert current[0]["team"] == "UNLV"
    assert current[0]["player_key"] == "terrance ford"
    assert current[0]["status"] == "Out"
    assert any(sql.startswith("DELETE FROM injury_status_current") for sql, _ in conn.calls)


def test_when_rotowire_fails_covers_sets_the_current_tags(monkeypatch):
    _wire(monkeypatch, [])
    conn = Conn()

    def fetch(url):
        if url == feed.ROTOWIRE_URL:
            return feed.FetchResult(500, "", None)
        return feed.FetchResult(200, _covers(), None)

    off = datetime(2026, 7, 1, 16, 0, tzinfo=timezone.utc)
    result = feed.run(conn, now=off, fetch=fetch, registry=REGISTRY)
    assert any("rotowire poll error HTTP 500" in a for a in result.alerts)
    current = [row for sql, rows in conn.calls if "INSERT INTO injury_status_current" in sql
               for row in rows]
    assert {r["player_raw"] for r in current} == {"Cooper Flagg", "Khaman Maluach"}
    assert all(r["team"] == "Duke" for r in current)


def test_the_second_403_waits_and_does_not_fetch(monkeypatch):
    polls, _opens = _wire(monkeypatch, [])
    polls["rotowire"] = feed.PollState(
        "rotowire", backoff_until=NOW + timedelta(minutes=5), last_error="HTTP 429",
        consecutive_failures=1)
    polls["covers"] = feed.PollState("covers", last_success_at=NOW)
    conn = Conn()
    called = []
    result = feed.run(conn, now=NOW, fetch=lambda url: called.append(url), registry=REGISTRY)
    assert called == []
    assert any("backing off" in a for a in result.alerts)


# ── the before-tip read is tags, and nothing a model imports ────────────────

def test_tags_before_tip_use_the_tip_and_drop_cleared():
    conn = Conn()
    answers = [
        [(TIP, 150, 2439)],
        [
            ("Terrance Ford", "UNLV", "terrance ford", "cleared", None, NOW),
            ("Cooper Flagg", "Duke", "cooper flagg", "Out", "Foot", NOW),
            ("Khaman Maluach", "Duke", "khaman maluach", "Probable", None, NOW),
        ],
    ]

    def execute(sql, params=None):
        conn.calls.append((" ".join(sql.split()), params))
        rows = answers.pop(0)
        return type("R", (), {"fetchall": lambda self: rows})()
    conn.execute = execute
    tags = feed.injury_tags_before_tip(conn, "NCAAB_2026-11-01_unlv_duke")
    game_sql, game_params = conn.calls[0]
    change_sql, change_params = conn.calls[1]
    assert "sport = %s" in game_sql and game_params[1] == "NCAAB"
    assert "received_at <= %s" in change_sql
    assert "DISTINCT ON" in change_sql
    assert change_params[0] == feed._aware(TIP)
    assert tags == [{
        "team": "Duke", "player_key": "cooper flagg", "player_name": "Cooper Flagg",
        "status": "Out", "injury_type": "Foot", "as_of": NOW, "tag": "O",
    }]


def test_a_game_with_no_tip_has_no_tag():
    conn = Conn()

    def execute(sql, params=None):
        return type("R", (), {"fetchall": lambda self: [(None, 150, 2439)]})()
    conn.execute = execute
    assert feed.injury_tags_before_tip(conn, "NCAAB_x") == []


def test_models_do_not_import_the_feed():
    for folder in ("models", "nfl"):
        for path in (ROOT / folder).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "ncaab_injury_feed" not in text, path
            assert "injury_tags_before_tip" not in text, path


# ── migration, current-status SQL, scheduler, probe ─────────────────────────

def test_the_migration_is_active_worker_only_and_names_cleared():
    assert MIGRATION in ACTIVE_MIGRATIONS
    sql = (ROOT / "data" / "migrations" / MIGRATION).read_text(encoding="utf-8")
    assert sql.index("RETURN;") < sql.index("CREATE TABLE")
    assert "status 'cleared'" in sql or "status\n    'cleared'" in sql or "'cleared'" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON public.ncaab_injury_changes FROM anon, authenticated" in sql
    assert "GRANT SELECT" not in sql
    for table in feed._TABLES:
        assert table in WORKER_ONLY_TABLES
        assert f"CREATE TABLE IF NOT EXISTS {table}" in (ROOT / "data" / "ingestors" / "ncaab_injury_feed.py").read_text(encoding="utf-8")
    for column in feed._CHANGE_COLUMNS:
        assert column in sql


def test_a_current_schema_runs_no_ddl(monkeypatch):
    monkeypatch.setattr("data.ddl_guard.schema_is_current", lambda *a, **k: True)
    conn = Conn()
    feed.ensure_tables(conn)
    assert conn.calls == []
    assert not conn.committed


def test_replace_current_is_sport_ncaab_and_skips_an_empty_caller_guard():
    conn = Conn()
    n = feed.replace_current(conn, [_open(received_at=NOW)])
    assert n == 1
    delete, params = conn.calls[0]
    assert delete == "DELETE FROM injury_status_current WHERE sport = %s"
    assert params == ("NCAAB",)
    insert, rows = conn.calls[1]
    assert "INSERT INTO injury_status_current" in insert
    assert "'NCAAB'" in insert
    assert rows[0]["player_key"] == "terrance ford"
    assert rows[0]["status_ts"]


def test_the_job_runs_every_five_minutes_and_raises_the_alert(monkeypatch):
    import inspect
    import scheduler
    from tests.test_nba_prop_window import _fires, _jobs
    from tracking.job_heartbeat import MAX_SILENCE
    job = _jobs(monkeypatch)["ncaab_injury_feed"]
    assert job.name.startswith("NCAAB injury feed")
    assert job.max_instances == 1 and job.coalesce is True
    start = datetime(2026, 11, 5, 2, 0, tzinfo=timezone.utc)
    assert len(_fires(job, start, start + timedelta(minutes=59))) == 12
    assert "ncaab_injury_feed" in scheduler._PIPELINE_JOBS
    assert MAX_SILENCE["ncaab_injury_feed"] == 20
    assert "_publish_new_signals" not in inspect.getsource(scheduler.run_ncaab_injury_feed)

    class Done:
        returncode = 1
        stdout = ""
        stderr = "NCAAB_INJURY_ALERT rotowire returned 0 rows on a game day\n"

    monkeypatch.setattr(scheduler.subprocess, "run", lambda *a, **k: Done())
    with pytest.raises(RuntimeError, match="0 rows on a game day"):
        scheduler.run_ncaab_injury_feed()


def test_the_probe_parses_both_sources_and_the_job_takes_no_args(monkeypatch):
    import scripts.ncaab_injury_probe as probe
    import tracking.job_queue as jq

    def fetch(url):
        body = _rotowire() if "rotowire" in url else _covers()
        return feed.FetchResult(200, body, None)

    assert probe.probe(fetch) == 0
    failed = probe.probe(lambda url: feed.FetchResult(403, "", None))
    assert failed == 1
    assert jq._validate_ncaab_injury_probe({}) == {}
    with pytest.raises(ValueError):
        jq._validate_ncaab_injury_probe({"url": "https://example.com"})
    assert jq.JOBS["ncaab_injury_probe"][0] is jq._job_ncaab_injury_probe


def test_a_healthy_rotowire_is_not_replaced_by_covers(monkeypatch):
    polls, _opens = _wire(monkeypatch, [("2026-11-01", TIP)])
    polls["rotowire"] = feed.PollState(
        "rotowire", last_success_at=NOW - timedelta(minutes=2), last_row_count=4)
    conn = Conn()
    result = feed.run(conn, now=NOW, fetch=lambda url: feed.FetchResult(200, _covers(), None),
                      registry=REGISTRY)
    assert result.alerts == []
    assert not any("injury_status_current" in sql for sql, _ in conn.calls)
    assert any("ncaab_injury_changes" in sql for sql, _ in conn.calls)


def test_the_kill_switch_exits_before_a_connection(monkeypatch):
    monkeypatch.setenv("RUN_NCAAB_INJURY", "0")
    import data.db as db
    monkeypatch.setattr(db, "get_connection", lambda: (_ for _ in ()).throw(AssertionError("connected")))
    assert feed.main() == 0
