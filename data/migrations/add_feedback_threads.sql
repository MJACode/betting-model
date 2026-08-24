-- Migration: add_feedback_threads
-- Apply via Supabase MCP apply_migration (project ref vvprgnrmzeekokzkrkfu) or
-- the SQL editor. Mirrors the blocks in supabase_schema.sql + db_setup.py.
--
-- In-app, two-way feedback. Replaces the mailto: hand-off in the mobile app:
-- the user writes feedback inside the app, we answer it, and the answer lands
-- back in the app (plus a push notification).
--
--   feedback_threads  — one conversation, owned by a device (and a user_id once
--     auth is on). Carries status + last_read_at so the app can show an unread
--     badge without reading anyone else's rows.
--   feedback_messages — the turns. sender is 'user' or 'support'.
--
-- NOTE on the pre-existing `feedback` table: it is an empty, undocumented
-- insert-only table from the website era. Nothing reads or writes it and it is
-- deliberately left untouched here — these two tables are the app's path.
--
-- ── Why RPCs instead of RLS policies ────────────────────────────────────────
-- The app talks to Supabase with the anon key and has no session (auth is dark),
-- so a policy has no identity to filter on: a plain `USING (true)` SELECT policy
-- would let any anon key read EVERY user's feedback. So both tables keep RLS on
-- with no policies at all, anon's default table grants are revoked, and the only
-- way in is the SECURITY DEFINER functions below, each of which requires the
-- caller to present the device_id that owns the row. That is the same trust
-- model tracked_bets / SharpSports already use here: the device_id is an
-- unguessable per-install UUID acting as a bearer token.

CREATE TABLE IF NOT EXISTS feedback_threads (
    id              BIGSERIAL PRIMARY KEY,
    device_id       TEXT NOT NULL,
    user_id         UUID,                     -- set when signed in (auth is dark today)
    category        TEXT NOT NULL DEFAULT 'other',   -- bug | idea | picks | billing | other
    subject         TEXT NOT NULL,            -- derived from the opening message
    app_version     TEXT,
    platform        TEXT,
    status          TEXT NOT NULL DEFAULT 'open',    -- open | answered | closed
    created_at      TEXT DEFAULT (NOW()::TEXT),
    last_message_at TEXT DEFAULT (NOW()::TEXT),
    last_read_at    TEXT                      -- when this DEVICE last opened the thread
);

CREATE TABLE IF NOT EXISTS feedback_messages (
    id         BIGSERIAL PRIMARY KEY,
    thread_id  BIGINT NOT NULL REFERENCES feedback_threads(id) ON DELETE CASCADE,
    sender     TEXT NOT NULL CHECK (sender IN ('user', 'support')),
    body       TEXT NOT NULL,
    created_at TEXT DEFAULT (NOW()::TEXT)
);

CREATE INDEX IF NOT EXISTS idx_feedback_threads_device ON feedback_threads(device_id);
CREATE INDEX IF NOT EXISTS idx_feedback_threads_status ON feedback_threads(status);
CREATE INDEX IF NOT EXISTS idx_feedback_messages_thread ON feedback_messages(thread_id, id);

ALTER TABLE feedback_threads  ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback_messages ENABLE ROW LEVEL SECURITY;

-- No policies, and no direct grants: everything goes through the functions.
-- Supabase's default privileges grant anon/authenticated ALL on new public
-- tables (the session-113 matview lesson), so revoke explicitly rather than
-- leaning on RLS alone.
REVOKE ALL ON TABLE feedback_threads  FROM anon, authenticated;
REVOKE ALL ON TABLE feedback_messages FROM anon, authenticated;
REVOKE ALL ON SEQUENCE feedback_threads_id_seq  FROM anon, authenticated;
REVOKE ALL ON SEQUENCE feedback_messages_id_seq FROM anon, authenticated;

-- ── RPCs (the only path in for the anon key) ────────────────────────────────
-- Every one takes the caller's device_id and filters on it. SECURITY DEFINER so
-- they can reach past RLS; search_path pinned so a definer function can't be
-- redirected at a shadowed table.

