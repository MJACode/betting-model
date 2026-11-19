-- Signal Base anon-key lockdown. HAND APPLIED. Not in ACTIVE_MIGRATIONS.
--
-- Project vvprgnrmzeekokzkrkfu. Matt, 2026-11-18: prep steps A and B; he OKs
-- the production apply. Authenticated grants stay as they are, except
-- tracked_bets. service_role is granted EXECUTE where a function lost PUBLIC,
-- and is otherwise untouched. The worker and Discord use postgres over
-- DATABASE_URL and bypass RLS.
--
-- Idempotent where PostgreSQL allows it (REVOKE, GRANT, ADD COLUMN IF NOT
-- EXISTS, DROP POLICY IF EXISTS). ALTER POLICY is safe to re-run: it sets
-- the role list again. No EXCEPTION handler swallows an error.

-- Apply this, deploy the website, and confirm the record row BEFORE step A.
-- security_invoker is off on purpose: anon must not need SELECT on picks.
-- The Supabase linter flags that (security_definer_view). It is intentional.

BEGIN;

CREATE TABLE IF NOT EXISTS public.site_retired_models (
    model_id text PRIMARY KEY
);
ALTER TABLE public.site_retired_models ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.site_retired_models FROM PUBLIC, anon, authenticated;

INSERT INTO public.site_retired_models (model_id) VALUES
  ('mlb_live_win_prob'),
  ('mlb_live_runline'),
  ('mlb_prop_batter_hr'),
  ('mlb_prop_batter_rbi'),
  ('golf_outright'),
  ('golf_top10'),
  ('golf_top20'),
  ('golf_make_cut'),
  ('golf_matchup'),
  ('nfl_live_prop'),
  ('nba_moneyline'),
  ('nba_over_under'),
  ('nba_spread'),
  ('nba_prop_player_points'),
  ('nba_prop_player_rebounds'),
  ('nba_prop_player_assists'),
  ('nba_prop_player_threes'),
  ('nba_prop_player_pra'),
  ('nba_prop_player_blocks'),
  ('nba_prop_player_steals'),
  ('nba_prop_player_turnovers'),
  ('nba_prop_player_dd'),
  ('ufc_moneyline'),
  ('ufc_total_rounds'),
  ('ufc_method_of_victory')
ON CONFLICT (model_id) DO NOTHING;

CREATE OR REPLACE VIEW public.site_public_record
WITH (security_invoker = false, security_barrier = true) AS
SELECT r.sport,
       SUM(r.picks)::integer AS picks,
       SUM(r.wins)::integer AS wins,
       SUM(r.losses)::integer AS losses,
       SUM(r.pushes)::integer AS pushes,
       ROUND(SUM(r.units), 2)::numeric(12, 2) AS units,
       ROUND(SUM(r.risked), 2)::numeric(12, 2) AS risked,
       MIN(r.first_date)::date AS first_date,
       MAX(r.last_date)::date AS last_date,
       now() AS refreshed_at
  FROM public.v_public_track_record r
 WHERE NOT EXISTS (
       SELECT 1 FROM public.site_retired_models s
        WHERE s.model_id = r.model_id)
 GROUP BY r.sport;

REVOKE ALL ON public.site_public_record FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.site_public_record TO anon, authenticated;

COMMENT ON VIEW public.site_public_record IS
  'Website record row. Settled published picks, one row per sport, no model id. security_invoker off so anon does not read picks. Intentional definer view.';

NOTIFY pgrst, 'reload schema';
COMMIT;
