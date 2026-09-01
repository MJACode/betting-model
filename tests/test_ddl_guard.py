"""The DDL guard: schema statements must not run on every write.

WHY THIS FILE EXISTS
On 2026-09-01 the Stats tab in the app showed "Connection error" and an empty
board for every sport. Nothing was wrong with the data or the RPCs -- PostgREST
was answering 503 because its schema cache had been invalidated ~3,600 times
and could no longer finish rebuilding inside the 8s statement timeout.

The invalidations came from this repo. Six modules create their own table at
write time and re-ran the whole CREATE/ALTER/REVOKE block on EVERY call, on the
assumption that `IF NOT EXISTS` makes them free. Postgres disagrees: each one
takes a lock and each one fires Supabase's `pgrst_ddl_watch` event trigger.
From pg_stat_statements, on production:

    CREATE INDEX IF NOT EXISTS idx_api_call_ts   1,925 calls  mean 15,082 ms
    ALTER TABLE api_call_log ENABLE ROW LEVEL SECURITY
                                                 1,676 calls  mean  7,797 ms

Every assertion below fails if data/ddl_guard.py's short-circuit is removed --
verified by deleting it, not by assuming.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ddl_guard import schema_is_current   # noqa: E402


# ── a connection that answers the guard's catalog query ──────────────────────

class GuardConn:
    """Records every statement; answers the catalog probe from `state`.

    `state` is (rls_on, columns, indexes, granted_role_count) or None for
    "table does not exist".
    """

    def __init__(self, state=None, raise_on_probe=False):
        self.state = state
        self.raise_on_probe = raise_on_probe
        self.statements: list[str] = []

    def execute(self, sql, params=None):
        probe = "relrowsecurity" in sql
        if not probe:
            self.statements.append(" ".join(sql.split()))
        elif self.raise_on_probe:
            raise RuntimeError("catalog unreadable")

        outer = self

        class C:
            def fetchone(self_inner):
                return outer.state if probe else None

            def fetchall(self_inner):
                return []
        return C()

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


CURRENT = (True, ["a", "b", "dedupe_key", "source"], ["ix_one", "ix_two"], 0)


# ── the guard itself ─────────────────────────────────────────────────────────

def test_guard_is_true_only_when_everything_already_matches():
    c = GuardConn(CURRENT)
    assert schema_is_current(c, "t", columns=("a",), indexes=("ix_one",),
                             rls=True, revoked_from=("anon",)) is True


@pytest.mark.parametrize("state, kwargs", [
    # The table is not there at all.
    (None, {}),
    # RLS is off but the caller wants it on.
    ((False, ["a"], ["ix_one"], 0), {"rls": True}),
    # anon/authenticated still hold a privilege the REVOKE would take away.
    ((True, ["a"], ["ix_one"], 1), {"rls": True, "revoked_from": ("anon",)}),
    # A column the ALTERs would add is missing.
    ((True, ["a"], ["ix_one"], 0), {"columns": ("a", "promoted")}),
    # An index the CREATE INDEX would add is missing.
    ((True, ["a"], ["ix_one"], 0), {"indexes": ("ix_one", "ix_missing")}),
])
def test_guard_is_false_whenever_anything_is_missing(state, kwargs):
    assert schema_is_current(GuardConn(state), "t", **kwargs) is False


def test_guard_fails_open_when_the_catalog_cannot_be_read():
    """SQLite, a shim connection, a role without catalog access — the caller
    must fall back to running its DDL exactly as it did before."""
    assert schema_is_current(GuardConn(CURRENT, raise_on_probe=True), "t") is False


def test_guard_rolls_back_a_failed_probe():
    """A failed statement poisons a Postgres transaction, so every LATER
    statement on the same connection fails too. The probe must not be the thing
    that breaks the caller's write."""
    class C(GuardConn):
        def __init__(self):
            super().__init__(CURRENT, raise_on_probe=True)
            self.rolled_back = 0

        def rollback(self):
            self.rolled_back += 1

    c = C()
    schema_is_current(c, "t")
    assert c.rolled_back > 0


