"""The unapplied Discord/Whop migration unlocks the app from Apple only.

`add_discord_link_and_whop_memberships.sql` has not been applied in
production. The first apply has to already be Apple-only: my_access().entitled
and has_app_access() read subscriptions (trialing/active, period open). A
Whop match stays discord_access and is not OR-ed into the app.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "data" / "migrations"


def _body(sql: str, signature: str) -> str:
    marker = f"CREATE FUNCTION {signature}"
    replaced = f"CREATE OR REPLACE FUNCTION {signature}"
    start = sql.find(marker)
    if start < 0:
        start = sql.find(replaced)
    assert start >= 0, signature
    end = sql.find("$$;", start)
    assert end > start
    return sql[start:end]


def test_has_app_access_does_not_or_whop():
    sql = (MIGRATIONS / "add_discord_link_and_whop_memberships.sql").read_text(
        encoding="utf-8"
    )
    body = _body(sql, "public.has_app_access()")
    assert "app_subscription_access_for" in body
    assert "discord_access_for" not in body


def test_my_access_for_entitled_is_the_apple_flag():
    sql = (MIGRATIONS / "add_discord_link_and_whop_memberships.sql").read_text(
        encoding="utf-8"
    )
    body = _body(sql, "public.my_access_for")
    assert "SELECT a," in body
    assert "(a OR d)" not in body
    assert "a OR d" not in body
    assert "d := public.discord_access_for" in body


def test_no_other_migration_ors_whop_into_app_access():
    for path in sorted(MIGRATIONS.glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        if "FUNCTION public.has_app_access" in text:
            body = _body(text, "public.has_app_access()")
            assert "discord_access_for" not in body, path.name
        if "FUNCTION public.my_access_for" in text:
            body = _body(text, "public.my_access_for")
            assert "a OR d" not in body, path.name
            assert "(a OR d)" not in body, path.name
