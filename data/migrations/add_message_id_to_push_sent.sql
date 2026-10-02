-- Record WHICH Discord message a ledgered post went out in.
--
-- Without this a post is fire-and-forget: _post() did not pass ?wait=true, so
-- Discord returned 204 with no body and no message id, and the webhook API has
-- no endpoint to list a channel's messages afterwards. The consequence showed up
-- on 2026-08-28 -- the morning slate published a stake that changed hours later,
-- and there was no way to delete or edit it. The only remedy was a correction
-- posted beneath the stale numbers.
--
-- With the id stored, a restatement can DELETE the original
-- (DELETE /webhooks/{id}/{token}/messages/{message_id}) and repost, leaving the
-- channel clean instead of stacked.
--
-- Nullable on purpose: every row written before this exists keeps NULL, and the
-- delete path skips those rather than guessing.
--
-- IDEMPOTENT, AND A NO-OP ONCE THE COLUMN EXISTS. ALTER TABLE ... ADD COLUMN
-- IF NOT EXISTS still takes AccessExclusiveLock before it notices the column
-- (PostgreSQL locks first, then checks). Hourly run
-- b22f8e4fb9e34d27858c341e46ce635c on 2026-10-01 waited on push_sent
-- (oid 25944) until statement_timeout (2min) cancelled it. The catalog check
-- below reads pg_attribute and returns without opening push_sent.

DO $mig$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name = 'push_sent'
       AND column_name = 'message_id'
  ) THEN
    RAISE NOTICE 'push_sent.message_id already present - skipping';
    RETURN;
  END IF;

  ALTER TABLE public.push_sent ADD COLUMN IF NOT EXISTS message_id TEXT;
END $mig$;
