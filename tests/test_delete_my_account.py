"""delete_my_account() deletes one caller's rows and nothing public.

The migration is unapplied. This reads the SQL file. It does not connect.

delete_my_login() is the second function in the same file. It deletes
auth.users only, after the app has unlinked Discord. discord_links is not
deleted by either function; the login delete cascades it.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "data/migrations/delete_my_account_2026_10_24.sql"
SQL = SQL_PATH.read_text(encoding="utf-8")

# Tables delete_my_account() may delete, each keyed by the caller.
# discord_links and auth.users are not in this list: unlink needs both.
DATA_OWNED = (
    "public.byom_model_snapshots",
    "public.byom_models",
    "public.feedback_messages",
    "public.feedback_threads",
    "public.member_sportsbooks",
    "public.subscriptions",
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
    "discord_links",
    "from games",
    "from public.games",
)


def _code(sql: str) -> str:
    return "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())


def _body(code: str, name: str) -> str:
    marker = f"CREATE OR REPLACE FUNCTION public.{name}()"
    start = code.index(marker)
    rest = code[start:]
    nxt = rest.find("CREATE OR REPLACE FUNCTION", len(marker))
    return rest if nxt < 0 else rest[:nxt]


def _deletes(body: str) -> list[str]:
    return [ln.strip() for ln in body.splitlines() if ln.strip().upper().startswith("DELETE")]


def test_the_file_is_not_on_the_worker_list():
    listed = (ROOT / "data/view_migrations.py").read_text(encoding="utf-8")
    assert SQL_PATH.name not in listed
    assert "UNAPPLIED" in SQL
    assert "ACTIVE_MIGRATIONS" in SQL


def test_only_the_caller_and_only_a_fresh_session():
    code = _code(SQL)
    assert code.count("SECURITY DEFINER") == 2
    assert code.count("v_uid uuid := auth.uid()") == 2
    assert code.count("last_sign_in_at") == 2
    assert code.count("interval '10 minutes'") == 2
    assert code.count("STALE_SESSION") >= 4
    assert code.count("28000") >= 4
    for name in ("delete_my_account", "delete_my_login"):
        assert f"GRANT EXECUTE ON FUNCTION public.{name}() TO authenticated" in code
        assert f"REVOKE ALL ON FUNCTION public.{name}() FROM PUBLIC" in code
        assert f"REVOKE ALL ON FUNCTION public.{name}() FROM anon" in code
    assert code.count("SET search_path = public, auth, pg_temp") == 2
    # No argument the client could use to name someone else.
    assert "p_user" not in code
    assert "p_uid" not in code


def test_every_delete_is_the_caller_and_the_public_record_is_absent():
    code = _code(SQL)
    data_deletes = _deletes(_body(code, "delete_my_account"))
    login_deletes = _deletes(_body(code, "delete_my_login"))
    assert len(data_deletes) == len(DATA_OWNED)
    for table in DATA_OWNED:
        match = [ln for ln in data_deletes if table in ln]
        assert match, table
        assert "v_uid" in match[0]
    assert len(login_deletes) == 1
    assert "auth.users" in login_deletes[0]
    assert "v_uid" in login_deletes[0]
    assert "auth.users" not in "\n".join(data_deletes)
    for name in FORBIDDEN:
        assert name not in code
    # The member_sportsbooks delete is the signed-in row, not the install's.
    books = next(ln for ln in data_deletes if "member_sportsbooks" in ln)
    assert "user:" in books
    assert "device:" not in books
