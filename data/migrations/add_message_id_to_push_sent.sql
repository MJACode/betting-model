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
-- IDEMPOTENT: ADD COLUMN IF NOT EXISTS. Safe on every pass.

DO $mig$
BEGIN
  ALTER TABLE public.push_sent ADD COLUMN IF NOT EXISTS message_id TEXT;
END $mig$;
