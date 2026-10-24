/**
 * Human-friendly labels and descriptions for each model_id.
 * The id set mirrors the models registry in docs/history/build_state.md.
 * longLabel is the name and shortLabel is the badge: the sport plus the
 * bet type, with no parenthetical. statLabel is the server's stat word
 * and is not part of that rename.
 */

import { hasFetchedThresholds, isBundledPaused, isModelPaused, isModelRetired } from './thresholds';

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
  ncaaf_over_under: {
    shortLabel: 'O/U',
    longLabel: 'NCAAF Totals',
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
};

export function modelProbabilityNote(modelId: string): string {
  return PROBABILITY_NOTE[modelId] ?? 'What our model says is the chance this side hits.';
}

// The NBA models that check each game once, about an hour before tip, and
// post only the bets they find: the
// full-game totals overs (scripts/nba_total_luck_card.py, 60-66 minutes out),
// the home team-total unders (scripts/nba_team_total_luck_card.py, 45-66) and
// the two prop models (scripts/nba_prop_market_card.py,
// nba_prop_projection_card.py, 45-57). Their page is empty most of the day,
// and the morning-run copy sent people back at the wrong time.
const HOUR_BEFORE_TIP_MODELS: readonly string[] = [
  'nba_prop_market',
  'nba_prop_projection',
  'nba_team_total_luck',
  'nba_total_luck',
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

/** When a model's page fills, said on its own page. */
export function modelPageTiming(modelId: string): ModelPageTiming {
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

export type BetTypeSport = 'MLB' | 'WNBA' | 'NBA' | 'NFL' | 'NCAAF' | 'UFC' | 'NHL' | 'GOLF';

/** Which sport a model_id belongs to, from its prefix. */
export function sportOfModel(modelId: string): BetTypeSport {
  if (modelId.startsWith('wnba')) return 'WNBA';
  if (modelId.startsWith('nba')) return 'NBA';
  if (modelId.startsWith('ncaaf')) return 'NCAAF';
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
