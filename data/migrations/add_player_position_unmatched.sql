-- Migration: add_player_position_unmatched
--
-- ESPN athlete ids the position pass already fetched and could not match to
-- a game-log row (mostly rookies). Without this, those athletes are fetched
-- again every morning — dry run 2 (job 406072) left 113 NBA and 30 WNBA
-- unmatched. The ingestor skips an id while its seen_at is inside the same
-- jittered window as a stored position, then tries again so a rookie who
-- later gets game rows does get matched.
--
-- Worker-only. The app never reads it. No anon grant: Supabase's default
-- privileges hand anon ALL, and REVOKE FROM PUBLIC does not undo that.
-- RLS with no policy is the second lock; the worker connects as the owner
-- and is not subject to it (no FORCE).
--
-- ONE guarded statement: data/view_migrations runs this on every refresh
-- pass, and ENABLE ROW LEVEL SECURITY takes ACCESS EXCLUSIVE and makes
-- PostgREST 503 the app while it reloads (tests/test_ddl_guard.py). The
-- guard is on the table existing, so the DDL fires once.
--
-- Not applied by the session that added the file. Matt applies it — the
-- worker's Step 0c pass runs this after the merge.

DO $mig$
BEGIN
    IF to_regclass('public.player_position_unmatched') IS NOT NULL THEN
        RAISE NOTICE 'player_position_unmatched already present — skipping';
        RETURN;
    END IF;

    CREATE TABLE public.player_position_unmatched (
        sport             TEXT NOT NULL,
        source_athlete_id TEXT NOT NULL,
        seen_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (sport, source_athlete_id)
    );

    REVOKE ALL ON public.player_position_unmatched FROM PUBLIC, anon, authenticated;
    ALTER TABLE public.player_position_unmatched ENABLE ROW LEVEL SECURITY;

    RAISE NOTICE 'player_position_unmatched created';
END
$mig$;
