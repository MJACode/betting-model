"""The pool size IS the client ceiling in session mode — so don't use it.

Measured 2026-09-06: at `pool_size: 15` the refresh pass lost `odds`,
`prop-odds`, `lineups`, `player-news-refresh` and `nba-prop-odds` to
EMAXCONNSESSION across the evening. `odds` failing means the lines every model
prices against were never fetched.

Supabase's docs: the pool size is shared between the session port (5432) and
the transaction port (6543), and in session mode each client holds a server
connection one-to-one. So session mode cannot serve a workload of dozens of
short independent steps, whatever the pool size is set to.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.db import _transaction_endpoint  # noqa: E402

SESSION = "postgresql://u.proj:pw@aws-1-us-west-2.pooler.supabase.com:5432/postgres"
TXN = "postgresql://u.proj:pw@aws-1-us-west-2.pooler.supabase.com:6543/postgres"


def test_a_supabase_session_url_becomes_the_transaction_url(monkeypatch):
    monkeypatch.delenv("DB_TRANSACTION_POOLER", raising=False)
    assert _transaction_endpoint(SESSION) == TXN


def test_it_is_idempotent(monkeypatch):
    monkeypatch.delenv("DB_TRANSACTION_POOLER", raising=False)
    assert _transaction_endpoint(TXN) == TXN


def test_a_direct_connection_is_left_alone(monkeypatch):
    """Only the POOLER host is understood. Rewriting the port of a database
    this does not recognise would point it at nothing at all."""
    monkeypatch.delenv("DB_TRANSACTION_POOLER", raising=False)
    direct = "postgresql://postgres:pw@db.abcdefgh.supabase.co:5432/postgres"
    assert _transaction_endpoint(direct) == direct


def test_a_local_postgres_is_left_alone(monkeypatch):
    monkeypatch.delenv("DB_TRANSACTION_POOLER", raising=False)
    local = "postgresql://postgres:pw@localhost:5432/betting"
    assert _transaction_endpoint(local) == local


def test_the_escape_hatch_works(monkeypatch):
    """The failure mode of the wrong port is total, so turning this off must
    not need a deploy."""
    monkeypatch.setenv("DB_TRANSACTION_POOLER", "0")
    assert _transaction_endpoint(SESSION) == SESSION


def test_only_the_port_changes(monkeypatch):
    """Credentials, host and database name must survive untouched."""
    monkeypatch.delenv("DB_TRANSACTION_POOLER", raising=False)
    out = _transaction_endpoint(SESSION)
    assert out.replace(":6543", ":5432") == SESSION


def test_the_job_queue_still_gets_session_mode(monkeypatch):
    """get_connection(session_mode=True) must NOT be rewritten: the queue holds
    a session-scoped advisory lock across claiming and running a job, and that
    cannot survive transaction pooling."""
    import inspect

    import data.db

    src = inspect.getsource(data.db.get_connection)
    session_branch = src[src.index("if session_mode:"):src.index("url = os.environ.get(\"DATABASE_URL\", \"\")")]
    assert "_transaction_endpoint" not in session_branch
