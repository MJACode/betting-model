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

-- The rows come from a SECURITY DEFINER function, not straight from
-- v_public_track_record. That view is security_invoker and reads push_sent
-- (via v_discord_published), and an invoker view nested in a definer view
-- still checks the CALLER: after step A, anon got 42501 on
-- v_discord_published and the website lost its record (2026-11-19, fixed
-- in production the same evening).
CREATE OR REPLACE FUNCTION public.site_public_record_rows()
RETURNS TABLE (sport text, picks integer, wins integer, losses integer, pushes integer,
               units numeric, risked numeric, first_date date, last_date date)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp
AS $fn$
  SELECT r.sport,
         sum(r.picks)::integer, sum(r.wins)::integer, sum(r.losses)::integer, sum(r.pushes)::integer,
         round(sum(r.units), 2), round(sum(r.risked), 2),
         min(r.first_date)::date, max(r.last_date)::date
    FROM public.v_public_track_record r
   WHERE NOT EXISTS (SELECT 1 FROM public.site_retired_models s WHERE s.model_id = r.model_id)
   GROUP BY r.sport
$fn$;
ALTER FUNCTION public.site_public_record_rows() OWNER TO postgres;
REVOKE ALL ON FUNCTION public.site_public_record_rows() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.site_public_record_rows() TO postgres, service_role, anon, authenticated;

CREATE OR REPLACE VIEW public.site_public_record
WITH (security_invoker = false, security_barrier = true) AS
SELECT f.sport, f.picks, f.wins, f.losses, f.pushes,
       f.units::numeric(12, 2) AS units,
       f.risked::numeric(12, 2) AS risked,
       f.first_date, f.last_date,
       now() AS refreshed_at
  FROM public.site_public_record_rows() f;

REVOKE ALL ON public.site_public_record FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.site_public_record TO anon, authenticated;

COMMENT ON VIEW public.site_public_record IS
  'Website record row. Settled published picks, one row per sport, no model id. security_invoker off so anon does not read picks. Intentional definer view.';

NOTIFY pgrst, 'reload schema';
COMMIT;
