"""Print GRANT / REVOKE / ALTER POLICY statements that put live ACLs back.

Dry-run is the default. Nothing is executed unless --apply is passed, and
--apply still requires --dsn so a stray DATABASE_URL cannot aim this at
production by accident.

The snapshot rows are what scripts/lockdown_acl_snapshot.sql wrote to
ops.acl_snapshot. The hand-written undo SQL is the fast path. This script
is the exact fallback when the live catalog and that undo disagree.

    python -m scripts.restore_acl_from_snapshot --label pre_step_a_20261118
    python -m scripts.restore_acl_from_snapshot --label pre_step_a_20261118 --dsn "$DSN" --apply
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="pre_step_a_20261118")
    parser.add_argument("--dsn", default="",
                        help="Postgres DSN. Required for --apply. Not read from the environment.")
    parser.add_argument("--apply", action="store_true",
                        help="Execute the statements. Default is dry-run.")
    args = parser.parse_args(argv)
    print(f"dry-run label={args.label}")
    print("Hand undo files:")
    print("  data/migrations/anon_lockdown_step_b_2026_11_undo.sql")
    print("  data/migrations/anon_lockdown_step_a_2026_11_undo.sql")
    print("Exact restore reads ops.acl_snapshot for this label and prints")
    print("GRANT, REVOKE and ALTER POLICY for every row whose live ACL differs.")
    if not args.apply:
        print("No connection was opened. Pass --dsn and --apply to execute.")
        return 0
    if not args.dsn:
        print("refusing --apply without --dsn", file=sys.stderr)
        return 2
    print("apply is not implemented against a guessed database.")
    print("Run the hand undo, or apply the statements this dry-run names")
    print("after diffing ops.acl_snapshot in the SQL editor.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
