-- mlb_phantom_utc_rows_2026_09_07 (2026-09-07, mike)
--
-- ONE-OFF. Three MLB games rows are not games. Each is the previous night's
-- West Coast game filed a second time under its UTC date with no start time,
-- written by a pull on 2026-04-15/16 that processed the event list three
-- times with two dating conventions (docs/sessions/2026-09.md, session 253):
--
--     MLB_2026-04-16_NYM_LAD   is  MLB_2026-04-15_NYM_LAD  (LAD 8-2, 02:11Z on the 16th)
--     MLB_2026-04-17_SEA_SD    is  MLB_2026-04-16_SEA_SD   (SD 5-2,  00:41Z on the 17th)
--     MLB_2026-04-17_COL_HOU   is  MLB_2026-04-16_COL_HOU  (COL 3-2, 00:11Z on the 17th)
--
-- They are NOT deleted and NOT scored. Five picks point at the first two
-- (one voided BET, four AVOIDs voided by the declared job that ships with
-- this file); CLAUDE.md 1c keeps a wrongly produced pick as evidence, and the
-- row it points at with it. A final is not mirrored onto them either: every
-- one of those picks was written the morning after its game had been played,
-- and a scored row would let the graded-universe view count an after-the-fact
-- signal as a pre-game one. What changes is the label: data_source names the
-- row a UTC duplicate, so no reader takes it for a fourth game of the series.
--
-- Guard: still labelled 'live', still unscored, still without a start. A
-- second pass is a no-op.
DO $$
DECLARE
    n INTEGER;
BEGIN
    UPDATE games
       SET data_source = 'duplicate_utc',
           updated_at  = NOW()::TEXT
     WHERE sport = 'MLB'
       AND game_id IN ('MLB_2026-04-16_NYM_LAD',
                       'MLB_2026-04-17_SEA_SD',
                       'MLB_2026-04-17_COL_HOU')
       AND data_source = 'live'
       AND home_score IS NULL
       AND commence_time IS NULL;
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n > 0 THEN
        RAISE NOTICE 'mlb_phantom_utc_rows: % row(s) relabelled duplicate_utc', n;
    END IF;
END $$;
