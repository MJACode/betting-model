"""ops.acl_snapshot restore: the diff is the grant, not a printed promise."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.restore_acl_from_snapshot import (  # noqa: E402
    default_statements,
    parse_acl,
    policy_statement,
    rel_statements,
)


def test_parse_acl_names_public_when_the_grantee_is_empty():
    got = parse_acl(["=r/postgres", "anon=arwd/postgres"])
    assert got["PUBLIC"] == {"r"}
    assert got["anon"] == {"a", "r", "w", "d"}


def test_a_live_grant_anon_lost_is_granted_back():
    lines = rel_statements(
        "public.games", "r",
        ["anon=r/postgres", "authenticated=r/postgres"],
        ["authenticated=r/postgres"],
    )
    assert lines == ["GRANT SELECT ON TABLE public.games TO \"anon\""]


def test_an_extra_live_privilege_is_revoked():
    lines = rel_statements(
        "public.games", "r",
        ["anon=r/postgres"],
        ["anon=arwd/postgres"],
    )
    assert lines == [
        "REVOKE DELETE, INSERT, UPDATE ON TABLE public.games FROM \"anon\""
    ]


def test_sequence_usage_uses_the_sequence_keyword():
    lines = rel_statements(
        "public.picks_pick_id_seq", "S",
        ["anon=rwU/postgres"],
        None,
    )
    assert lines == [
        "GRANT SELECT, UPDATE, USAGE ON SEQUENCE public.picks_pick_id_seq TO \"anon\""
    ]


def test_default_privileges_name_the_grantor():
    lines = default_statements(
        "postgres:f",
        ["=X/postgres"],
        None,
    )
    assert lines == [
        "ALTER DEFAULT PRIVILEGES FOR ROLE \"postgres\" IN SCHEMA public "
        "GRANT EXECUTE ON FUNCTIONS TO PUBLIC"
    ]


def test_policy_roles_become_an_alter():
    stmt = policy_statement(
        "public.games:anon read games", "{anon,authenticated}")
    assert stmt == (
        'ALTER POLICY "anon read games" ON public.games TO anon, authenticated'
    )


def test_dry_run_refuses_without_a_dsn():
    from scripts.restore_acl_from_snapshot import main
    assert main(["--label", "pre_step_a_20261118"]) == 2
