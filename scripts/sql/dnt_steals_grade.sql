-- Dunks & Threes' free per-player steals prediction (p_stl) graded against the steals props we
-- stored (mike, 2026-11-27: "just test it with the free data"). Read-only. One season per run
-- (:season, our label) and one prop table per run (:props = player_prop_odds, about an hour
-- before tip, or nba_prop_odds_early, 10 hours).
--
-- No book in that history prices Pinnacle steals, so the market is the CONSENSUS: at each
-- player's main line (the line the most books quote), the mean of every book's proportional
-- no-vig over. D&T's over probability is Poisson(p_stl) above the line. A bet takes the best
-- price at that line, 1 unit to win (risk capped at 3). Players who did not play are left out
-- (the bet is void). Names are matched within the game, accents and suffixes stripped.
-- No CASE: the read-only SQL hook refuses the keyword END.
WITH dp AS (
  SELECT p.game_id, pp.p_stl AS lam, pp.stl,
         trim(regexp_replace(regexp_replace(translate(lower(pp.player_name),
           'áàâäãåāčćçéèêëēíìîïñńóòôöõøšśúùûüýžźżđ', 'aaaaaaaccceeeeeiiiinnoooooossuuuuyzzzd'),
           '[^a-z ]', '', 'g'), ' (jr|sr|ii|iii|iv)$', '')) AS nk
  FROM dnt_player_predictions pp JOIN dnt_game_predictions p ON p.dnt_game_id = pp.dnt_game_id
  WHERE p.game_id IS NOT NULL AND p.season = :season AND pp.p_stl IS NOT NULL AND pp.mp > 0),
q AS (
  SELECT game_id, line, bookmaker,
         trim(regexp_replace(regexp_replace(translate(lower(player_name),
           'áàâäãåāčćçéèêëēíìîïñńóòôöõøšśúùûüýžźżđ', 'aaaaaaaccceeeeeiiiinnoooooossuuuuyzzzd'),
           '[^a-z ]', '', 'g'), ' (jr|sr|ii|iii|iv)$', '')) AS nk,
         1 + greatest(over_price, 0) / 100.0 + (over_price < 0)::int * 100.0 / abs(least(over_price, -100)) AS d_over,
         1 + greatest(under_price, 0) / 100.0 + (under_price < 0)::int * 100.0 / abs(least(under_price, -100)) AS d_under
  FROM :props
  WHERE market = 'player_steals' AND over_price IS NOT NULL AND under_price IS NOT NULL
    AND game_id IN (SELECT DISTINCT game_id FROM dp)),
l AS (
  SELECT game_id, nk, line, count(DISTINCT bookmaker) AS books,
         avg((1 / d_over) / (1 / d_over + 1 / d_under)) AS p_mkt,
         max(d_over) AS best_over, max(d_under) AS best_under,
         row_number() OVER (PARTITION BY game_id, nk ORDER BY count(DISTINCT bookmaker) DESC, line) AS rk
  FROM q GROUP BY game_id, nk, line),
j AS (
  SELECT l.*, dp.lam, dp.stl,
         1 - exp(-dp.lam) * (1 + (l.line >= 1.5)::int * dp.lam + (l.line >= 2.5)::int * dp.lam ^ 2 / 2
                             + (l.line >= 3.5)::int * dp.lam ^ 3 / 6) AS p_dnt,
         (dp.stl > l.line)::int AS over_hit
  FROM l JOIN dp ON dp.game_id = l.game_id AND dp.nk = l.nk
  WHERE l.rk = 1 AND l.line < 4),
-- calibration and information: does D&T's distance from the market predict the result?
cal AS (
  SELECT count(*) AS props, round(avg(over_hit)::numeric, 4) AS over_rate,
         round(avg(p_mkt)::numeric, 4) AS mean_p_mkt, round(avg(p_dnt)::numeric, 4) AS mean_p_dnt,
         round(avg((over_hit - p_mkt) ^ 2)::numeric, 5) AS brier_mkt,
         round(avg((over_hit - p_dnt) ^ 2)::numeric, 5) AS brier_dnt,
         round(corr(p_dnt - p_mkt, over_hit - p_mkt)::numeric, 4) AS corr_edge_resid,
         round(regr_slope(over_hit - p_mkt, p_dnt - p_mkt)::numeric, 4) AS slope_edge_resid
  FROM j),
bets AS (
  SELECT p_dnt - p_mkt AS edge,
         (p_dnt > p_mkt)::int * best_over + (p_dnt < p_mkt)::int * best_under AS dec,
         (p_dnt > p_mkt)::int * over_hit + (p_dnt < p_mkt)::int * (1 - over_hit) AS won
  FROM j WHERE p_dnt <> p_mkt),
r AS (SELECT edge, least(1 / (dec - 1), 3) AS risk,
             won * least(1 / (dec - 1), 3) * (dec - 1) - (1 - won) * least(1 / (dec - 1), 3) AS units
      FROM bets),
k AS (SELECT unnest(ARRAY[0.0, 0.03, 0.05, 0.08, 0.10, 0.15]) AS k)
SELECT :season AS season, k.k AS min_edge, count(*) AS bets, round(sum(units)::numeric, 2) AS units,
       round((sum(units) / sum(risk))::numeric, 4) AS roi,
       round((stddev_samp(units / risk) / sqrt(count(*)))::numeric, 4) AS roi_se,
       (SELECT row_to_json(cal) FROM cal) AS calibration
FROM r JOIN k ON abs(r.edge) >= k.k GROUP BY k.k ORDER BY k.k;
