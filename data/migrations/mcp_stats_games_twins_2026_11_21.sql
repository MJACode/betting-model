-- AI assistant (MCP) connector: one NCAAF game is one slate row.
--
-- Matt, 2026-11-21 ("We need the research to be better"). A member asked for
-- tonight's NCAAF pick at 15:53 ET. mcp_meter.calls shows what the connector
-- gave the assistant:
--   get_slate NCAAF today     -> 20 rows, the cap; every one kicked off by
--                                13:05 ET, four were LAST night's finals
--   get_slate NCAAF tomorrow  -> 6 rows: tonight's late games again
--   get_game_lines x6         -> not_found, all six
-- so the assistant fell back to the public web for every number it quoted.
--
-- Cause: public.games holds 574 NCAAF twin pairs (2023-08-26 -> 2026-11-27).
-- The CFBD ingestor used to date a game by its UTC kickoff, so a 9:30 PM ET
-- kick (02:30 UTC) was written as NCAAF_<next day>_...; the odds feed writes
-- the same game under its ET date. data/ingestors/cfbd_ingestor.py now dates
-- by ET, but retain_existing_cfbd_ids KEEPS the old UTC id on purpose
-- (ncaaf_team_game_log / ncaaf_qb_game hold FKs to it), so the twins stay in
-- public.games. Prices are written under the ET id only. "Tomorrow" therefore
-- listed tonight's late games under the CFBD id, which has no prices, and
-- "today" listed last night's games under theirs.
--
-- This view collapses each NCAAF twin to one row, without touching
-- public.games: one row per (home, away, ET date of kickoff). Not the kickoff
-- instant: the live feed rewrites commence_time to the actual kickoff, so on
-- game night Boise State's two rows read 02:30 and 02:40 UTC (v1 of this file
-- keyed on the instant and re-split them). Measured 2026-11-21: 702 pairs on
-- this key, none with three rows, at most 115 minutes apart. The kept row is the
-- one whose game_date is the ET date of its kickoff, then the non-CFBD row,
-- then game_id. game_date is the ET date of the kickoff (CFBD rows with no
-- twin carried the UTC date). A score missing on the kept row is taken from
-- its twin. alias_ids lists every game_id of the game, so a price stored under
-- either id is found (get_game_lines reads it).
--
-- Other sports have no twins (measured on the same query) and pass through
-- unchanged, so their slate reads keep the game_date index.
--
-- Same columns as before plus alias_ids at the end (CREATE OR REPLACE VIEW can
-- only append). mcp_stats_views_2026_11_21.sql carries the same definition.
-- Idempotent on the PROPERTY this file establishes: the view carries the
-- 'mcp_stats.games twins v2' marker in its comment, written by this file only
-- after the ET-date key is in place (v1, keyed on the instant, set no marker).

DO $twins$
BEGIN
  IF to_regclass('mcp_stats.games') IS NULL THEN
    RAISE EXCEPTION 'mcp_stats.games missing: apply mcp_stats_views_2026_11_21.sql first';
  END IF;
  IF coalesce(obj_description(to_regclass('mcp_stats.games'), 'pg_class'), '')
     LIKE '%mcp_stats.games twins v2%' THEN
    RETURN;
  END IF;

  CREATE OR REPLACE VIEW mcp_stats.games AS
  SELECT g.sport, g.game_id, g.game_date, g.season,
         coalesce(g.first_pitch_at, g.commence_time) AS starts_at,
         g.home_team, g.away_team, g.home_score, g.away_score,
         (g.home_score IS NOT NULL AND g.away_score IS NOT NULL) AS final,
         ARRAY[g.game_id] AS alias_ids
    FROM public.games g
   WHERE g.sport <> 'NCAAF'
  UNION ALL
  SELECT t.sport, t.game_id, coalesce(t.et_date, t.game_date), t.season, t.starts_at,
         t.home_team, t.away_team,
         coalesce(t.home_score, t.twin_home_score),
         coalesce(t.away_score, t.twin_away_score),
         (coalesce(t.home_score, t.twin_home_score) IS NOT NULL
          AND coalesce(t.away_score, t.twin_away_score) IS NOT NULL),
         t.alias_ids
    FROM (
      SELECT g.sport, g.game_id, g.game_date, g.season,
             coalesce(g.first_pitch_at, g.commence_time) AS starts_at,
             to_char(nullif(coalesce(g.first_pitch_at, g.commence_time), '')::timestamptz
                     AT TIME ZONE 'America/New_York', 'YYYY-MM-DD') AS et_date,
             g.home_team, g.away_team, g.home_score, g.away_score,
             max(g.home_score) OVER w AS twin_home_score,
             max(g.away_score) OVER w AS twin_away_score,
             array_agg(g.game_id) OVER w AS alias_ids,
             row_number() OVER (w ORDER BY
               (g.game_date = to_char(nullif(coalesce(g.first_pitch_at, g.commence_time), '')::timestamptz
                                      AT TIME ZONE 'America/New_York', 'YYYY-MM-DD')) DESC NULLS LAST,
               (g.data_source IS DISTINCT FROM 'cfbd') DESC,
               g.game_id) AS rn
        FROM public.games g
       WHERE g.sport = 'NCAAF'
      WINDOW w AS (PARTITION BY g.home_team, g.away_team,
                   coalesce(to_char(nullif(coalesce(g.first_pitch_at, g.commence_time), '')::timestamptz
                                    AT TIME ZONE 'America/New_York', 'YYYY-MM-DD'),
                            g.game_id))
    ) t
   WHERE t.rn = 1;

  COMMENT ON VIEW mcp_stats.games IS
    'One row per game; NCAAF twins collapsed on (home, away, ET kickoff date), alias_ids = every game_id. mcp_stats.games twins v2';
  GRANT SELECT ON mcp_stats.games TO mcp_reader;
END
$twins$;
