-- record_sheet_checks (2026-11-21, Matt)
--
-- One row per run of tracking/record_sheet_check.py: the published record
-- checked against the "SignalBase Record History" sheet, which Matt and mike
-- made the reference for the record that day. findings is the list the ops
-- alert names (empty when the two agree); error is set when the sheet could
-- not be read. Rows are never deleted (CLAUDE.md 1b).
--
-- Guarded on the table, so a second pass fires no DDL. Not readable by the
-- app: RLS on, no policy, and no grant to anon or authenticated.

DO $mig$
BEGIN
  IF to_regclass('public.record_sheet_checks') IS NULL THEN
    CREATE TABLE public.record_sheet_checks (
      check_id      bigserial PRIMARY KEY,
      checked_at    timestamptz NOT NULL,
      ok            boolean NOT NULL,
      record_graded integer,
      sheet_graded  integer,
      findings      jsonb NOT NULL DEFAULT '[]'::jsonb,
      error         text
    );
    CREATE INDEX record_sheet_checks_checked_at ON public.record_sheet_checks (checked_at DESC);
    ALTER TABLE public.record_sheet_checks ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.record_sheet_checks FROM PUBLIC;
    REVOKE ALL ON public.record_sheet_checks FROM anon;
    REVOKE ALL ON public.record_sheet_checks FROM authenticated;
    REVOKE ALL ON SEQUENCE public.record_sheet_checks_check_id_seq FROM anon;
    REVOKE ALL ON SEQUENCE public.record_sheet_checks_check_id_seq FROM authenticated;
    RAISE NOTICE 'record_sheet_checks created';
  END IF;
END $mig$;
