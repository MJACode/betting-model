"""Stop new tables arriving with Supabase's default anon grant, and keep the
app's read surface explicitly granted.

mike, 2026-09-03: "do the alter default privileges too."

THE PROBLEM IT SOLVES. Revoking the grant on the 51 existing tables fixed the
present, not the future: Supabase's default privileges hand `anon=arwdDxtm` to
every new table in `public`, so the next one arrives open again. That is not
hypothetical -- `model_artifacts` is created on demand by
models/trainer.py::_store_artifact and came back with the full grant between two
sweeps of the schema hours apart the same day.

WHAT IT DOES, in one transaction:

  1. ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES
     FROM anon, authenticated
  2. GRANT SELECT on every relation in data/anon_readable.py, so the app's read
     surface is stated rather than inherited.
  3. REVOKE, then ENABLE ROW LEVEL SECURITY, on every table in
     data/anon_readable.closed_tables() -- the worker-only tables plus the
     extracted-data archives. A second lock behind the ACL, so a future
     migration that re-grants is not sufficient on its own.

Step 2 is a no-op on today's schema -- all 34 are already readable, measured
before writing this. It exists because step 1 makes the grant something you
have to ask for, and the asking should live in the repo.

WHY IT IS A SCRIPT AND NOT A .sql FILE. The read surface is a Python list that
a test cross-checks against mobile/src; duplicating it into SQL would let the
two drift, which is the whole failure this is meant to prevent. Same reason
data.threshold_sync generates the threshold SQL from config.py.

────────────────────────────────────────────────────────────────────────────
TWO LIMITS, MEASURED AND STATED RATHER THAN DISCOVERED LATER

ALTER DEFAULT PRIVILEGES is PER GRANTOR ROLE. Measured on production
2026-11-18, read-only, no global (NULL schema) rows:

    public / postgres       sequences: anon has rwU
                            functions and tables: postgres and service_role only
    public / supabase_admin sequences, functions and tables: anon,
                            authenticated and service_role
    storage / postgres      and graphql, graphql_public / supabase_admin
                            also grant anon. Those schemas are not changed.

Step B revokes the postgres public entries it can. It cannot revoke the
supabase_admin entries: that needs membership in supabase_admin, which
postgres does not have. A table that role creates in public arrives open
to anon. scripts/lockdown_anon_stray_check.sql raises when that happens.
--lockdown-b revokes the grant when this role owns the object, and the
same check fails the run when it does not.

SEQUENCES AND FUNCTIONS ARE LEFT ALONE, deliberately and not by oversight. The
same default privileges also grant anon `rwU` on every new sequence and EXECUTE
on every new function. The function half matters -- a new RPC becomes callable
by anon -- but revoking it by default means every new RPC the app calls needs an
explicit GRANT EXECUTE or it 404s, which is a second silent-failure surface and
a separate decision. Recorded in docs/followups.md.

    python -m scripts.apply_anon_grants            # show the plan
    python -m scripts.apply_anon_grants --apply    # apply it
"""

from __future__ import annotations

import argparse

from loguru import logger

from data.anon_readable import (
    ANON_READABLE,
    API_ROLES,
    AUTHENTICATED_ONLY,
    AUTHENTICATED_READABLE,
    AUTHENTICATED_WRITABLE,
    ANON_WRITABLE,
    RPC_ANON_CALLABLE,
    RPC_AUTHENTICATED_CALLABLE,
    RPC_SWEEP_ANON,
    RPC_REVOKE,
    VIEW_BASE_TABLES,
    WRITE_VERBS,
    lock_down,
    closed_tables,
    write_verbs_for,
)
from data.db import get_connection

REVOKE_DEFAULT = (
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
    "REVOKE ALL ON TABLES FROM anon, authenticated"
)

REVOKE_DEFAULT_FUNCTIONS = (
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
    "REVOKE ALL ON FUNCTIONS FROM anon, authenticated"
)

# Sequences are NOT revoked, and that is measured rather than cautious:
# tracked_bets.id defaults to nextval('tracked_bets_id_seq'), and anon holds
# USAGE and UPDATE on that sequence today. Closing the sequence default would
# make the next app-writable table's INSERT fail on its own primary key.
SEQUENCES_LEFT_ALONE = "sequences: nextval() on an app-written table needs them"


