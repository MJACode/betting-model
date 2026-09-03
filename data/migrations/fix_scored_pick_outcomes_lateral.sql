-- fix_scored_pick_outcomes_lateral (2026-09-03, mike)
--
-- WHY. mv_scored_pick_outcomes graded player props through a LATERAL that ended
-- `... WHERE l.game_id = p.game_id AND l.player_id = p.player_id LIMIT 1`.
-- player_game_log carries a BATTING row and a PITCHING row for the same
-- (game_id, player_id) whenever a pitcher also bats: 481,240 rows for 460,877
-- distinct pairs, 20,363 surplus, and every one of those pairs is exactly one
-- batting row plus one pitching row (verified — zero pairs have two of either).
-- `LIMIT 1` with no ORDER BY takes an ARBITRARY row, so a pitcher prop that
-- landed on the batting row read a NULL mapped column, graded 'U', and was
-- dropped by the closing `WHERE b.res IN ('W','L','P')`.
--
-- It never mis-graded: no row carries both batting and pitching stats, so the
-- CASE cannot read a pitcher prop off batting data. The defect is that WHICH
-- picks survive was nondeterministic — a REFRESH could reshuffle it, and the
-- published record was therefore not reproducible. Six settled BETs are
-- currently dropped this way (-0.76u).
--
-- THE FIX. Aggregate instead of limiting: max() over the matching rows returns
-- the one non-NULL value, is identical when there is a single row, and an
-- ungrouped aggregate still returns exactly one row, so `LEFT JOIN LATERAL
-- ... ON true` keeps its one-row-per-pick semantics. Applied to the WNBA
-- lateral too — wnba_player_game_log has no duplicates today (34,632 rows,
-- 34,632 distinct pairs), but leaving one lane unguarded is how this repo
-- accumulates work (CLAUDE.md §1b).
--
-- WHAT THIS SCRIPT DOES. A matview cannot be CREATE OR REPLACE'd, and two
-- views depend on it, so both are dropped and recreated verbatim from their
-- live definitions. Grants are reapplied deliberately:
--   * mv_scored_pick_outcomes keeps REVOKE ALL + GRANT SELECT, exactly as
--     materialize_scored_pick_outcomes.sql documents.
--   * the two views are TIGHTENED. Both currently sit at anon=arwdDxtm /
--     authenticated=arwdDxtm — the full default-privilege grant Supabase hands
--     out on new objects in public, and precisely the hole CLAUDE.md §7 says to
--     close by REVOKING from anon and authenticated BY NAME. They only ever
--     need SELECT.
--
-- Idempotent and transactional: re-running is a no-op beyond a rebuild.

BEGIN;

DROP VIEW IF EXISTS public.v_public_track_record_daily;
DROP VIEW IF EXISTS public.v_model_full_outcome_record;
DROP MATERIALIZED VIEW IF EXISTS public.mv_scored_pick_outcomes;

CREATE MATERIALIZED VIEW public.mv_scored_pick_outcomes AS
WITH base AS (
  SELECT
    p.pick_id, p.model_id, p.sport, p.game_date, p.game_time, p.game_id,
    p.pick_label, p.pick_side, p.signal_type, p.confidence_tier,
    p.model_probability, p.edge, p.dk_odds, p.scored_line,
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
    -- Honest-era gate, same as the record views (pre-07-05 O/U probs are
    -- NaN-total_line tainted).
    AND NOT (p.model_id = 'mlb_over_under' AND p.game_date < '2026-07-05')
    AND p.is_live IS NOT TRUE
    AND (p.model_id IN ('mlb_moneyline','mlb_over_under','mlb_runline','mlb_f5_moneyline','wnba_moneyline')
         OR p.model_id LIKE 'mlb_prop_%' OR p.model_id LIKE 'wnba_prop_%')
)
SELECT
  b.pick_id, b.model_id, b.sport, b.game_date, b.game_time, b.game_id,
  b.pick_label, b.pick_side, b.signal_type, b.confidence_tier,
  b.model_probability, b.edge, b.dk_odds, b.scored_line,
  b.public_bet_pct, b.injury_flag, b.player_id,
  CASE WHEN b.model_id LIKE '%\_prop\_%' THEN 'prop' ELSE 'game' END AS bet_kind,
  CASE WHEN b.dk_odds IS NULL THEN NULL
       WHEN b.dk_odds < 0 THEN 'fav' ELSE 'dog' END AS price_side,
  CASE
    WHEN b.et_hour IS NULL THEN NULL
    WHEN b.et_hour >= 22 OR b.et_hour < 5 THEN 'late'
    WHEN b.et_hour < 16 THEN 'day'
    WHEN b.et_hour < 19 THEN 'early'
    ELSE 'prime'
  END AS time_slot,
  CASE b.res WHEN 'W' THEN 'WIN' WHEN 'L' THEN 'LOSS' ELSE 'PUSH' END AS result,
  CASE
    WHEN b.dk_odds IS NULL THEN NULL
    WHEN b.res = 'W' THEN CASE WHEN b.dk_odds > 0 THEN b.dk_odds/100.0 ELSE 100.0/abs(b.dk_odds) END
    WHEN b.res = 'L' THEN -1
    ELSE 0
  END AS profit_units
