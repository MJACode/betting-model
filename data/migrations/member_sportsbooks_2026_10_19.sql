-- The member's own sportsbooks: the books they can bet at in their state,
-- or simply the ones they choose to use (Matt, 2026-10-19). Display only.
-- The models, the scorer, the stored pick, the record and the published
-- surfaces never read this table: every pick is still decided, sized and
-- graded at the best bettable price (CLAUDE.md §6). The app reads it to
-- choose WHICH of the books it already holds a price for it shows.
--
-- One row per owner. A signed-in member is 'user:<auth uid>', so the set
-- follows them to a new phone; every install also keeps 'device:<id>' so a
-- signed-out member (auth can be off) keeps theirs. The device id is the
-- same per-install UUID bearer token tracked_bets and feedback use.
--
-- ACCESS. RLS on, no policies, anon/authenticated table grants revoked.
-- The only way in is the two SECURITY DEFINER functions below, the same
-- trust model as feedback_threads.
--
-- UNAPPLIED. In data/view_migrations.ACTIVE_MIGRATIONS, so the worker
-- creates it on the first pass after merge. A second pass returns on the
-- catalog read below and takes no lock. One DO block, no CONCURRENTLY.

DO $mig$
BEGIN
  IF to_regclass('public.member_sportsbooks') IS NOT NULL
     AND to_regprocedure('public.member_books_get(text)') IS NOT NULL
     AND to_regprocedure('public.member_books_set(text,text[])') IS NOT NULL
     AND has_function_privilege('anon', 'public.member_books_get(text)', 'EXECUTE')
     AND has_function_privilege('anon', 'public.member_books_set(text,text[])', 'EXECUTE')
     AND NOT has_table_privilege('anon', 'public.member_sportsbooks', 'SELECT')
  THEN
    RETURN;
  END IF;

  CREATE TABLE IF NOT EXISTS public.member_sportsbooks (
    owner_key  TEXT PRIMARY KEY,
    books      TEXT[] NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT member_sportsbooks_owner_shape
      CHECK (owner_key ~ '^(device|user):[A-Za-z0-9-]{8,64}$'),
    CONSTRAINT member_sportsbooks_books_size
      CHECK (cardinality(books) BETWEEN 1 AND 32)
  );

  ALTER TABLE public.member_sportsbooks ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON TABLE public.member_sportsbooks FROM anon, authenticated;

  -- The set for this caller: the signed-in member's row first, then the
  -- install's. NULL when they have never chosen (the app then asks).
  CREATE OR REPLACE FUNCTION public.member_books_get(p_device_id TEXT)
  RETURNS TEXT[]
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path = public, pg_temp
  AS $fn$
    SELECT books
      FROM public.member_sportsbooks
     WHERE owner_key IN (
             'user:' || auth.uid()::text,
             'device:' || p_device_id
           )
     ORDER BY (owner_key LIKE 'user:%') DESC
     LIMIT 1
  $fn$;

  -- Saves the set under the install and, when signed in, under the member.
  -- Book keys are lowercased slugs (draftkings, williamhill_us); anything
  -- else is refused rather than stored.
  CREATE OR REPLACE FUNCTION public.member_books_set(p_device_id TEXT, p_books TEXT[])
  RETURNS VOID
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = public, pg_temp
  AS $fn$
  DECLARE
    v_books TEXT[];
  BEGIN
    IF p_device_id IS NULL OR p_device_id !~ '^[A-Za-z0-9-]{8,64}$' THEN
      RAISE EXCEPTION 'member_books_set: bad device id' USING ERRCODE = '22023';
    END IF;
    SELECT array_agg(DISTINCT b ORDER BY b) INTO v_books
      FROM unnest(p_books) AS b
     WHERE b ~ '^[a-z_]{2,32}$';
    IF v_books IS NULL OR cardinality(v_books) = 0 OR cardinality(v_books) > 32 THEN
      RAISE EXCEPTION 'member_books_set: need 1-32 book keys' USING ERRCODE = '22023';
    END IF;

    INSERT INTO public.member_sportsbooks (owner_key, books, updated_at)
    VALUES ('device:' || p_device_id, v_books, NOW())
    ON CONFLICT (owner_key) DO UPDATE
      SET books = EXCLUDED.books, updated_at = EXCLUDED.updated_at;

    IF auth.uid() IS NOT NULL THEN
      INSERT INTO public.member_sportsbooks (owner_key, books, updated_at)
      VALUES ('user:' || auth.uid()::text, v_books, NOW())
      ON CONFLICT (owner_key) DO UPDATE
        SET books = EXCLUDED.books, updated_at = EXCLUDED.updated_at;
    END IF;
  END
  $fn$;

  REVOKE ALL ON FUNCTION public.member_books_get(TEXT) FROM PUBLIC;
  REVOKE ALL ON FUNCTION public.member_books_set(TEXT, TEXT[]) FROM PUBLIC;
  GRANT EXECUTE ON FUNCTION public.member_books_get(TEXT) TO anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.member_books_set(TEXT, TEXT[]) TO anon, authenticated;
END
$mig$;