def _function_signature(conn, name: str) -> str | None:
    """`name(argtypes)` for a public function, or None if it does not exist.

    GRANT on a function needs the SIGNATURE, not the name -- and a name that is
    absent must be skipped rather than guessed, because granting on a missing
    function errors and would roll the whole thing back. `my_access` is exactly
    that case: the app calls it and the migration defining it was never applied.
    """
    row = conn.execute(
        "SELECT p.oid::regprocedure::text FROM pg_proc p "
        "JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = 'public' AND p.proname = %s", (name,)
    ).fetchall()
    if not row:
        return None
    # Overloads are joined with '|' and the caller grants each, so adding an
    # overload later cannot leave one of them ungranted. There are none today.
    return "|".join(r[0] for r in row)


# In ANON_READABLE before the worker has applied their migration. A GRANT or
# has_table_privilege on a missing name raises and rolls the whole sweep back.
# Once the table exists the normal checks apply. byom_lock_shop is not here:
# it is worker-only and the closed-table path already skips an absent relation.
MAY_BE_UNAPPLIED = (
    "byom_game_facts",
    "byom_prop_facts",
    # The women's Stats view. Its migration is not in ACTIVE_MIGRATIONS, so
    # the relation is absent until someone applies it by hand. _table_exists
    # only matches base tables, and a view therefore stays in the skip path
    # even after it exists; the migration's own GRANT is the one that opens
    # it. Leaving it here keeps a grant sweep from raising on a missing name
    # and from failing its read-back on a view (has_table_privilege is never
    # asked of a non-table).
    "v_player_season_totals_ncaabw",
    # Notification inbox. Hand migration, not applied until Matt runs it.
    # Authenticated-only. The migration's own GRANT is the one that opens
    # them; this entry only stops a sweep from GRANT-ing a missing name.
    "notification_inbox",
    "notification_sport_prefs",
)


def _table_exists(conn, rel: str) -> bool:
    """Whether `rel` is a base table in public.

    ARCHIVE_TABLES have no create site, so one of them CAN legitimately go away
    -- a retention decision drops a repair backup nobody needs any more. Without
    this check `ALTER TABLE <gone> ENABLE ROW LEVEL SECURITY` raises and rolls
    back the WHOLE apply, so a tidy-up in one place would break the grant sweep
    everywhere. Same shape as _function_signature returning None for a function
    that is not there: skip it, say so, carry on.
    """
    return bool(conn.execute(
        "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relname = %s AND c.relkind = 'r'",
        (rel,)).fetchall())


def _relation_exists(conn, rel: str) -> bool:
    """True when `rel` is a table, view or matview in public."""
    return bool(conn.execute(
        "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relname = %s "
        "AND c.relkind IN ('r', 'v', 'm')",
        (rel,)).fetchall())


def _plan(conn=None, lockdown: bool = False) -> list[str]:
    """Table statements only. Function statements need the database to resolve
    each signature, so they are built in main().

    Pass conn on an apply. A missing MAY_BE_UNAPPLIED relation, or
    site_public_record before its migration, is left out: GRANT on a missing
    name raises.

    lockdown=False is today's grants: anon and authenticated both read the
    app surface. That is the plain sweep. lockdown=True is the state after
    step B: anon keeps ANON_READABLE only. The plain sweep sets that flag
    only when tracked_bets.user_id exists and no anon policy remains, so a
    merge does not revoke the live anon key.
    """
    stmts = [REVOKE_DEFAULT]
    app_role = "authenticated" if lockdown else "anon, authenticated"

    def _skip(rel: str) -> bool:
        if conn is None:
            return False
        if rel in MAY_BE_UNAPPLIED and not _table_exists(conn, rel):
            return True
        if rel in ANON_READABLE and not _relation_exists(conn, rel):
            return True
        return False

    for rel in AUTHENTICATED_READABLE:
        if _skip(rel):
            continue
        stmts.append(f'GRANT SELECT ON public."{rel}" TO {app_role}')
    for rel in ANON_READABLE:
        if _skip(rel):
            continue
        stmts.append(f'GRANT SELECT ON public."{rel}" TO anon, authenticated')
    for rel in AUTHENTICATED_ONLY:
        if (conn is not None and rel in MAY_BE_UNAPPLIED
                and not _table_exists(conn, rel)):
            continue
        stmts.append(f'GRANT SELECT ON public."{rel}" TO authenticated')
    # The security_invoker views' base tables: the caller reads them too.
    for rel in VIEW_BASE_TABLES:
        if _skip(rel):
            continue
        stmts.append(f'GRANT SELECT ON public."{rel}" TO {app_role}')
    return stmts


