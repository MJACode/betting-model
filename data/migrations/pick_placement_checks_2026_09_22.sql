-- Was this pick actually placeable at the book, at the number it named?
--
-- mike, 2026-09-22. The opener locked "TEN @ NYG — NYG -1 (Opener +2 vs
-- Pinnacle, MGM)" off a BetMGM number the feed served for four minutes, and the
-- first response was a filter that would have waited an hour on any number
-- that had just appeared. He rejected it: a book hanging a wrong number for
-- four minutes is the best case this model can find -- IF the number is
-- placeable -- and nothing in the feed or the backtest can say whether it is.
-- Only a person at the book can. This table is where that answer lives, one
-- row per pick, so that after a few weeks "are fresh numbers money or ghosts?"
-- is a query rather than an argument. Written by scripts/mark_placeable.py.
--
-- Not a column on `picks`: the pick is the model's statement and is immutable
-- once written (CLAUDE.md 1c); this is a human observation about it, made
-- later, and it can be corrected without touching the pick.
--
-- IDEMPOTENT: CREATE TABLE IF NOT EXISTS, and the grants are safe to repeat.
-- Single DO block, because data/view_migrations.py runs each file as ONE
-- statement.

DO $mig$
BEGIN
  CREATE TABLE IF NOT EXISTS public.pick_placement_checks (
    pick_id     BIGINT PRIMARY KEY,
    placeable   BOOLEAN NOT NULL,
    checked_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    checked_by  TEXT NOT NULL,
    note        TEXT
  );
  -- Supabase grants anon/authenticated by default; this is ops data.
  REVOKE ALL ON public.pick_placement_checks FROM anon, authenticated;
  ALTER TABLE public.pick_placement_checks ENABLE ROW LEVEL SECURITY;
END $mig$;
