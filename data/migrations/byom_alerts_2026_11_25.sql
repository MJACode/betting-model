-- Build Your Own Model: alerts and open bets for the member's own models.
--
-- Matt, 2026-11-25: "How do we alert the user when there is a pick from one
-- of their models. We should add an alert for them and a pick model card for
-- their pick." Then: "Let's start with just NFL to test this out."
-- Chosen that day: alert on every odds refresh, cards on the Picks tab and the
-- model's page, on by default with a per-model switch, and kept out of the
-- official record.
--
-- HAND APPLIED. NOT in data/view_migrations.ACTIVE_MIGRATIONS. Until it is
-- applied, the worker job byom_alerts finds no byom_alerts table and does
-- nothing (byom/alerts.py), and the app's open-bets read fails quietly.
--
-- Four things:
--
-- 1. byom_legs gains a third timing, 'open': the official legs on games that
--    have not started and are not graded. The official lock search is the
--    same one ('official'), so an open bet is the line and price the bet
--    would have been recorded at. 'official' and 'close' are unchanged. The
--    live body is the sum of seven earlier files, so, as
--    byom_no_half_yards_2026_11_17.sql does, this reads the live definition,
--    checks each anchor occurs the expected number of times (or raises and
--    changes nothing), and re-runs it. CREATE OR REPLACE keeps the grants
--    and SET clauses. Every earlier marker stays, so those files still skip.
--    A later file that re-creates byom_legs from its own text must carry
--    these lines, or 'open' is refused again.
--
-- 2. byom_models.alerts_enabled, default true (on by default, Matt).
--
-- 3. byom_alerts: one row per (model, game, market, side, player) the first
--    time an open bet is found. Insert-once: a later refresh where the line
--    has moved does not change the row (CLAUDE.md 1c applied to a member's
--    model). The worker sets notified_at once. Never written to picks, never
--    posted to a channel or X, never in the record views. A model delete or an
--    account delete removes its rows (ON DELETE CASCADE), the same as
--    byom_model_snapshots.
--
-- 4. Three RPCs for the signed-in member, SECURITY DEFINER on auth.uid():
--    byom_my_open_bets(), byom_alert_settings(), byom_set_alerts(uuid, bool).
--    The tables are not granted to anon or authenticated.
--
-- Skips once byom_legs carries byom_open_bets_v1 and every object exists.

DO $mig$
DECLARE
  v_proc regprocedure := to_regprocedure('public.byom_legs(integer, jsonb, text)');
  v_def text;
  v_marker text := '-- byom_trend_filters_v1';
  v_check text := 'IF p_timing IS NOT NULL AND p_timing NOT IN (''official'', ''close'') THEN';
  v_check_msg text := 'RAISE EXCEPTION ''timing is official or close'';';
  v_close_only text := 'WHERE p_timing IS DISTINCT FROM ''official''';
  v_kept text := 'AND (r.res IS NOT NULL OR r.played)';
  v_anchor text;
  v_want integer;
