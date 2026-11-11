-- A volume setting for every pre-game model: post fewer, stronger bets by one
-- input (mike, 2026-11-11: "give me bands or thresholds or easy ways to tune
-- every model for volume based on a simple input, maybe through the retool
-- dash").
--
-- WHAT IT BUILDS
--   model_action_thresholds.base_min_edge / base_min_prob
--       config.py's own cut, written by data.threshold_sync on every pass.
--       min_edge / min_prob stay what every surface reads: the cut IN FORCE.
--   model_volume_settings      one row per model that has a setting: the band
--       chosen ('top_75', 'top_half', 'top_quarter', or 'custom'), the number
--       it stood for when it was set, who set it, when, and a note.
--   model_volume_settings_log  every insert, change and removal of a setting,
--       written by a trigger, so a setting made anywhere is recorded.
--   apply_model_volume_settings()  sets each model's cut in force to the
--       tighter of config's cut and its setting. Called by data.threshold_sync
--       after it writes config's cuts, and by set_model_volume.
--   model_volume_bands         per model and band: the threshold today, the
--       bets it would have posted in the model's last 120 days of betting and
--       per day, and the graded record of every bet at or above it, in units
--       at the posted stake. What the dashboard shows beside the input.
--   set_model_volume(model, level, who, number, note)  the one input: 'all'
--       removes the setting, a band name takes that band's threshold today,
--       'custom' takes the number given. It refuses a number under config's
--       cut, an in-play model, and a band the model has too few bets for.
--
-- THE RULES IT KEEPS
--   * A setting only TIGHTENS. The cut in force is never under config.py's,
--     which is the cut each model's evidence was measured at.
--   * It changes what is POSTED (the app, Discord and push read
--     model_action_thresholds together), never what a model records: a bet
--     under the setting is still written to picks and can be graded.
--   * A bet already posted keeps the cuts it was posted under (the app's
--     passesActionFilter; the producers post a pick once).
--   * In-play models are listed with their bands and NOT moved: their
--     posting does not read min_edge (tracking/publish_filters.
--     live_publishable_sql), and their loops count bets a night themselves.
--   * A band is a quartile of the model's OWN bets at config's cut over its
--     last 120 days of betting (counted back from its newest bet, so a sport
--     out of season keeps the bands of the season it last played), and needs
--     20 of them. A threshold is never copied from another model.
--
-- anon and authenticated get nothing on the two tables, the functions or the
-- view: the app reads model_action_thresholds, as before.
--
-- One DO block: data/view_migrations.py runs each file as one statement, on
-- every pass. It returns on a catalog read once the view carries this file's
-- marker (the hash of this file with the marker blanked; tests/
-- test_model_volume_settings.py pins it), so an edit here is applied on the
-- next pass. It waits, without raising, for the tables it reads.

DO $mig$
BEGIN
  IF to_regclass('public.model_action_thresholds') IS NULL
     OR to_regclass('public.picks') IS NULL
     OR to_regprocedure('public.published_pick_unit_profit(numeric,text,numeric)') IS NULL
     OR to_regprocedure('public.published_pick_unit_risked(numeric,text,numeric)') IS NULL THEN
    RAISE NOTICE 'model_volume_settings waits for model_action_thresholds, picks and the posted-unit functions';
    RETURN;
  END IF;

  IF to_regclass('public.model_volume_bands') IS NOT NULL
     AND COALESCE(obj_description(to_regclass('public.model_volume_bands'), 'pg_class'), '')
         = 'model_volume 43f44f092173'
     AND to_regclass('public.model_volume_settings') IS NOT NULL
     AND to_regclass('public.model_volume_settings_log') IS NOT NULL
     AND NOT has_table_privilege('anon', 'public.model_volume_settings', 'SELECT')
     AND NOT has_table_privilege('authenticated', 'public.model_volume_settings', 'SELECT')
     AND NOT has_table_privilege('anon', 'public.model_volume_bands', 'SELECT')
     AND NOT has_table_privilege('authenticated', 'public.model_volume_bands', 'SELECT')
  THEN
    RETURN;
  END IF;

  -- 1. config's own cut beside the cut in force
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                  WHERE table_schema = 'public' AND table_name = 'model_action_thresholds'
                    AND column_name = 'base_min_edge') THEN
    ALTER TABLE public.model_action_thresholds
      ADD COLUMN base_min_edge NUMERIC,
      ADD COLUMN base_min_prob NUMERIC;
    UPDATE public.model_action_thresholds SET base_min_edge = min_edge, base_min_prob = min_prob;
  END IF;

  -- 2. the settings and their log
  CREATE TABLE IF NOT EXISTS public.model_volume_settings (
    model_id  TEXT PRIMARY KEY,
    level     TEXT NOT NULL,
    min_edge  NUMERIC,
    min_prob  NUMERIC,
    set_by    TEXT NOT NULL,
    set_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note      TEXT,
    CONSTRAINT model_volume_settings_level
      CHECK (level IN ('top_75', 'top_half', 'top_quarter', 'custom')),
    CONSTRAINT model_volume_settings_number
      CHECK (min_edge IS NOT NULL OR min_prob IS NOT NULL),
    CONSTRAINT model_volume_settings_range
      CHECK ((min_edge IS NULL OR (min_edge >= 0 AND min_edge < 1))
             AND (min_prob IS NULL OR (min_prob >= 0 AND min_prob < 1))),
    CONSTRAINT model_volume_settings_who
      CHECK (btrim(set_by) <> '')
  );
  CREATE TABLE IF NOT EXISTS public.model_volume_settings_log (
    id         BIGSERIAL PRIMARY KEY,
    logged_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action     TEXT NOT NULL,
    model_id   TEXT NOT NULL,
    level      TEXT,
    min_edge   NUMERIC,
    min_prob   NUMERIC,
    set_by     TEXT,
    note       TEXT
  );
  ALTER TABLE public.model_volume_settings ENABLE ROW LEVEL SECURITY;
  ALTER TABLE public.model_volume_settings_log ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.model_volume_settings FROM anon, authenticated;
  REVOKE ALL ON public.model_volume_settings_log FROM anon, authenticated;
  REVOKE ALL ON SEQUENCE public.model_volume_settings_log_id_seq FROM anon, authenticated;

  -- The log names who did THIS: the setter on a set or a change, and on a
  -- removal whoever set_model_volume was called by (it leaves the name in
  -- model_volume.actor for the transaction), else the database role.
  EXECUTE $fn$
    CREATE OR REPLACE FUNCTION public.model_volume_settings_log_row() RETURNS trigger
    LANGUAGE plpgsql AS $body$
    DECLARE actor text := NULLIF(current_setting('model_volume.actor', true), '');
    BEGIN
      IF TG_OP = 'DELETE' THEN
        INSERT INTO public.model_volume_settings_log (action, model_id, level, min_edge, min_prob, set_by, note)
        VALUES ('removed', OLD.model_id, OLD.level, OLD.min_edge, OLD.min_prob,
                COALESCE(actor, 'direct SQL as ' || session_user), OLD.note);
        RETURN OLD;
      END IF;
      INSERT INTO public.model_volume_settings_log (action, model_id, level, min_edge, min_prob, set_by, note)
      VALUES (CASE WHEN TG_OP = 'INSERT' THEN 'set' ELSE 'changed' END,
              NEW.model_id, NEW.level, NEW.min_edge, NEW.min_prob, NEW.set_by, NEW.note);
      RETURN NEW;
    END
    $body$
  $fn$;
  DROP TRIGGER IF EXISTS model_volume_settings_log_trg ON public.model_volume_settings;
  CREATE TRIGGER model_volume_settings_log_trg
    AFTER INSERT OR UPDATE OR DELETE ON public.model_volume_settings
    FOR EACH ROW EXECUTE FUNCTION public.model_volume_settings_log_row();
  REVOKE ALL ON FUNCTION public.model_volume_settings_log_row() FROM PUBLIC, anon, authenticated;

  -- 3. the cut in force: the tighter of config's and the setting's. Pre-game
  --    models only; an in-play model's row is put back to config's cut.
  EXECUTE $fn$
    CREATE OR REPLACE FUNCTION public.apply_model_volume_settings() RETURNS integer
    LANGUAGE plpgsql AS $body$
    DECLARE n integer;
    BEGIN
      UPDATE public.model_action_thresholds t
         SET min_edge = w.edge_in_force, min_prob = w.prob_in_force
        FROM (
          SELECT t2.model_id,
                 GREATEST(COALESCE(t2.base_min_edge, t2.min_edge),
                          COALESCE(s.min_edge, COALESCE(t2.base_min_edge, t2.min_edge))) AS edge_in_force,
                 GREATEST(COALESCE(t2.base_min_prob, t2.min_prob),
                          COALESCE(s.min_prob, COALESCE(t2.base_min_prob, t2.min_prob))) AS prob_in_force
            FROM public.model_action_thresholds t2
            LEFT JOIN public.model_volume_settings s
              ON s.model_id = t2.model_id AND t2.model_id NOT LIKE '%\_live\_%'
        ) w
       WHERE w.model_id = t.model_id
         AND (t.min_edge IS DISTINCT FROM w.edge_in_force OR t.min_prob IS DISTINCT FROM w.prob_in_force);
      SELECT count(*) INTO n
        FROM public.model_volume_settings s
        JOIN public.model_action_thresholds t ON t.model_id = s.model_id
       WHERE s.model_id NOT LIKE '%\_live\_%';
      RETURN n;
    END
    $body$
  $fn$;
  REVOKE ALL ON FUNCTION public.apply_model_volume_settings() FROM PUBLIC, anon, authenticated;

  -- 4. the bands
  EXECUTE $view$
    CREATE OR REPLACE VIEW public.model_volume_bands
    WITH (security_invoker = on) AS
    WITH cuts AS (
      SELECT t.model_id, t.paused, t.prob_only, t.min_odds,
             (t.model_id LIKE '%\_live\_%') AS in_play,
             COALESCE(t.base_min_edge, t.min_edge, 0)::numeric AS base_edge,
             COALESCE(t.base_min_prob, t.min_prob, 0)::numeric AS base_prob,
             (CASE WHEN t.prob_only THEN t.min_prob ELSE t.min_edge END)::numeric AS in_force
        FROM public.model_action_thresholds t
    ), bets AS (
      -- every bet the model has written at config's own cut: the number the
      -- cut is on, the day, and what it made at the posted stake
      SELECT p.model_id, p.game_date,
             (CASE WHEN c.prob_only THEN p.model_probability
                   ELSE COALESCE(p.decision_edge, p.edge) END)::numeric AS x,
             p.result,
             COALESCE(p.decision_odds, p.dk_odds)::numeric AS price,
             p.stake_units::numeric AS stake_units
        FROM public.picks p
        JOIN cuts c ON c.model_id = p.model_id
       WHERE p.signal_type = 'BET'
         AND (p.condition_status IS NULL OR p.condition_status NOT IN ('VOID', 'DUPLICATE'))
         AND p.downgrade_reason IS DISTINCT FROM 'model paused'
         AND (p.is_live IS TRUE) = c.in_play
         AND p.model_probability >= c.base_prob
         AND (c.prob_only OR COALESCE(p.decision_edge, p.edge) >= c.base_edge)
         AND (c.min_odds IS NULL OR COALESCE(p.decision_odds, p.dk_odds) IS NULL
              OR COALESCE(p.decision_odds, p.dk_odds) >= c.min_odds)
    ), span AS (
      -- the model's last 120 days of betting, counted back from its newest bet
      SELECT model_id, max(game_date) AS last_bet,
             to_char(max(game_date)::date - 120, 'YYYY-MM-DD') AS first_day
        FROM bets GROUP BY 1
    ), recent AS (
      SELECT b.* FROM bets b JOIN span sp ON sp.model_id = b.model_id
       WHERE b.game_date >= sp.first_day
    ), q AS (
      SELECT model_id, count(*) AS n, count(DISTINCT game_date) AS days,
             min(game_date) AS first_bet, max(game_date) AS last_bet,
             percentile_cont(0.25) WITHIN GROUP (ORDER BY x) AS q25,
             percentile_cont(0.50) WITHIN GROUP (ORDER BY x) AS q50,
             percentile_cont(0.75) WITHIN GROUP (ORDER BY x) AS q75
        FROM recent GROUP BY 1
    ), bands AS (
      -- trunc, not round: a threshold rounded up could sit above the bet that
      -- defines its band and drop it
      SELECT c.model_id, b.band, b.ord,
             CASE b.band
               WHEN 'all' THEN (CASE WHEN c.prob_only THEN c.base_prob ELSE c.base_edge END)
               WHEN 'top_75' THEN (CASE WHEN q.n >= 20 THEN trunc(q.q25::numeric, 4) END)
               WHEN 'top_half' THEN (CASE WHEN q.n >= 20 THEN trunc(q.q50::numeric, 4) END)
               ELSE (CASE WHEN q.n >= 20 THEN trunc(q.q75::numeric, 4) END)
             END AS threshold
        FROM cuts c
        LEFT JOIN q ON q.model_id = c.model_id
        CROSS JOIN (VALUES ('all', 1), ('top_75', 2), ('top_half', 3), ('top_quarter', 4)) AS b(band, ord)
    )
    SELECT c.model_id,
           upper(split_part(c.model_id, '_', 1)) AS sport,
           c.paused,
           c.in_play,
           CASE WHEN c.prob_only THEN 'probability' ELSE 'edge' END AS cut_on,
           ba.band,
           ba.ord AS band_order,
           ba.threshold,
           (CASE WHEN c.prob_only THEN c.base_prob ELSE c.base_edge END) AS config_cut,
           c.in_force AS cut_in_force,
           s.level AS setting,
           (CASE WHEN c.prob_only THEN s.min_prob ELSE s.min_edge END) AS setting_value,
           CASE WHEN s.model_id IS NULL THEN NULL
                ELSE (NOT c.in_play
                      AND c.in_force >= (CASE WHEN c.prob_only THEN s.min_prob ELSE s.min_edge END))
           END AS setting_in_force,
           s.set_by AS setting_by,
           s.set_at AS setting_at,
           COALESCE(q.n, 0) AS recent_bets_at_config_cut,
           COALESCE(q.days, 0) AS recent_days_with_a_bet,
           q.first_bet AS first_bet_date,
           q.last_bet AS last_bet_date,
           COALESCE(q.n, 0) >= 20 AS enough_bets,
           r.recent_bets,
           CASE WHEN COALESCE(q.days, 0) > 0 THEN round(r.recent_bets::numeric / q.days, 1) END AS bets_per_day,
           g.graded, g.wins, g.losses, g.units,
           CASE WHEN g.risked > 0 THEN round(g.units / g.risked * 100, 2) END AS roi_pct
      FROM cuts c
      JOIN bands ba ON ba.model_id = c.model_id
      LEFT JOIN q ON q.model_id = c.model_id
      LEFT JOIN public.model_volume_settings s ON s.model_id = c.model_id
      LEFT JOIN LATERAL (
        SELECT count(*) AS recent_bets FROM recent x
         WHERE x.model_id = c.model_id AND ba.threshold IS NOT NULL AND x.x >= ba.threshold
      ) r ON TRUE
      LEFT JOIN LATERAL (
        SELECT count(*) AS graded,
               count(*) FILTER (WHERE b.result = 'WIN') AS wins,
               count(*) FILTER (WHERE b.result = 'LOSS') AS losses,
               COALESCE(round(sum(public.published_pick_unit_profit(b.price, b.result, b.stake_units)), 2), 0) AS units,
               COALESCE(sum(public.published_pick_unit_risked(b.price, b.result, b.stake_units)), 0) AS risked
          FROM bets b
         WHERE b.model_id = c.model_id AND ba.threshold IS NOT NULL AND b.x >= ba.threshold
           AND b.result IN ('WIN', 'LOSS', 'PUSH') AND b.price IS NOT NULL
      ) g ON TRUE
  $view$;
  EXECUTE $c$COMMENT ON VIEW public.model_volume_bands IS 'model_volume 43f44f092173'$c$;
  REVOKE ALL ON public.model_volume_bands FROM anon, authenticated;

  -- 5. the one input. Everything a person or the dashboard does to a setting
  --    goes through here, so the checks and the log are the same for both.
  EXECUTE $fn$
    CREATE OR REPLACE FUNCTION public.set_model_volume(
      p_model_id text, p_level text, p_set_by text,
      p_value numeric DEFAULT NULL, p_note text DEFAULT NULL)
    RETURNS TABLE (model text, setting text, cut_on text, config_cut numeric, cut_in_force numeric)
    LANGUAGE plpgsql AS $body$
    #variable_conflict use_column
    DECLARE
      t     public.model_action_thresholds%ROWTYPE;
      who   text := btrim(COALESCE(p_set_by, ''));
      base  numeric;
      v     numeric;
    BEGIN
      IF who = '' THEN
        RAISE EXCEPTION 'a volume setting needs the name of who set it';
      END IF;
      SELECT m.* INTO t FROM public.model_action_thresholds m WHERE m.model_id = p_model_id;
      IF NOT FOUND THEN
        RAISE EXCEPTION 'no model % in model_action_thresholds', p_model_id;
      END IF;
      IF p_model_id LIKE '%\_live\_%' THEN
        RAISE EXCEPTION '% is an in-play model: a volume setting does not move it', p_model_id;
      END IF;
      base := CASE WHEN t.prob_only THEN COALESCE(t.base_min_prob, t.min_prob, 0)
                   ELSE COALESCE(t.base_min_edge, t.min_edge, 0) END;
      PERFORM set_config('model_volume.actor', who, true);

      IF p_level = 'all' THEN
        DELETE FROM public.model_volume_settings s WHERE s.model_id = p_model_id;
      ELSE
        IF p_level = 'custom' THEN
          v := p_value;
          IF v IS NULL THEN
            RAISE EXCEPTION 'a custom setting needs a number';
          END IF;
        ELSIF p_level IN ('top_75', 'top_half', 'top_quarter') THEN
          SELECT b.threshold INTO v FROM public.model_volume_bands b
           WHERE b.model_id = p_model_id AND b.band = p_level;
          IF v IS NULL THEN
            RAISE EXCEPTION '% has under 20 bets in its last 120 days of betting, so it has no bands: give a number (custom)', p_model_id;
          END IF;
        ELSE
          RAISE EXCEPTION 'unknown level %: all, top_75, top_half, top_quarter or custom', p_level;
        END IF;
        IF v < base THEN
          RAISE EXCEPTION 'a volume setting only tightens: % is under the cut in config.py (%)', v, base;
        END IF;
        IF v >= 1 THEN
          RAISE EXCEPTION 'a cut is a decimal under 1 (0.05 is 5 points of %): got %',
            CASE WHEN t.prob_only THEN 'probability' ELSE 'edge' END, v;
        END IF;
        INSERT INTO public.model_volume_settings AS s
               (model_id, level, min_edge, min_prob, set_by, set_at, note)
        VALUES (p_model_id, p_level,
                CASE WHEN t.prob_only THEN NULL ELSE v END,
                CASE WHEN t.prob_only THEN v END,
                who, now(), p_note)
        ON CONFLICT ON CONSTRAINT model_volume_settings_pkey DO UPDATE
           SET level = EXCLUDED.level, min_edge = EXCLUDED.min_edge, min_prob = EXCLUDED.min_prob,
               set_by = EXCLUDED.set_by, set_at = EXCLUDED.set_at, note = EXCLUDED.note;
      END IF;

      PERFORM public.apply_model_volume_settings();
      RETURN QUERY
        SELECT m.model_id, s.level,
               CASE WHEN m.prob_only THEN 'probability' ELSE 'edge' END,
               base,
               (CASE WHEN m.prob_only THEN m.min_prob ELSE m.min_edge END)::numeric
          FROM public.model_action_thresholds m
          LEFT JOIN public.model_volume_settings s ON s.model_id = m.model_id
         WHERE m.model_id = p_model_id;
    END
    $body$
  $fn$;
  REVOKE ALL ON FUNCTION public.set_model_volume(text, text, text, numeric, text) FROM PUBLIC, anon, authenticated;
END $mig$;
