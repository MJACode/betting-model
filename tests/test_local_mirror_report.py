"""The PC copy report (mike, 2026-11-16): one row in Supabase after each
nightly copy, for the ops dashboard's PC copy section.

scripts/local_mirror_report.py reads the copy's own files on mike's PC and
writes one row to public.pc_copy_snapshots
(data/migrations/pc_copy_snapshots_2026_11_16.sql). These tests build a fake
copy folder and read it with the real code; nothing here connects to a
database (tests/test_local_mirror_report_pg.py does, on a scratch Postgres).
The last test runs the real nightly runner, scripts/local_mirror_run.ps1, with
stand-in scripts, where PowerShell exists.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.view_migrations import ACTIVE_MIGRATIONS  # noqa: E402
from scripts import local_mirror_report as rep  # noqa: E402

NAME = "pc_copy_snapshots_2026_11_16.sql"
SQL = (ROOT / "data" / "migrations" / NAME).read_text(encoding="utf-8")
MARK = re.compile(r"pc_copy_snapshots [0-9a-f]{12}")
SCRIPT = ROOT / "scripts" / "local_mirror_report.py"
RUNNER = ROOT / "scripts" / "local_mirror_run.ps1"
UTC = dt.timezone.utc


def _code(sql: str) -> str:
    """The SQL with -- comments removed, so a clause in a comment proves nothing."""
    return "\n".join(line.split("--", 1)[0] for line in sql.splitlines())


CODE = _code(SQL)


# -- the migration --------------------------------------------------------------

def test_the_marker_is_the_hash_of_the_file():
    found = MARK.findall(SQL)
    assert len(found) == 2 and found[0] == found[1], found
    blank = MARK.sub("pc_copy_snapshots " + "0" * 12, SQL)
    want = "pc_copy_snapshots " + hashlib.sha256(blank.encode("utf-8")).hexdigest()[:12]
    assert found[0] == want, f"set the marker to '{want}'"


def test_it_is_one_statement_registered_with_the_database_health_file():
    body = CODE.strip()
    assert body.startswith("DO $mig$") and body.endswith("END $mig$;")
    assert body.count("$mig$") == 2
    assert ACTIVE_MIGRATIONS.count(NAME) == 1
    assert ACTIVE_MIGRATIONS.index(NAME) == ACTIVE_MIGRATIONS.index("db_health_snapshots_2026_11_15.sql") + 1
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"


def test_it_creates_only_its_table_and_writes_no_rows():
    for verb in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "DROP", "GRANT ", "SECURITY DEFINER",
                 "CREATE OR REPLACE FUNCTION", "CREATE OR REPLACE VIEW", "picks"):
        assert verb not in CODE, verb
    assert re.findall(r"CREATE TABLE IF NOT EXISTS public\.(\w+)", CODE) == ["pc_copy_snapshots"]


def test_the_table_is_closed_to_the_app_and_the_skip_reads_the_access_lists():
    assert "ALTER TABLE public.pc_copy_snapshots ENABLE ROW LEVEL SECURITY;" in CODE
    assert "REVOKE ALL ON public.pc_copy_snapshots FROM PUBLIC, anon, authenticated;" in CODE
    assert ("REVOKE ALL ON SEQUENCE public.pc_copy_snapshots_snapshot_id_seq "
            "FROM PUBLIC, anon, authenticated;") in CODE
    skip = CODE[:CODE.index("RETURN;")]
    assert skip.count("aclexplode(") == 2  # the table and sequence, then the columns
    assert skip.count("a.grantee IN (0, 'anon'::regrole, 'authenticated'::regrole)") == 2
    assert "has_table_privilege" not in skip  # an inherited privilege would re-run every pass


def test_every_column_the_report_writes_exists_in_the_migration():
    """A column named in the INSERT and missing from the table fails only in production."""
    block = CODE.split("CREATE TABLE IF NOT EXISTS public.pc_copy_snapshots (", 1)[1].split(");", 1)[0]
    defined = {ln.split()[0] for ln in block.splitlines()
               if ln.strip() and not ln.strip().startswith(("PRIMARY", "CONSTRAINT"))}
    assert set(rep.COLUMNS) <= defined, sorted(set(rep.COLUMNS) - defined)
    assert defined - set(rep.COLUMNS) == {"snapshot_id", "taken_at"}
    named = re.search(r"\((.*?)\) VALUES", rep.INSERT_SQL, re.S).group(1)
    assert [c.strip() for c in named.split(",")] == list(rep.COLUMNS)
    assert rep.INSERT_SQL.count("%s") == len(rep.COLUMNS)


# What production holds: the file as applied on 2026-11-16 at 13:15 UTC.
SHIPPED_COLUMNS = frozenset({
    "snapshot_id", "taken_at", "source", "pass_id", "host", "pass_started_at", "copy_run_id",
    "copy_started_at", "copy_finished_at", "copy_tables", "copy_rows_pulled", "copy_db_seconds",
    "copy_paused_seconds", "copy_this_pass", "failed_tables", "differing_tables", "github_exit",
    "supabase_exit", "duckdb_exit", "github_finished_at", "github_repos", "github_repos_failed",
    "local_tables", "local_rows", "tables_bytes", "schema_bytes", "storage_bytes", "github_bytes",
    "duckdb_bytes", "other_bytes", "total_bytes", "total_files", "disk_total_bytes", "disk_free_bytes",
    "report_ms",
})
SHIPPED_SOURCES = frozenset({"nightly", "manual"})


def test_a_column_or_source_added_later_has_its_own_statement():
    """CREATE TABLE IF NOT EXISTS does nothing to the table production already
    has. A column added to it reaches production only through its own ALTER
    TABLE ... ADD COLUMN IF NOT EXISTS, and a new allowed source only through a
    constraint statement; without one, the next pass runs the file, restamps
    the marker, and the table never changes (the review of #1412)."""
    block = CODE.split("CREATE TABLE IF NOT EXISTS public.pc_copy_snapshots (", 1)[1].split(");", 1)[0]
    defined = {ln.split()[0] for ln in block.splitlines()
               if ln.strip() and not ln.strip().startswith(("PRIMARY", "CONSTRAINT"))}
    for col in sorted(defined - SHIPPED_COLUMNS):
        assert re.search(rf"ADD COLUMN IF NOT EXISTS {col}\b", CODE), f"{col} needs its own ADD COLUMN IF NOT EXISTS"
    sources = set(re.findall(r"'(\w+)'", re.search(r"CHECK \(source IN \(([^)]*)\)\)", CODE).group(1)))
    if sources != SHIPPED_SOURCES:
        assert "DROP CONSTRAINT IF EXISTS pc_copy_snapshots_source" in CODE, "the source check needs re-adding"
    assert set(rep.COLUMNS) | {"snapshot_id", "taken_at"} <= SHIPPED_COLUMNS | (defined - SHIPPED_COLUMNS)


def test_the_writer_only_ever_adds_a_row():
    """CLAUDE.md section 1b: a report row is never updated or deleted."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert rep.INSERT_SQL.startswith("INSERT INTO public.pc_copy_snapshots (")
    assert rep.INSERT_SQL.endswith("ON CONFLICT (source, pass_id) DO NOTHING RETURNING snapshot_id")
    for pattern in (r"\bDELETE\s+FROM\b", r"\bUPDATE\s+[\w.]+\s+SET\b", r"\bDO\s+UPDATE\b", r"\bTRUNCATE\b"):
        assert not re.search(pattern, source, re.I), pattern


# -- reading the copy -----------------------------------------------------------

def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, (bytes, bytearray)):
        path.write_bytes(data)
    else:
        path.write_text(json.dumps(data), encoding="utf-8")


def _manifest(root: Path, table: str, rows: int, local: int | None, server: int | None,
              tail: int = 0, mismatched: int = 0) -> None:
    m = {"table": table, "mode": "full", "rows": rows}
    if local is not None:
        m["last_verify"] = {"at": "2026-11-16T07:00:00+00:00", "local_rows": local,
                            "server_rows_in_copied_ranges": server,
                            "server_rows_past_last_key": tail,
                            "mismatched_chunks": mismatched, "ranges_not_counted_timeout": 0}
    _write(root / "supabase_mirror" / "tables" / table / "manifest.json", m)


@pytest.fixture()
def copy_root(tmp_path):
    root = tmp_path / "betting_local_copies"
    _manifest(root, "public.picks", 100, 100, 100)
    _manifest(root, "public.odds", 500, 500, 497, mismatched=2)
    _manifest(root, "public.player_prop_odds", 900, 900, 900, tail=40)  # newer keys only
    _manifest(root, "public.never_checked", 7, None, None)
    _write(root / "supabase_mirror" / "tables" / "public.picks" / "chunk_0.parquet", b"x" * 1000)
    _write(root / "supabase_mirror" / "schema" / "20261116T055000Z" / "all.sql", b"s" * 30)
    _write(root / "supabase_mirror" / "storage" / "bucket" / "a.png", b"p" * 20)
    _write(root / "supabase_mirror" / "STATE.json", {
        "run_started_at": "2026-11-16T05:58:13+00:00", "run_id": "20261116T055813Z",
        "run_finished_at": "2026-11-16T13:40:00+00:00", "tables": 311,
        "failed_tables": ["public.nfl_research_data_backup"],
        "mismatched_tables": ["public.odds"], "rows_pulled": 23833580,
        "db_seconds": 9000, "paused_seconds": 3053})
    _write(root / "github" / "_mirror_summary.json", {
        "at": "2026-11-16T05:50:00+00:00",
        "repos": [{"repo": "a/b", "git": {"ok": True}}, {"repo": "a/c", "git": {"ok": False}},
                  {"repo": "a/d"}]})
    _write(root / "github" / "MJACode" / "betting-model.git" / "pack", b"g" * 300)
    _write(root / "betting.duckdb", b"d" * 50)
    _write(root / "logs" / "supabase_x.log", b"l" * 7)
    return root


def _row(root: Path, *, source="nightly", pass_id="20261116T054324Z", exits=None):
    return rep.build_row(root, source=source, pass_id=pass_id, host="TESTPC",
                         exits={"github": 1, "supabase": 0, "duckdb": 0} if exits is None else exits,
                         now=dt.datetime(2026, 11, 16, 13, 41, tzinfo=UTC))


def test_the_row_has_exactly_the_written_columns(copy_root):
    assert set(_row(copy_root)) == set(rep.COLUMNS)


def test_only_a_table_whose_check_counted_different_rows_is_listed(copy_root):
    row = _row(copy_root)
    differing = json.loads(row["differing_tables"])
    assert [d["table"] for d in differing] == ["public.odds"]
    assert differing[0]["local_rows"] == 500 and differing[0]["supabase_rows"] == 497
    assert differing[0]["ranges_differ"] == 2
    assert row["local_tables"] == 4 and row["local_rows"] == 100 + 500 + 900 + 7
    assert json.loads(row["failed_tables"]) == ["public.nfl_research_data_backup"]


def test_the_copy_run_is_this_passs_only_when_it_started_after_the_pass(copy_root):
    assert _row(copy_root, pass_id="20261116T054324Z")["copy_this_pass"] is True
    # a pass that started after the last finished run: its own copy did not finish
    assert _row(copy_root, pass_id="20261116T060000Z")["copy_this_pass"] is False
    manual = _row(copy_root, source="manual", pass_id="20261116T134100Z", exits={})
    assert manual["copy_this_pass"] is None and manual["pass_started_at"] is None
    assert manual["github_exit"] is None and manual["supabase_exit"] is None


def test_the_run_and_pass_times_are_read_as_utc(copy_root):
    row = _row(copy_root)
    assert row["pass_started_at"] == dt.datetime(2026, 11, 16, 5, 43, 24, tzinfo=UTC)
    assert row["copy_started_at"] == dt.datetime(2026, 11, 16, 5, 58, 13, tzinfo=UTC)
    assert row["copy_finished_at"] == dt.datetime(2026, 11, 16, 13, 40, tzinfo=UTC)
    assert row["copy_tables"] == 311 and row["copy_rows_pulled"] == 23833580
    assert row["copy_run_id"] == "20261116T055813Z"


def test_each_byte_is_counted_once_under_its_copy(copy_root):
    row = _row(copy_root)
    manifests = sum(p.stat().st_size for p in (copy_root / "supabase_mirror" / "tables").rglob("*.json"))
    assert row["tables_bytes"] == 1000 + manifests
    assert row["schema_bytes"] == 30 and row["storage_bytes"] == 20
    assert row["github_bytes"] == 300 + (copy_root / "github" / "_mirror_summary.json").stat().st_size
    assert row["duckdb_bytes"] == 50
    state = (copy_root / "supabase_mirror" / "STATE.json").stat().st_size
    assert row["other_bytes"] == 7 + state
    parts = sum(row[c] for c in ("tables_bytes", "schema_bytes", "storage_bytes", "github_bytes",
                                 "duckdb_bytes", "other_bytes"))
    assert row["total_bytes"] == parts
    assert row["total_files"] == sum(1 for p in copy_root.rglob("*") if p.is_file())
    assert row["disk_total_bytes"] >= row["disk_free_bytes"] > 0


def test_the_github_copy_counts_every_repository_not_marked_ok_as_failed(copy_root):
    row = _row(copy_root)
    assert row["github_repos"] == 3 and row["github_repos_failed"] == 2
    assert row["github_finished_at"] == dt.datetime(2026, 11, 16, 5, 50, tzinfo=UTC)


def test_an_empty_folder_still_gives_a_row(tmp_path):
    row = _row(tmp_path, exits={"github": 1, "supabase": 3, "duckdb": None})
    assert row["copy_run_id"] is None and row["copy_this_pass"] is False
    assert row["local_tables"] == 0 and json.loads(row["differing_tables"]) == []
    assert row["failed_tables"] is None and row["total_bytes"] == 0


# -- the command ----------------------------------------------------------------

def test_a_nightly_report_needs_the_passs_stamp(capsys):
    assert rep.main(["--source", "nightly", "--dry-run"]) == 2
    assert rep.main(["--source", "nightly", "--pass-id", "tonight", "--dry-run"]) == 2


def test_without_a_database_url_nothing_is_written(copy_root, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    code = rep.main(["--root", str(copy_root), "--env-file", str(tmp_path / "missing.env")])
    assert code == 2
    assert "no row written" in capsys.readouterr().out


@pytest.mark.parametrize("url, kind", [
    # A closed port on this machine: the driver's message names the host and port.
    ("postgresql://pc_copy_user:S3cretPw_not_real@127.0.0.1:1/postgres", "the server refused the connection"),
    # Malformed forms the driver echoes whole, password included (measured 2026-11-16).
    ("postgresql+psycopg2://pc_copy_user:S3cretPw_not_real@127.0.0.1:1/postgres",
     "DATABASE_URL is not a valid address"),
    ("postgresql:/pc_copy_user:S3cretPw_not_real@127.0.0.1:1/postgres", "DATABASE_URL is not a valid address"),
    ("postgres//pc_copy_user:S3cretPw_not_real@127.0.0.1:1/postgres", "DATABASE_URL is not a valid address"),
])
def test_a_failed_write_prints_no_part_of_the_address(copy_root, tmp_path, monkeypatch, capsys, url, kind):
    """Real driver errors, through the report's own main(): never a password,
    user, host or port. (Under the test suite's connection guard, two of the
    malformed forms are refused by the guard before the driver sees them; the
    next test names each kind from the driver's own error.)"""
    pytest.importorskip("psycopg2")
    env = tmp_path / ".env"
    env.write_text(f"DATABASE_URL={url}\n", encoding="utf-8")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(rep.time, "sleep", lambda s: None)  # the retries, without the wait
    assert rep.main(["--root", str(copy_root), "--env-file", str(env)]) == 3
    out = capsys.readouterr().out
    for secret in ("S3cretPw_not_real", "pc_copy_user", "127.0.0.1", "port 1"):
        assert secret not in out, (secret, out)
    assert "no row written: " in out


@pytest.mark.parametrize("url, kind", [
    ("postgresql+psycopg2://pc_copy_user:S3cretPw_not_real@127.0.0.1:1/postgres",
     "ProgrammingError: DATABASE_URL is not a valid address"),
    ("postgresql:/pc_copy_user:S3cretPw_not_real@127.0.0.1:1/postgres",
     "ProgrammingError: DATABASE_URL is not a valid address"),
    ("postgres//pc_copy_user:S3cretPw_not_real@127.0.0.1:1/postgres",
     "ProgrammingError: DATABASE_URL is not a valid address"),
])
def test_the_kind_of_failure_is_named_from_the_drivers_own_error(url, kind):
    psycopg2 = pytest.importorskip("psycopg2")
    with pytest.raises(psycopg2.Error) as caught:
        psycopg2.extensions.parse_dsn(url)  # the driver's own check, no connection
    assert "S3cretPw_not_real" in str(caught.value)  # what the old message printed
    assert rep.describe_failure(caught.value) == kind


def test_a_refused_connection_is_named_without_its_host_or_port():
    psycopg2 = pytest.importorskip("psycopg2")
    with pytest.raises(psycopg2.OperationalError) as caught:
        psycopg2.connect("host=127.0.0.1 port=1 user=pc_copy_user dbname=postgres connect_timeout=5")
    assert "127.0.0.1" in str(caught.value)
    said = rep.describe_failure(caught.value)
    assert said == "OperationalError: the server refused the connection", said


def test_a_one_table_run_by_hand_is_not_the_passs_copy(copy_root):
    """A run with --only rewrites STATE.json too. Started after the pass, it
    would otherwise pass for the night's copy."""
    _write(copy_root / "supabase_mirror" / "STATE.json", {
        "run_started_at": "2026-11-16T06:00:00+00:00", "run_id": "20261116T060000Z",
        "run_finished_at": "2026-11-16T06:04:00+00:00", "tables": 1,
        "failed_tables": [], "mismatched_tables": [], "rows_pulled": 3820})
    row = _row(copy_root, pass_id="20261116T054324Z")
    assert row["copy_tables"] == 1 and row["copy_this_pass"] is False
    assert rep.is_whole_run(311, 316) and not rep.is_whole_run(1, 316) and not rep.is_whole_run(None, 316)


def _logs(root: Path, *stamps: str) -> None:
    for s in stamps:
        _write(root / "logs" / f"supabase_{s}.log", b"log")


def _state(root: Path, start: str, end: str | None, tables: int) -> None:
    _write(root / "supabase_mirror" / "STATE.json", {
        "run_started_at": start, "run_id": "x", "run_finished_at": end, "tables": tables,
        "failed_tables": [], "mismatched_tables": [], "rows_pulled": 10})


NOW = dt.datetime(2026, 11, 17, 5, 31, tzinfo=UTC)


def test_catch_up_writes_the_previous_pass_when_its_whole_copy_finished(copy_root):
    _logs(copy_root, "20261115T053002Z", "20261116T054324Z")
    _state(copy_root, "2026-11-16T05:49:44+00:00", "2026-11-16T16:20:00+00:00", 4)
    row, why = rep.catch_up_row(copy_root, before="20261117T053005Z", host="PC", now=NOW)
    assert row is not None, why
    assert row["source"] == "nightly" and row["pass_id"] == "20261116T054324Z"
    assert row["copy_this_pass"] is True
    assert row["github_exit"] is None and row["supabase_exit"] is None and row["duckdb_exit"] is None


@pytest.mark.parametrize("start, end, tables, why", [
    ("2026-11-16T05:49:44+00:00", None, 4, "has finished"),          # its copy never finished
    ("2026-11-15T05:35:00+00:00", "2026-11-15T13:00:00+00:00", 4, "has finished"),  # an older run
    ("2026-11-16T06:10:00+00:00", "2026-11-16T06:14:00+00:00", 1, "not a pass's copy"),  # a run by hand
    ("2026-11-17T05:31:00+00:00", "2026-11-17T05:35:00+00:00", 4, "has finished"),  # started in this pass
])
def test_catch_up_writes_nothing_without_a_finished_whole_copy_from_that_pass(copy_root, start, end, tables, why):
    _logs(copy_root, "20261116T054324Z")
    _state(copy_root, start, end, tables)
    row, reason = rep.catch_up_row(copy_root, before="20261117T053005Z", host="PC", now=NOW)
    assert row is None and why in reason, reason


def test_catch_up_with_no_earlier_pass_writes_nothing(copy_root):
    row, reason = rep.catch_up_row(copy_root, before="20261117T053005Z", host="PC", now=NOW)
    assert row is None and "no earlier pass" in reason
    assert rep.main(["--root", str(copy_root), "--catch-up", "--before", "20261117T053005Z"]) == 0


class _Conn:
    def close(self):
        pass


def test_a_connection_error_is_tried_again_and_the_row_still_lands(monkeypatch):
    psycopg2 = pytest.importorskip("psycopg2")
    calls, pauses = [], []

    def connect(url):
        calls.append(url)
        if len(calls) < 3:
            raise psycopg2.OperationalError("server closed the connection unexpectedly")
        return _Conn()

    monkeypatch.setattr(rep, "connect", connect)
    monkeypatch.setattr(rep, "insert_row", lambda conn, row: 7)
    assert rep.write_with_retries("postgresql://x", {}, sleep=pauses.append) == 7
    assert len(calls) == 3 and pauses == [30.0, 60.0]


def test_a_database_that_stays_away_fails_the_report_and_a_wrong_statement_is_not_retried(monkeypatch):
    psycopg2 = pytest.importorskip("psycopg2")
    calls = []

    def away(url):
        calls.append(url)
        raise psycopg2.OperationalError("could not connect to server")

    monkeypatch.setattr(rep, "connect", away)
    with pytest.raises(psycopg2.OperationalError):
        rep.write_with_retries("postgresql://x", {}, sleep=lambda s: None)
    assert len(calls) == 3

    calls.clear()
    monkeypatch.setattr(rep, "connect", lambda url: calls.append(url) or _Conn())

    def wrong(conn, row):
        raise psycopg2.ProgrammingError("column \"nope\" does not exist")

    monkeypatch.setattr(rep, "insert_row", wrong)
    with pytest.raises(psycopg2.ProgrammingError):
        rep.write_with_retries("postgresql://x", {}, sleep=lambda s: None)
    assert len(calls) == 1


def test_it_runs_isolated_from_the_repo_as_the_task_runs_it(copy_root, tmp_path):
    """The task starts it as `python -I bin\\local_mirror_report.py` from a copy
    outside the repo: it must import nothing from here."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    shutil.copy(SCRIPT, bin_dir / SCRIPT.name)
    out = subprocess.run([sys.executable, "-I", str(bin_dir / SCRIPT.name), "--root", str(copy_root),
                          "--source", "nightly", "--pass-id", "20261116T054324Z",
                          "--github-exit", "1", "--supabase-exit", "0", "--dry-run"],
                         capture_output=True, text=True, timeout=120, cwd=str(tmp_path))
    assert out.returncode == 0, out.stdout + out.stderr
    assert "pass 20261116T054324Z (nightly)" in out.stdout
    assert '"github_exit": 1' in out.stdout and '"copy_this_pass": true' in out.stdout


# -- the nightly runner ---------------------------------------------------------

_STUB = '''import json, os, sys, time
# padding: the runner keeps a refreshed file only when it is over 1000 bytes
{pad}
name = os.path.basename(sys.argv[0])
root = os.environ["STUB_LOG_DIR"]
start = time.time()
time.sleep({sleep})
with open(os.path.join(root, name + ".jsonl"), "a", encoding="utf-8") as fh:
    fh.write(json.dumps({{"argv": sys.argv[1:], "start": start, "end": time.time()}}) + "\\n")
sys.exit({code})
'''


def _run_runner(tmp_path, codes):
    """The real runner, against a throwaway root and a throwaway repo whose
    origin/master holds stand-in scripts. Returns (the finished process, every
    call each stand-in saw, in order)."""
    repo, root, log_dir = tmp_path / "repo", tmp_path / "root", tmp_path / "stub_logs"
    log_dir.mkdir()
    # The GitHub copy runs alongside and is the slowest here, so a report that
    # did not wait for it starts before it ends.
    sleeps = {"local_mirror.py": 1.0, "local_mirror_github.py": 5.0,
              "local_mirror_report.py": 0.0, "local_mirror_duckdb.py": 0.0}
    ps1 = RUNNER.read_text(encoding="utf-8")
    (repo / "scripts").mkdir(parents=True)
    for name, sleep in sleeps.items():
        if f'"{name}"' not in ps1:
            continue  # a step this runner does not have
        (repo / "scripts" / name).write_text(
            _STUB.format(pad="#" * 1100, sleep=sleep, code=codes.get(name, 0)), encoding="utf-8")
    env = {**os.environ, "STUB_LOG_DIR": str(log_dir), "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-q", "-m", "stubs"],
                ["git", "update-ref", "refs/remotes/origin/master", "HEAD"]):
        subprocess.run(cmd, cwd=repo, check=True, env=env, capture_output=True)
    run = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(RUNNER),
                          "-Root", str(root), "-Repo", str(repo)],
                         capture_output=True, text=True, timeout=300, env=env)
    seen = {}
    for p in log_dir.glob("*.jsonl"):
        seen[p.name[:-len(".py.jsonl")]] = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()]
    return run, seen, root


_NEEDS_PS = pytest.mark.skipif(shutil.which("powershell") is None or shutil.which("git") is None,
                               reason="the runner is PowerShell on mike's PC")


@_NEEDS_PS
def test_the_runner_catches_up_first_and_reports_last_with_each_steps_exit_code(tmp_path):
    run, seen, root = _run_runner(tmp_path, {"local_mirror_github.py": 1})
    assert "local_mirror_report" in seen, (run.stdout, run.stderr, sorted(seen))
    calls = seen["local_mirror_report"]
    assert len(calls) == 2, calls
    catch_up, report = calls
    # first, before any copy starts: the previous pass's catch-up
    assert "--catch-up" in catch_up["argv"]
    stamp = catch_up["argv"][catch_up["argv"].index("--before") + 1]
    assert re.fullmatch(r"\d{8}T\d{6}Z", stamp)
    for step in ("local_mirror", "local_mirror_github"):
        assert catch_up["end"] <= seen[step][0]["start"], step
    # last, after every copy has ended: this pass's own row
    args = report["argv"]
    assert args[args.index("--source") + 1] == "nightly"
    assert args[args.index("--pass-id") + 1] == stamp
    assert args[args.index("--github-exit") + 1] == "1"
    assert args[args.index("--supabase-exit") + 1] == "0"
    assert args[args.index("--duckdb-exit") + 1] == "0"
    assert args[args.index("--root") + 1] == str(root)
    for step in ("local_mirror", "local_mirror_github", "local_mirror_duckdb"):
        assert seen[step][0]["end"] <= report["start"], step
    assert run.returncode == 1  # the GitHub stand-in's code; the report's 0 does not hide it


@_NEEDS_PS
def test_a_crashed_step_fails_the_task_and_the_report_gets_its_real_code(tmp_path):
    """A crash ends a step with a negative code (0xC0000005 is -1073741819).
    Ranked as a plain number it is below 0, and the night showed as a success."""
    run, seen, _ = _run_runner(tmp_path, {"local_mirror.py": -1073741819})
    report = seen["local_mirror_report"][-1]["argv"]
    assert report[report.index("--supabase-exit") + 1] == "-1073741819"
    assert run.returncode == 255, (run.returncode, run.stdout, run.stderr)


# -- the run's kind and the schedule (mike, 2026-11-19: "ensure the backup
# schedule and runs are captured in the retool app") ---------------------------

TASK = {"state": "Ready", "next_run_at": "2026-11-20T05:30:00.0000000Z",
        "last_run_at": "2026-11-19T05:30:01.0000000Z", "last_result": 1,
        "triggers": [{"type": "MSFT_TaskDailyTrigger", "start": "2026-11-03T00:30:00",
                      "delay": None, "enabled": True},
                     {"type": "MSFT_TaskLogonTrigger", "start": None, "delay": "PT2M", "enabled": True}]}


@pytest.fixture(autouse=True)
def _no_task_scheduler(monkeypatch):
    """No test reads this machine's Task Scheduler: the real task answers here."""
    monkeypatch.setattr(rep, "read_task", lambda *a, **k: dict(TASK))


def test_the_row_records_the_kind_of_run(copy_root):
    assert _row(copy_root)["copy_kind"] is None, "a run before 2026-11-20 has no kind"
    state = json.loads((copy_root / "supabase_mirror" / "STATE.json").read_text(encoding="utf-8"))
    for kind in ("diff", "full"):
        state["kind"] = kind
        _write(copy_root / "supabase_mirror" / "STATE.json", state)
        assert _row(copy_root)["copy_kind"] == kind
    state["kind"] = "something else"
    _write(copy_root / "supabase_mirror" / "STATE.json", state)
    assert _row(copy_root)["copy_kind"] is None


def test_the_row_records_the_schedule_from_task_scheduler(copy_root):
    s = json.loads(_row(copy_root)["schedule"])
    assert s["task"] == "\\BettingModel\\LocalMirror"
    assert s["next_run_at"] == "2026-11-20T05:30:00.0000000Z" and s["last_result"] == 1
    assert s["triggers"] == [{"type": "daily", "enabled": True, "at": "00:30"},
                             {"type": "sign-in", "enabled": True, "delay": "PT2M"}]
    assert s["last_full"] is None and s["next_full_from"] is None, "no full yet: the next pass runs it"
    _write(copy_root / "supabase_mirror" / "LAST_FULL.json", {
        "run_id": "20261120T053020Z", "run_started_at": "2026-11-20T05:30:20+00:00",
        "run_finished_at": "2026-11-20T09:00:00+00:00", "failed_tables": []})
    s = json.loads(_row(copy_root)["schedule"])
    assert s["last_full"]["run_id"] == "20261120T053020Z"
    assert s["next_full_from"] == "2026-12-01"


def test_a_full_started_on_the_evening_of_the_last_day_belongs_to_that_month():
    """23:30 Eastern on 11-30 is 04:30 UTC on 12-01: the month is Eastern."""
    assert rep.next_full_from({"run_started_at": "2026-12-01T04:30:00+00:00"}) == "2026-12-01"
    assert rep.next_full_from({"run_started_at": "2026-12-15T06:00:00+00:00"}) == "2027-01-01"


def test_a_task_that_cannot_be_read_is_recorded_and_the_row_still_written(copy_root, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("Get-ScheduledTask : No MSFT_ScheduledTask objects found")
    monkeypatch.setattr(rep, "read_task", boom)
    row = _row(copy_root)
    s = json.loads(row["schedule"])
    assert "No MSFT_ScheduledTask" in s["error"]
    assert set(row) == set(rep.COLUMNS)


def test_a_repository_whose_issues_could_not_be_exported_counts_as_failed(copy_root):
    _write(copy_root / "github" / "_mirror_summary.json", {
        "at": "2026-11-19T05:38:10+00:00",
        "repos": [{"repo": "a/b", "git": {"ok": True}},
                  {"repo": "a/c", "git": {"ok": True}, "error": "IncompleteRead(1308424 bytes read)"}]})
    assert _row(copy_root)["github_repos_failed"] == 1