# ── every write-time DDL site goes through it ────────────────────────────────
#
# One case per module. `ensure` runs the module's ensure function; `current` is
# the catalog state under which its block must become a no-op.

def _monitoring(conn):
    from monitoring import store
    store.ensure_table(conn)


def _run_ledger(conn):
    from tracking import run_ledger
    run_ledger._ensure_table(conn)


def _live_calibration(conn):
    from tracking import live_calibration
    live_calibration.persist(conn, {
        "model_id": "m", "sport": "MLB", "computed_at": "2026-09-01T00:00:00Z",
        "verdict": "ok",
    })


def _probability_calibration(conn):
    from models import probability_calibration
    probability_calibration.ensure_schema(conn)


def _job_queue(conn):
    from tracking import job_queue
    job_queue.ensure_schema(conn)


def _dk_direct_feed(conn):
    from data.ingestors import dk_direct_feed
    dk_direct_feed._ensure_schema(conn)


SITES = [
    ("monitoring.store", _monitoring,
     (True, [], ["idx_api_call_ts", "idx_api_call_api_ts"], 0)),
    ("tracking.run_ledger", _run_ledger,
     (True, [], ["idx_pipeline_runs_started", "idx_pipeline_runs_kind"], 0)),
    ("tracking.live_calibration", _live_calibration, (True, [], [], 0)),
    ("models.probability_calibration", _probability_calibration,
     (True, ["applied", "promoted", "promoted_a", "promoted_b", "promoted_at"], [], 0)),
    ("tracking.job_queue", _job_queue,
     (False, ["dedupe_key"], ["worker_jobs_pending_idx", "worker_jobs_dedupe_idx"], 0)),
    ("data.ingestors.dk_direct_feed", _dk_direct_feed,
     (False, ["source"], ["idx_odds_source_inplay"], 0)),
]


def _ddl(statements):
    """The statements that take a lock and invalidate PostgREST's cache."""
    return [s for s in statements
            if s.upper().startswith(("CREATE ", "ALTER ", "REVOKE ", "GRANT "))]


@pytest.mark.parametrize("name, ensure, current", SITES, ids=[s[0] for s in SITES])
def test_no_ddl_when_the_schema_is_already_current(name, ensure, current):
    """The whole point. A database that already has the table must receive
    ZERO lock-taking statements, because each one costs a PostgREST schema
    cache reload and the app gets 503s while it rebuilds."""
    conn = GuardConn(current)
    ensure(conn)
    assert _ddl(conn.statements) == [], (
        f"{name} still issues DDL against an up-to-date schema: "
        f"{_ddl(conn.statements)}"
    )


@pytest.mark.parametrize("name, ensure, current", SITES, ids=[s[0] for s in SITES])
def test_ddl_still_runs_on_a_database_that_needs_it(name, ensure, current):
    """The guard must not be able to skip real work. On a fresh database the
    full block runs exactly as before."""
    conn = GuardConn(None)          # table does not exist
    ensure(conn)
    assert _ddl(conn.statements), f"{name} created nothing on an empty database"


# ── the tripwire ─────────────────────────────────────────────────────────────

def test_every_write_time_lockdown_goes_through_the_guard():
    """Section 1b: a fix that lands in one module and not the other five is how
    this repo accumulates work. Any NEW module that runs RLS/REVOKE DDL at
    write time has to opt into the guard, or this fails.

    encoding="utf-8" is not optional -- read_text() with no encoding uses the
    platform default and raises UnicodeDecodeError on the box this suite
    actually runs on (section 7).
    """
    root = Path(__file__).parent.parent
    skip_dirs = {"tests", "node_modules", ".git", "mobile", "docs", "data/migrations"}
    offenders = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if any(rel.startswith(d) for d in skip_dirs):
            continue
        src = path.read_text(encoding="utf-8", errors="replace")
        if "ENABLE ROW LEVEL SECURITY" not in src:
            continue
        if "schema_is_current" not in src:
            offenders.append(rel)
    assert offenders == [], (
        "these modules run ENABLE ROW LEVEL SECURITY without the DDL guard, so "
        "every call forces a PostgREST schema-cache reload: " + ", ".join(offenders)
    )
