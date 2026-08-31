"""
Diagnose a DATABASE_URL without ever printing the secret.

WHY THIS EXISTS
---------------
2026-08-31: the Supabase password was reset TWICE and the pooler rejected both,
each time with the identical `password authentication failed for user
"postgres"`. That message is the same for a wrong password, a password mangled
by URI parsing, an empty password, and a placeholder pasted verbatim — so three
deploy-and-see rounds produced no new information. The error text is not a
diagnosis; the SHAPE of the string is.

So this reports the shape and never the value. Every field is either a
structural fact (scheme, host, port), a length, or a character CLASS. The
password itself is never printed, logged, or returned, which is what makes it
safe to run on the worker and paste the output into a chat.

WHAT IT CATCHES, that the driver's error does not
-------------------------------------------------
  * the Supabase Connect modal's literal [YOUR-PASSWORD] placeholder
  * a password containing URI-reserved characters that were not
    percent-encoded -- @ is the killer, because libpq splits userinfo from host
    at the LAST @, so an un-encoded one silently moves part of the password
    into the host or truncates it
  * an empty password (the URI had no password field at all)
  * leading/trailing whitespace or a trailing newline on the variable
  * a session-pooler host paired with a bare `postgres` username, or the
    reverse -- the two halves have to agree

USAGE
-----
    python -m scripts.db_url_doctor              # reads $DATABASE_URL
    python -m scripts.db_url_doctor --connect    # also attempts a connection

Pass a candidate string on stdin to check it BEFORE setting it in Railway:

    echo -n 'postgresql://...' | python -m scripts.db_url_doctor --stdin
"""

from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlsplit, unquote

from scripts._envfile import database_url

# URI-reserved characters that MUST be percent-encoded inside userinfo.
# '@' and ':' are the two that actually corrupt parsing; the rest are listed
# because a password containing them is a latent version of the same bug the
# moment the string is copied through something less forgiving.
_RESERVED = "@:/?#[]"
_SUBDELIMS = "!$&'()*+,;="


def _classes(s: str) -> str:
    """Describe a string by character CLASS, never by content."""
    if not s:
        return "(empty)"
    bits = []
    if any(c.islower() for c in s):
        bits.append("lower")
    if any(c.isupper() for c in s):
        bits.append("upper")
    if any(c.isdigit() for c in s):
        bits.append("digit")
    reserved = sorted({c for c in s if c in _RESERVED})
    subdelims = sorted({c for c in s if c in _SUBDELIMS})
    other = sorted({c for c in s if not c.isalnum()
                    and c not in _RESERVED and c not in _SUBDELIMS})
    if reserved:
        bits.append(f"RESERVED:{''.join(reserved)}")
    if subdelims:
        bits.append(f"sub-delims:{''.join(subdelims)}")
    if other:
        bits.append(f"other:{''.join(other)}")
    return ", ".join(bits)


