/**
 * Human-friendly labels and descriptions for each model_id.
 * The id set mirrors the models registry in docs/history/build_state.md.
 * longLabel is the name and shortLabel is the badge: the sport plus the
 * bet type, with no parenthetical. statLabel is the server's stat word
 * and is not part of that rename.
 */

import { hasFetchedThresholds, isBundledPaused, isLiveModel, isModelPaused, isModelRetired } from './thresholds';

/**
 * The market a model trades. `pitcher_prop` / `batter_prop` are MLB-only cuts;
 * every other sport's player market is `player_prop`. Surfaces that OFFER these
 * as a filter must scope the list to the sport on screen — see
 * `lib/pickFilterState.presentCategoriesFor`.
 */
export type ModelCategory = 'game' | 'pitcher_prop' | 'batter_prop' | 'player_prop';

export interface ModelMeta {
  shortLabel: string;
  longLabel: string;
  type: ModelCategory;
  statKey: keyof PlayerStats | null;
  statLabel: string;
}

export interface PlayerStats {
  p_strikeouts: number;
  p_hits_allowed: number;
  p_earned_runs: number;
  outs: number;
  p_walks: number;
  hits: number;
  total_bases: number;
  home_runs: number;
  rbi: number;
  runs: number;
  stolen_bases: number;
  walks: number;
}