FROM base b
WHERE b.res IN ('W','L','P');

-- Unique index is required for REFRESH ... CONCURRENTLY (no read downtime).
CREATE UNIQUE INDEX mv_scored_pick_outcomes_pick_id_idx
  ON public.mv_scored_pick_outcomes (pick_id);
-- Every custom-model query filters by model_id first.
CREATE INDEX mv_scored_pick_outcomes_model_idx
  ON public.mv_scored_pick_outcomes (model_id, model_probability, edge);

REVOKE ALL ON public.mv_scored_pick_outcomes FROM anon, authenticated;
GRANT SELECT ON public.mv_scored_pick_outcomes TO anon, authenticated;

-- ── dependent views, recreated verbatim from their live definitions ─────────

CREATE VIEW public.v_model_full_outcome_record AS
 WITH graded AS (
         SELECT o.model_id,
                CASE o.result
                    WHEN 'WIN'::text THEN 'W'::text
                    WHEN 'LOSS'::text THEN 'L'::text
                    ELSE 'P'::text
                END AS res,
            o.dk_odds,
            m.paused,
            m.prob_only,
            o.profit_units AS profit,
            ((o.model_probability >= m.min_prob) AND (m.prob_only OR (o.edge >= COALESCE(m.min_edge, (0)::numeric))) AND ((m.min_odds IS NULL) OR (o.dk_odds IS NULL) OR (o.dk_odds >= m.min_odds))) AS passes
           FROM (mv_scored_pick_outcomes o
             JOIN model_action_thresholds m ON ((m.model_id = o.model_id)))
        )
 SELECT model_id,
    bool_or(paused) AS paused,
    bool_or(prob_only) AS prob_only,
    count(*) FILTER (WHERE (passes AND (res = ANY (ARRAY['W'::text, 'L'::text, 'P'::text])))) AS bets,
    count(*) FILTER (WHERE (passes AND (res = 'W'::text))) AS wins,
    count(*) FILTER (WHERE (passes AND (res = 'L'::text))) AS losses,
    count(*) FILTER (WHERE (passes AND (res = 'P'::text))) AS pushes,
    count(*) FILTER (WHERE (passes AND (res = ANY (ARRAY['W'::text, 'L'::text, 'P'::text])) AND (dk_odds IS NOT NULL))) AS priced_bets,
        CASE
            WHEN (model_id = 'mlb_prop_batter_hr'::text) THEN (0)::numeric
            ELSE round(COALESCE(sum(profit) FILTER (WHERE passes), (0)::numeric), 6)
        END AS units,
        CASE
            WHEN (model_id = 'mlb_prop_batter_hr'::text) THEN NULL::numeric
            ELSE round(((sum(profit) FILTER (WHERE passes) / (NULLIF(count(*) FILTER (WHERE (passes AND (res = ANY (ARRAY['W'::text, 'L'::text, 'P'::text])) AND (dk_odds IS NOT NULL))), 0))::numeric) * (100)::numeric), 1)
        END AS roi_pct
   FROM graded
  GROUP BY model_id;

REVOKE ALL ON public.v_model_full_outcome_record FROM anon, authenticated;
GRANT SELECT ON public.v_model_full_outcome_record TO anon, authenticated;

