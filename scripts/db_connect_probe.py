"""
Which Supabase endpoint accepts our credential — pooler, transaction pooler, or direct?

WHY THIS EXISTS
---------------
2026-08-31: the database password was reset four times and the session pooler
rejected every one. `db_url_doctor` then proved the connection string itself is
structurally perfect — correct tenant-suffixed username, correct host, a real
21-character alphanumeric password, no encoding damage. So the string is right
and the server is still saying no, which the URL's shape cannot explain.

That leaves two very different causes, and they need different fixes:

  * The password is correct in Postgres but SUPAVISOR (the pooler) is still
    validating against a stale copy. Supabase keeps the pooler's tenant
    credentials separately from the Postgres role, and a dashboard reset has to
    land in both. If that is what happened, the DIRECT endpoint accepts the
    same password the pooler rejects, and the fix is to repoint DATABASE_URL --
    no further resets.
  * The password is simply not this project's -- a reset applied to a different
    Supabase project, or a reset that silently did not take. Then EVERY
    endpoint refuses it, and no amount of redeploying helps.

One run separates them. Guessing between them is what cost this outage its
morning.

SAFETY
------
The password is read from the environment and never printed. It is scrubbed out
of every error string before display, so this output is safe to paste anywhere.
"""

from __future__ import annotations

import os
import sys
import urllib.parse as urlparse

import psycopg2


def main() -> int:
    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        print("PROBE  fatal  DATABASE_URL is not set")
        return 2

    parts = urlparse.urlsplit(raw)
    pw = urlparse.unquote(parts.password or "")
    user = urlparse.unquote(parts.username or "")
    # The project ref is the tenant suffix on a pooler username; fall back to
    # parsing it out of a direct host so this works either way round.
    ref = user.split(".", 1)[1] if "." in user else parts.hostname.split(".")[0].removeprefix("db")

    candidates = [
        ("session-pooler-5432", raw),
        ("txn-pooler-6543", raw.replace(":5432/", ":6543/")),
        ("direct-db-5432",
         f"postgresql://postgres:{pw}@db.{ref}.supabase.co:5432/postgres"),
    ]

    print(f"PROBE  project ref {ref}")
    any_ok = False
    any_auth_reject = False
    for name, dsn in candidates:
        try:
            conn = psycopg2.connect(dsn, connect_timeout=15)
            cur = conn.cursor()
            cur.execute("select current_user, current_database()")
            who = cur.fetchone()
            conn.close()
            any_ok = True
            print(f"PROBE  {name:<20} OK    as {who[0]!r} on {who[1]!r}")
        except Exception as exc:  # noqa: BLE001 — this is a reporting tool
            msg = str(exc).strip().replace("\n", " | ")
            if pw:
                msg = msg.replace(pw, "***")
            # A refusal and an unreachable host are NOT the same evidence, and
            # conflating them is how this tool would lie: the direct host is
            # IPv6-only on Supabase without the IPv4 add-on, so from a v4-only
            # runner it fails for reasons that say nothing about the password.
            low = msg.lower()
            if "authentication failed" in low or "password" in low:
                kind, note = "AUTH", "credential refused"
                any_auth_reject = True
            elif ("could not translate host" in low or "connection refused" in low
                  or "timeout" in low or "unreachable" in low
                  or "no route to host" in low):
                kind, note = "NET ", "never reached the server — says nothing about the password"
            else:
                kind, note = "OTHER", ""
            print(f"PROBE  {name:<20} {kind}  {msg[:200]}")
            if note:
                print(f"PROBE  {'':<20}       ({note})")

    if any_ok:
        verdict = "an endpoint ACCEPTS this password — repoint DATABASE_URL at it, no further resets"
    elif any_auth_reject:
        verdict = ("every endpoint that we actually REACHED refused the credential — "
                   "the password is not this project's, or the reset did not take")
    else:
        verdict = "inconclusive — no endpoint was reachable, so nothing was learned about the password"
    print("PROBE  verdict:", verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
