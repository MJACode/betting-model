-- Images and an optional external reply on manual posts.
--
-- Adds three nullable columns to social_post_queue. A second pass returns
-- on the catalog read below and does not take the table lock. Does not
-- insert rows, does not rewrite the seeded ledger thread, and does not
-- touch picks or push_sent.
--
-- media_urls holds up to 4 https URLs. The drain fetches those bytes and
-- uploads them. media_ids is what X returned, committed before the tweet,
-- so a retry does not upload an index that already has an id. No storage
-- bucket is created here: a public https URL is enough, including a public
-- Supabase Storage object URL.
--
-- reply_to_tweet_id, when null, leaves thread chaining as it was.
--
-- One DO block. data/view_migrations.py runs each file as one statement.

DO $mig$
BEGIN
  IF to_regclass('public.social_post_queue') IS NULL THEN
    RAISE EXCEPTION 'social_post_queue is not created yet';
  END IF;

  IF EXISTS (
       SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'social_post_queue'
          AND column_name = 'media_urls'
     )
     AND EXISTS (
       SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'social_post_queue'
          AND column_name = 'media_ids'
     )
     AND EXISTS (
       SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'social_post_queue'
          AND column_name = 'reply_to_tweet_id'
     )
     AND EXISTS (
       SELECT 1 FROM pg_constraint WHERE conname = 'social_post_queue_media_urls_len'
     )
     AND EXISTS (
       SELECT 1 FROM pg_constraint WHERE conname = 'social_post_queue_media_ids_len'
     )
     AND EXISTS (
       SELECT 1 FROM pg_constraint WHERE conname = 'social_post_queue_reply_to_tweet_id'
     )
  THEN
    RETURN;
  END IF;

  ALTER TABLE public.social_post_queue
    ADD COLUMN IF NOT EXISTS media_urls TEXT[],
    ADD COLUMN IF NOT EXISTS media_ids TEXT[],
    ADD COLUMN IF NOT EXISTS reply_to_tweet_id TEXT;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'social_post_queue_media_urls_len'
  ) THEN
    ALTER TABLE public.social_post_queue
      ADD CONSTRAINT social_post_queue_media_urls_len
      CHECK (media_urls IS NULL OR cardinality(media_urls) <= 4);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'social_post_queue_media_ids_len'
  ) THEN
    ALTER TABLE public.social_post_queue
      ADD CONSTRAINT social_post_queue_media_ids_len
      CHECK (media_ids IS NULL OR cardinality(media_ids) <= 4);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'social_post_queue_reply_to_tweet_id'
  ) THEN
    ALTER TABLE public.social_post_queue
      ADD CONSTRAINT social_post_queue_reply_to_tweet_id
      CHECK (reply_to_tweet_id IS NULL OR reply_to_tweet_id ~ '^[0-9]{1,19}$');
  END IF;
END
$mig$;
