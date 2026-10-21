-- Manual posts and threads for @SignalBasePicks.
--
-- The pick slate and the results recaps keep using push_sent. This table is
-- a person's queue. tracking.social_posts drains it. A second pass returns
-- on the catalog read below and does not insert the seed again, so a deleted
-- thread is not resurrected and posted twice.
--
-- anon and authenticated get nothing. The worker's DATABASE_URL writes it.
-- The SQL editor (the table owner) can insert. The app's anon key cannot.
--
-- The seed is Draft 1, the all-time ledger thread, queued and not posted.
-- Position 1 asks to be pinned. The drain records that the API cannot pin.
-- Position 3 contains discord.gg and sets allow_link, because X bills a URL
-- at the link rate. Status stays 'queued' until the worker drains it.
--
-- One DO block. data/view_migrations.py runs each file as one statement.
--
-- The early return is a separate statement from the create path. A
-- 'rel'::regclass cast is planned even when AND would not run it, and it
-- errors when the table is absent, so a fresh database never reaches
-- CREATE. to_regclass returns NULL instead. The privilege checks run only
-- after that read says the table is there, because has_table_privilege
-- errors on a missing relation too. A locked table still returns here and
-- does not insert the seed again.

DO $mig$
BEGIN
  IF to_regclass('public.social_post_queue') IS NOT NULL THEN
    IF EXISTS (
         SELECT 1 FROM pg_class
          WHERE oid = to_regclass('public.social_post_queue')
            AND relrowsecurity
       )
       AND NOT has_table_privilege('anon', 'public.social_post_queue', 'SELECT')
       AND NOT has_table_privilege('anon', 'public.social_post_queue', 'INSERT')
       AND NOT has_table_privilege('anon', 'public.social_post_queue', 'UPDATE')
       AND NOT has_table_privilege('anon', 'public.social_post_queue', 'DELETE')
       AND NOT has_table_privilege('authenticated', 'public.social_post_queue', 'SELECT')
       AND NOT has_table_privilege('authenticated', 'public.social_post_queue', 'INSERT')
       AND NOT has_table_privilege('authenticated', 'public.social_post_queue', 'UPDATE')
       AND NOT has_table_privilege('authenticated', 'public.social_post_queue', 'DELETE')
    THEN
      RETURN;
    END IF;
  END IF;

  CREATE TABLE IF NOT EXISTS public.social_post_queue (
    id            BIGSERIAL PRIMARY KEY,
    thread_key    TEXT NOT NULL,
    position      INTEGER NOT NULL,
    body          TEXT NOT NULL,
    allow_link    BOOLEAN NOT NULL DEFAULT FALSE,
    pin           BOOLEAN NOT NULL DEFAULT FALSE,
    scheduled_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status        TEXT NOT NULL DEFAULT 'queued',
    tweet_id      TEXT,
    tweet_url     TEXT,
    pin_status    TEXT,
    pin_note      TEXT,
    error         TEXT,
    claimed_at    TIMESTAMPTZ,
    posted_at     TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT social_post_queue_position_positive CHECK (position >= 1),
    CONSTRAINT social_post_queue_body_len CHECK (char_length(body) BETWEEN 1 AND 280),
    CONSTRAINT social_post_queue_status CHECK (
      status IN ('queued', 'posting', 'posted', 'failed', 'uncertain')
    ),
    CONSTRAINT social_post_queue_thread_pos UNIQUE (thread_key, position)
  );

  INSERT INTO public.social_post_queue
    (thread_key, position, body, allow_link, pin)
  SELECT v.thread_key, v.position, v.body, v.allow_link, v.pin
    FROM (VALUES
    ('all-time-ledger-2026-10-20', 1, $ledger1$📒 SignalBase all-time ledger (since Aug 29):

468-398-3 · +30.35u · +3.1% ROI
Beat the closing line on 267 of 490 CLV-graded picks (54.5%)

Every graded pick counts toward units. Wins and losses.

By sport 🧵👇$ledger1$, false, true),
    ('all-time-ledger-2026-10-20', 2, $ledger2$Where it's made money:
🏀 WNBA 46-24, +23.48u
🏒 NHL 76-56, +16.01u
🏈 NCAAF 109-90, +10.20u
🥊 UFC 1-0, +1.00u

Where it hasn't (yet):
⚾ MLB 193-187-2, −15.45u
🏈 NFL 43-41-1, −4.90u

We post both.$ledger2$, false, false),
    ('all-time-ledger-2026-10-20', 3, $ledger3$Why CLV matters more than a hot week: if you keep getting a better number than where the market closes, the edge is real even through a bad night.

Full pick log + tonight's card in Discord 👇
discord.gg/Sge4Djj2xT$ledger3$, true, false)
    ) AS v(thread_key, position, body, allow_link, pin)
   WHERE NOT EXISTS (
     SELECT 1 FROM public.social_post_queue q
      WHERE q.thread_key = 'all-time-ledger-2026-10-20'
   );

  REVOKE ALL ON public.social_post_queue FROM anon, authenticated;
  REVOKE ALL ON SEQUENCE public.social_post_queue_id_seq FROM anon, authenticated;
  ALTER TABLE public.social_post_queue ENABLE ROW LEVEL SECURITY;
END
$mig$;
