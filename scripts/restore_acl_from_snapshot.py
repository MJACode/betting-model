"""Restore grants from ops.acl_snapshot.

Dry-run is the default. --dsn is required either way, because the snapshot
lives in the database. --apply executes the diff in one transaction.
Nothing is read from DATABASE_URL.

    python -m scripts.restore_acl_from_snapshot --label pre_step_a_20261118 --dsn "$DSN"
    python -m scripts.restore_acl_from_snapshot --label pre_step_a_20261118 --dsn "$DSN" --apply

The hand undo files put policies and the tracked_bets shape back. This
script puts table, column, function and default-privilege ACLs back to
the rows scripts/lockdown_acl_snapshot.sql stored.
"""

from __future__ import annotations

import argparse
import re
import sys

PRIVILEGE = {
    "r": "SELECT",
    "w": "UPDATE",
    "a": "INSERT",
    "d": "DELETE",
    "D": "TRUNCATE",
    "x": "REFERENCES",
    "t": "TRIGGER",
    "X": "EXECUTE",
    "U": "USAGE",
    "C": "CREATE",
    "c": "CONNECT",
    "T": "TEMPORARY",
    "m": "MAINTAIN",
}

_ACL = re.compile(r"^([^=]*)=([^/]+)/(.+)$")
DEFACL_TARGET = {"r": "TABLES", "S": "SEQUENCES", "f": "FUNCTIONS"}


def parse_acl(items: list[str] | None) -> dict[str, set[str]]:
    """aclitem text to {grantee: privilege letters}. Empty grantee is PUBLIC."""
    out: dict[str, set[str]] = {}
    for item in items or []:
        match = _ACL.match(item)
        if not match:
            continue
        grantee = match.group(1) or "PUBLIC"
        letters = {ch for ch in match.group(2) if ch != "*"}
        out.setdefault(grantee, set()).update(letters)
    return out


def _words(letters: set[str]) -> str:
    names = sorted(PRIVILEGE[ch] for ch in letters if ch in PRIVILEGE)
    return ", ".join(names)


def _quote_role(role: str) -> str:
    if role == "PUBLIC":
        return "PUBLIC"
    return '"' + role.replace('"', '""') + '"'


def rel_statements(object_name: str, relkind: str, snapshot: list[str] | None,
                   live: list[str] | None) -> list[str]:
    kind = "SEQUENCE" if relkind == "S" else "TABLE"
    return _diff(f"{kind} {object_name}", snapshot, live)


def func_statements(signature: str, snapshot: list[str] | None,
                    live: list[str] | None) -> list[str]:
    return _diff(f"FUNCTION {signature}", snapshot, live)


def column_statements(object_name: str, snapshot: list[str] | None,
                      live: list[str] | None) -> list[str]:
    table, _, column = object_name.rpartition(".")
    if not table or not column:
        return []
    target = f"TABLE {table}"
    return _diff(target, snapshot, live, column=column)


def default_statements(object_name: str, snapshot: list[str] | None,
                       live: list[str] | None) -> list[str]:
    role, _, objtype = object_name.partition(":")
    target = DEFACL_TARGET.get(objtype)
    if not role or not target:
        return []
    prefix = (
        "ALTER DEFAULT PRIVILEGES FOR ROLE "
        f"{_quote_role(role)} IN SCHEMA public"
    )
    lines = []
    for verb, role_name, letters in _changes(snapshot, live):
        words = _words(letters)
        if not words:
            continue
        lines.append(
            f"{prefix} {verb} {words} ON {target} "
            f"{'TO' if verb == 'GRANT' else 'FROM'} {_quote_role(role_name)}")
    return lines


def policy_statement(object_name: str, roles: str) -> str | None:
    """object is schema.table:policyname. roles is a pg name[] cast to text."""
    schema_table, sep, policy = object_name.partition(":")
    if not sep or not policy or "." not in schema_table:
        return None
    cleaned = roles.strip().strip("{}")
    if not cleaned:
        return None
    named = ", ".join(
        "public" if part.strip().strip('"') == "public" else part.strip()
        for part in cleaned.split(",")
        if part.strip()
    )
    safe_policy = policy.replace('"', '""')
    return f'ALTER POLICY "{safe_policy}" ON {schema_table} TO {named}'


def _changes(snapshot: list[str] | None, live: list[str] | None):
    want = parse_acl(snapshot)
    have = parse_acl(live)
    for role in sorted(set(want) | set(have)):
        missing = want.get(role, set()) - have.get(role, set())
        extra = have.get(role, set()) - want.get(role, set())
        if missing:
            yield "GRANT", role, missing
        if extra:
            yield "REVOKE", role, extra