def _anon_can_read(conn, rel: str) -> bool:
    """False only when the relation exists and anon cannot SELECT it.

    A MAY_BE_UNAPPLIED relation that is not in the catalog is not a failure:
    has_table_privilege on a missing name raises. Views are included: the
    website record is a view, and relkind 'r' alone would miss it.
    """
    if not _relation_exists(conn, rel):
        return rel in MAY_BE_UNAPPLIED
    return bool(conn.execute(
        "SELECT has_table_privilege('anon', %s, 'SELECT')",
        (f'public."{rel}"',)).fetchone()[0])


def _function_plan(conn, lockdown: bool = False) -> tuple[list[str], list[str]]:
    """(statements, skipped names). Resolves every signature from pg_proc.

    The plain sweep grants RPC_SWEEP_ANON to anon. That is today's app.
    lockdown=True grants only RPC_ANON_CALLABLE and takes PUBLIC and anon
    off every other declared function. PUBLIC is revoked first: anon is a
    member of PUBLIC, so a named revoke leaves the function callable.
    """
    stmts = [REVOKE_DEFAULT_FUNCTIONS]
    skipped: list[str] = []
    anon_names = RPC_ANON_CALLABLE if lockdown else RPC_SWEEP_ANON
    for name in anon_names:
        sig = _function_signature(conn, name)
        if sig is None:
            skipped.append(name)
            continue
        for one in sig.split("|"):
            stmts.append(f"REVOKE ALL ON FUNCTION {one} FROM PUBLIC")
            stmts.append(f"GRANT EXECUTE ON FUNCTION {one} TO anon, authenticated")
    if lockdown:
        keep = set(RPC_ANON_CALLABLE)
        for name in RPC_AUTHENTICATED_CALLABLE:
            if name in keep:
                continue
            sig = _function_signature(conn, name)
            if sig is None:
                skipped.append(name)
                continue
            for one in sig.split("|"):
                stmts.append(f"REVOKE ALL ON FUNCTION {one} FROM PUBLIC, anon")
                stmts.append(
                    "GRANT EXECUTE ON FUNCTION "
                    f"{one} TO postgres, authenticated, service_role")
    for name in RPC_REVOKE:
        sig = _function_signature(conn, name)
        if sig is None:
            skipped.append(name)
            continue
        for one in sig.split("|"):
            stmts.append(
                f"REVOKE ALL ON FUNCTION {one} FROM PUBLIC, anon, authenticated")
    return stmts, skipped


def _revoke_or_note(conn, sql: str) -> str | None:
    """None when the revoke committed to this transaction.

    A table owned by another role raises. The savepoint keeps the rest
    of the sweep able to run. The stray check then fails the run.
    """
    try:
        conn.execute("SAVEPOINT lockdown_stray")
        conn.execute(sql)
        conn.execute("RELEASE SAVEPOINT lockdown_stray")
        return None
    except Exception as exc:  # noqa: BLE001
        conn.execute("ROLLBACK TO SAVEPOINT lockdown_stray")
        return str(exc).splitlines()[0]


