-- Official lock read: covering index on byom_official_legs.
--
-- #1159 follow-up (squash 93cd9810). CE asked for this index as a
-- migration; a live CREATE timed out. byom_legs filters sport, season
-- and match_role, then DISTINCT ON (canonical_key, market, leg_side,
-- player_key) ORDER BY those columns plus locked_at. One NFL prop
-- season is about 0.5–0.7M candidate rows.
-- idx_byom_official_legs_season (sport, season, match_role, market)
-- is the smaller key.
--
-- Idempotent. One DO block. A catalog read returns once the index
-- exists, so a later pass does not take a SHARE lock or reload
-- PostgREST. Plain CREATE INDEX blocks writes to this table for the
-- build only. No other schema or function change.

DO $mig$
BEGIN
  IF to_regclass('public.byom_official_legs') IS NULL THEN
    RAISE EXCEPTION 'apply byom_official_legs_2026_11_04.sql first';
  END IF;

  IF to_regclass('public.idx_byom_official_legs_lock_read') IS NULL THEN
    CREATE INDEX IF NOT EXISTS idx_byom_official_legs_lock_read
      ON public.byom_official_legs
      (sport, season, match_role, canonical_key, market, leg_side, player_key, locked_at);
  END IF;
END
$mig$;
