-- Record what a live model actually saw when it wrote its first BET.
--
-- Idempotent, and guarded on the PROPERTY it establishes (the table's
-- existence) rather than on the shape of its own output -- see
-- .claude/rules/data-integrity.md on guards that are locks.
--
-- Applied by hand 2026-09-08; kept in the repo as the record of what was run.
DO $$
BEGIN
    IF to_regclass('public.live_pick_features') IS NULL THEN
        CREATE TABLE public.live_pick_features (
            game_id           TEXT NOT NULL REFERENCES public.games(game_id),
            model_id          TEXT NOT NULL,
            recorded_at       TEXT NOT NULL,
            state_at          TEXT,
            lam               REAL,
            model_probability REAL,
            features          TEXT NOT NULL,
            PRIMARY KEY (game_id, model_id)
        );
        RAISE NOTICE 'live_pick_features: created';
    ELSE
        RAISE NOTICE 'live_pick_features: already present';
    END IF;

    -- Default privileges hand anon/authenticated ALL, and REVOKE ... FROM
    -- PUBLIC does nothing about it. Revoke BY NAME (.claude/rules/operations.md).
    REVOKE ALL ON public.live_pick_features FROM anon;
    REVOKE ALL ON public.live_pick_features FROM authenticated;
    EXECUTE 'ALTER TABLE public.live_pick_features ENABLE ROW LEVEL SECURITY';
END $$;
