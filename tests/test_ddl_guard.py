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
    # relrowsecurity is True from 2026-09-04: worker_jobs is one of the three
    # worker-only tables that carry RLS as a second lock behind the revoke, so
    # ensure_schema's guard now asks for it and an "already current" schema has
    # it on. It was False here while the table had no RLS.
    ("tracking.job_queue", _job_queue,
     (True, ["dedupe_key"], ["worker_jobs_pending_idx", "worker_jobs_dedupe_idx"], 0)),
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

# Statements that are NOT free on an object that already exists. Each takes a
# lock, and -- the expensive part, and the one that has nothing to do with how
# long the statement runs -- each fires Supabase's `pgrst_ddl_watch`, so
# PostgREST answers 503 to the whole app while it rebuilds its schema cache.
#
# `CREATE TABLE IF NOT EXISTS` is in this list even though it is genuinely
# cheap to EXECUTE on an existing table (5-7 ms measured on production). Cost
# per statement is the wrong axis: it fired 3,479 times from job_queue and
# 2,360 from monitoring/store, and every one of those was a cache reload.
# Leaving it out is not hypothetical -- the first version of this test omitted
# it, and `tracking/threshold_review.py` (whose DDL is CREATE TABLE and nothing
# else) passed while completely unguarded.
WRITE_TIME_DDL = (
    "CREATE TABLE IF NOT EXISTS",
    "CREATE INDEX IF NOT EXISTS",
    "ADD COLUMN IF NOT EXISTS",
    "ENABLE ROW LEVEL SECURITY",
)

# Modules that carry the statements above but do NOT reach them from a repeated
# write, so there is no cache-reload storm to prevent.
#
# THIS LIST IS THE WEAK POINT OF THIS TEST. Adding an entry is easier than
# adding the guard, so every entry states what was MEASURED, not what was
# assumed -- the call counts are from pg_stat_statements on production,
# 2026-09-01, where every genuinely hot statement was in the thousands. If you
# are here because this test failed, the default answer is the guard; only add
# a line if you have checked the call count and it is a handful.
DDL_GUARD_EXEMPT = {
    # setup_database() runs once against an empty database. 59 statements, none
    # on a write path.
    "data/db_setup.py": "first-time setup, not a write path",
    # One CREATE TABLE per historical pull. odds_history_pulls: 4 calls.
    "data/ingestors/odds_ingestor.py": "per historical pull; 4 calls measured",
    # View definitions applied by a migration step, not by a writer.
    "data/view_migrations.py": "migration step, not a write path",
    # model_artifacts, written once per retrain.
    "models/trainer.py": "per retrain, not a write path",
    # Weekly sweep. model_calibration_sweeps never broke double digits.
    "tracking/model_calibration_agent.py": "weekly sweep; not in the top 100",
    # Manually invoked probes; neither table appears in pg_stat_statements.
    "scripts/dk_freshness_compare.py": "one-off probe script",
    "scripts/live_feed_probe.py": "one-off probe script",
}

SKIP_DIRS = ("tests", "node_modules", ".git", "mobile", "docs", "data/migrations")


def _modules_with_write_time_ddl():
    """(rel_path, source) for every repo module carrying a WRITE_TIME_DDL marker.

    encoding="utf-8" is not optional -- read_text() with no encoding uses the
    PLATFORM default and raises UnicodeDecodeError on the box this suite
    actually runs on (section 7).
    """
    root = Path(__file__).parent.parent
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if any(rel.startswith(d) for d in SKIP_DIRS):
            continue
        src = path.read_text(encoding="utf-8", errors="replace")
        if any(marker in src for marker in WRITE_TIME_DDL):
            yield rel, src


# data/anon_readable.py::lock_down() calls schema_is_current itself and runs the
# revoke + ENABLE RLS only when the catalog says they are needed, so a module
# that calls it IS guarded -- the guard is one indirection away, not absent.
# Recognised here rather than exempting each caller, because an exemption
# pre-approves everything that file later becomes, and because a test that
# rejects the gated helper pushes the next caller towards the ungated
# lock_down_sql(). test_the_lock_down_helper_is_itself_guarded keeps this
# honest.
GUARD_CALLS = ("schema_is_current", "lock_down(")


def _is_guarded(src: str) -> bool:
    return any(call in src for call in GUARD_CALLS)


def test_the_lock_down_helper_is_itself_guarded():
    """GUARD_CALLS treats `lock_down(` as proof a module is guarded, so this is
    the case that keeps that from being a lie. If lock_down ever stops calling
    schema_is_current, every caller silently becomes an unguarded DDL site and
    the offender test above goes on passing."""
    src = (Path(__file__).parent.parent / "data" / "anon_readable.py").read_text(
        encoding="utf-8")
    body = src[src.index("def lock_down(conn"):]
    assert "schema_is_current(" in body, (
        "lock_down() no longer gates on schema_is_current, so every call site "
        "that relies on it now fires ACCESS EXCLUSIVE DDL and a PostgREST "
        "schema-cache reload on every call")
    assert "return ()" in body, (
        "lock_down() must return early WITHOUT executing when the schema is "
        "already current")


def test_every_write_time_ddl_module_goes_through_the_guard():
    """Section 1b: a fix that lands in one module and not the others is how this
    repo accumulates work. Any NEW module that runs lock-taking, cache-busting
    DDL has to either use the guard or justify itself in DDL_GUARD_EXEMPT.
    """
    offenders = [
        rel for rel, src in _modules_with_write_time_ddl()
        if rel not in DDL_GUARD_EXEMPT and not _is_guarded(src)
    ]
    assert offenders == [], (
        "these modules run lock-taking DDL without the guard, so every call "
        "forces a PostgREST schema-cache reload: " + ", ".join(offenders)
    )


def test_the_exemption_list_stays_honest():
    """An exemption naming a file that no longer carries this DDL is a hole
    nobody can see -- it silently pre-approves whatever that path becomes."""
    seen = {rel for rel, _ in _modules_with_write_time_ddl()}
    stale = sorted(rel for rel in DDL_GUARD_EXEMPT if rel not in seen)
    assert stale == [], f"exempted files no longer carry write-time DDL: {stale}"


def test_the_hot_modules_are_guarded_not_exempted():
    """The seven modules the outage was traced to must never be exempted back
    out. An allowlist is easier to append to than a guard is to add, and this is
    the line that makes that shortcut fail."""
    must_guard = (
        "monitoring/store.py",
        "tracking/run_ledger.py",
        "tracking/live_calibration.py",
        "tracking/job_queue.py",
        "tracking/threshold_review.py",
        "models/probability_calibration.py",
        "data/ingestors/dk_direct_feed.py",
    )
    root = Path(__file__).parent.parent
    for rel in must_guard:
        assert rel not in DDL_GUARD_EXEMPT, f"{rel} must be guarded, not exempted"
        src = (root / rel).read_text(encoding="utf-8")
        assert "schema_is_current" in src, f"{rel} lost its DDL guard"