def _public_anon_strays(conn) -> list[str]:
    """Public objects anon can still use, outside the keep list.

    Same names as scripts/lockdown_anon_stray_check.sql. storage,
    graphql and graphql_public are not in this query.
    """
    from data.anon_lockdown_spec import ANON_KEEP_FUNCTIONS, ANON_KEEP_RELATIONS
    found: list[str] = []
    rels = conn.execute(
        "SELECT c.relname FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind IN ('r','v','m','p','f') "
        "AND (has_table_privilege('anon', c.oid, 'SELECT') "
        "  OR has_table_privilege('anon', c.oid, 'INSERT') "
        "  OR has_table_privilege('anon', c.oid, 'UPDATE') "
        "  OR has_table_privilege('anon', c.oid, 'DELETE')) "
        "ORDER BY c.relname"
    ).fetchall()
    found.extend(
        f"table {name}" for (name,) in rels if name not in ANON_KEEP_RELATIONS)
    seqs = conn.execute(
        "SELECT c.relname FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'S' "
        "AND c.relacl IS NOT NULL AND EXISTS ("
        "  SELECT 1 FROM aclexplode(c.relacl) a "
        "  WHERE a.grantee = (SELECT oid FROM pg_roles WHERE rolname = 'anon') "
        "    AND a.privilege_type = 'USAGE') "
        "ORDER BY c.relname"
    ).fetchall()
    found.extend(f"sequence {name}" for (name,) in seqs)
    fns = conn.execute(
        "SELECT p.proname FROM pg_proc p "
        "JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = 'public' "
        "AND has_function_privilege('anon', p.oid, 'EXECUTE') "
        "ORDER BY p.proname"
    ).fetchall()
    found.extend(
        f"function {name}" for (name,) in fns if name not in ANON_KEEP_FUNCTIONS)
    return found


