"""Every Odds API call is written to api_call_log, however the process started.

WHAT HAPPENED. On 2026-11-03, between 18:06 and 22:30 UTC, about 112,813
credits were spent with almost nothing in api_call_log. The NBA first-quarter
history purchase had been run on mike's PC as a plain module run, through a
launcher that calls `runpy.run_module("data.ingestors.nba_odds_history")`. The
call logger (monitoring/probe.py) was installed only by entrypoints -- the
scheduler, the pipeline, a list of scripts -- so a module run that no
entrypoint started logged nothing at all.

THE FIX. config.py installs the logger on import, and every Odds API caller
imports config or installs it itself. These tests run the real request path
(nba_odds_history's own `Meter.get`, the one the purchase used) in a child
process, with only the network transport and the database stood in for: the
transport answers like the Odds API, and the writer writes to a sqlite file.
No test here sends a request anywhere.
"""
from __future__ import annotations

import ast
import os
import re
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from monitoring import probe, store  # noqa: E402

# What a paid run does. The transport (HTTPAdapter.send) is replaced, so the
# real Session.request, the probe's wrapper and the module's own retry loop all
# run; the database is a sqlite file. Nothing in here installs the logger
# unless the mode says an entrypoint would have.
_FIXTURE = r'''
import os, sqlite3, sys, time

MODE = os.environ["FIXTURE_MODE"]
DB = os.environ["FIXTURE_DB"]

import requests
import requests.adapters
from requests.models import Response

sent = []


def fake_send(self, request, *args, **kwargs):
    if "the-odds-api.com" not in request.url:
        raise RuntimeError(f"fixture: unexpected host {request.url}")
    sent.append(request.url)
    r = Response()
    r.status_code = 200
    r._content = b"[]"
    r.encoding = "utf-8"
    r.headers["Content-Type"] = "application/json"
    r.headers["Content-Length"] = "2"
    r.headers["x-requests-last"] = "3"
    r.headers["x-requests-used"] = "1000"
    r.headers["x-requests-remaining"] = "4000000"
    r.url = request.url
    r.request = request
    return r


requests.adapters.HTTPAdapter.send = fake_send

import data.db
from monitoring import store

blips = [int(os.environ.get("FIXTURE_DB_FAILS", "0"))]


class Conn:
    def __init__(self):
        self.c = sqlite3.connect(DB, check_same_thread=False)

    def executemany(self, sql, rows):
        self.c.executemany(sql, [tuple(v.isoformat() if hasattr(v, "isoformat") else v
                                       for v in r) for r in rows])

    def execute(self, sql, params=()):
        return self.c.execute(sql, params)

    def commit(self):
        self.c.commit()

    def rollback(self):
        self.c.rollback()

    def close(self):
        self.c.close()


def connect(*a, **k):
    if MODE == "db_down":
        raise OSError("fixture: the database is unreachable")
    if blips[0] > 0:
        blips[0] -= 1
        raise OSError("fixture: a database blip")
    return Conn()


data.db.get_connection = connect
store.ensure_table = lambda conn: None

if MODE == "worker_first":
    # scheduler.main() installs before it runs a job in-process.
    from monitoring.probe import install
    install("scheduler")
if MODE == "worker_late":
    # scheduler.py imports config at the top, then main() installs.
    import config  # noqa: F401
    from monitoring.probe import install
    install("scheduler")

from data.ingestors import nba_odds_history as H

r = H.Meter(ceiling=10, floor=0).get(f"{H.BASE}/events",
                                     {"date": "2026-01-15T12:00:00Z"})
assert r.status_code == 200 and r.json() == [], r
assert len(sent) == 1, sent

if MODE == "retry":
    # The process lives on, as a purchase does, while the database comes back.
    deadline = time.time() + 15
    while time.time() < deadline:
        with sqlite3.connect(DB) as c:
            if c.execute("SELECT count(*) FROM api_call_log").fetchone()[0]:
                break
        time.sleep(0.05)
print("MAIN_DONE", flush=True)
'''

