"""delete_my_account() deletes one caller's rows and nothing public.

The migration is unapplied. This reads the SQL file. It does not connect.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "data/migrations/delete_my_account_2026_10_24.sql"
SQL = SQL_PATH.read_text(encoding="utf-8")

# Tables the function is allowed to delete, each keyed by the caller.
OWNED = (
    "public.byom_model_snapshots",
    "public.byom_models",
    "public.feedback_messages",
    "public.feedback_threads",
    "public.member_sportsbooks",
    "public.discord_links",
    "public.subscriptions",
    "auth.users",
)

# Public record and anything not owned by auth.uid().
FORBIDDEN = (
    "public.picks",
    "results_snapshots",
    "opening_signals",
    "parlay_track_record",
    "whop_memberships",
    "tracked_bets",
    "linked_sportsbook_accounts",
    "synced_bets",
    "device_push_tokens",
    "app_errors",
    "from games",
    "from public.games",
)


def _code(sql: str) -> str:
    return "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())


def test_the_file_is_not_on_the_worker_list():
    listed = (ROOT / "data/view_migrations.py").read_text(encoding="utf-8")
    assert SQL_PATH.name not in listed
    assert "UNAPPLIED" in SQL
    assert "ACTIVE_MIGRATIONS" in SQL


def test_only_the_caller_and_only_a_fresh_session():
    code = _code(SQL)
    assert "SECURITY DEFINER" in code
    assert "auth.uid()" in code
    assert "v_uid uuid := auth.uid()" in code
    assert "last_sign_in_at" in code
    assert "interval '10 minutes'" in code
    assert code.count("STALE_SESSION") >= 2
    assert code.count("28000") >= 2
    assert "GRANT EXECUTE ON FUNCTION public.delete_my_account() TO authenticated" in code
    assert "REVOKE ALL ON FUNCTION public.delete_my_account() FROM PUBLIC" in code
    assert "REVOKE ALL ON FUNCTION public.delete_my_account() FROM anon" in code
    assert "SET search_path = public, auth, pg_temp" in code
    # No argument the client could use to name someone else.
    assert "p_user" not in code
    assert "p_uid" not in code


def test_every_delete_is_the_caller_and_the_public_record_is_absent():
    code = _code(SQL)
    deletes = [ln.strip() for ln in code.splitlines() if ln.strip().upper().startswith("DELETE")]
    assert len(deletes) == len(OWNED)
    for table in OWNED:
        match = [ln for ln in deletes if table in ln]
        assert match, table
        assert "v_uid" in match[0]
    for name in FORBIDDEN:
        assert name not in code
    # The member_sportsbooks delete is the signed-in row, not the install's.
    books = next(ln for ln in deletes if "member_sportsbooks" in ln)
    assert "user:" in books
    assert "device:" not in books
