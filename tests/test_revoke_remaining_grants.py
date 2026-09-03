"""The sweep must revoke by RULE, keep SELECT, and spare what the app writes.

A revoke that goes one word too far is invisible afterwards: PostgREST answers
a permission error, the client folds it into `error`, and the screen renders
empty with nothing in any log near the cause. So the shape is pinned here.
"""

import io
import re
from pathlib import Path

SQL_PATH = (Path(__file__).parent.parent / "data" / "migrations"
            / "revoke_remaining_anon_write_grants.sql")
BODY = io.open(SQL_PATH, encoding="utf-8").read()
# Statements only. The file's reasoning names the things it must not do.
STMTS = "\n".join(ln for ln in BODY.splitlines()
                  if not ln.strip().startswith("--"))

# The app's entire direct write surface, established from mobile/src: two call
# sites. Everything else it writes goes through a SECURITY DEFINER RPC.
APP_WRITES = ("tracked_bets", "device_push_tokens")


def test_select_is_never_revoked():
    """Most of these tables are read by the app, several through
    security_invoker views that run as the caller."""
    for stmt in re.findall(r"REVOKE[^;']*", STMTS):
        assert "SELECT" not in stmt, stmt
        assert not re.search(r"\bREVOKE\s+ALL\b", stmt), stmt


def test_it_revokes_every_write_privilege():
    revoke = re.search(r"REVOKE ([A-Z, ]+?) '\s*\n?\s*'?ON public", STMTS) \
        or re.search(r"'REVOKE ([A-Z, ]+)", STMTS)
    assert revoke, STMTS
    privs = revoke.group(1)
    for w in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
        assert w in privs, f"{w} not revoked: {privs}"


def test_the_roles_are_named_never_public():
    """REVOKE ... FROM PUBLIC does not touch a named role -- which is how this
    grant survived every earlier attempt to remove it."""
    assert "FROM anon, authenticated" in STMTS, STMTS
    assert "FROM PUBLIC" not in STMTS.upper(), STMTS
    assert "service_role" not in STMTS, "service_role must keep its grant"


def test_the_set_is_computed_from_the_policy_rule_not_listed():
    """A hard-coded list goes stale and the rule does not: model_artifacts
    reappeared with the full default grant between two sweeps of the schema
    hours apart, because trainer.py creates it on demand."""
    assert "pg_policy" in STMTS, STMTS
    assert "polpermissive" in STMTS, STMTS
    assert "NOT EXISTS" in STMTS, STMTS
    # No table names in the revoke path -- only in the closing assertion.
    loop = STMTS[:STMTS.index("IF NOT (")]
    for name in ("picks", "games", "subscriptions", "player_prop_odds"):
        assert f"'{name}'" not in loop, f"{name} is hard-coded in the loop"


def test_it_asserts_the_app_write_surface_survives():
    """If a write policy is ever dropped, the loop would silently start
    catching one of these. The assertion turns that into a rollback."""
    tail = STMTS[STMTS.index("IF NOT ("):]
    for tbl in APP_WRITES:
        assert f"public.{tbl}" in tail, f"{tbl} is not asserted: {tail}"
    assert "RAISE EXCEPTION" in tail, tail


def test_the_runners_transaction_stripping_leaves_the_do_block_intact():
    """run_sql_file strips a leading BEGIN; and trailing COMMIT;. The DO block
    has its own BEGIN/END inside dollar quotes, and a regex with the wrong
    flags would eat one of them and leave unbalanced SQL."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.run_sql_file import _strip_outer_tx

    out = _strip_outer_tx(BODY)
    assert not out.lstrip().upper().startswith("BEGIN;")
    assert not out.rstrip().upper().endswith("COMMIT;")
    assert "\nBEGIN\n" in out, "the DO block lost its own BEGIN"
    assert "END $$;" in out, "the DO block lost its own END"
    assert out.count("$$") == 2, "dollar quoting is unbalanced"
    assert "%I" in out, "format()'s %I must survive; execute() with no params "\
                        "does no interpolation"
