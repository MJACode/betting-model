-- odds_history_pulls_minute_key_2026_10_30
--
-- The pull ledger is keyed by the minute as well as the hour.
--
-- WHY. The ledger records each historical snapshot the system has bought,
-- so a re-run never pays for one twice. Its key was (sport, snapshot_date,
-- hour_utc). The NCAAB opener grid (data/ingestors/ncaab_odds_history.py,
-- --opener-grid) buys every 30 minutes. Under an hour key, 22:30 would read
-- as 22:00 already bought and never be bought, or overwrite the 22:00 row so
-- 22:30 never reads as bought and every re-run pays for it again.
--
-- WHAT CHANGES. A minute_utc column, 0 to 59, NOT NULL DEFAULT 0. Every
-- existing row reads as minute 0, the hour it was bought at. The primary key
-- becomes (sport, snapshot_date, hour_utc, minute_utc) under the SAME name,
-- odds_history_pulls_pkey. Every writer says ON CONFLICT ON CONSTRAINT
-- odds_history_pulls_pkey, which matches the key before this runs and after.
-- The writers for the other sports (MLB, NCAAF, NHL, NBA) do not name the
-- minute, so their rows take the default 0.
--
-- One DO block (data/view_migrations.py runs single statements). It returns
-- on a catalog read when the ledger does not exist yet (the first purchase
-- creates it from odds_ingestor.PULL_LEDGER_DDL, already on the minute key)
-- or when the key already holds minute_utc, so it takes no lock on a second
-- run. The table holds about 28,000 rows (2026-10-30), so the re-key is a
-- short lock. The NCAAB purchase runs this same file before it buys when the
-- worker pass has not yet (ncaab_odds_history._ensure_tables).

DO $$
BEGIN
    IF to_regclass('public.odds_history_pulls') IS NULL THEN
        RETURN;
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_constraint c
          JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
         WHERE c.conrelid = 'public.odds_history_pulls'::regclass
           AND c.contype = 'p'
           AND a.attname = 'minute_utc'
    ) THEN
        RETURN;
    END IF;
    ALTER TABLE public.odds_history_pulls
        ADD COLUMN IF NOT EXISTS minute_utc INTEGER NOT NULL DEFAULT 0;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.odds_history_pulls'::regclass
           AND conname = 'odds_history_pulls_minute_utc_check'
    ) THEN
        ALTER TABLE public.odds_history_pulls
            ADD CONSTRAINT odds_history_pulls_minute_utc_check
            CHECK (minute_utc BETWEEN 0 AND 59);
    END IF;
    ALTER TABLE public.odds_history_pulls DROP CONSTRAINT IF EXISTS odds_history_pulls_pkey;
    ALTER TABLE public.odds_history_pulls
        ADD CONSTRAINT odds_history_pulls_pkey
        PRIMARY KEY (sport, snapshot_date, hour_utc, minute_utc);
END $$;
