/**
 * NFL player-prop correlations, market by market (Matt, 2026-11-12).
 *
 * A 5-leg WAS@NYG slip showed FanDuel at +8037; FanDuel's own slip said
 * +3085. The app had no NFL correlation at all, so it priced Daniels 2+ pass
 * TDs, Diggs 4+ catches and a Diggs TD as if they were unrelated. They are
 * not, and the book knows it.
 *
 * One latent (Gaussian-copula) correlation per pair of markets and
 * relationship, for the OVER x OVER orientation (an anytime TD's "Yes" is its
 * over). Each leg's side flips the sign: over = +1, under = -1.
 *
 *   same_player  the same player's two markets (Diggs catches x Diggs TD)
 *   same_team    two teammates (a QB's pass TDs x his receiver's TD)
 *   opp          players on opposite teams
 *
 * Measured from nfl_player_game_log, 2022 season to 2026-11-09, by
 * scripts/estimate_parlay_correlations.py --sport NFL. Each player-game is
 * scored against a stand-in for his line, his trailing 8-game average rounded
 * to the next half point, and only players a book would list are counted
 * (3+ targets, 6+ carries or 20+ attempts a game). rho is the Bonett-Price
 * tetrachoric estimate from the 2x2 table, the latent correlation the copula
 * takes. Pairs with fewer than 500 player-game pairs are left out (they read 0).
 *
 * The same rows are stored in parlay_correlations (sport 'NFL', the two market
 * keys as the class columns, the relationship as above).
 */

export type PropRel = 'same_player' | 'same_team' | 'opp';