_LAUNCHER = r'''
import runpy, sys
mod = sys.argv[1]
sys.argv = [mod] + sys.argv[2:]
runpy.run_module(mod, run_name="__main__", alter_sys=True)
'''

_COLS = ", ".join(store.INSERT_COLUMNS)


def _run(tmp_path, mode, *, how="module", env_extra=None, timeout=90):
    db = tmp_path / "api_call_log.sqlite"
    with sqlite3.connect(db) as c:
        c.execute(f"CREATE TABLE IF NOT EXISTS api_call_log ({_COLS})")
    (tmp_path / "paid_call_fixture.py").write_text(_FIXTURE, encoding="utf-8")
    (tmp_path / "launcher.py").write_text(_LAUNCHER, encoding="utf-8")
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("API_LOG_") and k != "PIPELINE_TELEMETRY"}
    # Sentinels, never a real database or key: config loads .env without
    # overriding, so a child whose stand-in failed fails to resolve instead of
    # writing to production, and the key it sends is one nobody holds.
    env.update({
        "DATABASE_URL": "postgresql://odds-call-log-test.invalid:1/none",
        "ODDS_API_KEY": "SECRET-TEST-KEY",
        "PYTHONPATH": str(ROOT),
        "PYTHONIOENCODING": "utf-8",
        "FIXTURE_MODE": mode,
        "FIXTURE_DB": str(db),
        "API_LOG_FLUSH_SEC": "0.05",
        "API_LOG_EXIT_WAIT_SEC": "1",
        **(env_extra or {}),
    })
    if how == "module":
        cmd = [sys.executable, "-m", "paid_call_fixture"]
    else:
        cmd = [sys.executable, "launcher.py", "paid_call_fixture"]
    started = time.time()
    proc = subprocess.run(cmd, cwd=str(tmp_path), env=env, capture_output=True,
                          text=True, encoding="utf-8", timeout=timeout)
    took = time.time() - started
    assert proc.returncode == 0, proc.stderr[-3000:]
    assert "MAIN_DONE" in proc.stdout, proc.stdout[-2000:] + proc.stderr[-2000:]
    with sqlite3.connect(db) as c:
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute("SELECT * FROM api_call_log")]
    return rows, proc, took


def _assert_one_odds_row(rows, source):
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["api"] == "The Odds API" and row["host"] == "api.the-odds-api.com"
    assert row["source"] == source
    assert row["status"] == 200 and row["ok"] == 1
    assert float(row["credits"]) == 3.0                    # x-requests-last
    assert float(row["quota_remaining"]) == 4000000.0      # x-requests-remaining
    assert row["sport"] == "NBA"
    assert row["path"].startswith("/v4/historical/sports/basketball_nba/events")
    assert "SECRET" not in repr(row)


# ── the hole: a run no entrypoint started ────────────────────────────────────

def test_a_direct_module_run_logs_its_odds_api_call(tmp_path):
    """`python -m <module>` with no install() anywhere: one row, named for
    the module."""
    rows, _, _ = _run(tmp_path, "plain", how="module")
    _assert_one_odds_row(rows, "paid_call_fixture")


def test_a_runpy_launcher_run_logs_its_odds_api_call(tmp_path):
    """The 2026-11-03 shape: a launcher calls runpy.run_module(...,
    alter_sys=True). One row, named for the module it ran."""
    rows, _, _ = _run(tmp_path, "plain", how="runpy")
    _assert_one_odds_row(rows, "paid_call_fixture")


# ── the worker: still exactly one ────────────────────────────────────────────

@pytest.mark.parametrize("mode", ["worker_first", "worker_late"])
def test_the_worker_path_still_logs_exactly_one_row(tmp_path, mode):
    """An entrypoint that installs the logger itself -- before config is
    imported, or after -- keeps its own source name and logs each call once."""
    rows, _, _ = _run(tmp_path, mode, how="module")
    _assert_one_odds_row(rows, "scheduler")