CREATE VIEW public.v_public_track_record_daily AS
 WITH fo_base AS (
         SELECT o.game_date,
            o.dk_odds,
                CASE
                    WHEN (o.model_id ~~ 'wnba%'::text) THEN 'WNBA'::text
                    ELSE 'MLB'::text
                END AS sport,
            ((o.model_probability >= t.min_prob) AND (t.prob_only OR (o.edge >= COALESCE(t.min_edge, (0)::numeric))) AND ((t.min_odds IS NULL) OR (o.dk_odds IS NULL) OR (o.dk_odds >= t.min_odds))) AS passes,
                CASE o.result
                    WHEN 'WIN'::text THEN 'W'::text
                    WHEN 'LOSS'::text THEN 'L'::text
                    ELSE 'P'::text
                END AS res,
            o.profit_units
           FROM (mv_scored_pick_outcomes o
             JOIN model_action_thresholds t ON ((t.model_id = o.model_id)))
          WHERE ((t.paused IS NOT TRUE) AND (o.model_id <> 'mlb_prop_batter_hr'::text))
        ), fo AS (
         SELECT fo_base.game_date,
            fo_base.sport,
            count(*) FILTER (WHERE (fo_base.passes AND (fo_base.res = ANY (ARRAY['W'::text, 'L'::text, 'P'::text])))) AS picks,
            count(*) FILTER (WHERE (fo_base.passes AND (fo_base.res = 'W'::text))) AS wins,
            count(*) FILTER (WHERE (fo_base.passes AND (fo_base.res = 'L'::text))) AS losses,
            count(*) FILTER (WHERE (fo_base.passes AND (fo_base.res = 'P'::text))) AS pushes,
            (COALESCE(sum(fo_base.profit_units) FILTER (WHERE (fo_base.passes AND (fo_base.dk_odds IS NOT NULL))), (0)::numeric) * (100)::numeric) AS profit_flat,
            (100 * count(*) FILTER (WHERE (fo_base.passes AND (fo_base.res = ANY (ARRAY['W'::text, 'L'::text, 'P'::text])) AND (fo_base.dk_odds IS NOT NULL)))) AS staked_flat
           FROM fo_base
          GROUP BY fo_base.game_date, fo_base.sport
        ), other AS (
         SELECT p.game_date,
            p.sport,
            count(*) FILTER (WHERE (p.result = ANY (ARRAY['WIN'::text, 'LOSS'::text, 'PUSH'::text]))) AS picks,
            count(*) FILTER (WHERE (p.result = 'WIN'::text)) AS wins,
            count(*) FILTER (WHERE (p.result = 'LOSS'::text)) AS losses,
            count(*) FILTER (WHERE (p.result = 'PUSH'::text)) AS pushes,
            COALESCE(sum(p.profit_flat) FILTER (WHERE ((p.result = ANY (ARRAY['WIN'::text, 'LOSS'::text, 'PUSH'::text])) AND (p.dk_odds IS NOT NULL))), (0)::numeric) AS profit_flat,
            (100 * count(*) FILTER (WHERE ((p.result = ANY (ARRAY['WIN'::text, 'LOSS'::text, 'PUSH'::text])) AND (p.dk_odds IS NOT NULL)))) AS staked_flat
           FROM (picks p
             JOIN model_action_thresholds t ON ((t.model_id = p.model_id)))
          WHERE ((p.signal_type = 'BET'::text) AND ((p.is_live IS NOT TRUE) OR (p.model_id ~~ '%\_live\_%'::text)) AND (t.paused IS NOT TRUE) AND (p.game_date >= '2026-04-14'::text) AND (NOT ((p.model_id = 'mlb_over_under'::text) AND (p.game_date < '2026-07-05'::text))) AND (p.model_probability >= t.min_prob) AND (t.prob_only OR (p.edge >= t.min_edge)) AND ((t.min_odds IS NULL) OR (p.dk_odds IS NULL) OR (p.dk_odds >= t.min_odds)) AND (NOT ((p.model_id = ANY (ARRAY['mlb_moneyline'::text, 'mlb_over_under'::text, 'mlb_runline'::text, 'mlb_f5_moneyline'::text, 'wnba_moneyline'::text])) OR (p.model_id ~~ 'mlb_prop_%'::text) OR (p.model_id ~~ 'wnba_prop_%'::text))))
          GROUP BY p.game_date, p.sport
        )
 SELECT fo.game_date, fo.sport, fo.picks, fo.wins, fo.losses, fo.pushes,
    fo.profit_flat, fo.staked_flat
   FROM fo
  WHERE (fo.picks > 0)
UNION ALL
 SELECT other.game_date, other.sport, other.picks, other.wins, other.losses,
    other.pushes, other.profit_flat, other.staked_flat
   FROM other;

REVOKE ALL ON public.v_public_track_record_daily FROM anon, authenticated;
GRANT SELECT ON public.v_public_track_record_daily TO anon, authenticated;

COMMIT;
