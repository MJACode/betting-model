-- Fill byom_prop_facts.team where the book left it empty.
--
-- Production NFL rows were written with team NULL (78,238 rows, 2023-2026,
-- none set). Opponent, home/away, favorite/underdog, team spread, short
-- week and off a bye all read that column, so they matched no leg.
-- This file sets team from the player log when exactly one team matches
-- the stored player key and that team is one of the two in the game.
-- A quote team already stored is left alone. Two log teams stay unset.
--
-- NOT in ACTIVE_MIGRATIONS. Apply by hand. It does not replace
-- byom_backtest and it does not write picks. Idempotent: a second run
-- only fills rows that are still blank. byom_prop_phase_a_filters is a
-- different file and is not applied here.
--
-- One DO block. The name function is dropped at the end.

DO $mig$
BEGIN
  IF to_regclass('public.byom_prop_facts') IS NULL
     OR to_regclass('public.byom_game_facts') IS NULL THEN
    RAISE EXCEPTION 'byom facts are not present; apply byom_facts_schema_2026_10_16.sql first';
  END IF;

  EXECUTE $fn$
  CREATE OR REPLACE FUNCTION public.byom_norm_player_name(p_name text)
  RETURNS text
  LANGUAGE plpgsql
  IMMUTABLE
  AS $body$
  DECLARE
    s text;
    parts text[];
    n int;
  BEGIN
    IF p_name IS NULL OR btrim(p_name) = '' THEN
      RETURN '';
    END IF;
    s := lower(btrim(p_name));
    s := translate(s,
      'áàâäãåéèêëíìîïóòôöõúùûüýÿñç',
      'aaaaaaeeeeiiiiooooouuuuyync');
    s := translate(s, '‘’ʼ.''', '');
    s := translate(s, '-‐‑‒–—_', '       ');
    s := regexp_replace(s, '[[:space:]]+', ' ', 'g');
    s := btrim(s);
    IF s = '' THEN
      RETURN '';
    END IF;
    parts := regexp_split_to_array(s, ' ');
    n := array_length(parts, 1);
    WHILE n > 1 AND parts[n] IN ('jr', 'sr', 'ii', 'iii', 'iv', 'v') LOOP
      parts := parts[1:n - 1];
      n := array_length(parts, 1);
    END LOOP;
    RETURN array_to_string(parts, ' ');
  END
  $body$
  $fn$;

  IF to_regclass('public.nfl_player_game_log') IS NOT NULL THEN
    UPDATE byom_prop_facts AS f
       SET team = picked.team
      FROM (
        SELECT f2.prop_key,
               min(upper(btrim(l.team))) AS team
          FROM byom_prop_facts f2
          JOIN byom_game_facts g ON g.canonical_key = f2.canonical_key
          JOIN nfl_player_game_log l
            ON l.game_id IN (f2.canonical_key, 'NFL_' || f2.canonical_key)
           AND public.byom_norm_player_name(l.player_name)
               = COALESCE(NULLIF(btrim(f2.player_key), ''),
                          public.byom_norm_player_name(f2.player_name))
         WHERE f2.sport = 'NFL'
           AND (f2.team IS NULL OR btrim(f2.team) = '')
           AND l.team IS NOT NULL
           AND btrim(l.team) <> ''
           AND upper(btrim(l.team)) IN (upper(btrim(g.home_team)), upper(btrim(g.away_team)))
         GROUP BY f2.prop_key
        HAVING count(DISTINCT upper(btrim(l.team))) = 1
      ) AS picked
     WHERE f.prop_key = picked.prop_key
       AND (f.team IS NULL OR btrim(f.team) = '');
  END IF;

  IF to_regclass('public.nba_player_game_log') IS NOT NULL THEN
    UPDATE byom_prop_facts AS f
       SET team = picked.team
      FROM (
        SELECT f2.prop_key,
               min(upper(btrim(l.team))) AS team
          FROM byom_prop_facts f2
          JOIN byom_game_facts g ON g.canonical_key = f2.canonical_key
          JOIN nba_player_game_log l
            ON l.game_id = f2.canonical_key
           AND public.byom_norm_player_name(l.player_name)
               = COALESCE(NULLIF(btrim(f2.player_key), ''),
                          public.byom_norm_player_name(f2.player_name))
         WHERE f2.sport = 'NBA'
           AND (f2.team IS NULL OR btrim(f2.team) = '')
           AND l.team IS NOT NULL
           AND btrim(l.team) <> ''
           AND upper(btrim(l.team)) IN (upper(btrim(g.home_team)), upper(btrim(g.away_team)))
         GROUP BY f2.prop_key
        HAVING count(DISTINCT upper(btrim(l.team))) = 1
      ) AS picked
     WHERE f.prop_key = picked.prop_key
       AND (f.team IS NULL OR btrim(f.team) = '');
  END IF;

  DROP FUNCTION public.byom_norm_player_name(text);
END $mig$;