def _diff(target: str, snapshot: list[str] | None, live: list[str] | None,
          column: str | None = None) -> list[str]:
    lines = []
    col = f"({column}) " if column else ""
    for verb, role, letters in _changes(snapshot, live):
        words = _words(letters)
        if not words:
            continue
        prep = "TO" if verb == "GRANT" else "FROM"
        lines.append(
            f"{verb} {words} {col}ON {target} {prep} {_quote_role(role)}")
    return lines


def _fetch_snapshot(cur, label: str) -> list[tuple]:
    cur.execute(
        "SELECT kind, object, detail FROM ops.acl_snapshot "
        "WHERE label = %s AND taken_at = ("
        "  SELECT max(taken_at) FROM ops.acl_snapshot WHERE label = %s)",
        (label, label),
    )
    return cur.fetchall()


def _live_acl(cur, kind: str, object_name: str):
    if kind == "relacl":
        cur.execute(
            "SELECT c.relacl::text[], c.relkind::text FROM pg_class c "
            "WHERE c.oid = to_regclass(%s)",
            (object_name,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return row
    if kind == "proacl":
        cur.execute(
            "SELECT p.proacl::text[] FROM pg_proc p "
            "WHERE p.oid = to_regprocedure(%s)",
            (object_name,),
        )
        row = cur.fetchone()
        return None if row is None else (row[0], None)
    if kind == "attacl":
        table, _, column = object_name.rpartition(".")
        cur.execute(
            "SELECT a.attacl::text[] FROM pg_attribute a "
            "WHERE a.attrelid = to_regclass(%s) AND a.attname = %s",
            (table, column),
        )
        row = cur.fetchone()
        return None if row is None else (row[0], None)
    if kind == "defacl":
        role, _, objtype = object_name.partition(":")
        cur.execute(
            "SELECT d.defaclacl::text[] FROM pg_default_acl d "
            "JOIN pg_namespace n ON n.oid = d.defaclnamespace "
            "WHERE n.nspname = 'public' AND pg_get_userbyid(d.defaclrole) = %s "
            "AND d.defaclobjtype = %s",
            (role, objtype),
        )
        row = cur.fetchone()
        return (None, None) if row is None else (row[0], None)
    return None


def build_statements(cur, label: str) -> list[str]:
    rows = _fetch_snapshot(cur, label)
    if not rows:
        raise SystemExit(f"no ops.acl_snapshot rows for label {label}")
    out: list[str] = []
    for kind, object_name, detail in rows:
        detail = detail or {}
        if kind == "policy":
            roles = detail.get("roles") or ""
            if isinstance(roles, list):
                roles = "{" + ",".join(str(role) for role in roles) + "}"
            stmt = policy_statement(object_name, str(roles))
            if stmt:
                out.append(stmt)
            continue
        live = _live_acl(cur, kind, object_name)
        if live is None:
            out.append(f"-- skipped, not in the catalog: {kind} {object_name}")
            continue
        snap_acl = detail.get("acl")
        live_acl = live[0]
        if kind == "relacl":
            out.extend(rel_statements(object_name, live[1], snap_acl, live_acl))
        elif kind == "proacl":
            out.extend(func_statements(object_name, snap_acl, live_acl))
        elif kind == "attacl":
            out.extend(column_statements(object_name, snap_acl, live_acl))
        elif kind == "defacl":
            out.extend(default_statements(object_name, snap_acl, live_acl))
    return [line for line in out if line]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="pre_step_a_20261118")
    parser.add_argument("--dsn", default="",
                        help="Postgres DSN. Required. Not read from the environment.")
    parser.add_argument("--apply", action="store_true",
                        help="Execute the statements. Default prints them.")
    args = parser.parse_args(argv)
    if not args.dsn:
        print("refusing: --dsn is required to read ops.acl_snapshot", file=sys.stderr)
        return 2
    import psycopg2
    conn = psycopg2.connect(args.dsn)
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            statements = build_statements(cur, args.label)
        for line in statements:
            print(line + ";")
        if not args.apply:
            conn.rollback()
            print(f"-- {len(statements)} statement(s). Pass --apply to execute.")
            return 0
        with conn.cursor() as cur:
            for line in statements:
                if line.startswith("--"):
                    continue
                cur.execute(line)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"applied {len(statements)} statement(s) for {args.label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
