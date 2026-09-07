-- promotions_endorsed_only_2026_09_07 (2026-09-07, mike)
--
-- ONE-OFF. Puts `model_calibration`'s promoted slot into the state the decision
-- path can now actually read, on the day that path reached player props.
--
-- WHY IT IS NEEDED AT ALL
--
-- `DECIDE_ON_CALIBRATED_PROB` shipped 2026-08-31 in `classify_edge`. Every model
-- carrying a promoted map is a player PROP, and props are built in
-- `_make_prop_pick`, which had no calibration branch — so for six days the flag
-- was on, a test asserted it was on, and it changed nothing anywhere. Wiring it
-- in (same commit) makes ten promoted maps live for the first time, so what is
-- promoted has to be correct BEFORE that lands rather than after.
--
-- Two corrections, both measured 2026-09-07 against the fits of that morning:
--
-- 1. A PROMOTED MAP MUST CARRY ITS OWN METHOD. `load_calibrations` read
--    `promoted_a`/`promoted_b` while filtering on `method` — the CANDIDATE's,
--    rewritten nightly. A refit that could not fit a model wrote `method=NULL`
--    and the promoted map vanished on the next read, silently:
--
--        mlb_prop_pitcher_k + mlb_prop_pitcher_hits, picks carrying a
--        calibrated number DIFFERENT from the raw one:
--            2026-08-31..09-03   166 of 166
--            2026-09-04           11 of  43
--            2026-09-05..09-07     0 of  95   <- three days, no calibration
--
--    The code fix reads `promoted_method`; this backfills it.
--
-- 2. PROMOTION NOW NEEDS helps AND transfers, NOT `applied` (= helps alone).
--    `helps` says the map beats the raw number out of sample; `transfers` says
--    it closes the gap. mlb_prop_pitcher_er helps (11.9pp -> 6.8pp) and does not
--    close, and its own fit note says "publish it; do not build a threshold on
--    it yet" — a display number, not a decision number.
--
-- SCOPE: the ten rows promoted today, plus two NEW promotions. Deliberately NOT
-- a rule that re-derives promotion from the latest fit — that is the cron-driven
-- model update this whole change exists to stop.
--
-- 3. TWO NEW PROMOTIONS, AND ONE REFUSAL, ON THE SAME TEST. Three models are
--    endorsed today (helps AND transfers) and were never promoted. The question
--    that separates them is NOT "is the map good" — all three pass — it is
--    "which scale was this model's CUT swept on":
--
--      wnba_prop_player_assists  cut 0.50/0.10, "on the floor-corrected
--                                CALIBRATED sweep" (config.py:269)   -> PROMOTE
--      wnba_prop_player_pra      cut 0.68/0.16, "calibrated sweep +
--                                time split" (config.py:271)          -> PROMOTE
--      mlb_prop_pitcher_walks    cut 0.60/0.08, "2026-06-21 FULL-OUTCOME"
--                                — swept on RAW probabilities         -> NO
--
--    The first two are the MLB prop bug exactly: a cut chosen on calibrated
--    numbers, applied to raw ones. Promoting closes that. The third would OPEN
--    it in reverse — a calibrated decision against a cut nobody swept on that
--    scale — which is the trap documented for mlb_live_total_runs, where the
--    measured map takes a claimed 0.74 to 0.598 against a raw-swept 0.70 floor.
--    pitcher_walks is paused, so this costs nothing today; the reasoning is what
--    matters when it is unpaused.
--
-- WHAT CHANGES, ROW BY ROW (state before, 2026-09-07 13:xx UTC):
--
--   KEPT, re-frozen on today's endorsed fit:
--     mlb_prop_batter_rbi        helps t transfers t   (model RETIRED 09-02, inert)
--     mlb_prop_batter_runs       helps t transfers t   a 1.138253  b 0.376525
--     wnba_prop_player_points    helps t transfers t   a 0.455974  b -0.132804
--     wnba_prop_player_rebounds  helps t transfers t   a 0.720791  b -0.145981
--
--   NEWLY PROMOTED (endorsed, and their cuts were swept on calibrated numbers):
--     wnba_prop_player_assists   helps t transfers t   a 0.841800  b -0.065500
--     wnba_prop_player_pra       helps t transfers t   a 0.570700  b -0.123700
--
--   DEMOTED, no longer endorsed:
--     mlb_prop_batter_tb         helps FALSE           (model paused)
--     mlb_prop_batter_walks      helps FALSE           (model ACTIVE)
--     mlb_prop_pitcher_er        transfers FALSE       (model paused)
--     mlb_prop_pitcher_hits      unfitted, 26/150      (model ACTIVE, already inert)
--     mlb_prop_pitcher_k         unfitted, 47/150      (model ACTIVE, already inert)
--     wnba_prop_player_threes    helps FALSE           (model paused)
--
-- EFFECT ON LIVE DECISIONS. pitcher_k and pitcher_hits were already inert, so
-- demoting them changes nothing today — they stay on raw probabilities until
-- their maps can be refit (they need 150 graded picks since the 09-03/09-05
-- retrains and have 47 and 26). config.PROP_MAX_SIGNALS_PER_DAY holds their
-- volume down in the meantime and comes off when those maps land. The two WNBA
-- maps and batter_runs bite for the first time, which is the intended effect of
-- the wiring fix. batter_walks loses a map it should never have decided on.
--
-- DEPLOY ORDER, AND THE SHORT REGRESSION IN IT. The code fix requires
-- `promoted_method`, which is NULL on every existing row until this runs — so
-- between the code deploy and the next pipeline pass EVERY promoted map is
-- inert. For eight of the ten that is a no-op (they were inert already, or
-- their models are paused or retired), but wnba_prop_player_points and
-- wnba_prop_player_rebounds WERE biting under the old loader and stop biting
-- for that window: those two decide on raw probabilities until this migration
-- lands. It is a few hours at the 6am cadence and it fails in the direction the
-- system has been running in all week, which is why it is acceptable rather
-- than invisible. To close it immediately, run this file by hand before the
-- deploy: it is a single idempotent DO block and takes no arguments.
--
-- GUARD is the PROPERTY this establishes, not the shape of its own output
-- (.claude/rules/data-integrity.md): after this runs, no promoted row has a NULL
-- `promoted_method`, so it can never fire twice.
--
-- ROLLBACK: restore the 2026-08-31 17:05 promoted values and clear the new
-- columns —
--   UPDATE model_calibration SET promoted = TRUE, promoted_method = NULL,
--          promoted_helps = NULL, promoted_transfers = NULL,
--          promoted_a = v.a, promoted_b = v.b
--   FROM (VALUES
--     ('mlb_prop_batter_rbi',       0.758681,  0.466694),
--     ('mlb_prop_batter_runs',      0.773988,  0.110082),
--     ('mlb_prop_batter_tb',        0.562124,  0.079787),
--     ('mlb_prop_batter_walks',     0.836780,  0.061352),
--     ('mlb_prop_pitcher_er',       0.645709, -0.160747),
--     ('mlb_prop_pitcher_hits',     0.506155, -0.321502),
--     ('mlb_prop_pitcher_k',        0.763085, -0.217100),
--     ('wnba_prop_player_points',   0.437564, -0.128927),
--     ('wnba_prop_player_rebounds', 0.747529, -0.156913),
--     ('wnba_prop_player_threes',   0.971577, -0.096230)
--   ) AS v(m, a, b) WHERE model_calibration.model_id = v.m;
--   UPDATE model_calibration SET promoted = FALSE, promoted_a = NULL,
--          promoted_b = NULL, promoted_method = NULL, promoted_helps = NULL,
--          promoted_transfers = NULL
--    WHERE model_id IN ('wnba_prop_player_assists', 'wnba_prop_player_pra');
-- ...and revert models/probability_calibration.py's load_calibrations to filter
-- on `method`. All three parts, or the maps stay inert.
--
-- Updated-By: mike