def _step_b_applied(conn) -> bool:
    """True when step B has replaced the tracked_bets anon policies.

    user_id existing is not enough on its own: the column is added in the
    same migration as the policy swap. An anon or PUBLIC policy still on
    the table means the swap has not happened, and the plain sweep must
    keep today's grants.
    """
    col = conn.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'tracked_bets' "
        "AND column_name = 'user_id'"
    ).fetchone()
    if not col:
        return False
    anon_policy = conn.execute(
        "SELECT 1 FROM pg_policy pol "
        "JOIN pg_class c ON c.oid = pol.polrelid "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relname = 'tracked_bets' "
        "AND (pol.polroles = ARRAY[0]::oid[] OR EXISTS ("
        "  SELECT 1 FROM pg_roles r "
        "   WHERE r.oid = ANY (pol.polroles) AND r.rolname = 'anon')) "
        "LIMIT 1"
    ).fetchone()
    return anon_policy is None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="actually run it (default is a dry run)")
    ap.add_argument(
        "--lockdown-b", action="store_true",
        help="after step B is applied, revoke anon from every public "
             "relation, sequence and function outside the keep list. "
             "Refuses when tracked_bets.user_id is missing or an anon "
             "policy remains. The plain sweep never does this.")
    args = ap.parse_args()

    if not args.apply:
        stmts = _plan()
        logger.info(f"{len(stmts)} statement(s): 1 ALTER DEFAULT PRIVILEGES, "
                    f"{len(AUTHENTICATED_READABLE)} anon+authenticated grants, "
                    f"{len(AUTHENTICATED_ONLY)} authenticated-only grant(s); plus "
                    f"revoke+RLS on {len(closed_tables())} closed tables, "
                    f"gated on the catalog")
        logger.info(REVOKE_DEFAULT)
        if args.lockdown_b:
            logger.info(
                "--lockdown-b refuses until step B is applied "
                "(tracked_bets.user_id and no anon policy). "
                "Nothing executed.")
        logger.info("DRY RUN — nothing executed. Re-run with --apply.")
        return 0

    conn = get_connection()
    try:
        lockdown = _step_b_applied(conn)
        if args.lockdown_b and not lockdown:
            conn.rollback()
            logger.error(
                "refusing --lockdown-b: tracked_bets.user_id is missing "
                "or an anon policy remains. Apply "
                "anon_lockdown_step_b_2026_11.sql first.")
            return 1
        if lockdown and not args.lockdown_b:
            logger.info(
                "step B marker is present; anon grants are not restored")
        stmts = _plan(conn, lockdown=lockdown)
        absent = [rel for rel in MAY_BE_UNAPPLIED if not _table_exists(conn, rel)]
        if absent:
            logger.warning(
                f"not in pg_class, grant skipped until the migration runs: "
                f"{absent}")
        logger.info(f"{len(stmts)} statement(s) after skipping unapplied "
                    f"relations; revoke+RLS on {len(closed_tables())} closed "
                    f"tables, gated on the catalog")
        logger.info(REVOKE_DEFAULT)
        fn_stmts, skipped = _function_plan(conn, lockdown=lockdown)
        if skipped:
            logger.warning(
                f"skipped (absent from pg_proc, granting would error): {skipped}")
        logger.info(f"{len(fn_stmts)} function statement(s), "
                    f"1 ALTER DEFAULT PRIVILEGES + "
                    f"{len(fn_stmts) - 1} grant/revoke")
        for s in stmts + fn_stmts:
            conn.execute(s)
        # The worker-only tables get the second lock: revoke, then RLS. Through
        # lock_down() rather than raw statements, so a re-run against an
        # already-closed schema fires no ACCESS EXCLUSIVE DDL and forces no
        # PostgREST cache reload. The read-back below still checks the state.
        present = [rel for rel in closed_tables() if _table_exists(conn, rel)]
        absent = [rel for rel in closed_tables() if rel not in present]
        if absent:
            logger.warning(
                f"not in pg_class, skipped (drop them from ARCHIVE_TABLES if "
                f"that is deliberate): {absent}")
        for rel in present:
            ran = lock_down(conn, rel)
            logger.info(f"{rel}: {len(ran)} lock-down statement(s)"
                        + (" (already closed)" if not ran else ""))
        # A relation the app READS holds SELECT and nothing else, unless it is
        # declared in ANON_WRITABLE. Built from what each relation ACTUALLY
        # holds rather than issued blind, so the statement count and the log
        # reflect the real change: every GRANT/REVOKE is DDL and fires
        # Supabase's pgrst_ddl_watch, and this file already issues 34 of them.
        # THE SWEEP IS DRIVEN BY THE CATALOG, NOT BY ANON_READABLE. Iterating the
        # declared READ surface misses a relation that is writable without being
        # readable, and that is not hypothetical: the first run of this code left
        # `feedback` holding TRUNCATE, because feedback is in ANON_WRITABLE and
        # NOT in ANON_READABLE, so the loop never visited it. The test asserting
        # TRUNCATE is never granted passed the whole time -- it checks the
        # declaration, and the declaration was right; the sweep was reading the
        # wrong list. Five views and `confirmed_picks` were skipped the same way.
        #
        # Asking the catalog "who holds a write verb?" cannot have that hole, and
        # it also covers anything created later without being declared anywhere.
        holders = [
            r[0] for r in conn.execute(
                "SELECT c.relname FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind IN ('r','v') "
                "AND (has_table_privilege('anon', c.oid, "
                "     'INSERT,UPDATE,DELETE,TRUNCATE') "
                "  OR has_table_privilege('authenticated', c.oid, "
                "     'INSERT,UPDATE,DELETE,TRUNCATE')) "
                "ORDER BY c.relname").fetchall()
        ]
        revoked = 0
        # The inbox is authenticated-only even before the lockdown. Anon
        # does not keep those writes. tracked_bets does, until step B.
        never_anon_write = {"notification_inbox", "notification_sport_prefs"}
        for rel in holders:
            anon_allowed = set() if lockdown else set(ANON_WRITABLE.get(rel, ()))
            if rel in never_anon_write:
                anon_allowed = set()
            auth_allowed = set(AUTHENTICATED_WRITABLE.get(rel, ()))
            if not lockdown:
                auth_allowed |= set(ANON_WRITABLE.get(rel, ())) - never_anon_write
            anon_held = [
                v for v in WRITE_VERBS
                if v not in anon_allowed and conn.execute(
                    "SELECT has_table_privilege('anon', %s, %s)",
                    (f'public."{rel}"', v)).fetchone()[0]
            ]
            auth_held = [
                v for v in WRITE_VERBS
                if v not in auth_allowed and conn.execute(
                    "SELECT has_table_privilege('authenticated', %s, %s)",
                    (f'public."{rel}"', v)).fetchone()[0]
            ]
            if anon_held:
                conn.execute(
                    f'REVOKE {", ".join(anon_held)} ON public."{rel}" FROM anon')
                logger.info(f"{rel}: revoked {', '.join(anon_held)} from anon")
                revoked += 1
            if auth_held:
                conn.execute(
                    f'REVOKE {", ".join(auth_held)} ON public."{rel}" '
                    f'FROM authenticated')
                logger.info(
                    f"{rel}: revoked {', '.join(auth_held)} from authenticated")
                revoked += 1
        if args.lockdown_b:
            # Stray anon grants the step B file did not name. Refused above
            # unless the marker says step B is already applied.
            anon_rels = conn.execute(
                "SELECT c.relname FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind IN ('r','v','m') "
                "AND (has_table_privilege('anon', c.oid, 'SELECT') "
                "  OR has_table_privilege('anon', c.oid, 'INSERT') "
                "  OR has_table_privilege('anon', c.oid, 'UPDATE') "
                "  OR has_table_privilege('anon', c.oid, 'DELETE')) "
                "ORDER BY c.relname"
            ).fetchall()
            for (rel,) in anon_rels:
                if rel in ANON_READABLE:
                    continue
                err = _revoke_or_note(
                    conn, f'REVOKE ALL ON TABLE public."{rel}" FROM anon')
                if err:
                    logger.error(f"{rel}: anon revoke failed: {err}")
                else:
                    logger.info(f"{rel}: revoked anon")
            anon_seqs = conn.execute(
                "SELECT c.relname FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind = 'S' "
                "AND c.relacl IS NOT NULL AND EXISTS ("
                "  SELECT 1 FROM aclexplode(c.relacl) a "
                "  WHERE a.grantee = (SELECT oid FROM pg_roles WHERE rolname = 'anon') "
                "    AND a.privilege_type = 'USAGE')"
            ).fetchall()
            for (rel,) in anon_seqs:
                err = _revoke_or_note(
                    conn, f'REVOKE ALL ON SEQUENCE public."{rel}" FROM anon')
                if err:
                    logger.error(f"{rel}: anon sequence revoke failed: {err}")
                else:
                    logger.info(f"{rel}: revoked anon sequence")
            if _relation_exists(conn, "tracked_bets"):
                conn.execute(
                    "GRANT USAGE, SELECT ON SEQUENCE public.tracked_bets_id_seq "
                    "TO authenticated")
            keep_fn = set(RPC_ANON_CALLABLE)
            stray = conn.execute(
                "SELECT p.oid::regprocedure::text, p.proname FROM pg_proc p "
                "JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname = 'public' "
                "AND has_function_privilege('anon', p.oid, 'EXECUTE')"
            ).fetchall()
            for sig, name in stray:
                if name in keep_fn:
                    continue
                err = _revoke_or_note(
                    conn, f"REVOKE ALL ON FUNCTION {sig} FROM PUBLIC, anon")
                if err:
                    logger.error(f"{sig}: anon execute revoke failed: {err}")
                else:
                    logger.info(f"{sig}: revoked anon execute")
            left = _public_anon_strays(conn)
            if left:
                conn.rollback()
                logger.error(
                    "anon still holds public grants the sweep could not "
                    f"revoke: {left}")
                return 1
        logger.info(f"write verbs revoked on {revoked} of {len(holders)} "
                    f"relation(s) holding one; {len(ANON_WRITABLE)} declared "
                    f"writable keep their declared verbs")

        # Verify inside the transaction: the app's read surface must survive.
        must_read = list(ANON_READABLE)
        if not lockdown:
            must_read += list(AUTHENTICATED_READABLE) + list(VIEW_BASE_TABLES)
        missing = [
            rel for rel in must_read
            if _relation_exists(conn, rel) and not _anon_can_read(conn, rel)
        ]
        if missing:
            conn.rollback()
            logger.error(f"anon cannot read {missing} — rolled back.")
            return 1
        if lockdown:
            still_open = [
                rel for rel in AUTHENTICATED_READABLE
                if _relation_exists(conn, rel) and _anon_can_read(conn, rel)
                and rel not in MAY_BE_UNAPPLIED
            ]
            if still_open:
                conn.rollback()
                logger.error(f"anon can still read {still_open} — rolled back.")
                return 1
        # And every RPC it must be able to call. _jsonb_text_array is in here
        # too: it is a transitive dependency of the two SECURITY INVOKER
        # custom-model RPCs, so losing it breaks that screen.
        anon_rpcs = RPC_ANON_CALLABLE if lockdown else RPC_SWEEP_ANON
        uncallable = [
            name for name in anon_rpcs
            if (sig := _function_signature(conn, name)) is not None
            and not all(
                conn.execute("SELECT has_function_privilege('anon', %s, 'EXECUTE')",
                             (one,)).fetchone()[0]
                for one in sig.split("|"))
        ]
        if uncallable:
            conn.rollback()
            logger.error(f"anon cannot call {uncallable} — rolled back.")
            return 1
        # And that the revokes actually bit. The first run "succeeded" while
        # leaving has_active_subscription callable through PUBLIC, so a revoke
        # is not believed until it is read back.
        still_callable = [
            name for name in RPC_REVOKE
            if (sig := _function_signature(conn, name)) is not None
            and any(
                conn.execute("SELECT has_function_privilege('anon', %s, 'EXECUTE')",
                             (one,)).fetchone()[0]
                for one in sig.split("|"))
        ]
        if still_callable:
            conn.rollback()
            logger.error(f"anon can STILL call {still_callable} after the "
                         f"revoke — rolled back.")
            return 1
        # PUBLIC must hold nothing on the declared callables. Read back for the
        # same reason as above: a revoke that did not bite reports success.
        public_names = (
            (*RPC_ANON_CALLABLE, *RPC_AUTHENTICATED_CALLABLE)
            if lockdown else RPC_SWEEP_ANON)
        public_left = [
            name for name in public_names
            if (sig := _function_signature(conn, name)) is not None
            and any(
                conn.execute("SELECT has_function_privilege('public', %s, 'EXECUTE')",
                             (one,)).fetchone()[0]
                for one in sig.split("|"))
        ]
        if public_left:
            conn.rollback()
            logger.error(f"PUBLIC still holds EXECUTE on {public_left} — "
                         f"rolled back.")
            return 1
        # RLS must actually be ON. Read back for the same reason as the revokes:
        # ALTER TABLE ... ENABLE ROW LEVEL SECURITY on a table that does not
        # exist errors, but on one already enabled it succeeds silently, and
        # "succeeded" is not the same as "is on".
        rls_off = [
            rel for rel in present
            if not conn.execute(
                "SELECT c.relrowsecurity FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = %s",
                (rel,)).fetchone()[0]
        ]
        if rls_off:
            conn.rollback()
            logger.error(f"RLS is still off on {rls_off} — rolled back.")
            return 1
        # AND the owner must not be forced under the policies. FORCE ROW LEVEL
        # SECURITY on a table with zero policies would deny the WORKER, which
        # owns every one of these -- a silent stop, not an error.
        forced = [
            rel for rel in present
            if conn.execute(
                "SELECT c.relforcerowsecurity FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = %s",
                (rel,)).fetchone()[0]
        ]
        if forced:
            conn.rollback()
            logger.error(f"FORCE RLS is on for {forced}, which would deny the "
                         f"table owner — rolled back.")
            return 1
        # And nothing in the read surface holds a write verb it was not declared
        # to need. Read back for the same reason as every other revoke here: one
        # that did not bite reports success.
        surplus = []
        for rel in holders:
            for v in WRITE_VERBS:
                anon_has = conn.execute(
                    "SELECT has_table_privilege('anon', %s, %s)",
                    (f'public."{rel}"', v)).fetchone()[0]
                auth_has = conn.execute(
                    "SELECT has_table_privilege('authenticated', %s, %s)",
                    (f'public."{rel}"', v)).fetchone()[0]
                anon_ok = set() if lockdown else set(ANON_WRITABLE.get(rel, ()))
                if rel in never_anon_write:
                    anon_ok = set()
                auth_ok = set(AUTHENTICATED_WRITABLE.get(rel, ()))
                if not lockdown:
                    auth_ok |= set(ANON_WRITABLE.get(rel, ())) - never_anon_write
                if anon_has and v not in anon_ok:
                    surplus.append(f"anon {rel}:{v}")
                if auth_has and v not in auth_ok:
                    surplus.append(f"authenticated {rel}:{v}")
        if surplus:
            conn.rollback()
            logger.error(f"undeclared write privileges survive: {surplus} — "
                         f"rolled back.")
            return 1
        conn.commit()
    except Exception as exc:                                   # noqa: BLE001
        conn.rollback()
        logger.error(f"FAILED, rolled back: {exc}")
        return 1

    logger.success(
        f"Default privileges revoked for {', '.join(API_ROLES)} on new public "
        f"tables; {len(ANON_READABLE) + len(AUTHENTICATED_ONLY)} read grants "
        f"asserted; RLS on for {len(present)} closed tables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
