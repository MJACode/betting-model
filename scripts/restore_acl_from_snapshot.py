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
    """aclitem text to {grantee: privilege letters}. Empty grantee is PUBLIC.

    A SQL NULL ACL is not an empty list. NULL means acldefault() for that
    object type and owner: the owner has the built-in rights, and a
    function also grants EXECUTE to PUBLIC. Callers expand NULL before
    this function sees it. An empty list is a real empty ACL.
    """
    out: dict[str, set[str]] = {}
    for item in items or []:
        match = _ACL.match(item)
        if not match:
            continue
        grantee = match.group(1) or "PUBLIC"
        letters = {ch for ch in match.group(2) if ch != "*"}
        out.setdefault(grantee, set()).update(letters)
    return out


def acl_type_for_relkind(relkind: str) -> str:
    """acldefault type character.

    pg_class.relkind 'S' is a sequence. acldefault uses lowercase 's' for
    that. Uppercase 'S' is a foreign server, whose default is only USAGE.
    A sequence's default is rwU. Everything else here is a table.
    """
    return "s" if relkind == "S" else "r"


def acldefault_type(objtype: str) -> str:
    """Map a pg_default_acl type onto acldefault's character.

    defaclobjtype 'S' is a sequence. acldefault('S') is a foreign server.
    """
    return "s" if objtype == "S" else objtype


def expand_null_acl(cur, acl, typ: str, owner_oid: int):
    """Replace a SQL NULL ACL with acldefault(typ, owner). Leave a real ACL."""
    if acl is not None:
        return list(acl)
    cur.execute("SELECT acldefault(%s, %s)::text[]", (typ, owner_oid))
    row = cur.fetchone()
    return list(row[0] or [])


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


def _split_defacl(object_name: str) -> tuple[str, str, bool]:
    """role, defaclobjtype, global.

    `postgres:f` is the public schema. `postgres:f:global` is
    defaclnamespace 0. The global entry is what can take PUBLIC EXECUTE
    off new functions. A per-schema entry cannot.
    """
    parts = object_name.split(":")
    role = parts[0] if parts else ""
    objtype = parts[1] if len(parts) > 1 else ""
    return role, objtype, len(parts) > 2 and parts[2] == "global"


def default_statements(object_name: str, snapshot: list[str] | None,
                       live: list[str] | None, *, global_scope: bool = False) -> list[str]:
    role, objtype, marked = _split_defacl(object_name)
    target = DEFACL_TARGET.get(objtype)
    if not role or not target:
        return []
    schema = "" if (global_scope or marked) else " IN SCHEMA public"
    prefix = (
        "ALTER DEFAULT PRIVILEGES FOR ROLE "
        f"{_quote_role(role)}{schema}"
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


def _owner_oid(cur, role: str):
    cur.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (role,))
    row = cur.fetchone()
    return None if row is None else row[0]


def _live_acl(cur, kind: str, object_name: str):
    """(acl, relkind, acldefault type, owner oid).

    acl is still NULL when the catalog stores NULL. build_statements
    expands it. A missing defacl row is the built-in default, so its
    acl is NULL on purpose and the type/owner are filled in.
    """
    if kind == "relacl":
        cur.execute(
            "SELECT c.relacl::text[], c.relkind::text, c.relowner "
            "FROM pg_class c WHERE c.oid = to_regclass(%s)",
            (object_name,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return (row[0], row[1], acl_type_for_relkind(row[1]), row[2])
    if kind == "proacl":
        cur.execute(
            "SELECT p.proacl::text[], p.proowner FROM pg_proc p "
            "WHERE p.oid = to_regprocedure(%s)",
            (object_name,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return (row[0], None, "f", row[1])
    if kind == "attacl":
        table, _, column = object_name.rpartition(".")
        cur.execute(
            "SELECT a.attacl::text[], c.relowner FROM pg_attribute a "
            "JOIN pg_class c ON c.oid = a.attrelid "
            "WHERE a.attrelid = to_regclass(%s) AND a.attname = %s",
            (table, column),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return (row[0], None, "c", row[1])
    if kind == "defacl":
        role, objtype, global_scope = _split_defacl(object_name)
        owner = _owner_oid(cur, role)
        if owner is None or objtype not in DEFACL_TARGET:
            return None
        if global_scope:
            cur.execute(
                "SELECT d.defaclacl::text[] FROM pg_default_acl d "
                "WHERE d.defaclnamespace = 0 AND d.defaclrole = %s "
                "AND d.defaclobjtype = %s",
                (owner, objtype),
            )
        else:
            cur.execute(
                "SELECT d.defaclacl::text[] FROM pg_default_acl d "
                "JOIN pg_namespace n ON n.oid = d.defaclnamespace "
                "WHERE n.nspname = 'public' AND d.defaclrole = %s "
                "AND d.defaclobjtype = %s",
                (owner, objtype),
            )
        row = cur.fetchone()
        # A missing per-schema row means nothing is added. An empty list.
        # A missing global row means the built-in default, so the caller
        # expands NULL with acldefault. A stored NULL ACL is expanded too.
        if row is None:
            acl = None if global_scope else []
        else:
            acl = row[0]
        return (acl, None, acldefault_type(objtype), owner)
    return None


def build_statements(cur, label: str) -> list[str]:
    rows = _fetch_snapshot(cur, label)
    if not rows:
        raise SystemExit(f"no ops.acl_snapshot rows for label {label}")
    out: list[str] = []
    seen_defacl: set[str] = set()
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
        snap_acl, live_acl, relkind, typ, owner = (
            detail.get("acl"), live[0], live[1], live[2], live[3])
        # Snapshot detail for relations does not store the owner. The
        # live owner is the same role: steps A and B do not change it.
        # A JSON null and a missing key are both SQL NULL.
        if snap_acl is None and detail.get("owner"):
            named = _owner_oid(cur, str(detail.get("owner")))
            if named is not None:
                owner = named
        snap_acl = expand_null_acl(cur, snap_acl, typ, owner)
        live_acl = expand_null_acl(cur, live_acl, typ, owner)
        if kind == "relacl":
            out.extend(rel_statements(object_name, relkind, snap_acl, live_acl))
        elif kind == "proacl":
            out.extend(func_statements(object_name, snap_acl, live_acl))
        elif kind == "attacl":
            out.extend(column_statements(object_name, snap_acl, live_acl))
        elif kind == "defacl":
            seen_defacl.add(object_name)
            out.extend(default_statements(object_name, snap_acl, live_acl))
    out.extend(_unlisted_global_function_defaults(cur, seen_defacl))
    return [line for line in out if line]


def _unlisted_global_function_defaults(cur, seen: set[str]) -> list[str]:
    """Live global function defaults the snapshot does not name.

    Step B writes `postgres:f:global` as owner-only EXECUTE. A pre-step
    snapshot has no such row. The built-in default is acldefault, which
    includes PUBLIC EXECUTE. The diff grants that back.
    """
    cur.execute(
        "SELECT pg_get_userbyid(d.defaclrole), d.defaclacl::text[], d.defaclrole "
        "FROM pg_default_acl d "
        "WHERE d.defaclnamespace = 0 AND d.defaclobjtype = 'f'"
    )
    lines: list[str] = []
    for role, acl, oid in cur.fetchall():
        key = f"{role}:f:global"
        if key in seen:
            continue
        baseline = expand_null_acl(cur, None, "f", oid)
        lines.extend(default_statements(key, baseline, list(acl or []), global_scope=True))
    return lines


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
