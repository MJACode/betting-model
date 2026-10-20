-- Same-book raw CLV is the headline. Pinnacle's power-de-vigged close is
-- the market-edge column. docs/clv.md.
--
-- Primary (neither side de-vigged), at the book the bet was taken at, same
-- side, same line, last pre-start snapshot:
--   clv_pct = (taken_decimal / close_decimal - 1) * 100
--   clv_pp  = (raw_close_implied - raw_taken_implied) * 100
-- Beat = clv_pct > 0. No pre-start close at that book on that line → NULL.
-- Another book is not a substitute.
--
-- Secondary, only when Pinnacle has a pre-start close on that line:
--   market_clv_pct = (taken_decimal * fair_close_prob - 1) * 100
--   fair_close from power de-vig (3-way when the close has a draw).
--
-- One statement. DDL is behind a catalog guard so a later pass fires no
-- pgrst_ddl_watch event. The recompute runs only while a row is still not
-- standard_v2. Worked picks 3114189, 2387645 and 3114194 are checked before
-- any row is written; a mismatch raises and the transaction rolls back.
-- Puck-line rows are not rewritten: the close matches the stored HOME sign.
-- A team total's close is its 'close' snapshot only: its other rows are the
-- decision fetch, the price taken (data/ingestors/nba_team_total_odds.py).
-- results_snapshots is not touched.

DO $mig$
DECLARE
  fn_comment text := 'clv-standard-v2-power-80-0.05-12-nba-team-total-luck';
  work_left boolean;
  def text;
  new_def text;
  old_tok text := 'clv_method = ANY (ARRAY[''no_vig''::text, ''zero_vig''::text])';
  new_tok text := 'clv_method = ''standard_v2''::text';
  extra text;
  pin jsonb;
  n_full integer;
  n_empty integer;
