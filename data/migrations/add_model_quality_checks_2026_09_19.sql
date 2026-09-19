-- Daily model-quality findings (tracking/model_quality.py).
--
-- Ops health (system_health_checks) catches stale feeds. This table is the
-- betting-quality half: one-sided slates, public-fade concentration, CLV/ROI
-- collapse, volume spikes. One row per (run_date, check_name, model_key);
-- re-runs upsert. Report only — nothing here pauses a model.
--
-- Anon SELECT so Claude mobile / any operator can read today's findings
-- the same way they read system_health_checks. Pipeline writes via the
-- table owner.
DO $$
BEGIN
  IF to_regclass('public.model_quality_checks') IS NULL THEN
    CREATE TABLE public.model_quality_checks (
      id          BIGSERIAL PRIMARY KEY,
      run_date    TEXT NOT NULL,
      check_name  TEXT NOT NULL,
      model_key   TEXT NOT NULL,
      sport       TEXT,
      status      TEXT NOT NULL,
      severity    TEXT NOT NULL,
      detail      TEXT,
      metrics     JSONB,
      created_at  TEXT NOT NULL
    );
    CREATE UNIQUE INDEX model_quality_checks_key
      ON public.model_quality_checks (run_date, check_name, model_key);
    CREATE INDEX idx_model_quality_run_date
      ON public.model_quality_checks (run_date);

    ALTER TABLE public.model_quality_checks ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.model_quality_checks FROM anon, authenticated;
    GRANT SELECT ON public.model_quality_checks TO anon, authenticated;
    CREATE POLICY "anon read model_quality_checks"
      ON public.model_quality_checks FOR SELECT TO anon, authenticated
      USING (true);
  END IF;
END $$;
