"""Grant or expire comped (non-IAP) app premium for one email, on the worker.

WHY THIS EXISTS. Matt, 2026-11-26: "You do the scripts." Claude's Supabase
route is read-only (CLAUDE.md section 1b, hook-enforced), so every comp change
used to end as a SQL file for Matt to paste. This is the standing route he
chose instead: a `premium_access` job in jobs/declared_jobs.json, run by the
worker, which holds DATABASE_URL. Adding a request is a reviewed diff.

WHAT IT TOUCHES, AND NOTHING ELSE
* `grant`  -- creates the email login in auth.users + auth.identities when
  none exists (the same shape as scripts/grant_tester_comped_2026_11_16.sql),
  then adds one indefinite `comped` access_grants row unless an active one
  is already there.
* `expire` -- sets expires_at = now() on the email's ACTIVE comped grants and
  appends a note. It deletes nothing: no row, no login (CLAUDE.md section 1b,
  no data is ever deleted). Access ends the moment the row expires, because
  app_grant_access_for / discord_grant_access_for read expires_at.

Both are idempotent: a second run changes nothing and says so.
"""
from __future__ import annotations

import re

ACTIONS = ("grant", "expire")
EMAIL_RE = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$")

FIND_USER_SQL = (
    "SELECT id::text FROM auth.users "
    "WHERE lower(email) = %s AND is_sso_user = false "
    "ORDER BY created_at LIMIT 1"
)

# Every token column GoTrue scans must be a non-NULL string (2026-11-16 OTP
# 500s; tests/test_auth_user_insert_columns.py checks this file too).
INSERT_USER_SQL = """
INSERT INTO auth.users (
    instance_id, id, aud, role, email, encrypted_password,
    email_confirmed_at, confirmation_token, recovery_token,
    email_change_token_new, email_change_token_current,
    reauthentication_token, email_change,
    raw_app_meta_data, raw_user_meta_data,
    created_at, updated_at, is_sso_user, is_anonymous
) VALUES (
    '00000000-0000-0000-0000-000000000000', %(uid)s::uuid,
    'authenticated', 'authenticated', %(email)s, '',
    now(), '', '', '', '', '', '',
    jsonb_build_object('provider', 'email', 'providers', jsonb_build_array('email')),
    jsonb_build_object('sub', %(uid)s, 'email', %(email)s,
                       'email_verified', true, 'phone_verified', false),
    now(), now(), false, false
)
"""

INSERT_IDENTITY_SQL = """
INSERT INTO auth.identities (
    provider_id, user_id, identity_data, provider,
    last_sign_in_at, created_at, updated_at
) VALUES (
    %(uid)s, %(uid)s::uuid,
    jsonb_build_object('sub', %(uid)s, 'email', %(email)s,
                       'email_verified', true, 'phone_verified', false),
    'email', now(), now(), now()
)
"""

INSERT_GRANT_SQL = """
INSERT INTO public.access_grants (user_id, access_source, notes)
SELECT %(uid)s::uuid, 'comped', %(note)s
WHERE NOT EXISTS (
    SELECT 1 FROM public.access_grants g
    WHERE g.user_id = %(uid)s::uuid
      AND g.access_source = 'comped'
      AND (g.expires_at IS NULL OR g.expires_at > now())
)
"""

EXPIRE_GRANT_SQL = """
UPDATE public.access_grants
SET expires_at = now(),
    notes = coalesce(notes, '') || ' | ' || %(note)s
WHERE user_id = %(uid)s::uuid
  AND access_source = 'comped'
  AND (expires_at IS NULL OR expires_at > now())
"""

STATE_SQL = """
SELECT access_source, granted_at::text, expires_at::text, notes,
       (expires_at IS NULL OR expires_at > now()) AS active
FROM public.access_grants
WHERE user_id = %s::uuid
ORDER BY granted_at
"""


def validate(args: dict) -> dict:
    action = str(args.get("action") or "").strip().lower()
    if action not in ACTIONS:
        raise ValueError(f"action must be one of {ACTIONS}; got {action!r}")
    email = str(args.get("email") or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError(f"not an email address: {email!r}")
    note = str(args.get("note") or "").strip()
    if len(note) < 10:
        raise ValueError("note must say who asked and when (10+ characters); "
                         "it is written to the grant row")
    return {"action": action, "email": email, "note": note[:300]}


def _state(conn, uid: str) -> list[dict]:
    rows = conn.execute(STATE_SQL, (uid,)).fetchall()
    return [{"source": r[0], "granted_at": r[1], "expires_at": r[2],
             "notes": r[3], "active": bool(r[4])} for r in rows]


def apply(conn, action: str, email: str, note: str) -> dict:
    """Run one validated request inside the caller's transaction. The caller
    commits. Returns what changed and the email's grants afterwards."""
    row = conn.execute(FIND_USER_SQL, (email,)).fetchone()
    uid = row[0] if row else None
    out = {"action": action, "email": email, "user_id": uid,
           "login_created": False, "grants_changed": 0}

    if action == "expire":
        if uid is None:
            out["result"] = "no login for this email; nothing to expire"
            return out
        cur = conn.execute(EXPIRE_GRANT_SQL, {"uid": uid, "note": note})
        out["grants_changed"] = cur.rowcount
        out["result"] = ("expired" if cur.rowcount else
                         "no active comped grant; nothing changed")
        out["grants"] = _state(conn, uid)
        return out

    if uid is None:
        uid = conn.execute("SELECT gen_random_uuid()::text").fetchone()[0]
        params = {"uid": uid, "email": email}
        conn.execute(INSERT_USER_SQL, params)
        conn.execute(INSERT_IDENTITY_SQL, params)
        out["user_id"] = uid
        out["login_created"] = True
    cur = conn.execute(INSERT_GRANT_SQL, {"uid": uid, "note": note})
    out["grants_changed"] = cur.rowcount
    out["result"] = ("granted" if cur.rowcount else
                     "already has an active comped grant; nothing changed")
    out["grants"] = _state(conn, uid)
    return out