DO $$
DECLARE
    kept   TEXT[] := ARRAY['mlb_prop_batter_rbi', 'mlb_prop_batter_runs',
                           'wnba_prop_player_points', 'wnba_prop_player_rebounds'];
    -- Endorsed today, never promoted, and carrying a CALIBRATED-swept cut.
    newly  TEXT[] := ARRAY['wnba_prop_player_assists', 'wnba_prop_player_pra'];
    dropped TEXT[] := ARRAY['mlb_prop_batter_tb', 'mlb_prop_batter_walks',
                            'mlb_prop_pitcher_er', 'mlb_prop_pitcher_hits',
                            'mlb_prop_pitcher_k', 'wnba_prop_player_threes'];
    n_kept   INT;
    n_dropped INT;
BEGIN
    IF to_regclass('public.model_calibration') IS NULL THEN
        RAISE NOTICE 'promotions_endorsed_only: no model_calibration table — skipped';
        RETURN;
    END IF;

    -- The columns the decision path now reads. Inside the guard, so this is one
    -- ALTER once rather than a PostgREST cache invalidation on every pass.
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'model_calibration'
                     AND column_name = 'promoted_method') THEN
        ALTER TABLE model_calibration
            ADD COLUMN IF NOT EXISTS promoted_method     TEXT,
            ADD COLUMN IF NOT EXISTS promoted_helps      BOOLEAN,
            ADD COLUMN IF NOT EXISTS promoted_transfers  BOOLEAN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM model_calibration
                   WHERE promoted AND promoted_method IS NULL) THEN
        RAISE NOTICE 'promotions_endorsed_only: already applied — skipped';
        RETURN;
    END IF;

    -- Re-freeze the endorsed four on TODAY's fit. Taking a/b from the candidate
    -- is the point: the promoted values were fitted 2026-08-31, before the
    -- 09-03/09-05 leak-repair retrains, so they map a model that no longer
    -- exists.
    UPDATE model_calibration
       SET promoted_a          = a,
           promoted_b          = b,
           promoted_method     = method,
           promoted_helps      = TRUE,
           promoted_transfers  = TRUE,
           promoted_at         = now()::text
     WHERE model_id = ANY(kept)
       AND method = 'platt' AND a IS NOT NULL AND b IS NOT NULL;
    GET DIAGNOSTICS n_kept = ROW_COUNT;

    -- The two new promotions. `applied` is the fit's own endorsement and the
    -- payload carries both verdicts; requiring transfers here keeps this file
    -- and promote() applying the same bar.
    UPDATE model_calibration
       SET promoted            = TRUE,
           promoted_a          = a,
           promoted_b          = b,
           promoted_method     = method,
           promoted_helps      = TRUE,
           promoted_transfers  = TRUE,
           promoted_at         = now()::text
     WHERE model_id = ANY(newly)
       AND applied
       AND method = 'platt' AND a IS NOT NULL AND b IS NOT NULL
       AND (payload::json->>'helps')::boolean
       AND (payload::json->>'transfers')::boolean;

    -- The named demotions, PLUS any of `kept` whose candidate turned out to be
    -- unfitted. Without that second clause a kept-but-unfittable row stays
    -- promoted with a NULL method, the guard above never becomes false, and this
    -- migration re-runs on every pipeline pass forever.
    UPDATE model_calibration
       SET promoted            = FALSE,
           promoted_a          = NULL,
           promoted_b          = NULL,
           promoted_method     = NULL,
           promoted_helps      = NULL,
           promoted_transfers  = NULL,
           promoted_at         = now()::text
     WHERE model_id = ANY(dropped)
        OR (model_id = ANY(kept) AND promoted AND promoted_method IS NULL);
    GET DIAGNOSTICS n_dropped = ROW_COUNT;

    -- Anything promoted that this migration did not name keeps its map but has
    -- no recorded method, which the new loader treats as inert. Fail LOUD rather
    -- than leaving a map that silently stopped deciding.
    IF EXISTS (SELECT 1 FROM model_calibration
               WHERE promoted AND promoted_method IS NULL) THEN
        RAISE WARNING 'promotions_endorsed_only: promoted rows this migration '
                      'did not name are now inert: %',
            (SELECT string_agg(model_id, ', ') FROM model_calibration
              WHERE promoted AND promoted_method IS NULL);
    END IF;

    RAISE NOTICE 'promotions_endorsed_only: % re-promoted, % demoted',
                 n_kept, n_dropped;
END $$;