# ── a failed log write never breaks the call ─────────────────────────────────

def test_a_database_that_never_answers_never_breaks_the_call(tmp_path):
    """The call returns its answer, the process exits cleanly and on time, and
    its own log says what api_call_log did not get."""
    rows, proc, took = _run(tmp_path, "db_down", how="module")
    assert rows == []
    assert took < 30, f"the process took {took:.1f}s"
    assert "not written" in proc.stderr and "3 Odds API credit" in proc.stderr, (
        proc.stderr[-2000:])


def test_a_failed_write_is_kept_and_written_later(tmp_path):
    """Two failed connects, then the database answers: the row is written
    once -- not dropped, not twice."""
    rows, proc, _ = _run(tmp_path, "retry", how="module",
                         env_extra={"FIXTURE_DB_FAILS": "2"})
    _assert_one_odds_row(rows, "paid_call_fixture")
    assert "write failed" in proc.stderr, proc.stderr[-2000:]


def test_a_failing_recorder_never_breaks_the_call(monkeypatch):
    """In-process: the recorder itself raising must not reach the caller."""
    import http.server
    import threading

    import requests

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert getattr(requests.sessions.Session.request, probe._MARK, False)

        def boom(*a, **k):
            raise RuntimeError("the log write failed")

        monkeypatch.setattr(probe, "record", boom)
        monkeypatch.setattr(probe, "_credits_from", boom)
        r = requests.get(f"http://127.0.0.1:{srv.server_address[1]}/x", timeout=5)
        assert r.status_code == 200 and r.text == "ok"
    finally:
        srv.shutdown()
        probe._drain(max_rows=probe._MAX_QUEUE)


# ── every caller is covered ──────────────────────────────────────────────────
# A module that builds an Odds API request must leave the logger installed
# once it is imported -- through config, or by installing it itself where it
# reads the key from the environment. Checked by importing each one in a
# fresh process, not by reading its source: an import chain is what decides.

_ODDS_URL = re.compile(r"api\.the-odds-api\.com|ODDS_API_BASE")
_SKIP_PARTS = {"tests", "graphify-out", ".git", "node_modules", "__pycache__",
               ".claude", "mobile"}
# Not callers: the base URL's definition, the host table, and a report that
# only reads api_call_log (its one mention of the host is in a WHERE clause).
_NOT_CALLERS = {"config.py", "monitoring/registry.py", "scripts/pipeline_report.py"}


def _odds_callers() -> list[tuple[str, str, str]]:
    """(relative path, module name, cwd) for every file that builds an Odds
    API request. nfl/ runs with cwd=nfl/ (scheduler.py), so its modules are
    imported from there, with the repo root NOT on the path."""
    out = []
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if _SKIP_PARTS & set(rel.split("/")[:-1]) or rel in _NOT_CALLERS:
            continue
        try:
            src = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if not _ODDS_URL.search(src):
            continue
        if rel.startswith("nfl/"):
            mod, cwd = rel[len("nfl/"):].removesuffix(".py").replace("/", "."), "nfl"
        else:
            mod, cwd = rel.removesuffix(".py").replace("/", "."), "."
        out.append((rel, mod, cwd))
    return out


_CHECK = (
    "import importlib, sys\n"
    "importlib.import_module(sys.argv[1])\n"
    "p = sys.modules.get('monitoring.probe')\n"
    "print('INSTALLED' if p is not None and p.stats()['installed'] else 'NOT_INSTALLED')\n"
)


def test_the_caller_list_is_not_empty():
    """The scan below would pass vacuously if the pattern stopped matching."""
    found = {rel for rel, _, _ in _odds_callers()}
    for must in ("data/ingestors/odds_ingestor.py", "data/ingestors/nba_odds_history.py",
                 "data/ingestors/ncaab_odds_history.py", "nfl/data_ingest/odds_api.py",
                 "nfl_live_leader/odds.py", "ncaaf_live/feeds/odds_live.py"):
        assert must in found, must


