-- ncaaf_fcs_visitor_names_2026_09_07 (2026-09-07, mike)
--
-- ONE-OFF. Nine NCAAF games rows written 2026-09-03..06 name the wrong
-- visitor. The Odds API name resolver handed each FCS visitor to the FBS school
-- its name starts with ("Indiana State Sycamores" -> Indiana), because
-- ncaaf_teams is /teams/fbs only. 27 of the 43 picks on those rows (six
-- live-total BETs and the pre-game NONE rows that name the visitor) carry the
-- wrong name in pick_label, and the six BETs were published to Discord and the
-- app under it. mike, 2026-09-07: "fix the labels ... settle the picks".
--
-- Per row, each step guarded so a second pass is a no-op:
--   1. games.away_team  -> the school CFBD names      (guard: still the wrong name)
--   2. games final      -> CFBD's score, from its own row (guard: still NULL), so
--                          the settle step later in the same pass grades the BETs
--   3. picks.pick_label -> the wrong name replaced, whole-word, once
--                          (guard: the label does not already carry the real name)
--
-- game_id is NOT re-keyed: it is the picks' foreign key and the bet of record
-- (CLAUDE.md 1c). The resolver fix that stops this recurring is in
-- data/ingestors/cfbd_ingestor.py in the same PR. Finals were read from the
-- CFBD rows on 2026-09-07 (docs/sessions/2026-09.md, session 253); home_win is
-- derived, not typed -- Idaho State won at Utah State.
DO $$
DECLARE
    fix       RECORD;
    n_names   INTEGER := 0;
    n_finals  INTEGER := 0;
    n_labels  INTEGER := 0;
    r         INTEGER;
BEGIN
    FOR fix IN
        SELECT * FROM (VALUES
            ('NCAAF_2026-09-03_arkansas_missouri',            'Arkansas',       'Arkansas-Pine Bluff', 54, 14),
            ('NCAAF_2026-09-04_indiana_purdue',               'Indiana',        'Indiana State',       44, 19),
            ('NCAAF_2026-09-04_north-carolina_georgia-state', 'North Carolina', 'North Carolina A&T',  59, 10),
            ('NCAAF_2026-09-05_tennessee_georgia',            'Tennessee',      'Tennessee State',     63,  3),
            ('NCAAF_2026-09-05_houston_rice',                 'Houston',        'Houston Christian',   31,  3),
            ('NCAAF_2026-09-05_northwestern_louisiana-tech',  'Northwestern',   'Northwestern State',  80,  6),
            ('NCAAF_2026-09-05_utah_byu',                     'Utah',           'Utah Tech',           63,  7),
            ('NCAAF_2026-09-06_utah_byu',                     'Utah',           'Utah Tech',           63,  7),
            ('NCAAF_2026-09-05_idaho_utah-state',             'Idaho',          'Idaho State',         17, 29)
        ) AS v(game_id, wrong, actual, home_score, away_score)
    LOOP
        UPDATE games
           SET away_team  = fix.actual,
               updated_at = NOW()::TEXT
         WHERE game_id = fix.game_id
           AND sport = 'NCAAF'
           AND away_team = fix.wrong;
        GET DIAGNOSTICS r = ROW_COUNT;
        n_names := n_names + r;

        UPDATE games
           SET home_score = fix.home_score,
               away_score = fix.away_score,
               home_win   = CASE WHEN fix.home_score > fix.away_score THEN 1
                                 WHEN fix.home_score < fix.away_score THEN 0
                            END,
               updated_at = NOW()::TEXT
         WHERE game_id = fix.game_id
           AND sport = 'NCAAF'
           AND home_score IS NULL;
        GET DIAGNOSTICS r = ROW_COUNT;
        n_finals := n_finals + r;

        UPDATE picks
           SET pick_label = regexp_replace(pick_label, '\m' || fix.wrong || '\M', fix.actual)
         WHERE game_id = fix.game_id
           AND pick_label ~ ('\m' || fix.wrong || '\M')
           AND pick_label NOT LIKE '%' || fix.actual || '%';
        GET DIAGNOSTICS r = ROW_COUNT;
        n_labels := n_labels + r;
    END LOOP;

    IF n_names + n_finals + n_labels > 0 THEN
        RAISE NOTICE 'ncaaf_fcs_visitor_names: % visitor name(s), % final(s), % label(s) corrected',
            n_names, n_finals, n_labels;
    END IF;
END $$;
