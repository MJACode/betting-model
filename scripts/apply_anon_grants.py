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

Step 2 is a no-op on today's schema -- all 34 are already readable, measured
before writing this. It exists because step 1 makes the grant something you
have to ask for, and the asking should live in the repo.

WHY IT IS A SCRIPT AND NOT A .sql FILE. The read surface is a Python list that
a test cross-checks against mobile/src; duplicating it into SQL would let the
two drift, which is the whole failure this is meant to prevent. Same reason
data.threshold_sync generates the threshold SQL from config.py.

────────────────────────────────────────────────────────────────────────────
TWO LIMITS, MEASURED AND STATED RATHER THAN DISCOVERED LATER

ALTER DEFAULT PRIVILEGES is PER GRANTOR ROLE, and `public` tables have TWO
default-ACL entries handing anon arwdDxtm:

    grantor postgres        -> anon=arwdDxtm/postgres
    grantor supabase_admin  -> anon=arwdDxtm/supabase_admin

This changes the `postgres` one, because that is the role everything here
creates tables as -- the worker and the pollers over DATABASE_URL, and the
Supabase SQL editor. The `supabase_admin` entry is not touched: altering it
needs membership in supabase_admin, which `postgres` does not have on a managed
project. So a table created BY supabase_admin would still arrive open. Nothing
in this repo creates one.

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
    AUTHENTICATED_ONLY,
    RPC_ANON_CALLABLE,
    RPC_REVOKE,
)
from data.db import get_connection

# The roles PostgREST authenticates as. service_role is deliberately absent:
# the edge functions (including every billing path) use it, and the worker
# connects as postgres.
API_ROLES = ("anon", "authenticated")

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


def _plan() -> list[str]:
    """Table statements only. Function statements need the database to resolve
    each signature, so they are built in main()."""
    stmts = [REVOKE_DEFAULT]
    for rel in ANON_READABLE:
        stmts.append(f'GRANT SELECT ON public."{rel}" TO anon, authenticated')
    for rel in AUTHENTICATED_ONLY:
        stmts.append(f'GRANT SELECT ON public."{rel}" TO authenticated')
    return stmts


def _function_plan(conn) -> tuple[list[str], list[str]]:
    """(statements, skipped names). Resolves every signature from pg_proc."""
    stmts = [REVOKE_DEFAULT_FUNCTIONS]
    skipped: list[str] = []
    for name in RPC_ANON_CALLABLE:
        sig = _function_signature(conn, name)
        if sig is None:
            skipped.append(name)
            continue
        for one in sig.split("|"):
            # PUBLIC OFF FIRST, then the named grant. Postgres grants function
            # EXECUTE to PUBLIC by default, so most of these carry `=X/postgres`
            # in their ACL and are callable by any role at all -- including any
            # role added later. The named grants are what the app actually needs,
            # so the end state is "PUBLIC holds nothing, anon and authenticated
            # hold exactly EXECUTE".
            #
            # Safe because the grant follows in the same transaction, and the
            # read-back at the end refuses to commit if anon has lost the call.
            # Verified before shipping: all 20 functions carrying the PUBLIC
            # grant already held explicit anon=X and authenticated=X, so PUBLIC
            # was never the only source for any of them.
            stmts.append(f"REVOKE ALL ON FUNCTION {one} FROM PUBLIC")
            stmts.append(f"GRANT EXECUTE ON FUNCTION {one} TO anon, authenticated")
    for name in RPC_REVOKE:
        sig = _function_signature(conn, name)
        if sig is None:
            skipped.append(name)
            continue
        for one in sig.split("|"):
            # PUBLIC FIRST, AND THAT IS NOT COSMETIC. Postgres grants EXECUTE on
            # a function to PUBLIC by default, and anon is a member of PUBLIC --
            # so `REVOKE ... FROM anon, authenticated` leaves the function
            # callable and reports success. Measured 2026-09-04: the first run
            # of this script revoked has_active_subscription from both named
            # roles and anon could still execute it, because its ACL carried
            # `=X/postgres` (empty grantee = PUBLIC). 21 of 28 public functions
            # carry that grant. data/migrations/add_discord_link_and_whop_
            # memberships.sql already spelled it `FROM PUBLIC, anon,
            # authenticated`; this is that lesson, relearned the hard way.
            stmts.append(
                f"REVOKE ALL ON FUNCTION {one} FROM PUBLIC, anon, authenticated")
    return stmts, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="actually run it (default is a dry run)")
    args = ap.parse_args()

    stmts = _plan()
    logger.info(f"{len(stmts)} statement(s): 1 ALTER DEFAULT PRIVILEGES, "
                f"{len(ANON_READABLE)} anon+authenticated grants, "
                f"{len(AUTHENTICATED_ONLY)} authenticated-only grant(s)")
    logger.info(REVOKE_DEFAULT)

    if not args.apply:
        logger.info("DRY RUN — nothing executed. Re-run with --apply.")
        return 0

    conn = get_connection()
    try:
        fn_stmts, skipped = _function_plan(conn)
        if skipped:
            logger.warning(
                f"skipped (absent from pg_proc, granting would error): {skipped}")
        logger.info(f"{len(fn_stmts)} function statement(s), "
                    f"1 ALTER DEFAULT PRIVILEGES + "
                    f"{len(fn_stmts) - 1} grant/revoke")
        for s in stmts + fn_stmts:
            conn.execute(s)
        # Verify inside the transaction: the app's read surface must survive.
        missing = [
            rel for rel in ANON_READABLE
            if not conn.execute(
                "SELECT has_table_privilege('anon', %s, 'SELECT')",
                (f'public."{rel}"',)).fetchone()[0]
        ]
        if missing:
            conn.rollback()
            logger.error(f"anon cannot read {missing} — rolled back.")
            return 1
        # And every RPC it must be able to call. _jsonb_text_array is in here
        # too: it is a transitive dependency of the two SECURITY INVOKER
        # custom-model RPCs, so losing it breaks that screen.
        uncallable = [
            name for name in RPC_ANON_CALLABLE
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
        public_left = [
            name for name in RPC_ANON_CALLABLE
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
        conn.commit()
    except Exception as exc:                                   # noqa: BLE001
        conn.rollback()
        logger.error(f"FAILED, rolled back: {exc}")
        return 1

    logger.success(
        f"Default privileges revoked for {', '.join(API_ROLES)} on new public "
        f"tables; {len(ANON_READABLE) + len(AUTHENTICATED_ONLY)} read grants "
        f"asserted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