export const NFL_PROP_CORRELATIONS: Readonly<Record<string, number>> = Object.freeze({
  'NFL|player_anytime_td|player_anytime_td|opp': 0.024, // n=43,888
  'NFL|player_anytime_td|player_pass_attempts|opp': 0.084, // n=13,658
  'NFL|player_anytime_td|player_pass_completions|opp': 0.054, // n=13,658
  'NFL|player_anytime_td|player_pass_tds|opp': 0.049, // n=13,658
  'NFL|player_anytime_td|player_pass_yds|opp': 0.043, // n=13,658
  'NFL|player_anytime_td|player_reception_yds|opp': 0.030, // n=62,432
  'NFL|player_anytime_td|player_receptions|opp': 0.040, // n=62,432
  'NFL|player_anytime_td|player_rush_attempts|opp': -0.057, // n=22,995
  'NFL|player_anytime_td|player_rush_reception_yds|opp': 0.013, // n=76,310
  'NFL|player_anytime_td|player_rush_yds|opp': -0.045, // n=22,995
  'NFL|player_pass_attempts|player_pass_attempts|opp': -0.067, // n=1,070
  'NFL|player_pass_attempts|player_pass_completions|opp': -0.068, // n=2,140
  'NFL|player_pass_attempts|player_pass_tds|opp': 0.134, // n=2,140
  'NFL|player_pass_attempts|player_pass_yds|opp': 0.054, // n=2,140
  'NFL|player_pass_attempts|player_reception_yds|opp': 0.011, // n=9,702
  'NFL|player_pass_attempts|player_receptions|opp': -0.054, // n=9,702
  'NFL|player_pass_attempts|player_rush_attempts|opp': 0.057, // n=3,580
  'NFL|player_pass_attempts|player_rush_reception_yds|opp': 0.010, // n=11,863
  'NFL|player_pass_attempts|player_rush_yds|opp': 0.057, // n=3,580
  'NFL|player_pass_completions|player_pass_completions|opp': -0.100, // n=1,070
  'NFL|player_pass_completions|player_pass_tds|opp': 0.112, // n=2,140
  'NFL|player_pass_completions|player_pass_yds|opp': 0.002, // n=2,140
  'NFL|player_pass_completions|player_reception_yds|opp': 0.004, // n=9,702
  'NFL|player_pass_completions|player_receptions|opp': -0.045, // n=9,702
  'NFL|player_pass_completions|player_rush_attempts|opp': -0.014, // n=3,580
  'NFL|player_pass_completions|player_rush_reception_yds|opp': -0.005, // n=11,863
  'NFL|player_pass_completions|player_rush_yds|opp': -0.002, // n=3,580
  'NFL|player_pass_tds|player_pass_tds|opp': 0.167, // n=1,070
  'NFL|player_pass_tds|player_pass_yds|opp': 0.145, // n=2,140
  'NFL|player_pass_tds|player_reception_yds|opp': 0.065, // n=9,702
  'NFL|player_pass_tds|player_receptions|opp': 0.048, // n=9,702
  'NFL|player_pass_tds|player_rush_attempts|opp': -0.003, // n=3,580
  'NFL|player_pass_tds|player_rush_reception_yds|opp': 0.051, // n=11,863
  'NFL|player_pass_tds|player_rush_yds|opp': 0.035, // n=3,580
  'NFL|player_pass_yds|player_pass_yds|opp': 0.040, // n=1,070
  'NFL|player_pass_yds|player_reception_yds|opp': 0.018, // n=9,702
  'NFL|player_pass_yds|player_receptions|opp': -0.015, // n=9,702
  'NFL|player_pass_yds|player_rush_attempts|opp': -0.004, // n=3,580
  'NFL|player_pass_yds|player_rush_reception_yds|opp': 0.004, // n=11,863
  'NFL|player_pass_yds|player_rush_yds|opp': 0.003, // n=3,580
  'NFL|player_reception_yds|player_reception_yds|opp': 0.007, // n=22,198
  'NFL|player_reception_yds|player_receptions|opp': 0.010, // n=44,396
  'NFL|player_reception_yds|player_rush_attempts|opp': -0.013, // n=16,376
  'NFL|player_reception_yds|player_rush_reception_yds|opp': -0.000, // n=54,307
  'NFL|player_reception_yds|player_rush_yds|opp': -0.001, // n=16,376
  'NFL|player_receptions|player_receptions|opp': 0.006, // n=22,198
  'NFL|player_receptions|player_rush_attempts|opp': -0.008, // n=16,376
  'NFL|player_receptions|player_rush_reception_yds|opp': -0.000, // n=54,307
  'NFL|player_receptions|player_rush_yds|opp': 0.008, // n=16,376
  'NFL|player_rush_attempts|player_rush_attempts|opp': -0.211, // n=3,010
  'NFL|player_rush_attempts|player_rush_reception_yds|opp': -0.050, // n=19,984
  'NFL|player_rush_attempts|player_rush_yds|opp': -0.147, // n=6,020
  'NFL|player_rush_reception_yds|player_rush_reception_yds|opp': -0.011, // n=33,174
  'NFL|player_rush_reception_yds|player_rush_yds|opp': -0.033, // n=19,984
  'NFL|player_rush_yds|player_rush_yds|opp': -0.104, // n=3,010
  'NFL|player_anytime_td|player_pass_attempts|same_player': -0.039, // n=2,267
  'NFL|player_anytime_td|player_pass_completions|same_player': -0.006, // n=2,267
  'NFL|player_anytime_td|player_pass_tds|same_player': -0.040, // n=2,267
  'NFL|player_anytime_td|player_pass_yds|same_player': 0.059, // n=2,267
  'NFL|player_anytime_td|player_reception_yds|same_player': 0.353, // n=10,360
  'NFL|player_anytime_td|player_receptions|same_player': 0.311, // n=10,360
  'NFL|player_anytime_td|player_rush_attempts|same_player': 0.387, // n=3,812
  'NFL|player_anytime_td|player_rush_reception_yds|same_player': 0.415, // n=12,661
  'NFL|player_anytime_td|player_rush_yds|same_player': 0.410, // n=3,812
  'NFL|player_pass_attempts|player_pass_completions|same_player': 0.889, // n=2,267
  'NFL|player_pass_attempts|player_pass_tds|same_player': 0.225, // n=2,267
  'NFL|player_pass_attempts|player_pass_yds|same_player': 0.699, // n=2,267
  'NFL|player_pass_completions|player_pass_tds|same_player': 0.355, // n=2,267
  'NFL|player_pass_completions|player_pass_yds|same_player': 0.791, // n=2,267
  'NFL|player_pass_tds|player_pass_yds|same_player': 0.506, // n=2,267
  'NFL|player_reception_yds|player_receptions|same_player': 0.796, // n=10,360
  'NFL|player_reception_yds|player_rush_attempts|same_player': 0.068, // n=1,511
  'NFL|player_reception_yds|player_rush_reception_yds|same_player': 0.950, // n=10,360
  'NFL|player_reception_yds|player_rush_yds|same_player': 0.054, // n=1,511
  'NFL|player_receptions|player_rush_attempts|same_player': 0.010, // n=1,511
  'NFL|player_receptions|player_rush_reception_yds|same_player': 0.743, // n=10,360
  'NFL|player_receptions|player_rush_yds|same_player': -0.042, // n=1,511
  'NFL|player_rush_attempts|player_rush_reception_yds|same_player': 0.713, // n=3,812
  'NFL|player_rush_attempts|player_rush_yds|same_player': 0.772, // n=3,812
  'NFL|player_rush_reception_yds|player_rush_yds|same_player': 0.930, // n=3,812
  'NFL|player_anytime_td|player_anytime_td|same_team': -0.055, // n=38,678
  'NFL|player_anytime_td|player_pass_attempts|same_team': -0.003, // n=11,942
  'NFL|player_anytime_td|player_pass_completions|same_team': 0.069, // n=11,942
  'NFL|player_anytime_td|player_pass_tds|same_team': 0.272, // n=11,942
  'NFL|player_anytime_td|player_pass_yds|same_team': 0.119, // n=11,942
  'NFL|player_anytime_td|player_reception_yds|same_team': 0.016, // n=55,037
  'NFL|player_anytime_td|player_receptions|same_team': -0.008, // n=55,037
  'NFL|player_anytime_td|player_rush_attempts|same_team': 0.006, // n=20,062
  'NFL|player_anytime_td|player_rush_reception_yds|same_team': 0.016, // n=67,261
  'NFL|player_anytime_td|player_rush_yds|same_team': 0.011, // n=20,062
  'NFL|player_pass_attempts|player_reception_yds|same_team': 0.198, // n=9,836
  'NFL|player_pass_attempts|player_receptions|same_team': 0.287, // n=9,836
  'NFL|player_pass_attempts|player_rush_attempts|same_team': -0.110, // n=3,287
  'NFL|player_pass_attempts|player_rush_reception_yds|same_team': 0.117, // n=11,685
  'NFL|player_pass_attempts|player_rush_yds|same_team': -0.181, // n=3,287
  'NFL|player_pass_completions|player_reception_yds|same_team': 0.244, // n=9,836
  'NFL|player_pass_completions|player_receptions|same_team': 0.336, // n=9,836
  'NFL|player_pass_completions|player_rush_attempts|same_team': -0.029, // n=3,287
  'NFL|player_pass_completions|player_rush_reception_yds|same_team': 0.162, // n=11,685
  'NFL|player_pass_completions|player_rush_yds|same_team': -0.131, // n=3,287
  'NFL|player_pass_tds|player_reception_yds|same_team': 0.150, // n=9,836
  'NFL|player_pass_tds|player_receptions|same_team': 0.097, // n=9,836
  'NFL|player_pass_tds|player_rush_attempts|same_team': 0.017, // n=3,287
  'NFL|player_pass_tds|player_rush_reception_yds|same_team': 0.121, // n=11,685
  'NFL|player_pass_tds|player_rush_yds|same_team': 0.002, // n=3,287
  'NFL|player_pass_yds|player_reception_yds|same_team': 0.332, // n=9,836
  'NFL|player_pass_yds|player_receptions|same_team': 0.252, // n=9,836
  'NFL|player_pass_yds|player_rush_attempts|same_team': -0.034, // n=3,287
  'NFL|player_pass_yds|player_rush_reception_yds|same_team': 0.247, // n=11,685
  'NFL|player_pass_yds|player_rush_yds|same_team': -0.109, // n=3,287
  'NFL|player_reception_yds|player_reception_yds|same_team': 0.007, // n=18,748
  'NFL|player_reception_yds|player_receptions|same_team': 0.006, // n=37,496
  'NFL|player_reception_yds|player_rush_attempts|same_team': -0.001, // n=14,902
  'NFL|player_reception_yds|player_rush_reception_yds|same_team': -0.006, // n=46,663
  'NFL|player_reception_yds|player_rush_yds|same_team': -0.033, // n=14,902
  'NFL|player_receptions|player_receptions|same_team': 0.020, // n=18,748
  'NFL|player_receptions|player_rush_attempts|same_team': -0.009, // n=14,902
  'NFL|player_receptions|player_rush_reception_yds|same_team': -0.013, // n=46,663
  'NFL|player_receptions|player_rush_yds|same_team': -0.050, // n=14,902
  'NFL|player_rush_attempts|player_rush_attempts|same_team': -0.030, // n=1,707
  'NFL|player_rush_attempts|player_rush_reception_yds|same_team': 0.004, // n=17,293
  'NFL|player_rush_attempts|player_rush_yds|same_team': 0.015, // n=3,414
  'NFL|player_rush_reception_yds|player_rush_reception_yds|same_team': -0.007, // n=28,699
  'NFL|player_rush_reception_yds|player_rush_yds|same_team': -0.019, // n=17,293
  'NFL|player_rush_yds|player_rush_yds|same_team': 0.031, // n=1,707
});

/** Order-independent key into NFL_PROP_CORRELATIONS. */
export function propPairKey(sport: string, a: string, b: string, rel: PropRel): string {
  const [lo, hi] = a <= b ? [a, b] : [b, a];
  return `${sport}|${lo}|${hi}|${rel}`;
}

/** The market a book lists the alternate ladder under is the same stat. */
export function baseMarket(market: string): string {
  return market.endsWith('_alternate') ? market.slice(0, -'_alternate'.length) : market;
}