export const MODEL_META: Record<string, ModelMeta> = {
  mlb_moneyline: {
    shortLabel: 'ML',
    longLabel: 'MLB Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  mlb_over_under: {
    shortLabel: 'O/U',
    longLabel: 'MLB Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  mlb_runline: {
    shortLabel: 'Spread',
    longLabel: 'MLB Spreads',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // Market-relative run line: de-vig Pinnacle, bet a bettable soft book
  // at the same ±1.5. Replaces the paused mlb_runline *publish path*;
  // mlb_runline itself stays paused. docs/mlb_runline_ou_edge_search.md.
  // The name is "MLB Spreads", same as the paused runline: the method
  // (Pinnacle, market-relative) is not in the label.
  mlb_spread_market: {
    shortLabel: 'Spread',
    longLabel: 'MLB Spreads',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // Market-relative totals: de-vig Pinnacle, bet a bettable soft book
  // at the same total. Replaces the paused mlb_over_under *publish path*;
  // mlb_over_under itself stays paused. Paper until MLB_TOTAL_MARKET_PUBLISH=1.
  mlb_total_market: {
    shortLabel: 'O/U',
    longLabel: 'MLB Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // Paper public-OVER fade: tickets ≥70 (env; 80 supported), bet UNDER.
  // INSERT gated by MLB_TOTAL_PUBLIC_FADE_PUBLISH default 0.
  // mlb_over_under stays paused. docs/mlb_total_public_fade.md.
  mlb_total_public_fade: {
    shortLabel: 'Fade',
    longLabel: 'MLB Totals Fade',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  mlb_f5_moneyline: {
    shortLabel: 'F5 ML',
    longLabel: 'MLB First 5 Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  mlb_f5_over_under: {
    shortLabel: 'F5 O/U',
    longLabel: 'MLB First 5 Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  mlb_f5_runline: {
    shortLabel: 'F5 Spread',
    longLabel: 'MLB First 5 Spreads',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // mlb_live_win_prob + mlb_live_runline are RETIRED (2026-08-30, see
  // thresholds.RETIRED_MODELS). Their labels stay so the picks they already made
  // still render with a name wherever history is shown.
  mlb_live_win_prob: {
    shortLabel: 'LIVE ML',
    longLabel: 'MLB Live Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  mlb_live_total_runs: {
    shortLabel: 'LIVE O/U',
    longLabel: 'MLB Live Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  mlb_live_runline: {
    shortLabel: 'LIVE Spread',
    longLabel: 'MLB Live Spreads',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  mlb_prop_pitcher_k: {
    shortLabel: 'P K',
    longLabel: 'MLB Pitcher Strikeouts',
    type: 'pitcher_prop',
    statKey: 'p_strikeouts',
    statLabel: 'Ks',
  },
  mlb_prop_pitcher_hits: {
    shortLabel: 'P H',
    longLabel: 'MLB Hits Allowed',
    type: 'pitcher_prop',
    statKey: 'p_hits_allowed',
    statLabel: 'Hits Allowed',
  },
  mlb_prop_pitcher_er: {
    shortLabel: 'P ER',
    longLabel: 'MLB Earned Runs',
    type: 'pitcher_prop',
    statKey: 'p_earned_runs',
    statLabel: 'ER',
  },
  mlb_prop_pitcher_outs: {
    shortLabel: 'P Outs',
    longLabel: 'MLB Pitcher Outs',
    type: 'pitcher_prop',
    statKey: 'outs',
    statLabel: 'Outs',
  },
  mlb_prop_pitcher_walks: {
    shortLabel: 'P BB',
    longLabel: 'MLB Pitcher Walks',
    type: 'pitcher_prop',
    statKey: 'p_walks',
    statLabel: 'Walks',
  },
  mlb_prop_batter_hits: {
    shortLabel: 'B H',
    longLabel: 'MLB Hits',
    type: 'batter_prop',
    statKey: 'hits',
    statLabel: 'Hits',
  },
  mlb_prop_batter_tb: {
    shortLabel: 'B TB',
    longLabel: 'MLB Total Bases',
    type: 'batter_prop',
    statKey: 'total_bases',
    statLabel: 'TB',
  },
  // mlb_prop_batter_hr + mlb_prop_batter_rbi are RETIRED (2026-09-02, see
  // thresholds.RETIRED_MODELS). Their labels stay so the picks they already made
  // still render with a name wherever history is shown — do not delete them.
  mlb_prop_batter_hr: {
    shortLabel: 'B HR',
    longLabel: 'MLB Home Runs',
    type: 'batter_prop',
    statKey: 'home_runs',
    statLabel: 'HR',
  },
  mlb_prop_batter_rbi: {
    shortLabel: 'B RBI',
    longLabel: 'MLB RBIs',
    type: 'batter_prop',
    statKey: 'rbi',
    statLabel: 'RBI',
  },
  mlb_prop_batter_runs: {
    shortLabel: 'B R',
    longLabel: 'MLB Runs Scored',
    type: 'batter_prop',
    statKey: 'runs',
    statLabel: 'Runs',
  },
  mlb_prop_batter_sb: {
    shortLabel: 'B SB',
    longLabel: 'MLB Stolen Bases',
    type: 'batter_prop',
    statKey: 'stolen_bases',
    statLabel: 'SB',
  },
  mlb_prop_batter_walks: {
    shortLabel: 'B BB',
    longLabel: 'MLB Batter Walks',
    type: 'batter_prop',
    statKey: 'walks',
    statLabel: 'Walks',
  },

  // ── WNBA ──────────────────────────────────────────────────────────────────
  wnba_moneyline: {
    shortLabel: 'ML',
    longLabel: 'WNBA Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  wnba_over_under: {
    shortLabel: 'O/U',
    longLabel: 'WNBA Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  wnba_spread: {
    shortLabel: 'Spread',
    longLabel: 'WNBA Spreads',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  wnba_prop_player_points: {
    shortLabel: 'PTS',
    longLabel: 'WNBA Points',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Pts',
  },
  wnba_prop_player_rebounds: {
    shortLabel: 'REB',
    longLabel: 'WNBA Rebounds',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Reb',
  },
  wnba_prop_player_assists: {
    shortLabel: 'AST',
    longLabel: 'WNBA Assists',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Ast',
  },
  // One name for the three multi-market prop rules: each bets a retail price
  // against Pinnacle's. The name is "<SPORT> Props"; Pinnacle is not in it.
  wnba_prop_market: {
    shortLabel: 'Props',
    longLabel: 'WNBA Props',
    type: 'player_prop',
    statKey: null,
    statLabel: '',
  },
  wnba_prop_player_threes: {
    shortLabel: '3PM',
    longLabel: 'WNBA Threes',
    type: 'player_prop',
    statKey: null,
    statLabel: '3PM',
  },
  wnba_prop_player_pra: {
    shortLabel: 'PRA',
    longLabel: 'WNBA Pts + Reb + Ast',
    type: 'player_prop',
    statKey: null,
    statLabel: 'PRA',
  },

  // ── NBA ───────────────────────────────────────────────────────────────────
  nba_moneyline: {
    shortLabel: 'ML',
    longLabel: 'NBA Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  nba_over_under: {
    shortLabel: 'O/U',
    longLabel: 'NBA Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  nba_spread: {
    shortLabel: 'Spread',
    longLabel: 'NBA Spreads',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  nba_prop_player_points: {
    shortLabel: 'PTS',
    longLabel: 'NBA Points',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Pts',
  },
  nba_prop_player_rebounds: {
    shortLabel: 'REB',
    longLabel: 'NBA Rebounds',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Reb',
  },
  nba_prop_player_assists: {
    shortLabel: 'AST',
    longLabel: 'NBA Assists',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Ast',
  },
  nba_prop_player_threes: {
    shortLabel: '3PM',
    longLabel: 'NBA Threes',
    type: 'player_prop',
    statKey: null,
    statLabel: '3PM',
  },
  nba_prop_player_pra: {
    shortLabel: 'PRA',
    longLabel: 'NBA Pts + Reb + Ast',
    type: 'player_prop',
    statKey: null,
    statLabel: 'PRA',
  },
  nba_prop_player_blocks: {
    shortLabel: 'BLK',
    longLabel: 'NBA Blocks',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Blk',
  },
  nba_prop_player_steals: {
    shortLabel: 'STL',
    longLabel: 'NBA Steals',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Stl',
  },
  nba_prop_player_turnovers: {
    shortLabel: 'TO',
    longLabel: 'NBA Turnovers',
    type: 'player_prop',
    statKey: null,
    statLabel: 'TO',
  },
  nba_prop_player_dd: {
    shortLabel: 'DD',
    longLabel: 'NBA Double-Double',
    type: 'player_prop',
    statKey: null,
    statLabel: 'DD',
  },
  // The 2026-27 NBA prop rule (models/nba_prop_market.py): unders at the best
  // bettable book on Pinnacle's own line, decided 45-57 minutes before tip.
  // ONE id across five markets (points, rebounds, assists, threes, PRA); the
  // market travels on picks.prop_market and the stat is in each pick's label,
  // so statLabel is empty, as for nfl_prop_market and wnba_prop_market.
  nba_prop_market: {
    shortLabel: 'Props',
    longLabel: 'NBA Props',
    type: 'player_prop',
    statKey: null,
    statLabel: '',
  },
  // The NBA projection model (models/nba_prop_projection.py): projects each
  // player's count from his minutes and per-minute rates and bets the books'
  // main line, in the same 45-57 minute window as the rule above. ONE id across six markets (steals,
  // rebounds, blocks+steals, blocks, rebounds+assists, threes), the market on
  // picks.prop_market, like nba_prop_market. Unlike that rule it bets BOTH
  // sides: steals, blocks+steals and threes can be over or under; rebounds,
  // blocks and rebounds+assists are unders. Named "NBA Projected Props" so it
  // is not the same title as "NBA Props": its number is its own projection,
  // not Pinnacle's price. Its shown probability is an
  // upper bound (graded: claimed 0.533, won 0.501; docs/nba_models_2026.md).
  nba_prop_projection: {
    shortLabel: 'Projected',
    longLabel: 'NBA Projected Props',
    type: 'player_prop',
    statKey: null,
    statLabel: '',
  },
  // NBA full-game totals, overs only (models/nba_total_luck.py, 2026-10-17).
  // A team's points allowed include how well its opponents happened to shoot
  // threes and free throws, which is mostly luck. When a total projected with
  // that luck taken out is at least 3 points above the plain projection, it
  // bets the over, once, about an hour before tip, at the best price. The
  // label is the platform's "BOS vs NYK Over 225.5". A game line, not a
  // picker slot: totals are not one (betSlotForModel).
  nba_total_luck: {
    // Chip is the market. The side is already in the pick label beside it.
    shortLabel: 'O/U',
    longLabel: 'NBA Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // NBA home team total points, unders only (models/nba_team_total_luck.py).
  // The same luck read as nba_total_luck, on one team: when the away
  // defence's opponents have shot luckily enough that its plain rating
  // overstates the home team's score by at least 2 points, it bets the home
  // team's own total under, once, about an hour before tip, at the best
  // price. It settles on the home team's final score, overtime included,
  // never the game total. The label is "BOS @ MIL — MIL Team Total Under
  // 115.5". A game line, not a picker slot.
  nba_team_total_luck: {
    // TT is the team total. The side is already in the pick label.
    shortLabel: 'TT',
    longLabel: 'NBA Team Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // NBA first half's total points, overs only (models/nba_first_half_total_luck.py).
  // The same luck read as nba_total_luck, on the first half's line: when both
  // teams' plain defensive ratings overstate how good they have been by at least
  // 2 points of game total, it bets the first half over, once, about an hour
  // before tip, at the best price. It settles on the first two quarters' points,
  // never the game total. The label is "BOS @ MIL — First Half Over 112.5". A game
  // line, not a picker slot.
  nba_first_half_total_luck: {
    // 1H O/U is the first half's total. The side is already in the pick label.
    shortLabel: '1H O/U',
    longLabel: 'NBA First Half Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // NBA first quarter's spread, the hot team (models/nba_q1_trend.py, mike,
  // 2026-11-07): mike's cover-record trend. When a team that is 4-1 or 5-0
  // against the first-quarter spread in its last five games at this venue meets
  // one that is 2-3 or 1-3 there, the last ten games agree, and both teams'
  // first-quarter scoring this season says the hot team covers, it bets that
  // team's first-quarter spread, once, about an hour before tip, at the best
  // price. It settles on the first quarter's score alone. The label is
  // "DEN @ LAC — First Quarter DEN -1.5". A game line, not a picker slot.
  nba_q1_trend: {
    // 1Q Spread, spelled out like '1H Spread'. The side is in the pick label.
    shortLabel: '1Q Spread',
    longLabel: 'NBA First Quarter Spreads',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // NBA first quarter's moneyline, the same hot team (models/nba_q1_trend_ml.py,
  // mike, 2026-11-07): the first-quarter spread model's own rule, bet on that
  // team's first-quarter moneyline, once, about an hour before tip, at the best
  // price. It settles on the first quarter's score alone; a level quarter is a
  // push. The label is "DEN @ LAC — First Quarter DEN ML". A game line, not a
  // picker slot.
  nba_q1_trend_ml: {
    // 1Q ML, spelled like '1Q Spread'. The side is in the pick label.
    shortLabel: '1Q ML',
    longLabel: 'NBA First Quarter Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // NBA in-play (models/nba_live_ig2.py, 2026-11-04): the game-state model's
  // margin against the live line, one bet per game at the first fresh price,
  // during quarters 1-2. The quarter-3 moneyline and spread are held out
  // (HELD_OUT_RULES) and have no entry until they ship. The bet SETTLES ON THE
  // FULL GAME, so the long name says when the bet is placed, never a period:
  // "First Half" in this app names a bet on that period alone
  // (nba_first_half_total_luck). The chip is Early Spread (mike, 2026-11-05:
  // "early is fine"), chosen over the design review's LIVE Spread. Its picks
  // appear on the Live segment only.
  nba_live_spread_q12: {
    shortLabel: 'Early Spread',
    longLabel: 'NBA Early Live Spreads',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // NCAAB in-play (models/ncaab_live_ig.py, 2026-11-07): the game-state
  // model against the live spread or total, one bet per game and rule at the
  // first fresh price, only its biggest edges, at most five a night across
  // the three. Every bet SETTLES ON THE FULL GAME, so the names say when the
  // bet is placed (Early: the first half; Late: halftime on), never a period.
  // The chips follow the NBA in-play model's (Early Spread, mike 2026-11-05),
  // and tell the two spread models apart. Their picks appear on the Live
  // segment only.
  ncaab_live_spread_h1: {
    shortLabel: 'Early Spread',
    longLabel: 'NCAAB Early Live Spreads',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  ncaab_live_spread_h2: {
    shortLabel: 'Late Spread',
    longLabel: 'NCAAB Late Live Spreads',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  ncaab_live_total_h2: {
    shortLabel: 'Late O/U',
    longLabel: 'NCAAB Late Live Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },

  // ── UFC ───────────────────────────────────────────────────────────────────
  ufc_moneyline: {
    shortLabel: 'ML',
    longLabel: 'UFC Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  ufc_total_rounds: {
    shortLabel: 'O/U',
    longLabel: 'UFC Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  ufc_method_of_victory: {
    shortLabel: 'Method',
    longLabel: 'UFC Method of Victory',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  nhl_moneyline: {
    shortLabel: 'ML',
    longLabel: 'NHL Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  nhl_moneyline_regulation: {
    shortLabel: '3-Way',
    longLabel: 'NHL 3-Way Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  nhl_over_under: {
    shortLabel: 'O/U',
    longLabel: 'NHL Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  nhl_puckline: {
    shortLabel: 'Spread',
    longLabel: 'NHL Spreads',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // Blocked shots at DraftKings (models/nhl_prop_blocked_shots.py). The stat
  // label is the wording the server writes into pick_label.
  nhl_prop_blocked_shots: {
    shortLabel: 'BLK',
    longLabel: 'NHL Blocked Shots',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Blocked Shots',
  },
  // Goalie saves, shots on goal and assists (models/nhl_props.py), each
  // priced at the best book on offer. The stat labels are the wording the
  // server writes into pick_label.
  nhl_prop_saves: {
    shortLabel: 'SV',
    longLabel: 'NHL Saves',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Saves',
  },
  nhl_prop_shots_on_goal: {
    shortLabel: 'SOG',
    longLabel: 'NHL Shots on Goal',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Shots on Goal',
  },
  nhl_prop_assists: {
    shortLabel: 'AST',
    longLabel: 'NHL Assists',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Assists',
  },

  // ── NFL ───────────────────────────────────────────────────────────────────
  // The standalone wind-totals card (§28) — under-only, published into picks
  // by scripts/nfl_wind_publisher.py after each scheduled live card run.
  // NCAAF (FBS). ncaaf_spread is a MARGIN-REGRESSION model, not a classifier:
  // it predicts the game's margin from fundamentals and bets when that
  // disagrees with the closing spread by >= 5.5 points. Moneyline and totals
  // are paused (their classifiers held out at AUC ~0.49 — coin flips).
  ncaaf_spread: {
    shortLabel: 'Spread',
    longLabel: 'NCAAF Spreads',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // Same opener rule, DISJOINT high-conviction band: the two books' openers
  // disagree by 2.5+ points instead of 1.0-2.5. Fewer picks, higher rate. A
  // game fires exactly ONE of the two tiers -- the scorer's band ceiling makes
  // them mutually exclusive, so these never double-stake the same side.
  ncaaf_spread_premium: {
    shortLabel: 'Premium',
    longLabel: 'NCAAF Premium Spreads',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // NCAAF live (in-play) lanes — picks appear on the Live tab only.
  ncaaf_live_win_prob: {
    shortLabel: 'LIVE ML',
    longLabel: 'NCAAF Live Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  ncaaf_live_total: {
    shortLabel: 'LIVE O/U',
    longLabel: 'NCAAF Live Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  ncaaf_moneyline: {
    shortLabel: 'ML',
    longLabel: 'NCAAF Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // The live NCAAF moneyline model (models/ncaaf_moneyline_market.py
  // MODEL_ID): the best moneyline against the win chance the books' consensus
  // spread implies. It carries the paused classifier's name above, as the live
  // and paused MLB Totals models share theirs; modelLongWithMark marks the
  // paused one. The id has no 'spread' in it, so markets.ts reads it as a
  // moneyline without a named line.
  ncaaf_moneyline_market: {
    shortLabel: 'ML',
    longLabel: 'NCAAF Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  ncaaf_over_under: {
    shortLabel: 'O/U',
    longLabel: 'NCAAF Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // ── NCAAB ─────────────────────────────────────────────────────────────────
  // Men's college basketball, full-game totals. Named like the other totals
  // ("NCAAB Totals", badge O/U). The id is the one the model writes its picks
  // under (models/ncaab_total_blend.py MODEL_ID). It has no 'over_under' in
  // it, so markets.ts names it for the totals rows. The build plan's id,
  // ncaab_over_under, is not a model. tests/test_mobile_pick_categories.py
  // fails if config scores an id with no label here.
  ncaab_total_blend: {
    shortLabel: 'O/U',
    longLabel: 'NCAAB Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // Men's college basketball, full-game spreads, named like NCAAF's
  // ("NCAAF Spreads", badge Spread). The id is the one the model writes its
  // picks under (models/ncaab_spread_market.py MODEL_ID); it has 'spread' in
  // it, so markets.ts reads the spreads rows without a named line.
  ncaab_spread_market: {
    shortLabel: 'Spread',
    longLabel: 'NCAAB Spreads',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // Men's college basketball, full-game moneylines, named like NCAAF's
  // ("NCAAF Moneyline", badge ML). The id is the one the model writes its
  // picks under (models/ncaab_moneyline_own_spread.py MODEL_ID). It has
  // 'spread' in it because each book's moneyline is priced off that book's
  // own spread; markets.ts names it as a moneyline before its substring test.
  ncaab_moneyline_own_spread: {
    shortLabel: 'ML',
    longLabel: 'NCAAB Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // Men's college basketball, full-game moneylines bet the moment a book
  // first posts its moneyline for a game (models/ncaab_moneyline_first_post.py
  // MODEL_ID). "Opening" is the reader's word for a book's first posted
  // price. The two moneyline models never bet one game twice.
  ncaab_moneyline_first_post: {
    // Its own badge: the Daily Results list and parlay legs show only the
    // badge, so two live 'ML' models in one sport could not be told apart
    // (UX review, 2026-11-03; the NBA Props / Projected Props pattern).
    shortLabel: 'Open ML',
    longLabel: 'NCAAB Opening Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // Men's college basketball, the first half's spread
  // (models/ncaab_first_half_spread.py MODEL_ID). It decides each game once,
  // about ten minutes before tip, at the best first-half spread any bettable
  // book hangs, and settles on the first half's score (no overtime). The label
  // is "Duke @ Kansas — First Half Duke +3.5". A game line, not a picker slot.
  ncaab_first_half_spread: {
    // The first half's spread, spelled out like 'F5 Spread' (UX review,
    // 2026-11-02: "SPR" is read out as letters). The side is in the pick label.
    shortLabel: '1H Spread',
    longLabel: 'NCAAB First Half Spreads',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // Men's college basketball, the first half's total points
  // (models/ncaab_first_half_total.py MODEL_ID). It decides each game once,
  // about an hour before tip, at the best first-half total any bettable book
  // hangs, over or under, and settles on the first half's points (no
  // overtime). The label is "Duke @ Kansas — First Half Under 70.5". A game
  // line, not a picker slot.
  ncaab_first_half_total: {
    // 1H O/U, as the NBA first half's total. The side is in the pick label.
    shortLabel: '1H O/U',
    longLabel: 'NCAAB First Half Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // ── NCAABW ────────────────────────────────────────────────────────────────
  // Women's college basketball, full-game totals: the one women's model
  // (2026-11-10). Named like the other totals ("NCAABW Totals", badge O/U).
  // The open-picks view names each model as this file does, in this order
  // (tests/test_open_picks_view.py), so the string must not vary. The id is
  // the one the model writes its picks under (models/ncaabw_total_blend.py
  // MODEL_ID). It starts with 'ncaab', so sportOfModel tests the women's
  // prefix first, and it has no 'over_under' in it, so markets.ts names it
  // for the totals rows.
  ncaabw_total_blend: {
    shortLabel: 'O/U',
    longLabel: 'NCAABW Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // Women's college basketball in play (models/ncaabw_live_ht.py, 2026-11-11):
  // the full-game total, bet once a game during the halftime break. It
  // SETTLES ON THE FULL GAME. Named like the other one-model live total
  // ('NCAAF Live Totals', LIVE O/U), not "Halftime": a "halftime bet" is a
  // bet on the second half in every betting glossary, and this is not one
  // (UX review, 2026-11-11). The lock row, the model's page and the Live
  // board say when it bets. Its picks appear on the Live segment only.
  ncaabw_live_total_ht: {
    shortLabel: 'LIVE O/U',
    longLabel: 'NCAABW Live Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // Matt, 2026-10-24: "NFL Totals", badge O/U, same as the other totals.
  // No other NFL model uses this name.
  nfl_wind_totals: {
    shortLabel: 'O/U',
    longLabel: 'NFL Totals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // The opener-spread rule: bet the side Pinnacle favours at a soft book's
  // stale number, locked ~2-7 days before kickoff (insert-once — never
  // re-priced; the edge is the staleness).
  nfl_opener_spread: {
    shortLabel: 'Spread',
    longLabel: 'NFL Spreads',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // The market-relative player-prop rule: de-vig Pinnacle, bet the retail
  // outlier. ONE id across every market it trades — the validated number is
  // pooled, and the market itself is on picks.prop_market, so per-market
  // breakdowns are a query rather than eight entries here.
  // Named "NFL Props", same shape as nba_prop_market and wnba_prop_market.
  nfl_prop_market: {
    shortLabel: 'Props',
    longLabel: 'NFL Props',
    type: 'player_prop',
    statKey: null,
    statLabel: '',
  },
  // The in-play NFL leader moneyline (nfl_live_leader/, LIVE 2026-10-13): late
  // in the 4th quarter, the team up 4-16 on DraftKings' live moneyline when
  // its win probability beats the price by 2 points. Same chip as the NCAAF
  // live moneyline; its picks appear on the Live segment only.
  nfl_live_leader_ml: {
    shortLabel: 'LIVE ML',
    longLabel: 'NFL Live Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // The in-play NFL prop model (nfl/live_model). LIVE since 2026-09-05 with the
  // §2 go-live gate deliberately not met (Matt's call).
  //
  // IT TRADES RUSHING ATTEMPTS, NOT PASSING, since 2026-09-21 — pass attempts
  // carried no edge in any season, so the model changed market rather than
  // threshold (docs/nfl_live_rush_attempts.md). These three strings said
  // "Pass Attempts" for a day after that switch, which is how the first rushing
  // pick reached Discord as "Blake Corum Under 11.5 Pass Attempts" — a running
  // back on a passing line, with a correct bet underneath it. The stat is named
  // "Carries" here to match the platform (models/scorer._NFL_PROP_CONFIG) and
  // the pre-game nfl_prop_rush_attempts model, so one stat has one name.
  nfl_live_prop: {
    // NOT 'LIVE Car'. On the Models list and the parlay leg card this chip sits
    // beside a matchup line, and CAR is Carolina -- a stat abbreviation that
    // reads as a team is worse than a long one. The chips carry no maxWidth and
    // no numberOfLines, so the full word fits.
    shortLabel: 'LIVE Carries',
    longLabel: 'NFL Live Rush Attempts',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Carries',
  },
  // The twelve per-stat NFL prop models. They were unpaused server-side
  // (model_action_thresholds.paused = false for all thirteen NFL prop ids on
  // 2026-09-09) while none of them had an entry here — so the board rendered
  // their RAW MODEL ID as the card's market chip ("nfl_prop_rush_rec_yards"),
  // and `MODEL_META[id]?.type` was undefined everywhere it is read, which let
  // them slip through the Market filter's category cut entirely.
  nfl_prop_pass_yards: {
    shortLabel: 'Pass Yds',
    longLabel: 'NFL Passing Yards',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Pass Yds',
  },
  nfl_prop_pass_attempts: {
    shortLabel: 'Pass Att',
    longLabel: 'NFL Pass Attempts',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Pass Att',
  },
  nfl_prop_pass_completions: {
    shortLabel: 'Pass Comp',
    longLabel: 'NFL Pass Completions',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Pass Comp',
  },
  nfl_prop_pass_tds: {
    shortLabel: 'Pass TD',
    longLabel: 'NFL Passing Touchdowns',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Pass TD',
  },
  nfl_prop_rush_yards: {
    shortLabel: 'Rush Yds',
    longLabel: 'NFL Rushing Yards',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Rush Yds',
  },
  nfl_prop_rush_attempts: {
    shortLabel: 'Rush Att',
    longLabel: 'NFL Rush Attempts',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Carries',
  },
  nfl_prop_rec_yards: {
    shortLabel: 'Rec Yds',
    longLabel: 'NFL Receiving Yards',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Rec Yds',
  },
  nfl_prop_receptions: {
    shortLabel: 'Recs',
    longLabel: 'NFL Receptions',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Recs',
  },
  nfl_prop_rush_rec_yards: {
    shortLabel: 'Ru+Re Yds',
    longLabel: 'NFL Rush + Receiving Yards',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Ru+Re Yds',
  },
  nfl_prop_anytime_td: {
    shortLabel: 'Anytime TD',
    longLabel: 'NFL Anytime TD',
    type: 'player_prop',
    statKey: null,
    statLabel: 'TD',
  },
  nfl_prop_tackles_assists: {
    shortLabel: 'Tkl+Ast',
    longLabel: 'NFL Tackles + Assists',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Tkl+Ast',
  },
  nfl_prop_sacks: {
    shortLabel: 'Sacks',
    longLabel: 'NFL Sacks',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Sacks',
  },

  // ── GOLF ──────────────────────────────────────────────────────────────────
  // Per-player markets rendered as single bets (player name in pick_label).
  golf_outright: {
    shortLabel: 'Win',
    longLabel: 'Golf Outright',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  golf_top10: {
    shortLabel: 'T10',
    longLabel: 'Golf Top 10',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  golf_top20: {
    shortLabel: 'T20',
    longLabel: 'Golf Top 20',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  golf_make_cut: {
    shortLabel: 'Cut',
    longLabel: 'Golf Make Cut',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  golf_matchup: {
    shortLabel: 'H2H',
    longLabel: 'Golf Matchups',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
};

export function modelShort(modelId: string): string {
  if (modelId === 'custom') return 'Custom'; // user-entered parlay leg (CUSTOM_MODEL_ID)
  if (modelId === 'stats_line') return 'Your line'; // a Stats-board line (lib/lineLegs.ts LINE_LEG_MODEL_ID)
  return MODEL_META[modelId]?.shortLabel ?? modelId;
}

export function modelLong(modelId: string): string {
  return MODEL_META[modelId]?.longLabel ?? modelId;
}

/**
 * The line under "Model probability" on a pick's "Why this bet?" card.
 *
 * The NBA projection model's probability is its own calibrated number, and it
 * still runs high where it bets: graded walk-forward over 2023-24..2025-26 it
 * claimed 0.533 and won 0.501, against 0.483 implied by the prices
 * (docs/nba_models_2026.md; models/nba_prop_projection.py). So its card says
 * to read the number as an upper bound, and gives the price comparison that
 * shows the 50% still beat the price. Those are graded seasons, not a posted
 * record: the model has none yet (UX review, 2026-10-16). Every other model
 * keeps the plain sentence.
 */
const PROBABILITY_NOTE: Readonly<Record<string, string>> = {
  nba_prop_projection:
    'What our model says is the chance this side hits. Read it as an upper bound: graded on the last ' +
    'three NBA seasons, the bets it would have made averaged 53% here, won 50%, and were priced at 48%.',
  // The market's fair chance plus the walk-forward uplift (+0.1022 for
  // 2026-27): on the 349 graded bets, 61.6% won where the market's fair
  // chance averaged 51.4%. docs/thresholds.md plans on +7.7%, not +16.6%.
  nba_team_total_luck:
    'What our model says is the chance this side hits: the market’s fair chance plus about 10 percentage ' +
    'points, the extra these bets won over the last three NBA seasons (62% won where the market’s fair ' +
    'chance averaged 51%). Read it as an upper bound: plan on a return nearer 8% than the 17% those ' +
    'seasons made.',
  // The market's fair chance plus the walk-forward uplift (+0.0572 for
  // 2026-27): on the 595 graded bets, 56.0% won where the market's fair chance
  // averaged 50.2%. docs/nba_models_2026.md 8.4 has the bets' return, +8.0%.
  nba_first_half_total_luck:
    'What our model says is the chance this side hits: the market’s fair chance plus about 6 percentage ' +
    'points, the extra these bets won over the last three NBA seasons (56% won where the market’s fair ' +
    'chance averaged 50%). Read it as an upper bound.',
  // The market's fair chance plus the walk-forward uplift (+0.1526 for
  // 2026-27): on the 88 graded bets, 65.9% won where the market's fair chance
  // averaged 50.7% (models/nba_q1_trend.py). Few bets, so the extra is large and
  // uncertain; the note says so.
  nba_q1_trend:
    'What our model says is the chance this side covers the first-quarter spread. It is the market’s ' +
    'fair chance plus about 15 percentage points, the extra these bets won over the last three NBA ' +
    'seasons (66% won where the market’s fair chance averaged 51%). That is only 88 bets, so the real ' +
    'extra could be much smaller. Read it as an upper bound.',
  // The market's no-vig chance plus the walk-forward uplift (+0.1416 for
  // 2026-27): on the 81 graded bets whose first quarter was not level, 56.8%
  // won where the market's fair chance averaged 42.6% (models/nba_q1_trend_ml.py).
  // A level quarter is a push, left out of both.
  nba_q1_trend_ml:
    'What our model says is the chance this team wins the first quarter, leaving out a tied quarter, ' +
    'which returns the stake. It is the market’s fair chance plus about 14 percentage points, the extra ' +
    'these bets won over the last three NBA seasons (of the 81 that were not tied, 57% won where the market’s ' +
    'fair chance averaged 43%). That is only 87 bets, 6 of them tied, so the real extra could be much smaller. ' +
    'Read it as an upper bound.',
  // The win chance the bet book's own spread implies
  // (models/ncaab_moneyline_own_spread.py); the edge is that minus the same
  // book's moneyline price's implied chance (UX review, 2026-11-02).
  ncaab_moneyline_own_spread:
    'The chance this side wins according to the spread at the book we bet. Edge is how much higher that ' +
    'is than the chance the same book’s moneyline price implies.',
  // The same number, read the moment the book first posted its moneyline
  // (models/ncaab_moneyline_first_post.py).
  ncaab_moneyline_first_post:
    'The chance this side wins according to the spread at the book we bet, when that book first posted ' +
    'its moneyline. Edge is how much higher that is than the chance the moneyline price implies.',
  // The win chance the books' middle spread implies
  // (models/ncaaf_moneyline_market.py); the edge is that minus the bet price's
  // implied chance (UX review, 2026-11-10).
  ncaaf_moneyline_market:
    'The chance this side wins according to the middle point spread across the sportsbooks we check. ' +
    'Edge is how much higher that is than the chance the moneyline price implies.',
  // P(cover | no push) at the bet's own number (models/ncaab_first_half_spread.py):
  // on a whole-number first-half line a push is possible and is left out.
  ncaab_first_half_spread:
    'What our model says is the chance this side covers the first-half spread. On a whole-number ' +
    'line it leaves out a push, which returns the stake.',
  // P(win | no push) at the bet's own number (models/ncaab_first_half_total.py):
  // a first-half total on a whole number can land on it, a push, left out.
  ncaab_first_half_total:
    'What our model says is the chance this side hits, on the first half’s points alone. On a ' +
    'whole-number line it leaves out a push, which returns the stake.',
};

export function modelProbabilityNote(modelId: string): string {
  return PROBABILITY_NOTE[modelId] ?? 'What our model says is the chance this side hits.';
}

// The NBA models that check each game once, about an hour before tip, and
// post only the bets they find: the
// full-game totals overs (scripts/nba_total_luck_card.py, 60-66 minutes out),
// the home team-total unders (scripts/nba_team_total_luck_card.py, 45-66), the
// first-half overs (scripts/nba_first_half_total_luck_card.py, 45-66) and
// the two prop models (scripts/nba_prop_market_card.py,
// nba_prop_projection_card.py, 45-57). Their page is empty most of the day,
// and the morning-run copy sent people back at the wrong time. The NCAAB
// first-half total card (scripts/ncaab_first_half_total_card.py) checks each
// game the same way, on the first-half lines fetched an hour before tip (55
// to 60 minutes out).
const HOUR_BEFORE_TIP_MODELS: readonly string[] = [
  'nba_first_half_total_luck',
  // The NBA first-quarter spreads (scripts/nba_q1_trend_card.py, 45-66).
  'nba_q1_trend',
  // The NBA first-quarter moneylines, on the same fetch (scripts/nba_q1_trend_ml_card.py).
  'nba_q1_trend_ml',
  'ncaab_first_half_total',
  'nba_prop_market',
  'nba_prop_projection',
  'nba_team_total_luck',
  'nba_total_luck',
];

// The models that decide each game once, minutes after DraftKings first posts
// its full-game total, and bet only while that first total and its prices
// are still DraftKings' number: the NCAAB totals card
// (scripts/ncaab_total_card.py, every five minutes, three after each odds
// capture poll; from 2026-11-03, PR #1139). It replaced the 22:00 UTC
// evening-before rule. DraftKings posts most first totals the day before the
// game and some on game day (76% and 21%, measured for #1139,
// docs/sessions/2026-11.md), so the page fills a few bets at a time at no
// fixed hour and prints no clock time. About half of DraftKings' first totals
// change within half an hour (docs/sports/ncaab.md), which the page and Pick
// Detail say, as the opening moneyline's do.
const FIRST_POST_TOTAL_MODELS: readonly string[] = [
  'ncaab_total_blend',
];

// The women's totals card (scripts/ncaabw_total_card.py, every five minutes,
// three after each women's odds capture poll; from 2026-11-10) decides the
// same way: once, minutes after DraftKings first posts a game's total, and
// only while that first total and its prices are still DraftKings' number.
// It is not in the list above because its timing is not the men's, and the
// page says the timing. DraftKings posted its first women's total 1 to 6
// Eastern dates before the game's date in 155 of 1,772 priced games, never
// more (that card's SLATE_DAYS); a first post is a pre-game quote, so the
// other 1,617 came on the game's own date. That first total stood a median
// 136 minutes in 2024-25 and 85 in 2025-26 (docs/sports/ncaabw.md), and one
// in ten changed within 10 minutes (the card's own header), so the page says
// an opening total "can change within minutes", not the men's "often changes
// within half an hour".
const GAME_DAY_FIRST_POST_TOTAL_MODELS: readonly string[] = [
  'ncaabw_total_blend',
];

// The models that decide each game once, on the morning of the game: the
// NCAAB spread card (scripts/ncaab_spread_card.py) reads the spread at each
// of the eight bettable books at 15:00 UTC on game day and posts its bets
// then, in one batch. Nothing posts later in the day, so the hourly-refresh
// copy sent people back for picks that would never come. 15:00 UTC is 10am ET
// in winter and 11am ET from mid-March (the clocks change on the second
// Sunday of March), and the tooltip says both. The empty state says only "by
// noon ET", which covers both: the run is at five past, and a late run still
// reads 15:00 UTC quotes only until 15:59 UTC. The page names no count of
// books: the server's list is set by an environment variable, and the app's
// sportsbook picker lists more books than it (UX review, 2026-11-03).
// The NCAAB moneyline card (scripts/ncaab_moneyline_card.py) decides at the
// same instant and posts in the same batch; its body says what it compares.
// The NCAAF moneyline card (scripts/ncaaf_moneyline_card.py) decides the same
// way an hour earlier, at 14:00 UTC: 10am ET until the clocks go back in early
// November, 9am ET after. Its body says its own times; the shared empty state
// ("by noon ET") covers both.
const GAME_MORNING_MODELS: readonly string[] = [
  'ncaab_moneyline_own_spread',
  'ncaab_spread_market',
  'ncaaf_moneyline_market',
];

// The moneyline model's page body (UX review, 2026-11-02): it bets the book
// whose moneyline is furthest below what that same book's spread implies,
// which need not be the best price, and a moneyline has no line. It never
// bets a side priced shorter than -200 (mike, "-200 max").
const GAME_MORNING_BODY: Readonly<Record<string, string>> = {
  ncaab_moneyline_own_spread:
    'This model decides each game once, at 10am ET on game day (11am ET from mid-March). At each ' +
    'sportsbook we check, it compares the book’s moneyline with the chance of winning that the same ' +
    'book’s spread implies. It bets only some games, each at the one book where that gap is largest, ' +
    'which may not be DraftKings. It never lays more than -200. It skips a game the NCAAB Opening ' +
    'Moneyline model has already bet. A posted bet is never re-priced: it stays at the price it posted at.',
  // The NCAAF moneyline model (UX review, 2026-11-10): the best moneyline on
  // offer against the win chance the books' middle spread implies
  // (models/ncaaf_moneyline_market.py). Never shorter than -200.
  ncaaf_moneyline_market:
    'This model decides each game once, at 10am ET on game day (9am ET from early November). It bets a ' +
    'moneyline only when the best price on offer beats the chance of winning implied by the middle point ' +
    'spread across the sportsbooks we check. That book may not be DraftKings. It never lays more than ' +
    '-200. It skips a game an NCAAF Spreads model has already bet. A posted bet is never re-priced: it ' +
    'stays at the price it posted at.',
};
// The model that bets a book's moneyline minutes after the book first posts
// it (scripts/ncaab_moneyline_first_post_card.py, every minute, on the
// five-minute odds capture): in its evidence 69% of the bets came between
// midnight and noon ET on game day and 26% the afternoon or evening before
// (docs/sports/ncaab.md), so its page fills a few bets at a time at no fixed
// hour. It never bets a side priced shorter than -200. Opening prices move
// fast, which the page says, since that is the one risk particular to these
// bets.
const OPENING_LINE_MODELS: readonly string[] = [
  'ncaab_moneyline_first_post',
];

// The models that check each game once, five to ten minutes before tip, and
// post only the bets they find: the NCAAB first-half spread card
// (scripts/ncaab_first_half_spread_card.py), on the first-half lines fetched
// ten minutes before each tip, or a retry up to five minutes before it. Its
// page fills game by game through the evening, minutes before each tip.
const MINUTES_BEFORE_TIP_MODELS: readonly string[] = [
  'ncaab_first_half_spread',
];

export interface ModelPageTiming {
  /** The tooltip beside "Today's potential picks". */
  title: string;
  body: string;
  /** The empty state's subtitle: when the page will change. */
  empty: string;
  /** The line under today's picks when the model is not paused. */
  note: string;
}

// The NBA in-play model (models/nba_live_ig2.py): when it bets, and
// what its bet settles on. The loop checks games in progress once an hour
// (models/nba_live_loop.py); no clock minute is named, so this copy does not
// go stale if that minute moves. Each bet is on the FULL game.
const NBA_LIVE_TIMING: Readonly<Record<string, { when: string; settles: string }>> = {
  nba_live_spread_q12: {
    when: 'during the first and second quarters',
    settles: 'The bet is on the full-game spread: it settles on the final score, not on the half.',
  },
};

// The NCAAB in-play models (models/ncaab_live_ig.py): when each bets. The loop
// checks games in progress every half hour (models/ncaab_live_loop.py) and
// posts only the night's strongest few. Each bet is on the FULL game.
const NCAAB_LIVE_TIMING: Readonly<Record<string, { when: string; market: string }>> = {
  ncaab_live_spread_h1: { when: 'during the first half', market: 'spread' },
  ncaab_live_spread_h2: { when: 'from halftime until two minutes are left', market: 'spread' },
  ncaab_live_total_h2: { when: 'from halftime until two minutes are left', market: 'total' },
};

// The women's in-play model (models/ncaabw_live_ht.py): one bet a game at most,
// decided during the halftime break (models/ncaabw_live_loop.py reads the
// books every five minutes while a game is at the half).
const NCAABW_HALFTIME_MODEL = 'ncaabw_live_total_ht';

const LIVE_NOT_IN_LIST = 'Its bets appear on the Live Signals board while the game is in play, not in this list.';
const NEVER_REPRICED = 'A posted bet is never re-priced: it stays at the line and price it posted at.';

/** When a model's page fills, said on its own page. */
export function modelPageTiming(modelId: string): ModelPageTiming {
  // In-play models bet during the game. "Today's potential picks" on the
  // model page reads the pre-game board (useTodayPicks excludes is_live), so
  // their bets are never listed there: the copy says where they are instead
  // of promising a pipeline refresh that will never fill the list.
  if (isLiveModel(modelId)) {
    const ncaab = NCAAB_LIVE_TIMING[modelId];
    if (ncaab) {
      return {
        title: 'Bets during the game',
        body:
          `This model checks NCAAB games in progress twice an hour, ${ncaab.when}, and bets each game at ` +
          `most once, at the sportsbook with the best offer. It bets only its biggest edges, and stops after ` +
          `five bets a night across the NCAAB in-play models. The bet is on the full-game ${ncaab.market}: it ` +
          `settles on the final score, overtime included, not on the half. ${LIVE_NOT_IN_LIST} ${NEVER_REPRICED}`,
        empty:
          `This model checks NCAAB games in progress twice an hour, ${ncaab.when}. ${LIVE_NOT_IN_LIST}`,
        note: 'In-play bets appear on Live Signals, not in this list.',
      };
    }
    if (modelId === NCAABW_HALFTIME_MODEL) {
      return {
        title: 'Bets at halftime',
        body:
          'This model checks each NCAABW game during its halftime break and bets it at most once, at the ' +
          'sportsbook with the best offer. The bet is on the full-game total: it settles on the final ' +
          `score, overtime included, not on a half. ${LIVE_NOT_IN_LIST} ${NEVER_REPRICED}`,
        empty: `This model checks each NCAABW game during its halftime break. ${LIVE_NOT_IN_LIST}`,
        note: 'In-play bets appear on Live Signals, not in this list.',
      };
    }
    const nba = NBA_LIVE_TIMING[modelId];
    if (nba) {
      return {
        title: 'Bets during the game',
        body:
          `This model checks NBA games in progress once an hour ${nba.when}, and bets each game at most ` +
          `once, at the sportsbook with the best offer. ${nba.settles} ${LIVE_NOT_IN_LIST} ${NEVER_REPRICED}`,
        empty:
          `This model checks NBA games in progress once an hour ${nba.when}. ${LIVE_NOT_IN_LIST}`,
        note: 'In-play bets appear on Live Signals, not in this list.',
      };
    }
    return {
      title: 'Bets during the game',
      body:
        `This is an in-play model: it checks games while they are being played and posts a bet when it ` +
        `finds one. ${LIVE_NOT_IN_LIST} ${NEVER_REPRICED}`,
      empty: `This model bets while games are being played. ${LIVE_NOT_IN_LIST}`,
      note: 'In-play bets appear on Live Signals, not in this list.',
    };
  }
  // The NBA first quarter's moneyline (models/nba_q1_trend_ml.py): a moneyline
  // has no line, so its page names only the price, as its Pick Detail note
  // does. It says a tied quarter returns the stake (some books also sell a
  // three-way first-quarter moneyline, where a tie loses), and that it bets the
  // same team in the same games as the first-quarter spread model (UX review,
  // 2026-11-07).
  if (modelId === 'nba_q1_trend_ml') {
    return {
      title: 'Checked once per game',
      body:
        'This model checks each game once, about an hour before tip-off, and posts a bet only when it ' +
        'finds one. It bets the same team, in the same games, as the NBA First Quarter Spreads model. ' +
        'A tied first quarter returns the stake. A posted bet is never re-priced: it stays at the price it ' +
        'posted at.',
      empty:
        'This model checks each game about an hour before tip-off and bets only some of them. ' +
        'Nothing has posted today so far.',
      note: 'Posted about an hour before tip-off and never re-priced.',
    };
  }
  if (HOUR_BEFORE_TIP_MODELS.includes(modelId)) {
    return {
      title: 'Checked once per game',
      body:
        'This model checks each game once, about an hour before tip-off, and posts a bet only when it ' +
        'finds one. A posted bet is never re-priced: it stays at the line and price it posted at.',
      empty:
        'This model checks each game about an hour before tip-off and bets only some of them. ' +
        'Nothing has posted today so far.',
      note: 'Posted about an hour before tip-off and never re-priced.',
    };
  }
  if (MINUTES_BEFORE_TIP_MODELS.includes(modelId)) {
    return {
      title: 'Checked once per game',
      body:
        'This model checks each game once, five to ten minutes before tip-off, and posts a bet only ' +
        'when it finds one. A posted bet is never re-priced: it stays at the line and price it posted at.',
      empty:
        'This model checks each game five to ten minutes before tip-off and bets only some of them. ' +
        'Nothing has posted today so far.',
      note: 'Posted five to ten minutes before tip-off and never re-priced.',
    };
  }
  if (OPENING_LINE_MODELS.includes(modelId)) {
    return {
      title: 'Decided when the line opens',
      body:
        'This model checks a game minutes after each book first posts its moneyline, usually overnight or ' +
        'on the morning of the game, sometimes the afternoon or evening before. It compares that moneyline ' +
        'with the chance of winning that the same book’s spread implies. It bets at most once per game, at ' +
        'the book that posted, which may not be DraftKings, and never a game the NCAAB Moneyline model has ' +
        'already bet. It never lays more than -200. An opening price often changes within half an hour: ' +
        'check the book’s price before you bet. A posted bet is never re-priced: it stays at the price it ' +
        'posted at.',
      empty:
        'This model bets only some games, minutes after a book first opens its moneyline. That is usually ' +
        'overnight or on the morning of the game, sometimes the afternoon or evening before. Nothing has ' +
        'posted yet.',
      note: 'Posted when the book opened its moneyline and never re-priced.',
    };
  }
  if (FIRST_POST_TOTAL_MODELS.includes(modelId)) {
    return {
      title: 'Decided when the total opens',
      body:
        'This model decides each game once, at DraftKings’ opening total, usually within minutes of it ' +
        'posting. DraftKings opens most totals the day before the game, some on game day. It bets at ' +
        'DraftKings, and only if DraftKings still offers that opening total at the same prices. If the ' +
        'total or a price has moved, it skips the game. An opening total often changes within half an ' +
        'hour: check DraftKings’ total and price before you bet. A posted bet is never re-priced: it stays ' +
        'at the line and price it posted at.',
      empty:
        'This model bets only some games, usually the day before each one, as DraftKings opens its totals. ' +
        'Nothing has posted yet.',
      note: 'Posted at DraftKings’ opening total and never re-priced.',
    };
  }
  if (GAME_DAY_FIRST_POST_TOTAL_MODELS.includes(modelId)) {
    return {
      title: 'Decided when the total opens',
      body:
        'This model decides each game once, at DraftKings’ opening total, usually within minutes of it ' +
        'posting. DraftKings opens most totals on the day of the game, some up to six days before. It bets ' +
        'at DraftKings, and only if DraftKings still offers that opening total at the same prices. If the ' +
        'total or a price has moved, it skips the game. An opening total can change within minutes: check ' +
        'DraftKings’ total and price before you bet. The pick is for the total and price shown, not a ' +
        'later one. A posted bet is never re-priced: it stays at the line and price it posted at.',
      empty:
        'This model bets only some games, usually on the day of each one, as DraftKings opens its totals. ' +
        'Nothing has posted yet.',
      note: 'Posted at DraftKings’ opening total and never re-priced.',
    };
  }
  if (GAME_MORNING_MODELS.includes(modelId)) {
    return {
      title: 'Decided the morning of the game',
      body:
        GAME_MORNING_BODY[modelId] ??
        'This model decides each game once, at 10am ET on game day (11am ET from mid-March), from the ' +
        'spread at each sportsbook we check. It bets only some games, each at the book with the best line ' +
        'and price, which may not be DraftKings. A posted bet is never re-priced: it stays at the line and ' +
        'price it posted at.',
      empty:
        'This model posts once, in the morning on each game day, and bets only some games. If nothing is ' +
        'here by noon ET, it found no bet today.',
      note: 'Posted the morning of the game and never re-priced.',
    };
  }
  return {
    title: 'Picks lock for the day',
    body:
      "A pick locks the first time this model scores it today and never changes after that — it can't flip between BET and AVOID as lines move.\n\nLines refresh hourly 6am–6pm ET, then every 10 minutes until 11pm, but only newly-priced games get scored on later refreshes.",
    empty:
      "This model hasn't fired a BET signal for today's slate. Check back after the next pipeline refresh, or pull to refresh on the Picks tab.",
    note: "Locked for the day once scored — won't change again until the game ends.",
  };
}

/**
 * The market category of a model — MODEL_META when it has an entry, and the
 * MODEL ID when it does not.
 *
 * Never returns undefined, and that is the point. Every caller that reached
 * for `MODEL_META[id]?.type` had to decide what an unknown model means, and the
 * Market filter decided "let it through": `if (meta && !categories.has(...))`
 * skipped the cut entirely for a model with no entry, so the twelve NFL prop
 * models survived EVERY category — including "Game", where they are not game
 * lines. A model missing its metadata is a labelling bug; it must not also be a
 * filtering bug.
 *
 * The id is a reliable fallback because every model in the registry is named
 * `<sport>_prop_<market>` or `<sport>_<game market>` — pinned by
 * tests/test_mobile_pick_categories.py, which walks every id in
 * ACTION_THRESHOLDS and asserts the derived category matches MODEL_META's.
 */
export function modelCategory(modelId: string): ModelCategory {
  const meta = MODEL_META[modelId];
  if (meta) return meta.type;
  if (modelId.includes('_prop_pitcher_')) return 'pitcher_prop';
  if (modelId.includes('_prop_batter_')) return 'batter_prop';
  if (modelId.includes('_prop_') || modelId.endsWith('_prop')) return 'player_prop';
  return 'game';
}

export function isPropModel(modelId: string): boolean {
  return modelCategory(modelId) !== 'game';
}

// ---------------------------------------------------------------------------
// Bet-type catalog — what the custom-model builder offers
// ---------------------------------------------------------------------------

export type BetTypeSport = 'MLB' | 'WNBA' | 'NBA' | 'NFL' | 'NCAAF' | 'NCAAB' | 'NCAABW' | 'UFC' | 'NHL' | 'GOLF';

/**
 * The on-screen title. "Double-Double" is one word to the wrapper; a
 * zero-width space after the hyphen is a break it may take. No ellipsis.
 */
export function modelDetailTitle(modelId: string): string {
  return modelLong(modelId).replaceAll('Double-Double', 'Double-\u200BDouble');
}

/** Which sport a model_id belongs to, from its prefix. */
export function sportOfModel(modelId: string): BetTypeSport {
  if (modelId.startsWith('wnba')) return 'WNBA';
  if (modelId.startsWith('nba')) return 'NBA';
  if (modelId.startsWith('ncaaf')) return 'NCAAF';
  // The women's prefix first: 'ncaabw_total_blend' starts with 'ncaab' too,
  // so the men's test alone files every women's model under NCAAB.
  if (modelId.startsWith('ncaabw')) return 'NCAABW';
  if (modelId.startsWith('ncaab')) return 'NCAAB';
  if (modelId.startsWith('nfl')) return 'NFL';
  if (modelId.startsWith('ufc')) return 'UFC';
  if (modelId.startsWith('nhl')) return 'NHL';
  if (modelId.startsWith('golf')) return 'GOLF';
  return 'MLB';
}

/**
 * Does any prop model that is neither retired nor paused price this sport's
 * players? Read from the model catalog, not the stat catalog: the
 * multi-market models (nba_prop_market, nba_prop_projection, nfl_prop_market,
 * wnba_prop_market) map to no single stat, so the stat-catalog test said NBA and the NFL had no
 * prop model while both had a live one. NCAAF has only game models, so its
 * player page still says no prop model prices it. Call it at render: the
 * pause flag can come from the server.
 */
export function sportHasLivePropModel(sport: BetTypeSport): boolean {
  return Object.keys(MODEL_META).some(
    (id) => sportOfModel(id) === sport && isPropModel(id) && !isModelRetired(id) && !isModelPaused(id),
  );
}

export interface BetTypeOption {
  /** The underlying model_id — one model prices each market. */
  id: string;
  /** The market name the user sees (never a model id). */
  label: string;
  sport: BetTypeSport;
  type: ModelMeta['type'];
}

const BET_TYPE_SPORT_ORDER: BetTypeSport[] = [
  'MLB',
  'WNBA',
  'NBA',
  'NFL',
  'NCAAF',
  'NCAAB',
  'NCAABW',
  'UFC',
  'NHL',
  'GOLF',
];

/**
 * Every market a custom model can be built on, grouped by sport. Users pick a
 * BET TYPE (moneyline, a specific prop, …), not one of our in-house models —
 * the model_id is only the plumbing underneath. Live (in-play) markets are
 * excluded: live picks are delete-and-rescored every pass and never graded
 * into the backtest universe, so a rule on them could match nothing.
 * Paused and retired models are excluded too — same `isModelPaused` /
 * `isModelRetired` the Models list and Stats add-pick use — so the picker
 * cannot offer a market the catalog has withdrawn. Labels stay on MODEL_META
 * so a pick those models already made still has a name.
 */
export function betTypeGroups(): Array<{ sport: BetTypeSport; options: BetTypeOption[] }> {
  return BET_TYPE_SPORT_ORDER.map((sport) => ({
    sport,
    options: Object.entries(MODEL_META)
      .filter(([id]) =>
        !id.includes('_live_') &&
        !isModelRetired(id) &&
        !isModelPaused(id) &&
        sportOfModel(id) === sport)
      .map(([id, meta]) => ({ id, label: meta.longLabel, sport, type: meta.type })),
  })).filter((g) => g.options.length > 0);
}

/**
 * The three bet types the custom-model picker offers. One row per slot, not
 * one row per model_id — `betTypeGroups()` stays the per-model catalog (pause
 * and retirement still drop ids there) and the picker collapses it.
 *
 * Totals, First-5, live, regulation 3-way and golf outrights are not a slot.
 * A sport that has no active model for a slot omits that row (WNBA's spread
 * is paused, so WNBA has no Spread row; NFL has no moneyline model at all).
 */
export type BetTypeSlot = 'ml' | 'line' | 'props';

export interface BetTypeChoice {
  /** Stable row key: sport + slot, not a model_id. */
  key: string;
  sport: BetTypeSport;
  slot: BetTypeSlot;
  /** Short label. Never MODEL_META.longLabel. */
  label: string;
  subtitle: string;
  /** Active model_ids this choice writes as rules, in catalog order. */
  modelIds: string[];
}

const BET_TYPE_SLOT_ORDER: BetTypeSlot[] = ['ml', 'line', 'props'];

/**
 * Which picker slot a model belongs to, or null when the picker does not
 * offer it. `betTypeGroups` has already dropped paused, retired and live ids;
 * the `_f5_` / `_live_` checks here are the second line so a caller that
 * passes a raw id still cannot surface those markets.
 */
export function betSlotForModel(id: string, type: ModelCategory): BetTypeSlot | null {
  if (id.includes('_live_') || id.includes('_f5_')) return null;
  // NCAAF Spread writes ncaaf_spread only. The premium band is the same
  // market at a higher cut; adding it made a second rule with the same
  // title. Chief of Staff, 2026-09-24.
  if (id === 'ncaaf_spread_premium') return null;
  // The NCAAB first half's spread is not the game's spread line: offered as
  // the "Spread" slot it would read as the full-game spread. Not a picker
  // slot, like the NBA first half's total.
  if (id === 'ncaab_first_half_spread') return null;
  // The NCAAB first half's total, the same: not the game's total line.
  if (id === 'ncaab_first_half_total') return null;
  // The NBA first quarter's spread, the same: not the game's spread line.
  if (id === 'nba_q1_trend') return null;
  // The NBA first quarter's moneyline, the same: not the game's moneyline.
  if (id === 'nba_q1_trend_ml') return null;
  if (type !== 'game') return 'props';
  if (id.includes('moneyline') && !id.includes('regulation')) return 'ml';
  if (id.includes('runline') || id.includes('puckline') || id.includes('_spread')) return 'line';
  return null;
}

function choiceCopy(sport: BetTypeSport, slot: BetTypeSlot): { label: string; subtitle: string } {
  if (slot === 'ml') return { label: 'ML', subtitle: 'Moneyline' };
  if (slot === 'props') return { label: 'Player props', subtitle: 'All player markets' };
  // MLB and NHL use the same word as the other sports. The model names are
  // "Spreads", never "Run line" or "Puck line". The subtitle stays the
  // number, so the row is not "Spread" read twice.
  if (sport === 'MLB' || sport === 'NHL') return { label: 'Spread', subtitle: '±1.5' };
  return { label: 'Spread', subtitle: 'Spread line' };
}

/** Status on a history row. Retired wins. Null while the model still scores.
 *  Shared names (MLB Totals, MLB Spreads, NBA Totals) need this: the Models
 *  list hides the paused or retired id, and the Record tab still shows it. */
export function modelHistoryMark(modelId: string): 'Retired' | 'Paused' | null {
  if (isModelRetired(modelId)) return 'Retired';
  // Until the live table lands, the bundled pause set. The cache can arrive
  // first and disagree with the fetch, which would put "· Paused" on the
  // card footer and take it off again. After the fetch, the server flag
  // wins, same as isModelPaused.
  const paused = hasFetchedThresholds() ? isModelPaused(modelId) : isBundledPaused(modelId);
  return paused ? 'Paused' : null;
}

/** Long name, with the history mark when this id no longer scores.
 *  "MLB Totals · Paused" is not the live "MLB Totals". Retired wins, same
 *  as `modelHistoryMark`. A live id is the long name alone. */
export function modelLongWithMark(modelId: string): string {
  const name = modelLong(modelId);
  const mark = modelHistoryMark(modelId);
  return mark ? `${name} · ${mark}` : name;
}

/**
 * Status on a picker row. Null when none of the slot's models are rules yet.
 * "Added" only when every one is. A partial slot stays tappable.
 */
export function choiceAddedLabel(present: number, total: number): string | null {
  if (present <= 0 || total <= 0) return null;
  if (present >= total) return 'Added';
  return `${present} of ${total} added`;
}

/** Picker rows: at most ML, the sport's line, and Player props. */
export function betTypePickerGroups(): Array<{ sport: BetTypeSport; choices: BetTypeChoice[] }> {
  return betTypeGroups()
    .map((group) => {
      const bySlot = new Map<BetTypeSlot, string[]>();
      for (const opt of group.options) {
        const slot = betSlotForModel(opt.id, opt.type);
        if (!slot) continue;
        const list = bySlot.get(slot) ?? [];
        list.push(opt.id);
        bySlot.set(slot, list);
      }
      const choices: BetTypeChoice[] = [];
      for (const slot of BET_TYPE_SLOT_ORDER) {
        const modelIds = bySlot.get(slot);
        if (!modelIds || modelIds.length === 0) continue;
        const copy = choiceCopy(group.sport, slot);
        choices.push({
          key: `${group.sport}:${slot}`,
          sport: group.sport,
          slot,
          label: copy.label,
          subtitle: copy.subtitle,
          modelIds,
        });
      }
      return { sport: group.sport, choices };
    })
    .filter((g) => g.choices.length > 0);
}

/** Module-load snapshot of `betTypeGroups()` (bundled pause set). Prefer the
 *  function at a render site so a server-flag pause lands without a rebuild. */
export const BET_TYPE_GROUPS: Array<{ sport: BetTypeSport; options: BetTypeOption[] }> =
  betTypeGroups();

/** The one sentence every surface uses for a rule on a retired bet type — the
 *  Models card, the editor's RuleRow, the detail rule line and its empties —
 *  so they cannot drift into three phrasings of the same state. */
export const RETIRED_RULE_CAPTION = 'Retired — no longer scored or counted';

/** Same role as RETIRED_RULE_CAPTION for a paused bet type. A pause does not
 *  unsay the settled record, so this is about the FUTURE (no new picks), not
 *  about the backtest. */
export const PAUSED_RULE_CAPTION = 'Paused — not producing new picks';

/** Suffix on a custom-model rule chip: retired first (stronger), then paused. */
export function betTypeStatusSuffix(modelId: string): string {
  if (isModelRetired(modelId)) return ' (retired)';
  if (isModelPaused(modelId)) return ' (paused)';
  return '';
}

/** Empty-board sentence when every rule on a custom model is withdrawn.
 *  Retired (no longer scored) wins over paused (not producing new picks).
 *  Null when at least one rule is still live — that empty is a quiet slate. */
export function withdrawnRulesEmpty(
  rules: ReadonlyArray<{ model_id: string }>,
): string | null {
  if (rules.length === 0) return null;
  if (rules.every((r) => isModelRetired(r.model_id))) {
    return 'Every bet type in this model has been retired — it is no longer scored.';
  }
  if (rules.every((r) => isModelRetired(r.model_id) || isModelPaused(r.model_id))) {
    return 'Every bet type in this model has been paused — it is not producing new picks.';
  }
  return null;
}

/**
 * How a custom-model rule is titled on the editor, the detail screen, and the
 * Models list. Always the long name. A slot used to return "MLB · Spread"
 * and everything else the long name, so one function returned two shapes
 * and a " · " that was not safe to split. The long name is already the
 * sport plus the bet type, and it tells two prop rules apart.
 */
export function betTypeLabel(modelId: string): string {
  return modelLong(modelId);
}