def test_every_odds_api_caller_installs_the_logger_on_import():
    callers = _odds_callers()
    env = {k: v for k, v in os.environ.items()
           if k not in ("PYTHONPATH", "PIPELINE_TELEMETRY") and not k.startswith("API_LOG_")}
    env.update({"DATABASE_URL": "postgresql://odds-call-log-test.invalid:1/none",
                "PYTHONIOENCODING": "utf-8"})

    def check(item):
        rel, mod, cwd = item
        proc = subprocess.run([sys.executable, "-c", _CHECK, mod],
                              cwd=str(ROOT / cwd), env=env, capture_output=True,
                              text=True, encoding="utf-8", timeout=180)
        return rel, proc

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(check, callers))
    missing = [f"{rel}: {proc.stdout.strip()[-200:]} {proc.stderr.strip()[-300:]}"
               for rel, proc in results if "INSTALLED" not in proc.stdout.split()]
    assert not missing, (
        "these modules build Odds API requests but importing them leaves "
        "api_call_log's logger uninstalled:\n" + "\n".join(missing))


# ── the suite itself ─────────────────────────────────────────────────────────

def test_the_test_suite_never_writes_to_the_call_log():
    """conftest installs the logger with no writer before config can, so a
    pytest run on a machine whose .env names production writes nothing."""
    # The source is not checked: the probe's own tests rename it.
    s = probe.stats()
    assert s["installed"]
    assert s["writer_wanted"] is False and s["writer"] is False


def test_a_pytest_process_never_arms_the_writer(tmp_path):
    """The subproject suites (ncaaf_live/tests, nfl/live_model/tests) have no
    conftest that installs first, so config's own install has to know it is
    inside pytest. Checked in a fresh process with pytest imported."""
    env = {k: v for k, v in os.environ.items()
           if k != "PIPELINE_TELEMETRY" and not k.startswith("API_LOG_")}
    env.update({"DATABASE_URL": "postgresql://odds-call-log-test.invalid:1/none",
                "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"})
    code = ("import pytest, config\n"
            "from monitoring import probe\n"
            "s = probe.stats()\n"
            "print('WANTED' if s['writer_wanted'] else 'NOT_WANTED', s['source'])\n")
    proc = subprocess.run([sys.executable, "-c", code], cwd=str(tmp_path), env=env,
                          capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert proc.stdout.split() == ["NOT_WANTED", "pytest"], proc.stdout


def test_a_test_cannot_reach_the_real_odds_api():
    """A test that forgets to mock fails instead of billing credits."""
    import requests
    with pytest.raises(RuntimeError, match="real request to the Odds API"):
        requests.get("https://api.the-odds-api.com/v4/sports",
                     params={"apiKey": "SECRET"}, timeout=5)
    probe._drain(max_rows=probe._MAX_QUEUE)


def test_config_installs_the_logger_last():
    """config.py's install is its last statement, after every constant, so the
    probe's import can never see a half-built config."""
    tree = ast.parse((ROOT / "config.py").read_text(encoding="utf-8"))
    last = tree.body[-1]
    assert isinstance(last, ast.Try)
    assert "monitoring.probe" in ast.unparse(last)


def test_the_default_source_is_the_module_or_script_name(monkeypatch):
    import types
    main = types.ModuleType("__main__")
    main.__spec__ = types.SimpleNamespace(name="data.ingestors.nba_odds_history")
    monkeypatch.setitem(sys.modules, "__main__", main)
    assert probe._default_source() == "data.ingestors.nba_odds_history"
    main.__spec__ = types.SimpleNamespace(name="monitoring.__main__")
    assert probe._default_source() == "monitoring"
    main.__spec__ = None
    monkeypatch.setattr(sys, "argv", ["C:/x/scripts/probe_ufc_markets.py"])
    assert probe._default_source() == "probe_ufc_markets"
    monkeypatch.setattr(sys, "argv", ["-c"])
    assert probe._default_source() == "unknown"
