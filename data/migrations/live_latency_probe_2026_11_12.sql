-- Raw reads of the in-play latency probe (scripts/ncaab_live_latency_probe.py):
-- ESPN's scoreboard, summaries and plays, DraftKings' own NCAAB board, and the
-- odds provider's DraftKings quotes, each with the moment we received it.
--
-- Why it exists (mike, 2026-11-12: "Ncaab live bets way to slow ... it needs
-- to fire in under 10 seconds"): the measurements behind the answer (how far
-- each ESPN surface and DraftKings' own score run behind a basket, how long a
-- DraftKings live line stays up, how often the provider's DraftKings number
-- differs from DraftKings' board) cost credits and an evening of live games,
-- so the reads are stored, not only the numbers derived from them.
--
-- One row per probe read (one JSON line of the probe's cache file), keyed
-- (run_id, probe, line_no) so a re-import writes nothing already stored.
-- anon and authenticated get nothing; the local DATABASE_URL writes it.
-- One DO block: data/view_migrations.py runs each file as one statement, on
-- every pass. The early return answers "already applied" on the property this
-- migration establishes (the table exists, RLS on, no anon/authenticated
-- privilege), read through to_regclass so a fresh database never casts a
-- missing relation.

DO $mig$
BEGIN
  IF to_regclass('public.live_latency_probe') IS NOT NULL THEN
    IF EXISTS (
         SELECT 1 FROM pg_class
          WHERE oid = to_regclass('public.live_latency_probe')
            AND relrowsecurity
       )
       AND NOT has_table_privilege('anon', 'public.live_latency_probe', 'SELECT')
       AND NOT has_table_privilege('anon', 'public.live_latency_probe', 'INSERT')
       AND NOT has_table_privilege('anon', 'public.live_latency_probe', 'UPDATE')
       AND NOT has_table_privilege('anon', 'public.live_latency_probe', 'DELETE')
       AND NOT has_table_privilege('authenticated', 'public.live_latency_probe', 'SELECT')
       AND NOT has_table_privilege('authenticated', 'public.live_latency_probe', 'INSERT')
       AND NOT has_table_privilege('authenticated', 'public.live_latency_probe', 'UPDATE')
       AND NOT has_table_privilege('authenticated', 'public.live_latency_probe', 'DELETE')
    THEN
      RETURN;
    END IF;
  END IF;

  CREATE TABLE IF NOT EXISTS public.live_latency_probe (
    id          BIGSERIAL PRIMARY KEY,
    run_id      TEXT NOT NULL,
    probe       TEXT NOT NULL,
    line_no     INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    read_at     TIMESTAMPTZ,
    sport       TEXT NOT NULL DEFAULT 'NCAAB',
    payload     JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  CREATE UNIQUE INDEX IF NOT EXISTS uq_live_latency_probe_line
    ON public.live_latency_probe (run_id, probe, line_no);
  CREATE INDEX IF NOT EXISTS live_latency_probe_run_kind_idx
    ON public.live_latency_probe (run_id, probe, kind);

  ALTER TABLE public.live_latency_probe ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.live_latency_probe FROM anon;
  REVOKE ALL ON public.live_latency_probe FROM authenticated;
END
$mig$;