def diagnose(raw: str) -> list[tuple[str, str, str]]:
    """Return (level, label, detail) rows. Never includes the password."""
    rows: list[tuple[str, str, str]] = []

    def ok(label, detail=""):
        rows.append(("OK", label, detail))

    def warn(label, detail=""):
        rows.append(("WARN", label, detail))

    def bad(label, detail=""):
        rows.append(("FAIL", label, detail))

    if not raw:
        bad("DATABASE_URL", "not set / empty")
        return rows

    stripped = raw.strip()
    if stripped != raw:
        bad("whitespace", "the value has leading or trailing whitespace "
                          "(a trailing newline is the usual cause) -- libpq "
                          "sends it as part of the string")
    else:
        ok("whitespace", "none")

    # The placeholder is checked on the RAW string, before parsing. It contains
    # square brackets, which urlsplit reads as an IPv6 literal and rejects with
    # a message about IP addresses -- technically true and completely
    # unhelpful, since the actual problem is that no password was ever pasted.
    # Found by this tool's own test.
    for token in ("[YOUR-PASSWORD]", "[YOUR_PASSWORD]", "[PASSWORD]",
                  "<YOUR-PASSWORD>", "YOUR-PASSWORD"):
        if token.lower() in stripped.lower():
            bad("password", f"the string still contains the literal "
                            f"{token} placeholder -- the Supabase Connect "
                            f"modal does NOT fill your password in for you")
            return rows

    try:
        parts = urlsplit(stripped)
    except ValueError as exc:
        bad("parse", f"the string is not a valid URI: {exc}")
        return rows

    def _safe(fn, label):
        """urlsplit defers validation to the accessors, so .hostname and .port
        each raise on exactly the malformed strings this tool exists to
        explain. A diagnostic that dies on bad input is not a diagnostic."""
        try:
            return fn()
        except ValueError as exc:
            bad(label, f"unparseable ({exc}). This is almost always an "
                       f"un-encoded special character in the password "
                       f"splitting the URI in the wrong place")
            return None

    if parts.scheme not in ("postgres", "postgresql"):
        bad("scheme", f"{parts.scheme!r} -- expected postgresql://")
    else:
        ok("scheme", parts.scheme)

    # ── host / port / db ──────────────────────────────────────────────────
    host = _safe(lambda: parts.hostname, "host") or ""
    ok("host", host) if host else bad("host", "missing or unparseable")
    port = _safe(lambda: parts.port, "port")
    if port:
        ok("port", str(port))
    dbname = parts.path.lstrip("/")
    ok("database", dbname or "(missing)") if dbname else bad("database", "missing")

    # ── username, and whether it agrees with the host ─────────────────────
    user = unquote(parts.username or "")
    is_pooler = "pooler.supabase.com" in host
    if not user:
        bad("username", "missing")
    elif is_pooler and "." not in user:
        bad("username", f"{user!r} on a POOLER host -- supavisor needs "
                        f"postgres.<project-ref> to resolve the tenant")
    elif is_pooler:
        ok("username", f"{user.split('.')[0]}.<ref> (tenant suffix present)")
    else:
        ok("username", user)

    # ── password: shape only, never the value ─────────────────────────────
    pw_raw = parts.password
    if pw_raw is None:
        bad("password", "the URI has NO password field at all")
        return rows

    pw = unquote(pw_raw)
    if not pw:
        bad("password", "present but empty")
        return rows

    if pw.upper().strip("[]<>{}") in ("YOUR-PASSWORD", "YOUR_PASSWORD",
                                      "PASSWORD"):
        bad("password", "this is the Supabase Connect modal's PLACEHOLDER, "
                        "not a real password")
        return rows

    ok("password length", f"{len(pw)} chars (decoded)")
    rows.append(("INFO", "password charset", _classes(pw)))

    # The one that actually corrupts parsing.
    if pw_raw != pw:
        ok("password encoding", "percent-encoded in the URI (correct)")
    hazards = sorted({c for c in pw if c in _RESERVED})
    if hazards and pw_raw == pw:
        bad("password encoding",
            f"contains {''.join(hazards)!r} un-encoded. libpq splits userinfo "
            f"from host at the LAST '@', so this is parsed wrong -- either "
            f"percent-encode it, or reset to an alphanumeric-only password")
    elif not hazards:
        ok("password encoding", "no URI-reserved characters -- safe as-is")

    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stdin", action="store_true",
                    help="read the candidate URL from stdin instead of the env")
    ap.add_argument("--connect", action="store_true",
                    help="also attempt a real connection and report the error")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.stdin else database_url()

    print("DATABASE_URL shape (the password is never printed)")
    print("=" * 66)
    worst = 0
    for level, label, detail in diagnose(raw):
        print(f"  {level:<5} {label:<20} {detail}")
        if level == "FAIL":
            worst = 2
        elif level == "WARN" and worst < 1:
            worst = 1

    if args.connect and raw.strip():
        print("-" * 66)
        try:
            import psycopg2
            conn = psycopg2.connect(raw.strip(), connect_timeout=15)
            cur = conn.cursor()
            cur.execute("select current_user, current_database()")
            who = cur.fetchone()
            conn.close()
            print(f"  OK    connect              authenticated as {who[0]!r} "
                  f"on {who[1]!r}")
        except Exception as exc:  # noqa: BLE001 — reporting tool
            worst = 2
            print(f"  FAIL  connect              {str(exc).strip()[:400]}")

    print("=" * 66)
    print({0: "Shape looks correct.",
           1: "Shape is usable but something is off.",
           2: "Found a problem above."}[worst])
    return worst if worst == 2 else 0


if __name__ == "__main__":
    raise SystemExit(main())