BEGIN
  IF v_proc IS NULL OR to_regclass('public.byom_models') IS NULL THEN
    RAISE NOTICE 'byom_legs or byom_models is not on this database - skipping';
    RETURN;
  END IF;

  -- 1. byom_legs: the 'open' timing.
  IF NOT (SELECT position('byom_open_bets_v1' in p.prosrc) > 0
            FROM pg_proc p WHERE p.oid = v_proc) THEN
    v_def := pg_get_functiondef(v_proc);
    FOR v_anchor, v_want IN
      SELECT a, n FROM (VALUES (v_marker, 1), (v_check, 1), (v_check_msg, 1),
                               (v_close_only, 2), (v_kept, 1)) AS t(a, n)
    LOOP
      IF (length(v_def) - length(replace(v_def, v_anchor, ''))) / length(v_anchor) <> v_want THEN
        RAISE EXCEPTION 'byom_alerts: anchor not found % time(s): %', v_want, v_anchor;
      END IF;
    END LOOP;

    v_def := replace(v_def, v_marker, v_marker || E'\n    -- byom_open_bets_v1');
    v_def := replace(v_def, v_check,
      'IF p_timing IS NOT NULL AND p_timing NOT IN (''official'', ''close'', ''open'') THEN');
    v_def := replace(v_def, v_check_msg,
      'RAISE EXCEPTION ''timing is official, close or open'';');
    -- The two closing branches stay out of 'open'.
    v_def := replace(v_def, v_close_only,
      v_close_only || ' AND p_timing IS DISTINCT FROM ''open''');
    -- 'open': official, ungraded, not played, kickoff still ahead.
    v_def := replace(v_def, v_kept,
      'AND CASE WHEN p_timing = ''open'''
      || E'\n                  -- byom_open_bets_v1: a bet on a game that has not started.'
      || E'\n                  THEN r.tmg = ''official'' AND r.res IS NULL'
      || E'\n                       AND NOT COALESCE(r.played, false)'
      || E'\n                       AND r.kick > pg_catalog.now()'
      || E'\n                  ELSE (r.res IS NOT NULL OR r.played) END');
    EXECUTE v_def;
  END IF;

  -- 2. The per-model switch.
  ALTER TABLE public.byom_models
    ADD COLUMN IF NOT EXISTS alerts_enabled boolean NOT NULL DEFAULT true;

  -- 3. One row per open bet, the first time it is found.
  CREATE TABLE IF NOT EXISTS public.byom_alerts (
    alert_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id       uuid NOT NULL REFERENCES public.byom_models (model_id)
                     ON DELETE CASCADE,
    user_id        uuid NOT NULL,
    sport          text NOT NULL,
    season         integer NOT NULL,
    canonical_key  text NOT NULL,
    market         text NOT NULL,
    leg_side       text NOT NULL,
    team           text,
    player_name    text NOT NULL DEFAULT '',
    home_team      text,
    away_team      text,
    commence_time  timestamptz,
    point          numeric,
    price          numeric NOT NULL,
    label          text NOT NULL,
    locked_at      timestamptz,
    detected_at    timestamptz NOT NULL DEFAULT now(),
    notified_at    timestamptz,
    CONSTRAINT byom_alerts_one_per_bet
      UNIQUE (model_id, canonical_key, market, leg_side, player_name)
  );
  CREATE INDEX IF NOT EXISTS idx_byom_alerts_user_kick
    ON public.byom_alerts (user_id, commence_time DESC);

  REVOKE ALL ON public.byom_alerts FROM PUBLIC, anon, authenticated;
  ALTER TABLE public.byom_alerts ENABLE ROW LEVEL SECURITY;
  DROP POLICY IF EXISTS "own byom_alerts" ON public.byom_alerts;
  CREATE POLICY "own byom_alerts"
    ON public.byom_alerts
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

  -- 4. The member's RPCs.
  EXECUTE $fn$
    CREATE OR REPLACE FUNCTION public.byom_my_open_bets()
    RETURNS TABLE (
      alert_id uuid,
      model_id uuid,
      model_name text,
      sport text,
      canonical_key text,
      market text,
      leg_side text,
      team text,
      player_name text,
      home_team text,
      away_team text,
      commence_time timestamptz,
      point numeric,
      price numeric,
      label text,
      locked_at timestamptz,
      detected_at timestamptz,
      started boolean
    )
    LANGUAGE plpgsql
    STABLE
    SECURITY DEFINER
    SET search_path = public, pg_temp
    AS $body$
    #variable_conflict use_column
    DECLARE
      -- byom_open_bets_v1
      v_uid uuid;
    BEGIN
      v_uid := auth.uid();
      IF v_uid IS NULL THEN
        RAISE EXCEPTION 'sign-in required';
      END IF;
      -- Open: not graded yet. A game with a final score in byom_game_facts,
      -- or a prop with a result, has left the list (its result is on the
      -- model's bet list). A game whose score never lands leaves 24 hours
      -- after kickoff.
      RETURN QUERY
      SELECT a.alert_id, a.model_id, m.name, a.sport, a.canonical_key,
             a.market, a.leg_side, a.team, NULLIF(a.player_name, ''),
             a.home_team, a.away_team, a.commence_time, a.point, a.price,
             a.label, a.locked_at, a.detected_at,
             a.commence_time <= pg_catalog.now()
        FROM byom_alerts a
        JOIN byom_models m ON m.model_id = a.model_id
        LEFT JOIN byom_game_facts g
          ON g.canonical_key = a.canonical_key AND g.sport = a.sport
       WHERE a.user_id = v_uid
         AND m.user_id = v_uid
         AND a.commence_time > pg_catalog.now() - interval '24 hours'
         AND NOT (g.home_score IS NOT NULL AND g.away_score IS NOT NULL)
       ORDER BY a.commence_time, m.name, a.label
       LIMIT 200;
    END;
    $body$;
  $fn$;

  EXECUTE $fn$
    CREATE OR REPLACE FUNCTION public.byom_alert_settings()
    RETURNS TABLE (model_id uuid, alerts_enabled boolean)
    LANGUAGE plpgsql
    STABLE
    SECURITY DEFINER
    SET search_path = public, pg_temp
    AS $body$
    #variable_conflict use_column
    DECLARE
      -- byom_open_bets_v1
      v_uid uuid;
    BEGIN
      v_uid := auth.uid();
      IF v_uid IS NULL THEN
        RAISE EXCEPTION 'sign-in required';
      END IF;
      RETURN QUERY
      SELECT m.model_id, m.alerts_enabled
        FROM byom_models m
       WHERE m.user_id = v_uid;
    END;
    $body$;
  $fn$;

  EXECUTE $fn$
    CREATE OR REPLACE FUNCTION public.byom_set_alerts(
      p_model_id uuid, p_enabled boolean)
    RETURNS boolean
    LANGUAGE plpgsql
    VOLATILE
    SECURITY DEFINER
    SET search_path = public, pg_temp
    AS $body$
    DECLARE
      -- byom_open_bets_v1
      v_uid uuid;
      v_done boolean;
    BEGIN
      v_uid := auth.uid();
      IF v_uid IS NULL THEN
        RAISE EXCEPTION 'sign-in required';
      END IF;
      IF p_enabled IS NULL THEN
        RAISE EXCEPTION 'alerts must be on or off';
      END IF;
      UPDATE byom_models m
         SET alerts_enabled = p_enabled
       WHERE m.model_id = p_model_id AND m.user_id = v_uid
      RETURNING m.alerts_enabled INTO v_done;
      IF v_done IS NULL THEN
        RAISE EXCEPTION 'model not found';
      END IF;
      RETURN v_done;
    END;
    $body$;
  $fn$;

  REVOKE ALL ON FUNCTION public.byom_my_open_bets() FROM PUBLIC, anon;
  REVOKE ALL ON FUNCTION public.byom_alert_settings() FROM PUBLIC, anon;
  REVOKE ALL ON FUNCTION public.byom_set_alerts(uuid, boolean) FROM PUBLIC, anon;
  GRANT EXECUTE ON FUNCTION public.byom_my_open_bets() TO authenticated;
  GRANT EXECUTE ON FUNCTION public.byom_alert_settings() TO authenticated;
  GRANT EXECUTE ON FUNCTION public.byom_set_alerts(uuid, boolean) TO authenticated;
END
$mig$;
