-- One queued update of the @SignalBasePicks X profile.
--
-- The pick slate, the recaps, and social_post_queue are unchanged. The
-- 5-minute drain applies a queued row once. anon and authenticated get
-- nothing. The worker's DATABASE_URL writes it.
--
-- The early return is a separate statement from the create path. A
-- 'rel'::regclass cast is planned even when AND would not run it, and it
-- errors when the table is absent, so a fresh database never reaches
-- CREATE. to_regclass returns NULL instead. The privilege checks run only
-- after that read says the table is there, because has_table_privilege
-- errors on a missing relation too. A locked table still returns here and
-- does not insert the seed again.
--
-- The seed is one row, status queued. Name is 30 characters. Description
-- is 156. Neither needed trimming. The URL is the sheet, 100 characters.
-- It is a single-quoted literal: data.db rewrites a ? outside single
-- quotes to %s, which turned this URL into 101 characters.
--
-- One DO block. data/view_migrations.py runs each file as one statement.

DO $mig$
BEGIN
  IF to_regclass('public.social_profile_update') IS NOT NULL THEN
    IF EXISTS (
         SELECT 1 FROM pg_class
          WHERE oid = to_regclass('public.social_profile_update')
            AND relrowsecurity
       )
       AND NOT has_table_privilege('anon', 'public.social_profile_update', 'SELECT')
       AND NOT has_table_privilege('anon', 'public.social_profile_update', 'INSERT')
       AND NOT has_table_privilege('anon', 'public.social_profile_update', 'UPDATE')
       AND NOT has_table_privilege('anon', 'public.social_profile_update', 'DELETE')
       AND NOT has_table_privilege('authenticated', 'public.social_profile_update', 'SELECT')
       AND NOT has_table_privilege('authenticated', 'public.social_profile_update', 'INSERT')
       AND NOT has_table_privilege('authenticated', 'public.social_profile_update', 'UPDATE')
       AND NOT has_table_privilege('authenticated', 'public.social_profile_update', 'DELETE')
    THEN
      RETURN;
    END IF;
  END IF;

  CREATE TABLE IF NOT EXISTS public.social_profile_update (
    id           BIGSERIAL PRIMARY KEY,
    name         TEXT,
    description  TEXT,
    url          TEXT,
    status       TEXT NOT NULL DEFAULT 'queued',
    response     TEXT,
    error        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_at   TIMESTAMPTZ,
    CONSTRAINT social_profile_update_status CHECK (
      status IN ('queued', 'done', 'failed')
    ),
    CONSTRAINT social_profile_update_name_len CHECK (
      name IS NULL OR char_length(name) <= 50
    ),
    CONSTRAINT social_profile_update_description_len CHECK (
      description IS NULL OR char_length(description) <= 160
    )
  );

  INSERT INTO public.social_profile_update (name, description, url)
  SELECT $pname$SignalBase | Model Picks + CLV$pname$,
         $pdesc$Model-driven picks: NHL, NFL, CFB, NBA & more. Every posted pick graded, every closing line tracked. Full record below. Discord: discord.gg/Sge4Djj2xT · 21+$pdesc$,
         'https://docs.google.com/spreadsheets/d/1FaUkZnjirMrh0G3Je3RpNoO6d9wq6CcKGZr9bbSovXo/edit?usp=sharing'
   WHERE NOT EXISTS (SELECT 1 FROM public.social_profile_update);

  REVOKE ALL ON public.social_profile_update FROM anon, authenticated;
  REVOKE ALL ON SEQUENCE public.social_profile_update_id_seq FROM anon, authenticated;
  ALTER TABLE public.social_profile_update ENABLE ROW LEVEL SECURITY;
END
$mig$;
