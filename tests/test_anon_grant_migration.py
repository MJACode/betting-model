"""The grant migration must not take away the read the app depends on.

A revoke is easy to widen by one word and impossible to notice afterwards: the
app just starts returning empty arrays, because PostgREST answers a permission
error the client swallows into `error` and the caller renders nothing.
"""

import inspect
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pathlib import Path

SQL = (Path(__file__).parent.parent / "data" / "migrations"
       / "tighten_anon_write_grants.sql")
BODY = io.open(SQL, encoding="utf-8").read()
# Statements only -- the file's reasoning mentions the things it must not do.
STMTS = " ".join(
    ln for ln in BODY.splitlines() if not ln.strip().startswith("--")
)


def test_odds_keeps_select_for_the_app():
    """mobile/src/lib/queries.ts reads `odds` directly, and v_latest_dk_odds /
    v_latest_odds_all_books are security_invoker=on so they run as the CALLER.
    Revoking SELECT breaks line-movement history and every best-price display."""
    odds = re.search(r"REVOKE([^;]*?)ON public\.odds FROM([^;]*);", STMTS)
    assert odds, STMTS
    privs = odds.group(1)
    assert "SELECT" not in privs, f"revokes SELECT on odds: {privs}"
    assert "ALL" not in privs, f"revokes ALL on odds, which includes SELECT: {privs}"
    for w in ("INSERT", "UPDATE", "DELETE"):
        assert w in privs, f"leaves {w} granted on odds: {privs}"


def test_the_two_rls_off_tables_lose_everything():
    """These three have RLS OFF, so the grant is live -- anon can really write
    them. worker_jobs is the queue the Railway worker claims and executes every
    five minutes, and model_artifacts holds the .pkl payloads the scorer loads,
    so a row there IS a model. None has any app surface."""
    for tbl in ("worker_jobs", "odds_history_pulls", "model_artifacts"):
        m = re.search(rf"REVOKE\s+ALL\s+ON public\.{tbl}\s+FROM([^;]*);", STMTS)
        assert m, f"{tbl} does not lose the whole grant: {STMTS}"
        assert "anon" in m.group(1) and "authenticated" in m.group(1), m.group(1)


def test_every_revoke_names_the_roles_rather_than_public():
    """REVOKE ... FROM PUBLIC does not touch a named role, which is how the
    grant survived every previous attempt to remove it (the ops rule)."""
    for stmt in re.findall(r"REVOKE[^;]*;", STMTS):
        assert "FROM PUBLIC" not in stmt.upper(), stmt
        assert "anon" in stmt and "authenticated" in stmt, stmt


def test_the_app_write_tables_are_not_touched():
    """device_push_tokens, feedback and tracked_bets are the four tables that
    carry a real permissive write policy for anon/authenticated -- the app
    genuinely writes them. A sweep that caught them would break sign-up,
    in-app feedback and the betslip."""
    for tbl in ("device_push_tokens", "feedback", "tracked_bets", "game_weather"):
        assert tbl not in STMTS, f"{tbl} must keep its write grant"


def test_it_does_not_enable_rls_blind():
    """RLS with no policy locks out every connection that is not the table
    owner, and the worker's role has not been verified to be that owner. The
    revoke closes the hole on its own; this must not gamble the job queue."""
    assert "ROW LEVEL SECURITY" not in STMTS.upper(), STMTS


def test_it_is_one_transaction():
    assert STMTS.strip().startswith("BEGIN"), STMTS[:80]
    assert STMTS.strip().rstrip(";").endswith("COMMIT"), STMTS[-80:]


def test_the_artifact_table_revokes_at_its_own_creation():
    """A migration alone cannot hold model_artifacts: trainer.py creates it on
    demand, so the next retrain against a database without it would recreate it
    carrying Supabase's full default grant. That is how it came back between
    one sweep of the schema and the next, hours apart.

    The statement moved into data/anon_readable.py::lock_down_sql on 2026-09-04
    when RLS joined it as a second lock -- the same rule now covers all three
    worker-only tables instead of being spelled out in trainer.py. What this
    pins is unchanged: the revoke happens at CREATION, before the first write.
    """
    from data.anon_readable import lock_down_sql
    from models import trainer

    assert "REVOKE ALL ON model_artifacts FROM anon, authenticated" \
        in lock_down_sql("model_artifacts"), lock_down_sql("model_artifacts")
    assert trainer.ARTIFACT_LOCKDOWN_TABLE == "model_artifacts"

    src = inspect.getsource(trainer._store_artifact)
    ddl = src.index("ARTIFACT_DDL")
    rev = src.index("lock_down(conn, ARTIFACT_LOCKDOWN_TABLE)")
    ins = src.index("INSERT INTO model_artifacts")
    assert ddl < rev < ins, (
        "the lock-down must run after the CREATE and before the first write")
