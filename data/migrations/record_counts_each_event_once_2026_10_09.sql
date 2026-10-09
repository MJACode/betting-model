-- record_counts_each_event_once (2026-10-09, mike)
--
-- WHY. mike, 2026-10-09: "Count each fight once." Two UFC fights are in the
-- settled record twice. Each was scored under two games rows for one fight,
-- so ufc_total_rounds wrote the same bet twice and both copies settled WIN:
--
--   kept 332605  UFC_2026-06-20_kevin-borjas_andre-lima   Over 2.5 at -166, WIN
--   mark 332615  UFC_2026-06-20_andre-lima_kevin-borjas   Over 2.5 at -130, WIN
--                (the fighters swapped; written in the same run, same second)
--
--   kept 524487  UFC_2026-07-18_kamaru-usman_dricus-du-plessis  Over 2.5, WIN
--   mark 530849  UFC_2026-07-19_kamaru-usman_dricus-du-plessis  Over 2.5, WIN
--                (an Eastern and a UTC date for one main event; both unpriced)
--
-- Measured read-only the same day over every BET ever written: these are the
-- only two unmarked pairs (tracking/record_duplicates.DUPLICATE_PAIRS_SQL).
-- Both are before the published window (2026-09-01), so the app, the public
-- views and the Discord recaps show the same numbers before and after this;
-- the monitor dashboard and any all-time count of ufc_total_rounds move from
-- 14 settled 9-5 (-1.09u, 8 priced) to 12 settled 7-5 (-1.86u, 7 priced).
--
-- WHAT CHANGES. The extra copy gets condition_status = 'DUPLICATE' and a note
-- naming the copy kept and who asked. NOTHING ELSE: result, profit_flat, the
-- line, the price, created_at and settled_at stay as written, and the kept
-- copy is not touched. Every record query excludes the marker
-- (config.duplicate_copy_exclusion_sql; the app's passesRecordFilter).
-- picks_audit_trigger logs the UPDATE.
--
-- WHICH COPY STAYS (tracking/record_duplicates.choose_kept): a Discord-posted
-- copy first (neither was posted), then the earliest created_at (decides the
-- July pair: 07-12 against 07-19), then the lowest pick_id (decides the June
-- pair, which share a created_at to the microsecond).
--
-- GUARD. Each UPDATE names the pick, its model and game id, needs it still
-- settled and unmarked, and needs the kept copy settled and unmarked. A second
-- pass changes nothing.
--
-- ROLLBACK: UPDATE picks SET condition_status = NULL, condition_note = NULL
--           WHERE pick_id IN (332615, 530849) AND condition_status = 'DUPLICATE';

DO $mig$
DECLARE
  n     integer;
  total integer := 0;
BEGIN
  UPDATE public.picks x
     SET condition_status = 'DUPLICATE',
         condition_note   = 'Same fight as pick 332605 under a second game id '
                         || '(fighters swapped). Counted once in the record; '
                         || 'result unchanged. mike, 2026-10-09.'
   WHERE x.pick_id = 332615
     AND x.model_id = 'ufc_total_rounds'
     AND x.game_id = 'UFC_2026-06-20_andre-lima_kevin-borjas'
     AND x.signal_type = 'BET'
     AND x.result IN ('WIN', 'LOSS', 'PUSH')
     AND x.condition_status IS NULL
     AND EXISTS (SELECT 1 FROM public.picks k
                  WHERE k.pick_id = 332605
                    AND k.model_id = x.model_id
                    AND k.game_id = 'UFC_2026-06-20_kevin-borjas_andre-lima'
                    AND k.signal_type = 'BET'
                    AND k.result IN ('WIN', 'LOSS', 'PUSH')
                    AND k.condition_status IS NULL);
  GET DIAGNOSTICS n = ROW_COUNT;
  total := total + n;

  UPDATE public.picks x
     SET condition_status = 'DUPLICATE',
         condition_note   = 'Same fight as pick 524487 under a second game id '
                         || '(UTC date). Counted once in the record; '
                         || 'result unchanged. mike, 2026-10-09.'
   WHERE x.pick_id = 530849
     AND x.model_id = 'ufc_total_rounds'
     AND x.game_id = 'UFC_2026-07-19_kamaru-usman_dricus-du-plessis'
     AND x.signal_type = 'BET'
     AND x.result IN ('WIN', 'LOSS', 'PUSH')
     AND x.condition_status IS NULL
     AND EXISTS (SELECT 1 FROM public.picks k
                  WHERE k.pick_id = 524487
                    AND k.model_id = x.model_id
                    AND k.game_id = 'UFC_2026-07-18_kamaru-usman_dricus-du-plessis'
                    AND k.signal_type = 'BET'
                    AND k.result IN ('WIN', 'LOSS', 'PUSH')
                    AND k.condition_status IS NULL);
  GET DIAGNOSTICS n = ROW_COUNT;
  total := total + n;

  IF total > 0 THEN
    RAISE NOTICE 'record_counts_each_event_once: % extra copy row(s) marked DUPLICATE', total;
  END IF;
END $mig$;
