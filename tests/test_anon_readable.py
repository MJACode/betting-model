"""The read-surface manifest must stay ahead of the app, not behind it.

Once ALTER DEFAULT PRIVILEGES has revoked the default grant, a new table or view
the app reads arrives with NO SELECT -- and that fails silently: PostgREST
answers a permission error, the client folds it into `error`, and the screen
renders empty with nothing in any log near the cause.

This test is the tripwire. It parses every `.from('...')` in mobile/src and
fails if one names a relation the manifest does not, so "somebody forgot the
GRANT" is a red test before the PR opens rather than an empty screen after the
OTA ships.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.anon_readable import ANON_READABLE, AUTHENTICATED_ONLY, all_readable
from scripts.apply_anon_grants import REVOKE_DEFAULT, _plan

MOBILE_SRC = Path(__file__).parent.parent / "mobile" / "src"


def _app_relations() -> set[str]:
    """Every relation mobile/src reads through PostgREST."""
    found: set[str] = set()
    for path in MOBILE_SRC.rglob("*.ts*"):
        src = path.read_text(encoding="utf-8", errors="replace")
        found.update(re.findall(r"\.from\('([a-z_0-9]+)'\)", src))
    return found


def test_every_relation_the_app_reads_is_declared():
    app = _app_relations()
    assert app, "found no .from() calls at all -- the parser is broken, not the app"
    undeclared = sorted(app - set(all_readable()))
    assert not undeclared, (
        f"mobile/src reads {undeclared}, which data/anon_readable.py does not "
        f"declare. After ALTER DEFAULT PRIVILEGES a new relation arrives with "
        f"NO anon SELECT, so this would render an empty screen with no error "
        f"anywhere near the cause. Add it to the manifest and re-run "
        f"`python -m scripts.apply_anon_grants --apply`.")


def test_the_manifest_does_not_grow_stale_entries():
    """A relation nobody reads should not keep a grant. Not fatal -- a screen
    may be mid-build -- but it must be deliberate, so it is asserted."""
    app = _app_relations()
    unused = sorted(set(all_readable()) - app)
    assert not unused, (
        f"{unused} are granted but nothing in mobile/src reads them. Remove "
        f"them from data/anon_readable.py, or add the query that needs them.")


def test_subscriptions_stays_authenticated_only():
    """Billing state must not be readable before sign-in. anon has never held
    SELECT on it; that is the right shape, so it is pinned."""
    assert "subscriptions" in AUTHENTICATED_ONLY
    assert "subscriptions" not in ANON_READABLE


def test_the_default_privilege_revoke_names_the_api_roles_only():
    """service_role must keep its grant -- the edge functions, including every
    billing path, authenticate as it. And REVOKE ... FROM PUBLIC would not
    touch a named role at all."""
    assert "FROM anon, authenticated" in REVOKE_DEFAULT, REVOKE_DEFAULT
    assert "service_role" not in REVOKE_DEFAULT, REVOKE_DEFAULT
    assert "PUBLIC" not in REVOKE_DEFAULT.upper().replace("IN SCHEMA PUBLIC", "")
    assert "IN SCHEMA public" in REVOKE_DEFAULT, REVOKE_DEFAULT
    assert "ON TABLES" in REVOKE_DEFAULT, REVOKE_DEFAULT


def test_the_plan_revokes_before_it_grants():
    """Order matters only for readability, but a plan that granted first and
    revoked after would leave the window open in the same transaction."""
    plan = _plan()
    assert plan[0] == REVOKE_DEFAULT, plan[0]
    assert all(s.startswith("GRANT SELECT") for s in plan[1:]), plan[1:3]


def test_every_declared_relation_is_granted_exactly_once():
    plan = " | ".join(_plan())
    for rel in ANON_READABLE:
        assert f'ON public."{rel}" TO anon, authenticated' in plan, rel
    for rel in AUTHENTICATED_ONLY:
        assert f'ON public."{rel}" TO authenticated' in plan, rel
        assert f'ON public."{rel}" TO anon' not in plan, rel


# ── RPCs ─────────────────────────────────────────────────────────────────────

def _app_rpcs() -> set[str]:
    """Every RPC the app can call, INCLUDING the ones it names at runtime.

    A literal grep for `.rpc('x')` finds 17. Four call sites in queries.ts do

        const fn = sport === 'NFL' ? 'player_window_totals_nfl'
                                   : 'player_window_totals_ncaaf';
        await supabase.rpc(fn, {...})

    so the real surface is 24. Resolving only the literal form is how a sweep
    would silently revoke EXECUTE on the NBA/WNBA/NCAAF/NFL stats functions.
    """
    found: set[str] = set()
    for path in MOBILE_SRC.rglob("*.ts*"):
        src = path.read_text(encoding="utf-8", errors="replace")
        found.update(re.findall(r"\.rpc\('([a-z_0-9]+)'", src))
        # Indirect: rpc(<ident>) -- collect the string literals assigned to that
        # identifier anywhere in the same file.
        for ident in set(re.findall(r"\.rpc\(([A-Za-z_][A-Za-z_0-9]*)\s*,", src)):
            for assign in re.findall(
                    rf"\b{re.escape(ident)}\s*=\s*([^;]+);", src, re.S):
                found.update(re.findall(r"'([a-z_][a-z_0-9]*)'", assign))
    return found


def test_the_dynamic_rpc_resolver_actually_finds_the_ternary_names():
    """Guard the guard. If this regex stops resolving indirect calls it fails
    OPEN -- the surface looks smaller and the sweep gets more aggressive -- so
    the resolver is pinned against names known to be reachable only that way."""
    rpcs = _app_rpcs()
    for only_indirect in ("player_window_totals_ncaaf", "player_recent_games_nfl",
                          "player_season_stat_values_nba"):
        assert only_indirect in rpcs, (
            f"{only_indirect} is reached only through `const fn = ... ? ... : ...` "
            f"and the resolver missed it -- a sweep would now revoke it")


def test_every_rpc_the_app_calls_is_declared_or_known_absent():
    from data.anon_readable import RPC_ANON_CALLABLE, RPC_MISSING_IN_PROD

    known = set(RPC_ANON_CALLABLE) | set(RPC_MISSING_IN_PROD)
    undeclared = sorted(_app_rpcs() - known)
    assert not undeclared, (
        f"mobile/src calls {undeclared}, which data/anon_readable.py does not "
        f"declare. After ALTER DEFAULT PRIVILEGES ... ON FUNCTIONS a new RPC "
        f"404s through PostgREST. Add it to RPC_ANON_CALLABLE and re-run "
        f"`python -m scripts.apply_anon_grants --apply`.")


def test_the_transitive_helper_is_granted():
    """custom_model_picks and custom_model_backtest are SECURITY INVOKER and
    both call _jsonb_text_array, so the CALLER needs EXECUTE on it even though
    the app never names it. Measured in pg_proc, not assumed."""
    from data.anon_readable import RPC_ANON_CALLABLE

    assert "_jsonb_text_array" in RPC_ANON_CALLABLE


def test_the_trigger_function_is_not_swept():
    """log_picks_changes returns `trigger`: PostgREST will not expose it and
    Postgres does not check EXECUTE when a trigger fires. Revoking gains
    nothing and risks the picks_log audit trail."""
    from data.anon_readable import RPC_LEFT_ALONE, RPC_REVOKE

    assert "log_picks_changes" in RPC_LEFT_ALONE
    assert "log_picks_changes" not in RPC_REVOKE


def test_the_function_default_revoke_leaves_sequences_and_service_role_alone():
    from scripts.apply_anon_grants import REVOKE_DEFAULT_FUNCTIONS as R

    assert "ON FUNCTIONS" in R, R
    assert "FROM anon, authenticated" in R, R
    assert "service_role" not in R, R
    assert "SEQUENCES" not in R.upper(), (
        "sequences must not be revoked: tracked_bets.id defaults to nextval() "
        "and anon holds USAGE/UPDATE on that sequence")


def test_the_function_revoke_names_public_as_well_as_the_roles():
    """Postgres grants EXECUTE to PUBLIC by default and anon is a member of
    PUBLIC, so `REVOKE ... FROM anon, authenticated` leaves the function
    callable AND reports success.

    Measured 2026-09-04: the first run of this script revoked
    has_active_subscription from both named roles and anon could still execute
    it -- its ACL carried `=X/postgres`, the empty grantee being PUBLIC. 21 of
    28 public functions carry that grant.
    """
    import inspect as _inspect

    from scripts import apply_anon_grants

    src = _inspect.getsource(apply_anon_grants._function_plan)
    # There are two revokes in this function and they mean different things:
    # one strips PUBLIC from a callable before granting it to the named roles,
    # the other takes a function away entirely. This is about the second, so it
    # matches the full role list rather than the first REVOKE it finds.
    targets = re.findall(r'REVOKE ALL ON FUNCTION \{one\} FROM ([^"]+)"', src)
    assert targets, src
    full = [t for t in targets if "anon" in t]
    assert full, (
        f"no revoke targets anon at all; found {targets!r}. The RPC_REVOKE "
        f"path must remove the named roles as well as PUBLIC.")
    for roles in full:
        assert "PUBLIC" in roles, (
            f"revoke targets {roles!r} -- without PUBLIC the function stays "
            f"callable and the run still reports success")
        assert "authenticated" in roles, roles


def test_public_is_stripped_from_every_declared_callable_before_it_is_granted():
    """Postgres grants function EXECUTE to PUBLIC by default, so a function with
    an explicit anon grant is usually ALSO callable by every other role --
    including any role added later. The end state wanted is "PUBLIC holds
    nothing, anon and authenticated hold exactly EXECUTE".

    Order is load-bearing: the revoke must come BEFORE the grant, or it strips
    the grant it just made. Measured before shipping: all 20 functions carrying
    the PUBLIC grant already held explicit anon=X and authenticated=X, so PUBLIC
    was never the only source for any of them.
    """
    import inspect as _inspect

    from scripts import apply_anon_grants

    src = _inspect.getsource(apply_anon_grants._function_plan)
    rev = src.index('REVOKE ALL ON FUNCTION {one} FROM PUBLIC"')
    grant = src.index('GRANT EXECUTE ON FUNCTION {one} TO anon, authenticated"')
    assert rev < grant, (
        "the PUBLIC revoke must be emitted before the named grant, or it "
        "removes the grant it just made")


# ── the worker-only tables and their second lock ─────────────────────────────
# mike, 2026-09-04: "enable rls on those three tables."


def test_the_worker_only_tables_are_not_also_declared_app_readable():
    """RLS with zero policies denies the APP too, not just a stray grant.

    This is the one way the second lock can break something. If a future change
    adds `worker_jobs` to ANON_READABLE while it sits in WORKER_ONLY_TABLES, the
    grant lands, RLS denies every row, and the screen renders empty with a
    permission answer folded into `error` -- the exact silent failure this
    module exists to prevent, one layer down.
    """
    from data.anon_readable import WORKER_ONLY_TABLES, all_readable

    overlap = set(WORKER_ONLY_TABLES) & set(all_readable())
    assert not overlap, (
        f"{sorted(overlap)} is declared both worker-only (RLS, no policies) and "
        f"app-readable. RLS with no policies denies anon regardless of the "
        f"GRANT, so the app would read an empty table. Pick one.")


def test_lock_down_sql_refuses_a_table_it_was_not_declared_for():
    """The helper is the only way to build these statements, so it is also the
    place to refuse an undeclared table -- otherwise `lock_down_sql(typo)` would
    happily generate DDL that enables RLS on something the app reads."""
    import pytest

    from data.anon_readable import lock_down_sql

    with pytest.raises(ValueError, match="not a worker-only table"):
        lock_down_sql("picks")


def test_lock_down_sql_revokes_before_it_enables_rls():
    """Order matters for the same reason it does for the function grants: the
    revoke is the lock that works today and RLS is the one behind it. A reader
    of the log should see them in that order."""
    from data.anon_readable import WORKER_ONLY_TABLES, lock_down_sql

    for table in WORKER_ONLY_TABLES:
        stmts = lock_down_sql(table)
        assert len(stmts) == 2, stmts
        assert stmts[0].startswith("REVOKE ALL ON "), stmts[0]
        assert "anon, authenticated" in stmts[0], stmts[0]
        assert stmts[1] == (
            f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"), stmts[1]


def test_lock_down_never_uses_force_row_level_security():
    """FORCE RLS subjects the table OWNER to the policies, and the owner is
    `postgres` -- the role the worker connects as. With zero policies on these
    tables that would stop every worker write, silently and immediately. Pinned
    because `FORCE` is one word away from the statement we do want."""
    from data.anon_readable import WORKER_ONLY_TABLES, lock_down_sql

    for table in WORKER_ONLY_TABLES:
        for stmt in lock_down_sql(table):
            assert "FORCE" not in stmt.upper(), stmt


def test_every_worker_only_create_site_goes_through_the_gated_helper():
    """All three tables are created on demand, so the lock-down has to live
    beside the CREATE -- and it has to be the GATED form.

    `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` takes ACCESS EXCLUSIVE whether
    or not RLS is already on and fires Supabase's pgrst_ddl_watch, which makes
    PostgREST answer 503 to the whole app while it rebuilds its schema cache.
    That trap cost 11.6 hours of database time across seven modules
    (data/ddl_guard.py). So a write-time call site must use lock_down(), which
    gates on the catalog -- never lock_down_sql(), which does not.
    """
    from pathlib import Path

    sites = {
        "tracking/job_queue.py": "worker_jobs",
        "data/ingestors/odds_ingestor.py": "odds_history_pulls",
        "models/trainer.py": "model_artifacts",
    }
    root = Path(__file__).resolve().parents[1]
    for rel_path, table in sites.items():
        src = (root / rel_path).read_text(encoding="utf-8")
        assert f'lock_down(conn, "{table}")' in src or (
            f'lock_down(conn, ARTIFACT_LOCKDOWN_TABLE)' in src
            and f'ARTIFACT_LOCKDOWN_TABLE = "{table}"' in src), (
            f"{rel_path} creates {table} but does not call "
            f"lock_down(conn, ...) beside the CREATE")
        assert "lock_down_sql(" not in src, (
            f"{rel_path} calls lock_down_sql() at a write-time site. That skips "
            f"the catalog gate and fires ACCESS EXCLUSIVE DDL plus a PostgREST "
            f"schema-cache reload on every call. Use lock_down(conn, table).")


def test_the_job_queue_guard_checks_rls_and_the_revoke():
    """job_queue.ensure_schema returns EARLY on schema_is_current(), before the
    lock_down() call. Without rls= and revoked_from= that guard answers True on
    a database where worker_jobs exists but is still open, and the lock-down
    never runs -- a guard that dead code can satisfy."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1]
           / "tracking" / "job_queue.py").read_text(encoding="utf-8")
    # Slice to the CLOSING paren, tracking depth: the argument list contains
    # `columns=("dedupe_key",)`, so a naive index(")") cuts the call in half and
    # the test passes for the wrong reason.
    start = src.index('schema_is_current(conn, "worker_jobs"')
    depth, end = 0, None
    for i, ch in enumerate(src[start:], start):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
    assert end is not None, "unbalanced parens in the schema_is_current call"
    call = src[start:end]
    assert "rls=True" in call, call
    assert "revoked_from=API_ROLES" in call, call


def test_the_apply_script_reads_back_that_rls_actually_landed():
    """A revoke that did not bite reports success -- that is how the first
    function-grant apply "succeeded" while leaving has_active_subscription
    callable. The same rule applies to RLS: read it back inside the transaction
    or do not believe it."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1]
           / "scripts" / "apply_anon_grants.py").read_text(encoding="utf-8")
    assert "relrowsecurity" in src, (
        "apply_anon_grants does not read RLS back from pg_class")
    assert "relforcerowsecurity" in src, (
        "apply_anon_grants does not check that FORCE RLS is off -- which would "
        "deny the table owner, i.e. the worker")
    # and both must be able to roll the whole thing back
    for probe in ("RLS is still off", "FORCE RLS is on"):
        assert probe in src, probe
