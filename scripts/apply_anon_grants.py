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

from data.anon_readable import ANON_READABLE, AUTHENTICATED_ONLY
from data.db import get_connection

# The roles PostgREST authenticates as. service_role is deliberately absent:
# the edge functions (including every billing path) use it, and the worker
# connects as postgres.
API_ROLES = ("anon", "authenticated")

REVOKE_DEFAULT = (
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
    "REVOKE ALL ON TABLES FROM anon, authenticated"
)


def _plan() -> list[str]:
    stmts = [REVOKE_DEFAULT]
    for rel in ANON_READABLE:
        stmts.append(f'GRANT SELECT ON public."{rel}" TO anon, authenticated')
    for rel in AUTHENTICATED_ONLY:
        stmts.append(f'GRANT SELECT ON public."{rel}" TO authenticated')
    return stmts


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
        for s in stmts:
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