-- Post feedback. Omit p_thread_id to open a new conversation; pass one to reply
-- into a conversation this device already owns. Returns the thread id.
CREATE OR REPLACE FUNCTION public.feedback_submit(
    p_device_id   TEXT,
    p_message     TEXT,
    p_category    TEXT   DEFAULT 'other',
    p_app_version TEXT   DEFAULT NULL,
    p_platform    TEXT   DEFAULT NULL,
    p_thread_id   BIGINT DEFAULT NULL,
    p_user_id     UUID   DEFAULT NULL
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_body   TEXT := btrim(COALESCE(p_message, ''));
    v_cat    TEXT := lower(COALESCE(p_category, 'other'));
    v_thread BIGINT;
    v_recent INT;
    v_open   INT;
BEGIN
    IF p_device_id IS NULL OR length(btrim(p_device_id)) < 8 OR length(p_device_id) > 64 THEN
        RAISE EXCEPTION 'invalid device';
    END IF;
    IF v_body = '' THEN
        RAISE EXCEPTION 'empty message';
    END IF;
    IF length(v_body) > 4000 THEN
        RAISE EXCEPTION 'message too long';
    END IF;
    IF v_cat NOT IN ('bug', 'idea', 'picks', 'billing', 'other') THEN
        v_cat := 'other';
    END IF;

    -- Abuse guards. Nothing here is authenticated, so bound what one device can
    -- write: 20 messages/hour and 25 live conversations.
    SELECT count(*) INTO v_recent
      FROM feedback_messages m
      JOIN feedback_threads t ON t.id = m.thread_id
     WHERE t.device_id = p_device_id
       AND m.sender = 'user'
       AND m.created_at::timestamptz > now() - interval '1 hour';
    IF v_recent >= 20 THEN
        RAISE EXCEPTION 'too many messages, try again later';
    END IF;

    IF p_thread_id IS NOT NULL THEN
        SELECT id INTO v_thread
          FROM feedback_threads
         WHERE id = p_thread_id AND device_id = p_device_id;
        IF v_thread IS NULL THEN
            RAISE EXCEPTION 'thread not found';
        END IF;
    ELSE
        SELECT count(*) INTO v_open
          FROM feedback_threads
         WHERE device_id = p_device_id AND status <> 'closed';
        IF v_open >= 25 THEN
            RAISE EXCEPTION 'too many open conversations';
        END IF;

        INSERT INTO feedback_threads (device_id, user_id, category, subject,
                                      app_version, platform)
        VALUES (p_device_id, p_user_id, v_cat,
                left(regexp_replace(v_body, '\s+', ' ', 'g'), 80),
                p_app_version, p_platform)
        RETURNING id INTO v_thread;
    END IF;

    INSERT INTO feedback_messages (thread_id, sender, body)
    VALUES (v_thread, 'user', v_body);

    -- A user turn reopens the thread (it needs an answer again) and clears the
    -- unread badge — they are looking right at it.
    UPDATE feedback_threads
       SET last_message_at = now()::TEXT,
           last_read_at    = now()::TEXT,
           status          = 'open'
     WHERE id = v_thread;

    RETURN v_thread;
END;
$$;

-- This device's conversations, newest activity first, with the unread-support
-- count the app badges on.
CREATE OR REPLACE FUNCTION public.feedback_threads_for_device(p_device_id TEXT)
RETURNS TABLE (
    thread_id       BIGINT,
    category        TEXT,
    subject         TEXT,
    status          TEXT,
    created_at      TEXT,
    last_message_at TEXT,
    last_read_at    TEXT,
    message_count   INT,
    unread_count    INT,
    last_sender     TEXT,
    last_body       TEXT
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT t.id, t.category, t.subject, t.status, t.created_at,
           t.last_message_at, t.last_read_at,
           (SELECT count(*)::INT FROM feedback_messages m WHERE m.thread_id = t.id),
           (SELECT count(*)::INT FROM feedback_messages m
             WHERE m.thread_id = t.id AND m.sender = 'support'
               AND (t.last_read_at IS NULL
                    OR m.created_at::timestamptz > t.last_read_at::timestamptz)),
           (SELECT m.sender FROM feedback_messages m
             WHERE m.thread_id = t.id ORDER BY m.id DESC LIMIT 1),
           (SELECT left(m.body, 160) FROM feedback_messages m
             WHERE m.thread_id = t.id ORDER BY m.id DESC LIMIT 1)
      FROM feedback_threads t
     WHERE t.device_id = p_device_id
       AND length(COALESCE(p_device_id, '')) >= 8
     ORDER BY t.last_message_at DESC
     LIMIT 100;
$$;

-- The turns of one conversation, oldest first. Joined back to the thread so a
-- thread_id belonging to someone else returns nothing rather than their mail.
CREATE OR REPLACE FUNCTION public.feedback_messages_for_thread(
    p_device_id TEXT,
    p_thread_id BIGINT
)
RETURNS TABLE (message_id BIGINT, sender TEXT, body TEXT, created_at TEXT)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT m.id, m.sender, m.body, m.created_at
      FROM feedback_messages m
      JOIN feedback_threads t ON t.id = m.thread_id
     WHERE m.thread_id = p_thread_id
       AND t.device_id = p_device_id
       AND length(COALESCE(p_device_id, '')) >= 8
     ORDER BY m.id
     LIMIT 500;
$$;

CREATE OR REPLACE FUNCTION public.feedback_mark_read(
    p_device_id TEXT,
    p_thread_id BIGINT
) RETURNS VOID
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    UPDATE feedback_threads
       SET last_read_at = now()::TEXT
     WHERE id = p_thread_id
       AND device_id = p_device_id
       AND length(COALESCE(p_device_id, '')) >= 8;
$$;

-- Scalar for the Settings badge — cheaper than pulling every thread to sum.
CREATE OR REPLACE FUNCTION public.feedback_unread_count(p_device_id TEXT)
RETURNS INT
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT COALESCE(count(*), 0)::INT
      FROM feedback_messages m
      JOIN feedback_threads t ON t.id = m.thread_id
     WHERE t.device_id = p_device_id
       AND length(COALESCE(p_device_id, '')) >= 8
       AND m.sender = 'support'
       AND (t.last_read_at IS NULL
            OR m.created_at::timestamptz > t.last_read_at::timestamptz);
$$;

-- SECURITY DEFINER functions are granted to PUBLIC by default — narrow them.
REVOKE ALL ON FUNCTION public.feedback_submit(TEXT, TEXT, TEXT, TEXT, TEXT, BIGINT, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.feedback_threads_for_device(TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.feedback_messages_for_thread(TEXT, BIGINT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.feedback_mark_read(TEXT, BIGINT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.feedback_unread_count(TEXT) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.feedback_submit(TEXT, TEXT, TEXT, TEXT, TEXT, BIGINT, UUID) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.feedback_threads_for_device(TEXT) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.feedback_messages_for_thread(TEXT, BIGINT) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.feedback_mark_read(TEXT, BIGINT) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.feedback_unread_count(TEXT) TO anon, authenticated;

-- ── Support side ────────────────────────────────────────────────────────────
-- How we answer. NOT callable with the anon key — only the service role (the
-- pipeline's DATABASE_URL, the Supabase SQL editor, Claude mobile's Supabase
-- MCP). Wraps the message + status + last_message_at in one call so a
-- hand-written UPDATE can't leave an answered thread looking unanswered.
CREATE OR REPLACE FUNCTION public.feedback_reply(
    p_thread_id BIGINT,
    p_body      TEXT,
    p_close     BOOLEAN DEFAULT FALSE
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_body TEXT := btrim(COALESCE(p_body, ''));
    v_id   BIGINT;
BEGIN
    IF v_body = '' THEN
        RAISE EXCEPTION 'empty reply';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM feedback_threads WHERE id = p_thread_id) THEN
        RAISE EXCEPTION 'thread % not found', p_thread_id;
    END IF;

    INSERT INTO feedback_messages (thread_id, sender, body)
    VALUES (p_thread_id, 'support', v_body)
    RETURNING id INTO v_id;

    UPDATE feedback_threads
       SET last_message_at = now()::TEXT,
           status          = CASE WHEN p_close THEN 'closed' ELSE 'answered' END
     WHERE id = p_thread_id;

    RETURN v_id;
END;
$$;

-- REVOKE FROM PUBLIC IS NOT ENOUGH HERE. Supabase's default privileges grant
-- EXECUTE on new public functions to anon and authenticated BY NAME, so a
-- PUBLIC-only revoke leaves the function callable with the anon key — verified
-- live: anon could post as 'support' until these roles were named explicitly.
REVOKE ALL ON FUNCTION public.feedback_reply(BIGINT, TEXT, BOOLEAN) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.feedback_reply(BIGINT, TEXT, BOOLEAN) TO service_role;
