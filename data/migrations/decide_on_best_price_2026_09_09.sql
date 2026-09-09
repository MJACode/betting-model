-- decide_on_best_price_2026_09_09 (mike: "we should remove DK only - we want
-- best lines for us regardless")
--
-- THE FLIP. Until 2026-09-09 a pick was decided, sized and settled at the
-- DraftKings price, and the best price found across the bettable books was
-- stamped beside it for display (picks.best_*). From this migration on, the
-- price that DECIDES is the best bettable price at the DraftKings line, and it
-- is recorded in four new columns so a reader can always tell which price a
-- pick was decided at:
--
--   decision_book          the book whose price qualified the pick
--   decision_odds          that price (American)
--   decision_implied_prob  its implied probability
--   decision_edge          model_probability - decision_implied_prob
--
-- `edge`, `dk_odds` and `dk_implied_prob` keep their meaning (DraftKings, the
-- reference line the models are trained against and the basis of CLV). Rows
-- written before the flip carry NULL in the new columns: they were decided at
-- DraftKings, so every reader COALESCEs decision_x to dk_x -- exact, not a
-- fallback. No bulk backfill: 161,781 rows on 2026-09-09, and the audit trigger
-- fires on UPDATE.
--
-- WHAT THIS SCRIPT DOES, in one idempotent statement (data/view_migrations.py
-- runs it every pass; every DDL is behind a guard on the property it
-- establishes, so the no-op path fires nothing -- CLAUDE.md section 7):
--   1. picks / picks_log gain the four columns; log_picks_changes() copies them.
--   2. mv_scored_pick_outcomes is rebuilt with decision_* columns; profit_units
--      and price_side grade at the decision price. v_model_full_outcome_record,
--      which depends on it, is recreated with its cut on the decision columns.
--   3. v_model_full_outcome_picks and v_model_full_record cut and grade at the
--      decision price.
--   4. custom_model_backtest / custom_model_picks (the app's custom-model
--      builder) cut, filter and grade at the decision price; custom_model_picks
--      returns the decision columns as well.
--
-- The two published-record views (v_public_track_record, _daily) are owned by
-- live_record_start_views_2026_09_01.sql and move there.
--
-- Applied to production by hand on 2026-09-09 BEFORE the code that writes the
-- columns was deployed; the runner then finds every guard satisfied.

DO $mig$
DECLARE
  d text;
BEGIN
  -- ── 1. the columns, and the audit trigger that copies them ───────────────
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                  WHERE table_schema = 'public' AND table_name = 'picks'
                    AND column_name = 'decision_edge') THEN
    ALTER TABLE public.picks
      ADD COLUMN decision_book         TEXT,
      ADD COLUMN decision_odds         NUMERIC,
      ADD COLUMN decision_implied_prob NUMERIC,
      ADD COLUMN decision_edge         NUMERIC;
    RAISE NOTICE 'picks: decision_* columns added';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                  WHERE table_schema = 'public' AND table_name = 'picks_log'
                    AND column_name = 'decision_edge') THEN
    ALTER TABLE public.picks_log
      ADD COLUMN decision_book         TEXT,
      ADD COLUMN decision_odds         NUMERIC,
      ADD COLUMN decision_implied_prob NUMERIC,
      ADD COLUMN decision_edge         NUMERIC;
    RAISE NOTICE 'picks_log: decision_* columns added';
  END IF;

  SELECT p.prosrc INTO d FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'public' AND p.proname = 'log_picks_changes';
  IF d IS NULL OR position('decision_edge' in d) = 0 THEN
    EXECUTE $fn$
      CREATE OR REPLACE FUNCTION public.log_picks_changes()
       RETURNS trigger
       LANGUAGE plpgsql
       SET search_path TO 'public', 'pg_catalog'
      AS $body$
      DECLARE
        r picks%ROWTYPE;
      BEGIN
        IF TG_OP = 'DELETE' THEN
          r := OLD;
        ELSE
          r := NEW;
        END IF;

        INSERT INTO picks_log (
          logged_at, operation, pick_id, game_id, model_id, sport, game_date, game_time, run_time,
          pick_side, pick_label, model_probability, dk_implied_prob, edge, dk_odds, scored_line,
          kelly_fraction, recommended_bet, bankroll_at_pick, injury_flag, injury_detail,
          signal_type, confidence_tier, result, profit_flat, profit_kelly, settled_at, created_at,
          decision_book, decision_odds, decision_implied_prob, decision_edge
        ) VALUES (
          NOW(), TG_OP, r.pick_id, r.game_id, r.model_id, r.sport, r.game_date, r.game_time, r.run_time,
          r.pick_side, r.pick_label, r.model_probability, r.dk_implied_prob, r.edge, r.dk_odds, r.scored_line,
          r.kelly_fraction, r.recommended_bet, r.bankroll_at_pick, r.injury_flag, r.injury_detail,
          r.signal_type, r.confidence_tier, r.result, r.profit_flat, r.profit_kelly, r.settled_at, r.created_at,
          r.decision_book, r.decision_odds, r.decision_implied_prob, r.decision_edge
        );

        RETURN r;
      END;
      $body$
    $fn$;
    RAISE NOTICE 'log_picks_changes now copies the decision columns';
  END IF;

  -- ── 2. the graded universe, at the decision price ────────────────────────
  IF NOT EXISTS (SELECT 1 FROM pg_attribute
                  WHERE attrelid = 'public.mv_scored_pick_outcomes'::regclass
                    AND attname = 'decision_edge' AND NOT attisdropped) THEN
    DROP VIEW IF EXISTS public.v_model_full_outcome_record;
    DROP MATERIALIZED VIEW IF EXISTS public.mv_scored_pick_outcomes;

    EXECUTE $v$
      CREATE MATERIALIZED VIEW public.mv_scored_pick_outcomes AS
      WITH base AS (
        SELECT
          p.pick_id, p.model_id, p.sport, p.game_date, p.game_time, p.game_id,
          p.pick_label, p.pick_side, p.signal_type, p.confidence_tier,
          p.model_probability, p.edge, p.dk_odds, p.scored_line,
          -- The price the pick was DECIDED at. Rows from before 2026-09-09 were
          -- decided at DraftKings and carry NULL here, so dk_* is exact for them.
          COALESCE(p.decision_book,
                   CASE WHEN p.dk_odds IS NULL THEN NULL ELSE 'draftkings' END) AS decision_book,
          COALESCE(p.decision_odds, p.dk_odds) AS decision_odds,
          COALESCE(p.decision_edge, p.edge)    AS decision_edge,
          p.public_bet_pct, p.injury_flag, p.player_id,
          CASE
            WHEN p.model_id = 'mlb_moneyline' THEN CASE
              WHEN g.home_win IS NULL THEN 'U'
              WHEN p.pick_side='home' AND g.home_win=1 OR p.pick_side='away' AND g.home_win=0 THEN 'W' ELSE 'L' END
            WHEN p.model_id = 'mlb_over_under' THEN CASE
              WHEN g.home_score IS NULL OR p.scored_line IS NULL THEN 'U'
              WHEN (g.home_score+g.away_score) = p.scored_line THEN 'P'
              WHEN p.pick_side='over' AND (g.home_score+g.away_score) > p.scored_line
                OR p.pick_side='under' AND (g.home_score+g.away_score) < p.scored_line THEN 'W' ELSE 'L' END
            -- scored_line is the HOME spread, so an away cover is (away-home) - line.
            WHEN p.model_id = 'mlb_runline' THEN CASE
              WHEN g.home_score IS NULL OR p.scored_line IS NULL THEN 'U'
              WHEN (CASE WHEN p.pick_side='home' THEN g.home_score-g.away_score+p.scored_line
                         ELSE g.away_score-g.home_score-p.scored_line END) = 0 THEN 'P'
              WHEN (CASE WHEN p.pick_side='home' THEN g.home_score-g.away_score+p.scored_line
                         ELSE g.away_score-g.home_score-p.scored_line END) > 0 THEN 'W' ELSE 'L' END
            WHEN p.model_id = 'mlb_f5_moneyline' THEN CASE
              WHEN g.home_score_f5 IS NULL OR g.away_score_f5 IS NULL THEN 'U'
              WHEN g.home_score_f5 = g.away_score_f5 THEN 'P'
              WHEN p.pick_side='home' AND g.home_score_f5 > g.away_score_f5
                OR p.pick_side='away' AND g.away_score_f5 > g.home_score_f5 THEN 'W' ELSE 'L' END
            WHEN p.model_id = 'wnba_moneyline' THEN CASE
              WHEN g.home_win IS NULL THEN 'U'
              WHEN p.pick_side='home' AND g.home_win=1 OR p.pick_side='away' AND g.home_win=0 THEN 'W' ELSE 'L' END
            WHEN p.model_id LIKE 'mlb_prop_%' THEN CASE
              WHEN p.scored_line IS NULL OR pl.actual IS NULL THEN 'U'
              WHEN pl.actual::numeric = p.scored_line THEN 'P'
              WHEN p.pick_side='over' AND pl.actual::numeric > p.scored_line
                OR p.pick_side='under' AND pl.actual::numeric < p.scored_line THEN 'W' ELSE 'L' END
            WHEN p.model_id LIKE 'wnba_prop_%' THEN CASE
              WHEN p.scored_line IS NULL OR wl.actual IS NULL THEN 'U'
              WHEN wl.actual::numeric = p.scored_line THEN 'P'
              WHEN p.pick_side='over' AND wl.actual::numeric > p.scored_line
                OR p.pick_side='under' AND wl.actual::numeric < p.scored_line THEN 'W' ELSE 'L' END
            ELSE 'U'
          END AS res,
          EXTRACT(hour FROM (p.game_time::timestamptz AT TIME ZONE 'America/New_York')) AS et_hour
        FROM picks p
        LEFT JOIN games g ON g.game_id = p.game_id
        LEFT JOIN LATERAL (
          SELECT max(CASE p.model_id
            WHEN 'mlb_prop_pitcher_k'     THEN l.p_strikeouts
            WHEN 'mlb_prop_pitcher_walks' THEN l.p_walks
            WHEN 'mlb_prop_pitcher_hits'  THEN l.p_hits_allowed
            WHEN 'mlb_prop_pitcher_er'    THEN l.p_earned_runs
            WHEN 'mlb_prop_pitcher_outs'  THEN (floor(l.innings_pitched)*3 + round((l.innings_pitched-floor(l.innings_pitched))*10))::integer
            WHEN 'mlb_prop_batter_hits'   THEN l.hits
            WHEN 'mlb_prop_batter_tb'     THEN l.total_bases
            WHEN 'mlb_prop_batter_rbi'    THEN l.rbi
            WHEN 'mlb_prop_batter_runs'   THEN l.runs
            WHEN 'mlb_prop_batter_sb'     THEN l.stolen_bases
            WHEN 'mlb_prop_batter_walks'  THEN l.walks
            WHEN 'mlb_prop_batter_hr'     THEN l.home_runs
            ELSE NULL END) AS actual
          FROM player_game_log l
          WHERE l.game_id = p.game_id AND l.player_id = p.player_id) pl ON true
        LEFT JOIN LATERAL (
          SELECT max(CASE p.model_id
            WHEN 'wnba_prop_player_points'   THEN l.points
            WHEN 'wnba_prop_player_rebounds' THEN l.rebounds
            WHEN 'wnba_prop_player_assists'  THEN l.assists
            WHEN 'wnba_prop_player_threes'   THEN l.fg3_made
            WHEN 'wnba_prop_player_pra'      THEN l.points + l.rebounds + l.assists
            ELSE NULL END) AS actual
          FROM wnba_player_game_log l
          WHERE l.game_id = p.game_id AND l.player_id = p.player_id) wl ON true
        WHERE p.game_date >= '2026-04-14'
          AND NOT (p.model_id = 'mlb_over_under' AND p.game_date < '2026-07-05')
          AND p.is_live IS NOT TRUE
          AND (p.model_id IN ('mlb_moneyline','mlb_over_under','mlb_runline','mlb_f5_moneyline','wnba_moneyline')
               OR p.model_id LIKE 'mlb_prop_%' OR p.model_id LIKE 'wnba_prop_%')
      )
      SELECT
        b.pick_id, b.model_id, b.sport, b.game_date, b.game_time, b.game_id,
        b.pick_label, b.pick_side, b.signal_type, b.confidence_tier,
        b.model_probability, b.edge, b.dk_odds, b.scored_line,
        b.decision_book, b.decision_odds, b.decision_edge,
        b.public_bet_pct, b.injury_flag, b.player_id,
        CASE WHEN b.model_id LIKE '%\_prop\_%' THEN 'prop' ELSE 'game' END AS bet_kind,
        CASE WHEN b.decision_odds IS NULL THEN NULL
             WHEN b.decision_odds < 0 THEN 'fav' ELSE 'dog' END AS price_side,
        CASE
          WHEN b.et_hour IS NULL THEN NULL
          WHEN b.et_hour >= 22 OR b.et_hour < 5 THEN 'late'
          WHEN b.et_hour < 16 THEN 'day'
          WHEN b.et_hour < 19 THEN 'early'
          ELSE 'prime'
        END AS time_slot,
        CASE b.res WHEN 'W' THEN 'WIN' WHEN 'L' THEN 'LOSS' ELSE 'PUSH' END AS result,
        -- Units on a 1u flat stake at the DECISION price.
        CASE
          WHEN b.decision_odds IS NULL THEN NULL
          WHEN b.res = 'W' THEN CASE WHEN b.decision_odds > 0 THEN b.decision_odds/100.0 ELSE 100.0/abs(b.decision_odds) END
          WHEN b.res = 'L' THEN -1
          ELSE 0
        END AS profit_units
      FROM base b
      WHERE b.res IN ('W','L','P')
    $v$;

    CREATE UNIQUE INDEX mv_scored_pick_outcomes_pick_id_idx
      ON public.mv_scored_pick_outcomes (pick_id);
    CREATE INDEX mv_scored_pick_outcomes_model_idx
      ON public.mv_scored_pick_outcomes (model_id, model_probability, decision_edge);

    REVOKE ALL ON public.mv_scored_pick_outcomes FROM anon, authenticated;
    GRANT SELECT ON public.mv_scored_pick_outcomes TO anon, authenticated;

    -- v_model_full_outcome_record depends on the matview, so it is recreated
    -- here with its cut on the decision columns. track_record_reads_graded_
    -- matview.sql carries the same definition and no-ops once it sees it.
    EXECUTE $v$
      CREATE VIEW public.v_model_full_outcome_record WITH (security_invoker = on) AS
      WITH graded AS (
        SELECT o.model_id,
               CASE o.result WHEN 'WIN' THEN 'W' WHEN 'LOSS' THEN 'L' ELSE 'P' END AS res,
               o.decision_odds,
               m.paused,
               m.prob_only,
               o.profit_units AS profit,
               (o.model_probability >= m.min_prob
                AND (m.prob_only OR o.decision_edge >= COALESCE(m.min_edge, 0::numeric))
                AND (m.min_odds IS NULL OR o.decision_odds IS NULL OR o.decision_odds >= m.min_odds)) AS passes
        FROM mv_scored_pick_outcomes o
        JOIN model_action_thresholds m ON m.model_id = o.model_id
      )
      SELECT model_id,
             bool_or(paused) AS paused,
             bool_or(prob_only) AS prob_only,
             count(*) FILTER (WHERE passes AND res = ANY (ARRAY['W','L','P'])) AS bets,
             count(*) FILTER (WHERE passes AND res = 'W') AS wins,
             count(*) FILTER (WHERE passes AND res = 'L') AS losses,
             count(*) FILTER (WHERE passes AND res = 'P') AS pushes,
             count(*) FILTER (WHERE passes AND res = ANY (ARRAY['W','L','P']) AND decision_odds IS NOT NULL) AS priced_bets,
             CASE WHEN model_id = 'mlb_prop_batter_hr' THEN 0::numeric
                  ELSE round(COALESCE(sum(profit) FILTER (WHERE passes), 0::numeric), 6) END AS units,
             CASE WHEN model_id = 'mlb_prop_batter_hr' THEN NULL::numeric
                  ELSE round(sum(profit) FILTER (WHERE passes)
                             / NULLIF(count(*) FILTER (WHERE passes AND res = ANY (ARRAY['W','L','P']) AND decision_odds IS NOT NULL), 0)::numeric
                             * 100::numeric, 1) END AS roi_pct
      FROM graded
      GROUP BY model_id
    $v$;
    REVOKE ALL ON public.v_model_full_outcome_record FROM anon, authenticated;
    GRANT SELECT ON public.v_model_full_outcome_record TO anon, authenticated;
    RAISE NOTICE 'mv_scored_pick_outcomes rebuilt at the decision price';
  END IF;

  -- ── 3. the two other picks-reading record views ─────────────────────────
  d := pg_get_viewdef('public.v_model_full_outcome_picks'::regclass, true);
  IF position('decision_edge' in d) = 0 THEN
    -- Columns are APPENDED (CREATE OR REPLACE VIEW allows nothing else); the
    -- existing dk_odds / edge columns keep their DraftKings meaning.
    EXECUTE $v$
      CREATE OR REPLACE VIEW public.v_model_full_outcome_picks WITH (security_invoker = on) AS
      SELECT o.pick_id, o.model_id, o.game_date, o.game_id, o.pick_label, o.pick_side,
             o.model_probability, o.edge, o.dk_odds, o.scored_line,
             o.result, o.profit_units,
             o.decision_book, o.decision_odds, o.decision_edge
      FROM mv_scored_pick_outcomes o
      JOIN model_action_thresholds m ON m.model_id = o.model_id
      WHERE o.model_probability >= m.min_prob
        AND (m.prob_only OR o.decision_edge >= COALESCE(m.min_edge, 0::numeric))
        AND (m.min_odds IS NULL OR o.decision_odds IS NULL OR o.decision_odds >= m.min_odds)
    $v$;
    RAISE NOTICE 'v_model_full_outcome_picks reads the matview at the decision price';
  END IF;

  d := pg_get_viewdef('public.v_model_full_record'::regclass, true);
  IF position('decision_odds' in d) = 0 THEN
    EXECUTE $v$
      CREATE OR REPLACE VIEW public.v_model_full_record WITH (security_invoker = on) AS
      WITH scored AS (
        SELECT p.model_id, p.pick_side, p.model_probability AS prob,
               COALESCE(p.decision_edge, p.edge) AS edge,
               p.scored_line,
               COALESCE(p.decision_odds, p.dk_odds, '-110'::integer::numeric) AS dk_odds,
               g.home_score, g.away_score, g.home_win_reg, g.went_to_ot,
               g.home_score_f5, g.away_score_f5,
               t.min_prob, t.min_edge, t.prob_only, t.paused,
               CASE
                 WHEN p.model_id LIKE '%f5_moneyline%' THEN 'h2h_1st_5_innings'
                 WHEN p.model_id LIKE '%f5_over_under%' THEN 'totals_1st_5_innings'
                 WHEN p.model_id LIKE '%f5_runline%' THEN 'spreads_1st_5_innings'
                 WHEN p.model_id = 'nhl_moneyline_regulation' THEN 'h2h_3way'
                 WHEN p.model_id LIKE '%over_under%' THEN 'totals'
                 WHEN p.model_id LIKE '%runline%' OR p.model_id LIKE '%puckline%' OR p.model_id LIKE '%spread%' THEN 'spreads'
                 ELSE 'h2h'
               END AS market
        FROM picks p
        JOIN games g ON g.game_id = p.game_id
        JOIN model_action_thresholds t ON t.model_id = p.model_id
        WHERE p.game_date >= '2026-04-14' AND p.is_live IS NOT TRUE
          AND g.home_score IS NOT NULL
          AND p.model_id NOT LIKE '%prop%' AND p.model_id NOT LIKE 'ufc_%' AND p.model_id NOT LIKE 'golf_%'
      ), ev AS (
        SELECT scored.*,
               CASE WHEN scored.market LIKE '%1st_5_innings' THEN scored.home_score_f5 ELSE scored.home_score END AS sh,
               CASE WHEN scored.market LIKE '%1st_5_innings' THEN scored.away_score_f5 ELSE scored.away_score END AS sa
        FROM scored
      ), o AS (
        SELECT ev.*,
               NOT ev.paused AND ev.prob >= ev.min_prob AND (ev.prob_only OR ev.edge >= ev.min_edge) AS qualifies,
               CASE
                 WHEN ev.sh IS NULL OR ev.sa IS NULL THEN NULL
                 WHEN ev.market IN ('h2h', 'h2h_1st_5_innings') THEN
                   CASE WHEN ev.sh = ev.sa THEN 'PUSH'
                        WHEN ev.pick_side = 'home' AND ev.sh > ev.sa THEN 'WIN'
                        WHEN ev.pick_side = 'away' AND ev.sa > ev.sh THEN 'WIN'
                        ELSE 'LOSS' END
                 WHEN ev.market = 'h2h_3way' THEN
                   CASE WHEN ev.pick_side = 'home' THEN CASE WHEN ev.home_win_reg = 1 THEN 'WIN' ELSE 'LOSS' END
                        WHEN ev.pick_side = 'away' THEN CASE WHEN ev.home_win_reg = 0 AND COALESCE(ev.went_to_ot, 0) = 0 THEN 'WIN' ELSE 'LOSS' END
                        WHEN ev.pick_side = 'draw' THEN CASE WHEN ev.went_to_ot = 1 THEN 'WIN' ELSE 'LOSS' END
                        ELSE NULL END
                 WHEN ev.market IN ('totals', 'totals_1st_5_innings') THEN
                   CASE WHEN ev.scored_line IS NULL THEN NULL
                        WHEN (ev.sh + ev.sa) = ev.scored_line THEN 'PUSH'
                        WHEN ev.pick_side = 'over' AND (ev.sh + ev.sa) > ev.scored_line THEN 'WIN'
                        WHEN ev.pick_side = 'under' AND (ev.sh + ev.sa) < ev.scored_line THEN 'WIN'
                        ELSE 'LOSS' END
                 WHEN ev.market IN ('spreads', 'spreads_1st_5_innings') THEN
                   CASE WHEN ev.scored_line IS NULL THEN NULL
                        WHEN (ev.sh - ev.sa + ev.scored_line) = 0 THEN 'PUSH'
                        WHEN ev.pick_side = 'home' AND (ev.sh - ev.sa + ev.scored_line) > 0 THEN 'WIN'
                        WHEN ev.pick_side = 'away' AND (ev.sh - ev.sa + ev.scored_line) < 0 THEN 'WIN'
                        ELSE 'LOSS' END
                 ELSE NULL
               END AS res
        FROM ev
      )
      SELECT model_id,
             count(*) FILTER (WHERE qualifies AND res IN ('WIN','LOSS','PUSH')) AS picks,
             count(*) FILTER (WHERE qualifies AND res = 'WIN') AS wins,
             count(*) FILTER (WHERE qualifies AND res = 'LOSS') AS losses,
             count(*) FILTER (WHERE qualifies AND res = 'PUSH') AS pushes,
             round(sum(CASE
               WHEN qualifies AND res = 'WIN' THEN CASE WHEN dk_odds > 0 THEN dk_odds / 100.0 ELSE 100.0 / abs(dk_odds) END
               WHEN qualifies AND res = 'LOSS' THEN '-1.0'::numeric
               ELSE 0 END), 3) AS profit_units
      FROM o
      GROUP BY model_id
    $v$;
    RAISE NOTICE 'v_model_full_record grades at the decision price';
  END IF;

  -- ── 4. the custom-model builder RPCs ─────────────────────────────────────
  SELECT p.prosrc INTO d FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'public' AND p.proname = 'custom_model_picks';
  IF d IS NULL OR position('decision_edge' in d) = 0 THEN
    -- The return table gains columns, which CREATE OR REPLACE refuses.
    DROP FUNCTION IF EXISTS public.custom_model_picks(jsonb, jsonb, int);

    EXECUTE $fn$
      CREATE OR REPLACE FUNCTION public.custom_model_backtest(
        p_rules jsonb,
        p_filters jsonb DEFAULT '{}'::jsonb
      )
      RETURNS TABLE (
        bets bigint, wins bigint, losses bigint, pushes bigint,
        priced bigint, units numeric, roi_pct numeric
      )
      LANGUAGE plpgsql STABLE SET search_path = public, pg_temp AS $body$
      DECLARE
        v_signals    text[] := _jsonb_text_array(p_filters->'signals');
        v_bet_kinds  text[] := _jsonb_text_array(p_filters->'betKinds');
        v_sides      text[] := _jsonb_text_array(p_filters->'sides');
        v_price      text[] := _jsonb_text_array(p_filters->'price');
        v_slots      text[] := _jsonb_text_array(p_filters->'timeSlots');
        v_days       text[] := _jsonb_text_array(p_filters->'dayTypes');
        v_tiers      text[] := _jsonb_text_array(p_filters->'tiers');
        v_min_odds   numeric := (p_filters->>'minOdds')::numeric;
        v_max_odds   numeric := (p_filters->>'maxOdds')::numeric;
        v_min_line   numeric := (p_filters->>'minLine')::numeric;
        v_max_line   numeric := (p_filters->>'maxLine')::numeric;
        v_max_public numeric := (p_filters->>'maxPublicBetPct')::numeric;
        v_min_public numeric := (p_filters->>'minPublicBetPct')::numeric;
        v_excl_inj   boolean := COALESCE((p_filters->>'excludeInjuries')::boolean, false);
      BEGIN
        RETURN QUERY
        WITH r AS (
          SELECT (x->>'model_id')::text AS mid,
                 COALESCE((x->>'min_prob')::numeric, 0) AS mp,
                 COALESCE((x->>'min_edge')::numeric, -9.99) AS me,
                 (x->>'min_ev')::numeric AS mev
          FROM jsonb_array_elements(COALESCE(p_rules,'[]'::jsonb)) x
        ),
        m AS (
          SELECT v.result AS res, v.profit_units AS pu
          FROM mv_scored_pick_outcomes v
          WHERE EXISTS (
              SELECT 1 FROM r
              WHERE r.mid = v.model_id AND v.model_probability >= r.mp AND v.decision_edge >= r.me
                AND (r.mev IS NULL OR (v.decision_odds IS NOT NULL AND
                     v.model_probability * (CASE WHEN v.decision_odds > 0 THEN 1 + v.decision_odds/100.0
                                                 ELSE 1 + 100.0/ABS(v.decision_odds) END) - 1 >= r.mev)))
            AND (v_signals   IS NULL OR v.signal_type = ANY(v_signals))
            AND (v_bet_kinds IS NULL OR v.bet_kind    = ANY(v_bet_kinds))
            AND (v_sides     IS NULL OR v.pick_side   = ANY(v_sides))
            AND (v_price     IS NULL OR (v.price_side IS NOT NULL AND v.price_side = ANY(v_price)))
            AND (v_slots     IS NULL OR (v.time_slot  IS NOT NULL AND v.time_slot  = ANY(v_slots)))
            AND (v_days      IS NULL OR (CASE WHEN EXTRACT(ISODOW FROM v.game_date::date) >= 6
                                              THEN 'weekend' ELSE 'weekday' END) = ANY(v_days))
            AND (v_tiers     IS NULL OR (v.confidence_tier IS NOT NULL AND v.confidence_tier = ANY(v_tiers)))
            AND (v_min_odds  IS NULL OR (v.decision_odds IS NOT NULL AND v.decision_odds >= v_min_odds))
            AND (v_max_odds  IS NULL OR (v.decision_odds IS NOT NULL AND v.decision_odds <= v_max_odds))
            AND (v_min_line  IS NULL OR (v.scored_line IS NOT NULL AND v.scored_line >= v_min_line))
            AND (v_max_line  IS NULL OR (v.scored_line IS NOT NULL AND v.scored_line <= v_max_line))
            AND (v_max_public IS NULL OR (v.public_bet_pct IS NOT NULL AND v.public_bet_pct <= v_max_public))
            AND (v_min_public IS NULL OR (v.public_bet_pct IS NOT NULL AND v.public_bet_pct >= v_min_public))
            AND (NOT v_excl_inj OR v.injury_flag IS NULL OR btrim(v.injury_flag) = '')
        )
        SELECT
          count(*)                                      AS bets,
          count(*) FILTER (WHERE res = 'WIN')           AS wins,
          count(*) FILTER (WHERE res = 'LOSS')          AS losses,
          count(*) FILTER (WHERE res = 'PUSH')          AS pushes,
          count(*) FILTER (WHERE pu IS NOT NULL)        AS priced,
          COALESCE(sum(pu), 0)                          AS units,
          CASE WHEN count(*) FILTER (WHERE pu IS NOT NULL) > 0
               THEN round(100.0 * COALESCE(sum(pu),0) / count(*) FILTER (WHERE pu IS NOT NULL), 2)
               ELSE NULL END                            AS roi_pct
        FROM m;
      END;
      $body$
    $fn$;

    EXECUTE $fn$
      CREATE FUNCTION public.custom_model_picks(
        p_rules jsonb,
        p_filters jsonb DEFAULT '{}'::jsonb,
        p_limit int DEFAULT 200
      )
      RETURNS TABLE (
        pick_id bigint, model_id text, game_date text, game_id text,
        pick_label text, pick_side text, signal_type text,
        model_probability numeric, edge numeric, dk_odds numeric,
        result text, profit_units numeric,
        decision_book text, decision_odds numeric, decision_edge numeric
      )
      LANGUAGE plpgsql STABLE SET search_path = public, pg_temp AS $body$
      DECLARE
        v_signals    text[] := _jsonb_text_array(p_filters->'signals');
        v_bet_kinds  text[] := _jsonb_text_array(p_filters->'betKinds');
        v_sides      text[] := _jsonb_text_array(p_filters->'sides');
        v_price      text[] := _jsonb_text_array(p_filters->'price');
        v_slots      text[] := _jsonb_text_array(p_filters->'timeSlots');
        v_days       text[] := _jsonb_text_array(p_filters->'dayTypes');
        v_tiers      text[] := _jsonb_text_array(p_filters->'tiers');
        v_min_odds   numeric := (p_filters->>'minOdds')::numeric;
        v_max_odds   numeric := (p_filters->>'maxOdds')::numeric;
        v_min_line   numeric := (p_filters->>'minLine')::numeric;
        v_max_line   numeric := (p_filters->>'maxLine')::numeric;
        v_max_public numeric := (p_filters->>'maxPublicBetPct')::numeric;
        v_min_public numeric := (p_filters->>'minPublicBetPct')::numeric;
        v_excl_inj   boolean := COALESCE((p_filters->>'excludeInjuries')::boolean, false);
      BEGIN
        RETURN QUERY
        WITH r AS (
          SELECT (x->>'model_id')::text AS mid,
                 COALESCE((x->>'min_prob')::numeric, 0) AS mp,
                 COALESCE((x->>'min_edge')::numeric, -9.99) AS me,
                 (x->>'min_ev')::numeric AS mev
          FROM jsonb_array_elements(COALESCE(p_rules,'[]'::jsonb)) x
        )
        SELECT v.pick_id, v.model_id, v.game_date, v.game_id, v.pick_label,
               v.pick_side, v.signal_type, v.model_probability, v.edge, v.dk_odds,
               v.result, v.profit_units,
               v.decision_book, v.decision_odds, v.decision_edge
        FROM mv_scored_pick_outcomes v
        WHERE EXISTS (
            SELECT 1 FROM r
            WHERE r.mid = v.model_id AND v.model_probability >= r.mp AND v.decision_edge >= r.me
              AND (r.mev IS NULL OR (v.decision_odds IS NOT NULL AND
                   v.model_probability * (CASE WHEN v.decision_odds > 0 THEN 1 + v.decision_odds/100.0
                                               ELSE 1 + 100.0/ABS(v.decision_odds) END) - 1 >= r.mev)))
          AND (v_signals   IS NULL OR v.signal_type = ANY(v_signals))
          AND (v_bet_kinds IS NULL OR v.bet_kind    = ANY(v_bet_kinds))
          AND (v_sides     IS NULL OR v.pick_side   = ANY(v_sides))
          AND (v_price     IS NULL OR (v.price_side IS NOT NULL AND v.price_side = ANY(v_price)))
          AND (v_slots     IS NULL OR (v.time_slot  IS NOT NULL AND v.time_slot  = ANY(v_slots)))
          AND (v_days      IS NULL OR (CASE WHEN EXTRACT(ISODOW FROM v.game_date::date) >= 6
                                            THEN 'weekend' ELSE 'weekday' END) = ANY(v_days))
          AND (v_tiers     IS NULL OR (v.confidence_tier IS NOT NULL AND v.confidence_tier = ANY(v_tiers)))
          AND (v_min_odds  IS NULL OR (v.decision_odds IS NOT NULL AND v.decision_odds >= v_min_odds))
          AND (v_max_odds  IS NULL OR (v.decision_odds IS NOT NULL AND v.decision_odds <= v_max_odds))
          AND (v_min_line  IS NULL OR (v.scored_line IS NOT NULL AND v.scored_line >= v_min_line))
          AND (v_max_line  IS NULL OR (v.scored_line IS NOT NULL AND v.scored_line <= v_max_line))
          AND (v_max_public IS NULL OR (v.public_bet_pct IS NOT NULL AND v.public_bet_pct <= v_max_public))
          AND (v_min_public IS NULL OR (v.public_bet_pct IS NOT NULL AND v.public_bet_pct >= v_min_public))
          AND (NOT v_excl_inj OR v.injury_flag IS NULL OR btrim(v.injury_flag) = '')
        ORDER BY v.game_date DESC, v.pick_id DESC
        LIMIT GREATEST(p_limit, 0);
      END;
      $body$
    $fn$;

    GRANT EXECUTE ON FUNCTION public.custom_model_backtest(jsonb, jsonb) TO anon, authenticated;
    GRANT EXECUTE ON FUNCTION public.custom_model_picks(jsonb, jsonb, int) TO anon, authenticated;
    RAISE NOTICE 'custom_model_backtest / custom_model_picks grade at the decision price';
  END IF;
END
$mig$;
