-- Migration: add_player_positions
--
-- One position per player we have a game log for, for the sports whose logs
-- carry none: NBA, WNBA, NCAAF (measured 2026-10-03). Backs phase 3 of the
-- player page's "same position vs the next opponent" card (Matt, 2026-10-05).
-- Written by data/ingestors/player_positions_ingestor.py:
--   NBA / WNBA  ESPN core rosters, mapped to our nba_api player_id by name
--   NCAAF       CFBD /roster, joined on CFBD's athlete id (the log's own id)
--
-- player_id is OUR id (the log's), so a card joins this table to the log with
-- no translation. source_athlete_id keeps the upstream id for the refresh skip.
-- pos_group is the bucket the card asks for: G / F / C for basketball (Matt,
-- 2026-10-05), the NFL buckets for NCAAF.
--
-- Anon reads it through the security-invoker position_vs_opponent_* functions,
-- so it gets SELECT and nothing else; revoke BY NAME first (default privileges
-- grant anon ALL, and REVOKE ... FROM PUBLIC does not undo that).
--
-- ONE guarded statement: data/view_migrations runs this on every refresh pass,
-- and every DDL statement makes PostgREST 503 the app while it reloads
-- (tests/test_ddl_guard.py). The guard is on the table existing.

DO $mig$
BEGIN
    IF to_regclass('public.player_positions') IS NOT NULL THEN
        RAISE NOTICE 'player_positions already present — skipping';
        RETURN;
    END IF;

    CREATE TABLE public.player_positions (
        sport             TEXT NOT NULL,
        player_id         TEXT NOT NULL,
        player_name       TEXT,
        team              TEXT,
        position          TEXT NOT NULL,
        pos_group         TEXT,
        source            TEXT NOT NULL,
        source_athlete_id TEXT,
        updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (sport, player_id)
    );
    CREATE INDEX idx_player_positions_group ON public.player_positions (sport, pos_group);

    ALTER TABLE public.player_positions ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.player_positions FROM anon, authenticated;
    GRANT SELECT ON public.player_positions TO anon, authenticated;
    CREATE POLICY "anon read player_positions"
        ON public.player_positions FOR SELECT TO anon, authenticated USING (true);

    RAISE NOTICE 'player_positions created';
END
$mig$;