BEGIN
  PERFORM set_config('statement_timeout', '600000', true);

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'picks' AND column_name = 'clv_pp'
  ) THEN
    ALTER TABLE public.picks
      ADD COLUMN clv_pp numeric,
      ADD COLUMN market_clv_pct numeric,
      ADD COLUMN market_clv_pp numeric,
      ADD COLUMN market_clv_method text,
      ADD COLUMN pinnacle_close_odds numeric;
  END IF;

  IF col_description('public.picks'::regclass,
       (SELECT attnum FROM pg_attribute
         WHERE attrelid = 'public.picks'::regclass AND attname = 'clv_pct' AND NOT attisdropped)
     ) IS DISTINCT FROM
     'Same-book raw CLV, percent: (taken_decimal / close_decimal - 1) * 100. NULL when that book has no pre-start close on the same line. standard_v2. docs/clv.md.'
  THEN
    COMMENT ON COLUMN public.picks.clv_pct IS
      'Same-book raw CLV, percent: (taken_decimal / close_decimal - 1) * 100. NULL when that book has no pre-start close on the same line. standard_v2. docs/clv.md.';
    COMMENT ON COLUMN public.picks.clv_pp IS
      'Same-book raw CLV, probability points: (raw close implied - raw taken implied) * 100. NULL with clv_pct.';
    COMMENT ON COLUMN public.picks.market_clv_pct IS
      'Market edge, percent: taken_decimal * Pinnacle fair close - 1, times 100. NULL without a Pinnacle close on the same line.';
    COMMENT ON COLUMN public.picks.market_clv_pp IS
      'Market edge, probability points: (Pinnacle fair close - raw taken implied) * 100.';
    COMMENT ON COLUMN public.picks.market_clv_method IS
      'How the Pinnacle close was de-vigged: power, power_3way, or zero_vig.';
    COMMENT ON COLUMN public.picks.pinnacle_close_odds IS
      'Pinnacle American on the bet side at the pre-start close. NULL when Pinnacle has no such quote.';
    COMMENT ON COLUMN public.picks.clv_method IS
      'standard_v2 is the only method averaged. Older stamps stay on the row until this recompute replaces them.';
    COMMENT ON COLUMN public.picks.clv_bet_book IS
      'Book the bet was taken at. Primary CLV reads that book''s own close.';
    COMMENT ON COLUMN public.picks.clv_close_book IS
      'Book whose American is closing_dk_odds: the bet book, when its close was found.';
    COMMENT ON COLUMN public.picks.clv_beat_close IS
      'True when same-book clv_pct > 0. NULL when the primary is NULL. Line movement stays in line_clv_pts and does not count as a beat.';
  END IF;

  IF to_regprocedure('public.clv_power_fair(double precision[])') IS NULL
     OR to_regprocedure('public.clv_prop_key(text)') IS NULL
     OR to_regprocedure('public.clv_game_market(text)') IS NULL
     OR COALESCE(obj_description(to_regprocedure('public.clv_power_fair(double precision[])')), '')
        IS DISTINCT FROM fn_comment THEN
    CREATE OR REPLACE FUNCTION public.clv_american_implied(american double precision)
    RETURNS double precision
    LANGUAGE sql IMMUTABLE AS $body$
      SELECT CASE
        WHEN american IS NULL OR american <> american THEN NULL
        WHEN american > 0 THEN 100.0 / (american + 100.0)
        ELSE abs(american) / (abs(american) + 100.0)
      END
    $body$;

    CREATE OR REPLACE FUNCTION public.clv_american_decimal(american double precision)
    RETURNS double precision
    LANGUAGE sql IMMUTABLE AS $body$
      SELECT CASE
        WHEN american IS NULL OR american = 0 OR american <> american THEN NULL
        WHEN american > 0 THEN 1.0 + american / 100.0
        ELSE 1.0 + 100.0 / abs(american)
      END
    $body$;

    CREATE OR REPLACE FUNCTION public.clv_label_book(token text)
    RETURNS text
    LANGUAGE sql IMMUTABLE AS $body$
      SELECT CASE upper(btrim(token))
        WHEN 'DK' THEN 'draftkings'
        WHEN 'FD' THEN 'fanduel'
        WHEN 'MGM' THEN 'betmgm'
        WHEN 'CZR' THEN 'williamhill_us'
        WHEN 'ESPN' THEN 'espnbet'
        WHEN 'BR' THEN 'betrivers'
        WHEN 'BOV' THEN 'bovada'
        WHEN 'PIN' THEN 'pinnacle'
        ELSE NULLIF(lower(btrim(token)), '')
      END
    $body$;

    CREATE OR REPLACE FUNCTION public.clv_prop_key(model_id text)
    RETURNS text
    LANGUAGE sql IMMUTABLE AS $body$
      SELECT CASE model_id
        WHEN 'mlb_prop_pitcher_k' THEN 'pitcher_strikeouts'
        WHEN 'mlb_prop_pitcher_hits' THEN 'pitcher_hits_allowed'
        WHEN 'mlb_prop_pitcher_er' THEN 'pitcher_earned_runs'
        WHEN 'mlb_prop_pitcher_outs' THEN 'pitcher_outs'
        WHEN 'mlb_prop_pitcher_walks' THEN 'pitcher_walks'
        WHEN 'mlb_prop_batter_hits' THEN 'batter_hits'
        WHEN 'mlb_prop_batter_tb' THEN 'batter_total_bases'
        WHEN 'mlb_prop_batter_hr' THEN 'batter_home_runs'
        WHEN 'mlb_prop_batter_rbi' THEN 'batter_rbis'
        WHEN 'mlb_prop_batter_runs' THEN 'batter_runs_scored'
        WHEN 'mlb_prop_batter_sb' THEN 'batter_stolen_bases'
        WHEN 'mlb_prop_batter_walks' THEN 'batter_walks'
        WHEN 'wnba_prop_player_points' THEN 'player_points'
        WHEN 'wnba_prop_player_rebounds' THEN 'player_rebounds'
        WHEN 'wnba_prop_player_assists' THEN 'player_assists'
        WHEN 'wnba_prop_player_threes' THEN 'player_threes'
        WHEN 'wnba_prop_player_pra' THEN 'player_points_rebounds_assists'
        WHEN 'nba_prop_player_points' THEN 'player_points'
        WHEN 'nba_prop_player_rebounds' THEN 'player_rebounds'
        WHEN 'nba_prop_player_assists' THEN 'player_assists'
        WHEN 'nba_prop_player_threes' THEN 'player_threes'
        WHEN 'nba_prop_player_pra' THEN 'player_points_rebounds_assists'
        WHEN 'nba_prop_player_blocks' THEN 'player_blocks'
        WHEN 'nba_prop_player_steals' THEN 'player_steals'
        WHEN 'nba_prop_player_turnovers' THEN 'player_turnovers'
        WHEN 'nba_prop_player_dd' THEN 'player_double_double'
        WHEN 'nfl_prop_pass_yards' THEN 'player_pass_yds'
        WHEN 'nfl_prop_pass_attempts' THEN 'player_pass_attempts'
        WHEN 'nfl_prop_pass_completions' THEN 'player_pass_completions'
        WHEN 'nfl_prop_pass_tds' THEN 'player_pass_tds'
        WHEN 'nfl_prop_rush_yards' THEN 'player_rush_yds'
        WHEN 'nfl_prop_rush_attempts' THEN 'player_rush_attempts'
        WHEN 'nfl_prop_rec_yards' THEN 'player_reception_yds'
        WHEN 'nfl_prop_receptions' THEN 'player_receptions'
        WHEN 'nfl_prop_rush_rec_yards' THEN 'player_rush_reception_yds'
        WHEN 'nfl_prop_anytime_td' THEN 'player_anytime_td'
        WHEN 'nfl_prop_tackles_assists' THEN 'player_tackles_assists'
        WHEN 'nfl_prop_sacks' THEN 'player_sacks'
        WHEN 'nhl_prop_blocked_shots' THEN 'player_blocked_shots'
        WHEN 'nhl_prop_saves' THEN 'player_total_saves'
        WHEN 'nhl_prop_shots_on_goal' THEN 'player_shots_on_goal'
        WHEN 'nhl_prop_assists' THEN 'player_assists'
        ELSE NULL
      END
    $body$;

    CREATE OR REPLACE FUNCTION public.clv_game_market(model_id text)
    RETURNS text
    LANGUAGE sql IMMUTABLE AS $body$
      SELECT CASE model_id
        WHEN 'mlb_moneyline' THEN 'h2h'
        WHEN 'mlb_over_under' THEN 'totals'
        WHEN 'mlb_runline' THEN 'spreads'
        WHEN 'mlb_f5_moneyline' THEN 'h2h_1st_5_innings'
        WHEN 'mlb_f5_over_under' THEN 'totals_1st_5_innings'
        WHEN 'mlb_f5_runline' THEN 'spreads_1st_5_innings'
        WHEN 'nhl_moneyline' THEN 'h2h'
        WHEN 'nhl_moneyline_regulation' THEN 'h2h_3way'
        WHEN 'nhl_puckline' THEN 'spreads'
        WHEN 'nhl_over_under' THEN 'totals'
        WHEN 'wnba_moneyline' THEN 'h2h'
        WHEN 'wnba_over_under' THEN 'totals'
        WHEN 'wnba_spread' THEN 'spreads'
        WHEN 'nba_moneyline' THEN 'h2h'
        WHEN 'nba_over_under' THEN 'totals'
        WHEN 'nba_spread' THEN 'spreads'
        WHEN 'ufc_moneyline' THEN 'h2h'
        WHEN 'ufc_total_rounds' THEN 'totals'
        WHEN 'ufc_method_of_victory' THEN 'method'
        WHEN 'ncaaf_spread' THEN 'spreads'
        WHEN 'ncaaf_spread_premium' THEN 'spreads'
        WHEN 'ncaaf_over_under' THEN 'totals'
        WHEN 'ncaaf_moneyline' THEN 'h2h'
        WHEN 'nfl_wind_totals' THEN 'totals'
        WHEN 'nfl_opener_spread' THEN 'spreads'
        WHEN 'mlb_spread_market' THEN 'spreads'
        WHEN 'mlb_total_market' THEN 'totals'
        WHEN 'mlb_total_public_fade' THEN 'totals'
        WHEN 'mlb_live_win_prob' THEN 'h2h'
        WHEN 'mlb_live_runline' THEN 'spreads'
        WHEN 'mlb_live_total_runs' THEN 'totals'
        WHEN 'ncaaf_live_win_prob' THEN 'h2h'
        WHEN 'ncaaf_live_total' THEN 'totals'
        WHEN 'nba_total_luck' THEN 'totals'
        WHEN 'nba_team_total_luck' THEN 'team_totals_home'
        ELSE 'h2h'
      END
    $body$;

    CREATE OR REPLACE FUNCTION public.clv_power_fair(prices double precision[])
    RETURNS double precision[]
    LANGUAGE plpgsql IMMUTABLE AS $body$
    DECLARE
      n int;
      i int;
      ips double precision[];
      p double precision;
      lo double precision := 0.05;
      hi double precision := 12.0;
      k double precision;
      total double precision;
      powered double precision[];
      scale double precision;
      iter int;
    BEGIN
      n := COALESCE(array_length(prices, 1), 0);
      IF n < 2 THEN
        RETURN NULL;
      END IF;
      ips := ARRAY[]::double precision[];
      FOR i IN 1..n LOOP
        p := public.clv_american_implied(prices[i]);
        IF p IS NULL OR p <= 0 OR p >= 1 THEN
          RETURN NULL;
        END IF;
        ips := ips || p;
      END LOOP;
      IF abs((SELECT SUM(x) FROM unnest(ips) AS x) - 1.0) < 1e-12 THEN
        RETURN ips;
      END IF;
      FOR iter IN 1..80 LOOP
        k := (lo + hi) / 2.0;
        total := 0;
        FOR i IN 1..n LOOP
          total := total + power(ips[i], k);
        END LOOP;
        IF total > 1.0 THEN
          lo := k;
        ELSE
          hi := k;
        END IF;
      END LOOP;
      k := (lo + hi) / 2.0;
      powered := ARRAY[]::double precision[];
      scale := 0;
      FOR i IN 1..n LOOP
        p := power(ips[i], k);
        powered := powered || p;
        scale := scale + p;
      END LOOP;
      IF scale = 0 THEN
        RETURN NULL;
      END IF;
      FOR i IN 1..n LOOP
        powered[i] := powered[i] / scale;
      END LOOP;
      RETURN powered;
    END
    $body$;

    CREATE OR REPLACE FUNCTION public.clv_same_book(bet double precision, close_px double precision)
    RETURNS TABLE(pct numeric, pp numeric)
    LANGUAGE plpgsql IMMUTABLE AS $body$
    DECLARE
      taken_p double precision;
      close_p double precision;
      taken_d double precision;
      close_d double precision;
    BEGIN
      taken_p := public.clv_american_implied(bet);
      close_p := public.clv_american_implied(close_px);
      taken_d := public.clv_american_decimal(bet);
      close_d := public.clv_american_decimal(close_px);
      IF taken_p IS NULL OR close_p IS NULL OR taken_d IS NULL OR close_d IS NULL OR close_d = 0 THEN
        pct := NULL;
        pp := NULL;
        RETURN NEXT;
        RETURN;
      END IF;
      pct := round((((taken_d / close_d) - 1.0) * 100.0)::numeric, 2);
      pp := round(((close_p - taken_p) * 100.0)::numeric, 2);
      RETURN NEXT;
    END
    $body$;

    CREATE OR REPLACE FUNCTION public.clv_market_edge(
      bet double precision,
      side_close double precision,
      others double precision[],
      book text
    )
    RETURNS TABLE(pct numeric, pp numeric, method text)
    LANGUAGE plpgsql IMMUTABLE AS $body$
    DECLARE
      taken_p double precision;
      taken_d double precision;
      fair double precision;
      fair_all double precision[];
      n_others int;
      i int;
    BEGIN
      taken_p := public.clv_american_implied(bet);
      taken_d := public.clv_american_decimal(bet);
      IF taken_p IS NULL OR taken_d IS NULL THEN
        pct := NULL; pp := NULL; method := NULL;
        RETURN NEXT;
        RETURN;
      END IF;
      IF lower(btrim(COALESCE(book, ''))) IN ('kalshi', 'polymarket') THEN
        fair := public.clv_american_implied(side_close);
        method := 'zero_vig';
      ELSE
        n_others := COALESCE(array_length(others, 1), 0);
        IF n_others < 1 THEN
          pct := NULL; pp := NULL; method := NULL;
          RETURN NEXT;
          RETURN;
        END IF;
        FOR i IN 1..n_others LOOP
          IF others[i] IS NULL THEN
            pct := NULL; pp := NULL; method := NULL;
            RETURN NEXT;
            RETURN;
          END IF;
        END LOOP;
        fair_all := public.clv_power_fair(ARRAY[side_close] || others);
        IF fair_all IS NULL THEN
          pct := NULL; pp := NULL; method := NULL;
          RETURN NEXT;
          RETURN;
        END IF;
        fair := fair_all[1];
        method := CASE WHEN n_others >= 2 THEN 'power_3way' ELSE 'power' END;
      END IF;
      IF fair IS NULL THEN
        pct := NULL; pp := NULL; method := NULL;
        RETURN NEXT;
        RETURN;
      END IF;
      pct := round(((taken_d * fair - 1.0) * 100.0)::numeric, 2);
      pp := round(((fair - taken_p) * 100.0)::numeric, 2);
      RETURN NEXT;
    END
    $body$;

    COMMENT ON FUNCTION public.clv_power_fair(double precision[]) IS
      'clv-standard-v2-power-80-0.05-12-nba-team-total-luck';
  END IF;

  SELECT EXISTS (
    SELECT 1
    FROM public.picks p
    JOIN public.games g ON g.game_id = p.game_id
    WHERE p.signal_type = 'BET'
      AND COALESCE(p.dk_odds, p.decision_odds) IS NOT NULL
      AND p.is_live IS NOT TRUE
      AND p.model_id NOT LIKE 'golf_%'
      AND p.clv_method IS DISTINCT FROM 'standard_v2'
      AND g.commence_time IS NOT NULL
      AND p.created_at::timestamptz <= g.commence_time::timestamptz
      AND g.commence_time::timestamptz <= now()
  ) INTO work_left;

  IF work_left THEN
    CREATE TEMP TABLE _clv_out ON COMMIT DROP AS
    WITH src AS (
      SELECT
        p.pick_id,
        p.game_id,
        p.model_id,
        p.pick_side,
        p.pick_label,
        p.scored_line,
        p.clv_method AS old_method,
        g.commence_time::timestamptz AS commence_ts,
        CASE
          WHEN p.game_time IS NOT NULL
           AND p.game_time::timestamptz < g.commence_time::timestamptz
          THEN p.game_time::timestamptz
          ELSE g.commence_time::timestamptz
        END AS close_bound,
        CASE
          WHEN p.decision_odds IS NOT NULL AND btrim(COALESCE(p.decision_book, '')) <> ''
            THEN p.decision_odds::double precision
          ELSE p.dk_odds::double precision
        END AS bet_price,
        CASE
          WHEN p.decision_odds IS NOT NULL AND btrim(COALESCE(p.decision_book, '')) <> ''
            THEN lower(btrim(p.decision_book))
          WHEN p.dk_odds IS NULL THEN NULL
          WHEN p.model_id IN ('nfl_prop_market', 'wnba_prop_market') THEN
            COALESCE(public.clv_label_book(substring(p.pick_label FROM '\(([A-Za-z_]+)\)\s*$')), 'draftkings')
          WHEN p.model_id IN ('nfl_wind_totals', 'nfl_opener_spread') THEN
            COALESCE(public.clv_label_book(substring(p.pick_label FROM ',\s*([A-Za-z_]+)\)')), 'draftkings')
          ELSE 'draftkings'
        END AS bet_book,
        CASE
          -- Multi-market prop models: the market is on the row. The two NBA ones
          -- (2026-10-16) fell to 'game' here, so a late recompute stamped their
          -- CLV empty and the Python capture never revisited it.
          WHEN p.model_id IN ('nfl_prop_market', 'wnba_prop_market',
                              'nba_prop_market', 'nba_prop_projection') THEN 'from_row'
          WHEN public.clv_prop_key(p.model_id) IS NOT NULL THEN 'prop'
          ELSE 'game'
        END AS kind,
        CASE
          WHEN p.model_id IN ('nfl_prop_market', 'wnba_prop_market',
                              'nba_prop_market', 'nba_prop_projection') THEN p.prop_market
          ELSE public.clv_prop_key(p.model_id)
        END AS prop_market,
        public.clv_game_market(p.model_id) AS game_market,
        substring(p.pick_label FROM '^(.+?)\s+(?:Over|Under)\s+') AS player_name,
        split_part(p.game_id, '_', 1) AS sport_prefix
      FROM public.picks p
      JOIN public.games g ON g.game_id = p.game_id
      WHERE p.signal_type = 'BET'
        AND COALESCE(p.dk_odds, p.decision_odds) IS NOT NULL
        AND p.is_live IS NOT TRUE
        AND p.model_id NOT LIKE 'golf_%'
        AND p.clv_method IS DISTINCT FROM 'standard_v2'
        AND g.commence_time IS NOT NULL
        AND p.created_at::timestamptz <= g.commence_time::timestamptz
        AND g.commence_time::timestamptz <= now()
    ),
    joined AS (
      SELECT
        s.*,
        (s.kind = 'game' AND (s.game_market LIKE '%spreads%' OR s.game_market LIKE '%totals%')) AS has_line,
        bp.over_price AS bp_over, bp.under_price AS bp_under, bp.line AS bp_line,
        bs.home_price AS bs_home, bs.away_price AS bs_away, bs.draw_price AS bs_draw,
        bs.spread_home AS bs_spread, bs.total_line AS bs_total,
        bs.over_price AS bs_over, bs.under_price AS bs_under,
        bm.home_price AS bm_home, bm.away_price AS bm_away, bm.draw_price AS bm_draw,
        bm.spread_home AS bm_spread, bm.total_line AS bm_total,
        bm.over_price AS bm_over, bm.under_price AS bm_under,
        pp.over_price AS pp_over, pp.under_price AS pp_under, pp.line AS pp_line,
        ps.home_price AS ps_home, ps.away_price AS ps_away, ps.draw_price AS ps_draw,
        ps.spread_home AS ps_spread, ps.total_line AS ps_total,
        ps.over_price AS ps_over, ps.under_price AS ps_under
      FROM src s
      LEFT JOIN LATERAL (
        SELECT o.over_price, o.under_price, o.line
        FROM public.player_prop_odds o
        WHERE s.kind <> 'game'
          AND s.prop_market IS NOT NULL
          AND s.player_name IS NOT NULL
          AND s.bet_book IS NOT NULL
          AND o.game_id = s.game_id
          AND o.player_name = s.player_name
          AND o.market = s.prop_market
          AND o.bookmaker = s.bet_book
          AND o.snapshot_at::timestamptz <= s.close_bound
        ORDER BY o.snapshot_at::timestamptz DESC
        LIMIT 1
      ) bp ON TRUE
      LEFT JOIN LATERAL (
        SELECT o.home_price, o.away_price, o.draw_price, o.spread_home, o.total_line,
               o.over_price, o.under_price
        FROM public.odds o
        WHERE s.kind = 'game'
          AND s.bet_book IS NOT NULL
          AND o.game_id = s.game_id
          AND o.market = s.game_market
          AND o.bookmaker = s.bet_book
          AND ((s.game_market LIKE 'team_totals%' AND o.snapshot_type = 'close')
            OR (s.game_market NOT LIKE 'team_totals%' AND o.snapshot_type <> 'in_play'))
          AND o.snapshot_at::timestamptz <= s.close_bound
          AND (
            (s.game_market LIKE '%spreads%' AND o.spread_home = s.scored_line)
            OR (s.game_market LIKE '%totals%' AND o.total_line = s.scored_line)
            OR (s.game_market NOT LIKE '%spreads%' AND s.game_market NOT LIKE '%totals%')
          )
        ORDER BY o.snapshot_at::timestamptz DESC
        LIMIT 1
      ) bs ON TRUE
      LEFT JOIN LATERAL (
        SELECT o.home_price, o.away_price, o.draw_price, o.spread_home, o.total_line,
               o.over_price, o.under_price
        FROM public.odds o
        WHERE s.kind = 'game'
          AND (s.game_market LIKE '%spreads%' OR s.game_market LIKE '%totals%')
          AND s.bet_book IS NOT NULL
          AND o.game_id = s.game_id
          AND o.market = s.game_market
          AND o.bookmaker = s.bet_book
          AND ((s.game_market LIKE 'team_totals%' AND o.snapshot_type = 'close')
            OR (s.game_market NOT LIKE 'team_totals%' AND o.snapshot_type <> 'in_play'))
          AND o.snapshot_at::timestamptz <= s.close_bound
          AND (
            s.game_market <> 'spreads'
            OR s.sport_prefix NOT IN ('MLB', 'NHL')
            OR ABS(o.spread_home) = 1.5
          )
        ORDER BY o.snapshot_at::timestamptz DESC
        LIMIT 1
      ) bm ON TRUE
      LEFT JOIN LATERAL (
        SELECT o.over_price, o.under_price, o.line
        FROM public.player_prop_odds o
        WHERE s.kind <> 'game'
          AND s.prop_market IS NOT NULL
          AND s.player_name IS NOT NULL
          AND o.game_id = s.game_id
          AND o.player_name = s.player_name
          AND o.market = s.prop_market
          AND o.bookmaker = 'pinnacle'
          AND o.snapshot_at::timestamptz <= s.close_bound
        ORDER BY o.snapshot_at::timestamptz DESC
        LIMIT 1
      ) pp ON TRUE
      LEFT JOIN LATERAL (
        SELECT o.home_price, o.away_price, o.draw_price, o.spread_home, o.total_line,
               o.over_price, o.under_price
        FROM public.odds o
        WHERE s.kind = 'game'
          AND o.game_id = s.game_id
          AND o.market = s.game_market
          AND o.bookmaker = 'pinnacle'
          AND ((s.game_market LIKE 'team_totals%' AND o.snapshot_type = 'close')
            OR (s.game_market NOT LIKE 'team_totals%' AND o.snapshot_type <> 'in_play'))
          AND o.snapshot_at::timestamptz <= s.close_bound
          AND (
            (s.game_market LIKE '%spreads%' AND o.spread_home = s.scored_line)
            OR (s.game_market LIKE '%totals%' AND o.total_line = s.scored_line)
            OR (s.game_market NOT LIKE '%spreads%' AND s.game_market NOT LIKE '%totals%')
          )
        ORDER BY o.snapshot_at::timestamptz DESC
        LIMIT 1
      ) ps ON TRUE
    ),
    priced AS (
      SELECT
        j.*,
        CASE
          WHEN j.kind = 'game' THEN CASE j.pick_side
            WHEN 'home' THEN j.bs_home WHEN 'away' THEN j.bs_away WHEN 'draw' THEN j.bs_draw
            WHEN 'over' THEN j.bs_over WHEN 'under' THEN j.bs_under ELSE NULL END
          ELSE CASE j.pick_side
            WHEN 'over' THEN j.bp_over WHEN 'under' THEN j.bp_under ELSE NULL END
        END AS bet_side_price,
        CASE
          WHEN j.kind = 'game' AND j.has_line THEN CASE j.pick_side
            WHEN 'home' THEN j.bm_home WHEN 'away' THEN j.bm_away WHEN 'draw' THEN j.bm_draw
            WHEN 'over' THEN j.bm_over WHEN 'under' THEN j.bm_under ELSE NULL END
          WHEN j.kind = 'game' THEN CASE j.pick_side
            WHEN 'home' THEN j.bs_home WHEN 'away' THEN j.bs_away WHEN 'draw' THEN j.bs_draw
            WHEN 'over' THEN j.bs_over WHEN 'under' THEN j.bs_under ELSE NULL END
          ELSE CASE j.pick_side
            WHEN 'over' THEN j.bp_over WHEN 'under' THEN j.bp_under ELSE NULL END
        END AS moved_side_price,
        CASE
          WHEN j.kind <> 'game' THEN j.bp_line
          WHEN j.game_market LIKE '%totals%' THEN j.bs_total
          WHEN j.game_market LIKE '%spreads%' THEN j.bs_spread
          ELSE NULL
        END AS bet_line,
        CASE
          WHEN j.kind <> 'game' THEN j.bp_line
          WHEN j.has_line AND j.game_market LIKE '%totals%' THEN j.bm_total
          WHEN j.has_line AND j.game_market LIKE '%spreads%' THEN j.bm_spread
          ELSE NULL
        END AS moved_line,
        CASE
          WHEN j.kind = 'game' THEN
            j.bs_home IS NOT NULL OR j.bs_away IS NOT NULL OR j.bs_draw IS NOT NULL
            OR j.bs_over IS NOT NULL OR j.bs_under IS NOT NULL
            OR j.bs_spread IS NOT NULL OR j.bs_total IS NOT NULL
          ELSE j.bp_over IS NOT NULL OR j.bp_under IS NOT NULL OR j.bp_line IS NOT NULL
        END AS bet_snap,
        CASE
          WHEN j.kind = 'game' AND j.has_line THEN
            j.bm_home IS NOT NULL OR j.bm_away IS NOT NULL OR j.bm_spread IS NOT NULL
            OR j.bm_total IS NOT NULL OR j.bm_over IS NOT NULL OR j.bm_under IS NOT NULL
          ELSE FALSE
        END AS moved_snap,
        CASE
          WHEN j.kind = 'game' THEN CASE j.pick_side
            WHEN 'home' THEN j.ps_home WHEN 'away' THEN j.ps_away WHEN 'draw' THEN j.ps_draw
            WHEN 'over' THEN j.ps_over WHEN 'under' THEN j.ps_under ELSE NULL END
          ELSE CASE j.pick_side
            WHEN 'over' THEN j.pp_over WHEN 'under' THEN j.pp_under ELSE NULL END
        END AS pin_side_price,
        CASE
          WHEN j.kind <> 'game' THEN j.pp_line
          WHEN j.game_market LIKE '%totals%' THEN j.ps_total
          WHEN j.game_market LIKE '%spreads%' THEN j.ps_spread
          ELSE NULL
        END AS pin_line,
        CASE WHEN j.kind = 'game' THEN j.ps_over ELSE j.pp_over END AS pin_over,
        CASE WHEN j.kind = 'game' THEN j.ps_under ELSE j.pp_under END AS pin_under,
        j.ps_home AS pin_home,
        j.ps_away AS pin_away,
        j.ps_draw AS pin_draw,
        CASE
          WHEN j.kind = 'game' THEN
            j.ps_home IS NOT NULL OR j.ps_away IS NOT NULL OR j.ps_draw IS NOT NULL
            OR j.ps_over IS NOT NULL OR j.ps_under IS NOT NULL
            OR j.ps_spread IS NOT NULL OR j.ps_total IS NOT NULL
          ELSE j.pp_over IS NOT NULL OR j.pp_under IS NOT NULL OR j.pp_line IS NOT NULL
        END AS pin_snap
      FROM joined j
    ),
    calc AS (
      SELECT
        q.*,
        (
          (q.moved_line IS NOT NULL AND q.scored_line IS NOT NULL
           AND abs(q.moved_line::double precision - q.scored_line::double precision) > 1e-9)
          OR (q.bet_line IS NOT NULL AND q.scored_line IS NOT NULL
           AND abs(q.bet_line::double precision - q.scored_line::double precision) > 1e-9)
        ) AS line_moved,
        (
          q.pin_line IS NOT NULL AND q.scored_line IS NOT NULL
          AND abs(q.pin_line::double precision - q.scored_line::double precision) > 1e-9
        ) AS pin_moved
      FROM priced q
    )
    SELECT
      c.pick_id,
      c.bet_book,
      c.old_method,
      c.commence_ts,
      c.bet_price,
      c.pick_side,
      c.line_moved,
      c.pin_moved,
      c.bet_snap,
      c.moved_snap,
      c.pin_snap,
      c.kind,
      c.has_line,
      CASE WHEN c.line_moved THEN c.moved_side_price ELSE c.bet_side_price END AS closing_odds,
      CASE
        WHEN NOT c.line_moved THEN c.bet_line
        ELSE c.moved_line
      END AS closing_line,
      NULL::numeric AS clv_pct,
      NULL::numeric AS clv_pp,
      NULL::numeric AS market_pct,
      NULL::numeric AS market_pp,
      NULL::text AS market_method,
      CASE
        WHEN c.bet_book IS NOT NULL AND (
          (NOT c.line_moved AND c.bet_snap)
          OR (c.kind <> 'game' AND c.bet_snap)
          OR (c.kind = 'game' AND c.has_line AND (c.moved_snap OR c.bet_snap))
          OR (c.kind = 'game' AND NOT c.has_line AND c.bet_snap)
        ) THEN c.bet_book
        ELSE NULL
      END AS close_book,
      CASE
        WHEN c.scored_line IS NULL OR (
          CASE WHEN c.line_moved THEN c.moved_line ELSE c.bet_line END
        ) IS NULL THEN NULL
        WHEN c.kind <> 'game' OR c.game_market LIKE '%totals%' THEN
          CASE c.pick_side
            WHEN 'over' THEN round((
              (CASE WHEN c.line_moved THEN c.moved_line ELSE c.bet_line END) - c.scored_line
            )::numeric, 2)
            WHEN 'under' THEN round((
              c.scored_line - (CASE WHEN c.line_moved THEN c.moved_line ELSE c.bet_line END)
            )::numeric, 2)
            ELSE NULL
          END
        WHEN c.game_market LIKE '%spreads%' THEN
          CASE c.pick_side
            WHEN 'home' THEN round((
              c.scored_line - (CASE WHEN c.line_moved THEN c.moved_line ELSE c.bet_line END)
            )::numeric, 2)
            WHEN 'away' THEN round((
              (CASE WHEN c.line_moved THEN c.moved_line ELSE c.bet_line END) - c.scored_line
            )::numeric, 2)
            ELSE NULL
          END
        ELSE NULL
      END AS line_pts,
      c.pin_side_price,
      c.pin_over,
      c.pin_under,
      c.pin_home,
      c.pin_away,
      c.pin_draw
    FROM calc c;

    UPDATE _clv_out o
       SET clv_pct = s.pct,
           clv_pp = s.pp
      FROM (
        SELECT o2.pick_id, x.pct, x.pp
        FROM _clv_out o2
        CROSS JOIN LATERAL public.clv_same_book(
          o2.bet_price,
          CASE WHEN o2.line_moved THEN NULL ELSE o2.closing_odds::double precision END
        ) x
      ) s
     WHERE o.pick_id = s.pick_id;

    UPDATE _clv_out o
       SET market_pct = m.pct,
           market_pp = m.pp,
           market_method = m.method
      FROM (
        SELECT o2.pick_id, x.pct, x.pp, x.method
        FROM _clv_out o2
        CROSS JOIN LATERAL public.clv_market_edge(
          o2.bet_price,
          o2.pin_side_price::double precision,
          CASE o2.pick_side
            WHEN 'over' THEN ARRAY[o2.pin_under::double precision]
            WHEN 'under' THEN ARRAY[o2.pin_over::double precision]
            WHEN 'home' THEN
              CASE WHEN o2.pin_draw IS NULL THEN ARRAY[o2.pin_away::double precision]
                   ELSE ARRAY[o2.pin_away::double precision, o2.pin_draw::double precision] END
            WHEN 'away' THEN
              CASE WHEN o2.pin_draw IS NULL THEN ARRAY[o2.pin_home::double precision]
                   ELSE ARRAY[o2.pin_home::double precision, o2.pin_draw::double precision] END
            WHEN 'draw' THEN ARRAY[o2.pin_home::double precision, o2.pin_away::double precision]
            ELSE ARRAY[]::double precision[]
          END,
          'pinnacle'
        ) x
        WHERE o2.pin_snap
          AND NOT o2.pin_moved
          AND o2.pin_side_price IS NOT NULL
      ) m
     WHERE o.pick_id = m.pick_id;

    IF EXISTS (
      SELECT 1 FROM public.picks
      WHERE pick_id = 3114189 AND clv_method IS DISTINCT FROM 'standard_v2'
    ) THEN
      SELECT to_jsonb(o) INTO pin FROM _clv_out o WHERE o.pick_id = 3114189;
      IF pin IS NULL
         OR (pin->>'clv_pct')::numeric IS DISTINCT FROM 8.50
         OR (pin->>'clv_pp')::numeric IS DISTINCT FROM 4.64
         OR (pin->>'market_pct')::numeric IS DISTINCT FROM 1.51
         OR (pin->>'market_pp')::numeric IS DISTINCT FROM 0.82
         OR pin->>'market_method' IS DISTINCT FROM 'power'
         OR (pin->>'closing_odds')::numeric IS DISTINCT FROM -145
         OR (pin->>'pin_side_price')::numeric IS DISTINCT FROM -142
         OR pin->>'bet_book' IS DISTINCT FROM 'draftkings'
      THEN
        RAISE EXCEPTION 'CLV pin 3114189 failed: %', pin;
      END IF;
    END IF;

    IF EXISTS (
      SELECT 1 FROM public.picks
      WHERE pick_id = 2387645 AND clv_method IS DISTINCT FROM 'standard_v2'
    ) THEN
      SELECT to_jsonb(o) INTO pin FROM _clv_out o WHERE o.pick_id = 2387645;
      IF pin IS NULL
         OR (pin->>'clv_pct')::numeric IS DISTINCT FROM 0.33
         OR (pin->>'clv_pp')::numeric IS DISTINCT FROM 0.18
         OR (pin->>'market_pct')::numeric IS DISTINCT FROM -4.47
         OR (pin->>'market_pp')::numeric IS DISTINCT FROM -2.54
         OR pin->>'market_method' IS DISTINCT FROM 'power'
         OR (pin->>'closing_odds')::numeric IS DISTINCT FROM -133
         OR (pin->>'pin_side_price')::numeric IS DISTINCT FROM -125
         OR pin->>'bet_book' IS DISTINCT FROM 'rebet'
      THEN
        RAISE EXCEPTION 'CLV pin 2387645 failed: %', pin;
      END IF;
    END IF;

    IF EXISTS (
      SELECT 1 FROM public.picks
      WHERE pick_id = 3114194 AND clv_method IS DISTINCT FROM 'standard_v2'
    ) THEN
      SELECT to_jsonb(o) INTO pin FROM _clv_out o WHERE o.pick_id = 3114194;
      IF pin IS NULL
         OR (pin->>'clv_pct')::numeric IS DISTINCT FROM 0.00
         OR (pin->>'clv_pp')::numeric IS DISTINCT FROM 0.00
         OR (pin->>'market_pct')::numeric IS DISTINCT FROM -5.21
         OR (pin->>'market_pp')::numeric IS DISTINCT FROM -3.21
         OR pin->>'market_method' IS DISTINCT FROM 'power'
         OR (pin->>'closing_odds')::numeric IS DISTINCT FROM -160
         OR (pin->>'pin_side_price')::numeric IS DISTINCT FROM -160
         OR pin->>'bet_book' IS DISTINCT FROM 'draftkings'
      THEN
        RAISE EXCEPTION 'CLV pin 3114194 failed: %', pin;
      END IF;
    END IF;

    UPDATE public.picks p
       SET closing_dk_odds = o.closing_odds,
           closing_line = o.closing_line,
           clv_pct = o.clv_pct,
           clv_pp = o.clv_pp,
           line_clv_pts = o.line_pts,
           clv_beat_close = CASE
             WHEN o.clv_pct IS NULL THEN NULL
             WHEN o.clv_pct > 0 THEN TRUE
             ELSE FALSE
           END,
           clv_captured_at = to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
           clv_method = 'standard_v2',
           clv_close_book = o.close_book,
           clv_bet_book = o.bet_book,
           market_clv_pct = o.market_pct,
           market_clv_pp = o.market_pp,
           market_clv_method = o.market_method,
           pinnacle_close_odds = CASE WHEN o.pin_moved THEN NULL ELSE o.pin_side_price END
      FROM _clv_out o
     WHERE p.pick_id = o.pick_id
       AND (o.clv_pct IS NOT NULL OR o.line_pts IS NOT NULL OR o.market_pct IS NOT NULL);
    GET DIAGNOSTICS n_full = ROW_COUNT;

    UPDATE public.picks p
       SET closing_dk_odds = NULL,
           closing_line = NULL,
           clv_pct = NULL,
           clv_pp = NULL,
           line_clv_pts = NULL,
           clv_beat_close = NULL,
           clv_method = 'standard_v2',
           clv_close_book = NULL,
           clv_bet_book = o.bet_book,
           market_clv_pct = NULL,
           market_clv_pp = NULL,
           market_clv_method = NULL,
           pinnacle_close_odds = NULL
      FROM _clv_out o
     WHERE p.pick_id = o.pick_id
       AND o.clv_pct IS NULL
       AND o.line_pts IS NULL
       AND o.market_pct IS NULL
       AND (
         o.old_method IS NOT NULL
         OR o.commence_ts < now() - interval '6 hours'
       );
    GET DIAGNOSTICS n_empty = ROW_COUNT;

    RAISE NOTICE 'clv standard_v2 wrote % rows, cleared %', n_full, n_empty;
  END IF;

  def := pg_get_viewdef('public.v_public_track_record'::regclass, true);
  IF position('clv_game_settled' IN def) = 0 THEN
    IF position(old_tok IN def) = 0 THEN
      RAISE EXCEPTION 'v_public_track_record is missing the no_vig CLV filter and the new columns';
    END IF;
    new_def := replace(def, old_tok, new_tok);
    extra := ',
    count(*) FILTER (WHERE (result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AND clv_pct IS NOT NULL AND clv_method = ''standard_v2''::text AND prop_market IS NULL AND model_id !~~ ''%prop%''::text) AS clv_game_settled,
    count(*) FILTER (WHERE (result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AND clv_pct > 0::numeric AND clv_method = ''standard_v2''::text AND prop_market IS NULL AND model_id !~~ ''%prop%''::text) AS clv_game_beat,
    avg(clv_pct) FILTER (WHERE (result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AND clv_pct IS NOT NULL AND clv_method = ''standard_v2''::text AND prop_market IS NULL AND model_id !~~ ''%prop%''::text) AS avg_clv_game_pct,
    count(*) FILTER (WHERE (result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AND clv_pct IS NOT NULL AND clv_method = ''standard_v2''::text AND (prop_market IS NOT NULL OR model_id ~~ ''%prop%''::text)) AS clv_prop_settled,
    count(*) FILTER (WHERE (result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AND clv_pct > 0::numeric AND clv_method = ''standard_v2''::text AND (prop_market IS NOT NULL OR model_id ~~ ''%prop%''::text)) AS clv_prop_beat,
    avg(clv_pct) FILTER (WHERE (result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AND clv_pct IS NOT NULL AND clv_method = ''standard_v2''::text AND (prop_market IS NOT NULL OR model_id ~~ ''%prop%''::text)) AS avg_clv_prop_pct,
    count(*) FILTER (WHERE (result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AND market_clv_pct IS NOT NULL AND clv_method = ''standard_v2''::text) AS market_clv_settled,
    count(*) FILTER (WHERE (result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AND market_clv_pct > 0::numeric AND clv_method = ''standard_v2''::text) AS market_clv_beat,
    avg(market_clv_pct) FILTER (WHERE (result = ANY (ARRAY[''WIN''::text, ''LOSS''::text, ''PUSH''::text])) AND market_clv_pct IS NOT NULL AND clv_method = ''standard_v2''::text) AS avg_market_clv_pct';
    IF position('AS last_date' IN new_def) = 0 THEN
      RAISE EXCEPTION 'v_public_track_record has no last_date column to extend';
    END IF;
    new_def := replace(new_def, 'AS last_date', 'AS last_date' || extra);
    EXECUTE 'CREATE OR REPLACE VIEW public.v_public_track_record AS ' || new_def;
  END IF;
END
$mig$;
